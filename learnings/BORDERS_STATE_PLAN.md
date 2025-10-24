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

## Data Flow

Command: python downloaders/usa_3dep.py tennessee --auto

Step 1: Download bounding box
Output: data/raw/srtm_30m/tennessee_bbox_30m.tif (9000x1800 pixels, all filled)

Step 2: Load state boundary
Check cache: data/.cache/borders/ne_110m_admin_1.pkl
If missing: Download from Natural Earth (~10 sec first time)
If cached: Load from pickle (~0.1 sec)
Query: country="United States of America", state="Tennessee"
Result: Polygon geometry with ~500 boundary points

Step 3: Clip to state
Input: bbox TIF + state geometry
Process: rasterio.mask(src, [state_geometry], crop=False, nodata=np.nan)
Output: data/clipped/srtm_30m/tennessee_clipped_srtm_30m_v1.tif (same dimensions, NaN outside state)

Step 4: Downsample
Input: 9000x1800 clipped TIF
Process: Downsample to 800x160 (11x reduction)
Output: data/processed/srtm_30m/tennessee_srtm_30m_800px_v2.tif

Step 5: Export elevation
Convert to JSON with null values where NaN
Output: generated/regions/tennessee_srtm_30m_v2.json

Step 6: Export borders
Extract state boundary coordinates
Output: generated/regions/tennessee_srtm_30m_v2_borders.json

Step 7: Load in viewer
User selects Tennessee from dropdown
Fetch both JSON files
Parse into JavaScript objects

Step 8: Render
Create terrain mesh (only non-null pixels)
Draw cyan border lines at state edges
Display in Three.js

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

