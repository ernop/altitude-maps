# Codebase Review: Altitude Maps Viewer

Date: 2026-07-15
Reviewed version: 1.382 (changes land as 1.383)
Scope: full read of the browser viewer (`js/`, `interactive_viewer_advanced.html`), the Python
pipeline entry points (`src/pipeline.py`, `src/config.py`), and a live comparison against the
production deployment at fuseki.net/altitude-maps.

This document records what was found, what was changed in this pass, and what remains as
recommended follow-up. Items changed in this pass are marked [FIXED]; open recommendations are
marked [OPEN].

---

## 1. Overall Assessment

The project is in good working order. The architecture is sound: a Python pipeline produces
gzipped JSON grids, and a dependency-free (no bundler) Three.js viewer renders them as instanced
bars with several camera schemes, color schemes, and a resolution slider. The module layout under
`js/` is clean and each file has a focused responsibility.

The main problems found were not structural. They were:

1. Data was held in memory as nested JavaScript arrays of `Number` (8 bytes + pointer + heap
   object overhead per cell), and every consumer re-checked three different nodata encodings
   (`null`, `undefined`, `NaN`).
2. Hot paths did redundant work: full instanced-mesh raycasts on every mousemove, per-instance
   `Object3D` matrix composition on every rebuild, and full re-bucketing that blocked the main
   thread during pregeneration.
3. Interaction quality: pan did not track the cursor (constant-rate incremental pan), wheel zoom
   speed depended on the input device, and the `camera` URL parameter was written but never read
   back on load.
4. Several hundred lines of dead code (two removed legacy control paths, an unused bucketing
   module, an orphaned HUD-drag system) and heavy console/activity-log spam.
5. The pipeline exported floats at full precision, roughly doubling `.json.gz` sizes for
   non-integer DEMs.

All five areas were addressed. Details below.

---

## 2. Data Path and Memory [FIXED]

### 2.1 Typed-array elevation grids

`loadElevationData()` now converts each row of the decoded JSON grid into a `Float32Array`,
with `NaN` as the single nodata encoding. All consumers were updated:

- `computeBucketedData()` reads rows directly and uses `v === v` / `Number.isFinite(v)` checks.
- `computeDerivedGrids()` (slope/aspect) outputs `Float32Array` rows as well.
- `map-shading.js` and `terrain-renderer.js` use `Number.isFinite` instead of
  `=== null || === undefined` checks.

Effect: a 3M-cell region drops from roughly 100+ MB of boxed doubles and array-of-array overhead
to ~12 MB of flat storage per grid, and the bucketing loop no longer megamorphs on element types.

### 2.2 Single-pass bucketing

`computeBucketedData()` previously collected values into a temporary array per bucket and then
reduced it. It now accumulates max/mean/count in a single pass over the source window, and
tracks the nodata count so boundary cells are still preserved.

### 2.3 Cooperative pregeneration

`pregenerateCommonBucketSizes()` used to compute every common bucket size in one synchronous
burst after load, freezing the UI for multiple seconds on large regions. It now computes one
bucket size per `setTimeout` slice, keeping the main thread responsive. A future improvement
would be to move bucketing into a Web Worker entirely (see section 7).

---

## 3. Rendering Hot Paths [FIXED]

### 3.1 Direct instance-matrix writes

`terrain-renderer.js:createBars()` wrote each instance transform through a shared
`THREE.Object3D` (`position/scale` set, `updateMatrix()`, `setMatrixAt()`). Since the bars only
ever need a scale + translation, the sixteen matrix elements are now written directly into
`instancedMesh.instanceMatrix.array`. This removes an Euler-to-quaternion-to-matrix composition
per instance per rebuild (hundreds of thousands of instances at low bucket sizes).

### 3.2 Plane-only raycasting for the HUD

`geometry-utils.js:raycastToWorld()` raycast against the full `InstancedMesh` on every
mousemove to feed the cursor HUD. Intersecting an instanced mesh tests every instance, so this
was O(instance count) per mouse event. It now intersects the `y = 0` ground plane analytically,
which is exact for the HUD's purpose (geographic coordinates under the cursor) and O(1).

### 3.3 Activity log cap

`activity-log.js` appended DOM nodes without bound; long sessions accumulated thousands of
entries. Now capped at 400, trimming from the oldest.

---

## 4. Controls [FIXED]

### 4.1 Anchored grab-pan

Left-drag pan was incremental: it moved the camera at a rate proportional to mouse delta, so the
terrain slid relative to the cursor. `ground-plane-camera.js` now records the ground point under
the cursor at mousedown and, on each mousemove, translates camera + focus so that the grabbed
point stays under the cursor. Movement is clamped to prevent runaway jumps when the ray
approaches the horizon; if no ground point is under the cursor, it falls back to the old
incremental pan.

### 4.2 Device-independent wheel zoom

