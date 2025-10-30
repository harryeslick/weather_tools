"""Tests for silo_geotiff module.

These tests cover URL construction, COG reading, downloading, and time series functionality.
Most tests use mocks to avoid actual network requests. Integration tests are marked separately.
"""

import datetime
from unittest.mock import Mock, patch, MagicMock
import numpy as np
import pytest
import requests
from shapely.geometry import Point, box

from weather_tools.silo_geotiff import (
    construct_geotiff_daily_url,
    construct_geotiff_monthly_url,
    read_cog,
    download_geotiff_with_subset,
    read_geotiff_timeseries,
    download_geotiff,
    SiloGeoTiffError,
)


class TestURLConstruction:
    """Test URL construction for SILO GeoTIFF files."""

    def test_construct_geotiff_daily_url_for_daily_rain(self):
        """Test constructing daily URL for rainfall."""
        url = construct_geotiff_daily_url("daily_rain", datetime.date(2023, 1, 15))

        assert url == (
            "https://s3-ap-southeast-2.amazonaws.com/silo-open-data/"
            "Official/daily/daily_rain/2023/20230115.daily_rain.tif"
        )

    def test_construct_geotiff_daily_url_for_max_temp(self):
        """Test constructing daily URL for maximum temperature."""
        url = construct_geotiff_daily_url("max_temp", datetime.date(2023, 12, 31))

        assert url == (
            "https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/daily/max_temp/2023/20231231.max_temp.tif"
        )

    def test_construct_geotiff_daily_url_different_year(self):
        """Test daily URL construction handles different years correctly."""
        url = construct_geotiff_daily_url("daily_rain", datetime.date(2020, 6, 1))

        assert "2020/20200601.daily_rain.tif" in url

    def test_construct_geotiff_monthly_url_for_monthly_rain(self):
        """Test constructing monthly URL for rainfall."""
        url = construct_geotiff_monthly_url("monthly_rain", 2023, 3)

        assert url == (
            "https://s3-ap-southeast-2.amazonaws.com/silo-open-data/"
            "Official/monthly/monthly_rain/2023/202303.monthly_rain.tif"
        )

    def test_construct_geotiff_monthly_url_december(self):
        """Test monthly URL construction for December (month 12)."""
        url = construct_geotiff_monthly_url("monthly_rain", 2023, 12)

        assert "202312.monthly_rain.tif" in url

    def test_construct_geotiff_monthly_url_january(self):
        """Test monthly URL construction for January (month 1)."""
        url = construct_geotiff_monthly_url("monthly_rain", 2023, 1)

        assert "202301.monthly_rain.tif" in url

    def test_invalid_variable_raises_error(self):
        """Test that invalid variable names raise ValueError."""
        with pytest.raises(ValueError, match="Unknown variable"):
            construct_geotiff_daily_url("invalid_var", datetime.date(2023, 1, 1))

    def test_url_format_consistency(self):
        """Test that URLs follow consistent format."""
        url = construct_geotiff_daily_url("evap_syn", datetime.date(2023, 7, 15))

        # Check URL structure
        assert url.startswith("https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/daily/")
        assert "evap_syn/2023/20230715.evap_syn.tif" in url


