"""
Output schemas for weather_tools point data.

This module defines the expected structure of DataFrames returned by all
point-data functions in weather_tools. Use these schemas to validate output
or to document integration contracts when building downstream packages.

## Discrepancies and unification decisions

The following inconsistencies exist across the user-facing point-data functions:

### 1. Date column name (fixed)
- SILO API (get_patched_point, get_data_drill): ``date``
- Met.no daily (get_daily_forecast, to_dataframe): ``date``
- Met.no raw (to_dataframe(daily=False)): ``time``
- Local xarray extract (CLI ``local extract``): ``time``  ← was inconsistent

**Resolution:** All point-data DataFrames must use ``date`` as the temporal column.
The ``local extract`` CLI command now renames ``time`` → ``date`` before output.
The Met.no raw path retains ``time`` because it represents sub-daily instants,
not daily observations, and is therefore excluded from the point-data schema.

### 2. Variable naming convention
- SILO: snake_case canonical names (``daily_rain``, ``max_temp``, ``min_temp``, ``vp``)
- Met.no raw columns: raw met.no API field names (``air_temperature``,
  ``precipitation_amount``, ``wind_speed``, …)

**Resolution:** SILO canonical names are the package standard. Met.no *daily*
summaries already emit canonical names directly (the aggregation is driven by the
``VARIABLES`` registry), so no separate rename step is needed. Met.no *raw*
(``to_dataframe(daily=False)``) keeps the raw met.no field names. Use
:func:`merge_historical_and_forecast` for a unified SILO-named DataFrame spanning
both sources.

### 3. Metadata embedded in data rows (not unified)
- SILO API embeds a JSON string in the ``metadata`` column of row 0 only.
- Other sources have no ``metadata`` column.

**Resolution:** The ``metadata`` column is a SILO API implementation detail and
is intentionally absent from the schema. Callers that need query metadata should
use ``return_metadata=True`` on ``get_patched_point``/``get_data_drill``, which
returns a proper ``(DataFrame, dict)`` tuple. The schema reflects the clean
DataFrame without the ``metadata`` column.

### 4. Location columns
- SILO API: no lat/lon in DataFrame (location is a query parameter)
- Local extract CLI: optionally retains ``lat``, ``lon``, ``crs`` (dropped by default)
- Met.no: no lat/lon in DataFrame

**Resolution:** Location is metadata, not data. Point-data DataFrames should not
carry lat/lon columns. Pass location via :class:`PointMetadata` alongside the
DataFrame when needed.

## Key conventions (applies to all point-data returns)
- Date column: always named ``date``, dtype ``datetime64[ns]``, timezone-naive
- Index: ``RangeIndex`` (0-based integer), not a ``DatetimeIndex``
- Variable columns: ``float64``, ``NaN`` for missing values
- No embedded metadata in data rows
- No location columns (lat/lon belong in :class:`PointMetadata`)
- Variable names use SILO canonical names as the package standard
"""

import datetime as dt
from typing import ClassVar, Dict, List, Literal, Optional, Union

import pandas as pd
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Standard column names
# ---------------------------------------------------------------------------

#: The temporal column name used in all point-data DataFrames.
DATE_COLUMN: str = "date"

#: The canonical data-source label used in merged DataFrames.
DATA_SOURCE_COLUMN: str = "data_source"

#: Column marking whether a row is a forecast (True) or observation (False).
IS_FORECAST_COLUMN: str = "is_forecast"


# ---------------------------------------------------------------------------
# Metadata model
# ---------------------------------------------------------------------------


class PointMetadata(BaseModel):
    """Metadata associated with a point timeseries DataFrame.

    This is a companion to the DataFrame returned by point-data functions.
    It is returned via ``return_metadata=True`` on API convenience methods, or
    constructed manually when working with local files.

    Attributes:
        latitude: Latitude of the point in decimal degrees (WGS84 / GDA94).
        longitude: Longitude of the point in decimal degrees (WGS84 / GDA94).
        station_code: BOM station code; ``None`` for DataDrill or local queries.
        source: Identifies which data pipeline produced the DataFrame.
        start_date: First date present in the timeseries.
        end_date: Last date present in the timeseries.
        variables: Canonical variable names present as columns in the DataFrame.
    """

    latitude: float = Field(..., description="Latitude in decimal degrees (WGS84)")
    longitude: float = Field(..., description="Longitude in decimal degrees (WGS84)")
    station_code: Optional[str] = Field(None, description="BOM station code (PatchedPoint only)")
    source: Literal["silo_patched_point", "silo_data_drill", "silo_local", "metno", "merged"] = (
        Field(..., description="Data source identifier")
    )
    start_date: dt.date = Field(..., description="First date in the timeseries (inclusive)")
    end_date: dt.date = Field(..., description="Last date in the timeseries (inclusive)")
    variables: List[str] = Field(
        ..., description="Canonical variable names present in the DataFrame"
    )


