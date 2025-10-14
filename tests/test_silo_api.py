"""
Comprehensive tests for silo_api.py module.

Tests cover:
1. Each dataset/format combination
2. Validation error cases
3. Missing required parameters
4. Timeout behavior
5. Error response handling
6. Mocked requests for unit testing
7. Date validation
8. Retry logic
9. Caching functionality
"""

from unittest.mock import Mock, patch

import pytest
import requests

from weather_tools.silo_api import SiloAPI, SiloAPIError


class TestSiloAPIInitialization:
    """Test SiloAPI initialization and configuration."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        api = SiloAPI(api_key="test_key")
        assert api.api_key == "test_key"
        assert api.timeout == SiloAPI.DEFAULT_TIMEOUT
        assert api.max_retries == SiloAPI.DEFAULT_MAX_RETRIES
        assert api.retry_delay == SiloAPI.DEFAULT_RETRY_DELAY
        assert api.enable_cache is False
        assert api._cache is None

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        api = SiloAPI(
            api_key="test_key",
            timeout=60,
            max_retries=5,
            retry_delay=2.0,
            enable_cache=True
        )
        assert api.timeout == 60
        assert api.max_retries == 5
        assert api.retry_delay == 2.0
        assert api.enable_cache is True
        assert api._cache == {}


class TestDateValidation:
    """Test date format validation."""

    def setup_method(self):
        self.api = SiloAPI(api_key="test_key")

    def test_valid_date_format(self):
        """Test that valid dates pass validation."""
        # Should not raise
        self.api._validate_date_format("20230101", "test_date")
        self.api._validate_date_format("20231231", "test_date")

    def test_none_date_is_valid(self):
        """Test that None dates are allowed."""
        # Should not raise
        self.api._validate_date_format(None, "test_date")

    def test_invalid_date_length(self):
        """Test that dates with wrong length are rejected."""
        with pytest.raises(ValueError, match="must be in YYYYMMDD format"):
            self.api._validate_date_format("2023010", "test_date")
        
        with pytest.raises(ValueError, match="must be in YYYYMMDD format"):
            self.api._validate_date_format("202301011", "test_date")

    def test_invalid_date_characters(self):
        """Test that non-numeric dates are rejected."""
        with pytest.raises(ValueError, match="must contain only digits"):
            self.api._validate_date_format("2023010a", "test_date")

    def test_invalid_date_ranges(self):
        """Test that out-of-range dates are rejected."""
        with pytest.raises(ValueError, match="month must be between"):
            self.api._validate_date_format("20231301", "test_date")
        
        with pytest.raises(ValueError, match="day must be between"):
            self.api._validate_date_format("20230132", "test_date")
        
        with pytest.raises(ValueError, match="year must be between"):
            self.api._validate_date_format("18991231", "test_date")


class TestFormatValidation:
    """Test format validation."""

    def setup_method(self):
        self.api = SiloAPI(api_key="test_key")

    def test_valid_formats(self):
        """Test that valid formats pass validation."""
        for fmt in ["csv", "apsim", "near"]:
            # Should not raise
            self.api._validate_format(fmt, "PatchedPoint")

    def test_invalid_format(self):
        """Test that invalid formats are rejected."""
        with pytest.raises(ValueError, match="Unknown format"):
            self.api._validate_format("json", "PatchedPoint")

    def test_datadrill_near_format_rejected(self):
        """Test that DataDrill + near format is rejected."""
        with pytest.raises(ValueError, match="does not support 'near' format"):
            self.api._validate_format("near", "DataDrill")


class TestEndpointValidation:
    """Test endpoint validation."""

    def setup_method(self):
        self.api = SiloAPI(api_key="test_key")

    def test_valid_datasets(self):
        """Test that valid datasets return correct endpoints."""
        url = self.api._get_endpoint("PatchedPoint")
        assert "PatchedPointDataset.php" in url
        
        url = self.api._get_endpoint("DataDrill")
        assert "DataDrillDataset.php" in url

    def test_invalid_dataset(self):
        """Test that invalid datasets raise error."""
        with pytest.raises(ValueError, match="Unknown dataset"):
            self.api._get_endpoint("InvalidDataset")


class TestPatchedPointParams:
    """Test PatchedPoint parameter building."""

    def setup_method(self):
        self.api = SiloAPI(api_key="test_key")

    def test_missing_station_code(self):
        """Test that missing station_code raises error."""
        with pytest.raises(ValueError, match="station_code is required"):
            self.api._build_patched_point_params(
                "csv", None, "20230101", "20230131", ["rain"], None
            )

    def test_csv_format_params(self):
        """Test CSV format parameter building."""
        params = self.api._build_patched_point_params(
            "csv", "30043", "20230101", "20230131", ["rain", "maxtemp"], None
        )
        assert params["station"] == "30043"
        assert params["start"] == "20230101"
        assert params["finish"] == "20230131"
        assert params["format"] == "csv"
        assert "rain,maxtemp" in params["comment"]
        assert params["username"] == "test_key"
        assert params["password"] == "api_request"

    def test_apsim_format_params(self):
        """Test APSIM format parameter building."""
        params = self.api._build_patched_point_params(
            "apsim", "30043", "20230101", "20230131", None, None
        )
        assert params["station"] == "30043"
        assert params["format"] == "apsim"
        assert params["username"] == "test_key"
        assert params["password"] == "api_request"

    def test_near_format_params(self):
        """Test near format parameter building."""
        params = self.api._build_patched_point_params(
            "near", "30043", None, None, None, 50.0
        )
        assert params["station"] == "30043"
        assert params["format"] == "near"
        assert params["radius"] == 50.0

    def test_invalid_date_format_rejected(self):
        """Test that invalid dates in params are rejected."""
        with pytest.raises(ValueError, match="must be in YYYYMMDD format"):
            self.api._build_patched_point_params(
                "csv", "30043", "2023-01-01", "20230131", ["rain"], None
            )


class TestDataDrillParams:
    """Test DataDrill parameter building."""

    def setup_method(self):
        self.api = SiloAPI(api_key="test_key")

    def test_missing_coordinates(self):
        """Test that missing coordinates raise error."""
        with pytest.raises(ValueError, match="longitude and latitude are required"):
            self.api._build_data_drill_params(
                "csv", None, None, "20230101", "20230131", ["rain"]
            )
        
        with pytest.raises(ValueError, match="longitude and latitude are required"):
            self.api._build_data_drill_params(
                "csv", 151.0, None, "20230101", "20230131", ["rain"]
            )

    def test_csv_format_params(self):
        """Test CSV format parameter building."""
        params = self.api._build_data_drill_params(
            "csv", 151.0, -27.5, "20230101", "20230131", ["rain", "maxtemp"]
        )
        assert params["longitude"] == 151.0
        assert params["latitude"] == -27.5
        assert params["start"] == "20230101"
        assert params["finish"] == "20230131"
        assert params["format"] == "csv"
        assert "rain,maxtemp" in params["comment"]
        assert params["username"] == "test_key"
        assert params["password"] == "api_request"

    def test_apsim_format_params(self):
        """Test APSIM format parameter building."""
        params = self.api._build_data_drill_params(
            "apsim", 151.0, -27.5, "20230101", "20230131", None
        )
        assert params["longitude"] == 151.0
        assert params["latitude"] == -27.5
        assert params["format"] == "apsim"


class TestRequestHandling:
    """Test HTTP request handling with mocking."""

    def setup_method(self):
        self.api = SiloAPI(api_key="test_key", max_retries=3, retry_delay=0.1)

    @patch('weather_tools.silo_api.requests.get')
    def test_successful_request(self, mock_get):
        """Test successful HTTP request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "station,date,rain\n30043,20230101,10.5"
        mock_get.return_value = mock_response

        result = self.api._make_request("http://test.com", {"param": "value"})
        
        assert result == mock_response
        mock_get.assert_called_once()

    @patch('weather_tools.silo_api.requests.get')
    def test_http_error_handling(self, mock_get):
        """Test HTTP error handling."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        mock_response.text = "Resource not found"
        mock_get.return_value = mock_response

        with pytest.raises(SiloAPIError, match="HTTP 404"):
            self.api._make_request("http://test.com", {})

    @patch('weather_tools.silo_api.requests.get')
    def test_silo_error_message_handling(self, mock_get):
        """Test SILO-specific error message handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Sorry, your request was rejected"
        mock_get.return_value = mock_response

        with pytest.raises(SiloAPIError, match="Sorry"):
            self.api._make_request("http://test.com", {})

    @patch('weather_tools.silo_api.requests.get')
    @patch('weather_tools.silo_api.time.sleep')
    def test_retry_on_timeout(self, mock_sleep, mock_get):
        """Test retry logic on timeout."""
        # First two calls timeout, third succeeds
        mock_get.side_effect = [
            requests.exceptions.Timeout("Connection timeout"),
            requests.exceptions.Timeout("Connection timeout"),
            Mock(status_code=200, text="success")
        ]

        result = self.api._make_request("http://test.com", {})
        
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries
        assert result.text == "success"

    @patch('weather_tools.silo_api.requests.get')
    def test_retry_exhausted(self, mock_get):
        """Test that retries are exhausted and error is raised."""
        mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")

        with pytest.raises(SiloAPIError, match="failed after 3 attempts"):
            self.api._make_request("http://test.com", {})
        
        assert mock_get.call_count == 3

    @patch('weather_tools.silo_api.requests.get')
    def test_no_retry_on_api_error(self, mock_get):
        """Test that API errors don't trigger retry."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.reason = "Bad Request"
        mock_response.text = "Invalid parameters"
        mock_get.return_value = mock_response

        with pytest.raises(SiloAPIError, match="HTTP 400"):
            self.api._make_request("http://test.com", {})
        
        # Should only call once, no retries
        assert mock_get.call_count == 1


class TestCaching:
    """Test response caching functionality."""

    def setup_method(self):
        self.api = SiloAPI(api_key="test_key", enable_cache=True)

    @patch('weather_tools.silo_api.requests.get')
    def test_cache_hit(self, mock_get):
        """Test that cached responses are returned."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "cached data"
        mock_get.return_value = mock_response

        # First call - should hit the API
        result1 = self.api._make_request("http://test.com", {"param": "value"})
        assert mock_get.call_count == 1

        # Second call - should use cache
        result2 = self.api._make_request("http://test.com", {"param": "value"})
        assert mock_get.call_count == 1  # No additional call
        assert result2 == result1

    def test_cache_key_generation(self):
        """Test that cache keys are generated consistently."""
        key1 = self.api._get_cache_key("http://test.com", {"a": 1, "b": 2})
        key2 = self.api._get_cache_key("http://test.com", {"b": 2, "a": 1})
        key3 = self.api._get_cache_key("http://test.com", {"a": 1, "b": 3})
        
        assert key1 == key2  # Order shouldn't matter
        assert key1 != key3  # Different params = different key

    def test_clear_cache(self):
        """Test cache clearing."""
        self.api._cache["key1"] = "value1"
        self.api._cache["key2"] = "value2"
        
        assert self.api.get_cache_size() == 2
        
        self.api.clear_cache()
        assert self.api.get_cache_size() == 0

    def test_cache_size_when_disabled(self):
        """Test cache size when caching is disabled."""
        api = SiloAPI(api_key="test_key", enable_cache=False)
        assert api.get_cache_size() == 0


