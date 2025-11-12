"""
Central registry for SILO climate variables.

Maps between:
- API single-letter codes (used in PatchedPoint/DataDrill queries)
- NetCDF filenames (used for gridded data downloads)
- Full variable names and metadata
- SILO dataframe column names
"""

from typing import List, Literal, Optional, Union

from pydantic import BaseModel

# ===========================
# Exception Hierarchy
# ===========================

class SiloDataError(Exception):
    """Base exception for SILO data operations."""
    pass


class SiloNetCDFError(SiloDataError):
    """NetCDF-specific errors."""
    pass


class SiloGeoTiffError(SiloDataError):
    """GeoTIFF-specific errors."""
    pass


# ===========================
# Constants
# ===========================

# AWS S3 base URL for SILO data
SILO_S3_BASE_URL = "https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official"
SILO_NETCDF_BASE_URL = f"{SILO_S3_BASE_URL}/annual"
SILO_GEOTIFF_BASE_URL = SILO_S3_BASE_URL  # daily/monthly added in construct functions

# Default timeouts for downloads
DEFAULT_NETCDF_TIMEOUT = 600  # Large files (400MB+)
DEFAULT_GEOTIFF_TIMEOUT = 300  # Smaller files or COG streaming


# ===========================
# Variable Metadata
# ===========================

class VariableMetadata(BaseModel):
    """Metadata for a SILO climate variable."""
    api_code: Optional[str]  # Single letter code for API (None for monthly_rain)
    netcdf_name: str  # Filename used in NetCDF downloads
    full_name: str  # Human-readable name
    units: str  # Units of measurement
    start_year: int = 1889  # First available year (default 1889)
    description: Optional[str] = None


# Complete mapping of all SILO variables
SILO_VARIABLES = {
    # Rainfall
    "R": VariableMetadata(api_code="R", netcdf_name="daily_rain", full_name="Daily rainfall", units="mm"),
    # "monthly_rain": VariableMetadata(
    #     api_code=None,
    #     netcdf_name="monthly_rain",
    #     full_name="Monthly rainfall",
    #     units="mm"
    # ),
    # Temperature
    "X": VariableMetadata(api_code="X", netcdf_name="max_temp", full_name="Maximum temperature", units="°C"),
    "N": VariableMetadata(api_code="N", netcdf_name="min_temp", full_name="Minimum temperature", units="°C"),
    # Humidity and Pressure
    "V": VariableMetadata(api_code="V", netcdf_name="vp", full_name="Vapour pressure", units="hPa"),
    "D": VariableMetadata(api_code="D", netcdf_name="vp_deficit", full_name="Vapour pressure deficit", units="hPa"),
    "H": VariableMetadata(
        api_code="H", netcdf_name="rh_tmax", full_name="Relative humidity at time of maximum temperature", units="%"
    ),
    "G": VariableMetadata(
        api_code="G", netcdf_name="rh_tmin", full_name="Relative humidity at time of minimum temperature", units="%"
    ),
    "M": VariableMetadata(
        api_code="M", netcdf_name="mslp", full_name="Mean sea level pressure", units="hPa", start_year=1957
    ),
    # Evaporation
    "E": VariableMetadata(
        api_code="E", netcdf_name="evap_pan", full_name="Class A pan evaporation", units="mm", start_year=1970
    ),
    "S": VariableMetadata(api_code="S", netcdf_name="evap_syn", full_name="Synthetic estimate evaporation", units="mm"),
    "C": VariableMetadata(api_code="C", netcdf_name="evap_comb", full_name="Combination evaporation", units="mm"),
    "L": VariableMetadata(
        api_code="L", netcdf_name="evap_morton_lake", full_name="Morton's shallow lake evaporation", units="mm"
    ),
    # Radiation
    "J": VariableMetadata(
        api_code="J", netcdf_name="radiation", full_name="Solar exposure (direct and diffuse)", units="MJ/m²"
    ),
    # Evapotranspiration
    "F": VariableMetadata(
        api_code="F", netcdf_name="et_short_crop", full_name="FAO56 short crop evapotranspiration", units="mm"
    ),
    "T": VariableMetadata(
        api_code="T", netcdf_name="et_tall_crop", full_name="ASCE tall crop evapotranspiration", units="mm"
    ),
    "A": VariableMetadata(
        api_code="A", netcdf_name="et_morton_actual", full_name="Morton's areal actual evapotranspiration", units="mm"
    ),
    "P": VariableMetadata(
        api_code="P",
        netcdf_name="et_morton_potential",
        full_name="Morton's point potential evapotranspiration",
        units="mm",
    ),
    "W": VariableMetadata(
        api_code="W",
        netcdf_name="et_morton_wet",
        full_name="Morton's wet-environment areal potential evapotranspiration",
        units="mm",
    ),
}

