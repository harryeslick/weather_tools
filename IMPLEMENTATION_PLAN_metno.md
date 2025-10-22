# Met.no API Integration - Detailed Implementation Plan

## Overview

This document provides a comprehensive implementation plan for integrating met.no weather forecast API with the existing weather_tools package. The integration will allow users to extend SILO historical weather observations with forecast data for downstream predictions.

## Architecture Goals

- **Consistency**: Follow existing SILO API patterns (Pydantic models, API client structure, CLI commands)
- **Modularity**: Separate concerns (models, API client, variable mapping, data merging, CLI)
- **Type Safety**: Use Pydantic for validation throughout
- **User Familiarity**: CLI interface should feel natural to existing users
- **Data Quality**: Validate merges and provide clear error messages

---

## 1. Core API Module: `metno_models.py`

Create Pydantic models following the existing SILO pattern in `silo_models.py`.

### Models to Create

While the api allows users to get data from all over the globe, this package is focused on australian users only. use the existing AustralianCoordinates to limit queries

#### `MetNoFormat`
```python
class MetNoFormat(str, Enum):
    """Met.no forecast formats."""
    COMPACT = "compact"  # Standard 9-day forecast
    COMPLETE = "complete"  # Includes percentile data
```

#### `MetNoQuery`
```python
class MetNoQuery(BaseModel):
    """
    Query for met.no locationforecast API.

    Examples:
        >>> query = MetNoQuery(
        ...     coordinates=MetNoCoordinates(latitude=-27.5, longitude=153.0),
        ...     format=MetNoFormat.COMPACT
        ... )
    """
    coordinates: MetNoCoordinates
    format: MetNoFormat = Field(default=MetNoFormat.COMPACT)

    def to_api_params(self) -> Dict[str, Any]:
        """Convert to API query parameters."""
        params = {
            "lat": self.coordinates.latitude,
            "lon": self.coordinates.longitude,
        }
        if self.coordinates.altitude is not None:
            params["altitude"] = self.coordinates.altitude
        return params
```

#### `MetNoResponse`
```python
class MetNoResponse(BaseModel):
    """
    Structured met.no API response.

    Contains the raw GeoJSON response and metadata.
    """
    raw_data: Dict[str, Any] = Field(..., description="Raw GeoJSON response")
    format: MetNoFormat
    coordinates: MetNoCoordinates
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    def get_timeseries(self) -> List[Dict[str, Any]]:
        """Extract timeseries from GeoJSON structure."""
        return self.raw_data.get("properties", {}).get("timeseries", [])

```

#### `ForecastTimestamp`
```python
class ForecastTimestamp(BaseModel):
    """
    Single forecast timestamp with instant and period data.
    """
    time: datetime
    air_temperature: Optional[float] = None
    precipitation_amount: Optional[float] = None  # 1h or 6h period
    relative_humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_from_direction: Optional[float] = None
    cloud_area_fraction: Optional[float] = None
    weather_symbol: Optional[str] = None
```

#### `DailyWeatherSummary`
```python
class DailyWeatherSummary(BaseModel):
    """
    Daily aggregated weather summary from hourly forecasts.
    """
    date: date
    min_temperature: Optional[float] = None  # °C
    max_temperature: Optional[float] = None  # °C
    total_precipitation: Optional[float] = None  # mm
    avg_wind_speed: Optional[float] = None  # m/s
    avg_relative_humidity: Optional[float] = None  # %
    dominant_weather_symbol: Optional[str] = None
```

### Key Design Points

- All models use Pydantic v2 syntax (matching existing codebase)
- Coordinate validation is Australia-specific
- Query model includes `to_api_params()` for consistency with SILO
- Response model wraps raw GeoJSON for future flexibility
- Daily summary model provides SILO-compatible aggregations

---

## 2. API Client: `metno_api.py`

Follow the architecture pattern established in `silo_api.py`.

### MetNoAPI Class Structure

```python
class MetNoAPI:
    """
    Python client for met.no locationforecast API.

    Provides 9-day weather forecasts for any global coordinate.
    """

    BASE_URL = "https://api.met.no/weatherapi/locationforecast/2.0/"
    DEFAULT_TIMEOUT = 30
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0

    def __init__(
        self,
        user_agent: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        enable_cache: bool = True,
        cache_expiry_hours: int = 1,
        debug: bool = False
    ):
        """
        Initialize met.no API client.

        Args:
            user_agent: Custom User-Agent (required by met.no)
            enable_cache: Cache responses (default: True, unlike SILO)
            cache_expiry_hours: Hours before cache expires (default: 1)
        """
```

### Key Methods to Implement

