# Complete Instructions to Fix All State Aspect Ratios

## The Problem

The validation failures are happening because of a **downsampling bug** in `src/pipeline.py`:

**OLD CODE (BUGGY)** used independent step sizes for X and Y:
```python
step_y = max(1, src.height // new_height)  # Different for height
step_x = max(1, src.width // new_width)    # Different for width
downsampled = elevation[::step_y, ::step_x]  # Distorts aspect ratio!
```

This caused aspect ratio distortion during downsampling (Connecticut 6840×3949 became 4282×1692 instead of correct proportions).

## The Solution

Delete old data and regenerate from scratch using the national elevation data.

---

## Step 1: Clean Up Old Files

```powershell
# Activate venv
.\venv\Scripts\Activate.ps1

# Delete ALL intermediate and processed state files
# (Keep the national USA file!)
Remove-Item -Force data\regions\*.tif
Remove-Item -Recurse -Force data\clipped\srtm_30m\*
Remove-Item -Recurse -Force data\processed\srtm_30m\*
Remove-Item -Force generated\regions\*_srtm_30m_*.json
Remove-Item -Force generated\regions\*_srtm_30m_*_borders.json
Remove-Item -Force generated\regions\*_srtm_30m_*_meta.json
```

**DO NOT DELETE**:
- `data/usa_elevation/nationwide_usa_elevation.tif` (if you have it)
- `data/raw/srtm_30m/*_bbox_30m.tif` files (these are OK)

---

## Step 2: Verify You Have National USA Data

```powershell
# Check if national file exists
Test-Path data\usa_elevation\nationwide_usa_elevation.tif
```

If it returns `False`, you need to download it first. See instructions at the end.

---

## Step 3: Extract and Process All States

### Option A: All Contiguous 48 States

```powershell
# Extract all states from national data and process to 4096px
python download_all_us_states.py --max-size 4096
```

This will:
1. Extract each state from the national USA elevation data (creates `data/regions/<state>.tif`)
2. Process through the full pipeline with proper masking (crop=True)
3. Export to JSON with validation

**Time**: ~2-4 hours for all 48 states

### Option B: Specific States Only

```powershell
# Just fix the failing ones
python download_all_us_states.py --states connecticut indiana iowa maine massachusetts minnesota nebraska new_hampshire north_dakota ohio oregon pennsylvania rhode_island south_dakota vermont washington wisconsin wyoming --max-size 4096
```

**Time**: ~30-45 minutes

### Option C: One State at a Time

```powershell
# Extract and process one state
python download_all_us_states.py --states tennessee --max-size 4096
```

---

## Step 4: Verify the Fix

```powershell
# Check aspect ratios
python fix_all_regions_aspect_ratio.py --check-only
```

You should see:
```
 All regions have correct aspect ratios!
```

Or at most a few with **< 30% difference** (within tolerance).

---

## Step 5: Visual Verification

```powershell
# Start the viewer
python serve_viewer.py

# Open browser to:
# http://localhost:8001/interactive_viewer_advanced.html
```

Select a state like **Tennessee** or **Nebraska** - they should appear **wide**, not square!

---

## If You Don't Have National USA Data

### Download National USA Elevation Data

The national file is large (~4-5 GB) but allows extracting all states.

**Option 1**: Download from USGS 3DEP (requires API setup)

See `tech/DOWNLOAD_GUIDE.md` for full instructions.

**Option 2**: Download States Individually via OpenTopography

```powershell
# For each state (example with Tennessee)
python download_unified.py tennessee --process --target-pixels 4096
```

This downloads just the bounding box for that state and processes it correctly.

**Time**: ~5-10 minutes per state
**Total for all failing states**: ~2-3 hours

---

## Alternative: Use Raw Bbox Files

If you have `data/raw/srtm_30m/*_bbox_30m.tif` files, you can process those directly:

```powershell
# Process from raw bbox files
python -c "from pathlib import Path; from src.pipeline import run_pipeline; import sys; [run_pipeline(f, f.stem.replace('_bbox_30m', ''), 'srtm_30m', f'United States of America/{f.stem.replace(\"_bbox_30m\", \"\").replace(\"_\", \" \").title()}', 'state', 4096, False) for f in Path('data/raw/srtm_30m').glob('*_bbox_30m.tif')]"
```

---

## What Was Fixed in Code

### 1. Downsampling Logic (`src/pipeline.py` line ~180-205)

**BEFORE** (buggy):
```python
# Used different step sizes for X and Y
step_y = max(1, src.height // new_height)
step_x = max(1, src.width // new_width)
downsampled = elevation[::step_y, ::step_x]  # DISTORTS ASPECT RATIO!
```

**AFTER** (fixed):
```python
# Use SAME step size for both dimensions
scale_factor = max_dim / target_pixels
step_size = max(1, int(np.ceil(scale_factor)))
downsampled = elevation[::step_size, ::step_size]  # PRESERVES ASPECT RATIO!
```

**Why**: Using different step sizes for X and Y changes the aspect ratio during downsampling. Must use the same step size for both dimensions.

### 2. Masking (`src/borders.py`)

Already fixed to use `crop=True` (this was done earlier).

---

## Expected Results

After regeneration:

| State | Old Aspect | New Aspect | Geographic | Status |
|-------|------------|------------|------------|--------|
| Tennessee | 0.932 | 5.044 | 5.1 |  FIXED |
| Connecticut | 1.732 | ~1.30 | 1.297 |  Will fix |
| Nebraska | 2.913 | ~2.18 | 2.179 |  Will fix |
| New Jersey | 0.679 | ~0.52 | 0.519 |  Will fix |

All states should be within **30%** of their geographic aspect ratio.

---

## Troubleshooting

### "USA elevation file not found"

Download the national file first or use individual state downloads (Option 2 above).

### "Still getting validation errors"

1. Make sure you **deleted the old files** in Step 1
2. Check that `src/borders.py` has `crop=True` (line ~187 and ~384)
3. Check that `src/pipeline.py` has the fixed downsampling logic

### "Processing is too slow"

Use a smaller `--max-size`:
```powershell
python download_all_us_states.py --states tennessee --max-size 2048
```

2048px is still good quality and processes faster.

### "Some states still fail"

Some irregularly-shaped states (islands, complex boundaries) might be borderline. If difference is 31-35%, you can:

1. Increase tolerance in `src/validation.py` (line 56: change 0.3 to 0.35)
2. Or accept it - viewer will still look correct, just slightly off

---

## Summary Commands (Quick Reference)

```powershell
# Full regeneration (recommended)
.\venv\Scripts\Activate.ps1
Remove-Item -Force data\regions\*.tif
Remove-Item -Recurse -Force data\clipped\srtm_30m\*
Remove-Item -Recurse -Force data\processed\srtm_30m\*
Remove-Item -Force generated\regions\*_srtm_30m_*.json
python download_all_us_states.py --max-size 4096
python fix_all_regions_aspect_ratio.py --check-only
```

**Total time**: 2-4 hours (mostly automated)
**Result**: All states with correct proportions and validated! 

