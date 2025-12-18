import datetime as dt

import pytest
import typer

from weather_tools.cli.date_utils import (
    iso_date_option,
    iso_to_silo_yyyymmdd_option,
    parse_iso_date_strict,
    silo_yyyymmdd_to_iso,
)


def test_parse_iso_date_strict_valid() -> None:
    assert parse_iso_date_strict("2023-01-01") == dt.date(2023, 1, 1)


@pytest.mark.parametrize("value", ["20230101", "2023/01/01", "01-01-2023", "2023-13-01"])
def test_parse_iso_date_strict_rejects_non_iso(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        parse_iso_date_strict(value)


@pytest.mark.parametrize("value", ["2023-1-01", "2023-01-1", "2023-1-1"])
def test_parse_iso_date_strict_rejects_non_zero_padded(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        parse_iso_date_strict(value)


def test_iso_date_option_returns_canonical_string() -> None:
    assert iso_date_option("2023-01-01") == "2023-01-01"


def test_iso_to_silo_yyyymmdd_option_converts() -> None:
    assert iso_to_silo_yyyymmdd_option("2023-01-31") == "20230131"


def test_silo_yyyymmdd_to_iso_converts_for_display() -> None:
    assert silo_yyyymmdd_to_iso("20230131") == "2023-01-31"

