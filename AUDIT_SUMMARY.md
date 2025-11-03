# Repository Audit Summary - 2025-11-03

**Context**: Fresh exploration of repository as a new agent learning the system.

## Issues Found & Fixed

### 1. README.md - Multiple Misleading Claims
**Problem**: Documentation falsely claimed US states always use 10m resolution.

**Fixed**:
- Line 150: Changed "US state (10m resolution, USGS)" → "US state (dynamic resolution: 10/30/90m)"
- Line 174: Changed "USA: 10m resolution via USGS 3DEP" → "USA: Dynamic resolution (10/30/90m) via USGS 3DEP + OpenTopography"
- Line 65: Fixed reference to obsolete doc (SRTM_90M_DOWNLOADER.md → DATA_PIPELINE.md)
- Lines 128-133: Rewrote data source section to explain dynamic resolution selection

### 2. tech/USER_GUIDE.md - Outdated Resolution Claims
**Problem**: Stated "10m resolution available for all states" without mentioning dynamic selection.

**Fixed**:
- Section "USA - USGS 3DEP (1-10m)" → "USA - USGS 3DEP + OpenTopography (10/30/90m)"
- Added explanation of dynamic resolution selection with examples
- Added resolution examples at different output sizes (512px→90m, 4096px→30m, 8192px→10m)
- Updated download instructions to use `ensure_region.py` (automated resolution selection)

### 3. src/data_types.py - Missing Context
**Problem**: `RegionInfo.region_type` field had minimal documentation, didn't reference enum.

**Fixed**:
- Updated docstring to clarify it's a JSON export format (string values)
- Added note referencing `src/types.py` for RegionType enum definition
- Clarified that enum is used in code, but manifest stores string values for JSON compatibility

## Verification Checks Performed

### ✓ Code Uses RegionType Enum Correctly
- `ensure_region.py` - Uses enum with exhaustive checking
- `src/downloaders/orchestrator.py` - Uses enum with proper imports
- `src/status.py` - Type hints expect RegionType enum
- `src/pipeline.py` - Correctly receives boundary info from callers (doesn't need enum)
- `src/data_types.py` - Correctly stores string values for JSON (with documentation)

### ✓ Dynamic Resolution System
- `src/downloaders/orchestrator.py` - Implements Nyquist sampling correctly
- `ensure_region.py` - Calls resolution determination for ALL region types
- All region types use dynamic selection (no hardcoded values)

### ✓ Border System
- `src/borders.py` - Clean utility, doesn't handle region types
- `src/regions_config.py` - All regions properly configured with `clip_boundary` flag
- `src/pipeline.py` - Correctly receives and uses boundary parameters

### ✓ Documentation Hierarchy
- `tech/DATA_PIPELINE.md` - Canonical reference (recently updated)
- `tech/DOWNLOAD_GUIDE.md` - Quick reference (defers to DATA_PIPELINE.md)
- `tech/DATA_PRINCIPLES.md` - Core principles (aspect ratios, rendering)
- `tech/OBSOLETE_DOCS.md` - Lists obsolete implementation docs

## System Architecture Understanding

### Data Flow
```
1. User runs: python ensure_region.py idaho
2. ensure_region.py:
   - Gets region config (RegionType.USA_STATE)
   - Calculates visible pixel size
   - Determines min required resolution (e.g., 90m for 2048px)
   - Checks for existing files (quality-first search)
   - Downloads if needed (tile-based system)
3. pipeline.py:
   - Clips to boundary (state border for USA_STATE)
   - Reprojects to metric CRS (fixes latitude distortion)
   - Downsamples to target pixels
   - Exports to JSON
   - Updates manifest
```

### Key Design Principles Found
1. **RegionType Enum**: All code must use enum, never ad-hoc strings
2. **Dynamic Resolution**: Based on Nyquist sampling (2x oversampling minimum)
3. **Quality-First**: Searches for ANY file that meets/exceeds quality requirement
4. **Tile Reuse**: 1×1 degree tiles with content-based naming for cross-region sharing
5. **Single Source of Truth**: DATA_PIPELINE.md is canonical, all docs defer to it

## Files Modified

**Documentation**:
- README.md (4 sections corrected)
- tech/USER_GUIDE.md (data sources section rewritten)
- src/data_types.py (docstring clarified)

**Created**:
- AUDIT_SUMMARY.md (this file)

## Recommendations

### Immediate Actions (Already Done)
✓ Fixed all misleading "always 10m" claims
✓ Updated public-facing docs (README.md)
✓ Clarified technical docs (USER_GUIDE.md)

### Future Improvements
- Consider adding unit tests for region type handling
- Add validation that manifest region_type values match enum string values
- Consider consolidating or archiving older learnings/* files (40 files currently)

## Conclusion

The repository is well-structured with:
- Clear separation of concerns (downloaders, pipeline, borders)
- Proper enum usage in code
- Comprehensive documentation (though some was outdated)
- Good caching and reuse strategies

Main issue was **documentation lag** - the code was correct (using enums, dynamic resolution) but public docs still claimed "always 10m for US states". This has been rectified.

**Status**: All discovered issues fixed. System correctly implements dynamic resolution selection with proper enum enforcement.

