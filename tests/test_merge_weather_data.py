"""
Tests for weather data merging functionality.

Tests merging SILO historical data with met.no forecasts.
"""

import numpy as np
import pandas as pd
import pytest

from weather_tools.merge_weather_data import (
    MergeValidationError,
    get_merge_summary,
    merge_historical_and_forecast,
    prepare_metno_for_merge,
    # fill_missing_silo_variables,
    validate_date_continuity,
    validate_merge_compatibility,
)


@pytest.fixture
def sample_silo_data():
    """Create sample SILO DataFrame."""
    return pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", "2023-01-10"),
            "day": range(1, 11),
            "year": [2023] * 10,
            "daily_rain": np.random.rand(10) * 10,
            "max_temp": np.random.rand(10) * 10 + 25,
            "min_temp": np.random.rand(10) * 10 + 15,
            "vp": np.random.rand(10) * 5 + 15,
            "radiation": np.random.rand(10) * 10 + 15,
        }
    )


@pytest.fixture
def sample_metno_data():
    """Create sample met.no DataFrame (with met.no column names)."""
    return pd.DataFrame(
        {
            "date": pd.date_range("2023-01-11", "2023-01-17"),
            "min_temperature": np.random.rand(7) * 10 + 15,
            "max_temperature": np.random.rand(7) * 10 + 25,
            "total_precipitation": np.random.rand(7) * 10,
            "avg_pressure": np.random.rand(7) * 5 + 1010,
        }
    )


@pytest.fixture
def sample_metno_data_silo_format():
    """Create sample met.no DataFrame already in SILO format."""
    return pd.DataFrame(
        {
            "date": pd.date_range("2023-01-11", "2023-01-17"),
            "day": range(11, 18),
            "year": [2023] * 7,
            "min_temp": np.random.rand(7) * 10 + 15,
            "max_temp": np.random.rand(7) * 10 + 25,
            "daily_rain": np.random.rand(7) * 10,
            "mslp": np.random.rand(7) * 5 + 1010,
        }
    )


class TestMergeBasicFunctionality:
    """Test basic merging functionality."""

    def test_merge_continuous_dates(self, sample_silo_data, sample_metno_data_silo_format):
        """Test merging with continuous dates."""
        merged = merge_historical_and_forecast(sample_silo_data, sample_metno_data_silo_format)

        assert len(merged) == len(sample_silo_data) + len(sample_metno_data_silo_format)
        assert "data_source" in merged.columns
        assert "is_forecast" in merged.columns

        # Check data sources
        assert (merged["data_source"] == "silo").sum() == len(sample_silo_data)
        assert (merged["data_source"] == "metno").sum() == len(sample_metno_data_silo_format)

    def test_merge_adds_metadata_columns(self, sample_silo_data, sample_metno_data_silo_format):
        """Test that merge adds metadata columns."""
        merged = merge_historical_and_forecast(sample_silo_data, sample_metno_data_silo_format)

        assert "data_source" in merged.columns
        assert "is_forecast" in merged.columns
        assert "forecast_generated_at" in merged.columns

        # Check SILO records
        silo_records = merged[merged["data_source"] == "silo"]
        assert all(silo_records["is_forecast"] == False)

        # Check met.no records
        metno_records = merged[merged["data_source"] == "metno"]
        assert all(metno_records["is_forecast"] == True)

    def test_merge_preserves_data_values(self, sample_silo_data, sample_metno_data_silo_format):
        """Test that merge preserves original data values."""
        merged = merge_historical_and_forecast(sample_silo_data, sample_metno_data_silo_format)

        # Check first SILO value preserved
        first_silo_rain = sample_silo_data["daily_rain"].iloc[0]
        merged_first_rain = merged[merged["data_source"] == "silo"]["daily_rain"].iloc[0]
        assert merged_first_rain == pytest.approx(first_silo_rain)

        # Check first met.no value preserved
        first_metno_rain = sample_metno_data_silo_format["daily_rain"].iloc[0]
        merged_first_metno_rain = merged[merged["data_source"] == "metno"]["daily_rain"].iloc[0]
        assert merged_first_metno_rain == pytest.approx(first_metno_rain)


