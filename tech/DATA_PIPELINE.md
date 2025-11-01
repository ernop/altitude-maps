# Data Pipeline: Complete Process Specification

**Canonical reference for the complete data pipeline from region definition to viewer-ready output.**

This document defines the exact steps, file paths, naming conventions, and rules for processing elevation data regions. Every region must belong to a class/group that makes its requirements clear.

---

## Region Classes

Every region must be classified into one of these groups:

### US State
- **Definition location**: `src/regions_config.py` -> `US_STATES`
- **Source**: USGS 3DEP (10m resolution)
- **Clipping**: Always `clip_boundary=True` -> clips to `"United States of America/<StateName>"`
- **Boundary source**: Natural Earth administrative boundaries (10m recommended)
- **Downloader**: `download_all_us_states_highres.py`

### Country
- **Definition location**: `src/regions_config.py` -> `COUNTRIES`
- **Source**: SRTMGL1 (30m) within 60degN-56degS, or COP30 (30m) outside that range
- **Clipping**: Usually `clip_boundary=True` -> clips to `"<CountryName>"`
- **Boundary source**: Natural Earth country boundaries (10m recommended)
- **Downloader**: OpenTopography GlobalDEM API

### Region (Islands/Peninsulas/Ranges)
- **Definition location**: `src/regions_config.py` -> `REGIONS`
- **Source**: SRTMGL1 (30m) within 60degN-56degS, or COP30 (30m) outside that range (unless overridden)
- **Clipping**: Usually `clip_boundary=False` -> no boundary clipping (uses bbox)
- **Boundary source**: N/A (free-form regions)
- **Downloader**: OpenTopography GlobalDEM API

**Note**: Some regions may have `clip_boundary=True` if they correspond to territories with known boundaries (e.g., Iceland).

---

## Pipeline Stages

### 1. Validate Region Definition

**Check**: Region exists in `src/regions_config.py` in `ALL_REGIONS`.

**Validation function**: `src/regions_config.is_region_configured(region_id)`

**Failure**: If region not found, stop with error message. Use `--list-regions` to see available options.

---

### 2. Determine Dataset & Resolution (Overrides First)

**Rule**: Check if region has hardcoded high-resolution requirements.

**US States**: Always use USGS 3DEP at 10m resolution (hardcoded in downloader).

**Other regions**: Check `RegionConfig.recommended_dataset` field:
- If set to a specific dataset (e.g., `"COP30"`, `"AW3D30"`), use that
- If not set, continue to step 2b for latitude-based selection

**Location**: Defined in `src/regions_config.py` per region.

**Rationale**: High-resolution overrides must be explicit in region definition, not inferred by download code.

---

### 3. Dataset Selection by Latitude (if no override)

**Rule**: For regions using OpenTopography (non-US), select dataset based on latitude:

- **If `north > 60.0` OR `south < -56.0`**: Use `COP30` (Copernicus DEM 30m)
- **Otherwise**: Use `SRTMGL1` (SRTM 30m)

**Location**: This logic is embedded in download functions (see `ensure_region.py` lines 342-351).

**Note**: This is only applied when step 2 did not produce a specific dataset.

---

### 4. Acquire Raw Elevation (GeoTIFF)

**Output paths** (by source):
- **US states (3DEP)**: `data/raw/usa_3dep/<region_id>_3dep_10m.tif`
- **International (OpenTopography)**: `data/raw/srtm_30m/<region_id>_bbox_30m.tif`

**File format**: Single-band GeoTIFF with CRS and transform metadata.

**Resolution**:
- US states: 10m (from USGS 3DEP)
- International: 30m (SRTMGL1 or COP30 depending on latitude from step 2b)

**Validation** (auto-run):
- File size > 1KB (catches corrupted downloads)
- Rasterio can open the file
- Has CRS and transform
- Can read a sample window (confirms data accessible)
- **Auto-cleanup**: Corrupted files are automatically deleted

**Metadata**: Raw downloads save metadata JSON at `data/metadata/<region_id>_raw.json` with bounds, download date, source, file hash.

---

### 5. Automatic Tiling for Large Areas (invisible)

**Trigger**: 
- OpenTopography request would exceed ~420,000 km² area, OR
- Width or height > ~4 degrees, AND
- Using SRTMGL1 dataset (COP30 has different limits)