#### `query_forecast()`
```python
def query_forecast(self, query: MetNoQuery) -> MetNoResponse:
    """
    Query met.no forecast API.

    Returns:
        MetNoResponse with raw GeoJSON data

    Raises:
        MetNoAPIError: If request fails
    """
```

#### `get_daily_forecast()`
```python
def get_daily_forecast(
    self,
    latitude: float,
    longitude: float,
    days: int = 7,
    altitude: Optional[int] = None
) -> List[DailyWeatherSummary]:
    """
    Convenience method: Get daily forecast summaries.

    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        days: Number of forecast days (1-9)
        altitude: Optional elevation in meters

    Returns:
        List of daily weather summaries
    """
```

#### `to_dataframe()`
```python
def to_dataframe(
    self,
    response: MetNoResponse,
    aggregate_to_daily: bool = True
) -> pd.DataFrame:
    """
    Convert met.no response to pandas DataFrame.

    Args:
        response: MetNoResponse from API
        aggregate_to_daily: Aggregate hourly data to daily summaries

    Returns:
        DataFrame with weather data
    """
```

#### `_aggregate_to_daily()`
```python
def _aggregate_to_daily(
    self,
    timeseries: List[Dict[str, Any]]
) -> List[DailyWeatherSummary]:
    """
    Aggregate hourly forecasts to daily summaries.

    Logic:
    - Group by date (convert UTC to local time based on coordinates)
    - Min/max temperature from all timestamps
    - Sum precipitation amounts
    - Average wind speed, humidity
    - Most common weather symbol
    """
```

### Daily Aggregation Logic Details

**Temperature:**
- Extract all `air_temperature` values for each date
- Calculate `min_temperature` and `max_temperature`

**Precipitation:**
- Sum all `precipitation_amount` values from period data
- Handle both 1-hour and 6-hour period forecasts
- Avoid double-counting overlapping periods

**Wind:**
- Average `wind_speed` across all timestamps
- Optionally calculate max gust speed

**Weather Symbol:**
- Select most severe or most common symbol for the day
- Priority: thunderstorm > rain > cloudy > clear

**Time Zone Handling:**
- Convert UTC timestamps to local time using coordinates
- Use `pytz` or `timezonefinder` for location-based timezone
- Group forecasts by local calendar date

### Error Handling

```python
class MetNoAPIError(Exception):
    """Met.no API error exception."""
    pass

class MetNoUserAgentError(MetNoAPIError):
    """Raised when User-Agent is missing or invalid."""
    pass

class MetNoRateLimitError(MetNoAPIError):
    """Raised when rate limited."""
    pass
```

### Retry Strategy

- **Transient errors** (timeout, connection): Retry with exponential backoff
- **403 Forbidden**: Likely User-Agent issue, don't retry, raise clear error
- **429 Rate Limit**: Wait and retry with longer delay
- **4xx Client errors**: Don't retry
- **5xx Server errors**: Retry

---

## 3. Variable Mapping: Extend `silo_variables.py`

Add met.no to SILO variable mappings for seamless data integration.

### New Data Structures

#### Met.no Variable Metadata
```python
class MetNoVariableMetadata(BaseModel):
    """Metadata for a met.no forecast variable."""
    metno_name: str  # met.no API name
    units: str
    description: Optional[str] = None
    maps_to_silo: Optional[str] = None  # SILO variable it maps to
```

#### Mapping Dictionaries

```python
# Met.no variables and their SILO equivalents
METNO_TO_SILO_MAPPING = {
    # Direct mappings
    "air_temperature": {
        "silo_min": "min_temp",  # Maps to SILO N variable
        "silo_max": "max_temp",  # Maps to SILO X variable
        "conversion": None,  # No unit conversion needed (both °C)
    },
    "precipitation_amount": {
        "silo": "daily_rain",  # Maps to SILO R variable
        "conversion": None,  # No conversion (both mm)
    },

    # Approximate mappings
    "relative_humidity": {
        "silo": "vp",  # Approximate via humidity-to-vapor pressure
        "conversion": "rh_to_vapor_pressure",
        "requires": ["air_temperature"],
    },

    # New columns (no SILO equivalent)
    "wind_speed": {
        "silo": None,  # Add as new column
        "silo_name": "wind_speed",
    },
    "wind_from_direction": {
        "silo": None,
        "silo_name": "wind_direction",
    },
    "cloud_area_fraction": {
        "silo": None,
        "silo_name": "cloud_fraction",
    },
}

# Variables that have no met.no equivalent
SILO_ONLY_VARIABLES = [
    "evap_pan",  # E - Class A pan evaporation
    "evap_syn",  # S - Synthetic evaporation
    "radiation",  # J - Solar radiation (met.no has UV, not global radiation)
    "vp_deficit",  # D - Vapor pressure deficit
    "mslp",  # M - Mean sea level pressure (met.no has sea level pressure)
]
```

