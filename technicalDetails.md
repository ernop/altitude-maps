# Technical Details

## Data Pipeline

### Pipeline Stages
1. Validate region definition
2. **Determine required resolution** (CRITICAL FLOW):
   - Calculate base dimension: `base_dimension = sqrt(target_total_pixels)`
   - Calculate visible pixel size: `visible_m_per_pixel = geographic_span_meters / base_dimension`
   - Apply Nyquist rule: `source_resolution ≤ visible_pixel_size / 2.0`
   - Select coarsest available resolution that meets requirement (prevents over-downloading)
   - Map resolution to dataset code (USA_3DEP, SRTMGL1, etc.)
3. Download raw elevation data (region-specific, no tile reuse)
4. Merge tiles for region bounds (if multiple tiles needed)
5. Clip to administrative boundaries (if configured)
6. Reproject to fix latitude distortion (EPSG:4326 → EPSG:3857)
7. Downsample to target resolution
8. Export to JSON for viewer

### Resolution Selection (CRITICAL - SINGLE SOURCE OF TRUTH)
**Flow**: `target_total_pixels` + `geographic_bounds` → visible pixel size → resolution → dataset

**Key Principle**: Resolution is determined FIRST based on final output needs, THEN dataset is selected. This ensures we don't over-download (e.g., if final output needs 200m/pixel, we select 90m source, not 10m).

**Process**:
1. Calculate base dimension: `base_dimension = sqrt(target_total_pixels)`
2. Calculate visible pixel size from geographic bounds and base_dimension
3. Apply Nyquist sampling rule (2.0x oversampling minimum)
4. Select coarsest available resolution that meets requirement
5. Map to dataset code based on resolution and region type

**Available Resolutions**:
- US regions: 10m (USGS 3DEP), 30m, 90m, 250m, 500m, 1000m (GMTED2010)
- International: 30m, 90m, 250m, 500m, 1000m (GMTED2010)

**Goal**: Always deliver the right amount of accurate pixels for regions of all sizes (large, medium, small, tiny). The system automatically selects the coarsest resolution that meets Nyquist requirements.

**Example**:
- 20-mile square, target_total_pixels=4194304 (2048²) → ~15.6m/pixel → requires 10m source
- 200-mile square, target_total_pixels=4194304 (2048²) → ~156m/pixel → requires 90m source (not 10m!)

### Tile System
- Downloads use 1×1 degree tile structure for organization
- Format: `{NS}{lat}_{EW}{lon}_{resolution}.tif`
- Storage: `data/raw/{source}/tiles/`
- **No tile reuse**: Each region downloads fresh data at required resolution
- Tile directories remain for reference but are not checked for reuse

## Data Sources

### USA
- **USGS 3DEP**: 10m resolution, full USA coverage
- **OpenTopography SRTM**: 30m/90m fallback

### Global
- **OpenTopography SRTM**: 30m/90m, 60°N to 56°S
- **Copernicus DEM**: 30m/90m, global coverage
- **ALOS AW3D30**: 30m, global coverage

### National Sources
- **Japan**: GSI DEM (5-10m)
- **Switzerland**: SwissTopo (0.5-2m)
- **Australia**: Geoscience Australia (5m)
- **Germany**: BKG DGM (1-25m)

## File Formats

### Raw Data
- Format: GeoTIFF (EPSG:4326)
- Storage: `data/raw/{source}/tiles/`
- Naming: `{NS}{lat}_{EW}{lon}_{resolution}.tif`

### Processed Data
- Format: GeoTIFF (EPSG:3857 after reprojection)
- Storage: `data/processed/{source}/`
- Naming: `{base}_processed_{pixels}px_v2.tif`

### Viewer Export
- Format: JSON (compressed as `.json.gz`)
- Storage: `generated/regions/`
- Naming: `{region_id}_{source}_{pixels}px_v2.json.gz`

## Region Types

### USA_STATE
- Enum: `RegionType.USA_STATE`
- Resolution: Dynamic (10m/30m/90m)
- Clipping: Always clips to state boundaries
- Sources: USGS 3DEP, OpenTopography

### COUNTRY
- Enum: `RegionType.COUNTRY`
- Resolution: Dynamic (30m/90m)
- Clipping: Usually clips to country boundaries
- Sources: OpenTopography, Copernicus

### AREA
- Enum: `RegionType.AREA`
- Resolution: Dynamic (30m/90m)
- Clipping: Usually bounding box only
- Sources: OpenTopography, Copernicus

## Viewer Architecture

### Rendering
- Three.js WebGL renderer
- Instanced mesh rendering for bars
- GPU uniforms for exaggeration and tile gap
- Scene hierarchy: `scene → terrainGroup → terrainMesh → bars`

### Camera System
- Ground plane camera (default)
- Fixed ground plane at y=0
- Focus point anchored on plane
- `camera.lookAt()` called only in update loop

### Performance
- Default bucket size: ~3,900 buckets
- GPU-first updates for continuous controls
- Debounced heavy operations (50-120ms)
- Conditional system checks before computing

## Coordinate Systems

### Data Processing
- Input: EPSG:4326 (WGS84 lat/lon)
- Processing: EPSG:3857 (Web Mercator)
- Output: EPSG:4326 (for viewer)

### Viewer
- Treats data as uniform 2D grid
- No geographic transformations in viewer
- Aspect ratio preserved from export

## Border System

### Sources
- Natural Earth administrative boundaries
- Resolutions: 10m (production), 50m, 110m
- 177 countries (admin_0) + US states (admin_1)

### Usage
- Clipping: `crop=True` in `rasterio_mask()`
- Export: Separate border JSON files
- Viewer: Toggleable overlay

## Cache System

### Locations
- `data/.cache/` - Masked/bordered raster data
- `generated/` - Exported JSON for viewer
- `data/raw/` - Raw tile downloads (reusable)

### Invalidation
- Format version changes trigger cache clear
- Manual: `python clear_caches.py`
- Automatic: Version mismatch detection

## Versioning

### Format Versions
- Raw: `raw_v1` (immutable)
- Clipped: `clipped_v1`
- Processed: `processed_v2`
- Export: `export_v2`

### Version Checking
- Metadata files contain version info
- Load functions check compatibility
- Mismatch raises clear error with fix instructions

