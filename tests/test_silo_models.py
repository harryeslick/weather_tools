"""Unit tests for silo_models.py — validators, query construction, and API params."""

import pytest
from pydantic import ValidationError

from weather_tools.silo_models import (
    AustralianCoordinates,
    DataDrillQuery,
    PatchedPointQuery,
    SiloDateRange,
    SiloFormat,
)

# ---------------------------------------------------------------------------
# FIX 1: Variables without SILO API codes must be rejected at validation time
# ---------------------------------------------------------------------------


class TestUntransportableVariableRejection:
    """Variables with no SILO API code (e.g. monthly_rain) must raise at construction."""

    def test_monthly_rain_rejected_in_patched_point(self):
        """monthly_rain has no SILO API code — must raise ValidationError."""
        with pytest.raises(ValidationError, match="no API code"):
            PatchedPointQuery(
                format=SiloFormat.CSV,
                station_code="30043",
                date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
                variables=["monthly_rain"],
            )

    def test_monthly_rain_rejected_in_data_drill(self):
        with pytest.raises(ValidationError, match="no API code"):
            DataDrillQuery(
                coordinates=AustralianCoordinates(latitude=-27.5, longitude=151.0),
                date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
                variables=["monthly_rain"],
            )

    def test_metno_only_variable_rejected(self):
        """met.no-only variables (e.g. relative_humidity) also have no SILO code."""
        with pytest.raises(ValidationError, match="no API code"):
            PatchedPointQuery(
                format=SiloFormat.CSV,
                station_code="30043",
                date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
                variables=["relative_humidity"],
            )

    def test_mixed_valid_and_untransportable_rejected(self):
        """A mix of valid and untransportable variables should still raise."""
        with pytest.raises(ValidationError, match="no API code"):
            PatchedPointQuery(
                format=SiloFormat.CSV,
                station_code="30043",
                date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
                variables=["daily_rain", "monthly_rain"],
            )

    def test_valid_silo_variable_accepted(self):
        """Variables with SILO API codes must continue to be accepted."""
        query = PatchedPointQuery(
            format=SiloFormat.CSV,
            station_code="30043",
            date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
            variables=["daily_rain", "max_temp", "min_temp"],
        )
        assert query.variables == ["daily_rain", "max_temp", "min_temp"]


# ---------------------------------------------------------------------------
# 1.2 extra="forbid" hardening
# ---------------------------------------------------------------------------


class TestBaseSiloQueryExtraForbid:
    """Unknown kwargs to PatchedPointQuery / DataDrillQuery must raise ValidationError."""

    def test_patched_point_extra_kwarg_raises(self):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            PatchedPointQuery(
                format=SiloFormat.CSV,
                station_code="30043",
                date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
                values=["daily_rain"],  # wrong kwarg — should be variables=
            )

    def test_data_drill_extra_kwarg_raises(self):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            DataDrillQuery(
                coordinates=AustralianCoordinates(latitude=-27.5, longitude=151.0),
                date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
                format=SiloFormat.CSV,
                values=["daily_rain"],  # wrong kwarg — should be variables=
            )


# ---------------------------------------------------------------------------
# 1.2 to_api_params — variables flow through correctly
# ---------------------------------------------------------------------------


class TestToApiParamsVariables:
    """Confirm that variables= actually reaches to_api_params() output."""

    def test_patched_point_csv_variables_in_comment(self):
        """CSV/JSON formats emit variable codes via 'comment' param."""
        query = PatchedPointQuery(
            format=SiloFormat.CSV,
            station_code="30043",
            date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
            variables=["daily_rain", "max_temp"],
        )
        params = query.to_api_params(api_key="test@example.com")
        assert "comment" in params, "Expected 'comment' key for CSV format with variables"
        # daily_rain → "R", max_temp → "X"
        assert "R" in params["comment"]
        assert "X" in params["comment"]

    def test_patched_point_json_variables_in_comment(self):
        query = PatchedPointQuery(
            format=SiloFormat.JSON,
            station_code="30043",
            date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
            variables=["daily_rain"],
        )
        params = query.to_api_params(api_key="test@example.com")
        assert "comment" in params
        assert "R" in params["comment"]

    def test_patched_point_apsim_no_comment(self):
        """APSIM format does not use the 'comment' param for variable selection."""
        query = PatchedPointQuery(
            format=SiloFormat.APSIM,
            station_code="30043",
            date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
            variables=["daily_rain", "max_temp"],
        )
        params = query.to_api_params(api_key="test@example.com")
        # APSIM uses password=apirequest but not comment for variable selection
        assert params.get("password") == "apirequest"
        assert "comment" not in params

    def test_patched_point_apsim_params_complete(self):
        """APSIM params include station, start, finish, username, password."""
        query = PatchedPointQuery(
            format=SiloFormat.APSIM,
            station_code="30043",
            date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
            variables=["daily_rain"],
        )
        params = query.to_api_params(api_key="test@example.com")
        assert params["station"] == "30043"
        assert params["start"] == "20230101"
        assert params["finish"] == "20230131"
        assert params["username"] == "test@example.com"
        assert params["password"] == "apirequest"

    def test_data_drill_csv_variables_in_comment(self):
        query = DataDrillQuery(
            coordinates=AustralianCoordinates(latitude=-27.5, longitude=151.0),
            date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
            format=SiloFormat.CSV,
            variables=["daily_rain", "max_temp"],
        )
        params = query.to_api_params(api_key="test@example.com")
        assert "comment" in params
        assert "R" in params["comment"]
        assert "X" in params["comment"]


