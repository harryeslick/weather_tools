"""
Central registry for SILO climate variables.

Maps between:
- API single-letter codes (used in PatchedPoint/DataDrill queries)
- NetCDF filenames (used for gridded data downloads)
- Full variable names and metadata
- SILO dataframe column names
"""

from typing import Optional
from pydantic import BaseModel


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
    "R": VariableMetadata(
        api_code="R",
        netcdf_name="daily_rain",
        full_name="Daily rainfall",
        units="mm"
    ),
    "monthly_rain": VariableMetadata(
        api_code=None,
        netcdf_name="monthly_rain",
        full_name="Monthly rainfall",
        units="mm"
    ),

    # Temperature
    "X": VariableMetadata(
        api_code="X",
        netcdf_name="max_temp",
        full_name="Maximum temperature",
        units="°C"
    ),
    "N": VariableMetadata(
        api_code="N",
        netcdf_name="min_temp",
        full_name="Minimum temperature",
        units="°C"
    ),

    # Humidity and Pressure
    "V": VariableMetadata(
        api_code="V",
        netcdf_name="vp",
        full_name="Vapour pressure",
        units="hPa"
    ),
    "D": VariableMetadata(
        api_code="D",
        netcdf_name="vp_deficit",
        full_name="Vapour pressure deficit",
        units="hPa"
    ),
    "H": VariableMetadata(
        api_code="H",
        netcdf_name="rh_tmax",
        full_name="Relative humidity at time of maximum temperature",
        units="%"
    ),
    "G": VariableMetadata(
        api_code="G",
        netcdf_name="rh_tmin",
        full_name="Relative humidity at time of minimum temperature",
        units="%"
    ),
    "M": VariableMetadata(
        api_code="M",
        netcdf_name="mslp",
        full_name="Mean sea level pressure",
        units="hPa",
        start_year=1957
    ),

    # Evaporation
    "E": VariableMetadata(
        api_code="E",
        netcdf_name="evap_pan",
        full_name="Class A pan evaporation",
        units="mm",
        start_year=1970
    ),
    "S": VariableMetadata(
        api_code="S",
        netcdf_name="evap_syn",
        full_name="Synthetic estimate evaporation",
        units="mm"
    ),
    "C": VariableMetadata(
        api_code="C",
        netcdf_name="evap_comb",
        full_name="Combination evaporation",
        units="mm"
    ),
    "L": VariableMetadata(
        api_code="L",
        netcdf_name="evap_morton_lake",
        full_name="Morton's shallow lake evaporation",
        units="mm"
    ),

    # Radiation
    "J": VariableMetadata(
        api_code="J",
        netcdf_name="radiation",
        full_name="Solar exposure (direct and diffuse)",
        units="MJ/m²"
    ),

    # Evapotranspiration
    "F": VariableMetadata(
        api_code="F",
        netcdf_name="et_short_crop",
        full_name="FAO56 short crop evapotranspiration",
        units="mm"
    ),
    "T": VariableMetadata(
        api_code="T",
        netcdf_name="et_tall_crop",
        full_name="ASCE tall crop evapotranspiration",
        units="mm"
    ),
    "A": VariableMetadata(
        api_code="A",
        netcdf_name="et_morton_actual",
        full_name="Morton's areal actual evapotranspiration",
        units="mm"
    ),
    "P": VariableMetadata(
        api_code="P",
        netcdf_name="et_morton_potential",
        full_name="Morton's point potential evapotranspiration",
        units="mm"
    ),
    "W": VariableMetadata(
        api_code="W",
        netcdf_name="et_morton_wet",
        full_name="Morton's wet-environment areal potential evapotranspiration",
        units="mm"
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


def expand_variable_preset(preset_or_vars: str | list[str]) -> list[str]:
    """
    Expand preset names to NetCDF variable names.

    Args:
        preset_or_vars: Either a preset name ("daily", "monthly") or list of variable names

    Returns:
        List of NetCDF variable names
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
