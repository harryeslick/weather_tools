# Command Line Interface (CLI)

The weather-tools package provides a powerful command-line interface for working with SILO weather data. You can query data directly from the SILO API or extract data from local netCDF files.

## Installation

### Using uv (Recommended)

```bash
# Install with uv
uv pip install weather-tools

# Or run directly with uvx (no installation)
uvx weather-tools --help
```

### Using pip

```bash
# Install from local directory
pip install -e .

# Or install from GitHub
pip install git+https://github.com/harryeslick/weather_tools.git
```

After installation, the `weather-tools` command will be available.

## Commands Overview

The CLI provides two command groups:

### SILO API Commands (Online)
- **`silo patched-point`** - Query SILO PatchedPoint dataset (station-based data)
- **`silo data-drill`** - Query SILO DataDrill dataset (gridded data)
- **`silo search`** - Search for SILO stations by name or find nearby stations

### Local NetCDF Commands (Offline)
- **`local info`** - Display information about available local SILO data
- **`local extract`** - Extract weather data from local netCDF files

## Quick Start Examples

### Query SILO API (No Downloads Required)

```bash
# Set your API key
export SILO_API_KEY="your_api_key_here"

# Query station data (PatchedPoint)
weather-tools silo patched-point --station 30043 \
  --start-date 2023-01-01 --end-date 2023-01-31 --output data.csv

# Query gridded data (DataDrill)
weather-tools silo data-drill --lat -27.5 --lon 151.0 \
  --start-date 2023-01-01 --end-date 2023-01-31 --output gridded_data.csv

# Search for stations
weather-tools silo search --name "Brisbane"
weather-tools silo search --station 30043 --radius 50
```

### Use Local NetCDF Files

```bash
# Display available local SILO data
weather-tools local info

# Extract data from local files
weather-tools local extract --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --output brisbane_2020.csv
```

## Command Reference

### Global Options

```
Usage: weather-tools [OPTIONS] COMMAND [ARGS]...

Commands:
  silo      Query SILO API directly (requires API key)
  info      Display information about available local SILO data
  extract   Extract weather data from local netCDF files

Options:
  --install-completion    Install completion for the current shell
  --show-completion      Show completion for the current shell
  --help                 Show this message and exit
```

---

## SILO API Commands

These commands query the SILO API directly - no local files required!

### `silo patched-point` Command

Query the SILO PatchedPoint dataset for station-based weather data.

```bash
weather-tools silo patched-point [OPTIONS]
```

#### Required Options

| Option | Type | Description |
|--------|------|-------------|
| `--station` | TEXT | Station code (e.g., 30043) |
| `--start-date` | TEXT | Start date in YYYYMMDD format |
| `--end-date` | TEXT | End date in YYYYMMDD format |

#### Optional Parameters

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `--format` | TEXT | Output format: 'csv', 'json', 'apsim', 'standard' | Auto-detected from output filename |
| `--variables` | TEXT | Weather variables (e.g. daily_rain, max_temp) (can be used multiple times) | All available |
| `--output` | PATH | Output filename | Required |
| `--api-key` | TEXT | SILO API key (or set SILO_API_KEY env var) | |

#### Examples

```bash
# Basic station data query
weather-tools silo patched-point --station 30043 \
    --start-date 20230101 --end-date 20230131 \
    --output data.csv

# Query with specific variables
weather-tools silo patched-point --station 30043 \
    --start-date 20230101 --end-date 20230131 \
    --variables daily_rain --variables max_temp --variables min_temp \
    --output station_data.csv

# Auto-detect format from extension
weather-tools silo patched-point --station 30043 \
    --start-date 20230101 --end-date 20230131 \
    --output data.json  # Automatically uses JSON format
```

### `silo data-drill` Command

Query the SILO DataDrill dataset for gridded weather data.

```bash
weather-tools silo data-drill [OPTIONS]
```

#### Required Options

| Option | Type | Description |
|--------|------|-------------|
| `--lat` | FLOAT | Latitude coordinate |
| `--lon` | FLOAT | Longitude coordinate |
| `--start-date` | TEXT | Start date in YYYYMMDD format |
| `--end-date` | TEXT | End date in YYYYMMDD format |

#### Optional Parameters

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `--format` | TEXT | Output format: 'csv', 'json', 'apsim', 'standard' | Auto-detected from output filename |
| `--variables` | TEXT | Weather variables (can be used multiple times) | All available |
| `--output` | PATH | Output filename | Required |
| `--api-key` | TEXT | SILO API key (or set SILO_API_KEY env var) | |

#### Examples

```bash
# Query gridded data for Brisbane
weather-tools silo data-drill --lat -27.5 --lon 153.0 \
    --start-date 20230101 --end-date 20230131 \
    --output brisbane_weather.csv

# Query with APSIM format
weather-tools silo data-drill --lat -27.5 --lon 153.0 \
    --start-date 20230101 --end-date 20230131 \
    --output weather.apsim  # Auto-detects APSIM format
```

### `silo search` Command

Search for SILO weather stations by name or find stations near a location.

```bash
weather-tools silo search [OPTIONS]
```

#### Search Options (choose one)

