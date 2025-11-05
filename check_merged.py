import rasterio
from pathlib import Path

merged_file = Path('data/merged/srtm_90m/minnesota_wm97p24_s43p50_em89p49_n49p38_merged_90m.tif')

if merged_file.exists():
    with rasterio.open(merged_file) as src:
        print(f"=== MERGED FILE: {merged_file.name} ===")
        print(f"Shape: {src.shape} (H x W)")
        print(f"Width x Height: {src.width} x {src.height}")
        print(f"Aspect (W/H): {src.width / src.height:.3f}")
        print(f"CRS: {src.crs}")
        print(f"Bounds: {src.bounds}")
        print(f"  West: {src.bounds.left:.3f}")
        print(f"  South: {src.bounds.bottom:.3f}")
        print(f"  East: {src.bounds.right:.3f}")
        print(f"  North: {src.bounds.top:.3f}")
        print(f"  Width (deg): {src.bounds.right - src.bounds.left:.3f}")
        print(f"  Height (deg): {src.bounds.top - src.bounds.bottom:.3f}")
        
        # Read some elevation samples
        import numpy as np
        data = src.read(1)
        print(f"\nData statistics:")
        print(f"  Min: {np.nanmin(data):.1f}m")
        print(f"  Max: {np.nanmax(data):.1f}m")
        print(f"  Mean: {np.nanmean(data):.1f}m")
        print(f"  Non-NaN pixels: {np.count_nonzero(~np.isnan(data)):,}")
else:
    print(f"File not found: {merged_file}")



