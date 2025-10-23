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

__all__ = ["get_console", "configure_logging", "get_package_logger", "resolve_log_level"]

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
