# Weather Tools CLI

A command-line interface for working with SILO weather data from two sources:
- **API**: Query live data from the SILO API (no downloads required)
- **Local**: Extract data from local netCDF files (requires downloaded data)

## Installation

**Option 1: Using uv (Recommended)**
```bash
uv pip install weather-tools
```

**Option 2: Using pip**
```bash
pip install -e .
```

**Option 3: Run directly with uvx**
```bash
uvx weather-tools --help
```

## Command Structure

The CLI is organized hierarchically by data source:

```
weather-tools
├── silo          # SILO API commands (requires API key)
│   ├── patched-point    # Query station-based data
│   ├── data-drill       # Query gridded data
│   └── search           # Search for stations
└── local         # Local netCDF file commands
    ├── extract          # Extract data for a location
    └── info             # View available local data
```

## Quick Start

### Using the SILO API (Online)

```bash
# Set your API key
export SILO_API_KEY="your_email@example.com"

# Query station data
weather-tools silo patched-point --station 30043 \
    --start-date 20230101 --end-date 20230131 \
    --var R --var X --output weather.csv

# Query gridded data
weather-tools silo data-drill --latitude -27.5 --longitude 151.0 \
    --start-date 20230101 --end-date 20230131 \
    --var R --output weather.csv

# Search for stations
weather-tools silo search --name Brisbane
```

### Using Local Files (Offline)

```bash
# View available data
weather-tools local info

# Extract data for a location
weather-tools local extract --lat -27.5 --lon 153.0 \
    --start-date 2020-01-01 --end-date 2025-01-01 \
    --output weather.csv
```

## SILO API Commands

These commands query the SILO API directly - **no local files required!**

### `silo patched-point`

Query station-based observational data with infilled gaps.

**Note:** This command requires a BOM station code. Use `weather-tools silo search --name [location]` to find station codes by name.

```bash
weather-tools silo patched-point [OPTIONS]
```

**Required Options:**
- `--station TEXT` - BOM station code (e.g., '30043' for Brisbane Aero)
- `--start-date TEXT` - Start date in YYYYMMDD format
- `--end-date TEXT` - End date in YYYYMMDD format

**Optional Options:**
- `--format TEXT` - Output format: csv, json, apsim, standard (auto-detected from filename if not specified)
- `--var TEXT` - Climate variable codes (can be used multiple times): R, X, N, V, E, J, F, T, A, P, W, L, S, C, H, G, D, M
- `--output, -o TEXT` - Output filename (extension auto-corrected to match format)
- `--api-key TEXT` - SILO API key (or set SILO_API_KEY env var)  
- `--enable-cache` - Enable response caching
- `--debug` - Print constructed URL for debugging

**Format Auto-Detection:**
File extensions automatically determine output format:
- `.csv` → csv format
- `.json` → json format  
- `.apsim` → apsim format
- `.txt` → standard format

**Examples:**

```bash
# Get rainfall and temperature for Brisbane Aero (format auto-detected from .csv)
weather-tools silo patched-point --station 30043 \
    --start-date 20230101 --end-date 20230131 \
    --var R --var X --var N --output data.csv

# Get all variables in APSIM format (auto-detected from .apsim extension)
weather-tools silo patched-point --station 30043 \
    --start-date 20230101 --end-date 20230131 \
    --output data.apsim

# Force JSON format (filename will be corrected to data.json)
weather-tools silo patched-point --station 30043 \
    --start-date 20230101 --end-date 20230131 \
    --format json --output data.csv
```

### `silo data-drill`

Query gridded data at 0.05° × 0.05° resolution (~5km grid spacing).

```bash
weather-tools silo data-drill [OPTIONS]
```

**Required Options:**
- `--latitude FLOAT` - Latitude in decimal degrees (-44 to -10)
- `--longitude FLOAT` - Longitude in decimal degrees (113 to 154)
- `--start-date TEXT` - Start date in YYYYMMDD format
- `--end-date TEXT` - End date in YYYYMMDD format

**Optional Options:**
- `--format TEXT` - Output format: csv, json, apsim, alldata, standard (default: csv)
- `--var TEXT` - Climate variable codes (can be used multiple times)
- `--output, -o TEXT` - Output filename
- `--api-key TEXT` - SILO API key (or set SILO_API_KEY env var)
- `--enable-cache` - Enable response caching
- `--debug` - Print constructed URL for debugging

**Examples:**

```bash
# Get rainfall for a specific location
weather-tools silo data-drill --latitude -27.5 --longitude 151.0 \
    --start-date 20230101 --end-date 20230131 \
    --var R --output data.csv

# Get all variables for a location
weather-tools silo data-drill --latitude -27.5 --longitude 151.0 \
    --start-date 20230101 --end-date 20230131 \
    --format alldata --output data.txt
```

### `silo search`

Search for SILO stations by name or find nearby stations.

```bash
weather-tools silo search [OPTIONS]
```

**Options:**
- `--name TEXT` - Search for stations by name fragment (e.g., 'Brisbane')
- `--station TEXT` - Station code for nearby search or details lookup
- `--radius FLOAT` - Search radius in km (for nearby search, default: 50.0)
- `--details` - Get detailed info for a specific station
- `--api-key TEXT` - SILO API key (or set SILO_API_KEY env var)
- `--output, -o TEXT` - Output filename
- `--debug` - Print constructed URL for debugging

**Examples:**

```bash
# Search by name
weather-tools silo search --name Brisbane

# Find nearby stations
weather-tools silo search --station 30043 --radius 50

# Get station details
weather-tools silo search --station 30043 --details
```

## Local File Commands

These commands work with local SILO netCDF files - **requires downloaded data**.

### `local extract`

Extract weather data from local netCDF files for a specific location and date range.