# ---------------------------------------------------------------------------
# Row-level schemas
# ---------------------------------------------------------------------------


class SiloPointSchema(BaseModel):
    """Schema for one daily observation row from a SILO point source.

    Covers all three SILO pathways:
    - ``SiloAPI.get_patched_point()`` – station-based observational data
    - ``SiloAPI.get_data_drill()`` – gridded interpolated data
    - ``read_silo_xarray().sel(...).to_dataframe()`` – local NetCDF extraction

    Variable columns are present only when requested; absent columns appear as
    ``NaN`` in the DataFrame.

    DataFrame layout::

        date         daily_rain  max_temp  min_temp  radiation  vp  ...
        2023-01-01   5.2         32.1      18.4      22.3       15.1
        2023-01-02   0.0         29.8      17.1      20.1       14.6
        ...

    All numeric columns have ``dtype=float64``.
    The ``date`` column has ``dtype=datetime64[ns]``, timezone-naive.
    The DataFrame index is a ``RangeIndex`` (not a ``DatetimeIndex``).
    """

    # Required
    date: dt.date = Field(..., description="Date of observation")

    # Rainfall
    daily_rain: Optional[float] = Field(None, description="Daily rainfall (mm)")
    monthly_rain: Optional[float] = Field(None, description="Monthly rainfall (mm)")

    # Temperature
    max_temp: Optional[float] = Field(None, description="Maximum temperature (°C)")
    min_temp: Optional[float] = Field(None, description="Minimum temperature (°C)")

    # Humidity / pressure
    vp: Optional[float] = Field(None, description="Vapour pressure (hPa)")
    vp_deficit: Optional[float] = Field(None, description="Vapour pressure deficit (hPa)")
    rh_tmax: Optional[float] = Field(
        None, description="Relative humidity at time of max temperature (%)"
    )
    rh_tmin: Optional[float] = Field(
        None, description="Relative humidity at time of min temperature (%)"
    )
    mslp: Optional[float] = Field(None, description="Mean sea level pressure (hPa)")

    # Evaporation
    evap_pan: Optional[float] = Field(None, description="Class A pan evaporation (mm)")
    evap_syn: Optional[float] = Field(
        None, description="Synthetic estimate of open-water evaporation (mm)"
    )
    evap_comb: Optional[float] = Field(None, description="Combination evaporation (mm)")
    evap_morton_lake: Optional[float] = Field(
        None, description="Morton's shallow lake evaporation (mm)"
    )

    # Radiation
    radiation: Optional[float] = Field(
        None, description="Solar exposure, direct and diffuse (MJ/m²)"
    )

    # Evapotranspiration
    et_short_crop: Optional[float] = Field(
        None, description="FAO56 short crop evapotranspiration (mm)"
    )
    et_tall_crop: Optional[float] = Field(
        None, description="ASCE tall crop evapotranspiration (mm)"
    )
    et_morton_actual: Optional[float] = Field(
        None, description="Morton's areal actual evapotranspiration (mm)"
    )
    et_morton_potential: Optional[float] = Field(
        None, description="Morton's point potential evapotranspiration (mm)"
    )
    et_morton_wet: Optional[float] = Field(
        None, description="Morton's wet environment areal evapotranspiration (mm)"
    )

    # Wind
    wind: Optional[float] = Field(None, description="Average daily wind speed at 2 m (m/s)")

    #: Columns that must be present in any conforming DataFrame.
    REQUIRED_COLUMNS: ClassVar[List[str]] = [DATE_COLUMN]

    @classmethod
    def validate_dataframe(cls, df: pd.DataFrame) -> List[str]:
        """Check that *df* conforms to this schema.

        Args:
            df: DataFrame to validate.

        Returns:
            List of issue strings. An empty list means the DataFrame is valid.

        Example::

            issues = SiloPointSchema.validate_dataframe(df)
            if issues:
                raise ValueError("\\n".join(issues))
        """
        issues: List[str] = []

        # Required column presence
        for col in cls.REQUIRED_COLUMNS:
            if col not in df.columns:
                issues.append(f"Missing required column '{col}'")

        # Date column dtype
        if DATE_COLUMN in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df[DATE_COLUMN]):
                issues.append(
                    f"Column '{DATE_COLUMN}' must be datetime64, got {df[DATE_COLUMN].dtype}"
                )
            elif df[DATE_COLUMN].dt.tz is not None:
                issues.append(
                    f"Column '{DATE_COLUMN}' must be timezone-naive, got tz={df[DATE_COLUMN].dt.tz}"
                )

        # Index must be a RangeIndex
        if not isinstance(df.index, pd.RangeIndex):
            issues.append(f"DataFrame index must be RangeIndex, got {type(df.index).__name__}")

        # Metadata must not bleed into data rows
        if "metadata" in df.columns:
            issues.append(
                "Column 'metadata' found in DataFrame. "
                "Use return_metadata=True to receive metadata separately as a dict."
            )

        # Location columns belong in PointMetadata, not in the DataFrame
        for loc_col in ("lat", "lon", "crs"):
            if loc_col in df.columns:
                issues.append(
                    f"Location column '{loc_col}' found. "
                    "Location data should be passed via PointMetadata, not as DataFrame columns."
                )

        # All non-date columns should be float64
        known_fields = set(cls.model_fields) - {"date"}
        for col in df.columns:
            if col == DATE_COLUMN:
                continue
            if col in known_fields and not pd.api.types.is_float_dtype(df[col]):
                issues.append(f"Column '{col}' expected float64, got {df[col].dtype}")

        return issues

    @classmethod
    def column_descriptions(cls) -> Dict[str, str]:
        """Return a mapping of column name → description for all defined variables."""
        return {name: (field.description or "") for name, field in cls.model_fields.items()}