### Conversion Functions

#### Main Conversion Function
```python
def convert_metno_to_silo_format(
    metno_df: pd.DataFrame,
    format: str = "silo",
    include_extra_columns: bool = False
) -> pd.DataFrame:
    """
    Convert met.no DataFrame to SILO-compatible format.

    Args:
        metno_df: DataFrame from met.no API
        format: Output format ("silo", "apsim", "raw")
        include_extra_columns: Include met.no columns with no SILO equivalent

    Returns:
        DataFrame with SILO-compatible column names and values
    """
```

#### Helper Conversions
```python
def rh_to_vapor_pressure(
    relative_humidity: float,
    temperature: float
) -> float:
    """
    Convert relative humidity to vapor pressure.

    Uses August-Roche-Magnus approximation.
    """

def silo_column_order() -> List[str]:
    """Return standard SILO CSV column order."""
    return ["date", "day", "year", "daily_rain", "max_temp", "min_temp", ...]
```

### Format-Specific Outputs

#### SILO Format
- Columns: `date`, `day`, `year`, `daily_rain`, `max_temp`, `min_temp`, etc.
- Date format: YYYYMMDD or YYYY-MM-DD
- Missing SILO variables: Fill with NaN
- Extra met.no columns: Optionally append with `metno_` prefix

#### APSIM Format
- Required columns in specific order
- Header row with site name, lat, lon
- Date format: DD/MM/YYYY
- Units row: `()` for unitless, `(mm)`, `(°C)`
- Missing required columns filled with defaults (e.g., radn = 20)

---

## 4. Data Merging Module: `merge_weather_data.py`

New module dedicated to combining historical SILO data with met.no forecasts.

### Main Merging Function

```python
def merge_historical_and_forecast(
    silo_data: pd.DataFrame,
    metno_data: pd.DataFrame,
    transition_date: Optional[str] = None,
    format: str = "silo",
    validate: bool = True,
    fill_gaps: bool = False
) -> pd.DataFrame:
    """
    Merge SILO historical data with met.no forecast data.

    Args:
        silo_data: Historical data from SILO (API or local)
        metno_data: Forecast data from met.no
        transition_date: Date to switch from SILO to met.no
                        (auto-detect if None: use last SILO date)
        format: Output format ("silo", "apsim")
        validate: Perform validation checks (default: True)
        fill_gaps: Fill missing variables with defaults (default: False)

    Returns:
        Merged DataFrame with 'data_source' column

    Raises:
        MergeValidationError: If data cannot be safely merged
    """
```

### Validation Checks

#### Date Continuity
```python
def validate_date_continuity(
    silo_data: pd.DataFrame,
    metno_data: pd.DataFrame,
    max_gap_days: int = 1
) -> Tuple[bool, List[str]]:
    """
    Check for date gaps between SILO and met.no data.

    Returns:
        (is_valid, list_of_issues)
    """
```

#### Column Compatibility
```python
def validate_column_compatibility(
    silo_data: pd.DataFrame,
    metno_data: pd.DataFrame
) -> Tuple[bool, Dict[str, str]]:
    """
    Check that met.no data has compatible columns.

    Returns:
        (is_valid, mapping_of_issues)
    """
```

#### Overlapping Dates
```python
def handle_overlapping_dates(
    silo_data: pd.DataFrame,
    metno_data: pd.DataFrame,
    strategy: str = "prefer_silo"
) -> pd.DataFrame:
    """
    Handle dates that appear in both datasets.

    Strategies:
    - "prefer_silo": Use SILO data for overlaps
    - "prefer_metno": Use met.no data for overlaps
    - "average": Average the values
    - "error": Raise error on overlap
    """
```

### Metadata Management

```python
def add_data_source_metadata(
    merged_df: pd.DataFrame,
    silo_dates: pd.DatetimeIndex,
    metno_dates: pd.DatetimeIndex,
    forecast_generated_at: datetime
) -> pd.DataFrame:
    """
    Add metadata columns to merged data.

    Adds:
    - 'data_source': 'silo' or 'metno'
    - 'forecast_generated_at': timestamp for met.no rows
    - 'is_forecast': boolean flag
    """
```

### Missing Variable Handling

```python
def fill_missing_variables(
    df: pd.DataFrame,
    variable: str,
    strategy: str = "default"
) -> pd.DataFrame:
    """
    Fill missing variables in merged data.

    Strategies:
    - "default": Use reasonable defaults (e.g., radiation = 20 MJ/m²)
    - "interpolate": Interpolate from surrounding values
    - "nan": Leave as NaN
    """
```

### Custom Exceptions

