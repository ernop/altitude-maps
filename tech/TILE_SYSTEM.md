# Tile System - Complete Strategy

**CANONICAL REFERENCE**: This is the single source of truth for all tile-related decisions.

---

## Overview

All elevation data downloads use a **unified 1-degree tile system**:
- Every download becomes a 1×1 degree tile
- Tiles are stored in shared pools (not per-region)
- Same system for all regions (no special cases)
- Automatic reuse across adjacent regions

---

## 1. Resolution Selection

### Nyquist Sampling Rule

Resolution is determined by the **final visible pixel size**, not by region type or size.

**Formula**: `source_resolution ≤ visible_pixel_size / 2.0`

**Why**: Ensures at least 2× oversampling to avoid aliasing when downsampling.

### Available Resolutions by Source

**US States (via USGS 3DEP or OpenTopography)**:
- 10m, 30m, or 90m (dynamic based on target_pixels)

**International (via OpenTopography)**:
- 30m or 90m (dynamic based on target_pixels)
- Copernicus DEM for latitudes outside SRTM range (>60°N or <-56°S)

### Examples

For Idaho (661km × 714km geographic span):
- `target_pixels=512`: visible=1292m/px → **90m source** (1292/90=14× > 2×)
- `target_pixels=2048`: visible=323m/px → **90m source** (323/90=3.6× > 2×)
- `target_pixels=4096`: visible=162m/px → **30m source** (162/30=5.4× > 2×)
- `target_pixels=8192`: visible=81m/px → **10m source** (81/10=8.1× > 2×)

**Implementation**: `src/downloaders/orchestrator.determine_min_required_resolution()`

---

## 2. Tile Naming Format

### Standard Format

```
{NS}{lat}_{EW}{lon}_{resolution}.tif
```

**Where**:
- `{NS}` = `N` for positive latitude, `S` for negative
- `{EW}` = `E` for positive longitude, `W` for negative
- `{lat}` = Integer latitude of southwest corner (e.g., `40`, `5`)
- `{lon}` = 3-digit integer longitude of southwest corner (e.g., `111`, `005`)
- `{resolution}` = Resolution string (e.g., `30m`, `90m`, `10m`)

### Examples

- `N40_W111_30m.tif` - 40°N, 111°W, 1° × 1°, 30m resolution
- `S05_E120_90m.tif` - 5°S, 120°E, 1° × 1°, 90m resolution
- `N65_W020_10m.tif` - 65°N, 20°W, 1° × 1°, 10m resolution

### Design Rationale

- **Industry standard**: Mirrors SRTM HGT convention (NASA, ESA, USGS)
- **Content-based**: Filename identifies data bounds → automatic reuse
- **Human readable**: Coordinates visible at a glance
- **No dataset in filename**: Directory path provides context

---

## 3. Storage Structure

### Directory Layout

```
data/raw/
  usa_3dep/tiles/      ← 10m USGS tiles
  srtm_30m/tiles/      ← 30m SRTM/Copernicus tiles
  srtm_90m/tiles/      ← 90m SRTM/Copernicus tiles

data/merged/
  usa_3dep/            ← Merged 10m files (region-specific)
  srtm_30m/            ← Merged 30m files (region-specific)
  srtm_90m/            ← Merged 90m files (region-specific)
```

### Key Principles

**Shared tile pools**:
- No per-region subdirectories
- All tiles in flat shared directory
- Adjacent regions automatically share tiles

**Example reuse**:
```
Tennessee needs: N35_W090_30m.tif, N35_W089_30m.tif, N36_W090_30m.tif
Kentucky needs:  N37_W089_30m.tif, N37_W088_30m.tif, N36_W089_30m.tif

Shared: N36_W089_30m.tif (downloaded once, used by both)
```

---

## 4. Download Process

### Unified Workflow (All Regions)

1. **Calculate tiles**: Snap bounds to 1° grid, calculate covering tiles
2. **Group into chunks**: For 90m data, group tiles into 2×2 degree chunks (optimization)
3. **Check cache**: For each tile, check if exists in shared pool
4. **Download missing**: Download chunks and split into tiles
5. **Merge tiles**: Combine tiles into single region file
6. **Process**: Clip, reproject, downsample as usual

### Download Optimization (Chunking)

For **90m data only**, tiles are downloaded in 2×2 degree chunks to reduce API calls:

**Why chunk for 90m?**
- Each 1-degree tile is tiny (~12 MB)
- Downloading 100 tiles = 100 API requests
- Downloading 25 chunks of 2×2 degrees = 25 API requests (4× reduction!)

**Process**:
1. Download 2×2 degree chunk (~48 MB)
2. Split chunk into four 1×1 degree tiles
3. Save tiles to shared pool
4. Clean up temporary chunk file

**Configuration**: `src/download_config.py` defines chunk sizes:
- 10m: 1×1 degree (tiles are large ~300MB, no benefit from chunking)
- 30m: 1×1 degree (tiles are moderate ~50MB, current behavior)
- 90m: 2×2 degree (tiles are tiny ~12MB, 4× reduction in API calls)

**Storage remains unchanged**: All tiles stored as 1×1 degrees for maximum reuse.

### No Special Cases by Region

