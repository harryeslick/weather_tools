"""SILO API CLI commands.

The ``patched-point`` and ``data-drill`` commands are thin downloaders: they
build a Pydantic query from CLI options (auto-derived from ``PatchedPointQuery``
/ ``DataDrillQuery`` via :func:`from_pydantic`), call the low-level API, and
write the raw SILO response body to disk. There is no format-driven branching
and no DataFrame round-trip — the CLI is a downloader, not a data adapter.

For analysis use cases (pandas DataFrames + metadata) use the Python API:
``SiloAPI().get_patched_point(...)`` and ``SiloAPI().get_data_drill(...)``.
"""

import json
import logging
from pathlib import Path
from typing import Annotated, Literal, Optional

import typer
from pydantic import ValidationError

from weather_tools.cli.pydantic_typer import from_pydantic
from weather_tools.config import get_cache_dir
from weather_tools.silo_api import SiloAPI, SiloAPIError
from weather_tools.silo_models import (
    DataDrillQuery,
    PatchedPointQuery,
    SiloFormat,
    SiloResponse,
)

logger = logging.getLogger(__name__)

silo_app = typer.Typer(
    name="silo",
    help="Query SILO API directly (requires API key)",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Format → output-extension mapping. The CLI coerces --output's extension to
# match --format so users don't end up with foo.json containing CSV bytes.
# ---------------------------------------------------------------------------

_FORMAT_EXTENSIONS: dict[SiloFormat, str] = {
    SiloFormat.CSV: ".csv",
    SiloFormat.JSON: ".json",
    SiloFormat.APSIM: ".apsim",
    SiloFormat.STANDARD: ".txt",
    SiloFormat.ALLDATA: ".txt",
}

_PATCHED_POINT_DATA_FORMATS = {
    SiloFormat.CSV,
    SiloFormat.JSON,
    SiloFormat.APSIM,
    SiloFormat.STANDARD,
}
_DATA_DRILL_DATA_FORMATS = {
    SiloFormat.CSV,
    SiloFormat.JSON,
    SiloFormat.APSIM,
    SiloFormat.ALLDATA,
    SiloFormat.STANDARD,
}


def _resolve_output_path(output: Optional[str], format: SiloFormat) -> Optional[Path]:
    """Coerce ``output``'s extension to match the SILO response format.

    Returns ``None`` if no output path was supplied. Otherwise returns a Path
    whose suffix matches :data:`_FORMAT_EXTENSIONS`, replacing any existing
    suffix or appending one if the user gave a bare filename.
    """
    if not output:
        return None
    path = Path(output)
    expected = _FORMAT_EXTENSIONS.get(format)
    if expected is None:
        return path
    if path.suffix.lower() != expected:
        path = path.with_suffix(expected)
    return path


def _materialise_response(response: SiloResponse) -> str:
    """Turn a SILO response body into text for writing to disk verbatim.

    JSON responses come back as dicts (parsed in ``SiloAPI._parse_response``);
    everything else is already text. We re-serialise JSON with ``json.dumps``
    so the on-disk file preserves SILO's native response shape rather than a
    pandas-flattened approximation.
    """
    raw = response.raw_data
    if isinstance(raw, str):
        return raw
    return json.dumps(raw, indent=2)


def _write_or_echo(text: str, output_path: Optional[Path]) -> None:
    """Write the response to disk if a path was given, otherwise echo (truncated)."""
    if output_path:
        output_path.write_text(text)
        typer.echo(f"💾 Saved to: {output_path.absolute()}")
        return
    typer.echo("\n📄 Result:")
    if len(text) > 500:
        typer.echo(text[:500] + "\n... (truncated)")
    else:
        typer.echo(text)


def _build_api(
    api_key: Optional[str],
    enable_cache: bool,
    cache_dir: Optional[str],
    log_level: str,
) -> SiloAPI:
    """Construct the API client from CLI-only knobs."""
    cache_kwargs: dict = {"enable_cache": enable_cache}
    if cache_dir:
        cache_kwargs["cache_dir"] = cache_dir
    if api_key:
        return SiloAPI(api_key=api_key, log_level=log_level, **cache_kwargs)
    return SiloAPI(log_level=log_level, **cache_kwargs)


def _report_cache(api: SiloAPI, enable_cache: bool) -> None:
    if not enable_cache:
        return
    disk_usage = api.get_cache_disk_usage()
    typer.echo(
        f"📦 Cache: {api.get_cache_size()} entries"
        f"{f', {disk_usage / 1024:.1f} KB on disk' if disk_usage else ''}. "
        "Clear with: weather-tools silo cache --clear"
    )


# ---------------------------------------------------------------------------
# patched-point — auto-derived from PatchedPointQuery
# ---------------------------------------------------------------------------


@silo_app.command(name="patched-point")
@from_pydantic(
    PatchedPointQuery,
    format_choices=_PATCHED_POINT_DATA_FORMATS,
    field_aliases={"variables": "--var"},
    skip={"radius", "name_fragment"},
)
def silo_patched_point(
    query: PatchedPointQuery,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output filename")] = None,
    api_key: Annotated[
        Optional[str], typer.Option(envvar="SILO_API_KEY", help="SILO API key (email address)")
    ] = None,
    enable_cache: Annotated[bool, typer.Option(help="Enable response caching")] = False,
    cache_dir: Annotated[
        Optional[str],
        typer.Option(
            "--cache-dir", help="Cache directory (default: ~/.cache/weather_tools/silo_api)"
        ),
    ] = None,
    log_level: Annotated[
        str,
        typer.Option("--log-level", help="Logging level for SILO client (e.g. INFO, DEBUG)"),
    ] = "INFO",
) -> None:
    """Download SILO PatchedPoint data (station observations with infilled gaps).

    Variables, station, dates, and format come from the underlying
    ``PatchedPointQuery`` model — that's the single source of truth for what's
    valid. The response body is written to ``--output`` verbatim; for JSON, the
    file contains SILO's native shape (with metadata block) rather than a
    pandas-flattened approximation.

    Use ``weather-tools silo search`` to find station codes by name.

    Examples:

        weather-tools silo patched-point --station-code 30043 \\
            --start-date 2023-01-01 --end-date 2023-01-31 \\
            --var daily_rain --var max_temp -o data.csv

        weather-tools silo patched-point --station-code 30043 \\
            --start-date 2023-01-01 --end-date 2023-01-31 \\
            --format apsim -o data.apsim
    """
    try:
        output_path = _resolve_output_path(output, SiloFormat(query.format))
        api = _build_api(api_key, enable_cache, cache_dir, log_level)

        typer.echo("🌐 Querying SILO PatchedPoint dataset...")
        typer.echo(f"   Station: {query.station_code}")
        if query.date_range is not None:
            typer.echo(
                f"   Date Range: {query.date_range.start_date} → {query.date_range.end_date}"
            )
        typer.echo(f"   Format: {query.format}")

        response = api.query_patched_point(query)
        typer.echo("✅ Query successful!")

        _write_or_echo(_materialise_response(response), output_path)
        _report_cache(api, enable_cache)

    except ValidationError as e:
        typer.echo("❌ Validation error:", err=True)
        for error in e.errors():
            typer.echo(f"   {error['loc'][0]}: {error['msg']}", err=True)
        raise typer.Exit(1)
    except SiloAPIError as e:
        typer.echo(f"❌ API Error: {e}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# data-drill — auto-derived from DataDrillQuery
# ---------------------------------------------------------------------------


@silo_app.command(name="data-drill")
@from_pydantic(
    DataDrillQuery,
    format_choices=_DATA_DRILL_DATA_FORMATS,
    field_aliases={"variables": "--var"},
)
def silo_data_drill(
    query: DataDrillQuery,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output filename")] = None,
    api_key: Annotated[
        Optional[str], typer.Option(envvar="SILO_API_KEY", help="SILO API key (email address)")
    ] = None,
    enable_cache: Annotated[bool, typer.Option(help="Enable response caching")] = False,
    cache_dir: Annotated[
        Optional[str],
        typer.Option(
            "--cache-dir", help="Cache directory (default: ~/.cache/weather_tools/silo_api)"
        ),
    ] = None,
    log_level: Annotated[
        str,
        typer.Option("--log-level", help="Logging level for SILO client (e.g. INFO, DEBUG)"),
    ] = "INFO",
) -> None:
    """Download SILO DataDrill data (gridded data interpolated to any lat/lon).

    Examples:

        weather-tools silo data-drill --latitude -27.5 --longitude 151.0 \\
            --start-date 2023-01-01 --end-date 2023-01-31 \\
            --var daily_rain -o data.csv

        weather-tools silo data-drill --latitude -27.5 --longitude 151.0 \\
            --start-date 2023-01-01 --end-date 2023-01-31 \\
            --format alldata -o data.txt
    """
    try:
        output_path = _resolve_output_path(output, SiloFormat(query.format))
        api = _build_api(api_key, enable_cache, cache_dir, log_level)

        typer.echo("🌐 Querying SILO DataDrill dataset...")
        typer.echo(f"   Location: {query.coordinates.latitude}°, {query.coordinates.longitude}°")
        typer.echo(f"   Date Range: {query.date_range.start_date} → {query.date_range.end_date}")
        typer.echo(f"   Format: {query.format}")

        response = api.query_data_drill(query)
        typer.echo("✅ Query successful!")

        _write_or_echo(_materialise_response(response), output_path)
        _report_cache(api, enable_cache)

    except ValidationError as e:
        typer.echo("❌ Validation error:", err=True)
        for error in e.errors():
            typer.echo(f"   {error['loc'][0]}: {error['msg']}", err=True)
        raise typer.Exit(1)
    except SiloAPIError as e:
        typer.echo(f"❌ API Error: {e}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# search — uses PatchedPointQuery directly (NAME/NEAR/ID formats). Kept as-is
# because it already follows the Pydantic-first pattern.
# ---------------------------------------------------------------------------


@silo_app.command(name="search")
def silo_search(
    name: Annotated[
        Optional[str], typer.Option(help="Search for stations by name fragment (e.g., 'Brisbane')")
    ] = None,
    station: Annotated[
        Optional[str], typer.Option(help="Station code for nearby search or details lookup")
    ] = None,
    lat: Annotated[
        Optional[float], typer.Option(help="Latitude for location-based search (e.g., -27.47)")
    ] = None,
    lon: Annotated[
        Optional[float], typer.Option(help="Longitude for location-based search (e.g., 153.03)")
    ] = None,
    radius: Annotated[Optional[int], typer.Option(help="Search radius in km (default 50)")] = None,
    state: Annotated[
        Optional[Literal["QLD", "NSW", "VIC", "TAS", "SA", "WA", "NT", "ACT"]],
        typer.Option(help="Filter by state (QLD, NSW, VIC, TAS, SA, WA, NT, ACT)"),
    ] = None,
    details: Annotated[bool, typer.Option(help="Get detailed info for a specific station")] = False,
    api_key: Annotated[
        Optional[str], typer.Option(envvar="SILO_API_KEY", help="SILO API key (email address)")
    ] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output filename")] = None,
    log_level: Annotated[
        str,
        typer.Option("--log-level", help="Logging level for SILO client (e.g. INFO, DEBUG)"),
    ] = "INFO",
) -> None:
    """Search for SILO stations by name, location, or find nearby stations.

    Examples:

        weather-tools silo search --name Brisbane
        weather-tools silo search --name Brisbane --state QLD
        weather-tools silo search --lat -27.47 --lon 153.03
        weather-tools silo search --lat -27.47 --lon 153.03 --radius 20 --name Airport
        weather-tools silo search --station 30043 --radius 50
        weather-tools silo search --station 30043 --details
    """
    try:
        if api_key:
            api = SiloAPI(api_key=api_key, log_level=log_level)
        else:
            api = SiloAPI(log_level=log_level)

        if details and station:
            typer.echo(f"ℹ️ Getting details for station {station}...")
            query = PatchedPointQuery(format=SiloFormat.ID, station_code=station)
            response = api.query_patched_point(query)
            typer.echo("✅ Search successful!")
            if output:
                output_path = Path(output)
                output_path.write_text(response.to_csv())
                typer.echo(f"💾 Saved to: {output_path.absolute()}")
            else:
                typer.echo("\n📍 Results:")
                typer.echo(response.to_csv())

        elif lat is not None and lon is not None:
            search_radius = radius if radius is not None else 50
            typer.echo(f"🔍 Searching for stations within {search_radius}km of ({lat}, {lon})...")
            if name:
                typer.echo(f"   Filtering by name: '{name}'")
            df = api.search_stations_by_location(
                latitude=lat,
                longitude=lon,
                radius_km=search_radius,
                name_fragment=name,
            )
            typer.echo(f"✅ Found {len(df)} station(s)!")
            if output:
                output_path = Path(output)
                df.to_csv(output_path, index=False)
                typer.echo(f"💾 Saved to: {output_path.absolute()}")
            else:
                typer.echo("\n📍 Results:")
                typer.echo(df.to_string(index=False))

        elif lat is not None or lon is not None:
            typer.echo("❌ Error: Both --lat and --lon are required for location search", err=True)
            raise typer.Exit(1)

        elif name:
            typer.echo(f"🔍 Searching for stations matching '{name}'...")
            if state:
                typer.echo(f"   Filtering by state: {state}")
            df = api.search_stations(name_fragment=name, state=state)
            typer.echo(f"✅ Found {len(df)} station(s)!")
            if output:
                output_path = Path(output)
                df.to_csv(output_path, index=False)
                typer.echo(f"💾 Saved to: {output_path.absolute()}")
            else:
                typer.echo("\n📍 Results:")
                typer.echo(df.to_string(index=False))

        elif station and radius is not None:
            typer.echo(f"🔍 Searching for stations near {station} within {radius}km...")
            df = api.search_stations(station_code=station, radius_km=radius)
            typer.echo(f"✅ Found {len(df)} station(s)!")
            if output:
                output_path = Path(output)
                df.to_csv(output_path, index=False)
                typer.echo(f"💾 Saved to: {output_path.absolute()}")
            else:
                typer.echo("\n📍 Results:")
                typer.echo(df.to_string(index=False))

        else:
            typer.echo(
                "❌ Error: Provide --name for name search, --lat --lon for location search, "
                "--station --radius for nearby search, or --station --details for info",
                err=True,
            )
            raise typer.Exit(1)

    except ValidationError as e:
        typer.echo("❌ Validation error:", err=True)
        for error in e.errors():
            typer.echo(f"   {error['loc'][0]}: {error['msg']}", err=True)
        raise typer.Exit(1)
    except SiloAPIError as e:
        typer.echo(f"❌ API Error: {e}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# cache — unchanged CLI plumbing
# ---------------------------------------------------------------------------


@silo_app.command(name="cache")
def silo_cache(
    clear: Annotated[bool, typer.Option("--clear", help="Clear all cached API responses")] = False,
    cache_dir: Annotated[
        Optional[str],
        typer.Option(
            "--cache-dir", help="Cache directory (default: ~/.cache/weather_tools/silo_api)"
        ),
    ] = None,
) -> None:
    """View or manage the SILO API response cache.

    Examples:

        weather-tools silo cache
        weather-tools silo cache --clear
    """
    import diskcache

    cache_path = Path(cache_dir) if cache_dir else get_cache_dir() / "silo_api"

    if not cache_path.exists():
        typer.echo(f"📦 Cache directory: {cache_path}")
        typer.echo("   No cache found (directory does not exist)")
        return

    cache = diskcache.Cache(str(cache_path))

    if clear:
        count = len(cache)
        cache.clear()
        cache.close()
        typer.echo(f"🗑️  Cleared {count} cached entries from {cache_path}")
    else:
        typer.echo(f"📦 Cache directory: {cache_path}")
        typer.echo(f"   Entries: {len(cache)}")
        typer.echo(f"   Disk usage: {cache.volume() / 1024:.1f} KB")
        cache.close()
