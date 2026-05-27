"""
Tests for met.no to SILO variable mapping functions.

Tests variable conversions and format transformations.
"""

import datetime as dt

import pandas as pd
import pytest

from weather_tools.cli.metno import add_silo_date_columns
from weather_tools.variable_register import VARIABLES
from weather_tools.weather_utils.dew_point import rh_to_vapor_pressure


class TestVariableRegistryMetnoMappings:
    """Test the met.no daily aggregation spec in the unified VariableRegistry.

    The registry is the single source of truth: each canonical variable records
    the raw met.no field it comes from and how that field is aggregated daily.
    """

    def test_temperature_agg_spec(self):
        """air_temperature feeds both max_temp (max) and min_temp (min)."""
        spec = VARIABLES.metno_daily_agg_spec()
        assert spec["max_temp"] == ("air_temperature", "max")
        assert spec["min_temp"] == ("air_temperature", "min")

    def test_precipitation_agg_spec(self):
        """precipitation_amount is summed into daily_rain."""
        assert VARIABLES.metno_daily_agg_spec()["daily_rain"] == (
            "precipitation_amount",
            "sum",
        )

    def test_pressure_agg_spec(self):
        """air_pressure_at_sea_level is averaged into mslp."""
        assert VARIABLES.metno_daily_agg_spec()["mslp"] == (
            "air_pressure_at_sea_level",
            "mean",
        )

    def test_humidity_agg_spec(self):
        """relative_humidity maps to a canonical relative_humidity column (mean)."""
        spec = VARIABLES.metno_daily_agg_spec()
        assert spec["relative_humidity"] == ("relative_humidity", "mean")
        # vp is *derived* in merge, not mapped directly from met.no.
        assert VARIABLES["vp"].metno_name is None
        assert VARIABLES["vp"].units == "hPa"

    def test_metno_only_agg_spec(self):
        """met.no-only variables share raw fields and carry an aggregation."""
        spec = VARIABLES.metno_daily_agg_spec()
        assert spec["wind_speed"] == ("wind_speed", "mean")
        assert spec["wind_speed_max"] == ("wind_speed", "max")
        assert spec["cloud_fraction"] == ("cloud_area_fraction", "mean")
        assert spec["weather_symbol"] == ("symbol_code", "dominant")

    def test_metno_only_flag(self):
        """Test metno_only flag on variables."""
        assert VARIABLES["wind_speed"].metno_only is True
        assert VARIABLES["wind_speed_max"].metno_only is True
        assert VARIABLES["cloud_fraction"].metno_only is True
        assert VARIABLES["weather_symbol"].metno_only is True

        # SILO variables should not have metno_only flag
        assert VARIABLES["daily_rain"].metno_only is False
        assert VARIABLES["max_temp"].metno_only is False

    def test_metno_only_variables_method(self):
        """Test metno_only_variables method."""
        metno_only = VARIABLES.metno_only_variables()
        assert "wind_speed" in metno_only
        assert "wind_speed_max" in metno_only
        assert "cloud_fraction" in metno_only
        assert "weather_symbol" in metno_only

        # SILO variables should not be in this list
        assert "daily_rain" not in metno_only
        assert "max_temp" not in metno_only

    def test_silo_variables_method(self):
        """Test silo_variables method."""
        silo_vars = VARIABLES.silo_variables()
        assert "daily_rain" in silo_vars
        assert "max_temp" in silo_vars

        # Met.no-only should not be in this list
        assert "wind_speed" not in silo_vars


