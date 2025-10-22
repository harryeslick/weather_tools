"""Command-line interface for weather_tools."""

from pathlib import Path
from typing import Annotated, Optional, Union

import pandas as pd
import typer
from rich.console import Console
from typing_extensions import List

from weather_tools.download_silo import SiloDownloadError, download_silo_gridded
from weather_tools.merge_weather_data import (
    MergeValidationError,
    get_merge_summary,
    merge_historical_and_forecast,
)
from weather_tools.metno_api import MetNoAPI
from weather_tools.metno_models import MetNoAPIError, MetNoRateLimitError
from weather_tools.read_silo_xarray import read_silo_xarray
from weather_tools.silo_api import SiloAPI, SiloAPIError
from weather_tools.silo_models import AustralianCoordinates

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

# Create subapp for met.no API commands
metno_app = typer.Typer(
    name="metno",
    help="Query met.no forecast API for Australian locations",
    no_args_is_help=True,
)
app.add_typer(metno_app, name="metno")


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
        downloaded = download_silo_gridded(
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
            format_type = "id"
        elif name:
            # Search by name
            typer.echo(f"🔍 Searching for stations matching '{name}'...")
            query = PatchedPointQuery(format=SiloFormat.NAME, name_fragment=name)
            format_type = "name"
        elif station:
            # Nearby search
            typer.echo(f"🔍 Searching for stations near {station} within {radius}km...")
            query = PatchedPointQuery(format=SiloFormat.NEAR, station_code=station, radius=radius)
            format_type = "near"
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


@metno_app.command()
def forecast(
    lat: Annotated[float, typer.Option(help="Latitude coordinate (-9 to -44 for Australia)")],
    lon: Annotated[float, typer.Option(help="Longitude coordinate (113 to 154 for Australia)")],
    days: Annotated[int, typer.Option(help="Number of forecast days (1-9)")] = 7,
    output: Annotated[Optional[str], typer.Option(help="Output CSV filename (optional)")] = None,
    format_silo: Annotated[bool, typer.Option(help="Convert to SILO column names")] = True,
    user_agent: Annotated[Optional[str], typer.Option(help="Custom User-Agent for met.no API")] = None,
) -> None:
    """
    Get met.no weather forecast for an Australian location.

    Retrieves up to 9 days of forecast data from met.no's locationforecast API.
    Daily summaries are automatically aggregated from hourly forecasts.

    Example:
        weather-tools metno forecast --lat -27.5 --lon 153.0 --days 7 --output brisbane_forecast.csv
    """
    console = Console()

    try:
        # Validate coordinates
        coords = AustralianCoordinates(latitude=lat, longitude=lon)

        # Validate days parameter
        if not 1 <= days <= 9:
            console.print("[red]❌ Error: days must be between 1 and 9[/red]")
            raise typer.Exit(1)

        console.print(f"[cyan]📡 Fetching met.no forecast for {coords.latitude}, {coords.longitude}...[/cyan]")

        # Create API client
        api = MetNoAPI(user_agent=user_agent)

        # Get daily forecast
        daily_forecasts = api.get_daily_forecast(latitude=coords.latitude, longitude=coords.longitude, days=days)

        console.print(f"[green]✓ Retrieved {len(daily_forecasts)} days of forecast data[/green]")

        # Convert to DataFrame
        forecast_df = pd.DataFrame([f.model_dump() for f in daily_forecasts])

        if format_silo:
            # Rename columns to SILO format
            from weather_tools.silo_variables import add_silo_date_columns, convert_metno_to_silo_columns

            column_mapping = convert_metno_to_silo_columns(forecast_df, include_extra=False)
            forecast_df = forecast_df.rename(columns=column_mapping)
            forecast_df = add_silo_date_columns(forecast_df)

        # Save or display
        if output:
            forecast_df.to_csv(output, index=False)
            console.print(f"[green]✓ Forecast saved to: {output}[/green]")
        else:
            console.print("\n[bold]Met.no Forecast:[/bold]")
            console.print(forecast_df.to_string(index=False))

    except ValueError as e:
        console.print(f"[red]❌ Validation Error: {e}[/red]")
        raise typer.Exit(1)
    except MetNoRateLimitError as e:
        console.print(f"[red]❌ Rate Limit Exceeded: {e}[/red]")
        console.print("[yellow]Please wait a few minutes before retrying[/yellow]")
        raise typer.Exit(1)
    except MetNoAPIError as e:
        console.print(f"[red]❌ met.no API Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


@metno_app.command()
def merge(
    lat: Annotated[float, typer.Option(help="Latitude coordinate (-9 to -44 for Australia)")],
    lon: Annotated[float, typer.Option(help="Longitude coordinate (113 to 154 for Australia)")],
    start_date: Annotated[str, typer.Option(help="Historical data start date (YYYY-MM-DD)")],
    end_date: Annotated[str, typer.Option(help="Historical data end date (YYYY-MM-DD)")],
    output: Annotated[str, typer.Option(help="Output CSV filename")],
    forecast_days: Annotated[int, typer.Option(help="Number of forecast days to append (1-9)")] = 7,
    silo_dir: Annotated[Optional[Path], typer.Option(help="Path to SILO data directory")] = None,
    variables: Annotated[
        Optional[List[str]],
        typer.Option(help="Weather variables for historical data (use 'daily' preset)"),
    ] = None,
    fill_missing: Annotated[bool, typer.Option(help="Fill missing SILO variables with estimates")] = False,
    user_agent: Annotated[Optional[str], typer.Option(help="Custom User-Agent for met.no API")] = None,
) -> None:
    """
    Merge SILO historical data with met.no forecast data.

    Combines historical observations from local SILO files with met.no forecast data
    for seamless downstream analysis.

    Example:
        weather-tools metno merge --lat -27.5 --lon 153.0 \\
            --start-date 2023-01-01 --end-date 2023-12-31 \\
            --forecast-days 7 --output combined_weather.csv
    """
    console = Console()

    try:
        # Validate coordinates
        coords = AustralianCoordinates(latitude=lat, longitude=lon)

        # Validate forecast days
        if not 1 <= forecast_days <= 9:
            console.print("[red]❌ Error: forecast_days must be between 1 and 9[/red]")
            raise typer.Exit(1)

        # Step 1: Get SILO historical data
        console.print(f"[cyan]📁 Loading SILO historical data from {start_date} to {end_date}...[/cyan]")

        if variables is None:
            variables = ["daily"]

        ds = read_silo_xarray(
            variables=variables,
            silo_dir=silo_dir,
        )

        # Extract data for location
        point_ds = ds.sel(lat=coords.latitude, lon=coords.longitude, method="nearest")
        silo_df = point_ds.to_dataframe().reset_index()

        # Filter by date range
        silo_df = silo_df[
            (silo_df["time"] >= pd.to_datetime(start_date)) & (silo_df["time"] <= pd.to_datetime(end_date))
        ]

        # Rename 'time' to 'date'
        silo_df = silo_df.rename(columns={"time": "date"})

        console.print(f"[green]✓ Loaded {len(silo_df)} days of SILO historical data[/green]")

        # Step 2: Get met.no forecast
        console.print(f"[cyan]📡 Fetching {forecast_days} days of met.no forecast...[/cyan]")

        api = MetNoAPI(user_agent=user_agent)
        daily_forecasts = api.get_daily_forecast(
            latitude=coords.latitude, longitude=coords.longitude, days=forecast_days
        )

        metno_df = pd.DataFrame([f.model_dump() for f in daily_forecasts])

        console.print(f"[green]✓ Retrieved {len(metno_df)} days of forecast data[/green]")

        # Step 3: Merge datasets
        console.print("[cyan]🔗 Merging historical and forecast data...[/cyan]")

        merged_df = merge_historical_and_forecast(
            silo_df, metno_df, validate=True, fill_missing=fill_missing, overlap_strategy="prefer_silo"
        )

        # Get merge summary
        summary = get_merge_summary(merged_df)

        console.print(f"[green]✓ Merge complete![/green]")
        console.print(f"  • Total records: {summary['total_records']}")
        console.print(f"  • SILO records: {summary['silo_records']}")
        console.print(f"  • met.no records: {summary['metno_records']}")
        console.print(
            f"  • Date range: {summary['date_range']['start'].date()} to {summary['date_range']['end'].date()}"
        )
        console.print(f"  • Transition date: {summary['transition_date'].date()}")

        # Save to CSV
        merged_df.to_csv(output, index=False)
        console.print(f"[green]✓ Merged data saved to: {output}[/green]")

    except ValueError as e:
        console.print(f"[red]❌ Validation Error: {e}[/red]")
        raise typer.Exit(1)
    except MergeValidationError as e:
        console.print(f"[red]❌ Merge Error: {e}[/red]")
        raise typer.Exit(1)
    except MetNoAPIError as e:
        console.print(f"[red]❌ met.no API Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        import traceback

        traceback.print_exc()
        raise typer.Exit(1)


@metno_app.command()
def info() -> None:
    """
    Display information about the met.no API and variable mappings.

    Shows available variables, data coverage, and API details.
    """
    console = Console()

    console.print("\n[bold cyan]met.no locationforecast API Information[/bold cyan]\n")

    console.print("[bold]API Details:[/bold]")
    console.print("  • Provider: Norwegian Meteorological Institute (met.no)")
    console.print("  • Endpoint: https://api.met.no/weatherapi/locationforecast/2.0/")
    console.print("  • Coverage: Global (optimized for Norwegian locations)")
    console.print("  • Forecast horizon: Up to 9 days")
    console.print("  • Update frequency: Hourly")
    console.print("  • Rate limit: Fair use policy (requires User-Agent)")

    console.print("\n[bold]Available Variables (Daily Aggregates):[/bold]")
    console.print("  • min_temperature (°C) → min_temp")
    console.print("  • max_temperature (°C) → max_temp")
    console.print("  • total_precipitation (mm) → daily_rain")
    console.print("  • avg_pressure (hPa) → mslp")
    console.print("  • avg_relative_humidity (%) → vp (converted)")
    console.print("  • avg_wind_speed (m/s) → wind_speed")
    console.print("  • max_wind_speed (m/s) → wind_speed_max")
    console.print("  • avg_cloud_fraction (%) → cloud_fraction")
    console.print("  • dominant_weather_symbol → weather_symbol")

    console.print("\n[bold]SILO-Only Variables (Not Available from met.no):[/bold]")
    console.print("  • evap_pan - Class A pan evaporation")
    console.print("  • evap_syn - Synthetic evaporation")
    console.print("  • radiation - Solar radiation (MJ/m²)")
    console.print("  • vp_deficit - Vapor pressure deficit")
    console.print("  • et_short_crop - FAO56 reference evapotranspiration")

    console.print("\n[bold]Usage Examples:[/bold]")
    console.print("  # Get 7-day forecast for Brisbane")
    console.print("  weather-tools metno forecast --lat -27.5 --lon 153.0 --days 7")
    console.print("")
    console.print("  # Merge historical SILO with 7-day forecast")
    console.print("  weather-tools metno merge --lat -27.5 --lon 153.0 \\")
    console.print("      --start-date 2023-01-01 --end-date 2023-12-31 \\")
    console.print("      --forecast-days 7 --output combined.csv")

    console.print("\n[bold]Note:[/bold] The met.no API is best used for Australian locations")
    console.print("near the coast. Inland locations may have less accurate forecasts.")
    console.print("For optimal results, use with SILO historical data.\n")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
