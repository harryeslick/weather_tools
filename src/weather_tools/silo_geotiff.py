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
from rasterio.features import geometry_mask, geometry_window
from rich.console import Console
from rich.logging import RichHandler
from shapely.geometry import Point, Polygon

from weather_tools.config import get_silo_data_dir
from weather_tools.logging_utils import configure_logging, create_download_progress, get_console
from weather_tools.silo_variables import (
    DEFAULT_GEOTIFF_TIMEOUT,
    SILO_GEOTIFF_BASE_URL,
    VARIABLES,
    SiloGeoTiffError,
    VariableInput,
)

logger = logging.getLogger(__name__)


def _ensure_logging_configured():
    """Ensure logging is configured with RichHandler if not already done."""
    root_logger = logging.getLogger()
    has_rich_handler = any(isinstance(h, RichHandler) for h in root_logger.handlers)
    if not has_rich_handler:
        configure_logging()


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
    if variable not in VARIABLES:
        raise ValueError(f"Unknown variable: {variable}")

    metadata = VARIABLES[variable]
    var_name = metadata.netcdf_name or variable
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
    if variable not in VARIABLES:
        raise ValueError(f"Unknown variable: {variable}")

    metadata = VARIABLES[variable]
    var_name = metadata.netcdf_name or variable
    date_str = f"{year:04d}{month:02d}"

    return f"{SILO_GEOTIFF_BASE_URL}/monthly/{var_name}/{year}/{date_str}.{var_name}.tif"


def read_cog(
    file_path: str,
    geometry: Optional[Union[Point, Polygon]] = None,
    overview_level: Optional[int] = None,
    use_mask: bool = True,
) -> Tuple[Union[np.ndarray, np.ma.MaskedArray], dict]:
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
        use_mask: If True, mask pixels outside geometry and apply nodata mask.
                  If False, return regular array without masking.

    Returns:
        Tuple of (data array or masked array, rasterio profile dict).
        Returns MaskedArray when use_mask=True, regular ndarray when use_mask=False.

    Raises:
        SiloGeoTiffError: If CRS is not EPSG:4326 or other errors occur

    Example:
        >>> from shapely.geometry import Point
        >>> point = Point(153.0, -27.5)
        >>> # Remote URL with geometry and masking
        >>> data, profile = read_cog("https://s3.../file.tif", geometry=point, use_mask=True)
        >>> # Local file, entire raster without masking
        >>> data, profile = read_cog("/path/to/local/file.tif", use_mask=False)
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

            # Build profile with updated transform and dimensions
            profile = src.profile.copy()
            transform = src.window_transform(window) if window else profile.get("transform")
            if scale_factor:
                original_height = window.height if window else src.height
                original_width = window.width if window else src.width
                transform = transform * transform.scale(
                    (original_width / data.shape[-1]), (original_height / data.shape[-2])
                )

            profile.update(
                {"height": data.shape[0], "width": data.shape[1], "transform": transform}
            )

            # Apply masking if requested
            if use_mask:
                # Create mask for pixels outside geometry
                mask = np.zeros(data.shape, dtype=bool)

                if geometry is not None:
                    # Use geometry_mask to identify pixels outside the geometry
                    # geometry_mask returns True for pixels OUTSIDE the geometry
                    geom_mask = geometry_mask(
                        [geometry],
                        out_shape=data.shape,
                        transform=transform,
                        invert=False,
                        all_touched=True,
                    )
                    mask |= geom_mask

                # Also mask nodata values
                if src.nodata is not None:
                    mask |= data == src.nodata

                # Create masked array
                data = np.ma.masked_array(data, mask=mask)

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
    url: str,
    destination: Path,
    geometry: Union[Point, Polygon, None],
    overview_level=None,
) -> None:
    """Download and clip GeoTIFF to geometry subset."""
    data, profile = read_cog(url, geometry, overview_level=overview_level)

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


