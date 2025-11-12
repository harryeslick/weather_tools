"""Centralized configuration for weather_tools package.

This module provides configuration constants and environment variable handling
for the weather_tools package, particularly for SILO data directory locations.
"""

import os
from pathlib import Path


def get_silo_data_dir() -> Path:
    """Get the SILO data directory from environment variable or default.

    The directory can be configured via the SILO_DATA_DIR environment variable.
    If not set, defaults to ~/DATA/silo_grids.

    Returns:
        Path to the SILO data directory (not guaranteed to exist)

    Example:
        >>> # Using default
        >>> dir_path = get_silo_data_dir()
        >>> # Using environment variable
        >>> os.environ['SILO_DATA_DIR'] = '/custom/path'
        >>> dir_path = get_silo_data_dir()
    """
    env_dir = os.environ.get('SILO_DATA_DIR')
    if env_dir:
        return Path(env_dir).expanduser()
    return Path.home() / "DATA" / "silo_grids"


# Default SILO data directory - uses environment variable if set
DEFAULT_SILO_DIR = get_silo_data_dir()