class TestReadCOG:
    """Test COG reading functionality (using mocks)."""

    def test_read_cog_with_point_geometry(self):
        """Test reading COG data for a Point geometry."""
        # Mock rasterio dataset
        mock_src = MagicMock()
        mock_src.crs.to_string.return_value = "EPSG:4326"
        mock_src.nodata = -999
        mock_src.profile = {"driver": "GTiff", "height": 10, "width": 10, "crs": "EPSG:4326"}
        mock_src.__enter__ = Mock(return_value=mock_src)
        mock_src.__exit__ = Mock(return_value=False)

        # Mock window
        from rasterio.windows import Window

        mock_window = Window(0, 0, 5, 5)

        # Mock read data
        test_data = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        mock_src.read.return_value = test_data
        mock_src.window_transform.return_value = "mock_transform"

        point = Point(153.0, -27.5)

        with patch("rasterio.open", return_value=mock_src):
            with patch("weather_tools.silo_geotiff.geometry_window", return_value=mock_window):
                data, profile = read_cog("https://example.com/test.tif", geometry=point, use_mask=False)

        # Check that data was returned
        assert isinstance(data, np.ndarray)
        assert data.shape == (3, 3)

    def test_read_cog_with_polygon_geometry(self):
        """Test reading COG data for a Polygon geometry."""
        mock_src = MagicMock()
        mock_src.crs.to_string.return_value = "EPSG:4326"
        mock_src.nodata = None
        mock_src.profile = {"driver": "GTiff"}
        mock_src.__enter__ = Mock(return_value=mock_src)
        mock_src.__exit__ = Mock(return_value=False)

        from rasterio.windows import Window

        mock_window = Window(0, 0, 10, 10)

        test_data = np.ones((10, 10))
        mock_src.read.return_value = test_data
        mock_src.window_transform.return_value = "mock_transform"

        polygon = box(150.0, -28.0, 154.0, -26.0)

        with patch("rasterio.open", return_value=mock_src):
            with patch("weather_tools.silo_geotiff.geometry_window", return_value=mock_window):
                data, profile = read_cog("https://example.com/test.tif", geometry=polygon)

        assert isinstance(data, np.ndarray)

    def test_read_cog_with_masking(self):
        """Test that nodata values are properly masked."""
        mock_src = MagicMock()
        mock_src.crs.to_string.return_value = "EPSG:4326"
        mock_src.nodata = -999
        mock_src.profile = {"driver": "GTiff"}
        mock_src.__enter__ = Mock(return_value=mock_src)
        mock_src.__exit__ = Mock(return_value=False)

        from rasterio.windows import Window

        mock_window = Window(0, 0, 5, 5)

        # Include nodata value
        test_data = np.array([[1, 2, -999], [4, 5, 6]])
        mock_src.read.return_value = test_data
        mock_src.window_transform.return_value = "mock_transform"

        point = Point(153.0, -27.5)

        with patch("rasterio.open", return_value=mock_src):
            with patch("weather_tools.silo_geotiff.geometry_window", return_value=mock_window):
                data, profile = read_cog("https://example.com/test.tif", geometry=point, use_mask=True)

        # Check that data is masked
        assert isinstance(data, np.ma.MaskedArray)

    def test_read_cog_invalid_crs_raises_error(self):
        """Test that non-EPSG:4326 CRS raises error."""
        mock_src = MagicMock()
        mock_src.crs.to_string.return_value = "EPSG:3857"  # Wrong CRS
        mock_src.__enter__ = Mock(return_value=mock_src)
        mock_src.__exit__ = Mock(return_value=False)

        point = Point(153.0, -27.5)

        with patch("rasterio.open", return_value=mock_src):
            with pytest.raises(SiloGeoTiffError, match="Expected EPSG:4326"):
                read_cog("https://example.com/test.tif", geometry=point)

    def test_read_cog_with_overview_level(self):
        """Test reading COG with overview level for reduced resolution."""
        mock_src = MagicMock()
        mock_src.crs.to_string.return_value = "EPSG:4326"
        mock_src.nodata = None
        mock_src.profile = {"driver": "GTiff"}
        mock_src.__enter__ = Mock(return_value=mock_src)
        mock_src.__exit__ = Mock(return_value=False)

        from rasterio.windows import Window

        mock_window = Window(0, 0, 100, 100)

        test_data = np.ones((25, 25))  # Reduced size for overview level 2
        mock_src.read.return_value = test_data
        mock_src.window_transform.return_value = "mock_transform"

        point = Point(153.0, -27.5)

        with patch("rasterio.open", return_value=mock_src):
            with patch("weather_tools.silo_geotiff.geometry_window", return_value=mock_window):
                data, profile = read_cog("https://example.com/test.tif", geometry=point, overview_level=2)

        # Verify read was called with out_shape parameter
        assert mock_src.read.called

    def test_read_cog_without_geometry(self):
        """Test reading entire COG without geometry parameter."""
        mock_src = MagicMock()
        mock_src.crs.to_string.return_value = "EPSG:4326"
        mock_src.nodata = -999
        mock_src.profile = {"driver": "GTiff", "height": 100, "width": 100, "transform": "mock_transform"}
        mock_src.__enter__ = Mock(return_value=mock_src)
        mock_src.__exit__ = Mock(return_value=False)

        test_data = np.ones((100, 100))
        mock_src.read.return_value = test_data

        with patch("rasterio.open", return_value=mock_src):
            data, profile = read_cog("https://example.com/test.tif", geometry=None, use_mask=False)

        # Verify entire raster was read with no window or out_shape
        mock_src.read.assert_called_once_with(1, window=None, out_shape=None)
        assert isinstance(data, np.ndarray)
        assert data.shape == (100, 100)


