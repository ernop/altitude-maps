# Compass Label Position Bug Fix

## Issue: Compass Ball Labels Misaligned After Region Switching

**Reported:** November 6, 2025  
**Symptoms:** When repeatedly clicking links to load new maps, compass ball labels (N/S/E/W markers and connectivity labels) become progressively misaligned and positioned incorrectly.

## Root Cause Analysis

### The Question
User asked: "When I click a link after having moved the cam/rotated/etc, does the new map get built at 0,0,0 as normal or does that change?"

### The Answer
**YES and NO:**
- The new map terrain IS built at (0,0,0) initially
- BUT the old rotation from the previous region is immediately restored
- This causes compass markers to be positioned for zero rotation while the terrain has non-zero rotation

### Detailed Bug Flow

#### Step-by-Step Trace (Before Fix)

1. **User loads Ohio, rotates terrain to 45 degrees**
   - terrainGroup.rotation = (0, 45°, 0)

2. **User clicks link to load Indiana**
   - `loadRegion('indiana')` called (viewer-advanced.js line 841)

3. **Inside loadRegion, autoAdjustBucketSize() is called** (line 928)
   - This calls `recreateTerrain()` internally

4. **Inside recreateTerrain() (terrain-renderer.js line 354)**
   ```javascript
   function recreate() {
       // PROBLEM: Saves rotation from OLD region (Ohio = 45°)
       if (window.terrainGroup) {
           oldTerrainGroupRotation = window.terrainGroup.rotation.clone();
       }

       create(); // ← Creates NEW terrainGroup at (0,0,0) with rotation (0,0,0)
                // ← Edge markers created with positions for ZERO rotation

       // PROBLEM: Restores OLD rotation (45°) onto NEW terrain!
       if (oldTerrainGroupRotation && window.terrainGroup) {
           window.terrainGroup.rotation.copy(oldTerrainGroupRotation);
       }
   }
   ```

5. **Edge markers created during create()** (edge-markers.js lines 116-136)
   - Positions calculated: `x = xExtent * spreadMultiplier`, etc.
   - These assume terrainGroup rotation is (0,0,0)
   - Added to terrainGroup
   - **THEN rotation is restored to 45° from Ohio!**
   - Result: Markers positioned for 0° but terrain is at 45° → MISALIGNED

6. **Connectivity labels created later** (state-connectivity.js line 520)
   - Calculate positions based on NEW terrain dimensions
   - But terrainGroup already has WRONG rotation
   - Result: Labels also misaligned

### Why This Existed

The `recreate()` function was designed to preserve position and rotation when:
- User changes bucket size on the SAME region
- We want terrain to stay in same place and orientation

BUT it was incorrectly preserving rotation when:
- User loads a COMPLETELY DIFFERENT region
- We want terrain to reset to default orientation

## The Fix

### Solution: Conditional Transform Preservation

Added `preserveTransform` parameter to control when rotation is preserved:

#### 1. Modified `TerrainRenderer.recreate()` (terrain-renderer.js)

```javascript
/**
 * Recreate terrain (optionally preserves position and rotation)
 * @param {boolean} preserveTransform - If true, preserve position and rotation (default: true)
 */
function recreate(preserveTransform = true) {
    // Only save old rotation if requested
    if (preserveTransform) {
        if (window.terrainGroup) {
            oldTerrainGroupRotation = window.terrainGroup.rotation.clone();
        }
    }

    create(); // Creates new terrain at (0,0,0)

    // Only restore rotation if it was saved
    if (oldTerrainGroupRotation && window.terrainGroup) {
        window.terrainGroup.rotation.copy(oldTerrainGroupRotation);
    }
}
```

#### 2. Modified `autoAdjustBucketSize()` (resolution-controls.js)

```javascript
/**
 * @param {boolean} preserveTransform - If true, preserve position and rotation (default: true)
 */
function autoAdjustBucketSize(preserveTransform = true) {
    // ... bucket size calculation ...
    
    rebucketData();
    recreateTerrain(preserveTransform); // Pass parameter through
    updateStats();
}
```

#### 3. Updated `loadRegion()` (viewer-advanced.js)

```javascript
// When loading NEW region, pass false to reset rotation
autoAdjustBucketSize(false);
```

#### 4. Updated wrapper function (viewer-advanced.js)

