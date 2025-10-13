# Command Line Interface (CLI)

The weather-tools package provides a powerful command-line interface for extracting weather data from SILO datasets. The CLI is built with [Typer](https://typer.tiangolo.com/) and provides an intuitive way to work with weather data.

## Installation

### Using uvx (Recommended)

The easiest way to use the CLI is with `uvx`, which automatically handles dependencies and isolation:

```bash
# Run directly from GitHub
uvx git+https://github.com/harryeslick/weather_tools.git --help

# Or run from local directory
uvx . --help
```

### Traditional Installation

```bash
# Install from local directory
pip install -e .

# Or install from GitHub
pip install git+https://github.com/harryeslick/weather_tools.git
```

After installation, the `weather-tools` command will be available system-wide.

## Quick Start

```bash
# Extract weather data for Brisbane for January 2020
weather-tools extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2020-01-31 --output brisbane_jan2020.csv
```

## Commands Overview

The CLI provides two main commands:

- **`info`** - Display information about available SILO data
- **`extract`** - Extract weather data for a specific location and date range

## Command Reference

### Global Options

```
Usage: weather-tools [OPTIONS] COMMAND [ARGS]...

Options:
  --install-completion    Install completion for the current shell
  --show-completion      Show completion for the current shell
  --help                 Show this message and exit
```

### `info` Command

Display information about available SILO data directories and files.

```bash
weather-tools info [OPTIONS]
```

#### Options

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `--silo-dir` | PATH | Path to SILO data directory | `~/Developer/DATA/silo_grids` |
| `--help` | | Show help message and exit | |

#### Example Usage

```bash
# Show info for default SILO directory
weather-tools info

# Show info for custom SILO directory
weather-tools info --silo-dir /path/to/my/silo/data
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

### `extract` Command

Extract weather data for a specific location and date range, saving results to CSV.

```bash
weather-tools extract [OPTIONS]
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
| `--silo-dir` | PATH | Path to SILO data directory | `~/Developer/DATA/silo_grids` |
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
weather-tools extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2020-12-31
```

##### Monthly Data

```bash
# Extract monthly rainfall data
weather-tools extract \
  --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --variables monthly \
  --output monthly_rainfall.csv
```

##### Specific Variables

```bash
# Extract only temperature data
weather-tools extract \
  --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --variables max_temp --variables min_temp \
  --output temperatures.csv
```

##### Custom Directory and Output

```bash
# Use custom SILO directory and output file
weather-tools extract \
  --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --silo-dir /path/to/my/silo/data \
  --output custom_weather_data.csv
```

##### Using Custom Tolerance

```bash
# Use stricter tolerance (0.01 degrees ≈ 1.1 km)
weather-tools extract \
  --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --tolerance 0.01

# Use more permissive tolerance (0.5 degrees ≈ 55 km)
weather-tools extract \
  --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --tolerance 0.5
```

##### Keeping Location Columns

By default, location columns (crs, lat, lon) are dropped from the output CSV. Use `--keep-location` to retain them:

```bash
# Keep location columns in output
weather-tools extract \
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
weather-tools extract --lat -27.5 --lon 153.0 \
  --start-date 2020-01-01 --end-date 2020-12-31 \
  --tolerance 0.01

# Permissive tolerance for regional analysis
weather-tools extract --lat -27.5 --lon 153.0 \
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
  weather-tools extract --lat "$lat" --lon "$lon" \
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