# ---------------------------------------------------------------------------
# 2.1 PatchedPointQuery — data format requires station_code
# ---------------------------------------------------------------------------


class TestPatchedPointDataFormatRequirements:
    """Data formats must raise ValidationError when station_code is absent."""

    @pytest.mark.parametrize(
        "fmt",
        [
            SiloFormat.CSV,
            SiloFormat.JSON,
            SiloFormat.APSIM,
            SiloFormat.STANDARD,
            SiloFormat.ALLDATA,
        ],
    )
    def test_missing_station_code_raises(self, fmt):
        with pytest.raises(ValidationError) as exc_info:
            PatchedPointQuery(
                format=fmt,
                date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
            )
        errors = exc_info.value.errors()
        msgs = " ".join(e["msg"] for e in errors)
        assert "station_code" in msgs, f"Expected 'station_code' in error for format={fmt}"

    @pytest.mark.parametrize(
        "fmt",
        [
            SiloFormat.CSV,
            SiloFormat.JSON,
            SiloFormat.APSIM,
            SiloFormat.STANDARD,
            SiloFormat.ALLDATA,
        ],
    )
    def test_missing_date_range_raises(self, fmt):
        with pytest.raises(ValidationError) as exc_info:
            PatchedPointQuery(
                format=fmt,
                station_code="30043",
            )
        errors = exc_info.value.errors()
        msgs = " ".join(e["msg"] for e in errors)
        assert "date_range" in msgs, f"Expected 'date_range' in error for format={fmt}"

    def test_valid_csv_query_succeeds(self):
        """A complete CSV query should not raise."""
        query = PatchedPointQuery(
            format=SiloFormat.CSV,
            station_code="30043",
            date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
        )
        assert query.station_code == "30043"

    def test_name_format_no_station_required(self):
        """NAME format should succeed without station_code."""
        query = PatchedPointQuery(format=SiloFormat.NAME)
        assert query.format == "name"

    def test_near_format_without_station_raises(self):
        """NEAR format without station_code should still raise."""
        with pytest.raises(ValidationError):
            PatchedPointQuery(format=SiloFormat.NEAR)


# ---------------------------------------------------------------------------
# SiloDateRange accepts ISO (YYYY-MM-DD) input and normalises to YYYYMMDD
# ---------------------------------------------------------------------------


class TestSiloDateRangeIsoInput:
    """SiloDateRange must accept either YYYY-MM-DD or YYYYMMDD; storage stays YYYYMMDD."""

    def test_iso_input_normalised_to_yyyymmdd(self):
        dr = SiloDateRange(start_date="2023-01-01", end_date="2023-01-31")
        assert dr.start_date == "20230101"
        assert dr.end_date == "20230131"

    def test_yyyymmdd_input_unchanged(self):
        dr = SiloDateRange(start_date="20230101", end_date="20230131")
        assert dr.start_date == "20230101"
        assert dr.end_date == "20230131"

    def test_mixed_input_forms(self):
        dr = SiloDateRange(start_date="2023-01-01", end_date="20230131")
        assert dr.start_date == "20230101"
        assert dr.end_date == "20230131"

    def test_invalid_iso_month_rejected(self):
        with pytest.raises(ValidationError):
            SiloDateRange(start_date="2023-13-01", end_date="2023-12-31")

    def test_malformed_string_rejected(self):
        # Not ISO, not YYYYMMDD → pattern check rejects it.
        with pytest.raises(ValidationError):
            SiloDateRange(start_date="2023/01/01", end_date="20230131")

    def test_iso_input_preserves_date_order_validation(self):
        # start > end must still raise after normalisation.
        with pytest.raises(ValidationError):
            SiloDateRange(start_date="2023-12-31", end_date="2023-01-01")
