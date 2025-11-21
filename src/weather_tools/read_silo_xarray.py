from pathlib import Path

import xarray as xr

from weather_tools.config import get_silo_data_dir
from weather_tools.silo_variables import VARIABLES, VariableInput


def read_silo_xarray(
    variables: VariableInput = "daily",
    silo_dir: Path | None = None,
) -> xr.Dataset:
    """
    Read SILO data from a directory containing the SILO netCDF files and return a merged xarray dataset.

    Args:
        variables: Variable preset ("daily", "monthly", "temperature", etc.),
                  variable name ("daily_rain", "max_temp", etc.),
                  or list of presets/variable names. Defaults to "daily".
        silo_dir: Path to the directory containing variable subdirectories (each containing .nc files).
            If None, uses the directory from SILO_DATA_DIR environment variable or
            defaults to ~/DATA/silo_grids.
            Expects the following structure:
                silo_dir/
                ├── daily_rain
                ├── evap_syn
                ├── max_temp
                ├── min_temp
                └── monthly_rain
                    ├── ...
                    ├── 2023.monthly_rain.nc
                    └── 2024.monthly_rain.nc

    Returns:
        xr.Dataset: merged xarray Dataset containing the requested variables concatenated along the
        'time' dimension. Coordinates typically include 'time', 'lat', and 'lon'.

    Example:
        >>> from pathlib import Path
        >>> from weather_tools.read_silo_xarray import read_silo_xarray
        >>> # Read the daily variables from the default silo_dir
        >>> ds = read_silo_xarray(variables="daily")
        >>> print(ds)
        >>> # Or specify variables explicitly and a custom directory
        >>> ds2 = read_silo_xarray(variables=["monthly_rain"], silo_dir=Path("/data/silo_grids"))
        >>> make a smaller subset to reduce size in memeory
        >>> ds3 = read_silo_xarray().sel(lat=slice(-39, -26), lon=slice(133, 154), time=slice("2020-01-01", "2025-01-01")).compute()
        >>> print(ds3)

    """
    # Use environment variable or default if silo_dir not provided
    if silo_dir is None:
        silo_dir = get_silo_data_dir()

    # Use centralized variable preset expansion
    variables = VARIABLES.expand_preset(variables)

    dss = []
    for variable in variables:
        # Convert generator to sorted list of file paths
        file_paths = sorted((silo_dir / variable).glob("*.nc"))

        # Use open_mfdataset to open all years for a single variable
        ds = xr.open_mfdataset(
            file_paths,
            chunks={"time": "auto"},
            combine="nested",  # Use nested combining for files that share dimensions
            concat_dim="time",  # Dimension along which to concatenate
            data_vars="minimal",  # Only data variables in which concat_dim appears are included
            compat="no_conflicts",  # Values must be equal or have disjoint (non-overlapping) coordinates
            join="outer",  # Use outer join for combining coordinates
            # parallel=True  # Enable parallel processing if needed
        ).sortby("time")  # Ensure the 'time' dimension is sorted
        dss.append(ds)

    # merge combines different variables with the same dimensions (eg. time, lat, lon)
    merged = xr.merge(dss, compat="override")
    [ds.close() for ds in dss]
    return merged
