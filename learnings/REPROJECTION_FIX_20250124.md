# Reprojection Fix for Latitude Distortion Correction

**Date:** January 24, 2025  
**Status:** ✅ RESOLVED  
**Related:** Aspect ratio preservation, EPSG:4326 distortion correction

## The Problem

Reprojecting data from EPSG:4326 (lat/lon) to EPSG:3857 (Web Mercator) to correct latitude distortion was causing:
1. **Data corruption** - millions of zero/negative elevation values appearing
2. **Loss of borders** - state boundaries becoming square/rectangular
3. **Visual artifacts** - regions showing as blue (water) where they shouldn't

Example: California had 773M pixels with zero or less elevation (62% of data corrupted)

## Root Cause Analysis

The bug was in the reprojection code in `src/pipeline.py::clip_to_boundary()`:

```python
# ❌ BUGGY CODE
reprojected = np.empty((1, height, width), dtype=out_image.dtype)
reproject(
    source=out_image,
    destination=reprojected,
    src_transform=out_transform,
    src_crs=src.crs,
    dst_transform=transform,
    dst_crs=dst_crs,
    resampling=Resampling.bilinear
)
```

**Two critical bugs:**

1. **Uninitialized array**: `np.empty()` creates an array with garbage/undefined values
2. **Missing nodata handling**: Not specifying `src_nodata` and `dst_nodata` meant invalid/masked areas couldn't be handled properly

When `rasterio_mask()` masks pixels outside boundaries with `filled=False`, those pixels become `NaN`. Without proper nodata handling, reprojection:
- Tried to interpolate from `NaN` pixels
- Produced garbage values where reconstruction was impossible
- Lost the boundary information

## The Fix

```python
# ✅ FIXED CODE
reprojected = np.empty((1, height, width), dtype=out_image.dtype)
reprojected.fill(out_meta.get('nodata', np.nan))  # Initialize with nodata

reproject(
    source=out_image,
    destination=reprojected,
    src_transform=out_transform,
    src_crs=src.crs,
    dst_transform=transform,
    dst_crs=dst_crs,
    resampling=Resampling.bilinear,
    src_nodata=out_meta.get('nodata'),  # CRITICAL
    dst_nodata=out_meta.get('nodata')   # CRITICAL
)
```

**Changes:**
1. Initialize array with nodata value before reprojection
2. Pass `src_nodata` so rasterio knows which source pixels to ignore
3. Pass `dst_nodata` so rasterio knows how to mark unprojected destination pixels

## Why Reprojection Is Needed

EPSG:4326 (WGS84 lat/lon) uses square pixels in **degrees**, not meters:
- Longitude degrees shrink toward poles by factor of `cos(latitude)`
- At Kansas (38.5°N): 1.28x distortion in longitude direction
- At Iceland (65°N): 2.37x distortion in longitude direction

Without reprojection:
- Kansas appears **27% too wide** (2.47:1 vs 1.94:1 correct ratio)
- Iceland appears **dramatically stretched** in one direction

**Solution**: Reproject to EPSG:3857 (Web Mercator) which uses meters for both axes, preserving real-world proportions.

## Results After Fix

### Kansas
- **Before**: 2.474:1 aspect ratio (27.6% too wide)
- **After**: 1.94:1 aspect ratio (correct)
- **Valid pixels**: 98.4% (properly preserved)

### Iceland  
- **Before**: Severely distorted at high latitude
- **After**: 1.467:1 aspect ratio (correct proportions)
- **Valid pixels**: 100% (all boundaries preserved)
- **Islands**: All 4 islands correctly captured

### California
- **Before**: 773M corrupted pixels with reprojection bug
- **After**: 42.8% valid pixels (correct - state has irregular boundaries)
- **Borders**: State shape perfectly preserved

## Key Learnings

### 1. Always Initialize Arrays Before Reprojection

```python
# ✅ DO: Fill with nodata
reprojected = np.empty(shape, dtype=dtype)
reprojected.fill(nodata_value)

# ❌ DON'T: Leave uninitialized
reprojected = np.empty(shape, dtype=dtype)  # Contains garbage!
```

### 2. Always Specify Nodata Parameters

```python
# ✅ DO: Explicit nodata handling
reproject(..., src_nodata=src_nodata, dst_nodata=dst_nodata)

# ❌ DON'T: Omit nodata parameters
reproject(...)  # No nodata info = data corruption
```

### 3. Reprojection is Essential for Mid-High Latitudes

- Any region >5° from equator needs reprojection
- Distortion increases dramatically with latitude
- Web Mercator (EPSG:3857) is appropriate for most regions
- Polar regions (>85°) may need polar stereographic (EPSG:3413/3031)

### 4. Validation Catches Issues

The export validation now ensures:
- Valid pixels > reasonable threshold
- Correct aspect ratios after reprojection
- Bounds properly transformed back to EPSG:4326 for viewer

## Related Files

- `src/pipeline.py` - Fixed reprojection code (lines 211-225)
- `.cursorrules` - Updated with reprojection pattern (lines 103-108)
- `tech/DATA_PRINCIPLES.md` - Documents aspect ratio requirements

## Pattern for Future Reprojection

When adding reprojection anywhere in the pipeline:

1. **Detect need**: Check latitude to determine if distortion is significant
2. **Initialize array**: Fill with nodata before reprojecting
3. **Pass nodata params**: Always specify `src_nodata` and `dst_nodata`
4. **Transform bounds**: Convert back to EPSG:4326 for consistent viewer input
5. **Validate**: Check pixel validity and aspect ratio after reprojection

## References

- Issue discovered: January 24, 2025 (CA reprocessing showing data corruption)
- Fix applied: Same day (initialize array + nodata parameters)
- Testing: Kansas, Iceland, California all validated
- Documented: `.cursorrules` updated with critical reprojection pattern