class MetNoForecastSchema(BaseModel):
    """Schema for one daily forecast row from met.no (via MetNoAPI.get_daily_forecast).

    Daily summaries use canonical SILO column names directly — the aggregation in
    :meth:`MetNoAPI._aggregate_daily` is driven by the ``VARIABLES`` registry, so
    no rename step is required. Columns labelled met.no-only have no SILO
    equivalent; :func:`merge_weather_data.merge_historical_and_forecast` derives
    ``vp`` from ``relative_humidity`` and drops the met.no-only columns.

    Raw met.no field → canonical SILO name (for reference):

    ========================== ===== =================== ====================
    Raw met.no field           Agg   Canonical column    Notes
    ========================== ===== =================== ====================
    precipitation_amount       sum   daily_rain          mm
    air_temperature            max   max_temp            °C
    air_temperature            min   min_temp            °C
    air_pressure_at_sea_level  mean  mslp                hPa
    relative_humidity          mean  relative_humidity   % (→ vp in merge)
    wind_speed                 mean  wind_speed          m/s (met.no-only)
    wind_speed                 max   wind_speed_max      m/s (met.no-only)
    cloud_area_fraction        mean  cloud_fraction      % (met.no-only)
    symbol_code                dom.  weather_symbol      met.no-only
    ========================== ===== =================== ====================

    DataFrame layout::

        date         min_temp  max_temp  daily_rain  mslp  ...
        2026-02-17   18.4      29.2      0.0         1014
        2026-02-18   19.1      30.5      2.1         1012
        ...
    """

    date: dt.date = Field(..., description="Forecast date")
    min_temp: Optional[float] = Field(None, description="Daily minimum air temperature (°C)")
    max_temp: Optional[float] = Field(None, description="Daily maximum air temperature (°C)")
    daily_rain: Optional[float] = Field(None, description="Total daily precipitation (mm)")
    mslp: Optional[float] = Field(None, description="Mean daily sea-level pressure (hPa)")
    relative_humidity: Optional[float] = Field(
        None, description="Mean daily relative humidity (%); met.no-only"
    )
    wind_speed: Optional[float] = Field(
        None, description="Mean daily wind speed at 10 m (m/s); met.no-only"
    )
    wind_speed_max: Optional[float] = Field(
        None, description="Maximum daily wind speed at 10 m (m/s); met.no-only"
    )
    cloud_fraction: Optional[float] = Field(
        None, description="Mean daily cloud area fraction (%); met.no-only"
    )
    weather_symbol: Optional[str] = Field(
        None, description="Dominant met.no weather symbol code for the day; met.no-only"
    )

    REQUIRED_COLUMNS: ClassVar[List[str]] = [DATE_COLUMN]

    @classmethod
    def validate_dataframe(cls, df: pd.DataFrame) -> List[str]:
        """Check that *df* conforms to this schema.

        Returns a list of issue strings (empty → valid).
        """
        issues: List[str] = []

        if DATE_COLUMN not in df.columns:
            issues.append(f"Missing required column '{DATE_COLUMN}'")

        if DATE_COLUMN in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df[DATE_COLUMN]):
                issues.append(
                    f"Column '{DATE_COLUMN}' must be datetime64, got {df[DATE_COLUMN].dtype}"
                )
            elif df[DATE_COLUMN].dt.tz is not None:
                issues.append(
                    f"Column '{DATE_COLUMN}' must be timezone-naive, got tz={df[DATE_COLUMN].dt.tz}"
                )

        if not isinstance(df.index, pd.RangeIndex):
            issues.append(f"DataFrame index must be RangeIndex, got {type(df.index).__name__}")

        return issues