```bash
weather-tools local extract [OPTIONS]
```

**Required Options:**
- `--lat FLOAT` - Latitude coordinate
- `--lon FLOAT` - Longitude coordinate
- `--start-date TEXT` - Start date (YYYY-MM-DD format)
- `--end-date TEXT` - End date (YYYY-MM-DD format)

**Optional Options:**
- `--output TEXT` - Output CSV filename (default: "weather_data.csv")
- `--variables TEXT` - Weather variables to extract (can be used multiple times):
  - `daily` (default) - Extracts max_temp, min_temp, daily_rain, evap_syn
  - `monthly` - Extracts monthly_rain
  - Individual variables: `max_temp`, `min_temp`, `daily_rain`, `evap_syn`, `monthly_rain`
- `--silo-dir PATH` - Path to SILO data directory (default: ~/Developer/DATA/silo_grids)
- `--tolerance FLOAT` - Maximum distance (in degrees) for nearest neighbor selection (default: 0.1)
- `--keep-location` - Keep location columns (crs, lat, lon) in output CSV

**Examples:**

```bash
# Basic extraction with default settings
weather-tools local extract --lat -27.5 --lon 153.0 \
    --start-date 2020-01-01 --end-date 2025-01-01

# Extract monthly data
weather-tools local extract --lat -27.5 --lon 153.0 \
    --start-date 2020-01-01 --end-date 2025-01-01 \
    --variables monthly --output monthly_data.csv

# Extract specific variables
weather-tools local extract --lat -27.5 --lon 153.0 \
    --start-date 2020-01-01 --end-date 2025-01-01 \
    --variables max_temp --variables min_temp

# Use custom SILO directory
weather-tools local extract --lat -27.5 --lon 153.0 \
    --start-date 2020-01-01 --end-date 2025-01-01 \
    --silo-dir /path/to/silo/data
```

### `local info`

Display information about available local SILO data.

```bash
weather-tools local info [OPTIONS]
```

**Options:**
- `--silo-dir PATH` - Path to SILO data directory (default: ~/Developer/DATA/silo_grids)

**Example:**

```bash
# View local data info
weather-tools local info

# View data in custom directory
weather-tools local info --silo-dir /path/to/silo/data
```

**Output includes:**
- SILO data directory path
- Available variable directories
- Number of files in each directory
- Year range for each variable

## Climate Variables

### SILO API Variable Codes

When using `silo patched-point` or `silo data-drill`, use these single-letter codes:

**Primary Variables (Observed):**
- `R` - Daily rainfall (mm)
- `X` - Maximum temperature (°C)
- `N` - Minimum temperature (°C)
- `V` - Vapour pressure (hPa)
- `E` - Class A pan evaporation (mm)

**Derived Variables:**
- `J` - Solar radiation (MJ/m²)
- `F` - FAO56 short crop evapotranspiration (mm)
- `T` - ASCE tall crop evapotranspiration (mm)
- `A` - Morton's actual evapotranspiration (mm)
- `P` - Morton's potential evapotranspiration (mm)
- `W` - Morton's wet-environment evapotranspiration (mm)
- `L` - Morton's shallow lake evaporation (mm)
- `S` - Synthetic evaporation estimate (mm)
- `C` - Combined evaporation (mm)
- `H` - Relative humidity at Tmax (%)
- `G` - Relative humidity at Tmin (%)
- `D` - Vapour pressure deficit (hPa)
- `M` - Mean sea level pressure (hPa)

### Local File Variable Names

When using `local extract`, use these full names:
- `daily_rain` - Daily rainfall
- `max_temp` - Maximum temperature
- `min_temp` - Minimum temperature
- `evap_syn` - Synthetic evaporation
- `monthly_rain` - Monthly rainfall totals

## Setting Up Local Files

If you want to use the `local` commands, you need to download SILO netCDF files.

**Download Location:**  
<https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/index.html>

**Expected Directory Structure:**

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

## Getting a SILO API Key

To use the `silo` commands, you need an API key (your email address):

1. Your email address serves as the API key
2. Set it as an environment variable:
   ```bash
   export SILO_API_KEY="your_email@example.com"
   ```
3. Or pass it with `--api-key` option

## Output Format

### SILO API Output

API commands return data in the requested format:
- **CSV**: Comma-separated values with headers
- **JSON**: Structured JSON data
- **APSIM**: APSIM agricultural model format
- **ALLDATA**: All available variables
- **STANDARD**: Common variables subset

### Local Extract Output

The `local extract` command outputs a CSV file containing:
- `time` - Date/time index
- Weather variable columns (e.g., `max_temp`, `min_temp`, `daily_rain`, `evap_syn`)

Location columns (`lat`, `lon`, `crs`) are dropped by default. Use `--keep-location` to retain them.

## Help

Use `--help` with any command to see detailed usage information:

```bash
weather-tools --help
weather-tools silo --help
weather-tools silo patched-point --help
weather-tools local --help
weather-tools local extract --help
```

## Comparison: API vs Local

| Feature | SILO API | Local Files |
|---------|----------|-------------|
| **Setup** | Just need email address | Download ~GB of netCDF files |
| **Speed** | Depends on internet | Fast (local disk) |
| **Data Range** | 1889-present | Only years you download |
| **Variables** | 18 climate variables | 5 common variables |
| **Location** | Any coordinates in Australia | Any coordinates in Australia |
| **Caching** | Optional response caching | N/A (already local) |
| **Formats** | csv, json, apsim, alldata, standard | CSV only |
| **Station Search** | Yes (search, nearby, details) | No |

**Recommendation:**
- Use **API** for ad-hoc queries, recent data, or many variables
- Use **Local** for bulk processing, offline work, or repeated queries
