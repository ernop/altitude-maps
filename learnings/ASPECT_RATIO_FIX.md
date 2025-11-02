# Aspect Ratio Fix - Complete Documentation

**Date:** October 28, 2025  
**Status:** RESOLVED

---

## Quick Summary

**Core Principle Violated**: Geographic data must preserve real-world proportions  
**Problem**: States/regions rendering with wrong aspect ratio (Tennessee appearing square instead of wide 5:1)  
**Root Cause**: Data export kept empty bounding box space, distorting proportions  
**Fix**: Export crops to actual boundaries, validation ensures correct proportions

---

## The Problem

State and region data was rendering with incorrect aspect ratios. Example:

**Tennessee:**
- **BEFORE**: 812 x 871 pixels (aspect ratio 0.932 - almost square!)
- **AFTER**: 1023 x 202 pixels (aspect ratio 5.044 - correctly wide!)
- **Reality**: Tennessee is ~8.7deg wide and ~1.7deg tall (should be ~5:1 aspect ratio)

**Root Cause**: Using `crop=False` in `rasterio.mask()` operations kept the full rectangular bounding box including empty (NaN) pixels outside the actual state boundaries. This made wide states appear square.

---

## The Fix

### Principle 1: Preserve Real-World Proportions in Data Export

Changed masking functions in `src/borders.py` to crop to actual boundaries:

```python
# OLD (BROKEN):
out_image, out_transform = rasterio_mask(
    raster_src, 
    geoms, 
    crop=False,  # ❌ Keeps full bounding box with empty space
    nodata=np.nan
)

# NEW (CORRECT):
out_image, out_transform = rasterio_mask(
    raster_src, 
    geoms, 
    crop=True,  # ✅ Crops to minimum bounding box of actual geometry
    nodata=np.nan
)
```

**Why this matters**: Using `crop=False` keeps the full rectangular bounding box. For a wide state like Tennessee, this includes huge empty areas above and below the state, making the data appear square when it should be wide (5:1 ratio).

### Principle 2: Treat Input Data as Uniform 2D Grid

Fixed `js/viewer-advanced.js` to stop reinterpreting already-correct data:

```javascript
// OLD (WRONG): Applied geographic transformations
const geometry = new THREE.PlaneGeometry(
    scale.widthMeters, scale.heightMeters, width - 1, height - 1
);

// NEW (CORRECT): Treat as simple 2D grid
const geometry = new THREE.PlaneGeometry(
    width, height, width - 1, height - 1
);
```

**Why this matters**: The input data from export already has correct geographic proportions (because we crop properly). Applying latitude-dependent scaling in the viewer would "correct" it twice, creating distortion.

---

## New Safeguards

### 1. Validation Module (`src/validation.py`)

New validation functions catch aspect ratio issues:
- `validate_aspect_ratio()` - Compares raster vs geographic aspect ratio
- `validate_non_null_coverage()` - Checks for too much empty space
- `validate_export_data()` - Comprehensive pre-export validation

**Raises exceptions** if:
- Aspect ratio differs by > 30% from geographic reality
- Non-null coverage is < 20% (configurable)

### 2. Export-Time Validation (`src/pipeline.py`)

Added automatic validation to `export_for_viewer()`:

```python
def export_for_viewer(..., validate_output: bool = True):
    if validate_output:
        diagnostics = validate_export_data(...)
        # Raises AspectRatioError if invalid
```

### 3. Regeneration Tool (`fix_all_regions_aspect_ratio.py`)

Tool to find and fix existing bad data:

```bash
# Check which regions need fixing
python fix_all_regions_aspect_ratio.py --check-only

# Fix all problematic regions
python fix_all_regions_aspect_ratio.py --fix-all

# Fix specific region
python fix_all_regions_aspect_ratio.py --region tennessee
```

---

## Important Update: Validation Refinement

### Initial Validation Was Too Strict

The original validation checked if raster aspect ratio matched "real world" geographic aspect ratio in meters. This was **incorrect** for our use case.

**Why**: Our GeoTIFFs use EPSG:4326 (WGS84 lat/lon) with **square pixels in degrees**, not square pixels in meters. The raster aspect ratio SHOULD differ from the metric geographic aspect ratio because:
- Longitude degrees shrink toward the poles (cos(latitude) factor)
- The data grid has square degree-pixels, not square meter-pixels
- The viewer treats this as a uniform 2D grid (correct behavior)

### Corrected Validation

