# Coordinate Space Architecture

**Date**: November 6, 2025  
**Topic**: Three.js scene graph hierarchy and coordinate spaces

## Overview

The viewer uses a hierarchical scene graph with distinct coordinate spaces. Understanding this hierarchy is CRITICAL for positioning 3D objects correctly.

## Scene Hierarchy

```
scene (world space)
└── terrainGroup (rotation group)
    ├── terrainMesh (instanced bars)
    │   └── individual bars (local coordinates)
    ├── edgeMarkers[] (compass sprites)
    └── connectivityLabels[] (neighbor sprites)
```

## Coordinate Spaces

### World Space (scene)
- Origin: (0, 0, 0) in absolute world coordinates
- Used for: Camera position, lights, UI that should NOT rotate with terrain

### Terrain Group Space (terrainGroup)
- Origin: (0, 0, 0) - same as world space initially
- Purpose: Container for terrain and related objects that should rotate together
- Rotation: Can be rotated via UI controls - all children rotate together
- Used for: Terrain mesh, edge markers, connectivity labels

### Terrain Mesh Space (terrainMesh)
- Origin: Offset to center the grid at terrainGroup origin
- Offset: `(-gridWidth * bucket / 2, 0, -gridHeight * bucket / 2)`
- Purpose: Position grid so it's centered around (0, 0, 0) for rotation
- Used for: Individual bar instances

## The Critical Rule

**ALL objects that should move/rotate with terrain MUST be added to `terrainGroup`, NOT `scene`.**

### Correct Pattern
```javascript
// Objects that rotate with terrain
window.terrainGroup.add(sprite);
```

### Wrong Pattern (causes misalignment)
```javascript
// Don't do this for terrain-relative objects!
scene.add(sprite);
```

## Examples

### Edge Markers (Correct)
```javascript
// In edge-markers.js line 97
window.terrainGroup.add(sprite);
```
Edge markers stay at terrain edges when terrain rotates.

### Connectivity Labels (Fixed November 6, 2025)
```javascript
// OLD (WRONG) - line 366 in state-connectivity.js
scene.add(label); // ❌ Wrong coordinate space

// NEW (CORRECT)
window.terrainGroup.add(label); // ✓ Matches terrain coordinate space
```

### Bug Symptoms When Wrong
When objects are added to `scene` instead of `terrainGroup`:
1. Labels appear in wrong positions
2. Labels don't rotate when terrain rotates
3. Labels "drift" as camera moves
4. Position calculations seem correct but visual placement is wrong

## Position Calculations

When positioning objects in terrain group space:

```javascript
// Calculate terrain extents
const gridWidth = processedData.width;
const gridHeight = processedData.height;
const bucketMultiplier = params.bucketSize;
const xExtent = (gridWidth - 1) * bucketMultiplier / 2;
const zExtent = (gridHeight - 1) * bucketMultiplier / 2;

// Position at North edge (top of terrain)
sprite.position.set(0, 0, -zExtent * 1.25);

// Add to terrainGroup (NOT scene)
window.terrainGroup.add(sprite);
```

The `1.25` multiplier pushes markers beyond terrain edges for visibility.

## Why This Architecture?

### Benefits
1. **Rotation support**: Terrain and all related objects rotate together
2. **Clean separation**: World-fixed UI vs terrain-relative objects
3. **Simplified math**: Positions calculated relative to terrain center
4. **Consistent behavior**: All terrain-related objects use same coordinate system

### Terrain Mesh Offset
The terrain mesh itself is offset inside terrainGroup:
```javascript
terrainMesh.position.x = -(width - 1) * bucketMultiplier / 2;
terrainMesh.position.z = -(height - 1) * bucketMultiplier / 2;
```

This centers the grid around terrainGroup origin (0, 0, 0) so:
- Grid extends from `-extent` to `+extent` in both X and Z
- Origin is at center of terrain
- Rotation happens around center (natural rotation point)

## Checking Object Parents

To debug positioning issues:
```javascript
console.log('Sprite parent:', sprite.parent.name || sprite.parent.type);
// Should log: "Group" (terrainGroup is a THREE.Group)
// NOT: "Scene" (wrong parent)
```

## Related Files

- `js/terrain-renderer.js` - Creates terrainGroup and positions terrainMesh
- `js/edge-markers.js` - Adds edge markers to terrainGroup
- `js/state-connectivity.js` - Adds connectivity labels to terrainGroup (fixed Nov 6, 2025)
- `js/viewer-advanced.js` - Creates scene and terrainGroup

## Future Considerations

When adding new 3D objects, ask:
1. **Should it rotate with terrain?** → Add to `terrainGroup`
2. **Should it stay fixed in world space?** → Add to `scene`

Examples:
- Terrain bars → `terrainGroup`
- Edge markers → `terrainGroup`
- Connectivity labels → `terrainGroup`
- Ground plane visualization → `terrainGroup`
- Camera → `scene` (world space)
- Lights → `scene` (typically world space)
- Fixed UI overlays → `scene`