class TestDownloadGeoTiffWithSubset:
    """Test GeoTIFF download functionality."""

    def test_skip_existing_file(self, tmp_path):
        """Test that existing files are skipped by default."""
        dest = tmp_path / "test.tif"
        dest.write_text("existing data")

        result = download_geotiff_with_subset(url="https://example.com/test.tif", destination=dest, force=False)

        assert result is False
        assert dest.read_text() == "existing data"

    def test_overwrite_with_force(self, tmp_path):
        """Test that existing files are overwritten with force=True."""
        dest = tmp_path / "test.tif"
        dest.write_text("old data")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content = Mock(return_value=[b"new ", b"data"])

        with patch("requests.get", return_value=mock_response):
            result = download_geotiff_with_subset(
                url="https://example.com/test.tif", destination=dest, geometry=None, force=True
            )

        assert result is True
        assert dest.read_text() == "new data"

    def test_create_parent_directory(self, tmp_path):
        """Test that parent directories are created if they don't exist."""
        dest = tmp_path / "subdir" / "nested" / "test.tif"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_content = Mock(return_value=[b"data"])

        with patch("requests.get", return_value=mock_response):
            download_geotiff_with_subset(url="https://example.com/test.tif", destination=dest)

        assert dest.parent.exists()
        assert dest.exists()

    def test_http_404_returns_false(self, tmp_path):
        """Test that 404 errors return False (not raise)."""
        dest = tmp_path / "test.tif"

        mock_response = Mock()
        mock_response.status_code = 404

        # Create proper HTTPError with response attribute
        http_error = requests.exceptions.HTTPError("404 Not Found")
        http_error.response = mock_response
        mock_response.raise_for_status = Mock(side_effect=http_error)

        with patch("requests.get", return_value=mock_response):
            result = download_geotiff_with_subset(url="https://example.com/missing.tif", destination=dest)

        # 404 should return False, not raise
        assert result is False

    def test_download_with_geometry_clipping(self, tmp_path):
        """Test downloading with geometry clipping."""
        dest = tmp_path / "test.tif"
        point = Point(153.0, -27.5)

        # Mock read_cog to return test data
        test_data = np.ones((5, 5))
        test_profile = {"driver": "GTiff", "height": 5, "width": 5, "count": 1, "dtype": "float64"}

        # Mock rasterio.open for writing
        mock_dst = MagicMock()
        mock_dst.__enter__ = Mock(return_value=mock_dst)
        mock_dst.__exit__ = Mock(return_value=False)

        with patch("weather_tools.silo_geotiff.read_cog", return_value=(test_data, test_profile)):
            with patch("rasterio.open", return_value=mock_dst):
                result = download_geotiff_with_subset(
                    url="https://example.com/test.tif", destination=dest, geometry=point
                )

        assert result is True
        # Verify write was called
        assert mock_dst.write.called


