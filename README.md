# Weather Tools

[![Deploy MkDocs GitHub Pages](https://github.com/harryeslick/weather_tools/actions/workflows/mkdocs.yml/badge.svg)](https://github.com/harryeslick/weather_tools/actions/workflows/mkdocs.yml)

Python tools for accessing and processing Australian SILO climate data.

**Features:**

- SILO API client for PatchedPoint (station) and DataDrill (gridded) datasets
- Download and work with SILO Cloud-Optimized GeoTIFF (COG) files with spatial subsetting
- Download and process SILO NetCDF files locally
- Command-line interface for quick data access
- Met.no API client for weather forecasts with SILO integration

## Quick Start

### Installation

```bash
# Install from GitHub using uv
uv pip install git+https://github.com/harryeslick/weather_tools.git

# Or run directly without installation
uvx --from git+https://github.com/harryeslick/weather_tools.git weather-tools --help
```

### CLI Usage

```bash
# Set API key (your email address)
export SILO_API_KEY="your.email@example.com"

# Query station data
weather-tools silo patched-point --station 30043 \
    --start-date 20230101 --end-date 20230131 \
    --var R --var X --output weather.csv

# Search for stations
weather-tools silo search --name Brisbane --state QLD

# Download SILO NetCDF files
weather-tools local download --var daily --start-year 2020 --end-year 2023

# Extract local data for a location
weather-tools local extract --lat -27.5 --lon 153.0 \
    --start-date 2020-01-01 --end-date 2020-12-31 \
    --output brisbane.csv
```

📖 **[Complete CLI Guide →](CLI_README.md)** - Comprehensive CLI documentation with detailed examples

### Python API Usage

```python
from weather_tools.silo_api import SiloAPI

# Initialize API client
api = SiloAPI()  # Uses SILO_API_KEY environment variable

# Get station data as DataFrame
df = api.get_station_data(
    station_code="30043",
    start_date="20230101",
    end_date="20230131",
    variables=["rainfall", "max_temp", "min_temp"]
)

# Search for stations
stations = api.search_stations(name_fragment="Brisbane", state="QLD")
print(stations[['name', 'station_code', 'latitude', 'longitude']])
```

📖 **[Complete Python API Guide →](PY_README.md)** - Comprehensive Python API documentation with examples

## What is SILO?

SILO (Scientific Information for Land Owners) provides Australian climate data from 1889 onwards with two dataset types:

- **PatchedPoint**: Station-based observational data with infilled gaps (ideal for specific weather station locations)
- **DataDrill**: Gridded data at 0.05° × 0.05° resolution (~5km) covering all of Australia

Data is available via:

- **API**: Real-time queries (requires API key = email address)
- **NetCDF Files**: Bulk downloads from AWS S3 for offline processing
- **GeoTIFF Files**: Cloud-optimized format for efficient spatial subsetting

## Climate Variables

**Common Variables:**

- Rainfall (daily/monthly)
- Maximum/minimum temperature
- Evaporation (pan/synthetic)
- Solar radiation
- Vapour pressure
- Wind, humidity, pressure

**Variable Codes:**

- **API**: Single letters (R=rainfall, X=max_temp, N=min_temp, etc.)
- **Local files**: Full names (daily_rain, max_temp, min_temp, etc.)

See [full documentation](https://harryeslick.github.io/weather_tools/silo_api/#climate-variables) for complete variable list.

## Documentation

📚 **[Full Documentation](https://harryeslick.github.io/weather_tools/)** - Complete guides, API reference, and examples

**Quick Links:**

- [CLI Guide](CLI_README.md) - Command-line interface documentation
- [Python API Guide](PY_README.md) - Python library documentation
- [SILO API Reference](https://harryeslick.github.io/weather_tools/silo_api/)
- [Examples & Tutorials](https://harryeslick.github.io/weather_tools/notebooks/example/)

## License

This project is licensed under the MIT License.

## Data License & Attribution

### SILO

**SILO climate data** are provided under the [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) license.

**Data Provider:**
SILO is managed by the Climate Projections and Services team within Queensland Treasury, Queensland Government.

**Data Sources:**
SILO datasets are constructed from observational data obtained from the Australian Bureau of Meteorology (BoM) and other suppliers.

**Citation:**
Jeffrey, S.J., Carter, J.O., Moodie, K.B. and Beswick, A.R. (2001). Using spatial interpolation to construct a comprehensive archive of Australian climate data. *Environmental Modelling & Software*, 16(4), 309-330.

**Website:**
<https://www.longpaddock.qld.gov.au/silo/>

**Important Notes:**

- SILO uses mathematical interpolation to construct spatial grids and infill gaps in time series
- Users should understand the implications and accuracy of using interpolated data

### Met.no Weather Forecast Data License & Attribution

**Weather forecast data** from met.no are provided under dual licenses:
- [Norwegian Licence for Open Government Data (NLOD) 2.0](https://data.norge.no/nlod/en/2.0)
- [Creative Commons 4.0 BY International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)

**Data Provider:**
The Norwegian Meteorological Institute (MET Norway)

**Attribution:**
Weather forecast data is based on data from [MET Norway](https://www.met.no/en).

**API Documentation:**
<https://api.met.no/weatherapi/locationforecast/2.0/documentation>

**Terms of Service:**
<https://developer.yr.no/doc/TermsOfService/>

**Important Notes:**

- Users must ensure they comply with the Met.no Terms of Service.
- Weather forecast data is retrieved in real-time from the met.no API
- Forecast data should be considered a supplement to SILO historical observations


## Acknowledgments

This software package is not affiliated with or endorsed by the Queensland Government, Queensland Treasury, the Australian Bureau of Meteorology, or the Norwegian Meteorological Institute. It is an independent tool for accessing and processing publicly available climate data.

We acknowledge:

- The SILO team (Queensland Government) for providing freely accessible, high-quality historical climate data for Australia
- The Norwegian Meteorological Institute (MET Norway) for providing freely accessible global weather forecast data through their API
