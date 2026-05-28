"""Generic date range model used across weather_tools query models.

This is the shared base for any Pydantic query model that needs a date span.
Subclasses (e.g. :class:`weather_tools.silo_models.SiloDateRange`) add
domain-specific constraints like dataset-availability year bounds.

Why this lives in its own module:
- ``silo_models.py`` imports SILO-specific concerns (variable registry, format
  enums). A generic ``DateRange`` shouldn't drag those in.
- Future query models (geotiff downloads, local-file extraction) need the same
  date semantics but live in different modules and shouldn't have to import
  through ``silo_models`` just to get a date range.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DateRange(BaseModel):
    """A pair of dates stored as ``YYYYMMDD`` strings, accepting ISO input.

    User-facing input may be either ``YYYY-MM-DD`` or ``YYYYMMDD``. Both forms
    are normalised to ``YYYYMMDD`` on validation and that's the canonical
    storage form (matches what the SILO HTTP API expects on the wire). The
    Python ``date`` object is intentionally *not* used as storage so the model
    round-trips losslessly through the SILO API without per-call formatting.

    Validation performed by the base class:

    1. Format coercion: ISO strings are normalised before the pattern check.
    2. Pattern: stored value must match ``\\d{8}``.
    3. Month/day plausibility via ``datetime.strptime``.
    4. Ordering: ``start_date <= end_date``.

    Subclasses can layer additional checks (e.g. year bounds for a specific
    dataset's availability window) by overriding ``validate_date`` or by
    adding their own validators. See :class:`SiloDateRange` for an example.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    start_date: str = Field(
        ...,
        pattern=r"^\d{8}$",
        description="Start date in YYYY-MM-DD or YYYYMMDD format (e.g., '2023-01-01')",
    )
    end_date: str = Field(
        ...,
        pattern=r"^\d{8}$",
        description="End date in YYYY-MM-DD or YYYYMMDD format (e.g., '2023-01-31')",
    )

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def normalize_iso_date(cls, v: Any) -> Any:
        """Accept ISO YYYY-MM-DD input and normalise to YYYYMMDD before pattern check."""
        if isinstance(v, str) and len(v) == 10 and v[4] == "-" and v[7] == "-":
            try:
                return datetime.strptime(v, "%Y-%m-%d").strftime("%Y%m%d")
            except ValueError:
                # Fall through and let the strict YYYYMMDD validator emit the error.
                return v
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        """Validate the date has plausible month/day values.

        Year bounds are *not* enforced here — subclasses add those when their
        dataset has a known availability window.
        """
        try:
            dt = datetime.strptime(v, "%Y%m%d")
            if dt.month < 1 or dt.month > 12:
                raise ValueError(f"Date month must be between 01 and 12, got {dt.month}")
            if dt.day < 1 or dt.day > 31:
                raise ValueError(f"Date day must be between 01 and 31, got {dt.day}")
            return v
        except ValueError as e:
            if "does not match format" in str(e):
                raise ValueError(f"Date must be in YYYYMMDD format, got: {v}")
            raise

    @model_validator(mode="after")
    def validate_date_order(self) -> "DateRange":
        """Ensure start_date is before or equal to end_date."""
        if self.start_date > self.end_date:
            raise ValueError(
                f"start_date ({self.start_date}) must be before or equal to end_date "
                f"({self.end_date})"
            )
        return self
