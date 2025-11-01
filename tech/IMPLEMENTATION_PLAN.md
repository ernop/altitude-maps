# Data Pipeline Implementation & Validation Plan

**Goal**: Ensure all code implements the canonical pipeline specification in `DATA_PIPELINE.md`.

**Status**: This plan tracks what's implemented vs what needs work.

---

## Stage-by-Stage Validation Checklist

### ✅ Stage 1: Validate Region Definition
- [x] `ensure_region.py` checks `ALL_REGIONS` in `src/regions_config.py`
- [x] Error message directs to `--list-regions`
- [x] Normalization (lowercase, underscores) works correctly

**Action**: ✅ VALIDATED - No changes needed

---

### ⚠️ Stage 2: Determine Dataset & Resolution (Overrides First)
- [x] US States hardcoded to USGS 3DEP 10m in `download_us_state()`
- [x] `RegionConfig.recommended_dataset` exists in config
- [ ] **MISSING**: Explicit stage reporting ("[STAGE 2/10] Determining dataset...")
- [ ] **MISSING**: Log which override was applied (US State, recommended_dataset, or none)

**Action Required**:
1. Add explicit stage logging in `ensure_region.py` before calling download functions
2. Report decision: "Using USGS 3DEP 10m (US State)" or "Using COP30 (recommended_dataset)" or "Proceeding to latitude-based selection"

**Files to modify**: `ensure_region.py` lines ~900-907

---

### ⚠️ Stage 3: Dataset Selection by Latitude
- [x] Logic exists in `download_international_region()` lines 341-350
- [ ] **MISSING**: This logic should be separated from download function for clarity
- [ ] **MISSING**: Explicit stage reporting
- [ ] **MISSING**: Report decision: "Using COP30 (>60degN or <-56degS)" or "Using SRTMGL1 (within coverage)"

**Action Required**:
1. Extract latitude-based dataset selection into separate function
2. Call it explicitly with stage reporting before download
3. Pass selected dataset to download function

**Files to modify**: `ensure_region.py` lines ~333-350, add helper function

---

### ✅ Stage 4: Acquire Raw Elevation (GeoTIFF)
- [x] Downloads to correct paths:
  - US: `data/raw/usa_3dep/<region_id>_3dep_10m.tif`
  - International: `data/raw/srtm_30m/<region_id>_bbox_30m.tif`
- [x] Validation (file size, rasterio open, CRS, sample read)
- [x] Auto-cleanup of corrupted files
- [x] Metadata saved with bounds
- [ ] **MISSING**: Stage number should be "[4/10]" not "[STAGE 1/4]"
- [ ] **MISSING**: Report outcome of prior stages before starting

**Action Required**:
1. Update stage numbering to match canonical spec (1-10)
2. Add summary of prior stage outcomes before stage 4

**Files to modify**: `ensure_region.py` lines ~882-920

---

### ✅ Stage 5: Automatic Tiling for Large Areas
- [x] Logic exists in `download_international_region()` lines 468-517
- [x] Automatic detection (area >420k km² or >4deg dimensions)
- [x] Tile download, validation, merge
- [ ] **MISSING**: Stage reporting should mention this is stage 5
- [x] User sees "Downloading tile 1/4..." messages

**Action Required**:
1. Add "[STAGE 5/10]" prefix to tiling messages
2. Report stage completion: "Stage 5 complete: Tiled and merged X tiles"

**Files to modify**: `ensure_region.py` lines ~468-517

---

### ⚠️ Stage 6: Clip to Administrative Boundary
- [x] Boundary source: Natural Earth via `src/borders.get_border_manager()`
- [x] Clipping logic with `crop=True`
- [ ] **CRITICAL FIX NEEDED**: `clip_to_boundary()` returns False on missing boundary but doesn't know if boundary is REQUIRED
- [x] Pipeline now errors if boundary required (recent fix in `src/pipeline.py` line 862-866)
- [ ] **MISSING**: Need to pass "required" flag to `clip_to_boundary()` so it can fail hard vs soft
- [ ] **MISSING**: Stage numbering: should be "[6/10]" not "[2/4]"

**Action Required**:
1. Modify `clip_to_boundary()` to accept `boundary_required: bool` parameter
2. If `boundary_required=True` and geometry is None/empty, raise exception or return clear error
3. Caller in `process_region()` must determine if boundary is required based on:
   - US State -> always required
   - Country/Region with `clip_boundary=True` -> required
   - Region with `clip_boundary=False` -> not required
