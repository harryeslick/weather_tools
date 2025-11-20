"""
Tests for met.no to SILO variable mapping functions.

Tests variable conversions and format transformations.
"""

import datetime as dt

import pandas as pd
import pytest

from weather_tools.silo_variables import (
    METNO_TO_SILO_MAPPING,
    SILO_ONLY_VARIABLES,
    MetNoVariableMapping,
    add_silo_date_columns,
    convert_metno_to_silo_columns,
    get_silo_column_order,
    rh_to_vapor_pressure,
)


class TestMetNoVariableMapping:
    """Test MetNoVariableMapping model."""

    def test_simple_mapping_creation(self):
        """Test creating simple variable mapping."""
        mapping = MetNoVariableMapping(metno_name="min_temperature", silo_name="min_temp")

        assert mapping.metno_name == "min_temperature"
        assert mapping.silo_name == "min_temp"
        assert mapping.conversion_func is None
        assert mapping.requires_other_vars is None

    def test_mapping_with_conversion(self):
        """Test mapping with conversion function."""
        mapping = MetNoVariableMapping(
            metno_name="avg_relative_humidity",
            silo_name="vp",
            conversion_func="rh_to_vapor_pressure",
            requires_other_vars=["min_temperature", "max_temperature"],
        )

        assert mapping.conversion_func == "rh_to_vapor_pressure"
        assert len(mapping.requires_other_vars) == 2


class TestMetNoToSiloMappingRegistry:
    """Test mapping registry constants."""

    def test_mapping_registry_exists(self):
        """Test that mapping registry is defined."""
        assert METNO_TO_SILO_MAPPING is not None
        assert isinstance(METNO_TO_SILO_MAPPING, dict)

    def test_direct_temperature_mappings(self):
        """Test temperature variable mappings."""
        assert "min_temperature" in METNO_TO_SILO_MAPPING
        assert "max_temperature" in METNO_TO_SILO_MAPPING

        assert METNO_TO_SILO_MAPPING["min_temperature"].silo_name == "min_temp"
        assert METNO_TO_SILO_MAPPING["max_temperature"].silo_name == "max_temp"

    def test_direct_precipitation_mapping(self):
        """Test precipitation mapping."""
        assert "total_precipitation" in METNO_TO_SILO_MAPPING
        assert METNO_TO_SILO_MAPPING["total_precipitation"].silo_name == "daily_rain"

    def test_pressure_mapping(self):
        """Test pressure mapping."""
        assert "avg_pressure" in METNO_TO_SILO_MAPPING
        assert METNO_TO_SILO_MAPPING["avg_pressure"].silo_name == "mslp"

    def test_humidity_mapping_requires_conversion(self):
        """Test humidity mapping requires conversion."""
        assert "avg_relative_humidity" in METNO_TO_SILO_MAPPING
        mapping = METNO_TO_SILO_MAPPING["avg_relative_humidity"]

        assert mapping.silo_name == "vp"
        assert mapping.conversion_func == "rh_to_vapor_pressure"
        assert mapping.requires_other_vars is not None

    def test_metno_only_variables(self):
        """Test met.no-only variables."""
        assert "avg_wind_speed" in METNO_TO_SILO_MAPPING
        assert "max_wind_speed" in METNO_TO_SILO_MAPPING
        assert "avg_cloud_fraction" in METNO_TO_SILO_MAPPING

    def test_silo_only_variables_list(self):
        """Test SILO-only variables list."""
        assert isinstance(SILO_ONLY_VARIABLES, list)
        assert len(SILO_ONLY_VARIABLES) > 0

        # Check some known SILO-only variables
        assert "evap_pan" in SILO_ONLY_VARIABLES
        assert "evap_syn" in SILO_ONLY_VARIABLES
        assert "radiation" in SILO_ONLY_VARIABLES
        assert "et_short_crop" in SILO_ONLY_VARIABLES


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


class TestColumnConversion:
    """Test DataFrame column conversion."""

    def test_convert_basic_columns(self):
        """Test converting basic met.no columns."""
        df = pd.DataFrame(
            {
                "date": [dt.date(2023, 1, 1)],
                "min_temperature": [18.5],
                "max_temperature": [28.3],
                "total_precipitation": [5.2],
            }
        )

        mapping = convert_metno_to_silo_columns(df, include_extra=False)

        assert mapping["date"] == "date"
        assert mapping["min_temperature"] == "min_temp"
        assert mapping["max_temperature"] == "max_temp"
        assert mapping["total_precipitation"] == "daily_rain"

    def test_convert_with_extra_columns(self):
        """Test converting with met.no-only columns."""
        df = pd.DataFrame(
            {
                "date": [dt.date(2023, 1, 1)],
                "min_temperature": [18.5],
                "avg_wind_speed": [4.2],
                "avg_cloud_fraction": [60.0],
            }
        )

        mapping = convert_metno_to_silo_columns(df, include_extra=True)

        assert "avg_wind_speed" in mapping
        assert mapping["avg_wind_speed"] == "wind_speed"
        assert "avg_cloud_fraction" in mapping
        assert mapping["avg_cloud_fraction"] == "cloud_fraction"

    def test_convert_exclude_extra_columns(self):
        """Test excluding met.no-only columns."""
        df = pd.DataFrame(
            {"date": [dt.date(2023, 1, 1)], "min_temperature": [18.5], "avg_wind_speed": [4.2]}
        )

        mapping = convert_metno_to_silo_columns(df, include_extra=False)

        assert "avg_wind_speed" not in mapping
        assert "min_temperature" in mapping


class TestSiloColumnOrder:
    """Test SILO column ordering."""

    def test_get_silo_column_order(self):
        """Test getting standard SILO column order."""
        columns = get_silo_column_order()

        assert isinstance(columns, list)
        assert len(columns) > 0

        # Check specific order
        assert columns[0] == "date"
        assert columns[1] == "day"
        assert columns[2] == "year"

        # Check key variables present
        assert "daily_rain" in columns
        assert "max_temp" in columns
        assert "min_temp" in columns
        assert "mslp" in columns

    def test_silo_column_order_unique(self):
        """Test that column order has no duplicates."""
        columns = get_silo_column_order()

        assert len(columns) == len(set(columns))


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
    """Test integrated conversion workflow."""

    def test_full_metno_to_silo_conversion(self):
        """Test complete conversion from met.no to SILO format."""
        # Create met.no daily summary DataFrame
        metno_df = pd.DataFrame(
            {
                "date": [dt.date(2023, 1, 15), dt.date(2023, 1, 16)],
                "min_temperature": [18.5, 19.0],
                "max_temperature": [28.3, 29.5],
                "total_precipitation": [5.2, 0.0],
                "avg_pressure": [1013.2, 1012.5],
            }
        )

        # Get column mapping
        mapping = convert_metno_to_silo_columns(metno_df, include_extra=False)

        # Rename columns
        silo_df = metno_df.rename(columns=mapping)

        # Add SILO date columns
        silo_df = add_silo_date_columns(silo_df)

        # Verify SILO format
        assert "date" in silo_df.columns
        assert "day" in silo_df.columns
        assert "year" in silo_df.columns
        assert "min_temp" in silo_df.columns
        assert "max_temp" in silo_df.columns
        assert "daily_rain" in silo_df.columns
        assert "mslp" in silo_df.columns

        # Verify values preserved
        assert silo_df["min_temp"].iloc[0] == 18.5
        assert silo_df["max_temp"].iloc[0] == 28.3
        assert silo_df["daily_rain"].iloc[0] == 5.2
