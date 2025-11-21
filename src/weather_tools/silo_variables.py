"""
Central registry for SILO climate variables.

Maps between:
- API single-letter codes (used in PatchedPoint/DataDrill queries)
- NetCDF filenames (used for gridded data downloads)
- Full variable names and metadata
- DataFrame column names (canonical names = SILO_VARIABLES.keys())
"""

from typing import Iterator, KeysView, List, Literal, Optional, Union, ValuesView

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
    """Metadata for a climate variable.

    Attributes:
        silo_code: Single letter code for SILO API (None for variables without API code)
        netcdf_name: Filename used in NetCDF downloads (None for non-NetCDF variables)
        metno_name: Corresponding met.no variable name for forecast data
        full_name: Human-readable name
        units: Units of measurement
        description: Optional detailed description
        metno_only: True if variable is only available from met.no (not in SILO)
    """

    silo_code: Optional[str] = None
    netcdf_name: Optional[str] = None
    metno_name: Optional[str] = None
    full_name: str
    units: str
    description: Optional[str] = None
    metno_only: bool = False


# Complete mapping of all SILO variables
# Keys are canonical names used in DataFrames, CSV exports, and user-facing APIs
SILO_VARIABLES: dict[str, VariableMetadata] = {
    # Rainfall
    "daily_rain": VariableMetadata(
        silo_code="R",
        netcdf_name="daily_rain",
        metno_name="total_precipitation",
        full_name="Daily rainfall",
        units="mm",
    ),
    "monthly_rain": VariableMetadata(
        silo_code=None,
        netcdf_name="monthly_rain",
        full_name="Monthly rainfall",
        units="mm",
    ),
    # Temperature
    "max_temp": VariableMetadata(
        silo_code="X",
        netcdf_name="max_temp",
        metno_name="max_temperature",
        full_name="Maximum temperature",
        units="°C",
    ),
    "min_temp": VariableMetadata(
        silo_code="N",
        netcdf_name="min_temp",
        metno_name="min_temperature",
        full_name="Minimum temperature",
        units="°C",
    ),
    # Humidity and Pressure
    "vp": VariableMetadata(
        silo_code="V",
        netcdf_name="vp",
        metno_name="avg_relative_humidity",
        full_name="Vapour pressure",
        units="hPa",
    ),
    "vp_deficit": VariableMetadata(
        silo_code="D",
        netcdf_name="vp_deficit",
        full_name="Vapour pressure deficit",
        units="hPa",
    ),
    "rh_tmax": VariableMetadata(
        silo_code="H",
        netcdf_name="rh_tmax",
        full_name="Relative humidity at time of maximum temperature",
        units="%",
    ),
    "rh_tmin": VariableMetadata(
        silo_code="G",
        netcdf_name="rh_tmin",
        full_name="Relative humidity at time of minimum temperature",
        units="%",
    ),
    "mslp": VariableMetadata(
        silo_code="M",
        netcdf_name="mslp",
        metno_name="avg_pressure",
        full_name="Mean sea level pressure",
        units="hPa",
    ),
    # Evaporation
    "evap_pan": VariableMetadata(
        silo_code="E",
        netcdf_name="evap_pan",
        full_name="Class A pan evaporation",
        units="mm",
    ),
    "evap_syn": VariableMetadata(
        silo_code="S",
        netcdf_name="evap_syn",
        full_name="Synthetic estimate evaporation",
        units="mm",
    ),
    "evap_comb": VariableMetadata(
        silo_code="C",
        netcdf_name="evap_comb",
        full_name="Combination evaporation",
        units="mm",
    ),
    "evap_morton_lake": VariableMetadata(
        silo_code="L",
        netcdf_name="evap_morton_lake",
        full_name="Morton's shallow lake evaporation",
        units="mm",
    ),
    # Radiation
    "radiation": VariableMetadata(
        silo_code="J",
        netcdf_name="radiation",
        full_name="Solar exposure (direct and diffuse)",
        units="MJ/m²",
    ),
    # Evapotranspiration
    "et_short_crop": VariableMetadata(
        silo_code="F",
        netcdf_name="et_short_crop",
        full_name="FAO56 short crop evapotranspiration",
        units="mm",
    ),
    "et_tall_crop": VariableMetadata(
        silo_code="T",
        netcdf_name="et_tall_crop",
        full_name="ASCE tall crop evapotranspiration",
        units="mm",
    ),
    "et_morton_actual": VariableMetadata(
        silo_code="A",
        netcdf_name="et_morton_actual",
        full_name="Morton's areal actual evapotranspiration",
        units="mm",
    ),
    "et_morton_potential": VariableMetadata(
        silo_code="P",
        netcdf_name="et_morton_potential",
        full_name="Morton's point potential evapotranspiration",
        units="mm",
    ),
    "et_morton_wet": VariableMetadata(
        silo_code="W",
        netcdf_name="et_morton_wet",
        full_name="Morton's wet-environment areal potential evapotranspiration",
        units="mm",
    ),
    # Met.no-only variables (not available in SILO)
    "wind_speed": VariableMetadata(
        metno_name="avg_wind_speed",
        full_name="Average wind speed",
        units="m/s",
        metno_only=True,
    ),
    "wind_speed_max": VariableMetadata(
        metno_name="max_wind_speed",
        full_name="Maximum wind speed",
        units="m/s",
        metno_only=True,
    ),
    "cloud_fraction": VariableMetadata(
        metno_name="avg_cloud_fraction",
        full_name="Average cloud fraction",
        units="%",
        metno_only=True,
    ),
    "weather_symbol": VariableMetadata(
        metno_name="dominant_weather_symbol",
        full_name="Dominant weather symbol",
        units="code",
        metno_only=True,
    ),
}

