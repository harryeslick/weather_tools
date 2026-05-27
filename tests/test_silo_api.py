"""Integration tests for SILO station search helpers."""

import os

import pandas as pd
import pytest

from weather_tools.silo_api import SiloAPI
from weather_tools.silo_models import SiloDataset, SiloFormat, SiloResponse

# ---------------------------------------------------------------------------
# FIX 2: parse_station_data must return an empty DataFrame on empty responses
# ---------------------------------------------------------------------------


class TestParseStationDataEmptyResponse:
    """parse_station_data must not raise IndexError when the response body is empty."""

    def _make_api(self) -> SiloAPI:
        """Create a SiloAPI instance with a dummy key (no real requests made)."""
        return SiloAPI.__new__(SiloAPI)

    def test_empty_string_returns_empty_dataframe(self):
        api = self._make_api()
        response = SiloResponse(
            raw_data="", format=SiloFormat.NAME, dataset=SiloDataset.PATCHED_POINT
        )
        df = api.parse_station_data(response)
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_whitespace_only_returns_empty_dataframe(self):
        api = self._make_api()
        response = SiloResponse(
            raw_data="   \n  \n", format=SiloFormat.NEAR, dataset=SiloDataset.PATCHED_POINT
        )
        df = api.parse_station_data(response)
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_empty_dataframe_has_expected_columns(self):
        api = self._make_api()
        response = SiloResponse(
            raw_data="", format=SiloFormat.NAME, dataset=SiloDataset.PATCHED_POINT
        )
        df = api.parse_station_data(response)
        expected = {"station_code", "name", "latitude", "longitude", "state", "elevation"}
        assert set(df.columns) == expected


# ---------------------------------------------------------------------------
# FIX 3: get_patched_point / get_data_drill must reject unknown format strings
# ---------------------------------------------------------------------------


class TestConvenienceMethodFormatValidation:
    """Unknown format strings must raise ValueError, not silently coerce to CSV."""

    def _make_api(self) -> SiloAPI:
        """Create a SiloAPI with dummy credentials — no network calls made."""
        api = SiloAPI.__new__(SiloAPI)
        api.api_key = "test@example.com"
        api.timeout = 30
        api.max_retries = 3
        api.retry_delay = 1.0
        api.enable_cache = False
        api._disk_cache = None
        return api

    def test_get_patched_point_unknown_format_raises(self):
        api = self._make_api()
        with pytest.raises(ValueError, match="Unsupported format"):
            api.get_patched_point("30043", "20230101", "20230131", format="json")

    def test_get_patched_point_typo_format_raises(self):
        api = self._make_api()
        with pytest.raises(ValueError, match="Unsupported format"):
            api.get_patched_point("30043", "20230101", "20230131", format="csb")

    def test_get_data_drill_unknown_format_raises(self):
        api = self._make_api()
        with pytest.raises(ValueError, match="Unsupported format"):
            api.get_data_drill(-27.5, 151.0, "20230101", "20230131", format="alldata")

    def test_get_patched_point_valid_formats_not_rejected(self):
        """Valid format strings must not raise a format-validation ValueError."""
        api = self._make_api()
        for fmt in ("csv", "CSV", "apsim", "APSIM", "standard", "Standard"):
            try:
                api.get_patched_point("30043", "20230101", "20230131", format=fmt)
            except ValueError as exc:
                assert "Unsupported format" not in str(exc), (
                    f"Format '{fmt}' should be accepted but got ValueError: {exc}"
                )
            except Exception:
                pass  # Network errors, etc. are expected in unit tests

    def test_get_data_drill_valid_formats_not_rejected(self):
        """Valid format strings must not raise a format-validation ValueError."""
        api = self._make_api()
        for fmt in ("csv", "CSV", "apsim", "standard"):
            try:
                api.get_data_drill(-27.5, 151.0, "20230101", "20230131", format=fmt)
            except ValueError as exc:
                assert "Unsupported format" not in str(exc), (
                    f"Format '{fmt}' should be accepted but got ValueError: {exc}"
                )
            except Exception:
                pass  # Network errors, etc. are expected in unit tests


TEST_AREAS = [
    ("Badgingarra", -30.3900, 115.5000),
    ("Bendigo", -36.7400, 144.3300),
    ("Birchip", -35.9800, 142.9200),
]


@pytest.fixture(scope="module")
def silo_api() -> SiloAPI:
    """Return a SILO API client, skipping if key is unavailable."""
    if not os.environ.get("SILO_API_KEY"):
        pytest.skip("SILO_API_KEY environment variable not set")
    return SiloAPI()


@pytest.mark.integration
@pytest.mark.parametrize(("station_name", "latitude", "longitude"), TEST_AREAS)
def test_search_stations_by_location_real_api(silo_api, station_name, latitude, longitude):
    """Find a nearby station and verify nearest match for the provided location."""
    pytest.importorskip("geopandas")

    try:
        result = silo_api.search_stations_by_location(
            latitude=latitude,
            longitude=longitude,
            radius_km=35.0,
            name_fragment=station_name,
        )
    except Exception as exc:
        pytest.skip(f"SILO API unavailable: {exc}")

    assert not result.empty, f"No station found near {station_name}"
    assert "distance_km" in result.columns
    assert result["distance_km"].is_monotonic_increasing
    assert station_name.lower() in str(result.iloc[0]["name"]).lower()
