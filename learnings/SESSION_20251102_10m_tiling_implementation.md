# Session 2025-11-02: 10m Data Unified Tiling Implementation

## Problem Statement

User discovered that **10m USGS 3DEP data was NOT using the unified tiling system** that 30m and 90m data use. This violated the documented architecture and prevented:
- Tile reuse across regions
- Consistent folder structure
- Grid snapping behavior
- Proper handling of large regions

## Root Cause

The orchestrator was routing 10m downloads directly to `data/merged/usa_3dep/` without tiling, instead of using the documented 1-degree tile system in `data/raw/usa_3dep/tiles/`.

## Solution Implemented

### 1. Created Dedicated 10m Tile Downloader

**New file**: `src/downloaders/usgs_3dep_10m.py`

Features:
- `download_single_tile_10m()` - Downloads single 1-degree tile
- `download_usgs_3dep_10m_tiles()` - Main entry point, downloads and merges tiles
- `download_usgs_3dep_10m_single()` - Deprecated compatibility function

Architecture matches `src/downloaders/srtm_90m.py` exactly.

### 2. Updated Orchestrator

**File**: `src/downloaders/orchestrator.py`

Changes:
- Removed inline 10m download code (lines 143-161)
- Added import and routing to tile-based system
- Now follows same pattern as 30m/90m (checks `width > 4.0` for tiling messages)
- All regions use tiling for consistency and reuse

### 3. Comprehensive Tests

**New file**: `tests/test_usgs_3dep_10m_tiling.py`

Test coverage:
- Tile calculation for small/large regions
- Naming convention compliance
- Storage location verification
- Tile reuse across adjacent regions
- Consistency with 30m/90m systems
- Documentation compliance
- Integration tests

### 4. Documentation Updates

**File**: `tech/GRID_ALIGNMENT_STRATEGY.md`

Added:
- 10m tile size estimates (150-190 MB per tile at various latitudes)
- Relationship between resolutions (9x size increase: 90m → 30m → 10m)
- USGS API limitations and behavior

## Key Architectural Principles Enforced

### 1. Unified 1-Degree Grid System

**ALL resolutions** (10m, 30m, 90m) now use:
- 1.0-degree tiles (integer degree boundaries)
- Southwest corner snapping
- Shared tile pool directories
- Standard naming: `{NS}{lat}_{EW}{lon}_{resolution}.tif`

### 2. No Special Cases

- Small regions (< 4 degrees): Use tiling
- Large regions (> 4 degrees): Use tiling
- **Same process for all sizes** - enables tile reuse

### 3. Content-Based Naming

Tiles are named by their geographic coordinates, not region names:
- `N40_W111_10m.tif` (not `ohio_tile_00.tif`)
- Adjacent regions automatically share border tiles
- No duplicate downloads

### 4. Folder Structure

```
data/raw/usa_3dep/tiles/     ← Shared 10m tile pool
data/raw/srtm_30m/tiles/     ← Shared 30m tile pool  
data/raw/srtm_90m/tiles/     ← Shared 90m tile pool
data/merged/{source}/        ← Merged outputs per region
```

## Tile Size Comparison

| Resolution | Equator | 40°N | 65°N | Ratio |
|------------|---------|------|------|-------|
| 10m        | ~190 MB | ~150 MB | ~80 MB | 1x |
| 30m        | ~21 MB  | ~16 MB  | ~8.7 MB | 9x smaller |
| 90m        | ~2.3 MB | ~1.8 MB | ~1.0 MB | 81x smaller |

**Why this matters**:
- 10m tiles are large (150 MB) but manageable
- Download time is longer but API handles it well
- Tile reuse saves significant bandwidth for adjacent regions

## Before vs After

### Before (Broken)

```python
# Direct download to merged directory (NO TILING)
downloader = USGSElevationDownloader(data_dir=str(output_path.parent))
result = downloader.download_via_national_map_api(
    bbox=bounds,
    output_file=output_path.name
)
# Output: data/merged/usa_3dep/region_name_10m.tif
```

