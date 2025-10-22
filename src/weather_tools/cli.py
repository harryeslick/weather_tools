"""Command-line interface for weather_tools."""

import datetime
from pathlib import Path
from typing import Annotated, Optional, Union

import pandas as pd
import typer
from typing_extensions import List
from rich.console import Console

from weather_tools.read_silo_xarray import read_silo_xarray
from weather_tools.silo_api import SiloAPI, SiloAPIError
from weather_tools.download_silo import download_silo_gridded, SiloDownloadError
from weather_tools.silo_geotiff import download_geotiff_range, SiloGeoTiffError

app = typer.Typer(
    name="weather-tools",
    help="CLI tool for extracting weather data from SILO datasets (local netCDF files or API)",
    no_args_is_help=True,
)

# Create subapp for SILO API commands
silo_app = typer.Typer(
    name="silo",
    help="Query SILO API directly (requires API key)",
    no_args_is_help=True,
)
app.add_typer(silo_app, name="silo")

# Create subapp for local netCDF file commands
local_app = typer.Typer(
    name="local",
    help="Work with local SILO netCDF files",
    no_args_is_help=True,
)
app.add_typer(local_app, name="local")

# Create subapp for GeoTIFF commands
geotiff_app = typer.Typer(
    name="geotiff",
    help="Work with SILO Cloud-Optimized GeoTIFF files",
    no_args_is_help=True,
)
app.add_typer(geotiff_app, name="geotiff")


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
        silo_dir = Path.home() / "Developer/DATA/silo_grids"

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


@local_app.command()
def info(
    silo_dir: Annotated[Optional[Path], typer.Option(help="Path to SILO data directory")] = None,
) -> None:
    """
    Display information about available local SILO data.
    """
    if silo_dir is None:
        silo_dir = Path.home() / "Developer/DATA/silo_grids"

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
        Optional[List[str]],
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
        silo_dir = Path.home() / "Developer/DATA/silo_grids"

    console = Console()

    try:
        download_silo_gridded(
            variables=variables,
            start_year=start_year,
            end_year=end_year,
            output_dir=silo_dir,
            force=force,
            timeout=timeout,
            console=console,
        )

    except ValueError as e:
        console.print(f"[red]❌ Validation error: {e}[/red]")
        raise typer.Exit(1)
    except SiloDownloadError as e:
        console.print(f"[red]❌ Download error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Unexpected error: {e}[/red]")
        raise typer.Exit(1)