```python
class MergeValidationError(Exception):
    """Raised when data cannot be safely merged."""
    pass

class DateGapError(MergeValidationError):
    """Raised when there's a gap in dates."""
    pass

class ColumnMismatchError(MergeValidationError):
    """Raised when columns don't align."""
    pass
```

---

## 5. CLI Integration: Extend `cli.py`

Add new `metno` subcommand following the existing pattern.

### CLI Structure

```
weather-tools
├── silo (existing)
│   ├── patched-point
│   ├── data-drill
│   └── search
├── local (existing)
│   ├── extract
│   ├── info
│   └── download
└── metno (new)
    ├── forecast
    ├── merge
    └── info
```

### Command: `metno forecast`

```python
@metno_app.command()
def forecast(
    lat: Annotated[float, typer.Option(help="Latitude coordinate")],
    lon: Annotated[float, typer.Option(help="Longitude coordinate")],
    altitude: Annotated[
        Optional[int],
        typer.Option(help="Elevation in meters above sea level")
    ] = None,
    days: Annotated[
        int,
        typer.Option(help="Number of forecast days (1-9)")
    ] = 7,
    format: Annotated[
        str,
        typer.Option(help="Output format: silo, apsim, raw")
    ] = "silo",
    output: Annotated[
        str,
        typer.Option(help="Output CSV filename")
    ] = "forecast.csv",
    include_extra: Annotated[
        bool,
        typer.Option(help="Include met.no variables with no SILO equivalent")
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(help="Print API URL for debugging")
    ] = False
) -> None:
    """
    Get weather forecast from met.no API.

    Example:
        weather-tools metno forecast --lat -27.5 --lon 153.0 \\
            --days 7 --format silo --output forecast.csv
    """
```

**Implementation steps:**
1. Create `MetNoQuery` from coordinates
2. Query met.no API via `MetNoAPI.get_daily_forecast()`
3. Convert to DataFrame
4. Apply format conversion (SILO/APSIM)
5. Write to output file
6. Display preview and summary

### Command: `metno merge`

```python
@metno_app.command()
def merge(
    lat: Annotated[float, typer.Option(help="Latitude coordinate")],
    lon: Annotated[float, typer.Option(help="Longitude coordinate")],
    start_date: Annotated[
        str,
        typer.Option(help="Historical data start date (YYYY-MM-DD)")
    ],
    forecast_days: Annotated[
        int,
        typer.Option(help="Number of forecast days to append (1-9)")
    ] = 7,
    format: Annotated[
        str,
        typer.Option(help="Output format: silo, apsim")
    ] = "silo",
    silo_source: Annotated[
        str,
        typer.Option(help="SILO data source: api or local")
    ] = "local",
    silo_dir: Annotated[
        Optional[Path],
        typer.Option(help="Path to SILO data directory (for local source)")
    ] = None,
    output: Annotated[
        str,
        typer.Option(help="Output filename for merged data")
    ] = "merged_weather.csv",
    variables: Annotated[
        Optional[List[str]],
        typer.Option(
            "--var",
            help="Variables to include (default: daily preset)"
        )
    ] = None,
    no_validate: Annotated[
        bool,
        typer.Option(help="Skip validation checks")
    ] = False,
    fill_gaps: Annotated[
        bool,
        typer.Option(help="Fill missing variables with defaults")
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(help="Print debug information")
    ] = False
) -> None:
    """
    Merge SILO historical data with met.no forecast.

    This command:
    1. Fetches SILO historical data (from local files or API)
    2. Fetches met.no forecast data
    3. Validates and merges the datasets
    4. Outputs combined data in specified format

    Examples:
        # Merge local SILO data with met.no forecast
        weather-tools metno merge --lat -27.5 --lon 153.0 \\
            --start-date 2020-01-01 --forecast-days 7 \\
            --output merged.csv

        # Use SILO API instead of local files
        weather-tools metno merge --lat -27.5 --lon 153.0 \\
            --start-date 2023-01-01 --silo-source api \\
            --output merged.csv

        # Output in APSIM format
        weather-tools metno merge --lat -27.5 --lon 153.0 \\
            --start-date 2023-01-01 --format apsim \\
            --output weather.met
    """
```

**Implementation steps:**
1. Get SILO historical data:
   - If `silo_source == "local"`: Use `read_silo_xarray()`
   - If `silo_source == "api"`: Use `SiloAPI.get_gridded_data()`
2. Extract data for specified lat/lon (if local) and date range
3. Get met.no forecast via `MetNoAPI.get_daily_forecast()`
4. Convert met.no data to SILO format
5. Call `merge_historical_and_forecast()`
6. Handle validation errors with clear messages
7. Write merged data to output
8. Display summary: X days from SILO, Y days from met.no

### Command: `metno info`

