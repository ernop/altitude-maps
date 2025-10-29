# Aspect Ratio Validation Fix - Summary

**Date:** October 28, 2025  
**Status:**  RESOLVED

## The Problem

When running `reprocess_existing_states.py`, the pipeline was failing with errors like:

```
 VALIDATION FAILED: Aspect ratio mismatch detected!
  Raster:     1935 x 1605 = 1.206
  Geographic: 365.6km x 396.8km = 0.921
  Difference: 30.8% (tolerance: 30.0%)
```

19 states were failing validation.

## Root Cause Analysis

### Initial Investigation
1. **Suspected the downsampling code** - Found off-by-one issue where `dimension // step` didn't match actual array shape after slicing
   - Fixed by using actual `downsampled.shape[0/1]` instead of calculated dimensions
   
2. **Suspected the clipping code** - Thought `crop=True` wasn't working
   - Diagnostic showed **clipping IS working correctly** - all-empty rows/columns are removed
   - The sparse edges (29% valid on edges) are because states have irregular boundaries

3. **Found the actual bug: THE VALIDATION WAS WRONG**

### The Real Issue

The validation code in `src/validation.py::validate_export_data()` was checking if the raster aspect ratio matched the "real world" geographic aspect ratio in meters. This is **fundamentally incorrect** for our use case.

**Per project principles (DATA_PRINCIPLES.md):**
>  **Principle 2: Treat Input Data as Uniform 2D Grid**
> 
> Elevation data from GeoTIFFs is a simple 2D array of height values at evenly-spaced grid points. **Do not reinterpret or transform this data** based on latitude/longitude when rendering.

Our GeoTIFFs use EPSG:4326 (WGS84 lat/lon) with **square pixels in degrees**, not square pixels in meters. The raster aspect ratio SHOULD differ from the metric geographic aspect ratio because:
- Longitude degrees shrink toward the poles (cos(latitude) factor)
- The data grid has square degree-pixels, not square meter-pixels
- The viewer treats this as a uniform 2D grid (correct behavior)

### Why the "Validation" Was Failing

Example: Ohio
- **Raster:** 1935 x 1605 pixels = aspect 1.206 (wider than tall in pixels)
- **Geographic (meters):** 365.6km x 396.8km = aspect 0.921 (taller than wide in meters)  
- **Diff:** 30.8%

This is **completely normal and correct**! At Ohio's latitude (~40degN), longitude degrees are ~76% as wide as latitude degrees in meters (cos(40deg) ~ 0.766). The raster correctly preserves the degree-based grid spacing.

## The Fix

### Code Changes

1. **src/pipeline.py** - Removed incorrect aspect ratio validation from `export_for_viewer()`:
   ```python
   # OLD (WRONG):
   diagnostics = validate_export_data(
       src.width, src.height, elevation, bounds_tuple,
       aspect_tolerance=0.3, min_coverage=0.2
   )
   
   # NEW (CORRECT):
   coverage = validate_non_null_coverage(elevation, min_coverage=0.2, warn_only=True)
   # Only validate data coverage, not aspect ratio
   ```

2. **reprocess_existing_states.py** - Added `--states` filter for testing specific states

3. **src/pipeline.py** - Fixed minor downsampling dimension calculation (was already mostly correct)

4. **src/pipeline.py** - Added automatic cleanup of dependent files when regenerating clipped data

### Results

Successfully reprocessed all 19 states that were previously "failing":
- kentucky, north_dakota, washington, minnesota, maine, wisconsin, oregon, south_dakota
- new_hampshire, vermont, wyoming, massachusetts, iowa, rhode_island, nebraska
- connecticut, pennsylvania, ohio, indiana

All now export successfully with proper data coverage validation.

## Why fix_all_regions_aspect_ratio.py Shows "Issues"

The script `fix_all_regions_aspect_ratio.py` still uses the OLD (incorrect) validation logic. It's checking geographic meter-based aspect ratios, which we now know is wrong.

**This script is OBSOLETE** - the "issues" it reports are not actually issues.

## Validation That Matters

What we SHOULD validate:
1.  **Data coverage** - Percentage of non-null pixels (should be reasonable for the region)
2.  **All-empty edges removed** - crop=True successfully removes all-empty rows/columns
3.  **Downsampling preserves aspect ratio** - Same step size for both dimensions
4.  **File format consistency** - Proper metadata and versioning

What we should NOT validate:
-  Raster aspect ratio vs geographic meter-based aspect ratio (meaningless for degree-gridded data)

## Files Modified

- `src/pipeline.py` - Removed incorrect validation, fixed dimension calculation
- `reprocess_existing_states.py` - Added --states filter
- Created diagnostic scripts (later deleted):
  - `check_ohio_data.py` - Analyzed raw vs clipped data
  - `diagnose_cropping.py` - Verified crop=True effectiveness

## Commands Used

```powershell
# Test single state
python reprocess_existing_states.py --target-pixels 2048 --states ohio

# Process all 19 states
python reprocess_existing_states.py --target-pixels 2048 --states kentucky north_dakota washington minnesota maine wisconsin oregon south_dakota new_hampshire vermont wyoming massachusetts iowa rhode_island nebraska connecticut pennsylvania ohio indiana
```

## Conclusion

The "aspect ratio errors" were not errors at all - they were a symptom of incorrect validation logic that didn't account for the project's design principle of treating input data as uniform 2D grids.

The fix was simple: **remove the incorrect validation**. The data processing pipeline was working correctly all along.

All state data now exports successfully and will display with correct proportions in the viewer.

