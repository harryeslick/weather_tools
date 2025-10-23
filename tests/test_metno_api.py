"""
Tests for met.no API client.

Tests API client functionality with mocked responses.
"""
import datetime as dt
import json
import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from weather_tools.metno_api import MetNoAPI
from weather_tools.metno_models import (
    MetNoAPIError,
    MetNoFormat,
    MetNoQuery,
    MetNoRateLimitError,
    MetNoUserAgentError,
)
from weather_tools.silo_models import AustralianCoordinates


@pytest.fixture
def mock_metno_response():
    """Load fixture JSON for met.no response."""
    fixture_path = Path(__file__).parent / "fixtures" / "metno_response_compact.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def sample_coords():
    """Sample Australian coordinates."""
    return AustralianCoordinates(latitude=-27.5, longitude=153.0)


class TestMetNoAPIInitialization:
    """Test API client initialization."""

    def test_api_initialization_default_user_agent(self):
        """Test API initialization with default User-Agent."""
        api = MetNoAPI()

        assert api.user_agent.startswith("weather-tools/")
        assert "Python" in api.user_agent
        assert api.timeout == 30
        assert api.max_retries == 3
        assert api.enable_cache is True

    def test_api_initialization_custom_user_agent(self):
        """Test API initialization with custom User-Agent."""
        api = MetNoAPI(user_agent="TestApp/1.0 (test@example.com)")

        assert api.user_agent == "TestApp/1.0 (test@example.com)"

    def test_api_initialization_custom_options(self):
        """Test API initialization with custom options."""
        api = MetNoAPI(
            timeout=60,
            max_retries=5,
            retry_delay=2.0,
            enable_cache=False,
            cache_expiry_hours=2,
            log_level="DEBUG",
        )

        assert api.timeout == 60
        assert api.max_retries == 5
        assert api.retry_delay == 2.0
        assert api.enable_cache is False
        assert api.cache_expiry_hours == 2
        assert api.log_level == logging.DEBUG


class TestMetNoAPIEndpoints:
    """Test API endpoint construction."""

    def test_get_endpoint_compact(self):
        """Test compact endpoint URL."""
        api = MetNoAPI()
        url = api._get_endpoint(MetNoFormat.COMPACT)

        assert url == "https://api.met.no/weatherapi/locationforecast/2.0/compact"

    def test_get_endpoint_complete(self):
        """Test complete endpoint URL."""
        api = MetNoAPI()
        url = api._get_endpoint(MetNoFormat.COMPLETE)

        assert url == "https://api.met.no/weatherapi/locationforecast/2.0/complete"


class TestMetNoAPICaching:
    """Test API caching functionality."""

    def test_cache_enabled_by_default(self):
        """Test that caching is enabled by default."""
        api = MetNoAPI()

        assert api.enable_cache is True
        assert api._cache is not None

    def test_cache_disabled(self):
        """Test disabling cache."""
        api = MetNoAPI(enable_cache=False)

        assert api.enable_cache is False
        assert api._cache is None

    def test_get_cache_size_empty(self):
        """Test cache size when empty."""
        api = MetNoAPI()

        assert api.get_cache_size() == 0

    def test_get_cache_size_disabled(self):
        """Test cache size when caching disabled."""
        api = MetNoAPI(enable_cache=False)

        assert api.get_cache_size() == 0

    def test_clear_cache(self):
        """Test clearing cache."""
        api = MetNoAPI()
        # Add something to cache
        api._cache["test"] = ("data", dt.datetime.now(dt.UTC))

        api.clear_cache()

        assert api.get_cache_size() == 0


