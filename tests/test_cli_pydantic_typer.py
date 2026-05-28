"""Unit tests for cli/pydantic_typer.py — the Pydantic → Typer adapter."""

from __future__ import annotations

import inspect
from typing import Annotated, Optional

import pytest
import typer
from typer.testing import CliRunner

from weather_tools.cli.pydantic_typer import from_pydantic
from weather_tools.silo_models import (
    DataDrillQuery,
    PatchedPointQuery,
    SiloFormat,
)

# ---------------------------------------------------------------------------
# Signature shape — what Typer sees after the decorator runs
# ---------------------------------------------------------------------------


class TestSignatureRewrite:
    """The decorator must expose flattened CLI params on the wrapped function."""

    def test_patched_point_signature_includes_flattened_date_range(self):
        @from_pydantic(
            PatchedPointQuery,
            format_choices={
                SiloFormat.CSV,
                SiloFormat.JSON,
                SiloFormat.APSIM,
                SiloFormat.STANDARD,
            },
            field_aliases={"variables": "--var"},
            skip={"radius", "name_fragment"},
        )
        def cmd(query: PatchedPointQuery) -> None:
            pass

        names = list(inspect.signature(cmd).parameters)
        # date_range is flattened, dataset is frozen-skipped, radius/name_fragment
        # are explicitly skipped.
        assert "start_date" in names
        assert "end_date" in names
        assert "date_range" not in names
        assert "dataset" not in names
        assert "radius" not in names
        assert "name_fragment" not in names
        assert "query" not in names  # consumed by the wrapper

    def test_data_drill_signature_flattens_coordinates_and_date_range(self):
        @from_pydantic(DataDrillQuery, format_choices={SiloFormat.CSV})
        def cmd(query: DataDrillQuery) -> None:
            pass

        names = list(inspect.signature(cmd).parameters)
        assert {"latitude", "longitude", "start_date", "end_date"}.issubset(names)
        assert "coordinates" not in names
        assert "date_range" not in names

    def test_cli_only_extras_preserved_after_model_params(self):
        @from_pydantic(PatchedPointQuery, skip={"radius", "name_fragment"})
        def cmd(query: PatchedPointQuery, api_key: Optional[str] = None) -> None:
            pass

        params = list(inspect.signature(cmd).parameters)
        # CLI-only params come after model-derived ones.
        assert "api_key" in params
        assert params.index("api_key") > params.index("station_code")


# ---------------------------------------------------------------------------
# Enum narrowing — only allowed formats appear in --help
# ---------------------------------------------------------------------------


class TestEnumNarrowing:
    """format_choices must restrict the Typer enum to the allowed subset."""

    def test_format_choices_restrict_enum(self):
        app = typer.Typer()

        @app.command()
        @from_pydantic(
            PatchedPointQuery,
            format_choices={SiloFormat.CSV, SiloFormat.APSIM},
            skip={"radius", "name_fragment"},
        )
        def cmd(query: PatchedPointQuery) -> None:  # pragma: no cover
            pass

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # The subset enum's values appear in the help; the excluded ones do not.
        assert "csv" in result.output
        assert "apsim" in result.output
        assert "json" not in result.output.split("--format")[1].split("\n\n")[0]


# ---------------------------------------------------------------------------
# Reassembly — kwargs round-trip into a valid Pydantic instance
# ---------------------------------------------------------------------------


class TestReassembly:
    """The wrapper must reconstruct the model from flat kwargs."""

    def test_patched_point_round_trip(self):
        captured: dict = {}

        @from_pydantic(
            PatchedPointQuery,
            format_choices={SiloFormat.CSV, SiloFormat.JSON, SiloFormat.APSIM, SiloFormat.STANDARD},
            field_aliases={"variables": "--var"},
            skip={"radius", "name_fragment"},
        )
        def cmd(query: PatchedPointQuery) -> None:
            captured["query"] = query

        # Call via kwargs (what Typer would do after parsing).
        cmd(
            format=SiloFormat.CSV,
            variables=["daily_rain"],
            station_code="30043",
            start_date="2023-01-01",
            end_date="2023-01-31",
        )
        q = captured["query"]
        assert isinstance(q, PatchedPointQuery)
        assert q.station_code == "30043"
        assert q.date_range is not None
        assert q.date_range.start_date == "20230101"  # ISO normalised by model
        assert q.date_range.end_date == "20230131"
        assert q.variables == ["daily_rain"]
        assert q.format == "csv"

    def test_data_drill_round_trip(self):
        captured: dict = {}

        @from_pydantic(
            DataDrillQuery,
            format_choices={
                SiloFormat.CSV,
                SiloFormat.APSIM,
                SiloFormat.ALLDATA,
                SiloFormat.STANDARD,
            },
        )
        def cmd(query: DataDrillQuery) -> None:
            captured["query"] = query

        cmd(
            format=SiloFormat.ALLDATA,
            variables=None,
            latitude=-27.5,
            longitude=151.0,
            start_date="2023-01-01",
            end_date="2023-01-31",
        )
        q = captured["query"]
        assert isinstance(q, DataDrillQuery)
        assert q.coordinates.latitude == -27.5
        assert q.coordinates.longitude == 151.0
        assert q.date_range.start_date == "20230101"
        assert q.format == "alldata"

    def test_extras_passed_through(self):
        captured: dict = {}

        @from_pydantic(PatchedPointQuery, skip={"radius", "name_fragment"})
        def cmd(query: PatchedPointQuery, api_key: Optional[str] = None) -> None:
            captured["query"] = query
            captured["api_key"] = api_key

        cmd(
            format=SiloFormat.CSV,
            variables=["daily_rain"],
            station_code="30043",
            start_date="20230101",
            end_date="20230131",
            api_key="user@example.com",
        )
        assert captured["api_key"] == "user@example.com"
        assert captured["query"].station_code == "30043"