def download_geotiffs(
    variables: VariableInput,
    start_date: datetime.date,
    end_date: datetime.date,
    geometry: Union[Point, Polygon],
    output_dir: Optional[Path] = None,
    save_to_disk: bool = False,
    overview_level: Optional[int] = None,
    force: bool = False,
    timeout: int = DEFAULT_GEOTIFF_TIMEOUT,
    console: Optional[Console] = None,
) -> dict[str, List[Path]]:
    """
    Download SILO GeoTIFF files for date range and geometry.

    This function downloads GeoTIFF files to disk (permanently or temporarily)
    and returns the paths to downloaded files. Files are always cached to
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
                   uses SILO_DATA_DIR/geotiff (or ~/DATA/silo_grids/geotiff by default)
        save_to_disk: If False, uses session-persistent temp cache (survives across function calls
                     until system reboot). If True, files persist permanently in output_dir.
        overview_level: Optional pyramid level for reduced resolution
                       (None=full resolution, 0=first overview, 1=second overview, etc.)
        force: Overwrite existing files
        timeout: Request timeout in seconds (default: 300)
        console: Rich console for output

    Returns:
        Dict mapping variable names to lists of downloaded file paths

    Raises:
        ValueError: For invalid parameter combinations or date ranges
        SiloGeoTiffError: For download failures

    Examples:
        >>> from pathlib import Path
        >>> from datetime import date
        >>> from shapely.geometry import Point, box
        >>>
        >>> # Download with temp caching (persists across calls)
        >>> files = download_geotiffs(
        ...     variables=["daily_rain"],
        ...     start_date=date(2023, 1, 1),
        ...     end_date=date(2023, 1, 31),
        ...     geometry=Point(153.0, -27.5),
        ...     save_to_disk=False,  # Uses temp cache
        ...     overview_level=1  # 4x reduced resolution
        ... )
        >>>
        >>> # Download and cache files with bounding box
        >>> bbox = box(150.5, -28.5, 154.0, -26.0)
        >>> files = download_geotiffs(
        ...     variables=["daily_rain", "max_temp"],
        ...     start_date=date(2023, 1, 1),
        ...     end_date=date(2023, 1, 31),
        ...     geometry=bbox,
        ...     output_dir=Path("./data"),
        ...     save_to_disk=True
        ... )
    """
    # Ensure logging is configured for Rich markup
    _ensure_logging_configured()

    # Initialize console if not provided
    if console is None:
        console = get_console()

    # Validate date range
    if start_date > end_date:
        raise ValueError(f"start_date ({start_date}) must be <= end_date ({end_date})")

    # Warn about future dates
    today = datetime.date.today()
    if start_date > today:
        logger.warning(
            f"[yellow]start_date ({start_date}) is in the future - no data will be available[/yellow]"
        )
    elif end_date > today:
        logger.warning(
            f"[yellow]end_date ({end_date}) is in the future - some dates may not have data available[/yellow]"
        )

    # Generate date sequence
    date_list = _generate_date_range(start_date, end_date)

    # Validate variables and get metadata
    metadata_map = VARIABLES.validate(variables, ValueError)

    # Determine cache directory
    if save_to_disk:
        # Use permanent storage
        if output_dir is None:
            cache_dir = get_silo_data_dir() / "geotiff"
        else:
            cache_dir = output_dir
    else:
        # Use session-persistent temp cache (not cleaned up automatically)
        # Files persist across function calls and even across sessions until system reboot
        cache_dir = Path(tempfile.gettempdir()) / "weather_tools_cache" / "geotiff"

    # Build download task list
    download_tasks = []
    file_paths = {var: [] for var in metadata_map.keys()}
    for var_name, _ in metadata_map.items():
        for date in date_list:
            # Construct URL and destination path
            url = construct_geotiff_daily_url(var_name, date)
            dest_path = (
                cache_dir / var_name / str(date.year) / f"{date.strftime('%Y%m%d')}.{var_name}.tif"
            )

            file_paths[var_name].append(dest_path)
            if not dest_path.exists() or force:
                download_tasks.append((var_name, date, url, dest_path))

    # Download files with progress bar
    downloaded_files = {var: set() for var in metadata_map.keys()}

    with create_download_progress(console=console, show_percentage=True) as progress:
        task_id = progress.add_task("[cyan]Downloading GeoTIFFs...", total=len(download_tasks))

        for var_name, date, url, dest_path in download_tasks:
            progress.update(task_id, description=f"[cyan]Downloading {var_name} {date}...")

            try:
                downloaded = download_geotiff_with_subset(
                    url, dest_path, geometry, overview_level, force, timeout
                )
                if downloaded:
                    downloaded_files[var_name].add(dest_path)
            except SiloGeoTiffError as e:
                logger.warning(f"[yellow]Warning: {e}[/yellow]")

            progress.advance(task_id)

    # Print download summary
    logger.info("\n[bold green]Download Summary:[/bold green]")
    for var_name, files in downloaded_files.items():
        logger.info(f"  {var_name}: {len(files)} files")

    # Return paths to files that exist or were downloaded
    return {
        var: [p for p in paths if p.exists() or p in downloaded_files[var]]
        for var, paths in file_paths.items()
    }


