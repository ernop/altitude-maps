# viewer-advanced.js Function Analysis

**Total:** 107 functions, 4,323 lines

## Natural Groupings by Correlation

### 🎨 GROUP 1: TERRAIN RENDERING PIPELINE (~600 lines)
**Core rendering logic - tightly coupled**

| Function | Lines | Purpose |
|----------|-------|---------|
| `createTerrain()` | 81 | Main orchestrator |
| `createBarsTerrain()` | 165 | 3D rectangular prisms (instanced) |
| `createPointCloudTerrain()` | 58 | Point cloud rendering |
| `createSurfaceTerrain()` | 77 | Smooth surface mesh |
| `recreateTerrain()` | 3 | Rebuild wrapper |
| `updateTerrainHeight()` | 37 | Update Y values |
| `updateColors()` | 82 | Recolor terrain |
| `getColorForElevation()` | 55 | Color calculation |
| `computeDerivedGrids()` | 35 | Slope/aspect |
| `getSlopeDegrees()` | 7 | Slope at point |
| `getAspectDegrees()` | 7 | Aspect at point |

**Extraction potential:** HIGH - Could be `terrain-renderer.js`

---

### 📊 GROUP 2: DATA LOADING & PROCESSING (~500 lines)
**Data acquisition and preparation**

| Function | Lines | Purpose |
|----------|-------|---------|
| `loadRegion()` | 100 | Load region data |
| `loadElevationData()` | 55 | Fetch elevation JSON |
| `loadBorderData()` | 23 | Fetch border data |
| `loadRegionsManifest()` | 19 | Fetch manifest |
| `populateRegionSelector()` | 109 | Build dropdown |
| `resolveRegionIdFromInput()` | 12 | Name→ID |
| `updateRegionInfo()` | 14 | Update UI |
| `rebucketData()` | 114 | Aggregate data |
| `computeAutoStretchStats()` | 25 | Percentile calc |

**Extraction potential:** MEDIUM - Some couples to UI

---

### 🎛️ GROUP 3: RESOLUTION CONTROLS (~400 lines)
**Bucket size / detail level management**

| Function | Lines | Purpose |
|----------|-------|---------|
| `initResolutionScale()` | 186 | Slider initialization |
| `updateResolutionScaleUI()` | 13 | Update slider |
| `adjustBucketSize()` | 46 | Change resolution |
| `setMaxResolution()` | 40 | Max detail |
| `setDefaultResolution()` | 22 | Default detail |
| `autoAdjustBucketSize()` | 53 | Auto-calculate |
| `bucketSizeToPercent()` | 6 | Convert to % |
| `percentToBucketSize()` | 7 | Convert from % |
| `showResolutionLoading()` | 6 | Loading overlay |
| `hideResolutionLoading()` | 7 | Hide overlay |
| `updateResolutionInfo()` | 18 | Info display |

**Extraction potential:** HIGH - Could be `resolution-controls.js`

---

### 🗺️ GROUP 4: BORDERS & CONTOURS (~250 lines)
**Rendering border lines and contours**

| Function | Lines | Purpose |
|----------|-------|---------|
| `recreateBorders()` | 141 | Border line rendering |
| `createContourLines()` | 73 | Generate contours |
| `traceContourLevel()` | 101 | Contour algorithm |

**Extraction potential:** HIGH - Self-contained

---

### 🎭 GROUP 5: LIGHTING & SHADING (~120 lines)
**Light sources and material setup**

| Function | Lines | Purpose |
|----------|-------|---------|
| `updateMaterialsForShading()` | 3 | Update materials |
| `updateSunLightDirection()` | 10 | Sun position |
| `updateLightingForShading()` | 39 | Light configuration |
| `initSunPad()` | 34 | Sun control UI |
| `drawSunPad()` | 36 | Render sun control |

**Extraction potential:** MEDIUM - Visual tool

---

### 📍 GROUP 6: EDGE MARKERS (~100 lines)
**N/E/S/W directional labels**

| Function | Lines | Purpose |
|----------|-------|---------|
| `createEdgeMarkers()` | 58 | Create markers |
| `createTextSprite()` | 37 | Text rendering |
| `updateEdgeMarkers()` | 10 | Update positions |

**Extraction potential:** HIGH - Very isolated

---

### 📈 GROUP 7: HUD & CURSOR INFO (~200 lines)
**Heads-up display with elevation/slope/aspect**

| Function | Lines | Purpose |
|----------|-------|---------|
| `updateCursorHUD()` | 53 | Update HUD values |
| `loadHudSettings()` | 12 | Load preferences |
| `saveHudSettings()` | 3 | Save preferences |
| `applyHudSettingsToUI()` | 26 | Apply settings |
| `bindHudSettingsHandlers()` | 33 | Event binding |
| `computeDistanceToNearestBorderMetersGeo()` | 50 | Border distance |
| `computeDistanceToDataEdgeMeters()` | 34 | Edge distance |

**Extraction potential:** HIGH - Could be `hud-manager.js`

---

### 🎥 GROUP 8: CAMERA CONTROLS (~200 lines)
**Camera positioning and movement**

| Function | Lines | Purpose |
|----------|-------|---------|
| `resetCamera()` | 22 | Reset view |
| `setView()` | 50 | Preset views |
| `onKeyDown()` | 37 | Keyboard input |
| `onKeyUp()` | 17 | Key release |
| `handleKeyboardMovement()` | 64 | WASD movement |
| `isCameraMoving()` | 15 | Movement check |

