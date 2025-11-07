# Camera State URL Persistence

Date: 2025-11-06
Status: Implemented

## Overview

Camera position, orientation, and map rotation are now persisted in the URL query string, enabling shareable links that preserve exact camera views.

## Implementation

### URL Parameters

Camera state is encoded using 9 URL parameters:

**Camera Position (required):**
- `cx` - Camera X position (meters)
- `cy` - Camera Y position (meters, altitude)
- `cz` - Camera Z position (meters)

**Focus Point (optional, defaults to origin):**
- `fx` - Focus point X (where camera looks)
- `fy` - Focus point Y
- `fz` - Focus point Z

**Terrain Rotation (optional, defaults to zero):**
- `rx` - Terrain rotation around X axis (radians)
- `ry` - Terrain rotation around Y axis (radians)
- `rz` - Terrain rotation around Z axis (radians)

### Example URLs

**Basic overhead view:**
```
?region=california&cx=0.00&cy=2200.00&cz=2.20
```

**Tilted view with focus point:**
```
?region=ohio&cx=500.00&cy=1500.00&cz=800.00&fx=100.00&fy=0.00&fz=50.00
```

**Rotated map view:**
```
?region=tennessee&cx=0.00&cy=2000.00&cz=1000.00&ry=0.785&rz=0.524
```

## Behavior

### Loading from URL

1. URL parameters are parsed in `applyParamsFromURL()`
2. Camera state is stored in `window.urlCameraState` (if present)
3. When region loads, `applyCameraStateFromURL()` is called instead of `reframeView()`
4. Camera position, focus point, and terrain rotation are applied
5. `window.urlCameraState` is cleared after application

### Updating URL During Use

1. `updateCameraStateInURL()` is called every frame in the animation loop
2. Camera state is captured and compared to previous frame
3. If changed, sets `cameraIsMoving = true`
4. When state stops changing (camera stops moving) AND no mouse buttons are held, URL is updated immediately
5. Only significant changes trigger updates (threshold: 0.01)

### Optimization Details

**Movement Detection:**
- Compares current frame state to previous frame state
- Sets `cameraIsMoving = true` when state changes
- Updates URL only when BOTH conditions are met:
  - Camera has stopped moving (state hasn't changed for at least one frame)
  - No mouse buttons are held down (`activeMouseButtons === 0`)
- No artificial delay - updates the instant movement stops AND mouse is released

**Change Detection:**
- Compares current state to `lastCameraState`
- Threshold of 0.01 prevents floating point noise from triggering updates
- Skips update if no significant change

**Mouse Button Tracking:**
- Uses bitmask to track which buttons are pressed (`activeMouseButtons`)
- `mousedown` sets the corresponding bit: `activeMouseButtons |= (1 << e.button)`
- `mouseup` clears the corresponding bit: `activeMouseButtons &= ~(1 << e.button)`
- Prevents URL updates during drag operations (keeps URL stable during interaction)
- Resets to 0 when mouse leaves canvas (prevents stuck button state)

**Precision:**
- Position values rounded to 2 decimal places (centimeter precision)
- Rotation values rounded to 3 decimal places (milliradians)
- Keeps URLs readable and prevents excessive precision

**Optional Parameters:**
- Focus point omitted if at origin (fx=0, fy=0, fz=0)
- Rotation omitted if no rotation (rx=0, ry=0, rz=0)
- Reduces URL clutter for common cases

### History Management

Uses `window.history.replaceState()` instead of `pushState()`:
- Avoids cluttering browser history with every camera movement
- Back button takes you to previous region, not previous camera position
- Shareable URL always reflects current view

## Integration with Existing Features

### Region Switching

When switching regions:
1. `window.urlCameraState` is cleared after first use
2. New region loads with default reframed view
3. New camera position is captured in URL
4. Prevents old camera state from applying to new region

### Camera Schemes

Works with all camera schemes:
- Ground Plane (default)
- Google Earth
- Roblox Studio
- Flying
- Jumping
- Blender
- Unity Editor

Each scheme's focus point is updated if it has a `focusPoint` property.

### F Key (Reframe)

Pressing F reframes to default view and updates URL to reflect new position.

### Share Links

The `copyShareLink()` function copies the current URL including camera state, making it easy to share exact views with others.

## Code Locations

**URL Parameter Parsing:**
- `applyParamsFromURL()` in `js/viewer-advanced.js` (lines 170-245)

**Applying Camera State:**
- `applyCameraStateFromURL()` in `js/viewer-advanced.js` (lines 2404-2440)

**Updating URL:**
- `updateCameraStateInURL()` in `js/viewer-advanced.js` (lines 2442-2534)
- Called from `animate()` loop (line 3029)
- Uses frame-to-frame comparison to detect when movement stops

**Region Loading:**
- Modified in `loadRegionData()` (lines 990-1002)
- Checks for `window.urlCameraState` before calling `reframeView()`

## Testing

Test the feature by:

1. **Manual URL construction:**
   ```
   http://localhost:8001?region=california&cx=500&cy=1500&cz=800
   ```

2. **Move camera and observe URL:**
   - Pan, zoom, rotate the view
   - Watch URL update after stopping movement
   - Verify parameters change in address bar

3. **Copy and share URL:**
   - Move camera to interesting position
   - Copy URL from address bar
   - Open in new tab or share with someone
   - Verify exact camera position is restored

4. **Region switching:**
   - Load region with camera parameters
   - Switch to different region
   - Verify new region uses default view (not old camera state)
   - Verify URL updates with new camera position

## Performance Impact

Minimal performance impact:
- URL update check runs every frame (~60fps)
- Early exit if no significant change (fast comparison)
- Actual URL update only when camera stops moving (typically once per interaction)
- No geometry regeneration or heavy computation
- Uses `replaceState()` (fast DOM operation)
- Instant feedback - URL updates immediately when movement stops

## Future Enhancements

Potential improvements:
- Add camera animation when loading from URL (smooth transition to saved position)
- Compress parameters for shorter URLs (base64 encoding)
- Add preset camera positions (save/load named views)
- QR code generation for mobile sharing
- Social media preview images with camera view

