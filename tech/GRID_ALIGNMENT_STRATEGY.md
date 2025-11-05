# Grid Alignment Strategy - Unified 1-Degree System

**Status**: Implemented (January 2025)  
**Grid Size**: **1.0 degrees** (integer degrees only)

---

## Core Decision: Unified 1-Degree Grid

**We use a unified 1-degree grid system for ALL raw elevation data downloads.**

### Why 1-Degree?

1. **Maximum Reuse**: Every download becomes a 1-degree tile that can be shared across regions
2. **No Special Cases**: No distinction between "bbox downloads" and "tiling" - everything is just tiles
3. **Provider Compatibility**: 1-degree tiles are always safe (well under 450,000 km² limit)
4. **Human Readable**: Integer degrees in filenames are clear and match SRTM convention
5. **Efficient Coverage**: Simple grid makes coverage management trivial

### Trade-offs

**Pros:**
- Maximum reuse across regions
- Unified system (simpler code)
- Consistent naming and organization
- Well-understood grid system

**Cons:**
- Small regions download more data than needed (~16 MB for 1-degree tile vs ~4 MB for 0.5-degree)
- Slight storage overhead for regions much smaller than 1-degree

**Decision**: The benefits of maximum reuse and unified system outweigh the cost of slightly larger downloads for small regions.

---

## Grid Specifications

### Grid Alignment

- **Grid size**: 1.0 degrees (integer degrees only)
- **Alignment**: Southwest corner snapped to integer degree boundaries
- **Expansion**: Bounds expanded outward to nearest grid boundaries (west/south floor down, east/north ceil up)

**Example:**
- Original region bounds: `(-111.622, 40.1467, -111.0902, 40.7020)`
- Grid-aligned bounds: `(-112.0, 40.0, -111.0, 41.0)` (expanded to 1-degree grid)

### Tile Naming

**Format:** `{NS}{lat}_{EW}{lon}_{resolution}.tif`

**Where:**
- `{NS}` = `N` for positive latitude, `S` for negative
- `{EW}` = `E` for positive longitude, `W` for negative
- `{lat}` = Integer latitude of southwest corner (no padding, e.g., `40`, `5`)
- `{lon}` = 3-digit integer longitude of southwest corner (000-180, e.g., `111`, `005`)
- `{resolution}` = Resolution string (e.g., `30m`, `90m`, `10m`)

**Examples:**
- `N40_W111_30m.tif` (40degN, 111degW, 1deg x 1deg, 30m resolution)
- `N41_W110_30m.tif` (41degN, 110degW, 1deg x 1deg, 30m resolution)
- `S50_W061_30m.tif` (50degS, 61degW, 1deg x 1deg, 30m resolution)
- `N5_E120_90m.tif` (5degN, 120degE, 1deg x 1deg, 90m resolution)

**Always represents:** 1.0 degree x 1.0 degree tile from southwest corner

### Tile Size Estimates

**At various latitudes (10m resolution):**
- Equator: ~190 MB per tile
- 40degN: ~150 MB per tile
- 65degN: ~80 MB per tile

**At various latitudes (30m resolution):**
- Equator: ~21 MB per tile
- 40degN: ~16 MB per tile
- 65degN: ~8.7 MB per tile

**At various latitudes (90m resolution):**
- Equator: ~2.3 MB per tile
- 40degN: ~1.8 MB per tile
- 65degN: ~1.0 MB per tile

**Note**: 10m tiles are ~9x larger than 30m tiles (3^2 = 9x more pixels at same area).
30m tiles are ~9x larger than 90m tiles. Compression ratios vary with terrain complexity.

---

## File Storage

### Shared Tile Pool

**All tiles stored in shared pool directories:**
- `data/raw/srtm_30m/tiles/` - 30m SRTM tiles
- `data/raw/srtm_90m/tiles/` - 90m SRTM tiles
- `data/raw/cop30/tiles/` - Copernicus DEM 30m tiles
- `data/raw/usa_3dep/tiles/` - USGS 3DEP 10m tiles

**Key principle:** No per-region subdirectories. All tiles in shared pool for maximum reuse.

### Metadata

**Note:** JSON metadata files are not used for tile validation or reuse. Tiles are validated directly via rasterio when needed.

---

## Download Process

### For Any Region

