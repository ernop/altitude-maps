# Viewer Architecture Refactoring Proposal

## Current State Analysis

### What's Working Well
- **Camera systems**: Cleanly separated into `ground-plane-camera.js`, `ground-plane-google-earth.js`, `camera-schemes.js`
- **Color schemes**: Data separated into `color-schemes.js`, UI component in `color-legend.js`
- **Utility modules**: `bucketing.js`, `geometry-utils.js`, `format-utils.js`, `activity-log.js`, `ui-loading.js`
- **Resolution controls**: Separated into `resolution-controls.js`

### What Needs Refactoring

**`viewer-advanced.js` (3500+ lines) currently mixes:**
1. **Core initialization** (init, setupScene) - KEEP
2. **Data loading** (region loading, manifest) - KEEP
3. **UI controls setup** (`setupControls()` - 280+ lines) - EXTRACT
4. **HUD system** (dragging, position, settings, updates) - EXTRACT
5. **Compass rose click handling** (in `setupEventListeners()`) - EXTRACT
6. **Map shading** (`getColorForElevation()`, `updateColors()`, materials, lighting) - EXTRACT
7. **Terrain rendering** (`createTerrain()`, `createBarsTerrain()`, etc.) - EXTRACT
8. **Event handling** (`setupEventListeners()` - mixes many concerns) - REFACTOR

## Proposed Architecture

### Core Principle
**Separation by Domain**: Each module owns a complete feature domain (like camera systems do).

### Module Structure

```
js/
├── viewer-advanced.js          # Core orchestrator (init, data loading, animation loop)
├── camera-schemes.js           # Camera scheme base class
├── ground-plane-camera.js      # Default camera system
├── ground-plane-google-earth.js # Google Earth camera
│
├── ui-controls-manager.js     # NEW: All UI control setup and event binding
├── hud-system.js              # NEW: Complete HUD overlay system
├── compass-rose.js            # NEW: Edge markers + click handling (extends edge-markers.js)
├── map-shading.js             # NEW: Visual appearance (colors, materials, lighting)
├── terrain-renderer.js        # NEW: Terrain creation (bars/surface/points)
│
├── color-schemes.js          # Color palette data (keep)
├── color-legend.js            # Color legend UI component (keep)
├── edge-markers.js            # Edge marker creation (keep, extend)
├── resolution-controls.js     # Resolution controls (keep)
├── state-connectivity.js       # Region adjacency (keep)
├── bucketing.js               # Data aggregation (keep)
├── geometry-utils.js           # Spatial calculations (keep)
├── format-utils.js            # Data formatting (keep)
├── activity-log.js            # Activity log UI (keep)
└── ui-loading.js              # Loading screen (keep)
```

## Detailed Module Responsibilities

### 1. `ui-controls-manager.js` - UI Controls Management

**Purpose**: Centralized setup and coordination of all UI controls

**Responsibilities**:
- Region selector dropdown (custom search/filter)
- Render mode selector
- Vertical exaggeration controls (slider + input + buttons)
- Color scheme selector + quick jump buttons
- Grid toggle, auto-rotate toggle
- Mobile UI toggle
- URL parameter synchronization
- Control state synchronization (sync input ↔ slider)

**Interface**:
```javascript
window.UIControlsManager = {
    init: function() { /* Setup all controls */ },
    syncFromParams: function(params) { /* Sync UI from params object */ },
    syncToParams: function() { /* Update params from UI */ },
    onControlChange: function(controlName, callback) { /* Register change handlers */ }
};
```

**Dependencies**:
- `params` object (shared state)
- `loadRegion()` function (from viewer-advanced)
- `recreateTerrain()` function (from terrain-renderer)
- `updateColors()` function (from map-shading)

**Benefits**:
- Single place to add new controls
- Consistent event handling patterns
- Easy to test controls in isolation
- Clear extension point for new control types

---

### 2. `hud-system.js` - HUD Overlay System

**Purpose**: Complete HUD overlay management

