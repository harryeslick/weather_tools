"""
Pydantic models for met.no API requests and responses.

This module provides type-safe, validated data models for interacting with the
met.no (Norwegian Meteorological Institute) locationforecast API.
"""

import datetime as dt
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MetNoFormat(str, Enum):
    """
    Met.no forecast formats.

    - COMPACT: Standard 9-day forecast with essential variables
    - COMPLETE: Extended forecast including percentile data and additional variables
    """

    COMPACT = "compact"
    COMPLETE = "complete"


class MetNoQuery(BaseModel):
    """
    Query for met.no locationforecast API.

    The met.no API provides 9-day weather forecasts for any global coordinate.
    This package focuses on Australian locations for compatibility with SILO data.

    Examples:
        >>> from weather_tools.silo_models import AustralianCoordinates
        >>> query = MetNoQuery(
        ...     coordinates=AustralianCoordinates(latitude=-27.5, longitude=153.0),
        ...     format=MetNoFormat.COMPACT
        ... )
        >>> params = query.to_api_params()
        >>> print(params)
        {'lat': -27.5, 'lon': 153.0}
    """

    model_config = ConfigDict(use_enum_values=True)

    coordinates: Any = Field(
        ...,
        description="Australian coordinates (GDA94). Import AustralianCoordinates from silo_models.",
    )
    format: MetNoFormat = Field(
        default=MetNoFormat.COMPACT, description="Response format (compact or complete)"
    )

    def to_api_params(self) -> Dict[str, Any]:
        """
        Convert query to met.no API parameters.

        Note: Latitude and longitude are truncated to 4 decimal places as per
        met.no Terms of Service to reduce unnecessary precision and server load.

        Returns:
            Dictionary of query parameters for the API request

        Example:
            >>> query = MetNoQuery(coordinates=AustralianCoordinates(latitude=-27.5, longitude=153.0))
            >>> params = query.to_api_params()
            >>> params
            {'lat': -27.5, 'lon': 153.0}
        """
        # Truncate coordinates to 4 decimals as per met.no Terms of Service
        # https://developer.yr.no/doc/TermsOfService/
        params: Dict[str, Any] = {
            "lat": round(self.coordinates.latitude, 4),
            "lon": round(self.coordinates.longitude, 4),
        }

        # Include altitude if available (altitude is not in AustralianCoordinates)
        if hasattr(self.coordinates, "altitude") and self.coordinates.altitude is not None:
            params["altitude"] = self.coordinates.altitude

        return params


class MetNoResponse(BaseModel):
    """
    Structured met.no API response.

    Contains the raw GeoJSON response from the API along with metadata about
    the query and when the forecast was generated.

    The response follows the GeoJSON Feature format with weather data in a
    timeseries under properties.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    raw_data: Dict[str, Any] = Field(..., description="Raw GeoJSON response from met.no API")
    format: MetNoFormat = Field(..., description="Response format used (compact or complete)")
    coordinates: Any = Field(..., description="Coordinates for this forecast")
    generated_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.UTC),
        description="Timestamp when forecast was retrieved",
    )

    def get_timeseries(self) -> List[Dict[str, Any]]:
        """
        Extract timeseries data from GeoJSON structure.

        Returns:
            List of timestep dictionaries containing forecast data

        Example:
            >>> response = MetNoResponse(raw_data={...}, format=MetNoFormat.COMPACT, coordinates=coords)
            >>> timeseries = response.get_timeseries()
            >>> len(timeseries)
            216  # Approximately 9 days of hourly data
        """
        return self.raw_data.get("properties", {}).get("timeseries", [])

    def get_meta(self) -> Dict[str, Any]:
        """
        Extract metadata from GeoJSON structure.

        Returns:
            Dictionary containing metadata about the forecast
        """
        return self.raw_data.get("properties", {}).get("meta", {})


class ForecastTimestamp(BaseModel):
    """
    Single forecast timestamp with instant and period data.

    Represents weather conditions at a specific time, including both
    instantaneous values (temperature, humidity) and period forecasts
    (precipitation over next 1h, 6h, or 12h).
    """

    time: dt.datetime = Field(..., description="Forecast timestamp (UTC)")

    # Instant parameters (point-in-time values)
    air_temperature: Optional[float] = Field(None, description="Air temperature (°C)")
    relative_humidity: Optional[float] = Field(None, description="Relative humidity (%)")
    wind_speed: Optional[float] = Field(None, description="Wind speed (m/s)")
    wind_from_direction: Optional[float] = Field(None, description="Wind direction (degrees)")
    cloud_area_fraction: Optional[float] = Field(None, description="Cloud cover fraction (%)")
    air_pressure_at_sea_level: Optional[float] = Field(None, description="Sea level pressure (hPa)")

    # Period parameters (forecast for upcoming period)
    precipitation_amount: Optional[float] = Field(None, description="Precipitation amount (mm)")
    precipitation_period_hours: Optional[int] = Field(
        None, description="Period for precipitation forecast (1, 6, or 12 hours)"
    )

    # Weather symbol
    weather_symbol: Optional[str] = Field(None, description="Weather symbol code")


class DailyWeatherSummary(BaseModel):
    """
    Daily aggregated weather summary from hourly forecasts.

    Aggregates hourly met.no forecast data to daily values compatible with
    SILO daily weather data format.

    Examples:
        >>> summary = DailyWeatherSummary(
        ...     date=dt.date(2023, 1, 15),
        ...     min_temperature=18.5,
        ...     max_temperature=28.3,
        ...     total_precipitation=5.2
        ... )
    """

    date: dt.date = Field(..., description="Date for this daily summary")

    # Temperature (°C)
    min_temperature: Optional[float] = Field(
        None, description="Minimum temperature for the day (°C)"
    )
    max_temperature: Optional[float] = Field(
        None, description="Maximum temperature for the day (°C)"
    )

    # Precipitation (mm)
    total_precipitation: Optional[float] = Field(
        None, description="Total precipitation for the day (mm)"
    )

    # Wind (m/s)
    avg_wind_speed: Optional[float] = Field(None, description="Average wind speed (m/s)")
    max_wind_speed: Optional[float] = Field(None, description="Maximum wind speed (m/s)")

    # Humidity (%)
    avg_relative_humidity: Optional[float] = Field(
        None, description="Average relative humidity (%)"
    )

    # Pressure (hPa)
    avg_pressure: Optional[float] = Field(None, description="Average sea level pressure (hPa)")

    # Cloud cover (%)
    avg_cloud_fraction: Optional[float] = Field(
        None, description="Average cloud cover fraction (%)"
    )

    # Weather condition
    dominant_weather_symbol: Optional[str] = Field(
        None, description="Most common or severe weather symbol for the day"
    )


class MetNoAPIError(Exception):
    """Base exception for met.no API errors."""


class MetNoUserAgentError(MetNoAPIError):
    """Raised when User-Agent header is missing or invalid."""


class MetNoRateLimitError(MetNoAPIError):
    """Raised when API rate limit is exceeded."""