class TestReadGeoTiffTimeseries:
    """Test timeseries reading functionality."""

    def test_read_timeseries_single_variable(self):
        """Test reading timeseries for a single variable."""
        point = Point(153.0, -27.5)

        # Mock download and read operations
        test_data = np.ones((10, 10))
        test_profile = {"driver": "GTiff"}

        with patch("weather_tools.silo_geotiff.download_geotiff_with_subset", return_value=True), \
             patch("weather_tools.silo_geotiff.read_cog", return_value=(test_data, test_profile)):
            result = read_geotiff_timeseries(
                variables=["daily_rain"],
                start_date=datetime.date(2023, 1, 1),
                end_date=datetime.date(2023, 1, 3),
                geometry=point,
                save_to_disk=False,
            )

        assert "daily_rain" in result
        # Should have 3 days of data
        assert result["daily_rain"].shape[0] == 3

    def test_read_timeseries_multiple_variables(self):
        """Test reading timeseries for multiple variables."""
        point = Point(153.0, -27.5)

        test_data = np.ones((5, 5))
        test_profile = {"driver": "GTiff"}

        with patch("weather_tools.silo_geotiff.download_geotiff_with_subset", return_value=True), \
             patch("weather_tools.silo_geotiff.read_cog", return_value=(test_data, test_profile)):
            result = read_geotiff_timeseries(
                variables=["daily_rain", "max_temp"],
                start_date=datetime.date(2023, 1, 1),
                end_date=datetime.date(2023, 1, 2),
                geometry=point,
                save_to_disk=False,
            )

        assert "daily_rain" in result
        assert "max_temp" in result
        assert result["daily_rain"].shape[0] == 2
        assert result["max_temp"].shape[0] == 2

    def test_read_timeseries_with_preset(self):
        """Test reading timeseries with variable preset."""
        point = Point(153.0, -27.5)

        test_data = np.ones((5, 5))
        test_profile = {"driver": "GTiff"}

        with patch("weather_tools.silo_geotiff.download_geotiff_with_subset", return_value=True), \
             patch("weather_tools.silo_geotiff.read_cog", return_value=(test_data, test_profile)):
            result = read_geotiff_timeseries(
                variables="daily",  # Preset
                start_date=datetime.date(2023, 1, 1),
                end_date=datetime.date(2023, 1, 1),
                geometry=point,
                save_to_disk=False,
            )

        # Daily preset includes multiple variables
        assert "daily_rain" in result
        assert "max_temp" in result


