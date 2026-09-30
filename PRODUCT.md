# Altitude Maps: Product Direction and Decisions

This file is the canonical record of product requirements and settled decisions. Update it in the same change that alters a requirement or decision.

## Goal

Fly around any place on Earth, with the terrain at the best resolution that exists, and see the places I have walked (and the places I plan to walk) draped on that terrain, with an adjustable vertical exaggeration that makes slopes obvious.

Concrete requirements:

1. **No pre-configured regions.** Any point on Earth is reachable by panning, searching a place name, typing coordinates, or selecting a GPS track. California and the rest of the US get the highest resolution available.
2. **Best available elevation, fetched efficiently.** Only the tiles actually looked at (or explicitly prefetched) are downloaded, once, and cached on disk.
3. **Personal GPS traces.** All tracks from configured folders (for example, exports from the Matthoom project) are listed, drawn on the terrain, and individually explorable. Planned routes are shown in a different color.
4. **Slopes must be readable.** Vertical exaggeration from 1x to 10x, a slope-steepness overlay, and a track colored by grade, with an elevation profile.
5. **Flight.** Orbit the terrain with the mouse, fly freely with the keyboard, and replay a walk as a chase-camera flight.

## Review of the previous system (October 2025 state)

The previous system (`ensure_region.py`, `src/`, `interactive_viewer_advanced.html`, `js/viewer-advanced.js`) is a batch pipeline over 89 hand-configured regions. It downloads rasters from USGS/OpenTopography/Copernicus, clips them to boundaries, downsamples each to one grid of about 2048 x 2048 pixels, exports JSON, and renders that grid as instanced 3D bars in Three.js.

What it does well:
- Careful resolution selection (Nyquist rule), boundary clipping, format versioning, a polished bar renderer with many camera schemes.
- Good for comparing whole states and countries as data objects.

Why it cannot reach the new goal:
- **Fixed regions and a single grid per region.** A 2048-pixel grid over a state is hundreds of meters per pixel; over a 10 km walk it would need a new region definition and a new pipeline run. There is no level of detail: close-up and far-away views share one resolution.
- **Resolution ceiling of 10 m**, while 1 m lidar now covers most of California.
- **No track support.**
- **Operational weight.** Around 40 one-off scripts and reports at the repository root, OpenTopography API keys and rate-limit handling, GMTED manual downloads, a 3,466-line viewer file.

Decision: the previous system stays in place, frozen and working, for whole-region bar visualizations. New work goes into `fly/`, a separate viewer and local server. Nothing in `fly/` imports from `src/`.

## Findings that drive the new design (measured September 2026)

### Elevation sources

