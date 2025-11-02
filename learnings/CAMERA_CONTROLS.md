# Camera Controls - Comprehensive Documentation

**Last Updated:** November 2025  
**Status:** Implemented and Production-Ready

---

## Quick Summary

### What Was Fixed
When dragging the map, the point under your cursor would slide away - the map "raced" ahead or lagged behind your mouse. This made navigation frustrating and imprecise.

**Solution:** Raycasting-based camera control system with true "point-stays-under-cursor" behavior.

### Key Improvements
1. **Point-Under-Cursor Dragging** - Uses raycasting to keep the exact 3D point locked under cursor during drag
2. **Zoom-to-Cursor** - Zoom moves toward/away from the point under cursor, not just forward/backward
3. **Simple Ground Plane** - Uses y=0 plane as fallback when cursor is over sky

### How to Test
Visit: `http://localhost:8001/interactive_viewer_advanced.html`
1. Left-click on a specific mountain and drag - it should stay glued under cursor
2. Move cursor over a peak, scroll wheel - should zoom directly toward that peak
3. Try at different zoom levels - should feel consistent

---

## Architecture

### Problem Statement

The original camera controls used Three.js OrbitControls with a dynamic `panSpeed` multiplier. This approach has fundamental issues:

1. **No Point Tracking**: Pan speed multipliers can't provide true "point-stays-under-cursor" behavior
2. **Inconsistent Feel**: Speed adjustments based on distance/FOV/terrain create unpredictable behavior
3. **Racing**: Map moves too fast or slow - point under cursor slides away during drag
4. **Wrong Abstraction**: We're trying to solve a geometric problem (keep point locked) with speed tuning

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
```javascript
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

---

## Implementation Details

### Files Modified
- `interactive_viewer_advanced.html`: Main implementation

### New Functions
- `raycastToWorld(x, y)`: Convert screen position to 3D world point
- `onMouseDown/Move/Up()`: Custom mouse handlers for pan
- `linearZoom()`: Rewritten for zoom-to-cursor

### New Variables
- `groundPlane`: Simple y=0 plane for fallback when cursor misses terrain
- `isPanning`, `panStartWorldPoint`, `panStartCameraPos`, `panStartTargetPos`: Pan state
- `currentMouseX`, `currentMouseY`: Track cursor for zoom-to-cursor

### Disabled
- `OrbitControls.enablePan = false`
- `OrbitControls.mouseButtons.LEFT = -1`
- Removed `updateDynamicPanSpeed()` (obsolete)

### Core Algorithm
```javascript
// Old approach (WRONG)
controls.panSpeed = (frustumHeight / terrainScale) * baseSensitivity;
// Complex, unpredictable, never quite right

// New approach (CORRECT)
const worldDelta = pickedPoint - currentPoint;
camera.position += worldDelta;
// Simple, perfect, always works
```

---

## Software Comparison

Altitude Maps implements a **Ground Plane Camera System** designed specifically for 3D terrain visualization, drawing inspiration from Google Maps and Google Earth.

### Key Innovations

1. **Single `lookAt()` per Frame**: Prevents jitter from competing camera orientation updates
2. **Raycasting-Based Pan**: Geometric solution ensures point-under-cursor stays locked during drag
3. **Bidirectional Focus Shift in Zoom**: Both camera and focus point move during zoom to prevent conflict
4. **Shift-Release Cancellation**: Graceful exit from tilt mode if modifier key released mid-drag
5. **Screen-Space Pan with Adaptive Speed**: Smooth dragging without continuous raycasting overhead

### Control Mapping

| Action | Input | Behavior |
|--------|-------|----------|
| **Pan** | Left Drag | "Grab and drag" the map surface along ground plane |
| **Tilt** | Shift + Left Drag | Adjust viewing angle (pitch): drag down = see more land, drag up = overhead view |
| **Rotate** | Right Drag | Orbit camera around focus point (theta and phi adjustment) |
| **Zoom** | Mouse Wheel | Zoom toward/away from point under cursor (scroll up = zoom in) |

### Technical Architecture

**Ground Plane Model:**
- Fixed ground plane at `y = 0` (the map surface)
- Focus point anchored ON the plane (where camera looks)
- All operations relative to this plane
- Spherical coordinate system for rotation (theta, phi, radius)

**Camera Orientation:**
- `camera.lookAt()` called ONLY in `update()` loop (once per frame)
- NEVER in mouse event handlers (prevents jitter)
- Synchronized with rendering loop at 60fps

### Closest Competitors

1. **Google Earth** - Industry standard for terrain exploration
   - Altitude Maps matches its smoothness
   - Altitude Maps has simpler, more explicit controls
   
2. **ArcGIS Scene Viewer** - Professional GIS terrain visualization
   - Similar control scheme (left-drag pan, right-drag rotate)
   - ArcGIS more complex (full GIS suite)
   
3. **Cesium** - Open-source 3D geospatial platform
   - Both web-based, smooth performance
   - Cesium globe-focused, Altitude Maps flat-plane-focused

### Unique Technical Innovations

#### 1. Single `lookAt()` Call Per Frame
**Problem Solved:** Camera orientation jitter from competing updates

```javascript
// In mouse handlers: Update positions only
this.camera.position.copy(newPosition);
this.controls.target.copy(this.focusPoint);
// DON'T call lookAt() here!

