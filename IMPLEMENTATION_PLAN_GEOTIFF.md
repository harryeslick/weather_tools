# SILO GeoTIFF/COG Support Implementation Plan

## 1. Objectives

### Primary Goals
- Add support for downloading and reading SILO Cloud-Optimized GeoTIFF (COG) files
- Leverage COG features: partial spatial reads, overview pyramids, HTTP range requests
- Support shapely geometry queries (Point and Polygon)
- Intelligent file management: check existing files, skip if present, graceful handling of missing files
- Consistent architecture with existing weather_tools modules

### Expected Outcomes
- **New module**: `src/weather_tools/silo_geotiff.py` - core GeoTIFF functionality
- **CLI extension**: New `weather-tools geotiff` subcommand group
- **Python API**: Flexible read/download functions with geometry support
- **Tests**: Unit and integration tests for GeoTIFF operations
- **Documentation**: Updated README and docstrings

---

## 2. Module Architecture

### 2.1 Core Module: `src/weather_tools/silo_geotiff.py`

**Dependencies**:
```python
import datetime
import logging
from pathlib import Path
from typing import Optional, Union, List, Tuple
import numpy as np
import rasterio
from rasterio.features import geometry_window
from shapely.geometry import Point, Polygon, box
import requests
from rich.console import Console
from rich.progress import Progress
from .silo_variables import get_variable_metadata, expand_variable_preset
```

**Key Classes/Functions**:

#### **`GeoTiffURLBuilder`**
- `construct_daily_url(variable: str, date: datetime.date) -> str`
  - Format: `https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/daily/{variable}/{year}/{YYYYMMDD}.{variable}.tif`
- `construct_monthly_url(variable: str, year: int, month: int) -> str`
  - Format: `https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/monthly/{variable}/{year}/{YYYYMM}.{variable}.tif`

#### **`read_cog()`**
```python
def read_cog(
    cog_url: str,
    geometry: Union[Point, Polygon],
    overview_level: Optional[int] = None,
    use_mask: bool = True
) -> Tuple[np.ndarray, dict]:
    """
    Read COG data for given geometry using HTTP range requests.

    Args:
        cog_url: URL to COG file
        geometry: Shapely Point or Polygon defining area of interest
        overview_level: Pyramid level (None=full resolution, 0=first overview, etc)
        use_mask: Return masked array (np.ma.MaskedArray) with nodata handling

    Returns:
        Tuple of (data array, rasterio profile dict)

    Implementation:
        - Open COG via rasterio.open(cog_url)
        - Validate CRS is EPSG:4326
        - Calculate window from geometry using geometry_window()
        - Read data with window parameter for partial read
        - Apply overview_level if specified
        - Return masked array with proper nodata handling
    """
```

#### **`download_geotiff_with_subset()`**
```python
def download_geotiff_with_subset(
    url: str,
    destination: Path,
    geometry: Optional[Union[Point, Polygon]] = None,
    force: bool = False,
    timeout: int = 300
) -> bool:
    """
    Download single GeoTIFF file, optionally clipped to geometry subset.

    Args:
        url: Source URL
        destination: Local file path
        geometry: Optional shapely geometry to clip/subset the downloaded file
                  If None, downloads entire file. If provided, downloads full file
                  but saves only the clipped portion.
        force: Overwrite if exists
        timeout: Request timeout

    Returns:
        True if downloaded, False if skipped (exists), raises on error

    Implementation:
        - Check if destination exists (skip if not force)
        - Create parent directories
        - If geometry is None: stream download entire file
        - If geometry provided:
            * Open COG from URL with rasterio
            * Calculate window from geometry
            * Read windowed data
            * Write clipped GeoTIFF to destination with updated transform
        - Return False for 404 errors (log warning, don't raise)
        - Raise SiloGeoTiffError for other HTTP errors
    """
```

