"""Unit tests for the generic DateRange base model."""

import pytest
from pydantic import ValidationError

from weather_tools.date_range import DateRange


class TestDateRangeBase:
    """DateRange validates format and ordering without imposing year bounds."""

    def test_iso_input_normalised(self):
        dr = DateRange(start_date="2023-01-01", end_date="2023-12-31")
        assert dr.start_date == "20230101"
        assert dr.end_date == "20231231"

    def test_yyyymmdd_input_unchanged(self):
        dr = DateRange(start_date="20230101", end_date="20231231")
        assert dr.start_date == "20230101"
        assert dr.end_date == "20231231"

    def test_no_year_bounds_on_base(self):
        """The base must not reject far-past or far-future years.

        Year bounds are a dataset-specific concern (e.g. SILO begins 1889) and
        belong on subclasses like ``SiloDateRange``. A forecast model with
        dates well beyond 2100 should work against this base.
        """
        # A century before SILO and far beyond its upper bound: both fine here.
        dr = DateRange(start_date="1700-06-15", end_date="2500-06-15")
        assert dr.start_date == "17000615"
        assert dr.end_date == "25000615"

    def test_invalid_month_rejected(self):
        with pytest.raises(ValidationError):
            DateRange(start_date="2023-13-01", end_date="2023-12-31")

    def test_malformed_string_rejected(self):
        with pytest.raises(ValidationError):
            DateRange(start_date="2023/01/01", end_date="20230131")

    def test_start_after_end_rejected(self):
        with pytest.raises(ValidationError):
            DateRange(start_date="2023-12-31", end_date="2023-01-01")

    def test_equal_dates_allowed(self):
        """A single-day range is valid."""
        dr = DateRange(start_date="2023-06-15", end_date="2023-06-15")
        assert dr.start_date == dr.end_date == "20230615"


class TestSiloDateRangeYearBounds:
    """Verify SiloDateRange still rejects years outside SILO's 1889-2100 window."""

    def test_year_below_1889_rejected(self):
        from weather_tools.silo_models import SiloDateRange

        with pytest.raises(ValidationError, match="between 1889 and 2100"):
            SiloDateRange(start_date="1800-01-01", end_date="2023-12-31")

    def test_year_above_2100_rejected(self):
        from weather_tools.silo_models import SiloDateRange

        with pytest.raises(ValidationError, match="between 1889 and 2100"):
            SiloDateRange(start_date="2023-01-01", end_date="2200-12-31")

    def test_silo_date_range_inherits_iso_normalisation(self):
        """SiloDateRange must keep the ISO acceptance from its base."""
        from weather_tools.silo_models import SiloDateRange

        dr = SiloDateRange(start_date="2023-01-01", end_date="2023-12-31")
        assert dr.start_date == "20230101"
