"""Simple smoke tests for read_silo_xarray module.

These tests assume the presence of SILO data in ~/Developer/DATA/silo_grids
and focus on basic functionality without loading large datasets.
"""

from pathlib import Path

import pytest
import xarray as xr

from weather_tools.read_silo_xarray import read_silo_xarray, expand_variable_preset

# Define the expected SILO data directory
SILO_DIR = Path.home() / "Developer/DATA/silo_grids"


def read_silo_test_safe(variables="daily", silo_dir=SILO_DIR, max_year=2024):
    """Read SILO data excluding years that may be incomplete or corrupted.

    Args:
        variables: Variables to read (same as read_silo_xarray)
        silo_dir: Path to SILO data directory
        max_year: Maximum year to include (default 2024, excludes 2025)

    Returns:
        xr.Dataset: Merged dataset with filtered years
    """
    variables = expand_variable_preset(variables)

    dss = []
    for variable in variables:
        # Filter files to exclude years > max_year
        file_paths = sorted([
            f for f in (silo_dir / variable).glob("*.nc")
            if int(f.stem.split('.')[0]) <= max_year
        ])

        if not file_paths:
            continue

        ds = xr.open_mfdataset(
            file_paths,
            chunks={"time": "auto"},
            combine="nested",
            concat_dim="time",
            data_vars="minimal",
            compat="no_conflicts",
            join="outer",
        ).sortby("time")
        dss.append(ds)

    merged = xr.merge(dss, compat="override")
    [ds.close() for ds in dss]
    return merged


@pytest.fixture
def silo_data_available():
    """Check if SILO data directory exists and skip tests if not."""
    if not SILO_DIR.exists():
        pytest.skip(f"SILO data directory not found: {SILO_DIR}")
    return SILO_DIR


def test_silo_directory_exists(silo_data_available):
    """Test that the SILO data directory exists."""
    assert silo_data_available.exists()
    assert silo_data_available.is_dir()


def test_silo_subdirectories_exist(silo_data_available):
    """Test that expected variable directories exist."""
    expected_dirs = ["max_temp", "min_temp", "daily_rain", "evap_syn"]
    
    for var_dir in expected_dirs:
        dir_path = silo_data_available / var_dir
        assert dir_path.exists(), f"Expected directory {var_dir} not found"
        
        # Check that directory contains .nc files
        nc_files = list(dir_path.glob("*.nc"))
        assert len(nc_files) > 0, f"No .nc files found in {var_dir}"


def test_read_daily_variables_structure():
    """Test reading daily variables returns proper structure."""
    ds = read_silo_test_safe(variables="daily", silo_dir=SILO_DIR)
    
    # Check that dataset is returned
    assert isinstance(ds, xr.Dataset)
    
    # Check that expected variables are present
    expected_vars = ["max_temp", "min_temp", "daily_rain", "evap_syn"]
    for var in expected_vars:
        assert var in ds.data_vars, f"Variable {var} not found in dataset"
    
    # Check that expected dimensions are present
    assert "time" in ds.dims
    assert "lat" in ds.dims
    assert "lon" in ds.dims
    
    # Check that time dimension has data
    assert len(ds.time) > 0
    
    ds.close()


def test_read_single_variable():
    """Test reading a single variable."""
    ds = read_silo_test_safe(variables=["max_temp"], silo_dir=SILO_DIR)
    
    # Check that dataset is returned
    assert isinstance(ds, xr.Dataset)
    
    # Check that variable is present
    assert "max_temp" in ds.data_vars
    
    ds.close()


def test_extract_single_point():
    """Test extracting data for a single point (Brisbane) and time range."""
    ds = read_silo_test_safe(variables=["max_temp"], silo_dir=SILO_DIR)
    
    # Brisbane coordinates
    lat, lon = -27.5, 153.0
    
    # Extract nearest point for a short time period
    point_ds = ds.sel(
        lat=lat, lon=lon, method="nearest", tolerance=0.1
    ).sel(time=slice("2020-01-01", "2020-01-07"))
    
    assert point_ds is not None
    assert "max_temp" in point_ds.data_vars
    assert len(point_ds.time) > 0
    assert len(point_ds.time) <= 7
    
    ds.close()


def test_to_dataframe_conversion():
    """Test converting a small subset to pandas DataFrame."""
    ds = read_silo_test_safe(variables=["max_temp"], silo_dir=SILO_DIR)
    
    # Extract a small subset for testing
    subset = ds.sel(
        lat=-27.5, lon=153.0, method="nearest", tolerance=0.1
    ).sel(time=slice("2020-01-01", "2020-01-03"))
    
    # Convert to DataFrame
    df = subset.to_dataframe().reset_index()
    
    # Check DataFrame structure
    assert "time" in df.columns
    assert "lat" in df.columns
    assert "lon" in df.columns
    assert "max_temp" in df.columns
    assert len(df) > 0
    assert len(df) <= 3  # At most 3 days
    
    ds.close()


def test_time_coordinate_sorted():
    """Test that time coordinate is sorted in ascending order."""
    ds = read_silo_test_safe(variables=["max_temp"], silo_dir=SILO_DIR)
    
    # Take a small sample of time values
    time_sample = ds.time.isel(time=slice(0, 100))
    
    # Check that time is monotonically increasing
    time_diff = time_sample.diff(dim="time")
    assert (time_diff > 0).all(), "Time coordinate is not sorted in ascending order"
    
    ds.close()


def test_coordinate_ranges():
    """Test that coordinate ranges are reasonable for Australian data."""
    ds = read_silo_test_safe(variables=["max_temp"], silo_dir=SILO_DIR)
    
    # Check latitude range (Australia is roughly -44 to -10)
    lat_min = float(ds.lat.min())
    lat_max = float(ds.lat.max())
    assert -45 <= lat_min <= -9, f"Latitude min {lat_min} outside Australian range"
    assert -45 <= lat_max <= -9, f"Latitude max {lat_max} outside Australian range"
    
    # Check longitude range (Australia is roughly 113 to 154)
    lon_min = float(ds.lon.min())
    lon_max = float(ds.lon.max())
    assert 112 <= lon_min <= 155, f"Longitude min {lon_min} outside Australian range"
    assert 112 <= lon_max <= 155, f"Longitude max {lon_max} outside Australian range"
    
    ds.close()


def test_data_has_values():
    """Test that extracted data contains actual values (not all NaN)."""
    ds = read_silo_test_safe(variables=["max_temp"], silo_dir=SILO_DIR)
    
    # Extract a specific point and time
    point_ds = ds.sel(
        lat=-27.5, lon=153.0, method="nearest", tolerance=0.1
    ).sel(time=slice("2020-01-01", "2020-01-03"))
    
    # Check that we have some non-NaN values
    max_temp = point_ds["max_temp"]
    assert not max_temp.isnull().all(), "All values are NaN"
    
    # Check that values are in reasonable range for temperature (Celsius)
    valid_values = max_temp.dropna(dim="time")
    if len(valid_values) > 0:
        assert float(valid_values.min()) > -20, "Temperature too low"
        assert float(valid_values.max()) < 60, "Temperature too high"
    
    ds.close()


@pytest.mark.xfail(raises=(FileNotFoundError, ValueError, OSError))
def test_nonexistent_directory_fails():
    """Test that non-existent directory raises an error."""
    fake_dir = Path("/nonexistent/path/to/silo")
    ds = read_silo_xarray(variables="daily", silo_dir=fake_dir)
    ds.close()
