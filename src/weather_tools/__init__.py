
from __future__ import annotations

__version__ = "0.0.2"

from .cli import main as cli_main
from .read_silo_xarray import read_silo_xarray
from .silo_api import SiloAPI, SiloAPIError
from .silo_models import (
    AustralianCoordinates,
    ClimateVariable,
    DataDrillQuery,
    PatchedPointQuery,
    SiloDataset,
    SiloDateRange,
    SiloFormat,
    SiloResponse,
)
from .silo_variables import (
    SILO_VARIABLES,
    NETCDF_TO_API,
    API_TO_NETCDF,
    VARIABLE_PRESETS,
    get_variable_metadata,
    expand_variable_preset,
)
from .download_silo import download_silo_gridded, SiloDownloadError

__all__ = [
    "read_silo_xarray",
    "cli_main",
    "SiloAPI",
    "SiloAPIError",
    "AustralianCoordinates",
    "ClimateVariable",
    "DataDrillQuery",
    "PatchedPointQuery",
    "SiloDataset",
    "SiloDateRange",
    "SiloFormat",
    "SiloResponse",
    "download_silo_gridded",
    "SiloDownloadError",
    "SILO_VARIABLES",
    "NETCDF_TO_API",
    "API_TO_NETCDF",
    "VARIABLE_PRESETS",
    "get_variable_metadata",
    "expand_variable_preset",
]
