"""Unit tests for local_models.ExtractQuery and DownloadQuery."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from weather_tools.local_models import (
    DEFAULT_DAILY_VARIABLES,
    DownloadQuery,
    ExtractQuery,
)
from weather_tools.silo_models import AustralianCoordinates, SiloDateRange

# ---------------------------------------------------------------------------
# ExtractQuery
# ---------------------------------------------------------------------------


class TestExtractQueryValid:
    """ExtractQuery accepts well-formed inputs."""

    def test_minimal_valid_query(self):
        q = ExtractQuery(
            coordinates=AustralianCoordinates(latitude=-27.5, longitude=153.0),
            date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
        )
        assert q.coordinates.latitude == -27.5
        assert q.coordinates.longitude == 153.0
        assert q.date_range.start_date == "20230101"
        assert q.date_range.end_date == "20230131"
        assert q.variables is None
        assert q.silo_dir is None
        assert q.tolerance == 0.1
        assert q.keep_location is False

    def test_full_query_with_overrides(self):
        q = ExtractQuery(
            coordinates=AustralianCoordinates(latitude=-30.0, longitude=140.0),
            date_range=SiloDateRange(start_date="2020-06-01", end_date="2020-06-30"),
            variables=["daily_rain", "max_temp"],
            silo_dir=Path("/tmp/silo"),
            tolerance=0.5,
            keep_location=True,
        )
        assert q.variables == ["daily_rain", "max_temp"]
        assert q.silo_dir == Path("/tmp/silo")
        assert q.tolerance == 0.5
        assert q.keep_location is True
        # ISO normalised by SiloDateRange's base validator
        assert q.date_range.start_date == "20200601"
        assert q.date_range.end_date == "20200630"

    def test_monthly_rain_accepted(self):
        """Local files include monthly_rain even though SILO API does not."""
        q = ExtractQuery(
            coordinates=AustralianCoordinates(latitude=-27.5, longitude=153.0),
            date_range=SiloDateRange(start_date="20230101", end_date="20231231"),
            variables=["monthly_rain"],
        )
        assert q.variables == ["monthly_rain"]


class TestExtractQueryValidationErrors:
    """Invalid ExtractQuery inputs raise ValidationError."""

    def test_unknown_variable_rejected(self):
        with pytest.raises(ValidationError, match="Unknown variables"):
            ExtractQuery(
                coordinates=AustralianCoordinates(latitude=-27.5, longitude=153.0),
                date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
                variables=["not_a_variable"],
            )

    def test_iso_and_yyyymmdd_both_accepted(self):
        """SiloDateRange should normalise both forms."""
        q_iso = ExtractQuery(
            coordinates=AustralianCoordinates(latitude=-27.5, longitude=153.0),
            date_range=SiloDateRange(start_date="2023-01-01", end_date="2023-01-31"),
        )
        q_compact = ExtractQuery(
            coordinates=AustralianCoordinates(latitude=-27.5, longitude=153.0),
            date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
        )
        assert q_iso.date_range.start_date == q_compact.date_range.start_date
        assert q_iso.date_range.end_date == q_compact.date_range.end_date

    def test_latitude_out_of_australian_bounds(self):
        with pytest.raises(ValidationError):
            ExtractQuery(
                coordinates=AustralianCoordinates(latitude=0.0, longitude=153.0),
                date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
            )

    def test_year_before_silo_window(self):
        with pytest.raises(ValidationError, match="1889"):
            ExtractQuery(
                coordinates=AustralianCoordinates(latitude=-27.5, longitude=153.0),
                date_range=SiloDateRange(start_date="18000101", end_date="18000131"),
            )

    def test_tolerance_must_be_positive(self):
        with pytest.raises(ValidationError):
            ExtractQuery(
                coordinates=AustralianCoordinates(latitude=-27.5, longitude=153.0),
                date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
                tolerance=0.0,
            )

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            ExtractQuery(
                coordinates=AustralianCoordinates(latitude=-27.5, longitude=153.0),
                date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
                bogus=True,
            )


# ---------------------------------------------------------------------------
# DownloadQuery
# ---------------------------------------------------------------------------


class TestDownloadQueryValid:
    """DownloadQuery accepts well-formed inputs."""

    def test_default_variables(self):
        q = DownloadQuery(start_year=2020, end_year=2023)
        assert q.variables == DEFAULT_DAILY_VARIABLES
        assert q.start_year == 2020
        assert q.end_year == 2023
        assert q.silo_dir is None

    def test_explicit_variables(self):
        q = DownloadQuery(
            variables=["daily_rain", "monthly_rain"],
            start_year=2020,
            end_year=2023,
        )
        assert q.variables == ["daily_rain", "monthly_rain"]

    def test_monthly_rain_accepted(self):
        """Variables with no SILO API code are valid for downloads."""
        q = DownloadQuery(variables=["monthly_rain"], start_year=2020, end_year=2020)
        assert q.variables == ["monthly_rain"]

    def test_silo_dir_override(self):
        q = DownloadQuery(start_year=2020, end_year=2020, silo_dir=Path("/data/silo"))
        assert q.silo_dir == Path("/data/silo")

    def test_same_start_and_end_year(self):
        q = DownloadQuery(start_year=2023, end_year=2023)
        assert q.start_year == q.end_year == 2023


class TestDownloadQueryValidationErrors:
    """Invalid DownloadQuery inputs raise ValidationError."""

    def test_unknown_variable_rejected(self):
        with pytest.raises(ValidationError, match="Unknown variables"):
            DownloadQuery(variables=["bogus_var"], start_year=2020, end_year=2020)

    def test_start_year_below_lower_bound(self):
        with pytest.raises(ValidationError):
            DownloadQuery(start_year=1800, end_year=2020)

    def test_start_year_above_upper_bound(self):
        with pytest.raises(ValidationError):
            DownloadQuery(start_year=2200, end_year=2200)

    def test_end_year_above_upper_bound(self):
        with pytest.raises(ValidationError):
            DownloadQuery(start_year=2020, end_year=2200)

    def test_end_year_below_lower_bound(self):
        with pytest.raises(ValidationError):
            DownloadQuery(start_year=1700, end_year=1800)

    def test_start_year_after_end_year(self):
        with pytest.raises(ValidationError, match="start_year"):
            DownloadQuery(start_year=2025, end_year=2020)

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            DownloadQuery(start_year=2020, end_year=2020, bogus=True)
