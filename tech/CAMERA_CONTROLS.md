# Camera Controls - Ground Plane System

Complete documentation of the camera control system used in Altitude Maps interactive viewer.

## Overview

The camera system is based on a **ground plane** architecture, modeled after Google Earth and Google Maps for intuitive navigation. The key concept is a fixed ground plane (y=0) representing the map surface, with a focus point that anchors camera operations.

## Core Architecture

### Ground Plane Model

1. **Fixed Reference Plane**: Horizontal plane (y=0) representing the map surface
2. **Focus Point**: A point ON that plane where the camera is currently looking
3. **Camera State**: Position in 3D space + focus point on plane
4. **All Operations Relative to Plane**: Every camera movement is defined relative to this plane

### Why This Works

**Benefits**:
- Camera always relates to the ground plane
- Focus point provides a consistent anchor
- All operations are predictable
- Natural, intuitive behavior

**Without plane concept**:
- Camera moves arbitrarily in 3D space
- No consistent reference
- Pan/zoom/rotate are disconnected operations
- Hard to keep intuitive behavior

## Control Behaviors

### 1. Pan (Left-Click Drag)

**Behavior**: "Grab and drag" the map surface

- Drag DOWN → map moves down (northward)
- Drag UP → map moves up (southward)
- Drag LEFT → map moves left (eastward)
- Drag RIGHT → map moves right (westward)

**Implementation**: Screen-space movement for smoothness
- Speed: Adaptive based on distance from focus point (distance * 0.001)
- Camera and focus point move together, maintaining view angle
- Point under cursor stays visually stable

### 2. Tilt View (Shift + Left-Click Drag)

**Behavior**: Change viewing angle to see more/less terrain

- Drag DOWN → tilt down (increase phi angle, see more land/horizon)
- Drag UP → tilt up (decrease phi angle, more overhead view)

**Implementation**: Spherical coordinate adjustment around focus point
- Angle limits: 0.1 to π/2 - 0.01 radians (prevents camera flip)
- Tilt speed: 0.005 radians per pixel
- Focus point stays fixed on ground plane
- Cancels smoothly if Shift released mid-drag

### 3. Rotate (Right-Click Drag)

**Behavior**: Orbit camera around current focus point

- Horizontal drag (deltaX) → rotate around vertical axis (theta)
- Vertical drag (deltaY) → adjust pitch angle (phi)

**Implementation**: Spherical coordinate transformation
- Rotation speed: 0.005 radians per pixel
- Maintains constant distance from focus point
- Same angle limits as tilt to prevent flipping

### 4. Zoom (Mouse Wheel)

**Behavior**: Zoom toward point under cursor (Google Maps style)

- Scroll UP (negative delta) → zoom IN (camera moves toward cursor point)
- Scroll DOWN (positive delta) → zoom OUT (camera moves away from cursor point)
- Zoom factor: 10% of distance per scroll tick
- Minimum distance: 5 meters (prevents getting too close)

**Critical Feature - Bidirectional focus shift**:
- Zoom IN: Focus moves toward cursor (focusShift = +0.1)
- Zoom OUT: Focus moves away from cursor (focusShift = -0.1)
- This ensures camera AND focus move in same direction
- Cursor point stays visually stable under mouse

## Keyboard Controls

### Movement
- **W**: Move up (raise camera vertically)
- **S**: Move down (lower camera vertically)
- **A**: Rotate left (spin counter-clockwise)
- **D**: Rotate right (spin clockwise)
- **Q**: Move backward (fly away from view direction)
- **E**: Move forward (fly toward view direction)
- **R**: Reset (return to default camera position)
- **F**: Focus (same as R, Roblox Studio style)
- **Space**: Auto-rotate (toggle automatic rotation)

### Speed Modifiers
- **None**: 1.0× (normal speed)
- **Shift**: 2.5× (fast movement)
- **Ctrl**: 0.3× (brush/precise movement)
- **Alt**: 4.0× (very fast movement)
- **Shift+Alt**: 10× (turbo mode)

### Examples
- `Shift + W` = Move up fast
- `Ctrl + A` = Rotate left slowly (precise)
- `Alt + E` = Fly forward very fast

## Critical Implementation Pattern

### DO NOT Call camera.lookAt() in Event Handlers

**Correct Pattern**:
```javascript
// In mouse event handlers (onMouseMove, onWheel):
// 1. Calculate new camera position
this.camera.position.copy(newPosition);

// 2. Update focus point if needed
this.focusPoint.copy(newFocusPoint);

// 3. Update controls target
this.controls.target.copy(this.focusPoint);

// 4. DO NOT call camera.lookAt() here!

// In update() loop (called by requestAnimationFrame):
update() {
    if (this.enabled && this.focusPoint) {
        this.camera.lookAt(this.focusPoint); // ONLY place this is called
    }
}
```

