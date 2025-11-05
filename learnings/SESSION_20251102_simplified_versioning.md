# Session: Simplified Versioning - Filename-Based Approach

**Date**: November 2, 2025  
**Change**: Removed redundant in-file version tracking, rely on filenames

---

## What Changed

**Removed unnecessary complexity:**
- No more `format_version: 2` field inside JSON files
- No more `exported_at` timestamps inside JSON files
- Version is now tracked solely in filename: `ohio_srtm_30m_2048px_v2.json`

**Rationale:**
- **Duplication**: Version was in both filename AND file content
- **Existing systems**: Already have filename patterns, manifest, metadata tracking
- **Strict policy**: "Never patchwork" - we regenerate ALL files on format changes anyway
- **Simpler is better**: One source of truth (filename) is cleaner

---

## How It Works Now

### Version Tracking

**Filename IS the version:**
```
ohio_srtm_30m_2048px_v2.json  ← Version 2 format
ohio_srtm_30m_2048px_v3.json  ← Version 3 format (if format changes)
```

**File content is simpler:**
```json
{
  "region_id": "ohio",
  "source": "srtm_30m",
  "name": "Ohio",
  "width": 888,
  "height": 834,
  "elevation": [[...]],
  "bounds": {...},
  "stats": {...}
}
```

**Manifest is simpler:**
```json
{
  "regions": {
    "ohio": {
      "name": "Ohio",
      "file": "ohio_srtm_30m_2048px_v2.json",
      ...
    }
  }
}
```

**Frontend extracts version from filename:**
```javascript
// In js/viewer-advanced.js
const versionMatch = filename.match(/_v(\d+)\.json/);
const fileVersion = versionMatch ? versionMatch[1] : 'unknown';
appendActivityLog(`[OK] Data format v${fileVersion} from filename`);
```

### No In-File Version Tracking

- NO `version` field in exported JSON files
- NO `version` field in manifest
- Version is ONLY in the filename (e.g., `_v2.json`)
- Backend pipeline versioning handled by metadata files (separate from exports)

---

## Files Changed

1. **src/pipeline.py**:
   - Removed ALL version fields from exports
   - Removed version field from manifest
   - Exports now have only essential data fields

2. **js/viewer-advanced.js**:
   - Removed `EXPECTED_FORMAT_VERSION` constant
   - Removed format version validation logic
   - Added filename-based version extraction for logging

3. **src/data_types.py**:
   - Updated `ViewerElevationData` dataclass to match actual format
   - Removed `format_version` and `exported_at` fields
   - Added note about filename-based versioning

4. **src/status.py**:
   - Simplified `check_export_version()` to check filename patterns
   - No longer reads version field from inside files

5. **learnings/CACHE_AND_VERSIONING.md**:
   - Updated to document filename-based approach
   - Removed references to in-file version fields
   - Emphasized strict regeneration policy

---

## When Format Changes

**Simple workflow:**

1. Change data processing code
2. Update filename pattern: `_v2.json` → `_v3.json`
3. Update `EXPORT_VERSION` in `src/versioning.py`
4. Clear caches: `python clear_caches.py`
5. Regenerate ALL regions with new filenames
6. Delete old `_v2.json` files after confirming v3 works

**No need to:**
- Update in-file version numbers
- Patch existing files
- Validate version fields at runtime

---

## Why This Is Better

**Simpler:**
- One version number to track (in filename)
- No duplication between filename and file content
- Less code to maintain

**More reliable:**
- Filesystem prevents mixing versions naturally
- Can't accidentally serve wrong format with right filename
- Manifest tracks what files exist

**Aligned with philosophy:**
- "Never patchwork" - we regenerate everything anyway
- Existing systems already work (filename patterns, manifest, metadata)
- Don't add complexity without clear need

---

## What We Keep

**Still have robust version tracking:**
- **Filenames**: `<region>_<source>_<pixels>px_v2.json` (format version)
- **Backend versioning**: `src/versioning.py` (pipeline stage versions)
- **Manifest**: `regions_manifest.json` (what files exist)
- **Metadata**: Hash-based validation in `data/metadata/`

**These systems are sufficient for:**
- Detecting stale caches
- Invalidating old data
- Ensuring consistency
- Tracking what's been generated

---

## Verification

Tested with alcatraz region:

```bash
# Regenerated without ANY version fields
python ensure_region.py alcatraz --force-reprocess

# Verified structure
Get-Content generated/regions/alcatraz_usa_3dep_2048px_v2.json | ConvertFrom-Json
# Result: Has region_id, source, name, width, height, elevation, bounds, stats
#         Does NOT have ANY version fields

# Manifest also has no version field
Get-Content generated/regions/regions_manifest.json | ConvertFrom-Json
# Result: Just has "regions" dict, no version field

# Frontend extracts version from filename
# Console shows: "[OK] Data format v2 from filename"
```

✅ No warnings
✅ Cleaner exports (no redundant fields)
✅ Frontend handles correctly
✅ Version visible in logs from filename

---

## Bottom Line

**Before**: Version in filename AND file content (duplication)
**After**: Version in filename only (single source of truth)

**Cleanup**: Removed ALL in-file version tracking - exports, manifest, everything

**Result**: Radically simpler system that works better, aligned with existing patterns and project philosophy of "never patchwork, never hack together".

