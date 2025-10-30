# US State Data Audit & Fixing Guide

## Problem Overview

US state regions were exported with two critical issues:

1. **Aspect Ratio Distortion** - Independent step sizes during downsampling distorted rectangular states into squares
2. **Wrong Borders** - Country-level borders (entire USA) shown instead of state-specific outlines

## Root Causes

### Broken Downsampling (Pre-Fix)
```python
# OLD CODE (caused distortion):
step_y = max(1, height // max_size)
step_x = max(1, width // max_size)
elevation = elevation[::step_y, ::step_x]
```

This caused states with different width/height to get squeezed or stretched.

### Missing State Borders
All states exported with country-level borders showing entire USA outline instead of individual state shapes.

## Fixed Code

### Aspect-Preserving Downsampling
```python
# NEW CODE (preserves aspect):
scale_factor = max(height / max_size, width / max_size)
step_size = max(1, int(scale_factor))
elevation = elevation[::step_size, ::step_size]
```

### Validation Added
Both `download_regions.py` and `src/pipeline.py` now validate aspect ratio before export:
```python
export_aspect = width / height
if abs(export_aspect - source_aspect) > 0.01:
    raise ValueError("Aspect ratio not preserved!")
```

## Audit Results (Oct 28, 2025)

**Total US States:** 50
- **No source TIF:** 22 (not yet downloaded)
- **Correct:** 2 (Nebraska, Nevada - recently fixed)
- **Need aspect fix:** 23 states
- **Need border fix:** 26 states
- **Total needing fixes:** 26 states

### States with Major Distortion (>50% error)

| State | Expected Aspect | Exported Aspect | Error | Status |
|-------|----------------|-----------------|-------|--------|
| Kansas | 2.478 | 0.976 | 61% | Bad |
| Oklahoma | 2.536 | 1.000 | 61% | Bad |
| Maryland | 2.453 | 1.033 | 58% | Bad |
| North Dakota | 2.451 | 0.966 | 61% | Bad |
| Pennsylvania | 2.286 | 0.968 | 58% | Bad |
| Washington | 2.259 | 0.968 | 57% | Bad |
| Massachusetts | 2.170 | 0.949 | 56% | Bad |
| South Dakota | 2.196 | 0.969 | 56% | Bad |
| Iowa | 2.083 | 1.005 | 52% | Bad |
| Oregon | 1.886 | 0.995 | 47% | Bad |
| Connecticut | 1.764 | 0.882 | 50% | Bad |
| Colorado | 1.751 | 1.017 | 42% | Bad |
| Wyoming | 1.744 | 1.014 | 42% | Bad |

### States Corrected

| State | Before | After | Status |
|-------|--------|-------|--------|
| Nebraska | 807x831 (0.971) | 807x277 (2.913) |  Fixed |
| Nevada | 827x813 (1.017) | 694x813 (0.854) |  Fixed |
| Delaware | 888x834 (1.065) | 444x834 (0.532) |  Fixed |

## How to Use Fix Utility

### Audit All States
```bash
python fix_all_states.py --audit
```

Shows which states need fixing and what issues they have.

### Fix Specific States
```bash
python fix_all_states.py --fix delaware florida california
```

Re-exports elevation and borders for named states.

### Fix All Bad States
```bash
python fix_all_states.py --fix-all
```

Automatically fixes all states that failed the audit.

### Force Re-export (Even if Correct)
```bash
python fix_all_states.py --fix delaware --force
```

Useful for regenerating with different settings.

## Validation Checklist

For each state, verify:

- [ ] **Aspect ratio** preserved within 0.01 tolerance
  - Source TIF aspect = Export JSON aspect
  - Use: `python -c "import rasterio; src=rasterio.open('data/regions/STATE.tif'); print(src.width/src.height)"`

- [ ] **State borders** exported (not country borders)
  - File: `generated/regions/STATE_borders.json`
  - Contains: `"states"` key (NOT `"countries"`)

