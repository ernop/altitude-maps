# Commands to Fix All Region Aspect Ratios

## Quick Summary

**Core Principle Violated**: Geographic data must preserve real-world proportions  
**Problem**: States/regions rendering with wrong aspect ratio (Tennessee appearing square instead of wide 5:1)  
**Root Causes**: 
1. Data export kept empty bounding box space (distorted proportions)
2. Viewer applied geographic transformations to already-correct data (double correction)

**Fix**: 
1. Export crops to actual boundaries (preserves proportions)
2. Viewer treats data as simple 2D grid (no reinterpretation)
3. Validation ensures proportions match geographic reality  

---

## Step 1: Check What Needs Fixing

```powershell
# Activate venv
.\venv\Scripts\Activate.ps1

# Scan all regions for aspect ratio issues
python fix_all_regions_aspect_ratio.py --check-only
```

This will show you which regions have incorrect aspect ratios.

---

## Step 2: Fix All Affected Regions

### Option A: Fix Everything Automatically (Recommended)

```powershell
# Fix all regions that have source TIF files available
python fix_all_regions_aspect_ratio.py --fix-all --target-pixels 1024
```

This regenerates all problematic regions from their source TIF files.

### Option B: Fix Specific Regions

```powershell
# Fix one region at a time
python fix_all_regions_aspect_ratio.py --region tennessee --target-pixels 1024
python fix_all_regions_aspect_ratio.py --region kansas --target-pixels 1024
```

---

## Step 3: Handle Missing Source Files

If a region's source TIF is not found, you'll need to re-download it first:

### For US States:

```powershell
# If you have the national USA elevation file
python download_all_us_states.py --states tennessee kansas --max-size 1024

# Or ensure individual states
python ensure_region.py tennessee --target-pixels 1024
```

### For Other Regions:

```powershell
# Ensure international regions
python ensure_region.py <region_id> --target-pixels 1024

# Example for international regions
python ensure_region.py iceland --target-pixels 1024
```

---

## Step 4: Verify the Fix

```powershell
# Check aspect ratios again
python fix_all_regions_aspect_ratio.py --check-only

# Start the viewer to visually verify
python serve_viewer.py
# Open: http://localhost:8001/interactive_viewer_advanced.html
```

---

## What Was Fixed

### Core Principle Applied: Accurate Real-World Representation

**Goal**: Display geographic data with correct proportions (wide states appear wide, tall states appear tall)

### Implementation:

1. **Data Export** (`src/borders.py`):
   - Now crops to actual boundaries (removes empty bounding box space)
   - Preserves real geographic proportions in the output data
   - Tennessee: now exports as wide data (5:1 ratio) not square data

2. **Data Viewer** (`js/viewer-advanced.js`):
   - Now treats input as simple uniform 2D grid (no geographic reinterpretation)
   - Renders the grid as-is without latitude corrections
   - Data already has correct proportions from export, don't "correct" it again

### New Safety Features Added:

1. **`src/validation.py`** - New module with:
   - `validate_aspect_ratio()` - Catches distortion
   - `validate_non_null_coverage()` - Catches bounding box issues
   - `validate_export_data()` - Comprehensive pre-export checks

2. **`src/pipeline.py`** - Added automatic validation to `export_for_viewer()`
   - Exports now fail early if aspect ratio is wrong
   - Clear error messages explain the problem

3. **`fix_all_regions_aspect_ratio.py`** - Tool to find and fix existing bad data

4. **`.cursorrules`** - Updated with critical masking pattern to prevent future mistakes

---

## Safeguards for the Future

### Automatic Validation

Every data export now automatically validates:
-  Aspect ratio matches geographic reality (+/-30% tolerance)
-  Sufficient non-null data coverage (>20%)
-  Clear error messages if validation fails

### Principles Enforced

Two fundamental principles now documented in `.cursorrules`:

**Principle 1**: Preserve real-world proportions
- Export data must maintain geographic aspect ratios
- Crop to actual boundaries, not bounding boxes
- Wide states export as wide data

**Principle 2**: Treat input as uniform 2D grid
- Elevation data is a simple 2D array
- Render as-is without geographic transformations
- Don't reinterpret or "correct" already-correct data

### This Mistake Cannot Happen Again

1. **At export time**: Validation catches aspect ratio issues immediately
2. **In code reviews**: Pattern is documented in `.cursorrules`
3. **For existing data**: `fix_all_regions_aspect_ratio.py` can detect problems

---

## Expected Timeline

**Per region**: ~2-5 minutes (depending on source data availability)

**For all affected regions**: 
- If source TIFs exist: 15-30 minutes total
- If re-downloading needed: 1-2 hours (due to download times)

---

## Troubleshooting

### "Source TIF not found"
Re-download the region first (see Step 3 above)

### "Validation failed"
This is GOOD - it means the safeguard caught a problem. Check the error message for details.

### "Aspect ratio still wrong"
1. Delete cached/intermediate files:
   ```powershell
   Remove-Item data\clipped\srtm_30m\<region>_*
   Remove-Item data\processed\srtm_30m\<region>_*
   ```
2. Re-run the fix command

### Need to regenerate ALL data (nuclear option):
```powershell
# Delete all processed data
Remove-Item -Recurse -Force data\clipped\*
Remove-Item -Recurse -Force data\processed\*
Remove-Item -Recurse -Force generated\regions\*

# Regenerate everything (will take hours)
python fix_all_regions_aspect_ratio.py --fix-all --target-pixels 1024
```

---

## Documentation

See `learnings/ASPECT_RATIO_BOUNDING_BOX_FIX.md` for complete technical details.

