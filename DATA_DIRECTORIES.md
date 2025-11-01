# Data Storage Directories - Complete Reference

Complete list of all directories where geo data is stored (raw from upstream or processed for our use).

## Pipeline Stages (1-10)

The pipeline has 10 stages:
1. Validate Region Definition
2. Determine Dataset & Resolution (overrides first)
3. Dataset Selection by Latitude (if no override)
4. Acquire Raw Elevation (download)
5. Automatic Tiling for Large Areas (if needed)
6. Clip to Administrative Boundary
7. Reproject to Metric CRS
8. Downsample/Process for Viewer
9. Export to JSON + Gzip Compression
10. Update Regions Manifest

---

## `data/` Directory Structure

### 1. `data/raw/srtm_30m/tiles/` (shared tile pool - UNIFIED 1-DEGREE GRID SYSTEM)
- **Type**: Unified 1-degree tile files stored in **shared pool** for reuse across regions
- **Contents**: Individual 1-degree tile GeoTIFF files with **grid-aligned bounds**, stored in shared directory (NOT per-region subdirectories)
- **Filename Pattern**: `{NS}{lat}_{EW}{lon}_{resolution}.tif`
  - Format: `{NS}{lat}_{EW}{lon}_{resolution}.tif`
  - Example: `N40_W111_30m.tif` (40degN, 111degW, 1deg x 1deg tile, 30m resolution)
  - Uses southwest corner coordinates from **integer-degree grid** (1.0-degree grid)
  - All tiles are **1-degree x 1-degree** - unified grid system
  - `NS` = `N` for positive latitude, `S` for negative
  - `EW` = `E` for positive longitude, `W` for negative
  - `lat` = Integer latitude (no padding, e.g., `40`, `5`)
  - `lon` = 3-digit integer longitude (e.g., `111`, `005`) - southwest corner
- **Pipeline Stage**: Stage 4 (Acquire Raw Elevation) - **ALL downloads become 1-degree tiles**
- **Grid Alignment**: Uses **unified 1.0-degree grid** (integer degrees) - all downloads use this system
- **Storage**: Stored in **shared pool** (`data/raw/srtm_30m/tiles/` or `data/raw/srtm_90m/tiles/`) - **NOT** in per-region subdirectories
- **Metadata**: JSON metadata files are not used - tiles are validated directly via rasterio when needed
- **Purpose**: Enables content-based tile reuse across regions sharing same 1-degree tiles
- **Reuse**: Multiple regions downloading overlapping tiles share the same cached tile file - no redundant downloads!
- **Unified System**: No distinction between "bbox downloads" and "tiling" - everything is 1-degree tiles that are merged as needed
- **Outdated Forms**: 
  - `bbox_W{west}_S{south}_E{east}_N{north}_*.tif` files in `data/raw/srtm_30m/` (migrated to unified 1-degree tiles)
  - `{region_id}_bbox_30m.tif` (migrated to unified 1-degree tiles)
  - Precise bounds with fractional degrees (migrated to unified 1-degree grid)
  - Per-region tile subdirectories (migrated to shared tile pool)

### 5. `data/raw/srtm_30m/subparts/`
- **Type**: Intermediate subpart files for regions that span latitude boundaries (e.g., crossing 60degN/S)
- **Contents**: Individual subpart GeoTIFF files before merging
- **Filename Pattern**: `{region_id}/part_<index>_<dataset>.tif` (temporary, gets merged)
  - Example: `iceland/part_0_COP30.tif`, `iceland/part_1_SRTMGL1.tif`
- **Pipeline Stage**: Stage 4 (Intermediate files during download for cross-boundary regions)
- **Note**: Temporary files that are merged and deleted after download completes

### 6. `data/raw/srtm_90m/`
- **Type**: Downloaded bounding box elevation files from OpenTopography SRTM (90m resolution)
- **Contents**: GeoTIFF files containing elevation data for rectangular bounding boxes (lower resolution fallback), **grid-aligned bounds for reuse**
- **Filename Pattern**: `bbox_W<west>_S<south>_E<east>_N<north>_srtm_90m_90m.tif`
  - Format: `bbox_W{west}_S{south}_E{east}_N{north}_srtm_90m_90m.tif`
  - Example (with 0.5-degree grid): `bbox_W111_5_S40_0_E111_0_N41_0_srtm_90m_90m.tif`
  - Bounds are **snapped to 0.5-degree grid** before download (same as 30m)
