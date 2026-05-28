"""CLI-level smoke tests for `weather-tools local` commands.

These exercise the @from_pydantic adapter end-to-end via Typer's CliRunner.
The heavy data paths (read_silo_xarray, download_netcdf) are patched so the
tests stay fast and don't require any on-disk SILO data.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest
import xarray as xr
from typer.testing import CliRunner

from weather_tools.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------


def _make_fake_dataset() -> xr.Dataset:
    """Build a tiny xarray dataset that supports nearest-neighbour selection."""
    times = pd.date_range("2023-01-01", "2023-01-03", freq="D")
    lats = [-28.0, -27.5, -27.0]
    lons = [152.5, 153.0, 153.5]
    data = [
        [[i + j + k for k in range(len(lons))] for j in range(len(lats))] for i in range(len(times))
    ]
    return xr.Dataset(
        {"daily_rain": (("time", "lat", "lon"), data)},
        coords={"time": times, "lat": lats, "lon": lons},
    )


class TestExtractCli:
    def test_extract_invokes_read_silo_xarray(self, runner: CliRunner, tmp_path):
        out = tmp_path / "weather.csv"
        ds = _make_fake_dataset()
        with patch("weather_tools.cli.local.read_silo_xarray", return_value=ds) as mock_read:
            result = runner.invoke(
                app,
                [
                    "local",
                    "extract",
                    "--latitude",
                    "-27.5",
                    "--longitude",
                    "153.0",
                    "--start-date",
                    "2023-01-01",
                    "--end-date",
                    "2023-01-03",
                    "--var",
                    "daily_rain",
                    "--silo-dir",
                    str(tmp_path),
                    "-o",
                    str(out),
                ],
            )
        assert result.exit_code == 0, result.output
        mock_read.assert_called_once()
        assert out.exists()
        df = pd.read_csv(out)
        # Default keep_location=False, so lat/lon dropped.
        assert "daily_rain" in df.columns
        assert "lat" not in df.columns

    def test_extract_invalid_latitude(self, runner: CliRunner):
        """Pydantic should reject coordinates outside Australian bounds."""
        result = runner.invoke(
            app,
            [
                "local",
                "extract",
                "--latitude",
                "0.0",
                "--longitude",
                "153.0",
                "--start-date",
                "2023-01-01",
                "--end-date",
                "2023-01-03",
            ],
        )
        assert result.exit_code != 0
        assert "Validation error" in result.output or "validation" in result.output.lower()

    def test_extract_invalid_date_format(self, runner: CliRunner):
        result = runner.invoke(
            app,
            [
                "local",
                "extract",
                "--latitude",
                "-27.5",
                "--longitude",
                "153.0",
                "--start-date",
                "not-a-date",
                "--end-date",
                "2023-01-03",
            ],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------


class TestDownloadCli:
    def test_download_passes_query_fields_through(self, runner: CliRunner, tmp_path):
        with patch("weather_tools.cli.local.download_netcdf", return_value={}) as mock_dl:
            result = runner.invoke(
                app,
                [
                    "local",
                    "download",
                    "--var",
                    "daily_rain",
                    "--start-year",
                    "2020",
                    "--end-year",
                    "2021",
                    "--silo-dir",
                    str(tmp_path),
                ],
            )
        assert result.exit_code == 0, result.output
        mock_dl.assert_called_once()
        kwargs = mock_dl.call_args.kwargs
        assert kwargs["variables"] == ["daily_rain"]
        assert kwargs["start_year"] == 2020
        assert kwargs["end_year"] == 2021
        assert kwargs["output_dir"] == tmp_path
        assert kwargs["force"] is False
        assert kwargs["timeout"] == 600

    def test_download_default_variables(self, runner: CliRunner, tmp_path):
        with patch("weather_tools.cli.local.download_netcdf", return_value={}) as mock_dl:
            result = runner.invoke(
                app,
                [
                    "local",
                    "download",
                    "--start-year",
                    "2020",
                    "--end-year",
                    "2020",
                    "--silo-dir",
                    str(tmp_path),
                ],
            )
        assert result.exit_code == 0, result.output
        assert mock_dl.call_args.kwargs["variables"] == [
            "daily_rain",
            "max_temp",
            "min_temp",
            "evap_syn",
        ]

    def test_download_start_after_end_rejected(self, runner: CliRunner):
        result = runner.invoke(
            app,
            [
                "local",
                "download",
                "--start-year",
                "2025",
                "--end-year",
                "2020",
            ],
        )
        assert result.exit_code != 0
        assert "Validation error" in result.output or "start_year" in result.output

    def test_download_unknown_variable_rejected(self, runner: CliRunner):
        result = runner.invoke(
            app,
            [
                "local",
                "download",
                "--var",
                "not_a_variable",
                "--start-year",
                "2020",
                "--end-year",
                "2020",
            ],
        )
        assert result.exit_code != 0
