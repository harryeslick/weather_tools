"""
Example: Using geometry masking with SILO GeoTIFF data

This script demonstrates how to use the geometry_mask feature to mask pixels
outside a specific geometry when reading SILO Cloud-Optimized GeoTIFF files.
"""

import datetime

from shapely.geometry import Point, box

from weather_tools.silo_geotiff import construct_geotiff_daily_url, read_cog

# Example 1: Read data for a point with masking enabled (default)
print("Example 1: Point geometry with masking")
print("=" * 50)

point = Point(153.0, -27.5)  # Brisbane area
date = datetime.date(2023, 1, 15)
url = construct_geotiff_daily_url("daily_rain", date)

# Read with masking (default: use_mask=True)
data, profile = read_cog(url, geometry=point, use_mask=True)
print(f"Data type: {type(data)}")
print(f"Data shape: {data.shape}")
print(f"Masked values: {data.mask.sum()} out of {data.size} pixels")
print(f"Valid values: {(~data.mask).sum()}")
print()

# Example 2: Read data for a polygon with masking
print("Example 2: Polygon geometry with masking")
print("=" * 50)

# Small polygon around Brisbane
polygon = box(152.9, -27.6, 153.1, -27.4)
data_masked, profile = read_cog(url, geometry=polygon, use_mask=True)

print(f"Data type: {type(data_masked)}")
print(f"Data shape: {data_masked.shape}")
print(f"Masked values: {data_masked.mask.sum()} out of {data_masked.size} pixels")
print(f"Valid values: {(~data_masked.mask).sum()}")
print(f"Mean rainfall (valid pixels only): {data_masked.mean():.2f} mm")
print()

# Example 3: Read data without masking (use_mask=False)
print("Example 3: Same polygon without masking")
print("=" * 50)

data_unmasked, profile = read_cog(url, geometry=polygon, use_mask=False)
print(f"Data type: {type(data_unmasked)}")
print(f"Data shape: {data_unmasked.shape}")
print(f"No masking applied - all pixels included")
print()

# Example 4: Using with reduced resolution (overview level)
print("Example 4: Using overview level with masking")
print("=" * 50)

# Read at reduced resolution (4x smaller)
data_overview, profile = read_cog(url, geometry=polygon, overview_level=1, use_mask=True)
print(f"Data shape (overview level 1): {data_overview.shape}")
print(f"Data shape (full resolution): {data_masked.shape}")
print(f"Resolution reduction: {data_masked.size / data_overview.size:.1f}x")
print()

print("Done!")
