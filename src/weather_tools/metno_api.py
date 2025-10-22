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
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from weather_tools.metno_models import (
    DailyWeatherSummary,
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
        debug: bool = False,
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
            debug: Whether to print debug information including constructed URLs (default: False)

        Example:
            >>> # Using default User-Agent
            >>> api = MetNoAPI()
            >>>
            >>> # With custom User-Agent
            >>> api = MetNoAPI(user_agent="MyApp/1.0 (contact@example.com)")
            >>>
            >>> # With additional options
            >>> api = MetNoAPI(enable_cache=True, timeout=60, debug=True)
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
        self.debug = debug
        self._cache: Optional[Dict[str, Tuple[Any, dt.datetime]]] = {} if enable_cache else None

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
        # Print constructed URL if debug mode is enabled
        if self.debug:
            param_str = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{url}?{param_str}"
            print(f"🌐 Constructed URL: {full_url}")
            print(f"📋 User-Agent: {self.user_agent}")

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
                        f"Met.no API rate limit exceeded. Please wait before making more requests."
                    )
                elif response.status_code >= 400:
                    raise MetNoAPIError(f"HTTP {response.status_code}: {response.reason}\n{response.text}")

                # Cache successful response
                if self.enable_cache and self._cache is not None:
                    cache_key = self._get_cache_key(url, params)
                    self._cache[cache_key] = (response, dt.datetime.now(dt.UTC))
                    logger.debug("Cached response for: %s", cache_key)

                logger.info("Request successful on attempt %d", attempt + 1)
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
        self, latitude: float, longitude: float, days: int = 7, altitude: Optional[int] = None
    ) -> List[DailyWeatherSummary]:
        """
        Convenience method: Get daily forecast summaries.

        Args:
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            days: Number of forecast days (1-9, default: 7)
            altitude: Optional elevation in meters

        Returns:
            List of daily weather summaries

        Raises:
            ValueError: If days is not between 1 and 9

        Example:
            >>> daily_forecasts = api.get_daily_forecast(
            ...     latitude=-27.5,
            ...     longitude=153.0,
            ...     days=7
            ... )
            >>> for forecast in daily_forecasts:
            ...     print(f"{forecast.date}: {forecast.min_temperature}°C - {forecast.max_temperature}°C")
        """
        if days < 1 or days > 9:
            raise ValueError(f"Days must be between 1 and 9, got {days}")

        # Import here to avoid circular import
        from weather_tools.silo_models import AustralianCoordinates

        coords = AustralianCoordinates(latitude=latitude, longitude=longitude)
        query = MetNoQuery(coordinates=coords, format=MetNoFormat.COMPACT)
        response = self.query_forecast(query)

        # Aggregate to daily summaries
        timeseries = response.get_timeseries()
        daily_summaries = self._aggregate_to_daily(timeseries, coords)

        # Return only requested number of days
        return daily_summaries[:days]

    def _aggregate_to_daily(self, timeseries: List[Dict[str, Any]], coordinates: Any) -> List[DailyWeatherSummary]:
        """
        Aggregate hourly forecasts to daily summaries.

        Args:
            timeseries: List of forecast timestamps from met.no
            coordinates: Coordinates for timezone determination

        Returns:
            List of daily weather summaries

        Logic:
        - Group by date (using UTC for simplicity, could add timezone support)
        - Min/max temperature from all timestamps
        - Sum precipitation amounts (avoiding double-counting)
        - Average wind speed, humidity, pressure
        - Most common/severe weather symbol
        """

        # Group data by date
        def _default_daily_data():
            return {
                "temperatures": [],
                "precipitation": 0.0,
                "wind_speeds": [],
                "humidities": [],
                "pressures": [],
                "cloud_fractions": [],
                "weather_symbols": [],
            }

        daily_data: Dict[dt.date, Dict[str, Any]] = defaultdict(_default_daily_data)

        # Track precipitation periods to avoid double-counting
        precipitation_covered = set()

        for entry in timeseries:
            try:
                time_str = entry.get("time")
                if not time_str:
                    continue

                timestamp = dt.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                date = timestamp.date()

                # Extract instant data
                instant_data = entry.get("data", {}).get("instant", {}).get("details", {})

                # Temperature
                if "air_temperature" in instant_data:
                    daily_data[date]["temperatures"].append(instant_data["air_temperature"])

                # Wind speed
                if "wind_speed" in instant_data:
                    daily_data[date]["wind_speeds"].append(instant_data["wind_speed"])

                # Humidity
                if "relative_humidity" in instant_data:
                    daily_data[date]["humidities"].append(instant_data["relative_humidity"])

                # Pressure
                if "air_pressure_at_sea_level" in instant_data:
                    daily_data[date]["pressures"].append(instant_data["air_pressure_at_sea_level"])

                # Cloud fraction
                if "cloud_area_fraction" in instant_data:
                    daily_data[date]["cloud_fractions"].append(instant_data["cloud_area_fraction"])

                # Extract precipitation from next_1_hours, next_6_hours, or next_12_hours
                # Use the shortest available period to avoid double-counting
                period_key = timestamp.isoformat()
                if period_key not in precipitation_covered:
                    for period_name in ["next_1_hours", "next_6_hours", "next_12_hours"]:
                        period_data = entry.get("data", {}).get(period_name, {})
                        if period_data:
                            details = period_data.get("details", {})
                            if "precipitation_amount" in details:
                                precip = details["precipitation_amount"]
                                daily_data[date]["precipitation"] += precip
                                precipitation_covered.add(period_key)

                                # Also get weather symbol
                                summary = period_data.get("summary", {})
                                if "symbol_code" in summary:
                                    daily_data[date]["weather_symbols"].append(summary["symbol_code"])
                                break  # Use first available period

            except Exception as e:
                logger.warning("Error processing timestamp: %s", e)
                continue

        # Create daily summaries
        summaries = []
        for date in sorted(daily_data.keys()):
            data = daily_data[date]

            summary = DailyWeatherSummary(
                date=date,
                min_temperature=min(data["temperatures"]) if data["temperatures"] else None,
                max_temperature=max(data["temperatures"]) if data["temperatures"] else None,
                total_precipitation=data["precipitation"] if data["precipitation"] > 0 else None,
                avg_wind_speed=sum(data["wind_speeds"]) / len(data["wind_speeds"]) if data["wind_speeds"] else None,
                max_wind_speed=max(data["wind_speeds"]) if data["wind_speeds"] else None,
                avg_relative_humidity=sum(data["humidities"]) / len(data["humidities"]) if data["humidities"] else None,
                avg_pressure=sum(data["pressures"]) / len(data["pressures"]) if data["pressures"] else None,
                avg_cloud_fraction=sum(data["cloud_fractions"]) / len(data["cloud_fractions"])
                if data["cloud_fractions"]
                else None,
                dominant_weather_symbol=self._get_dominant_symbol(data["weather_symbols"]),
            )
            summaries.append(summary)

        return summaries

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

    def to_dataframe(self, response: MetNoResponse, aggregate_to_daily: bool = True) -> pd.DataFrame:
        """
        Convert met.no response to pandas DataFrame.

        Args:
            response: MetNoResponse from API
            aggregate_to_daily: Aggregate hourly data to daily summaries (default: True)

        Returns:
            DataFrame with weather data

        Example:
            >>> response = api.query_forecast(query)
            >>> df = api.to_dataframe(response)
            >>> print(df.head())
        """
        if aggregate_to_daily:
            timeseries = response.get_timeseries()
            daily_summaries = self._aggregate_to_daily(timeseries, response.coordinates)

            # Convert to DataFrame
            records = [summary.model_dump() for summary in daily_summaries]
            df = pd.DataFrame(records)
            return df
        else:
            # Return hourly data
            timeseries = response.get_timeseries()
            records = []

            for entry in timeseries:
                time_str = entry.get("time")
                instant_data = entry.get("data", {}).get("instant", {}).get("details", {})

                record = {"time": time_str}
                record.update(instant_data)

                # Add period data if available
                for period_name in ["next_1_hours", "next_6_hours", "next_12_hours"]:
                    period_data = entry.get("data", {}).get(period_name, {})
                    if period_data:
                        details = period_data.get("details", {})
                        for key, value in details.items():
                            record[f"{period_name}_{key}"] = value
                        break

                records.append(record)

            df = pd.DataFrame(records)
            if "time" in df.columns:
                df["time"] = pd.to_datetime(df["time"])
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
