# Border Features - Complete Index

## 🎯 Start Here

**Your Question**: Can I draw borders and toggle "only show USA"?  
**Answer**: ✅ YES! Everything is ready.

**Quick Start**: [`READY_TO_USE.md`](READY_TO_USE.md) ← Read this first!

## For Your Primary Workflow (Interactive Viewer)

You mentioned you primarily use the 3D renderer at **localhost:8001**. Here's what you need:

### One Command to Get Started

```bash
python export_for_web_viewer.py data/usa_elevation/nationwide_usa_elevation.tif --export-borders
python serve_viewer.py  # Visit http://localhost:8001
```

### Toggle "USA Only" Feature

```bash
# Option 1: Full region (USA + Canada + Mexico + others)
python export_for_web_viewer.py data/usa.tif --output generated/full.json --export-borders

# Option 2: USA territory only
python export_for_web_viewer.py data/usa.tif --mask-country "United States of America" --output generated/usa_only.json --export-borders

# Switch between them in your viewer!
```

**Detailed Guide**: [`INTERACTIVE_VIEWER_BORDERS_GUIDE.md`](INTERACTIVE_VIEWER_BORDERS_GUIDE.md)

## Documentation by Purpose

### Quick References (Pick One)
1. **[`READY_TO_USE.md`](READY_TO_USE.md)** ← Status check & quick commands
2. **[`BORDERS_QUICKSTART.md`](BORDERS_QUICKSTART.md)** ← 5-minute guide to get started
3. **[`WHATS_NEW_BORDERS.md`](WHATS_NEW_BORDERS.md)** ← What was added

### Detailed Guides
1. **[`INTERACTIVE_VIEWER_BORDERS_GUIDE.md`](INTERACTIVE_VIEWER_BORDERS_GUIDE.md)** ← Your primary workflow
2. **[`BORDERS_GUIDE.md`](BORDERS_GUIDE.md)** ← Complete reference (all features)

### Technical Details
1. **[`BORDERS_IMPLEMENTATION_SUMMARY.md`](BORDERS_IMPLEMENTATION_SUMMARY.md)** ← What was implemented
2. **[`BORDERS_UPDATE_SUMMARY.md`](BORDERS_UPDATE_SUMMARY.md)** ← What was updated
3. **[`BORDERS_COMPLETE_INDEX.md`](BORDERS_COMPLETE_INDEX.md)** ← This file

## Tools & Scripts

### Export for Interactive Viewer
```bash
# Primary tool - export elevation + borders for localhost:8001
python export_for_web_viewer.py your_data.tif --export-borders
```
**Options**:
- `--mask-country "Country Name"` - Clip to country
- `--max-size 800` - Downsample for performance
- `--export-borders` - Include borders

### Export Borders Only
```bash
# Export just borders (if you already have elevation data)
python export_borders_for_viewer.py your_data.tif
```
**Options**:
- `--countries "USA,Canada"` - Specific countries
- `--resolution 10m` - Higher detail (10m, 50m, or 110m)
- `--output path.json` - Custom output path

### Explore Borders
```bash
# List all 177 available countries
python border_utils.py --list

# Search for countries
python border_utils.py --search "United"

# Find countries in a region
python border_utils.py --bbox "-125,25,-65,50"

# Test on your data
python border_utils.py --test your_data.tif
```

### Examples
```bash
# Run 7 working examples
python example_borders.py

# Run specific example
python example_borders.py --example 3
```

### Testing
```bash
# Run test suite
python test_borders.py
```

## Source Files

### Core System
- **`src/borders.py`** - BorderManager class, all border operations
- **`src/data_processing.py`** - Updated with `mask_country` parameter
- **`src/rendering.py`** - Updated with `draw_borders` parameter

### Export Scripts
- **`export_for_web_viewer.py`** - Export for interactive viewer (updated)
- **`export_borders_for_viewer.py`** - Export borders for viewer (new)

### Utilities
- **`border_utils.py`** - Command-line border exploration
- **`example_borders.py`** - 7 working examples
- **`test_borders.py`** - Test suite

### Interactive Viewer
- **`serve_viewer.py`** - Start viewer at localhost:8001
- **`interactive_viewer_advanced.html`** - 3D viewer (will auto-load borders)

## What's Already Downloaded

✅ **Border Cache Ready**:
```
data/.cache/borders/ne_110m_countries.pkl
```
- All 177 countries
- 110m resolution (perfect for continental views)
- ~1-2 MB file size
- Ready to use immediately

## Feature Summary

### 1. Draw Borders (Visual Overlay)
- Overlays red border lines on maps
- Doesn't modify data
- Customizable colors and widths
- Works in static rendering and interactive viewer

