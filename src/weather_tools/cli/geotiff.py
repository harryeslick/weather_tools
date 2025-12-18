"""SILO GeoTIFF CLI commands."""

import logging
from pathlib import Path
from typing import Annotated, Optional

import typer
from shapely.geometry import box
from typing_extensions import List

from weather_tools.cli.date_utils import iso_date_option, parse_iso_date_strict
from weather_tools.config import get_silo_data_dir
from weather_tools.logging_utils import get_console
from weather_tools.silo_geotiff import download_geotiff
from weather_tools.silo_variables import SiloGeoTiffError

logger = logging.getLogger(__name__)

geotiff_app = typer.Typer(
    name="geotiff",
    help="Work with SILO Cloud-Optimized GeoTIFF files",
    no_args_is_help=True,
)


@geotiff_app.command(name="download")
def geotiff_download(
    start_date: Annotated[str, typer.Option(help="Start date (YYYY-MM-DD)", callback=iso_date_option)],
    end_date: Annotated[str, typer.Option(help="End date (YYYY-MM-DD)", callback=iso_date_option)],
    variables: Annotated[
        Optional[List[str]],
        typer.Option(
            "--var",
            help="Variable names (daily_rain, max_temp, etc.) or presets (daily, monthly). Can specify multiple.",
        ),
    ] = None,
    output_dir: Annotated[
        Optional[Path], typer.Option(help="Output directory for downloaded GeoTIFF files")
    ] = None,
    bbox: Annotated[
        Optional[List[float]],
        typer.Option(
            help="Bounding box: min_lon min_lat max_lon max_lat (4 values, mutually exclusive with --geometry)"
        ),
    ] = None,
    geometry: Annotated[
        Optional[Path],
        typer.Option(
            help="Path to GeoJSON file with Polygon for clipping (mutually exclusive with --bbox)"
        ),
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
        output_dir = get_silo_data_dir() / "geotiff"

    console = get_console()

    # Validate that bbox and geometry are mutually exclusive
    if bbox is not None and geometry is not None:
        logger.error("[red]Error: Cannot specify both --bbox and --geometry[/red]")
        raise typer.Exit(1)

    # Validate bbox format
    if bbox is not None:
        if len(bbox) != 4:
            logger.error(
                "[red]Error: --bbox requires exactly 4 values: min_lon min_lat max_lon max_lat[/red]"
            )
            raise typer.Exit(1)

    # Parse dates (validated by option callbacks)
    start = parse_iso_date_strict(start_date)
    end = parse_iso_date_strict(end_date)

    # Load geometry from file if provided
    geom_obj = None
    if geometry is not None:
        try:
            import geopandas as gpd

            gdf = gpd.read_file(geometry)
            if len(gdf) == 0:
                logger.error(f"[red]Error: No geometries found in {geometry}[/red]")
                raise typer.Exit(1)
            # Use the first geometry
            geom_obj = gdf.geometry.iloc[0]
            logger.info(f"[cyan]Loaded geometry from {geometry}[/cyan]")
        except ImportError:
            logger.error("[red]Error: geopandas is required for reading GeoJSON files[/red]")
            logger.warning("[yellow]Install with: uv sync --extra geotiff[/yellow]")
            raise typer.Exit(1)
        except Exception as e:
            logger.error(f"[red]Error loading geometry file: {e}[/red]")
            raise typer.Exit(1)

    # Convert bbox to Polygon geometry if provided
    if bbox is not None:
        # Create a Polygon from bounding box (min_lon, min_lat, max_lon, max_lat)
        geom_obj = box(*bbox)
        logger.info(f"[cyan]Bounding box: {bbox} → Polygon[/cyan]")

    try:
        download_geotiff(
            variables=variables,
            start_date=start,
            end_date=end,
            output_dir=output_dir,
            geometry=geom_obj,
            force=force,
            console=console,
        )

        logger.info("\n[bold green]Download complete![/bold green]")

    except ValueError as e:
        logger.error(f"[red]Validation error: {e}[/red]")
        raise typer.Exit(1)
    except SiloGeoTiffError as e:
        logger.error(f"[red]Download error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        logger.exception(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)