# ---------------------------------------------------------------------------
# End-to-end via Typer CliRunner — the real integration test
# ---------------------------------------------------------------------------


class TestThroughTyper:
    """Drive the decorator through Typer to confirm option parsing works."""

    def test_typer_invokes_wrapped_function(self):
        captured: dict = {}

        app = typer.Typer()

        @app.command()
        @from_pydantic(
            PatchedPointQuery,
            format_choices={SiloFormat.CSV, SiloFormat.JSON, SiloFormat.APSIM, SiloFormat.STANDARD},
            field_aliases={"variables": "--var"},
            skip={"radius", "name_fragment"},
        )
        def cmd(
            query: PatchedPointQuery,
            api_key: Annotated[Optional[str], typer.Option()] = None,
        ) -> None:
            captured["query"] = query
            captured["api_key"] = api_key

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "--station-code",
                "30043",
                "--start-date",
                "2023-01-01",
                "--end-date",
                "2023-01-31",
                "--var",
                "daily_rain",
                "--var",
                "max_temp",
                "--api-key",
                "user@example.com",
            ],
        )
        assert result.exit_code == 0, result.output
        q = captured["query"]
        assert q.station_code == "30043"
        assert q.date_range.start_date == "20230101"
        assert q.variables == ["daily_rain", "max_temp"]
        assert captured["api_key"] == "user@example.com"


# ---------------------------------------------------------------------------
# Regression: ``from __future__ import annotations`` must not silently strip
# ``typer.Option(...)`` metadata from CLI-only extras.
# ---------------------------------------------------------------------------


class TestForwardRefExtras:
    """Extras carrying string-form Annotated metadata must still reach Typer.

    Modules that use ``from __future__ import annotations`` have all their
    type hints stored as strings. Without resolving them via
    ``typing.get_type_hints(..., include_extras=True)`` the adapter would
    hand Typer a string like ``"Annotated[Optional[str], typer.Option(...)]"``
    that Typer can't evaluate — silently dropping the help text, envvar, and
    flag aliases. This test exercises the resolution path.
    """

    def test_extras_with_stringified_annotations_keep_option_metadata(self):
        # Module-level test helper to ensure annotations are stringified the
        # same way they would be under ``from __future__ import annotations``.
        # We can't easily flip the import in the test file itself, so we build
        # the function dynamically with explicit string annotations.
        import builtins

        captured: dict = {}

        def cmd(
            query: PatchedPointQuery,
            api_key: "Annotated[Optional[str], typer.Option('--api-key', envvar='SILO_API_KEY', help='SILO key')]" = None,  # noqa: F722
        ) -> None:
            captured["query"] = query
            captured["api_key"] = api_key

        # Make the names referenced in the forward-ref string resolvable.
        cmd.__globals__.update(
            {
                "Annotated": Annotated,
                "Optional": Optional,
                "typer": typer,
                "builtins": builtins,
            }
        )

        decorated = from_pydantic(
            PatchedPointQuery,
            field_aliases={"variables": "--var"},
            skip={"radius", "name_fragment"},
        )(cmd)

        app = typer.Typer()
        app.command()(decorated)

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "--station-code",
                "30043",
                "--start-date",
                "2023-01-01",
                "--end-date",
                "2023-01-31",
                "--api-key",
                "via-flag@example.com",
            ],
        )
        assert result.exit_code == 0, result.output
        assert captured["api_key"] == "via-flag@example.com"

        # And the help text must surface the resolved Option metadata, proving
        # the string-form annotation was evaluated rather than passed through.
        help_result = runner.invoke(app, ["--help"])
        assert help_result.exit_code == 0
        assert "SILO key" in help_result.output
