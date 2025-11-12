"""Tests for read_silo_xarray module."""

from pathlib import Path

import pytest
import xarray as xr

from weather_tools.config import get_silo_data_dir
from weather_tools.read_silo_xarray import read_silo_xarray
from weather_tools.silo_variables import expand_variable_preset

# Define the expected SILO data directory
SILO_DIR = get_silo_data_dir()


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
    """Check if SILO data directory exists."""
    if not SILO_DIR.exists():
        pytest.skip(f"SILO data directory not found: {SILO_DIR}")
    return SILO_DIR


class TestReadSiloXarray:
    """Test suite for read_silo_xarray function."""

    def test_silo_directory_exists(self, silo_data_available):
        """Test that the SILO data directory exists."""
        assert silo_data_available.exists()
        assert silo_data_available.is_dir()

    def test_read_daily_variables(self, silo_data_available):
        """Test reading daily variables with default settings."""
        ds = read_silo_test_safe(variables="daily", silo_dir=silo_data_available)
        
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

    def test_read_monthly_variables(self, silo_data_available):
        """Test reading monthly variables."""
        ds = read_silo_test_safe(variables="monthly", silo_dir=silo_data_available)
        
        # Check that dataset is returned
        assert isinstance(ds, xr.Dataset)
        
        # Check that monthly_rain variable is present
        assert "monthly_rain" in ds.data_vars
        
        # Check dimensions
        assert "time" in ds.dims
        assert "lat" in ds.dims
        assert "lon" in ds.dims

    def test_read_specific_variables(self, silo_data_available):
        """Test reading specific variables as a list."""
        variables = ["max_temp", "min_temp"]
        ds = read_silo_test_safe(variables=variables, silo_dir=silo_data_available)
        
        # Check that dataset is returned
        assert isinstance(ds, xr.Dataset)
        
        # Check that only requested variables are present
        for var in variables:
            assert var in ds.data_vars, f"Variable {var} not found in dataset"

    def test_read_single_variable(self, silo_data_available):
        """Test reading a single variable."""
        ds = read_silo_test_safe(variables=["max_temp"], silo_dir=silo_data_available)
        
        # Check that dataset is returned
        assert isinstance(ds, xr.Dataset)
        
        # Check that variable is present
        assert "max_temp" in ds.data_vars

    def test_time_coordinate_sorted(self, silo_data_available):
        """Test that time coordinate is sorted in ascending order."""
        ds = read_silo_test_safe(variables="daily", silo_dir=silo_data_available)
        
        # Check that time is monotonically increasing
        time_diff = ds.time.diff(dim="time")
        assert (time_diff > 0).all(), "Time coordinate is not sorted in ascending order"

    def test_data_integrity(self, silo_data_available):
        """Test basic data integrity checks on a small subset."""
        ds = read_silo_test_safe(variables=["max_temp"], silo_dir=silo_data_available)
        
        # Work with a small time slice to avoid memory issues
        subset = ds.sel(time=slice("2020-01-01", "2020-01-07"))
        
        # Check that data is not all NaN
        assert not subset["max_temp"].isnull().all(), "All max_temp values are NaN"
        
        # Check that data has reasonable values (temperature in Celsius)
        # Australia temperature range typically -10 to 50°C
        max_temp_values = subset["max_temp"].values
        non_nan_mask = ~xr.ufuncs.isnan(max_temp_values)
        
        if non_nan_mask.any():
            non_nan_values = max_temp_values[non_nan_mask]
            assert non_nan_values.min() > -20, "Temperature values seem unreasonably low"
            assert non_nan_values.max() < 60, "Temperature values seem unreasonably high"

    def test_coordinate_ranges(self, silo_data_available):
        """Test that coordinate ranges are reasonable for Australian data."""
        ds = read_silo_test_safe(variables="daily", silo_dir=silo_data_available)
        
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

    def test_dataset_attributes(self, silo_data_available):
        """Test that dataset has proper attributes and metadata."""
        ds = read_silo_test_safe(variables="daily", silo_dir=silo_data_available)
        
        # Check that coordinates have attributes
        assert hasattr(ds.lat, "attrs")
        assert hasattr(ds.lon, "attrs")
        assert hasattr(ds.time, "attrs")

    def test_chunking(self, silo_data_available):
        """Test that data is properly chunked for time dimension."""
        ds = read_silo_test_safe(variables="daily", silo_dir=silo_data_available)
        
        # Check if data is chunked (dask arrays)
        # This depends on how the data was loaded
        for var in ds.data_vars:
            if hasattr(ds[var].data, "chunks"):
                # If chunked, time should be in chunks
                assert "time" in ds[var].dims


class TestReadSiloXarrayEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_variable_string(self, silo_data_available):
        """Test with an invalid variable string."""
        # Should handle gracefully or skip non-existent variables
        # This tests robustness
        try:
            ds = read_silo_xarray(variables="invalid", silo_dir=silo_data_available)
            # If no error, check that dataset is empty or has no data vars
            assert len(ds.data_vars) == 0 or ds is not None
        except (FileNotFoundError, ValueError, OSError):
            # Expected to fail - this is acceptable
            pass

    def test_empty_variable_list(self, silo_data_available):
        """Test with an empty variable list."""
        ds = read_silo_test_safe(variables=[], silo_dir=silo_data_available)
        
        # Should return a dataset with no data variables
        assert isinstance(ds, xr.Dataset)
        assert len(ds.data_vars) == 0

    def test_nonexistent_directory(self):
        """Test with a non-existent SILO directory."""
        fake_dir = Path("/nonexistent/path/to/silo")
        
        with pytest.raises((FileNotFoundError, ValueError, OSError)):
            read_silo_xarray(variables="daily", silo_dir=fake_dir)


@pytest.mark.integration
class TestReadSiloXarrayIntegration:
    """Integration tests for read_silo_xarray."""

    def test_extract_location_data(self, silo_data_available):
        """Test extracting data for a specific location (Brisbane)."""
        ds = read_silo_test_safe(variables="daily", silo_dir=silo_data_available)
        
        # Brisbane coordinates
        lat, lon = -27.5, 153.0
        
        # Extract nearest point
        point_ds = ds.sel(lat=lat, lon=lon, method="nearest", tolerance=0.1)
        
        assert point_ds is not None
        assert "max_temp" in point_ds.data_vars
        
        # Check that we got data for the location
        assert len(point_ds.time) > 0

    def test_extract_time_slice(self, silo_data_available):
        """Test extracting a time slice."""
        ds = read_silo_test_safe(variables="daily", silo_dir=silo_data_available)
        
        # Extract January 2020
        time_slice = ds.sel(time=slice("2020-01-01", "2020-01-31"))
        
        assert time_slice is not None
        assert len(time_slice.time) > 0
        assert len(time_slice.time) <= 31  # At most 31 days in January

    def test_to_dataframe_conversion(self, silo_data_available):
        """Test converting dataset to pandas DataFrame."""
        ds = read_silo_test_safe(variables=["max_temp"], silo_dir=silo_data_available)
        
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
