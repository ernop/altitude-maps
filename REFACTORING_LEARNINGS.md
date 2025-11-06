# Refactoring Learnings (November 2025)

## Key Insights from Python Refactoring Session

### 1. **Enum Implementation for Closed Sets**

**Learning**: When you have a closed set of string values that represent types/categories, use enums immediately.

**Implementation**:
```python
# src/types.py
from enum import Enum

class RegionType(str, Enum):
    USA_STATE = "usa_state"
    COUNTRY = "country"
    AREA = "area"
```

**Benefits Realized**:
- IDE autocomplete catches typos at development time
- Type safety prevents invalid values
- Self-documenting code (RegionType.USA_STATE is clearer than "usa_state")
- Refactoring safety (rename in one place)

**When to Use**:
- Closed set of values (won't grow frequently)
- Used in comparisons/conditionals
- Low refactoring cost (<50 occurrences)

**When NOT to Use**:
- Open-ended values (resolutions: 10m, 30m, 90m, future 5m, 1m)
- Dual nature (strings for files, ints for calculations)
- Heavy usage with mixed types (use `Literal` type hints instead)

---

### 2. **Terminology Consistency is Critical**

**Problem Found**: We had both `category` and `region_type` referring to the same concept.

**Solution**: Unified to single term `region_type` everywhere.

**Lesson**: When you notice dual terminology for the same concept, unify immediately. Don't let it spread.

**Pattern**:
1. Choose the most semantically accurate term
2. Rename in data structures first (RegionConfig.category → RegionConfig.region_type)
3. Update all references
4. Update documentation

---

### 3. **Separation of Concerns: Type vs Usage**

**Critical Insight**: Region type (USA_STATE/COUNTRY/REGION) should NOT dictate quality requirements.

**What We Fixed**:
- **Before**: US states hardcoded to require 10m resolution, international regions used Nyquist calculation
- **After**: ALL regions use Nyquist sampling rule based on visible pixel size

**Lesson**: Type classification should only affect:
- Routing (which downloader to use)
- UI organization (dropdown grouping)

NOT:
- Quality requirements (universal rules apply)
- Resolution selection (based on actual data needs)

---

### 4. **Missing Validation Functions Surface During Refactoring**

**Problem**: `src/pipeline.py` was importing `validate_elevation_range()` and `validate_non_null_coverage()` from `src/validation.py`, but they didn't exist.

**Why This Happened**: Functions were moved during refactoring but not all dependencies were checked.

**Solution**: Added missing functions to `src/validation.py`.

**Lesson**: When refactoring, use grep to find ALL imports of moved functions:
```bash
grep -r "from src.validation import" src/
```

---

### 5. **Data Flow Requires Multiple Directories**

**Learning**: Raw tiles, merged outputs, and processed files need separate directories.

**Structure**:
- `data/raw/srtm_30m/tiles/` - Pure 1×1 degree tiles (reusable)
- `data/merged/srtm_30m/` - Region-specific merged files (intermediate)
- `data/processed/srtm_30m/` - Clipped/reprojected (pipeline stage)
- `generated/regions/` - Final JSON exports (viewer-ready)

**Why**: Prevents mixing reusable upstream data with region-specific intermediate files.

---

### 6. **Metadata Function Signatures Must Match**

**Bug Found**: `create_raw_metadata()` was being called with wrong parameters:
```python
# WRONG
create_raw_metadata(source='srtm_30m', resolution='30m', bounds=bounds)

# CORRECT
create_raw_metadata(tif_path=path, region_id=id, source='srtm_30m', download_url=url)
```

**Lesson**: When creating wrapper functions or moving code, verify function signatures match at call sites.

---

### 7. **Defensive Imports Are an Anti-Pattern**

**Problem Found**:
```python
try:
    from downloaders.tile_large_states import download_and_merge_1degree_tiles
except ImportError:
    # Fallback to different implementation
    ...
```

**Why This Is Wrong**:
- Hides real import errors
- Allows duplicate implementations to proliferate
- Makes debugging harder

**Correct Approach**: Let imports fail hard, fix the underlying issue.

---

## Recommended .cursorrules Updates

### Add to "Development Patterns" Section:

```markdown
### Type Safety with Enums
- Use `enum.Enum` for closed sets of string values (types, categories, states)
- Inherit from `str` for JSON serialization: `class MyEnum(str, Enum)`
- Place enums in `src/types.py` for project-wide access
- Use `typing.Literal` for open-ended string sets (resolutions, formats)

### Terminology Consistency
- ONE term per concept - no synonyms (e.g., not both "category" and "region_type")
- When refactoring, unify terminology immediately
- Update data structures, code, and documentation together

### Validation Functions
- Centralize in `src/validation.py`
- After moving functions, grep for all import statements
- Never use defensive `try/except ImportError` for internal modules
```

### Add to "Data Handling" Section:

```markdown
### Data Flow Directories
- `data/raw/{source}/tiles/` - Pure reusable tiles (1×1 degree)
- `data/merged/{source}/` - Region-specific merged files
- `data/processed/{source}/` - Clipped/reprojected intermediate files
- `generated/regions/` - Final JSON exports for viewer

### Resolution Requirements
- ALL regions use Nyquist sampling rule (no type-based exceptions)
- Region type (USA_STATE/COUNTRY/REGION) is for routing and UI only
- Quality requirements are universal, based on visible pixel size
```

---

## Proposed Documentation Cleanup

### Files to DELETE (obsolete/redundant):

**Root Level:**
- `ENUM_ANALYSIS.md` - Move key insights to this file, then delete
- `REFACTORING_EVALUATION.md` - Completed, archive to learnings/
- `EXISTING_FILES_ANALYSIS.md` - One-time analysis, delete
- `DATA_DIRECTORIES.md` - Merge into tech/TECHNICAL_REFERENCE.md

**learnings/ - Consolidate/Delete:**
- `ASPECT_RATIO_BOUNDING_BOX_FIX.md` - Merge into ASPECT_RATIO_FIX_SUMMARY.md
- `ASPECT_RATIO_FIX_PROCEDURE.md` - Merge into ASPECT_RATIO_FIX_SUMMARY.md
- `BORDERS_STATE_PLAN.md` - Completed, delete (info in BORDERS_CURRENT.md)
- `CONSOLIDATION_SUMMARY.md` - Redundant with session notes
- `FINAL_REPORT.md` - Vague name, merge into relevant session notes
- `COMPLETED_DOWNLOADS_SUMMARY.md` - Outdated status file, delete

### Files to KEEP (valuable reference):

**Critical Technical:**
- `DEPTH_BUFFER_PRECISION_CRITICAL.md` - Prevents serious rendering bugs
- `TILE_NAMING_DESIGN.md` - Core architectural decision
- `DATA_MANAGEMENT_DESIGN.md` - Core principles
- `CAMERA_CONTROLS_ARCHITECTURE.md` - Reference implementation

**Session Notes (Recent):**
- Keep all `SESSION_202510*` files (recent development history)

### Files to CONSOLIDATE:

**Camera Controls (4 files → 1):**
Merge these into single `learnings/CAMERA_CONTROLS.md`:
- CAMERA_CONTROLS_ARCHITECTURE.md
- CAMERA_CONTROLS_COMPARISON.md
- CAMERA_CONTROLS_IMPLEMENTATION.md
- CAMERA_CONTROLS_SUMMARY.md

**Aspect Ratio (3 files → 1):**
Merge into single `learnings/ASPECT_RATIO_FIX.md`:
- ASPECT_RATIO_BOUNDING_BOX_FIX.md
- ASPECT_RATIO_FIX_PROCEDURE.md
- ASPECT_RATIO_FIX_SUMMARY.md

---

## New Documentation to CREATE:

### `tech/REFACTORING_GUIDE.md`
Document the refactoring patterns learned:
- When to use enums vs Literal types
- How to safely move functions between modules
- Validation function patterns
- Data flow directory structure

### `learnings/PYTHON_REFACTORING_20251101.md`
Archive this session's work:
- RegionType enum implementation
- Terminology unification
- Resolution logic fixes
- Validation function additions

---

## Summary Statistics

**Files Modified**: 8 core files
- `src/types.py` (created)
- `src/regions_config.py` (55 regions updated)
- `src/validation.py` (2 functions added)
- `src/downloaders/opentopography.py` (metadata fix)
- `ensure_region.py` (logic unified)
- `ENUM_ANALYSIS.md` (updated)

**Lines Changed**: ~150 lines across codebase

**Bugs Fixed**: 4 critical issues
1. Metadata creation parameter mismatch
2. Missing validation functions
3. Category-based resolution requirements (architectural)
4. Merged file discovery in validation

**Time Investment**: ~2 hours of refactoring

**Result**: Type-safe, consistent, unified codebase with proper separation of concerns.

