# Aspect Ratio & Bounding Box Fix

## Date: 2025-10-28

## Core Principle Learned

**Our goal is to accurately represent geographic data with correct real-world proportions.** Wide states like Tennessee must appear wide, not square. The data should look like the actual geography.

## Two-Part Problem Discovered

State and region data was rendering with incorrect aspect ratios due to violations of two fundamental principles:

1. **Data export didn't preserve proportions** - Kept empty bounding box space
2. **Viewer reinterpreted data incorrectly** - Applied geographic transformations to already-correct data

**Example - Tennessee:**
- **BEFORE**: 812 x 871 pixels (aspect ratio 0.932 - almost square!)
- **AFTER**: 1023 x 202 pixels (aspect ratio 5.044 - correctly wide!)
- **Reality**: Tennessee is ~8.7deg wide and ~1.7deg tall (should be ~5:1 aspect ratio)

**Root Cause**: Using `crop=False` in `rasterio.mask()` operations kept the full rectangular bounding box including empty (NaN) pixels outside the actual state boundaries. This made wide states appear square.

## The Fix

### Principle 1: Preserve Real-World Proportions in Data Export

Changed masking functions in `src/borders.py` to crop to actual boundaries, removing empty space that distorts proportions:

```python
# OLD (BROKEN):
out_image, out_transform = rasterio_mask(
    raster_src, 
    geoms, 
    crop=False,  #  Keeps full bounding box with empty space
    nodata=np.nan,
    invert=False
)

# NEW (CORRECT):
out_image, out_transform = rasterio_mask(
    raster_src, 
    geoms, 
    crop=True,  #  Crops to minimum bounding box of actual geometry
    nodata=np.nan,
    invert=False
)
```

**Why this matters**: Using `crop=False` keeps the full rectangular bounding box. For a wide state like Tennessee, this includes huge empty areas above and below the state, making the data appear square when it should be wide (5:1 ratio).

This affects:
- `BorderManager.mask_raster_to_country()` (line ~188)
- `BorderManager.mask_raster_to_state()` (line ~384)

### Principle 2: Treat Input Data as Uniform 2D Grid

Fixed `js/viewer-advanced.js` to stop reinterpreting already-correct data. Input elevation arrays are simple 2D grids - render them as-is without geographic transformations:

```javascript
// OLD (WRONG): Applied geographic transformations
// This was trying to "correct" data that was already correct
const geometry = new THREE.PlaneGeometry(
    scale.widthMeters, scale.heightMeters, width - 1, height - 1
);

// NEW (CORRECT): Treat as simple 2D grid
// The data already has correct proportions from export
const geometry = new THREE.PlaneGeometry(
    width, height, width - 1, height - 1
);
```

**Why this matters**: The input data from export already has correct geographic proportions (because we crop properly). Applying latitude-dependent scaling in the viewer would "correct" it twice, creating distortion. Just render the grid as-is.

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

**This prevents bad data from being exported in the first place.**

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

## Commands to Fix Everything

### 1. Check Current State
```bash
# Activate venv
.\venv\Scripts\Activate.ps1

# See which regions have problems
python fix_all_regions_aspect_ratio.py --check-only
```

### 2. Fix All Affected Regions
```bash
# Fix everything (uses existing source TIF files)
python fix_all_regions_aspect_ratio.py --fix-all --target-pixels 1024
```

### 3. If Source TIFs are Missing

For regions where source TIF is not available locally, you'll need to re-download:

```bash
# For US states (from national data):
python download_all_us_states.py --states <state_id> --max-size 1024

# For regions via the standardized command:
python ensure_region.py <region_id> --target-pixels 1024

# For specific countries:
python downloaders/tile_large_states.py <region_id>  # If it's a large state
```

## Fundamental Principles (To Prevent Future Issues)

### 1. Goal: Accurate Real-World Representation

Always ask: **"Will this preserve the geographic proportions as they exist in reality?"**
- Wide states should appear wide
- Tall states should appear tall  
- The visualization should look like the actual geography

### 2. Data is a 2D Grid, Not Geodata (in the viewer)

Input elevation arrays are simple 2D grids of height values. **Render them as-is**:
-  Treat each pixel as one unit of space (uniform grid)
-  Don't apply geographic projections or latitude corrections
-  Don't reinterpret coordinate systems

The data already has correct proportions from the export process.

### 3. Technical Patterns

When masking/clipping geographic data for export:

```python
#  CORRECT PATTERN:
out_image, out_transform = rasterio_mask(
    raster_src, 
    geometries, 
    crop=True,  # Always crop to actual boundaries
    nodata=np.nan
)

#  WRONG PATTERN:
out_image, out_transform = rasterio_mask(
    raster_src, 
    geometries, 
    crop=False,  # Don't do this with state/country boundaries!
    nodata=np.nan
)
```

**Exception**: Only use `crop=False` when you explicitly need to preserve the original extent (e.g., for alignment with other rasters).

## Files Modified

### Core Fixes:
- `src/borders.py` - Changed crop=False to crop=True in both mask functions
- `js/viewer-advanced.js` - Removed latitude-dependent aspect ratio corrections

### New Safety Features:
- `src/validation.py` - New validation module
- `src/pipeline.py` - Added validation to export function
- `fix_all_regions_aspect_ratio.py` - Tool to fix existing data

### Documentation:
- This file (`learnings/ASPECT_RATIO_BOUNDING_BOX_FIX.md`)
- `.cursorrules` - Updated with learned patterns

## Impact

All state/country data needs to be regenerated to fix aspect ratios. The validation system will prevent this from happening again.

**Estimated regeneration time**: ~2-5 minutes per region (depending on source data availability)

