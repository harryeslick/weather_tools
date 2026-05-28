"""SILO GeoTIFF CLI commands.

The ``download`` command is a thin downloader: variables, date range, output
directory, and the ``force`` flag come from :class:`GeoTiffDownloadQuery`
(auto-flattened into CLI options via :func:`from_pydantic`); the spatial inputs
(``--bbox`` and ``--geometry``) stay as CLI-only options and are resolved into
a shapely geometry *before* the model is consulted. That split is intentional —
the spatial inputs are a tagged union with file-loading side effects that don't
fit the adapter's one-level flattening contract, and forcing them into the
model would invert the simplification we're trying to achieve.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, List, Optional

import typer
from pydantic import ValidationError
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from weather_tools.cli.date_utils import silo_yyyymmdd_to_iso
from weather_tools.cli.pydantic_typer import from_pydantic
from weather_tools.config import get_silo_data_dir
from weather_tools.geotiff_models import GeoTiffDownloadQuery
from weather_tools.logging_utils import get_console
from weather_tools.silo_geotiff import download_geotiffs
from weather_tools.variable_register import SiloGeoTiffError

logger = logging.getLogger(__name__)

geotiff_app = typer.Typer(
    name="geotiff",
    help="Work with SILO Cloud-Optimized GeoTIFF files",
    no_args_is_help=True,
)


def _resolve_spatial_input(
    bbox: Optional[List[float]],
    geometry: Optional[Path],
) -> Optional[BaseGeometry]:
    """Resolve mutually-exclusive --bbox / --geometry into a shapely geometry.

    Returns ``None`` if neither was provided (download proceeds without spatial
    subsetting). Raises ``typer.Exit(1)`` for invalid combinations or unreadable
    geometry files.
    """
    if bbox is not None and geometry is not None:
        logger.error("[red]Error: Cannot specify both --bbox and --geometry[/red]")
        raise typer.Exit(1)

    if bbox is not None:
        if len(bbox) != 4:
            logger.error(
                "[red]Error: --bbox requires exactly 4 values: "
                "min_lon min_lat max_lon max_lat[/red]"
            )
            raise typer.Exit(1)
        geom = box(*bbox)
        logger.info(f"[cyan]Bounding box: {bbox} → Polygon[/cyan]")
        return geom

    if geometry is not None:
        try:
            import geopandas as gpd

            gdf = gpd.read_file(geometry)
        except ImportError:
            logger.error("[red]Error: geopandas is required for reading GeoJSON files[/red]")
            logger.warning("[yellow]Install with: uv sync --extra geotiff[/yellow]")
            raise typer.Exit(1)
        except Exception as e:
            logger.error(f"[red]Error loading geometry file: {e}[/red]")
            raise typer.Exit(1)

        if len(gdf) == 0:
            logger.error(f"[red]Error: No geometries found in {geometry}[/red]")
            raise typer.Exit(1)
        logger.info(f"[cyan]Loaded geometry from {geometry}[/cyan]")
        return gdf.geometry.iloc[0]

    return None


@geotiff_app.command(name="download")
@from_pydantic(GeoTiffDownloadQuery, field_aliases={"variables": "--var"})
def geotiff_download(
    query: GeoTiffDownloadQuery,
    bbox: Annotated[
        Optional[List[float]],
        typer.Option(
            help=(
                "Bounding box: min_lon min_lat max_lon max_lat "
                "(4 values, mutually exclusive with --geometry)"
            ),
        ),
    ] = None,
    geometry: Annotated[
        Optional[Path],
        typer.Option(
            help="Path to GeoJSON file with Polygon for clipping (mutually exclusive with --bbox)",
        ),
    ] = None,
) -> None:
    """Download SILO GeoTIFF files for a date range, optionally clipped to geometry/bbox.

    Variables, dates, output directory, and the ``force`` flag come from the
    underlying ``GeoTiffDownloadQuery`` model. Spatial subsetting via ``--bbox``
    or ``--geometry`` is resolved separately before the download runs.

    Files are organized in the structure::

        output_dir/
        ├── daily_rain/
        │   └── 2023/
        │       ├── 20230101.daily_rain.tif
        │       └── 20230102.daily_rain.tif
        └── monthly_rain/       # monthly variables use YYYYMM filename
            └── 2023/
                ├── 202301.monthly_rain.tif
                └── 202302.monthly_rain.tif

    By default, existing files are skipped. Use --force to re-download.

    Examples:

        weather-tools geotiff download \\
            --var daily_rain --var max_temp \\
            --start-date 2023-01-01 --end-date 2023-01-31

        weather-tools geotiff download \\
            --var daily_rain \\
            --start-date 2023-01-01 --end-date 2023-01-31 \\
            --bbox 150.5 -28.5 154.0 -26.0

        weather-tools geotiff download \\
            --var daily_rain \\
            --start-date 2023-01-01 --end-date 2023-01-31 \\
            --geometry region.geojson
    """
    console = get_console()

    # Resolve the spatial inputs first so any user error there short-circuits
    # before we touch the model or kick off any download work.
    geom_obj = _resolve_spatial_input(bbox, geometry)

    output_dir = (
        query.output_dir if query.output_dir is not None else get_silo_data_dir() / "geotiff"
    )

    # SiloDateRange stores YYYYMMDD; convert to datetime.date for the API.
    start = _yyyymmdd_to_date(query.date_range.start_date)
    end = _yyyymmdd_to_date(query.date_range.end_date)

    try:
        download_geotiffs(
            variables=query.variables,
            start_date=start,
            end_date=end,
            geometry=geom_obj,
            output_dir=output_dir,
            save_to_disk=True,
            force=query.force,
            console=console,
        )

        logger.info("\n[bold green]Download complete![/bold green]")

    except ValidationError as e:
        logger.error("[red]Validation error:[/red]")
        for error in e.errors():
            loc = ".".join(str(part) for part in error.get("loc", ())) or "?"
            logger.error(f"   {loc}: {error['msg']}")
        raise typer.Exit(1)
    except ValueError as e:
        logger.error(f"[red]Validation error: {e}[/red]")
        raise typer.Exit(1)
    except SiloGeoTiffError as e:
        logger.error(f"[red]Download error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        logger.exception(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


def _yyyymmdd_to_date(value: str):
    """Convert a YYYYMMDD string (as stored by SiloDateRange) to a datetime.date."""
    import datetime as _dt

    # silo_yyyymmdd_to_iso is best-effort; we want a hard failure if the model
    # somehow handed us a malformed string (shouldn't happen post-validation).
    iso = silo_yyyymmdd_to_iso(value)
    return _dt.datetime.strptime(iso, "%Y-%m-%d").date()
