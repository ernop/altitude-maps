"""Test GPXZ API to understand data sources and capabilities."""
import requests
import json
from pathlib import Path

settings = json.load(open('settings.json'))
api_key = settings['gpxz']['api_key']

# Test points in different regions
test_points = [
    (35.3, -120.8, "Morro Bay, CA"),
    (40.0, -100.0, "Kansas, USA"),
    (50.0, 10.0, "Germany"),
    (-35.0, 150.0, "Australia"),
    (60.0, 10.0, "Norway"),
]

print("Testing GPXZ data sources:")
print("=" * 60)

for lat, lon, location in test_points:
    try:
        r = requests.get(
            'https://api.gpxz.io/v1/elevation/point',
            params={'lat': lat, 'lon': lon},
            headers={'x-api-key': api_key},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            result = data.get('result', {})
            print(f"{location:20s} ({lat:6.1f}, {lon:7.1f}):")
            print(f"  Elevation: {result.get('elevation', 'N/A')}m")
            print(f"  Source: {result.get('data_source', 'unknown')}")
            print(f"  Resolution: {result.get('resolution', 'unknown')}m")
        else:
            print(f"{location:20s}: Error {r.status_code}")
    except Exception as e:
        print(f"{location:20s}: Error - {str(e)[:50]}")

print("\n" + "=" * 60)
print("GPXZ Limitations:")
print("- Maximum res_m for raster: 30m (does NOT support >100m)")
print("- Rate limit: 100 reqs/sec (as configured)")
print("- Useful for: High-resolution data (1m-30m)")
print("- NOT useful for: Coarse resolutions (>100m)")

