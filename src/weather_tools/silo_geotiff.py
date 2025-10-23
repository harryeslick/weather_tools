"""
SILO Cloud-Optimized GeoTIFF (COG) support module.

This module provides functionality for downloading and reading SILO daily and monthly
GeoTIFF files from AWS S3, with support for:
- Cloud-Optimized GeoTIFF (COG) features: partial spatial reads, overview pyramids
- Shapely geometry queries (Point and Polygon)
- Intelligent file management with caching
- HTTP range requests for efficient data access
"""

import datetime
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np
import rasterio
import requests
from rasterio.features import geometry_window
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from shapely.geometry import Point, Polygon, box

from .logging_utils import get_console
from .silo_variables import VariableMetadata, expand_variable_preset, get_variable_metadata

logger = logging.getLogger(__name__)

# Base URL for SILO GeoTIFF files on AWS S3
SILO_GEOTIFF_BASE_URL = "https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official"


class SiloGeoTiffError(Exception):
    """Base exception for GeoTIFF operations."""

    pass


def construct_daily_url(variable: str, date: datetime.date) -> str:
    """
    Construct URL for daily GeoTIFF file.

    Args:
        variable: Variable name (e.g., "daily_rain", "max_temp")
        date: Date for the data

    Returns:
        Full URL to the GeoTIFF file

    Example:
        >>> construct_daily_url("daily_rain", datetime.date(2023, 1, 15))
        'https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/daily/daily_rain/2023/20230115.daily_rain.tif'
    """
    # Validate variable
    metadata = get_variable_metadata(variable)
    if metadata is None:
        raise SiloGeoTiffError(f"Unknown variable: {variable}")

    var_name = metadata.netcdf_name
    year = date.year
    date_str = date.strftime("%Y%m%d")

    return f"{SILO_GEOTIFF_BASE_URL}/daily/{var_name}/{year}/{date_str}.{var_name}.tif"


def construct_monthly_url(variable: str, year: int, month: int) -> str:
    """
    Construct URL for monthly GeoTIFF file.

    Args:
        variable: Variable name (e.g., "monthly_rain")
        year: Year
        month: Month (1-12)

    Returns:
        Full URL to the GeoTIFF file

    Example:
        >>> construct_monthly_url("monthly_rain", 2023, 3)
        'https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/monthly/monthly_rain/2023/202303.monthly_rain.tif'
    """
    # Validate variable
    metadata = get_variable_metadata(variable)
    if metadata is None:
        raise SiloGeoTiffError(f"Unknown variable: {variable}")

    var_name = metadata.netcdf_name
    date_str = f"{year:04d}{month:02d}"

    return f"{SILO_GEOTIFF_BASE_URL}/monthly/{var_name}/{year}/{date_str}.{var_name}.tif"


