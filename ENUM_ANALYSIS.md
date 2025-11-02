# Enum Analysis: region_type and resolution

## ✅ IMPLEMENTED: RegionType Enum

### What Was Actually Done

After reviewing `src/regions_config.py`, discovered the actual structure:
- **3 types:** `usa_state`, `country`, `region` (not just 2!)
- **Download simplification:** Code maps these to binary download routing ('us_state' vs 'international')

**Implementation:**
```python
# src/types.py (NEW)
class RegionType(str, Enum):
    USA_STATE = "usa_state"  # US states
    COUNTRY = "country"      # Countries (Iceland, Japan, etc.)
    REGION = "region"        # Islands, mountain ranges, peninsulas, etc.
```

**Field renamed:** `category` → `region_type` (unified terminology throughout codebase)

**Updated:**
- `src/types.py`: Created `RegionType` enum
- `src/regions_config.py`: 55 region definitions use `region_type` field with enum values
- `ensure_region.py`: Uses `region_config.region_type` with enum comparison
- All tests passing ✅

---

## Question 1 (Original): Should `region_type` be an enum?

### Original Analysis (before discovering 3 categories)
```python
# String literals used throughout
region_type = 'us_state'
region_type = 'international'

# Usage pattern
if region_type == 'us_state':
    ...
elif region_type == 'international':
    ...
```

### Analysis

**Pros of using Enum:**
- ✅ **Type safety:** IDE autocomplete, catch typos at development time
- ✅ **Clear contract:** Only 2 valid values, enum makes this explicit
- ✅ **Refactoring safety:** Rename once in enum, all usages update
- ✅ **Self-documenting:** `RegionType.US_STATE` is clearer than `'us_state'`

**Cons of using Enum:**
- ❌ **Minimal usage:** Only 18 occurrences across 3 files
- ❌ **Simple values:** Just 2 options, not complex
- ❌ **No behavior:** No methods or complex logic needed
- ❌ **Import overhead:** Need to import enum everywhere it's used

### Recommendation: **YES, use Enum** ⭐

**Rationale:**
- Only 2 values means it's a true enumeration (not open-ended)
- Type safety benefit outweighs small import cost
- Makes code more maintainable and self-documenting
- Python's `Enum` is lightweight and standard

**Suggested Implementation:**
```python
# src/types.py (NEW)
from enum import Enum

class RegionType(str, Enum):
    """Region classification for download and processing."""
    US_STATE = "us_state"
    INTERNATIONAL = "international"
```

**Why `str, Enum`?**
- Inherits from `str` so it's JSON-serializable
- Works with string comparisons for backward compatibility
- Can use `.value` to get string when needed

---

## Question 2: Should `resolution` be an enum?

### Current State
```python
# Mixed usage - BOTH strings AND integers!

# String format (for filenames, directories)
resolution = '30m'
resolution = '90m'
resolution = '10m'

# Integer format (for calculations)
resolution_meters = 30
resolution_meters = 90
min_required = 30  # returned from determine_min_required_resolution()

# Conversions everywhere
if resolution == '90m':
    resolution_meters = 90
    
resolution = '30m' if '30m' in source else '90m'
```

### Analysis

**Pros of using Enum:**
- ✅ **Unify dual representation:** One enum with both `.value` (string) and `.meters` (int)
- ✅ **Type safety:** Prevent invalid resolutions like '45m' or 25
- ✅ **Centralize logic:** Resolution-related methods in one place
- ✅ **Prevent errors:** Can't accidentally mix up string/int formats

**Cons of using Enum:**
- ❌ **Heavy usage:** 35+ occurrences across 8 files (big refactor)
- ❌ **Calculations:** Used in math (`visible_m_per_pixel / 90.0`)
- ❌ **String parsing:** Extracted from filenames, directory names
- ❌ **External data:** Comes from API responses, user input, file paths
- ❌ **Complexity:** Need custom enum with both string and int properties

### Recommendation: **NO, don't use Enum** ❌

**Rationale:**

