# Smart Resolution Selection - Design Document

**Date:** 2025-01-09  
**Status:** Implemented  
**Purpose:** Avoid downloading unnecessary high-resolution data when downsampling will hide the extra detail.

## Problem

Currently, we always download 30m SRTM/COP30 data, even when the final visible pixel size (after downsampling to 2048px) will be >90m. This wastes:
- Download time
- Storage space  
- Processing time

Example:
- Alaska: ~1.4M km², downsampled to 2048px -> visible pixels are ~1.8km each
- Using 30m vs 90m doesn't change what users see (90m is still 20x more detailed!)

## Solution: Calculate Visible Pixel Size Before Download

Calculate the final visible pixel size in real-world meters, then suggest the optimal source dataset:

```
Visible Pixel Size = (real_world_width_meters) / target_pixels

If Visible Pixel Size >= 180m:
  Suggest 90m dataset (90m input provides 2.0x oversampling - Nyquist safe)
Else if Visible Pixel Size >= 90m:
  Suggest 30m dataset (90m would be marginal quality, 30m is safer)
Else:
  Suggest 30m dataset (users can zoom in and see finer detail)
```

**Quality Threshold Rationale**: 
- **>= 180m visible**: 90m input provides 2.0x+ oversampling -> guaranteed quality (Nyquist safe)
- **90-180m visible**: 90m input gives 1.0-2.0x -> marginal to acceptable, recommend 30m for safety
- **< 90m visible**: 30m input clearly needed

**Threshold selection**: Using 180m (2x) instead of 135m (1.5x) for guaranteed quality without artifacts. The 1.5x factor was a practical compromise, but without empirical testing we can't be certain it's safe.

See `learnings/RESAMPLING_QUALITY_THRESHOLDS.md` for detailed technical analysis.

## Implementation Plan

### 1. Helper Function: Calculate Visible Pixel Size

Location: `ensure_region.py`

```python
def calculate_visible_pixel_size(bounds, target_pixels):
    """Calculate final visible pixel size in meters after downsampling.
    
    Args:
        bounds: (west, south, east, north) in degrees
        target_pixels: Target output dimension (e.g., 2048)
    
    Returns:
        dict with 'width_m_per_pixel', 'height_m_per_pixel', 'avg_m_per_pixel'
    """
    west, south, east, north = bounds
    width_deg = east - west
    height_deg = north - south
    
    # Calculate real-world dimensions in meters
    center_lat = (north + south) / 2.0
    import math
    meters_per_deg_lat = 111_320  # constant
    meters_per_deg_lon = 111_320 * math.cos(math.radians(center_lat))
    
    width_m = width_deg * meters_per_deg_lon
    height_m = height_deg * meters_per_deg_lat
    
    # Calculate pixels preserving aspect ratio
    aspect = width_deg / height_deg
    if width_deg >= height_deg:
        output_width = target_pixels
        output_height = int(round(target_pixels / aspect))
    else:
        output_height = target_pixels
        output_width = int(round(target_pixels * aspect))
    
    m_per_pixel_x = width_m / output_width
    m_per_pixel_y = height_m / output_height
    avg_m_per_pixel = (m_per_pixel_x + m_per_pixel_y) / 2.0
    
    return {
        'width_m_per_pixel': m_per_pixel_x,
        'height_m_per_pixel': m_per_pixel_y,
        'avg_m_per_pixel': avg_m_per_pixel,
        'output_width_px': output_width,
        'output_height_px': output_height
    }
```

### 2. Interactive Dataset Selection

Location: `download_international_region()` in `ensure_region.py`

When `dataset_override` is None, calculate visible pixel size and prompt user:

```python
visible = calculate_visible_pixel_size((west, south, east, north), target_pixels)

print(f"\n  Visible pixel size: {visible['avg_m_per_pixel']:.1f}m/pixel")
if visible['avg_m_per_pixel'] > 90:
    print(f"  Recommendation: Use 90m dataset (30m detail would be wasted)")
    print(f"  Options:")
    print(f"    1. Use 90m dataset (faster download, same visual quality)")
    print(f"    2. Use 30m dataset (slower, no quality difference)")
    choice = input("  Your choice [1 or 2]: ").strip()
    if choice == "1":
        dataset = 'SRTMGL3'  # or COP90 if >60degN
```

### 3. Pipeline Tolerance for 90m Data

**Principle:** The pipeline should work identically for 30m or 90m data. No special handling needed.

Key changes:
- Update `download_international_region()` to support SRTMGL3 and COP90 demtypes
- Ensure metadata tracks actual source resolution
- No changes to clipping, reprojection, or downsampling code (they handle any input resolution)

### 4. Metadata Updates

Location: `src/metadata.py`

Update source type mapping to distinguish 30m vs 90m:

```python
# In create_raw_metadata() or similar
if 'SRTMGL3' in download_params.get('demtype', ''):
    source = 'srtm_90m'
elif 'COP90' in download_params.get('demtype', ''):
    source = 'cop90_30m'  # or new cop90_90m?
elif 'SRTMGL1' in download_params.get('demtype', ''):
    source = 'srtm_30m'
elif 'COP30' in download_params.get('demtype', ''):
    source = 'cop30_30m'
```

### 5. Documentation Updates