1. **Calculate required tiles**: Determine which 1-degree tiles cover the region bounds
2. **Check existing tiles**: For each required tile, check if it exists in shared pool
3. **Download missing tiles**: Download only tiles that don't exist
4. **Merge tiles**: Merge all required tiles into single file for processing
5. **Process normally**: Clip, reproject, downsample as usual

### No Special Cases

- **Small regions** (< 1 degree): Download 1-4 tiles, merge
- **Medium regions** (1-4 degrees): Download 4-16 tiles, merge
- **Large regions** (> 4 degrees): Download 16+ tiles, merge

**Same process for all!** No distinction between "single bbox download" and "tiled download".

---

## Splitting Strategy

### When Splitting Existing Large Files

**Rules:**
1. **Split into 1-degree tiles** aligned to integer grid
2. **Discard edge pieces** that are too small (< 0.5 degrees)
   - Prevents storage of tiny fragments
   - Keeps grid clean and consistent
3. **Save to shared tile pool** with standard naming
4. **Skip tiles that already exist** (don't overwrite)

**Example:**
- Large file: `bbox_N37_W114_N43_W109_srtm_30m_30m.tif` (5deg x 6deg)
- Split into: 30 tiles (5 x 6 grid of 1-degree tiles)
- Edge piece (e.g., 0.3deg strip): **Discarded** (too small)
- Saved: `tile_N37_W114`, `tile_N37_W113`, ..., `tile_N42_W109`

---

## Provider Limitations

### OpenTopography (SRTMGL1, COP30 - 30m)
- **Maximum area**: 450,000 km²
- **Maximum dimension**: ~4.0 degrees
- **1-degree tiles**: Always safe (max ~123,000 km² at equator)

### OpenTopography (SRTMGL3, COP90 - 90m)
- **Maximum area**: ~500,000 km²
- **Maximum dimension**: ~4.5 degrees
- **1-degree tiles**: Always safe

### USGS 3DEP (10m, USA only)
- **Maximum area**: ~1,000,000 km² (varies by region)
- **Maximum dimension**: ~5-10 degrees (API dependent)
- **1-degree tiles**: Always safe (~123,000 km² at equator, ~94,000 km² at 40°N)
- **Note**: Large tiles (150+ MB) take longer to download but API handles them well

**Conclusion**: 1-degree tiles work with all providers!

---

## Implementation Notes

### Grid Snapping Function

```python
def snap_bounds_to_grid(bounds: Tuple[float, float, float, float], 
                        grid_size: float = 1.0) -> Tuple[float, float, float, float]:
    """
    Snap bounding box to 1-degree grid boundaries.
    Expands bounds outward to nearest grid boundaries.
    """
    west, south, east, north = bounds
    snapped_west = math.floor(west / grid_size) * grid_size
    snapped_south = math.floor(south / grid_size) * grid_size
    snapped_east = math.ceil(east / grid_size) * grid_size
    snapped_north = math.ceil(north / grid_size) * grid_size
    return (snapped_west, snapped_south, snapped_east, snapped_north)
```

### Tile Calculation

```python
def calculate_tiles_for_bounds(bounds: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
    """
    Calculate list of 1-degree tiles needed to cover bounds.
    """
    # Snap bounds to 1-degree grid
    grid_bounds = snap_bounds_to_grid(bounds, grid_size=1.0)
    west, south, east, north = grid_bounds
    
    tiles = []
    for lat in range(int(south), int(north)):
        for lon in range(int(west), int(east)):
            tile_bounds = (lon, lat, lon + 1.0, lat + 1.0)
            tiles.append(tile_bounds)
    
    return tiles
```

---

## Migration Notes

**Before (old system):**
- Bbox files: 0.5-degree grid (e.g., `bbox_W111_5_S40_0_E111_0_N41_0_*.tif`)
- Tiles: 1-degree grid (e.g., `tile_N40_W111_*.tif`)
- Different handling for small vs large regions

**After (unified system):**
- All tiles: 1-degree grid (e.g., `tile_N40_W111_*.tif`)
- Same handling for all regions
- No bbox files - everything is tiles

---

## References

- **DATA_DIRECTORIES.md** - File organization and naming
- **EXISTING_FILES_ANALYSIS.md** - Splitting strategy for existing files
- **TECHNICAL_REFERENCE.md** - Complete technical specs

