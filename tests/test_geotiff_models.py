"""Unit tests for the GeoTiffDownloadQuery Pydantic model."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from weather_tools.geotiff_models import GeoTiffDownloadQuery
from weather_tools.silo_models import SiloDateRange


class TestValidConstruction:
    """The model accepts well-formed input."""

    def test_minimal_required_fields(self):
        """date_range is the only required field; variables defaults to daily_rain."""
        query = GeoTiffDownloadQuery(
            date_range=SiloDateRange(start_date="2023-01-01", end_date="2023-01-31"),
        )
        assert query.variables == ["daily_rain"]
        assert query.date_range.start_date == "20230101"
        assert query.date_range.end_date == "20230131"
        assert query.output_dir is None
        assert query.force is False

    def test_full_construction(self):
        query = GeoTiffDownloadQuery(
            variables=["daily_rain", "max_temp"],
            date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
            output_dir=Path("/tmp/geotiff"),
            force=True,
        )
        assert query.variables == ["daily_rain", "max_temp"]
        assert query.output_dir == Path("/tmp/geotiff")
        assert query.force is True

    def test_iso_dates_normalised_to_yyyymmdd(self):
        query = GeoTiffDownloadQuery(
            variables=["daily_rain"],
            date_range=SiloDateRange(start_date="2023-06-15", end_date="2023-07-20"),
        )
        assert query.date_range.start_date == "20230615"
        assert query.date_range.end_date == "20230720"


class TestDateRangeValidation:
    """The model inherits SiloDateRange's 1889-2100 window."""

    def test_yyyymmdd_input_accepted(self):
        query = GeoTiffDownloadQuery(
            date_range=SiloDateRange(start_date="19000101", end_date="19001231"),
        )
        assert query.date_range.start_date == "19000101"

    def test_year_before_1889_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            GeoTiffDownloadQuery(
                date_range=SiloDateRange(start_date="1850-01-01", end_date="1851-01-01"),
            )
        assert "1889" in str(exc_info.value)

    def test_year_after_2100_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            GeoTiffDownloadQuery(
                date_range=SiloDateRange(start_date="2101-01-01", end_date="2101-02-01"),
            )
        assert "2100" in str(exc_info.value)

    def test_start_after_end_rejected(self):
        with pytest.raises(ValidationError):
            GeoTiffDownloadQuery(
                date_range=SiloDateRange(start_date="2023-06-01", end_date="2023-01-01"),
            )

    def test_malformed_date_rejected(self):
        with pytest.raises(ValidationError):
            GeoTiffDownloadQuery(
                date_range=SiloDateRange(start_date="2023/01/01", end_date="2023-01-31"),
            )


class TestVariableValidation:
    """Variable names must exist in the central registry."""

    def test_unknown_variable_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            GeoTiffDownloadQuery(
                variables=["not_a_real_variable"],
                date_range=SiloDateRange(start_date="2023-01-01", end_date="2023-01-31"),
            )
        msg = str(exc_info.value)
        assert "not_a_real_variable" in msg
        assert "Unknown variables" in msg

    def test_mix_of_valid_and_invalid_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            GeoTiffDownloadQuery(
                variables=["daily_rain", "bogus_var"],
                date_range=SiloDateRange(start_date="2023-01-01", end_date="2023-01-31"),
            )
        assert "bogus_var" in str(exc_info.value)

    def test_empty_variables_list_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            GeoTiffDownloadQuery(
                variables=[],
                date_range=SiloDateRange(start_date="2023-01-01", end_date="2023-01-31"),
            )
        assert "At least one variable" in str(exc_info.value)

    def test_known_variables_accepted(self):
        # Sanity-check a representative spread of registry entries.
        for name in ("daily_rain", "max_temp", "min_temp", "monthly_rain"):
            query = GeoTiffDownloadQuery(
                variables=[name],
                date_range=SiloDateRange(start_date="2023-01-01", end_date="2023-01-31"),
            )
            assert query.variables == [name]


class TestSpatialInputsNotOnModel:
    """bbox/geometry are CLI-only — they must not be accepted on the model."""

    def test_bbox_field_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            GeoTiffDownloadQuery(
                date_range=SiloDateRange(start_date="2023-01-01", end_date="2023-01-31"),
                bbox=[150.0, -28.0, 154.0, -26.0],  # type: ignore[call-arg]
            )
        assert "bbox" in str(exc_info.value).lower()

    def test_geometry_field_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            GeoTiffDownloadQuery(
                date_range=SiloDateRange(start_date="2023-01-01", end_date="2023-01-31"),
                geometry="some/path.geojson",  # type: ignore[call-arg]
            )
        assert "geometry" in str(exc_info.value).lower()

    def test_model_fields_are_exactly_the_expected_set(self):
        """Guard against accidental field drift that could re-open the CLI/model split."""
        assert set(GeoTiffDownloadQuery.model_fields.keys()) == {
            "variables",
            "date_range",
            "output_dir",
            "force",
        }