def read_geotiff_stack(
    file_paths: dict[str, List[Path]],
    filter_incomplete_dates: bool = True,
    console: Optional[Console] = None,
) -> dict[str, tuple[np.ndarray, dict]]:
    """
    Read GeoTIFF files into memory as stacked numpy arrays.

    This function reads downloaded GeoTIFF files and stacks them along the time dimension.
    Optionally filters to only include dates where all variables have data available.

    Args:
        file_paths: Dict mapping variable names to lists of file paths
        filter_incomplete_dates: If True, only read dates where all variables have files.
                                If False, read all available files (arrays may have different lengths)
        console: Rich console for output

    Returns:
        Dict mapping variable names to tuples of (3D numpy array, rasterio profile).
        Arrays have shape (time, height, width).

    Raises:
        SiloGeoTiffError: If file reading fails

    Examples:
        >>> from pathlib import Path
        >>>
        >>> # Read files with filtering for complete dates
        >>> file_paths = {
        ...     "daily_rain": [Path("20230101.daily_rain.tif"), Path("20230102.daily_rain.tif")],
        ...     "max_temp": [Path("20230101.max_temp.tif"), Path("20230102.max_temp.tif")]
        ... }
        >>> results = read_geotiff_stack(file_paths, filter_incomplete_dates=True)
        >>> data, profile = results["daily_rain"]
        >>> data.shape  # (2, height, width)
        >>>
        >>> # Read all files without filtering
        >>> results = read_geotiff_stack(file_paths, filter_incomplete_dates=False)
    """
    # Ensure logging is configured for Rich markup
    _ensure_logging_configured()

    # Initialize console if not provided
    if console is None:
        console = get_console()

    # Filter to only existing files
    existing_file_paths = {
        var: [p for p in paths if p.exists()] for var, paths in file_paths.items()
    }

    # Filter for complete date sets if requested
    if filter_incomplete_dates and len(existing_file_paths) > 1:
        # Flatten the nested list structure using list comprehension
        files = [item for sublist in existing_file_paths.values() for item in sublist]
        arr = np.array([f.stem.split(".")[0] for f in files])
        unique_values, counts = np.unique(arr, return_counts=True)
        # find dates where a full set of files exists
        complete_dates = unique_values[counts == len(existing_file_paths)]
        missing_dates = unique_values[counts != len(existing_file_paths)]
        if len(missing_dates) > 0:
            console.log(f"Some layers missing for dates: {missing_dates}")

        # only read files where a full set exists, output arrays should be the same shape
        existing_file_paths = {
            var: [p for p in paths if p.stem.split(".")[0] in complete_dates]
            for var, paths in existing_file_paths.items()
        }

    # Read files into memory as numpy arrays
    results = {}
    for var_name, file_list in existing_file_paths.items():
        if not file_list:
            logger.warning(f"[yellow]No files available for {var_name}[/yellow]")
            continue

        logger.info(f"[cyan]Reading {var_name} into memory...[/cyan]")
        arrays = []
        profile = None

        for file_path in file_list:
            try:
                data, file_profile = read_cog(
                    f"file://{file_path.absolute()}",
                )  # geometry, overview_level already applied when downloading
                arrays.append(data)
                profile = file_profile  # Keep the last profile
            except SiloGeoTiffError as e:
                logger.warning(f"[yellow]Failed to read {file_path}: {e}[/yellow]")

        # Stack arrays into 3D array (time, height, width)
        if arrays and profile is not None:
            # Update profile to reflect stacked data
            profile.update({"count": len(arrays)})
            stacked_array = np.stack(arrays, axis=0)
            results[var_name] = (stacked_array, profile)
            logger.info(f"[green]Loaded {var_name}: {stacked_array.shape}[/green]")
        else:
            logger.warning(f"[yellow]No data loaded for {var_name}[/yellow]")

    return results


