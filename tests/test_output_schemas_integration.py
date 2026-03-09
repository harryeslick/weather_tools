"""
Integration tests for output_schemas against real API data.

These tests call the live SILO and met.no APIs — they do NOT use mocks or
patching. They are excluded from the default test run; execute explicitly
with:

    uv run pytest tests/test_output_schemas_integration.py -m integration -v

Prerequisites
-------------
- ``SILO_API_KEY`` environment variable set to your registered SILO e-mail.
- Network access to api.silo.bom.gov.au and api.met.no.

All four point-data sources are validated:
1. SILO PatchedPoint  → SiloPointSchema
2. SILO DataDrill     → SiloPointSchema
3. met.no forecast    → MetNoForecastSchema
4. Merged history+forecast → MergedPointSchema
"""

import os

import pandas as pd
import pytest

from weather_tools.output_schemas import (
    MetNoForecastSchema,
    MergedPointSchema,
    SiloPointSchema,
    validate_point_dataframe,
)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

# Brisbane area — good data coverage for all sources
_LAT = -27.5
_LON = 153.0
_STATION_CODE = "40913"  # Bureau of Meteorology station: Brisbane
_VARIABLES = ["daily_rain", "max_temp", "min_temp"]

# A short, fixed historical window guaranteed to have complete SILO data
_SILO_START = "20240101"
_SILO_END = "20240107"