class TestMetNoAPIRequests:
    """Test API request handling."""

    def test_query_forecast_success(self, mock_metno_response, sample_coords):
        """Test successful forecast query."""
        api = MetNoAPI()
        query = MetNoQuery(coordinates=sample_coords, format=MetNoFormat.COMPACT)

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_metno_response
            mock_get.return_value = mock_response

            response = api.query_forecast(query)

            assert response.format == MetNoFormat.COMPACT
            assert response.coordinates.latitude == -27.5
            assert response.coordinates.longitude == 153.0
            timeseries = response.get_timeseries()
            assert len(timeseries) > 0

    def test_query_forecast_403_user_agent_error(self, sample_coords):
        """Test 403 error (User-Agent issue)."""
        api = MetNoAPI()
        query = MetNoQuery(coordinates=sample_coords)

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.reason = "Forbidden"
            mock_response.text = "Invalid User-Agent"
            mock_get.return_value = mock_response

            with pytest.raises(MetNoUserAgentError) as exc_info:
                api.query_forecast(query)

            assert "403 Forbidden" in str(exc_info.value)
            assert "User-Agent" in str(exc_info.value)

    def test_query_forecast_429_rate_limit_error(self, sample_coords):
        """Test 429 error (rate limit)."""
        api = MetNoAPI()
        query = MetNoQuery(coordinates=sample_coords)

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.reason = "Too Many Requests"
            mock_response.text = "Rate limit exceeded"
            mock_get.return_value = mock_response

            with pytest.raises(MetNoRateLimitError) as exc_info:
                api.query_forecast(query)

            assert "rate limit" in str(exc_info.value).lower()

    def test_query_forecast_500_error(self, sample_coords):
        """Test 500 server error."""
        api = MetNoAPI(max_retries=1)
        query = MetNoQuery(coordinates=sample_coords)

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.reason = "Internal Server Error"
            mock_response.text = "Server error"
            mock_get.return_value = mock_response

            with pytest.raises(MetNoAPIError):
                api.query_forecast(query)

    def test_query_forecast_timeout_retry(self, mock_metno_response, sample_coords):
        """Test retry on timeout."""
        api = MetNoAPI(max_retries=2, retry_delay=0.1)
        query = MetNoQuery(coordinates=sample_coords)

        with patch("requests.get") as mock_get:
            # First call: timeout, second call: success
            mock_get.side_effect = [
                requests.exceptions.Timeout("Connection timeout"),
                Mock(status_code=200, json=lambda: mock_metno_response)
            ]

            response = api.query_forecast(query)

            assert response is not None
            assert mock_get.call_count == 2

    def test_query_forecast_connection_error_retry(self, sample_coords):
        """Test retry on connection error."""
        api = MetNoAPI(max_retries=2, retry_delay=0.1)
        query = MetNoQuery(coordinates=sample_coords)

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

            with pytest.raises(MetNoAPIError) as exc_info:
                api.query_forecast(query)

            assert "failed after 2 attempts" in str(exc_info.value)
            assert mock_get.call_count == 2

    def test_query_forecast_invalid_json(self, sample_coords):
        """Test handling of invalid JSON response."""
        api = MetNoAPI()
        query = MetNoQuery(coordinates=sample_coords)

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_get.return_value = mock_response

            with pytest.raises(MetNoAPIError) as exc_info:
                api.query_forecast(query)

            assert "parse JSON" in str(exc_info.value)


class TestMetNoAPIDailyAggregation:
    """Test daily aggregation from hourly forecasts."""

    def test_aggregate_to_daily(self, mock_metno_response, sample_coords):
        """Test aggregation of hourly data to daily summaries."""
        api = MetNoAPI()

        timeseries = mock_metno_response["properties"]["timeseries"]
        daily_summaries = api._aggregate_to_daily(timeseries, sample_coords)

        assert len(daily_summaries) == 2  # 2 days in fixture

        # Check first day
        day1 = daily_summaries[0]
        assert day1.date == dt.date(2023, 1, 15)
        assert day1.min_temperature is not None
        assert day1.max_temperature is not None
        assert day1.total_precipitation is not None

        # Check second day
        day2 = daily_summaries[1]
        assert day2.date == dt.date(2023, 1, 16)

    def test_aggregate_temperature_min_max(self, mock_metno_response, sample_coords):
        """Test temperature min/max calculation."""
        api = MetNoAPI()

        timeseries = mock_metno_response["properties"]["timeseries"]
        daily_summaries = api._aggregate_to_daily(timeseries, sample_coords)

        day1 = daily_summaries[0]
        # From fixture: 25.5, 26.2, 27.1
        assert day1.min_temperature == 25.5
        assert day1.max_temperature == 27.1

    def test_aggregate_precipitation_sum(self, mock_metno_response, sample_coords):
        """Test precipitation summation."""
        api = MetNoAPI()

        timeseries = mock_metno_response["properties"]["timeseries"]
        daily_summaries = api._aggregate_to_daily(timeseries, sample_coords)

        day1 = daily_summaries[0]
        # From fixture: 0.0, 0.2, 0.8 = 1.0
        assert day1.total_precipitation == pytest.approx(1.0, abs=0.01)

    def test_get_dominant_symbol(self):
        """Test weather symbol selection."""
        api = MetNoAPI()

        # Test severity prioritization
        symbols = ["clearsky_day", "partlycloudy_day", "rain"]
        result = api._get_dominant_symbol(symbols)
        assert "rain" in result

        # Test thunderstorm priority
        symbols = ["rain", "thunder", "cloudy"]
        result = api._get_dominant_symbol(symbols)
        assert "thunder" in result

        # Test empty list
        assert api._get_dominant_symbol([]) is None


