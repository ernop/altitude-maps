# Proposed .cursorrules Updates

## Additions Based on Refactoring Learnings

### 1. Add to "Development Patterns" Section

After the "Code Style" subsection, add:

```markdown
### Type Safety and Enums
- **Use enums for closed sets**: When you have a fixed set of string values (types, categories, states), use `enum.Enum`
- **String enums for serialization**: Inherit from `str` for JSON compatibility: `class MyEnum(str, Enum)`
- **Centralized location**: Place project-wide enums in `src/types.py`
- **When NOT to use enums**: Open-ended values (resolutions: 10m, 30m, future 5m), dual-nature fields (string for files, int for math)
- **Alternative**: Use `typing.Literal['value1', 'value2']` for type hints without runtime overhead

Example:
```python
# src/types.py
from enum import Enum

class RegionType(str, Enum):
    USA_STATE = "usa_state"
    COUNTRY = "country"
    AREA = "area"
```

### Terminology Consistency
- **One term per concept**: Never use synonyms for the same thing (e.g., not both "category" and "region_type")
- **Unify immediately**: When you notice dual terminology, refactor to single term before it spreads
- **Refactoring order**: Data structures first → code references → documentation
- **Semantic accuracy**: Choose the term that best describes the concept's purpose

### Import Safety
- **Never use defensive imports for internal code**: No `try/except ImportError` for your own modules
- **Let imports fail hard**: If an internal import fails, fix the underlying issue, don't add fallbacks
- **After refactoring**: Use grep to find ALL import statements of moved functions
  ```bash
  grep -r "from src.module import function_name" .
  ```
```

### 2. Update "Data Handling" Section

Replace the existing "Data Handling" section with:

```markdown
### Data Handling

#### Directory Structure (Data Flow)
- **`data/raw/{source}/tiles/`** - Pure reusable 1×1 degree tiles (never region-specific)
- **`data/merged/{source}/`** - Region-specific merged files (intermediate output from tile merging)
- **`data/processed/{source}/`** - Clipped/reprojected files (pipeline intermediate stage)
- **`data/borders/`** - Natural Earth border data (canonical, stable, not cache)
- **`generated/regions/`** - Final JSON exports for web viewer

**Why separate directories**: Prevents mixing reusable upstream data with region-specific intermediate files.

#### Resolution Requirements (CRITICAL)
- **Universal rule**: ALL regions use Nyquist sampling rule based on visible pixel size
- **No type-based exceptions**: Region type (USA_STATE/COUNTRY/REGION) does NOT dictate quality requirements
- **Region type is for**:
  - Download routing (which API/source to use)
  - UI organization (dropdown grouping in viewer)
- **Region type is NOT for**:
  - Quality requirements (universal rules apply)
  - Resolution selection (based on actual data needs)

#### Border Resolution (CRITICAL)
- **Always use 10m resolution borders** for accurate clipping (Natural Earth 10m dataset)
- 110m borders are TOO COARSE and miss islands/coastline details
- Specify with `--border-resolution 10m` flag (now the default)

#### Tile Naming Convention (Content-Based Reuse)
[Keep existing content]

#### File Naming Philosophy: Abstract vs Specific
[Keep existing content]

#### Core Data Principles - CRITICAL
[Keep existing content]
```

### 3. Add New Section: "Validation Patterns"

Add after "Data Handling" section:

```markdown
### Validation Patterns

#### Centralized Validation Functions
- **Location**: All validation logic in `src/validation.py`
- **Purpose**: Enable reuse and independent testing
- **Types of validation**:
  - GeoTIFF file validation (structure, CRS, data integrity)
  - Elevation range validation (detect flat/corrupted data)
  - Non-null coverage validation (ensure sufficient data)
  - JSON export validation (required fields, data types)

#### Standard Validation Function Signature
```python
def validate_something(
    data,
    threshold: float = DEFAULT_VALUE,
    warn_only: bool = False
) -> Tuple[result_values..., bool]:
    """
    Validate something about the data.
    
    Args:
        data: The data to validate
        threshold: Threshold for validation
        warn_only: If True, print warning; if False, raise exception
        
    Returns:
        Tuple of (computed_values..., is_valid)
    """
    # Validation logic
    if not is_valid:
        msg = f"Validation failed: {reason}"
        if warn_only:
            print(f"  WARNING: {msg}")
        else:
            raise ValueError(msg)
    
    return computed_values, is_valid
```

#### After Moving Validation Functions
When refactoring validation code:
1. Move function to `src/validation.py`
2. Search for ALL imports: `grep -r "from .* import function_name" .`
3. Update all import statements
4. Test end-to-end to catch missing imports
```

### 4. Update "Project Organization" Section

Update the documentation structure rules to reflect learnings cleanup:

```markdown
### Historical Learnings (`learnings/` folder)
Session notes and development threads only:
- **`SESSION_YYYYMMDD_description.md`** - Session-specific notes (use standardized date format)
- **`[FEATURE]_SUMMARY.md`** - Feature-specific learnings (e.g., DEPTH_BUFFER_PRECISION_CRITICAL.md)
- **`[FEATURE]_FIX.md`** - Bug fix summaries (e.g., ASPECT_RATIO_FIX.md)

**Consolidation Rule**: When you have 3+ files on the same topic, consolidate into one comprehensive file.

**Examples**:
- CAMERA_CONTROLS_*.md (4 files) → CAMERA_CONTROLS.md (1 file)
- ASPECT_RATIO_*_FIX.md (3 files) → ASPECT_RATIO_FIX.md (1 file)

**Deletion Rule**: Delete files that are:
- One-time analyses (EXISTING_FILES_ANALYSIS.md)
- Completed status reports (COMPLETED_DOWNLOADS_SUMMARY.md)
- Redundant with session notes (CONSOLIDATION_SUMMARY.md)
- Vague/generic names without unique content (FINAL_REPORT.md)
```

---

## Summary of Changes

### New Sections:
1. Type Safety and Enums (under Development Patterns)
2. Terminology Consistency (under Development Patterns)
3. Import Safety (under Development Patterns)
4. Validation Patterns (new top-level section)

### Updated Sections:
1. Data Handling - Added directory structure clarity and resolution requirements
2. Project Organization - Added consolidation and deletion rules

### Key Principles Added:
- Enums for closed sets, Literal for open sets
- One term per concept (no synonyms)
- Let imports fail hard (no defensive try/except)
- Universal resolution rules (no type-based exceptions)
- Separate directories for different data flow stages
- Consolidate learnings when 3+ files on same topic

---

## Implementation Steps

1. Review this proposal
2. If approved, update `.cursorrules` with these sections
3. Execute documentation cleanup (delete/consolidate as proposed in REFACTORING_LEARNINGS.md)
4. Archive ENUM_ANALYSIS.md and REFACTORING_EVALUATION.md to learnings/
5. Test that all documentation references still work