- **Pipeline Stage**: Stage 4 (Acquire Raw Elevation)
- **Grid Alignment**: Uses **0.5-degree grid** (half-degree increments)
- **Metadata**: Same directory, `.json` extension
- **Subdirectories**: `tiles/` (shared tile pool, same grid alignment pattern as srtm_30m/tiles/)

### 7. `data/raw/usa_3dep/`
- **Type**: Downloaded bounding box elevation files from USGS 3DEP (10m resolution, US states only)
- **Contents**: GeoTIFF files containing elevation data for rectangular bounding boxes, **grid-aligned bounds for reuse**
- **Filename Pattern**: `bbox_W<west>_S<south>_E<east>_N<north>_usa_3dep_10m.tif`
  - Format: `bbox_W{west}_S{south}_E{east}_N{north}_usa_3dep_10m.tif`
  - Example (with 0.5-degree grid): `bbox_W111_5_S40_0_E111_0_N41_0_usa_3dep_10m.tif`
  - Bounds are **snapped to 0.5-degree grid** before download (same as SRTM)
- **Pipeline Stage**: Stage 4 (Acquire Raw Elevation)
- **Grid Alignment**: Uses **0.5-degree grid** (half-degree increments)
- **Metadata**: Same directory, `.json` extension
- **Reuse**: Multiple regions with overlapping bounds share the same grid-aligned bbox file
- **Outdated Forms**: 
  - `{region_id}_3dep_10m.tif` (migrated to abstract bounds-based naming)
  - Precise bounds with 4+ decimal places (migrated to grid-aligned bounds)

### 8. `data/clipped/{source}/`
- **Type**: Elevation data clipped to administrative boundaries (states/countries)
- **Contents**: GeoTIFF files cropped to actual boundary shapes (not rectangular bounding boxes), preserving real-world aspect ratios
- **Filename Pattern**: `<base_part>_clipped_<hash>_v1.tif`
  - Format: `{base_part}_clipped_{hash}_v1.tif`
  - Example: `W111_6220_S40_1467_E111_0902_N40_7020_srtm_30m_30m_clipped_147070_v1.tif`
  - `{base_part}` is extracted from bounds-based raw filename (without `bbox_` prefix and `.tif` suffix)
  - `{hash}` is 6-digit hash of boundary name (e.g., "United States of America/Tennessee")
- **Pipeline Stage**: Stage 6 (Clip to Administrative Boundary)
- **Metadata**: Same directory, `.json` extension
- **Subdirectories**: `srtm_30m/`, `srtm_90m/`, `usa_3dep/`
- **Outdated Forms**: 
  - `{region_id}_clipped_{source}_v1.tif` (migrated to abstract bounds-based naming)

### 9. `data/processed/{source}/`
- **Type**: Reprojected and downsampled elevation data ready for viewer
- **Contents**: GeoTIFF files in metric CRS (EPSG:3857 or polar projections), downsampled to target pixel resolution
- **Filename Pattern**: `<base_part>_processed_<target_pixels>px_v2.tif`
  - Format: `{base_part}_processed_{target_pixels}px_v2.tif`
  - Example: `W111_6220_S40_1467_E111_0902_N40_7020_srtm_30m_30m_processed_2048px_v2.tif`
  - `{target_pixels}` is the target resolution (e.g., `2048`, `4096`, `800`)
- **Pipeline Stages**: 
  - Stage 7 (Reproject to Metric CRS)
  - Stage 8 (Downsample/Process for Viewer)
- **Metadata**: Same directory, `.json` extension
- **Subdirectories**: `srtm_30m/`, `srtm_90m/`, `usa_3dep/`
- **Intermediate Files** (temporary, may exist during processing):
  - `{base_part}_reproj.tif` - Intermediate reprojected file
  - `{base_part}_reproj_reproj.tif` - Double-reprojected intermediate (should be cleaned up)