class TestMergeValidation:
    """Test merge validation logic."""

    def test_validation_detects_date_gap(self, sample_silo_data):
        """Test validation detects gaps in dates."""
        # Create met.no data with a gap
        metno_with_gap = pd.DataFrame(
            {
                "date": pd.date_range("2023-01-15", "2023-01-20"),  # 4-day gap
                "min_temp": [20.0] * 6,
                "max_temp": [30.0] * 6,
                "daily_rain": [5.0] * 6,
            }
        )

        with pytest.raises(MergeValidationError) as exc_info:
            merge_historical_and_forecast(sample_silo_data, metno_with_gap)

        assert "gap" in str(exc_info.value).lower()

    def test_validate_merge_compatibility_success(
        self, sample_silo_data, sample_metno_data_silo_format
    ):
        """Test successful validation."""
        is_valid, issues = validate_merge_compatibility(
            sample_silo_data,
            sample_metno_data_silo_format,
            pd.Timestamp("2023-01-11"),
            overlap_strategy="prefer_silo",
        )

        assert is_valid is True
        assert len(issues) == 0

    def test_validate_merge_compatibility_missing_columns(self):
        """Test validation catches missing columns."""
        df_no_date = pd.DataFrame({"value": [1, 2, 3]})
        df_with_date = pd.DataFrame({"date": pd.date_range("2023-01-01", periods=3)})

        is_valid, issues = validate_merge_compatibility(
            df_no_date, df_with_date, pd.Timestamp("2023-01-01"), overlap_strategy="prefer_silo"
        )

        assert is_valid is False
        assert len(issues) > 0
        assert any("missing 'date'" in issue.lower() for issue in issues)


