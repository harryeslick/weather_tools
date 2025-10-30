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
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np
import rasterio
import rasterio.errors
import requests
from rasterio.features import geometry_window
from rich.console import Console
from shapely.geometry import Point, Polygon

from weather_tools.logging_utils import create_download_progress, get_console
from weather_tools.silo_variables import (
    DEFAULT_GEOTIFF_TIMEOUT,
    SILO_GEOTIFF_BASE_URL,
    SiloGeoTiffError,
    VariableInput,
    get_variable_metadata,
    validate_silo_s3_variables,
)

logger = logging.getLogger(__name__)


def _generate_date_range(start_date: datetime.date, end_date: datetime.date) -> List[datetime.date]:
    """
    Generate list of dates between start and end (inclusive).

    Args:
        start_date: First date (inclusive)
        end_date: Last date (inclusive)

    Returns:
        List of dates from start_date to end_date

    Example:
        >>> import datetime
        >>> dates = _generate_date_range(datetime.date(2023, 1, 1), datetime.date(2023, 1, 3))
        >>> len(dates)
        3
    """
    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date)
        current_date += datetime.timedelta(days=1)
    # remove future dates
    today = datetime.date.today()
    date_list = [d for d in date_list if d < today]
    return date_list


def construct_geotiff_daily_url(variable: str, date: datetime.date) -> str:
    """
    Construct URL for daily GeoTIFF file.

    Args:
        variable: Variable name (e.g., "daily_rain", "max_temp")
        date: Date for the data

    Returns:
        Full URL to the GeoTIFF file

    Raises:
        ValueError: If variable is unknown

    Example:
        >>> construct_geotiff_daily_url("daily_rain", datetime.date(2023, 1, 15))
        'https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/daily/daily_rain/2023/20230115.daily_rain.tif'
    """
    # Validate variable
    metadata = get_variable_metadata(variable)
    if metadata is None:
        raise ValueError(f"Unknown variable: {variable}")

    var_name = metadata.netcdf_name
    year = date.year
    date_str = date.strftime("%Y%m%d")

    return f"{SILO_GEOTIFF_BASE_URL}/daily/{var_name}/{year}/{date_str}.{var_name}.tif"


def construct_geotiff_monthly_url(variable: str, year: int, month: int) -> str:
    """
    Construct URL for monthly GeoTIFF file.

    Args:
        variable: Variable name (e.g., "monthly_rain")
        year: Year
        month: Month (1-12)

    Returns:
        Full URL to the GeoTIFF file

    Raises:
        ValueError: If variable is unknown

    Example:
        >>> construct_geotiff_monthly_url("monthly_rain", 2023, 3)
        'https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/monthly/monthly_rain/2023/202303.monthly_rain.tif'
    """
    # Validate variable
    metadata = get_variable_metadata(variable)
    if metadata is None:
        raise ValueError(f"Unknown variable: {variable}")

    var_name = metadata.netcdf_name
    date_str = f"{year:04d}{month:02d}"

    return f"{SILO_GEOTIFF_BASE_URL}/monthly/{var_name}/{year}/{date_str}.{var_name}.tif"


def read_cog(
    file_path: str,
    geometry: Optional[Union[Point, Polygon]] = None,
    overview_level: Optional[int] = None,
    use_mask: bool = True,
) -> Tuple[np.ndarray, dict]:
    """
    Read COG data, optionally for a specific geometry, using HTTP range requests or local file access.

    This function leverages Cloud-Optimized GeoTIFF features to efficiently
    read only the required spatial subset (if geometry provided). Works with both
    remote URLs (via HTTP range requests) and local file paths.

    Args:
        file_path: Path to GeoTIFF file. Accepts:
                   - Remote URLs: 'https://...' or 'http://...'
                   - File URIs: 'file:///absolute/path/to/file.tif'
                   - Direct paths: '/absolute/path/to/file.tif'
        geometry: Optional Shapely Point or Polygon defining area of interest.
                  If None, reads entire raster.
        overview_level: Pyramid level (None=full resolution, 0=first overview, etc)
        use_mask: Return masked array (np.ma.MaskedArray) with nodata handling

    Returns:
        Tuple of (data array, rasterio profile dict)

    Raises:
        SiloGeoTiffError: If CRS is not EPSG:4326 or other errors occur

    Example:
        >>> from shapely.geometry import Point
        >>> point = Point(153.0, -27.5)
        >>> # Remote URL with geometry
        >>> data, profile = read_cog("https://s3.../file.tif", geometry=point)
        >>> # Local file, entire raster
        >>> data, profile = read_cog("/path/to/local/file.tif")
    """
    try:
        with rasterio.open(file_path) as src:
            # Validate CRS is EPSG:4326
            if src.crs.to_string() != "EPSG:4326":
                raise SiloGeoTiffError(f"Expected EPSG:4326, got {src.crs}")

            # Calculate window from geometry if provided
            window = None
            if geometry is not None:
                try:
                    window = geometry_window(src, [geometry])
                except Exception as e:
                    raise SiloGeoTiffError(f"Failed to calculate window from geometry: {e}")

            # Read data - build parameters based on overview_level and window
            scale_factor = 2**overview_level if overview_level is not None else None

            # Calculate output shape if using overview
            out_shape = None
            if scale_factor:
                height = window.height // scale_factor if window else src.height // scale_factor
                width = window.width // scale_factor if window else src.width // scale_factor
                out_shape = (int(height), int(width))

            # Read data (band 1)
            data = src.read(1, window=window, out_shape=out_shape)

            # Apply masking if requested
            if use_mask and src.nodata is not None:
                data = np.ma.masked_equal(data, src.nodata)

            # Build profile with updated transform and dimensions
            profile = src.profile.copy()
            transform = src.window_transform(window) if window else profile.get("transform")
            profile.update({"height": data.shape[0], "width": data.shape[1], "transform": transform})

            return data, profile

    except rasterio.errors.RasterioIOError as e:
        raise SiloGeoTiffError(f"Failed to read COG from {file_path}: {e}")


