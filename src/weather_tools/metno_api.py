"""
met.no API client for weather forecast data.

This module provides a type-safe, validated interface to the met.no
(Norwegian Meteorological Institute) location forecast API using Pydantic models.
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
        >>> daily_forecasts = api.get_daily_forecast(latitude=-27.5, longitude=153.0, days=7)
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
            if isinstance(handler, logging.Handler) and getattr(handler, "_weather_tools_handler", False):
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
                logger.debug("Making request (attempt %d/%d): %s", attempt + 1, self.max_retries, url)
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
                    raise MetNoAPIError(f"HTTP {response.status_code}: {response.reason}\n{response.text}")

                # Cache successful response
                if self.enable_cache and self._cache is not None:
                    cache_key = self._get_cache_key(url, params)
                    self._cache[cache_key] = (response, dt.datetime.now(dt.UTC))
                    logger.debug("Cached response for: %s", cache_key)

                logger.debug("Request successful on attempt %d", attempt + 1)
                return response

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_exception = e
                logger.warning("Transient error on attempt %d/%d: %s", attempt + 1, self.max_retries, e)
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
            days: Number of forecast days (1-9, default: 7)
            altitude: Optional elevation in meters

        Returns:
            DataFrame with daily aggregated forecasts

        Raises:
            ValueError: If days is not between 1 and 9

        Example:
            >>> api = MetNoAPI()
            >>> df = api.get_daily_forecast(latitude=-27.5, longitude=153.0, days=7)
            >>> print(df[['date', 'min_temperature', 'max_temperature', 'total_precipitation']])
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
        daily_df = self._resample(df, "D")

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

    def _resample(self, df: pd.DataFrame, freq: str) -> pd.DataFrame:
        """
        Aggregate DataFrame to specified frequency using pandas resample.

        This replaces ~80 lines of manual aggregation with pandas built-in
        time series operations. Much cleaner and more performant.

        Args:
            df: DataFrame with time index
            freq: Pandas frequency string ('D' for daily, 'W' for weekly, 'M' for monthly)

        Returns:
            Aggregated DataFrame with renamed columns matching SILO conventions
        """
        # Set time as index for resampling
        df = df.set_index("time")

        # Define aggregations for each variable
        aggregated = df.resample(freq).agg({
            "air_temperature": ["min", "max"],
            "precipitation_amount": "sum",
            "wind_speed": ["mean", "max"],
            "relative_humidity": "mean",
            "air_pressure_at_sea_level": "mean",
            "cloud_area_fraction": "mean",
            "symbol_code": lambda x: self._get_dominant_symbol(x.dropna().tolist()),
        })

        # Flatten multi-level column names
        aggregated.columns = ["_".join(col).strip("_") for col in aggregated.columns]

        # Rename to match SILO/user-friendly conventions
        aggregated = aggregated.rename(
            columns={
                "air_temperature_min": "min_temperature",
                "air_temperature_max": "max_temperature",
                "precipitation_amount_sum": "total_precipitation",
                "wind_speed_mean": "avg_wind_speed",
                "wind_speed_max": "max_wind_speed",
                "relative_humidity_mean": "avg_relative_humidity",
                "air_pressure_at_sea_level_mean": "avg_pressure",
                "cloud_area_fraction_mean": "avg_cloud_fraction",
                "symbol_code_<lambda>": "dominant_weather_symbol",
            }
        )

        # Reset index to make 'time' a column again, rename to 'date'
        result = aggregated.reset_index().rename(columns={"time": "date"})

        # Convert to timezone-naive to match SILO data format (SILO uses naive timestamps)
        # This prevents "Cannot compare tz-naive and tz-aware timestamps" errors during merge
        result["date"] = result["date"].dt.tz_localize(None)

        return result

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
        self, response: MetNoResponse, frequency: str = "daily", aggregate_to_daily: Optional[bool] = None
    ) -> pd.DataFrame:
        """
        Convert met.no response to pandas DataFrame with flexible aggregation.

        Args:
            response: MetNoResponse from API
            frequency: Aggregation frequency: 'hourly', 'daily' (default), 'weekly', 'monthly'
                      Pandas frequency codes also accepted: 'D', 'W', 'M'
            aggregate_to_daily: Deprecated. Use frequency='daily' or frequency='hourly' instead.
                               For backwards compatibility, if set to False, uses frequency='hourly'

        Returns:
            DataFrame with weather data at the specified frequency

        Example:
            >>> response = api.query_forecast(query)
            >>> # Daily aggregation (default)
            >>> daily_df = api.to_dataframe(response)
            >>> # Hourly data
            >>> hourly_df = api.to_dataframe(response, frequency='hourly')
            >>> # Weekly aggregation
            >>> weekly_df = api.to_dataframe(response, frequency='weekly')
        """
        # Handle deprecated aggregate_to_daily parameter
        if aggregate_to_daily is not None:
            logger.warning(
                "aggregate_to_daily parameter is deprecated. Use frequency='daily' or frequency='hourly' instead."
            )
            frequency = "daily" if aggregate_to_daily else "hourly"

        # Convert to DataFrame first (always)
        timeseries = response.get_timeseries()
        df = self._timeseries_to_dataframe(timeseries)

        # Normalize frequency parameter
        freq_map = {
            "hourly": None,  # No aggregation
            "daily": "D",
            "weekly": "W",
            "monthly": "M",
            "D": "D",
            "W": "W",
            "M": "M",
        }

        freq = freq_map.get(frequency.lower() if isinstance(frequency, str) else frequency)

        if freq is None:
            # Return hourly data (no aggregation)
            # Convert to timezone-naive to match SILO format
            if "time" in df.columns:
                df["time"] = df["time"].dt.tz_localize(None)
            return df

        # Aggregate using pandas resample
        return self._resample(df, freq)

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