class TestOverlapHandling:
    """Test handling of overlapping dates."""

    def test_overlap_prefer_silo(self, sample_silo_data):
        """Test prefer_silo overlap strategy."""
        # Create overlapping met.no data
        metno_overlap = pd.DataFrame(
            {
                "date": pd.date_range("2023-01-08", "2023-01-15"),  # Overlaps last 3 days
                "min_temp": [20.0] * 8,
                "max_temp": [30.0] * 8,
                "daily_rain": [5.0] * 8,
            }
        )

        merged = merge_historical_and_forecast(
            sample_silo_data, metno_overlap, overlap_strategy="prefer_silo"
        )

        # Overlapping dates should have SILO data
        overlap_dates = pd.date_range("2023-01-08", "2023-01-10")
        for date in overlap_dates:
            records = merged[merged["date"] == date]
            assert len(records) == 1
            assert records["data_source"].iloc[0] == "silo"

    def test_overlap_prefer_metno(self, sample_silo_data):
        """Test prefer_metno overlap strategy."""
        metno_overlap = pd.DataFrame(
            {
                "date": pd.date_range("2023-01-08", "2023-01-15"),
                "min_temp": [20.0] * 8,
                "max_temp": [30.0] * 8,
                "daily_rain": [5.0] * 8,
            }
        )

        merged = merge_historical_and_forecast(
            sample_silo_data, metno_overlap, overlap_strategy="prefer_metno"
        )

        # Overlapping dates should have met.no data
        overlap_dates = pd.date_range("2023-01-08", "2023-01-10")
        for date in overlap_dates:
            records = merged[merged["date"] == date]
            assert len(records) == 1
            assert records["data_source"].iloc[0] == "metno"

    def test_invalid_overlap_strategy_with_overlap(self, sample_silo_data):
        """Test that invalid overlap strategy causes validation to fail on overlap."""
        metno_overlap = pd.DataFrame(
            {
                "date": pd.date_range("2023-01-08", "2023-01-15"),
                "min_temp": [20.0] * 8,
                "max_temp": [30.0] * 8,
                "daily_rain": [5.0] * 8,
            }
        )

        # Invalid overlap_strategy with overlapping data raises MergeValidationError
        with pytest.raises(MergeValidationError) as exc_info:
            merge_historical_and_forecast(
                sample_silo_data, metno_overlap, overlap_strategy="invalid_strategy"
            )

        assert "overlap" in str(exc_info.value).lower()

    def test_invalid_overlap_strategy_without_overlap(
        self, sample_silo_data, sample_metno_data_silo_format
    ):
        """Test that invalid overlap strategy raises ValueError when no overlap exists."""
        # Use continuous data without overlap to reach the ValueError check
        with pytest.raises(ValueError) as exc_info:
            merge_historical_and_forecast(
                sample_silo_data, sample_metno_data_silo_format, overlap_strategy="invalid_strategy"
            )

        assert "overlap_strategy" in str(exc_info.value).lower()

    def test_overlap_error_strategy_raises_on_overlap(self, sample_silo_data):
        """Test that overlap_strategy='error' raises MergeValidationError when overlap exists."""
        metno_overlap = pd.DataFrame(
            {
                "date": pd.date_range("2023-01-08", "2023-01-15"),  # overlaps last 3 SILO days
                "min_temp": [20.0] * 8,
                "max_temp": [30.0] * 8,
                "daily_rain": [5.0] * 8,
            }
        )

        with pytest.raises(MergeValidationError) as exc_info:
            merge_historical_and_forecast(sample_silo_data, metno_overlap, overlap_strategy="error")

        msg = str(exc_info.value)
        assert "overlap" in msg.lower()
        # Message should mention the overlapping dates count
        assert "3" in msg

    def test_overlap_error_strategy_succeeds_without_overlap(
        self, sample_silo_data, sample_metno_data_silo_format
    ):
        """Test that overlap_strategy='error' merges successfully when there is no overlap."""
        merged = merge_historical_and_forecast(
            sample_silo_data, sample_metno_data_silo_format, overlap_strategy="error"
        )

        assert len(merged) == len(sample_silo_data) + len(sample_metno_data_silo_format)
        assert (merged["data_source"] == "silo").sum() == len(sample_silo_data)
        assert (merged["data_source"] == "metno").sum() == len(sample_metno_data_silo_format)

    def test_prefer_silo_deduplicates_overlap(self, sample_silo_data):
        """Test prefer_silo leaves exactly one row per overlapping date (SILO wins)."""
        metno_overlap = pd.DataFrame(
            {
                "date": pd.date_range("2023-01-08", "2023-01-15"),
                "min_temp": [20.0] * 8,
                "max_temp": [30.0] * 8,
                "daily_rain": [5.0] * 8,
            }
        )

        merged = merge_historical_and_forecast(
            sample_silo_data, metno_overlap, overlap_strategy="prefer_silo"
        )

        # Each date should appear exactly once
        assert merged["date"].duplicated().sum() == 0

    def test_prefer_metno_deduplicates_overlap(self, sample_silo_data):
        """Test prefer_metno leaves exactly one row per overlapping date (met.no wins)."""
        metno_overlap = pd.DataFrame(
            {
                "date": pd.date_range("2023-01-08", "2023-01-15"),
                "min_temp": [20.0] * 8,
                "max_temp": [30.0] * 8,
                "daily_rain": [5.0] * 8,
            }
        )

        merged = merge_historical_and_forecast(
            sample_silo_data, metno_overlap, overlap_strategy="prefer_metno"
        )

        assert merged["date"].duplicated().sum() == 0


