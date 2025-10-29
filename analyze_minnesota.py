"""Analyze Minnesota data through the processing pipeline."""
import rasterio
import numpy as np
import json
import gzip
import math

print("=" * 70)
print("MINNESOTA DATA ANALYSIS")
print("=" * 70)

# 1. Raw source data
print("\n1. RAW SOURCE DATA")
print("-" * 70)
try:
    with rasterio.open('data/regions/minnesota.tif') as src:
        elev = src.read(1)
        valid = ~np.isnan(elev)
        print(f"CRS: {src.crs}")
        print(f"Dimensions: {src.width} x {src.height}")
        print(f"Bounds: {src.bounds}")
        print(f"Elevation range: {np.nanmin(elev):.1f}m to {np.nanmax(elev):.1f}m")
        print(f"Mean elevation: {np.nanmean(elev):.1f}m")
        print(f"Valid pixels: {np.sum(valid):,} / {elev.size:,} ({100 * np.sum(valid) / elev.size:.1f}%)")
except Exception as e:
    print(f"Error reading raw source: {e}")

# 2. Clipped data
print("\n2. CLIPPED DATA")
print("-" * 70)
try:
    with rasterio.open('data/clipped/srtm_30m/minnesota_clipped_srtm_30m_v1.tif') as src:
        elev = src.read(1)
        valid = ~np.isnan(elev)
        print(f"CRS: {src.crs}")
        print(f"Dimensions: {src.width} x {src.height}")
        print(f"Bounds: {src.bounds}")
        print(f"Elevation range: {np.nanmin(elev):.1f}m to {np.nanmax(elev):.1f}m")
        print(f"Mean elevation: {np.nanmean(elev):.1f}m")
        print(f"Valid pixels: {np.sum(valid):,} / {elev.size:,} ({100 * np.sum(valid) / elev.size:.1f}%)")
except Exception as e:
    print(f"Error reading clipped data: {e}")

# 3. Processed data
print("\n3. PROCESSED DATA")
print("-" * 70)
try:
    with rasterio.open('data/processed/srtm_30m/minnesota_srtm_30m_2048px_v2.tif') as src:
        elev = src.read(1)
        valid = ~np.isnan(elev)
        print(f"CRS: {src.crs}")
        print(f"Dimensions: {src.width} x {src.height}")
        print(f"Bounds: {src.bounds}")
        print(f"Elevation range: {np.nanmin(elev):.1f}m to {np.nanmax(elev):.1f}m")
        print(f"Mean elevation: {np.nanmean(elev):.1f}m")
        print(f"Valid pixels: {np.sum(valid):,} / {elev.size:,} ({100 * np.sum(valid) / elev.size:.1f}%)")
except Exception as e:
    print(f"Error reading processed data: {e}")

# 4. Exported JSON
print("\n4. EXPORTED JSON")
print("-" * 70)
try:
    with gzip.open('generated/regions/minnesota.json.gz', 'rt') as f:
        data = json.load(f)
    
    elev = np.array(data['elevation'], dtype=np.float32)
    valid = ~np.isnan(elev)
    bounds = data['bounds']
    
    print(f"Dimensions: {data['width']} x {data['height']}")
    print(f"Bounds: {bounds}")
    print(f"Elevation range: {np.nanmin(elev):.1f}m to {np.nanmax(elev):.1f}m")
    print(f"Mean elevation: {np.nanmean(elev):.1f}m")
    print(f"Valid pixels: {np.sum(valid):,} / {elev.size:,} ({100 * np.sum(valid) / elev.size:.1f}%)")
    
    # Calculate aspect ratio
    lon_span = bounds['right'] - bounds['left']
    lat_span = bounds['top'] - bounds['bottom']
    avg_lat = (bounds['top'] + bounds['bottom']) / 2
    lon_km = lon_span * 111.32 * math.cos(math.radians(avg_lat))
    lat_km = lat_span * 111.32
    real_aspect = lon_km / lat_km
    data_aspect = data['width'] / data['height']
    print(f"Aspect ratio: {data_aspect:.2f}:1 (should be ~{real_aspect:.2f}:1)")
    print(f"Distortion: {data_aspect/real_aspect:.2f}x")
except Exception as e:
    print(f"Error reading JSON: {e}")

print("\n" + "=" * 70)