4. Update stage reporting to "[6/10]"

**Files to modify**:
- `src/pipeline.py` function `clip_to_boundary()` signature and error handling (lines 41-136)
- `ensure_region.py` function `process_region()` to determine required flag (lines 654-670)
- `src/pipeline.py` function `run_pipeline()` to pass required flag (lines 856-866)

---

### ✅ Stage 7: Downsample/Process for Viewer
- [x] Reprojection to metric CRS if EPSG:4326
- [x] Aspect ratio preservation
- [x] Validation checks (CRS not 4326, elevation range, coverage)
- [x] Hyperflat detection exists (`validate_elevation_range()`)
- [ ] **MISSING**: Hyperflat validation must FAIL HARD (currently `warn_only=True` in some places)
- [ ] **MISSING**: Stage numbering: should be "[7/10]" not "[3/4]"

**Action Required**:
1. Ensure `validate_elevation_range()` is called with `warn_only=False` in critical paths:
   - After clipping (line 275-280 in `src/pipeline.py`) ✅ Already does this
   - During processing (needs check in `downsample_for_viewer()`)
2. If validation fails, abort pipeline with clear error
3. Update stage reporting to "[7/10]"

**Files to modify**:
- `src/pipeline.py` function `downsample_for_viewer()` - add elevation range validation with `warn_only=False` (around line 310-370)
- `src/pipeline.py` function `run_pipeline()` stage reporting (line 870-874)

---

### ✅ Stage 8: Export to JSON
- [x] Reads from processed TIF (step 7 output)
- [x] Bounds conversion to EPSG:4326
- [x] Validation (aspect ratio, structure, coverage)
- [x] Creates `.json` file
- [ ] **MISSING**: Stage numbering: should be "[8/10]" not "[4/4]"

**Action Required**:
1. Update stage reporting to "[8/10]"

**Files to modify**: `src/pipeline.py` function `run_pipeline()` (line 878-882)

---

### ✅ Stage 9: Gzip Compression
- [x] Creates `.json.gz` file
- [x] Compression level 9
- [x] Logs compression stats
- [ ] **MISSING**: Explicit stage reporting "[9/10]"

**Action Required**:
1. Add explicit stage log message in `export_for_viewer()` after JSON write, before gzip

**Files to modify**: `src/pipeline.py` function `export_for_viewer()` (around line 704-713)

---

### ✅ Stage 10: Update Viewer Manifest
- [x] Scans `generated/regions/*.json`
- [x] Creates/updates `regions_manifest.json`
- [x] Called after export
- [ ] **MISSING**: Explicit stage reporting "[10/10]"

**Action Required**:
1. Add explicit stage log in `run_pipeline()` before calling `update_regions_manifest()`

**Files to modify**: `src/pipeline.py` function `run_pipeline()` (around line 886-888)

---

## Critical Cross-Cutting Issues

### 1. ❌ Stage Numbering Inconsistency
**Problem**: Code uses "[1/4]", "[2/4]", "[3/4]", "[4/4]" but spec has 10 stages.

**Files affected**:
- `ensure_region.py`: lines 882, 893 (uses [STAGE 1/4], [STAGE 4/4])
- `src/pipeline.py`: lines 853, 860, 870, 878 (uses [1/4], [2/4], [3/4], [4/4])

**Action**: Update all stage numbers to 1-10 format matching canonical spec.

---

### 2. ⚠️ Boundary Failure Behavior
**Problem**: `clip_to_boundary()` doesn't know if boundary is required. Currently returns False for missing boundaries, which causes pipeline to abort only if `run_pipeline()` checks (which it now does), but the error message could be clearer.

**Current behavior**: 
- `clip_to_boundary()` returns False when boundary missing
- `run_pipeline()` now aborts if clipping fails
- But `clip_to_boundary()` error messages say "Warning: ... Skipping clipping step..." which is misleading if boundary is required

**Action**: 
1. Pass `boundary_required: bool` to `clip_to_boundary()`
2. If required and missing, raise exception with clear error
3. If not required, return False gracefully

---

### 3. ⚠️ Hyperflat Elevation Validation
**Problem**: `validate_elevation_range()` has `warn_only` parameter. Need to ensure it's set to `False` (fail hard) in critical paths.

