# Data Pipeline: Complete Process Specification

**Canonical reference for the complete data pipeline from region definition to viewer-ready output.**

This document defines the exact steps, file paths, naming conventions, and rules for processing elevation data regions.

---

## Region Type System (CRITICAL)

**ALL regions MUST use the `RegionType` enum from `src/types.py`. Never use ad-hoc strings.**

```python
from src.types import RegionType

class RegionType(str, Enum):
    USA_STATE = "usa_state"  # US states
    COUNTRY = "country"      # Countries  
    REGION = "region"        # Islands, ranges, custom areas
```

**Enforcement**: Any code checking region types MUST:
1. Use the enum values (e.g., `RegionType.USA_STATE`)
2. Check all three cases exhaustively
3. Raise ValueError for unknown types (never silently default)

**Violation Example (FORBIDDEN)**:
```python
# DON'T DO THIS
if region_type == 'us_state':  # Wrong - string literal
    ...
elif region_type == 'international':  # Wrong - not an enum value
    ...
else:
    boundary_name = None  # Wrong - silent fallback
```

**Correct Pattern**:
```python
# DO THIS
if region_type == RegionType.USA_STATE:
    boundary_name = f"United States of America/{state_name}"
    boundary_type = "state"
elif region_type == RegionType.COUNTRY:
    boundary_name = country_name
    boundary_type = "country"
elif region_type == RegionType.REGION:
    boundary_name = None if not clip_boundary else region_name
    boundary_type = None
else:
    raise ValueError(f"Unknown region type: {region_type}")
```

---

## Region Classes

Every region is classified using the `RegionType` enum:

### USA_STATE (RegionType.USA_STATE)
- **Enum value**: `RegionType.USA_STATE` (string value: `"usa_state"`)
- **Definition location**: `src/regions_config.py` -> `US_STATES`
- **Resolution**: **Dynamic** - 10m, 30m, or 90m based on Nyquist sampling rule
- **Available sources**: USGS 3DEP (10m), SRTM (30m/90m via OpenTopography)
- **Clipping**: Always `clip_boundary=True` -> clips to `"United States of America/<StateName>"`
- **Boundary type**: `"state"` (hierarchical Natural Earth boundary)
- **Boundary source**: Natural Earth admin_1 boundaries (10m recommended)

### COUNTRY (RegionType.COUNTRY)
- **Enum value**: `RegionType.COUNTRY` (string value: `"country"`)
- **Definition location**: `src/regions_config.py` -> `COUNTRIES`
- **Resolution**: **Dynamic** - 30m or 90m based on Nyquist sampling rule
- **Available sources**: SRTM (30m/90m), Copernicus DEM (30m/90m via OpenTopography)
- **Clipping**: Usually `clip_boundary=True` -> clips to `"<CountryName>"`
- **Boundary type**: `"country"` (Natural Earth country boundary)
- **Boundary source**: Natural Earth admin_0 boundaries (10m recommended)

### REGION (RegionType.REGION)
- **Enum value**: `RegionType.REGION` (string value: `"region"`)
- **Definition location**: `src/regions_config.py` -> `REGIONS`
- **Resolution**: **Dynamic** - 30m or 90m based on Nyquist sampling rule
- **Available sources**: SRTM (30m/90m), Copernicus DEM (30m/90m via OpenTopography)
- **Clipping**: Usually `clip_boundary=False` (free-form bbox, no boundaries)
- **Boundary source**: N/A (some may have custom boundaries if `clip_boundary=True`)

**Note**: Some REGION types may have `clip_boundary=True` for territories with known boundaries (e.g., Iceland island).

---

## Pipeline Stages

### 1. Validate Region Definition

**Check**: Region exists in `src/regions_config.py` in `ALL_REGIONS`.

**Validation function**: `src/regions_config.is_region_configured(region_id)`

**Failure**: If region not found, stop with error message. Use `--list-regions` to see available options.

---

### 2. Determine Required Resolution (Nyquist Sampling Rule)

**CRITICAL**: Resolution is NEVER hardcoded by region type. It is dynamically determined based on target output size.

**Rule**: Calculate minimum required resolution using Nyquist sampling theorem (2× oversampling minimum).

**Formula**: `min_resolution ≤ visible_m_per_pixel / 2.0`

**Available Resolutions**:
- `RegionType.USA_STATE`: `[10m, 30m, 90m]`
- `RegionType.COUNTRY`: `[30m, 90m]`
- `RegionType.REGION`: `[30m, 90m]`

**See `tech/TILE_SYSTEM.md` Section 1** for complete details, examples, and calculation process.

**Implementation**: `src/downloaders/orchestrator.determine_min_required_resolution()`

---

### 3. Determine Dataset (Source Selection)

**Rule**: For each region type, select appropriate data source based on resolution + latitude.

**USA_STATE** (`RegionType.USA_STATE`):
- If requires 10m: Use `USA_3DEP` (USGS 3D Elevation Program)
- If requires 30m: Use `SRTMGL1` (OpenTopography)
- If requires 90m: Use `SRTMGL3` (OpenTopography)

**COUNTRY/REGION** (international):
- Check `RegionConfig.recommended_dataset` override first
- If north > 60°N OR south < -56°S:
  - 30m: Use `COP30` (Copernicus DEM)
  - 90m: Use `COP90` (Copernicus DEM)
- Otherwise (SRTM coverage area):
  - 30m: Use `SRTMGL1` (SRTM)
  - 90m: Use `SRTMGL3` (SRTM)

**Implementation**: `src/downloaders/orchestrator.determine_dataset_override()`

**Key Point**: Dataset selection is the OUTPUT of resolution determination, not an input.

---

