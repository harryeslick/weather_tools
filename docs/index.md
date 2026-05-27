# Welcome to weather tools

A Python package and command-line interface for accessing and processing Australian SILO climate data.

This package provides both a Python API and a powerful CLI for querying the SILO API, working with local NetCDF files, and reading Cloud-Optimized GeoTIFFs.

## Features

- **SILO API Client**: Query PatchedPoint (station) and DataDrill (gridded) datasets directly
- **Local NetCDF Files**: Download and process SILO gridded data for offline use
- **Cloud-Optimized GeoTIFFs**: Efficiently stream or download spatial subsets via HTTP range requests
- **Command-Line Interface**: Simple commands for all data access patterns
- **Python API**: Programmatic access using Pydantic models and xarray
- **Station Search**: Find weather stations by name or location
- **Easy Installation**: Use with `uvx` for zero-installation usage

## Quick Start

### CLI Usage

**SILO API (Online - requires API key):**
```bash
# Query station data
weather-tools silo patched-point --station 30043 \
  --start-date 2023-01-01 --end-date 2023-01-31 \
  --output station_data.csv

# Query gridded data  
weather-tools silo data-drill \
  --lat -27.5 --lon 153.0 --start-date 2023-01-01 --end-date 2023-01-31 \
  --output brisbane_2023.csv
```

**Local NetCDF files (Offline):**
```bash
# Download files
weather-tools local download --start-year 2020 --end-year 2023

# Extract weather data for Brisbane from local files
weather-tools local extract \
  --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --output brisbane_2020.csv
```

### Python API

```python
from weather_tools import read_silo_xarray

# Load available daily weather variables
ds = read_silo_xarray()

# Extract data for a specific location and date range
df = ds.sel(lat=-27.5, lon=153.0, method="nearest").sel(
    time=slice("2020-01-01", "2020-12-31")
).to_dataframe().reset_index()
```

## Documentation Sections

- **[CLI Reference](cli.md)**: Complete command-line interface documentation
- **[Python API Guide](../PY_README.md)**: Comprehensive Python API documentation  
- **[Examples](notebooks/example.ipynb)**: Jupyter notebook examples

## Data Sources

This package supports multiple SILO data access patterns:

- **SILO API**: Real-time queries (requires API key = email address)
- **NetCDF Files**: Bulk downloads from AWS S3 for offline processing
- **GeoTIFF Files**: Cloud-optimized format for efficient spatial subsetting

**Data Resources:**
- **SILO Homepage**: [https://www.longpaddock.qld.gov.au/silo/](https://www.longpaddock.qld.gov.au/silo/)
- **NetCDF Files**: [AWS S3 Index](https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/index.html)