```python
@metno_app.command()
def info() -> None:
    """
    Display met.no API information and variable mappings.

    Shows:
    - API status and version
    - Available forecast variables
    - Variable mapping table (met.no → SILO)
    - Coverage information
    """
```

**Implementation:**
1. Query met.no status endpoint
2. Display API health and version
3. Show variable mapping table using Rich tables
4. Display forecast duration (9 days)
5. Show geographic coverage (global)

### CLI Helper Functions

```python
def format_merge_summary(
    merged_df: pd.DataFrame,
    silo_count: int,
    metno_count: int
) -> str:
    """Create rich summary output for merged data."""

def validate_coordinates_in_australia(
    lat: float,
    lon: float
) -> bool:
    """Check if coordinates are in Australia (for SILO compatibility)."""

def auto_detect_format_from_filename(
    filename: str
) -> str:
    """Auto-detect format from file extension."""
```

---

## 6. Testing Strategy

Follow existing pytest patterns in the codebase.

### Test File Structure

```
tests/
├── test_metno_models.py           # Pydantic model validation
├── test_metno_api.py              # API client with mocked responses
├── test_metno_variables.py        # Variable mapping and conversion
├── test_merge_weather_data.py     # Data merging logic
├── test_metno_cli.py              # CLI command testing
└── fixtures/
    ├── metno_response_compact.json
    ├── metno_response_complete.json
    └── sample_silo_data.csv
```

### Unit Tests: `test_metno_models.py`

```python
def test_metno_coordinates_valid():
    """Test valid coordinate creation."""

def test_metno_coordinates_invalid_latitude():
    """Test latitude validation (must be -90 to 90)."""

def test_metno_coordinates_invalid_longitude():
    """Test longitude validation (must be -180 to 180)."""

def test_metno_query_to_api_params():
    """Test conversion to API parameters."""

def test_metno_response_get_timeseries():
    """Test timeseries extraction from GeoJSON."""

def test_daily_weather_summary_creation():
    """Test daily summary model creation."""
```

### Unit Tests: `test_metno_api.py`

```python
@pytest.fixture
def mock_metno_response():
    """Load fixture JSON for met.no response."""
    with open("tests/fixtures/metno_response_compact.json") as f:
        return json.load(f)

def test_api_initialization():
    """Test API client initialization with User-Agent."""

def test_api_missing_user_agent_error():
    """Test error when User-Agent is missing."""

def test_query_forecast_success(mock_metno_response, requests_mock):
    """Test successful forecast query."""

def test_query_forecast_403_error(requests_mock):
    """Test 403 Forbidden (User-Agent issue)."""

def test_aggregate_to_daily():
    """Test hourly to daily aggregation logic."""

def test_aggregate_precipitation_no_double_count():
    """Ensure precipitation isn't double-counted."""

def test_to_dataframe():
    """Test conversion to pandas DataFrame."""
```

### Unit Tests: `test_metno_variables.py`

```python
def test_convert_metno_to_silo_format():
    """Test conversion from met.no to SILO format."""

def test_rh_to_vapor_pressure():
    """Test relative humidity to vapor pressure conversion."""

def test_silo_column_order():
    """Test SILO column ordering."""

def test_apsim_format_conversion():
    """Test conversion to APSIM format."""

def test_handle_missing_variables():
    """Test handling of variables with no SILO equivalent."""
```

### Unit Tests: `test_merge_weather_data.py`

```python
@pytest.fixture
def sample_silo_data():
    """Create sample SILO DataFrame."""
    return pd.DataFrame({
        "date": pd.date_range("2023-01-01", "2023-01-31"),
        "daily_rain": np.random.rand(31) * 10,
        "max_temp": np.random.rand(31) * 10 + 25,
        "min_temp": np.random.rand(31) * 10 + 15,
    })

@pytest.fixture
def sample_metno_data():
    """Create sample met.no DataFrame."""
    return pd.DataFrame({
        "date": pd.date_range("2023-02-01", "2023-02-07"),
        "daily_rain": np.random.rand(7) * 10,
        "max_temp": np.random.rand(7) * 10 + 25,
        "min_temp": np.random.rand(7) * 10 + 15,
    })

def test_merge_continuous_dates(sample_silo_data, sample_metno_data):
    """Test merging with continuous dates."""

def test_merge_with_gap_raises_error():
    """Test that date gaps raise validation error."""

def test_merge_with_overlap_prefer_silo():
    """Test overlap handling with prefer_silo strategy."""

def test_validate_date_continuity():
    """Test date continuity validation."""

def test_validate_column_compatibility():
    """Test column compatibility checking."""

def test_add_data_source_metadata():
    """Test metadata column addition."""

def test_fill_missing_variables():
    """Test filling missing variables with defaults."""
```