#### **`read_geotiff_timeseries()`**
```python
def read_geotiff_timeseries(
    variables: Union[str, List[str]],
    start_date: datetime.date,
    end_date: datetime.date,
    geometry: Union[Point, Polygon],
    save_to_disk: bool = False,
    cache_dir: Optional[Path] = None,
    overview_level: Optional[int] = None,
    console: Optional[Console] = None
) -> dict[str, np.ndarray]:
    """
    Read time series of GeoTIFF data for date range and geometry.

    Args:
        variables: Variable names or preset ("daily", "monthly")
        start_date: First date (inclusive)
        end_date: Last date (inclusive)
        geometry: Shapely geometry for spatial query
        save_to_disk: If True, download to cache_dir; if False, stream from URL
        cache_dir: Where to save files (default: ./DATA/silo_grids/geotiff)
        overview_level: Pyramid level for reduced resolution
        console: Rich console for progress output

    Returns:
        Dict mapping variable names to 3D numpy arrays (time, height, width)

    Implementation:
        1. Expand variable presets using silo_variables.expand_variable_preset()
        2. Generate date sequence (daily or monthly based on variable)
        3. For each variable and date:
           - Construct URL
           - Check if file exists locally (if save_to_disk)
           - Download if needed (only if missing and save_to_disk=True)
           - Read with read_cog() using geometry
           - Handle 404s: log warning and continue (don't fail entire query)
           - Collect arrays
        4. Stack arrays into 3D array per variable
        5. Return dict of arrays with metadata
    """
```

#### **`download_geotiff_range()`**
```python
def download_geotiff_range(
    variables: Union[str, List[str]],
    start_date: datetime.date,
    end_date: datetime.date,
    output_dir: Path,
    geometry: Optional[Union[Point, Polygon]] = None,
    bounding_box: Optional[Tuple[float, float, float, float]] = None,
    force: bool = False,
    console: Optional[Console] = None
) -> dict[str, List[Path]]:
    """
    Download GeoTIFF files for date range, optionally clipped to geometry/bbox (CLI-focused).

    Similar to download_silo_gridded() but for daily/monthly GeoTIFFs.

    Args:
        variables: Variable names or preset
        start_date: First date
        end_date: Last date
        output_dir: Directory to save files
        geometry: Optional shapely geometry to clip downloads
        bounding_box: Optional (min_lon, min_lat, max_lon, max_lat) tuple
                      Converted to Polygon for clipping. Mutually exclusive with geometry.
        force: Overwrite existing files
        console: Rich console for output

    Returns:
        Dict mapping variable names to lists of downloaded file paths

    Implementation:
        - Validate variables using silo_variables.get_variable_metadata()
        - Convert bounding_box to Polygon if provided
        - Build download task list (variable, date, URL, destination)
        - Validate year ranges against variable metadata start_year
        - Skip dates before variable start_year
        - Use Rich progress bars
        - Call download_geotiff_with_subset() for each file
        - On 404: log warning and continue (server may be missing some dates)
        - Return dict of downloaded paths per variable
    """
```

#### **Exception Classes**
```python
class SiloGeoTiffError(Exception):
    """Base exception for GeoTIFF operations"""
    pass
```

---

### 2.2 CLI Integration: `src/weather_tools/cli.py`

Add new subcommand group `geotiff_app`:

```python
geotiff_app = typer.Typer(
    name="geotiff",
    help="Work with SILO Cloud-Optimized GeoTIFF files",
    no_args_is_help=True,
)
app.add_typer(geotiff_app, name="geotiff")
```

#### **Commands**

**`geotiff download`** - Download GeoTIFF files (optionally clipped to geometry/bbox)

```bash
# Download entire files
weather-tools geotiff download \
    --var daily_rain --var max_temp \
    --start-date 2023-01-01 \
    --end-date 2023-12-31 \
    --output-dir ./DATA/silo_grids/geotiff \
    --force

# Download with bounding box clipping
weather-tools geotiff download \
    --var daily_rain \
    --start-date 2023-01-01 \
    --end-date 2023-01-31 \
    --bbox 150.5 -28.5 154.0 -26.0 \
    --output-dir ./DATA/silo_grids/geotiff

# Download with geometry file clipping
weather-tools geotiff download \
    --var daily_rain \
    --start-date 2023-01-01 \
    --end-date 2023-01-31 \
    --geometry region.geojson \
    --output-dir ./DATA/silo_grids/geotiff
```

