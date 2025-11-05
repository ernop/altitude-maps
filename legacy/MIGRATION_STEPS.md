# Migration to Abstract Naming - Next Steps

## Overview
Migrating from region_id-based filenames to abstract bounds-based filenames for all data files.

## Current Status
- Dry-run completed: 73 files ready to migrate
- 110 files skipped (expected - metadata, intermediate, legacy files)

---

## Step-by-Step Migration

### Step 1: Review Dry-Run Results (Already Done)
✅ Confirmed 73 files ready for migration (raw, clipped, processed, exported)
✅ Confirmed skipped files are expected (metadata, reproj intermediates, tiles)

### Step 2: Backup (Optional but Recommended)
```powershell
# Optional: Create backup of generated files (if you want safety net)
# The migration script only renames files (doesn't delete), but backup is safe
Copy-Item -Recurse generated\regions generated\regions_backup
```

### Step 3: Execute Migration
```powershell
python migrate_to_abstract_naming.py --execute
```

This will:
- Rename 73 files from old naming to abstract bounds-based naming
- Skip metadata/intermediate files (expected)
- Report results

**Expected output**: Similar to dry-run, but files will actually be renamed.

### Step 4: Verify Migration
```powershell
# Check that files were renamed successfully
ls generated\regions\bbox_*.json
ls data\raw\srtm_30m\bbox_*.tif
ls data\processed\srtm_30m\bbox_*.tif

# Verify a specific region still works
python ensure_region.py utah --check-only
```

### Step 5: Update Code to Remove Backward Compatibility
After migration, we can remove the old filename checks:

**Files to update:**
1. `ensure_region.py` - Remove old filename checks in `find_raw_file()`
2. `ensure_region.py` - Remove old filename checks in `check_pipeline_complete()`
3. `ensure_region.py` - Remove old filename checks in other lookup functions

**What gets removed:**
- Lines checking for `{region_id}_bbox_30m.tif`
- Lines checking for `{region_id}_3dep_10m.tif`
- Lines checking for `{region_id}_clipped_*.tif`
- Lines checking for `{region_id}_*_*px_v2.tif`
- Lines checking for `{region_id}_*.json`

**What stays:**
- All abstract bounds-based filename generation
- All bounds-based file lookup

### Step 6: Test After Migration
```powershell
# Test that a region still loads correctly
python serve_viewer.py
# Then select a migrated region (e.g., utah) and verify it loads

# Test that pipeline still works
python ensure_region.py utah --check-only
```

### Step 7: Clean Up (Optional)
After confirming everything works, you can optionally remove:
- Old legacy JSON files (`{region}.json` without `_px_v2`)
- Backup directory if created

---

## What Gets Migrated

### Files That Will Be Renamed:
1. **Raw files**: `{region_id}_bbox_30m.tif` → `bbox_{bounds}_srtm_30m_30m.tif`
2. **Clipped files**: `{region_id}_clipped_{source}_v1.tif` → `bbox_{bounds}_{source}_clipped_{hash}_v1.tif`
3. **Processed files**: `{region_id}_{source}_{pixels}px_v2.tif` → `bbox_{bounds}_{source}_processed_{pixels}px_v2.tif`
4. **Exported JSON**: `{region_id}_{source}_{pixels}px_v2.json` → `bbox_{bounds}_{source}_{pixels}px_v2.json`

### Files That Will Be Skipped (Expected):
- `_meta.json` files (metadata)
- `_reproj.tif` files (intermediate, will be regenerated)
- `tile_*.tif` files (already using abstract naming)
- `turkiye_tile_*.tif` (custom format)
- `regions_manifest.json` (special file)
- `{region}.json` without `_px_v2` (legacy files)

---

## Rollback Plan

If something goes wrong:
1. The migration script uses `rename()` - files are moved, not deleted
2. Old files become new files (can't easily undo)
3. Solution: Re-run `ensure_region.py` with `--force-reprocess` to regenerate from raw files
4. Raw files are preserved (never modified), so everything can be regenerated

---

## After Migration

Once migration is complete and verified:

1. **Remove backward compatibility checks** (will make code cleaner)
2. **Update manifest** if needed (should auto-update on next processing)
3. **Document the change** (already in abstract naming docs)

---

## Ready to Proceed?

If everything looks good from the dry-run, run:

```powershell
python migrate_to_abstract_naming.py --execute
```

Then verify and let me know if you want me to remove the backward compatibility checks!

