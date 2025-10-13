# Weather tools

[![Deploy MkDocs GitHub Pages](https://github.com/harryeslick/weather_tools/actions/workflows/mkdocs.yml/badge.svg)](https://github.com/harryeslick/weather_tools/actions/workflows/mkdocs.yml)

This is a python package for personal commonly used functions for working with weather data.
Primarily for loading and using [SILO weather data](https://www.longpaddock.qld.gov.au/silo/gridded-data/) from **local** netCDF files.

## Installation

### Option 1: Using uvx (Recommended for CLI usage)

The easiest way to use the CLI tool is with `uvx`, which automatically handles dependencies and isolation:

```bash
# Run directly from GitHub (once published)
uvx git+https://github.com/harryeslick/weather_tools.git --help

# Or run from local directory
uvx . --help
```

### Option 2: Traditional pip installation

```bash
# Install from local directory
pip install -e .

# Or install from GitHub (once published)
pip install git+https://github.com/harryeslick/weather_tools.git
```

## Data Setup

To use this package you will need to download the netCDF files which you require from SILO.
A complete list of netCDF files available on AWS S3 can be found here:
<https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/index.html>

### Expected Directory Structure

The package expects SILO data to be organized as follows:

```
~/Developer/DATA/silo_grids/
├── daily_rain/
│   ├── 2020.daily_rain.nc
│   ├── 2021.daily_rain.nc
│   └── ...
├── evap_syn/
│   ├── 2020.evap_syn.nc
│   ├── 2021.evap_syn.nc  
│   └── ...
├── max_temp/
│   ├── 2020.max_temp.nc
│   ├── 2021.max_temp.nc
│   └── ...
├── min_temp/
│   ├── 2020.min_temp.nc
│   ├── 2021.min_temp.nc
│   └── ...
└── monthly_rain/
    ├── 2020.monthly_rain.nc
    ├── 2021.monthly_rain.nc
    └── ...
```


## CLI Usage

The package provides a command-line interface for extracting weather data from SILO datasets.

### Quick Start

```bash
# Extract weather data for Brisbane (lat: -27.5, lon: 153.0) for January 2020
uvx . extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2020-01-31 --output brisbane_jan2020.csv
```

### Available Commands

#### `info` - View available data

Display information about your SILO data directory:

```bash
uvx . info
```

This shows:
- Available variable directories (daily_rain, max_temp, min_temp, etc.)
- Number of files in each directory  
- Year ranges available for each variable

#### `extract` - Extract weather data

Extract weather data for a specific location and date range:

```bash
uvx . extract --lat LAT --lon LON --start-date YYYY-MM-DD --end-date YYYY-MM-DD [OPTIONS]
```

**Required Parameters:**
- `--lat`: Latitude coordinate
- `--lon`: Longitude coordinate  
- `--start-date`: Start date (YYYY-MM-DD format)
- `--end-date`: End date (YYYY-MM-DD format)

**Optional Parameters:**
- `--output`: Output CSV filename (default: `weather_data.csv`)
- `--variables`: Variables to extract (see options below)
- `--silo-dir`: Path to SILO data directory (default: `~/Developer/DATA/silo_grids`)

**Variable Options:**
- `daily` (default): Extracts max_temp, min_temp, daily_rain, evap_syn
- `monthly`: Extracts monthly_rain  
- Individual variables: `max_temp`, `min_temp`, `daily_rain`, `evap_syn`, `monthly_rain`

### Usage Examples

1. **Basic extraction with default daily variables:**
   ```bash
   uvx . extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2020-12-31
   ```

2. **Extract monthly rainfall data:**
   ```bash
   uvx . extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2020-12-31 --variables monthly --output monthly_rainfall.csv
   ```

3. **Extract specific variables:**
   ```bash
   uvx . extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2020-12-31 --variables max_temp --variables min_temp --output temperatures.csv
   ```

4. **Use custom SILO directory:**
   ```bash
   uvx . extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2020-12-31 --silo-dir /path/to/my/silo/data
   ```

### Output Format

The CLI generates CSV files with the following columns:
- `time`: Date/time index
- `lat`: Latitude (nearest grid point to your coordinates)
- `lon`: Longitude (nearest grid point to your coordinates)  
- Weather variable columns (e.g., `max_temp`, `min_temp`, `daily_rain`, `evap_syn`)

## Python API

You can also use the package directly in Python:

```python
from weather_tools import read_silo_xarray

# Load daily variables (max_temp, min_temp, daily_rain, evap_syn)
ds = read_silo_xarray(variables="daily")

# Extract data for a specific location and date range
df = ds.sel(lat=-27.5, lon=153.0, method="nearest").sel(
    time=slice("2020-01-01", "2020-12-31")
).to_dataframe().reset_index()
```


