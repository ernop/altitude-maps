import rasterio
from pathlib import Path
import json

print("=== MINNESOTA DATA CHECK ===\n")

# Check clipped files
clipped = list(Path('data/clipped').glob('**/minnesota_clipped*.tif'))
print(f"Clipped files found: {len(clipped)}")
for p in clipped[:1]:
    with rasterio.open(p) as src:
        print(f"  File: {p.name}")
        print(f"  Shape: {src.shape} (H x W)")
        print(f"  Width x Height: {src.width} x {src.height}")
        print(f"  Aspect (W/H): {src.width / src.height:.3f}")
        print(f"  CRS: {src.crs}")
        print(f"  Bounds: {src.bounds}")

# Check processed files
print("\nProcessed files:")
processed = list(Path('data/processed').glob('**/minnesota_*.tif'))
print(f"Processed files found: {len(processed)}")
for p in processed[:1]:
    with rasterio.open(p) as src:
        print(f"  File: {p.name}")
        print(f"  Shape: {src.shape} (H x W)")
        print(f"  Width x Height: {src.width} x {src.height}")
        print(f"  Aspect (W/H): {src.width / src.height:.3f}")
        print(f"  CRS: {src.crs}")
        print(f"  Bounds: {src.bounds}")

# Check JSON
print("\nExported JSON:")
json_files = list(Path('generated/regions').glob('minnesota_*.json'))
for jf in json_files:
    if 'meta' not in jf.name:
        with open(jf, 'r') as f:
            data = json.load(f)
            print(f"  File: {jf.name}")
            print(f"  Width x Height: {data['width']} x {data['height']}")
            print(f"  Aspect (W/H): {data['width'] / data['height']:.3f}")
            print(f"  Bounds: {data['bounds']}")
            break


