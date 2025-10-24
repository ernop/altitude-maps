# Altitude Maps - Product Requirements & Description

## Overview

An interactive 3D terrain visualization system for exploring elevation data across the globe. Users can view any region's topography as a 3D bar chart or smooth surface with real-world geographic accuracy and scale.

**Primary Use Case:** Explore and understand elevation patterns, mountain ranges, valleys, and terrain features through intuitive 3D visualization.

**Target Users:** Geography enthusiasts, researchers, educators, hikers, and anyone interested in understanding terrain topology.

---

## Core Product Features

### 1. Interactive 3D Viewer

**Primary Interface:** Browser-based 3D viewer served at `http://localhost:8001`

**Navigation Controls (Google Earth-Inspired):**
- **Left-Click + Drag:** Pan/strafe the view
- **Right-Click + Drag:** Rotate/orbit around target point
- **Middle Mouse + Drag:** Rotate/orbit (alternative)
- **Scroll Wheel:** Zoom in/out (linear forward/backward movement)
- **Shift + Scroll:** Precise zoom at 1/20× speed

**Keyboard Controls:**
- **W/S:** Move up/down (vertical movement)
- **A/D:** Rotate left/right around center
- **Q/E:** Move vertically (up/down in world space)
- **Arrow Keys:** Pan view in cardinal directions
- **R:** Reset camera to default position
- **F:** Focus on center
- **Space:** Toggle auto-rotate

**Design Philosophy:** Simple, intuitive controls. OrbitControls handle all mouse interactions naturally - no complex custom event handlers fighting with the library.

---

### 2. Visualization Modes

#### Rendering Options
1. **3D Rectangular Prisms (Bars)** - Primary visualization mode
   - Each data point rendered as a vertical bar
   - Height represents elevation
   - Clean, easy-to-understand representation
   
2. **Smooth Surface** - Continuous terrain mesh
   - Interpolated surface between data points
   - Natural, realistic appearance
   
3. **Wireframe** - Technical view
   - Shows mesh structure
   - Useful for understanding data density
   
4. **Point Cloud** - Minimal visualization
   - Each data point as a colored dot
   - Fastest rendering for large datasets

#### Visual Style Controls
- **Color Schemes:**
  - Terrain (Natural) - Greens to browns
  - Elevation (Blue-Red) - Cold to hot gradient
  - Grayscale - Monochrome intensity
  - Rainbow - Full spectrum
  - Earth Tones - Natural palette
  - Heatmap - Intensity-based

- **Visual Toggles:**
  - Wireframe Overlay (show mesh structure over solid)
  - Ground Grid (reference grid at sea level)
  - Country Borders (overlay political boundaries)
  - Flat Shading (toggle between flat/smooth shading)
  - Auto-Rotate (continuous rotation for presentation)

---

### 3. Data Management

#### Bucketing/Aggregation System

**Purpose:** Reduce data complexity for performance while maintaining visual fidelity

**Bucket Size:** 1× to 500× (pixel aggregation)
- 1× = Full resolution (1 bar per pixel)
- 8× = Default (64 pixels aggregated into 1 bar)
- Higher = More aggressive reduction

**Aggregation Methods:**
- **Max:** Use highest elevation in bucket (shows peaks)
- **Mean:** Average elevation (smooth representation)
- **Min:** Lowest elevation (shows valleys)
- **Median:** Middle value (robust to outliers)

**Performance Targets:**
- < 15,000 bars: Excellent performance
- 15,000-25,000 bars: Good performance
- > 25,000 bars: Warning shown, suggest higher bucket size

#### Tile Gap Control
- 0% = Tiles touching (continuous appearance)
- 1-50% = Increasing gaps between tiles
- Purpose: Visual separation, reduce depth buffer artifacts at extreme viewing angles

---

### 4. Scale & Accuracy

#### Vertical Exaggeration
- **Range:** 0.00001× to 0.3×
- **Default:** 0.001× (appropriate for large regions)
- **True Earth Scale:** 1.0× (where both horizontal and vertical use same meters-per-unit ratio)
- **Purpose:** Make elevation differences visible when viewing large geographic areas

**Scale System:**
- X/Z axes: Meters (horizontal distance based on lat/lon bounds)
- Y axis: Meters (elevation scaled by vertical exaggeration)
- Both axes derived from real-world coordinates

**Example:** For a 500km × 600km region:
- Without exaggeration: A 3km mountain is barely visible (3km height vs 500km width)
- With 0.001× exaggeration: Terrain features become clearly visible
- Grid remains undistorted (square tiles, no aspect ratio stretching)

---

### 5. Geographic Features

#### Border Support
- **177 countries available** from Natural Earth dataset
- **Resolutions:** 10m, 50m, 110m (meters per pixel at equator)
- **Functions:**
  - Draw borders: Overlay country boundaries on terrain
  - Mask data: Clip elevation data to country boundaries
  - Cache: Automatic caching of borders and masked data

