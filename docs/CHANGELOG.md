# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),

## [0.0.3] - 2026-03-10

### Added

- `silo search --lat --lon` for location-based station search using coordinates and radius
- `search_stations_by_location` for location-based station search through python API
- Typer-based CLI interface (`weather-tools` command)
- Cloud-Optimized GeoTIFF (COG) support for spatial data queries (#1)
- NetCDF file download from SILO AWS S3 public data
- Met.no weather forecast API integration with SILO data merging (#5)
- Merge historical SILO data with met.no forecasts for continuous time series
- Centralized logging with Rich console output (#7)
- `SILO_DATA_DIR` environment variable to configure local data directory
- ISO date format support in CLI (YYYY-MM-DD)
- GitHub Pages documentation site

### Changed

- Default local data path changed to `~/DATA`
- Standardized SILO variable names across CLI and documentation
- SILO date column renamed for consistency
- SILO metadata output changed to JSON format

## [0.0.2] - 2025-05-05

### Added

- Read silo data from local netCDF files using Xarray

<!-- keep for reference
## [Unreleased]
### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security
-->