**Process**:
1. Calculate tile grid (approximately 3.5deg per tile)
2. Download each tile to shared pool: `data/raw/srtm_30m/tiles/tile_N##_W###_{dataset}_{res}.tif`
   - Uses content-based SRTM-style integer degree grid naming
   - Tiles automatically reused across regions with overlapping bounds
3. Validate each tile (same checks as step 2)
4. Merge all tiles into single output: `data/raw/srtm_30m/<region_id>_bbox_30m.tif`
5. Save metadata indicating tiling was used (tile count, bounds)

**User experience**: This happens automatically during download. User sees "Downloading tile 1/4..." but final output is a single file.

**Important**: If region bounds change (detected via metadata comparison), stale raw file is deleted and re-downloaded to include new area.

---

### 6. Clip to Administrative Boundary (if `clip_boundary=True`)

**Decision rule**: Based on region class and `RegionConfig.clip_boundary`:

- **US State**: Always clips to `"United States of America/<StateName>"` (state boundary)
- **Country**: Clips to `"<CountryName>"` if `clip_boundary=True` (default True)
- **Region**: Usually `clip_boundary=False` (free-form regions, no boundary available)

**Boundary source**: Natural Earth (10m/50m/110m) via `src/borders.get_border_manager()`

**Boundary resolution**:
- **Default**: 10m (high detail, recommended)
- **Configurable**: `--border-resolution 10m|50m|110m` (use 10m for production)

**Operation**: `rasterio.mask(..., crop=True, filled=False)` to remove empty space outside boundary.
 
**Failure policy**:
- If a region is classified to require boundaries (US State or Country, or any region with `clip_boundary=True`) and the boundary geometry is missing or cannot be loaded, the job MUST error and stop. Do not proceed using the raw bounding box.

**Output path**:
- `data/clipped/<source>/<region_id>_clipped_<source>_v1.tif`

**Output format**: GeoTIFF, same resolution as input, cropped to boundary shape. May still be in EPSG:4326 (lat/lon).

**Critical**: If clipped file is regenerated (corruption detected, force reprocess), ALL downstream files (processed, generated) are automatically deleted to ensure consistency.

**Metadata**: Saved to `data/metadata/<region_id>_clipped.json` with source file hash, clip boundary name, version.

**Note**: Clipping preserves CRS from input. Reprojection to metric CRS happens in next stage (Stage 7).

---

### 7. Reproject to Metric CRS (Fix Latitude Distortion)

**Purpose**: Fix horizontal stretching caused by EPSG:4326 (lat/lon) at all latitudes except equator.

**Input**: Clipped TIF from Stage 6 (or raw TIF if `clip_boundary=False`)

**When**: Applied to ALL regions with EPSG:4326 input (no exceptions).

**Process**:
1. Check if input CRS is EPSG:4326
2. If yes, calculate average latitude from clipped bounds
3. Reproject to metric CRS:
   - Mid-latitudes (|lat| < 85deg): EPSG:3857 (Web Mercator)
   - High latitudes (|lat| >= 85deg): EPSG:3413 (Arctic) or EPSG:3031 (Antarctic)
4. Initialize destination array with nodata
5. Use bilinear resampling with `src_nodata` and `dst_nodata` parameters
6. Validate elevation range post-reproject (fail hard if hyperflat detected)

**Output path**: 
- Overwrites clipped TIF if reprojection occurred, OR
- Creates separate reprojected file: `data/clipped/<source>/<region_id>_reprojected_<source>_v1.tif`

**Output format**: GeoTIFF in metric CRS (EPSG:3857 or polar stereographic).

**Critical note**: **After this stage, data is treated as a pure 2D array everywhere else in the pipeline.** The reprojection fixes the aspect ratio distortion once, and from this point forward the data is simply a uniform grid of elevation values. No further geographic transformations are applied.

**Validation**: 
- Elevation range validation (fail hard if <50m range - catches reprojection corruption)
- CRS verification (must be metric CRS, not EPSG:4326)

**Metadata**: Updated in clipped metadata with reprojection details.

---

### 8. Downsample/Process for Viewer (preserve aspect)

**Target resolution**: `--target-pixels` (default 2048). Short side is computed to preserve aspect ratio.

**Input**: Reprojected TIF from Stage 7 (MUST be in metric CRS, NOT EPSG:4326)