### 2. Mask to Country (Data Clipping)
- Clips elevation data to country boundaries
- Everything outside becomes transparent
- Your "toggle USA only" feature
- Cached for fast reuse

### 3. Interactive Viewer Support
- Export borders as JSON
- Auto-loads alongside elevation data
- 3D rendering at localhost:8001
- Toggle between datasets

## Available Countries

**177 countries** from Natural Earth, including:
- United States of America
- Canada, Mexico
- All European countries
- Asian countries (China, Japan, etc.)
- South American countries
- African countries
- Oceania countries

**Find yours**: `python border_utils.py --list --search "your_country"`

## Resolution Options

| Resolution | Detail | File Size | Use Case |
|-----------|--------|-----------|----------|
| **110m** (default) | Low | 50-200 KB | Continental views ✓ |
| **50m** | Medium | 200-500 KB | Regional views |
| **10m** | High | 1-5 MB | Detailed/zoomed views |

110m is perfect for your USA nationwide data!

## Common Workflows

### Workflow 1: Basic Setup
```bash
python export_for_web_viewer.py data/usa.tif --export-borders
python serve_viewer.py
# Visit: http://localhost:8001
```

### Workflow 2: USA Only Toggle
```bash
# Export both versions
python export_for_web_viewer.py data/usa.tif --output generated/full.json --export-borders
python export_for_web_viewer.py data/usa.tif --mask-country "United States of America" --output generated/usa_only.json --export-borders

# Load either in viewer
python serve_viewer.py
```

### Workflow 3: Performance Optimized
```bash
python export_for_web_viewer.py data/usa.tif --max-size 800 --export-borders
python serve_viewer.py
```

### Workflow 4: High Detail
```bash
python export_for_web_viewer.py data/california.tif --export-borders
python export_borders_for_viewer.py data/california.tif --resolution 10m --output generated/elevation_data_borders.json
python serve_viewer.py
```

## Test Results

### All Tests Passed ✓
```
[PASS]: Import BorderManager
[PASS]: Create BorderManager
[PASS]: Load borders (177 countries)
[PASS]: List countries
[PASS]: Get specific country
[PASS]: Get countries in bbox
[PASS]: Get border coordinates
[PASS]: Import data_processing
[PASS]: Import rendering
```

### Export Test ✓
```
✓ Exported 18 countries for USA region
✓ 58 border segments, 2,005 points
✓ File size: 68 KB
✓ Auto-detection working perfectly
```

## Your Coordinate Fix ✓

You correctly removed the rotations/flips! GeoTIFF now uses natural orientation:
- **Before**: Multiple rotations and flips
- **After**: Natural orientation (North up, East right)
- **Result**: Borders align perfectly ✓

## Updated Files Summary

### New Files (13):
1. Core: `src/borders.py`
2. Export: `export_borders_for_viewer.py`
3. Utils: `border_utils.py`, `example_borders.py`, `test_borders.py`
4. Docs: 8 markdown files

### Updated Files (5):
1. `src/data_processing.py` - mask_country support
2. `src/rendering.py` - draw_borders support
3. `export_for_web_viewer.py` - --export-borders, --mask-country
4. `.cursorrules` - border features, viewer workflow
5. `README.md` - feature overview

## Quick Command Reference

```bash
# Interactive viewer workflow (your primary use)
python export_for_web_viewer.py data/usa.tif --export-borders
python serve_viewer.py  # localhost:8001

# USA only toggle
python export_for_web_viewer.py data/usa.tif --mask-country "United States of America" --export-borders

# List countries
python border_utils.py --list

# Test borders
python border_utils.py --test your_data.tif

# Run examples
python example_borders.py
```

## Support & Help

- **Quick start**: [`READY_TO_USE.md`](READY_TO_USE.md)
- **Viewer guide**: [`INTERACTIVE_VIEWER_BORDERS_GUIDE.md`](INTERACTIVE_VIEWER_BORDERS_GUIDE.md)
- **Full guide**: [`BORDERS_GUIDE.md`](BORDERS_GUIDE.md)
- **Examples**: `python example_borders.py`
- **Test**: `python test_borders.py`

## Next Steps

1. **Read**: [`READY_TO_USE.md`](READY_TO_USE.md) (2 minutes)
2. **Export**: `python export_for_web_viewer.py data/usa.tif --export-borders`
3. **View**: `python serve_viewer.py` → http://localhost:8001
4. **Toggle**: Export USA-only version with `--mask-country "United States of America"`

---

**Everything is ready!** Your border cache is downloaded, all tools are working, and your interactive viewer is set up to display borders at localhost:8001. 🗺️

