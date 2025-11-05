# Pipeline Interface Consolidation Plan

## Current Problem: Too Many Files, Unnecessary Indirection

### Current Structure:
```
ensure_region.py (CLI + Stages 1-5)
  -> process_region() (boundary logic wrapper)
       -> src/pipeline.run_pipeline() (Stages 6-11)
```

**Issues:**
1. **Unnecessary wrapper**: `process_region()` just determines boundaries and calls `run_pipeline()` - this logic should be in `run_pipeline()`
2. **Split download logic**: Download functions in `ensure_region.py`, processing in `src/pipeline.py` - should be unified
3. **Multiple entry points**: `download_unified.py` and `reprocess_existing_states.py` bypass `ensure_region.py` and call `run_pipeline()` directly - this is fine, but shows the interface is confusing
4. **Boundary determination duplicated**: Logic for "is boundary required?" is in `process_region()` but should be in pipeline

### Files Involved:
- `ensure_region.py`: 985 lines - Stages 1-5, CLI, validation, downloads, wrapper
- `src/pipeline.py`: 933 lines - Stages 6-11, core processing
- `src/borders.py`: Boundary loading (used by pipeline) - **KEEP** (utility)
- `src/metadata.py`: Metadata creation (used by pipeline) - **KEEP** (utility)
- `src/versioning.py`: Version checking (used by pipeline) - **KEEP** (utility)
- `src/validation.py`: Validation functions (used by pipeline) - **KEEP** (utility)
- `src/regions_config.py`: Region definitions - **KEEP** (data/config)

## Proposed Solution: Single Interface with Optional Hooks

### Architecture:
```
ensure_region.py (thin CLI wrapper, ~100 lines)
  -> src/pipeline.run_full_pipeline(region_id, ...) (ALL stages 1-11, single interface)

src/pipeline.py (unified pipeline module)
  -> run_full_pipeline() - Main entry point (stages 1-11)
  -> Individual stage functions (for advanced users/hooks):
      -> stage_1_validate_region()
      -> stage_2_determine_dataset()
      -> stage_4_download_raw()
      -> stage_6_clip_boundary()
      -> stage_7_reproject_to_metric_crs()  [NEW - extract from clip/process]
      -> stage_8_downsample_for_viewer()
      -> stage_9_export_to_json()
      -> stage_10_gzip()
      -> stage_11_update_manifest()
  -> Helper utilities (download, validation, etc.)
```

### Benefits:
1. **Single interface**: `run_full_pipeline(region_id)` does everything
2. **Still hookable**: Individual stage functions available for advanced use
3. **Clear boundaries**: All pipeline logic in one module
4. **Reduced indirection**: No wrapper functions, direct calls

### Implementation Plan:

#### Step 1: Extract Reprojection to Separate Function
- Create `reproject_to_metric_crs()` in `src/pipeline.py`
- Remove reprojection from `clip_to_boundary()` 
- Remove reprojection from `downsample_for_viewer()`
- Call reprojection as explicit Stage 7 in `run_pipeline()`

#### Step 2: Move Download Logic to Pipeline Module
- Move `download_us_state()`, `download_international_region()`, `download_region()` from `ensure_region.py` to `src/pipeline.py`
- Move dataset determination logic to `src/pipeline.py`

#### Step 3: Create `run_full_pipeline()` Function
- New function that does ALL stages 1-11
- Takes just `region_id` and options (target_pixels, border_resolution, etc.)
- Handles all boundary determination internally
- Returns `(success: bool, result_paths: dict)`

#### Step 4: Simplify `ensure_region.py`
- Keep only: CLI argument parsing, venv check, call to `run_full_pipeline()`
- Remove: `process_region()`, download functions, boundary determination
- Becomes thin wrapper (~100 lines)

#### Step 5: Update `run_pipeline()` to Handle Boundary Determination
- Move boundary determination logic from `process_region()` into `run_pipeline()`
- Accept `region_id` and `region_config` instead of pre-determined `boundary_name`
- Determine boundary internally based on region class

#### Step 6: Update Other Scripts
- `reprocess_existing_states.py`: Can still call `run_pipeline()` directly (stages 6-11 only)
- `download_unified.py`: Can call `run_full_pipeline()` or continue using `run_pipeline()` if it has raw data

## Alternative: Everything in `ensure_region.py`?

**Option B**: Move all pipeline logic into `ensure_region.py`, make it a single 2000+ line file.

**Pros:**
- Truly single file interface
- All logic visible in one place

**Cons:**
- Very large file (2000+ lines)
- Harder to maintain
- Can't easily reuse stages 6-11 without importing CLI code
- Mixes CLI logic with pipeline logic

**Recommendation**: Option A (consolidated pipeline module) - better separation of concerns, still single interface, allows reuse.

---

## Decision Needed

**Question**: Do you want:
1. **Single interface ... but keep hooks** (Option A - recommended)
   - `run_full_pipeline(region_id)` for normal use
   - Individual stage functions available for advanced use
   - All in `src/pipeline.py`

2. **Truly single file** (Option B)
   - Everything in `ensure_region.py`
   - No separate pipeline module

3. **Current structure but fix indirection**
   - Keep separate files but remove `process_region()` wrapper
   - Move boundary determination into `run_pipeline()`