```javascript
function autoAdjustBucketSize(preserveTransform = true) {
    return window.ResolutionControls.autoAdjust(preserveTransform);
}
```

### Behavior After Fix

| Action | preserveTransform | Behavior |
|--------|------------------|----------|
| Load new region | `false` | Terrain resets to (0,0,0) rotation |
| Change bucket size | `true` (default) | Terrain keeps current rotation |
| Click DEFAULT button | `true` (default) | Terrain keeps current rotation |

## Testing

### Expected Results After Fix

1. **Load Ohio, rotate terrain to 45°**
   - Compass markers correctly positioned

2. **Click link to load Indiana**
   - New terrain created at (0,0,0)
   - Rotation is NOT preserved (stays at 0,0,0)
   - Edge markers positioned for zero rotation
   - Connectivity labels positioned for zero rotation
   - Camera reframes to default view
   - **All labels correctly aligned!**

3. **Rotate Indiana to 90°, adjust bucket size**
   - Terrain recreated
   - Rotation IS preserved (stays at 90°)
   - Labels recreated at correct positions for 90° rotation
   - **Labels still aligned!**

### Console Logging

Added logging to verify behavior:
```
[TERRAIN] recreateTerrain() called from: ... (preserveTransform=false)
[RESOLUTION] autoAdjustBucketSize: rebucketing and recreating terrain (preserveTransform=false)...
```

## Key Insights

### Coordinate Space Architecture (Review)

The viewer uses hierarchical scene graph:
```
scene (world space, never rotates)
└── terrainGroup (local space, can rotate)
    ├── terrainMesh (terrain bars/surface)
    ├── edgeMarkers[] (compass balls)
    └── connectivityLabels[] (neighbor names)
```

**CRITICAL RULE:** All objects that should rotate with terrain MUST be added to `terrainGroup`, not `scene`.

### Position Calculation

Edge markers calculate positions using terrain extents:
```javascript
const xExtent = (gridWidth - 1) * bucketMultiplier / 2;
const zExtent = (gridHeight - 1) * bucketMultiplier / 2;

// North marker
position.set(0, 0, -zExtent * spreadMultiplier);
```

These calculations assume terrainGroup rotation is (0,0,0) when markers are created. If rotation is changed AFTER creation, the markers appear misaligned.

### Why This Was Hard to Spot

1. The bug only occurred when switching between regions (not when adjusting bucket size)
2. The rotation restoration happened inside `recreate()`, separate from `loadRegion()`
3. The position calculations were correct - the rotation timing was wrong
4. The misalignment accumulated with each region switch

## Related Documentation

- **Coordinate Space:** `learnings/COORDINATE_SPACE_ARCHITECTURE.md`
- **Edge Markers:** `js/edge-markers.js` (creation logic)
- **Connectivity Labels:** `js/state-connectivity.js` (positioning logic)
- **Terrain Lifecycle:** `learnings/REGION_SWITCHING_LIFECYCLE.md`

## Prevention Guidelines

### When Adding New Terrain-Relative Objects

1. **Always add to terrainGroup:**
   ```javascript
   window.terrainGroup.add(object); // CORRECT
   window.scene.add(object);        // WRONG if it should rotate with terrain
   ```

2. **Calculate positions assuming zero rotation:**
   - Edge markers use terrain extents directly
   - Don't apply rotation in position calculation
   - Let the parent group (terrainGroup) handle rotation

3. **Clear old objects before creating new ones:**
   ```javascript
   // Clear array (objects already disposed by terrain-renderer.js)
   window.edgeMarkers.length = 0;
   ```

### When Modifying Terrain Recreation

1. **Consider the context:**
   - New region load → Reset transform
   - Bucket size change → Preserve transform
   - Color change → No recreation needed

2. **Use parameters to control behavior:**
   - Don't assume one behavior fits all use cases
   - Make preservation explicit with parameters
   - Default to safe behavior (preserve = true)

3. **Log the context:**
   ```javascript
   console.log(`recreate() called from: ${caller} (preserveTransform=${preserveTransform})`);
   ```

## Summary

**Problem:** Old rotation preserved when loading new regions caused compass labels to be misaligned.

**Solution:** Added `preserveTransform` parameter through the call chain:
- `loadRegion()` → `autoAdjustBucketSize(false)` → `recreateTerrain(false)`
- Bucket size changes still preserve rotation (default `true`)

**Result:** Compass markers and labels now correctly positioned when switching regions!

