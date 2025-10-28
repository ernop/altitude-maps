import rasterio
import numpy as np
import json
from pathlib import Path

# Expected Nebraska bounds from usa_3dep.py
EXPECTED_BOUNDS = (-104.05, 40.00, -95.31, 43.00)  # west, south, east, north

print("=" * 70)
print("NEBRASKA SOURCE DATA")
print("=" * 70)

# Check source file in data/regions
with rasterio.open('data/regions/nebraska.tif') as src:
    print(f"\nSource: data/regions/nebraska.tif")
    print(f"  Width: {src.width}, Height: {src.height}")
    print(f"  Bounds: {src.bounds}")
    print(f"  Aspect ratio: {src.width/src.height:.3f}")

# Check if there are processed files
processed_files = [
    'data/processed/srtm_30m/nebraska.tif',
    'data/clipped/srtm_30m/nebraska.tif',
]

for proc_file in processed_files:
    proc_path = Path(proc_file)
    if proc_path.exists():
        print(f"\n" + "=" * 70)
        print(f"PROCESSED FILE: {proc_file}")
        print("=" * 70)
        with rasterio.open(proc_path) as src:
            print(f"  Width: {src.width}, Height: {src.height}")
            print(f"  Bounds: {src.bounds}")
            print(f"  Aspect ratio: {src.width/src.height:.3f}")
            
            # Check if square
            if src.width == src.height:
                print(f"  WARNING: This processed file is SQUARE!")

print("\n" + "=" * 70)
print("NEBRASKA EXPORTED JSON")
print("=" * 70)

with open('generated/regions/nebraska.json', 'r') as f:
    nebraska_data = json.load(f)
    print(f"\nExported: generated/regions/nebraska.json")
    print(f"  Width: {nebraska_data['width']}")
    print(f"  Height: {nebraska_data['height']}")
    print(f"  Aspect ratio: {nebraska_data['width']/nebraska_data['height']:.3f}")
    print(f"  Bounds: {nebraska_data.get('bounds', 'not specified')}")