**Parameters**:
- `--var`: Variable names (repeatable, supports presets like "daily")
- `--start-date` / `--end-date`: Date range (YYYY-MM-DD format)
- `--output-dir`: Where to save GeoTIFFs (default: `./DATA/silo_grids/geotiff`)
- `--bbox`: Bounding box as four values: min_lon min_lat max_lon max_lat (mutually exclusive with --geometry)
- `--geometry`: Path to GeoJSON file with Polygon for clipping (mutually exclusive with --bbox)
- `--force`: Overwrite existing files

**Note**: Reading/extracting data to CSV is ONLY available through the Python API, not the CLI.

#### **Python API Usage Examples**

```python
from shapely.geometry import Point, Polygon
from weather_tools.silo_geotiff import read_geotiff_timeseries, read_cog
from datetime import date

# Example 1: Read timeseries for a Point (in-memory, no disk caching)
point = Point(153.0, -27.5)  # Note: lon, lat order
data = read_geotiff_timeseries(
    variables=["daily_rain", "max_temp"],
    start_date=date(2023, 1, 1),
    end_date=date(2023, 1, 31),
    geometry=point,
    save_to_disk=False  # Stream from URL, no caching
)
# Returns: {"daily_rain": array(31, h, w), "max_temp": array(31, h, w)}

# Example 2: Read timeseries for a Polygon (with disk caching)
polygon = Polygon([(152.5, -28.0), (153.5, -28.0), (153.5, -27.0), (152.5, -27.0)])
data = read_geotiff_timeseries(
    variables="daily",  # Uses preset
    start_date=date(2023, 1, 1),
    end_date=date(2023, 1, 7),
    geometry=polygon,
    save_to_disk=True,
    cache_dir=Path("./DATA/silo_grids/geotiff")
)

# Example 3: Read single COG file for a location
cog_url = "https://s3-ap-southeast-2.amazonaws.com/.../20230101.daily_rain.tif"
data, profile = read_cog(cog_url, geometry=point)
# data is masked numpy array, profile has georeferencing info
```

---

### 2.3 Dependencies Update: `pyproject.toml`

Add new required dependencies:
```toml
dependencies = [
    # ... existing ...
    "rasterio>=1.3.0",
    "shapely>=2.0.0",
]
```

Optional for GeoJSON reading:
```toml
[project.optional-dependencies]
geotiff = [
    "geopandas>=0.14.0",  # For loading GeoJSON geometries
]
```

---

## 3. Implementation Steps

### Phase 0: Update Variable Registry (Priority: High, if needed)

**File**: `src/weather_tools/silo_variables.py`

1. **Review VariableMetadata for GeoTIFF support**
   - Check if existing variable metadata includes all variables available in GeoTIFF format
   - If GeoTIFFs support different variables than NetCDF/API, add them to SILO_VARIABLES dict
   - Ensure `netcdf_name` field can be used for GeoTIFF URLs (likely same naming convention)
   - Update presets if needed

2. **Validation**
   - All modules (download_silo, silo_geotiff, silo_api) must reference this central registry
   - No hardcoded variable lists in silo_geotiff module
   - All variable validation must use `get_variable_metadata()`

### Phase 1: Core GeoTIFF Module (Priority: High)

**File**: `src/weather_tools/silo_geotiff.py`

1. **Create URL construction functions**
   - Implement `construct_daily_url()`
   - Implement `construct_monthly_url()`
   - **CRITICAL**: Validate all variable names using `silo_variables.get_variable_metadata()`
   - This module must use `silo_variables.py` as the central source of truth for variable mappings
   - Test with known URLs from documentation

2. **Implement `read_cog()` function**
   - Based on `rasterio_cog_example.py:read_cog()`
   - Add CRS validation (assert EPSG:4326)
   - Add geometry window calculation
   - Support overview levels
   - Return masked arrays with nodata handling
   - Add comprehensive error handling

3. **Implement `download_geotiff_with_subset()` function**
   - Pattern based on `download_silo.py:download_file()`
   - Check file existence before download
   - Support optional geometry clipping during download
   - If geometry provided: use rasterio to read windowed data and write clipped GeoTIFF
   - If no geometry: stream full file download
   - Handle 404 gracefully (return False, log warning)
   - Raise SiloGeoTiffError for other HTTP errors
   - Support force overwrite

4. **Implement `read_geotiff_timeseries()` function**
   - Generate date sequences
   - Loop over variables and dates
   - Call `read_cog()` for each file
   - Option: save_to_disk vs in-memory streaming
   - Aggregate into 3D numpy arrays
   - Rich progress display

