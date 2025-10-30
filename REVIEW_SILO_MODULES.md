# Code Review: SILO Download Modules

## Executive Summary

Review of `download_silo.py` (NetCDF) and `silo_geotiff.py` (GeoTIFF) modules reveals:
- **Naming issues**: Unclear distinction between NetCDF and GeoTIFF operations
- **API inconsistencies**: Different parameter patterns for similar operations
- **Duplication**: Significant overlap in validation, error handling, and infrastructure

---

## 1. Naming Issues

### 1.1 Unclear Function Names

| Current Name | Issue | Suggested Name |
|-------------|-------|----------------|
| `download_silo_gridded()` | Doesn't indicate NetCDF format | `download_netcdf()` or `download_silo_netcdf()` |
| `construct_download_url()` | Too generic, no format indication | `construct_netcdf_url()` |
| `download_geotiff_range()` | "range" is vague, inconsistent with NetCDF | `download_geotiff()` |
| `construct_daily_url()` | Doesn't indicate GeoTIFF format | `construct_geotiff_daily_url()` |
| `construct_monthly_url()` | Doesn't indicate GeoTIFF format | `construct_geotiff_monthly_url()` |

### 1.2 Naming Patterns

**Recommendation**: Adopt consistent naming pattern across both modules:

```python
# NetCDF module
download_netcdf(...)
construct_netcdf_url(variable, year)

# GeoTIFF module
download_geotiff(...)
construct_geotiff_url(variable, date)  # or keep daily/monthly variants
```
**Decision**: Agree
---

## 2. API Consistency Issues

### 2.1 Time Range Parameters

**INCONSISTENT:**

```python
# download_silo.py (NetCDF)
def download_silo_gridded(
    variables: VariableInput,
    start_year: int,        # ← Year-based
    end_year: int,          # ← Year-based
    ...
)

# silo_geotiff.py
def download_geotiff_range(
    variables: VariableInput,
    start_date: datetime.date,  # ← Date-based
    end_date: datetime.date,    # ← Date-based
    ...
)
```

**Issue**: Different temporal granularity makes API confusing.

**Options**:
1. **Keep as-is** (justified by data granularity - NetCDF is annual, GeoTIFF is daily)
2. **Unify to dates** - NetCDF accepts dates but only downloads years that span the range
3. **Add both** - NetCDF adds optional date parameters for consistency

**Recommendation**: Option 1 with better documentation explaining the difference.
**Decision**: go with option 1.


### 2.2 Timeout Parameter

**INCONSISTENT:**

```python
# download_silo.py
def download_silo_gridded(..., timeout: int = 600, ...)  # Has timeout

# silo_geotiff.py
def download_geotiff_range(...)  # NO timeout parameter!
    # But download_geotiff_with_subset() has timeout=300
```

**Recommendation**: Add `timeout` parameter to `download_geotiff_range()` and pass through to `download_geotiff_with_subset()`.
**Decision**: Agree

### 2.3 Validation Differences

**INCONSISTENT:**

```python
# download_silo.py - Validates year range
if start_year > end_year:
    raise ValueError(...)
if end_year > current_year:
    raise ValueError(...)

# silo_geotiff.py - NO date range validation!
# Accepts any dates, even future dates
```

**Recommendation**: Add date range validation to GeoTIFF module:
```python
if start_date > end_date:
    raise ValueError("start_date must be <= end_date")
# Optionally check against current date
```

**Decision**: Agree. Allow future dates is the correct behaviour. future dates should warn user re the date range which is not available. The command should be able to be run again in the future when more date area available, and the gaps will be filled. eg. I would like to set the date range for the whole year in January, and run the same command weekly, to fetch the new datasets. 

### 2.4 Error Types

**INCONSISTENT:**

```python
# download_silo.py
raise ValueError("Invalid variables or year range")      # For parameter errors
raise SiloDownloadError("HTTP error downloading...")     # For download errors

# silo_geotiff.py
raise SiloGeoTiffError("Unknown variable: {var_name}")   # For parameter errors
raise SiloGeoTiffError("HTTP error downloading {url}...")  # For download errors
```

**Recommendation**: Use consistent pattern:
- `ValueError` for invalid parameters (bad user input)
- `SiloDownloadError` / `SiloGeoTiffError` for operational failures (network, file system)

