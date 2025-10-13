"""Command-line interface for weather_tools."""

from pathlib import Path
from typing import Annotated, Optional, Union

import pandas as pd
import typer
from typing_extensions import List

from weather_tools.read_silo_xarray import read_silo_xarray

app = typer.Typer(
    name="weather-tools",
    help="CLI tool for extracting weather data from SILO datasets",
    no_args_is_help=True,
)


@app.command()
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
    keep_location: Annotated[
        bool, typer.Option(help="Keep location columns (crs, lat, lon) in output CSV")
    ] = False,
) -> None:
    """
    Extract weather data for a specific location and date range, saving results to CSV.
    
    Example:
        weather-tools extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2025-01-01 --output weather.csv
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


@app.command()
def info(
    silo_dir: Annotated[
        Optional[Path], 
        typer.Option(help="Path to SILO data directory")
    ] = None,
) -> None:
    """
    Display information about available SILO data.
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
                    year = file.stem.split('.')[0]
                    if year.isdigit():
                        years.append(int(year))
                except Exception:
                    pass
            
            if years:
                typer.echo(f"    📅 Years: {min(years)}-{max(years)}")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()