"""SILO API CLI commands."""

import logging
from pathlib import Path
from typing import Annotated, Literal, Optional

import typer
from typing_extensions import List

from weather_tools.silo_api import SiloAPI, SiloAPIError

logger = logging.getLogger(__name__)

silo_app = typer.Typer(
    name="silo",
    help="Query SILO API directly (requires API key)",
    no_args_is_help=True,
)

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
    log_level: Annotated[
        str, typer.Option("--log-level", help="Logging level for SILO client (e.g. INFO, DEBUG, WARNING)")
    ] = "INFO",
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

    from weather_tools.silo_models import (
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
            api = SiloAPI(api_key=api_key, enable_cache=enable_cache, log_level=log_level)
        else:
            api = SiloAPI(enable_cache=enable_cache, log_level=log_level)

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
    log_level: Annotated[
        str, typer.Option("--log-level", help="Logging level for SILO client (e.g. INFO, DEBUG, WARNING)")
    ] = "INFO",
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

    from weather_tools.silo_models import (
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
            api = SiloAPI(api_key=api_key, enable_cache=enable_cache, log_level=log_level)
        else:
            api = SiloAPI(enable_cache=enable_cache, log_level=log_level)

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
    radius: Annotated[Optional[int], typer.Option(help="Search radius in km (for nearby search)")] = None,
    state: Annotated[
        Optional[Literal["QLD", "NSW", "VIC", "TAS", "SA", "WA", "NT", "ACT"]],
        typer.Option(help="Filter by state (QLD, NSW, VIC, TAS, SA, WA, NT, ACT)"),
    ] = None,
    details: Annotated[bool, typer.Option(help="Get detailed info for a specific station")] = False,
    api_key: Annotated[Optional[str], typer.Option(envvar="SILO_API_KEY", help="SILO API key (email address)")] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output filename")] = None,
    log_level: Annotated[
        str, typer.Option("--log-level", help="Logging level for SILO client (e.g. INFO, DEBUG, WARNING)")
    ] = "INFO",
) -> None:
    """
    Search for SILO stations by name or find nearby stations.

    Examples:
        # Search by name
        weather-tools silo search --name Brisbane

        # Search by name and filter by state
        weather-tools silo search --name Brisbane --state QLD

        # Find nearby stations
        weather-tools silo search --station 30043 --radius 50

        # Get station details
        weather-tools silo search --station 30043 --details
    """
    from pydantic import ValidationError

    from .silo_models import PatchedPointQuery, SiloFormat

    try:
        if api_key:
            api = SiloAPI(api_key=api_key, log_level=log_level)
        else:
            api = SiloAPI(log_level=log_level)

        # Determine search type
        if details and station:
            # Get station details - use direct API call since search_stations doesn't support this
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

        elif name:
            # Search by name using the search_stations method
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
            # Nearby search using the search_stations method
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
                "❌ Error: Provide --name for name search, --station --radius for nearby search, or --station --details for info",
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
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)
