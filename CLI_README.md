# Weather Tools CLI

A command-line interface for extracting weather data from SILO datasets.

## Installation

First, install the required dependencies:

```bash
pip install typer
```

Then install the weather_tools package in development mode:

```bash
cd /path/to/weather_tools
pip install -e .
```

## Usage

The CLI provides two main commands: `extract` and `info`.

### Extract Weather Data

Extract weather data for a specific location and date range:

```bash
weather-tools extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2025-01-01 --output weather.csv
```

#### Parameters:

- `--lat`: Latitude coordinate (required)
- `--lon`: Longitude coordinate (required)  
- `--start-date`: Start date in YYYY-MM-DD format (required)
- `--end-date`: End date in YYYY-MM-DD format (required)
- `--output`: Output CSV filename (default: "weather_data.csv")
- `--variables`: Weather variables to extract. Options:
  - `daily` (default): Extracts max_temp, min_temp, daily_rain, evap_syn
  - `monthly`: Extracts monthly_rain
  - Individual variables: specify as multiple options, e.g., `--variables max_temp --variables min_temp`
- `--silo-dir`: Path to SILO data directory (default: ~/Developer/DATA/silo_grids)

#### Examples:

1. Basic extraction with default settings:
```bash
weather-tools extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2025-01-01
```

2. Extract monthly data:
```bash
weather-tools extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2025-01-01 --variables monthly --output monthly_data.csv
```

3. Extract specific variables:
```bash
weather-tools extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2025-01-01 --variables max_temp --variables min_temp
```

4. Use custom SILO directory:
```bash
weather-tools extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2025-01-01 --silo-dir /path/to/silo/data
```

### Get Dataset Information

Display information about available SILO data:

```bash
weather-tools info
```

This command shows:
- The SILO data directory path
- Available variable directories
- Number of files in each directory
- Year range for each variable

You can also specify a custom SILO directory:

```bash
weather-tools info --silo-dir /path/to/silo/data
```

## Expected Data Structure

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

## Output

The CLI will output a CSV file containing:
- `time`: Date/time index
- `lat`: Latitude coordinate (nearest to specified location)
- `lon`: Longitude coordinate (nearest to specified location)
- Weather variable columns (e.g., `max_temp`, `min_temp`, `daily_rain`, `evap_syn`)

The CSV will include all available data points within the specified date range for the nearest grid point to your coordinates.

## Help

Use `--help` with any command to see detailed usage information:

```bash
weather-tools --help
weather-tools extract --help
weather-tools info --help
```