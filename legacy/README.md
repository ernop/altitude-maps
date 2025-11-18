# Legacy Documentation - Historical Reference Only

This folder contains documentation about completed migrations and one-time transformations that were performed on the codebase. All executable scripts have been removed as they are no longer needed.

**Note**: All knowledge from these migrations has been captured in `.cursorrules` and `tech/` documentation.

## Completed Migrations

### Abstract Naming Migration (Completed)
**Purpose**: Migrated files from region_id-based naming to abstract bounds-based naming.

**Status**: ✓ Completed - Migration script has been removed.

**What was done**: 
- Scanned for old region_id-based files (e.g., `utah_bbox_30m.tif`)
- Renamed them to abstract bounds-based naming (e.g., `bbox_N37_W114_N42_W109_srtm_30m_30m.tif`)
- Covered raw, clipped, processed, and exported files

**Knowledge preserved in**: 
- `.cursorrules` (File Naming Philosophy section)
- `tech/TECHNICAL_REFERENCE.md` (naming conventions)
- `legacy/MIGRATION_STEPS.md` (detailed migration steps)

## Completed One-Off Tasks

### Emoji Removal Cleanup (Completed)
**Status**: ✓ Completed - Cleanup script has been removed.

**What was done**: Scanned markdown, Python, JavaScript, and other text files to find and remove emoji characters.

**Knowledge preserved in**: `.cursorrules` (ABSOLUTE RULE: NEVER use emojis)

### Region Name Fixes (Completed)
**Status**: ✓ Completed - Fix script has been removed.

**What was done**: Fixed incorrectly swapped region display names in exported JSON files.

**Knowledge preserved in**: Region names now centrally managed in `src/region_config.py`

### Deployment Script Updates (Completed)
**Status**: ✓ Completed - All obsolete scripts have been removed.

**Replaced by**: 
- `deploy.ps1` (PowerShell, Windows)
- `deploy.sh` (Bash, Linux/Mac)

**Knowledge preserved in**: 
- `tech/DEPLOYMENT_GUIDE.md`
- `.cursorrules` (Production Deployment section)

### Border Functionality Testing (Completed)
**Status**: ✓ Completed - Test scripts have been removed.

**What was done**: Tested BorderManager imports, Natural Earth border loading, and `.htaccess` configurations.

**Knowledge preserved in**: 
- Border functionality tested in normal pipeline (`src/pipeline.py`)
- `.htaccess` configuration documented in `tech/PRODUCTION_COMPRESSION_SETUP.md`

---

## What Happened to the Scripts?

All executable scripts have been **deleted** as they are no longer needed:
- One-time migrations have been completed
- Knowledge has been captured in documentation
- Defensive import patterns have been removed (violates project coding standards)
- Test functionality has been integrated into the main pipeline

Only documentation files remain for historical reference.

## Why Keep This Folder?

This folder preserves:
1. **Migration history**: Understanding how the project evolved (naming conventions, etc.)
2. **Lessons learned**: What issues were encountered and how they were solved
3. **Context for future work**: Reference for similar migrations or transformations

## Related Active Files

For current functionality, see:
- **Version management**: `bump_version.py`
- **Deployment**: `deploy.ps1`, `deploy.sh`, `DEPLOY_README.md`
- **Region management**: `src/region_config.py`, `ensure_region.py`
- **Pipeline**: `src/pipeline.py`, `ensure_region.py`
- **Documentation**: `.cursorrules`, `tech/` folder


