"""
Tests for met.no API Pydantic models.

Tests validation, serialization, and model methods for met.no API interaction.
"""
import pytest
import datetime as dt
from pydantic import ValidationError

from weather_tools.metno_models import (
    MetNoFormat,
    MetNoQuery,
    MetNoResponse,
    ForecastTimestamp,
    DailyWeatherSummary,
)
from weather_tools.silo_models import AustralianCoordinates


class TestMetNoFormat:
    """Test MetNoFormat enum."""

    def test_format_values(self):
        """Test enum values are correct."""
        assert MetNoFormat.COMPACT == "compact"
        assert MetNoFormat.COMPLETE == "complete"

    def test_format_from_string(self):
        """Test creating enum from string."""
        assert MetNoFormat("compact") == MetNoFormat.COMPACT
        assert MetNoFormat("complete") == MetNoFormat.COMPLETE

    def test_invalid_format(self):
        """Test invalid format raises error."""
        with pytest.raises(ValueError):
            MetNoFormat("invalid")


class TestMetNoQuery:
    """Test MetNoQuery model."""

    def test_valid_query_creation(self):
        """Test creating valid query with Australian coordinates."""
        coords = AustralianCoordinates(latitude=-27.5, longitude=153.0)
        query = MetNoQuery(coordinates=coords)

        assert query.coordinates.latitude == -27.5
        assert query.coordinates.longitude == 153.0
        assert query.format == MetNoFormat.COMPACT

    def test_query_with_explicit_format(self):
        """Test creating query with explicit format."""
        coords = AustralianCoordinates(latitude=-27.5, longitude=153.0)
        query = MetNoQuery(coordinates=coords, format=MetNoFormat.COMPLETE)

        assert query.format == MetNoFormat.COMPLETE

    def test_to_api_params_basic(self):
        """Test conversion to API parameters."""
        coords = AustralianCoordinates(latitude=-27.5, longitude=153.0)
        query = MetNoQuery(coordinates=coords)
        params = query.to_api_params()

        assert params["lat"] == -27.5
        assert params["lon"] == 153.0
        assert "altitude" not in params

    def test_query_with_invalid_coordinates(self):
        """Test that invalid Australian coordinates are rejected."""
        # Outside Australian bounds
        with pytest.raises(ValidationError):
            AustralianCoordinates(latitude=0.0, longitude=153.0)

        with pytest.raises(ValidationError):
            AustralianCoordinates(latitude=-27.5, longitude=0.0)


class TestMetNoResponse:
    """Test MetNoResponse model."""

    def test_valid_response_creation(self):
        """Test creating valid response."""
        coords = AustralianCoordinates(latitude=-27.5, longitude=153.0)
        raw_data = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [153.0, -27.5, 0]},
            "properties": {
                "meta": {"updated_at": "2023-01-15T12:00:00Z"},
                "timeseries": [
                    {
                        "time": "2023-01-15T12:00:00Z",
                        "data": {
                            "instant": {
                                "details": {
                                    "air_temperature": 25.0,
                                    "relative_humidity": 70.0
                                }
                            }
                        }
                    }
                ]
            }
        }

        response = MetNoResponse(
            raw_data=raw_data,
            format=MetNoFormat.COMPACT,
            coordinates=coords
        )

        assert response.format == MetNoFormat.COMPACT
        assert response.coordinates.latitude == -27.5
        assert isinstance(response.generated_at, dt.datetime)

    def test_get_timeseries(self):
        """Test extracting timeseries from response."""
        coords = AustralianCoordinates(latitude=-27.5, longitude=153.0)
        timeseries_data = [
            {"time": "2023-01-15T12:00:00Z", "data": {}},
            {"time": "2023-01-15T13:00:00Z", "data": {}},
        ]

        raw_data = {
            "properties": {
                "timeseries": timeseries_data
            }
        }

        response = MetNoResponse(
            raw_data=raw_data,
            format=MetNoFormat.COMPACT,
            coordinates=coords
        )

        timeseries = response.get_timeseries()
        assert len(timeseries) == 2
        assert timeseries[0]["time"] == "2023-01-15T12:00:00Z"

    def test_get_timeseries_empty(self):
        """Test get_timeseries with no timeseries data."""
        coords = AustralianCoordinates(latitude=-27.5, longitude=153.0)
        raw_data = {"properties": {}}

        response = MetNoResponse(
            raw_data=raw_data,
            format=MetNoFormat.COMPACT,
            coordinates=coords
        )

        timeseries = response.get_timeseries()
        assert timeseries == []

    def test_get_meta(self):
        """Test extracting metadata from response."""
        coords = AustralianCoordinates(latitude=-27.5, longitude=153.0)
        meta_data = {"updated_at": "2023-01-15T12:00:00Z", "units": {}}

        raw_data = {
            "properties": {
                "meta": meta_data
            }
        }

        response = MetNoResponse(
            raw_data=raw_data,
            format=MetNoFormat.COMPACT,
            coordinates=coords
        )

        meta = response.get_meta()
        assert meta["updated_at"] == "2023-01-15T12:00:00Z"


