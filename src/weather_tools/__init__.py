from __future__ import annotations

__version__ = "0.0.2"

from weather_tools.cli import main as cli_main
from weather_tools.read_silo_xarray import read_silo_xarray
from weather_tools.silo_api import SiloAPI, SiloAPIError
from weather_tools.silo_geotiff import (
    construct_geotiff_daily_url,
    construct_geotiff_monthly_url,
    download_and_read_geotiffs,
    download_geotiff,
    download_geotiffs,
    read_geotiff_stack,
)
from weather_tools.silo_models import (
    AustralianCoordinates,
    DataDrillQuery,
    PatchedPointQuery,
    SiloDataset,
    SiloDateRange,
    SiloFormat,
    SiloResponse,
)
from weather_tools.silo_netcdf import download_netcdf
from weather_tools.silo_variables import (
    API_TO_NETCDF,
    SILO_VARIABLES,
    VARIABLE_PRESETS,
    VARIABLES,
    SiloDataError,
    SiloGeoTiffError,
    SiloNetCDFError,
    VariableRegistry,
)

__all__ = [
    "read_silo_xarray",
    "cli_main",
    "SiloAPI",
    "SiloAPIError",
    "AustralianCoordinates",
    "DataDrillQuery",
    "PatchedPointQuery",
    "SiloDataset",
    "SiloDateRange",
    "SiloFormat",
    "SiloResponse",
    "download_netcdf",
    "download_geotiff",
    "download_geotiffs",
    "read_geotiff_stack",
    "download_and_read_geotiffs",
    "construct_geotiff_daily_url",
    "construct_geotiff_monthly_url",
    "SiloDataError",
    "SiloNetCDFError",
    "SiloGeoTiffError",
    "VARIABLES",
    "VariableRegistry",
    "SILO_VARIABLES",
    "API_TO_NETCDF",
    "VARIABLE_PRESETS",
]