- **Outdated Forms**: 
  - `{region_id}_{source}_{target_pixels}px_v2.tif` (migrated to abstract bounds-based naming)

### 10. `data/.cache/borders/`
- **Type**: Cached Natural Earth border geometry files (pickled GeoDataFrames)
- **Contents**: Pickle files containing GeoDataFrame objects with country/state border geometries
- **Filename Pattern**: `ne_<resolution>_countries.pkl` or `ne_<resolution>_admin_1.pkl`
  - Format: `ne_{resolution}_countries.pkl` (for country borders)
  - Format: `ne_{resolution}_admin_1.pkl` (for state/province borders, if implemented)
  - Example: `ne_10m_countries.pkl`, `ne_50m_countries.pkl`, `ne_110m_countries.pkl`
  - `{resolution}` is `10m`, `50m`, or `110m` (Natural Earth resolution)
- **Pipeline Stage**: Used by Stage 6 (Clip to Administrative Boundary) for border geometry lookup
- **Purpose**: Cache downloaded Natural Earth border data to avoid re-downloading on every use
- **Source**: Downloaded from Natural Earth CDN, then cached locally

---

## `generated/` Directory Structure

### 11. `generated/regions/`
- **Type**: Exported JSON files for web viewer (final output)
- **Contents**: JSON files containing elevation data formatted for Three.js viewer, plus compressed versions and metadata
- **Main Data Files**:
  - **Filename Pattern**: `<region_id>_<source>_<target_pixels>px_v2.json`
    - Format: `{region_id}_{source}_{target_pixels}px_v2.json`
    - Example: `cottonwood_valley_usa_3dep_2048px_v2.json`
    - Uses `region_id` (NOT bounds-based naming) because these are viewer-specific exports already clipped to specific boundaries
  - **Pipeline Stage**: Stage 9 (Export to JSON for web viewer)
- **Compressed Versions**:
  - **Filename Pattern**: `<region_id>_<source>_<target_pixels>px_v2.json.gz`
    - Format: `{region_id}_{source}_{target_pixels}px_v2.json.gz`
    - Example: `cottonwood_valley_usa_3dep_2048px_v2.json.gz`
    - Pipeline Stage: Stage 9 (Gzip compression, part of export stage)
- **Border Files** (optional, if borders are exported):
  - **Filename Pattern**: `<region_id>_<source>_<target_pixels>px_v2_borders.json`
    - Format: `{region_id}_{source}_{target_pixels}px_v2_borders.json`
    - Contains border line segments for rendering in viewer
- **Metadata Files**:
  - **Filename Pattern**: `<region_id>_<source>_<target_pixels>px_v2_meta.json`
    - Format: `{region_id}_{source}_{target_pixels}px_v2_meta.json`
    - Contains processing metadata (source file hash, version, etc.)
- **Manifest File**:
  - **Filename**: `regions_manifest.json`
  - **Filename (compressed)**: `regions_manifest.json.gz`
  - Contains index of all available regions mapping `region_id` to filename
  - Pipeline Stage: Stage 10 (Update Regions Manifest)
- **Outdated Forms**: 
  - `{region_id}_{source}_{target_pixels}px_v2.json` without version suffix (legacy, should be removed)
  - Abstract bounds-based JSON filenames (never used - exported JSON always uses region_id)

---

## Summary Table

