# Camera Controls Architecture

## Problem Statement

The original camera controls used Three.js OrbitControls with a dynamic `panSpeed` multiplier. This approach has fundamental issues:

1. **No Point Tracking**: Pan speed multipliers can't provide true "point-stays-under-cursor" behavior
2. **Inconsistent Feel**: Speed adjustments based on distance/FOV/terrain create unpredictable behavior
3. **Racing**: Map moves too fast or slow - point under cursor slides away during drag
4. **Wrong Abstraction**: We're trying to solve a geometric problem (keep point locked) with speed tuning

## Correct Architecture

### Core Principle: Raycasting-Based Dragging

For pan/strafe (left-click drag):
1. **On mousedown**: Raycast from cursor to find 3D world point that was clicked
2. **On mousemove**: Raycast from current cursor position into 3D space
3. **Calculate offset**: Determine how much the picked point has "moved" in world space
4. **Apply correction**: Translate camera and target to keep the picked point under cursor

This is a **geometric solution** not a **speed-tuning solution**.

### Implementation Strategy

#### 1. Raycasting System
- Cast ray from camera through screen-space cursor position
- Intersect with terrain geometry (mesh or ground plane)
- Handle miss cases (cursor over sky) with ground plane fallback

#### 2. Pan/Strafe (Left-Click Drag)
```
On Mouse Down:
  - Raycast to get pickedPoint3D (world coordinates)
  - Store pickedPoint3D and initial camera/target positions

On Mouse Move:
  - Raycast to get currentPoint3D (world coordinates)
  - Calculate worldDelta = pickedPoint3D - currentPoint3D
  - camera.position += worldDelta
  - controls.target += worldDelta
  - Update: picked point is now back under cursor
```

#### 3. Rotate (Right-Click or Ctrl+Left Drag)
- Keep OrbitControls' rotation behavior (it works well)
- Set controls.target to the clicked point (rotate around that point)
- Use raycasting to pick rotation pivot point

#### 4. Zoom (Scroll Wheel)
- Move camera toward/away from cursor point (zoom-to-cursor)
- Raycast to find point under cursor
- Lerp camera position toward that point
- Adjust target proportionally to maintain view

#### 5. Keyboard Movement (WASD/QE)
- Keep current implementation (works well)
- Move camera and target together in view-relative directions

### Key Implementation Details

#### Ground Plane Fallback
When raycasting misses terrain (cursor over sky):
- Use an infinite horizontal plane at terrain mid-elevation
- Ensures we always have a point to work with
- Prevents "no intersection" errors

#### Dual-Mode Controls
- **Left-Click Drag**: Custom raycasting pan (this implementation)
- **Right-Click Drag**: OrbitControls rotation (keep existing)
- **Ctrl+Left Drag**: OrbitControls rotation (keep existing)
- Disable OrbitControls.enablePan, implement pan ourselves

#### Performance Considerations
- Raycasting is fast enough for mouse events (~once per frame during drag)
- Only raycast when needed (during drag, not every frame)
- Cache terrain geometry reference for intersection tests

### Benefits of This Approach

1. **Perfect Tracking**: Point under cursor stays locked - no sliding
2. **Predictable**: No complex speed formulas, just geometry
3. **Scale-Independent**: Works at any zoom level, terrain size, or FOV
4. **Intuitive**: Matches Google Earth, Google Maps, most modern map viewers
5. **Debuggable**: Can visualize picked point, ray, intersections

### Migration Path

1. Keep OrbitControls for rotation (works well)
2. Disable OrbitControls.enablePan
3. Add custom mousedown/mousemove/mouseup handlers for pan
4. Implement raycasting with ground plane fallback
5. Test across different regions and zoom levels
6. Remove old `updateDynamicPanSpeed()` function (no longer needed)

## Technical References

- Three.js Raycaster: https://threejs.org/docs/#api/en/core/Raycaster
- OrbitControls source: Shows how to mix custom and OrbitControls behavior
- Google Earth: Reference implementation of this interaction model

