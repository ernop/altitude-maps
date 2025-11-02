# Documentation Cleanup Plan

## Overview
Based on refactoring learnings, this plan consolidates, archives, and removes redundant/obsolete documentation.

---

## Phase 1: DELETE (Obsolete/Redundant)

### Root Level - DELETE (6 files)
```
❌ ENUM_ANALYSIS.md - Archive key insights to learnings/, then delete
❌ REFACTORING_EVALUATION.md - Move to learnings/PYTHON_REFACTORING_20251101.md
❌ EXISTING_FILES_ANALYSIS.md - One-time analysis, no longer needed
❌ DATA_DIRECTORIES.md - Merge into tech/TECHNICAL_REFERENCE.md, then delete
```

**Rationale**: These are temporary analysis files from refactoring work. Key insights preserved in learnings/ and .cursorrules.

### learnings/ - DELETE (6 files)
```
❌ BORDERS_STATE_PLAN.md - Completed plan, info preserved in BORDERS_CURRENT.md
❌ CONSOLIDATION_SUMMARY.md - Redundant with session notes
❌ FINAL_REPORT.md - Vague name, no unique content
❌ COMPLETED_DOWNLOADS_SUMMARY.md - Outdated status snapshot
```

**Rationale**: Completed plans, redundant summaries, and outdated status files add no value.

---

## Phase 2: CONSOLIDATE (Reduce 7 files → 2 files)

### Camera Controls (4 files → 1 file)

**Merge into `learnings/CAMERA_CONTROLS.md`:**
- CAMERA_CONTROLS_ARCHITECTURE.md
- CAMERA_CONTROLS_COMPARISON.md
- CAMERA_CONTROLS_IMPLEMENTATION.md
- CAMERA_CONTROLS_SUMMARY.md

**Structure of consolidated file:**
```markdown
# Camera Controls

## Architecture
[Content from ARCHITECTURE.md]

## Comparison of Approaches
[Content from COMPARISON.md]

## Implementation Details
[Content from IMPLEMENTATION.md]

## Summary
[Content from SUMMARY.md]
```

**Then DELETE**: Original 4 files

---

### Aspect Ratio Fixes (3 files → 1 file)

**Merge into `learnings/ASPECT_RATIO_FIX.md`:**
- ASPECT_RATIO_BOUNDING_BOX_FIX.md
- ASPECT_RATIO_FIX_PROCEDURE.md
- ASPECT_RATIO_FIX_SUMMARY.md

**Structure of consolidated file:**
```markdown
# Aspect Ratio Fix

## Problem
[Content from SUMMARY.md]

## Root Cause
[Content from BOUNDING_BOX_FIX.md]

## Fix Procedure
[Content from PROCEDURE.md]

## Results
[Content from SUMMARY.md]
```

**Then DELETE**: Original 3 files

---

## Phase 3: ARCHIVE (Move to learnings/)

### Root Level → learnings/

```
📦 ENUM_ANALYSIS.md → learnings/PYTHON_REFACTORING_20251101.md (merge key insights)
📦 REFACTORING_EVALUATION.md → learnings/PYTHON_REFACTORING_20251101.md (merge)
```

**Create new file**: `learnings/PYTHON_REFACTORING_20251101.md`
- Combine insights from ENUM_ANALYSIS.md and REFACTORING_EVALUATION.md
- Add session context and outcomes
- Delete originals after merge

---

## Phase 4: KEEP (Valuable Reference)

### Critical Technical (KEEP - 8 files)
```
✅ DEPTH_BUFFER_PRECISION_CRITICAL.md - Prevents serious rendering bugs
✅ TILE_NAMING_DESIGN.md - Core architectural decision
✅ DATA_MANAGEMENT_DESIGN.md - Core principles
✅ CACHE_AND_VERSIONING.md - Important patterns
✅ SMART_RESOLUTION_SELECTION.md - Nyquist rule documentation
✅ RESAMPLING_QUALITY_THRESHOLDS.md - Quality standards
✅ LARGE_STATES_TILING.md - Tiling strategy
✅ LINTER_TYPE_STUBS_SETUP.md - Development setup
```

### Recent Session Notes (KEEP - 11 files)
```
✅ All SESSION_202510* files (recent development history)
✅ VIEWER_REFACTORING_STATUS.md (different topic, still relevant)
```

### Specific Fixes (KEEP - 5 files)
```
✅ REPROJECTION_FIX_20250124.md - Important bug fix
✅ DOWNSAMPLING_BUG_FIX.md - Important bug fix
✅ VERTICAL_EXAGGERATION_FIX.md - Important bug fix
✅ JSON_EXPORT_PERFORMANCE_20250227.md - Performance optimization
✅ NATIVE_RESOLUTION_DISPLAY_OPTIMIZATION.md - Optimization
```

### Other (KEEP - 4 files)
```
✅ BORDERS_CURRENT.md - Current border implementation
✅ HIGH_RESOLUTION_DOWNLOAD_GUIDE.md - User guide
✅ RENDERING_EFFICIENCY_ANALYSIS.md - Performance analysis
✅ STATE_DATA_AUDIT.md - Data quality audit
✅ US_STATES_DOWNLOAD_COMPLETE.md - Milestone record
✅ GROUND_PLANE_REALIZATION.md - Key architectural insight
```

---

## Phase 5: CREATE (New Documentation)

### New Files to Create:

**1. `learnings/PYTHON_REFACTORING_20251101.md`**
- Merge ENUM_ANALYSIS.md + REFACTORING_EVALUATION.md
- Add session context and learnings
- Document RegionType enum implementation
- Document terminology unification
- Document resolution logic fixes

**2. `tech/REFACTORING_GUIDE.md`**
- When to use enums vs Literal types
- How to safely move functions between modules
- Validation function patterns
- Data flow directory structure
- Import safety patterns

**3. `REFACTORING_LEARNINGS.md` (already created)**
- Keep at root for visibility
- Summary of all learnings from this session

---

## Summary Statistics

### Before Cleanup:
- Root level: 6 analysis/refactoring docs
- learnings/: 43 files

### After Cleanup:
- Root level: 1 file (REFACTORING_LEARNINGS.md)
- learnings/: 33 files (10 deleted, 7 consolidated to 2, 1 new)

**Net reduction**: 16 files removed/consolidated

---

## Execution Order

1. **Create new files first** (so we don't lose content):
   - `learnings/PYTHON_REFACTORING_20251101.md`
   - `learnings/CAMERA_CONTROLS.md`
   - `learnings/ASPECT_RATIO_FIX.md`
   - `tech/REFACTORING_GUIDE.md`

2. **Merge DATA_DIRECTORIES.md** into `tech/TECHNICAL_REFERENCE.md`

3. **Delete obsolete files** (after verifying content is preserved):
   - Root level: 4 files
   - learnings/: 6 files
   - learnings/: 7 files (after consolidation)

4. **Update .cursorrules** with new patterns

5. **Test**: Verify all documentation references still work

---

## Approval Checklist

- [ ] Review list of files to delete
- [ ] Review consolidation plan
- [ ] Review new files to create
- [ ] Approve .cursorrules updates
- [ ] Execute cleanup
- [ ] Verify no broken references
- [ ] Commit changes

