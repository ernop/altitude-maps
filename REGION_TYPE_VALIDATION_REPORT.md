# Region Type System Validation Report

## Rule Being Validated

ALL code handling region types MUST:
1. Import and use `RegionType` enum from `src/types.py`
2. Use enum values: `RegionType.USA_STATE` (NOT strings like `'us_state'`)
3. Check all three cases exhaustively with `if/elif/elif/else`
4. Raise `ValueError` for unknown types (NEVER silent fallback to None/default)

## Summary

**Status**: ✅ PASSED - All 6 violations have been fixed

**Last Updated**: 2025-11-03

All Python files now properly use the `RegionType` enum with exhaustive checking and error handling.

## Violations Found

### 1. ❌ ensure_region.py:499 - String Literal Instead of Enum

**Location**: `ensure_region.py`, line 499

**Issue**: Uses string literal `'us_region'` instead of enum value

```python
# CURRENT (WRONG):
if region_type == 'us_region':
    available_downloads = [10, 30, 90]
else:
    available_downloads = [30, 90]
```

**Problem**:
- Uses undefined string `'us_region'` (not a valid RegionType value)
- Should be `RegionType.USA_STATE`
- This code will never match, causing US states to incorrectly get international resolutions

**Fix Required**:
```python
# CORRECT:
if region_type == RegionType.USA_STATE:
    available_downloads = [10, 30, 90]
elif region_type == RegionType.COUNTRY or region_type == RegionType.REGION:
    available_downloads = [30, 90]
else:
    raise ValueError(f"Unknown region type: {region_type}")
```

---

### 2. ❌ src/downloaders/orchestrator.py:258+ - No Exhaustive Checking

**Location**: `src/downloaders/orchestrator.py`, lines 258-321

**Issue**: Only checks `RegionType.USA_STATE` explicitly, then has implicit fallthrough for "international regions" without checking COUNTRY/REGION

```python
# CURRENT (INCOMPLETE):
if region_type == RegionType.USA_STATE:
    # ... handle US states
    return 'USA_3DEP' or 'SRTMGL1' or 'SRTMGL3'

# International regions - check for explicit override first
recommended = None
# ... (no explicit check for COUNTRY or REGION)
# ... falls through to handle both as "international"
```

**Problem**:
- No explicit check for `RegionType.COUNTRY` or `RegionType.REGION`
- No `else` clause with `ValueError` for unknown types
- Silent fallthrough allows invalid region types to be processed

**Fix Required**:
```python
# CORRECT:
if region_type == RegionType.USA_STATE:
    # ... handle US states
    return dataset

elif region_type == RegionType.COUNTRY or region_type == RegionType.REGION:
    # ... handle international regions
    return dataset

else:
    raise ValueError(f"Unknown region type: {region_type}")
```

---

### 3. ❌ compute_adjacency.py:95-127 - Missing REGION Check

**Location**: `compute_adjacency.py`, lines 95-127

**Issue**: Only handles USA_STATE and COUNTRY, doesn't handle REGION, no ValueError else clause

```python
# CURRENT (INCOMPLETE):
for region in all_regions:
    if region.region_type == RegionType.USA_STATE:
        # ... process US states
        
# Add countries
for region in all_regions:
    if region.region_type == RegionType.COUNTRY:
        # ... process countries

# MISSING: No handling for RegionType.REGION
# MISSING: No error for unknown types
```

**Problem**:
- Silently skips regions with `region_type == RegionType.REGION`
- No error handling for invalid region types
- Incomplete data processing

**Fix Required**:
```python
# CORRECT:
for region in all_regions:
    if region.region_type == RegionType.USA_STATE:
        # ... process US states
    elif region.region_type == RegionType.COUNTRY:
        # ... process countries
    elif region.region_type == RegionType.REGION:
        # ... process regions (or skip with explicit comment)
    else:
        raise ValueError(f"Unknown region type for {region.id}: {region.region_type}")
```

---

### 4. ❌ src/regions_config.py:918 - Non-existent Attribute

**Location**: `src/regions_config.py`, line 918

**Issue**: Accesses `r.category` which doesn't exist on `RegionConfig`

```python
# CURRENT (WRONG):
def list_regions(category: Optional[str] = None) -> List[RegionConfig]:
    regions = list(ALL_REGIONS.values())
    if category:
        regions = [r for r in regions if r.category == category]  # WRONG: .category doesn't exist
    return sorted(regions, key=lambda r: r.name.lower())
```

**Confirmed by Test**:
```
Has category: False
Has region_type: True
```

**Problem**:
- `RegionConfig` has `region_type` attribute, not `category`
- This function will crash with `AttributeError` when called with a category parameter

**Fix Required**:
```python
# CORRECT:
def list_regions(region_type: Optional[RegionType] = None) -> List[RegionConfig]:
    """List all regions, optionally filtered by region type."""
    regions = list(ALL_REGIONS.values())
    if region_type:
        regions = [r for r in regions if r.region_type == region_type]
    return sorted(regions, key=lambda r: r.name.lower())
```

---

### 5. ❌ reprocess_existing_states.py:127 - Non-existent Attribute