| Option | Type | Description |
|--------|------|-------------|
| `--name` | TEXT | Search stations by name |
| `--station` | TEXT | Find stations near this station code |
| `--lat` | FLOAT | Latitude for proximity search (requires --lon) |
| `--lon` | FLOAT | Longitude for proximity search (requires --lat) |

#### Optional Parameters

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `--radius` | FLOAT | Search radius in km | `50.0` |
| `--api-key` | TEXT | SILO API key (or set SILO_API_KEY env var) | |
| `--output` | TEXT | Output filename (optional) | |

#### Examples

```bash
# Search by station name
weather-tools silo search --name "Brisbane"

# Find stations near a specific station
weather-tools silo search --station 30043 --radius 50

# Find stations near coordinates
weather-tools silo search --lat -27.5 --lon 153.0 --radius 100

# Save results to file
weather-tools silo search --name "Sydney" --output sydney_stations.txt
```

### Setting Your API Key

For security, it's best to set your API key as an environment variable:

```bash
# In your terminal or .bashrc/.zshrc
export SILO_API_KEY="your_api_key_here"

# Then you can use commands without --api-key option
weather-tools silo patched-point --station 30043 ...
```

Or create a `.env` file in your project:

```bash
# .env file
SILO_API_KEY=your_api_key_here
```

---

## Local NetCDF Commands

These commands work with downloaded SILO gridded data files.

### `local info` Command

Display information about available SILO data directories and files.

```bash
weather-tools local info [OPTIONS]
```

#### Options

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `--silo-dir` | PATH | Path to SILO data directory | `~/DATA/silo_grids` |
| `--help` | | Show help message and exit | |

#### Example Usage

```bash
# Show info for default SILO directory
weather-tools local info

# Show info for custom SILO directory
weather-tools local info --silo-dir /path/to/my/silo/data
```

#### Sample Output

```
SILO data directory: /Users/user/Developer/DATA/silo_grids

📁 Available variable directories:
  📂 daily_rain: 25 files
    📅 Years: 2000-2024
  📂 evap_syn: 25 files
    📅 Years: 2000-2024
  📂 max_temp: 25 files
    📅 Years: 2000-2024
  📂 min_temp: 25 files
    📅 Years: 2000-2024
  📂 monthly_rain: 136 files
    📅 Years: 1889-2024
```

### `local extract` Command

Extract weather data for a specific location and date range, saving results to CSV.

```bash
weather-tools local extract [OPTIONS]
```

#### Required Options

| Option | Type | Description |
|--------|------|-------------|
| `--lat` | FLOAT | Latitude coordinate (required) |
| `--lon` | FLOAT | Longitude coordinate (required) |
| `--start-date` | TEXT | Start date in YYYY-MM-DD format (required) |
| `--end-date` | TEXT | End date in YYYY-MM-DD format (required) |

#### Optional Options

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `--output` | TEXT | Output CSV filename | `weather_data.csv` |
| `--variables` | TEXT | Weather variables to extract (see below) | `daily` |
| `--silo-dir` | PATH | Path to SILO data directory | `~/DATA/silo_grids` |
| `--tolerance` | FLOAT | Maximum distance (in degrees) for nearest neighbor selection | `0.1` |
| `--keep-location` | BOOLEAN | Keep location columns (crs, lat, lon) in output CSV | `False` (columns are dropped by default) |
| `--help` | | Show help message and exit | |

#### Variable Options

The `--variables` option accepts the following values:

| Value | Variables Included | Description |
|-------|-------------------|-------------|
| `daily` | max_temp, min_temp, daily_rain, evap_syn | Daily weather variables (default) |
| `monthly` | monthly_rain | Monthly rainfall data |
| Individual variables | Any combination of: `max_temp`, `min_temp`, `daily_rain`, `evap_syn`, `monthly_rain` | Specify individual variables |

#### Example Usage

##### Basic Extraction

```bash
# Extract daily variables for Brisbane in 2020
weather-tools local extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2020-12-31
```

##### Monthly Data

```bash
# Extract monthly rainfall data
weather-tools local extract \
  --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --variables monthly \
  --output monthly_rainfall.csv
```

##### Specific Variables

```bash
# Extract only temperature data
weather-tools local extract \
  --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --variables max_temp --variables min_temp \
  --output temperatures.csv
```

##### Custom Directory and Output

```bash
# Use custom SILO directory and output file
weather-tools local extract \
  --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --silo-dir /path/to/my/silo/data \
  --output custom_weather_data.csv
```

##### Using Custom Tolerance

```bash
# Use stricter tolerance (0.01 degrees ≈ 1.1 km)
weather-tools local extract \
  --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --tolerance 0.01

# Use more permissive tolerance (0.5 degrees ≈ 55 km)
weather-tools local extract \
  --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --tolerance 0.5
```

##### Keeping Location Columns

By default, location columns (crs, lat, lon) are dropped from the output CSV. Use `--keep-location` to retain them:

```bash
# Keep location columns in output
weather-tools local extract \
  --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --keep-location \
  --output data_with_coords.csv
```

#### Sample Output

