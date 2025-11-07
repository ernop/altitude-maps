# Hypsometric 12-Band Color Schemes

## Summary
Created two 12-band hypsometric color schemes with adjustable boundaries:
1. **hypsometric-intense**: Super intense version with vivid saturated colors spanning the full spectrum
2. **hypsometric-refined**: Muted, naturalistic version with earthy tones and better visual balance

## Implementation Details

### Color Schemes

**hypsometric-intense** (Super Intense):
- **Colors**: Vivid saturated colors spanning the full spectrum
  - Deep ocean blue (0x001a33) → Deep forest green (0x004d00) → Bright green (0x00b300)
  - Lime (0x66ff00) → Bright yellow (0xffff00) → Vivid orange (0xff9900)
  - Red-orange (0xff4400) → Pure red (0xff0000) → Magenta (0xcc0066)
  - Purple (0x9900cc) → Light grey (0xcccccc) → White peaks (0xffffff)
- **Default stops**: [0.00, 0.08, 0.17, 0.25, 0.33, 0.42, 0.50, 0.58, 0.67, 0.75, 0.83, 0.92, 1.00]
- **Use case**: Maximum visual distinction between elevation bands

**hypsometric-refined** (Refined/Muted):
- **Colors**: Naturalistic earth tones with lower saturation
  - Deep teal-green (0x1a3d3d) → Forest green (0x2d5a3d) → Moss green (0x4a7c4e)
  - Olive green (0x6b9b5f) → Yellow-green (0x9bb076) → Sandy tan (0xb89d6a)
  - Ochre (0xc0845f) → Terra cotta (0xb36b52) → Brown-red (0x9a5a47)
  - Dark brown (0x7a503f) → Grey-brown (0xa09090) → Light grey peaks (0xe0e0e0)
- **Default stops**: [0.00, 0.08, 0.17, 0.25, 0.33, 0.42, 0.50, 0.58, 0.67, 0.75, 0.83, 0.92, 1.00]
- **Use case**: Professional cartographic presentation with natural appearance

### Band Editor Enhancement
Extended the band editor (`js/band-editor.js`) to support multiple banded schemes:

1. **Configuration-driven architecture**: Added `SCHEME_CONFIGS` object mapping scheme names to their stops and colors
2. **Multi-scheme support**: Changed from single scheme to multi-scheme with separate localStorage per scheme
3. **Automatic scheme switching**: Band editor UI automatically recreates sliders when switching between banded schemes
4. **Backward compatibility**: Handles migration from old single-array format to new multi-scheme object format

### Rendering Updates
Updated these files to recognize all three banded schemes:

1. **js/map-shading.js**: Extended `isBanded` check to include `hypsometric-intense` and `hypsometric-refined`
2. **js/color-legend.js**: Extended `isBanded` check to include `hypsometric-intense` and `hypsometric-refined`
3. **interactive_viewer_advanced.html**: Added dropdown options:
   - "Hypsometric (Refined 12-Band)" - recommended default for 12-band use
   - "Hypsometric (Super Intense 12-Band)" - for maximum visual impact

### User Experience
- Selecting any banded scheme shows the band editor
- Three schemes available:
  - `hypsometric-banded` (8 bands) - Original scheme
  - `hypsometric-refined` (12 bands) - Naturalistic earth tones
  - `hypsometric-intense` (12 bands) - Vivid saturated colors
- Each scheme maintains its own custom band boundaries in localStorage
- Sliders are color-coded with swatches matching each band's color
- Real-time updates with no lag (GPU-side rendering)
- Reset button restores default boundaries for current scheme
- Switching between schemes preserves custom settings for each

## Testing
To test the schemes:
1. Open the viewer and select a region
2. Choose "Hypsometric (Refined 12-Band)" from Color Scheme dropdown (recommended)
3. Band editor appears with 11 adjustable sliders (12 bands = 11 interior boundaries)
4. Drag sliders to adjust band boundaries - changes apply instantly
5. Switch to "Hypsometric (Super Intense 12-Band)" to compare
6. Reset button restores default evenly-distributed boundaries for active scheme

## Files Modified
- `js/color-schemes.js` - Added new scheme definition and description
- `js/band-editor.js` - Refactored to support multiple banded schemes
- `js/map-shading.js` - Updated banded rendering logic
- `js/color-legend.js` - Updated legend rendering logic
- `interactive_viewer_advanced.html` - Added dropdown option

## Design Rationale

### Why 12 Bands?
- More granularity than the 8-band scheme for finer elevation discrimination
- Provides better resolution for complex terrain with wide elevation ranges
- Adjustable boundaries allow users to emphasize features at specific elevation ranges

### Two Intensity Levels
**Refined (Recommended)**:
- Naturalistic earth tones (greens → tans → browns → greys)
- Lower saturation prevents visual fatigue
- Professional cartographic appearance
- Better for general use and presentations
- Similar to traditional topographic map color schemes

**Intense (High Impact)**:
- Vivid saturated colors spanning full spectrum
- Maximum visual distinction between bands
- Dramatic visual impact for presentations
- Better for highlighting subtle elevation changes
- Trade-off: higher saturation can be visually tiring

### Technical Benefits
- **Independent settings**: Each scheme has separate saved boundaries in localStorage
- **Instant switching**: Compare different color schemes without losing customizations
- **Backward compatible**: Works alongside existing 8-band scheme

