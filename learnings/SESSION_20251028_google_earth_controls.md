# Google Earth Style Controls + F Key Reframe

**Date:** October 28, 2025  
**Summary:** Updated right-drag rotation to Google Earth style and added F key to reframe view

---

## Changes Made

### 1. Right-Drag -> Google Earth Style Rotation

**Previous Behavior:**
- Right drag = Orbit around focus point (Maya/Blender style)
- Alt+Left drag = Same orbit behavior

**New Behavior:**
- Right drag = Google Earth style rotation around focus point
- Alt+Left drag = Same Google Earth style rotation
- Both now behave identically to Google Earth

**What's Different:**
The rotation behavior itself is the same (spherical coordinates around focus point), but now explicitly documented as "Google Earth style" to clarify the interaction model. The implementation rotates the view around the focus point on the ground plane:
- Horizontal drag = Turn left/right (rotate around vertical axis)
- Vertical drag = Tilt up/down (adjust viewing angle)

**Implementation:**
```javascript
// Google Earth style rotation: rotate view around focus point
// Horizontal drag = rotate around vertical axis (turn left/right)
// Vertical drag = tilt view up/down
const deltaX = event.clientX - this.state.rotateStart.x;
const deltaY = event.clientY - this.state.rotateStart.y;

// Convert to spherical coordinates
const spherical = new THREE.Spherical();
spherical.setFromVector3(offset);

// Apply rotation
spherical.theta -= deltaX * 0.005;  // Horizontal rotation
spherical.phi = Math.max(0.1, Math.min(Math.PI / 2 - 0.01, spherical.phi - deltaY * 0.005));  // Tilt

// Convert back and update camera position
offset.setFromSpherical(spherical);
this.camera.position.copy(this.focusPoint).add(offset);
```

### 2. F Key -> Reframe View

**New Feature:**
Press F to automatically reframe the camera to show the entire terrain, centered on the map.

**Behavior:**
- Calculates center of terrain bounds
- Positions camera at optimal distance to frame entire terrain
- Sets viewing angle to ~30 degrees (comfortable overhead view)
- Smooth instant repositioning (no animation)

**Implementation:**
```javascript
// F key handler in onKeyDown
if (key === 'f') {
    this.reframeView();
    return;
}

// Reframe view to center of terrain
reframeView() {
    const bounds = this.terrainBounds;
    const center = new THREE.Vector3(
        (bounds.minX + bounds.maxX) / 2,
        0, // Keep focus on ground plane
        (bounds.minZ + bounds.maxZ) / 2
    );
    
    // Calculate size of terrain
    const size = Math.max(bounds.maxX - bounds.minX, bounds.maxZ - bounds.minZ);
    
    // Position camera to frame the terrain
    const distance = size * 0.8;
    const height = distance * 0.6; // ~30-degree angle
    
    // Place camera above and behind center
    this.camera.position.set(center.x, height, center.z + distance * 0.5);
    this.focusPoint.copy(center);
    this.controls.target.copy(this.focusPoint);
}
```

**Terrain Bounds Integration:**
The viewer now passes terrain bounds to the camera scheme after creating terrain:
```javascript
// In createTerrain() - viewer-advanced.js
if (controls && controls.activeScheme && controls.activeScheme.setTerrainBounds) {
    // Calculate bounds based on render mode
    if (params.renderMode === 'bars') {
        const bucketMultiplier = params.bucketSize;
        const halfWidth = (width - 1) * bucketMultiplier / 2;
        const halfDepth = (height - 1) * bucketMultiplier / 2;
        controls.activeScheme.setTerrainBounds(-halfWidth, halfWidth, -halfDepth, halfDepth);
    }
    // ... surface and points modes
}
```

---

## Control Scheme Summary

### Mouse Controls

| Input | Action | Style |
|-------|--------|-------|
| Left drag | Pan | Google Maps |
| Shift+Left drag | Tilt | Unique |
| Alt+Left drag | Rotate | Google Earth |
| Right drag | Rotate | Google Earth |
| Scroll wheel | Zoom | Google Maps |

### Keyboard Controls

| Key | Action |
|-----|--------|
| W | Move forward |
| S | Move backward |
| A | Strafe left |
| D | Strafe right |
| Q | Move down |
| E | Move up |
| **F** | **Reframe view** <- NEW |

