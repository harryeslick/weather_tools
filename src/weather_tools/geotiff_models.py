"""Pydantic models for SILO GeoTIFF download requests.

This module exposes :class:`GeoTiffDownloadQuery`, the Pydantic-first query model
that drives the ``weather-tools geotiff download`` CLI command. The model owns
field names, types, defaults, validation, and help text for the parts of a
GeoTIFF download request that fit a flat parameter shape (variables, date
range, output directory, force flag).

Spatial inputs — ``--bbox`` and ``--geometry`` — intentionally do *not* live on
this model. They form a tagged union with file-loading side effects that don't
flatten cleanly through the ``@from_pydantic`` adapter's one-level nesting
contract; the CLI resolves them into a shapely geometry before constructing the
model. Keeping the model focused on what *does* fit the pattern avoids
inverting the simplification the pattern is meant to deliver.

The module lives next to :mod:`weather_tools.silo_geotiff` rather than inside
it because the file is already large and mixes URL builders, COG readers, and
the download orchestrator; a separate models module mirrors the
``silo_models.py`` / ``silo_api.py`` split.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from weather_tools.silo_models import SiloDateRange
from weather_tools.variable_register import VARIABLES


class GeoTiffDownloadQuery(BaseModel):
    """Query parameters for a SILO GeoTIFF batch download.

    Examples:
        >>> query = GeoTiffDownloadQuery(
        ...     variables=["daily_rain"],
        ...     date_range=SiloDateRange(start_date="2023-01-01", end_date="2023-01-31"),
        ... )

        >>> query = GeoTiffDownloadQuery(
        ...     variables=["daily_rain", "max_temp"],
        ...     date_range=SiloDateRange(start_date="20230101", end_date="20230131"),
        ...     output_dir=Path("./data"),
        ...     force=True,
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    variables: List[str] = Field(
        default=["daily_rain"],
        description=(
            "Variable names (daily_rain, max_temp, etc.). Specify each variable "
            "explicitly; repeat the option for multiple."
        ),
    )
    date_range: SiloDateRange = Field(
        ...,
        description="Date range for the GeoTIFF download (YYYY-MM-DD or YYYYMMDD)",
    )
    output_dir: Optional[Path] = Field(
        default=None,
        description=(
            "Output directory for downloaded GeoTIFF files "
            "(default: $SILO_DATA_DIR/geotiff, typically ~/DATA/silo_grids/geotiff)"
        ),
    )
    force: bool = Field(default=False, description="Overwrite existing files")

    @field_validator("variables")
    @classmethod
    def validate_variables(cls, v: List[str]) -> List[str]:
        """Reject unknown variable names against the central registry.

        Mirrors the validation done by :func:`silo_geotiff.download_geotiffs`
        via ``VARIABLES.validate``, but raises ``ValueError`` (which Pydantic
        wraps in ``ValidationError``) so the failure surfaces at model
        construction rather than deep inside the download orchestrator.
        """
        if not v:
            raise ValueError("At least one variable must be specified")
        unknown = [name for name in v if name not in VARIABLES]
        if unknown:
            valid_names = ", ".join(sorted(VARIABLES.keys()))
            raise ValueError(f"Unknown variables: {unknown}. Valid names: {valid_names}")
        return v
