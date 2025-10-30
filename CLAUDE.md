# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**weather_tools** is a Python CLI tool and library for accessing and processing Australian SILO (Scientific Information for Land Owners) climate data. It supports both API-based queries and local NetCDF file processing.

[SILO API Guide](https://www.longpaddock.qld.gov.au/silo/api-documentation/guide/)
[SILO API reference](https://www.longpaddock.qld.gov.au/silo/api-documentation/reference/)


**Core Features:**
- SILO API client with Pydantic validation for type-safe queries
- Local NetCDF file support via xarray/pandas
- Cloud-Optimized GeoTIFF (COG) support with spatial subsetting
- CLI interface built with Typer
- Two dataset types: PatchedPoint (station data) and DataDrill (gridded data at 0.05° resolution)

## Development Commands

This package is in active development, when making breaking changes, DO NOT include deprecation warnings or wrappers to maintain earlier functionality. assume no external users currently exist for this code. 

### Environment Setup
```bash
# Install dependencies (using uv package manager)
uv sync

```

### Testing
```bash
# Run all tests
uv run pytest tests/

# Run simple/fast tests only
uv run pytest tests/test_read_silo_simple.py

# Run with coverage report
uv run pytest tests/ --cov=src --cov-report=term-missing

# Run specific test
uv run pytest tests/test_read_silo_simple.py::test_extract_single_point -v

# Skip integration tests
uv run pytest tests/ -m "not integration"
```

**Note:** Tests require SILO data in `~/Developer/DATA/silo_grids/`. If unavailable, tests auto-skip.

### Code Quality
```bash
# Format code (using ruff)
uv run ruff format .

# Lint code
uv run ruff check .

# Run bandit security checks
uv run bandit -r src/

```

### CLI Usage During Development
```bash
# Run CLI without installation
uv run weather-tools --help

# Query SILO API (requires SILO_API_KEY environment variable)
export SILO_API_KEY="your.email@example.com"
uv run weather-tools silo patched-point --station 30043 --start-date 20230101 --end-date 20230131 --var R --var X

# Work with local NetCDF files
uv run weather-tools local extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2020-12-31

# Download SILO data from AWS S3
uv run weather-tools local download --var daily --start-year 2020 --end-year 2023

# Download GeoTIFF files with spatial clipping
uv run weather-tools geotiff download --var daily_rain \
    --start-date 2023-01-01 --end-date 2023-01-31 \
    --bbox 150.5 -28.5 154.0 -26.0
```

### Download SILO Data
```bash
# Download daily variables for 2020-2023
weather-tools local download --var daily --start-year 2020 --end-year 2023

# Download specific variables
weather-tools local download --var daily_rain --var max_temp \
    --start-year 2022 --end-year 2023

# Download to custom directory with force overwrite
weather-tools local download --var monthly \
    --start-year 2020 --end-year 2023 \
    --silo-dir /data/silo_grids --force
```

## Architecture

### Core Modules

**`silo_models.py`** - Pydantic models for type-safe API interactions
- `SiloDataset`, `SiloFormat`, `ClimateVariable` enums define API options
- `SiloDateRange` validates dates (YYYYMMDD format, 1889-present)
- `AustralianCoordinates` validates lat/lon within Australian bounds
- `PatchedPointQuery` and `DataDrillQuery` represent API requests
- `SiloResponse` wraps API responses with metadata
- All query models have `to_api_params()` method to convert to HTTP parameters

**`silo_api.py`** - HTTP client for SILO API
- `SiloAPI` class handles all API communication
- Retry logic with exponential backoff for transient errors
- Optional response caching (disabled by default)
- `log_level` controls constructed URL emission (set to `DEBUG` for request details)
- Two query methods: `query_patched_point()` and `query_data_drill()` accept Pydantic models
- Convenience methods (`get_patched_point()`, `get_data_drill()`, `search_stations()`) accept simple string arguments
- `_response_to_dataframe()` converts API responses to pandas DataFrames
- Error handling via `SiloAPIError` exception

**`silo_variables.py`** - Central registry for climate variables
- Maps between API codes (R, X, N) and NetCDF names (daily_rain, max_temp)
- Variable metadata including units, start years, descriptions
- Preset groups for common variable collections ("daily", "monthly", etc.)
- Used by both API client and download module for consistency

**`download_silo.py`** - NetCDF file downloader
- Downloads files from AWS S3 public data (`s3-ap-southeast-2.amazonaws.com/silo-open-data`)
- Constructs URLs: `{base}/annual/{variable}/{year}.{variable}.nc`
- Rich progress bars with download speed and ETA
- Validates year ranges based on variable availability
- Skips existing files by default (override with `--force`)
- Creates directory structure compatible with `read_silo_xarray()`

**`read_silo_xarray.py`** - Local NetCDF file loader
- `read_silo_xarray()` loads local SILO gridded data into xarray datasets
- Supports variable presets: "daily", "monthly", or explicit variable lists
- Uses centralized preset definitions from `silo_variables.py`
- Default data directory: `~/Developer/DATA/silo_grids/`
- Expected structure: `{variable_name}/{year}.{variable_name}.nc`

**`silo_geotiff.py`** - Cloud-Optimized GeoTIFF support
- `construct_daily_url()` and `construct_monthly_url()` - Build URLs for SILO GeoTIFF files on S3
- `read_cog()` - Read COG data for Point/Polygon geometries using HTTP range requests
- `download_geotiff_with_subset()` - Download GeoTIFF files with optional spatial clipping
- `read_geotiff_timeseries()` - Read time series data (streaming or disk-cached)
- `download_geotiff_range()` - Batch download GeoTIFFs with progress tracking
- Leverages COG features: partial spatial reads, overview pyramids, HTTP range requests
- Supports both in-memory streaming (no disk usage) and disk caching workflows
- Error handling via `SiloGeoTiffError` exception

### Logging and Console Output

Use the shared helpers in `weather_tools.logging_utils` for all CLI and SDK messaging. Call `configure_logging()` once (for example in `cli.main()`) to attach the Rich-backed handler that writes through the shared console. When you need a console object for progress bars, call `get_console()`, but send user-facing messages through the standard logging APIs rather than `console.print()`. The configured handler already understands Rich markup such as `[green]...[/green]`, so existing styling keeps working. Avoid configuring logging manually in new modules; reuse these helpers to maintain consistent output formatting.

**`cli.py`** - Typer-based command-line interface
- Main app with three subcommands: `silo` (API queries), `local` (NetCDF files), `geotiff` (COG files)
- `silo` commands: `patched-point`, `data-drill`, `search`
- `local` commands: `extract`, `info`, `download`
- `geotiff` commands: `download` (with optional --bbox or --geometry clipping)
- Entry point: `main()` function registered as `weather-tools` script

### Data Flow

**API Query Flow:**
1. User creates Pydantic query model (`PatchedPointQuery` or `DataDrillQuery`)
2. Query model validates all parameters (coordinates, dates, variables)
3. `SiloAPI` converts query to HTTP params via `to_api_params()`
4. API makes request with retry logic and optional caching
5. Response parsed into `SiloResponse` with format/dataset metadata
6. Can convert to DataFrame via `_response_to_dataframe()` or access raw data

**Local File Flow:**
1. `read_silo_xarray()` scans directory for NetCDF files matching variable names
2. Opens files with xarray, concatenates across years
3. Returns xarray Dataset with time/lat/lon coordinates
4. User can use xarray's `.sel()` for location/time slicing, then `.to_dataframe()`

**GeoTIFF Flow:**
1. User provides Point or Polygon geometry (shapely) and date range
2. `read_geotiff_timeseries()` or `read_cog()` constructs URLs using `construct_daily_url()`
3. COG files read directly from S3 using HTTP range requests (rasterio)
4. `geometry_window()` calculates spatial subset to read
5. Only requested pixels transferred via HTTP range requests (COG efficiency)
6. Returns numpy arrays with time dimension, ready for analysis
7. Optional: Files cached to disk for reuse (via `save_to_disk=True`)

### Key Design Patterns

**Type Safety via Pydantic:**
- All API parameters validated before requests
- Enums prevent invalid variable codes, formats, or datasets
- Date ranges validated for format and logical ordering
- Australian coordinate bounds enforced

**Dual Interface:**
- Low-level: Use Pydantic models for full type safety and validation
- High-level: Use convenience methods with simple strings for quick queries
- CLI wraps both approaches for command-line access

**Error Handling:**
- `SiloAPIError` for all API-related failures (HTTP errors, SILO-specific errors)
- Retry logic only for transient errors (timeouts, connection issues)
- No retries for validation errors or 4xx HTTP responses
- Tests auto-skip when data unavailable rather than failing

## Important Notes

### SILO API Requirements
- API key is an email address, set via `SILO_API_KEY` environment variable or passed to `SiloAPI(api_key="...")`
- PatchedPoint and DataDrill use different endpoints but share parameter structure
- Some formats (NEAR, NAME, ID) only work with PatchedPoint dataset
- Date format is always YYYYMMDD (no dashes or slashes)
- Variable codes are single letters (R=rainfall, X=max_temp, N=min_temp, etc.)

### Local Data Structure
- NetCDF files must be in `{variable_name}/{year}.{variable_name}.nc` structure
- Variables: `daily_rain`, `monthly_rain`, `max_temp`, `min_temp`, `evap_syn`, `evap_pan`, `radiation`, `vp`
- Files use GDA94 coordinate system with lat/lon dimensions
- Time dimension named "time" with datetime64 dtype

### Module Dependencies
- CLI imports `silo_api`, `read_silo_xarray`, `download_silo`, and `silo_geotiff` modules
- `silo_api` imports `silo_models` for all type definitions
- `read_silo_xarray` imports `silo_variables` for preset expansion
- `download_silo` imports `silo_variables` for variable metadata
- `silo_geotiff` imports `silo_variables` for variable metadata and preset expansion
- `silo_geotiff` uses `rasterio` for COG reading and `shapely` for geometry handling
- No circular dependencies

### Testing Strategy
- Tests split into simple (fast) and comprehensive suites
- Use fixtures to check for data availability before running
- Always close xarray datasets with `ds.close()` to free memory
- Integration tests marked with `pytest.mark.integration`
- Mock API responses for `silo_api` tests to avoid real API calls

### NetCDF Downloads
- Files downloaded from AWS S3 public data (no authentication required)
- Daily variable files are ~410MB each (365-366 daily grids)
- Monthly rainfall files are ~14MB each (12 monthly grids)
- S3 does not support partial downloads - entire files must be downloaded
- Geographic filtering should be done after download using xarray's `.sel()` method
- Variable availability varies by year (most: 1889+, MSLP: 1957+, evap_pan: 1970+)

### GeoTIFF Structure and Usage
- **URL Pattern**: `https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/daily/{variable}/{year}/{YYYYMMDD}.{variable}.tif`
- **File Organization** (when cached): `{cache_dir}/{variable}/{year}/{YYYYMMDD}.{variable}.tif`
- **COG Benefits**: Only download pixels you need via HTTP range requests (much faster than full file)
- **Date Format**: GeoTIFF uses YYYY-MM-DD (unlike NetCDF which uses years)
- **CRS**: All GeoTIFFs are in EPSG:4326 (WGS84 lat/lon)
- **Geometry Support**: Accept shapely Point or Polygon objects
- **Workflows**:
  - **Streaming**: `save_to_disk=False` reads directly from S3 without caching (great for one-off queries)
  - **Caching**: `save_to_disk=True` downloads to local disk for reuse
- **CLI vs Python API**:
  - CLI: Download command only (saves to disk with optional spatial clipping)
  - Python API: Full functionality including streaming reads and Point/Polygon queries

### Common Pitfalls
- Forgetting to set `SILO_API_KEY` environment variable causes initialization error
- PatchedPoint queries require `station_code`, DataDrill queries require `coordinates`
- Date ranges must include both start_date and end_date for data queries
- Local file paths assume specific directory structure - missing files cause FileNotFoundError
- NetCDF download command uses year range (--start-year/--end-year), GeoTIFF uses dates (--start-date/--end-date)
- GeoTIFF geometries use (lon, lat) order, not (lat, lon) - `Point(153.0, -27.5)` is Brisbane
- GeoTIFF CRS must be EPSG:4326 - other projections will raise `SiloGeoTiffError`
- Some GeoTIFF files may return 404 if data is unavailable for that date (handled gracefully, logs warning)