// In update() loop: Single orientation update per frame
update() {
    if (this.enabled && this.focusPoint) {
        this.camera.lookAt(this.focusPoint); // ONLY place
    }
}
```

**Result:** Buttery smooth camera orientation, no jitter, synchronized with 60fps render loop.

#### 2. Bidirectional Focus Shift in Zoom
**Problem Solved:** Conflict between camera movement and focus point during zoom

```javascript
// Move camera toward cursor point
this.camera.position.addScaledVector(direction, moveAmount);

// ALSO shift focus point toward cursor
const focusShift = event.deltaY > 0 ? -0.1 : 0.1;
this.focusPoint.addScaledVector(towardsCursor, focusShift);
```

**Result:** Smooth, natural zoom feel where both camera and focus move together in the same direction.

#### 3. Shift-Release Cancellation
**Problem Solved:** Jarring behavior when modifier key released mid-drag

```javascript
if (this.state.tilting && !event.shiftKey) {
    console.log('Tilt cancelled (Shift released)');
    this.state.tilting = false;
    return; // Gracefully exit
}
```

**Result:** If you accidentally release Shift while dragging, tilt mode cancels smoothly.

---

## Design Philosophy

### Geometric Solution Over Speed Tuning

**Traditional Approach:** Adjust `panSpeed`, `zoomSpeed`, etc. with complex formulas
```javascript
// Complex, unpredictable
controls.panSpeed = (frustumHeight / terrainScale) * baseSensitivity;
```

**Altitude Maps Approach:** Solve the geometric problem directly
```javascript
// Simple, direct
const worldDelta = pickedPoint - currentPoint;
camera.position += worldDelta;
```

### Raycasting-Based Precision
Use raycasting to find exact 3D points rather than estimating with speed multipliers. This ensures:
- Point under cursor stays locked during pan
- Zoom moves toward exact feature you're pointing at
- No sliding, no racing, no guesswork

### Google Maps/Earth-Inspired But Refined
Takes the best ideas from industry leaders:
- Ground plane model from Google Maps
- Zoom-to-cursor from Google Earth
- Clean control separation for precision

But adds technical improvements:
- No `lookAt()` jitter (single call per frame)
- Bidirectional focus shift (smoother zoom)
- Better documentation (this file!)

---

## Testing & Validation

### Test Scenarios

1. **Drag Test**: Left-click on a specific mountain or feature and drag it around. The feature should stay glued under your cursor - no sliding.

2. **Zoom Test**: Move cursor over a peak, scroll wheel. You should zoom directly toward that peak.

3. **Different Zoom Levels**: Try close-up and far away - should feel consistent.

4. **Rotation Test**: Right-click or Ctrl+left-click - should still work as before.

5. **Tilt Test**: Shift+left-drag - should adjust viewing angle smoothly.

### Known Issues & Limitations

**Current Limitations:**
- No touch/trackpad gesture support (planned enhancement)
- Shift+drag for tilt is non-standard (Alt+drag more common in professional tools)
- No WASD flythrough mode (game engines have this)
- No visual mode indicator (could add overlay)

**Not Issues:**
- Ground plane at y=0 is intentional (simple, consistent reference)
- No middle-mouse support is intentional (accessibility - trackpad users)
- Focused on terrain visualization (not general-purpose 3D tool)

---

## Future Enhancements

### Short-Term
1. **Touch/Trackpad Gestures** - Pinch-to-zoom, two-finger pan (HIGH PRIORITY)
2. **Alt+Drag Alternative** - Add Alt+left-drag as alternative to Shift for tilt
3. **Cursor Visual Feedback** - Change cursor icon for different operations

### Long-Term
1. **WASD Flythrough Mode** - Optional keyboard-based camera movement
2. **Customizable Control Schemes** - Settings panel to remap controls
3. **Camera Path Recording** - Record/replay camera movements for presentations

---

## Technical References

- Three.js Raycaster: https://threejs.org/docs/#api/en/core/Raycaster
- OrbitControls source: Shows how to mix custom and OrbitControls behavior
- Google Earth: Reference implementation of this interaction model
- Source code: `js/ground-plane-camera.js`
- Project standards: `.cursorrules`

---

**Document Status:** Consolidated from 4 separate files (Architecture, Comparison, Implementation, Summary)  
**Maintained By:** Altitude Maps Project  
**For Questions:** See project documentation or source code comments

