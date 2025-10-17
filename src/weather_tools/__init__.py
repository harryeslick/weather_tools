
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
]