### 4. Check for Existing Files (Quality-First)

**Implementation**: `src/validation.find_raw_file(region_id, min_required_resolution_meters)`

**Rule**: Search for ANY existing file that meets or exceeds quality requirement.

**Quality Logic**:
- Need 90m: Can use 10m, 30m, OR 90m (all meet requirement)
- Need 30m: Can use 10m OR 30m (won't use 90m - insufficient quality)
- Need 10m: Can ONLY use 10m

**Search Locations** (abstract bounds-based naming):
```
data/raw/usa_3dep/bbox_{bounds}_usa_3dep_10m.tif
data/raw/srtm_30m/bbox_{bounds}_srtm_30m_30m.tif  
data/raw/srtm_90m/bbox_{bounds}_srtm_90m_90m.tif
```

**Behavior**:
- If suitable file found: Skip to Stage 6 (Clipping)
- If no suitable file: Continue to Stage 5 (Download)

---

### 5. Acquire Raw Elevation (Download if needed)

**Tile-Based System**: All downloads use unified 1×1 degree tiles.

**See `tech/TILE_SYSTEM.md` for complete tile strategy** - naming, storage, grid alignment, provider limits.

**Process**:
1. Calculate 1° tile grid covering region bounds
2. Download missing tiles to `data/raw/{source}/tiles/`
3. Merge tiles into single file: `data/raw/{source}/{merged_filename}.tif`

**Validation** (auto-run): File size, rasterio open, CRS/transform present, sample read. Corrupted files auto-deleted.

---

### 6. Clip to Administrative Boundary (if `clip_boundary=True`)

**Implementation**: `src/pipeline.clip_to_boundary()`

**Decision Rule** (using RegionType enum):

```python
if region_type == RegionType.USA_STATE:
    boundary_name = f"United States of America/{state_name}"
    boundary_type = "state"
elif region_type == RegionType.COUNTRY:
    if config.clip_boundary:  # Usually True
        boundary_name = country_name
        boundary_type = "country"
    else:
        skip_clipping = True
elif region_type == RegionType.REGION:
    if config.clip_boundary:  # Usually False
        boundary_name = region_name
        boundary_type = "country"  # Or custom
    else:
        skip_clipping = True
else:
    raise ValueError(f"Unknown region type: {region_type}")
```

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

### Raw Data (Abstract Bounds-Based Naming)
```
data/raw/{source}/bbox_{bounds}_{dataset}_{res}.tif

Examples:
data/raw/usa_3dep/bbox_N42W114_N45W111_usa_3dep_10m.tif
data/raw/srtm_30m/bbox_N42W114_N45W111_srtm_30m_30m.tif
data/raw/srtm_90m/bbox_N42W114_N45W111_srtm_90m_90m.tif
```

### Tiles (see TILE_SYSTEM.md)
```
data/raw/{source}/tiles/{NS}{lat}_{EW}{lon}_{res}.tif
(1-degree tiles in shared pools - see tech/TILE_SYSTEM.md for details)
```

### Processed & Exported (Region-Specific Names)
```
data/processed/{source}/bbox_{bounds}_processed_{pixels}px_v2.tif
generated/regions/{region_id}_{source}_{pixels}px_v2.json
generated/regions/{region_id}_{source}_{pixels}px_v2.json.gz
```

### Manifest
```
generated/regions/regions_manifest.json
```

---

## Region Type Summary Table

| Type | Enum | Resolution | Sources | Clip | Boundary Format |
|------|------|------------|---------|------|-----------------|
| USA_STATE | `RegionType.USA_STATE` | Dynamic (10/30/90m) | USGS 3DEP + SRTM | Always | `"United States of America/<State>"` |
| COUNTRY | `RegionType.COUNTRY` | Dynamic (30/90m) | SRTM + Copernicus | Usually | `"<CountryName>"` |
| REGION | `RegionType.REGION` | Dynamic (30/90m) | SRTM + Copernicus | Rarely | N/A or custom |

---

## Quick Reference: Decision Flow

```
1. Validate region → src/regions_config.py
2. Determine resolution → Nyquist rule (see TILE_SYSTEM.md)
3. Determine dataset → USA_3DEP/SRTMGL1/SRTMGL3/COP30/COP90
4. Check existing files → data/raw/{source}/
5. Download if needed → 1° tiles (see TILE_SYSTEM.md)
6. Clip to boundary → if USA_STATE/COUNTRY with clip_boundary=True
7. Reproject → EPSG:4326 to EPSG:3857 (fix distortion)
8. Downsample → to target_pixels (preserve aspect)
9. Export JSON → generated/regions/
10. Compress + Update Manifest → .json.gz + manifest
```

---

## Related Documentation

- **Tile System**: `tech/TILE_SYSTEM.md` - Complete tile strategy (CANONICAL for tiles)
- **Data Principles**: `tech/DATA_PRINCIPLES.md` - Aspect ratios, rendering
- **Data Format**: `tech/DATA_FORMAT_EFFICIENCY.md` - JSON format, GZIP compression
- **Implementation**: `src/pipeline.py` - Pipeline code
- **Entry Point**: `ensure_region.py` - CLI
- **Quick Start**: `tech/DOWNLOAD_GUIDE.md` - User guide

---

**Last Updated**: 2025-11-03  
**Status**: Canonical reference - all data processing must follow these stages and rules.

**CRITICAL ENFORCEMENT**:
1. Always use `RegionType` enum - never ad-hoc strings
2. Resolution is ALWAYS dynamic (Nyquist rule) - never hardcoded by region type  
3. Check all three enum cases exhaustively - never silent fallbacks
4. When in doubt, defer to this document as the single source of truth