#### Region Selection
- **US States:** All 50 states available (USGS 3DEP high-resolution data)
- **Countries:** Switzerland, Japan (national high-resolution sources)
- **Global:** Any bounding box via SRTM or Copernicus DEM

**Dropdown Interface:** Typeahead search for quick region selection

---

### 6. Camera & Rendering

#### Camera Presets
- **Overhead:** Top-down view (90° from vertical)
- **Isometric:** 45° angle perspective
- **Cardinal Directions:** North, South, East, West views
- **Reset Camera:** Return to optimal default view for current data

#### Critical Technical Constraints

**Near/Far Plane Ratio:**
```
Near plane: 1 meter
Far plane: 100,000 meters (100km)
Ratio: 100,000:1
```

**⚠️ DO NOT MODIFY** without understanding depth buffer implications:
- Ratios > 1,000,000:1 cause depth buffer precision loss
- Symptoms: Distant geometry bleeds through nearby geometry
- Artifacts worsen at oblique viewing angles
- Solution: Keep ratio reasonable, implement logarithmic depth buffer if larger distances needed

**Performance Monitoring:**
- Real-time FPS counter
- Bar count display
- Resolution statistics
- Warning messages for performance-impacting configurations

---

### 7. Data Sources Priority

#### USA (Always First Choice)
**Source:** USGS 3D Elevation Program (3DEP)
- **Resolution:** 1-10m (far superior to global sources)
- **Coverage:** All 50 states
- **Workflow:** Download bounding box → Clip to boundaries → Cache
- **URL:** https://elevation.nationalmap.gov/

#### Other Countries (Priority Order)
1. **National agency data** (if available)
   - Examples: Australia (Geoscience), Japan (GSI), Germany (BKG), UK (Ordnance Survey), Switzerland (SwissTopo)
   - Always check for country-specific high-resolution sources first
   
2. **Global fallback sources:**
   - OpenTopography SRTM (30m, 60°N to 56°S)
   - Copernicus DEM (30m/90m, global, newest 2021)
   - ASTER GDEM (30m, 83°N to 83°S)
   - ALOS World 3D (30m free, 5m paid)

---

### 8. Data Format & Versioning

#### Export Format (JSON)
```json
{
  "version": 2,
  "exported": "ISO 8601 timestamp",
  "region": "Region name",
  "bounds": {
    "north": lat, "south": lat,
    "east": lon, "west": lon
  },
  "elevation": [[row arrays]], // 2D array: [row][col]
  "width": cols, "height": rows,
  "nodata": null_value
}
```

**Critical:** 
- Version number MUST be incremented when format changes
- Viewer validates version on load
- Fail if version mismatch (prevents mixing incompatible formats)

#### Cache Invalidation
When changing data processing or export format:
1. Update format version number
2. Add version validation on load
3. Document changes in code comments
4. Re-export ALL cached/generated data
5. Test with multiple regions

**Cache Locations:**
- `data/.cache/` - Masked/bordered raster data
- `generated/` - Exported JSON for web viewer
- `generated/regions/` - Per-region exported data

---

### 9. User Interface Components

#### Left Sidebar (Controls Panel)
- **Region Selection:** Dropdown with typeahead search
- **Render Mode:** Dropdown (bars/surface/wireframe/points)
- **Vertical Exaggeration:** Slider with preset buttons
- **Color Scheme:** Dropdown with 6 options
- **Visual Toggles:** Checkboxes for wireframe overlay, grid, borders, flat shading, auto-rotate
- **Camera Presets:** Button grid (6 preset views)
- **Reset/Screenshot:** Utility buttons

#### Bottom Left (Status Display)
- **Region Info:** Current region name and source
- **Statistics:** Bar count, data extent, resolution
- **FPS Counter:** Real-time performance monitoring
- **Orientation Compass:** 3D compass showing N/E/S/W

#### Top Center (Status Messages)
- Loading indicators
- Error messages
- Processing status

---

### 10. Quality Standards

#### Code Standards
- Type hints for all function parameters and returns
- Single-purpose functions
- Meaningful variable names (not abbreviations)
- Document complex transformations with inline comments
- No self-praise in documentation ("stunning", "incredible", etc.)

#### Data Standards
- Validate data ranges and handle missing values
- GeoTIFF uses natural orientation (North up, East right)
- No transformations needed for standard GeoTIFF data
- Always cache processed data to avoid re-downloading

#### Testing Standards
- Test with small data samples first
- Verify coordinate systems and projections
- Check data units and conversions
- Validate visualizations manually

---

### 11. Performance Optimization

#### Instanced Rendering
- Use `THREE.InstancedMesh` for bars (1 draw call for all bars)
- Use `THREE.MeshLambertMaterial` (faster than StandardMaterial)
- Minimize scene objects (use instancing, not individual meshes)