| Directory | Type | Filename Pattern | Grid Alignment | Pipeline Stage(s) |
|-----------|------|------------------|----------------|-------------------|
| `data/raw/srtm_30m/` | Downloaded bbox elevation (30m) | `bbox_W<west>_S<south>_E<east>_N<north>_srtm_30m_30m.tif` | 0.5° grid | Stage 4 |
| `data/raw/srtm_30m/tiles/` | Shared tile pool (30m) | `tile_<NS><lat:02d>_<EW><lon:03d>_srtm_30m_30m.tif` | 1.0° grid | Stage 5 |
| `data/raw/srtm_30m/subparts/` | Intermediate subparts | `{region_id}/part_<index>_<dataset>.tif` | N/A | Stage 4 |
| `data/raw/srtm_90m/` | Downloaded bbox elevation (90m) | `bbox_W<west>_S<south>_E<east>_N<north>_srtm_90m_90m.tif` | 0.5° grid | Stage 4 |
| `data/raw/srtm_90m/tiles/` | Shared tile pool (90m) | `tile_<NS><lat:02d>_<EW><lon:03d>_srtm_90m_90m.tif` | 1.0° grid | Stage 5 |
| `data/raw/usa_3dep/` | Downloaded bbox elevation (10m) | `bbox_W<west>_S<south>_E<east>_N<north>_usa_3dep_10m.tif` | 0.5° grid | Stage 4 |
| `data/clipped/{source}/` | Clipped to boundaries | `<base_part>_clipped_<hash>_v1.tif` | N/A | Stage 6 |
| `data/processed/{source}/` | Reprojected & downsampled | `<base_part>_processed_<target_pixels>px_v2.tif` | N/A | Stages 7-8 |
| `data/.cache/borders/` | Cached border geometries | `ne_<resolution>_countries.pkl` | N/A | Used by Stage 6 |
| `generated/regions/` | Viewer JSON exports | `<region_id>_<source>_<target_pixels>px_v2.json` | N/A | Stage 9 |
| `generated/regions/` | Compressed exports | `<region_id>_<source>_<target_pixels>px_v2.json.gz` | N/A | Stage 9 |
| `generated/regions/` | Manifest index | `regions_manifest.json` (+ `.gz`) | N/A | Stage 10 |

---

## Naming Convention Principles

### Grid-Aligned Bounds-Based Naming (for reusable data)
- **Used for**: Raw downloads (bbox files and tiles), clipped files, processed files
- **Format**: Grid-aligned bounds-based naming (e.g., `bbox_W{west}_S{south}_E{east}_N{north}`)
- **Grid Sizes**:
  - **Bbox files**: 0.5-degree grid (half-degree increments)
  - **Tiles**: 1.0-degree grid (integer-degree increments)
- **Why**: Grid alignment enables content-based reuse - multiple regions with overlapping bounds share the same cached files
- **How**: Bounds are expanded outward to nearest grid boundaries before download (west/south floor down, east/north ceil up)
- **Examples** (with grid alignment):
  - Raw bbox: `bbox_W111_5_S40_0_E111_0_N41_0_srtm_30m_30m.tif` (snapped to 0.5° grid)
  - Tile: `tile_N40_W111_srtm_30m_30m.tif` (snapped to 1.0° grid, integer degrees)
  - Clipped: `W111_5_S40_0_E111_0_N41_0_srtm_30m_30m_clipped_147070_v1.tif` (uses base from grid-aligned bbox)
  - Processed: `W111_5_S40_0_E111_0_N41_0_srtm_30m_30m_processed_2048px_v2.tif` (uses base from grid-aligned bbox)

### Region ID-Based Naming (for viewer exports)
- **Used for**: Exported JSON files for web viewer
- **Format**: `{region_id}_{source}_{target_pixels}px_v2.json`
- **Why**: These are viewer-specific exports already clipped to specific boundaries and filtered for a particular viewer use case
- **Examples**: 
  - `cottonwood_valley_usa_3dep_2048px_v2.json`
  - `tennessee_srtm_30m_4096px_v2.json`

---

## Unified 1-Degree Grid System

**All raw elevation data downloads use a unified 1-degree grid system.**

### Why 1-Degree?

- **Maximum Reuse**: Every download becomes a 1-degree tile that can be shared across regions
- **No Special Cases**: No distinction between "bbox downloads" and "tiling" - everything is just tiles
- **Provider Compatibility**: 1-degree tiles are always safe (well under 450,000 km² limit)
- **Human Readable**: Integer degrees in filenames are clear and match SRTM convention
- **Efficient Coverage**: Simple grid makes coverage management trivial

### Implementation

- **Grid size**: 1.0 degrees (integer degrees only)
- **Alignment**: Southwest corner snapped to integer degree boundaries
- **Expansion**: Bounds expanded outward to nearest grid boundaries (west/south floor down, east/north ceil up)
- **Storage**: All tiles stored in shared pool directories (not per-region subdirectories)
- **Naming**: Standard format `tile_{NS}{lat:02d}_{EW}{lon:03d}_{dataset}_{resolution}.tif`

