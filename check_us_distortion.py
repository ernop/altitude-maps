"""Check if US states have aspect ratio distortion like Iceland did"""
import json
import math
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Check a few representative US states
test_states = [
    'ohio',           # Mid-latitude (40°N)
    'tennessee',      # Southern (36°N) - explicitly mentioned in rules as "wide"
    'montana',        # Northern (47°N) - near the 45° threshold
    'florida'         # Southern (28°N)
]

print("US STATE ASPECT RATIO ANALYSIS")
print("="*70)

for state_id in test_states:
    json_files = list(Path('generated/regions').glob(f'{state_id}_*.json'))
    json_files = [f for f in json_files if not f.name.endswith('_meta.json')]
    
    if not json_files:
        print(f"\n{state_id.upper()}: No data file found")
        continue
    
    with open(json_files[0]) as f:
        d = json.load(f)
    
    # Get bounds and calculate real-world dimensions
    b = d['bounds']
    
    # Check if bounds are in lat/lon (EPSG:4326) or projected (EPSG:3857)
    if abs(b['left']) < 180 and abs(b['right']) < 180:
        # Lat/lon bounds
        lon_span = b['right'] - b['left']
        lat_span = b['top'] - b['bottom']
        avg_lat = (b['top'] + b['bottom']) / 2
        
        # Calculate real-world distances
        lon_km = lon_span * 111.32 * math.cos(math.radians(avg_lat))
        lat_km = lat_span * 111.32
        
        real_aspect = lon_km / lat_km
        data_aspect = d['width'] / d['height']
        distortion = data_aspect / real_aspect
        cos_lat = math.cos(math.radians(avg_lat))
        expected_distortion = 1.0 / cos_lat
        
        print(f"\n{state_id.upper()} (Latitude: {avg_lat:.1f}°N)")
        print(f"  Real dimensions: {lon_km:.0f}km × {lat_km:.0f}km = {real_aspect:.2f}:1")
        print(f"  Data dimensions: {d['width']}px × {d['height']}px = {data_aspect:.2f}:1")
        print(f"  Distortion factor: {distortion:.2f}x (expected: {expected_distortion:.2f}x)")
        
        if abs(distortion - 1.0) > 0.15:
            print(f"  ⚠️  DISTORTED by {(distortion-1)*100:.0f}%")
        else:
            print(f"  ✅ Correct proportions")
    else:
        # Already reprojected
        print(f"\n{state_id.upper()}: Already in projected coordinates (Web Mercator)")
        print(f"  Data: {d['width']}px × {d['height']}px = {d['width']/d['height']:.2f}:1")
        print(f"  ✅ Should have correct proportions")

print("\n" + "="*70)
print("\nCONCLUSION:")
print("If any states show distortion >15%, they need the same fix as Iceland.")