class TestForecastTimestamp:
    """Test ForecastTimestamp model."""

    def test_valid_timestamp_creation(self):
        """Test creating valid forecast timestamp."""
        timestamp = ForecastTimestamp(
            time=dt.datetime(2023, 1, 15, 12, 0, 0),
            air_temperature=25.0,
            relative_humidity=70.0,
            wind_speed=5.5,
            precipitation_amount=2.5,
            precipitation_period_hours=6
        )

        assert timestamp.time == dt.datetime(2023, 1, 15, 12, 0, 0)
        assert timestamp.air_temperature == 25.0
        assert timestamp.relative_humidity == 70.0
        assert timestamp.wind_speed == 5.5
        assert timestamp.precipitation_amount == 2.5
        assert timestamp.precipitation_period_hours == 6

    def test_timestamp_with_optional_fields(self):
        """Test creating timestamp with only required fields."""
        timestamp = ForecastTimestamp(
            time=dt.datetime(2023, 1, 15, 12, 0, 0)
        )

        assert timestamp.time == dt.datetime(2023, 1, 15, 12, 0, 0)
        assert timestamp.air_temperature is None
        assert timestamp.relative_humidity is None
        assert timestamp.precipitation_amount is None

    def test_timestamp_with_all_fields(self):
        """Test timestamp with all available fields."""
        timestamp = ForecastTimestamp(
            time=dt.datetime(2023, 1, 15, 12, 0, 0),
            air_temperature=25.0,
            relative_humidity=70.0,
            wind_speed=5.5,
            wind_from_direction=180.0,
            cloud_area_fraction=50.0,
            air_pressure_at_sea_level=1013.25,
            precipitation_amount=2.5,
            precipitation_period_hours=6,
            weather_symbol="cloudy"
        )

        assert timestamp.wind_from_direction == 180.0
        assert timestamp.cloud_area_fraction == 50.0
        assert timestamp.air_pressure_at_sea_level == 1013.25
        assert timestamp.weather_symbol == "cloudy"


class TestDailyWeatherSummary:
    """Test DailyWeatherSummary model."""

    def test_valid_summary_creation(self):
        """Test creating valid daily summary."""
        summary = DailyWeatherSummary(
            date=dt.date(2023, 1, 15),
            min_temperature=18.5,
            max_temperature=28.3,
            total_precipitation=5.2
        )

        assert summary.date == dt.date(2023, 1, 15)
        assert summary.min_temperature == 18.5
        assert summary.max_temperature == 28.3
        assert summary.total_precipitation == 5.2

    def test_summary_with_all_fields(self):
        """Test summary with all available fields."""
        summary = DailyWeatherSummary(
            date=dt.date(2023, 1, 15),
            min_temperature=18.5,
            max_temperature=28.3,
            total_precipitation=5.2,
            avg_wind_speed=4.2,
            max_wind_speed=8.5,
            avg_relative_humidity=75.0,
            avg_pressure=1013.25,
            avg_cloud_fraction=60.0,
            dominant_weather_symbol="partlycloudy_day"
        )

        assert summary.avg_wind_speed == 4.2
        assert summary.max_wind_speed == 8.5
        assert summary.avg_relative_humidity == 75.0
        assert summary.avg_pressure == 1013.25
        assert summary.avg_cloud_fraction == 60.0
        assert summary.dominant_weather_symbol == "partlycloudy_day"

    def test_summary_with_minimal_fields(self):
        """Test summary with only required date field."""
        summary = DailyWeatherSummary(date=dt.date(2023, 1, 15))

        assert summary.date == dt.date(2023, 1, 15)
        assert summary.min_temperature is None
        assert summary.max_temperature is None
        assert summary.total_precipitation is None

    def test_summary_temperature_validation(self):
        """Test that temperatures can be negative (winter conditions)."""
        summary = DailyWeatherSummary(
            date=dt.date(2023, 7, 15),
            min_temperature=-5.0,
            max_temperature=2.0
        )

        assert summary.min_temperature == -5.0
        assert summary.max_temperature == 2.0

    def test_summary_zero_precipitation(self):
        """Test that zero precipitation is valid."""
        summary = DailyWeatherSummary(
            date=dt.date(2023, 1, 15),
            total_precipitation=0.0
        )

        assert summary.total_precipitation == 0.0