**Responsibilities**:
- HUD dragging (position management)
- HUD position persistence (localStorage)
- HUD show/hide toggle
- HUD settings panel (units, visible fields)
- HUD content updates (elevation, slope, aspect from mouse position)
- HUD minimize/restore

**Interface**:
```javascript
window.HUDSystem = {
    init: function() { /* Setup HUD dragging, settings */ },
    update: function(worldX, worldZ, elevation, slope, aspect) { /* Update HUD content */ },
    show: function() { /* Show HUD */ },
    hide: function() { /* Hide HUD */ },
    isVisible: function() { /* Check visibility */ },
    loadSettings: function() { /* Load from localStorage */ },
    saveSettings: function() { /* Save to localStorage */ }
};
```

**Dependencies**:
- `raycastToWorld()` function (from viewer-advanced or geometry-utils)
- `getSlopeDegrees()`, `getAspectDegrees()` functions (from viewer-advanced)
- `hudSettings` object (shared state)

**Benefits**:
- Self-contained HUD logic
- Easy to add new HUD fields
- Clear separation from main viewer logic

---

### 3. `compass-rose.js` - Compass Rose + Click Handling

**Purpose**: Edge markers with click handling for region navigation

**Responsibilities**:
- Extend `edge-markers.js` functionality
- Click detection on edge markers
- Raycasting to detect marker clicks
- Button boundary detection (UV coordinate mapping)
- Hover state management
- Region loading on click

**Interface**:
```javascript
window.CompassRose = {
    init: function(renderer, camera, scene) { /* Setup click listeners */ },
    update: function() { /* Update marker visibility/positions */ },
    handleClick: function(event) { /* Process click events */ },
    handleHover: function(event) { /* Process hover events */ }
};
```

**Dependencies**:
- `edge-markers.js` (marker creation)
- `loadRegion()` function (from viewer-advanced)
- `edgeMarkers` array (shared state)
- `regionAdjacency` data (shared state)

**Benefits**:
- Complete compass rose feature in one module
- Easy to experiment with different click/hover behaviors
- Clear separation from main viewer event handling

---

### 4. `map-shading.js` - Map Visual Appearance

**Purpose**: Apply visual appearance to terrain (colors, shading, materials)

**Responsibilities**:
- `getColorForElevation(elevation)` - Color lookup for single elevation
- `updateColors()` - Update all terrain colors
- Handle different render modes (bars, points, surface)
- Support derived modes (slope, aspect)
- Auto-stretch color calculation
- Gamma correction
- Material properties (flat lighting, shader uniforms)
- Lighting coordination (ambient, directional lights)

**Interface**:
```javascript
window.MapShading = {
    getColor: function(elevation, row, col) { /* Get color for elevation */ },
    updateAll: function() { /* Update all terrain colors */ },
    setScheme: function(schemeName) { /* Change color scheme */ },
    setGamma: function(gamma) { /* Set gamma correction */ },
    updateMaterials: function() { /* Update material properties */ },
    setFlatLighting: function(enabled) { /* Toggle flat lighting */ }
};
```

**Dependencies**:
- `COLOR_SCHEMES` (from color-schemes.js)
- `params.colorScheme`, `params.colorGamma`, `params.flatLighting` (shared state)
- `processedData`, `derivedSlopeDeg`, `derivedAspectDeg` (shared state)
- `terrainMesh`, `barsInstancedMesh` (shared state)
- Lighting system (ambient/directional lights)

**Relationship to Terrain Renderer**:
- **Terrain Renderer**: Creates geometry (mesh structure, vertices, instanced meshes)
- **Map Shading**: Applies visual appearance (colors, materials, lighting)
- Clear separation: Geometry vs. Appearance
- Terrain Renderer calls Map Shading during creation to apply initial colors

**Benefits**:
- Single place for all visual appearance logic
- Easy to add new color schemes or shading modes
- Clear separation from geometry creation
- Testable color/shading calculations

---

### 5. `terrain-renderer.js` - Terrain Rendering

**Purpose**: Create and manage terrain geometry