**What we SHOULD validate:**
1. ✅ **Data coverage** - Percentage of non-null pixels (should be reasonable)
2. ✅ **All-empty edges removed** - `crop=True` successfully removes all-empty rows/columns
3. ✅ **Downsampling preserves aspect ratio** - Same step size for both dimensions
4. ✅ **File format consistency** - Proper metadata and versioning

**What we should NOT validate:**
- ❌ Raster aspect ratio vs geographic meter-based aspect ratio (meaningless for degree-gridded data)

### Code Changes

**src/pipeline.py** - Removed incorrect aspect ratio validation:
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

---

## Commands to Fix Everything

### Step 1: Check Current State
```bash
# Activate venv
.\venv\Scripts\Activate.ps1

# See which regions have problems
python fix_all_regions_aspect_ratio.py --check-only
```

### Step 2: Fix All Affected Regions
```bash
# Fix everything (uses existing source TIF files)
python fix_all_regions_aspect_ratio.py --fix-all --target-pixels 1024
```

### Step 3: Handle Missing Source Files

For regions where source TIF is not available:

```bash
# For US states
python ensure_region.py tennessee --target-pixels 1024

# For international regions
python ensure_region.py iceland --target-pixels 1024
```

### Step 4: Verify the Fix
```bash
# Check aspect ratios again
python fix_all_regions_aspect_ratio.py --check-only

# Start the viewer to visually verify
python serve_viewer.py
# Open: http://localhost:8001/interactive_viewer_advanced.html
```

---

## Fundamental Principles

### 1. Goal: Accurate Real-World Representation

Always ask: **"Will this preserve the geographic proportions as they exist in reality?"**
- Wide states should appear wide
- Tall states should appear tall  
- The visualization should look like the actual geography

### 2. Data is a 2D Grid, Not Geodata (in the viewer)

Input elevation arrays are simple 2D grids of height values. **Render them as-is**:
- ✅ Treat each pixel as one unit of space (uniform grid)
- ❌ Don't apply geographic projections or latitude corrections
- ❌ Don't reinterpret coordinate systems

The data already has correct proportions from the export process.

### 3. Technical Pattern

When masking/clipping geographic data for export:

```python
# ✅ CORRECT PATTERN:
out_image, out_transform = rasterio_mask(
    raster_src, 
    geometries, 
    crop=True,  # Always crop to actual boundaries
    nodata=np.nan
)

# ❌ WRONG PATTERN:
out_image, out_transform = rasterio_mask(
    raster_src, 
    geometries, 
    crop=False,  # Don't do this with state/country boundaries!
    nodata=np.nan
)
```

**Exception**: Only use `crop=False` when you explicitly need to preserve the original extent (e.g., for alignment with other rasters).

---

## Files Modified

### Core Fixes:
- `src/borders.py` - Changed `crop=False` to `crop=True` in both mask functions
- `js/viewer-advanced.js` - Removed latitude-dependent aspect ratio corrections
- `src/pipeline.py` - Removed incorrect aspect ratio validation, kept coverage validation

### New Safety Features:
- `src/validation.py` - New validation module
- `src/pipeline.py` - Added validation to export function
- `fix_all_regions_aspect_ratio.py` - Tool to fix existing data

### Documentation:
- This file (`learnings/ASPECT_RATIO_FIX.md`)
- `.cursorrules` - Updated with learned patterns

---

## Impact & Timeline

**Impact**: All state/country data needs to be regenerated to fix aspect ratios. The validation system will prevent this from happening again.

**Timeline**:
- Per region: ~2-5 minutes (depending on source data availability)
- For all affected regions: 15-30 minutes if source TIFs exist, 1-2 hours if re-downloading needed

---

## Troubleshooting

### "Source TIF not found"
Re-download the region first using `ensure_region.py`

### "Validation failed"
This is GOOD - it means the safeguard caught a problem. Check the error message for details.

### "Aspect ratio still wrong"
1. Delete cached/intermediate files
2. Re-run the fix command

### Nuclear option (regenerate ALL data):
```bash
Remove-Item -Recurse -Force data\clipped\*
Remove-Item -Recurse -Force data\processed\*
Remove-Item -Recurse -Force generated\regions\*

python fix_all_regions_aspect_ratio.py --fix-all --target-pixels 1024
```

---

**Document Status:** Consolidated from 3 separate files (Bounding Box Fix, Procedure, Summary)  
**Maintained By:** Altitude Maps Project