- [ ] **Visual check** in viewer
  - Correct shape (not square if state isn't square)
  - State outline visible (not USA outline)

- [ ] **Manifest updated**
  - Entry in `generated/regions/regions_manifest.json`
  - Correct dimensions listed

## Manual Fix Process

If you need to fix a state manually:

### 1. Re-export Elevation
```python
from pathlib import Path
from download_regions import process_region

region_info = {
    "bounds": (-XX.XX, YY.YY, -XX.XX, YY.YY),  # From USA_STATES
    "name": "State Name",
    "description": "State Name elevation data"
}

process_region(
    "state_id",
    region_info,
    Path("data/regions"),
    Path("generated/regions"),
    max_size=800
)
```

### 2. Export State Borders
```bash
python -c "
from pathlib import Path
from fix_all_states import export_state_borders

export_state_borders(
    Path('data/regions/STATE.tif'),
    'State Name',  # Exact case matters!
    Path('generated/regions/STATE_borders.json')
)
"
```

### 3. Verify
```bash
python fix_all_states.py --audit | grep STATE
```

## Prevention Measures

### Automated Validation
All export functions now validate aspect ratio automatically. If aspect ratio changes >0.01, export fails with error.

### Pre-commit Check
Before committing region data:
```bash
python fix_all_states.py --audit
```

Ensure no states show "needs_fix: True".

### Testing New Exports
After adding new states:
1. Run audit immediately
2. Fix any issues before committing
3. Visually verify in viewer

## Common Issues

### Issue: "Aspect ratio not preserved" Error
**Cause:** Downsampling logic is broken
**Fix:** Ensure using unified `step_size` (not separate `step_x`/`step_y`)

### Issue: State Shows as Square
**Cause:** Old export with broken downsampling
**Fix:** Re-export with `fix_all_states.py --fix STATE`

### Issue: Shows USA Outline Instead of State
**Cause:** Missing state borders or has country borders
**Fix:** Export state borders: `export_state_borders(tif_path, state_name, output_path)`

### Issue: State Not in Audit
**Cause:** Source TIF doesn't exist in `data/regions/`
**Fix:** Download state data first: `python downloaders/usa_3dep.py STATE --auto`

## State Name Mapping

Natural Earth uses official state names (exact case). Common mappings:

| State ID | Official Name | Notes |
|----------|---------------|-------|
| new_york | New York | Two words |
| new_hampshire | New Hampshire | Two words |
| new_jersey | New Jersey | Two words |
| new_mexico | New Mexico | Two words |
| north_carolina | North Carolina | Two words |
| north_dakota | North Dakota | Two words |
| south_carolina | South Carolina | Two words |
| south_dakota | South Dakota | Two words |
| west_virginia | West Virginia | Two words |
| rhode_island | Rhode Island | Two words |

## Files Modified

### Export Functions
- `download_regions.py` - Lines 358-363 (aspect validation)
- `src/pipeline.py` - Lines 302-308 (aspect validation)
- `download_all_us_states.py` - Lines 360-372 (fixed downsampling)
- `download_all_us_states_highres.py` - Lines 127-142 (fixed downsampling)
- `export_for_web_viewer.py` - Lines 55-72 (fixed downsampling)

### Border System
- `fix_all_states.py` - Utility script for auditing and fixing
- `js/viewer-advanced.js` - Lines 1574-1665 (handle state borders)

### Documentation
- `learnings/ASPECT_RATIO_FIX_SUMMARY.md` - Technical details
- `learnings/STATE_DATA_AUDIT.md` - This file

## Future Work

### Remaining States
22 states have no source TIF yet. To add them:

```bash
python downloaders/usa_3dep.py STATE_ID --auto
python fix_all_states.py --fix STATE_ID
```

### Higher Resolution
Some states support higher resolution (1-10m from 3DEP). Use:

```bash
python downloaders/usa_3dep.py STATE_ID --manual
# Follow instructions for USGS EarthExplorer download
```

### Batch Processing
To fix all remaining states at once:

```bash
python fix_all_states.py --fix-all
```

This will process all 26 states that currently need fixes.

## Summary

- **Problem:** 26 states had distorted aspect ratios and wrong borders
- **Solution:** Fixed downsampling algorithm + added validation + export state borders
- **Status:** 3 states fixed (Nebraska, Nevada, Delaware), 23 remaining
- **Next Steps:** Run `python fix_all_states.py --fix-all` to fix remaining states