**Decision**: Agree

---

## 3. Duplication Opportunities

### 3.1 Exception Hierarchy

**CURRENT:**
```python
# download_silo.py
class SiloDownloadError(Exception):
    pass

# silo_geotiff.py
class SiloGeoTiffError(Exception):
    pass
```

**PROPOSED** (in `silo_variables.py` or new `silo_exceptions.py`):
```python
class SiloDataError(Exception):
    """Base exception for SILO data operations."""
    pass

class SiloNetCDFError(SiloDataError):
    """NetCDF-specific errors."""
    pass

class SiloGeoTiffError(SiloDataError):
    """GeoTIFF-specific errors."""
    pass
```

**Benefits**:
- Unified exception handling: `except SiloDataError`
- Clear hierarchy
- Shared error utilities

**Decision**: Agree

---

### 3.2 Constants

**CURRENT:**
```python
# download_silo.py
DEFAULT_TIMEOUT = 600

# silo_geotiff.py
timeout: int = 300  # Hardcoded in download_geotiff_with_subset()
```

**PROPOSED** (in `silo_variables.py` or new `silo_constants.py`):
```python
# Timeouts
DEFAULT_NETCDF_TIMEOUT = 600  # Large files (400MB+)
DEFAULT_GEOTIFF_TIMEOUT = 300  # Smaller files or COG streaming

# S3 base URLs
SILO_S3_BASE_URL = "https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official"
SILO_NETCDF_BASE_URL = f"{SILO_S3_BASE_URL}/annual"
SILO_GEOTIFF_BASE_URL = f"{SILO_S3_BASE_URL}"  # daily/monthly added in construct functions
```
**Decision**: Agree

---

### 3.3 Variable Validation

**DUPLICATED PATTERN** (both modules):

```python
# Both do this:
var_list = expand_variable_preset(variables)

metadata_map: dict[str, VariableMetadata] = {}
for var_name in var_list:
    metadata = get_variable_metadata(var_name)
    if metadata is None:
        raise SomeError(f"Unknown variable: {var_name}")
    metadata_map[var_name] = metadata
```

**PROPOSED** (in `silo_variables.py`):

```python
def validate_variables(
    variables: VariableInput,
    error_class: type[Exception] = ValueError
) -> dict[str, VariableMetadata]:
    """
    Validate and expand variables, returning metadata map.

    Args:
        variables: Variable preset/name or list
        error_class: Exception class to raise for unknown variables

    Returns:
        Dict mapping variable names to metadata

    Raises:
        error_class: If any variable is unknown
    """
    var_list = expand_variable_preset(variables)

    metadata_map: dict[str, VariableMetadata] = {}
    for var_name in var_list:
        metadata = get_variable_metadata(var_name)
        if metadata is None:
            raise error_class(f"Unknown variable: {var_name}")
        metadata_map[var_name] = metadata

    return metadata_map
```

**Usage**:
```python
# In both modules:
metadata_map = validate_variables(variables, SiloGeoTiffError)
```
**Decision**: Agree. adjust function name to distinuguish this from other variables in the package. eg validate_silo_S3_variables ...
---

### 3.4 Year/Date Filtering

**DUPLICATED LOGIC** (checking against `metadata.start_year`):

```python
# download_silo.py (lines 229-232)
if year < metadata.start_year:
    logger.warning(f"[yellow]Skipping {var} for {year} (data starts in {metadata.start_year})[/yellow]")
    continue

# silo_geotiff.py (lines 494-496)
if date.year < metadata.start_year:
    continue
```

**PROPOSED** (in `silo_variables.py`):

```python
def is_year_valid_for_variable(
    year: int,
    metadata: VariableMetadata,
    current_year: Optional[int] = None
) -> bool:
    """Check if year is within valid range for variable."""
    if current_year is None:
        current_year = datetime.now().year

    return metadata.start_year <= year <= current_year

def filter_dates_by_variable(
    dates: List[datetime.date],
    metadata: VariableMetadata
) -> List[datetime.date]:
    """Filter dates that are valid for a variable."""
    return [d for d in dates if d.year >= metadata.start_year]
```
**Decision**: Unsure about this, please exclude for now. 
---

