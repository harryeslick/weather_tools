"""Unit tests for weather_utils.dew_point.rh_to_vapor_pressure.

Known-value tests derived from the August-Roche-Magnus formula:
    es = 6.1094 * exp(17.625 * T / (T + 243.04))   [saturation vapour pressure, hPa]
    e  = (RH / 100) * es                             [actual vapour pressure, hPa]
"""

import math

import pytest

from weather_tools.weather_utils.dew_point import rh_to_vapor_pressure


class TestRhToVaporPressure:
    """Tests for rh_to_vapor_pressure using values computed from the formula directly."""

    def test_saturated_air_at_20c(self):
        """At 100% RH the result equals saturation vapour pressure (es ≈ 23.33 hPa at 20°C)."""
        result = rh_to_vapor_pressure(relative_humidity=100.0, temperature=20.0)
        expected = 6.1094 * math.exp((17.625 * 20.0) / (20.0 + 243.04))
        assert result == pytest.approx(expected, rel=1e-6)
        assert result == pytest.approx(23.3344, abs=0.001)

    def test_60_percent_rh_at_25c(self):
        """Standard mid-range case: RH=60%, T=25°C → e ≈ 18.97 hPa."""
        result = rh_to_vapor_pressure(relative_humidity=60.0, temperature=25.0)
        assert result == pytest.approx(18.9704, abs=0.001)

    def test_50_percent_rh_at_zero_celsius(self):
        """At 0°C saturation VP is the base constant (6.1094 hPa); half gives ~3.05 hPa."""
        result = rh_to_vapor_pressure(relative_humidity=50.0, temperature=0.0)
        assert result == pytest.approx(3.0547, abs=0.001)

    def test_80_percent_rh_at_15c(self):
        """Typical warm-season morning: RH=80%, T=15°C → e ≈ 13.62 hPa."""
        result = rh_to_vapor_pressure(relative_humidity=80.0, temperature=15.0)
        assert result == pytest.approx(13.6159, abs=0.001)

    def test_zero_rh_returns_zero(self):
        """0% relative humidity means no water vapour — result must be 0."""
        result = rh_to_vapor_pressure(relative_humidity=0.0, temperature=25.0)
        assert result == pytest.approx(0.0, abs=1e-10)

    def test_returns_float(self):
        """Return type should be float."""
        result = rh_to_vapor_pressure(relative_humidity=75.0, temperature=22.0)
        assert isinstance(result, float)

    def test_higher_temperature_gives_higher_vp(self):
        """Vapour pressure increases monotonically with temperature at fixed RH."""
        vp_low = rh_to_vapor_pressure(relative_humidity=70.0, temperature=10.0)
        vp_high = rh_to_vapor_pressure(relative_humidity=70.0, temperature=30.0)
        assert vp_high > vp_low
