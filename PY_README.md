# Weather Tools Python API

Comprehensive guide to using `weather_tools` as a Python library for accessing and processing Australian SILO climate data.

## Installation

```bash
# Install from GitHub using uv
uv pip install git+https://github.com/harryeslick/weather_tools.git

# Or with pip
pip install git+https://github.com/harryeslick/weather_tools.git
```

## Table of Contents

- [SILO API Client](#silo-api-client)
  - [Quick Start](#quick-start)
  - [Station Data (PatchedPoint)](#station-data-patchedpoint)
  - [Gridded Data (DataDrill)](#gridded-data-datadrill)
  - [Station Search](#station-search)
  - [Recent Data](#recent-data)
- [Local NetCDF Files](#local-netcdf-files)
  - [Downloading Data](#downloading-data)
  - [Loading Data](#loading-data)
  - [Extracting Timeseries](#extracting-timeseries)
- [Cloud-Optimized GeoTIFF (COG)](#cloud-optimized-geotiff-cog)
  - [Streaming Data](#streaming-data)
  - [Point Queries](#point-queries)
  - [Polygon Queries](#polygon-queries)
  - [Downloading with Clipping](#downloading-with-clipping)
- [Met.no Weather Forecasts](#metno-weather-forecasts)
  - [Getting Forecasts](#getting-forecasts)
  - [Merging with SILO Historical Data](#merging-with-silo-historical-data)

---

## SILO API Client

The SILO API provides access to two datasets:
- **PatchedPoint**: Station-based observational data with infilled gaps
- **DataDrill**: Gridded data at 0.05° resolution (~5km)

### Quick Start

```python
import os
from weather_tools.silo_api import SiloAPI

# Set API key (your email address)
os.environ["SILO_API_KEY"] = "your.email@example.com"

# Initialize client
api = SiloAPI()  # Reads SILO_API_KEY from environment

# Or pass API key directly
api = SiloAPI(api_key="your.email@example.com")
```

### Station Data (PatchedPoint)

Get weather data from Bureau of Meteorology stations.

#### High-Level API (Recommended)

Simple interface that returns pandas DataFrames:

```python
# Get station data as DataFrame
df = api.get_station_data(
    station_code="30043",  # Brisbane Aero
    start_date="20230101",
    end_date="20230131",
    variables=["rainfall", "max_temp", "min_temp"]
)

print(df.head())
#         date  daily_rain  max_temp  min_temp
# 0 2023-01-01        12.4      29.1      21.3
# 1 2023-01-02         0.0      31.2      22.1
# ...

# Get all available variables
df_all = api.get_station_data(
    station_code="30043",
    start_date="20230101",
    end_date="20230131"
    # variables=None gets all variables
)

# Return with metadata
df, metadata = api.get_station_data(
    station_code="30043",
    start_date="20230101",
    end_date="20230131",
    return_metadata=True
)
print(metadata)
# {'station_code': '30043', 'date_range': {...}, 'variables': [...]}
```

**Available Variables:**
- `"rainfall"` - Daily rainfall (mm)
- `"max_temp"` - Maximum temperature (°C)
- `"min_temp"` - Minimum temperature (°C)
- `"evaporation"` - Class A pan evaporation (mm)
- `"radiation"` - Solar radiation (MJ/m²)
- `"vapour_pressure"` - Vapour pressure (hPa)
- `"max_rh"` - Relative humidity at max temp (%)
- `"min_rh"` - Relative humidity at min temp (%)

#### Low-Level API (Type-Safe)

Type-safe interface using Pydantic models with validation:

```python
from weather_tools.silo_models import (
    PatchedPointQuery,
    SiloDateRange,
    ClimateVariable,
    SiloFormat
)

# Build query with validation
query = PatchedPointQuery(
    station_code="30043",
    format=SiloFormat.CSV,
    date_range=SiloDateRange(
        start_date="20230101",
        end_date="20230131"
    ),
    values=[
        ClimateVariable.RAINFALL,
        ClimateVariable.MAX_TEMP,
        ClimateVariable.MIN_TEMP
    ]
)

# Execute query
response = api.query_patched_point(query)

# Access raw data
print(response.raw_data)  # CSV string

# Convert to different formats
print(response.to_csv())   # CSV string
print(response.to_dict())  # Dictionary
```

**Available Formats:**
- `SiloFormat.CSV` - CSV format
- `SiloFormat.JSON` - JSON format
- `SiloFormat.APSIM` - APSIM format
- `SiloFormat.STANDARD` - Standard format

### Gridded Data (DataDrill)

Get interpolated data for any location in Australia (0.05° grid).

#### High-Level API

```python
# Get gridded data for any coordinates
df = api.get_gridded_data(
    latitude=-27.5,
    longitude=151.0,
    start_date="20230101",
    end_date="20230131",
    variables=["rainfall", "max_temp"]
)

print(df.head())
#         date  daily_rain  max_temp
# 0 2023-01-01        11.2      28.9
# 1 2023-01-02         0.2      30.5
# ...
```

#### Low-Level API

```python
from weather_tools.silo_models import (
    DataDrillQuery,
    AustralianCoordinates,
    SiloDateRange,
    ClimateVariable
)

query = DataDrillQuery(
    coordinates=AustralianCoordinates(
        latitude=-27.5,
        longitude=151.0
    ),
    date_range=SiloDateRange(
        start_date="20230101",
        end_date="20230131"
    ),
    values=[ClimateVariable.RAINFALL]
)

response = api.query_data_drill(query)
print(response.to_csv())
```

### Station Search

Find weather stations by name, location, or get nearby stations.

#### Search by Name

```python
# Search for stations by name
stations = api.search_stations(name_fragment="Brisbane")

print(stations[['name', 'station_code', 'latitude', 'longitude', 'state']])
#                          name  station_code  latitude  longitude state
# 0        BRISBANE AERO             30043   -27.3842   153.1180   QLD
# 1        BRISBANE                  40214   -27.4806   153.0389   QLD
# 2        BRISBANE REGIONAL OFFICE  40913   -27.4553   153.0361   QLD
# ...

# Search with state filter
qld_stations = api.search_stations(
    name_fragment="Brisbane",
    state="QLD"
)

# Results are sorted by fuzzy match score (best matches first)
```

**Available States:**
- `"QLD"` - Queensland
- `"NSW"` - New South Wales
- `"VIC"` - Victoria
- `"TAS"` - Tasmania
- `"SA"` - South Australia
- `"WA"` - Western Australia
- `"NT"` - Northern Territory
- `"ACT"` - Australian Capital Territory

#### Find Nearby Stations

```python
# Find stations within 50km of a station
nearby = api.search_stations(
    station_code="30043",  # Brisbane Aero
    radius_km=50
)

print(nearby[['name', 'station_code', 'latitude', 'longitude']])
#                          name  station_code  latitude  longitude
# 0        BRISBANE AERO             30043   -27.3842   153.1180
# 1        ARCHERFIELD AIRPORT       40004   -27.5703   153.0081
# 2        BRISBANE                  40214   -27.4806   153.0389
# ...
```

#### Wildcard Searching

Use underscores for wildcard matching:

```python
# Find stations with "Bri" followed by any characters and "ne"
stations = api.search_stations(name_fragment="Bri_ne")
# Matches: Brisbane, Brigalow, Bridgetown, etc.
```

### Recent Data

Get recent data for the last N days.

```python
# Get last 7 days for a station
df = api.get_recent_data(
    station_code="30043",
    days=7,
    variables=["rainfall", "max_temp", "min_temp"]
)

# Get last 7 days for coordinates (gridded data)
df = api.get_recent_data(
    latitude=-27.5,
    longitude=151.0,
    days=7
)
```

### API Client Options

```python
# Enable response caching
api = SiloAPI(enable_cache=True)

# Custom timeout and retries
api = SiloAPI(
    timeout=60,        # Request timeout in seconds
    max_retries=5,     # Maximum retry attempts
    retry_delay=2.0    # Base delay between retries
)

# Debug logging
api = SiloAPI(log_level="DEBUG")  # See constructed URLs

# Check cache size
print(f"Cached responses: {api.get_cache_size()}")

# Clear cache
api.clear_cache()
```

---

## Local NetCDF Files

Work with downloaded SILO gridded data for offline processing.

### Downloading Data

Download SILO NetCDF files programmatically:

```python
from pathlib import Path
from weather_tools.download_silo import download_silo_gridded
from weather_tools.logging_utils import get_console

# Download daily variables for recent years
download_silo_gridded(
    variables=["daily"],  # Preset: daily_rain, max_temp, min_temp, evap_syn
    start_year=2020,
    end_year=2023,
    output_dir=Path.home() / "Developer/DATA/silo_grids",
    console=get_console()
)

# Download specific variables
download_silo_gridded(
    variables=["daily_rain", "max_temp"],
    start_year=2022,
    end_year=2023,
    output_dir=Path("./data/silo"),
    force=False,  # Skip existing files
    console=get_console()
)
```

**Variable Presets:**
- `"daily"` - daily_rain, max_temp, min_temp, evap_syn (~1.6GB/year)
- `"monthly"` - monthly_rain (~14MB/year)
- `"temperature"` - max_temp, min_temp (~820MB/year)

**Individual Variables:**
- `"daily_rain"`, `"monthly_rain"`
- `"max_temp"`, `"min_temp"`
- `"evap_syn"`, `"evap_pan"` (1970+)
- `"radiation"`, `"vp"`
- `"mslp"` (1957+)

### Loading Data

Load local NetCDF files into xarray datasets:

```python
from weather_tools import read_silo_xarray
from pathlib import Path

# Load daily variables (default preset)
ds = read_silo_xarray(
    variables="daily",
    silo_dir=Path.home() / "Developer/DATA/silo_grids"
)

print(ds)
# <xarray.Dataset>
# Dimensions:     (time: 1461, lat: 681, lon: 841)
# Coordinates:
#   * time        (time) datetime64[ns] 2020-01-01 ... 2023-12-31
#   * lat         (lat) float64 -44.0 -43.95 ... -10.05 -10.0
#   * lon         (lon) float64 112.0 112.05 ... 153.95 154.0
# Data variables:
#     daily_rain  (time, lat, lon) float32
#     max_temp    (time, lat, lon) float32
#     min_temp    (time, lat, lon) float32
#     evap_syn    (time, lat, lon) float32

# Load specific variables
ds = read_silo_xarray(
    variables=["max_temp", "min_temp"],
    silo_dir=Path("./data/silo")
)

# Load monthly data
ds_monthly = read_silo_xarray(
    variables="monthly",
    silo_dir=Path.home() / "Developer/DATA/silo_grids"
)
```

### Extracting Timeseries

Extract data for specific locations and time periods:

```python
# Extract for a single point
point_data = ds.sel(
    lat=-27.5,
    lon=153.0,
    method="nearest"  # Find nearest grid cell
).sel(
    time=slice("2020-01-01", "2020-12-31")
)

# Convert to DataFrame
df = point_data.to_dataframe().reset_index()
print(df.head())
#         time   lat     lon  daily_rain  max_temp  min_temp  evap_syn
# 0 2020-01-01 -27.5  153.0        12.4      29.1      21.3       5.2
# 1 2020-01-02 -27.5  153.0         0.0      31.2      22.1       6.1
# ...

# Extract for a region (bounding box)
region_data = ds.sel(
    lat=slice(-28.0, -27.0),  # North to South
    lon=slice(152.5, 153.5),  # West to East
    time=slice("2020-01-01", "2020-01-31")
)

# Calculate spatial mean
regional_mean = region_data.mean(dim=["lat", "lon"])
df_mean = regional_mean.to_dataframe().reset_index()

# Extract multiple points
locations = [
    {"name": "Brisbane", "lat": -27.5, "lon": 153.0},
    {"name": "Toowoomba", "lat": -27.6, "lon": 151.9},
]

dfs = []
for loc in locations:
    point = ds.sel(
        lat=loc["lat"],
        lon=loc["lon"],
        method="nearest"
    ).sel(time=slice("2020-01-01", "2020-12-31"))

    df = point.to_dataframe().reset_index()
    df["location"] = loc["name"]
    dfs.append(df)

combined_df = pd.concat(dfs, ignore_index=True)
```

### Working with Large Datasets

```python
# Use dask for lazy loading (doesn't load all data into memory)
ds = read_silo_xarray(variables="daily")

# Compute only what you need
point_data = ds.sel(
    lat=-27.5,
    lon=153.0,
    method="nearest"
).load()  # Load only this subset

# Always close datasets when done
ds.close()

# Or use context manager
with read_silo_xarray(variables="daily") as ds:
    df = ds.sel(lat=-27.5, lon=153.0, method="nearest").to_dataframe()
# Dataset automatically closed
```

---

## Cloud-Optimized GeoTIFF (COG)

SILO provides daily and monthly data as Cloud-Optimized GeoTIFFs, enabling efficient partial reads via HTTP range requests.

### Streaming Data

Read GeoTIFF data directly from URLs without downloading:

```python
from weather_tools.silo_geotiff import read_geotiff_timeseries
from shapely.geometry import Point
from datetime import date

# Stream data for a point (no disk usage)
point = Point(153.0, -27.5)  # Brisbane (lon, lat order!)

data = read_geotiff_timeseries(
    variables=["daily_rain", "max_temp"],
    start_date=date(2023, 1, 1),
    end_date=date(2023, 1, 31),
    geometry=point,
    save_to_disk=False  # Stream from S3
)

# Returns dict: {"daily_rain": array, "max_temp": array}
print(data["daily_rain"].shape)  # (31, h, w) - 31 days of data
print(data["daily_rain"][0])     # First day's data
# array([[12.4, nan, ...]], dtype=float32)
```

### Point Queries

Extract timeseries for a single location:

```python
from shapely.geometry import Point

# Define location
brisbane = Point(153.0, -27.5)  # (longitude, latitude)

# Extract daily data
data = read_geotiff_timeseries(
    variables="daily",  # Uses preset: daily_rain, max_temp, min_temp, evap_syn
    start_date=date(2023, 1, 1),
    end_date=date(2023, 1, 7),
    geometry=brisbane,
    save_to_disk=False
)

# Convert to DataFrame
import pandas as pd
import numpy as np

df = pd.DataFrame({
    "date": pd.date_range("2023-01-01", "2023-01-07"),
    "daily_rain": data["daily_rain"][:, 0, 0],
    "max_temp": data["max_temp"][:, 0, 0],
    "min_temp": data["min_temp"][:, 0, 0],
})
print(df)
```

### Polygon Queries

Extract data for a region:

```python
from shapely.geometry import box, Polygon

# Define bounding box (west, south, east, north)
bbox = box(152.5, -28.0, 153.5, -27.0)

# Extract data for region
data = read_geotiff_timeseries(
    variables=["daily_rain"],
    start_date=date(2023, 1, 1),
    end_date=date(2023, 1, 7),
    geometry=bbox,
    save_to_disk=True,  # Cache to disk for reuse
    cache_dir=Path("./data/geotiff")
)

# Shape: (7 days, height, width)
print(data["daily_rain"].shape)  # (7, ~100, ~100)

# Calculate spatial mean for each day
daily_means = data["daily_rain"].mean(axis=(1, 2))
print(daily_means)  # [12.4, 5.2, 0.0, ...]

# Or use custom polygon
region = Polygon([
    (153.0, -27.5),
    (153.0, -27.0),
    (153.5, -27.0),
    (153.5, -27.5),
    (153.0, -27.5)
])

data = read_geotiff_timeseries(
    variables=["daily_rain"],
    start_date=date(2023, 1, 1),
    end_date=date(2023, 1, 31),
    geometry=region,
    save_to_disk=False
)
```

### Reading Single GeoTIFF Files

For more control, read individual GeoTIFF files:

```python
from weather_tools.silo_geotiff import construct_daily_url, read_cog

# Construct URL for a specific date
url = construct_daily_url("daily_rain", date(2023, 1, 15))
print(url)
# https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/daily/daily_rain/2023/20230115.daily_rain.tif

# Read entire file
data, profile = read_cog(url)
print(data.shape)  # (681, 841) - full Australia grid
print(profile)     # Georeferencing info

# Read subset for a geometry
brisbane = Point(153.0, -27.5)
data, profile = read_cog(url, geometry=brisbane)
print(data.shape)  # (1, 1) - just the pixel containing Brisbane
print(data[0, 0])  # Rainfall value: 12.4 mm
```

### Downloading with Clipping

Download GeoTIFF files with spatial subsetting:

```python
from weather_tools.silo_geotiff import download_geotiff_range
from shapely.geometry import box

# Download with bounding box clipping
bbox = (150.5, -28.5, 154.0, -26.0)  # (min_lon, min_lat, max_lon, max_lat)

download_geotiff_range(
    variables=["daily_rain", "max_temp"],
    start_date=date(2023, 1, 1),
    end_date=date(2023, 1, 31),
    output_dir=Path("./data/geotiff"),
    bounding_box=bbox,
    console=get_console()
)

# Download with polygon clipping
region = box(152.5, -28.0, 153.5, -27.0)

download_geotiff_range(
    variables=["daily_rain"],
    start_date=date(2023, 1, 1),
    end_date=date(2023, 1, 31),
    output_dir=Path("./data/geotiff"),
    geometry=region,
    force=False  # Skip existing files
)
```

**GeoTIFF Benefits:**
- Only download pixels you need via HTTP range requests
- Work with data without storing locally (streaming mode)
- Faster than downloading full NetCDF files for small regions
- Includes overview pyramids for quick previews

---

## Met.no Weather Forecasts

Access weather forecasts from the Norwegian Meteorological Institute's API.

**Data Attribution:** Weather forecast data is provided by The Norwegian Meteorological Institute (MET Norway) under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) and [NLOD 2.0](https://data.norge.no/nlod/en/2.0) licenses. When using this data, you must provide attribution: "Weather forecast data is based on data from [MET Norway](https://www.met.no/en)."

### Getting Forecasts

```python
from weather_tools.metno_api import MetNoAPI
from weather_tools.silo_models import AustralianCoordinates

# Initialize API
api = MetNoAPI(user_agent="MyApp/1.0")  # Required by met.no

# Get daily forecasts for next 7 days
coords = AustralianCoordinates(latitude=-27.5, longitude=153.0)

forecasts = api.get_daily_forecast(
    latitude=coords.latitude,
    longitude=coords.longitude,
    days=7
)

# Convert to DataFrame
import pandas as pd

df = pd.DataFrame([f.model_dump() for f in forecasts])
print(df.columns)
# ['date', 'min_temperature', 'max_temperature', 'total_precipitation',
#  'avg_pressure', 'avg_relative_humidity', 'avg_wind_speed', ...]

# Format to match SILO column names
from weather_tools.silo_variables import convert_metno_to_silo_columns

column_mapping = convert_metno_to_silo_columns(df)
df_silo = df.rename(columns=column_mapping)
print(df_silo.columns)
# ['date', 'min_temp', 'max_temp', 'daily_rain', 'mslp', ...]
```

### Merging with SILO Historical Data

Combine SILO historical observations with met.no forecasts:

```python
from weather_tools import read_silo_xarray
from weather_tools.merge_weather_data import merge_historical_and_forecast
from weather_tools.metno_api import MetNoAPI
from pathlib import Path

# 1. Get SILO historical data
ds = read_silo_xarray(
    variables="daily",
    silo_dir=Path.home() / "Developer/DATA/silo_grids"
)

# Extract for location
silo_df = ds.sel(
    lat=-27.5,
    lon=153.0,
    method="nearest"
).to_dataframe().reset_index()

# Filter to recent period
silo_df = silo_df[
    (silo_df["time"] >= "2023-01-01") &
    (silo_df["time"] <= "2023-12-31")
]
silo_df = silo_df.rename(columns={"time": "date"})

# 2. Get met.no forecast
metno_api = MetNoAPI()
forecasts = metno_api.get_daily_forecast(
    latitude=-27.5,
    longitude=153.0,
    days=7
)

metno_df = pd.DataFrame([f.model_dump() for f in forecasts])

# 3. Merge datasets
merged_df = merge_historical_and_forecast(
    silo_df,
    metno_df,
    validate=True,
    fill_missing=False,  # Don't fill SILO-only variables with estimates
    overlap_strategy="prefer_silo"  # Prefer SILO data if dates overlap
)

# Get merge summary
from weather_tools.merge_weather_data import get_merge_summary

summary = get_merge_summary(merged_df)
print(f"Total records: {summary['total_records']}")
print(f"SILO records: {summary['silo_records']}")
print(f"Met.no records: {summary['metno_records']}")
print(f"Transition date: {summary['transition_date']}")

# Save combined dataset
merged_df.to_csv("historical_and_forecast.csv", index=False)
```

**Merge Options:**
- `validate=True` - Validate data consistency during merge
- `fill_missing=True` - Estimate SILO-only variables in forecast (radiation, evaporation)
- `overlap_strategy` - How to handle overlapping dates:
  - `"prefer_silo"` - Use SILO data when available (default)
  - `"prefer_metno"` - Use forecast data
  - `"error"` - Raise error on overlap

---

## Advanced Examples

### Batch Processing Multiple Locations

```python
from weather_tools.silo_api import SiloAPI
import pandas as pd

api = SiloAPI()

locations = [
    {"name": "Brisbane", "station": "30043"},
    {"name": "Sydney", "station": "66062"},
    {"name": "Melbourne", "station": "86071"},
]

all_data = []
for loc in locations:
    df = api.get_station_data(
        station_code=loc["station"],
        start_date="20230101",
        end_date="20231231",
        variables=["rainfall", "max_temp"]
    )
    df["location"] = loc["name"]
    all_data.append(df)

combined = pd.concat(all_data, ignore_index=True)
combined.to_csv("australia_weather_2023.csv", index=False)
```

### Spatial Analysis with NetCDF

```python
from weather_tools import read_silo_xarray
import matplotlib.pyplot as plt

# Load data
ds = read_silo_xarray(variables=["daily_rain"])

# Select a specific day
day_data = ds.sel(time="2023-01-15")

# Plot rainfall map
day_data["daily_rain"].plot(
    cmap="Blues",
    vmin=0,
    vmax=50,
    cbar_kwargs={"label": "Rainfall (mm)"}
)
plt.title("Daily Rainfall - 2023-01-15")
plt.show()

# Calculate monthly totals
monthly_rain = ds["daily_rain"].resample(time="1M").sum()
monthly_df = monthly_rain.sel(
    lat=-27.5,
    lon=153.0,
    method="nearest"
).to_dataframe()
```

### Comparing API vs Local Data

```python
# API approach (quick, no downloads)
api = SiloAPI()
df_api = api.get_gridded_data(
    latitude=-27.5,
    longitude=153.0,
    start_date="20230101",
    end_date="20230131",
    variables=["rainfall"]
)

# Local file approach (faster for bulk queries)
ds = read_silo_xarray(variables=["daily_rain"])
df_local = ds.sel(
    lat=-27.5,
    lon=153.0,
    method="nearest"
).sel(
    time=slice("2023-01-01", "2023-01-31")
).to_dataframe().reset_index()

# Both produce equivalent results
```

---

## Error Handling

```python
from weather_tools.silo_api import SiloAPI, SiloAPIError
from weather_tools.silo_geotiff import SiloGeoTiffError
from weather_tools.metno_models import MetNoAPIError, MetNoRateLimitError

# SILO API errors
api = SiloAPI()
try:
    df = api.get_station_data(
        station_code="99999",  # Invalid station
        start_date="20230101",
        end_date="20230131"
    )
except SiloAPIError as e:
    print(f"API error: {e}")

# GeoTIFF errors
try:
    from shapely.geometry import Point
    point = Point(200, -27.5)  # Invalid longitude
    data = read_geotiff_timeseries(
        variables=["daily_rain"],
        start_date=date(2023, 1, 1),
        end_date=date(2023, 1, 31),
        geometry=point
    )
except SiloGeoTiffError as e:
    print(f"GeoTIFF error: {e}")

# Met.no rate limiting
try:
    api = MetNoAPI()
    forecasts = api.get_daily_forecast(-27.5, 153.0, days=7)
except MetNoRateLimitError as e:
    print(f"Rate limited: {e}")
    # Wait before retrying
except MetNoAPIError as e:
    print(f"API error: {e}")
```

---

## Performance Tips

### 1. Use Caching for Repeated Queries

```python
# Enable caching for repeated API calls
api = SiloAPI(enable_cache=True)

# First call: queries API
df1 = api.get_station_data("30043", "20230101", "20230131")

# Second call: uses cache (instant)
df2 = api.get_station_data("30043", "20230101", "20230131")

print(f"Cached responses: {api.get_cache_size()}")
api.clear_cache()  # Clear when done
```

### 2. Use Local Files for Bulk Processing

```python
# Download once
download_silo_gridded(
    variables="daily",
    start_year=2020,
    end_year=2023
)

# Query many times (fast, no network)
ds = read_silo_xarray(variables="daily")
for lat in range(-44, -10):
    for lon in range(113, 154):
        df = ds.sel(lat=lat, lon=lon, method="nearest").to_dataframe()
        # Process...
```

### 3. Use GeoTIFF Streaming for Small Regions

```python
# For small spatial queries, stream GeoTIFFs (no disk usage)
point = Point(153.0, -27.5)
data = read_geotiff_timeseries(
    variables=["daily_rain"],
    start_date=date(2023, 1, 1),
    end_date=date(2023, 12, 31),
    geometry=point,
    save_to_disk=False  # Stream, don't cache
)
# Much faster than downloading full NetCDF files
```

---

## Full Documentation

📚 **[Online Documentation](https://harryeslick.github.io/weather_tools/)** - Complete API reference and examples

**See Also:**
- [CLI Guide](CLI_README.md) - Command-line interface documentation
- [SILO API Reference](https://www.longpaddock.qld.gov.au/silo/api-documentation/)
- [Examples & Tutorials](https://harryeslick.github.io/weather_tools/notebooks/example/)