@geotiff_app.command(name="download")
def geotiff_download(
    start_date: Annotated[str, typer.Option(help="Start date (YYYY-MM-DD format)")],
    end_date: Annotated[str, typer.Option(help="End date (YYYY-MM-DD format)")],
    variables: Annotated[
        Optional[List[str]],
        typer.Option(
            "--var",
            help="Variable names (daily_rain, max_temp, etc.) or presets (daily, monthly). Can specify multiple.",
        ),
    ] = None,
    output_dir: Annotated[Optional[Path], typer.Option(help="Output directory for downloaded GeoTIFF files")] = None,
    bbox: Annotated[
        Optional[List[float]],
        typer.Option(
            help="Bounding box: min_lon min_lat max_lon max_lat (4 values, mutually exclusive with --geometry)"
        ),
    ] = None,
    geometry: Annotated[
        Optional[Path],
        typer.Option(help="Path to GeoJSON file with Polygon for clipping (mutually exclusive with --bbox)"),
    ] = None,
    force: Annotated[bool, typer.Option(help="Overwrite existing files")] = False,
) -> None:
    """
    Download SILO GeoTIFF files for a date range, optionally clipped to geometry/bbox.

    Files are organized in the structure:
        output_dir/
        ├── daily_rain/
        │   ├── 2023/
        │   │   ├── 20230101.daily_rain.tif
        │   │   └── 20230102.daily_rain.tif
        │   └── ...
        └── ...

    By default, existing files are skipped. Use --force to re-download.

    Examples:
        # Download entire files for daily rainfall
        weather-tools geotiff download \\
            --var daily_rain --var max_temp \\
            --start-date 2023-01-01 --end-date 2023-01-31

        # Download with bounding box clipping
        weather-tools geotiff download \\
            --var daily_rain \\
            --start-date 2023-01-01 --end-date 2023-01-31 \\
            --bbox 150.5 -28.5 154.0 -26.0

        # Download with geometry file clipping
        weather-tools geotiff download \\
            --var daily_rain \\
            --start-date 2023-01-01 --end-date 2023-01-31 \\
            --geometry region.geojson
    """
    # Set defaults
    if variables is None:
        variables = ["daily_rain"]

    if output_dir is None:
        output_dir = Path.cwd() / "DATA" / "silo_grids" / "geotiff"

    console = Console()

    # Validate that bbox and geometry are mutually exclusive
    if bbox is not None and geometry is not None:
        console.print("[red]Error: Cannot specify both --bbox and --geometry[/red]")
        raise typer.Exit(1)

    # Validate bbox format
    if bbox is not None:
        if len(bbox) != 4:
            console.print("[red]Error: --bbox requires exactly 4 values: min_lon min_lat max_lon max_lat[/red]")
            raise typer.Exit(1)

    # Parse dates
    try:
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError as e:
        console.print(f"[red]Error parsing dates: {e}[/red]")
        console.print("[yellow]Expected format: YYYY-MM-DD[/yellow]")
        raise typer.Exit(1)

    # Load geometry from file if provided
    geom_obj = None
    if geometry is not None:
        try:
            import geopandas as gpd

            gdf = gpd.read_file(geometry)
            if len(gdf) == 0:
                console.print(f"[red]Error: No geometries found in {geometry}[/red]")
                raise typer.Exit(1)
            # Use the first geometry
            geom_obj = gdf.geometry.iloc[0]
            console.print(f"[cyan]Loaded geometry from {geometry}[/cyan]")
        except ImportError:
            console.print("[red]Error: geopandas is required for reading GeoJSON files[/red]")
            console.print("[yellow]Install with: uv sync --extra geotiff[/yellow]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error loading geometry file: {e}[/red]")
            raise typer.Exit(1)

    # Convert bbox to bounding box tuple
    bbox_tuple = None
    if bbox is not None:
        bbox_tuple = tuple(bbox)
        console.print(f"[cyan]Bounding box: {bbox_tuple}[/cyan]")

    try:
        download_geotiff_range(
            variables=variables,
            start_date=start,
            end_date=end,
            output_dir=output_dir,
            geometry=geom_obj,
            bounding_box=bbox_tuple,
            force=force,
            console=console,
        )

        console.print("\n[bold green]Download complete![/bold green]")

    except ValueError as e:
        console.print(f"[red]Validation error: {e}[/red]")
        raise typer.Exit(1)
    except SiloGeoTiffError as e:
        console.print(f"[red]Download error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


@silo_app.command(name="patched-point")
def silo_patched_point(
    station: Annotated[str, typer.Option(help="BOM station code (e.g., '30043' for Brisbane Aero)")],
    start_date: Annotated[str, typer.Option(help="Start date in YYYYMMDD format")],
    end_date: Annotated[str, typer.Option(help="End date in YYYYMMDD format")],
    format: Annotated[
        Optional[str],
        typer.Option(help="Output format: csv, json, apsim, standard (auto-detected from filename if not specified)"),
    ] = None,
    variables: Annotated[
        Optional[List[str]], typer.Option("--var", help="Climate variable codes (R, X, N, V, E, J, F, etc.)")
    ] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output filename")] = None,
    api_key: Annotated[Optional[str], typer.Option(envvar="SILO_API_KEY", help="SILO API key (email address)")] = None,
    enable_cache: Annotated[bool, typer.Option(help="Enable response caching")] = False,
    debug: Annotated[bool, typer.Option(help="Print constructed URL for debugging")] = False,
) -> None:
    """
    Query SILO PatchedPoint dataset (station-based data).
    
    Format is auto-detected from output filename extension:
    - .csv → csv format
    - .json → json format  
    - .apsim → apsim format
    - .txt → standard format
    
    Use 'weather-tools silo search' to find station codes by name.
    
    Examples:
        # Get rainfall and temperature for Brisbane Aero (format auto-detected)
        weather-tools silo patched-point --station 30043 \\
            --start-date 20230101 --end-date 20230131 \\
            --var R --var X --var N --output data.csv
        
        # Get all variables in APSIM format
        weather-tools silo patched-point --station 30043 \\
            --start-date 20230101 --end-date 20230131 \\
            --output data.apsim
            
        # Force specific format (extension will be corrected)
        weather-tools silo patched-point --station 30043 \\
            --start-date 20230101 --end-date 20230131 \\
            --format json --output data.json
    """
    from pydantic import ValidationError

    from .silo_models import (
        ClimateVariable,
        PatchedPointQuery,
        SiloDateRange,
        SiloFormat,
    )

    # Format detection and validation
    valid_formats = ["csv", "json", "apsim", "standard"]

    # Detect format from output file extension if format not specified
    if format is None and output:
        output_path = Path(output)
        suffix = output_path.suffix.lower()
        if suffix == ".csv":
            format = "csv"
        elif suffix == ".json":
            format = "json"
        elif suffix == ".apsim":
            format = "apsim"
        elif suffix == ".txt":
            format = "standard"
        else:
            format = "csv"  # Default fallback
    elif format is None:
        format = "csv"  # Default when no output file specified

    # Validate format
    if format not in valid_formats:
        typer.echo(f"❌ Error: Invalid format '{format}'. Valid formats: {', '.join(valid_formats)}", err=True)
        typer.echo("   Use 'weather-tools silo search' for station search operations", err=True)
        raise typer.Exit(1)

    # Adjust output filename to match format
    if output:
        output_path = Path(output)
        format_extensions = {"csv": ".csv", "json": ".json", "apsim": ".apsim", "standard": ".txt"}
        expected_ext = format_extensions[format]

        # Force correct extension
        if not output_path.suffix or output_path.suffix.lower() != expected_ext:
            if output_path.suffix:
                # Replace existing extension
                output = str(output_path.with_suffix(expected_ext))
            else:
                # Add extension
                output = str(output_path) + expected_ext

    try:
        # Convert variable strings to enums
        variable_enums = None
        if variables:
            try:
                variable_enums = [ClimateVariable(v) for v in variables]
            except ValueError as e:
                typer.echo(f"❌ Invalid variable code: {e}", err=True)
                typer.echo("   Valid codes: R, X, N, V, E, J, F, T, A, P, W, L, S, C, H, G, D, M", err=True)
                raise typer.Exit(1)

        # Build query using Pydantic model - automatic validation!
        query = PatchedPointQuery(
            format=SiloFormat(format),
            station_code=station,
            date_range=SiloDateRange(start_date=start_date, end_date=end_date),
            values=variable_enums,
        )

        # Initialize API and execute query
        if api_key:
            api = SiloAPI(api_key=api_key, enable_cache=enable_cache, debug=debug)
        else:
            api = SiloAPI(enable_cache=enable_cache, debug=debug)

        typer.echo("🌐 Querying SILO PatchedPoint dataset...")
        typer.echo(f"   Station: {station}")
        typer.echo(f"   Date Range: {start_date} to {end_date}")
        typer.echo(f"   Format: {format}")

        response = api.query_patched_point(query)

        typer.echo("✅ Query successful!")

        # Output results
        result_text = response.to_csv() if format != "json" else str(response.to_dict())

        if output:
            output_path = Path(output)
            output_path.write_text(result_text)
            typer.echo(f"💾 Saved to: {output_path.absolute()}")
        else:
            typer.echo("\n📄 Result:")
            # Print first 500 chars to avoid overwhelming terminal
            if len(result_text) > 500:
                typer.echo(result_text[:500] + "\n... (truncated)")
            else:
                typer.echo(result_text)

        if enable_cache:
            typer.echo(f"📦 Cache size: {api.get_cache_size()}")

    except ValidationError as e:
        typer.echo("❌ Validation error:", err=True)
        for error in e.errors():
            typer.echo(f"   {error['loc'][0]}: {error['msg']}", err=True)
        raise typer.Exit(1)
    except SiloAPIError as e:
        typer.echo(f"❌ API Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {e}", err=True)
        raise typer.Exit(1)


@silo_app.command(name="data-drill")
def silo_data_drill(
    latitude: Annotated[float, typer.Option(help="Latitude in decimal degrees (-44 to -10)")],
    longitude: Annotated[float, typer.Option(help="Longitude in decimal degrees (113 to 154)")],
    start_date: Annotated[str, typer.Option(help="Start date in YYYYMMDD format")],
    end_date: Annotated[str, typer.Option(help="End date in YYYYMMDD format")],
    format: Annotated[str, typer.Option(help="Output format: csv, json, apsim, alldata, standard")] = "csv",
    variables: Annotated[
        Optional[List[str]], typer.Option("--var", help="Climate variable codes (R, X, N, V, E, J, F, etc.)")
    ] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output filename")] = None,
    api_key: Annotated[Optional[str], typer.Option(envvar="SILO_API_KEY", help="SILO API key (email address)")] = None,
    enable_cache: Annotated[bool, typer.Option(help="Enable response caching")] = False,
    debug: Annotated[bool, typer.Option(help="Print constructed URL for debugging")] = False,
) -> None:
    """
    Query SILO DataDrill dataset (gridded data).
    
    Examples:
        # Get rainfall for a specific location
        weather-tools silo data-drill --latitude -27.5 --longitude 151.0 \\
            --start-date 20230101 --end-date 20230131 \\
            --var R --output data.csv
        
        # Get all variables for a location
        weather-tools silo data-drill --latitude -27.5 --longitude 151.0 \\
            --start-date 20230101 --end-date 20230131 \\
            --format alldata --output data.txt
    """
    from pydantic import ValidationError

    from .silo_models import (
        AustralianCoordinates,
        ClimateVariable,
        DataDrillQuery,
        SiloDateRange,
        SiloFormat,
    )

    try:
        # Convert variable strings to enums
        variable_enums = None
        if variables:
            try:
                variable_enums = [ClimateVariable(v) for v in variables]
            except ValueError as e:
                typer.echo(f"❌ Invalid variable code: {e}", err=True)
                typer.echo("   Valid codes: R, X, N, V, E, J, F, T, A, P, W, L, S, C, H, G, D, M", err=True)
                raise typer.Exit(1)

        # Build query using Pydantic model - automatic validation!
        query = DataDrillQuery(
            coordinates=AustralianCoordinates(latitude=latitude, longitude=longitude),
            date_range=SiloDateRange(start_date=start_date, end_date=end_date),
            format=SiloFormat(format),
            values=variable_enums,
        )

        # Initialize API and execute query
        if api_key:
            api = SiloAPI(api_key=api_key, enable_cache=enable_cache, debug=debug)
        else:
            api = SiloAPI(enable_cache=enable_cache, debug=debug)

        typer.echo("🌐 Querying SILO DataDrill dataset...")
        typer.echo(f"   Location: {latitude}°S, {longitude}°E")
        typer.echo(f"   Date Range: {start_date} to {end_date}")
        typer.echo(f"   Format: {format}")

        response = api.query_data_drill(query)

        typer.echo("✅ Query successful!")

        # Output results
        result_text = response.to_csv() if format != "json" else str(response.to_dict())

        if output:
            output_path = Path(output)
            output_path.write_text(result_text)
            typer.echo(f"💾 Saved to: {output_path.absolute()}")
        else:
            typer.echo("\n📄 Result:")
            # Print first 500 chars to avoid overwhelming terminal
            if len(result_text) > 500:
                typer.echo(result_text[:500] + "\n... (truncated)")
            else:
                typer.echo(result_text)

        if enable_cache:
            typer.echo(f"📦 Cache size: {api.get_cache_size()}")

    except ValidationError as e:
        typer.echo("❌ Validation error:", err=True)
        for error in e.errors():
            typer.echo(f"   {error['loc'][0]}: {error['msg']}", err=True)
        raise typer.Exit(1)
    except SiloAPIError as e:
        typer.echo(f"❌ API Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {e}", err=True)
        raise typer.Exit(1)


@silo_app.command(name="search")
def silo_search(
    name: Annotated[Optional[str], typer.Option(help="Search for stations by name fragment (e.g., 'Brisbane')")] = None,
    station: Annotated[Optional[str], typer.Option(help="Station code for nearby search or details lookup")] = None,
    radius: Annotated[float, typer.Option(help="Search radius in km (for nearby search)")] = 50.0,
    details: Annotated[bool, typer.Option(help="Get detailed info for a specific station")] = False,
    api_key: Annotated[Optional[str], typer.Option(envvar="SILO_API_KEY", help="SILO API key (email address)")] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output filename")] = None,
    debug: Annotated[bool, typer.Option(help="Print constructed URL for debugging")] = False,
) -> None:
    """
    Search for SILO stations by name or find nearby stations.

    Examples:
        # Search by name
        weather-tools silo search --name Brisbane

        # Find nearby stations
        weather-tools silo search --station 30043 --radius 50

        # Get station details
        weather-tools silo search --station 30043 --details
    """
    from pydantic import ValidationError

    from .silo_models import PatchedPointQuery, SiloFormat

    try:
        if api_key:
            api = SiloAPI(api_key=api_key, debug=debug)
        else:
            api = SiloAPI(debug=debug)

        # Determine search type
        if details and station:
            # Get station details
            typer.echo(f"� Getting details for station {station}...")
            query = PatchedPointQuery(format=SiloFormat.ID, station_code=station)
        elif name:
            # Search by name
            typer.echo(f"🔍 Searching for stations matching '{name}'...")
            query = PatchedPointQuery(format=SiloFormat.NAME, name_fragment=name)
        elif station:
            # Nearby search
            typer.echo(f"🔍 Searching for stations near {station} within {radius}km...")
            query = PatchedPointQuery(format=SiloFormat.NEAR, station_code=station, radius=radius)
        else:
            typer.echo(
                "❌ Error: Provide --name for name search, --station for nearby search, or --station --details for info",
                err=True,
            )
            raise typer.Exit(1)

        response = api.query_patched_point(query)

        typer.echo("✅ Search successful!")

        if output:
            output_path = Path(output)
            output_path.write_text(response.to_csv())
            typer.echo(f"💾 Saved to: {output_path.absolute()}")
        else:
            typer.echo("\n📍 Results:")
            typer.echo(response.to_csv())

    except ValidationError as e:
        typer.echo("❌ Validation error:", err=True)
        for error in e.errors():
            typer.echo(f"   {error['loc'][0]}: {error['msg']}", err=True)
        raise typer.Exit(1)
    except SiloAPIError as e:
        typer.echo(f"❌ API Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
