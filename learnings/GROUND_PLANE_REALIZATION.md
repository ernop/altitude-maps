# The Ground Plane Revelation

## The Missing Concept

All professional map viewers (Google Maps, Google Earth, Mapbox, etc.) work with a **fundamental ground plane** concept that I was missing:

### The Ground Plane Model

1. **Fixed Reference Plane**: A horizontal plane (y=0) representing the map surface
2. **Focus Point**: A point ON that plane where the camera is currently looking
3. **Camera State**: Position in 3D space + focus point on plane
4. **All Operations Relative to Plane**: Every camera movement is defined relative to this plane

### Why This Matters

**Without plane concept** (what I was doing):
- Camera moves arbitrarily in 3D space
- No consistent reference
- Pan/zoom/rotate are disconnected operations
- Hard to keep intuitive behavior

**With plane concept** (what Google does):
- Camera always relates to the ground plane
- Focus point is the anchor
- All operations are predictable
- Natural, intuitive behavior

## The Three Operations

### 1. Pan (Google Maps left-drag)
- **What it does**: Slides the focus point along the plane
- **Camera movement**: Follows parallel to the plane, maintaining height
- **Key**: Camera height above plane never changes
- **Implementation**: 
  - Get mouse movement in screen space
  - Project to plane movement
  - Translate focus point on plane
  - Move camera to maintain same relative position

### 2. Zoom (Scroll wheel)
- **What it does**: Moves camera perpendicular to plane
- **Direction**: Toward/away from focus point
- **Key**: Focus point on plane stays fixed
- **Implementation**:
  - Get cursor position
  - Raycast to plane to find target point
  - Move camera toward/away from that point
  - Perpendicular to plane only

### 3. Rotate/Tilt (Right-drag, varies by app)
- **Google Maps**: Orbit around focus point at fixed height
- **Google Earth**: Tilt (change pitch angle) or orbit
- **Key**: Always relative to focus point on plane
- **Implementation**:
  - Orbit around focus point
  - Maintain distance from focus point
  - Can change pitch (tilt) but always looking at plane

## Why User Kept Saying "Center Point"

The user was referring to the **focus point on the ground plane**! This is the fundamental anchor that everything revolves around. Without understanding this, I was:
- Trying to track arbitrary 3D points
- Losing the reference during operations
- Creating janky, unpredictable behavior

## Implementation Strategy

```javascript
class GroundPlaneCameraSystem {
    constructor() {
        this.groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
        this.focusPoint = new THREE.Vector3(0, 0, 0); // ON the plane
        this.camera = camera;
    }
    
    pan(screenDeltaX, screenDeltaY) {
        // Convert screen movement to plane movement
        // Move focusPoint on plane
        // Move camera parallel to plane
    }
    
    zoom(amount, cursorScreenPos) {
        // Raycast cursor to plane
        // Move camera toward/away from that point
        // Perpendicular to plane only
    }
    
    rotate(deltaX, deltaY) {
        // Orbit camera around focusPoint
        // Maintain distance from plane
    }
}
```

## The Real Implementations

### Google Maps (Research Needed)
- Uses Web Mercator projection
- 2D tiles on a plane
- Camera always parallel to ground (no tilt in default view)
- Pan is pure XZ translation
- Zoom is Y-axis movement + FOV adjustment

### Google Earth (Research Needed)
- Spherical Earth model
- Tangent plane at current location
- More complex: handles globe curvature
- Can tilt camera (change pitch)
- Can rotate around vertical axis

### Key Insight
They all start with **a plane** and **a focus point**. Everything else is built on top of this foundation.

## Next Steps

1. Implement proper ground plane camera system
2. Research actual Google Maps/Earth camera code
3. Test with real examples
4. Validate against user expectations

The user was right to keep pushing on this - the plane is THE fundamental concept I was missing!

