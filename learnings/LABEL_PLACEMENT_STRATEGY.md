# Label Placement Strategy

**Date**: November 6, 2025  
**Topic**: Current implementation and optimal placement options for navigation labels

## Current Placement System

### 1. Edge Markers (Compass Letters: N, S, E, W)

**Position**: At terrain edges, at ground level
```javascript
// Position calculations
const xExtent = (gridWidth - 1) * bucketMultiplier / 2;
const zExtent = (gridHeight - 1) * bucketMultiplier / 2;
const spreadMultiplier = 1.25; // Push beyond edges

// Cardinal positions
North:  x=0,                      z=-zExtent * 1.25, y=0
South:  x=0,                      z=+zExtent * 1.25, y=0
East:   x=+xExtent * 1.25,        z=0,               y=0
West:   x=-xExtent * 1.25,        z=0,               y=0
```

**Visual**:
- Scale: `avgSize * 0.06` (size adapts to terrain)
- Colors: Red (N), Blue (S), Green (E), Yellow (W)
- Always visible at ground level (y=0)

---

### 2. Connectivity Labels (Neighboring Regions)

**Position**: Below edge markers, negative Y
```javascript
const verticalStartOffset = -avgSize * 0.12; // Start below ground
const labelSpacing = labelHeight * 2.5;      // Stack vertically

// Example (3 neighbors to the north):
Label 1: x=0, z=-zExtent*1.25, y=-avgSize*0.12 - spacing*1
Label 2: x=0, z=-zExtent*1.25, y=-avgSize*0.12 - spacing*0
Label 3: x=0, z=-zExtent*1.25, y=-avgSize*0.12 + spacing*1
```

**Visual**:
- Scale: Wide rectangles (5:1 aspect ratio)
- Colors: Match edge marker direction (red for north neighbors, etc.)
- Stack vertically, centered on edge marker position
- Example: "Oregon" label below the "N" marker for California

**Purpose**: Navigate to adjacent regions (states/countries that share a border)

---

### 3. Contained Area Labels (Regions Within This Region)

**Position**: Center of map, ABOVE terrain
```javascript
const yOffset = totalHeight / 2 + avgSize * 0.15; // Elevated above terrain

// Example (2 contained areas):
Label 1: x=0, z=0, y=+avgSize*0.15 + spacing*0.5  (top)
Label 2: x=0, z=0, y=+avgSize*0.15 - spacing*0.5  (bottom)
```

**Visual**:
- Color: Purple/Magenta (`0xff88ff`)
- Position: Floating above terrain center
- Stack vertically if multiple areas

**Purpose**: "Zoom in" navigation - click to jump to smaller contained regions
- Example: California showing "San Francisco", "Mavericks", "San Mateo Area"

---

### 4. Within Labels (Parent Regions Containing This Area)

**Position**: Center of map, BELOW terrain
```javascript
const yOffset = -totalHeight / 2 - avgSize * 0.20; // Below terrain

// Example (2 parent regions):
Label 1: x=0, z=0, y=-avgSize*0.20 - spacing*0.5  (top)
Label 2: x=0, z=0, y=-avgSize*0.20 - spacing*1.5  (bottom)
```

**Visual**:
- Color: Cyan (`0x44ffff`)
- Position: Below terrain center (can be obscured!)
- Stack vertically if multiple parent regions

**Purpose**: "Zoom out" navigation - click to jump to larger containing regions
- Example: San Francisco showing "California" (parent state)
- Example: Alcatraz showing "California" (parent state)

---

## Current Issues

### Problem 1: "Within" Labels Below Terrain

For small areas (parks, islands, points of interest), the "zoom out" button is positioned below the terrain, which can be:
- **Obscured by tall terrain**: Mountain peaks or elevated terrain hide the label
- **Hard to find**: Users naturally look up/around, not down/below
- **Unintuitive**: "Back" or "Zoom out" buttons are usually in consistent UI positions (top-left corner, etc.)