# Reverse mappings for convenience
NETCDF_TO_API = {v.netcdf_name: v.api_code for k, v in SILO_VARIABLES.items()}
API_TO_NETCDF = {v.api_code: v.netcdf_name for k, v in SILO_VARIABLES.items() if v.api_code}

# Preset groups
VARIABLE_PRESETS = {
    "daily": ["daily_rain", "max_temp", "min_temp", "evap_syn"],
    "monthly": ["monthly_rain"],
    "temperature": ["max_temp", "min_temp"],
    "evaporation": ["evap_pan", "evap_syn", "evap_comb"],
    "radiation": ["radiation"],
    "humidity": ["vp", "vp_deficit", "rh_tmax", "rh_tmin"],
}

# Type hints for valid variable inputs
VariablePreset = Literal["daily", "monthly", "temperature", "evaporation", "radiation", "humidity"]


VariableName = Literal[
    "daily_rain",
    "monthly_rain",
    "max_temp",
    "min_temp",
    "vp",
    "vp_deficit",
    "rh_tmax",
    "rh_tmin",
    "mslp",
    "evap_pan",
    "evap_syn",
    "evap_comb",
    "evap_morton_lake",
    "radiation",
    "et_short_crop",
    "et_tall_crop",
    "et_morton_actual",
    "et_morton_potential",
    "et_morton_wet",
]

# Union type for function parameters accepting variables
VariableInput = Union[VariablePreset, VariableName, List[Union[VariablePreset, VariableName]]]


def get_variable_metadata(identifier: str) -> Optional[VariableMetadata]:
    """
    Get variable metadata by API code or NetCDF name.

    Args:
        identifier: API code (e.g., "R") or NetCDF name (e.g., "daily_rain")

    Returns:
        VariableMetadata or None if not found
    """
    # Try direct lookup
    if identifier in SILO_VARIABLES:
        return SILO_VARIABLES[identifier]

    # Try reverse lookup by netcdf_name
    for meta in SILO_VARIABLES.values():
        if meta.netcdf_name == identifier:
            return meta

    return None


def expand_variable_preset(preset_or_vars: VariableInput) -> list[str]:
    """
    Expand preset names to NetCDF variable names.

    Args:
        preset_or_vars: Variable preset name ("daily", "monthly", etc.),
                       variable name ("daily_rain", "max_temp", etc.),
                       or list of presets/variable names

    Returns:
        List of NetCDF variable names

    Example:
        >>> expand_variable_preset("daily")
        ['daily_rain', 'max_temp', 'min_temp', 'evap_syn']
        >>> expand_variable_preset(["daily_rain", "max_temp"])
        ['daily_rain', 'max_temp']
    """
    if isinstance(preset_or_vars, str):
        if preset_or_vars in VARIABLE_PRESETS:
            return VARIABLE_PRESETS[preset_or_vars]
        else:
            return [preset_or_vars]
    else:
        # Expand any presets in the list
        expanded = []
        for item in preset_or_vars:
            if item in VARIABLE_PRESETS:
                expanded.extend(VARIABLE_PRESETS[item])
            else:
                expanded.append(item)
        return expanded


def validate_silo_s3_variables(
    variables: VariableInput,
    error_class: type[Exception] = ValueError
) -> dict[str, VariableMetadata]:
    """
    Validate and expand variables, returning metadata map.

    This function combines variable expansion and validation, ensuring all
    requested variables exist and returning their metadata for further processing.

    Args:
        variables: Variable preset name ("daily", "monthly", etc.),
                  variable name ("daily_rain", "max_temp", etc.),
                  or list of presets/variable names
        error_class: Exception class to raise for unknown variables (default: ValueError)

    Returns:
        Dict mapping variable names to their VariableMetadata

    Raises:
        error_class: If any variable is unknown

    Example:
        >>> from weather_tools.silo_variables import validate_silo_s3_variables, SiloGeoTiffError
        >>> # Validate with default ValueError
        >>> metadata_map = validate_silo_s3_variables("daily")
        >>> print(list(metadata_map.keys()))
        ['daily_rain', 'max_temp', 'min_temp', 'evap_syn']
        >>> # Validate with custom exception
        >>> metadata_map = validate_silo_s3_variables(["daily_rain", "max_temp"], SiloGeoTiffError)
    """
    var_list = expand_variable_preset(variables)

    metadata_map: dict[str, VariableMetadata] = {}
    for var_name in var_list:
        metadata = get_variable_metadata(var_name)
        if metadata is None:
            raise error_class(f"Unknown variable: {var_name}")
        metadata_map[var_name] = metadata

    return metadata_map