Problems:
- No tile reuse across regions
- Large regions could fail
- Non-standard directory structure
- No grid snapping

### After (Fixed)

```python
# Tile-based download (UNIFIED SYSTEM)
from src.downloaders.usgs_3dep_10m import download_usgs_3dep_10m_tiles

download_usgs_3dep_10m_tiles(region_id, bounds, output_path)

# Process:
# 1. Calculate 1-degree tiles needed
# 2. Download missing tiles to data/raw/usa_3dep/tiles/
# 3. Reuse existing tiles (N40_W111_10m.tif, etc.)
# 4. Merge tiles to data/merged/usa_3dep/region_name_10m.tif
```

Benefits:
- Tile reuse across all regions
- Handles any region size
- Standard architecture
- Grid-aligned

## Testing

Run tests with:
```bash
pytest tests/test_usgs_3dep_10m_tiling.py -v
```

Test coverage:
- 20+ test cases
- Tile calculation logic
- Naming convention compliance
- Integration with 30m/90m systems
- Documentation compliance

## Verification Checklist

- [x] 10m uses `calculate_1degree_tiles()` (same as 30m/90m)
- [x] 10m uses `tile_filename_from_bounds()` (same as 30m/90m)
- [x] Tiles stored in `data/raw/usa_3dep/tiles/` (parallel to 30m/90m)
- [x] Naming: `N40_W111_10m.tif` format (consistent)
- [x] Merged files: `data/merged/usa_3dep/` (consistent)
- [x] Large regions (>4 deg): Use tiling
- [x] Small regions (<4 deg): Use tiling (for consistency)
- [x] Tile reuse across adjacent regions
- [x] Grid snapping to integer degrees
- [x] Documentation updated
- [x] Tests written and passing

## Files Modified

1. **Created**: `src/downloaders/usgs_3dep_10m.py` (186 lines)
2. **Created**: `tests/test_usgs_3dep_10m_tiling.py` (273 lines)
3. **Modified**: `src/downloaders/orchestrator.py` (replaced inline code with tiling system)
4. **Modified**: `tech/GRID_ALIGNMENT_STRATEGY.md` (added 10m estimates)
5. **Created**: `learnings/SESSION_20251102_10m_tiling_implementation.md` (this file)

## Impact

**Positive**:
- 10m data now follows unified architecture
- Tile reuse saves bandwidth for adjacent US states
- Consistent codebase (no special cases)
- Easier to maintain and debug

**Neutral**:
- Slightly more complex for first-time download (tile overhead)
- Larger cache directory over time (but tiles are reused)

**Breaking Changes**:
- None (backwards compatible - still outputs to same locations)

## Next Steps

1. **Test with real regions**: Download a US state with 10m data
2. **Verify tile reuse**: Download adjacent states (Tennessee + Kentucky)
3. **Performance check**: Monitor large 10m downloads (California, Texas)
4. **Cache validation**: Run `validate_all_tiles.py` on 10m tiles

## Related Documentation

- `tech/GRID_ALIGNMENT_STRATEGY.md` - Unified grid system design
- `tech/DATA_PIPELINE.md` - Complete pipeline documentation
- `learnings/TILE_NAMING_DESIGN.md` - Why we use content-based naming
- `learnings/SESSION_20251101_srtm_90m_downloader.md` - Similar work for 90m data

## Lessons Learned

1. **Documentation is not enough** - Code must match documented architecture
2. **Consistency matters** - All resolutions should follow same patterns
3. **Test coverage prevents regressions** - Comprehensive tests catch issues early
4. **Fresh eyes catch bugs** - User's question revealed inconsistency immediately
5. **Incremental implementation creates gaps** - 10m was added without full tiling support

## User Question That Triggered This

> "the 10m data system should obviously use the exact same tiling scheme, folder structure (with its own individual nature ofc), etc all the way through, just like any other resolution, just like 30m and 90m. Does it?"

**Answer**: No, it didn't. But it does now! ✓

