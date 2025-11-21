"""Tests for silo_variables module.

These tests document how to use the variable registry and preset system.
"""

import pytest

from weather_tools.silo_variables import (
    SILO_VARIABLES,
    VARIABLE_PRESETS,
    VARIABLES,
)


class TestVariableMetadata:
    """Test variable metadata lookups."""

    def test_lookup_by_silo_code(self):
        """Test looking up variable metadata using SILO API code (e.g., 'R')."""
        # Rainfall has SILO code 'R'
        meta = VARIABLES.get_by_any("R")

        assert meta is not None
        assert meta.silo_code == "R"
        assert meta.netcdf_name == "daily_rain"
        assert meta.full_name == "Daily rainfall"
        assert meta.units == "mm"

    def test_lookup_by_canonical_name(self):
        """Test looking up variable metadata using canonical name (e.g., 'max_temp')."""
        # Max temperature has canonical name 'max_temp'
        meta = VARIABLES.get_by_any("max_temp")

        assert meta is not None
        assert meta.silo_code == "X"
        assert meta.netcdf_name == "max_temp"
        assert meta.full_name == "Maximum temperature"
        assert meta.units == "°C"

    def test_lookup_invalid_variable(self):
        """Test that invalid variable names return None."""
        meta = VARIABLES.get_by_any("invalid_var")
        assert meta is None

    def test_monthly_rain_has_no_silo_code(self):
        """Test that monthly_rain has no SILO API code."""
        meta = VARIABLES.get_by_any("monthly_rain")
        assert meta is not None
        assert meta.silo_code is None


class TestSiloRegistry:
    """Test the SILO registry class."""

    def test_registry_getitem(self):
        """Test dict-like access to registry."""
        meta = VARIABLES["daily_rain"]
        assert meta.silo_code == "R"
        assert meta.units == "mm"

    def test_registry_contains(self):
        """Test 'in' operator on registry."""
        assert "daily_rain" in VARIABLES
        assert "max_temp" in VARIABLES
        assert "invalid_var" not in VARIABLES

    def test_registry_keys(self):
        """Test keys() returns canonical variable names."""
        keys = list(VARIABLES.keys())
        assert "daily_rain" in keys
        assert "max_temp" in keys
        assert "min_temp" in keys

    def test_silo_code_from_name(self):
        """Test converting canonical name to SILO code."""
        assert VARIABLES.silo_code_from_name("daily_rain") == "R"
        assert VARIABLES.silo_code_from_name("max_temp") == "X"
        assert VARIABLES.silo_code_from_name("monthly_rain") is None

    def test_name_from_silo_code(self):
        """Test converting SILO code to canonical name."""
        assert VARIABLES.name_from_silo_code("R") == "daily_rain"
        assert VARIABLES.name_from_silo_code("X") == "max_temp"

    def test_get_by_any(self):
        """Test lookup by any identifier."""
        # By canonical name
        meta = VARIABLES.get_by_any("daily_rain")
        assert meta is not None
        assert meta.silo_code == "R"

        # By SILO code
        meta = VARIABLES.get_by_any("R")
        assert meta is not None
        assert meta.netcdf_name == "daily_rain"

        # Invalid
        meta = VARIABLES.get_by_any("invalid")
        assert meta is None


class TestPresetExpansion:
    """Test variable preset expansion."""

    def test_expand_daily_preset(self):
        """Test that 'daily' preset expands to the four daily variables."""
        variables = VARIABLES.expand_preset("daily")

        assert variables == ["daily_rain", "max_temp", "min_temp", "evap_syn"]

    def test_expand_monthly_preset(self):
        """Test that 'monthly' preset expands to monthly rainfall."""
        variables = VARIABLES.expand_preset("monthly")

        assert variables == ["monthly_rain"]

    def test_expand_temperature_preset(self):
        """Test that 'temperature' preset expands to min and max temp."""
        variables = VARIABLES.expand_preset("temperature")

        assert variables == ["max_temp", "min_temp"]

    def test_expand_evaporation_preset(self):
        """Test that 'evaporation' preset expands to evaporation variables."""
        variables = VARIABLES.expand_preset("evaporation")

        assert "evap_pan" in variables
        assert "evap_syn" in variables
        assert "evap_comb" in variables

    def test_expand_single_variable_string(self):
        """Test that a single variable name is wrapped in a list."""
        variables = VARIABLES.expand_preset("daily_rain")

        assert variables == ["daily_rain"]

    def test_expand_list_of_variables(self):
        """Test that a list of variables is returned as-is."""
        input_vars = ["daily_rain", "max_temp"]
        variables = VARIABLES.expand_preset(input_vars)

        assert variables == ["daily_rain", "max_temp"]

    def test_expand_list_with_presets(self):
        """Test that presets within a list are expanded."""
        # Mix of preset and explicit variable
        input_vars = ["temperature", "daily_rain"]
        variables = VARIABLES.expand_preset(input_vars)

        # Should expand 'temperature' to ['max_temp', 'min_temp']
        assert "max_temp" in variables
        assert "min_temp" in variables
        assert "daily_rain" in variables

    def test_registry_validate(self):
        """Test variable validation via SILO registry."""
        metadata_map = VARIABLES.validate("daily")
        assert "daily_rain" in metadata_map
        assert metadata_map["daily_rain"].silo_code == "R"

        # Invalid variable should raise
        with pytest.raises(ValueError, match="Unknown variable"):
            VARIABLES.validate(["invalid_var"])


class TestVariableRegistry:
    """Test the complete variable registry."""

    def test_all_variables_have_required_fields(self):
        """Test that all variables have the required metadata fields."""
        for key, meta in SILO_VARIABLES.items():
            # Every variable must have these fields
            assert meta.full_name is not None
            assert meta.units is not None

            # Canonical name should match dict key
            assert key == meta.netcdf_name or meta.netcdf_name is None

    def test_all_presets_have_valid_variables(self):
        """Test that all preset groups contain valid variable names."""
        for preset_name, var_list in VARIABLE_PRESETS.items():
            for var in var_list:
                # Each variable in a preset should be resolvable
                meta = VARIABLES.get_by_any(var)
                assert meta is not None, f"Invalid variable '{var}' in preset '{preset_name}'"

    def test_expected_variable_count(self):
        """Test that we have the expected number of variables registered."""
        # SILO has 19 climate variables (18 with API codes + monthly_rain)
        assert len(SILO_VARIABLES) >= 18
