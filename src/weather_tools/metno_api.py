"""
met.no API client for weather forecast data.

This module provides a type-safe, validated interface to the met.no
(Norwegian Meteorological Institute) location forecast API using Pydantic models.

**Data Attribution:**
Weather forecast data retrieved using this client is provided by The Norwegian
Meteorological Institute (MET Norway) under Creative Commons 4.0 BY International
(CC BY 4.0) and Norwegian Licence for Open Government Data (NLOD) 2.0.

When using this data, you must provide attribution: "Weather forecast data is based
on data from MET Norway" with a link to https://www.met.no/en where feasible.

**Terms of Service Compliance:**
This client complies with met.no Terms of Service by:
- Including a User-Agent header identifying the application
- Truncating coordinates to 4 decimal places
- Enabling response caching by default to reduce API load
- Using HTTPS exclusively

For full terms: https://developer.yr.no/doc/TermsOfService/
"""

import datetime as dt
import hashlib
import json
import logging
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from weather_tools.logging_utils import configure_logging, get_package_logger, resolve_log_level
from weather_tools.metno_models import (
    MetNoAPIError,
    MetNoFormat,
    MetNoQuery,
    MetNoRateLimitError,
    MetNoResponse,
    MetNoUserAgentError,
)
from weather_tools.variable_register import VARIABLES

# Get package version for User-Agent
try:
    from importlib.metadata import version

    __version__ = version("weather_tools")
except Exception:
    __version__ = "unknown"

METNO_BASE_URL = "https://api.met.no/weatherapi/locationforecast/2.0/"

logger = logging.getLogger(__name__)