**Current state**:
- Clipping validation (line 275-280): ✅ Uses `warn_only=False`
- Processing validation: ❌ Not explicitly checked in `downsample_for_viewer()`
- Export validation: ❌ Not explicitly checked in `export_for_viewer()`

**Action**: 
1. Add elevation range validation in `downsample_for_viewer()` with `warn_only=False`
2. Export uses JSON validation which checks structure, but should also validate elevation range from processed TIF

---

### 4. ⚠️ Job Progress Reporting
**Problem**: Not all stages clearly report:
- Which stage is starting
- Outcome of prior stages
- Clear success/failure messages

**Action**:
1. Before each stage, print summary of prior stage outcomes
2. Each stage prints "[STAGE N/10] Starting..."
3. Each stage prints "[STAGE N/10] Complete: <summary>" or "[STAGE N/10] FAILED: <reason>"
4. On failure, print "[STAGE N/10] ABORT: Cannot continue without this stage"

---

### 5. ⚠️ Stage 2/3 Separation
**Problem**: Stage 2 (overrides) and Stage 3 (latitude) logic is embedded in download functions rather than being explicit decision points.

**Action**:
1. Extract dataset determination into separate functions:
   - `determine_dataset_override(region_config) -> Optional[str]`
   - `determine_dataset_by_latitude(bounds) -> str`
2. Call these explicitly before download with stage reporting
3. Pass selected dataset to download function

---

## Implementation Order (Priority)

### High Priority (Critical for correctness)
1. **Fix boundary failure behavior** - Regions that require boundaries must fail clearly (Stage 6)
2. **Enforce hyperflat validation** - Ensure elevation range validation fails hard (Stage 7)
3. **Fix stage numbering** - Update all to 1-10 format for consistency

### Medium Priority (User experience)
4. **Add explicit stage reporting** - All 10 stages should be clearly logged
5. **Separate dataset determination** - Extract Stages 2/3 into explicit functions
6. **Job progress summary** - Report outcomes of prior stages

### Low Priority (Polish)
7. **Consolidate error messages** - Ensure consistent format
8. **Add stage timing** - Optional: report how long each stage took

---

## Validation Tests

### Test 1: Boundary Required Failure
**Setup**: Create test region with `clip_boundary=True` but invalid boundary name
**Expected**: Pipeline stops at Stage 6 with clear error: "ERROR: Boundary required for region X but boundary 'Y' not found. Aborting."

### Test 2: Hyperflat Detection
**Setup**: Use corrupted test data with elevation range <50m
**Expected**: Pipeline stops at Stage 7 with clear error: "ERROR: Elevation range suspicious (X-Y m). Possible reprojection corruption. Aborting."

### Test 3: Stage Reporting
**Expected Output**:
```
[STAGE 1/10] Validate region definition... [OK]
[STAGE 2/10] Determine dataset & resolution... [OK] (USGS 3DEP 10m - US State)
[STAGE 3/10] Dataset selection by latitude... [SKIP] (skipped - override applied)
[STAGE 4/10] Acquire raw elevation... [OK] (Downloaded 125.3 MB)
[STAGE 5/10] Automatic tiling... [SKIP] (not needed)
[STAGE 6/10] Clip to boundary... [OK] (California state boundary)
[STAGE 7/10] Downsample/process... [OK] (800px, aspect preserved)
[STAGE 8/10] Export to JSON... [OK] (1.2 MB)
[STAGE 9/10] Gzip compression... [OK] (85% reduction)
[STAGE 10/10] Update manifest... [OK]
```

### Test 4: Fail-Fast Behavior
**Setup**: Stage 4 (download) fails
**Expected**: Pipeline stops immediately, Stages 5-10 never execute, clear error message

---

## Files Requiring Changes

### Primary Implementation Files
1. `ensure_region.py` - Entry point, stage orchestration, progress reporting
2. `src/pipeline.py` - Core pipeline implementation, stage execution
3. `src/borders.py` - Boundary loading (may need to raise exceptions vs return None)

### Supporting Files
4. `src/validation.py` - Already has elevation range validation; verify usage
5. `src/regions_config.py` - Already correct

---

## Next Steps

1. Create separate branch for implementation
2. Start with High Priority items:
   - Fix boundary failure behavior
   - Enforce hyperflat validation
   - Update stage numbering
3. Test each change with real regions
4. Update canonical doc if behavior changes

---

**Last Updated**: 2025-01-XX  
**Status**: Planning phase - ready for implementation