def download_and_read_geotiffs(
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
    filter_incomplete_dates: bool = True,
    console: Optional[Console] = None,
) -> Union[dict[str, tuple[np.ndarray, dict]], dict[str, List[Path]]]:
    """
    Download and optionally read SILO GeoTIFF files for date range and geometry.

    This convenience function combines downloading and reading operations.
    Use `download_geotiffs()` and `read_geotiff_stack()` separately for more control.

    Args:
        variables: Variable preset ("daily", "monthly", "temperature", etc.),
                  variable name ("daily_rain", "max_temp", etc.),
                  or list of presets/variable names
        start_date: First date (inclusive)
        end_date: Last date (inclusive)
        geometry: Shapely geometry (Point or Polygon) for spatial subsetting.
                  To use a bounding box, create a Polygon: box(min_lon, min_lat, max_lon, max_lat)
        output_dir: Directory to save files. If None and save_to_disk=True,
                   uses SILO_DATA_DIR/geotiff (or ~/DATA/silo_grids/geotiff by default)
        save_to_disk: If False, uses session-persistent temp cache (survives across function calls
                     until system reboot). If True, files persist permanently in output_dir.
        read_files: If True, return numpy arrays (3D: time, height, width).
                   If False, return file paths only.
        overview_level: Optional pyramid level for reduced resolution
                       (None=full resolution, 0=first overview, 1=second overview, etc.)
        force: Overwrite existing files
        timeout: Request timeout in seconds (default: 300)
        filter_incomplete_dates: If True and read_files=True, only read dates where all
                                variables have data. If False, read all available files.
        console: Rich console for output

    Returns:
        If read_files=True: Dict mapping variable names to (3D numpy array, rasterio profile) tuples
        If read_files=False: Dict mapping variable names to lists of file paths

    Raises:
        ValueError: For invalid parameter combinations or date ranges
        SiloGeoTiffError: For download or read failures

    Examples:
        >>> from pathlib import Path
        >>> from datetime import date
        >>> from shapely.geometry import Point, box
        >>>
        >>> # Download and read into memory
        >>> results = download_and_read_geotiffs(
        ...     variables=["daily_rain"],
        ...     start_date=date(2023, 1, 1),
        ...     end_date=date(2023, 1, 31),
        ...     geometry=Point(153.0, -27.5),
        ...     save_to_disk=False,
        ...     read_files=True
        ... )
        >>> data, profile = results["daily_rain"]
        >>>
        >>> # Download only (return paths)
        >>> files = download_and_read_geotiffs(
        ...     variables=["daily_rain", "max_temp"],
        ...     start_date=date(2023, 1, 1),
        ...     end_date=date(2023, 1, 31),
        ...     geometry=box(150.5, -28.5, 154.0, -26.0),
        ...     output_dir=Path("./data"),
        ...     save_to_disk=True,
        ...     read_files=False
        ... )
    """

    # Ensure logging is configured for Rich markup
    _ensure_logging_configured()

    # Download files
    file_paths = download_geotiffs(
        variables=variables,
        start_date=start_date,
        end_date=end_date,
        geometry=geometry,
        output_dir=output_dir,
        save_to_disk=save_to_disk,
        overview_level=overview_level,
        force=force,
        timeout=timeout,
        console=console,
    )

    # Return file paths if not reading
    if not read_files:
        return file_paths

    # Read files into memory
    return read_geotiff_stack(
        file_paths=file_paths,
        filter_incomplete_dates=filter_incomplete_dates,
        console=console,
    )


# Backward compatibility alias
download_geotiff = download_and_read_geotiffs