class MetNoAPI:
    """
    Python client for the met.no locationforecast API.

    This client uses Pydantic models for type-safe, validated queries. Met.no provides
    weather forecasts up to 9 days ahead for any global coordinate.

    The API requires a custom User-Agent header to identify the application.

    For more information, see: https://api.met.no/weatherapi/locationforecast/2.0/documentation

    Examples:
        >>> # Query forecast (using default User-Agent)
        >>> from weather_tools.metno_models import MetNoQuery
        >>> from weather_tools.silo_models import AustralianCoordinates
        >>> api = MetNoAPI()
        >>> query = MetNoQuery(
        ...     coordinates=AustralianCoordinates(latitude=-27.5, longitude=153.0)
        ... )
        >>> response = api.query_forecast(query)

        >>> # Get daily forecast summaries
        >>> daily_forecasts = api.get_daily_forecast(latitude=-27.5, longitude=153.0, days=9)
    """

    DEFAULT_TIMEOUT = 30
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0

    def __init__(
        self,
        user_agent: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        enable_cache: bool = True,
        cache_expiry_hours: int = 1,
        log_level: int | str = logging.INFO,
    ):
        """
        Initialize the met.no API client.

        Args:
            user_agent: Custom User-Agent header. If not provided, uses default weather-tools identifier.
            timeout: Request timeout in seconds (default: 30)
            max_retries: Maximum number of retry attempts for failed requests (default: 3)
            retry_delay: Base delay between retries in seconds (default: 1.0)
            enable_cache: Whether to cache API responses (default: True)
            cache_expiry_hours: Hours before cache expires (default: 1)
            log_level: Logging level for API diagnostics (default: ``INFO``)

        Example:
            >>> # Using default User-Agent
            >>> api = MetNoAPI()
            >>>
            >>> # With custom User-Agent
            >>> api = MetNoAPI(user_agent="MyApp/1.0 (contact@example.com)")
            >>>
            >>> # With additional options
            >>> api = MetNoAPI(enable_cache=True, timeout=60, log_level="DEBUG")
        """
        # Set User-Agent (required by met.no API)
        if user_agent is None:
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
            user_agent = f"weather-tools/{__version__} (Python {python_version})"

        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.enable_cache = enable_cache
        self.cache_expiry_hours = cache_expiry_hours
        self.log_level = resolve_log_level(log_level)
        self._cache: Optional[Dict[str, Tuple[Any, dt.datetime]]] = {} if enable_cache else None

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
            if isinstance(handler, logging.Handler) and getattr(
                handler, "_weather_tools_handler", False
            ):
                # Always update handler to match the current API instance level
                # This allows users to control verbosity by creating new instances
                handler.setLevel(self.log_level)
                break

    def _get_endpoint(self, format: MetNoFormat) -> str:
        """Get the API endpoint for a given format."""
        endpoints = {
            MetNoFormat.COMPACT: "compact",
            MetNoFormat.COMPLETE: "complete",
        }
        return METNO_BASE_URL + endpoints[format]

    def _get_cache_key(self, url: str, params: Dict[str, Any]) -> str:
        """Generate a cache key from URL and parameters."""
        param_str = json.dumps(params, sort_keys=True)
        combined = f"{url}:{param_str}"
        return hashlib.md5(combined.encode(), usedforsecurity=False).hexdigest()

    def _is_cache_expired(self, cached_time: dt.datetime) -> bool:
        """Check if cached data has expired."""
        age = dt.datetime.now(dt.UTC) - cached_time
        return age.total_seconds() > (self.cache_expiry_hours * 3600)

    def _make_request(self, url: str, params: Dict[str, Any]) -> requests.Response:
        """Make the HTTP request with retry logic and caching."""
        # Emit constructed URL when debug logging is enabled
        if logger.isEnabledFor(logging.DEBUG):
            param_str = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{url}?{param_str}"
            logger.debug("🌐 Constructed URL: %s", full_url)
            logger.debug("📋 User-Agent: %s", self.user_agent)

        # Check cache first
        if self.enable_cache and self._cache is not None:
            cache_key = self._get_cache_key(url, params)
            if cache_key in self._cache:
                cached_response, cached_time = self._cache[cache_key]
                if not self._is_cache_expired(cached_time):
                    logger.debug("Cache hit for request: %s", cache_key)
                    return cached_response
                else:
                    # Remove expired cache entry
                    logger.debug("Cache expired for request: %s", cache_key)
                    del self._cache[cache_key]

        # Set up headers with User-Agent
        headers = {"User-Agent": self.user_agent}

        last_exception = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    "Making request (attempt %d/%d): %s", attempt + 1, self.max_retries, url
                )
                response = requests.get(url, params=params, headers=headers, timeout=self.timeout)

                # Handle specific HTTP errors
                if response.status_code == 403:
                    raise MetNoUserAgentError(
                        f"Met.no API returned 403 Forbidden. "
                        f"This usually means the User-Agent header is invalid or missing. "
                        f"Current User-Agent: {self.user_agent}"
                    )
                elif response.status_code == 429:
                    raise MetNoRateLimitError(
                        "Met.no API rate limit exceeded. Please wait before making more requests."
                    )
                elif response.status_code >= 400:
                    raise MetNoAPIError(
                        f"HTTP {response.status_code}: {response.reason}\n{response.text}"
                    )

                # Cache successful response
                if self.enable_cache and self._cache is not None:
                    cache_key = self._get_cache_key(url, params)
                    self._cache[cache_key] = (response, dt.datetime.now(dt.UTC))
                    logger.debug("Cached response for: %s", cache_key)

                logger.debug("Request successful on attempt %d", attempt + 1)
                return response

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_exception = e
                logger.warning(
                    "Transient error on attempt %d/%d: %s", attempt + 1, self.max_retries, e
                )
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)  # Exponential backoff
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error("All %d attempts failed", self.max_retries)
                    raise MetNoAPIError(
                        f"Request failed after {self.max_retries} attempts: {last_exception}"
                    ) from last_exception
            except (MetNoAPIError, MetNoUserAgentError, MetNoRateLimitError):
                # Don't retry on API-specific errors
                raise

        # Should not reach here, but just in case
        raise MetNoAPIError(f"Request failed after {self.max_retries} attempts: {last_exception}")

    def query_forecast(self, query: MetNoQuery) -> MetNoResponse:
        """
        Query met.no forecast API.

        Args:
            query: MetNoQuery model with validated parameters

        Returns:
            MetNoResponse with raw GeoJSON data

        Raises:
            MetNoAPIError: If the API request fails
            MetNoUserAgentError: If User-Agent is invalid
            MetNoRateLimitError: If rate limit is exceeded

        Example:
            >>> from weather_tools.metno_models import MetNoQuery, MetNoFormat
            >>> from weather_tools.silo_models import AustralianCoordinates
            >>> query = MetNoQuery(
            ...     coordinates=AustralianCoordinates(latitude=-27.5, longitude=153.0),
            ...     format=MetNoFormat.COMPACT
            ... )
            >>> response = api.query_forecast(query)
        """
        url = self._get_endpoint(query.format)
        params = query.to_api_params()
        response = self._make_request(url, params)

        # Parse JSON response
        try:
            raw_data = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError) as e:
            raise MetNoAPIError(f"Failed to parse JSON response: {e}")

        return MetNoResponse(raw_data=raw_data, format=query.format, coordinates=query.coordinates)

    def get_daily_forecast(
        self, latitude: float, longitude: float, days: int = 9, altitude: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Convenience method: Get daily forecast summaries as DataFrame.

        Args:
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            days: Number of forecast days (1-9, default: 9)
            altitude: Optional elevation in meters

        Returns:
            DataFrame with daily aggregated forecasts

        Raises:
            ValueError: If days is not between 1 and 9

        Example:
            >>> api = MetNoAPI()
            >>> df = api.get_daily_forecast(latitude=-27.5, longitude=153.0, days=9)
            >>> print(df[['date', 'min_temp', 'max_temp', 'daily_rain']])
        """
        if days < 1 or days > 9:
            raise ValueError(f"Days must be between 1 and 9, got {days}")

        # Import here to avoid circular import
        from weather_tools.silo_models import AustralianCoordinates

        coords = AustralianCoordinates(latitude=latitude, longitude=longitude)
        query = MetNoQuery(coordinates=coords, format=MetNoFormat.COMPACT)
        response = self.query_forecast(query)

        # Convert to DataFrame and aggregate to daily
        timeseries = response.get_timeseries()
        df = self._timeseries_to_dataframe(timeseries)
        daily_df = self._aggregate_daily(df)

        # Return only requested number of days
        return daily_df.head(days)

    def _timeseries_to_dataframe(self, timeseries: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Convert raw GeoJSON timeseries to flat pandas DataFrame.

        This replaces manual loops with a simple list comprehension and lets
        pandas handle the data structure. Much faster and more maintainable.

        Args:
            timeseries: List of forecast timestamps from met.no API

        Returns:
            DataFrame with time index and all weather variables as columns
        """
        records = []
        for entry in timeseries:
            time_str = entry.get("time")
            if not time_str:
                continue

            # Extract instant weather data (temperature, wind, pressure, etc.)
            instant_data = entry.get("data", {}).get("instant", {}).get("details", {})

            # Start with time and instant measurements
            record = {"time": pd.to_datetime(time_str), **instant_data}

            # Add precipitation and symbol from period data (prefer shortest period)
            for period_name in ["next_1_hours", "next_6_hours", "next_12_hours"]:
                period_data = entry.get("data", {}).get(period_name, {})
                if period_data:
                    # Add precipitation details
                    details = period_data.get("details", {})
                    if "precipitation_amount" in details:
                        record["precipitation_amount"] = details["precipitation_amount"]

                    # Add weather symbol
                    summary = period_data.get("summary", {})
                    if "symbol_code" in summary:
                        record["symbol_code"] = summary["symbol_code"]

                    break  # Use first available period

            records.append(record)

        return pd.DataFrame(records)

    def _aggregate_daily(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate raw hourly forecast data to daily summaries.

        Column naming and aggregation are driven entirely by the central
        ``VARIABLES`` registry (``metno_daily_agg_spec()``), so the output
        columns are canonical SILO names directly — there is no intermediate
        vocabulary and no second rename step. A single raw met.no field may
        produce several canonical columns (e.g. ``air_temperature`` yields both
        ``max_temp`` and ``min_temp``).

        Args:
            df: DataFrame with a ``time`` column and raw met.no fields

        Returns:
            Daily DataFrame with a ``date`` column and canonical variable columns
        """
        # Build pandas named-aggregation kwargs from the registry, keeping only
        # the variables whose raw met.no field is actually present in this frame.
        named_aggs = {}
        for canonical, (raw_field, agg) in VARIABLES.metno_daily_agg_spec().items():
            if raw_field not in df.columns:
                continue
            func = self._get_dominant_symbol_series if agg == "dominant" else agg
            named_aggs[canonical] = pd.NamedAgg(column=raw_field, aggfunc=func)

        daily = df.set_index("time").resample("D").agg(**named_aggs)

        # Reset index to make 'time' a column again, rename to canonical 'date'
        result = daily.reset_index().rename(columns={"time": "date"})

        # Convert to timezone-naive to match SILO data format (SILO uses naive
        # timestamps); prevents tz-aware/naive comparison errors during merge.
        result["date"] = result["date"].dt.tz_localize(None)

        return result

    def _get_dominant_symbol_series(self, symbols: "pd.Series") -> Optional[str]:
        """Aggregation adaptor: pick the dominant symbol from a pandas Series."""
        return self._get_dominant_symbol(symbols.dropna().tolist())

    def _get_dominant_symbol(self, symbols: List[str]) -> Optional[str]:
        """
        Get the most common or severe weather symbol.

        Prioritizes severe weather (thunderstorm > rain > cloudy > clear).
        """
        if not symbols:
            return None

        # Severity ranking (higher = more severe)
        severity_keywords = [
            ("thunder", 100),
            ("lightning", 100),
            ("heavyrain", 90),
            ("rain", 80),
            ("sleet", 75),
            ("snow", 70),
            ("fog", 60),
            ("cloudy", 40),
            ("partlycloudy", 30),
            ("fair", 20),
            ("clearsky", 10),
        ]

        # Find most severe symbol
        max_severity = -1
        most_severe = symbols[0]

        for symbol in symbols:
            symbol_lower = symbol.lower()
            for keyword, severity in severity_keywords:
                if keyword in symbol_lower:
                    if severity > max_severity:
                        max_severity = severity
                        most_severe = symbol
                    break

        return most_severe

    # TODO confirm if metno timezones are handled correctly, else add timezone support. output should match SILO timezone.
    def to_dataframe(
        self,
        response: MetNoResponse,
        daily: bool = True,
    ) -> pd.DataFrame:
        """
        Convert a met.no response to a pandas DataFrame.

        There are exactly two output modes:

        - ``daily=True`` (default): aggregate the hourly forecast to daily
          summaries. Columns use canonical SILO names (``daily_rain``,
          ``max_temp``, ``min_temp``, ``mslp``, plus met.no-only extras such as
          ``relative_humidity``, ``wind_speed``). Driven by the ``VARIABLES``
          registry — see :meth:`_aggregate_daily`.
        - ``daily=False``: the raw hourly forecast with the **raw met.no field
          names** exactly as returned by the API (``air_temperature``,
          ``precipitation_amount``, ``wind_speed``, ``symbol_code``, ...).

        Args:
            response: MetNoResponse from the API
            daily: If True, return daily canonical summaries; if False, return
                raw hourly values with raw met.no names.

        Returns:
            DataFrame with weather data, daily or raw.

        Example:
            >>> response = api.query_forecast(query)
            >>> daily_df = api.to_dataframe(response)            # canonical daily
            >>> raw_df = api.to_dataframe(response, daily=False)  # raw met.no names
        """
        timeseries = response.get_timeseries()
        df = self._timeseries_to_dataframe(timeseries)

        if daily:
            return self._aggregate_daily(df)

        # Raw hourly values with raw met.no names. Make timezone-naive to match
        # SILO format and the daily output.
        if "time" in df.columns:
            df["time"] = df["time"].dt.tz_localize(None)
        return df

    def clear_cache(self) -> None:
        """
        Clear all cached API responses.

        Use this method when you want to force fresh API requests.
        Has no effect if caching is not enabled.

        Example:
            >>> api = MetNoAPI(enable_cache=True)
            >>> data = api.query_forecast(query)  # Cached
            >>> api.clear_cache()
            >>> data = api.query_forecast(query)  # Fresh request
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
            >>> api = MetNoAPI(enable_cache=True)
            >>> api.get_cache_size()
            0
            >>> api.query_forecast(query)
            >>> api.get_cache_size()
            1
        """
        if self._cache is not None:
            return len(self._cache)
        return 0
