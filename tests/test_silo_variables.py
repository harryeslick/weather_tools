"""Tests for silo_variables module.

These tests document how to use the variable registry and preset system.
"""

import pytest

from weather_tools.silo_variables import (
    API_TO_NETCDF,
    NETCDF_TO_API,
    SILO_VARIABLES,
    VARIABLE_PRESETS,
    expand_variable_preset,
    get_variable_metadata,
)


class TestVariableMetadata:
    """Test variable metadata lookups."""

    def test_lookup_by_api_code(self):
        """Test looking up variable metadata using API code (e.g., 'R')."""
        # Rainfall has API code 'R'
        meta = get_variable_metadata("R")

        assert meta is not None
        assert meta.api_code == "R"
        assert meta.netcdf_name == "daily_rain"
        assert meta.full_name == "Daily rainfall"
        assert meta.units == "mm"
        assert meta.start_year == 1889

    def test_lookup_by_netcdf_name(self):
        """Test looking up variable metadata using NetCDF name (e.g., 'max_temp')."""
        # Max temperature has NetCDF name 'max_temp'
        meta = get_variable_metadata("max_temp")

        assert meta is not None
        assert meta.api_code == "X"
        assert meta.netcdf_name == "max_temp"
        assert meta.full_name == "Maximum temperature"
        assert meta.units == "°C"

    def test_lookup_invalid_variable(self):
        """Test that invalid variable names return None."""
        meta = get_variable_metadata("invalid_var")
        assert meta is None

    def test_variable_with_different_start_year(self):
        """Test that some variables have different start years."""
        # Most variables start in 1889
        rain_meta = get_variable_metadata("daily_rain")
        assert rain_meta.start_year == 1889

        # MSLP starts later
        mslp_meta = get_variable_metadata("mslp")
        assert mslp_meta.start_year == 1957

        # Pan evaporation starts even later
        pan_meta = get_variable_metadata("evap_pan")
        assert pan_meta.start_year == 1970


class TestReverseMappings:
    """Test the convenience mapping dictionaries."""

    def test_api_to_netcdf_mapping(self):
        """Test converting API codes to NetCDF names."""
        assert API_TO_NETCDF["R"] == "daily_rain"
        assert API_TO_NETCDF["X"] == "max_temp"
        assert API_TO_NETCDF["N"] == "min_temp"
        assert API_TO_NETCDF["S"] == "evap_syn"

    def test_netcdf_to_api_mapping(self):
        """Test converting NetCDF names to API codes."""
        assert NETCDF_TO_API["daily_rain"] == "R"
        assert NETCDF_TO_API["max_temp"] == "X"
        assert NETCDF_TO_API["min_temp"] == "N"

        # Monthly rain has no API code
        assert NETCDF_TO_API["monthly_rain"] is None


class TestPresetExpansion:
    """Test variable preset expansion."""

    def test_expand_daily_preset(self):
        """Test that 'daily' preset expands to the four daily variables."""
        variables = expand_variable_preset("daily")

        assert variables == ["daily_rain", "max_temp", "min_temp", "evap_syn"]

    def test_expand_monthly_preset(self):
        """Test that 'monthly' preset expands to monthly rainfall."""
        variables = expand_variable_preset("monthly")

        assert variables == ["monthly_rain"]

    def test_expand_temperature_preset(self):
        """Test that 'temperature' preset expands to min and max temp."""
        variables = expand_variable_preset("temperature")

        assert variables == ["max_temp", "min_temp"]

    def test_expand_evaporation_preset(self):
        """Test that 'evaporation' preset expands to evaporation variables."""
        variables = expand_variable_preset("evaporation")

        assert "evap_pan" in variables
        assert "evap_syn" in variables
        assert "evap_comb" in variables

    def test_expand_single_variable_string(self):
        """Test that a single variable name is wrapped in a list."""
        variables = expand_variable_preset("daily_rain")

        assert variables == ["daily_rain"]

    def test_expand_list_of_variables(self):
        """Test that a list of variables is returned as-is."""
        input_vars = ["daily_rain", "max_temp"]
        variables = expand_variable_preset(input_vars)

        assert variables == ["daily_rain", "max_temp"]

    def test_expand_list_with_presets(self):
        """Test that presets within a list are expanded."""
        # Mix of preset and explicit variable
        input_vars = ["temperature", "daily_rain"]
        variables = expand_variable_preset(input_vars)

        # Should expand 'temperature' to ['max_temp', 'min_temp']
        assert "max_temp" in variables
        assert "min_temp" in variables
        assert "daily_rain" in variables


class TestVariableRegistry:
    """Test the complete variable registry."""

    def test_all_variables_have_required_fields(self):
        """Test that all variables have the required metadata fields."""
        for key, meta in SILO_VARIABLES.items():
            # Every variable must have these fields
            assert meta.netcdf_name is not None
            assert meta.full_name is not None
            assert meta.units is not None
            assert meta.start_year >= 1889

            # api_code is optional (monthly_rain doesn't have one)
            # description is optional

    def test_all_presets_have_valid_variables(self):
        """Test that all preset groups contain valid variable names."""
        for preset_name, var_list in VARIABLE_PRESETS.items():
            for var in var_list:
                # Each variable in a preset should be resolvable
                meta = get_variable_metadata(var)
                assert meta is not None, f"Invalid variable '{var}' in preset '{preset_name}'"

    def test_expected_variable_count(self):
        """Test that we have the expected number of variables registered."""
        # SILO has 19 climate variables (18 with API codes + monthly_rain)
        assert len(SILO_VARIABLES) >= 18
