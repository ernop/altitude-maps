# Refactoring Plan: Three-Layer Architecture

## Current State Analysis

### File Responsibilities (current)

**ensure_region.py** (2,966 lines):
- **UI/I/O**: CLI argument parsing, user prompts, status reporting
- **Download orchestration**: Coordinate downloads for US states vs international
- **Resolution selection**: Determine optimal dataset/resolution based on target pixels
- **Pipeline coordination**: Call processing pipeline with correct parameters
- **Verification**: Validate outputs, auto-fix issues
- **DUPLICATED**: Has its own copy of `run_pipeline()`, `clip_to_boundary()`, `downsample_for_viewer()`, `export_for_viewer()`, `update_regions_manifest()` - same as pipeline.py

**src/pipeline.py** (1,022 lines):
- **Processing**: Clip, reproject, downsample, export operations
- **Core logic**: Geographic data transformations
- **DUPLICATED**: Has its own copy of same functions as ensure_region.py

**src/tile_geometry.py** (194 lines):
- **Math/Geometry**: Tile calculations, bounds snapping, filename generation
- **Pure calculations**: No I/O, no user interaction

---

## Target Three-Layer Architecture

### Layer 1: UI/I/O Layer
**Files**: `ensure_region.py` (CLI entry point)

**Responsibilities**:
- User input: argparse, prompts, help text
- User output: status messages, progress indicators, error messages
- Coordination: Decide what operations to run based on user intent
- File discovery: Check what exists, report status
- Delegation: Call layer 2/3 for actual work

**Should NOT contain**:
- Download logic (delegate to layer 2)
- Processing operations (delegate to layer 2)
- Mathematical calculations (delegate to layer 3)

---

### Layer 2: Download/Processing Layer
**Files**: `src/pipeline.py`, download modules

**Responsibilities**:
- Download: Fetch data from external sources (OpenTopography, USGS)
- Processing: Clip boundaries, reproject CRS, downsample, export
- I/O coordination: File reads/writes for pipeline stages
- Validation: Check data quality (but not user-facing messages)

**Should NOT contain**:
- User prompts or status reporting (layer 1 does that)
- CLI argument parsing
- Mathematical calculations (delegate to layer 3)

---

### Layer 3: Math/Geometry Layer
**Files**: `src/tile_geometry.py`, calculation modules

**Responsibilities**:
- Pure calculations: Tile math, bounds snapping, coordinate conversions
- Rules: Nyquist sampling, file size estimation, resolution selection
- Transformations: Geographic calculations

**Should NOT contain**:
- I/O operations (layers 1/2 do that)
- User interaction
- File system access

---

## Migration Steps

### Step 1: Consolidate duplicate pipeline functions (PRIORITY)
**Problem**: Both `ensure_region.py` and `src/pipeline.py` have identical copies of:
- `run_pipeline()`
- `clip_to_boundary()`
- `downsample_for_viewer()`
- `export_for_viewer()`
- `update_regions_manifest()`

**Action**: Keep ONE copy in `src/pipeline.py`, delete from `ensure_region.py`, import instead.

**Benefit**: Reduces ensure_region.py by ~800 lines, eliminates duplication

---

### Step 2: Move calculation functions to tile_geometry.py
**Functions to move**:
- `determine_min_required_resolution()` - Nyquist sampling rule
- `format_pixel_size()` - Simple formatting
- `calculate_visible_pixel_size()` - Pixel size calculations

**Benefit**: Centralizes all mathematical/geometric calculations

---

### Step 3: Create dedicated download module
**New file**: `src/downloads.py`

**Move from ensure_region.py**:
- `download_us_state()`
- `download_international_region()`
- `download_region()` (wrapper)
- `determine_dataset_override()`

**Benefit**: Separates download logic from UI coordination

---

### Step 4: Keep validation/utilities separate
**Current organization is GOOD**:
- `src/metadata.py` - File metadata utilities
- `src/borders.py` - Boundary loading
- `src/validation.py` - Data validation
- `src/regions_config.py` - Configuration data

**These are small, focused utilities - no changes needed**

---

## Expected Results

### Line Count Reduction
- **ensure_region.py**: 2,966 → ~400 lines (UI/coordination only)
- **src/pipeline.py**: 1,022 → 1,022 lines (consolidate duplicates here)
- **src/tile_geometry.py**: 194 → ~280 lines (add calculations)
- **src/downloads.py**: 0 → ~500 lines (new, extracts download logic)

### Clear Boundaries
- Layer 1: User interaction, nothing else
- Layer 2: Data operations, no user prompts
- Layer 3: Pure math, no I/O

### Testing Benefits
- Layer 3 functions are easily unit testable (no I/O, pure functions)
- Layer 2 can be tested with mock files
- Layer 1 can be tested with mock layer 2/3

---

## Risk Assessment

**LOW RISK**: This is refactoring/organizing, not changing functionality
- All existing code paths preserved
- Import paths change, behavior doesn't
- Can do incrementally, test after each step

**High Value**: Makes codebase maintainable and testable

