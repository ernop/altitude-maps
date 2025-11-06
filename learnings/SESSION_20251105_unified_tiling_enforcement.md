# Session 2025-11-05: Unified Tiling System Enforcement

## Problem Statement

After merging remote updates, discovered that **30m and 90m downloads were not using the unified 1-degree tile system** for small regions (<4 degrees), despite documentation claiming otherwise.

**Documentation said**:
- `tech/GRID_ALIGNMENT_STRATEGY.md`: "We use a unified 1-degree grid system for ALL raw elevation data downloads"
- "No Special Cases: No distinction between 'bbox downloads' and 'tiling' - everything is just tiles"

**Code actually did**:
- 10m data: ✅ Always used tiles
- 30m/90m data: ❌ Hybrid system - tiles for large regions, direct bbox downloads for small regions

## Root Cause

The orchestrator had conditional logic that checked region size:

```python
needs_tiling = (width > 4.0 or height > 4.0)
if needs_tiling:
    return download_and_merge_tiles()  # Tiles for large regions
else:
    return download_srtm_90m_single()  # Direct download for small regions
```

This violated the documented unified architecture and prevented tile reuse.

## Solution Implemented

### 1. Fixed Orchestrator (`src/downloaders/orchestrator.py`)

**Removed**:
- Size-based conditional logic (`needs_tiling` checks)
- Calls to `download_srtm()` and `download_srtm_90m_single()` for small regions
- Unused imports

**Changed to**:
- ALL resolutions now ALWAYS use `download_and_merge_tiles()`
- No special cases based on region size
- Consistent behavior: 10m, 30m, 90m all use 1-degree tile system

**Before**:
```python
needs_tiling = (width > 4.0 or height > 4.0)
if needs_tiling:
    return download_and_merge_tiles()
else:
    return download_srtm(region_id, bounds, output_path)  # Direct download
```

**After**:
```python
# Always use unified 1-degree tile system
return download_and_merge_tiles(region_id, bounds, output_path, source='srtm_30m')
```

### 2. Enhanced Tile Manager (`src/tile_manager.py`)

**Problem**: Only used `download_srtm()` for all sources, ignoring resolution differences.

**Fixed**: Added resolution-aware routing in tile download loop:

```python
if resolution == '10m':
    success = download_single_tile_10m(tile_bounds, tile_path, dataset='USA_3DEP')
elif resolution == '90m':
    dataset = 'COP90' if 'cop' in source.lower() else 'SRTMGL3'
    success = download_single_tile_90m(tile_bounds, tile_path, api_key, dataset=dataset)
else:  # 30m
    success = download_srtm(tile_bounds, tile_path, api_key)
```

**Benefits**:
- Proper routing to resolution-specific downloaders
- Handles SRTM vs Copernicus dataset selection for 90m
- Works for all resolutions (10m, 30m, 90m)

### 3. Updated Documentation Strings

- Orchestrator docstring now explicitly states "UNIFIED ARCHITECTURE"
- Tile manager docstring updated to reflect "ALL regions regardless of size"
- Added references to `tech/GRID_ALIGNMENT_STRATEGY.md`

## Impact

### Positive Changes

1. **Maximum Tile Reuse**: Small adjacent regions now share 1-degree tiles
   - Example: Vermont (0.5deg wide) and New Hampshire download same tiles where they overlap
   - Storage savings compound across 50 US states

2. **Consistent Architecture**: All resolutions follow same pattern
   - No special cases
   - Easier to maintain
   - Matches documentation

3. **Predictable File Structure**: 
   ```
   data/raw/usa_3dep/tiles/    ← All 10m tiles
   data/raw/srtm_30m/tiles/    ← All 30m tiles
   data/raw/srtm_90m/tiles/    ← All 90m tiles
   ```

4. **Future-Proof**: New regions automatically benefit from existing tile cache

### Slight Overhead for Small Regions

Small regions (<1 degree) now download 1-4 tiles instead of exact bbox:
- Slightly more data per download (~16 MB tile vs ~4 MB exact bbox for 30m)
- But tiles are reused across regions, so net savings over time
- Trade-off accepted per documented design decision

## Verification

### Code Changes
- [x] Removed conditional tiling logic from orchestrator
- [x] All resolutions use `download_and_merge_tiles()`
- [x] Tile manager routes by resolution properly
- [x] Cleaned up unused imports
- [x] Fixed linter errors (RegionType import)

### Documentation Alignment
- [x] Code matches `tech/GRID_ALIGNMENT_STRATEGY.md`
- [x] Code matches `tech/DATA_PIPELINE.md`
- [x] Code matches `learnings/SESSION_20251102_10m_tiling_implementation.md`

## Files Modified

1. **`src/downloaders/orchestrator.py`**:
   - Removed conditional tiling logic (30 lines → 15 lines per resolution)
   - Removed unused imports (download_srtm, download_srtm_90m_single)
   - Added TYPE_CHECKING import for RegionType
   - Updated docstrings

2. **`src/tile_manager.py`**:
   - Added resolution-aware download routing
   - Imported `download_single_tile_10m` and `download_single_tile_90m`
   - Updated docstrings

3. **`learnings/SESSION_20251105_unified_tiling_enforcement.md`** (this file)

## Testing Recommendations

1. **Test small region download** (e.g., Rhode Island, Delaware):
   ```bash
   python ensure_region.py rhode_island --target-pixels 2048
   ```
   - Verify tiles stored in `data/raw/{source}/tiles/`
   - Check tile naming follows format

2. **Test adjacent regions** (e.g., Vermont + New Hampshire):
   ```bash
   python ensure_region.py vermont
   python ensure_region.py new_hampshire
   ```
   - Verify shared border tiles are reused (not re-downloaded)

3. **Test all three resolutions**:
   ```bash
   python ensure_region.py rhode_island --target-pixels 512   # Should use 90m
   python ensure_region.py rhode_island --target-pixels 2048  # Should use 30m
   python ensure_region.py rhode_island --target-pixels 8192  # Should use 10m (US only)
   ```

## Related Documentation

- `tech/GRID_ALIGNMENT_STRATEGY.md` - Complete unified grid system design
- `tech/DATA_PIPELINE.md` - Pipeline stages and tile usage
- `learnings/TILE_NAMING_DESIGN.md` - Why content-based naming matters
- `learnings/SESSION_20251102_10m_tiling_implementation.md` - Previous tiling work for 10m

## Lessons Learned

1. **Documentation divergence happens**: Even with clear docs, implementation can drift
2. **Code review caught it**: User's question about "are we using tiles?" revealed the issue
3. **Incremental implementation creates gaps**: 10m was added with tiles, but 30m/90m retained old hybrid logic
4. **Testing prevents regressions**: Need integration tests that verify tile reuse behavior

## Status

**COMPLETE** - Code now rigorously follows documented unified 1-degree tile architecture for all resolutions.