See `tech/GRID_ALIGNMENT_STRATEGY.md` for complete documentation.

---

## Grid Alignment Details (LEGACY - for reference)

### Why Grid Alignment?
Grid alignment solves the problem of redundant downloads when region bounds change slightly:
- **Before**: Each region with slightly different bounds would download its own precise bbox/tile
- **After**: Regions with overlapping bounds share the same grid-aligned files

### Grid Size Selection
- **Bbox files (0.5° grid)**: Balance between reuse and precision - small enough for most regions, large enough for significant reuse
- **Tiles (1.0° grid)**: Coarser grid aligns with SRTM naming convention and ensures maximum tile reuse

### How It Works
1. Original region bounds are expanded outward to nearest grid boundaries
2. Download uses grid-aligned bounds (ensures coverage)
3. Filename uses grid-aligned bounds (enables reuse)
4. Multiple regions with overlapping bounds share the same cached file
5. Clipping/processing steps handle the actual region boundaries from the larger grid-aligned file

### Example: Region Border Change
- **Original region bounds**: `(-111.622, 40.1467, -111.0902, 40.7020)`
- **Grid-aligned bounds (0.5° grid)**: `(-111.5, 40.0, -111.0, 41.0)`
- **Another region with slightly different bounds**: `(-111.58, 40.15, -111.05, 40.70)`
- **Grid-aligned bounds**: `(-111.5, 40.0, -111.0, 41.0)` **SAME FILE!**
- Result: Both regions reuse the same bbox file, no redundant download!

---

## Outdated Forms (Historical Reference)

These naming patterns were used in the past but have been migrated to grid-aligned bounds-based naming:

1. **Raw files**: 
   - Old: `{region_id}_bbox_30m.tif`, `{region_id}_3dep_10m.tif`, `{region_id}_bbox_90m.tif`
   - Old: `bbox_W111_6220_S40_1467_E111_0902_N40_7020_srtm_30m_30m.tif` (precise bounds, 4+ decimal places)
   - New: `bbox_W111_5_S40_0_E111_0_N41_0_srtm_30m_30m.tif` (grid-aligned, 0.5° grid)

2. **Tiles**:
   - Old: Per-region tile subdirectories (e.g., `data/raw/srtm_30m/tiles/{region_id}/tile_*.tif`)
   - Old: Precise tile bounds not aligned to grid
   - New: Shared tile pool with grid-aligned bounds (e.g., `data/raw/srtm_30m/tiles/tile_N40_W111_*.tif`)

3. **Clipped files**: 
   - Old: `{region_id}_clipped_{source}_v1.tif`
   - New: `{base_part}_clipped_{hash}_v1.tif` (uses base from grid-aligned bbox)

4. **Processed files**: 
   - Old: `{region_id}_{source}_{target_pixels}px_v2.tif`
   - New: `{base_part}_processed_{target_pixels}px_v2.tif` (uses base from grid-aligned bbox)

5. **Exported JSON** (note: these still use region_id, but old versions may lack `_px_v2` suffix):
   - Old: `{region_id}.json` (no version suffix)
   - New: `{region_id}_{source}_{target_pixels}px_v2.json`

6. **Intermediate reprojection files**: 
   - `*_reproj.tif`, `*_reproj_reproj.tif` (should be cleaned up, temporary intermediates)

Migration was completed via `legacy/migrate_to_abstract_naming.py` (now preserved for reference).

---

## Metadata Files

All data files have corresponding metadata JSON files stored in the **same directory** as the data file:

- **For `.tif` files**: Same filename with `.json` extension
  - Example: `bbox_W111_6220_S40_1467_E111_0902_N40_7020_srtm_30m_30m.tif` → `bbox_W111_6220_S40_1467_E111_0902_N40_7020_srtm_30m_30m.json`

- **For `.json` data files**: Same filename with `_meta.json` suffix
  - Example: `cottonwood_valley_usa_3dep_2048px_v2.json` → `cottonwood_valley_usa_3dep_2048px_v2_meta.json`

Metadata contains: source file hash, processing version, bounds, CRS, resolution, timestamps, etc.