### Unit Tests: `test_metno_cli.py`

```python
from typer.testing import CliRunner

runner = CliRunner()

def test_forecast_command_basic():
    """Test basic forecast command."""
    result = runner.invoke(app, [
        "metno", "forecast",
        "--lat", "-27.5",
        "--lon", "153.0",
        "--days", "7",
        "--output", "test_forecast.csv"
    ])
    assert result.exit_code == 0

def test_forecast_command_invalid_coordinates():
    """Test forecast with invalid coordinates."""

def test_merge_command_local_silo():
    """Test merge command with local SILO data."""

def test_merge_command_api_silo():
    """Test merge command with SILO API."""

def test_merge_command_validation_error():
    """Test merge command with data that fails validation."""

def test_info_command():
    """Test info command output."""
```

### Integration Tests

Mark with `@pytest.mark.integration` and skip if no internet:

```python
@pytest.mark.integration
def test_real_metno_api_query():
    """Test real met.no API query (requires internet)."""

@pytest.mark.integration
def test_end_to_end_merge_local_silo_metno():
    """Test complete workflow: local SILO + met.no → merged output."""

@pytest.mark.integration
def test_end_to_end_merge_api_silo_metno():
    """Test complete workflow: SILO API + met.no → merged output."""
```

### Test Configuration

In `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
    "slow: marks tests as slow (deselect with '-m \"not slow\"')"
]
```

---

## 7. Implementation Order

Recommended phased development approach:

### Phase 1: Core Models (1-2 days)

**Tasks:**
- [ ] Create `src/weather_tools/metno_models.py`
- [ ] Implement all Pydantic models
- [ ] Create `tests/test_metno_models.py`
- [ ] Write unit tests for all models
- [ ] Verify validation logic works correctly

**Deliverable:** Type-safe models with full test coverage

### Phase 2: API Client (2-3 days)

**Tasks:**
- [ ] Create `src/weather_tools/metno_api.py`
- [ ] Implement `MetNoAPI` class
- [ ] Add User-Agent handling
- [ ] Implement retry logic
- [ ] Implement daily aggregation logic
- [ ] Create test fixtures (JSON responses)
- [ ] Create `tests/test_metno_api.py`
- [ ] Write unit tests with mocked responses
- [ ] Write integration test for real API call

**Deliverable:** Working API client with caching and error handling

### Phase 3: Variable Mapping (1-2 days)

**Tasks:**
- [ ] Extend `src/weather_tools/silo_variables.py`
- [ ] Add met.no variable metadata
- [ ] Create mapping dictionaries
- [ ] Implement conversion functions
- [ ] Create `tests/test_metno_variables.py`
- [ ] Test all conversions
- [ ] Verify SILO format output matches expected structure
- [ ] Verify APSIM format output matches expected structure

**Deliverable:** Variable conversion functions with test coverage

### Phase 4: Data Merging (2-3 days)

**Tasks:**
- [ ] Create `src/weather_tools/merge_weather_data.py`
- [ ] Implement merge function
- [ ] Implement validation functions
- [ ] Implement metadata management
- [ ] Create custom exceptions
- [ ] Create `tests/test_merge_weather_data.py`
- [ ] Test all validation scenarios
- [ ] Test edge cases (gaps, overlaps, mismatches)
- [ ] Test missing variable handling

**Deliverable:** Robust merging logic with comprehensive validation

### Phase 5: CLI Integration (2-3 days)

**Tasks:**
- [ ] Extend `src/weather_tools/cli.py`
- [ ] Create `metno_app` subcommand
- [ ] Implement `forecast` command
- [ ] Implement `merge` command
- [ ] Implement `info` command
- [ ] Add format auto-detection
- [ ] Create `tests/test_metno_cli.py`
- [ ] Test all CLI commands
- [ ] Test error handling and validation messages
- [ ] Write integration test for full workflow

**Deliverable:** Complete CLI interface with full functionality

### Phase 6: Documentation & Polish (1-2 days)

**Tasks:**
- [ ] Update `README.md` with met.no examples
- [ ] Update `CLAUDE.md` with met.no patterns
- [ ] Add docstrings to all public functions
- [ ] Create usage examples for common workflows
- [ ] Add type hints to all functions
- [ ] Run `ruff` linter and fix issues
- [ ] Run `pytest` with coverage report
- [ ] Create example Jupyter notebook (optional)

**Deliverable:** Production-ready feature with complete documentation

**Total estimated time: 9-15 days**

---

## 8. Key Design Decisions

### Date Handling

**Challenge:** SILO uses YYYYMMDD format, met.no uses ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)

**Solution:**
- Standardize internally to pandas datetime objects
- Convert to appropriate format on output
- Store timezone info with met.no data
- For merging, use local calendar dates (not UTC)