# Preset groups for common variable combinations
VARIABLE_PRESETS: dict[str, list[str]] = {
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
    # Met.no-only variables
    "wind_speed",
    "wind_speed_max",
    "cloud_fraction",
    "weather_symbol",
]

# Union type for function parameters accepting variables
VariableInput = Union[VariablePreset, VariableName, List[Union[VariablePreset, VariableName]]]


# ===========================
# Variable Registry
# ===========================


class VariableRegistry:
    """Registry providing variable lookups and conversions.

    This class wraps SILO_VARIABLES dict and provides:
    - Dict-like access to variable metadata
    - Conversion between canonical names, SILO codes, and met.no names
    - Preset expansion and validation

    The registry is typically used via the singleton VARIABLES instance:

        >>> from weather_tools.silo_variables import VARIABLES
        >>> VARIABLES["daily_rain"].units
        'mm'
        >>> VARIABLES.silo_code_from_name("daily_rain")
        'R'
        >>> VARIABLES.name_from_silo_code("R")
        'daily_rain'
    """

    def __init__(
        self, variables: dict[str, VariableMetadata], presets: dict[str, list[str]]
    ) -> None:
        """Initialize registry with variable metadata.

        Args:
            variables: Dict mapping canonical names to VariableMetadata
            presets: Dict mapping preset names to lists of variable names
        """
        self._variables = variables
        self._presets = presets

        # Build reverse lookup indexes (computed once)
        self._by_silo_code: dict[str, str] = {}
        self._by_netcdf_name: dict[str, str] = {}
        self._by_metno_name: dict[str, str] = {}

        for name, meta in variables.items():
            if meta.silo_code:
                self._by_silo_code[meta.silo_code] = name
            if meta.netcdf_name:
                self._by_netcdf_name[meta.netcdf_name] = name
            if meta.metno_name:
                self._by_metno_name[meta.metno_name] = name

    # -------------------------
    # Dict-like interface
    # -------------------------

    def __getitem__(self, name: str) -> VariableMetadata:
        """Get variable metadata by canonical name."""
        return self._variables[name]

    def __contains__(self, name: str) -> bool:
        """Check if canonical name exists in registry."""
        return name in self._variables

    def __iter__(self) -> Iterator[str]:
        """Iterate over canonical names."""
        return iter(self._variables)

    def __len__(self) -> int:
        """Return number of variables in registry."""
        return len(self._variables)

    def keys(self) -> KeysView[str]:
        """Return view of canonical variable names."""
        return self._variables.keys()

    def values(self) -> ValuesView[VariableMetadata]:
        """Return view of variable metadata."""
        return self._variables.values()

    def items(self):
        """Return view of (name, metadata) pairs."""
        return self._variables.items()

    def get(
        self, name: str, default: Optional[VariableMetadata] = None
    ) -> Optional[VariableMetadata]:
        """Get variable metadata by canonical name, or default if not found."""
        return self._variables.get(name, default)

    # -------------------------
    # Conversion methods
    # -------------------------

    def silo_code_from_name(self, name: str) -> Optional[str]:
        """Convert canonical name to SILO API code.

        Args:
            name: Canonical variable name (e.g., "daily_rain")

        Returns:
            SILO API code (e.g., "R") or None if variable has no API code

        Raises:
            KeyError: If name is not a valid canonical name
        """
        return self._variables[name].silo_code

    def name_from_silo_code(self, code: str) -> str:
        """Convert SILO API code to canonical name.

        Args:
            code: SILO API code (e.g., "R")

        Returns:
            Canonical variable name (e.g., "daily_rain")

        Raises:
            KeyError: If code is not a valid SILO API code
        """
        return self._by_silo_code[code]

    def name_from_netcdf(self, netcdf_name: str) -> str:
        """Convert NetCDF filename to canonical name.

        Args:
            netcdf_name: NetCDF variable name (e.g., "daily_rain")

        Returns:
            Canonical variable name

        Raises:
            KeyError: If netcdf_name is not found
        """
        return self._by_netcdf_name[netcdf_name]

    def name_from_metno(self, metno_name: str) -> str:
        """Convert met.no variable name to canonical name.

        Args:
            metno_name: met.no variable name (e.g., "total_precipitation")

        Returns:
            Canonical variable name (e.g., "daily_rain")

        Raises:
            KeyError: If metno_name is not found
        """
        return self._by_metno_name[metno_name]

    def get_by_any(self, identifier: str) -> Optional[VariableMetadata]:
        """Get variable metadata by any identifier.

        Tries canonical name, SILO code, NetCDF name, and met.no name.

        Args:
            identifier: Any variable identifier

        Returns:
            VariableMetadata or None if not found
        """
        # Try canonical name first
        if identifier in self._variables:
            return self._variables[identifier]

        # Try SILO code
        if identifier in self._by_silo_code:
            return self._variables[self._by_silo_code[identifier]]

        # Try NetCDF name
        if identifier in self._by_netcdf_name:
            return self._variables[self._by_netcdf_name[identifier]]

        # Try met.no name
        if identifier in self._by_metno_name:
            return self._variables[self._by_metno_name[identifier]]

        return None

    # -------------------------
    # Met.no conversion methods
    # -------------------------

    def variables_without_metno(self) -> list[str]:
        """Return list of SILO variables that have no met.no equivalent.

        These variables will be empty/NaN when using met.no forecast data.

        Returns:
            List of canonical variable names without met.no mapping
        """
        return [name for name, meta in self._variables.items() if meta.metno_name is None]

    def has_metno_mapping(self, metno_name: str) -> bool:
        """Check if a met.no variable name has a SILO mapping.

        Args:
            metno_name: met.no variable name

        Returns:
            True if mapping exists, False otherwise
        """
        return metno_name in self._by_metno_name

    def metno_to_canonical_mapping(self) -> dict[str, str]:
        """Return mapping from met.no variable names to canonical names.

        Returns:
            Dict mapping met.no names to canonical SILO names
        """
        return dict(self._by_metno_name)

    # -------------------------
    # Preset expansion and validation
    # -------------------------

    def expand_preset(self, preset_or_vars: VariableInput) -> list[str]:
        """Expand preset names to canonical variable names.

        Args:
            preset_or_vars: Variable preset name ("daily", "monthly", etc.),
                           variable name ("daily_rain", "max_temp", etc.),
                           or list of presets/variable names

        Returns:
            List of canonical variable names

        Example:
            >>> VARIABLES.expand_preset("daily")
            ['daily_rain', 'max_temp', 'min_temp', 'evap_syn']
            >>> VARIABLES.expand_preset(["daily_rain", "max_temp"])
            ['daily_rain', 'max_temp']
        """
        if isinstance(preset_or_vars, str):
            if preset_or_vars in self._presets:
                return list(self._presets[preset_or_vars])
            else:
                return [preset_or_vars]
        else:
            expanded = []
            for item in preset_or_vars:
                if item in self._presets:
                    expanded.extend(self._presets[item])
                else:
                    expanded.append(item)
            return expanded

    def validate(
        self, variables: VariableInput, error_class: type[Exception] = ValueError
    ) -> dict[str, VariableMetadata]:
        """Validate and expand variables, returning metadata map.

        Args:
            variables: Variable preset name, variable name, or list of both
            error_class: Exception class to raise for unknown variables

        Returns:
            Dict mapping canonical names to VariableMetadata

        Raises:
            error_class: If any variable is unknown

        Example:
            >>> metadata_map = VARIABLES.validate("daily")
            >>> print(list(metadata_map.keys()))
            ['daily_rain', 'max_temp', 'min_temp', 'evap_syn']
        """
        var_list = self.expand_preset(variables)

        metadata_map: dict[str, VariableMetadata] = {}
        for var_name in var_list:
            if var_name not in self._variables:
                raise error_class(f"Unknown variable: {var_name}")
            metadata_map[var_name] = self._variables[var_name]

        return metadata_map

    def is_preset(self, name: str) -> bool:
        """Check if name is a preset name."""
        return name in self._presets

    def preset_names(self) -> list[str]:
        """Return list of available preset names."""
        return list(self._presets.keys())

    def metno_only_variables(self) -> list[str]:
        """Return list of variables that are only available from met.no.

        Returns:
            List of canonical variable names that are met.no-only
        """
        return [name for name, meta in self._variables.items() if meta.metno_only]

    def silo_variables(self) -> list[str]:
        """Return list of variables available in SILO (not met.no-only).

        Returns:
            List of canonical variable names available in SILO
        """
        return [name for name, meta in self._variables.items() if not meta.metno_only]


# Singleton registry instance
VARIABLES = VariableRegistry(SILO_VARIABLES, VARIABLE_PRESETS)


def convert_metno_to_silo_columns(df, include_extra: bool = False) -> dict:
    """
    Convert met.no DataFrame column names to canonical format.

    Uses the unified VARIABLES registry for all variable mappings.

    Args:
        df: DataFrame with met.no daily summaries
        include_extra: If True, include met.no-only variables (wind, clouds)

    Returns:
        Dictionary mapping met.no columns to canonical column names
    """
    column_mapping = {}
    metno_only_vars = VARIABLES.metno_only_variables()

    for metno_col in df.columns:
        if metno_col == "date":
            column_mapping[metno_col] = "date"
        elif VARIABLES.has_metno_mapping(metno_col):
            canonical_name = VARIABLES.name_from_metno(metno_col)

            # Skip met.no-only variables unless requested
            if not include_extra and canonical_name in metno_only_vars:
                continue

            column_mapping[metno_col] = canonical_name

    return column_mapping