class TestMetNoPreparation:
    """Test preparation of met.no data."""

    def test_prepare_metno_converts_columns(self, sample_silo_data, sample_metno_data):
        """Test column name conversion."""
        prepared = prepare_metno_for_merge(sample_metno_data, sample_silo_data)

        # Should have SILO column names
        assert "min_temp" in prepared.columns
        assert "max_temp" in prepared.columns
        assert "daily_rain" in prepared.columns

        # Should not have met.no column names
        assert "min_temperature" not in prepared.columns
        assert "max_temperature" not in prepared.columns

    def test_prepare_metno_rh_converted_to_vapour_pressure(self, sample_silo_data):
        """vp must hold vapour pressure (hPa), not raw relative humidity (%).

        Regression test: the variable registry maps avg_relative_humidity -> vp,
        so a naive rename would leave RH percentages mislabelled as vapour
        pressure. prepare_metno_for_merge must instead derive true vp.
        """
        from weather_tools.weather_utils.dew_point import rh_to_vapor_pressure

        metno = pd.DataFrame(
            {
                "date": pd.date_range("2023-01-11", periods=3),
                "min_temperature": [15.0, 16.0, 14.0],
                "max_temperature": [25.0, 26.0, 24.0],
                "total_precipitation": [0.0, 2.0, 1.0],
                "avg_relative_humidity": [80.0, 60.0, 90.0],
            }
        )

        prepared = prepare_metno_for_merge(metno, sample_silo_data)

        expected = [
            rh_to_vapor_pressure(80.0, 20.0),
            rh_to_vapor_pressure(60.0, 21.0),
            rh_to_vapor_pressure(90.0, 19.0),
        ]
        assert np.allclose(prepared["vp"], expected)
        # Vapour pressure is ~5-40 hPa; raw RH would be ~0-100.
        assert (prepared["vp"] < 50).all()

    def test_prepare_metno_rh_conversion_can_be_disabled(self, sample_silo_data):
        """convert_rh_to_vp=False suppresses the RH->vp conversion entirely."""
        metno = pd.DataFrame(
            {
                "date": pd.date_range("2023-01-11", periods=3),
                "min_temperature": [15.0, 16.0, 14.0],
                "max_temperature": [25.0, 26.0, 24.0],
                "total_precipitation": [0.0, 2.0, 1.0],
                "avg_relative_humidity": [80.0, 60.0, 90.0],
            }
        )

        prepared = prepare_metno_for_merge(metno, sample_silo_data, convert_rh_to_vp=False)

        # No vp column should be produced, and RH must never be mislabelled as vp.
        assert "vp" not in prepared.columns
        # Raw RH is preserved under its own name, not silently dropped.
        assert "avg_relative_humidity" in prepared.columns
        assert prepared["avg_relative_humidity"].tolist() == [80.0, 60.0, 90.0]

    # def test_prepare_metno_adds_date_columns(self, sample_silo_data, sample_metno_data):
    #     """Test adding day and year columns."""
    #     prepared = prepare_metno_for_merge(sample_metno_data, sample_silo_data)

    #     assert 'day' in prepared.columns
    #     assert 'year' in prepared.columns
    #     assert prepared['year'].iloc[0] == 2023

    # def test_prepare_metno_with_fill_missing(self, sample_silo_data, sample_metno_data):
    #     """Test filling missing SILO variables."""
    #     prepared = prepare_metno_for_merge(
    #         sample_metno_data,
    #         sample_silo_data,
    #         fill_missing=True
    #     )

    #     # Should have filled some SILO-only variables
    #     assert 'radiation' in prepared.columns or 'evap_syn' in prepared.columns


# class TestMissingVariableFilling:
#     """Test filling of missing SILO variables."""

#     def test_fill_with_defaults(self, sample_silo_data, sample_metno_data_silo_format):
#         """Test filling with default values."""
#         # Remove a column that SILO has
#         metno_missing = sample_metno_data_silo_format.copy()

#         filled = fill_missing_silo_variables(
#             metno_missing,
#             sample_silo_data,
#             strategy="default"
#         )

#         # Should have radiation with default value
#         if 'radiation' not in metno_missing.columns:
#             assert 'radiation' in filled.columns
#             assert filled['radiation'].iloc[0] == pytest.approx(20.0)

#     def test_fill_with_last_known(self, sample_silo_data):
#         """Test filling with last known SILO value."""
#         metno_missing = pd.DataFrame({
#             'date': pd.date_range('2023-01-11', '2023-01-15'),
#             'min_temp': [20.0] * 5,
#             'max_temp': [30.0] * 5,
#         })