5. **Implement `download_geotiff_range()` function**
   - Pattern based on `download_silo.py:download_silo_gridded()`
   - Support optional geometry or bounding_box parameters (mutually exclusive)
   - Convert bounding_box tuple to Polygon if provided
   - Validate variables using `silo_variables.get_variable_metadata()`
   - Build download task list
   - Validate date ranges against variable metadata start_year
   - Call `download_geotiff_with_subset()` for each file
   - Rich progress bars
   - Summary output

### Phase 2: CLI Integration (Priority: High)

**File**: `src/weather_tools/cli.py`

1. **Add `geotiff_app` subcommand group**
   - Create Typer app
   - Add to main app with `app.add_typer()`

2. **Implement `geotiff download` command**
   - Parameters: variables, start-date, end-date, output-dir, bbox, geometry, force
   - Parse bbox (4 float values) or geometry (GeoJSON file path)
   - Validate that bbox and geometry are mutually exclusive
   - If geometry file provided: load using geopandas or shapely
   - Call `download_geotiff_range()` with appropriate parameters
   - Display summary

**Note**: There is NO extract command in CLI. Data extraction using Point geometries is ONLY available through the Python API (`read_geotiff_timeseries()` and `read_cog()` functions).

### Phase 3: Testing (Priority: High)

**File**: `tests/test_silo_geotiff.py`

1. **Unit tests**
   - URL construction (daily/monthly, various variables)
   - Geometry validation
   - Date range generation
   - Error handling (404s, invalid geometries, etc.)

