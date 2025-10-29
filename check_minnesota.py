"""Check Minnesota data aspect ratio and bounds."""
import json
import gzip
import math

# Load data
with gzip.open('generated/regions/minnesota.json.gz', 'rt') as f:
    data = json.load(f)

bounds = data['bounds']
lon_span = bounds['right'] - bounds['left']
lat_span = bounds['top'] - bounds['bottom']
avg_lat = (bounds['top'] + bounds['bottom']) / 2

# Calculate real-world distances
lon_km = lon_span * 111.32 * math.cos(math.radians(avg_lat))
lat_km = lat_span * 111.32
real_aspect = lon_km / lat_km

# Data aspect
data_aspect = data['width'] / data['height']

print(f"Minnesota Data Analysis")
print(f"=" * 50)
print(f"Geographic bounds:")
print(f"  Longitude: {bounds['left']:.2f}° to {bounds['right']:.2f}° (span: {lon_span:.2f}°)")
print(f"  Latitude: {bounds['bottom']:.2f}° to {bounds['top']:.2f}° (span: {lat_span:.2f}°)")
print(f"  Avg latitude: {avg_lat:.1f}°N")
print()
print(f"Real-world dimensions:")
print(f"  Width: {lon_km:.0f} km")
print(f"  Height: {lat_km:.0f} km")
print(f"  Geographic aspect ratio: {real_aspect:.2f}:1")
print()
print(f"Data dimensions:")
print(f"  Width: {data['width']} pixels")
print(f"  Height: {data['height']} pixels")
print(f"  Data aspect ratio: {data_aspect:.2f}:1")
print()
print(f"Distortion factor: {data_aspect/real_aspect:.2f}x")

