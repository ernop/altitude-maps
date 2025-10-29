"""Debug Minnesota reprojection issue."""
import rasterio
import numpy as np
from rasterio.mask import mask as rasterio_mask
from rasterio.warp import calculate_default_transform, reproject, Resampling
import geopandas as gpd
from src.borders import BorderManager

print("=" * 70)
print("DEBUG MINNESOTA REPROJECTION")
print("=" * 70)

# Load raw data
raw_path = 'data/regions/minnesota.tif'
with rasterio.open(raw_path) as src:
    print(f"\n1. RAW DATA:")
    print(f"   CRS: {src.crs}")
    print(f"   Dimensions: {src.width} x {src.height}")
    print(f"   Nodata value: {src.nodata}")
    print(f"   Dtype: {src.dtypes}")
    elev = src.read(1)
    print(f"   Elevation range: {np.nanmin(elev):.1f}m to {np.nanmax(elev):.1f}m")
    print(f"   Array dtype: {elev.dtype}")

# Clip to state boundary
print(f"\n2. CLIPPING TO BOUNDARY...")
border_mgr = BorderManager("110m")
geom = border_mgr.get_state("United States of America", "Minnesota")
if geom is not None:
    geom = geom.geometry.iloc[0]
if geom is None:
    print("ERROR: Could not get Minnesota boundary")
    exit(1)

print(f"   Got boundary geometry")

with rasterio.open(raw_path) as src:
    print(f"   Applying mask...")
    out_image, out_transform = rasterio_mask(src, [geom], crop=True, filled=False)
    print(f"   Clipped dimensions: {out_image.shape}")
    print(f"   Clipped range: {np.nanmin(out_image):.1f}m to {np.nanmax(out_image):.1f}m")
    print(f"   Clipped dtype: {out_image.dtype}")
    out_meta = src.meta.copy()
    
    # Update metadata
    out_meta.update({
        "driver": "GTiff",
        "height": out_image.shape[1],
        "width": out_image.shape[2],
        "transform": out_transform
    })
    
    bounds = src.bounds
    avg_lat = (bounds.top + bounds.bottom) / 2
    print(f"\n3. REPROJECTING...")
    print(f"   Average latitude: {avg_lat:.1f}°")
    print(f"   Source CRS: {src.crs}")
    print(f"   Source nodata: {src.nodata}")
    print(f"   Meta nodata: {out_meta.get('nodata')}")
    
    # Reproject to EPSG:3857
    dst_crs = 'EPSG:3857'
    transform, width, height = calculate_default_transform(
        src.crs, dst_crs,
        out_meta['width'], out_meta['height'],
        *rasterio.transform.array_bounds(out_meta['height'], out_meta['width'], out_transform)
    )
    
    print(f"   Output dimensions: {width} x {height}")
    
    # Create reprojected array
    reprojected = np.empty((1, height, width), dtype=out_image.dtype)
    nodata_val = out_meta.get('nodata')
    print(f"   Initializing with nodata: {nodata_val}")
    reprojected.fill(nodata_val if nodata_val is not None else np.nan)
    print(f"   Initialized range: {np.nanmin(reprojected):.2f} to {np.nanmax(reprojected):.2f}")
    
    # Reproject
    print(f"   Reprojecting...")
    reproject(
        source=out_image,
        destination=reprojected,
        src_transform=out_transform,
        src_crs=src.crs,
        dst_transform=transform,
        dst_crs=dst_crs,
        resampling=Resampling.bilinear,
        src_nodata=nodata_val,
        dst_nodata=nodata_val
    )
    
    print(f"   Reprojected range: {np.nanmin(reprojected):.2f} to {np.nanmax(reprojected):.2f}")
    print(f"   Reprojected dtype: {reprojected.dtype}")
    
    # Check how many pixels are valid
    valid = ~np.isnan(reprojected[0])
    print(f"   Valid pixels: {np.sum(valid)} / {reprojected.size}")
    
    # Print some sample values
    print(f"\n4. SAMPLE VALUES:")
    print(f"   Min 10 values: {np.sort(reprojected[0].flatten())[:10]}")
    print(f"   Max 10 values: {np.sort(reprojected[0].flatten())[-10:]}")

print("\n" + "=" * 70)

