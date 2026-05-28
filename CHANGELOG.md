# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-28

Realigned the CLI with the original Pydantic-first vision: query models own field names, types, defaults, validation, and help text; Typer options are auto-derived from the models; CLI commands are thin downloaders that write the upstream response to disk verbatim. Applied to four data commands across three CLI modules.

### Added

- `@from_pydantic` decorator in `weather_tools.cli.pydantic_typer` — auto-derives Typer CLI options from a Pydantic model, flattens one level of nested `BaseModel` fields (e.g. `date_range` → `--start-date` / `--end-date`), narrows enum choices per-command via `format_choices`, supports field aliases (`--var` for the `variables` field), and renders Pydantic `ValidationError`s in the CLI house style.
- `weather_tools.date_range.DateRange` — generic Pydantic base model with ISO/YYYYMMDD date acceptance, format normalisation, and ordering check. No year bounds — subclasses add those when relevant.
- `weather_tools.local_models.ExtractQuery` and `DownloadQuery` — Pydantic query models backing `local extract` and `local download`. `ExtractQuery` nests `AustralianCoordinates` + `SiloDateRange`; `DownloadQuery` uses year ints with a `start_year ≤ end_year` validator.
- `weather_tools.geotiff_models.GeoTiffDownloadQuery` — Pydantic query model backing the non-spatial fields of `geotiff download` (variables, date range, output dir, force). Spatial inputs (`--bbox`, `--geometry`) remain CLI-only by design.
- `SiloDateRange` now accepts ISO `YYYY-MM-DD` input in addition to `YYYYMMDD`; both forms normalise to `YYYYMMDD` storage. The convenience applies to every consumer of `SiloDateRange` — CLI and Python API alike.

### Changed

- `SiloDateRange` now inherits from `DateRange`; the 1889-2100 SILO year-availability check is the only thing the subclass adds.
- `silo patched-point` and `silo data-drill` CLI commands rewritten as thin downloaders. Same code path for every format — no more branching between `api.get_*` (DataFrame round-trip) and `api.query_*` (raw response). The response body is written to disk verbatim.
- `local extract` and `local download` CLI commands rewritten to use `@from_pydantic`. Date validation, year-range validation, and variable validation moved from CLI bodies onto the query models. ISO and YYYYMMDD dates now both accepted on `local extract`.
- `geotiff download` CLI partially refactored: variables/date/output/force come from `GeoTiffDownloadQuery`; `--bbox` and `--geometry` stay as CLI-only options resolved into a shapely geometry before the model is consulted.

### Breaking

- `silo patched-point --format json` now writes SILO's native JSON shape including the metadata block, instead of a pandas-flattened list-of-records. This restores fidelity with the upstream service; consumers parsing the previous flat structure will need to adapt.
- `silo patched-point --station` renamed to `--station-code` (matches the underlying model field on `PatchedPointQuery`).
- `local extract --lat` / `--lon` renamed to `--latitude` / `--longitude` (matches `silo data-drill` and the underlying `AustralianCoordinates` model fields).
- Out-of-Australia coordinates and pre-1889 / post-2100 dates are now rejected at model construction (i.e. before any data is loaded or downloaded), instead of failing partway through the call.

### Removed

- `weather_tools.cli.date_utils.iso_to_silo_yyyymmdd_option` — the Typer callback that converted ISO dates to YYYYMMDD. Replaced by the `field_validator(mode="before")` on `DateRange`, so the conversion now happens at the model boundary for every consumer.

### Fixed

- `@from_pydantic` now resolves forward-reference annotations on CLI-only extras via `typing.get_type_hints(fn, include_extras=True)`. Without this, command modules using `from __future__ import annotations` silently lost `help=`, `envvar=`, and flag-alias metadata on their CLI-only options. A regression test exercises the resolution path.

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