def read_cog(
    cog_url: str, geometry: Union[Point, Polygon], overview_level: Optional[int] = None, use_mask: bool = True
) -> Tuple[np.ndarray, dict]:
    """
    Read COG data for given geometry using HTTP range requests.

    This function leverages Cloud-Optimized GeoTIFF features to efficiently
    read only the required spatial subset via HTTP range requests.

    Args:
        cog_url: URL to COG file
        geometry: Shapely Point or Polygon defining area of interest
        overview_level: Pyramid level (None=full resolution, 0=first overview, etc)
        use_mask: Return masked array (np.ma.MaskedArray) with nodata handling

    Returns:
        Tuple of (data array, rasterio profile dict)

    Raises:
        SiloGeoTiffError: If CRS is not EPSG:4326 or other errors occur

    Example:
        >>> from shapely.geometry import Point
        >>> point = Point(153.0, -27.5)
        >>> data, profile = read_cog(url, geometry=point)
    """
    try:
        with rasterio.open(cog_url) as src:
            # Validate CRS is EPSG:4326
            if src.crs.to_string() != "EPSG:4326":
                raise SiloGeoTiffError(f"Expected EPSG:4326, got {src.crs}")

            # Calculate window from geometry
            try:
                window = geometry_window(src, [geometry])
            except Exception as e:
                raise SiloGeoTiffError(f"Failed to calculate window from geometry: {e}")

            # Read data with window parameter for partial read
            if overview_level is not None:
                # Read from overview
                data = src.read(
                    1,
                    window=window,
                    out_shape=(int(window.height // (2**overview_level)), int(window.width // (2**overview_level))),
                )
            else:
                # Read at full resolution
                data = src.read(1, window=window)

            # Apply masking if requested
            if use_mask and src.nodata is not None:
                data = np.ma.masked_equal(data, src.nodata)

            # Build profile with updated transform and dimensions
            profile = src.profile.copy()
            profile.update({"height": data.shape[0], "width": data.shape[1], "transform": src.window_transform(window)})

            return data, profile

    except rasterio.errors.RasterioIOError as e:
        raise SiloGeoTiffError(f"Failed to read COG from {cog_url}: {e}")


def download_geotiff_with_subset(
    url: str,
    destination: Path,
    geometry: Optional[Union[Point, Polygon]] = None,
    force: bool = False,
    timeout: int = 300,
) -> bool:
    """
    Download single GeoTIFF file, optionally clipped to geometry subset.

    Args:
        url: Source URL
        destination: Local file path
        geometry: Optional shapely geometry to clip/subset the downloaded file.
                  If None, downloads entire file. If provided, downloads full file
                  but saves only the clipped portion.
        force: Overwrite if exists
        timeout: Request timeout in seconds

    Returns:
        True if downloaded, False if skipped (exists), raises on error

    Raises:
        SiloGeoTiffError: For HTTP errors (except 404 which returns False)

    Example:
        >>> from pathlib import Path
        >>> from shapely.geometry import Point
        >>> point = Point(153.0, -27.5)
        >>> download_geotiff_with_subset(url, Path("data.tif"), geometry=point)
    """
    # Check if destination exists
    if destination.exists() and not force:
        logger.debug(f"File exists, skipping: {destination}")
        return False

    # Create parent directories
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        if geometry is None:
            # Stream download entire file
            response = requests.get(url, stream=True, timeout=timeout)

            if response.status_code == 404:
                logger.warning(f"File not found (404): {url}")
                return False

            response.raise_for_status()

            with open(destination, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        else:
            # Download and clip to geometry
            with rasterio.open(url) as src:
                # Calculate window from geometry
                window = geometry_window(src, [geometry])

                # Read windowed data
                data = src.read(1, window=window)

                # Build profile with updated transform and dimensions
                profile = src.profile.copy()
                profile.update(
                    {"height": data.shape[0], "width": data.shape[1], "transform": src.window_transform(window)}
                )

                # Write clipped GeoTIFF
                with rasterio.open(destination, "w", **profile) as dst:
                    dst.write(data, 1)

        logger.info(f"Downloaded: {destination}")
        return True

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning(f"File not found (404): {url}")
            return False
        raise SiloGeoTiffError(f"HTTP error downloading {url}: {e}")
    except Exception as e:
        raise SiloGeoTiffError(f"Error downloading {url}: {e}")


def read_geotiff_timeseries(
    variables: Union[str, List[str]],
    start_date: datetime.date,
    end_date: datetime.date,
    geometry: Union[Point, Polygon],
    save_to_disk: bool = False,
    cache_dir: Optional[Path] = None,
    overview_level: Optional[int] = None,
    console: Optional[Console] = None,
) -> dict[str, np.ndarray]:
    """
    Read time series of GeoTIFF data for date range and geometry.

    Args:
        variables: Variable names or preset ("daily", "monthly")
        start_date: First date (inclusive)
        end_date: Last date (inclusive)
        geometry: Shapely geometry for spatial query
        save_to_disk: If True, download to cache_dir; if False, stream from URL
        cache_dir: Where to save files (default: ./DATA/silo_grids/geotiff)
        overview_level: Pyramid level for reduced resolution
        console: Rich console for progress output

    Returns:
        Dict mapping variable names to 3D numpy arrays (time, height, width)

    Example:
        >>> from shapely.geometry import Point
        >>> from datetime import date
        >>> point = Point(153.0, -27.5)
        >>> data = read_geotiff_timeseries(
        ...     variables=["daily_rain", "max_temp"],
        ...     start_date=date(2023, 1, 1),
        ...     end_date=date(2023, 1, 7),
        ...     geometry=point,
        ...     save_to_disk=False
        ... )
    """
    if console is not None:
        logger.debug("Custom console provided to read_geotiff_timeseries; logging handles output automatically.")

    # Expand variable presets
    var_list = expand_variable_preset(variables)

    # Set default cache directory
    if cache_dir is None:
        cache_dir = Path.cwd() / "DATA" / "silo_grids" / "geotiff"

    # Generate date sequence
    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date)
        current_date += datetime.timedelta(days=1)

    # Collect data for each variable
    results = {}

    for var_name in var_list:
        logger.info(f"[cyan]Reading {var_name}...[/cyan]")

        arrays = []

        for date in date_list:
            # Construct URL
            url = construct_daily_url(var_name, date)

            # Determine file path if saving to disk
            if save_to_disk:
                file_path = cache_dir / var_name / str(date.year) / f"{date.strftime('%Y%m%d')}.{var_name}.tif"

                # Check if file exists locally
                if not file_path.exists():
                    # Download if missing
                    try:
                        download_geotiff_with_subset(url, file_path)
                    except SiloGeoTiffError as e:
                        logger.warning(f"Skipping {date}: {e}")
                        continue

                # Read from local file
                try:
                    data, _ = read_cog(f"file://{file_path.absolute()}", geometry, overview_level)
                    arrays.append(data)
                except SiloGeoTiffError as e:
                    logger.warning(f"Failed to read {file_path}: {e}")
                    continue
            else:
                # Stream from URL (no caching)
                try:
                    data, _ = read_cog(url, geometry, overview_level)
                    arrays.append(data)
                except SiloGeoTiffError as e:
                    logger.warning(f"Skipping {date}: {e}")
                    continue

        # Stack arrays into 3D array (time, height, width)
        if arrays:
            results[var_name] = np.stack(arrays, axis=0)
            logger.info(f"[green]Loaded {var_name}: {results[var_name].shape}[/green]")
        else:
            logger.warning(f"[yellow]No data loaded for {var_name}[/yellow]")

    return results


def download_geotiff_range(
    variables: Union[str, List[str]],
    start_date: datetime.date,
    end_date: datetime.date,
    output_dir: Path,
    geometry: Optional[Union[Point, Polygon]] = None,
    bounding_box: Optional[Tuple[float, float, float, float]] = None,
    force: bool = False,
    console: Optional[Console] = None,
) -> dict[str, List[Path]]:
    """
    Download GeoTIFF files for date range, optionally clipped to geometry/bbox.

    Similar to download_silo_gridded() but for daily/monthly GeoTIFFs.

    Args:
        variables: Variable names or preset
        start_date: First date
        end_date: Last date
        output_dir: Directory to save files
        geometry: Optional shapely geometry to clip downloads
        bounding_box: Optional (min_lon, min_lat, max_lon, max_lat) tuple.
                      Converted to Polygon for clipping. Mutually exclusive with geometry.
        force: Overwrite existing files
        console: Rich console for output

    Returns:
        Dict mapping variable names to lists of downloaded file paths

    Raises:
        SiloGeoTiffError: For invalid parameters or download failures

    Example:
        >>> from pathlib import Path
        >>> from datetime import date
        >>> download_geotiff_range(
        ...     variables=["daily_rain"],
        ...     start_date=date(2023, 1, 1),
        ...     end_date=date(2023, 1, 31),
        ...     output_dir=Path("./data"),
        ...     bounding_box=(150.5, -28.5, 154.0, -26.0)
        ... )
    """
    # Validate that geometry and bounding_box are mutually exclusive
    if geometry is not None and bounding_box is not None:
        raise SiloGeoTiffError("Cannot specify both geometry and bounding_box")

    # Convert bounding_box to Polygon if provided
    if bounding_box is not None:
        min_lon, min_lat, max_lon, max_lat = bounding_box
        geometry = box(min_lon, min_lat, max_lon, max_lat)

    # Expand variable presets
    var_list = expand_variable_preset(variables)

    # Validate variables and keep metadata handy for later use
    metadata_map: dict[str, VariableMetadata] = {}
    for var_name in var_list:
        metadata = get_variable_metadata(var_name)
        if metadata is None:
            raise SiloGeoTiffError(f"Unknown variable: {var_name}")
        metadata_map[var_name] = metadata

    # Initialize console if not provided
    if console is None:
        console = get_console()

    # Generate date sequence
    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date)
        current_date += datetime.timedelta(days=1)

    # Build download task list
    tasks = []
    for var_name in var_list:
        metadata = metadata_map[var_name]

        for date in date_list:
            # Skip dates before variable start_year
            if date.year < metadata.start_year:
                continue

            # Construct URL and destination path
            url = construct_daily_url(var_name, date)
            dest_path = output_dir / var_name / str(date.year) / f"{date.strftime('%Y%m%d')}.{var_name}.tif"

            tasks.append((var_name, date, url, dest_path))

    # Download files with progress bar
    downloaded_files = {var: [] for var in var_list}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("[cyan]Downloading GeoTIFFs...", total=len(tasks))

        for var_name, date, url, dest_path in tasks:
            progress.update(task_id, description=f"[cyan]Downloading {var_name} {date}...")

            try:
                downloaded = download_geotiff_with_subset(url, dest_path, geometry, force)
                if downloaded:
                    downloaded_files[var_name].append(dest_path)
            except SiloGeoTiffError as e:
                logger.warning(f"[yellow]Warning: {e}[/yellow]")

            progress.advance(task_id)

    # Print summary via logger
    logger.info("\n[bold green]Download Summary:[/bold green]")
    for var_name, files in downloaded_files.items():
        logger.info(f"  {var_name}: {len(files)} files")

    return downloaded_files
