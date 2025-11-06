anRegion Switching Lifecycle

**Date**: November 6, 2025  
**Topic**: What gets recreated and what persists when switching regions

## The Problem

When switching from one region to another (e.g., California → New Mexico), edge markers and connectivity labels were being positioned incorrectly. They would use the old region's dimensions until a page refresh.

**Root Cause**: The arrays (`window.edgeMarkers`, `window.connectivityLabels`) still had references to sprites from the destroyed terrainGroup, so the check `if (edgeMarkers.length === 0)` was false and new markers weren't created.

## The Solution: Centralized Lifecycle Management

**One place controls everything**: `js/terrain-renderer.js` → `create()` function

### When Region Switches

**What happens in order:**

1. **Destroy old terrain** (line 56):
   ```javascript
   window.scene.remove(window.terrainGroup);
   ```
   - Old terrainGroup is removed from scene
   - ALL children (terrain mesh, edge markers, connectivity labels) are removed with it

2. **Clear marker arrays** (lines 62-66):
   ```javascript
   if (window.edgeMarkers) {
       window.edgeMarkers.length = 0;
   }
   if (window.connectivityLabels) {
       window.connectivityLabels.length = 0;
   }
   ```
   - Clear the arrays so new markers can be created
   - Critical: Old sprites are already gone (removed with terrainGroup), but arrays still had references

3. **Create new terrainGroup** (line 70):
   ```javascript
   window.terrainGroup = new THREE.Group();
   window.scene.add(window.terrainGroup);
   ```
   - Fresh, empty group for the new region

4. **Create new terrain mesh** (line 81):
   ```javascript
   createBars(width, height, elevation, scale);
   ```
   - Uses `window.processedData` (new region's data)
   - Added to terrainGroup

5. **Create new edge markers** (line 123):
   ```javascript
   createEdgeMarkers();
   ```
   - Uses new region's `processedData.width` and `processedData.height`
   - Sprites added to terrainGroup
   - Populates `window.edgeMarkers` array

6. **Create new connectivity labels** (line 131):
   ```javascript
   createConnectivityLabels();
   ```
   - Uses new region's dimensions
   - Sprites added to terrainGroup
   - Populates `window.connectivityLabels` array

## What Gets Recreated Every Region Switch

### Always Recreated (Fresh Each Time)
1. **terrainGroup** - New THREE.Group() every time
2. **terrainMesh** - New InstancedMesh with new region's bars
3. **Edge markers** - New sprites at new positions
4. **Connectivity labels** - New sprites for new neighbors
5. **Navigation panel** - DOM elements cleared and repopulated

### Persists Across Regions
1. **scene** - The main THREE.Scene (never destroyed)
2. **camera** - Same camera instance, just repositioned
3. **lights** - Ambient and directional lights stay
4. **Arrays** - `window.edgeMarkers` and `window.connectivityLabels` arrays persist (but are cleared)
5. **Controls** - Camera control scheme instance persists

## Critical Rules

### Rule 1: Single Point of Control
**All lifecycle management happens in `terrain-renderer.js` → `create()`**
- Don't clear arrays in multiple places
- Don't remove terrainGroup in multiple places
- One function owns the entire lifecycle

### Rule 2: Arrays Are References
**Arrays persist, but must be cleared when terrainGroup is destroyed**
```javascript
// WRONG - creates new array, breaks references
window.edgeMarkers = [];

// RIGHT - clears existing array, keeps references
window.edgeMarkers.length = 0;
```

### Rule 3: Always Recreate with New Terrain
**Don't check `if (array.length === 0)`** - always create markers when terrain is created
```javascript
// WRONG - might skip creation if array has stale references
if (window.edgeMarkers.length === 0) {
    createEdgeMarkers();
}

// RIGHT - always create markers for new terrain
createEdgeMarkers();
```

### Rule 4: Add to terrainGroup, Not scene
**All terrain-relative objects go in terrainGroup**
```javascript
// RIGHT - rotates with terrain
window.terrainGroup.add(sprite);

// WRONG - doesn't rotate with terrain
scene.add(sprite);
```

## Debugging Region Switch Issues

### Check Console Logs
```
[EDGE MARKERS] Creating markers for grid: 512x512
[Connectivity] Creating labels for california with grid: 512x512
```

If dimensions are wrong, check:
1. Is `processedData` updated before `createEdgeMarkers()` is called?
2. Are arrays cleared before creating new markers?
3. Is terrainGroup recreated each time?

### Common Symptoms

**Markers in wrong positions**:
- Arrays not cleared → old references prevent new creation
- processedData stale → using old region's dimensions

**Markers don't appear**:
- Added to scene instead of terrainGroup
- terrainGroup not added to scene

**Markers appear then disappear**:
- Added before terrainGroup is created
- terrainGroup recreated after markers added

## Files Modified

- **`js/terrain-renderer.js`** - Centralized lifecycle management
- **`js/edge-markers.js`** - Simplified to just create markers (cleanup handled centrally)
- **`js/state-connectivity.js`** - Simplified to just create labels (cleanup handled centrally)

## Testing

To verify the fix:
1. Load California
2. Check console: `Creating markers for grid: 512x512` (example)
3. Load New Mexico (different shape)
4. Check console: `Creating markers for grid: 512x512` (different dimensions)
5. Markers should be positioned correctly immediately (no refresh needed)

