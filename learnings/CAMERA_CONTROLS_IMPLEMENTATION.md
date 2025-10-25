# Camera Controls Implementation - October 25, 2025

## Problem Solved

The original camera controls had a fundamental flaw: during pan/drag operations, the point under the cursor would slide away. This was caused by using speed multipliers on mouse deltas instead of true geometric point-tracking.

## Solution: Raycasting-Based Controls

Implemented a proper raycasting-based camera control system with true "point-stays-under-cursor" behavior.

### Key Changes

#### 1. Pan/Strafe (Left-Click Drag)
**Before:** OrbitControls with dynamic `panSpeed` multiplier
- Complex formulas based on distance, FOV, terrain scale
- Point under cursor would slide/race
- Unpredictable behavior

**After:** Custom raycasting implementation
- On mousedown: Raycast to find 3D world point under cursor
- On mousemove: Raycast again, calculate world-space delta
- Apply delta to camera and target to keep point locked under cursor
- Ground plane fallback (y=0) when cursor misses terrain

```javascript
// Core algorithm
const worldDelta = panStartWorldPoint - currentWorldPoint;
camera.position += worldDelta;
controls.target += worldDelta;
// Result: Point stays perfectly locked under cursor
```

#### 2. Zoom (Mouse Wheel)
**Before:** Linear zoom in view direction
- Moved camera forward/backward in current view direction
- No relationship to cursor position

**After:** Zoom-to-cursor
- Raycast to find 3D point under cursor
- Move camera toward/away from that specific point
- Distance-based speed (15% of distance per tick)
- Shift modifier for precise control (3% per tick)
- Orbit target gradually moves toward cursor point for smooth feel

#### 3. Rotation (Right-Click or Ctrl+Left-Click)
**Unchanged:** OrbitControls rotation behavior (works well)

### Implementation Details

**Files Modified:**
- `interactive_viewer_advanced.html`: Main implementation

**New Functions:**
- `raycastToWorld(x, y)`: Convert screen position to 3D world point
- `onMouseDown/Move/Up()`: Custom mouse handlers for pan
- `linearZoom()`: Rewritten for zoom-to-cursor

**New Variables:**
- `groundPlane`: Simple y=0 plane for fallback when cursor misses terrain
- `isPanning`, `panStartWorldPoint`, `panStartCameraPos`, `panStartTargetPos`: Pan state
- `currentMouseX`, `currentMouseY`: Track cursor for zoom-to-cursor

**Disabled:**
- `OrbitControls.enablePan = false`
- `OrbitControls.mouseButtons.LEFT = -1`
- Removed `updateDynamicPanSpeed()` (obsolete)

### Benefits

1. **Perfect Point Tracking**: Point under cursor stays locked during drag - no sliding
2. **Predictable**: Simple geometry, no complex speed formulas
3. **Scale-Independent**: Works at any zoom level, terrain size, or FOV
4. **Intuitive**: Matches Google Earth, Google Maps interaction model
5. **Maintainable**: Clear code, easy to debug

### Design Philosophy

**Geometric Solution > Speed Tuning**
- Old approach: Try to tune speed multipliers to feel right
- New approach: Solve the geometric problem directly

**Simplicity**
- Ground plane at y=0 (not mid-elevation, not scaled by vertical exaggeration)
- Just provides a consistent reference for raycasting
- Works perfectly for dragging and zooming

### Testing

**To Test:**
1. Visit http://localhost:8001/interactive_viewer_advanced.html
2. Load any region (e.g., Colorado, Japan, Switzerland)
3. **Test Pan**: Left-click on a specific feature and drag - it should stay under cursor
4. **Test Zoom**: Move cursor over a mountain peak, scroll - should zoom toward that peak
5. **Test at Different Zoom Levels**: Close-up and far away - tracking should be consistent
6. **Test Rotation**: Right-click or Ctrl+left-click - should still work as before

### Future Improvements

- Consider showing a visual indicator of the raycast hit point during drag
- Potentially add "sticky" behavior when cursor is over a landmark
- Add touch/trackpad gesture support with same raycasting approach

## References

- Architecture doc: `learnings/CAMERA_CONTROLS_ARCHITECTURE.md`
- Three.js Raycaster: https://threejs.org/docs/#api/en/core/Raycaster
- Google Earth: Reference implementation for this interaction pattern