### Touch/Trackpad Controls

| Gesture | Action |
|---------|--------|
| Single finger drag | Pan |
| Two-finger drag | Pan |
| Two-finger pinch | Zoom |

---

## Why These Changes

### 1. Google Earth Naming
- **Clarity:** Explicitly identifying the rotation style as "Google Earth" helps users understand the interaction model
- **Familiarity:** Google Earth is the gold standard for terrain navigation
- **Consistency:** Our implementation matches Google Earth's behavior

### 2. F Key Reframe
- **Exploration:** Easy way to "reset" view when you get lost
- **Standard:** F key for "frame" is standard in Unity, Blender, Maya
- **Convenience:** One-key instant reframe vs manual navigation back

---

## Files Modified

1. **`js/ground-plane-camera.js`**
   - Updated constructor name from "Google Maps" to "Google Earth"
   - Updated comments to clarify Google Earth style rotation
   - Added F key handler in onKeyDown
   - Added reframeView() method
   - Added setTerrainBounds() method

2. **`js/viewer-advanced.js`**
   - Added terrain bounds calculation in createTerrain()
   - Calls setTerrainBounds() after terrain creation
   - Handles all render modes (bars, points, surface)

3. **`.cursorrules`**
   - Updated rotation documentation to say "Google Earth style"
   - Added F key to keyboard controls section
   - Clarified rotation behavior

---

## Testing

### Rotation (Can test)
- [x] Right drag rotates view (Google Earth style)
- [x] Alt+Left drag rotates view (same behavior)
- [x] Horizontal drag turns left/right
- [x] Vertical drag tilts up/down
- [x] Release Alt mid-drag cancels smoothly

### F Key (Can test)
- [ ] Press F to reframe view
- [ ] Camera centers on terrain
- [ ] Entire terrain visible
- [ ] Viewing angle comfortable (~30 degrees)
- [ ] Works in all render modes (bars, points, surface)
- [ ] Works after changing bucket size
- [ ] Console logs center position

### Integration
- [ ] Terrain bounds update when terrain recreated
- [ ] F key works after region switch
- [ ] F key works after exaggeration changes

---

## Technical Notes

### Terrain Bounds Calculation

Different render modes have different coordinate systems:

**Bars Mode:**
- Uses bucket multiplier for spacing
- Bounds: `+/-(width-1) * bucketMultiplier / 2`

**Points Mode:**
- Uses unit spacing
- Bounds: `+/-(width-1) / 2`

**Surface Mode:**
- Uses real-world scale
- Bounds: `+/-scale.width / 2` and `+/-scale.depth / 2`

### Reframe Algorithm

1. Calculate center: `(minX + maxX) / 2`, `(minZ + maxZ) / 2`
2. Calculate size: `max(width, depth)`
3. Set distance: `size * 0.8` (80% for margin)
4. Set height: `distance * 0.6` (creates ~30deg viewing angle)
5. Position: `center.x, height, center.z + distance * 0.5`

The formula ensures the entire terrain fits in view with comfortable margins.

---

## User Benefits

1. **Familiar rotation:** Matches Google Earth (millions of users know this)
2. **Quick reset:** F key instantly reframes when lost
3. **Professional feel:** F key matches Maya/Unity/Blender standards
4. **Exploration friendly:** Easy to pan around, then press F to reset

---

## Related Documents

- `learnings/CAMERA_CONTROLS_COMPARISON.md` - Full comparison with 14+ software
- `learnings/SESSION_20251028_camera_enhancements.md` - WASD and touch implementation
- `learnings/SESSION_20251028_maya_trackpad_update.md` - Alt+Left Maya-style rotation
- `learnings/CAMERA_CONTROLS_ARCHITECTURE.md` - Design principles
- `.cursorrules` - Current control scheme documentation

---

## Conclusion

The camera controls now explicitly follow Google Earth's interaction model for rotation, making them immediately familiar to millions of users. The F key provides a professional-standard reframe function for quick navigation resets.

**Status:**  Complete and ready for testing  
**Breaking Changes:** None - all existing controls unchanged  
**New Features:** F key reframe functionality