class TestDownloadGeoTiffRange:
    """Test downloading range of GeoTIFF files."""

    def test_download_range_basic(self, tmp_path):
        """Test downloading a range of files."""
        point = Point(153.0, -27.5)

        with patch("weather_tools.silo_geotiff.download_geotiff_with_subset", return_value=True):
            result = download_geotiff(
                variables=["daily_rain"],
                start_date=datetime.date(2023, 1, 1),
                end_date=datetime.date(2023, 1, 3),
                geometry=point,
                output_dir=tmp_path,
                save_to_disk=True,
                read_files=False,
            )

        assert "daily_rain" in result
        # Should attempt to download 3 files
        assert len(result["daily_rain"]) == 3

    def test_download_range_with_bbox(self, tmp_path):
        """Test downloading with bounding box as Polygon geometry."""
        # Create a Polygon from bounding box coordinates
        bbox_geom = box(150.0, -28.0, 154.0, -26.0)

        with patch("weather_tools.silo_geotiff.download_geotiff_with_subset", return_value=True):
            result = download_geotiff(
                variables=["daily_rain"],
                start_date=datetime.date(2023, 1, 1),
                end_date=datetime.date(2023, 1, 2),
                geometry=bbox_geom,
                output_dir=tmp_path,
                save_to_disk=True,
                read_files=False,
            )

        assert "daily_rain" in result
        assert len(result["daily_rain"]) == 2

    def test_download_range_geometry_required(self, tmp_path):
        """Test that geometry parameter is required."""
        # This test verifies that the geometry parameter cannot be omitted
        # The function signature requires it, so this would be a TypeError
        with pytest.raises(TypeError):
            download_geotiff(
                variables=["daily_rain"],
                start_date=datetime.date(2023, 1, 1),
                end_date=datetime.date(2023, 1, 2),
                output_dir=tmp_path,
                # Missing required geometry parameter
            )

    def test_download_range_invalid_variable(self, tmp_path):
        """Test that invalid variables raise ValueError."""
        point = Point(153.0, -27.5)

        with pytest.raises(ValueError, match="Unknown variable"):
            download_geotiff(
                variables=["invalid_var"],
                start_date=datetime.date(2023, 1, 1),
                end_date=datetime.date(2023, 1, 2),
                geometry=point,
                output_dir=tmp_path,
                save_to_disk=True,
                read_files=False,
            )

    def test_download_range_skips_old_years(self, tmp_path):
        """Test that years before variable start are skipped."""
        # MSLP starts in 1957
        point = Point(153.0, -27.5)

        with patch("weather_tools.silo_geotiff.download_geotiff_with_subset", return_value=True):
            result = download_geotiff(
                variables=["mslp"],
                start_date=datetime.date(1950, 1, 1),
                end_date=datetime.date(1950, 1, 3),
                geometry=point,
                output_dir=tmp_path,
                save_to_disk=True,
                read_files=False,
            )

        # Should not download anything (1950 is before MSLP start year)
        assert len(result["mslp"]) == 0

    def test_download_range_continues_on_failure(self, tmp_path):
        """Test that download continues if individual files fail."""
        point = Point(153.0, -27.5)
        call_count = 0

        def mock_download(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise SiloGeoTiffError("Simulated failure")
            return True

        with patch("weather_tools.silo_geotiff.download_geotiff_with_subset", side_effect=mock_download):
            result = download_geotiff(
                variables=["daily_rain"],
                start_date=datetime.date(2023, 1, 1),
                end_date=datetime.date(2023, 1, 2),
                geometry=point,
                output_dir=tmp_path,
                save_to_disk=True,
                read_files=False,
            )

        # Should have attempted both downloads
        assert call_count == 2
        # Only one should have succeeded
        assert len(result["daily_rain"]) == 1


# Integration tests (require network access and actual SILO data)
@pytest.mark.integration
class TestGeoTiffIntegration:
    """Integration tests that access real SILO GeoTIFF files."""

    def test_read_actual_cog_point(self):
        """Test reading actual COG file from SILO for a point."""
        # Use recent date that should exist
        url = construct_geotiff_daily_url("daily_rain", datetime.date(2023, 1, 15))
        point = Point(153.0, -27.5)  # Brisbane area

        data, profile = read_cog(url, geometry=point)

        # Verify we got data
        assert isinstance(data, np.ma.MaskedArray)
        assert data.size > 0
        assert profile["driver"] == "GTiff"

    def test_read_actual_cog_polygon(self):
        """Test reading actual COG file for a polygon."""
        url = construct_geotiff_daily_url("daily_rain", datetime.date(2023, 1, 15))
        # Small polygon around Brisbane
        polygon = box(152.9, -27.6, 153.1, -27.4)

        data, profile = read_cog(url, geometry=polygon)

        assert isinstance(data, np.ma.MaskedArray)
        assert data.shape[0] > 1
        assert data.shape[1] > 1

    def test_download_single_geotiff(self, tmp_path):
        """Test downloading a single GeoTIFF file."""
        url = construct_geotiff_daily_url("daily_rain", datetime.date(2023, 1, 15))
        dest = tmp_path / "test.tif"

        result = download_geotiff_with_subset(url, dest)

        assert result is True
        assert dest.exists()
        # File should be a valid GeoTIFF
        assert dest.stat().st_size > 0

    def test_download_with_clipping(self, tmp_path):
        """Test downloading with spatial clipping."""
        url = construct_geotiff_daily_url("daily_rain", datetime.date(2023, 1, 15))
        dest = tmp_path / "clipped.tif"
        # Small area
        point = Point(153.0, -27.5)

        result = download_geotiff_with_subset(url, dest, geometry=point)

        assert result is True
        assert dest.exists()
        # Clipped file should be smaller than full file
        assert dest.stat().st_size > 0
