# State-Level Borders - Implementation Plan

Problem: US states download as rectangular bounding boxes, not actual state shapes.
Solution: Add Natural Earth admin_1 (states/provinces) support to border system.

## Data Source

Natural Earth admin_1 states/provinces
URL: https://naciscdn.org/naturalearth/{resolution}/cultural/ne_{resolution}_admin_1_states_provinces.zip
Resolutions: 10m, 50m, 110m (same as countries)
Coverage: ~1000 subdivisions worldwide including 50 US states + DC + territories
Will cache to: data/.cache/borders/ne_{resolution}_admin_1.pkl

Data structure (GeoDataFrame columns):
- name: State name (Tennessee, California, etc)
- admin: Parent country (United States of America)
- type: Subdivision type (State, Province, Territory)
- geometry: Shapely Polygon/MultiPolygon
- adm1_code: Unique identifier (USA-3640)

Download strategy: Dynamic on first use, cached locally. Same pattern as countries.

## Code Changes Required

### 1. BorderManager Extension (src/borders.py)

Add methods:
- load_state_borders(resolution) - Download/cache admin_1 data
- get_state(country, state, resolution) - Query specific state
- list_states_in_country(country, resolution) - List all states in country
- mask_raster_to_state(raster, country, state, resolution) - Clip to state boundary

Query logic: states[(states['admin'] == country) & (states['name'] == state)]

State name mapping needed for US states:
{"tennessee": "Tennessee", "california": "California", "new_york": "New York", ...}

### 2. Pipeline Updates (src/pipeline.py)

Modify clip_to_boundary() to handle boundary_type parameter:
- If boundary_type == "country": use get_country_geometry()
- If boundary_type == "state": parse "Country/State" format, use get_state()

Parse format: "United States of America/Tennessee"
Extract state geometry using BorderManager.get_state()
Apply same rasterio.mask logic as countries

### 3. Downloader Updates (downloaders/usa_3dep.py)

Change line 394: skip_clip=False (enable clipping)
Change line 384: Use state boundary instead of country
Add boundary_type="state" parameter to pipeline call
Format: boundary_name = f"United States of America/{US_STATES[region_id]['name']}"

### 4. Border Export (export_borders_for_viewer.py)

Add states parameter: List of (country, state) tuples
Extract state boundary coordinates same as countries
Output format adds states section to JSON:
{
  "countries": [...],
  "states": [{
    "country": "United States of America",
    "name": "Tennessee",
    "segments": [{"lon": [...], "lat": [...]}]
  }]
}

### 5. Viewer Updates (interactive_viewer_advanced.html)

Modify recreateBorders() function (line 2258):
- After rendering countries, check if borderData.states exists
- Iterate through states array
- Render state borders as cyan lines (distinguish from yellow country borders)
- Use same coordinate mapping logic as countries
- Fixed height at 100m above ground

### 6. CLI Tools (border_utils.py)

Add commands:
- --list-states COUNTRY: List all states in country
- --state-info COUNTRY STATE: Show state information
Update argparse to handle new commands

## Technical Pipeline

One command: python downloaders/usa_3dep.py tennessee --auto

STEP 1: DOWNLOAD ELEVATION BBOX
Input: User command with region bounds
Process: HTTP request to OpenTopography API
Output: data/raw/srtm_30m/tennessee_bbox_30m.tif
Format: GeoTIFF, Float32, 9000x1800 pixels, ~60 MB, EPSG:4326
Content: Elevation values for entire rectangle, all pixels filled
Can skip if exists: YES - file is reusable
Requires internet: YES - first time only

STEP 2: LOAD STATE BOUNDARY
Input: Country name + state name strings
Process: Query Natural Earth admin_1 shapefile (download first time, then cached)
Output: data/.cache/borders/ne_110m_admin_1.pkl (cache), in-memory GeoDataFrame
Format: Pickled GeoDataFrame with geometry column
Content: State polygon with ~500 (lon, lat) points defining boundary
Can skip if cached: YES - cache persists between runs
Requires internet: YES - first time only (~10 sec download)
Subsequent runs: NO - uses local cache (~0.1 sec)