class TestMetNoAPIConvenience:
    """Test convenience methods."""

    def test_get_daily_forecast(self, mock_metno_response):
        """Test get_daily_forecast convenience method."""
        api = MetNoAPI()

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_metno_response
            mock_get.return_value = mock_response

            forecasts = api.get_daily_forecast(latitude=-27.5, longitude=153.0, days=7)

            assert len(forecasts) <= 7
            assert all(hasattr(f, "date") for f in forecasts)
            assert all(hasattr(f, "min_temperature") for f in forecasts)

    def test_get_daily_forecast_invalid_days(self):
        """Test validation of days parameter."""
        api = MetNoAPI()

        with pytest.raises(ValueError) as exc_info:
            api.get_daily_forecast(latitude=-27.5, longitude=153.0, days=10)

        assert "between 1 and 9" in str(exc_info.value)

        with pytest.raises(ValueError):
            api.get_daily_forecast(latitude=-27.5, longitude=153.0, days=0)

    def test_to_dataframe_daily(self, mock_metno_response, sample_coords):
        """Test conversion to DataFrame with daily aggregation."""
        api = MetNoAPI()

        from weather_tools.metno_models import MetNoResponse

        response = MetNoResponse(
            raw_data=mock_metno_response,
            format=MetNoFormat.COMPACT,
            coordinates=sample_coords
        )

        df = api.to_dataframe(response, aggregate_to_daily=True)

        assert not df.empty
        assert "date" in df.columns
        assert "min_temperature" in df.columns
        assert "max_temperature" in df.columns
        assert "total_precipitation" in df.columns

    def test_to_dataframe_hourly(self, mock_metno_response, sample_coords):
        """Test conversion to DataFrame with hourly data."""
        api = MetNoAPI()

        from weather_tools.metno_models import MetNoResponse

        response = MetNoResponse(
            raw_data=mock_metno_response,
            format=MetNoFormat.COMPACT,
            coordinates=sample_coords
        )

        df = api.to_dataframe(response, aggregate_to_daily=False)

        assert not df.empty
        assert "time" in df.columns
        assert "air_temperature" in df.columns


@pytest.mark.integration
class TestMetNoAPIIntegration:
    """Integration tests with real API (requires internet)."""

    def test_real_api_query(self):
        """Test real met.no API query."""
        api = MetNoAPI()
        coords = AustralianCoordinates(latitude=-27.5, longitude=153.0)
        query = MetNoQuery(coordinates=coords, format=MetNoFormat.COMPACT)

        try:
            response = api.query_forecast(query)
            assert response is not None
            timeseries = response.get_timeseries()
            assert len(timeseries) > 0
        except Exception as e:
            pytest.skip(f"Real API call failed (may be offline): {e}")

    def test_real_daily_forecast(self):
        """Test real daily forecast retrieval."""
        api = MetNoAPI()

        try:
            forecasts = api.get_daily_forecast(
                latitude=-27.5,
                longitude=153.0,
                days=3
            )
            assert len(forecasts) == 3
            assert all(f.date is not None for f in forecasts)
        except Exception as e:
            pytest.skip(f"Real API call failed (may be offline): {e}")
