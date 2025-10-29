"""Review Connecticut's data at all stages."""
import rasterio
import numpy as np
import json
import gzip
from pathlib import Path

print("=" * 70)
print("CONNECTICUT DATA REVIEW")
print("=" * 70)

# 1. Raw source
print("\n1. RAW SOURCE")
print("-" * 70)
raw_path = Path("data/regions/connecticut.tif")
if raw_path.exists():
    with rasterio.open(raw_path) as src:
        elev = src.read(1)
        print(f"CRS: {src.crs}")
        print(f"Dimensions: {src.width}x{src.height}")
        print(f"Elevation range: {np.nanmin(elev):.1f}m to {np.nanmax(elev):.1f}m")
        print(f"Mean: {np.nanmean(elev):.1f}m")

# 2. Clipped file
print("\n2. CLIPPED FILE")
print("-" * 70)
clipped_path = Path("data/clipped/srtm_30m/connecticut_clipped_srtm_30m_v1.tif")
if clipped_path.exists():
    with rasterio.open(clipped_path) as src:
        elev = src.read(1)
        print(f"CRS: {src.crs}")
        print(f"Dimensions: {src.width}x{src.height}")
        print(f"Elevation range: {np.nanmin(elev):.1f}m to {np.nanmax(elev):.1f}m")
        print(f"Mean: {np.nanmean(elev):.1f}m")

# 3. Exported JSON
print("\n3. EXPORTED JSON")
print("-" * 70)
json_path = Path("generated/regions/connecticut_srtm_30m_2048px_v2.json.gz")
if json_path.exists():
    with gzip.open(json_path, 'rt') as f:
        data = json.load(f)
    elev = np.array(data['elevation'], dtype=np.float32)
    print(f"Dimensions: {data['width']}x{data['height']}")
    print(f"Elevation range: {np.nanmin(elev):.1f}m to {np.nanmax(elev):.1f}m")
    print(f"Mean: {np.nanmean(elev):.1f}m")
    print(f"Bounds: {data['bounds']}")

print("\n" + "=" * 70)