STEP 3: CLIP TO STATE BOUNDARY
Input: data/raw/srtm_30m/tennessee_bbox_30m.tif + state geometry from Step 2
Process: rasterio.mask() sets pixels outside state polygon to NaN
Output: data/clipped/srtm_30m/tennessee_clipped_srtm_30m_v1.tif
Format: GeoTIFF, Float32, 9000x1800 pixels (same dimensions), ~40 MB, EPSG:4326
Content: Elevation inside state, NaN outside state (sparse, compresses better)
Can skip if exists: YES - but must regenerate if raw TIF or boundary changes
Requires internet: NO - all local processing

STEP 4: DOWNSAMPLE FOR VIEWER
Input: data/clipped/srtm_30m/tennessee_clipped_srtm_30m_v1.tif
Process: Subsample by taking every Nth pixel (step=11 for each dimension)
Output: data/processed/srtm_30m/tennessee_srtm_30m_800px_v2.tif
Format: GeoTIFF, Float32, 800x160 pixels, ~3 MB, EPSG:4326
Content: Downsampled elevation, NaN pattern preserved
Can skip if exists: YES - but must regenerate if clipped TIF changes
Requires internet: NO - all local processing

STEP 5: EXPORT ELEVATION DATA
Input: data/processed/srtm_30m/tennessee_srtm_30m_800px_v2.tif
Process: Read array, convert NaN to null, package with metadata
Output: generated/regions/tennessee_srtm_30m_v2.json
Format: JSON text file, ~5 MB
Content: {"width": 800, "height": 160, "elevation": [[null, 120.5, ...], ...], "bounds": {...}, "stats": {...}}
Can skip if exists: YES - but must regenerate if processed TIF changes
Requires internet: NO - all local processing
Used by: Web viewer (loaded via fetch())

STEP 6: EXPORT BORDER COORDINATES
Input: State geometry from Step 2 (can reload from cache)
Process: Extract exterior coordinates from polygon, convert to lon/lat arrays
Output: generated/regions/tennessee_srtm_30m_v2_borders.json
Format: JSON text file, ~300 KB
Content: {"states": [{"name": "Tennessee", "segments": [{"lon": [-90.31, ...], "lat": [35.00, ...]}]}]}
Can skip if exists: YES - but must regenerate if state boundary data updates
Requires internet: NO - uses cached boundary data
Used by: Web viewer (loaded via fetch())

STEP 7: VIEWER LOADS DATA
Input: User selects "Tennessee" from dropdown
Process: fetch() both JSON files from generated/regions/
Output: JavaScript objects in browser memory
Format: rawElevationData object + borderData object
Content: Parsed JSON with typed arrays ready for Three.js
Can skip if cached: Browser may cache, but typically re-fetches
Requires internet: YES if serving from remote server, NO if localhost

STEP 8: VIEWER RENDERS SCENE
Input: rawElevationData + borderData objects from Step 7
Process: Create Three.js BufferGeometry for terrain + Line geometry for borders
Output: Rendered WebGL scene in canvas element
Format: GPU buffers with vertex positions, colors, normals
Content: 3D bars for elevation (skip null values), cyan lines for state boundary
Can skip: NO - regenerated on every param change (bucket size, colors, etc)
Requires internet: NO - all client-side processing

## Can Existing Downloads Be Reprocessed?

YES - All steps after download can be re-run without internet:

Scenario 1: Already have Tennessee raw TIF, want to add state clipping
Command: python -m src.pipeline run_pipeline data/raw/srtm_30m/tennessee_bbox_30m.tif tennessee srtm_30m --boundary-name "United States of America/Tennessee" --boundary-type state
Result: Generates Steps 3-6 using existing raw TIF
Internet needed: Only if state boundary not cached (Step 2)

Scenario 2: State boundaries just implemented, need to reprocess all existing states
Loop through all TIF files in data/raw/srtm_30m/
Run pipeline for each with state boundaries enabled
Internet needed: Only first time to download admin_1 shapefile (~10 sec)
Time: ~5 sec per state after that = ~4 minutes for 48 states

Scenario 3: Change downsample resolution (e.g., 800px to 1200px)
Only need to regenerate Steps 4-6 from clipped TIF
No internet needed, ~2 sec per state

