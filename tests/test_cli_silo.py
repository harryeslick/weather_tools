"""CLI tests for SILO station search behavior."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from weather_tools.cli import app
from weather_tools.silo_api import SiloAPI
from weather_tools.silo_models import SiloDataset, SiloFormat, SiloResponse


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_bare_station_performs_exact_lookup_with_table_output(runner: CliRunner):
    """A station code without radius should use ID lookup and standard table formatting."""
    response = SiloResponse(
        raw_data=(
            " 73142|COOTAMUNDRA AIRPORT                      | -34.630| 148.036|"
            "NSW |  335.0|Climate \n"
        ),
        format=SiloFormat.ID,
        dataset=SiloDataset.PATCHED_POINT,
    )

    with (
        patch.object(SiloAPI, "__init__", return_value=None),
        patch.object(SiloAPI, "query_patched_point", return_value=response) as query_method,
    ):
        result = runner.invoke(app, ["silo", "search", "--station", "73142"])

    assert result.exit_code == 0, result.output
    query = query_method.call_args.args[0]
    assert query.format == SiloFormat.ID
    assert query.station_code == "73142"
    assert "station_code" in result.output
    assert "COOTAMUNDRA AIRPORT" in result.output
    assert "Climate" not in result.output


def test_search_help_does_not_offer_details(runner: CliRunner):
    """The breaking CLI release should remove the redundant details option."""
    result = runner.invoke(app, ["silo", "search", "--help"])

    assert result.exit_code == 0, result.output
    assert "--details" not in result.output
