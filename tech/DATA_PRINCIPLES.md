# Core Data Principles

## Overview

This document defines the fundamental principles for handling geographic elevation data in the Altitude Maps project. These principles ensure accurate visualization that represents geographic reality.

---

## Principle 1: Preserve Real-World Proportions

### Goal
Display geographic data with accurate real-world proportions. A wide state like Tennessee must appear wide, not square. A tall state like New Jersey must appear tall.

### Why This Matters
Geographic features have characteristic shapes that are recognizable and meaningful:
- **Tennessee**: 8.7deg wide x 1.7deg tall = ~5:1 aspect ratio (very wide)
- **New Jersey**: 1.3deg wide x 2.5deg tall = ~0.5:1 aspect ratio (very tall)  
- **Kansas**: 5deg wide x 3deg tall = ~1.7:1 aspect ratio (moderately wide)

Incorrect proportions make states unrecognizable and misleading.

### Implementation: Export/Processing

When exporting data for regions (states, countries):

** DO**: Crop to actual geographic boundaries
```python
# Removes empty space, preserves proportions
out_image, out_transform = rasterio_mask(
    raster_src, 
    geometries, 
    crop=True,
    nodata=np.nan
)
```

** DON'T**: Keep rectangular bounding boxes
```python
# Keeps empty space, distorts proportions
out_image, out_transform = rasterio_mask(
    raster_src, 
    geometries, 
    crop=False,  # BAD
    nodata=np.nan
)
```

**Why**: Using `crop=False` keeps the full rectangular bounding box. For Tennessee, this includes huge empty areas above/below the state, resulting in ~1:1 square data when it should be ~5:1 wide data.

### Validation

Every data export automatically validates aspect ratio:
- Compares raster aspect ratio vs geographic aspect ratio
- Accounts for latitude effects (longitude degrees shrink toward poles)
- Fails if difference > 30%
- Provides clear error message explaining the issue

See `src/validation.py` for implementation.

---

## Principle 2: Treat Input Data as Uniform 2D Grid

### Goal
Render elevation data as a simple, uniform 2D grid without geographic reinterpretation or transformations.

### Why This Matters
Input elevation arrays are 2D grids of height values at evenly-spaced points:
```
elevation[row][col] = height in meters
```

**The data already has correct geographic proportions** from the export process (Principle 1). If you apply geographic transformations in the viewer, you would "correct" the data twice, creating distortion.

### Implementation: Viewer/Rendering

** DO**: Render as simple uniform grid
```javascript
// Each pixel = one unit of space
const geometry = new THREE.PlaneGeometry(
    width,  // Simple pixel width
    height, // Simple pixel height
    width - 1, 
    height - 1
);
```

** DON'T**: Apply geographic transformations
```javascript
// DON'T calculate meters per degree
const metersPerDegLon = 111_320 * Math.cos(lat);  // NO!
const widthMeters = lonSpan * metersPerDegLon;     // NO!

// DON'T use these in rendering
const geometry = new THREE.PlaneGeometry(
    widthMeters,   // WRONG
    heightMeters,  // WRONG
    ...
);
```

### Data Flow

```
GeoTIFF Source (geographic CRS)
    ->
[Masking with crop=True]  <- Principle 1 applied here
    ->
Elevation Array (correct proportions baked in)
    ->
[Export to JSON]
    ->
Viewer receives simple 2D array
    ->
[Render as uniform grid]  <- Principle 2 applied here
    ->
Display (correct proportions)
```

### Key Points

1. **Don't overthink it**: If export is correct, viewer is simple
2. **No projection math**: Data isn't in a projection system that needs interpretation
3. **One correction, one place**: Geographic proportions handled in export, not viewer
4. **Grid = Grid**: Treat `elevation[i][j]` as `position(i, j)` with height `elevation[i][j]`

---

## Common Mistakes to Avoid

### Mistake 1: Bounding Box Cropping
**Problem**: Keeping rectangular bounding box when masking states  
**Result**: Tennessee appears square (1:1) instead of wide (5:1)  
**Fix**: Use `crop=True` to remove empty space

### Mistake 2: Double Geographic Correction  
**Problem**: Applying latitude scaling in viewer to already-correct data  
**Result**: Distorted proportions (corrections applied twice)  
**Fix**: Treat input as simple 2D grid, no transformations

### Mistake 3: No Validation
**Problem**: Not checking if output proportions match geographic reality  
**Result**: Bad data gets exported and used  
**Fix**: Use `src/validation.py` checks before export

---

## Validation & Safeguards

### Automatic Validation

Every export runs validation checks:

```python
from src.validation import validate_export_data

diagnostics = validate_export_data(
    width, height, elevation, bounds_tuple,
    aspect_tolerance=0.3,  # 30% max difference
    min_coverage=0.2        # 20% min non-null pixels
)
```

**Checks**:
1. Raster aspect ratio vs geographic aspect ratio (within 30%)
2. Non-null data coverage (at least 20%)
3. Clear error messages if validation fails

### Manual Checking

To regenerate regions with correct proportions, use the unified pipeline:

```bash
# Regenerate a specific region
python ensure_region.py <region_id> --force-reprocess

# Regenerate multiple regions
python reprocess_existing_states.py --states <region1> <region2> ...
```

---

## References

- **Complete Pipeline**: `tech/DATA_PIPELINE.md` - Full process specification (stages, paths, rules)
- **Implementation**: `src/borders.py` (masking), `js/viewer-advanced.js` (rendering)
- **Validation**: `src/validation.py`
- **Regeneration**: `ensure_region.py` (unified pipeline for all regions)
- **Historical Context**: `learnings/ASPECT_RATIO_BOUNDING_BOX_FIX.md`

---

## Quick Decision Guide

**Question**: Should I apply geographic transformations/corrections?

**Answer**:
- **During export/masking**: YES - Use `crop=True` to preserve proportions
- **During rendering/display**: NO - Data is already correct, render as-is

**Rule of Thumb**: Geographic understanding applied once (at export), simple grid rendering everywhere else.