### Time Zone Conversion

**Challenge:** met.no returns UTC, SILO varies by Australian location

**Solution:**
- Use `timezonefinder` to get timezone from coordinates
- Convert met.no UTC timestamps to local time
- Group forecasts by local calendar date for daily aggregation
- Store timezone info in metadata

### Transition Date Handling

**Challenge:** Determining where to split historical vs forecast

**Solution:**
- Auto-detect: Use last available SILO date
- Manual: Allow user to specify transition date
- Validate: Ensure no gaps between datasets
- Handle overlap: Prefer SILO historical over met.no "forecast" of past

### Missing Variables

**Challenge:** Met.no doesn't provide all SILO variables (e.g., evapotranspiration)

**Solution:**
- Document which variables are unavailable
- Provide `--fill-gaps` option with reasonable defaults
- Add `is_forecast` flag so users can identify forecast rows
- Consider using simple models to estimate missing variables (e.g., Penman-Monteith for ET)

### Precipitation Aggregation

**Challenge:** Met.no provides precipitation for multiple time periods (1h, 6h, 12h)

**Solution:**
- Use shortest available period (1h) preferentially
- For longer periods, distribute evenly across hours
- Avoid double-counting by tracking which hours are covered
- Sum to daily total carefully

### Cache Management

**Challenge:** Forecasts change over time, need to balance caching vs freshness

**Solution:**
- Default cache expiry: 1 hour
- Store cache key with timestamp
- Allow manual cache clearing
- Consider HTTP caching headers (ETag, Last-Modified) for efficiency

### Coordinate Validation

**Challenge:** met.no is global, SILO is Australia-only

**Solution:**
- `MetNoCoordinates` allows global coordinates
- Warn user if coordinates are outside Australia when using merge
- For merge command, validate coordinates are within SILO coverage
- Allow override with `--force-global` flag

### Error Messaging

**Principle:** Clear, actionable error messages

**Examples:**
- ❌ "Validation error" → ✅ "Date gap detected: SILO data ends on 2023-01-31, met.no starts on 2023-02-05. Missing 4 days."
- ❌ "403 error" → ✅ "Met.no API returned 403 Forbidden. This usually means User-Agent header is invalid. Ensure you're using weather-tools version X.Y.Z."
- ❌ "Column mismatch" → ✅ "Missing columns in met.no data: ['radiation', 'evap_pan']. Use --fill-gaps to use default values."

---

## 9. API Constraints & Considerations

### Rate Limiting

**Met.no policy:** No explicit rate limits documented, but they request "responsible use"

**Implementation:**
- Add 1 second delay between requests (default)
- Implement exponential backoff on errors
- Cache responses to minimize requests
- Consider batch processing for multiple locations

### User-Agent Requirement

**Met.no requirement:** Custom User-Agent header is mandatory

**Implementation:**
```python
USER_AGENT = f"weather-tools/{__version__} (https://github.com/user/weather-tools) Python/{sys.version_info.major}.{sys.version_info.minor}"
```

**Banned User-Agents:** okhttp, Dalvik, fhttp, Java (as of documentation)

### Forecast Duration

**Constraint:** Met.no provides 9-day forecasts

**Handling:**
- Validate `days` parameter ≤ 9
- Clear error message if user requests > 9 days
- Document accuracy decreases after day 3-4

### Geographic Coverage

**Coverage:** Global, but optimized for Nordic region

**Consideration:**
- Quality may vary by location
- Consider adding data quality indicators
- Document that accuracy may differ from SILO quality

### Data Update Frequency

**Met.no updates:** Approximately every 6 hours (4 times per day)

**Implications:**
- Cache should expire appropriately (1-2 hours)
- Users may want to re-fetch for updated forecasts
- Consider adding `--force-refresh` flag

### API Stability

**Version:** Currently at v2.0

**Preparation:**
- Version API endpoint in code
- Monitor for deprecation notices
- Handle version transitions gracefully

---

## 10. Future Enhancements

Ideas for future iterations (out of scope for initial implementation):

### Hourly Forecast Support
- Add `--hourly` flag to get hourly data instead of daily
- Useful for sub-daily modeling

### Ensemble Forecasts
- Use `/complete` endpoint for percentile data
- Provide uncertainty estimates (P10, P90)
- Useful for risk analysis

### Weather Symbol Interpretation
- Parse weather symbols into human-readable descriptions
- Map to weather icons for visualization
- Group into categories (clear, cloudy, rainy, stormy)

### Multi-Location Batch Processing
- Process multiple locations in one command
- Parallel API requests for efficiency
- Output to multiple files or single multi-location file

### Automatic Data Refresh
- Daemon mode to keep forecasts updated
- Scheduled re-fetching
- Notification on significant forecast changes