**Responsibilities**:
- `createTerrain()` - Main terrain creation dispatcher
- `createBarsTerrain()` - Instanced bars rendering
- `createSurfaceTerrain()` - Surface mesh rendering
- `createPointCloudTerrain()` - Point cloud rendering
- `recreateTerrain()` - Rebuild terrain (preserve position/rotation)
- `updateTerrainHeight()` - Update vertical exaggeration
- Terrain position/rotation preservation

**Interface**:
```javascript
window.TerrainRenderer = {
    create: function(data, params) { /* Create terrain */ },
    recreate: function() { /* Rebuild terrain */ },
    updateHeight: function() { /* Update vertical exaggeration */ },
    getMesh: function() { /* Get current terrain mesh */ },
    getGroup: function() { /* Get terrain group */ }
};
```

**Dependencies**:
- `processedData` (shared state)
- `params.renderMode`, `params.verticalExaggeration`, `params.bucketSize` (shared state)
- `scene`, `terrainGroup` (shared state)
- `getColorForElevation()` function (from map-shading)

**Benefits**:
- Single place for terrain creation logic
- Easy to add new render modes
- Clear separation from color/control logic
- Testable rendering code

---

## Communication Patterns & Shared State

### Why This Matters for LLM-Managed Code

**Key Principles for LLM-Friendly Architecture:**
1. **Explicitness over Implicitness** - Clear, obvious patterns are easier for LLMs to understand and maintain
2. **Single Source of Truth** - One place to look for each piece of state
3. **Consistent Patterns** - Same pattern everywhere reduces cognitive load
4. **Minimal Abstraction** - Too much abstraction confuses LLMs (they need to see the actual code)
5. **Discoverability** - Easy to find where things are defined and used

### Shared State Options

#### Option A: Global Window Objects (Current Approach)

**Structure:**
```javascript
// In viewer-advanced.js (or state-manager.js)
window.scene, window.camera, window.renderer, window.controls
window.terrainMesh, window.terrainGroup
window.rawElevationData, window.processedData
window.derivedSlopeDeg, window.derivedAspectDeg
window.params = { bucketSize, renderMode, verticalExaggeration, colorScheme, ... }
window.currentRegionId, window.regionsManifest, window.regionAdjacency
window.hudSettings, window.edgeMarkers
```

**Pros:**
- ✅ **Simple** - No abstraction, direct access
- ✅ **Explicit** - Can see exactly what's shared by searching for `window.`
- ✅ **LLM-friendly** - Easy to understand and modify
- ✅ **No overhead** - Direct property access
- ✅ **Works everywhere** - No import/export complexity

**Cons:**
- ❌ **No validation** - Can set invalid values
- ❌ **No change tracking** - Hard to debug what changed state
- ❌ **Namespace pollution** - Many `window.` properties
- ❌ **No type safety** - JavaScript doesn't enforce types

**Best for:** LLM-managed code, simple projects, when explicitness matters more than safety

---

#### Option B: Centralized State Manager Module

**Structure:**
```javascript
// In state-manager.js
window.ViewerState = {
    // Core Three.js
    scene: null,
    camera: null,
    renderer: null,
    controls: null,
    terrainMesh: null,
    terrainGroup: null,
    
    // Data
    rawElevationData: null,
    processedData: null,
    derivedSlopeDeg: null,
    derivedAspectDeg: null,
    
    // Parameters
    params: {
        bucketSize: 4,
        renderMode: 'bars',
        verticalExaggeration: 0.04,
        colorScheme: 'high-contrast',
        // ...
    },
    
    // Region state
    currentRegionId: null,
    regionsManifest: null,
    regionAdjacency: null,
    
    // UI state
    hudSettings: null,
    edgeMarkers: [],
    
    // Validation helpers
    setParam: function(key, value) {
        // Validate before setting
        if (key === 'renderMode' && !['bars', 'points', 'surface'].includes(value)) {
            console.error('Invalid renderMode:', value);
            return false;
        }
        this.params[key] = value;
        return true;
    },
    
    // Change tracking (optional)
    onChange: function(callback) { /* Register change listeners */ }
};
```