**Extraction potential:** LOW - Integrates with camera schemes

---

### 📏 GROUP 9: VERTICAL EXAGGERATION (~80 lines)
**Height scaling controls**

| Function | Lines | Purpose |
|----------|-------|---------|
| `setVertExag()` | 16 | Set value |
| `setTrueScale()` | 19 | Set 1:1 |
| `setVertExagMultiplier()` | 17 | Set by multiplier |
| `updateVertExagButtons()` | 36 | Button states |
| `multiplierToInternal()` | 12 | Convert value |
| `internalToMultiplier()` | 7 | Convert back |

**Extraction potential:** MEDIUM - Needs terrain reference

---

### ⚡ GROUP 10: PERFORMANCE & GPU (~100 lines)
**Performance monitoring and optimization**

| Function | Lines | Purpose |
|----------|-------|---------|
| `testFrustumCulling()` | 35 | Test culling |
| `measureFPS()` | 24 | FPS measurement |
| `updateFPS()` | 18 | Update counter |
| `autoReduceResolution()` | 30 | Auto reduce |

**Extraction potential:** MEDIUM - Performance tools

---

### 🏗️ GROUP 11: INITIALIZATION & SETUP (~1000 lines)
**Application bootstrap and scene creation**

| Function | Lines | Purpose |
|----------|-------|---------|
| `init()` | 180 | Main initialization |
| `applyParamsFromURL()` | 79 | Parse URL params |
| `setupScene()` | 176 | Three.js setup |
| `setupControls()` | 399 | UI initialization |
| `setupEventListeners()` | 105 | Event binding |
| `animate()` | 16 | Render loop |
| `onWindowResize()` | 16 | Resize handler |
| `switchCameraScheme()` | 20 | Switch controls |
| `syncUIControls()` | 58 | Sync UI state |

**Extraction potential:** LOW - Core orchestration

---

### 🔧 GROUP 12: UTILITIES (~150 lines)
**Helper functions and misc**

| Function | Lines | Purpose |
|----------|-------|---------|
| `debounce()` | 9 | Debounce helper |
| `logResourceTiming()` | 57 | Resource timing |
| `updateStats()` | 38 | Stats display |
| `updateURLParameter()` | 7 | URL updates |
| `copyShareLink()` | 23 | Share link |
| `exportImage()` | 12 | Screenshot |
| `toggleControlsHelp()` | 13 | Help toggle |
| `createPivotMarker()` | 34 | Debug marker |

**Extraction potential:** MEDIUM - Mixed bag

---

### 🚦 GROUP 13: UI LOADING STATES (~30 lines)
**Loading screens and progress**

| Function | Lines | Purpose |
|----------|-------|---------|
| `showLoading()` | 17 | Show loading |
| `hideLoading()` | 5 | Hide loading |
| `updateLoadingProgress()` | 10 | Progress bar |

**Extraction potential:** HIGH - Simple UI module

---

## 🎯 RECOMMENDED EXTRACTION PRIORITIES

### Phase 1: Easy Wins (Low Risk, High Value)
1. **Resolution Controls** (~400 lines) → `resolution-controls.js`
   - Self-contained UI logic
   - Clear interface boundaries
   - High line count reduction

2. **Edge Markers** (~100 lines) → `edge-markers.js`
   - Completely isolated
   - Visual feature only
   - Zero dependencies

3. **HUD Manager** (~200 lines) → `hud-manager.js`
   - Well-defined purpose
   - Clear state management
   - Already uses settings object

4. **Borders & Contours** (~250 lines) → `borders-contours.js`
   - Rendering logic only
   - No state dependencies
   - Clear input/output

5. **Loading States** (~30 lines) → `ui-loading.js`
   - Trivial extraction
   - Pure UI updates

### Phase 2: Medium Effort (Moderate coupling)
6. **Terrain Rendering** (~600 lines) → `terrain-renderer.js`
   - Core feature but modular
   - Needs global state access
   - Performance-critical (be careful!)

7. **Lighting & Shading** (~120 lines) → `lighting.js`
   - Visual tool
   - Some terrain coupling
   - Optional feature

8. **Vertical Exaggeration** (~80 lines) → `vertical-exaggeration.js`
   - Needs terrain reference
   - State management required

### Phase 3: Complex (High coupling, save for later)
9. **Data Loading** (~500 lines) - Complex UI interactions
10. **Camera Controls** (~200 lines) - Integrates with schemes
11. **Initialization** (~1000 lines) - Core orchestration

---

## 💡 KEY INSIGHTS

### Natural Clusters Detected:
1. **Visual Features** (Markers, Borders, Contours, Lighting) - ~500 lines
2. **UI Controls** (Resolution, HUD, Exaggeration) - ~700 lines  
3. **Data Pipeline** (Loading, Processing, Rendering) - ~1100 lines
4. **Core Infrastructure** (Init, Scene, Events) - ~1000 lines

### Anti-patterns Found:
- `setupControls()` is 399 lines (WAY too large!)
- Some functions are wrappers (3 lines) while originals are huge
- Mix of UI logic and rendering logic in same functions
- Initialization scattered across multiple functions

### Best Extraction Strategy:
**Start with self-contained features** (Phase 1) that:
- Have clear boundaries
- Don't touch core state
- Are optional/visual features
- Reduce line count significantly

This gives you wins without risk, then tackle harder ones later.

