# Cache Management & Data Format Versioning

## The Problem We Solved

**Issue**: Changed data processing format (removed transformations), but old exported JSON files still had the old transformations baked in. This caused inconsistent display between regions.

**Root Cause**: No versioning system to detect when cached/exported data is stale.

---

## Safeguards Implemented

### 1. **Format Versioning**

#### In Export Script (`export_for_web_viewer.py`)
```python
DATA_FORMAT_VERSION = 2  # Increment when changing transformations/structure
```

Every exported JSON now includes:
```json
{
  "format_version": 2,
  "exported_at": "2025-10-22T10:30:00Z",
  "source_file": "japan.tif",
  "orientation": {
    "description": "Natural GeoTIFF orientation",
    "transformations": "None"
  },
  ...
}
```

**Format History**:
- **v2** (2025-10-22): Natural GeoTIFF orientation, no transformations
- **v1** (legacy): Had `fliplr()` + `rot90()` transformations (DEPRECATED)

#### In Viewer (`interactive_viewer_advanced.html`)
```javascript
const EXPECTED_FORMAT_VERSION = 2;

// Validates on load and shows clear error if mismatch
if (data.format_version !== EXPECTED_FORMAT_VERSION) {
  throw new Error("Data format mismatch! Please re-export...");
}
```

**Result**: If you try to load old data with new code, you get an immediate, clear error message.

---

### 2. **Cache Clearing Utility**

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

### 3. **Orientation Diagnostic Tool**

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

### 4. **Documentation in `.cursorrules`**

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

1. **Make your changes** to data processing code
   ```python
   # Example: Change how elevation data is transformed
   elevation_viz = some_new_transformation(elevation)
   ```

2. **Update format version** in `export_for_web_viewer.py`
   ```python
   DATA_FORMAT_VERSION = 3  # Was 2, now 3
   ```

3. **Document the change** in format history
   ```python
   """
   FORMAT VERSION HISTORY:
   - v3 (2025-XX-XX): [Describe what changed]
   - v2 (2025-10-22): Natural GeoTIFF orientation, no transformations
   - v1 (legacy): Had fliplr() + rot90() transformations (DEPRECATED)
   """
   ```

4. **Clear all caches**
   ```powershell
   python clear_caches.py
   ```

5. **Re-export all data**
   ```powershell
   # Default data
   python export_for_web_viewer.py
   
   # All regions
   python download_regions.py  # Or manually export each
   ```

6. **Test with multiple regions** to ensure consistency
   ```powershell
   python serve_viewer.py
   # Load USA, Japan, California, etc. - verify all look correct
   ```

7. **Commit changes** with clear description
   ```bash
   git add .
   git commit -m "Change data format to [describe]: bump to v3, re-exported all data"
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

# Re-export single file
python export_for_web_viewer.py data/your_file.tif -o generated/your_file.json

# View in browser
python serve_viewer.py
```

### File Locations
- **Export script**: `export_for_web_viewer.py`
- **Viewer**: `interactive_viewer_advanced.html`
- **Data processing**: `src/data_processing.py`
- **Cache utility**: `clear_caches.py`
- **Diagnostic**: `check_geotiff_orientation.py`

### Key Constants
- **Python**: `DATA_FORMAT_VERSION` in `export_for_web_viewer.py`
- **JavaScript**: `EXPECTED_FORMAT_VERSION` in `interactive_viewer_advanced.html`
- **Must match**: Both must be the same for data to load

---

## Future Improvements

Potential enhancements:
- [ ] Auto-detect stale cache based on source file modification time
- [ ] Hash-based cache validation
- [ ] Automatic re-export on version mismatch (with user confirmation)
- [ ] Cache statistics (size, age, hit rate)
- [ ] Migration scripts for backward compatibility