Scenario 4: Export format changes (e.g., JSON structure update)
Only need to regenerate Steps 5-6 from processed TIF
No internet needed, ~1 sec per state

## Live Processing Feasibility

Can borders be applied live in viewer without re-download?
NO - Clipping must happen server-side with rasterio because:
- Browser can't read GeoTIFF format (binary, compressed)
- Masking requires geometric operations (point-in-polygon tests for millions of pixels)
- Would need to download full unclipped data (~60 MB) to browser
- Python libraries (rasterio, shapely) not available in JavaScript

Current approach (pre-process server-side) is correct:
- Download once: ~60 MB raw TIF
- Clip once: ~2 seconds, produces ~40 MB clipped TIF
- Export once: ~1 second, produces ~5 MB JSON
- Viewer downloads: ~5 MB total (already clipped)
- Render: Instant in browser

Alternative (client-side clipping) would be:
- Download: ~60 MB unclipped data to browser
- Clip: Need full geometry library in JavaScript (~1 MB extra)
- Process: 5-10 seconds in browser for geometry operations
- Worse user experience, more bandwidth, slower

Conclusion: Server-side preprocessing is optimal. Pipeline cannot be done live but steps are incremental and cacheable.

## File Size Impact

Natural Earth admin_1 cache: ~10 MB (one-time)
Clipped TIF: Smaller than bbox (sparse data compresses better)
Border JSON: ~300 KB per state
No increase in elevation JSON size

## Performance

First state boundary load: ~10 seconds (download admin_1)
Subsequent loads: < 0.1 seconds (cached)
Clipping operation: ~2 seconds per state
Total pipeline: ~5 seconds (with cache), ~15 seconds (first time)

## Validation

Check clipped file exists and is smaller than raw bbox
Inspect data array for NaN values at edges (15-30% for Tennessee)
Visual check in viewer: shape not rectangular, matches real geography
Border lines follow state boundary exactly

## Implementation Phases

Phase 1 (6-8 hours): Extend BorderManager, update pipeline, add CLI tools
Phase 2 (3-4 hours): Update downloader, test with Tennessee
Phase 3 (3 hours): Export borders, update viewer rendering
Phase 4 (2-4 hours): Batch process all 48 states
Phase 5 (2 hours): Test varied states, update docs

Total: 16-21 hours estimated

## Batch Processing

Script to reprocess all 48 contiguous US states:
for state_id in US_STATES:
    os.system(f"python downloaders/usa_3dep.py {state_id} --auto")

Time: ~45 seconds per state = ~36 minutes total

## Error Handling

State not found: Try fuzzy match, list available states
Clipping fails: Fall back to bbox, log warning
Download fails: Retry with backoff, use cache if available
Border export fails: Non-critical, continue without borders

## Testing Strategy

Test states with varied shapes:
- Tennessee: Irregular, original problem case
- Florida: Peninsula with complex coastline
- Michigan: Two peninsulas, water boundaries
- California: Long coastline and mountains
- Colorado: Actually rectangular, verify no regression

Visual verification: Shape matches real geography, no artifacts, borders render correctly

## Global Applicability

Same system works for:
- Canadian provinces (13)
- Australian states (8)
- German states (16)
- Japanese prefectures (47)
- Any country's subdivisions in Natural Earth admin_1

No US-specific code except state name mapping. BorderManager.get_state() works globally.

## Files to Modify

src/borders.py: Add 4 new methods (~100 lines)
src/pipeline.py: Update clip_to_boundary() (~50 lines)
downloaders/usa_3dep.py: Change 3 lines, add state name mapping dict
export_borders_for_viewer.py: Add state export logic (~80 lines)
interactive_viewer_advanced.html: Update recreateBorders() (~60 lines)
border_utils.py: Add 2 new CLI commands (~80 lines)

Total new code: ~470 lines
Modified existing: ~50 lines

## Success Criteria

Tennessee displays with correct irregular shape, not rectangle
All 48 contiguous US states show actual boundaries
State borders render as cyan lines in viewer
Performance < 1 second to load cached state data
System works for other countries' subdivisions
Zero regression in existing country-level borders