#         filled = fill_missing_silo_variables(
#             metno_missing,
#             sample_silo_data,
#             strategy="last_known"
#         )

#         # Should have radiation from last SILO value
#         assert 'radiation' in filled.columns

#     def test_fill_with_median(self, sample_silo_data):
#         """Test filling with median SILO value."""
#         metno_missing = pd.DataFrame({
#             'date': pd.date_range('2023-01-11', '2023-01-15'),
#             'min_temp': [20.0] * 5,
#             'max_temp': [30.0] * 5,
#         })

#         filled = fill_missing_silo_variables(
#             metno_missing,
#             sample_silo_data,
#             strategy="median"
#         )

#         # Should have radiation from median SILO value
#         assert 'radiation' in filled.columns


class TestDateContinuityValidation:
    """Test date continuity validation."""

    def test_continuous_dates_pass(self):
        """Test that continuous dates pass validation."""
        df1 = pd.DataFrame({"date": pd.date_range("2023-01-01", "2023-01-10")})
        df2 = pd.DataFrame({"date": pd.date_range("2023-01-11", "2023-01-20")})

        is_valid, error = validate_date_continuity(df1, df2)

        assert is_valid is True
        assert error is None

    def test_gap_detected(self):
        """Test that gaps are detected."""
        df1 = pd.DataFrame({"date": pd.date_range("2023-01-01", "2023-01-10")})
        df2 = pd.DataFrame({"date": pd.date_range("2023-01-15", "2023-01-20")})  # 4-day gap

        is_valid, error = validate_date_continuity(df1, df2, max_gap_days=1)

        assert is_valid is False
        assert error is not None
        assert "gap" in error.lower()

    def test_overlap_detected(self):
        """Test that overlaps are detected."""
        df1 = pd.DataFrame({"date": pd.date_range("2023-01-01", "2023-01-10")})
        df2 = pd.DataFrame({"date": pd.date_range("2023-01-08", "2023-01-20")})  # 3-day overlap

        is_valid, error = validate_date_continuity(df1, df2)

        assert is_valid is False
        assert error is not None
        assert "overlap" in error.lower()


class TestMergeSummary:
    """Test merge summary statistics."""

    def test_get_merge_summary(self, sample_silo_data, sample_metno_data_silo_format):
        """Test getting merge summary."""
        merged = merge_historical_and_forecast(sample_silo_data, sample_metno_data_silo_format)

        summary = get_merge_summary(merged)

        assert "total_records" in summary
        assert "silo_records" in summary
        assert "metno_records" in summary
        assert "date_range" in summary
        assert "transition_date" in summary

        assert summary["total_records"] == len(merged)
        assert summary["silo_records"] == len(sample_silo_data)
        assert summary["metno_records"] == len(sample_metno_data_silo_format)

    def test_summary_date_ranges(self, sample_silo_data, sample_metno_data_silo_format):
        """Test summary includes correct date ranges."""
        merged = merge_historical_and_forecast(sample_silo_data, sample_metno_data_silo_format)

        summary = get_merge_summary(merged)

        assert summary["date_range"]["start"] == sample_silo_data["date"].min()
        assert summary["date_range"]["end"] == sample_metno_data_silo_format["date"].max()
        assert summary["transition_date"] == sample_metno_data_silo_format["date"].min()


class TestAutoTransitionDate:
    """Test automatic transition date detection."""

    def test_auto_transition_date(self, sample_silo_data, sample_metno_data_silo_format):
        """Test that transition date is auto-detected from last SILO date."""
        merged = merge_historical_and_forecast(sample_silo_data, sample_metno_data_silo_format)

        # Should transition right after last SILO date
        last_silo_date = sample_silo_data["date"].max()
        first_metno_record = merged[merged["data_source"] == "metno"].iloc[0]

        assert first_metno_record["date"] > last_silo_date