- **Small regions** (< 1°): Download 1-4 tiles
- **Medium regions** (1-4°): Download 4-16 tiles
- **Large regions** (> 4°): Download 16+ tiles (or 4-16 chunks for 90m)

**Same process for all!** Only the download chunk size varies by resolution.

---

## 5. Grid Alignment

### Snapping Rules

Bounds expanded **outward** to nearest integer degree boundaries:
- West/South: `floor()` (expand left/down)
- East/North: `ceil()` (expand right/up)

**Example**:
- Input: `(-111.622, 40.147, -111.090, 40.702)`
- Snapped: `(-112.0, 40.0, -111.0, 41.0)`
- Tiles: 2 tiles (N40_W112_30m.tif, N40_W111_30m.tif)

### Tile Size Estimates

**10m resolution**:
- Equator: ~190 MB/tile
- 40°N: ~150 MB/tile
- 65°N: ~80 MB/tile

**30m resolution**:
- Equator: ~21 MB/tile
- 40°N: ~16 MB/tile
- 65°N: ~8.7 MB/tile

**90m resolution**:
- Equator: ~2.3 MB/tile
- 40°N: ~1.8 MB/tile
- 65°N: ~1.0 MB/tile

---

## 6. Implementation

### Code Locations

**Core functions** (`src/tile_geometry.py`):
- `calculate_1degree_tiles(bounds)` - Calculate tiles covering region
- `group_tiles_into_chunks(tiles, chunk_degrees)` - Group tiles into download chunks
- `tile_filename_from_bounds(bounds, resolution)` - Generate tile names
- `snap_bounds_to_grid(bounds)` - Expand bounds to grid
- `merged_filename_from_region(region_id, bounds, resolution)` - Merged file names

**Download configuration** (`src/download_config.py`):
- `CHUNK_SIZE_BY_RESOLUTION` - Chunk sizes for each resolution (10m→1, 30m→1, 90m→2)
- `get_chunk_size(resolution_m)` - Get chunk size for a resolution
- Single source of truth for download strategy

**Downloaders** (all use unified tile system):
- `src/downloaders/usgs_3dep_10m.py` - 10m USGS 3DEP tiles
- `src/downloaders/srtm_90m.py` - 90m SRTM/Copernicus (chunks + tiles)
- `src/tile_manager.py` - 30m/90m/10m tile orchestration with chunking

**Orchestration**:
- `src/downloaders/orchestrator.py` - Route downloads to correct source
- `src/pipeline.py` - Merge tiles and process

### Key Rule

**NO non-tile approaches**. Everything uses 1-degree tiles.

**Download optimization**: Only chunk size varies by resolution (storage always 1-degree).

---

## 7. Provider Limits

### OpenTopography

**30m (SRTMGL1, COP30)**:
- Max area: 450,000 km²
- 1° tiles always safe (~123,000 km² at equator)

**90m (SRTMGL3, COP90)**:
- Max area: ~500,000 km²
- 1° tiles always safe

### USGS 3DEP

**10m (USA only)**:
- Max area: ~1,000,000 km² (varies)
- 1° tiles always safe (~94,000 km² at 40°N)
- Large tiles (150+ MB) take longer but work fine

**Conclusion**: 1-degree tiles work with all providers!

---

## 8. Why This System Works

### Benefits

1. **Maximum reuse**: Tennessee + Kentucky share border tiles
2. **Storage efficiency**: No duplicate downloads
3. **Predictable**: Same process for all regions
4. **Scalable**: Works for any region size
5. **Standard**: Follows NASA/ESA/USGS conventions
6. **Simple**: One grid size, one naming scheme
7. **Fast**: Check cache before download

### Trade-offs Accepted

**Small overhead for tiny regions**:
- Region < 1° downloads 1-4 tiles (~16-64 MB)
- Could download exact bbox (~4-16 MB)
- **Decision**: Uniform system worth the extra ~12-48 MB

**Why accepted**:
- Simplifies code (no special cases)
- Enables reuse (tiny regions rare, adjacent regions common)
- Small cost (bandwidth cheap, storage cheap)

---

## 9. Usage Examples

### Download a Region

```python
from src.downloaders.orchestrator import download_elevation_data

# Automatically selects resolution and tiles
success = download_elevation_data(
    region_id='tennessee',
    region_info={'bounds': (-90.3, 34.98, -81.6, 36.68)},
    dataset_override='SRTMGL1',  # or None for auto-select
    target_pixels=2048
)
```

### Calculate Tiles Manually

```python
from src.tile_geometry import calculate_1degree_tiles, tile_filename_from_bounds

bounds = (-111.622, 40.147, -111.090, 40.702)
tiles = calculate_1degree_tiles(bounds)
# Returns: [(-112, 40, -111, 41), (-111, 40, -110, 41)]

for tile_bounds in tiles:
    filename = tile_filename_from_bounds(tile_bounds, '30m')
    print(filename)
    # N40_W112_30m.tif
    # N40_W111_30m.tif
```

---

## Related Documentation

- **`DATA_PIPELINE.md`** - Complete pipeline (references this doc for tile details)
- **`DOWNLOAD_GUIDE.md`** - User guide for downloads
- **`src/tile_geometry.py`** - Implementation code

**Rule**: When tile documentation conflicts, this document wins.

