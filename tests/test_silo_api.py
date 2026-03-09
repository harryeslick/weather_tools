"""Integration tests for SILO station search helpers."""

import os

import pytest

from weather_tools.silo_api import SiloAPI

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
