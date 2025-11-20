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
    ClimateVariable,
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
    NETCDF_TO_API,
    SILO_VARIABLES,
    VARIABLE_PRESETS,
    SiloDataError,
    SiloGeoTiffError,
    SiloNetCDFError,
    expand_variable_preset,
    get_variable_metadata,
    validate_silo_s3_variables,
)

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
    "SILO_VARIABLES",
    "NETCDF_TO_API",
    "API_TO_NETCDF",
    "VARIABLE_PRESETS",
    "get_variable_metadata",
    "expand_variable_preset",
    "validate_silo_s3_variables",
]
