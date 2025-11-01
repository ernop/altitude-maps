# Vertical Exaggeration Fix - October 22, 2025

**Latest Update**: Range extended to 0.1-50.0, default set to 4.0 for better usability with meter-based scaling.

## Problem

Previously, vertical exaggeration was applied as a multiplier on elevation values (in meters) while horizontal coordinates used arbitrary pixel indices. This meant:

- **Horizontal scale**: 0 to width_pixels (arbitrary units)
- **Vertical scale**: elevation_meters x exaggeration

This made the meaning of "vertical exaggeration" confusing and dependent on:
- Image resolution (pixels)
- Geographic coverage area
- Elevation range

Even values like 0.01 or 0.05 felt "very exaggerated" because elevation in meters was already comparable to the pixel counts.

## Solution

Both horizontal and vertical coordinates now use **real-world meters** calculated from geographic bounds (lat/lon):

- **Horizontal scale**: Calculated from degrees to meters at appropriate latitude
- **Vertical scale**: elevation_meters x exaggeration
- **Vertical exaggeration = 1.0**: True Earth scale (1000m horizontal = 1000m vertical)
- **Vertical exaggeration = 2.0**: Mountains twice as steep as reality

### Calculation Method

```python
# Calculate real-world dimensions
lon_span = abs(bounds.right - bounds.left)  # degrees
lat_span = abs(bounds.top - bounds.bottom)  # degrees

# Meters per degree at center latitude
center_lat = (bounds.top + bounds.bottom) / 2.0
meters_per_deg_lon = 111_320 * cos(radians(center_lat))
meters_per_deg_lat = 111_320

# Convert to meters
width_meters = lon_span * meters_per_deg_lon
height_meters = lat_span * meters_per_deg_lat

# Scale pixel coordinates to meters
x_meters = pixel_x * (width_meters / image_width)
z_meters = pixel_y * (height_meters / image_height)
y_meters = elevation * vertical_exaggeration
```

## Changes Made

### Code Updates

1. **`src/rendering.py`**:
   - Added real-world scale calculation from geographic bounds
   - Converts X/Y coordinates from pixels to meters
   - Default vertical_exaggeration: 8.0 -> 4.0

2. **`interactive_viewer_advanced.html`**:
   - Added `calculateRealWorldScale()` function
   - Updated all terrain creation functions (bars, points, surface)
   - Updated border rendering to use meter coordinates
   - Slider range: 0.0001-5.0 -> 0.1-50.0
   - Default: 0.01 -> 4.0
   - Updated preset buttons: 0.001x, 0.01x, 0.1x, 1.0x, 2.0x -> 0.5x, 1.0x (True), 4.0x, 10.0x, 25.0x

3. **`visualize_real_data.py`**:
   - Default: 3.0 -> 4.0
   - Updated docstring and help text with range info

4. **`visualize_usa_overhead.py`**:
   - Default: 8.0 -> 4.0
   - Updated help text with range info

5. **Settings files**:
   - `settings.json`
   - `settings.example.json`
   - `load_settings.py`
   - All updated: 0.01 -> 4.0

### Documentation Updates

1. **`TECH.md`**: Updated command reference and slider range
2. **`QUICKSTART.md`**: Updated examples with new values
3. **`.cursorrules`**: Added explanation of vertical exaggeration scale

## Migration Guide

### For Users

**Old behavior (pixel-based)**:
```powershell
# Very small values were needed
python visualize_usa_overhead.py --vertical-exaggeration 0.01
```

**New behavior (meter-based)**:
```powershell
# Natural values that make sense
python visualize_usa_overhead.py --vertical-exaggeration 1.0   # True scale
python visualize_usa_overhead.py --vertical-exaggeration 4.0   # 4x dramatic (default)
python visualize_usa_overhead.py --vertical-exaggeration 10.0  # 10x dramatic
python visualize_usa_overhead.py --vertical-exaggeration 25.0  # Very extreme
```

### Interactive Viewer

The slider now uses intuitive ranges (0.1 to 50.0):
- **0.5x**: Very flat (mountains compressed)
- **1.0x**: True Earth scale (realistic proportions)
- **4.0x**: Default (moderately dramatic)
- **10.0x**: Very dramatic (mountains much steeper)
- **25.0x**: Extreme exaggeration
- **50.0x**: Maximum (ultra dramatic)

## Benefits

1. **Intuitive**: 1.0 means "looks like real Earth"
2. **Portable**: Same value works for any region/resolution
3. **Predictable**: 2.0 means "twice as steep as reality"
4. **Educational**: True scale helps understand actual terrain

## Technical Notes

- Uses WGS84 approximation: 1deg ~ 111,320 meters
- Adjusts for latitude (longitude degrees get smaller near poles)
- Both static renderer (matplotlib) and interactive viewer (Three.js) use same scale
- Borders also converted to meter coordinates for consistency

## Additional Improvements (User Contributions)

Along with the vertical exaggeration fix, the following enhancements were added:

1. **Smart Camera Positioning**: Camera distance now scales based on terrain size
2. **Bucket Size Fix**: Bars and points correctly maintain map extent when bucketed
3. **Controls Help Window**: Interactive popup with Roblox Studio-style controls guide
4. **Border Visibility Toggle**: Checkbox to show/hide country borders
5. **Edge Markers**: Cardinal direction labels (N/E/S/W) scale with terrain

## Testing Recommendations

After pulling this update:

1. Try the interactive viewer at `localhost:8001`
2. Set vertical exaggeration to 1.0 to see true Earth scale
3. Compare 1.0 vs 4.0 vs 10.0 vs 25.0 to understand the effect
4. Old visualizations with values like 0.01 should be re-rendered with new defaults (4.0)
5. Test the camera presets - they now scale properly with terrain size

## Related Files

- Core rendering: `src/rendering.py`
- Web viewer: `interactive_viewer_advanced.html`
- Export: `export_for_web_viewer.py` (data format unchanged)
- Settings: `settings.json`, `load_settings.py`
- Documentation: `TECH.md`, `QUICKSTART.md`, `.cursorrules`