class MergedPointSchema(BaseModel):
    """Schema for one row of a merged SILO + Met.no DataFrame.

    Produced by :func:`merge_weather_data.merge_historical_and_forecast`.
    All variable columns use SILO canonical names. The two provenance
    columns (``data_source``, ``is_forecast``) allow downstream callers to
    distinguish observations from forecasts.

    DataFrame layout::

        date         daily_rain  max_temp  min_temp  ...  data_source  is_forecast
        2026-02-10   5.2         32.1      18.4           silo         False
        2026-02-17   0.0         29.2      18.4           metno        True
        ...

    The ``forecast_generated_at`` column is only present in met.no rows and
    records the UTC timestamp when the forecast was retrieved.
    """

    date: dt.date = Field(..., description="Date of observation or forecast")

    # SILO canonical variable columns (same as SiloPointSchema)
    daily_rain: Optional[float] = Field(None, description="Daily rainfall (mm)")
    max_temp: Optional[float] = Field(None, description="Maximum temperature (°C)")
    min_temp: Optional[float] = Field(None, description="Minimum temperature (°C)")
    radiation: Optional[float] = Field(
        None, description="Solar exposure, direct and diffuse (MJ/m²)"
    )
    vp: Optional[float] = Field(None, description="Vapour pressure (hPa)")
    evap_pan: Optional[float] = Field(None, description="Class A pan evaporation (mm)")
    mslp: Optional[float] = Field(None, description="Mean sea level pressure (hPa)")

    # Provenance
    data_source: Literal["silo", "metno"] = Field(
        ..., description="Identifies whether the row is from SILO or met.no"
    )
    is_forecast: bool = Field(
        ..., description="True for met.no forecast rows, False for SILO observations"
    )
    forecast_generated_at: Optional[dt.datetime] = Field(
        None,
        description="UTC timestamp when the forecast was retrieved (met.no rows only)",
    )

    REQUIRED_COLUMNS: ClassVar[List[str]] = [
        DATE_COLUMN,
        DATA_SOURCE_COLUMN,
        IS_FORECAST_COLUMN,
    ]

    @classmethod
    def validate_dataframe(cls, df: pd.DataFrame) -> List[str]:
        """Check that *df* conforms to this schema.

        Returns a list of issue strings (empty → valid).
        """
        issues: List[str] = []

        for col in cls.REQUIRED_COLUMNS:
            if col not in df.columns:
                issues.append(f"Missing required column '{col}'")

        if DATE_COLUMN in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df[DATE_COLUMN]):
                issues.append(
                    f"Column '{DATE_COLUMN}' must be datetime64, got {df[DATE_COLUMN].dtype}"
                )
            elif df[DATE_COLUMN].dt.tz is not None:
                issues.append(
                    f"Column '{DATE_COLUMN}' must be timezone-naive, got tz={df[DATE_COLUMN].dt.tz}"
                )

        if DATA_SOURCE_COLUMN in df.columns:
            valid_sources = {"silo", "metno"}
            bad = set(df[DATA_SOURCE_COLUMN].dropna().unique()) - valid_sources
            if bad:
                issues.append(f"Column '{DATA_SOURCE_COLUMN}' contains unexpected values: {bad}")

        if not isinstance(df.index, pd.RangeIndex):
            issues.append(f"DataFrame index must be RangeIndex, got {type(df.index).__name__}")

        return issues


# ---------------------------------------------------------------------------
# Convenience validator
# ---------------------------------------------------------------------------


def validate_point_dataframe(
    df: pd.DataFrame,
    schema: Union[type[SiloPointSchema], type[MetNoForecastSchema], type[MergedPointSchema]],
) -> List[str]:
    """Validate *df* against the given point-data schema.

    Args:
        df: DataFrame to check.
        schema: One of :class:`SiloPointSchema`, :class:`MetNoForecastSchema`,
                or :class:`MergedPointSchema`.

    Returns:
        List of issue strings describing any violations. An empty list means
        the DataFrame is valid.

    Example::

        from weather_tools.output_schemas import SiloPointSchema, validate_point_dataframe

        df = api.get_patched_point("30043", "20230101", "20230131")
        # Drop the metadata column before validating
        df = df.drop(columns=["metadata"], errors="ignore")

        issues = validate_point_dataframe(df, SiloPointSchema)
        if issues:
            raise ValueError("\\n".join(issues))
    """
    return schema.validate_dataframe(df)
