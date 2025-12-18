# `weather-tools`

CLI tool for extracting weather data from SILO datasets (local netCDF files or API)

**Usage**:

```console
$ weather-tools [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `-v, --version`: Show version and exit
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `silo`: Query SILO API directly (requires API key)
* `local`: Work with local SILO netCDF files
* `metno`: Query met.no forecast API for Australian...
* `geotiff`: Work with SILO Cloud-Optimized GeoTIFF files

## `weather-tools silo`

Query SILO API directly (requires API key)

**Usage**:

```console
$ weather-tools silo [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `patched-point`: Query SILO PatchedPoint dataset...
* `data-drill`: Query SILO DataDrill dataset (gridded data).
* `search`: Search for SILO stations by name or find...

### `weather-tools silo patched-point`

Query SILO PatchedPoint dataset (station-based data).

Format is auto-detected from output filename extension:
- .csv → csv format
- .json → json format  
- .apsim → apsim format
- .txt → standard format

Use &#x27;weather-tools silo search&#x27; to find station codes by name.

Examples:
    # Get rainfall and temperature for Brisbane Aero (format auto-detected)
    weather-tools silo patched-point --station 30043 \
        --start-date 2023-01-01 --end-date 2023-01-31 \
        --var rainfall --var max_temp --var min_temp --output data.csv
    
    # Get all variables in APSIM format
    weather-tools silo patched-point --station 30043 \
        --start-date 2023-01-01 --end-date 2023-01-31 \
        --output data.apsim
        
    # Force specific format (extension will be corrected)
    weather-tools silo patched-point --station 30043 \
        --start-date 2023-01-01 --end-date 2023-01-31 \
        --format json --output data.json

**Usage**:

```console
$ weather-tools silo patched-point [OPTIONS]
```

**Options**:

* `--station TEXT`: BOM station code (e.g., &#x27;30043&#x27; for Brisbane Aero)  [required]
* `--start-date TEXT`: Start date (YYYY-MM-DD)  [required]
* `--end-date TEXT`: End date (YYYY-MM-DD)  [required]
* `--format TEXT`: Output format: csv, json, apsim, standard (auto-detected from filename if not specified)
* `--var TEXT`: Climate variables: daily_rain, monthly_rain, max_temp, min_temp, vp, vp_deficit, rh_tmax, rh_tmin, mslp, evap_pan, evap_syn, evap_comb, evap_morton_lake, radiation, et_short_crop, et_tall_crop, et_morton_actual, et_morton_potential, et_morton_wet
* `-o, --output TEXT`: Output filename
* `--api-key TEXT`: SILO API key (email address)  [env var: SILO_API_KEY]
* `--enable-cache / --no-enable-cache`: Enable response caching  [default: no-enable-cache]
* `--log-level TEXT`: Logging level for SILO client (e.g. INFO, DEBUG, WARNING)  [default: INFO]
* `--help`: Show this message and exit.

### `weather-tools silo data-drill`

Query SILO DataDrill dataset (gridded data).

Examples:
    # Get rainfall for a specific location
    weather-tools silo data-drill --latitude -27.5 --longitude 151.0 \
        --start-date 2023-01-01 --end-date 2023-01-31 \
        --var rainfall --output data.csv
    
    # Get all variables for a location
    weather-tools silo data-drill --latitude -27.5 --longitude 151.0 \
        --start-date 2023-01-01 --end-date 2023-01-31 \
        --format alldata --output data.txt

**Usage**:

```console
$ weather-tools silo data-drill [OPTIONS]
```

**Options**:

* `--latitude FLOAT`: Latitude in decimal degrees (-44 to -10)  [required]
* `--longitude FLOAT`: Longitude in decimal degrees (113 to 154)  [required]
* `--start-date TEXT`: Start date (YYYY-MM-DD)  [required]
* `--end-date TEXT`: End date (YYYY-MM-DD)  [required]
* `--format TEXT`: Output format: csv, json, apsim, alldata, standard  [default: csv]
* `--var TEXT`: Climate variables: daily_rain, monthly_rain, max_temp, min_temp, vp, vp_deficit, rh_tmax, rh_tmin, mslp, evap_pan, evap_syn, evap_comb, evap_morton_lake, radiation, et_short_crop, et_tall_crop, et_morton_actual, et_morton_potential, et_morton_wet
* `-o, --output TEXT`: Output filename
* `--api-key TEXT`: SILO API key (email address)  [env var: SILO_API_KEY]
* `--enable-cache / --no-enable-cache`: Enable response caching  [default: no-enable-cache]
* `--log-level TEXT`: Logging level for SILO client (e.g. INFO, DEBUG, WARNING)  [default: INFO]
* `--help`: Show this message and exit.

### `weather-tools silo search`

Search for SILO stations by name or find nearby stations.

Examples:
    # Search by name
    weather-tools silo search --name Brisbane

    # Search by name and filter by state
    weather-tools silo search --name Brisbane --state QLD

    # Find nearby stations
    weather-tools silo search --station 30043 --radius 50

    # Get station details
    weather-tools silo search --station 30043 --details

**Usage**:

```console
$ weather-tools silo search [OPTIONS]
```

**Options**:

* `--name TEXT`: Search for stations by name fragment (e.g., &#x27;Brisbane&#x27;)
* `--station TEXT`: Station code for nearby search or details lookup
* `--radius INTEGER`: Search radius in km (for nearby search)
* `--state [QLD|NSW|VIC|TAS|SA|WA|NT|ACT]`: Filter by state (QLD, NSW, VIC, TAS, SA, WA, NT, ACT)
* `--details / --no-details`: Get detailed info for a specific station  [default: no-details]
* `--api-key TEXT`: SILO API key (email address)  [env var: SILO_API_KEY]
* `-o, --output TEXT`: Output filename
* `--log-level TEXT`: Logging level for SILO client (e.g. INFO, DEBUG, WARNING)  [default: INFO]
* `--help`: Show this message and exit.

## `weather-tools local`

Work with local SILO netCDF files

**Usage**:

```console
$ weather-tools local [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `extract`: Extract weather data from local netCDF...
* `info`: Display information about available local...
* `download`: Download SILO gridded NetCDF files from...

### `weather-tools local extract`

Extract weather data from local netCDF files for a specific location and date range.

Example:
    weather-tools local extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2025-01-01 --output weather.csv

**Usage**:

```console
$ weather-tools local extract [OPTIONS]
```

**Options**:

* `--lat FLOAT`: Latitude coordinate  [required]
* `--lon FLOAT`: Longitude coordinate  [required]
* `--start-date TEXT`: Start date (YYYY-MM-DD format)  [required]
* `--end-date TEXT`: End date (YYYY-MM-DD format)  [required]
* `--output TEXT`: Output CSV filename  [default: weather_data.csv]
* `--variables TEXT`: Weather variables to extract. Use &#x27;daily&#x27; or &#x27;monthly&#x27; for presets, or specify individual variables
* `--silo-dir PATH`: Path to SILO data directory
* `--tolerance FLOAT`: Maximum distance (in degrees) for nearest neighbor selection  [default: 0.1]
* `--keep-location / --no-keep-location`: Keep location columns (crs, lat, lon) in output CSV  [default: no-keep-location]
* `--help`: Show this message and exit.

### `weather-tools local info`

Display information about available local SILO data.

**Usage**:

```console
$ weather-tools local info [OPTIONS]
```

**Options**:

* `--silo-dir PATH`: Path to SILO data directory
* `--help`: Show this message and exit.

### `weather-tools local download`

Download SILO gridded NetCDF files from AWS S3.

Files are organized in the same structure expected by &#x27;weather-tools local extract&#x27;:
    output_dir/
    ├── daily_rain/
    │   ├── 2020.daily_rain.nc
    │   └── 2021.daily_rain.nc
    ├── max_temp/
    │   └── ...
    └── ...

By default, existing files are skipped. Use --force to re-download.

Examples:
    # Download daily variables for 2020-2023
    weather-tools local download --var daily --start-year 2020 --end-year 2023

    # Download specific variables
    weather-tools local download --var daily_rain --var max_temp \
        --start-year 2022 --end-year 2023

    # Download to custom directory
    weather-tools local download --var monthly \
        --start-year 2020 --end-year 2023 \
        --silo-dir /data/silo_grids

    # Force re-download existing files
    weather-tools local download --var daily_rain \
        --start-year 2023 --end-year 2023 --force

**Usage**:

```console
$ weather-tools local download [OPTIONS]
```

**Options**:

* `--start-year INTEGER`: First year to download (inclusive)  [required]
* `--end-year INTEGER`: Last year to download (inclusive)  [required]
* `--var [daily_rain|monthly_rain|max_temp|min_temp|vp|vp_deficit|rh_tmax|rh_tmin|mslp|evap_pan|evap_syn|evap_comb|evap_morton_lake|radiation|et_short_crop|et_tall_crop|et_morton_actual|et_morton_potential|et_morton_wet|wind_speed|wind_speed_max|cloud_fraction|weather_symbol]`: Variable names (daily_rain, max_temp, etc.) or presets (daily, monthly). Can specify multiple.
* `--silo-dir PATH`: Output directory for downloaded files
* `--force / --no-force`: Overwrite existing files  [default: no-force]
* `--timeout INTEGER`: Download timeout in seconds  [default: 600]
* `--help`: Show this message and exit.

## `weather-tools metno`

Query met.no forecast API for Australian locations

**Usage**:

```console
$ weather-tools metno [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `forecast`: Get met.no weather forecast for an...
* `merge`: Merge SILO historical data with met.no...
* `info`: Display information about the met.no API...

### `weather-tools metno forecast`

Get met.no weather forecast for an Australian location.

Retrieves up to 9 days of forecast data from met.no&#x27;s locationforecast API.
Daily summaries are automatically aggregated from hourly forecasts.

Example:
    weather-tools metno forecast --lat -27.5 --lon 153.0 --days 7 --output brisbane_forecast.csv

**Usage**:

```console
$ weather-tools metno forecast [OPTIONS]
```

**Options**:

* `--lat FLOAT`: Latitude coordinate (-9 to -44 for Australia)  [required]
* `--lon FLOAT`: Longitude coordinate (113 to 154 for Australia)  [required]
* `--days INTEGER`: Number of forecast days (1-9)  [default: 7]
* `--output TEXT`: Output CSV filename (optional)
* `--format-silo / --no-format-silo`: Convert to SILO column names  [default: format-silo]
* `--user-agent TEXT`: Custom User-Agent for met.no API
* `--help`: Show this message and exit.

### `weather-tools metno merge`

Merge SILO historical data with met.no forecast data.

Combines historical observations from SILO DataDrill API with met.no forecast data
for seamless downstream analysis.

Example:
    weather-tools metno merge --lat -27.5 --lon 153.0 \
        --start-date 2023-01-01 --end-date 2023-12-31 \
        --forecast-days 7 --output combined_weather.csv

**Usage**:

```console
$ weather-tools metno merge [OPTIONS]
```

**Options**:

* `--lat FLOAT`: Latitude coordinate (-9 to -44 for Australia)  [required]
* `--lon FLOAT`: Longitude coordinate (113 to 154 for Australia)  [required]
* `--start-date TEXT`: Historical data start date (YYYY-MM-DD)  [required]
* `--end-date TEXT`: Historical data end date (YYYY-MM-DD)  [required]
* `--output TEXT`: Output CSV filename  [required]
* `--forecast-days INTEGER`: Number of forecast days to append (1-9)  [default: 7]
* `--api-key TEXT`: SILO API key (email address)  [env var: SILO_API_KEY]
* `--fill-missing / --no-fill-missing`: Fill missing SILO variables with estimates  [default: no-fill-missing]
* `--enable-cache / --no-enable-cache`: Enable response caching for SILO API  [default: no-enable-cache]
* `--user-agent TEXT`: Custom User-Agent for met.no API
* `--log-level TEXT`: Logging level for SILO client (e.g. INFO, DEBUG, WARNING)  [default: INFO]
* `--help`: Show this message and exit.

### `weather-tools metno info`

Display information about the met.no API and variable mappings.

Shows available variables, data coverage, and API details.

**Usage**:

```console
$ weather-tools metno info [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `weather-tools geotiff`

Work with SILO Cloud-Optimized GeoTIFF files

**Usage**:

```console
$ weather-tools geotiff [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `download`: Download SILO GeoTIFF files for a date...

### `weather-tools geotiff download`

Download SILO GeoTIFF files for a date range, optionally clipped to geometry/bbox.

Files are organized in the structure:
    output_dir/
    ├── daily_rain/
    │   ├── 2023/
    │   │   ├── 20230101.daily_rain.tif
    │   │   └── 20230102.daily_rain.tif
    │   └── ...
    └── ...

By default, existing files are skipped. Use --force to re-download.

Examples:
    # Download entire files for daily rainfall
    weather-tools geotiff download \
        --var daily_rain --var max_temp \
        --start-date 2023-01-01 --end-date 2023-01-31

    # Download with bounding box clipping
    weather-tools geotiff download \
        --var daily_rain \
        --start-date 2023-01-01 --end-date 2023-01-31 \
        --bbox 150.5 -28.5 154.0 -26.0

    # Download with geometry file clipping
    weather-tools geotiff download \
        --var daily_rain \
        --start-date 2023-01-01 --end-date 2023-01-31 \
        --geometry region.geojson

**Usage**:

```console
$ weather-tools geotiff download [OPTIONS]
```

**Options**:

* `--start-date TEXT`: Start date (YYYY-MM-DD format)  [required]
* `--end-date TEXT`: End date (YYYY-MM-DD format)  [required]
* `--var TEXT`: Variable names (daily_rain, max_temp, etc.) or presets (daily, monthly). Can specify multiple.
* `--output-dir PATH`: Output directory for downloaded GeoTIFF files
* `--bbox FLOAT`: Bounding box: min_lon min_lat max_lon max_lat (4 values, mutually exclusive with --geometry)
* `--geometry PATH`: Path to GeoJSON file with Polygon for clipping (mutually exclusive with --bbox)
* `--force / --no-force`: Overwrite existing files  [default: no-force]
* `--help`: Show this message and exit.