**Critical requirement**: Input MUST already be in metric CRS (NOT EPSG:4326). If input is EPSG:4326, this stage fails - reprojection (Stage 7) must complete first.

**Validation**: If existing processed file is EPSG:4326, it is deleted and regenerated.

**Process**:
- Downsample preserving aspect ratio (use same step size for both dimensions)
- Output: Single-band float32 GeoTIFF with consistent nodata value
- **No reprojection needed** - input is already in metric CRS from Stage 7

**Output path**:
- `data/processed/<source>/<region_id>_<source>_<target_pixels>px_v2.tif`

**Output format**: GeoTIFF, metric CRS, aspect-correct, downsampled to target pixel dimensions.

**Validation checks**:
- Pixel sanity (sample central window)
- CRS is NOT EPSG:4326 (hard fail)
- Elevation range reasonable (catches corruption)
- Coverage percentage (warn-only)

If elevation range is unreasonably small (historical "hyperflat" error), this stage or earlier clipping validation MUST fail and stop. The front-door command will attempt an auto-fix by force reprocessing; if that cannot repair, the job fails clearly.

**Metadata**: Saved to `data/metadata/<region_id>_processed.json` with source file hash, target pixels, version.

---

### 9. Export to JSON

**Input**: Processed TIF from Stage 8

**Process**:
1. Read processed TIF (already in metric CRS, aspect-correct)
2. Convert bounds to EPSG:4326 (lat/lon) for viewer metadata
3. Filter nodata and extreme elevation values (< -500m or > 9000m)
4. Convert to 2D array with `null` for nodata pixels
5. Calculate statistics (min, max, mean)

**Output path**:
- `generated/regions/<region_id>_<source>_<target_pixels>px_v2.json`

**Output format**: JSON with fields:
- `version`: Export format version (e.g., `"export_v2"`)
- `region_id`: Region identifier
- `source`: Data source (e.g., `"usa_3dep"`, `"srtm_30m"`)
- `width`, `height`: Dimensions
- `elevation`: 2D array (list of lists) with `null` for nodata
- `bounds`: `{left, right, top, bottom}` in EPSG:4326 degrees
- `stats`: `{min, max, mean}` elevation values