**Location**: `reprocess_existing_states.py`, line 127

**Issue**: Accesses `config.category` which doesn't exist on `RegionConfig`

```python
# CURRENT (WRONG):
boundary_type = 'state' if config.category == 'usa_state' else 'country'
```

**Problem**:
- Same as #4 - uses non-existent `.category` attribute
- Uses string literal `'usa_state'` instead of enum
- Will crash with `AttributeError`

**Fix Required**:
```python
# CORRECT:
if config.region_type == RegionType.USA_STATE:
    boundary_type = 'state'
elif config.region_type == RegionType.COUNTRY:
    boundary_type = 'country'
elif config.region_type == RegionType.REGION:
    boundary_type = None  # or appropriate handling
else:
    raise ValueError(f"Unknown region type: {config.region_type}")
```

---

## Compliant Code Examples

### ✅ ensure_region.py:177-199 (CORRECT)

```python
# Determine boundary based on region type (using enum)
# CANONICAL REFERENCE: tech/DATA_PIPELINE.md - Section "Region Type System"
if region_type == RegionType.USA_STATE:
    state_name = region_info['name']
    boundary_name = f"United States of America/{state_name}"
    boundary_type = "state"
elif region_type == RegionType.COUNTRY:
    # For countries, use country-level boundary
    if region_info.get('clip_boundary', True):
        boundary_name = region_info['name']
        boundary_type = "country"
    else:
        boundary_name = None
        boundary_type = None
elif region_type == RegionType.REGION:
    # For regions (islands, ranges, etc.), check if boundary clipping is enabled
    if region_info.get('clip_boundary', False):
        boundary_name = region_info['name']
        boundary_type = "country"
    else:
        boundary_name = None
        boundary_type = None
else:
    raise ValueError(f"Unknown region type: {region_type}")
```

**Why This Is Correct**:
- ✅ Uses `RegionType` enum values
- ✅ Exhaustive checking: if/elif/elif/else
- ✅ Raises `ValueError` for unknown types
- ✅ Handles all three cases: USA_STATE, COUNTRY, REGION

---

## Files Checked

### Python Files Using RegionType

1. ✅ **src/types.py** - Enum definition (correct)
2. ✅ **src/regions_config.py** - Region definitions (mostly correct, 1 violation in utility function)
3. ⚠️ **ensure_region.py** - Mixed (1 correct pattern, 1 violation)
4. ❌ **src/downloaders/orchestrator.py** - Incomplete checking
5. ❌ **compute_adjacency.py** - Incomplete checking
6. ❌ **reprocess_existing_states.py** - Wrong attribute access

### JavaScript Files (Expected to Use Strings)

JavaScript files are expected to use string literals since they don't have access to Python enums:
- `js/viewer-advanced.js` - Uses `'usa_state'` (acceptable for JS)
- `js/state-connectivity.js` - Uses `'usa_state'` (acceptable for JS)

---

## Priority for Fixes

### High Priority (Causes Runtime Errors)
1. **src/regions_config.py:918** - Function crashes when called
2. **reprocess_existing_states.py:127** - Script crashes when run
3. **ensure_region.py:499** - Incorrect logic, US states get wrong resolutions

### Medium Priority (Silent Failures)
4. **src/downloaders/orchestrator.py** - No validation, allows invalid types
5. **compute_adjacency.py** - Silently skips REGION types

---

## Fixes Applied

All 6 violations have been fixed:

1. ✅ **src/regions_config.py:918** - Changed `.category` to `.region_type`, updated function signature
2. ✅ **reprocess_existing_states.py:127** - Replaced `.category` with exhaustive `region_type` checking
3. ✅ **ensure_region.py:499** - Replaced `'us_region'` string with `RegionType.USA_STATE` enum
4. ✅ **src/downloaders/orchestrator.py:258+** - Added exhaustive checking with `elif` and `else` clause
5. ✅ **compute_adjacency.py:95-127** - Added REGION handling and error clause
6. ✅ **All syntax validated** - All files pass Python compilation

---

## Validation Results

### Functional Tests Passed:
```
✅ list_regions() - Works without crashes (89 total regions)
✅ list_regions(RegionType.USA_STATE) - Returns 50 US states
✅ list_regions(RegionType.COUNTRY) - Returns 8 countries  
✅ list_regions(RegionType.REGION) - Returns 31 regions
✅ get_region('ohio').region_type - Returns RegionType.USA_STATE correctly
```

### Syntax Validation Passed:
```
✅ ensure_region.py - Syntax OK
✅ src/downloaders/orchestrator.py - Syntax OK
✅ reprocess_existing_states.py - Syntax OK
✅ compute_adjacency.py - Syntax OK
✅ src/regions_config.py - Syntax OK
```

### Code Search Validation:
```
✅ No `.category ==` usage found in Python files
✅ No string literal region type comparisons found
✅ All region_type comparisons use RegionType enum
```

---

## Next Steps

1. ✅ All fixes completed
2. Consider adding unit tests to prevent future violations
3. Consider adding type checking with mypy to catch attribute errors
4. Update any documentation that references the old patterns