def _download_full_geotiff(url: str, destination: Path, timeout: int) -> None:
    """Download entire GeoTIFF file via streaming."""
    response = requests.get(url, stream=True, timeout=timeout)
    response.raise_for_status()

    with open(destination, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def _download_geotiff_subset(
    url: str, destination: Path, geometry: Union[Point, Polygon, None], overview_level=None, use_mask=False
) -> None:
    """Download and clip GeoTIFF to geometry subset."""
    data, profile = read_cog(url, geometry, overview_level=overview_level, use_mask=use_mask)

    with rasterio.open(destination, "w", **profile) as dst:
        dst.write(data, 1)


def download_geotiff_with_subset(
    url: str,
    destination: Path,
    geometry: Optional[Union[Point, Polygon]] = None,
    overview_level=None,
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
        overview_level: Optional pyramid level for reduced resolution
                        (None=full resolution, 0=first overview, etc.)
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
        >>> download_geotiff_with_subset(url, Path("data.tif"), geometry=point, overview_level=1)
    """
    # Check if destination exists
    if destination.exists() and not force:
        logger.debug(f"File exists, skipping: {destination}")
        return False

    # Create parent directories
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Download using appropriate strategy
        if geometry is not None or overview_level is not None:
            _download_geotiff_subset(url, destination, geometry, overview_level=overview_level)
        else:
            _download_full_geotiff(url, destination, timeout)

        logger.info(f"Downloaded: {destination}")
        return True

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning(f"File not found (404): {url}")
            return False
        raise SiloGeoTiffError(f"HTTP error downloading {url}: {e}")
    except rasterio.errors.RasterioIOError as e:
        # Handle 404s from read_cog (when geometry is provided)
        if "404" in str(e) or "Not Found" in str(e):
            logger.warning(f"File not found (404): {url}")
            return False
        raise SiloGeoTiffError(f"Error reading GeoTIFF from {url}: {e}")
    except Exception as e:
        raise SiloGeoTiffError(f"Error downloading {url}: {e}")


def download_geotiff(
    variables: VariableInput,
    start_date: datetime.date,
    end_date: datetime.date,
    geometry: Union[Point, Polygon],
    output_dir: Optional[Path] = None,
    save_to_disk: bool = False,
    read_files: bool = True,
    overview_level: Optional[int] = None,
    force: bool = False,
    timeout: int = DEFAULT_GEOTIFF_TIMEOUT,
    console: Optional[Console] = None,
) -> Union[dict[str, np.ndarray], dict[str, List[Path]]]:
    """
    Download and optionally read SILO GeoTIFF files for date range and geometry.

    This unified function downloads GeoTIFF files to disk (permanently or temporarily)
    and optionally reads them into memory as numpy arrays. Files are always cached to
    enable efficient reuse, with temporary storage available for one-off queries.

    Args:
        variables: Variable preset ("daily", "monthly", "temperature", etc.),
                  variable name ("daily_rain", "max_temp", etc.),
                  or list of presets/variable names
        start_date: First date (inclusive)
        end_date: Last date (inclusive)
        geometry: Shapely geometry (Point or Polygon) for spatial subsetting.
                  To use a bounding box, create a Polygon: box(min_lon, min_lat, max_lon, max_lat)
        output_dir: Directory to save files. If None and save_to_disk=True,
                   uses default: ./DATA/silo_grids/geotiff
        save_to_disk: If False, uses session-persistent temp cache (survives across function calls
                     until system reboot). If True, files persist permanently in output_dir.
        read_files: If True, return numpy arrays (3D: time, height, width).
                   If False, return file paths only.
        overview_level: Optional pyramid level for reduced resolution
                       (None=full resolution, 0=first overview, 1=second overview, etc.)
        force: Overwrite existing files
        timeout: Request timeout in seconds (default: 300)
        console: Rich console for output

    Returns:
        If read_files=True: Dict mapping variable names to 3D numpy arrays (time, height, width)
        If read_files=False: Dict mapping variable names to lists of downloaded file paths

    Raises:
        ValueError: For invalid parameter combinations or date ranges
        SiloGeoTiffError: For download failures

    Examples:
        >>> from pathlib import Path
        >>> from datetime import date
        >>> from shapely.geometry import Point, box
        >>>
        >>> # Stream data into memory with temp caching (persists across calls)
        >>> data = download_geotiff(
        ...     variables=["daily_rain"],
        ...     start_date=date(2023, 1, 1),
        ...     end_date=date(2023, 1, 31),
        ...     geometry=Point(153.0, -27.5),
        ...     save_to_disk=False,  # Uses temp cache, reuses cached files
        ...     read_files=True,
        ...     overview_level=1  # 4x reduced resolution
        ... )
        >>>
        >>> # Download and cache files with bounding box
        >>> bbox = box(150.5, -28.5, 154.0, -26.0)
        >>> files = download_geotiff(
        ...     variables=["daily_rain", "max_temp"],
        ...     start_date=date(2023, 1, 1),
        ...     end_date=date(2023, 1, 31),
        ...     geometry=bbox,
        ...     output_dir=Path("./data"),
        ...     save_to_disk=True,
        ...     read_files=False
        ... )
    """
    # Initialize console if not provided
    if console is None:
        console = get_console()

    # Validate date range
    if start_date > end_date:
        raise ValueError(f"start_date ({start_date}) must be <= end_date ({end_date})")

    # Warn about future dates
    today = datetime.date.today()
    if start_date > today:
        logger.warning(f"[yellow]start_date ({start_date}) is in the future - no data will be available[/yellow]")
    elif end_date > today:
        logger.warning(f"[yellow]end_date ({end_date}) is in the future - some dates may not have data available[/yellow]")

    # Generate date sequence
    date_list = _generate_date_range(start_date, end_date)

    # Validate variables and get metadata
    metadata_map = validate_silo_s3_variables(variables, ValueError)

    # Determine cache directory
    if save_to_disk:
        # Use permanent storage
        if output_dir is None:
            cache_dir = Path.cwd() / "DATA" / "silo_grids" / "geotiff"
        else:
            cache_dir = output_dir
    else:
        # Use session-persistent temp cache (not cleaned up automatically)
        # Files persist across function calls and even across sessions until system reboot
        cache_dir = Path(tempfile.gettempdir()) / "weather_tools_cache" / "geotiff"

    # Build download task list
    download_tasks = []
    read_tasks = {var: [] for var in metadata_map.keys()}
    for var_name, _ in metadata_map.items():
        for date in date_list:
            # Construct URL and destination path
            url = construct_geotiff_daily_url(var_name, date)
            dest_path = cache_dir / var_name / str(date.year) / f"{date.strftime('%Y%m%d')}.{var_name}.tif"

            read_tasks[var_name].append(dest_path)
            if not dest_path.exists() or force:
                download_tasks.append((var_name, date, url, dest_path))

    # Download files with progress bar
    downloaded_files = {var: [] for var in metadata_map.keys()}

    with create_download_progress(console=console, show_percentage=True) as progress:
        task_id = progress.add_task("[cyan]Downloading GeoTIFFs...", total=len(download_tasks))

        for var_name, date, url, dest_path in download_tasks:
            progress.update(task_id, description=f"[cyan]Downloading {var_name} {date}...")

            try:
                downloaded = download_geotiff_with_subset(url, dest_path, geometry, overview_level, force, timeout)
                if downloaded:
                    downloaded_files[var_name].append(dest_path)
            except SiloGeoTiffError as e:
                logger.warning(f"[yellow]Warning: {e}[/yellow]")

            progress.advance(task_id)

    # Print download summary
    logger.info("\n[bold green]Download Summary:[/bold green]")
    for var_name, files in downloaded_files.items():
        logger.info(f"  {var_name}: {len(files)} files")

    # If read_files=False, return file paths
    if not read_files:
        return read_tasks

    # Read files into memory as numpy arrays
    results = {}
    for var_name, file_paths in read_tasks.items():
        if not file_paths:
            logger.warning(f"[yellow]No files downloaded for {var_name}[/yellow]")
            continue

        logger.info(f"[cyan]Reading {var_name} into memory...[/cyan]")
        arrays = []

        for file_path in file_paths:
            try:
                data, profile = read_cog(f"file://{file_path.absolute()}", geometry, overview_level)
                arrays.append(data)
            except SiloGeoTiffError as e:
                logger.warning(f"[yellow]Failed to read {file_path}: {e}[/yellow]")

        # Stack arrays into 3D array (time, height, width)
        if arrays:
            profile.update({"count": len(arrays)})
            results[var_name] = np.stack(arrays, axis=0), profile
            logger.info(f"[green]Loaded {var_name}: {results[var_name][0].shape}[/green]")
        else:
            logger.warning(f"[yellow]No data loaded for {var_name}[/yellow]")

    return results
