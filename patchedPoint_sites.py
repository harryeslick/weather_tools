# %%
"""
# Exploring SILO Patched Point Weather Stations

This notebook demonstrates how to search and visualize all available weather stations
in the SILO Patched Point dataset. The resulting interactive map shows station locations
colored by elevation and includes station numbers that can be used for data queries.

"""

# %%
# ## Setup and Imports

import numpy as np
import pandas as pd
from pathlib import Path
from pprint import pprint
import geopandas as gpd
import matplotlib.pyplot as plt
import os

from weather_tools.silo_api import SiloAPI
import folium
import matplotlib

# %%
# ## Search for All SILO Weather Stations
#
# The `search_stations()` method with the wildcard pattern "__" returns metadata
# for all available stations in the SILO Patched Point dataset. This includes:
# - Station codes (used for data queries)
# - Geographic coordinates (latitude/longitude)
# - Elevation above sea level
# - Station names and other metadata

silo_api = SiloAPI(log_level="INFO")
station_meta = silo_api.search_stations("__")

# Convert to GeoDataFrame for spatial operations and mapping
gdf = gpd.GeoDataFrame(
    station_meta,
    geometry=gpd.points_from_xy(station_meta.longitude, station_meta.latitude),
    crs=4326
)

print(f"Found {len(gdf)} weather stations in SILO database")

# %%
# ## Interactive Station Map
#
# This map displays all SILO weather stations colored by elevation (meters above sea level).
#
# **Map Features:**
# - Color scale: Lower elevations (coastal) appear green, higher elevations (mountains) appear brown
# - Click any marker to view station details including the station code
# - Use station codes from the popup to query weather data via the CLI or API
#
# **Example Query Using Station Code:**
# ```bash
# weather-tools silo patched-point --station 30043 \
#     --start-date 20230101 --end-date 20231231 --var R --var X
# ```

gdf.explore(
    "elevation",  # use elevation column for color
    cmap="terrain",
    marker_kwds=dict(radius=5, stroke=False, alpha=0.8),
)

# %%
