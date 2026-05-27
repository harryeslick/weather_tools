"""Tests for silo_variables module.

These tests document how to use the variable registry. Variables must be
specified explicitly by canonical name; there are no presets.
"""

import pytest

from weather_tools.variable_register import (
    SILO_VARIABLES,
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


class TestVariableValidation:
    """Test variable validation and normalisation (no presets)."""

    def test_validate_single_variable_string(self):
        """Test that a single variable name is accepted and validated."""
        metadata_map = VARIABLES.validate("daily_rain")

        assert list(metadata_map.keys()) == ["daily_rain"]
        assert metadata_map["daily_rain"].silo_code == "R"

    def test_validate_list_of_variables(self):
        """Test that a list of variables is validated and preserved in order."""
        metadata_map = VARIABLES.validate(["daily_rain", "max_temp"])

        assert list(metadata_map.keys()) == ["daily_rain", "max_temp"]
        assert metadata_map["max_temp"].silo_code == "X"

    def test_validate_unknown_variable_raises(self):
        """Test that an unknown variable raises the configured error class."""
        with pytest.raises(ValueError, match="Unknown variable"):
            VARIABLES.validate(["invalid_var"])

    def test_former_preset_name_is_not_a_variable(self):
        """Test that old preset names like 'daily' are no longer accepted."""
        with pytest.raises(ValueError, match="Unknown variable"):
            VARIABLES.validate("daily")


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

    def test_expected_variable_count(self):
        """Test that we have the expected number of variables registered."""
        # SILO has 19 climate variables (18 with API codes + monthly_rain)
        assert len(SILO_VARIABLES) >= 18