Update `learnings/HIGH_RESOLUTION_DOWNLOAD_GUIDE.md` to explain when to use 90m vs 30m:

```markdown
## Resolution Selection Guide

**When to use 90m (SRTMGL3/COP90):**
- Very large regions (>500k km²)
- Visible pixels will be >90m after downsampling to 2048px
- Smaller files, faster downloads
- **Same visual quality** as 30m for large regions!

**When to use 30m (SRTMGL1/COP30):**
- Small-to-medium regions
- Users might zoom in close
- Visible pixels will be <90m after processing
- Higher detail matters for the target output resolution
```

## Edge Cases

### Small Regions
- If visible pixel size <90m, always recommend 30m
- Users can zoom in to see the extra detail

### Large Regions  
- If visible pixel size >=180m, recommend 90m (Nyquist safe)
- Auto-select 90m without prompting (default choice)

### User Already Specified Dataset
- Respect `dataset_override` parameter
- Skip calculation and prompting

## Implementation Summary

**Completed:** 2025-01-09

### Key Changes Made:

1. **Added `calculate_visible_pixel_size()` function** in `ensure_region.py`
   - Calculates final visible pixel size from bounds and target_pixels
   - Returns real-world dimensions and output resolution

2. **Updated `download_international_region()`** 
   - Calculates visible pixel size before download
   - **>=180m visible**: Prompts user to choose 90m (recommended, Nyquist safe) vs 30m
   - **90-180m visible**: Prompts user with 30m recommended for quality vs 90m for speed
   - **<90m visible**: Automatically uses 30m dataset
   - Supports SRTMGL3 (90m SRTM) and COP90 (90m Copernicus)
   - **Quality-focused**: 180m threshold ensures 2.0x oversampling (Nyquist criterion) for guaranteed quality

3. **Updated `find_raw_file()`**
   - Now checks `data/raw/srtm_90m/` directory for 90m files
   - Updated `get_source_from_path()` to recognize 90m files

4. **Updated metadata system**
   - Uses `dataset_to_source_name()` to map datasets to source identifiers
   - Both COP30 and SRTMGL1 map to `srtm_30m` directory
   - Both COP90 and SRTMGL3 map to `srtm_90m` directory

5. **Updated `src/regions_registry.py`**
   - `dataset_to_source_name()` now maps:
     - COP30 -> srtm_30m
     - COP90 -> srtm_90m  
     - SRTMGL1 -> srtm_30m
     - SRTMGL3 -> srtm_90m

### File Structure:
```
data/raw/
  srtm_30m/  # 30m SRTM and Copernicus files
    <region>_bbox_30m.tif
  srtm_90m/  # 90m SRTM and Copernicus files (NEW)
    <region>_bbox_90m.tif
  usa_3dep/  # US state files (unchanged)
```

## Testing Plan

Test scenarios:
1. **Alaska** (1.7M km²) -> Should suggest 90m, visible pixels ~1.8km
2. **Iceland** (103k km²) -> Should suggest 90m, visible pixels ~400m  
3. **Rhode Island** (3k km²) -> Should suggest 30m, visible pixels ~120m
4. **Custom small region** (100 km²) -> Should suggest 30m

## Backward Compatibility

- Existing regions with 30m data continue to work
- No forced re-downloads
- Users can manually re-download with different resolution if desired
- Metadata clearly tracks what was used

## Future Enhancements

- Auto-detect and suggest when to re-download with lower resolution
- Add `--smart-resolution` flag to auto-select without prompting
- Batch-recalculate recommendations for all regions

## Usage

Interactive mode (automatic suggestion):
```powershell
python ensure_region.py iceland
# System calculates visible pixel size
# If >=180m: Prompts "Use 90m dataset (guaranteed quality, Nyquist safe)? [1 or 2]"
# If 90-180m: Prompts "Use 30m dataset (recommended for quality) vs 90m? [1 or 2]"
# If <90m: Automatically uses 30m
```

Manual override:
```powershell
# Force 90m dataset explicitly (no prompting)
python download_high_resolution.py alaska --dataset SRTMGL3 --process

# Force 30m dataset
python download_high_resolution.py small_region --dataset SRTMGL1 --process
```

## Decision Flow Examples

**Very Large Region (e.g., Siberia, 200m visible pixels):**
```
Visible: 200m per pixel
90m input: 200/90 = 2.2x oversampling [OK] Excellent quality
Decision: Recommend 90m (Option 1)
```

**Large Region (e.g., Iceland, 400m visible pixels):**
```
Visible: 400m per pixel  
90m input: 400/90 = 4.4x oversampling [OK] Excellent quality
Decision: Recommend 90m (Option 1)
```

**Medium Region (e.g., 120m visible pixels):**
```
Visible: 120m per pixel
90m input: 120/90 = 1.33x oversampling [WARN] Marginal
30m input: 120/30 = 4x oversampling [OK] Excellent
Decision: Recommend 30m (Option 1), user can choose 90m for speed
```

**Small Region (e.g., 50m visible pixels):**
```
Visible: 50m per pixel
90m input: 50/90 = 0.56x undersampling [BAD]
30m input: 50/30 = 1.67x oversampling [OK] Good
Decision: Automatically use 30m (no prompt)
```

