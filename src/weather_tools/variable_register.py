"""
Central registry for SILO climate variables.

Maps between:
- API single-letter codes (used in PatchedPoint/DataDrill queries)
- NetCDF filenames (used for gridded data downloads)
- Full variable names and metadata
- DataFrame column names (canonical names = SILO_VARIABLES.keys())
- SILO variables and metno aggregated forecast variables.

SILO variable reference: https://www.longpaddock.qld.gov.au/silo/about/climate-variables/
"""

from typing import Iterator, KeysView, Literal, Optional, ValuesView

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
        metno_name: Raw met.no API field name this variable is derived from
            (e.g. "air_temperature", "precipitation_amount"). None if met.no does
            not supply it. Several canonical variables may share one raw field
            (e.g. max_temp/min_temp both come from "air_temperature").
        metno_agg: Aggregation applied to the raw met.no field to produce this
            variable's daily summary. None if the variable is not derived from met.no.
        full_name: Human-readable name
        units: Units of measurement
        description: Optional detailed description
        metno_only: True if variable is only available from met.no (not in SILO)
    """

    silo_code: Optional[str] = None
    netcdf_name: Optional[str] = None
    metno_name: Optional[str] = None
    metno_agg: Optional[Literal["min", "max", "sum", "mean", "dominant"]] = None
    full_name: str
    units: str
    description: Optional[str] = None
    metno_only: bool = False
    granularity: Literal["daily", "monthly"] = "daily"


# Complete mapping of all SILO variables
# Keys are canonical names used in DataFrames, CSV exports, and user-facing APIs
SILO_VARIABLES: dict[str, VariableMetadata] = {
    # Rainfall
    "daily_rain": VariableMetadata(
        silo_code="R",
        netcdf_name="daily_rain",
        metno_name="precipitation_amount",
        metno_agg="sum",
        full_name="Daily rainfall",
        units="mm",
    ),
    "monthly_rain": VariableMetadata(
        silo_code=None,
        netcdf_name="monthly_rain",
        full_name="Monthly rainfall",
        units="mm",
        granularity="monthly",
    ),
    # Temperature
    "max_temp": VariableMetadata(
        silo_code="X",
        netcdf_name="max_temp",
        metno_name="air_temperature",
        metno_agg="max",
        full_name="Maximum temperature",
        units="°C",
    ),
    "min_temp": VariableMetadata(
        silo_code="N",
        netcdf_name="min_temp",
        metno_name="air_temperature",
        metno_agg="min",
        full_name="Minimum temperature",
        units="°C",
    ),
    # Humidity and Pressure
    "vp": VariableMetadata(
        silo_code="V",
        netcdf_name="vp",
        full_name="Vapour pressure",
        units="hPa",
        description=(
            "SILO observation. Not mapped directly from met.no; merge derives it "
            "from met.no relative_humidity and mean daily temperature."
        ),
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
        metno_name="air_pressure_at_sea_level",
        metno_agg="mean",
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
        full_name="Combination (synthetic estimate pre-1970, class A pan 1970 onwards)",
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
        full_name="Morton's wet-environment areal potential evapotranspiration over land",
        units="mm",
    ),
    # Met.no-only variables (not available in SILO)
    "relative_humidity": VariableMetadata(
        metno_name="relative_humidity",
        metno_agg="mean",
        full_name="Average relative humidity",
        units="%",
        metno_only=True,
    ),
    "wind_speed": VariableMetadata(
        metno_name="wind_speed",
        metno_agg="mean",
        full_name="Average wind speed",
        units="m/s",
        metno_only=True,
    ),
    "wind_speed_max": VariableMetadata(
        metno_name="wind_speed",
        metno_agg="max",
        full_name="Maximum wind speed",
        units="m/s",
        metno_only=True,
    ),
    "cloud_fraction": VariableMetadata(
        metno_name="cloud_area_fraction",
        metno_agg="mean",
        full_name="Average cloud fraction",
        units="%",
        metno_only=True,
    ),
    "weather_symbol": VariableMetadata(
        metno_name="symbol_code",
        metno_agg="dominant",
        full_name="Dominant weather symbol",
        units="code",
        metno_only=True,
    ),
}

# ===========================
# Variable Registry
# ===========================


class VariableRegistry:
    """Registry providing variable lookups and conversions.

    This class wraps SILO_VARIABLES dict and provides:
    - Dict-like access to variable metadata
    - Conversion between canonical names, SILO codes, and met.no names
    - Validation of requested variables

    The registry is typically used via the singleton VARIABLES instance:

        >>> from weather_tools.silo_variables import VARIABLES
        >>> VARIABLES["daily_rain"].units
        'mm'
        >>> VARIABLES.silo_code_from_name("daily_rain")
        'R'
        >>> VARIABLES.name_from_silo_code("R")
        'daily_rain'
    """

    def __init__(self, variables: dict[str, VariableMetadata]) -> None:
        """Initialize registry with variable metadata.

        Args:
            variables: Dict mapping canonical names to VariableMetadata
        """
        self._variables = variables

        # Build reverse lookup indexes (computed once).
        # Note: there is intentionally no reverse index for met.no names. A raw
        # met.no field (e.g. "air_temperature") can map to several canonical
        # variables (max_temp, min_temp), so it is not a 1:1 relationship.
        # Daily aggregation uses metno_daily_agg_spec() instead.
        self._by_silo_code: dict[str, str] = {}
        self._by_netcdf_name: dict[str, str] = {}

        for name, meta in variables.items():
            if meta.silo_code:
                self._by_silo_code[meta.silo_code] = name
            if meta.netcdf_name:
                self._by_netcdf_name[meta.netcdf_name] = name

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

    def get_by_any(self, identifier: str) -> Optional[VariableMetadata]:
        """Get variable metadata by any identifier.

        Tries canonical name, SILO code, and NetCDF name.

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

        return None

    # -------------------------
    # Met.no aggregation
    # -------------------------

    def metno_daily_agg_spec(self) -> dict[str, tuple[str, str]]:
        """Return the daily aggregation spec for met.no-derived variables.

        Maps each canonical variable that comes from met.no to the raw met.no
        field and the aggregation used to summarise it to a daily value. This is
        the single source of truth for met.no -> canonical naming: a raw field
        may feed several canonical variables (e.g. ``air_temperature`` produces
        both ``max_temp`` and ``min_temp``).

        Returns:
            Dict mapping canonical name -> (raw_metno_field, aggregation), e.g.
            ``{"max_temp": ("air_temperature", "max"), ...}``
        """
        return {
            name: (meta.metno_name, meta.metno_agg)
            for name, meta in self._variables.items()
            if meta.metno_name and meta.metno_agg
        }

    # -------------------------
    # Validation
    # -------------------------

    def validate(
        self, variables: str | list[str], error_class: type[Exception] = ValueError
    ) -> dict[str, VariableMetadata]:
        """Validate requested variables, returning a metadata map.

        Accepts a single canonical variable name or a list of names. Every name
        must be specified explicitly; there are no presets.

        Args:
            variables: Canonical variable name, or list of canonical names
            error_class: Exception class to raise for unknown variables

        Returns:
            Dict mapping canonical names to VariableMetadata

        Raises:
            error_class: If any variable is unknown

        Example:
            >>> metadata_map = VARIABLES.validate(["daily_rain", "max_temp"])
            >>> print(list(metadata_map.keys()))
            ['daily_rain', 'max_temp']
        """
        var_list = [variables] if isinstance(variables, str) else list(variables)

        metadata_map: dict[str, VariableMetadata] = {}
        for var_name in var_list:
            if var_name not in self._variables:
                raise error_class(f"Unknown variable: {var_name}")
            metadata_map[var_name] = self._variables[var_name]

        return metadata_map

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
VARIABLES = VariableRegistry(SILO_VARIABLES)
