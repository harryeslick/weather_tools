"""Dew-point and vapour-pressure utility functions."""

import math


def rh_to_vapor_pressure(relative_humidity: float, temperature: float) -> float:
    """
    Convert relative humidity to vapor pressure using August-Roche-Magnus approximation.

    Args:
        relative_humidity: Relative humidity (%)
        temperature: Air temperature (°C)

    Returns:
        Vapor pressure (hPa)

    Formula:
        es = 6.1094 * exp(17.625 * T / (T + 243.04))  [saturation vapor pressure]
        e = (RH / 100) * es                            [actual vapor pressure]
    """
    # Saturation vapor pressure (hPa)
    es = 6.1094 * math.exp((17.625 * temperature) / (temperature + 243.04))

    # Actual vapor pressure (hPa)
    e = (relative_humidity / 100.0) * es

    return e
