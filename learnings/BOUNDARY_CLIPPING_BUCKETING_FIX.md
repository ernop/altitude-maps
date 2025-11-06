# Boundary Clipping Missing - Root Cause and Fixes

**Date**: 2025-11-06  
**Issue**: State/country boundaries not visible (Pennsylvania showing as filled rectangle)  
**Root Cause #1**: Manifest pointing to old unclipped JSON file  
**Root Cause #2**: Bucketing aggregation would fill in clipped boundary areas (preventative fix)  
**Status**: Fixed

## Problem Description

Users reported that Pennsylvania (and likely other regions) appeared to have no border clipping applied, showing as rectangular bounding boxes instead of proper state shapes.

## Root Cause #1: Manifest Pointing to Wrong File (ACTUAL ISSUE)

### Investigation - Following the Data Flow

Traced through the complete pipeline systematically:

**Stage 6 - Clipping** (Pipeline working correctly):
- Clipped GeoTIFF: **15.14% nodata pixels** (properly clipped to state boundary)
- File: `data/clipped/srtm_30m/pennsylvania_clipped_srtm_30m_v1.tif`
- Size: 385 MB, modified Oct 28

**Stage 8 - Processing** (Pipeline working correctly):
- Processed GeoTIFF: **15.14% nodata pixels** (preserved through reprojection)
- File: `data/processed/srtm_30m/pennsylvania_srtm_30m_2048px_v2.tif`
- Size: 3 MB, modified Oct 28

**Stage 9 - Export** (Pipeline working correctly):
- Exported JSON: **15.14% None values** (preserved in export)
- File: `pennsylvania_srtm_30m_2048px_v2.json` (9.3 MB)
- Shape: 835 x 1908 pixels
- Modified Oct 28 6:09 PM

**Stage 11 - Manifest** (PROBLEM FOUND HERE):
- Manifest entry: `"file": "pennsylvania.json"` ← **WRONG FILE!**
- This file: 1.7 MB, modified Oct 28 1:28 PM (older than pipeline run)
- Shape: 354 x 808 pixels
- **0% None values** - NO CLIPPING!
- Old pre-pipeline format (no version field, no source field)

### Why This Happened

The manifest generator (`regenerate_manifest.py`) scans `generated/regions/*.json` and when multiple files exist for a region, it uses **the first one alphabetically**:

```python
for candidate_file in json_files_by_region[region_id]:
    json_file = candidate_file
    break  # Uses first file!
```

Alphabetically: `pennsylvania.json` < `pennsylvania_srtm_30m_2048px_v2.json`

So it picked the old unclipped file instead of the new properly-clipped v2 file.

### The Fix

1. Delete old files: `Remove-Item generated/regions/pennsylvania.json*`
2. Regenerate manifest: `python regenerate_manifest.py`
3. Verify: Manifest now points to `pennsylvania_srtm_30m_2048px_v2.json`
4. Bump version: Force browser cache reload

### Verification

After fix:
```bash
# Check manifest
python -c "import json; m=json.load(open('generated/regions/regions_manifest.json')); 
           print(m['regions']['pennsylvania']['file'])"
# Output: pennsylvania_srtm_30m_2048px_v2.json ✓

# Verify file has clipping
python -c "import json,gzip; d=json.load(gzip.open('generated/regions/pennsylvania_srtm_30m_2048px_v2.json.gz')); 
           flat=[v for row in d['elevation'] for v in row]; 
           print(f'{sum(1 for v in flat if v is None)} None values ({100*sum(1 for v in flat if v is None)/len(flat):.2f}%)')"
# Output: 241219 None values (15.14%) ✓
```

---

## Root Cause #2: Bucketing Would Fill Boundaries (PREVENTATIVE FIX)

Even though Root Cause #1 was the actual problem, the bucketing code had a latent bug that would have caused issues once the correct file was loaded.

### Investigation

Data pipeline was working correctly:
- Clipped GeoTIFF: **15.14% nodata pixels** (properly clipped to state boundary)
- Processed GeoTIFF: **15.14% nodata pixels** (preserved through reprojection)
- Exported JSON: **15.14% None values** (preserved in export)

But the viewer showed:
- Bucketed grid: **808 x 354 = 286,032 bars**
- All 286,032 bars rendered (100% of grid)
- **0% None values after bucketing** - boundaries completely filled in!

### Root Cause

The bucketing aggregation in `js/bucketing.js` was using this logic:

```javascript
// OLD CODE (WRONG):
let value = null;
if (count > 0) {  // Create bar if ANY pixel is valid
    // Aggregate the valid pixels
}
```

This meant:
- A bucket straddling the state border might have 1 valid pixel (inside state) and 5 None pixels (outside state)
- Old logic: "count > 0, so create a bar with the value from that 1 pixel"
- Result: Boundary pixels get filled in with aggregated values from sparse data
- Effect: State boundaries disappear, map looks like rectangular bounding box

### Example (Pennsylvania)

```
Original:  1,908 x 835 = 1,593,180 pixels (15.14% None)
Bucketed:    808 x 354 =   286,032 buckets (0% None) <-- WRONG!

Bucket size: ~2.36 x 2.36 pixels (~5.6 pixels per bucket)
```

