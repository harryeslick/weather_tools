"""
Download SILO gridded NetCDF files from AWS S3 public data.

This module provides functionality to download climate data files that can be
used with the local NetCDF processing functions.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from rich.console import Console
from rich.progress import Progress, TaskID

from weather_tools.logging_utils import create_download_progress, get_console
from weather_tools.silo_variables import (
    DEFAULT_NETCDF_TIMEOUT,
    SILO_NETCDF_BASE_URL,
    SiloNetCDFError,
    VariableInput,
    get_variable_metadata,
    validate_silo_s3_variables,
)

logger = logging.getLogger(__name__)


def construct_netcdf_url(variable: str, year: int) -> str:
    """
    Construct the S3 download URL for a SILO NetCDF file.

    Args:
        variable: NetCDF variable name (e.g., "daily_rain", "max_temp")
        year: Year (e.g., 2023)

    Returns:
        Full S3 URL

    Example:
        >>> construct_netcdf_url("daily_rain", 2023)
        'https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/daily_rain/2023.daily_rain.nc'
    """
    filename = f"{year}.{variable}.nc"
    return f"{SILO_NETCDF_BASE_URL}/{variable}/{filename}"


def validate_year_for_variable(variable: str, year: int) -> bool:
    """
    Check if a year is valid for a given variable.

    Args:
        variable: NetCDF variable name
        year: Year to validate

    Returns:
        True if valid, False otherwise
    """
    metadata = get_variable_metadata(variable)
    if metadata is None:
        return False

    current_year = datetime.now().year
    return metadata.start_year <= year <= current_year


def download_file(
    url: str,
    destination: Path,
    force: bool = False,
    timeout: int = DEFAULT_NETCDF_TIMEOUT,
    progress: Optional[Progress] = None,
    task_id: Optional[TaskID] = None,
) -> bool:
    """
    Download a file from a URL to a destination path.

    Args:
        url: URL to download from
        destination: Local file path to save to
        force: If True, overwrite existing files
        timeout: Request timeout in seconds
        progress: Optional rich Progress instance for progress tracking
        task_id: Optional task ID for progress updates

    Returns:
        True if downloaded, False if skipped (file exists and not force)

    Raises:
        SiloNetCDFError: If download fails
    """
    # Check if file exists
    if destination.exists() and not force:
        logger.info(f"Skipping existing file: {destination}")
        if progress and task_id is not None:
            # Mark as complete without downloading
            file_size = destination.stat().st_size
            progress.update(task_id, completed=file_size, total=file_size)
        return False

    # Create parent directory if needed
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Stream download with progress tracking
        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()

        # Get total file size
        total_size = int(response.headers.get("content-length", 0))

        # Initialize progress task if provided
        if progress and task_id is not None:
            progress.update(task_id, total=total_size)

        # Download in chunks
        chunk_size = 8192
        downloaded = 0

        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress and task_id is not None:
                        progress.update(task_id, completed=downloaded)

        logger.info(f"Downloaded: {destination}")
        return True

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise SiloNetCDFError(f"File not found: {url}") from e
        else:
            raise SiloNetCDFError(f"HTTP error downloading {url}: {e}") from e
    except requests.exceptions.RequestException as e:
        raise SiloNetCDFError(f"Failed to download {url}: {e}") from e
    except IOError as e:
        raise SiloNetCDFError(f"Failed to write file {destination}: {e}") from e


def download_netcdf(
    variables: VariableInput,
    start_year: int,
    end_year: int,
    output_dir: Path,
    force: bool = False,
    timeout: int = DEFAULT_NETCDF_TIMEOUT,
    console: Optional[Console] = None,
) -> dict[str, list[Path]]:
    """
    Download SILO NetCDF files from AWS S3.

    Args:
        variables: Variable preset ("daily", "monthly", "temperature", etc.),
                  variable name ("daily_rain", "max_temp", etc.),
                  or list of presets/variable names
        start_year: First year to download (inclusive)
        end_year: Last year to download (inclusive)
        output_dir: Directory to save files (will create subdirs per variable)
        force: If True, overwrite existing files
        timeout: Request timeout in seconds (default: 600)
        console: Optional rich Console for output

    Returns:
        Dictionary mapping variable names to lists of downloaded file paths

    Raises:
        ValueError: If invalid variables or year range
        SiloNetCDFError: If download fails

    Example:
        >>> from pathlib import Path
        >>> downloaded = download_netcdf(
        ...     variables="daily",
        ...     start_year=2020,
        ...     end_year=2023,
        ...     output_dir=Path.home() / "DATA/silo_grids"
        ... )
        >>> print(downloaded)
        {'daily_rain': [Path(...), ...], 'max_temp': [...], ...}
    """
    if console is None:
        console = get_console()

    # Validate variables and get metadata
    metadata_map = validate_silo_s3_variables(variables, ValueError)

    # Validate year range
    if start_year > end_year:
        raise ValueError(f"start_year ({start_year}) must be <= end_year ({end_year})")

    current_year = datetime.now().year
    if end_year > current_year:
        raise ValueError(
            f"end_year ({end_year}) cannot be in the future (current year: {current_year})"
        )

    # Build download list
    download_tasks = []
    for var, metadata in metadata_map.items():
        for year in range(start_year, end_year + 1):
            # Skip years before variable starts
            if year < metadata.start_year:
                logger.warning(
                    f"[yellow]Skipping {var} for {year} (data starts in {metadata.start_year})[/yellow]"
                )
                continue

            url = construct_netcdf_url(var, year)
            dest = output_dir / var / f"{year}.{var}.nc"
            download_tasks.append((var, year, url, dest))

    if not download_tasks:
        logger.info("[yellow]No files to download[/yellow]")
        return {}

    # Display summary
    var_list = list(metadata_map.keys())
    logger.info("\n[bold]Downloading SILO NetCDF data...[/bold]")
    logger.info(f"  Variables: {', '.join(var_list)} ({len(var_list)} variable(s))")
    logger.info(f"  Years: {start_year}-{end_year} ({end_year - start_year + 1} year(s))")
    logger.info(f"  Total files: {len(download_tasks)}")
    logger.info(f"  Output directory: {output_dir}\n")

    # Download with progress tracking
    downloaded_files = {var: [] for var in var_list}

    with create_download_progress(console=console, show_percentage=False) as progress:
        for idx, (var, year, url, dest) in enumerate(download_tasks, 1):
            task_desc = f"[{idx}/{len(download_tasks)}] {var}/{year}.{var}.nc"
            task_id = progress.add_task(task_desc, total=None)

            try:
                downloaded = download_file(
                    url=url,
                    destination=dest,
                    force=force,
                    timeout=timeout,
                    progress=progress,
                    task_id=task_id,
                )

                if downloaded:
                    downloaded_files[var].append(dest)
                    progress.update(task_id, description=f"[green]✓[/green] {task_desc}")
                else:
                    progress.update(
                        task_id, description=f"[yellow]↷[/yellow] {task_desc} (skipped)"
                    )

            except SiloNetCDFError as e:
                progress.update(task_id, description=f"[red]✗[/red] {task_desc}")
                logger.error(f"[red]Error: {e}[/red]")
                # Continue with next file rather than failing completely

    # Summary
    total_downloaded = sum(len(files) for files in downloaded_files.values())
    logger.info("\n[bold green]✓[/bold green] Download complete!")
    logger.info(f"  Downloaded: {total_downloaded} file(s)")
    logger.info(f"  Skipped: {len(download_tasks) - total_downloaded} file(s)")

    return downloaded_files