class TestResponseParsing:
    """Test response parsing."""

    def setup_method(self):
        self.api = SiloAPI(api_key="test_key")

    def test_parse_csv_response(self):
        """Test parsing CSV response."""
        mock_response = Mock()
        mock_response.text = "station,date,rain\n30043,20230101,10.5"
        
        result = self.api._parse_response(mock_response, "csv")
        assert result == mock_response.text

    def test_parse_json_response(self):
        """Test parsing JSON response."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": "value"}
        
        result = self.api._parse_response(mock_response, "json")
        assert result == {"data": "value"}

    def test_parse_invalid_json_response(self):
        """Test parsing invalid JSON returns text."""
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "not json data"
        
        result = self.api._parse_response(mock_response, "json")
        assert result == "not json data"


class TestQueryIntegration:
    """Integration tests for the query method."""

    def setup_method(self):
        self.api = SiloAPI(api_key="test_key")

    @patch('weather_tools.silo_api.requests.get')
    def test_patched_point_csv_query(self, mock_get):
        """Test complete PatchedPoint CSV query."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "station,date,rain\n30043,20230101,10.5"
        mock_get.return_value = mock_response

        result = self.api.query(
            dataset="PatchedPoint",
            format="csv",
            station_code="30043",
            start_date="20230101",
            end_date="20230131",
            values=["rain"]
        )

        assert "30043" in result
        mock_get.assert_called_once()

    @patch('weather_tools.silo_api.requests.get')
    def test_data_drill_query(self, mock_get):
        """Test complete DataDrill query."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "longitude,latitude,date,rain\n151.0,-27.5,20230101,10.5"
        mock_get.return_value = mock_response

        result = self.api.query(
            dataset="DataDrill",
            format="csv",
            longitude=151.0,
            latitude=-27.5,
            start_date="20230101",
            end_date="20230131",
            values=["rain"]
        )

        assert "151.0" in result
        mock_get.assert_called_once()

    def test_query_with_invalid_dataset(self):
        """Test query with invalid dataset."""
        with pytest.raises(ValueError, match="Unknown dataset"):
            self.api.query(dataset="InvalidDataset")

    def test_query_with_invalid_format(self):
        """Test query with invalid format."""
        with pytest.raises(ValueError, match="Unknown format"):
            self.api.query(dataset="PatchedPoint", format="invalid")

    def test_query_patched_point_missing_station(self):
        """Test PatchedPoint query with missing station_code."""
        with pytest.raises(ValueError, match="station_code is required"):
            self.api.query(
                dataset="PatchedPoint",
                format="csv",
                start_date="20230101",
                end_date="20230131"
            )

    def test_query_data_drill_missing_coordinates(self):
        """Test DataDrill query with missing coordinates."""
        with pytest.raises(ValueError, match="longitude and latitude are required"):
            self.api.query(
                dataset="DataDrill",
                format="csv",
                start_date="20230101",
                end_date="20230131"
            )


class TestTimeoutConfiguration:
    """Test timeout configuration."""

    @patch('weather_tools.silo_api.requests.get')
    def test_custom_timeout_used(self, mock_get):
        """Test that custom timeout is used in requests."""
        api = SiloAPI(api_key="test_key", timeout=60)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "success"
        mock_get.return_value = mock_response

        api._make_request("http://test.com", {})

        # Check that timeout parameter was passed correctly
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["timeout"] == 60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