def _prepare_silo_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strip SILO-specific columns that are not part of the SiloPointSchema contract.

    The raw API response includes columns that are implementation details of the
    SILO service, not part of the point-data schema:

    - ``*_source`` columns — data quality / infill flags for each variable
    - ``metadata``         — JSON query metadata stored only in row 0
    - ``station``          — station code scalar (PatchedPoint only)
    - ``latitude`` / ``longitude`` — grid coordinates (DataDrill only)

    Location and metadata belong in ``PointMetadata``, not in the DataFrame.
    """
    non_schema = [
        c
        for c in df.columns
        if c.endswith("_source") or c in ("station", "latitude", "longitude")
    ]
    return df.drop(columns=non_schema, errors="ignore")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def silo_api():
    """Return a SiloAPI instance, skipping the module if no key is set."""
    from weather_tools.silo_api import SiloAPI

    if not os.environ.get("SILO_API_KEY"):
        pytest.skip("SILO_API_KEY environment variable not set")
    return SiloAPI()


@pytest.fixture(scope="module")
def metno_api():
    """Return a MetNoAPI instance."""
    from weather_tools.metno_api import MetNoAPI

    return MetNoAPI(enable_cache=True)


@pytest.fixture(scope="module")
def raw_patched_point(silo_api):
    """Fetch a small PatchedPoint window; cached for the module."""
    df, _ = silo_api.get_patched_point(
        station_code=_STATION_CODE,
        start_date=_SILO_START,
        end_date=_SILO_END,
        variables=_VARIABLES,
    )
    return df


@pytest.fixture(scope="module")
def raw_data_drill(silo_api):
    """Fetch a small DataDrill window; cached for the module."""
    df, _ = silo_api.get_data_drill(
        latitude=_LAT,
        longitude=_LON,
        start_date=_SILO_START,
        end_date=_SILO_END,
        variables=_VARIABLES,
    )
    return df


@pytest.fixture(scope="module")
def raw_forecast(metno_api):
    """Fetch a 7-day met.no forecast; cached for the module."""
    try:
        return metno_api.get_daily_forecast(latitude=_LAT, longitude=_LON, days=7)
    except Exception as exc:
        pytest.skip(f"met.no API unavailable: {exc}")


@pytest.fixture(scope="module")
def raw_merged(silo_api, raw_forecast):
    """Fetch SILO history and merge with the cached forecast."""
    from weather_tools.merge_weather_data import merge_historical_and_forecast

    forecast_start = raw_forecast["date"].min()
    history_end = forecast_start - pd.Timedelta(days=1)
    history_start = history_end - pd.Timedelta(days=6)

    silo_history, _ = silo_api.get_data_drill(
        latitude=_LAT,
        longitude=_LON,
        start_date=history_start.strftime("%Y%m%d"),
        end_date=history_end.strftime("%Y%m%d"),
        variables=_VARIABLES,
    )

    return merge_historical_and_forecast(
        silo_data=silo_history,
        metno_data=raw_forecast,
        overlap_strategy="prefer_silo",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestSiloPointSchema:
    """SiloPointSchema validated against live SILO API responses."""

    def test_patched_point_no_schema_violations(self, raw_patched_point):
        """Cleaned PatchedPoint DataFrame passes SiloPointSchema with no issues."""
        df = _prepare_silo_df(raw_patched_point)
        issues = validate_point_dataframe(df, SiloPointSchema)
        assert issues == [], f"Schema violations:\n" + "\n".join(issues)

    def test_patched_point_date_column_present(self, raw_patched_point):
        """PatchedPoint response has a 'date' column (not 'time')."""
        assert "date" in raw_patched_point.columns, (
            "Expected 'date' column; found: " + str(raw_patched_point.columns.tolist())
        )

    def test_patched_point_date_is_datetime(self, raw_patched_point):
        """PatchedPoint 'date' column is timezone-naive datetime64."""
        assert pd.api.types.is_datetime64_any_dtype(raw_patched_point["date"])
        assert raw_patched_point["date"].dt.tz is None

    def test_patched_point_variable_columns_are_float(self, raw_patched_point):
        """Requested variable columns are float64."""
        df = _prepare_silo_df(raw_patched_point)
        for var in _VARIABLES:
            assert pd.api.types.is_float_dtype(df[var]), (
                f"Column '{var}' expected float64, got {df[var].dtype}"
            )

    def test_patched_point_row_count(self, raw_patched_point):
        """PatchedPoint returns the expected number of rows for the date window."""
        assert len(raw_patched_point) == 7

    def test_patched_point_range_index(self, raw_patched_point):
        """DataFrame uses RangeIndex, not a DatetimeIndex."""
        assert isinstance(raw_patched_point.index, pd.RangeIndex)

    def test_data_drill_no_schema_violations(self, raw_data_drill):
        """Cleaned DataDrill DataFrame passes SiloPointSchema with no issues."""
        df = _prepare_silo_df(raw_data_drill)
        issues = validate_point_dataframe(df, SiloPointSchema)
        assert issues == [], f"Schema violations:\n" + "\n".join(issues)

    def test_data_drill_date_column_present(self, raw_data_drill):
        """DataDrill response has a 'date' column (not 'time')."""
        assert "date" in raw_data_drill.columns

    def test_data_drill_date_is_datetime(self, raw_data_drill):
        """DataDrill 'date' column is timezone-naive datetime64."""
        assert pd.api.types.is_datetime64_any_dtype(raw_data_drill["date"])
        assert raw_data_drill["date"].dt.tz is None

    def test_data_drill_variable_columns_are_float(self, raw_data_drill):
        """Requested variable columns are float64."""
        df = _prepare_silo_df(raw_data_drill)
        for var in _VARIABLES:
            assert pd.api.types.is_float_dtype(df[var]), (
                f"Column '{var}' expected float64, got {df[var].dtype}"
            )

    def test_data_drill_row_count(self, raw_data_drill):
        """DataDrill returns the expected number of rows for the date window."""
        assert len(raw_data_drill) == 7

@pytest.mark.integration
class TestMetNoForecastSchema:
    """MetNoForecastSchema validated against a live met.no API response."""

    def test_forecast_no_schema_violations(self, raw_forecast):
        """Daily forecast DataFrame passes MetNoForecastSchema with no issues."""
        issues = validate_point_dataframe(raw_forecast, MetNoForecastSchema)
        assert issues == [], f"Schema violations:\n" + "\n".join(issues)

    def test_forecast_date_column_present(self, raw_forecast):
        """Forecast DataFrame has a 'date' column (not 'time')."""
        assert "date" in raw_forecast.columns

    def test_forecast_date_is_timezone_naive(self, raw_forecast):
        """Forecast 'date' column is timezone-naive (matches SILO format)."""
        assert pd.api.types.is_datetime64_any_dtype(raw_forecast["date"])
        assert raw_forecast["date"].dt.tz is None, (
            "Expected timezone-naive; got tz=" + str(raw_forecast["date"].dt.tz)
        )

    def test_forecast_expected_columns_present(self, raw_forecast):
        """Forecast DataFrame contains the core met.no variable columns."""
        for col in ("min_temperature", "max_temperature", "total_precipitation"):
            assert col in raw_forecast.columns, f"Missing expected column '{col}'"

    def test_forecast_variables_are_float(self, raw_forecast):
        """Numeric forecast columns are float64."""
        float_cols = [
            "min_temperature",
            "max_temperature",
            "total_precipitation",
            "avg_wind_speed",
        ]
        for col in float_cols:
            if col in raw_forecast.columns:
                assert pd.api.types.is_float_dtype(raw_forecast[col]), (
                    f"Column '{col}' expected float64, got {raw_forecast[col].dtype}"
                )

    def test_forecast_range_index(self, raw_forecast):
        """Forecast DataFrame uses RangeIndex."""
        assert isinstance(raw_forecast.index, pd.RangeIndex)

    def test_forecast_row_count(self, raw_forecast):
        """get_daily_forecast(days=7) returns exactly 7 rows."""
        assert len(raw_forecast) == 7


@pytest.mark.integration
class TestMergedPointSchema:
    """MergedPointSchema validated against a live merged SILO + met.no DataFrame."""

    def test_merged_no_schema_violations(self, raw_merged):
        """Merged DataFrame passes MergedPointSchema with no issues."""
        issues = validate_point_dataframe(raw_merged, MergedPointSchema)
        assert issues == [], f"Schema violations:\n" + "\n".join(issues)

    def test_merged_date_column_present(self, raw_merged):
        """Merged DataFrame has a 'date' column."""
        assert "date" in raw_merged.columns

    def test_merged_provenance_columns_present(self, raw_merged):
        """Merged DataFrame has 'data_source' and 'is_forecast' columns."""
        assert "data_source" in raw_merged.columns
        assert "is_forecast" in raw_merged.columns

    def test_merged_data_source_values(self, raw_merged):
        """'data_source' column contains only 'silo' and 'metno' values."""
        values = set(raw_merged["data_source"].unique())
        assert values <= {"silo", "metno"}, f"Unexpected data_source values: {values}"

    def test_merged_is_forecast_dtype(self, raw_merged):
        """'is_forecast' column contains boolean values."""
        assert raw_merged["is_forecast"].dtype == bool or pd.api.types.is_bool_dtype(
            raw_merged["is_forecast"]
        )

    def test_merged_silo_rows_not_forecast(self, raw_merged):
        """All rows with data_source='silo' have is_forecast=False."""
        silo_rows = raw_merged[raw_merged["data_source"] == "silo"]
        assert (silo_rows["is_forecast"] == False).all(), (  # noqa: E712
            "Some SILO rows are unexpectedly marked as forecasts"
        )

    def test_merged_metno_rows_are_forecast(self, raw_merged):
        """All rows with data_source='metno' have is_forecast=True."""
        metno_rows = raw_merged[raw_merged["data_source"] == "metno"]
        assert (metno_rows["is_forecast"] == True).all(), (  # noqa: E712
            "Some met.no rows are unexpectedly not marked as forecasts"
        )

    def test_merged_date_sorted_ascending(self, raw_merged):
        """Merged DataFrame is sorted by date ascending."""
        assert raw_merged["date"].is_monotonic_increasing

    def test_merged_uses_silo_column_names(self, raw_merged):
        """After merging, variable columns use SILO canonical names."""
        for col in ("daily_rain", "max_temp", "min_temp"):
            assert col in raw_merged.columns, (
                f"Expected SILO canonical column '{col}' after merge"
            )

    def test_merged_range_index(self, raw_merged):
        """Merged DataFrame uses RangeIndex."""
        assert isinstance(raw_merged.index, pd.RangeIndex)
