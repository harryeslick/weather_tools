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

__all__ = ["get_console", "configure_logging", "ensure_logging_configured", "resolve_log_level"]

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
    """

    console = get_console()
    root_logger = logging.getLogger()

    # Avoid registering duplicate Rich handlers if configure_logging is called
    # multiple times (e.g. by tests importing the CLI).
    numeric_level = resolve_log_level(level)

    for handler in root_logger.handlers:
        if isinstance(handler, RichHandler) and getattr(handler, "_weather_tools_handler", False):
            root_logger.setLevel(numeric_level)
            return

    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=rich_tracebacks,
        markup=True,
        show_path=show_path,
    )
    rich_handler.setFormatter(logging.Formatter("%(message)s"))
    # Flag the handler so future configure_logging calls can detect it.
    setattr(rich_handler, "_weather_tools_handler", True)

    root_logger.addHandler(rich_handler)
    root_logger.setLevel(numeric_level)


def ensure_logging_configured(
    level: int | str = logging.INFO,
    *,
    rich_tracebacks: bool = True,
    show_path: bool = False,
) -> None:
    """Ensure a Rich-backed logging handler is attached.

    This helper is safe to call multiple times. If the weather_tools Rich handler
    has already been registered, it simply adjusts the root logger level when
    needed; otherwise it delegates to :func:`configure_logging`.
    """

    root_logger = logging.getLogger()
    numeric_level = resolve_log_level(level)

    for handler in root_logger.handlers:
        if isinstance(handler, RichHandler) and getattr(handler, "_weather_tools_handler", False):
            if root_logger.level > numeric_level:
                root_logger.setLevel(numeric_level)
            return

    configure_logging(level=numeric_level, rich_tracebacks=rich_tracebacks, show_path=show_path)
