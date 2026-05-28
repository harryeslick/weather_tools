"""Pydantic query models for local SILO NetCDF file operations.

These models drive the ``weather-tools local extract`` and ``weather-tools local
download`` CLI commands via the ``@from_pydantic`` adapter in
``weather_tools.cli.pydantic_typer``. They are the single source of truth for
field names, types, defaults, and validation rules — the CLI options are
auto-derived from them.

Unlike ``BaseSiloQuery`` in ``silo_models.py``, local-file queries accept
*any* canonical variable in the registry — including ones with no SILO HTTP
API code (e.g. ``monthly_rain``) because the data is read from local NetCDF
files rather than the HTTP API.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from weather_tools.silo_models import AustralianCoordinates, SiloDateRange
from weather_tools.variable_register import VARIABLES

# Default daily variable set used when the user doesn't supply --var.
DEFAULT_DAILY_VARIABLES: list[str] = ["daily_rain", "max_temp", "min_temp", "evap_syn"]


def _validate_local_variables(v: Optional[List[str]]) -> Optional[List[str]]:
    """Validate variable names against the registry.

    Local NetCDF queries accept any canonical name in ``VARIABLES`` — including
    variables without a SILO API code (e.g. ``monthly_rain``). The only
    constraint is that the name exists in the registry.
    """
    if v is None:
        return v
    unknown = [name for name in v if name not in VARIABLES]
    if unknown:
        valid_names = ", ".join(sorted(VARIABLES.keys()))
        raise ValueError(f"Unknown variables: {unknown}. Valid names: {valid_names}")
    return v


class ExtractQuery(BaseModel):
    """Query model for ``weather-tools local extract``.

    Reads gridded SILO NetCDF files from a local directory, selects the nearest
    pixel to ``coordinates`` over ``date_range``, and returns a DataFrame to the
    caller. The CLI materialises that DataFrame as CSV.
    """

    model_config = ConfigDict(extra="forbid")

    coordinates: AustralianCoordinates = Field(
        ..., description="Australian coordinates (GDA94) of the point to extract"
    )
    date_range: SiloDateRange = Field(..., description="Date range to slice from the dataset")
    variables: Optional[List[str]] = Field(
        default=None,
        description=(
            "Climate variables to extract (canonical names, e.g. 'daily_rain', "
            "'max_temp'). Repeat the option for multiple; omit to use the default "
            "daily set."
        ),
    )
    silo_dir: Optional[Path] = Field(
        default=None,
        description="Path to the local SILO data directory (defaults to ~/DATA/silo_grids)",
    )
    tolerance: float = Field(
        default=0.1,
        gt=0.0,
        description="Maximum distance (in degrees) for nearest-neighbour selection",
    )
    keep_location: bool = Field(
        default=False,
        description="Keep location columns (crs, lat, lon) in the output DataFrame",
    )

    @field_validator("variables")
    @classmethod
    def validate_variables(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        return _validate_local_variables(v)


class DownloadQuery(BaseModel):
    """Query model for ``weather-tools local download``.

    SILO NetCDF files are organised as one file per (variable, year), so the
    download surface uses year integers — not a date range — to match the
    granularity of the upstream S3 store.
    """

    model_config = ConfigDict(extra="forbid")

    variables: List[str] = Field(
        default_factory=lambda: list(DEFAULT_DAILY_VARIABLES),
        description=(
            "Climate variables to download (canonical names, e.g. 'daily_rain', "
            "'max_temp', 'monthly_rain'). Repeat the option for multiple."
        ),
    )
    start_year: int = Field(
        ...,
        ge=1889,
        le=2100,
        description="First year to download (inclusive)",
    )
    end_year: int = Field(
        ...,
        ge=1889,
        le=2100,
        description="Last year to download (inclusive)",
    )
    silo_dir: Optional[Path] = Field(
        default=None,
        description="Output directory for downloaded files (defaults to ~/DATA/silo_grids)",
    )

    @field_validator("variables")
    @classmethod
    def validate_variables(cls, v: List[str]) -> List[str]:
        # The Optional-aware helper handles ``None`` too, but DownloadQuery's
        # field is non-Optional; we still funnel through it for one validator.
        result = _validate_local_variables(v)
        # ``v`` is guaranteed non-None here because the field is required-with-default.
        assert result is not None
        return result

    @model_validator(mode="after")
    def validate_year_order(self) -> "DownloadQuery":
        """Ensure start_year <= end_year."""
        if self.start_year > self.end_year:
            raise ValueError(
                f"start_year ({self.start_year}) must be <= end_year ({self.end_year})"
            )
        return self
