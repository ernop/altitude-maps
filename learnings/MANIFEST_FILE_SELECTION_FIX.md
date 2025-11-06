# Manifest File Selection - Fail-Fast Implementation

**Date**: 2025-11-06  
**Issue**: Manifest generator was using naive "first file alphabetically" selection  
**Risk**: Would silently fall back to old unclipped files if they existed  
**Solution**: Implemented strict v2-only selection with fail-fast behavior  
**Status**: Fixed

## Problem

The original manifest generator used a naive selection algorithm:

```python
# OLD CODE (WRONG):
for candidate_file in json_files_by_region[region_id]:
    json_file = candidate_file
    break  # Uses first file alphabetically!
```

**Risks:**
- Would pick `pennsylvania.json` over `pennsylvania_srtm_30m_2048px_v2.json` (alphabetical order)
- No validation of file format or version
- Silent fallback to old unclipped files
- No warnings when multiple files exist

This violated the project's "NO SILENT FALLBACKS" philosophy.

## Project Philosophy (from .cursorrules)

The project has clear rules about error handling:

1. **"NEVER silent fallback to None/default"** - Raise ValueError for unknown types
2. **"NO fallback implementations"** - Let imports fail hard
3. **"Do not add fallback loaders"** - Fix the primary path
4. **"fail fast with a clear error"** - Don't proceed if earlier stage failed
5. **"Add version validation on data load (fail if version mismatch)"**

**The boundary clipping bug happened because of "silent fallback to no clipping"**

## Solution Implemented

### 1. Export Code Fix

Added missing `version` field to export:

```python
# src/pipeline.py line 739
export_data = {
    "version": "export_v2",  # CRITICAL: Required for manifest validation
    "region_id": region_id,
    "source": source,
    # ... rest of fields
}
```

### 2. Manifest Generator - Strict v2-Only Selection

```python
# regenerate_manifest.py lines 82-118

# Filter to ONLY v2 files with proper version field
v2_candidates = []
for candidate_file in candidates:
    try:
        data = json.load(open(candidate_file))
        
        # CRITICAL: Only accept files with version field
        # NO SILENT FALLBACKS to old format files
        version = data.get('version')
        if version == 'export_v2':
            v2_candidates.append((candidate_file, data))
        else:
            # Warn about files without proper version
            print(f"[!] SKIP {region_id}: {candidate_file.name} (version={version}, expected 'export_v2')")
    except Exception as e:
        print(f"[!] SKIP {region_id}: {candidate_file.name} (failed to load: {e})")

# If no v2 files found, skip this region entirely (fail fast)
if not v2_candidates:
    if candidates:
        print(f"[X] SKIP {region_id}: No v2 files found (had {len(candidates)} non-v2 files)")
    continue  # DON'T include in manifest

# Warn if multiple v2 files exist
if len(v2_candidates) > 1:
    print(f"[!] WARNING {region_id}: Multiple v2 files found:")
    for cf, _ in v2_candidates:
        print(f"    - {cf.name} (modified: {cf.stat().st_mtime})")
    # Pick newest by modification time
    v2_candidates.sort(key=lambda x: x[0].stat().st_mtime, reverse=True)
    print(f"    Selected: {v2_candidates[0][0].name} (newest)")

# Use the v2 file
json_file = v2_candidates[0][0]
json_data = v2_candidates[0][1]
```

### Behavior Summary

| Scenario | Old Behavior | New Behavior |
|----------|-------------|-------------|
| Only v2 file exists | Use it | Use it ✓ |
| Only old file exists | Use it silently | **SKIP with warning** ✓ |
| v2 + old file exist | Use old (alphabetically first) | **Use v2, warn about old** ✓ |
| Multiple v2 files | Use first alphabetically | **Use newest, warn about duplicates** ✓ |
| File lacks version field | Use it silently | **SKIP with warning** ✓ |
| File load fails | Skip silently | **SKIP with error message** ✓ |

## Testing Results

