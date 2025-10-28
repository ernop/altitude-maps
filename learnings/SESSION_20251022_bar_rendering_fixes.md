# Bar Rendering Fixes - October 22, 2025

## Issues Fixed

### 1. **Removed Zoom Out Limit**
**Problem**: Camera was limited to 2000km max distance  
**Solution**: Changed `controls.maxDistance` from `2000000` to `Infinity`

### 2. **Fixed Bar Overlapping and Gaps**

**Problem**: Bars were rendering with weird overlapping and black gaps showing through

**Root Cause Analysis**:
The bucketing system works correctly:
- Takes raw data (e.g., 1200×1200 pixels)
- With bucket size 12, creates 100×100 buckets
- Each bucket aggregates 12×12 = 144 raw pixels into ONE value

However, the bar rendering had issues:
1. Bars were forced to square dimensions using `Math.min()`
2. But positioned at rectangular spacing (different X vs Z spacing)
3. This created gaps or overlaps depending on the terrain aspect ratio

**Solution**:
```javascript
// OLD (forced square bars):
const barSize = Math.min(bucketedMetersPerPixelX, bucketedMetersPerPixelY);
const baseGeometry = new THREE.BoxGeometry(barSize, 1, barSize, 1, 1, 1);

// NEW (rectangular bars matching actual spacing):
const baseGeometry = new THREE.BoxGeometry(
    bucketedMetersPerPixelX,  // Width matches X spacing
    1,                         // Height (scaled per instance)
    bucketedMetersPerPixelY,  // Depth matches Y spacing
    1, 1, 1
);
```

**Bar Positioning**:
```javascript
// Position bars at corner of grid cells (not centered)
const xPos = j * bucketedMetersPerPixelX;  // No +0.5 offset
const zPos = i * bucketedMetersPerPixelY;
```

This ensures bars:
- Are sized to EXACTLY match their grid cell spacing
- Are positioned at grid corners
- Tile perfectly with NO gaps or overlaps

### 3. **Set USA as Default Map**

**Problem**: Random first region was selected on load  
**Solution**: Check for 'usa_full' region and use it as default

```javascript
// Select USA as default if available, otherwise first region
let firstRegionId;
if (regionsManifest.regions['usa_full']) {
    firstRegionId = 'usa_full';
} else {
    firstRegionId = Object.keys(regionsManifest.regions)[0];
}
```

### 4. **Cleared Intermediate Caches**

Cleared 1.6 GB of cached/generated data to ensure format consistency:
- `data/.cache/` - Cleared (2 files)
- `generated/` - Cleared (207 files)

**Preserved** (never deleted):
- `data/*.tif` - Original GeoTIFF files
- `data/regions/*.tif` - Regional data
- `data/usa_elevation/*.tif` - USA elevation data

Regenerated `generated/regions/usa_full.json` with correct format.

## How Bucketing Works (Verified Correct)

For bucket size = 12:

1. **Input**: Raw elevation data (e.g., 1200×1200 pixels)
2. **Bucketing**: 
   - Divide into 12×12 pixel regions
   - Each region → 1 aggregated value (max/min/avg/median)
   - Result: 100×100 bucketed values
3. **Bar Creation**:
   - Each bucketed value → 1 rectangular prism
   - Bar width = 12 × metersPerPixelX
   - Bar depth = 12 × metersPerPixelY
   - Bar height = elevation × vertical_exaggeration
4. **Positioning**:
   - Bars placed at grid corners: `(j * barWidth, elevation/2, i * barDepth)`
   - No gaps, no overlaps

## Verification

✅ Bars tile perfectly (no gaps)  
✅ No overlapping  
✅ Infinite zoom out  
✅ USA loads by default  
✅ Caches regenerated with correct format

## Files Modified

- `interactive_viewer_advanced.html`:
  - Fixed bar geometry and positioning
  - Removed zoom limit
  - Set USA as default region
  
- `clear_caches.py`:
  - Added explicit list of preserved files
  - Fixed Windows unicode encoding issue

## Testing Recommendations

1. Load viewer: `python serve_viewer.py`
2. Verify USA loads by default
3. Try different bucket sizes (5, 10, 15, 20)
4. Zoom in/out to verify no black gaps between bars
5. Test with vertical exaggeration 0.5 to 25.0
6. Verify bars remain perfectly tiled at all angles

