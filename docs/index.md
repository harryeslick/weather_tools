# Welcome to weather tools

A Python package and command-line interface for working with weather data operations.

This package provides both a Python API and a powerful CLI for loading and using [SILO weather data](https://www.longpaddock.qld.gov.au/silo/gridded-data/) from local netCDF files.

## Features

- **Dual Mode Access**: Query SILO API directly or work with local NetCDF files
- **Command-Line Interface**: Simple commands for both online API and offline data
- **Python API**: Programmatic access to SILO data using xarray
- **Multiple Data Sources**: PatchedPoint (station) and DataDrill (gridded) datasets
- **Flexible Output**: Export data to CSV, JSON, APSIM, or standard formats
- **Station Search**: Find weather stations by name or proximity
- **Easy Installation**: Use with `uvx` for zero-installation usage

## Quick Start

### CLI Usage

**SILO API (Online - requires API key):**
```bash
# Query station data
uvx git+https://github.com/harryeslick/weather_tools.git silo patched-point \
  --station 30043 --start-date 2023-01-01 --end-date 2023-01-31 \
  --output station_data.csv

# Query gridded data  
uvx git+https://github.com/harryeslick/weather_tools.git silo data-drill \
  --lat -27.5 --lon 153.0 --start-date 2023-01-01 --end-date 2023-01-31 \
  --output brisbane_2023.csv
```

**Local NetCDF files (Offline):**
```bash
# Extract weather data for Brisbane from local files
uvx git+https://github.com/harryeslick/weather_tools.git local extract \
  --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --output brisbane_2020.csv
```

### Python API

```python
from weather_tools import read_silo_xarray

# Load daily weather variables
ds = read_silo_xarray(variables="daily")

# Extract data for a specific location and date range
df = ds.sel(lat=-27.5, lon=153.0, method="nearest").sel(
    time=slice("2020-01-01", "2020-12-31")
).to_dataframe().reset_index()
```

## Documentation Sections

- **[CLI Reference](cli.md)**: Complete command-line interface documentation
- **[API Reference](api_docs/read_silo.md)**: Python API documentation  
- **[Examples](notebooks/example.ipynb)**: Jupyter notebook examples

## Data Requirements

To use this package you will need to download the netCDF files which you require from SILO:

- **Data Source**: [SILO Gridded Data](https://www.longpaddock.qld.gov.au/silo/gridded-data/)
- **AWS S3 Index**: [Complete file list](https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/index.html)
