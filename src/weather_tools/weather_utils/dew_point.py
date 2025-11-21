"""
function under active development and untested. 
USE WITH CAUTION
"""

import math

import numpy as np


def dewpoint_from_vp(vp_hpa):
    """
    Calculate daily mean dew-point temperature from actual vapour pressure.

    Parameters
    ----------
    vp_hpa : float or array-like
        Actual vapour pressure in hectopascals (hPa). 
        This is typically the daily mean vapour pressure computed
        from humidity measurements.

    Returns
    -------
    float or ndarray
        Dew-point temperature in degrees Celsius.

    Notes
    -----
    This function inverts the Tetens equation for saturation vapour pressure,
    assuming the standard constants:
        a = 17.27
        b = 237.7 °C
    The derivation uses:

        alpha = ln(e / 6.1078)

        Td = (b * alpha) / (a - alpha)

    where:
        e = actual vapour pressure (hPa)
        Td = dew-point temperature (°C)

    The constant 6.1078 hPa is the saturation vapour pressure at 0°C.
    """
    a, b = 17.27, 237.7
    alpha = np.log(np.asarray(vp_hpa) / 6.1078)
    return (b * alpha) / (a - alpha)


def dewpoint_from_T_RH(T_degC, RH_pct):
    """
    Calculate dew-point temperature from air temperature and relative humidity.

    Parameters
    ----------
    T_degC : float or array-like
        Air temperature in degrees Celsius.
    RH_pct : float or array-like
        Relative humidity in percent (0–100).

    Returns
    -------
    float or ndarray
        Dew-point temperature in degrees Celsius.

    Notes
    -----
    Computes dew point using the Magnus–Tetens approximation:

        gamma = ln(RH/100) + a*T / (b + T)

        Td = b * gamma / (a - gamma)

    where:
        T = air temperature (°C)
        RH = relative humidity (%)
        Td = dew-point temperature (°C)

    Constants used:
        a = 17.27
        b = 237.7 °C

    This formulation is widely used in ag-meteorology and is suitable
    for typical field temperature ranges in Australian grain systems.
    """
    a, b = 17.27, 237.7
    T = np.asarray(T_degC)
    RH = np.asarray(RH_pct)

    gamma = np.log(RH / 100.0) + (a * T) / (b + T)
    return (b * gamma) / (a - gamma)


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
    import math

    # Saturation vapor pressure (hPa)
    es = 6.1094 * math.exp((17.625 * temperature) / (temperature + 243.04))

    # Actual vapor pressure (hPa)
    e = (relative_humidity / 100.0) * es

    return e