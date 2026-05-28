"""Local SILO NetCDF file CLI commands.

The ``extract`` and ``download`` commands are auto-derived from the Pydantic
query models in :mod:`weather_tools.local_models` via :func:`from_pydantic`.
Pure CLI concerns (output path, force overwrite, download timeout) remain as
hand-written Typer options after the model-derived ones.

``info`` is plain Typer because it takes no user-facing query inputs — there's
nothing to validate.
"""

import logging
from pathlib import Path
from typing import Annotated, Optional

import typer
from pydantic import ValidationError

from weather_tools.cli.pydantic_typer import from_pydantic
from weather_tools.config import get_silo_data_dir
from weather_tools.local_models import DEFAULT_DAILY_VARIABLES, DownloadQuery, ExtractQuery
from weather_tools.logging_utils import get_console
from weather_tools.read_silo_xarray import read_silo_xarray
from weather_tools.silo_netcdf import download_netcdf
from weather_tools.variable_register import SiloNetCDFError

logger = logging.getLogger(__name__)

local_app = typer.Typer(
    name="local",
    help="Work with local SILO netCDF files",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# extract — auto-derived from ExtractQuery
# ---------------------------------------------------------------------------


@local_app.command()
@from_pydantic(ExtractQuery, field_aliases={"variables": "--var"})
def extract(
    query: ExtractQuery,
    output: Annotated[
        str, typer.Option("--output", "-o", help="Output CSV filename")
    ] = "weather_data.csv",
) -> None:
    """Extract weather data from local netCDF files for a point and date range.

    The query model (``ExtractQuery``) drives all input validation: coordinates
    must be in the Australian bounding box, dates must be in SILO's
    1889-2100 window, and variable names must exist in the registry.

    Example:
        weather-tools local extract --latitude -27.5 --longitude 153.0 \\
            --start-date 2020-01-01 --end-date 2025-01-01 -o weather.csv
    """
    silo_dir = query.silo_dir if query.silo_dir is not None else get_silo_data_dir()
    variables_to_use = query.variables  # ``None`` → read_silo_xarray default set

    try:
        typer.echo(f"Loading SILO data from: {silo_dir}")
        typer.echo(f"Variables: {variables_to_use or 'default daily set'}")

        with typer.progressbar(length=1, label="Loading SILO dataset...") as progress:
            ds = read_silo_xarray(variables=variables_to_use, silo_dir=silo_dir)
            progress.update(1)

        lat = query.coordinates.latitude
        lon = query.coordinates.longitude
        # The model stores YYYYMMDD; xarray time slicing accepts that form, but ISO
        # reads more naturally in log output.
        start_iso = f"{query.date_range.start_date[:4]}-{query.date_range.start_date[4:6]}-{query.date_range.start_date[6:]}"
        end_iso = f"{query.date_range.end_date[:4]}-{query.date_range.end_date[4:6]}-{query.date_range.end_date[6:]}"

        typer.echo(f"Extracting data for location: lat={lat}, lon={lon}")
        typer.echo(f"Date range: {start_iso} to {end_iso}")

        df = (
            ds.sel(lat=lat, lon=lon, method="nearest", tolerance=query.tolerance)
            .sel(time=slice(start_iso, end_iso))
            .to_dataframe()
            .reset_index()
        )

        # Rename 'time' → 'date' to match the standard point-data column name
        if "time" in df.columns and "date" not in df.columns:
            df = df.rename(columns={"time": "date"})

        if not query.keep_location:
            columns_to_drop = [col for col in ["crs", "lat", "lon"] if col in df.columns]
            if columns_to_drop:
                df = df.drop(columns=columns_to_drop)
                typer.echo(f"🗑️  Dropped location columns: {', '.join(columns_to_drop)}")

        output_path = Path(output)
        df.to_csv(output_path, index=False)

        typer.echo("✅ Data extracted successfully!")
        typer.echo(f"📊 Shape: {df.shape[0]} rows, {df.shape[1]} columns")
        typer.echo(f"💾 Saved to: {output_path.absolute()}")

        if not df.empty:
            typer.echo("\n📋 Preview (first 5 rows):")
            typer.echo(df.head().to_string())

    except ValidationError as e:
        typer.echo("❌ Validation error:", err=True)
        for error in e.errors():
            typer.echo(f"   {error['loc'][0]}: {error['msg']}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# info — no user-facing query inputs; left as plain Typer.
# ---------------------------------------------------------------------------


@local_app.command(name="info")
def local_info(
    silo_dir: Annotated[Optional[Path], typer.Option(help="Path to SILO data directory")] = None,
) -> None:
    """Display information about available local SILO data."""
    if silo_dir is None:
        silo_dir = get_silo_data_dir()

    typer.echo(f"SILO data directory: {silo_dir}")

    if not silo_dir.exists():
        typer.echo(f"❌ Directory does not exist: {silo_dir}", err=True)
        raise typer.Exit(1)

    typer.echo("\n📁 Available variable directories:")
    variable_dirs = [d for d in silo_dir.iterdir() if d.is_dir()]

    if not variable_dirs:
        typer.echo("  No variable directories found")
        return

    for var_dir in sorted(variable_dirs):
        nc_files = list(var_dir.glob("*.nc"))
        typer.echo(f"  📂 {var_dir.name}: {len(nc_files)} files")

        if nc_files:
            years = []
            for file in nc_files:
                # Extract year from filename (assuming format like "2023.variable.nc")
                try:
                    year = file.stem.split(".")[0]
                    if year.isdigit():
                        years.append(int(year))
                except Exception:
                    pass

            if years:
                typer.echo(f"    📅 Years: {min(years)}-{max(years)}")


# ---------------------------------------------------------------------------
# download — auto-derived from DownloadQuery
# ---------------------------------------------------------------------------


@local_app.command()
@from_pydantic(DownloadQuery, field_aliases={"variables": "--var"})
def download(
    query: DownloadQuery,
    force: Annotated[bool, typer.Option(help="Overwrite existing files")] = False,
    timeout: Annotated[int, typer.Option(help="Download timeout in seconds")] = 600,
) -> None:
    """Download SILO gridded NetCDF files from AWS S3.

    Files are organized in the structure expected by ``weather-tools local extract``::

        output_dir/
        ├── daily_rain/
        │   ├── 2020.daily_rain.nc
        │   └── 2021.daily_rain.nc
        ├── max_temp/
        │   └── ...
        └── ...

    By default, existing files are skipped. Use ``--force`` to re-download.

    Examples:
        # Default daily variables for 2020-2023
        weather-tools local download --start-year 2020 --end-year 2023

        # Specific variables
        weather-tools local download --var daily_rain --var max_temp \\
            --start-year 2022 --end-year 2023

        # Custom output directory
        weather-tools local download --var monthly_rain \\
            --start-year 2020 --end-year 2023 \\
            --silo-dir /data/silo_grids
    """
    silo_dir = query.silo_dir if query.silo_dir is not None else get_silo_data_dir()
    # Pydantic guarantees variables is a non-empty list (default factory supplies
    # the daily set). We pass it through directly.
    variables = query.variables or list(DEFAULT_DAILY_VARIABLES)
    console = get_console()

    try:
        download_netcdf(
            variables=variables,
            start_year=query.start_year,
            end_year=query.end_year,
            output_dir=silo_dir,
            force=force,
            timeout=timeout,
            console=console,
        )
    except ValueError as e:
        logger.error(f"[red]❌ Validation error: {e}[/red]")
        raise typer.Exit(1)
    except SiloNetCDFError as e:
        logger.error(f"[red]❌ Download error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        logger.exception(f"[red]❌ Unexpected error: {e}[/red]")
        raise typer.Exit(1)