1. **Dual nature is fundamental:**
   - Strings are for **external interface** (filenames, directories, APIs)
   - Integers are for **internal calculations** (Nyquist rule, comparisons)
   - This duality is inherent to the problem domain, not a design flaw

2. **External data source:**
   ```python
   # Resolution comes from many external sources:
   - File paths: "data/raw/srtm_30m/..."
   - Directory names: "srtm_30m", "srtm_90m"
   - API parameters: demtype='SRTMGL1' (30m)
   - User input: --dataset COP90
   ```
   Converting all these to enums adds complexity without benefit.

3. **Calculation-heavy:**
   ```python
   oversampling = visible_m_per_pixel / 90.0  # Direct math
   if file_resolution > min_required_resolution_meters:  # Comparison
   ```
   Enum would require `.meters` everywhere, making code more verbose.

4. **String parsing is common:**
   ```python
   resolution = '30m' if '30m' in source else '90m'
   tile_name = f"tile_{resolution}.tif"
   ```
   Enum adds conversion overhead without clarity benefit.

5. **Open to extension:**
   - Future: 5m, 1m data sources
   - Custom resolutions from external providers
   - Enum would need constant updates

### Better Alternative: **Type Hints + Constants**

```python
# src/types.py (NEW)
from typing import Literal

# Type hint for resolution strings
ResolutionStr = Literal['10m', '30m', '90m']

# Type hint for resolution integers
ResolutionMeters = Literal[10, 30, 90]

# Constants for validation
VALID_RESOLUTIONS_STR = {'10m', '30m', '90m'}
VALID_RESOLUTIONS_INT = {10, 30, 90}

# Conversion helpers
def resolution_to_meters(resolution: ResolutionStr) -> ResolutionMeters:
    """Convert resolution string to meters."""
    return int(resolution[:-1])

def meters_to_resolution(meters: ResolutionMeters) -> ResolutionStr:
    """Convert meters to resolution string."""
    return f"{meters}m"
```

**Benefits:**
- ✅ Type checking without runtime overhead
- ✅ Clear documentation of valid values
- ✅ Simple conversion functions
- ✅ No refactoring needed (type hints are optional)
- ✅ Works with external data sources
- ✅ Supports calculations naturally

---

## Summary

| Question | Recommendation | Reason |
|----------|---------------|---------|
| `region_type` enum? | **YES** ⭐ | Small, closed set; type safety worth it |
| `resolution` enum? | **NO** ❌ | Dual nature is fundamental; use type hints instead |

---

## Implementation Plan (if you agree)

### Phase 1: Add RegionType Enum (Low effort, high value)

1. Create `src/types.py`:
```python
from enum import Enum

class RegionType(str, Enum):
    US_STATE = "us_state"
    INTERNATIONAL = "international"
```

2. Update imports (3 files):
   - `ensure_region.py`
   - `src/downloaders/orchestrator.py`
   - `src/status.py`

3. Replace string literals:
```python
# Before
if region_type == 'us_state':

# After
if region_type == RegionType.US_STATE:
# or
if region_type == RegionType.US_STATE.value:  # if needed
```

**Effort:** 30 minutes
**Benefit:** Type safety, better IDE support, clearer code

### Phase 2: Add Resolution Type Hints (Optional, low effort)

1. Add to `src/types.py`:
```python
from typing import Literal

ResolutionStr = Literal['10m', '30m', '90m']
ResolutionMeters = Literal[10, 30, 90]
```

2. Gradually add type hints to function signatures:
```python
def tile_filename_from_bounds(
    bounds: Tuple[float, float, float, float],
    resolution: ResolutionStr = '30m',  # Type hint added
    ...
) -> str:
```

**Effort:** 1-2 hours (gradual, as you touch files)
**Benefit:** Better type checking, documentation

---

## Conclusion

**Do:** Create `RegionType` enum - clear win for maintainability.

**Don't:** Create `Resolution` enum - the dual string/int nature is fundamental to the domain, not a design flaw. Use type hints instead.

