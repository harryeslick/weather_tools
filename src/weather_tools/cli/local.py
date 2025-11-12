"""Local SILO NetCDF file CLI commands."""

import logging
from pathlib import Path
from typing import Annotated, Optional, Union

import pandas as pd
import typer
from typing_extensions import List

from weather_tools.config import get_silo_data_dir
from weather_tools.logging_utils import get_console
from weather_tools.read_silo_xarray import read_silo_xarray
from weather_tools.silo_netcdf import download_netcdf
from weather_tools.silo_variables import SiloNetCDFError, VariableName

logger = logging.getLogger(__name__)

local_app = typer.Typer(
    name="local",
    help="Work with local SILO netCDF files",
    no_args_is_help=True,
)

@local_app.command()
def extract(
    lat: Annotated[float, typer.Option(help="Latitude coordinate")],
    lon: Annotated[float, typer.Option(help="Longitude coordinate")],
    start_date: Annotated[str, typer.Option(help="Start date (YYYY-MM-DD format)")],
    end_date: Annotated[str, typer.Option(help="End date (YYYY-MM-DD format)")],
    output: Annotated[str, typer.Option(help="Output CSV filename")] = "weather_data.csv",
    variables: Annotated[
        Optional[List[str]],
        typer.Option(
            help="Weather variables to extract. Use 'daily' or 'monthly' for presets, or specify individual variables"
        ),
    ] = None,
    silo_dir: Annotated[Optional[Path], typer.Option(help="Path to SILO data directory")] = None,
    tolerance: Annotated[
        float, typer.Option(help="Maximum distance (in degrees) for nearest neighbor selection")
    ] = 0.1,
    keep_location: Annotated[bool, typer.Option(help="Keep location columns (crs, lat, lon) in output CSV")] = False,
) -> None:
    """
    Extract weather data from local netCDF files for a specific location and date range.

    Example:
        weather-tools local extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2025-01-01 --output weather.csv
    """
    # Set default values and process variables
    variables_to_use: Union[str, List[str]]
    if variables is None:
        variables_to_use = "daily"
    elif len(variables) == 1 and variables[0].lower() in ["daily", "monthly"]:
        variables_to_use = variables[0].lower()
    else:
        variables_to_use = variables

    if silo_dir is None:
        silo_dir = get_silo_data_dir()

    try:
        # Validate date formats
        pd.to_datetime(start_date)
        pd.to_datetime(end_date)

        typer.echo(f"Loading SILO data from: {silo_dir}")
        typer.echo(f"Variables: {variables_to_use}")

        # Load the dataset
        with typer.progressbar(length=1, label="Loading SILO dataset...") as progress:
            ds = read_silo_xarray(variables=variables_to_use, silo_dir=silo_dir)
            progress.update(1)

        typer.echo(f"Extracting data for location: lat={lat}, lon={lon}")
        typer.echo(f"Date range: {start_date} to {end_date}")

        # Extract data for the specified location and date range
        df = (
            ds.sel(lat=lat, lon=lon, method="nearest", tolerance=tolerance)
            .sel(time=slice(start_date, end_date))
            .to_dataframe()
            .reset_index()
        )

        # Drop location columns by default unless --keep-location is specified
        if not keep_location:
            columns_to_drop = [col for col in ["crs", "lat", "lon"] if col in df.columns]
            if columns_to_drop:
                df = df.drop(columns=columns_to_drop)
                typer.echo(f"🗑️  Dropped location columns: {', '.join(columns_to_drop)}")

        # Save to CSV
        output_path = Path(output)
        df.to_csv(output_path, index=False)

        typer.echo("✅ Data extracted successfully!")
        typer.echo(f"📊 Shape: {df.shape[0]} rows, {df.shape[1]} columns")
        typer.echo(f"💾 Saved to: {output_path.absolute()}")

        # Show a preview of the data
        if not df.empty:
            typer.echo("\n📋 Preview (first 5 rows):")
            typer.echo(df.head().to_string())

    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@local_app.command(name="info")
def local_info(
    silo_dir: Annotated[Optional[Path], typer.Option(help="Path to SILO data directory")] = None,
) -> None:
    """
    Display information about available local SILO data.
    """
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


@local_app.command()
def download(
    start_year: Annotated[int, typer.Option(help="First year to download (inclusive)")],
    end_year: Annotated[int, typer.Option(help="Last year to download (inclusive)")],
    variables: Annotated[
        Optional[VariableName],
        typer.Option(
            "--var",
            help="Variable names (daily_rain, max_temp, etc.) or presets (daily, monthly). Can specify multiple.",
        ),
    ] = None,
    silo_dir: Annotated[Optional[Path], typer.Option(help="Output directory for downloaded files")] = None,
    force: Annotated[bool, typer.Option(help="Overwrite existing files")] = False,
    timeout: Annotated[int, typer.Option(help="Download timeout in seconds")] = 600,
) -> None:
    """
    Download SILO gridded NetCDF files from AWS S3.

    Files are organized in the same structure expected by 'weather-tools local extract':
        output_dir/
        ├── daily_rain/
        │   ├── 2020.daily_rain.nc
        │   └── 2021.daily_rain.nc
        ├── max_temp/
        │   └── ...
        └── ...

    By default, existing files are skipped. Use --force to re-download.

    Examples:
        # Download daily variables for 2020-2023
        weather-tools local download --var daily --start-year 2020 --end-year 2023

        # Download specific variables
        weather-tools local download --var daily_rain --var max_temp \\
            --start-year 2022 --end-year 2023

        # Download to custom directory
        weather-tools local download --var monthly \\
            --start-year 2020 --end-year 2023 \\
            --silo-dir /data/silo_grids

        # Force re-download existing files
        weather-tools local download --var daily_rain \\
            --start-year 2023 --end-year 2023 --force
    """
    # Set defaults
    if variables is None:
        variables = ["daily"]

    if silo_dir is None:
        silo_dir = get_silo_data_dir()

    console = get_console()

    try:
        download_netcdf(
            variables=variables,
            start_year=start_year,
            end_year=end_year,
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