class TestRelativeHumidityConversion:
    """Test relative humidity to vapor pressure conversion."""

    def test_rh_to_vp_at_20c(self):
        """Test conversion at 20°C."""
        # At 20°C, saturation VP ~23.4 hPa
        # At 50% RH, VP should be ~11.7 hPa
        vp = rh_to_vapor_pressure(50.0, 20.0)

        assert vp == pytest.approx(11.7, abs=0.5)

    def test_rh_to_vp_at_25c(self):
        """Test conversion at 25°C."""
        # At 25°C, saturation VP ~31.7 hPa
        # At 70% RH, VP should be ~22.2 hPa
        vp = rh_to_vapor_pressure(70.0, 25.0)

        assert vp == pytest.approx(22.2, abs=0.5)

    def test_rh_to_vp_at_100_percent(self):
        """Test conversion at 100% RH (saturation)."""
        vp = rh_to_vapor_pressure(100.0, 20.0)

        # Should equal saturation vapor pressure
        assert vp == pytest.approx(23.4, abs=0.5)

    def test_rh_to_vp_at_0_percent(self):
        """Test conversion at 0% RH (dry)."""
        vp = rh_to_vapor_pressure(0.0, 20.0)

        assert vp == 0.0

    def test_rh_to_vp_negative_temperature(self):
        """Test conversion at negative temperature."""
        # Should still work (Australian winter conditions)
        vp = rh_to_vapor_pressure(80.0, -5.0)

        assert vp >= 0.0
        assert vp < 10.0  # Should be low at negative temps


class TestAddSiloDateColumns:
    """Test adding SILO date columns."""

    def test_add_date_columns(self):
        """Test adding day and year columns."""
        df = pd.DataFrame(
            {"date": [dt.date(2023, 1, 15), dt.date(2023, 6, 30)], "min_temp": [18.5, 12.0]}
        )

        result = add_silo_date_columns(df)

        assert "day" in result.columns
        assert "year" in result.columns
        assert result["day"].iloc[0] == 15  # 15th day of year
        assert result["year"].iloc[0] == 2023
        assert result["day"].iloc[1] == 181  # 181st day of year (June 30)

    def test_add_date_columns_preserves_data(self):
        """Test that adding date columns doesn't modify original data."""
        df = pd.DataFrame({"date": [dt.date(2023, 1, 15)], "min_temp": [18.5], "max_temp": [28.3]})

        result = add_silo_date_columns(df)

        assert "min_temp" in result.columns
        assert "max_temp" in result.columns
        assert result["min_temp"].iloc[0] == 18.5
        assert result["max_temp"].iloc[0] == 28.3

    def test_add_date_columns_handles_string_dates(self):
        """Test conversion of string dates."""
        df = pd.DataFrame({"date": ["2023-01-15", "2023-12-31"], "min_temp": [18.5, 20.0]})

        result = add_silo_date_columns(df)

        assert "day" in result.columns
        assert "year" in result.columns
        assert result["year"].iloc[0] == 2023
        assert result["day"].iloc[1] == 365  # Last day of year

    def test_add_date_columns_no_date_column(self):
        """Test behavior when date column is missing."""
        df = pd.DataFrame({"min_temp": [18.5], "max_temp": [28.3]})

        result = add_silo_date_columns(df)

        # Should return copy without date columns
        assert "day" not in result.columns
        assert "year" not in result.columns


class TestIntegratedConversion:
    """Test the integrated daily-aggregation workflow.

    Daily aggregation now emits canonical SILO names directly (driven by the
    registry), so there is no separate rename step.
    """

    def test_raw_hourly_aggregates_to_canonical_daily(self):
        """Raw met.no fields aggregate straight to canonical SILO columns."""
        from weather_tools.metno_api import MetNoAPI

        api = MetNoAPI(enable_cache=False)
        times = pd.to_datetime(
            [dt.datetime(2023, 1, 15, h, tzinfo=dt.timezone.utc) for h in range(0, 24, 6)]
            + [dt.datetime(2023, 1, 16, h, tzinfo=dt.timezone.utc) for h in range(0, 24, 6)]
        )
        raw = pd.DataFrame(
            {
                "time": times,
                "air_temperature": [18.5, 28.3, 24.0, 20.0, 19.0, 29.5, 25.0, 21.0],
                "precipitation_amount": [0.0, 2.1, 3.1, 0.0, 0.0, 0.0, 0.0, 0.0],
                "air_pressure_at_sea_level": [1013.2] * 4 + [1012.5] * 4,
            }
        )

        daily = api._aggregate_daily(raw)
        daily = add_silo_date_columns(daily)

        # Canonical SILO names appear directly — no intermediate vocabulary.
        for col in ("date", "day", "year", "min_temp", "max_temp", "daily_rain", "mslp"):
            assert col in daily.columns
        assert daily["max_temp"].iloc[0] == 28.3
        assert daily["min_temp"].iloc[0] == 18.5
        assert daily["daily_rain"].iloc[0] == pytest.approx(5.2)
