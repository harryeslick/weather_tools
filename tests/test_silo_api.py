"""Tests for the SILO API client module."""

from unittest.mock import Mock, patch
import pandas as pd

from weather_tools.silo_api import SiloAPI
from weather_tools.silo_models import (
    PatchedPointQuery,
    SiloFormat,
)


class TestSearchStations:
    """Tests for the search_stations method."""

    def test_search_stations_with_spaces(self):
        """Test that search_stations properly handles station names with spaces."""
        # Mock the API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Number | Station name | Latitude | Longitud | Stat | Elevat.\n30043 | BRISBANE AERO | -27.38 | 153.13 | QLD | 5"

        with patch("weather_tools.silo_api.requests.get") as mock_get:
            mock_get.return_value = mock_response

            # Create API instance
            api = SiloAPI(api_key="test@example.com")

            # Call search_stations with a name containing spaces
            result = api.search_stations(name_fragment="BRISBANE AERO")

            # Verify that the API was called with underscores instead of spaces
            call_args = mock_get.call_args
            params = call_args[1]["params"]

            # The nameFrag parameter should have underscores instead of spaces
            assert params["nameFrag"] == "BRISBANE_AERO"
            assert params["format"] == "name"

            # Verify result is a DataFrame
            assert isinstance(result, pd.DataFrame)

    def test_search_stations_without_spaces(self):
        """Test that search_stations works normally when there are no spaces."""
        # Mock the API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Number | Station name | Latitude | Longitud | Stat | Elevat.\n30043 | BRISBANE AERO | -27.38 | 153.13 | QLD | 5"

        with patch("weather_tools.silo_api.requests.get") as mock_get:
            mock_get.return_value = mock_response

            # Create API instance
            api = SiloAPI(api_key="test@example.com")

            # Call search_stations with a name without spaces
            result = api.search_stations(name_fragment="BRISBANE")

            # Verify that the API was called with the original name
            call_args = mock_get.call_args
            params = call_args[1]["params"]

            # The nameFrag parameter should remain unchanged
            assert params["nameFrag"] == "BRISBANE"
            assert params["format"] == "name"

            # Verify result is a DataFrame
            assert isinstance(result, pd.DataFrame)


class TestPatchedPointQueryParams:
    """Tests for PatchedPointQuery parameter conversion."""

    def test_name_format_with_spaces_in_fragment(self):
        """Test that name_fragment with spaces gets underscores."""
        query = PatchedPointQuery(format=SiloFormat.NAME, name_fragment="BRISBANE AERO")

        params = query.to_api_params(api_key="test@example.com")

        # The nameFrag parameter should have underscores instead of spaces
        assert params["nameFrag"] == "BRISBANE_AERO"
        assert params["format"] == "name"

    def test_name_format_without_spaces_in_fragment(self):
        """Test that name_fragment without spaces remains unchanged."""
        query = PatchedPointQuery(format=SiloFormat.NAME, name_fragment="BRISBANE")

        params = query.to_api_params(api_key="test@example.com")

        # The nameFrag parameter should remain unchanged
        assert params["nameFrag"] == "BRISBANE"
        assert params["format"] == "name"