# ===========================
# Met.no to SILO Variable Mapping
# ===========================

class MetNoVariableMapping(BaseModel):
    """Mapping from met.no variable to SILO variable."""
    metno_name: str
    silo_name: str
    conversion_func: Optional[str] = None  # Name of conversion function if needed
    requires_other_vars: Optional[list[str]] = None  # Other variables needed for conversion


# Mappings from met.no daily summary fields to SILO column names
METNO_TO_SILO_MAPPING = {
    # Direct mappings (same units, no conversion needed)
    "min_temperature": MetNoVariableMapping(
        metno_name="min_temperature",
        silo_name="min_temp"
    ),
    "max_temperature": MetNoVariableMapping(
        metno_name="max_temperature",
        silo_name="max_temp"
    ),
    "total_precipitation": MetNoVariableMapping(
        metno_name="total_precipitation",
        silo_name="daily_rain"
    ),
    "avg_pressure": MetNoVariableMapping(
        metno_name="avg_pressure",
        silo_name="mslp"
    ),

    # Approximate mappings (may need conversion)
    "avg_relative_humidity": MetNoVariableMapping(
        metno_name="avg_relative_humidity",
        silo_name="vp",
        conversion_func="rh_to_vapor_pressure",
        requires_other_vars=["min_temperature", "max_temperature"]
    ),

    # Met.no only variables (no SILO equivalent)
    "avg_wind_speed": MetNoVariableMapping(
        metno_name="avg_wind_speed",
        silo_name="wind_speed"
    ),
    "max_wind_speed": MetNoVariableMapping(
        metno_name="max_wind_speed",
        silo_name="wind_speed_max"
    ),
    "avg_cloud_fraction": MetNoVariableMapping(
        metno_name="avg_cloud_fraction",
        silo_name="cloud_fraction"
    ),
    "dominant_weather_symbol": MetNoVariableMapping(
        metno_name="dominant_weather_symbol",
        silo_name="weather_symbol"
    ),
}

# SILO variables that have no met.no equivalent
SILO_ONLY_VARIABLES = [
    "evap_pan",      # E - Class A pan evaporation
    "evap_syn",      # S - Synthetic evaporation
    "evap_comb",     # C - Combination evaporation
    "radiation",     # J - Solar radiation (met.no has UV, not global radiation)
    "vp_deficit",    # D - Vapor pressure deficit
    "rh_tmax",       # H - RH at time of max temp
    "rh_tmin",       # G - RH at time of min temp
    "et_short_crop", # F - FAO56 ET
    "et_tall_crop",  # T - ASCE tall crop ET
    "et_morton_actual",     # A
    "et_morton_potential",  # P
    "et_morton_wet",        # W
    "evap_morton_lake",     # L
]


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


def convert_metno_to_silo_columns(df, include_extra: bool = False) -> dict:
    """
    Convert met.no DataFrame column names to SILO format.

    Args:
        df: DataFrame with met.no daily summaries
        include_extra: If True, include met.no-only variables (wind, clouds)

    Returns:
        Dictionary mapping met.no columns to SILO columns
    """

    column_mapping = {}

    for metno_col in df.columns:
        if metno_col == "date":
            column_mapping[metno_col] = "date"
        elif metno_col in METNO_TO_SILO_MAPPING:
            mapping = METNO_TO_SILO_MAPPING[metno_col]

            # Skip met.no-only variables unless requested
            if not include_extra and mapping.silo_name in ["wind_speed", "wind_speed_max", "cloud_fraction", "weather_symbol"]:
                continue

            column_mapping[metno_col] = mapping.silo_name

    return column_mapping


def get_silo_column_order() -> list[str]:
    """
    Return standard SILO CSV column order.

    Returns:
        List of column names in standard SILO order
    """
    return [
        "date",
        "day",
        "year",
        "daily_rain",
        "max_temp",
        "min_temp",
        "vp",
        "evap_pan",
        "evap_syn",
        "evap_comb",
        "evap_morton_lake",
        "radiation",
        "rh_tmax",
        "rh_tmin",
        "et_short_crop",
        "et_tall_crop",
        "et_morton_actual",
        "et_morton_potential",
        "et_morton_wet",
        "mslp",
    ]


def add_silo_date_columns(df):
    """
    Add SILO-specific date columns (day, year) from date column.

    Args:
        df: DataFrame with 'date' column

    Returns:
        DataFrame with added 'day' and 'year' columns
    """
    import pandas as pd

    df = df.copy()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df["day"] = df["date"].dt.dayofyear
        df["year"] = df["date"].dt.year

    return df