| Source | Resolution in California | Coverage | Access |
|---|---|---|---|
| [Mapterhorn](https://mapterhorn.com/) | 1 m (z16 at 512 px), 0.5 m in places | Global; 30 m floor (Copernicus) through z12, finer where national lidar exists | Free, no key, CORS, Cloudflare CDN, BSD code, CC BY-compatible data |
| USGS 3DEP ImageServer | 1 m where lidar exists, else 10 m | US only | Free, no key, CORS; dynamic rendering, first request up to 8 s, occasional 502 |
| AWS Terrain Tiles (Tilezen) | about 5-10 m effective at z15 | Global | Free; the best free global source when the previous system was built |

Evidence:
- Hillshade comparisons at Mt. Tamalpais, the Berkeley hills, and Yosemite: Mapterhorn is visually indistinguishable from 3DEP 1 m lidar (mean absolute difference 0.3-1.0 m, mostly half-pixel registration). AWS tiles are far blurrier.
- Maximum Mapterhorn zoom sampled at 20 places: 1 m or better at Mt. Tam, Half Dome, Big Sur, Joshua Tree, Mt. Shasta, Lassen, Mt. Whitney, Humboldt, rural Nevada, rural Texas, Maine, Colorado, Fuji; 0.5 m at San Diego, Hawaii, Zermatt. Gaps: Death Valley and rural Mojave (about 8 m), Denali (about 4 m), Patagonia (about 12 m).
- 3DEP had a 1 m dataset for Death Valley published 2026-06-08 (`CA_FEMAR9Southeast_D24`) that Mapterhorn has not yet ingested. New 3DEP lidar appears there first.

Decision: **Mapterhorn is the primary terrain source. USGS 3DEP fills US tiles that Mapterhorn does not have. Elsewhere, missing high-zoom tiles are upsampled from the nearest existing ancestor.** All three paths go through one local caching tile server, so the browser sees a single seamless terrain source at `/tiles/terrain/{z}/{x}/{y}`.

### Existing tools, and why they are not enough on their own

- [Google Earth Pro](https://www.google.com/earth/about/versions/) (desktop, free): opens GPX files; Tools > Options > 3D View > Elevation Exaggeration, capped at 3x. Good for a quick look at one walk today; no bulk archive, no slope overlay, exaggeration too low for gentle terrain.
- [Mapterhorn viewer](https://mapterhorn.com/viewer): terrain only, no tracks.
- [fuzue/share-gpx](https://github.com/fuzue/share-gpx): self-hosted GPX sharing with a first-person 3D flythrough; one track at a time, no exaggeration control.
- [ElyOgl/GPXMap](https://github.com/ElyOgl/GPXMap): MapLibre GPX PWA with 3D terrain, exaggeration 1-3x, slope-colored tracks. The closest in spirit; AWS terrain (blurry), no free flight.
- Physical terrain models: [TouchTerrain](https://github.com/ChHarding/TouchTerrain_for_CAGEO) (STL/OBJ from DEMs, used for 3D printing and CNC), [GPXtruder](https://gpxtruder.xyz/) (3D-printable route profiles). I did not find a specific open "Bay Area maps" project to reuse; TouchTerrain is the common engine behind such prints. The local tile cache here could feed an STL export later.

Decision: build our own small viewer, reusing the best public parts (Mapterhorn data, MapLibre renderer) rather than rebuilding them.

## Architecture of `fly/`

- **Renderer: [MapLibre GL JS](https://maplibre.org/) 6.x** loaded as an ES module from a CDN. It provides streaming level-of-detail terrain meshes, live `exaggeration`, hillshade, color relief, sky/fog, raster draping, and camera placement from a 3D position (`calculateCameraOptionsFromCameraLngLatAltRotation`, `calculateCameraOptionsFromTo`). Rebuilding these in Three.js would be the bulk of the work with no gain.
- **Local server: `fly/server.py`** (Python standard library HTTP server plus numpy and Pillow).
  - Serves the viewer.
  - `/tiles/terrain/{z}/{x}/{y}`: terrarium-encoded 512 px tiles. Disk cache, per-tile locking, negative cache for upstream 404s.
  - `/tiles/slope/{z}/{x}/{y}.png`: slope-steepness overlay computed from the terrain tile, colored in grade bands.
  - `/api/tracks...`: track listing, overview geometry, per-track profiles, drag-and-drop import.
- **Prefetch CLI: `fly/prefetch.py`** warms the tile cache along all tracks, a bounding box, or a named place, so later flights are instant and work offline.
- **Configuration:** `fly/settings.json` (gitignored), created from `fly/settings.example.json` on first run. No environment variables.

### Terrain tile policy

For tile `z/x/y`:
1. Disk cache hit: serve it.
2. Mapterhorn returns the tile: cache and serve it.
3. Mapterhorn 404, `z > 12`, tile intersects the US coverage boxes, and `z <= usgs_3dep_max_zoom`: request a 512 x 512 float32 raster for the exact tile bounds from 3DEP `exportImage`, fill any nodata pixels from the upsampled ancestor, encode as terrarium, cache, serve.
4. Otherwise: bilinear-upsample the nearest ancestor that exists. This keeps the terrain continuous; MapLibre never sees a hole.
5. Upstream network failures are not cached, so they are retried on the next request.

`terrain.max_zoom` defaults to 16 (1 m in California). Setting it to 17 uses 0.5 m data where it exists, at four times the tile count elsewhere.

### Track policy

- Formats: GPX (tracks and routes), TCX, KML (LineString and `gx:Track`), GeoJSON, CSV with latitude/longitude columns. FIT is not yet supported.
- Folders are listed in `track_dirs`, each with `kind` `walked` or `planned`. Dropped files are copied into `import_dir` (a `walked` folder).
- Geometry is simplified with Douglas-Peucker at 1 m for the selected track (the traces stay "exact" to GPS precision) and 8 m for the all-tracks overview.
- Elevation profiles use the terrain DEM, not GPS altitude. GPS altitude is noisy by tens of meters; lidar is accurate to decimeters. Tracks are densified to 5 m spacing before sampling so that simplification does not flatten hills.
- Grade is computed over a 30 m window. Gain and loss use a 1 m hysteresis.

### Slope bands

Walking grade bands, used for both the terrain overlay and track coloring:

| Grade | Angle | Color |
|---|---|---|
| under 5% | under 3 degrees | none |
| 5-10% | 3-6 degrees | green |
| 10-15% | 6-9 degrees | yellow-green |
| 15-20% | 9-11 degrees | yellow |
| 20-30% | 11-17 degrees | orange |
| 30-45% | 17-24 degrees | red |
| 45-70% | 24-35 degrees | magenta |
| 70-100% | 35-45 degrees | purple |
| over 100% | over 45 degrees | near black |

Grades are chosen for walking rather than avalanche terrain: 10% is noticeable, 20% is steep, 30% is a scramble on loose ground.

### Viewer behavior

- Full-viewport map, a side panel sized as a fraction of the viewport width, and a bottom profile panel when a track is selected.
- Vertical exaggeration slider 1x-10x, default 3x, with notches and numeric labels, current value shown.
- Basemaps: Relief (color relief auto-fitted to the elevations in view, plus hillshade), Satellite (Esri World Imagery), USGS Imagery, USGS Topo, OpenTopoMap, OpenStreetMap. Overlays: hillshade, slope.
- Camera modes: Orbit (standard MapLibre mouse), Fly (mouse-look; keys move). WASD move, Q/E down/up, arrows turn and pitch, Shift for five times speed, wheel in Fly mode changes speed. Keys are ignored while typing in inputs.
- Fly-along: a chase camera follows the selected track at a chosen height and speed (real time multiplied by 1x-500x; 4.5 km/h assumed when there are no timestamps). Clicking or dragging on the profile scrubs.
- Search: place names via Nominatim, or `lat, lon` coordinates.
- Visual rules: only pure white text on dark panels; numbers are the most prominent elements; every list row is a single line.

## Open work (ordered)

1. FIT file support (Garmin devices).
2. Matthoom integration: point `track_dirs` at its export folder; if Matthoom stores traces in a database instead of files, add an exporter there or a reader here. Needs the Matthoom storage format.
3. Static deployment mode: a build that points at Mapterhorn directly and loads tracks from a prebuilt JSON, for the existing web host.
4. Slope tiles: compute gradients with a one-pixel border from neighboring tiles to remove faint seams at tile edges.
5. Offline bundles: optionally use Mapterhorn PMTiles extracts for large areas instead of tile-by-tile prefetch.
6. Photo pins from geotagged images along tracks.
7. STL export of a selected area for 3D printing or CNC, from cached tiles.
8. Retire or archive the previous system's root-level one-off scripts once `fly/` covers everything used.
