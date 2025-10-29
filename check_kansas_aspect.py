#!/usr/bin/env python3
"""Quick check of Kansas aspect ratio."""

import json
import math

# Load Kansas JSON
with open('generated/regions/kansas.json') as f:
    data = json.load(f)

width = data['width']
height = data['height']
bounds = data['bounds']

# Calculate data aspect ratio
data_aspect = width / height

# Calculate geographic extent
lon_span = bounds['right'] - bounds['left']  # east - west
lat_span = bounds['top'] - bounds['bottom']  # north - south

# Geographic aspect ratio (degrees)
geo_aspect_deg = lon_span / lat_span

# For proper comparison, we need to account for latitude compression
# At Kansas's latitude (~38.5°N), longitude degrees are shorter than latitude degrees
avg_lat = (bounds['top'] + bounds['bottom']) / 2
lat_rad = math.radians(avg_lat)

# Real-world aspect ratio accounting for latitude
# Longitude distance = lon_degrees * cos(latitude) * meters_per_degree
# Latitude distance = lat_degrees * meters_per_degree  
# So aspect ratio = (lon_degrees * cos(latitude)) / lat_degrees
geo_aspect_real = (lon_span * math.cos(lat_rad)) / lat_span

print("KANSAS ASPECT RATIO CHECK")
print("=" * 60)
print(f"Data dimensions: {width} x {height} pixels")
print(f"Data aspect ratio: {data_aspect:.3f}:1")
print()
print(f"Geographic bounds:")
print(f"  Longitude: {bounds['left']:.3f}° to {bounds['right']:.3f}° (span: {lon_span:.3f}°)")
print(f"  Latitude: {bounds['bottom']:.3f}° to {bounds['top']:.3f}° (span: {lat_span:.3f}°)")
print(f"  Average latitude: {avg_lat:.3f}°")
print()
print(f"Geographic aspect ratio (degrees only): {geo_aspect_deg:.3f}:1")
print(f"Geographic aspect ratio (real-world, accounting for latitude): {geo_aspect_real:.3f}:1")
print()

# Check difference
difference = abs(data_aspect - geo_aspect_real)
percent_diff = (difference / geo_aspect_real) * 100

print(f"Difference: {difference:.3f} ({percent_diff:.1f}%)")
print()

if percent_diff < 1:
    print("✓ EXCELLENT - Aspect ratio is correct (<1% difference)")
elif percent_diff < 5:
    print("✓ GOOD - Aspect ratio is acceptable (<5% difference)")
elif percent_diff < 30:
    print("⚠ WARNING - Noticeable distortion (5-30% difference)")
else:
    print("✗ PROBLEM - Significant distortion (>30% difference)")
    print("  Kansas should appear wider than it is tall!")

print()
print("Expected: Kansas is a wide state, roughly 2.5x wider than tall")
print(f"Actual data shows: {data_aspect:.2f}x wider than tall")