### 3.5 Progress Bar Configuration

**DUPLICATED:**

```python
# download_silo.py (lines 252-259)
with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    DownloadColumn(),
    TransferSpeedColumn(),
    TimeRemainingColumn(),
    console=console,
) as progress:

# silo_geotiff.py (lines 507-516)
with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),  # ← Only difference
    DownloadColumn(),
    TransferSpeedColumn(),
    TimeRemainingColumn(),
    console=console,
) as progress:
```

**PROPOSED** (in `logging_utils.py`):

```python
def create_download_progress(
    console: Optional[Console] = None,
    show_percentage: bool = False
) -> Progress:
    """Create standardized progress bar for downloads."""
    columns = [
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
    ]

    if show_percentage:
        columns.append(TextColumn("[progress.percentage]{task.percentage:>3.0f}%"))

    columns.extend([
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ])

    return Progress(*columns, console=console or get_console())
```
**Decision**: Agree
---

### 3.6 Date Range Generation

**CURRENT** (only in `silo_geotiff.py`):

```python
def _generate_date_range(start_date: datetime.date, end_date: datetime.date) -> List[datetime.date]:
    """Generate list of dates between start and end (inclusive)."""
    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date)
        current_date += datetime.timedelta(days=1)
    return date_list
```

**PROPOSED**: Move to shared utility module or keep private (it's simple enough).

**Decision**: Keep private. 
---

### 3.7 File Path Construction

**SIMILAR PATTERNS:**

```python
# download_silo.py
dest = output_dir / var / f"{year}.{var}.nc"

# silo_geotiff.py
dest_path = output_dir / var_name / str(date.year) / f"{date.strftime('%Y%m%d')}.{var_name}.tif"
```

**PROPOSED** (optional - formats differ enough to keep separate):

**Decision**: CHANGE: filenames should be the same as the original in S3. Allow an optional kwarg which appends a suffix to the name seperated using "_"

---

## 4. Summary of Recommendations

### High Priority (Breaking Changes)

1. **Rename functions for clarity**:
   - `download_silo_gridded()` → `download_netcdf()`
   - `download_geotiff_range()` → `download_geotiff()`
   - `construct_download_url()` → `construct_netcdf_url()`
   - `construct_daily_url()` → `construct_geotiff_daily_url()`

2. **Add missing validation to GeoTIFF**:
   - Date range validation (start <= end)
   - Optional check against current date

3. **Consistent error types**:
   - `ValueError` for parameter validation errors
   - Custom exceptions for operational failures

### Medium Priority (Non-Breaking)

4. **Add `timeout` parameter** to `download_geotiff_range()`

5. **Extract shared code**:
   - Create `validate_variables()` in `silo_variables.py`
   - Create base `SiloDataError` exception hierarchy
   - Consolidate constants

### Low Priority (Refinements)

6. **Extract progress bar factory** to `logging_utils.py`

7. **Add helper functions**:
   - `is_year_valid_for_variable()`
   - `filter_dates_by_variable()`
   - Path construction helpers

---

## 5. Proposed Module Structure

```
weather_tools/
├── silo_exceptions.py       # NEW: Shared exception hierarchy
├── silo_constants.py         # NEW: Shared constants (timeouts, URLs)
├── silo_variables.py         # ENHANCED: Add validation helpers
├── silo_netcdf.py           # RENAMED from download_silo.py
├── silo_geotiff.py          # EXISTING with improvements
└── logging_utils.py          # ENHANCED: Add progress bar factory
```

### Alternative (Minimal Changes)

Keep current structure but:
1. Add shared exceptions to `silo_variables.py`
2. Add validation helpers to `silo_variables.py`
3. Add constants to `silo_variables.py`
4. Rename key functions for clarity

---

## 6. Migration Path

### Phase 1: Non-Breaking Improvements
- Add validation helpers to `silo_variables.py`
- Add shared exception base class
- Add missing validation/parameters

### Phase 2: Deprecations
- Add new function names alongside old ones
- Deprecate old names with warnings
- Update documentation

### Phase 3: Breaking Changes (v2.0)
- Remove deprecated names
- Finalize API

**Decision**: This package is still in development, so breaking changes are fine. there are no external users for this package currently

