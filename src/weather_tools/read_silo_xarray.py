
from pathlib import Path

import xarray as xr


def read_silo_xarray(
    variables: list | str = "daily",
    silo_dir: Path = Path.home() / "Developer/DATA/silo_grids",
) -> xr.Dataset:
    """
    Read SILO data from a directory containing the SILO netCDF files and return a merged xarray dataset.

    Args:
        variables: list of silo variable, matching the directory names. Literal "daily"/"monthly" Defaults to "daily".
        silo_dir: _description_. Defaults to Path.home()/"Developer/DATA/silo_grids".
            expects the following structure:
                ~/Developer/DATA/silo_grids
                ├── daily_rain
                ├── evap_syn
                ├── max_temp
                ├── min_temp
                └── monthly_rain
                    ├── ...
                    ├── 2023.monthly_rain.nc
                    └── 2024.monthly_rain.nc


    Returns:
        _description_
    """
    if isinstance(variables, str):
        if variables == "daily":
            variables = ["max_temp", "min_temp", "daily_rain", "evap_syn"]
        elif variables == "monthly":
            variables = ["monthly_rain"]

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