**Pros:**
- ✅ **Single source of truth** - All state in one object
- ✅ **Validation** - Can check values before setting
- ✅ **Change tracking** - Can log what changed
- ✅ **Namespace clean** - One `window.ViewerState` instead of many properties
- ✅ **Documentation** - Clear structure shows all state

**Cons:**
- ❌ **More abstraction** - Need to understand the state manager
- ❌ **Slightly more verbose** - `window.ViewerState.params.bucketSize` vs `window.params.bucketSize`
- ❌ **LLM complexity** - More concepts to understand

**Best for:** Larger projects, when validation matters, when you want change tracking

---

#### Option C: Event Bus / Pub-Sub Pattern

**Structure:**
```javascript
// In event-bus.js
window.EventBus = {
    events: {},
    on: function(event, callback) { /* Subscribe */ },
    emit: function(event, data) { /* Publish */ }
};

// Usage:
window.EventBus.on('paramsChanged', (newParams) => {
    // React to change
});
window.EventBus.emit('paramsChanged', window.params);
```

**Pros:**
- ✅ **Decoupled** - Modules don't need to know about each other
- ✅ **Flexible** - Easy to add new listeners
- ✅ **Event-driven** - Natural for reactive updates

**Cons:**
- ❌ **Hard to trace** - Difficult to see what triggers what
- ❌ **LLM confusion** - Abstract pattern, harder to understand
- ❌ **Debugging difficulty** - Hard to find where events are emitted
- ❌ **Overkill** - Too much abstraction for this use case

**Best for:** Complex event-driven systems, not recommended for LLM-managed code

---

### Recommended Approach: Hybrid (Option A + Light State Manager)

**For LLM-Managed Code, Use:**

1. **Global window objects for core state** (Option A)
   - Simple, explicit, easy to understand
   - Direct access: `window.params.bucketSize`
   - No abstraction overhead

2. **Light state manager for parameters only** (Option B variant)
   - Centralized `window.params` object (already exists)
   - Optional validation helpers if needed
   - Keep it simple - don't over-engineer

3. **Direct function calls for module communication**
   - Explicit: `window.TerrainRenderer.updateHeight()`
   - Easy to trace: Can search for function calls
   - No magic: See exactly what's called

**Example:**
```javascript
// Simple, explicit pattern
window.params = { bucketSize: 4, renderMode: 'bars', ... };

// Modules read/write directly
window.params.bucketSize = 8;
window.TerrainRenderer.recreate();

// Optional: Add validation helper if needed
window.ViewerState = {
    setParam: function(key, value) {
        // Simple validation
        if (key === 'renderMode' && !['bars', 'points', 'surface'].includes(value)) {
            return false;
        }
        window.params[key] = value;
        return true;
    }
};
```

### Communication Pattern (Recommended)

**Modules communicate via:**

1. **Shared state objects** (window.params, window.processedData, etc.)
   - Read/write directly
   - Simple and explicit

2. **Direct function calls** (modules expose public APIs)
   - `window.TerrainRenderer.updateHeight()`
   - `window.MapShading.updateAll()`
   - `window.HUDSystem.update(x, y, z)`

3. **Event listeners** (for DOM events only)
   - Centralized in `ui-controls-manager.js`
   - Centralized in `compass-rose.js`
   - Not for inter-module communication

**Example flow:**
```javascript
// User changes vertical exaggeration slider
// In ui-controls-manager.js:
document.getElementById('vertExag').addEventListener('input', (e) => {
    // 1. Update shared state (explicit)
    window.params.verticalExaggeration = multiplierToInternal(e.target.value);
    
    // 2. Call affected modules directly (explicit)
    window.TerrainRenderer.updateHeight();
    
    // 3. Update HUD if visible (explicit check)
    if (window.HUDSystem.isVisible()) {
        window.HUDSystem.update(currentMouseX, currentMouseY);
    }
    
    // 4. Sync URL (explicit)
    window.UIControlsManager.syncToURL();
});
```

**Why This Works for LLMs:**
- ✅ **Explicit** - Can see exactly what happens
- ✅ **Traceable** - Can search for function calls
- ✅ **Simple** - No hidden magic or abstractions
- ✅ **Consistent** - Same pattern everywhere
- ✅ **Discoverable** - Easy to find where things are defined