```
Loading SILO data from: /Users/user/Developer/DATA/silo_grids
Variables: daily
Loading SILO dataset...  [####################################]  100%
Extracting data for location: lat=-27.5, lon=153.0
Date range: 2020-01-01 to 2020-12-31
✅ Data extracted successfully!
📊 Shape: 366 rows, 5 columns
💾 Saved to: /path/to/weather_data.csv

📋 Preview (first 5 rows):
        time  max_temp  min_temp  daily_rain  evap_syn
0 2020-01-01      30.5      21.7         0.1       7.6
1 2020-01-02      31.0      21.0         0.0       7.2
2 2020-01-03      31.1      20.2         0.0       7.7
3 2020-01-04      31.7      20.4         0.0       8.1
4 2020-01-05      32.1      19.8         0.0       8.1
```

## Output Format

The CLI generates CSV files with the following structure:

| Column | Description |
|--------|-------------|
| `time` | Date/time index (YYYY-MM-DD format) |
| `lat` | Latitude (nearest grid point to your coordinates) - **dropped by default** |
| `lon` | Longitude (nearest grid point to your coordinates) - **dropped by default** |
| `crs` | Coordinate reference system information - **dropped by default** |
| Weather variables | Columns for each requested variable (e.g., `max_temp`, `min_temp`, `daily_rain`, `evap_syn`) |

!!! note "Location Columns"
    By default, the `crs`, `lat`, and `lon` columns are dropped from the output CSV to reduce file size. Use the `--keep-location` flag if you need these columns in your output.

### Units

| Variable | Units | Description |
|----------|-------|-------------|
| `max_temp` | °C | Maximum temperature |
| `min_temp` | °C | Minimum temperature |
| `daily_rain` | mm | Daily rainfall |
| `evap_syn` | mm | Synthetic evaporation |
| `monthly_rain` | mm | Monthly rainfall |

## Data Requirements

### Expected Directory Structure

The CLI expects SILO data to be organized as follows:

```
~/DATA/silo_grids/
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

### Downloading SILO Data

To use this package, you need to download the netCDF files from SILO:

- **Data Source**: [SILO Gridded Data](https://www.longpaddock.qld.gov.au/silo/gridded-data/)
- **AWS S3 Index**: [Complete file list](https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/index.html)

## Tips and Best Practices

### Performance

- **Start small**: Test with short date ranges first (e.g., 1 month) before extracting large datasets
- **Use specific variables**: Only extract the variables you need to reduce processing time
- **Monitor disk space**: Large date ranges can generate substantial CSV files

### Date Formats

- Always use YYYY-MM-DD format for dates
- Ensure your date range falls within the available data years
- Use the `info` command to check available years for each variable

### Coordinate Selection

- The CLI automatically selects the nearest grid point to your coordinates
- SILO data has approximately 5km resolution
- Coordinates are returned in the output to show the actual grid point used

### Tolerance Parameter

The `--tolerance` parameter controls the maximum distance (in degrees) for nearest neighbor selection:

- **Default value**: 0.1 degrees (approximately 11 km)
- **Purpose**: Prevents selection of grid points that are too far from your requested coordinates
- **When to adjust**:
  - Use **smaller values** (e.g., 0.01) when you need strict spatial accuracy
  - Use **larger values** (e.g., 0.5) when working near data boundaries or with sparse grids
  - The selection will fail if no grid point exists within the tolerance distance

**Distance reference** (at mid-latitudes):
- 0.01 degrees ≈ 1.1 km
- 0.1 degrees ≈ 11 km (default)
- 0.5 degrees ≈ 55 km
- 1.0 degrees ≈ 111 km

**Example scenarios**:

```bash
# Strict tolerance for urban planning (must be very close)
weather-tools local extract --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --tolerance 0.01

# Permissive tolerance for regional analysis
weather-tools local extract --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --tolerance 0.5
```

### Error Handling

The CLI provides informative error messages for common issues:

- Invalid date formats
- Missing SILO data directories
- Coordinates outside the data extent
- Network connectivity issues (when using uvx with GitHub)

## Advanced Usage

### Shell Completion

Install shell completion for better command-line experience:

```bash
weather-tools --install-completion
```

### Batch Processing

Use shell scripting for batch processing multiple locations:

```bash
#!/bin/bash
locations=(
  "-27.5,153.0,brisbane"
  "-33.9,151.2,sydney"
  "-37.8,144.9,melbourne"
)

for location in "${locations[@]}"; do
  IFS=',' read -r lat lon name <<< "$location"
  weather-tools local extract --lat "$lat" --lon "$lon" \
    --start-date 2020-01-01 --end-date 2020-12-31 \
    --output "${name}_2020.csv"
done
```

### Integration with Python

Combine CLI output with Python analysis:

```python
import pandas as pd
import subprocess

# Extract data using CLI
subprocess.run([
    "weather-tools", "extract",
    "--lat", "-27.5", "--lon", "153.0",
    "--start-date", "2020-01-01", "--end-date", "2020-12-31",
    "--output", "analysis_data.csv"
])

# Load and analyze with pandas
df = pd.read_csv("analysis_data.csv")
df['time'] = pd.to_datetime(df['time'])
print(df.describe())
```