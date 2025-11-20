"""Shared logging utilities for weather_tools.

This module provides a single Rich console instance and helper functions
for configuring logging across the package. All user-facing messaging
should go through the standard logging APIs so output can be routed to
both the Rich console for CLI use and any other handlers configured by
calling code.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

__all__ = [
    "get_console",
    "configure_logging",
    "get_package_logger",
    "resolve_log_level",
    "create_download_progress",
]

_LEVEL_MAP = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}


def resolve_log_level(level: int | str) -> int:
    """Convert a logging level (name or numeric) to an integer."""

    if isinstance(level, str):
        try:
            return _LEVEL_MAP[level.upper()]
        except KeyError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid logging level string: {level}") from exc
    if isinstance(level, int):
        return level
    raise TypeError(f"Invalid logging level type: {type(level)!r}")


@lru_cache(maxsize=1)
def get_console() -> Console:
    """Return the shared Rich console instance.

    A single console is reused so that Rich progress bars and logging share
    the same output device, ensuring clean rendering when multiple features
    are active at once.
    """

    return Console()


def configure_logging(
    level: int | str = logging.INFO,
    *,
    rich_tracebacks: bool = True,
    show_path: bool = False,
) -> None:
    """Configure logging for weather_tools using Rich.

    This attaches a RichHandler to the root logger (if one is not already
    present) so that all log records render via Rich. The handler uses the
    shared console returned by :func:`get_console` to ensure compatibility
    with progress bars and other Rich features.

    Args:
        level: Logging level (name or numeric). Applied to both root logger and handler.
        rich_tracebacks: Enable rich exception formatting.
        show_path: Show file paths in log output.

    Note:
        This function is idempotent - calling it multiple times will update
        the existing handler's level rather than creating duplicates.
    """

    console = get_console()
    root_logger = logging.getLogger()
    numeric_level = resolve_log_level(level)

    # Check if our handler is already attached
    for handler in root_logger.handlers:
        if isinstance(handler, RichHandler) and getattr(handler, "_weather_tools_handler", False):
            # Update both root logger and handler levels
            root_logger.setLevel(numeric_level)
            handler.setLevel(numeric_level)
            return

    # Remove any existing non-RichHandler handlers to avoid duplicate output
    # This can happen if other packages add their own handlers to the root logger
    handlers_to_remove = [h for h in root_logger.handlers if not isinstance(h, RichHandler)]
    for handler in handlers_to_remove:
        root_logger.removeHandler(handler)

    # Create and attach new handler
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=rich_tracebacks,
        markup=True,
        show_path=show_path,
    )
    rich_handler.setLevel(numeric_level)  # Set level on handler
    rich_handler.setFormatter(logging.Formatter("%(message)s"))
    setattr(rich_handler, "_weather_tools_handler", True)

    root_logger.addHandler(rich_handler)
    root_logger.setLevel(numeric_level)


@lru_cache(maxsize=1)
def get_package_logger() -> logging.Logger:
    """Get the package-level logger for weather_tools.

    This logger sits at the top of the weather_tools.* hierarchy and can be
    used to control logging verbosity for the entire package without affecting
    other libraries or the root logger.

    Returns:
        The weather_tools package logger.

    Example:
        >>> # Control all weather_tools logging
        >>> pkg_logger = get_package_logger()
        >>> pkg_logger.setLevel(logging.DEBUG)
    """
    return logging.getLogger("weather_tools")


def create_download_progress(
    console: Console | None = None, show_percentage: bool = False
) -> Progress:
    """Create standardized progress bar for downloads.

    This factory function creates a Rich Progress instance configured with
    the standard columns for download operations across weather_tools.

    Args:
        console: Optional Console instance. If None, uses the shared console from get_console().
        show_percentage: If True, adds a percentage column to the progress bar.

    Returns:
        Configured Progress instance ready for use with download operations.

    Example:
        >>> with create_download_progress(show_percentage=True) as progress:
        ...     task_id = progress.add_task("Downloading...", total=100)
        ...     for i in range(100):
        ...         progress.update(task_id, advance=1)
    """
    columns = [
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
    ]

    if show_percentage:
        columns.append(TextColumn("[progress.percentage]{task.percentage:>3.0f}%"))

    columns.extend(
        [
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ]
    )

    return Progress(*columns, console=console or get_console())
