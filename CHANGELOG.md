# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-27

### Changed

- Refactored variable system: replaced `VariableInput` and `VariableName` with centralized `VariableRegistry` for consistency across API, NetCDF, and GeoTIFF modules
- Simplified Met.no variable handling with explicit `vp` (vapour pressure) instead of deprecated `dew_point`
- Updated Met.no API docstrings and removed deprecation wrappers
- Fixed SILO and merge validation with improved contracts and docstrings
- Improved GeoTIFF geometry caching with stable hash-based subset namespacing

### Fixed

- Fixed Phase 1 public API correctness bugs
- Corrected SILO/merge validation issues
- Fixed monthly variable handling and orphaned variable definitions
- Added SILO maintenance window warning
- Minor fixes to various edge cases

## [0.0.3] - 2026-04-15

### Fixed

- error handling non-matching arrays


## [0.0.2] - Earlier version

### Added

- Initial version with SILO API support for PatchedPoint and DataDrill datasets
- CLI interface with Typer for easy command-line access
- Local NetCDF file support via xarray for gridded climate data
- Cloud-Optimized GeoTIFF (COG) support with spatial subsetting capabilities
- Persistent disk cache for API responses via diskcache
- Met.no weather forecast integration and data merging
- Comprehensive variable registry for climate data standardization