**Why This Works**:
- Single source of truth for camera orientation (no fighting between handlers)
- Synchronized with render loop (60fps, no micro-stutters)
- Predictable timing regardless of input frequency
- Standard pattern used by Three.js OrbitControls and professional systems

### What NOT To Do

 Don't call camera.lookAt() in mouse handlers (causes jitter)  
 Don't use continuous raycasting for pan (too slow/jerky)  
 Don't make focus shift unidirectional (breaks zoom out feel)  
 Don't forget to cancel operations if modifier keys released mid-drag

## Camera Near/Far Planes - CRITICAL

 **DO NOT MODIFY** without understanding depth buffer implications

### Current Safe Settings
```javascript
camera = new THREE.PerspectiveCamera(60, aspect, 1, 100000);
//                                              ^  ^^^^^^
//                                           near   far
//                                           1m    100km
//                                         Ratio: 100,000:1 
```

### The Problem

Extreme near/far ratios cause depth buffer precision loss:
- Symptoms: Jagged "bleeding" artifacts where distant geometry appears in front of nearby geometry
- Worse at oblique viewing angles
- **Root cause**: 24-bit depth buffer cannot maintain precision across extreme ratios

### Rules to Follow

 **GOOD PRACTICES**:
- Near plane: 1-10 meters for terrain visualization
- Far plane: 10,000-100,000 meters for terrain
- Ratio: Keep under 1,000,000:1
- Current values: near=1, far=100000 (ratio 100,000:1) 

 **NEVER DO THIS**:
```javascript
//  Extreme ratios cause artifacts
camera = new THREE.PerspectiveCamera(60, aspect, 0.001, 50000000);
// Ratio: 50,000,000,000:1  GUARANTEED ARTIFACTS

//  "I want to see everything"
camera = new THREE.PerspectiveCamera(60, aspect, 0.001, 10000000);

//  "Infinite far plane to be safe"
camera = new THREE.PerspectiveCamera(60, aspect, 1, Number.MAX_VALUE);
```

### Advanced Solutions

If you genuinely need extreme view distances:

1. **Logarithmic Depth Buffer**: Requires custom shaders
2. **Dynamic Near/Far Adjustment**: Calculate based on scene bounds
3. **Multi-Pass Rendering**: Render near/far objects separately
4. **Level of Detail**: Don't render distant objects at full detail

See `learnings/DEPTH_BUFFER_PRECISION_CRITICAL.md` for detailed information.

## Performance Optimization

The camera system is optimized for smooth 60 FPS:

1. **Single lookAt() Call**: Only in render loop, not in event handlers
2. **Debouncing**: 150ms delay on slider changes prevents excessive updates
3. **Synchronized Updates**: All camera/controls updates happen in animation loop
4. **Conservative Near/Far**: Reasonable ratio prevents precision issues

## Testing Recommendations

After any camera modifications:

1. Load viewer: `python serve_viewer.py`
2. Test pan: Left-click and drag - feature should stay under cursor
3. Test zoom: Scroll over a peak - should zoom toward that point
4. Test rotate: Right-click and drag - should orbit smoothly
5. Test tilt: Shift + left drag - should change viewing angle smoothly
6. Test at different zoom levels: Close-up and far away should feel consistent
7. Check for depth buffer artifacts: Look for geometry bleeding through

## Related Documentation

- **Technical details**: See `TECHNICAL_REFERENCE.md` for complete API
- **Implementation details**: See camera control implementation in interactive viewer
- **Depth buffer**: See `learnings/DEPTH_BUFFER_PRECISION_CRITICAL.md`
- **Ground plane concept**: See `learnings/GROUND_PLANE_REALIZATION.md`
- **Camera architecture**: See `learnings/CAMERA_CONTROLS_ARCHITECTURE.md`

## Summary

The camera system provides intuitive, Google Earth-style navigation through a ground plane architecture. Key principles:

- **Ground plane**: Fixed reference for all operations
- **Focus point**: Anchor that everything revolves around
- **Single lookAt()**: Only called in render loop for smoothness
- **Reasonable near/far ratio**: 100,000:1 maximum for depth precision
- **Bidirectional focus shift**: Essential for smooth zoom experience

This design provides buttery-smooth navigation that matches user expectations from professional mapping applications.

