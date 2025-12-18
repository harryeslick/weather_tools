"""CLI date parsing helpers.

The Python API and Pydantic models for SILO expect dates in YYYYMMDD format.
The CLI standardizes on ISO dates (YYYY-MM-DD) and converts at the boundary.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

import typer

_ISO_FMT = "%Y-%m-%d"


def parse_iso_date_strict(value: str) -> _dt.date:
    """Parse an ISO date string strictly as YYYY-MM-DD (zero-padded)."""
    try:
        parsed = _dt.datetime.strptime(value, _ISO_FMT).date()
    except (TypeError, ValueError) as exc:
        raise typer.BadParameter("Expected date format: YYYY-MM-DD") from exc

    # Enforce canonical zero-padded ISO input (e.g. reject 2023-1-1)
    if value != parsed.strftime(_ISO_FMT):
        raise typer.BadParameter("Expected date format: YYYY-MM-DD") from None

    return parsed


def iso_date_option(value: Optional[str]) -> Optional[str]:
    """Typer option callback: validate ISO date and return canonical string."""
    if value is None:
        return None
    return parse_iso_date_strict(value).strftime(_ISO_FMT)


def iso_to_silo_yyyymmdd_option(value: Optional[str]) -> Optional[str]:
    """Typer option callback: validate ISO date and return YYYYMMDD for SILO API."""
    if value is None:
        return None
    return parse_iso_date_strict(value).strftime("%Y%m%d")


def silo_yyyymmdd_to_iso(value: str) -> str:
    """Convert a SILO YYYYMMDD string to ISO YYYY-MM-DD (for display)."""
    try:
        parsed = _dt.datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        # Best-effort: if it isn't a SILO date, just return it unchanged.
        return value
    return parsed.strftime(_ISO_FMT)
