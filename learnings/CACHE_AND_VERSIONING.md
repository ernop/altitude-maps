# Cache Management & Data Format Versioning

## The Problem We Solved

**Issue**: Changed data processing format (removed transformations), but old exported JSON files still had the old transformations baked in. This caused inconsistent display between regions.

**Root Cause**: No versioning system to detect when cached/exported data is stale.

**Solution**: Filename-based versioning + strict regeneration policy

---

## Versioning Strategy

### Filename-Based Versioning

**Format versions are encoded in filenames:**
- `ohio_srtm_30m_2048px_v2.json` - Version 2 format
- `ohio_srtm_30m_2048px_v3.json` - Version 3 format (if we change format)

**Why filenames?**
- Single source of truth
- No duplication (version isn't also inside the file)
- Easy to see what version a file is
- Filesystem naturally prevents mixing versions
- Works with existing manifest system

**Version History**:
- **v2** (2025-10-22): Natural GeoTIFF orientation, no transformations
- **v1** (legacy): Had `fliplr()` + `rot90()` transformations (DEPRECATED)

### Strict Regeneration Policy

**"Never patchwork, never hack together"**

When format changes:
1. Bump version in filename pattern (v2 → v3)
2. Regenerate ALL region files with new version
3. Never mix old and new format files
4. Delete old version files after confirming new ones work

This ensures consistency across all regions.

---

## Safeguards Implemented

### 1. **Cache Clearing Utility**

Created `clear_caches.py` to safely clear all cached/generated data:

```powershell
# Interactive (asks for confirmation)
python clear_caches.py

# Non-interactive
python clear_caches.py --yes
```

**What it clears**:
- `data/.cache/` - Masked/bordered raster data (pickled)
- `generated/` - Exported JSON for web viewer
- `generated/regions/` - Per-region exported data

**When to use**:
- After changing data processing format
- When debugging data inconsistencies
- When switching data sources
- To ensure a clean slate

---

### 2. **Orientation Diagnostic Tool**

Created `check_geotiff_orientation.py` to verify GeoTIFF orientation:

```powershell
python check_geotiff_orientation.py data/your_file.tif
```

**What it checks**:
- Affine transform matrix components
- Whether columns increase East (standard) or West (flipped)
- Whether rows increase South (standard) or North (flipped)
- Corner pixel geographic coordinates
- Recommends transformations needed (if any)

**Output Example**:
```
DATA ORIENTATION:
   [OK] Columns increase EASTWARD (standard)
   [OK] Rows increase SOUTHWARD (standard)
   [OK] Image is north-up (no rotation)
   
   [OK] STANDARD ORIENTATION - Use data as-is:
   - data[0, 0] is NORTHWEST corner
   - Increasing row -> South
   - Increasing col -> East
   - NO TRANSFORMATION NEEDED
```

---

### 3. **Documentation in `.cursorrules`**

Added a dedicated section on cache invalidation:

```
 **CRITICAL**: When changing data processing/export format:
1. Update the format version number in export scripts
2. Add version validation on data load (fail if version mismatch)
3. Document the change in code comments
4. Re-export ALL cached/generated data - don't mix old and new formats
5. Test with multiple regions to ensure consistency
```

---

## Workflow: Changing Data Format

### Step-by-Step Process

1. **Make your changes** to data processing code in `src/pipeline.py`
   ```python
   # Example: Change how elevation data is transformed
   elevation_viz = some_new_transformation(elevation)
   ```

2. **Update filename version pattern** throughout codebase
   - Search for: `_v2.json`
   - Replace with: `_v3.json`
   - Update in: `src/pipeline.py`, filename generation logic

3. **Update version history** in `src/versioning.py`
   ```python
   EXPORT_VERSION = "export_v3"  # Was export_v2
   
   VERSION_HISTORY = {
       ...
       "export_v3": {
           "date": "2025-XX-XX",
           "changes": "[Describe what changed]",
           "breaking": True,
           "incompatible_with": ["export_v2", "export_v1"]
       }
   }
   ```

4. **Clear all caches**
   ```powershell
   python clear_caches.py
   ```

5. **Regenerate ALL regions** with new format
   ```powershell
   # Regenerate all regions - ensures consistency
   # For each region:
   python ensure_region.py <region_id> --force-reprocess
   ```

6. **Delete old v2 files** after confirming v3 works
   ```powershell
   Remove-Item generated/regions/*_v2.json
   Remove-Item generated/regions/*_v2.json.gz
   ```

7. **Test with multiple regions** to ensure consistency
   ```powershell
   python serve_viewer.py
   # Visit http://localhost:8001
   # Load multiple regions - verify all look correct
   ```

8. **Commit changes** with clear description
   ```bash
   git add .
   git commit -m "Change data format to [describe]: bump to v3, regenerated all data"
   ```

---

## General Best Practices

### Cache Invalidation Strategy

**Rule of Thumb**: When in doubt, clear and re-export!

**Always clear caches when**:
- Changing array transformations (flip, rotate, transpose)
- Changing coordinate systems or projections
- Changing aggregation methods (max, mean, median)
- Changing masking/cropping logic
- Upgrading major libraries (numpy, rasterio, gdal)

**Maybe clear caches when**:
- Changing visualization parameters (these usually don't affect exported data)
- Changing UI/rendering code (viewer-only changes)
- Adding new features that don't touch existing data

### Version Numbering

**Increment version when**:
- Data structure changes (new fields, removed fields)
- Coordinate/orientation changes
- Transformation logic changes
- Any change that makes old data incompatible

**Don't increment for**:
- Bug fixes that don't change output
- Performance improvements (same result, faster)
- Documentation updates
- Adding optional metadata fields

### Testing

After any format change:
1.  Export at least 2 different regions
2.  Load both in viewer
3.  Verify compass orientation matches expected N/S/E/W
4.  Check that recognizable geographic features are in correct positions
5.  Verify version numbers in browser console

---

## Quick Reference

### Commands
```powershell
# Check if GeoTIFF needs transformations
python check_geotiff_orientation.py data/your_file.tif

# Clear all caches
python clear_caches.py

# Regenerate single region
python ensure_region.py <region_id> --force-reprocess

# Regenerate multiple regions
python ensure_region.py ohio kentucky tennessee --force-reprocess

# View in browser
python serve_viewer.py
# Then visit: http://localhost:8001/interactive_viewer_advanced.html
```

### File Locations
- **Export pipeline**: `src/pipeline.py` (export_for_viewer function)
- **Viewer**: `interactive_viewer_advanced.html` and `js/viewer-advanced.js`
- **Versioning system**: `src/versioning.py` (backend pipeline tracking)
- **Cache utility**: `clear_caches.py`
- **Diagnostic**: `check_geotiff_orientation.py`

### Version Tracking
- **Filenames**: `<region>_<source>_<pixels>px_v2.json` (v2 is the version)
- **Backend**: `EXPORT_VERSION = "export_v2"` in `src/versioning.py`
- **No in-file version field** - filename is the source of truth

---

## Future Improvements

Potential enhancements:
- [ ] Auto-detect stale cache based on source file modification time
- [ ] Hash-based cache validation
- [ ] Automatic re-export on version mismatch (with user confirmation)
- [ ] Cache statistics (size, age, hit rate)
- [ ] Migration scripts for backward compatibility