Even small buckets spanning the boundary would "heal" the clipped areas by aggregating the few valid pixels they contained.

## Solution

Added a **valid pixel ratio threshold** to the bucketing logic:

```javascript
// NEW CODE (CORRECT):
let value = null;
const maxPossiblePixels = bucketSize * bucketSize;
const validPixelRatio = count / maxPossiblePixels;

// Require at least 50% of bucket pixels to be valid
if (validPixelRatio >= 0.5) {
    // Only aggregate if bucket is mostly inside the boundary
    switch (params.aggregation) {
        // ... aggregation logic
    }
}
```

**Threshold reasoning (50%)**:
- Buckets fully inside the state: 100% valid → bar created
- Buckets fully outside the state: 0% valid → no bar (remains None)
- Buckets straddling border: <50% valid → no bar (boundary preserved)
- Buckets mostly inside: >50% valid → bar created

This preserves the clipped boundary shape during aggregation.

## Expected Results

After fix:
- Bucketed data should retain roughly the same percentage of None values as input
- Pennsylvania: Should preserve ~15% None values after bucketing
- Visual: State boundaries should be clearly visible as gaps in the bar grid
- Edge buckets along borders should be filtered out, creating clean boundary edges

## Verification

Added diagnostic logging to `js/bucketing.js`:

```
[BUCKETING] Boundary preservation: X,XXX None buckets (XX.XX% of XXX,XXX total)
```

This shows:
- How many buckets were kept as None (boundary areas)
- Percentage of total buckets that are boundary (should match input data)
- Total bucket count for reference

## Testing

To verify the fix works:

1. Load Pennsylvania in viewer: `http://localhost:8001/interactive_viewer_advanced.html?region=pennsylvania`
2. Check console for bucketing log showing None percentage
3. Visually inspect the map - should see clear state boundary shape
4. Try other clipped regions (Ohio, Kentucky, Iceland, etc.)
5. Try different bucket sizes - boundary should remain visible at all resolutions

## Related Files

- `js/viewer-advanced.js` - Contains `computeBucketedData()` function (main fix applied here, lines 1047-1084)
- `js/bucketing.js` - Standalone bucketing module (fixed but not currently used by viewer)
- `js/terrain-renderer.js` - Already correctly skips None values when creating bars
- `src/pipeline.py` - Data clipping logic (was working correctly)
- `tech/DATA_PIPELINE.md` - Pipeline documentation

**Note**: The project has bucketing code in two places:
1. `js/viewer-advanced.js` - The actual running code (fixed)
2. `js/bucketing.js` - Standalone module (also fixed for consistency, but not loaded by HTML)

## Lessons Learned

1. **Trace the entire data flow**: When something looks wrong, don't guess - systematically trace from source to display
2. **Check what's actually loading**: The manifest might point to a different file than you expect
3. **Alphabetical sorting matters**: When picking "first file" alphabetically, old files can shadow new ones
4. **File naming conventions matter**: Using standardized suffixes (`_v2.json`) makes it clear which files are current
5. **Aggregation can destroy signal**: When aggregating sparse data, check if you're filling in meaningful gaps
6. **Thresholds matter**: "count > 0" is almost never the right threshold for sparse data
7. **Percentage preservation**: When data has meaningful None values, track their percentage through the pipeline
8. **Diagnostic logging**: Adding percentage tracking immediately revealed the problem

## Preventative Measures

To avoid this issue in the future:

### 1. Clean Up Old Files After Pipeline Changes
When the pipeline format changes (e.g., adding `_v2` suffix), delete old files:
```bash
# Find and review old files
Get-ChildItem generated/regions/*.json | Where-Object { $_.Name -notmatch '_v2\.json$' -and $_.Name -notmatch 'manifest|adjacency|meta|borders' }

# Delete after verification
Remove-Item generated/regions/<region_id>.json*  # Keep only v2 files
```

### 2. Improve Manifest File Selection
Current code uses first file alphabetically. Consider improving to:
- Prefer files with `_v2` suffix
- Prefer files with version field in JSON
- Prefer newer files by modification time
- Warn if multiple candidates exist

### 3. Add Validation to Manifest Generator
```python
# Suggested enhancement
if len(json_files_by_region[region_id]) > 1:
    print(f"Warning: Multiple files for {region_id}: {[f.name for f in json_files_by_region[region_id]]}")
    # Prefer v2 files
    v2_files = [f for f in json_files_by_region[region_id] if '_v2.json' in f.name]
    if v2_files:
        json_file = v2_files[0]
```

### 4. Add Data Validation
Check clipping during manifest generation:
```python
# Verify clipping for states/countries that should be clipped
if config.clip_boundary and none_percentage < 1.0:
    print(f"Warning: {region_id} expects clipping but has <1% None values")
```

## Future Improvements

Potential enhancements:
1. Make bucketing threshold configurable (currently hardcoded to 0.5)
2. Consider adaptive thresholds based on bucket size (smaller buckets = lower threshold?)
3. Add UI toggle to show/hide boundary buckets
4. Consider alternative aggregation for boundary buckets (weighted by valid pixel count?)

