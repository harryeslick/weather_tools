"""Tests for silo_netcdf module.

These tests document how to construct URLs and validate downloads.
Most tests use mocks to avoid actual network requests.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
import requests

from weather_tools.silo_netcdf import (
    construct_netcdf_url,
    download_file,
    download_netcdf,
    validate_year_for_variable,
)
from weather_tools.silo_variables import SiloNetCDFError


class TestURLConstruction:
    """Test URL construction for SILO S3 downloads."""

    def test_construct_url_for_daily_rain(self):
        """Test constructing download URL for daily rainfall."""
        url = construct_netcdf_url("daily_rain", 2023)

        assert url == (
            "https://s3-ap-southeast-2.amazonaws.com/silo-open-data/"
            "Official/annual/daily_rain/2023.daily_rain.nc"
        )

    def test_construct_url_for_max_temp(self):
        """Test constructing download URL for maximum temperature."""
        url = construct_netcdf_url("max_temp", 2020)

        assert url == (
            "https://s3-ap-southeast-2.amazonaws.com/silo-open-data/"
            "Official/annual/max_temp/2020.max_temp.nc"
        )

    def test_construct_url_for_monthly_rain(self):
        """Test constructing download URL for monthly rainfall."""
        url = construct_netcdf_url("monthly_rain", 2022)

        assert url == (
            "https://s3-ap-southeast-2.amazonaws.com/silo-open-data/"
            "Official/annual/monthly_rain/2022.monthly_rain.nc"
        )

    def test_url_format_consistency(self):
        """Test that URLs follow consistent format: {base}/{variable}/{year}.{variable}.nc"""
        url = construct_netcdf_url("evap_syn", 2021)

        # Check URL structure
        assert url.startswith(
            "https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/"
        )
        assert "evap_syn/2021.evap_syn.nc" in url


class TestYearValidation:
    """Test year validation for different variables."""

    def test_valid_year_for_daily_rain(self):
        """Test that years from 1889 onwards are valid for daily_rain."""
        # daily_rain starts in 1889
        assert validate_year_for_variable("daily_rain", 1889) is True
        assert validate_year_for_variable("daily_rain", 2023) is True

    def test_invalid_year_too_early(self):
        """Test that years before variable start are invalid."""
        # daily_rain starts in 1889
        assert validate_year_for_variable("daily_rain", 1888) is False

    def test_invalid_year_in_future(self):
        """Test that future years are invalid."""
        future_year = datetime.now().year + 10
        assert validate_year_for_variable("daily_rain", future_year) is False

    def test_valid_year_for_mslp(self):
        """Test that MSLP (mean sea level pressure) only valid from 1957."""
        # MSLP starts in 1957
        assert validate_year_for_variable("mslp", 1956) is False
        assert validate_year_for_variable("mslp", 1957) is True
        assert validate_year_for_variable("mslp", 2023) is True

    def test_valid_year_for_evap_pan(self):
        """Test that pan evaporation only valid from 1970."""
        # evap_pan starts in 1970
        assert validate_year_for_variable("evap_pan", 1969) is False
        assert validate_year_for_variable("evap_pan", 1970) is True

    def test_invalid_variable_name(self):
        """Test that unknown variables return False."""
        assert validate_year_for_variable("invalid_var", 2023) is False


class TestDownloadFile:
    """Test individual file download logic (using mocks)."""

    def test_skip_existing_file(self, tmp_path):
        """Test that existing files are skipped by default."""
        # Create an existing file
        dest = tmp_path / "test.nc"
        dest.write_text("existing data")

        # Try to download without force
        result = download_file(
            url="https://example.com/test.nc",
            destination=dest,
            force=False,
        )

        # Should return False (skipped)
        assert result is False
        # File should be unchanged
        assert dest.read_text() == "existing data"

    def test_overwrite_with_force(self, tmp_path):
        """Test that existing files are overwritten with force=True."""
        # Create an existing file
        dest = tmp_path / "test.nc"
        dest.write_text("old data")

        # Mock the requests.get call
        mock_response = Mock()
        mock_response.headers = {"content-length": "100"}
        mock_response.iter_content = Mock(return_value=[b"new ", b"data"])

        with patch("requests.get", return_value=mock_response):
            result = download_file(
                url="https://example.com/test.nc",
                destination=dest,
                force=True,
            )

        # Should return True (downloaded)
        assert result is True
        # File should be updated
        assert dest.read_text() == "new data"

    def test_create_parent_directory(self, tmp_path):
        """Test that parent directories are created if they don't exist."""
        # Non-existent directory structure
        dest = tmp_path / "subdir" / "nested" / "test.nc"

        # Mock the requests.get call
        mock_response = Mock()
        mock_response.headers = {"content-length": "100"}
        mock_response.iter_content = Mock(return_value=[b"data"])

        with patch("requests.get", return_value=mock_response):
            download_file(
                url="https://example.com/test.nc",
                destination=dest,
            )

        # Directory should be created
        assert dest.parent.exists()
        assert dest.exists()

    def test_http_404_error(self, tmp_path):
        """Test that 404 errors raise SiloNetCDFError with helpful message."""
        dest = tmp_path / "test.nc"

        # Mock a 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status = Mock(
            side_effect=requests.exceptions.HTTPError(response=mock_response)
        )

        with patch("requests.get", return_value=mock_response):
            with pytest.raises(SiloNetCDFError, match="File not found"):
                download_file(
                    url="https://example.com/missing.nc",
                    destination=dest,
                )

    def test_network_error(self, tmp_path):
        """Test that network errors raise SiloNetCDFError."""
        dest = tmp_path / "test.nc"

        # Mock a network error
        with patch(
            "requests.get", side_effect=requests.exceptions.ConnectionError("Network error")
        ):
            with pytest.raises(SiloNetCDFError, match="Failed to download"):
                download_file(
                    url="https://example.com/test.nc",
                    destination=dest,
                )


