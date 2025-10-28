"""
Diagnostic script to check if Ohio data files are correctly processed.
"""
import rasterio
import numpy as np
from pathlib import Path

print('=' * 70)
print('OHIO DATA ANALYSIS')
print('=' * 70)

# Check raw file
raw_path = Path('data/raw/srtm_30m/ohio_bbox_30m.tif')
with rasterio.open(raw_path) as raw:
    raw_data = raw.read(1)
    raw_valid = ~np.isnan(raw_data) & (raw_data > -500)
    raw_valid_pct = np.sum(raw_valid) / raw_data.size * 100
    
    print(f'\n📦 RAW FILE (bbox download):')
    print(f'   Path: {raw_path}')
    print(f'   Dimensions: {raw.width} × {raw.height} pixels')
    print(f'   Bounds: {raw.bounds}')
    print(f'   CRS: {raw.crs}')
    print(f'   Valid data: {raw_valid_pct:.1f}%')
    print(f'   Pixel size: {raw.transform[0]:.10f} × {abs(raw.transform[4]):.10f} degrees')

# Check clipped file
clip_path = Path('data/clipped/srtm_30m/ohio_clipped_srtm_30m_v1.tif')
with rasterio.open(clip_path) as clip:
    clip_data = clip.read(1)
    clip_valid = ~np.isnan(clip_data) & (clip_data > -500)
    clip_valid_pct = np.sum(clip_valid) / clip_data.size * 100
    
    print(f'\n✂️  CLIPPED FILE (state boundary):')
    print(f'   Path: {clip_path}')
    print(f'   Dimensions: {clip.width} × {clip.height} pixels')
    print(f'   Bounds: {clip.bounds}')
    print(f'   Valid data: {clip_valid_pct:.1f}%')
    print(f'   Pixel size: {clip.transform[0]:.10f} × {abs(clip.transform[4]):.10f} degrees')
    
    # Check if bounds changed
    bounds_changed = (raw.bounds != clip.bounds)
    dims_changed = (raw.width != clip.width or raw.height != clip.height)
    
    print(f'\n🔍 CLIPPING ANALYSIS:')
    print(f'   Width changed: {raw.width} → {clip.width} (diff: {raw.width - clip.width} pixels)')
    print(f'   Height changed: {raw.height} → {clip.height} (diff: {raw.height - clip.height} pixels)')
    print(f'   Bounds changed: {bounds_changed}')
    if bounds_changed:
        print(f'      Left:   {raw.bounds.left:.6f} → {clip.bounds.left:.6f}')
        print(f'      Right:  {raw.bounds.right:.6f} → {clip.bounds.right:.6f}')
        print(f'      Top:    {raw.bounds.top:.6f} → {clip.bounds.top:.6f}')
        print(f'      Bottom: {raw.bounds.bottom:.6f} → {clip.bounds.bottom:.6f}')
    
    # Check if data was actually masked (holes inside)
    print(f'\n📊 DATA MASKING:')
    print(f'   Raw file valid pixels: {np.sum(raw_valid):,} ({raw_valid_pct:.1f}%)')
    print(f'   Clipped file valid pixels: {np.sum(clip_valid):,} ({clip_valid_pct:.1f}%)')
    print(f'   Data masked out: {np.sum(raw_valid) - np.sum(clip_valid):,} pixels')
    
    # Visual check - look at edges
    print(f'\n🔲 EDGE ANALYSIS (checking if borders were cropped):')
    # Check if top/bottom/left/right rows are mostly nodata
    top_row_valid = np.sum(clip_valid[0, :]) / clip.width * 100
    bottom_row_valid = np.sum(clip_valid[-1, :]) / clip.width * 100
    left_col_valid = np.sum(clip_valid[:, 0]) / clip.height * 100
    right_col_valid = np.sum(clip_valid[:, -1]) / clip.height * 100
    
    print(f'   Top edge valid: {top_row_valid:.1f}%')
    print(f'   Bottom edge valid: {bottom_row_valid:.1f}%')
    print(f'   Left edge valid: {left_col_valid:.1f}%')
    print(f'   Right edge valid: {right_col_valid:.1f}%')
    
    if all(v < 50 for v in [top_row_valid, bottom_row_valid, left_col_valid, right_col_valid]):
        print(f'   ⚠️  WARNING: Edges mostly empty - crop=True may not have worked!')
        print(f'   Expected: Edges should be ~100% valid if properly cropped to state')
    else:
        print(f'   ✅ Edges have data - suggests proper cropping')

print(f'\n' + '=' * 70)
print('CONCLUSION:')
print('=' * 70)

# The key insight: for states, we WANT significant empty space because the state
# boundary is irregular. The question is whether crop=True worked to minimize it.
print(f'Valid data in clipped file: {clip_valid_pct:.1f}%')
if clip_valid_pct < 50:
    print('⚠️  Very low valid data percentage - may indicate excessive bounding box')
elif clip_valid_pct > 90:
    print('✅ Very high valid data - state nearly fills its bounding box')
else:
    print('ℹ️  Moderate valid data - typical for irregular state boundaries')

print(f'\nDimension change: {raw.width}×{raw.height} → {clip.width}×{clip.height}')
if clip.width == raw.width and clip.height == raw.height:
    print('⚠️  Dimensions unchanged - crop=True may not have worked!')
else:
    print(f'✅ Dimensions changed by {raw.width*raw.height - clip.width*clip.height:,} pixels')