---

## Migration Strategy

### Phase 1: Extract UI Controls (Low Risk)
1. Create `ui-controls-manager.js`
2. Move `setupControls()` function
3. Move control event handlers
4. Test: All controls work identically

### Phase 2: Extract HUD System (Low Risk)
1. Create `hud-system.js`
2. Move HUD dragging, position, settings
3. Move HUD update logic
4. Test: HUD works identically

### Phase 3: Extract Compass Rose (Medium Risk)
1. Extend `edge-markers.js` → `compass-rose.js`
2. Move click handling from `setupEventListeners()`
3. Move hover state management
4. Test: Compass rose clicks work

### Phase 4: Extract Map Shading (Medium Risk)
1. Create `map-shading.js`
2. Move `getColorForElevation()`, `updateColors()`, material/lighting logic
3. Update all call sites
4. Test: Colors and shading update correctly

### Phase 5: Extract Terrain Renderer (Higher Risk)
1. Create `terrain-renderer.js`
2. Move all terrain creation functions
3. Update all call sites
4. Test: Terrain renders correctly

### Phase 6: Cleanup (Low Risk)
1. Remove unused code from `viewer-advanced.js`
2. Update documentation
3. Consolidate event handling

---

## Benefits of This Architecture

### 1. Extensibility
- **New control types**: Add to `ui-controls-manager.js` with consistent pattern
- **New camera schemes**: Already working pattern (ground-plane-camera.js)
- **New render modes**: Add to `terrain-renderer.js`
- **New color schemes**: Add to `color-schemes.js`, works automatically

### 2. Maintainability
- **Single responsibility**: Each module has one clear purpose
- **Easy to find code**: Know where to look for each feature
- **Reduced coupling**: Modules communicate via clear interfaces
- **Testability**: Each module can be tested independently

### 3. Clarity
- **Logical organization**: Related code grouped together
- **Clear naming**: Module names describe their purpose
- **Consistent patterns**: Similar to camera system organization
- **Documentation**: Each module can document its own domain

### 4. Performance
- **Lazy loading**: Modules only load what they need
- **Efficient updates**: Clear update paths (no redundant work)
- **Debouncing**: Centralized in control manager

---

## Example: Adding a New Control Type

**Before (in viewer-advanced.js):**
- Find `setupControls()` function
- Add event listener somewhere in 280+ lines
- Hope you find the right place
- Mix with other control logic

**After (with new architecture):**
```javascript
// In ui-controls-manager.js
function setupNewControl() {
    const control = document.getElementById('newControl');
    control.addEventListener('change', (e) => {
        window.params.newParam = e.target.value;
        window.TerrainRenderer.update(); // Or appropriate module
        window.UIControlsManager.syncToURL();
    });
}

// In init():
setupNewControl(); // Clear, explicit, easy to find
```

---

## Questions to Consider

1. **Should `viewer-advanced.js` become thinner?**
   - Yes: Keep only orchestration (init, data loading, animation loop)
   - Current: ~3500 lines → Target: ~1500 lines

2. **How to handle shared state?**
   - **Recommended: Hybrid approach**
   - Global window objects for core state (simple, explicit, LLM-friendly)
   - Centralized `window.params` object (already exists, single source of truth)
   - Direct function calls for module communication (explicit, traceable)
   - See "Communication Patterns & Shared State" section above for detailed analysis

3. **Event handling consolidation?**
   - Current: Multiple `addEventListener` calls scattered
   - Proposed: Centralized in `ui-controls-manager.js` and `compass-rose.js`
   - Benefit: Single place to see all event handlers

4. **Module loading order?**
   - Current: All scripts loaded in HTML
   - Proposed: Keep same (simple, works)
   - Future: Could use ES modules if needed

---

## Next Steps

1. **Review this proposal** - Does this architecture make sense?
2. **Start with Phase 1** - Extract UI controls (lowest risk, highest impact)
3. **Iterate** - Extract one module at a time, test thoroughly
4. **Document** - Update module headers as we go