**Validation** (must pass or export fails):
- Aspect ratio matches raster dimensions (hard fail if mismatch)
- Structure valid (all required fields present)
- Coverage warning if < 20% valid pixels (doesn't fail)

**Metadata**: Saved to `data/metadata/<region_id>_export.json` with source file hash, export version.

---

### 10. Gzip Compression

**Input**: JSON file from Stage 9

**Output path**:
- `generated/regions/<region_id>_<source>_<target_pixels>px_v2.json.gz`

**Process**: Gzip compress with compression level 9 (maximum).

**Compression ratio**: Typically 85-95% reduction for sparse elevation data.

**Usage**:
- Production: Serve `.json.gz` files (web server auto-detects and serves compressed)
- Development: Both `.json` and `.json.gz` are created

**Metadata**: Compression stats logged during export.

---

### 11. Update Viewer Manifest

**Manifest file**: `generated/regions/regions_manifest.json`

**Format**: JSON object/dict (NOT array) keyed by `region_id`:
```json
{
  "version": "export_v2",
  "regions": {
    "california": {
      "name": "California",
      "description": "California elevation data",
      "source": "usa_3dep",
      "file": "california_usa_3dep_2048px_v2.json",
      "bounds": {...},
      "stats": {...}
    },
    ...
  }
}
```

**Process**:
1. Scan `generated/regions/*.json` (excluding `_meta.json`, `_borders.json`, and manifest files)
2. Extract region_id from filename or JSON content
3. Build manifest entry from JSON metadata
4. Write/update manifest file

**When**: After every successful export (Stage 10).

**Viewer usage**: Viewer loads this manifest at startup to populate region dropdown.

**Critical**: If a region's JSON is deleted but manifest still references it, region won't load. Run manifest regeneration if needed.

---

## Versioning and Cache Management

### Version Checking

Each pipeline stage has a version:
- `raw_v1`: Raw downloads (immutable, never changes)
- `clipped_v1`: Boundary clipping algorithm
- `processed_v2`: Downsampling/processing algorithm
- `export_v2`: JSON export format

**Checking**: When loading cached data, version compatibility is checked. Mismatches trigger automatic regeneration.

**Version definitions**: `src/versioning.py`

### Cache Invalidation

**Automatic triggers**:
- Version mismatch in metadata
- Source file hash changed (downstream files regenerated)
- Bounds changed in raw file metadata (raw file re-downloaded)

**Manual**: Use `--force-reprocess` flag in `ensure_region.py` to force regeneration.

---

## Entry Point Command

**Single command for complete pipeline**: `python ensure_region.py <region_id> [options]`

**Options**:
- `--target-pixels N`: Target resolution (default 2048)
- `--border-resolution 10m|50m|110m`: Border detail (default 10m)
- `--force-reprocess`: Force full rebuild
- `--check-only`: Check status only, don't download/process
- `--list-regions`: List all available regions

**Status & Logging requirements**:
- Each job MUST report which stage it is executing and the outcome of all prior stages.
- A later stage MUST NOT run if an earlier stage failed; fail fast with a clear error.
- Use `--check-only` to see current status without modifying files.

---

## File Path Summary

### Raw Data
- US states: `data/raw/usa_3dep/<region_id>_3dep_10m.tif`
- International: `data/raw/srtm_30m/<region_id>_bbox_30m.tif`

### Clipped Data
- `data/clipped/<source>/<region_id>_clipped_<source>_v1.tif`

### Processed Data
- `data/processed/<source>/<region_id>_<source>_<target_pixels>px_v2.tif`

### Exported Data
- JSON: `generated/regions/<region_id>_<source>_<target_pixels>px_v2.json`
- Gzip: `generated/regions/<region_id>_<source>_<target_pixels>px_v2.json.gz`
- Manifest: `generated/regions/regions_manifest.json`

### Metadata
- `data/metadata/<region_id>_raw.json`
- `data/metadata/<region_id>_clipped.json`
- `data/metadata/<region_id>_processed.json`
- `data/metadata/<region_id>_export.json`

---

## Region Class Summary Table

| Class | Source | Resolution | Clip Boundary | Boundary Type | Boundary Source |
|-------|--------|------------|---------------|---------------|-----------------|
| US State | USGS 3DEP | 10m | Always True | `"United States of America/<StateName>"` | Natural Earth 10m |
| Country | SRTMGL1/COP30 | 30m | Usually True | `"<CountryName>"` | Natural Earth 10m |
| Region | SRTMGL1/COP30 | 30m | Usually False | N/A | N/A |

---

## Quick Reference: Decision Flow

```
1. Region defined? (src/regions_config.py)
   NO -> Error: use --list-regions
   YES -> Continue

2. Dataset & resolution override?
   US State -> Use USGS 3DEP 10m
   If `recommended_dataset` set -> Use that dataset
   Otherwise -> Continue to 3

3. Latitude-based dataset?
   north > 60deg OR south < -56deg -> COP30
   Otherwise -> SRTMGL1

4. Download raw data
   Large area? -> Auto-tile (5) and merge
   Save to: data/raw/<source>/<region_id>_*.tif

6. Clip boundary?
   clip_boundary=True -> Clip to boundary (Natural Earth 10m)
   clip_boundary=False -> Skip clipping, use raw
   Save to: data/clipped/<source>/<region_id>_clipped_*.tif

7. Process/downsample
   Reproject if EPSG:4326 -> Metric CRS
   Downsample to target_pixels (preserve aspect)
   Save to: data/processed/<source>/<region_id>_*_px_v2.tif

8. Export JSON
   Convert to 2D array with nulls
   Save to: generated/regions/<region_id>_*_v2.json

9. Gzip
   Compress JSON
   Save to: generated/regions/<region_id>_*_v2.json.gz

10. Update manifest
   Scan all JSON files
   Update: generated/regions/regions_manifest.json
```

---

## Related Documentation

- **Data Principles**: `tech/DATA_PRINCIPLES.md` - Core principles (aspect ratios, rendering)
- **Data Format**: `tech/DATA_FORMAT_EFFICIENCY.md` - JSON format and GZIP compression
- **Versioning System**: `src/versioning.py` - Version definitions and compatibility
- **Implementation**: `src/pipeline.py` - Pipeline implementation
- **Entry Point**: `ensure_region.py` - Command-line interface

---

**Last Updated**: 2025-10-29
**Status**: Canonical reference - all data processing must follow these stages and rules.