**Example scenario**: User loads "Alcatraz Island"
- Problem: They want to zoom out to see California, but the cyan "California" label is below the island terrain
- User might not even know there's a way to zoom out

### Problem 2: Center Overlap Risk

Both contained and within labels are at center (x=0, z=0), just different Y heights:
- If a region has both contained areas AND is within a parent, they're vertically stacked at center
- Could be confusing with many labels

### Problem 3: Camera Angle Dependence

Labels positioned below terrain (negative Y) are only visible from certain camera angles:
- Low camera angles: Below-terrain labels hidden
- High camera angles: Above-terrain labels might be small/far

---

## Placement Options

### Option A: Fixed Screen-Space "Back" Button (Recommended for Small Areas)

**Concept**: For AREA-type regions (small parks, islands), add a persistent "Back" or "Zoom Out" button in screen space (2D overlay)

**Pros**:
- Always visible, never obscured
- Familiar UI pattern (every app has a back button)
- Doesn't depend on camera angle or terrain height
- Clear exit path for users

**Cons**:
- Breaks the "all navigation in 3D space" pattern
- Requires 2D UI overlay system

**Implementation**:
```javascript
// Add to HTML (top-left corner)
<div id="parentRegionButton" style="position: absolute; top: 60px; left: 10px;">
  ↑ Back to California
</div>

// Show only for AREA-type regions with 'within' relationship
if (currentRegionType === RegionType.AREA && withinData) {
  document.getElementById('parentRegionButton').style.display = 'block';
}
```

---

### Option B: Above-Terrain Placement for "Within" Labels

**Concept**: Move "within" labels to ABOVE terrain (like contained labels), but separate them spatially

**Positions**:
- **Contained areas** (purple): Center top, elevated high (`y = +avgSize * 0.25`)
- **Within/Parent** (cyan): Center bottom, elevated low (`y = +avgSize * 0.05`)

**Pros**:
- Always visible from any camera angle
- Still in 3D space (consistent pattern)
- Color-coded for clarity (purple = zoom in, cyan = zoom out)

**Cons**:
- Center can get crowded with many labels
- Still not as discoverable as a fixed UI button

---

### Option C: Edge Placement for "Within" Labels

**Concept**: Put "within" labels at a specific edge (e.g., South edge, below "S" marker)

**Position**:
```javascript
// Position within labels at South edge, below terrain
x = 0
z = +zExtent * 1.25  // South edge
y = -avgSize * 0.12  // Same as connectivity labels
```