Wheel zoom applied `deltaY` directly, so trackpads (small, high-frequency deltas) and mouse
wheels (large, chunky deltas) zoomed at very different speeds. Zoom is now exponential in a
normalized delta (`deltaMode`-aware), giving consistent behavior across devices.

### 4.3 Camera scheme restored from URL

The `camera` URL parameter was written on scheme change but ignored on load. `init()` now reads
it and activates the matching scheme, so shared links reproduce the full view.

### 4.4 On-screen keyboard controls wired up

`interactive_viewer_advanced.html` called `toggleKeyboardControls()` which did not exist
(silent `ReferenceError` on click). Implemented it, plus `initKeyboardControlButtons()` which
makes the on-screen WASD/QE buttons dispatch synthetic key events.

---

## 5. Dead Code and Logging [FIXED]

Removed (~700 lines net across the viewer):

- `js/bucketing.js` — an entire module that was never loaded by the HTML.
- Legacy mouse handlers (`onMouseDown`/`onMouseMove`/`onMouseUp`), `setView`,
  `handleKeyboardMovement` in `viewer-advanced.js` — superseded by the camera-scheme system.
- The HUD drag/persistence system (`initHudDragging`, `saveHudPosition`, `loadHudPosition`,
  `updateCursorHUD`, HUD settings load/save/bind) — orphaned; `hud-system.js` owns this now.
- `linearZoom_OLD`, `createPivotMarker`, `createBarsTerrain`,
  `computeDistanceToDataEdgeMeters`, `toggleControlsHelp`, the global `barsDummy`.
- `console.table` dumps and per-region logging in manifest loading; scene-traversal debug logs
  in the renderer.

---

## 6. Pipeline and Data Files [FIXED]

### 6.1 Float rounding on export

`src/pipeline.py` now rounds elevations to 2 decimal places (centimeter precision) before JSON
serialization. Full-precision floats serialized 17 significant digits, roughly doubling gzipped
size for float DEMs. Integer-valued DEMs (most SRTM-derived data) are unaffected.

`repack_regions.py` (new) applies the same rounding to already-generated `.json.gz` files in
place, so existing data can be shrunk without re-running the pipeline. Supports `--dry-run`.

### 6.2 Sample data fetcher

`fetch_sample_data.py` (new) downloads the manifest, adjacency file, and any named regions from
production into `generated/regions/`, so a fresh checkout can run the viewer locally without
GIS dependencies or API keys. `--list` shows available regions. Documented in `install.md`
("Quick Start Without the Pipeline").

### 6.3 URL state hygiene

`updateURLParameter()` used `history.pushState` for every slider tweak, polluting browser
history. It now uses `replaceState` by default; `pushState` is reserved for region changes.
Region data fetches also carry a cache key derived from the manifest stats, so browsers can
cache region files across sessions and still pick up re-generated data.

---

## 7. Open Recommendations [OPEN]

In rough priority order:

1. **Web Worker bucketing.** Bucketing is now single-pass over typed arrays, but still runs on
   the main thread. Moving `computeBucketedData` + derived grids into a worker (transfering the
   `Float32Array` buffers) would eliminate the remaining resolution-change hitch on large
   regions.
2. **Binary data format.** The `.json.gz` format decodes to text and then parses. A flat binary
   format (header + Float32/Int16 payload, still gzipped) would cut decode time and file size
   substantially. The pipeline already holds numpy arrays, so export is trivial; the loader
   change is contained in `loadElevationData()`.
3. **Surface mesh mode.** Bars are distinctive but cost one instance per cell. An indexed
   triangle grid (one vertex per cell corner) would render the same data with far less geometry
   and enable smooth shading, contour lines, and higher effective resolution for the same frame
   budget. Could live alongside bars as a render mode.
4. **Merge `three.min.js` r128 upgrade.** r128 is from 2021; current releases have substantially
   better `InstancedMesh` support, `WebGLRenderer` performance, and color management. The
   upgrade is mostly mechanical but touches every module that constructs Three objects.
5. **Favicons missing from the repository.** `interactive_viewer_advanced.html` references
   `favicon-180/192/512.png`, which exist on production and in `deploy.ps1` but are not in git.
   Commit them (they are small) so fresh clones do not 404.
6. **jQuery dependency.** Loaded from CDN but used in only a handful of places. Removing it
   drops a network dependency and ~30 KB.
7. **`console.log` volume.** Reduced in this pass but still chatty during load. Consider a
   log-level flag (e.g. `?debug=1`) gating the remaining diagnostics.

---

## 8. Testing Performed

- Downloaded California and Estonia data from production via `fetch_sample_data.py`.
- Served locally (`serve_viewer.py`) and drove the viewer with headless Chromium (Playwright):
  region load, bucket-size changes across the slider range, color scheme changes, camera scheme
  switching, wheel zoom, drag pan, URL parameter round-trip.
- Verified no console errors during the above, and that bucketed grid dimensions, bar counts,
  and elevation ranges match pre-change values for both integer (Estonia) and float (California)
  DEMs.
- `repack_regions.py --dry-run` verified against downloaded production files.