class TestDownloadSiloGridded:
    """Test the main download function (using mocks)."""

    def test_expand_daily_preset(self, tmp_path):
        """Test that 'daily' preset expands to multiple variables."""
        # Mock successful downloads
        with patch("weather_tools.silo_netcdf.download_file", return_value=True):
            result = download_netcdf(
                variables="daily",
                start_year=2023,
                end_year=2023,
                output_dir=tmp_path,
            )

        # Should have downloaded 4 variables (daily preset)
        assert "daily_rain" in result
        assert "max_temp" in result
        assert "min_temp" in result
        assert "evap_syn" in result

    def test_specific_variables_list(self, tmp_path):
        """Test downloading specific variables as a list."""
        # Mock successful downloads
        with patch("weather_tools.silo_netcdf.download_file", return_value=True):
            result = download_netcdf(
                variables=["daily_rain", "max_temp"],
                start_year=2022,
                end_year=2023,
                output_dir=tmp_path,
            )

        # Should have only the requested variables
        assert set(result.keys()) == {"daily_rain", "max_temp"}

        # Should have 2 files per variable (2022 and 2023)
        assert len(result["daily_rain"]) == 2
        assert len(result["max_temp"]) == 2

    def test_invalid_variable_raises_error(self, tmp_path):
        """Test that invalid variable names raise ValueError."""
        with pytest.raises(ValueError, match="Unknown variable"):
            download_netcdf(
                variables=["invalid_var"],
                start_year=2023,
                end_year=2023,
                output_dir=tmp_path,
            )

    def test_invalid_year_range_raises_error(self, tmp_path):
        """Test that invalid year ranges raise ValueError."""
        # start_year > end_year
        with pytest.raises(ValueError, match="must be <="):
            download_netcdf(
                variables="daily",
                start_year=2023,
                end_year=2020,
                output_dir=tmp_path,
            )

    def test_future_year_raises_error(self, tmp_path):
        """Test that future years raise ValueError."""
        future_year = datetime.now().year + 10

        with pytest.raises(ValueError, match="cannot be in the future"):
            download_netcdf(
                variables="daily",
                start_year=future_year,
                end_year=future_year,
                output_dir=tmp_path,
            )

    def test_skip_years_before_variable_start(self, tmp_path):
        """Test that years before variable start are skipped with warning."""
        # MSLP only starts in 1957
        with patch("weather_tools.silo_netcdf.download_file", return_value=True):
            result = download_netcdf(
                variables=["mslp"],
                start_year=1950,  # Before MSLP starts
                end_year=1958,
                output_dir=tmp_path,
            )

        # Should only download 1958 (1950-1956 skipped)
        assert len(result["mslp"]) == 2  # 1957 and 1958

    def test_file_organization(self, tmp_path):
        """Test that files are organized in correct directory structure."""
        # Mock successful downloads and capture the paths
        downloaded_paths = []

        def mock_download(url, destination, **kwargs):
            downloaded_paths.append(destination)
            return True

        with patch("weather_tools.silo_netcdf.download_file", side_effect=mock_download):
            download_netcdf(
                variables=["daily_rain"],
                start_year=2023,
                end_year=2023,
                output_dir=tmp_path,
            )

        # Check file path structure
        expected_path = tmp_path / "daily_rain" / "2023.daily_rain.nc"
        assert expected_path in downloaded_paths

    def test_continue_on_individual_failure(self, tmp_path):
        """Test that download continues even if individual files fail."""
        call_count = 0

        def mock_download(url, destination, **kwargs):
            nonlocal call_count
            call_count += 1
            # Fail on first file, succeed on others
            if call_count == 1:
                raise SiloNetCDFError("Simulated failure")
            return True

        with patch("weather_tools.silo_netcdf.download_file", side_effect=mock_download):
            result = download_netcdf(
                variables=["daily_rain", "max_temp"],
                start_year=2023,
                end_year=2023,
                output_dir=tmp_path,
            )

        # Should have attempted both files
        assert call_count == 2
        # Only one should have succeeded
        total_downloaded = sum(len(files) for files in result.values())
        assert total_downloaded == 1
