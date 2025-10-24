"""
SILO API client for Australian climate data.

This module provides a type-safe, validated interface to the SILO
(Scientific Information for Land Owners) API using Pydantic models.
"""
import hashlib
import io
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

import pandas as pd
import requests
from rapidfuzz import fuzz

from weather_tools.logging_utils import (
    configure_logging,
    get_package_logger,
    resolve_log_level,
)
from weather_tools.silo_models import (
    DataDrillQuery,
    PatchedPointQuery,
    SiloDataset,
    SiloFormat,
    SiloResponse,
)

SILO_BASE_URL = "https://www.longpaddock.qld.gov.au/cgi-bin/silo/"

logger = logging.getLogger(__name__)


class SiloAPIError(Exception):
    """SILO API error exception."""
    pass


class SiloAPI:
    """
    Python client for the SILO (Scientific Information for Land Owners) API.

    This client uses Pydantic models for type-safe, validated queries. SILO provides
    Australian climate data from 1889 onwards with two dataset types:

    **PatchedPoint Dataset**:
        Station-based observational data with infilled gaps. Data comes from Bureau of
        Meteorology weather stations across Australia. Missing observations are filled using
        interpolation from nearby stations. This dataset is ideal when you need data for a
        specific weather station location.

    **DataDrill Dataset**:
        Gridded data at 0.05° × 0.05° resolution (~5km). Data is interpolated across a regular
        grid covering Australia. This dataset is ideal when you need data for any latitude/longitude
        coordinate, including locations without weather stations.

    Both datasets include daily climate variables from 1889 to the present, updated daily.

    For more information, see: https://www.longpaddock.qld.gov.au/silo/

    Examples:
        >>> # Query station data (using environment variable SILO_API_KEY)
        >>> from weather_tools.silo_models import PatchedPointQuery, SiloDateRange, ClimateVariable
        >>> api = SiloAPI()  # Uses SILO_API_KEY environment variable
        >>> query = PatchedPointQuery(
        ...     station_code="30043",
        ...     date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
        ...     values=[ClimateVariable.RAINFALL, ClimateVariable.MAX_TEMP]
        ... )
        >>> response = api.query_patched_point(query)

        >>> # Query gridded data (with explicit API key)
        >>> from weather_tools.silo_models import DataDrillQuery, AustralianCoordinates
        >>> api = SiloAPI(api_key="user@example.com")  # Explicit API key
        >>> query = DataDrillQuery(
        ...     coordinates=AustralianCoordinates(latitude=-27.5, longitude=151.0),
        ...     date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
        ...     values=[ClimateVariable.RAINFALL]
        ... )
        >>> response = api.query_data_drill(query)
    """

    DEFAULT_TIMEOUT = 30
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        enable_cache: bool = True,
        log_level: int | str = logging.INFO,
    ):
        """
        Initialize the SILO API client.

        Args:
            api_key: Your SILO API key (email address). If not provided, will look for SILO_API_KEY environment variable.
            timeout: Request timeout in seconds (default: 30)
            max_retries: Maximum number of retry attempts for failed requests (default: 3)
            retry_delay: Base delay between retries in seconds (default: 1.0)
            enable_cache: Whether to cache API responses (default: False)
            log_level: Logging level for API diagnostics (default: ``INFO``)

        Raises:
            ValueError: If no API key is provided and SILO_API_KEY environment variable is not set

        Example:
            >>> # Using explicit API key
            >>> api = SiloAPI(api_key="user@example.com")
            >>>
            >>> # Using environment variable SILO_API_KEY
            >>> api = SiloAPI()
            >>>
            >>> # With additional options
            >>> api = SiloAPI(enable_cache=True, timeout=60, log_level="DEBUG")
        """
        # Get API key from parameter or environment variable
        if api_key is None:
            api_key = os.getenv("SILO_API_KEY")
            if api_key is None:
                raise ValueError(
                    "API key is required. Either provide api_key parameter or set SILO_API_KEY environment variable."
                )

        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.enable_cache = enable_cache
        self.log_level = resolve_log_level(log_level)
        self._cache: Optional[Dict[str, Any]] = {} if enable_cache else None

        # Ensure logging is configured with a basic setup if not already done.
        # This is a fallback for library usage outside of CLI context.
        root_logger = logging.getLogger()
        if not any(isinstance(h, logging.Handler) for h in root_logger.handlers):
            configure_logging(level=logging.INFO)

        # Set the level on the package logger to control weather_tools.* logging
        # without affecting other libraries or the root logger configuration.
        # We always set the level (not conditionally) to support changing levels
        # between API instances (e.g., DEBUG -> INFO -> DEBUG).
        package_logger = get_package_logger()
        package_logger.setLevel(self.log_level)

        # Also adjust the handler level to match the most restrictive setting.
        # The handler level acts as a global minimum - it should be set to the
        # lowest (most verbose) level requested by any active API instance.
        # Since we can't track all instances, we conservatively match this instance's level.
        for handler in root_logger.handlers:
            if isinstance(handler, logging.Handler) and getattr(handler, "_weather_tools_handler", False):
                # Always update handler to match the current API instance level
                # This allows users to control verbosity by creating new instances
                handler.setLevel(self.log_level)
                break

    def _get_endpoint(self, dataset: SiloDataset) -> str:
        """Get the API endpoint for a given dataset."""
        endpoints = {
            SiloDataset.PATCHED_POINT: "PatchedPointDataset.php",
            SiloDataset.DATA_DRILL: "DataDrillDataset.php",
        }
        return SILO_BASE_URL + endpoints[dataset]

    def _get_cache_key(self, url: str, params: Dict[str, Any]) -> str:
        """Generate a cache key from URL and parameters."""
        param_str = json.dumps(params, sort_keys=True)
        combined = f"{url}:{param_str}"
        return hashlib.md5(combined.encode(), usedforsecurity=False).hexdigest()

    def _make_request(self, url: str, params: Dict[str, Any]) -> requests.Response:
        """Make the HTTP request with retry logic and caching."""
        # Emit constructed URL when debug logging is enabled
        if logger.isEnabledFor(logging.DEBUG):
            param_str = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{url}?{param_str}"
            logger.debug("🌐 Constructed URL: %s", full_url)

        # Check cache first
        if self.enable_cache and self._cache is not None:
            cache_key = self._get_cache_key(url, params)
            if cache_key in self._cache:
                logger.debug("Cache hit for request: %s", cache_key)
                return self._cache[cache_key]

        last_exception = None
        for attempt in range(self.max_retries):
            try:
                logger.debug("Making request (attempt %d/%d): %s", attempt + 1, self.max_retries, url)
                response = requests.get(url, params=params, timeout=self.timeout)

                # HTTP error handling
                if response.status_code >= 400:
                    raise SiloAPIError(f"HTTP {response.status_code}: {response.reason}\n{response.text}")

                # Check for SILO-specific error messages
                if "Sorry" in response.text or "Request Rejected" in response.text:
                    raise SiloAPIError(response.text)

                # Cache successful response
                if self.enable_cache and self._cache is not None:
                    cache_key = self._get_cache_key(url, params)
                    self._cache[cache_key] = response
                    logger.debug("Cached response for: %s", cache_key)

                logger.debug("Request successful on attempt %d", attempt + 1)
                return response

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_exception = e
                logger.warning("Transient error on attempt %d/%d: %s", attempt + 1, self.max_retries, e)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    logger.error("All %d attempts failed", self.max_retries)
                    raise SiloAPIError(
                        f"Request failed after {self.max_retries} attempts: {last_exception}"
                    ) from last_exception
            except SiloAPIError:
                # Don't retry on API errors (bad request, etc.)
                raise

        # Should not reach here, but just in case
        raise SiloAPIError(f"Request failed after {self.max_retries} attempts: {last_exception}")

    def _parse_response(
        self, response: requests.Response, response_format: SiloFormat, dataset: SiloDataset
    ) -> SiloResponse:
        """Parse the response into a structured Pydantic model."""
        if response_format in [
            SiloFormat.CSV,
            SiloFormat.APSIM,
            SiloFormat.NEAR,
            SiloFormat.NAME,
            SiloFormat.ID,
            SiloFormat.ALLDATA,
            SiloFormat.STANDARD,
        ]:
            raw_data = response.text
        else:
            try:
                raw_data = response.json()
            except (ValueError, requests.exceptions.JSONDecodeError):
                raw_data = response.text

        return SiloResponse(raw_data=raw_data, format=response_format, dataset=dataset)

    def query_patched_point(self, query: PatchedPointQuery) -> SiloResponse:
        """
        Query PatchedPoint dataset with a Pydantic model.

        Args:
            query: PatchedPointQuery model with validated parameters

        Returns:
            SiloResponse with structured data

        Raises:
            SiloAPIError: If the API request fails

        Example:
            >>> from weather_tools.silo_models import (
            ...     PatchedPointQuery, SiloDateRange, ClimateVariable, SiloFormat
            ... )
            >>> query = PatchedPointQuery(
            ...     format=SiloFormat.CSV,
            ...     station_code="30043",
            ...     date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
            ...     values=[ClimateVariable.RAINFALL, ClimateVariable.MAX_TEMP]
            ... )
            >>> response = api.query_patched_point(query)
            >>> print(response.to_csv())
        """
        url = self._get_endpoint(SiloDataset.PATCHED_POINT)
        params = query.to_api_params(self.api_key)
        response = self._make_request(url, params)
        return self._parse_response(response, query.format, SiloDataset.PATCHED_POINT)

    def query_data_drill(self, query: DataDrillQuery) -> SiloResponse:
        """
        Query DataDrill dataset with a Pydantic model.

        Args:
            query: DataDrillQuery model with validated parameters

        Returns:
            SiloResponse with structured data

        Raises:
            SiloAPIError: If the API request fails

        Example:
            >>> from weather_tools.silo_models import (
            ...     DataDrillQuery, AustralianCoordinates, SiloDateRange, ClimateVariable
            ... )
            >>> query = DataDrillQuery(
            ...     coordinates=AustralianCoordinates(latitude=-27.5, longitude=151.0),
            ...     date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
            ...     values=[ClimateVariable.RAINFALL]
            ... )
            >>> response = api.query_data_drill(query)
            >>> print(response.to_csv())
        """
        url = self._get_endpoint(SiloDataset.DATA_DRILL)
        params = query.to_api_params(self.api_key)
        response = self._make_request(url, params)
        return self._parse_response(response, query.format, SiloDataset.DATA_DRILL)

    def clear_cache(self) -> None:
        """
        Clear all cached API responses.

        Use this method when you want to force fresh API requests or to free memory.
        Has no effect if caching is not enabled.

        Example:
            >>> api = SiloAPI(api_key="user@example.com", enable_cache=True)
            >>> data = api.query_patched_point(query)  # Cached
            >>> api.clear_cache()
            >>> data = api.query_patched_point(query)  # Fresh request
        """
        if self._cache is not None:
            self._cache.clear()
            logger.info("Cache cleared")

    def get_cache_size(self) -> int:
        """
        Get the number of cached API responses.

        Returns:
            Number of responses currently in cache, or 0 if caching is disabled.

        Example:
            >>> api = SiloAPI(api_key="user@example.com", enable_cache=True)
            >>> api.get_cache_size()
            0
            >>> api.query_patched_point(query)
            >>> api.get_cache_size()
            1
        """
        if self._cache is not None:
            return len(self._cache)
        return 0

    def get_station_data(
        self,
        station_code: str,
        start_date: str,
        end_date: str,
        variables: Optional[List[str]] = None,
        format: str = "csv",
        return_metadata: bool = False,
    ) -> Union[pd.DataFrame, Tuple[pd.DataFrame, dict]]:
        """
        Get weather station data using simple string arguments.

        Args:
            station_code: Bureau of Meteorology station code (e.g., "30043")
            start_date: Start date in format "YYYYMMDD" (e.g., "20230101")
            end_date: End date in format "YYYYMMDD" (e.g., "20231231")
            variables: List of climate variables. If None, gets all available variables.
                      Options: "rainfall", "max_temp", "min_temp", "evaporation",
                      "radiation", "vapour_pressure", "max_rh", "min_rh"
            format: Response format, default "csv"
            return_metadata: If True, returns tuple of (DataFrame, metadata dict)

        Returns:
            pandas.DataFrame with climate data, or tuple of (DataFrame, metadata) if return_metadata=True

        Example:
            >>> api = SiloAPI()
            >>> df = api.get_station_data("30043", "20230101", "20230131", ["rainfall", "max_temp"])
            >>> print(df.head())
            >>>
            >>> # With metadata
            >>> df, metadata = api.get_station_data("30043", "20230101", "20230131",
            ...                                    return_metadata=True)
        """
        from weather_tools.silo_models import (
            ClimateVariable,
            PatchedPointQuery,
            SiloDateRange,
            SiloFormat,
        )

        # Convert string variables to ClimateVariable enum
        if variables is None:
            climate_vars = [
                ClimateVariable.RAINFALL,
                ClimateVariable.MAX_TEMP,
                ClimateVariable.MIN_TEMP,
                ClimateVariable.EVAPORATION,
                ClimateVariable.SOLAR_RADIATION,
                ClimateVariable.VAPOUR_PRESSURE,
            ]
        else:
            var_mapping = {
                "rainfall": ClimateVariable.RAINFALL,
                "max_temp": ClimateVariable.MAX_TEMP,
                "min_temp": ClimateVariable.MIN_TEMP,
                "evaporation": ClimateVariable.EVAPORATION,
                "radiation": ClimateVariable.SOLAR_RADIATION,
                "vapour_pressure": ClimateVariable.VAPOUR_PRESSURE,
                "max_rh": ClimateVariable.RH_TMAX,
                "min_rh": ClimateVariable.RH_TMIN,
            }
            climate_vars = [var_mapping[var.lower()] for var in variables if var.lower() in var_mapping]
            if not climate_vars:
                raise ValueError(f"No valid variables found. Available: {list(var_mapping.keys())}")

        # Convert format string to SiloFormat enum
        format_mapping = {
            "csv": SiloFormat.CSV,
            "apsim": SiloFormat.APSIM,
            "standard": SiloFormat.STANDARD,
        }
        silo_format = format_mapping.get(format.lower(), SiloFormat.CSV)

        # Create query
        query = PatchedPointQuery(
            station_code=station_code,
            date_range=SiloDateRange(start_date=start_date, end_date=end_date),
            values=climate_vars,
            format=silo_format,
        )

        # Execute query
        response = self.query_patched_point(query)

        # Parse to DataFrame
        df = self._response_to_dataframe(response)

        if return_metadata:
            metadata = {
                "station_code": station_code,
                "date_range": {"start": start_date, "end": end_date},
                "variables": variables or [var.value for var in climate_vars],
                "format": format,
                "dataset": "PatchedPoint",
            }
            return df, metadata

        return df

    def get_gridded_data(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        variables: Optional[List[str]] = None,
        format: str = "csv",
        return_metadata: bool = False,
    ) -> Union[pd.DataFrame, Tuple[pd.DataFrame, dict]]:
        """
        Get gridded climate data for any coordinates using simple arguments.

        Args:
            latitude: Latitude in decimal degrees (e.g., -27.5)
            longitude: Longitude in decimal degrees (e.g., 151.0)
            start_date: Start date in format "YYYYMMDD" (e.g., "20230101")
            end_date: End date in format "YYYYMMDD" (e.g., "20231231")
            variables: List of climate variables. If None, gets all available variables.
            format: Response format, default "csv"
            return_metadata: If True, returns tuple of (DataFrame, metadata dict)

        Returns:
            pandas.DataFrame with climate data, or tuple of (DataFrame, metadata) if return_metadata=True

        Example:
            >>> api = SiloAPI()
            >>> df = api.get_gridded_data(-27.5, 151.0, "20230101", "20230131", ["rainfall"])
            >>> print(df.head())
        """
        from weather_tools.silo_models import (
            AustralianCoordinates,
            ClimateVariable,
            DataDrillQuery,
            SiloDateRange,
            SiloFormat,
        )

        # Convert string variables to ClimateVariable enum (same as above)
        if variables is None:
            climate_vars = [
                ClimateVariable.RAINFALL,
                ClimateVariable.MAX_TEMP,
                ClimateVariable.MIN_TEMP,
                ClimateVariable.EVAPORATION,
                ClimateVariable.SOLAR_RADIATION,
                ClimateVariable.VAPOUR_PRESSURE,
            ]
        else:
            var_mapping = {
                "rainfall": ClimateVariable.RAINFALL,
                "max_temp": ClimateVariable.MAX_TEMP,
                "min_temp": ClimateVariable.MIN_TEMP,
                "evaporation": ClimateVariable.EVAPORATION,
                "radiation": ClimateVariable.SOLAR_RADIATION,
                "vapour_pressure": ClimateVariable.VAPOUR_PRESSURE,
                "max_rh": ClimateVariable.RH_TMAX,
                "min_rh": ClimateVariable.RH_TMIN,
            }
            climate_vars = [var_mapping[var.lower()] for var in variables if var.lower() in var_mapping]
            if not climate_vars:
                raise ValueError(f"No valid variables found. Available: {list(var_mapping.keys())}")

        # Convert format string to SiloFormat enum
        format_mapping = {
            "csv": SiloFormat.CSV,
            "apsim": SiloFormat.APSIM,
            "standard": SiloFormat.STANDARD,
        }
        silo_format = format_mapping.get(format.lower(), SiloFormat.CSV)

        # Create query
        query = DataDrillQuery(
            coordinates=AustralianCoordinates(latitude=latitude, longitude=longitude),
            date_range=SiloDateRange(start_date=start_date, end_date=end_date),
            values=climate_vars,
            format=silo_format,
        )

        # Execute query
        response = self.query_data_drill(query)

        # Parse to DataFrame
        df = self._response_to_dataframe(response)

        metadata = json.loads(df.loc[0, "metadata"])
        metadata.update(
            {
                "coordinates": {"latitude": latitude, "longitude": longitude},
                "date_range": {"start": start_date, "end": end_date},
                "variables": variables or [var.value for var in climate_vars],
                "format": format,
                "dataset": "DataDrill",
            }
        )
        # df.drop(columns=["metadata"], inplace=True, errors="ignore")
        df.loc[0, "metadata"] = json.dumps(metadata)

        if return_metadata:
            return df, metadata

        return df

    def search_stations(
        self,
        name_fragment: Optional[str] = None,
        state: Literal["QLD", "NSW", "VIC", "TAS", "SA", "WA", "NT", "ACT"] = None,
        station_code: Optional[str] = None,
        radius_km: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Search for weather stations by name or state.

        Args:
            name_fragment: Partial station name to search for (e.g., "Brisbane"). Underscores can be used for wildcard searching (e.g., "Bri_ne")
            state: State abbreviation (e.g., "QLD", "NSW", "VIC")
            return_metadata: If True, returns tuple of (DataFrame, metadata dict)

        Returns:
            pandas.DataFrame with station information, or tuple of (DataFrame, metadata)

        Example:
            >>> api = SiloAPI()
            >>> stations = api.search_stations("Brisbane")
            >>> print(stations[['name', 'station_code', 'latitude', 'longitude']])
        """
        

        if name_fragment:
            name_fragment = name_fragment.replace(" ", "_")
            query = PatchedPointQuery(format=SiloFormat.NAME, name_fragment=name_fragment)
            if radius_km:
                logger.warning("radius_km is ignored when searching by name_fragment")

        elif radius_km is not None:
            query = PatchedPointQuery(format=SiloFormat.NEAR, radius=radius_km, station_code=station_code)
        else:
            raise ValueError("Either name_fragment or station_code+radius_km must be provided for station search")

        # Execute query
        response = self.query_patched_point(query)

        # Parse to DataFrame
        df = self._response_to_dataframe(response)

        # Filter by state if provided
        if state:
            df = df[df["state"].str.upper() == state.upper()]

        # Sort the DataFrame based on fuzzy matching
        if df.shape[0] > 1 and name_fragment:
            df = df.sort_values(
                by="name",
                key=lambda col: col.map(
                    lambda name: fuzz.ratio(
                        name_fragment.lower(),
                        re.sub(r'\([^)]*\)', '', name).strip().lower()
                    ) if isinstance(name, str) and name_fragment else 0
                ),
                ascending=False,
            )
        return df

    def get_recent_data(
        self,
        station_code: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        days: int = 7,
        variables: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Get recent climate data (last N days) for a station or coordinates.

        Args:
            station_code: Station code (for station data)
            latitude: Latitude (for gridded data, requires longitude)
            longitude: Longitude (for gridded data, requires latitude)
            days: Number of recent days to retrieve (default: 7)
            variables: List of climate variables to retrieve

        Returns:
            pandas.DataFrame with recent climate data

        Example:
            >>> api = SiloAPI()
            >>> # Recent station data
            >>> df = api.get_recent_data(station_code="30043", days=7)
            >>>
            >>> # Recent gridded data
            >>> df = api.get_recent_data(latitude=-27.5, longitude=151.0, days=7)
        """

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        if station_code:
            return self.get_station_data(station_code, start_str, end_str, variables)
        elif latitude is not None and longitude is not None:
            return self.get_gridded_data(latitude, longitude, start_str, end_str, variables)
        else:
            raise ValueError("Either station_code or both latitude/longitude must be provided")

    def _response_to_dataframe(self, response: SiloResponse) -> pd.DataFrame:
        """
        Convert a SiloResponse to a pandas DataFrame.

        Args:
            response: SiloResponse object from API call

        Returns:
            pandas.DataFrame with parsed data
        """
        if response.format == SiloFormat.CSV:
            # Parse CSV data
            csv_data = response.raw_data
            if isinstance(csv_data, str):
                # Use StringIO to read CSV string
                df = pd.read_csv(io.StringIO(csv_data))
                metadata = df.metadata.dropna().to_list()
                metadata = {k.strip(): v.strip() for k, v in (item.split("=") for item in metadata if item and "=" in item)}

                df["date"] = pd.to_datetime(df["YYYY-MM-DD"], errors="coerce")
                df = df.drop(columns=["metadata", "YYYY-MM-DD"], errors="ignore")
                df.loc[0, "metadata"] = json.dumps(metadata)
                df.dropna(subset=["date"], inplace=True)

                return df
            else:
                # Handle non-string data
                return pd.DataFrame([csv_data])
        elif response.format == SiloFormat.NAME:
            return self.parse_station_data(response)
        elif response.format == SiloFormat.NEAR:
            return self.parse_station_data(response)

        else:
            # For non-CSV formats, return as simple DataFrame
            if isinstance(response.raw_data, str):
                # Split lines and create simple DataFrame
                lines = response.raw_data.strip().split("\n")
                return pd.DataFrame({"data": lines})
            else:
                return pd.DataFrame([response.raw_data])

    def parse_station_data(self, response: SiloResponse) -> pd.DataFrame:
        """Parse pipe-delimited station data into a DataFrame."""
        # Split into lines and remove empty lines
        raw_data = response.raw_data
        lines = [line.strip() for line in raw_data.strip().split("\n") if line.strip()]

        # Parse header and data rows
        header_line = lines[0]
        data_lines = lines[1:]

        # Extract column names from header (split by |)
        columns = [col.strip() for col in header_line.split("|")]

        # Parse data rows
        data_rows = []
        for line in data_lines:
            row = [col.strip() for col in line.split("|")]
            data_rows.append(row)

        # Create DataFrame
        df = pd.DataFrame(data_rows, columns=columns)

        # Convert numeric columns
        numeric_columns = ["Number", "Latitude", "Longitud", "Elevat."]
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Rename columns for clarity
        column_mapping = {
            "Number": "station_code",
            "Station name": "name",
            "Latitude": "latitude",
            "Longitud": "longitude",
            "Stat": "state",
            "Elevat.": "elevation",
        }
        df = df.rename(columns=column_mapping)

        return df