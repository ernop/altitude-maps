# Legacy Files - One-Off Transformation Scripts and Completed Migrations

This folder contains one-off scripts and completed migration utilities that are no longer actively used but are preserved for historical reference.

## Migration Scripts (Completed)

### `migrate_to_abstract_naming.py`
**Purpose**: One-time migration script to rename files from region_id-based naming to abstract bounds-based naming.

**Status**: Migration completed. The codebase now uses abstract bounds-based naming exclusively.

**What it did**: 
- Scanned for old region_id-based files (e.g., `utah_bbox_30m.tif`)
- Renamed them to abstract bounds-based naming (e.g., `bbox_N37_W114_N42_W109_srtm_30m_30m.tif`)
- Covered raw, clipped, processed, and exported files

**Knowledge preserved in**: 
- `.cursorrules` (File Naming Philosophy section)
- `tech/TECHNICAL_REFERENCE.md` (naming conventions)

### `MIGRATION_STEPS.md`
**Purpose**: Step-by-step migration guide for the abstract naming migration.

**Status**: Migration completed.

**Knowledge preserved in**: `.cursorrules` (File Naming Philosophy: Abstract vs Specific section)

## One-Off Utility Scripts (Completed)

### `remove_emojis.py`
**Purpose**: One-off script to remove emojis from documentation and code files.

**Status**: Cleanup completed. Project now enforces no emojis in documentation (absolute rule in `.cursorrules`).

**What it did**: Scanned markdown, Python, JavaScript, and other text files to find and remove emoji characters.

**Knowledge preserved in**: `.cursorrules` (ABSOLUTE RULE: NEVER use emojis)

### `update_region_names.py`
**Purpose**: One-off fix script for swapping "peninsula" and "san_mateo" region names in JSON exports.

**Status**: Fix completed. Region names now correctly managed via `src/regions_config.py`.

**What it did**: Fixed incorrectly swapped region display names in exported JSON files.

**Knowledge preserved in**: Region names now centrally managed in `src/regions_config.py`

## Obsolete Deployment Scripts

### `deploy_production.py`
**Purpose**: Older deployment script that prepared files for deployment.

**Status**: Replaced by `deploy.ps1` and `deploy.sh` which are more comprehensive and handle rsync directly.

**Replaced by**: 
- `deploy.ps1` (PowerShell, Windows)
- `deploy.sh` (Bash, Linux/Mac)

**Knowledge preserved in**: 
- `tech/DEPLOYMENT_GUIDE.md`
- `.cursorrules` (Production Deployment section)

### `deploy_htaccess.py`
**Purpose**: One-off script to deploy `.htaccess` file to production server for gzip compression.

**Status**: Deployment completed. `.htaccess` configuration is now part of standard deployment.

**What it did**: Deployed `.htaccess` file to enable gzip compression for JSON files on Dreamhost.

**Knowledge preserved in**: `tech/PRODUCTION_COMPRESSION_SETUP.md`

## Temporary Test Scripts

### `test_site_status.py`
**Purpose**: Quick test script to verify site accessibility (check for 500 errors).

**Status**: One-off diagnostic script, no longer needed.

**What it did**: Tested if site loads without HTTP 500 errors (useful for diagnosing `.htaccess` issues).

### `test_htaccess_features.py`
**Purpose**: Interactive test script for different `.htaccess` configurations on Dreamhost.

**Status**: One-off diagnostic script used during `.htaccess` setup.

**What it did**: Tested different `.htaccess` configurations incrementally to identify which features work on Dreamhost hosting.

**Knowledge preserved in**: `tech/PRODUCTION_COMPRESSION_SETUP.md`

### `test_borders.py`
**Purpose**: Test script for border functionality (imports, loading, Natural Earth borders).

**Status**: Temporary diagnostic script. Border functionality is tested as part of normal pipeline.

**What it did**: Tested BorderManager imports, instantiation, and Natural Earth border loading.

---

## Why These Files Are Preserved

These files are kept for historical reference and to understand:
1. **Migration history**: How the project evolved (e.g., naming convention migration)
2. **One-off fixes**: What issues were encountered and how they were solved
3. **Deployment evolution**: How deployment processes improved over time

## When It's Safe to Delete

These files can be safely deleted if:
- You're certain all knowledge is captured in documentation
- You don't need historical reference for similar future tasks
- You want to reduce repository size (though these are small text files)

## Related Active Files

For current functionality, see:
- **Version management**: `bump_version.py`, `update_version.py`
- **Deployment**: `deploy.ps1`, `deploy.sh`
- **Region management**: `src/regions_config.py`, `ensure_region.py`
- **Testing**: Normal pipeline testing in `ensure_region.py` and `src/pipeline.py`

