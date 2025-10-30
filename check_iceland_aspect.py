"""Check Iceland's aspect ratio - real world vs data"""
import json
import math

# Load Iceland data
with open('generated/regions/iceland_srtm_30m_2048px_v2.json') as f:
    d = json.load(f)

bounds = d['bounds']
lon_span = bounds['right'] - bounds['left']
lat_span = bounds['top'] - bounds['bottom']
avg_lat = (bounds['top'] + bounds['bottom']) / 2

# Calculate real-world distances
# At high latitudes, longitude degrees are compressed
lon_km = lon_span * 111.32 * math.cos(math.radians(avg_lat))
lat_km = lat_span * 111.32

real_aspect = lon_km / lat_km
data_aspect = d['width'] / d['height']

print(f"Iceland Geographic Bounds:")
print(f"  West to East: {bounds['left']:.2f}deg to {bounds['right']:.2f}deg ({lon_span:.2f}deg span)")
print(f"  South to North: {bounds['bottom']:.2f}deg to {bounds['top']:.2f}deg ({lat_span:.2f}deg span)")
print(f"  Average latitude: {avg_lat:.1f}degN")
print()
print(f"Real-World Dimensions:")
print(f"  Width: {lon_km:.1f} km")
print(f"  Height: {lat_km:.1f} km")
print(f"  REAL aspect ratio: {real_aspect:.2f}:1")
print()
print(f"Data Dimensions:")
print(f"  Width: {d['width']} pixels")
print(f"  Height: {d['height']} pixels")
print(f"  DATA aspect ratio: {data_aspect:.2f}:1")
print()
print(f"Problem:")
print(f"  Distortion: {data_aspect/real_aspect:.2f}x TOO WIDE")
print(f"  Iceland should be {real_aspect:.2f}:1, but data shows {data_aspect:.2f}:1")
print()
print("Why? The GeoTIFF uses EPSG:4326 (lat/lon) projection where pixels")
print("represent equal ANGULAR spacing, not equal DISTANCE. At 65degN latitude,")
print("longitude degrees are compressed ~2.4x compared to latitude degrees.")

