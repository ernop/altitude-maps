# Color Scale Legend Feature

## Overview
Added a visual color scale legend that displays in the lower-right corner of the map viewer, showing the mapping between colors and data values (elevation, slope, aspect, etc.).

## Implementation

### Files Created
- `js/color-legend.js` - Legend rendering and update logic

### Files Modified
- `interactive_viewer_advanced.html` - Added legend HTML structure
- `css/viewer-advanced.css` - Added legend styling and mobile responsiveness
- `js/viewer-advanced.js` - Integrated legend initialization and updates

### Features
1. **Dynamic Legend Display**
   - Shows color gradient from high (top) to low (bottom)
   - Displays 5 labeled values with appropriate units
   - Title updates based on color scheme (Elevation, Slope, Aspect, etc.)

2. **Color Scheme Support**
   - Works with all color schemes (elevation, slope, aspect, rainbow, etc.)
   - Handles special modes: slope (0-60°), aspect (0-360°)
   - Supports auto-stretch with dynamic ranges
   - Correctly renders banded color schemes (hypsometric-banded)

3. **Automatic Updates**
   - Updates when color scheme changes
   - Updates when new region loads
   - Updates after terrain recreation

4. **Responsive Design**
   - Positioned in lower-right of map area (not overlapping controls)
   - Scales down on mobile devices (< 768px)
   - Semi-transparent background with blur effect
   - Always visible above terrain, below UI controls

5. **Value Formatting**
   - Smart formatting based on magnitude (e.g., 1500m → 1.5km)
   - Appropriate precision for different ranges
   - Unit labels (m for elevation, ° for slope/aspect)

## Usage

### Toggle Control
- **"Show Scale" checkbox** in the Display section of the controls panel
- **Default: ON** (visible by default)
- **Persists**: State saved to localStorage
- Located alongside "Show HUD Overlay" and "Show Edge Markers" toggles

### Automatic Updates
The legend automatically updates when visible and when:
- User changes color scheme via dropdown
- User loads a different region
- Terrain is recreated (resolution change, etc.)

When the toggle is off, the legend is hidden and does not update (performance optimization).

## Technical Details

### Canvas Rendering
- Canvas: 50×200px (actual resolution)
- Display: 30×200px (CSS scaled for sharpness)
- Gradient rendered line-by-line for smooth color transitions
- Supports both interpolated and stepped (banded) gradients

### Positioning
- Positioned absolutely within `#canvas-container`
- Bottom-right corner with 20px margins (10px on mobile)
- z-index: 10 (above map, below UI overlays)

### Integration Points
- `initColorLegend()` - Called during viewer initialization
- `updateColorLegend()` - Called after `updateColors()` in all render modes
- Uses global `rawElevationData.stats` for min/max values
- Reads current `params.colorScheme` to determine display mode

## Future Enhancements (Optional)
- Toggle button to show/hide legend
- Draggable positioning (like HUD overlay)
- Horizontal orientation option
- More granular labels (7-10 stops instead of 5)
- Custom color scheme preview before applying