### Before Fix
```
47 regions in manifest
- 25 using old unclipped files (0% None values)
- 2 using v2 files without version field
- 20 using proper v2 files
```

### After Fix
```
46 regions in manifest (1 excluded due to rate limit)
- 0 using old files (all deleted)
- 0 using files without version field (SKIPPED)
- 46 using proper v2 files with version field ✓

Example output:
[!] SKIP new_jersey: new_jersey_old.json (version=None, expected 'export_v2')
[X] SKIP new_jersey: No v2 files found (had 1 non-v2 files)
```

### Verification
```bash
python -c "import json,gzip; d=json.load(gzip.open('generated/regions/new_jersey_srtm_30m_1024px_v2.json.gz')); print('Version:', d.get('version')); flat=[v for row in d['elevation'] for v in row]; print('None values:', sum(1 for v in flat if v is None), f'({100*sum(1 for v in flat if v is None)/len(flat):.2f}%)')"

Output:
Version: export_v2
None values: 256,055 (47.18%)  # Proper clipping!
```

## Key Design Decisions

### Q: Should we fall back to old files if no v2 files exist?

**A: NO. Fail fast instead.**

**Reasoning:**
1. Project philosophy: "NO SILENT FALLBACKS"
2. Old files caused the boundary clipping bug
3. Better to exclude a region than show wrong data
4. Loud warnings help identify issues early

### Q: Should we accept files without version field?

**A: NO. Skip with warning.**

**Reasoning:**
1. Version field is mandatory in v2 format
2. Missing version indicates export bug or old file
3. Enforces format consistency
4. Prevents mixing old and new formats

### Q: How to handle multiple v2 files?

**A: Pick newest, warn loudly.**

**Reasoning:**
1. Shouldn't happen in normal operation (indicates process issue)
2. Newest file is most likely to be correct
3. Loud warning helps catch duplicate file bugs

## Related Changes

### Files Modified
- `src/pipeline.py` - Added `version` field to export (line 739)
- `regenerate_manifest.py` - Strict v2-only selection (lines 76-118)

### Files Cleaned Up
- Deleted 25 old unclipped state files (`pennsylvania.json`, etc.)
- Re-exported New Jersey with fixed export code
- Uintas Wilderness still needs re-export (rate limited)

## Future Improvements

### 1. Add Version Validation to Viewer
```javascript
// viewer-advanced.js
const data = await loadRegionData(filename);
if (data.version !== 'export_v2') {
    console.error(`Invalid data version: ${data.version} (expected export_v2)`);
    // Refuse to load
}
```

### 2. Add Pre-Commit Hook
Check that all JSON files in `generated/regions/` have `version: export_v2` field before allowing commit.

### 3. Add Pipeline Test
Test that export code produces files with all required fields including `version`.

## Lessons Learned

1. **Enforce format requirements at load time, not silently accept anything**
2. **Loud warnings > silent fallbacks** - easier to debug, prevents wrong data
3. **Version fields are mandatory** - enables forward compatibility and validation
4. **Multiple files for same region = bug** - warn loudly to catch process issues
5. **Fail fast philosophy prevents downstream bugs** - better to skip than show wrong data

## Commands for Future Reference

```bash
# Check for files without version field
python -c "import json,gzip,glob; [print(f) for f in glob.glob('generated/regions/*_v2.json.gz') if not json.load(gzip.open(f)).get('version')]"

# Verify all files have proper clipping
python -c "import json,gzip,glob; [(print(f'{f}: {sum(1 for row in (d:=json.load(gzip.open(f)))["elevation"] for v in row if v is None)} None')) for f in glob.glob('generated/regions/*_v2.json.gz')[:5]]"

# Find duplicate files for a region
Get-ChildItem generated\regions\*pennsylvania*.json | Select Name
```

---

**Status**: ✓ Fixed and tested  
**Version**: Viewer v1.367+ includes manifest validation  
**Next**: Re-export uintas_wilderness when rate limit clears