**Pros**:
- Out of the way (doesn't clutter center)
- Consistent position (always at south edge)
- Similar to connectivity labels (familiar pattern)

**Cons**:
- Still can be obscured by terrain
- Asymmetric (all other labels are north/east/west/center)

---

### Option D: Corner Positioning

**Concept**: Use 3D space corners for special navigation

**Positions**:
- **Contained areas** (purple): Northeast corner (`x=+xExtent*1.25, z=-zExtent*1.25`)
- **Within/Parent** (cyan): Southwest corner (`x=-xExtent*1.25, z=+zExtent*1.25`)

**Pros**:
- Clear separation (no overlap possible)
- Utilizes unused space (corners not used for anything else)
- Symmetric and balanced

**Cons**:
- Far from center (might be off-screen in tight views)
- Less intuitive (users might not look at corners)

---

### Option E: Dynamic Height Adjustment

**Concept**: Sample terrain height at label position and place label above the tallest nearby point

**Implementation**:
```javascript
// Sample terrain height at center
const centerHeight = getTerrainHeightAt(0, 0);
const maxNearbyHeight = sampleHeightsInRadius(0, 0, avgSize * 0.2);

// Place labels above tallest point
const withinYOffset = maxNearbyHeight + avgSize * 0.1;
```

**Pros**:
- Never obscured by terrain
- Adaptive to terrain shape

**Cons**:
- Complex calculation
- Position changes based on terrain (inconsistent)
- Doesn't solve discoverability issue

---

## Recommendations

### For Small AREA Regions (Parks, Islands, Points of Interest)

**Use Option A: Fixed Screen-Space "Back" Button**

Reasoning:
- Small areas need clear exit path
- Users expect a "back" button in consistent location
- Never obscured, always discoverable
- Familiar UX pattern

Implementation:
```javascript
// Show button for AREA regions with parent
if (regionType === RegionType.AREA && withinData) {
  showParentButton(withinData); // Show in top-left corner
}
```

---

### For Large Regions with Contained Areas (States, Countries)

**Keep Current System: Center Above Terrain (Purple)**

Reasoning:
- Works well for large regions (California, Pennsylvania)
- Center is natural focal point
- Not too many contained areas per region (typically 1-5)

Optional Enhancement:
- Add heading text: "Areas Within California:" above the labels
- Group by type (islands, cities, mountain ranges)

---

### For Regions That Are Both Containers and Contained

**Example**: A region that contains smaller areas AND is within a larger region

Use **Option B: Tiered Above-Terrain Placement**:
- Top tier (high, purple): Contained areas (zoom in)
- Bottom tier (low, cyan): Parent regions (zoom out)
- Both above terrain, separated by height

---

## Visual Summary

```
                    [Contained Areas - Purple]
                    Floating high above center
                           ↓ Zoom In
    
[W]  ←  West Neighbors                    East Neighbors  →  [E]
        (Yellow labels)                    (Green labels)


                    [TERRAIN CENTER]
                    

                    [Within/Parent - Cyan]
                    Floating low above center
                           ↑ Zoom Out


[S]  ↓  South Neighbors (Blue labels)


Alternative for small areas:
┌─────────────────────────┐
│ ↑ Back to California    │  ← Fixed UI button
│                         │
│      [Terrain]          │
│                         │
└─────────────────────────┘
```

---

## Implementation (November 6, 2025)

**Solution Chosen: 2D Navigation Panel in Lower-Left Corner**

Based on user feedback, implemented a fixed 2D UI panel with two columns:

### Design
```
┌─────────────────────────────┐
│ Contains    │    Part of    │  ← Lower-left corner panel
│ ─────────   │   ────────    │
│ • San Fran  │  • California │
│ • Mavericks │               │
│ • San Mateo │               │
└─────────────────────────────┘
```

### Features
- **Always visible**: Never obscured by terrain or camera angle
- **Color-coded**: Purple border for "Contains" (zoom in), Cyan border for "Part of" (zoom out)
- **Hover effects**: Background highlight and slide animation on hover
- **Click to navigate**: Single click jumps to that region
- **Auto-hide**: Only shows when region has containment relationships
- **Responsive**: Adapts to number of items (1-2 columns)

### Benefits Over 3D Labels
1. **Discoverability**: Fixed position, always in same place
2. **Accessibility**: DOM elements work with screen readers
3. **No obstruction**: Never hidden by terrain height
4. **Clear organization**: Two distinct columns with headers
5. **Scalable**: Can show many items without crowding 3D space

### Technical Implementation
- **HTML**: Added `<div id="region-navigation">` in lower-left
- **CSS**: Styled with semi-transparent background, color-coded borders
- **JavaScript**: Populates panel instead of creating 3D sprites
- **Integration**: Shows/hides automatically based on adjacency data

### Current System (After Implementation)
1. **Edge Markers (N/S/E/W)**: 3D sprites at terrain edges
2. **Neighbor Labels**: 3D sprites below edge markers
3. **Contains/Part Of**: 2D panel in lower-left corner ← NEW

## Next Steps

1. ✅ **DONE**: Add fixed navigation panel for containment relationships
2. **Future**: Add keyboard shortcuts (Tab to cycle, Enter to select)
3. **Future**: Consider hierarchy breadcrumbs (e.g., "San Francisco → California → USA")
4. **Future**: Add region thumbnail previews on hover