### Data Quality Indicators
- Add confidence scores based on forecast age
- Flag low-quality data
- Compare forecast vs actual (when available)

### Integration with Other APIs
- BOM (Australian Bureau of Meteorology) API
- ECMWF (European Centre for Medium-Range Weather Forecasts)
- DarkSky-style API for longer forecasts

### Visualization
- Generate weather charts
- Compare historical vs forecast
- Plot uncertainty ranges

### Machine Learning Features
- Bias correction for met.no forecasts using SILO historical
- Extend forecast beyond 9 days using statistical models
- Downscaling to higher spatial resolution

---

## 11. Documentation Checklist

Before considering implementation complete:

- [ ] README.md updated with met.no examples
- [ ] CLAUDE.md updated with met.no architecture patterns
- [ ] All public functions have docstrings (Google style)
- [ ] Type hints on all function signatures
- [ ] CLI help text is clear and comprehensive
- [ ] Example notebooks created (optional but recommended)
- [ ] Variable mapping table documented
- [ ] Known limitations documented
- [ ] Contributing guidelines updated (if applicable)
- [ ] CHANGELOG.md updated with new features

---

## 12. Success Criteria

Implementation is complete when:

1. **All tests pass** with >70% coverage
2. **CLI works end-to-end:**
   - Can fetch met.no forecast and save to file
   - Can merge SILO + met.no successfully
   - Error messages are clear and actionable
3. **Data quality:**
   - SILO format output matches existing SILO structure
   - APSIM format output is valid
   - Merged data has no gaps or overlaps
4. **Code quality:**
   - Passes `ruff format` and `ruff check`
   - Follows existing codebase patterns
   - Documented with docstrings
5. **User experience:**
   - Commands are intuitive for existing users
   - Error messages are helpful
   - Default options are sensible

---

## Appendices

### A. Met.no API Reference Links

- Documentation: https://api.met.no/weatherapi/locationforecast/2.0/documentation
- OpenAPI Spec: https://api.met.no/weatherapi/locationforecast/2.0/swagger
- Status Endpoint: https://api.met.no/weatherapi/locationforecast/2.0/status
- Terms of Service: https://api.met.no/doc/TermsOfService

### B. SILO Format Specification

Standard SILO CSV format:
```
date,day,year,daily_rain,max_temp,min_temp,vp,evap_pan,evap_syn,evap_comb,evap_morton_lake,radiation,rh_tmax,rh_tmin,et_short_crop,et_tall_crop,et_morton_actual,et_morton_potential,et_morton_wet,mslp
20230101,1,2023,5.2,28.3,18.7,18.5,6.5,5.8,5.9,6.2,25.3,65,88,4.8,5.2,3.8,5.1,5.3,1013.2
```

### C. APSIM Format Specification

APSIM .met file format:
```
[weather.met.weather]
Latitude = -27.5
Longitude = 153.0
tav = 22.5
amp = 8.2

year  day  radn  maxt  mint  rain  evap  vp
()    ()   (MJ/m^2) (°C)  (°C)  (mm)  (mm)  (hPa)
2023  1    25.3  28.3  18.7  5.2   5.8   18.5
```

### D. Variable Mapping Table

| Met.no Variable | Units | SILO Variable | SILO Code | Conversion | Notes |
|---|---|---|---|---|---|
| air_temperature (min) | °C | min_temp | N | None | Direct mapping |
| air_temperature (max) | °C | max_temp | X | None | Direct mapping |
| precipitation_amount | mm | daily_rain | R | None | Direct mapping |
| relative_humidity | % | vp | V | RH → VP | Requires temperature |
| wind_speed | m/s | (new) | - | None | No SILO equivalent |
| cloud_area_fraction | % | (new) | - | None | No SILO equivalent |

### E. Example Workflows

**Workflow 1: Get 7-day forecast**
```bash
weather-tools metno forecast \
  --lat -27.5 --lon 153.0 \
  --days 7 \
  --output forecast.csv
```

**Workflow 2: Merge local SILO with forecast**
```bash
# Step 1: Ensure local SILO data is available
weather-tools local info

# Step 2: Merge historical + forecast
weather-tools metno merge \
  --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 \
  --forecast-days 7 \
  --output merged_weather.csv

# Step 3: Verify output
head merged_weather.csv
```

**Workflow 3: Use SILO API + met.no for recent location**
```bash
export SILO_API_KEY="your.email@example.com"

weather-tools metno merge \
  --lat -35.5 --lon 149.0 \
  --start-date 2023-01-01 \
  --silo-source api \
  --forecast-days 7 \
  --format apsim \
  --output weather.met
```

---

## Revision History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-01-22 | 1.0 | Initial comprehensive plan | Claude |

