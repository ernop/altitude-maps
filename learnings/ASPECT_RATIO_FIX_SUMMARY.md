# Aspect Ratio Fix Summary

## Problem Discovered
US state regions (Nebraska, Nevada, and likely others) were rendering incorrectly in the viewer:
1. **Stretched/Square appearance** - Regions displayed with distorted proportions
2. **Wrong borders** - Country-level borders (entire USA) shown instead of state-specific borders

## Root Causes

### Issue 1: Aspect Ratio Distortion During Downsampling

**Code Location:** Multiple export scripts

**Problem:** Independent step sizes for width and height distorted aspect ratios:
```python
# OLD (BROKEN):
step_y = max(1, height // max_size)
step_x = max(1, width // max_size)
elevation = elevation[::step_y, ::step_x]
```

**Example - Nebraska:**
- Source: 31464×10800 (aspect 2.913)
- step_x=39, step_y=13
- Result: 807×831 (aspect 0.971) ❌ SQUARE!

**Solution:** Use single step size based on larger dimension:
```python
# NEW (CORRECT):
scale_factor = max(height / max_size, width / max_size)
step_size = max(1, int(scale_factor))
elevation = elevation[::step_size, ::step_size]
```

**Result - Nebraska:**
- Source: 31464×10800 (aspect 2.913)
- step_size=39
- Result: 807×277 (aspect 2.913) ✅ PRESERVED!

### Issue 2: Wrong Border Type

**Problem:** US states exported with country-level borders showing entire USA outline instead of individual state shapes.

**Solution:** Created state-level border export using Natural Earth admin_1 data:
- `export_state_borders.py` - Exports state-specific border coordinates
- Borders JSON now has `"states"` key with actual state outlines
- Viewer updated to handle both `countries` and `states` border data

## Files Modified

### Export Scripts (Aspect Ratio Fix)
1. `download_regions.py` - Lines 338-354
2. `download_all_us_states.py` - Lines 360-372
3. `download_all_us_states_highres.py` - Lines 127-142
4. `export_for_web_viewer.py` - Lines 55-72

Changes:
- Unified step size calculation
- Added aspect ratio validation warnings
- Print aspect ratio before/after downsampling

### Border System (State Borders)
5. `export_state_borders.py` - NEW FILE
   - Exports state-level borders using `BorderManager.get_state()`
   - Creates JSON with `"states"` key instead of `"countries"`
   - Handles Polygon/MultiPolygon geometry types

6. `js/viewer-advanced.js` - Lines 125-142, 1574-1665
   - `loadBorderData()` - Detects border type (states vs countries)
   - `recreateBorders()` - Handles both border types via `allBorders` array
   - Logging shows correct entity type and count

## States Fixed

### Nebraska
- Elevation: 807×277 (aspect 2.913) ✅
- Borders: 39 points, 1 segment ✅
- Type: State borders ✅

### Nevada
- Elevation: 694×813 (aspect 0.854) ✅
- Borders: 21 points, 1 segment ✅
- Type: State borders ✅

## How to Fix Other States

For any US state with existing elevation data:
```bash
# 1. Re-export elevation with correct aspect ratio
python re_export_state.py <state_id>

# 2. Export state borders
python export_state_borders.py data/regions/<state>.tif "<State Name>" generated/regions/<state>_borders.json

# Example for California:
python export_state_borders.py data/regions/california.tif California generated/regions/california_borders.json
```

## Prevention Measures

All export scripts now:
1. Use unified `step_size` for both dimensions
2. Print aspect ratios before/after downsampling
3. Warn if aspect ratio changes > 0.1

This prevents future regressions and makes the issue immediately visible in logs.

## Validation

Aspect ratio preservation can be verified with:
```python
orig_aspect = width / height
result_aspect = result_width / result_height
assert abs(result_aspect - orig_aspect) < 0.01, "Aspect ratio not preserved!"
```

## Technical Details

**Why this matters:**
- Geographic regions have specific shapes
- Incorrect aspect ratios make rectangular states appear square
- Wrong borders show entire USA instead of individual states
- Both issues make visualization meaningless

**Natural Earth Data:**
- admin_0: Country-level borders (177 countries)
- admin_1: State/province borders (~1000 worldwide, includes 50 US states)
- Resolution: 110m (low detail, small files) to 10m (high detail)
- Cache: `data/.cache/borders/ne_110m_admin_1.pkl`

**BorderManager methods used:**
- `load_state_borders(resolution)` - Downloads/caches admin_1 shapefile
- `get_state(country, state, resolution)` - Queries specific state geometry
- Returns GeoDataFrame with Polygon/MultiPolygon geometry

**Viewer rendering:**
- Yellow lines at 100m height above ground
- Same coordinate mapping as elevation mesh
- Works with all render modes (surface, bars, points)