2. **Integration tests** (marked with `@pytest.mark.integration`)
   - Download single GeoTIFF (small date range)
   - Read COG with Point geometry
   - Read COG with Polygon geometry
   - Test overview levels
   - Test caching behavior (existing files skipped)
   - Test 404 handling (invalid date that doesn't exist on server)
   - Test time series aggregation

3. **CLI tests**
   - Test `geotiff download` command (basic download)
   - Test `geotiff download` with bounding box clipping
   - Test `geotiff download` with geometry file clipping
   - Verify mutually exclusive bbox/geometry validation

### Phase 4: Documentation (Priority: Medium)

1. **Update README.md**
   - Add GeoTIFF section under "Features"
   - Add CLI examples for `weather-tools geotiff`
   - Add Python API examples
   - Update module relationships diagram (add silo_geotiff.py)

2. **Add comprehensive docstrings**
   - All public functions with Args, Returns, Examples
   - Module-level docstring explaining COG benefits

3. **Create example notebook** (optional)
   - Demonstrate partial reads
   - Show overview usage for quick previews
   - Compare performance: COG vs NetCDF downloads

---

## 4. Technical Specifications

### URL Patterns
```
Daily:   https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/daily/{variable}/{year}/{YYYYMMDD}.{variable}.tif
Monthly: https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/monthly/{variable}/{year}/{YYYYMM}.{variable}.tif
```

### File Storage Structure (when save_to_disk=True)
```
{cache_dir}/
├── daily_rain/
│   ├── 2023/
│   │   ├── 20230101.daily_rain.tif
│   │   ├── 20230102.daily_rain.tif
│   │   └── ...
│   └── 2024/
│       └── ...
├── max_temp/
│   └── 2023/
│       └── ...
```

Default cache_dir: `./DATA/silo_grids/geotiff/`

### Geometry Handling
- **Point**: Use lat/lon to create `shapely.geometry.Point(lon, lat)` (note: lon first!)
- **Polygon**: Load from GeoJSON using `geopandas.read_file()` or `shapely.from_geojson()`
- Window calculation: Use `rasterio.features.geometry_window()`

### COG Optimization Features
- **Partial reads**: Only read pixels within geometry window (reduces bandwidth)
- **Overviews**: Use pyramid levels for quick previews at reduced resolution
- **HTTP range requests**: rasterio automatically uses HTTP byte ranges for efficiency

### Error Handling
- **404 Not Found**: Log warning, continue to next file (some dates may be unavailable)
- **Invalid geometry**: Raise `SiloGeoTiffError` with clear message
- **CRS mismatch**: Raise error if GeoTIFF is not EPSG:4326
- **Network errors**: Retry logic (optional) or clear error messages

---

## 5. Testing Strategy

### Test Data
- Use recent dates (e.g., 2023-01-01 to 2023-01-07) for small test range
- Test variables: `daily_rain`, `max_temp` (reliable availability)
- Test geometries:
  - Point: Brisbane CBD (-27.4698, 153.0251)
  - Polygon: Small bounding box around Brisbane

### Test Coverage
- URL construction for all variable types
- Read single COG with Point
- Read single COG with Polygon
- Read time series (7 days)
- Download to disk and verify file existence
- Skip existing files (not force)
- Handle missing dates on server gracefully
- Overview level functionality

### Performance Tests (optional)
- Compare download time: small geometry vs full tile
- Compare overview vs full resolution
- Memory usage for large date ranges

---

## 6. Code Quality Checks

- Run `uv run ruff format .`
- Run `uv run ruff check .`
- Run `uv run pytest tests/test_silo_geotiff.py -v`
- Run `uv run pytest tests/test_silo_geotiff.py --cov=src/weather_tools/silo_geotiff`

---

## 7. Open Questions / Design Decisions

1. **Output format for polygon queries**: Return 3D array (time, height, width) or aggregate to mean/stats per timestep?
   - **Recommendation**: Return full 3D array, let user aggregate as needed

2. **Monthly variable support**: Monthly rainfall uses different URL pattern - support in initial version?
   - **Recommendation**: Yes, add monthly support from start using `construct_monthly_url()`

3. **Coordinate reference system handling**: Support reprojection if user provides non-EPSG:4326 geometry?
   - **Recommendation**: Phase 2 feature. Initial version requires EPSG:4326, raise clear error otherwise

4. **Caching strategy**: LRU cache for recently accessed files?
   - **Recommendation**: Not needed initially. File-based caching (check if exists) is sufficient

---

## 8. Success Criteria

✅ Developer can download daily GeoTIFF files via CLI (full files or clipped to geometry/bbox)
✅ CLI supports bounding box and geometry file parameters for spatial subsetting
✅ Python API supports both in-memory and disk-cached workflows
✅ Python API allows Point and Polygon geometry queries for data extraction
✅ All variable validation uses `silo_variables.py` as central source of truth
✅ Smart file management: skips existing files, handles missing dates gracefully
✅ Leverages COG features: partial reads demonstrated and tested
✅ Tests achieve >80% coverage on new module
✅ Documentation includes clear examples for both CLI and Python API
✅ Consistent code style with existing weather_tools modules
✅ No CSV extraction in CLI - extraction is Python API only

---

## 9. User Requirements (from discussion)

### Storage/Caching Behavior
- **CLI**: Always download files to disk with caching at `./DATA/silo_grids/geotiff/<variable>/<year>/<file>.tif`
  - Root location should be user configurable (default: current working directory)
  - Similar pattern to existing NetCDF downloads

- **Python API**: Flexible approach
  - `save_to_disk=True`: Download and cache files locally
  - `save_to_disk=False`: Work in memory only (stream from URL without saving)
  - No caching feature required for in-memory mode

### Output Format
- Primary output: **numpy arrays** (specifically `np.ndarray` or `np.ma.MaskedArray`)
- Return format: Dict mapping variable names to 3D arrays `{variable: array(time, height, width)}`
- Include rasterio profile dict for georeferencing metadata

### Module Organization
- Create **new separate module** `src/weather_tools/silo_geotiff.py`
- Keep GeoTIFF functionality isolated from existing NetCDF download module
- Better separation of concerns between annual NetCDF and daily/monthly GeoTIFF workflows

### CLI vs Python API Separation
- **CLI**: Only download command, NO extract/read commands
  - `geotiff download` supports optional geometry/bbox clipping
  - Saves files to disk (always caches)
  - No data extraction to CSV

- **Python API**: Full functionality
  - Download AND read capabilities
  - Point geometry queries for extracting timeseries data
  - Polygon geometry queries for spatial subsets
  - Choice of in-memory or disk-cached workflows

### Variable Validation
- **CRITICAL**: All modules must use `silo_variables.py` as the single source of truth
- No hardcoded variable lists in any module
- All variable names validated via `get_variable_metadata()`
- If GeoTIFF supports additional variables, add them to `silo_variables.py` FIRST