#### Data Reduction
- Automatic bucketing for large datasets
- User-adjustable bucket size
- Warning system for performance-impacting configurations
- "Surface" mode recommended for very large datasets

#### Rendering Settings
- Antialiasing: Enabled (prevents edge artifacts)
- Depth testing: Enabled
- Face culling: DoubleSide for bars (prevents perspective artifacts)
- Flat shading: User-toggleable (affects performance and appearance)

---

### 12. Common Workflows

#### View a New Region
1. Select region from dropdown
2. Wait for data to load (cached after first load)
3. Adjust vertical exaggeration for visibility
4. Adjust bucket size if performance is poor
5. Use right-click + drag to rotate and explore

#### Export Screenshot
1. Position camera to desired view
2. Adjust visual settings (colors, wireframe, etc.)
3. Click "📸 Save Screenshot" button
4. Image downloads automatically

#### Compare Regions
1. Load first region
2. Note elevation patterns
3. Select different region from dropdown
4. Use same camera presets for consistency
5. Compare visual characteristics

---

### 13. Known Limitations

#### Technical Limitations
- Maximum practical bar count: ~25,000 for smooth performance
- Camera near/far ratio constrained to 100,000:1 for depth precision
- Browser-based (limited by WebGL capabilities)
- Single region loaded at a time (no multi-region comparison)

#### Data Limitations
- Global SRTM: 30m resolution maximum
- National sources: Variable coverage (not all countries)
- Ocean/water: Typically shown as 0 elevation
- Missing data: Filled with nodata value or interpolated

---

### 14. Future Enhancements (Not Yet Implemented)

#### Potential Features
- Multi-region comparison (side-by-side views)
- Time-series visualization (glacial retreat, etc.)
- Climate data overlay (temperature, precipitation)
- Logarithmic depth buffer (for extreme viewing distances)
- GPU-based bucketing (faster data reduction)
- Path/route visualization (hiking trails, etc.)
- Measurement tools (distance, elevation profile)
- VR/AR support

#### Data Enhancements
- Real-time data fetching (no pre-processing)
- Global coverage without pre-download
- Higher resolution sources integration
- Bathymetry (ocean depth) data

---

## Critical Design Decisions

### Why Bars Instead of Surface as Default?
- **Clarity:** Each data point is distinct and visible
- **Accuracy:** No interpolation artifacts
- **Understanding:** Easy to see data density and resolution
- **Performance:** Instanced rendering is extremely efficient

### Why Google Earth-Style Controls?
- **Familiarity:** Many users already know these controls
- **Simplicity:** Works out-of-box with OrbitControls
- **No Custom Code:** Avoid complex event handlers fighting with library
- **Predictable:** Standard orbital camera behavior

### Why Bucketing System?
- **Scalability:** Handle full-resolution data (millions of points)
- **User Control:** Let user choose performance vs. quality tradeoff
- **Transparency:** Show exactly how many bars and what reduction
- **Flexibility:** Multiple aggregation methods for different use cases

### Why Not WebGPU/Modern Graphics?
- **Compatibility:** WebGL works everywhere
- **Stability:** Mature, well-tested libraries (Three.js)
- **Sufficient:** Current approach handles all use cases
- **Simplicity:** Avoid cutting-edge complexity

---

## Success Metrics

### Performance
- Load time < 2 seconds for cached regions
- Maintain 60 FPS at < 15,000 bars
- Maintain 30 FPS at < 25,000 bars

### Usability
- Region change < 1 second (cached)
- Intuitive controls (no tutorial needed)
- Clear visual feedback for all actions
- No unexpected camera behavior

### Quality
- Geographically accurate (correct scale and projection)
- Visually clear (elevation features distinguishable)
- Color schemes accessible (consider colorblind users)
- No rendering artifacts under normal viewing angles

---

## Maintenance Notes

### Cache Management
- Clear caches when format changes: `python clear_caches.py`
- Caches stored in `data/.cache/` and `generated/`
- Re-export required after format version bump

### Adding New Regions
1. Add to region data in export script
2. Download/process data: `python download_regions.py`
3. Export for viewer: `python export_for_web_viewer.py`
4. Add to region dropdown in HTML

### Updating Dependencies
- Three.js: Test camera controls after update
- Select2: Test region dropdown after update
- Python libs: Test data processing pipeline

---

## Documentation Index

For detailed information, see:
- `README.md` - Setup and quick start
- `TECH.md` - Technical architecture
- `.cursorrules` - Development guidelines
- `learnings/BORDERS_GUIDE.md` - Border system details
- `learnings/QUICKSTART.md` - Quick reference
- `DATA_STATUS.md` - Current data inventory

---

**Document Version:** 1.0  
**Last Updated:** October 24, 2025  
**Status:** Production - Active Development

