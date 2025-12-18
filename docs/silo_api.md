# SILO API Module

The `silo_api` module provides a Python interface for querying the [SILO (Scientific Information for Land Owners)](https://www.longpaddock.qld.gov.au/silo/) API directly, allowing you to fetch weather data without downloading large netCDF files.

## Features

- ✅ **Two dataset types**: PatchedPoint (station-based) and DataDrill (gridded)
- ✅ **Multiple formats**: CSV, APSIM, and near-station search
- ✅ **Automatic retry logic** with exponential backoff
- ✅ **Response caching** to reduce redundant API calls
- ✅ **Date validation** ensures correct YYYYMMDD format
- ✅ **Configurable timeouts** and retry behavior
- ✅ **Comprehensive logging** for debugging and monitoring

## Installation

The SILO API module is included with the weather_tools package:

```bash
pip install weather-tools
```

## Quick Start

### Basic Usage

```python
from weather_tools.silo_api import SiloAPI, SiloAPIError

# Initialize the API client
api = SiloAPI(api_key="your_silo_api_key")

try:
    # Query PatchedPoint data for a station
    result = api.query(
        dataset="PatchedPoint",
        format="csv",
        station_code="30043",
        start_date="20230101",
        end_date="20230131",
        values=["rain", "maxtemp", "mintemp"]
    )
    print(result)
except SiloAPIError as e:
    print(f"API Error: {e}")
```

### DataDrill (Gridded Data)

```python
# Query DataDrill data for specific coordinates
result = api.query(
    dataset="DataDrill",
    format="csv",
    longitude=151.0,
    latitude=-27.5,
    start_date="20230101",
    end_date="20230131",
    values=["rain", "maxtemp", "mintemp"]
)
```

## Configuration Options

### Initialize with Custom Settings

```python
from weather_tools.silo_api import SiloAPI

api = SiloAPI(
    api_key="your_api_key",
    timeout=60,              # Request timeout in seconds (default: 30)
    max_retries=5,           # Maximum retry attempts (default: 3)
    retry_delay=2.0,         # Base delay between retries (default: 1.0)
    enable_cache=True        # Enable response caching (default: False)
)
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | str | Required | Your SILO API key |
| `timeout` | float | 30 | Request timeout in seconds |
| `max_retries` | int | 3 | Maximum number of retry attempts |
| `retry_delay` | float | 1.0 | Base delay between retries (exponential backoff) |
| `enable_cache` | bool | False | Enable response caching |

## API Methods

### query()

Main method for querying the SILO API.

```python
result = api.query(
    dataset: str,
    format: str = "csv",
    station_code: Optional[str] = None,
    longitude: Optional[float] = None,
    latitude: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    values: Optional[List[str]] = None,
    radius: Optional[float] = None
) -> Union[str, Dict[str, Any]]
```

**Parameters:**

- `dataset`: 'PatchedPoint' or 'DataDrill'
- `format`: 'csv', 'apsim', or 'near'
- `station_code`: SILO station code (required for PatchedPoint)
- `longitude`, `latitude`: Location coordinates (required for DataDrill)
- `start_date`, `end_date`: Date range in YYYYMMDD format
- `values`: List of weather variables to request
- `radius`: Search radius for 'near' format

**Returns:**
- CSV/APSIM data as string
- JSON data as dictionary (for non-standard formats)

**Raises:**
- `ValueError`: For invalid parameters
- `SiloAPIError`: For API request failures

### Cache Management

```python
# Get number of cached responses
cache_size = api.get_cache_size()

# Clear the cache
api.clear_cache()
```

## Datasets and Formats

### PatchedPoint Dataset

Station-based data with quality-controlled observations.

**Supported Formats:**
- `csv`: Comma-separated values
- `apsim`: APSIM format
- `near`: Find nearby stations

**Example:**
```python
# CSV format
result = api.query(
    dataset="PatchedPoint",
    format="csv",
    station_code="30043",
    start_date="20230101",
    end_date="20230131",
    values=["rain", "maxtemp", "mintemp"]
)

# APSIM format
result = api.query(
    dataset="PatchedPoint",
    format="apsim",
    station_code="30043",
    start_date="20230101",
    end_date="20230131"
)

# Find nearby stations
result = api.query(
    dataset="PatchedPoint",
    format="near",
    station_code="30043",
    radius=50.0  # Search radius in km
)
```

### DataDrill Dataset

Gridded data interpolated to specific coordinates.

**Supported Formats:**
- `csv`: Comma-separated values
- `apsim`: APSIM format

**Example:**
```python
result = api.query(
    dataset="DataDrill",
    format="csv",
    longitude=151.0,
    latitude=-27.5,
    start_date="20230101",
    end_date="20230131",
    values=["rain", "maxtemp", "mintemp"]
)
```

## Weather Variables

Common weather variables available from SILO:

- `rain`: Daily rainfall (mm)
- `maxtemp`: Maximum temperature (°C)
- `mintemp`: Minimum temperature (°C)
- `vp`: Vapor pressure (hPa)
- `evap_pan`: Class A pan evaporation (mm)
- `evap_syn`: Synthetic estimate of evaporation (mm)
- `evap_comb`: Combination of measured and synthetic evaporation (mm)
- `radiation`: Solar radiation (MJ/m²)
- `rh_tmax`: Relative humidity at time of maximum temperature (%)
- `rh_tmin`: Relative humidity at time of minimum temperature (%)

## Error Handling

### Exception Types

**SiloAPIError**: Raised for API-related errors

```python
from weather_tools.silo_api import SiloAPI, SiloAPIError

try:
    result = api.query(...)
except SiloAPIError as e:
    print(f"API Error: {e}")
```

**ValueError**: Raised for invalid input parameters

```python
try:
    result = api.query(
        dataset="InvalidDataset",
        format="csv"
    )
except ValueError as e:
    print(f"Invalid parameter: {e}")
```

### Common Errors

**HTTP Errors (4xx, 5xx):**
```
SiloAPIError: HTTP 404: Not Found
```

**SILO-Specific Errors:**
```
SiloAPIError: Sorry, your request was rejected
```

**Timeout Errors (after retries):**
```
SiloAPIError: Request failed after 3 attempts: Connection timeout
```

**Invalid Dataset:**
```
ValueError: Unknown dataset: InvalidDataset. Valid datasets: ['PatchedPoint', 'DataDrill']
```

**Invalid Date Format:**
```
ValueError: start_date must be in YYYYMMDD format (e.g., '20230101'), got: 2023-01-01
```

**Missing Required Parameters:**
```
ValueError: station_code is required for PatchedPoint queries
ValueError: longitude and latitude are required for DataDrill queries
```

## Advanced Features

### Response Caching

Enable caching to avoid redundant API calls:

```python
import logging

# Configure logging to see cache activity
logging.basicConfig(level=logging.INFO)

# Create API with caching enabled
api = SiloAPI(api_key="your_key", enable_cache=True)

# First query - hits the API
result1 = api.query(
    dataset="PatchedPoint",
    station_code="30043",
    start_date="20230101",
    end_date="20230131",
    values=["rain"]
)

# Second identical query - uses cache
result2 = api.query(
    dataset="PatchedPoint",
    station_code="30043",
    start_date="20230101",
    end_date="20230131",
    values=["rain"]
)

print(f"Cache size: {api.get_cache_size()}")  # Output: 1
print(f"Results identical: {result1 == result2}")  # Output: True

# Clear cache when done
api.clear_cache()
```

### Automatic Retries

The API automatically retries on transient failures:

```python
api = SiloAPI(
    api_key="your_key",
    max_retries=5,      # Retry up to 5 times
    retry_delay=2.0     # 2 second base delay (with exponential backoff)
)

# API will automatically retry on:
# - Connection timeouts
# - Connection errors
# But NOT on:
# - HTTP 4xx/5xx errors
# - SILO-specific rejection messages
```

### Logging and Debugging

Enable detailed logging to monitor API activity:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Show all logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

api = SiloAPI(api_key="your_key")

# You'll see detailed logs:
# - Request attempts
# - Cache hits/misses
# - Retry attempts
# - Success/failure messages
```

### Production Configuration

Recommended settings for production use:

```python
import os
import logging

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,  # Only info and above
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load API key from environment variable
api_key = os.getenv("SILO_API_KEY")

if not api_key:
    raise ValueError("SILO_API_KEY environment variable not set")

# Create production-ready API client
api = SiloAPI(
    api_key=api_key,
    timeout=60,              # Generous timeout
    max_retries=5,           # More retries for reliability
    retry_delay=2.0,         # Longer delays between retries
    enable_cache=True        # Enable caching
)

try:
    result = api.query(...)
    logging.info(f"Query successful, cache size: {api.get_cache_size()}")
except SiloAPIError as e:
    logging.error(f"API error: {e}")
    # Handle error appropriately
```

## CLI Usage

The SILO API functionality is also available via the command-line interface:

```bash
# Query PatchedPoint data
weather-tools silo patched-point --station 30043 \
    --start-date 2023-01-01 --end-date 2023-01-31 \
    --var rainfall --var max_temp --var min_temp --output silo_data.csv

# Query DataDrill data
weather-tools silo data-drill --latitude -27.5 --longitude 151.0 \
    --start-date 2023-01-01 --end-date 2023-01-31 \
    --var rainfall --var max_temp --output silo_data.csv

# Find nearby stations
weather-tools silo search --station 30043 --radius 50
```

See the [CLI Reference](cli.md) for more details.

## Getting Your API Key

To use the SILO API, you need to obtain an API key:

1. Visit the [SILO website](https://www.longpaddock.qld.gov.au/silo/)
2. Register for API access
3. Store your API key securely (use environment variables)

**Security Note:** Never hardcode your API key in your source code. Use environment variables or secure configuration files:

```python
import os

# Load from environment variable
api_key = os.getenv("SILO_API_KEY")

# Or use python-dotenv
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("SILO_API_KEY")
```

## Best Practices

1. **Use environment variables for API keys**
   ```python
   api_key = os.getenv("SILO_API_KEY")
   ```

2. **Enable caching for repeated queries**
   ```python
   api = SiloAPI(api_key=key, enable_cache=True)
   ```

3. **Set appropriate timeouts**
   ```python
   # Short timeout for quick checks
   api = SiloAPI(api_key=key, timeout=10)
   
   # Longer timeout for large data downloads
   api = SiloAPI(api_key=key, timeout=120)
   ```

4. **Handle exceptions appropriately**
   ```python
   try:
       result = api.query(...)
   except ValueError as e:
       # Handle input validation errors
       logger.error(f"Invalid input: {e}")
   except SiloAPIError as e:
       # Handle API errors
       logger.error(f"API error: {e}")
   ```

5. **Use logging in production**
   ```python
   import logging
   logging.basicConfig(
       level=logging.WARNING,  # Only warnings and errors
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
   )
   ```

## Data Models

The weather_tools package provides Pydantic models for structured API queries:

### PatchedPointQuery

Model for PatchedPoint dataset queries:

```python
from weather_tools import PatchedPointQuery

query = PatchedPointQuery(
    station="30043",
    start_date="20230101",
    end_date="20230131",
    variables=["R", "X", "N"],  # Rain, Max temp, Min temp
    format="csv"
)
```

### DataDrillQuery  

Model for DataDrill dataset queries:

```python
from weather_tools import DataDrillQuery

query = DataDrillQuery(
    lat=-27.5,
    lon=153.0,
    start_date="20230101", 
    end_date="20230131",
    variables=["R", "X", "N"],
    format="csv"
)
```

### Other Models

- **`ClimateVariable`**: Enum for valid climate variable codes
- **`SiloFormat`**: Enum for output formats (csv, json, apsim, standard)
- **`SiloDataset`**: Enum for dataset types (PatchedPoint, DataDrill)
- **`AustralianCoordinates`**: Validator for Australian lat/lon coordinates
- **`SiloDateRange`**: Validator for SILO date format (YYYYMMDD)
- **`SiloResponse`**: Response wrapper with metadata

These models provide validation, type hints, and automatic parameter generation for SILO API requests.

## See Also

- [CLI Reference](cli.md) - Command-line interface documentation
- [API Reference](api_docs/read_silo.md) - Local netCDF file reading
- [Examples](notebooks/example.ipynb) - Jupyter notebook examples
