# Using Borders in the Interactive 3D Viewer

## Quick Start

The interactive 3D viewer at `http://localhost:8001` can now display country borders!

### Step 1: Export Elevation Data with Borders

```bash
# Export with auto-detected borders
python export_for_web_viewer.py data/usa_elevation/nationwide_usa_elevation.tif --export-borders

# Or export masked to USA only with borders
python export_for_web_viewer.py data/usa_elevation/nationwide_usa_elevation.tif \
    --mask-country "United States of America" \
    --export-borders
```

This creates two files:
- `generated/elevation_data.json` - Elevation data
- `generated/elevation_data_borders.json` - Border data

### Step 2: Export Just Border Data (Optional)

If you already have elevation data and just want to add borders:

```bash
# Auto-detect borders from region
python export_borders_for_viewer.py data/usa_elevation/nationwide_usa_elevation.tif

# Or specify countries
python export_borders_for_viewer.py data/usa.tif \
    --countries "United States of America,Canada,Mexico"
```

### Step 3: Load in Interactive Viewer

The interactive viewer will automatically look for borders in the same directory as your elevation data with the suffix `_borders.json`.

If you have:
- `generated/elevation_data.json`
- `generated/elevation_data_borders.json`

The viewer will automatically load both!

## Command Examples

### Export USA Data with Borders

```bash
# Full resolution with borders
python export_for_web_viewer.py \
    data/usa_elevation/nationwide_usa_elevation.tif \
    --output generated/usa_full.json \
    --export-borders

# Then serve:
python serve_viewer.py
# Visit: http://localhost:8001
```

### Export Downsampled Data with High-Res Borders

```bash
# Downsample elevation for performance, but keep detailed borders
python export_for_web_viewer.py \
    data/usa_elevation/nationwide_usa_elevation.tif \
    --max-size 800 \
    --export-borders

# Export high-resolution borders separately
python export_borders_for_viewer.py \
    data/usa_elevation/nationwide_usa_elevation.tif \
    --resolution 10m \
    --output generated/elevation_data_borders.json
```

### Mask to USA Only

```bash
# Show only USA territory in viewer
python export_for_web_viewer.py \
    data/usa_elevation/nationwide_usa_elevation.tif \
    --mask-country "United States of America" \
    --export-borders \
    --output generated/usa_only.json
```

### Multiple Countries

```bash
# Export North America with all borders
python export_for_web_viewer.py \
    data/usa_elevation/nationwide_usa_elevation.tif \
    --output generated/north_america.json \
    --export-borders

# This will auto-detect USA, Canada, Mexico, and other visible countries
```

## Border Data Format

The exported border JSON has this structure:

```json
{
  "bounds": {
    "left": -125.0,
    "right": -65.0,
    "top": 50.0,
    "bottom": 25.0
  },
  "resolution": "110m",
  "countries": [
    {
      "name": "United States of America",
      "segments": [
        {
          "lon": [-122.5, -122.4, ...],
          "lat": [48.5, 48.6, ...]
        },
        ...
      ],
      "segment_count": 10
    },
    ...
  ]
}
```

## Resolution Guide

Choose border resolution based on your view:

### 110m (Default) - Continental/Global Views
```bash
python export_borders_for_viewer.py your_data.tif --resolution 110m
```
- **File size**: Small (~50-200 KB)
- **Detail**: Low, simplified borders
- **Best for**: Continental USA, multi-country views, global maps
- **Performance**: Fastest

### 50m - Regional Views
```bash
python export_borders_for_viewer.py your_data.tif --resolution 50m
```
- **File size**: Medium (~200-500 KB)
- **Detail**: Medium
- **Best for**: State-sized regions, detailed continental views
- **Performance**: Good

### 10m - Detailed/Zoomed Views
```bash
python export_borders_for_viewer.py your_data.tif --resolution 10m
```
- **File size**: Large (~1-5 MB)
- **Detail**: High, shows coastal detail
- **Best for**: City/regional views, high-detail presentations
- **Performance**: May be slower on large datasets

## Workflow Examples

### Typical USA Project

```bash
# 1. Export elevation and borders
python export_for_web_viewer.py \
    data/usa_elevation/nationwide_usa_elevation.tif \
    --export-borders

# 2. Start viewer
python serve_viewer.py

# 3. Open browser
# Visit: http://localhost:8001
```

### Toggle "USA Only" View

```bash
# Export two versions:

# Version 1: Full region with all countries
python export_for_web_viewer.py data/usa.tif \
    --output generated/full_region.json \
    --export-borders

# Version 2: USA territory only
python export_for_web_viewer.py data/usa.tif \
    --mask-country "United States of America" \
    --output generated/usa_only.json \
    --export-borders

# Switch between them in the viewer!
```

### High-Performance Setup

```bash
# Downsample elevation heavily but keep detailed borders
python export_for_web_viewer.py data/usa.tif \
    --max-size 600 \
    --export-borders \
    --output generated/usa_fast.json

# Optional: Replace with high-res borders
python export_borders_for_viewer.py data/usa.tif \
    --resolution 50m \
    --output generated/usa_fast_borders.json
```

## Troubleshooting

### Borders not loading

1. Check file names match: `elevation_data.json` and `elevation_data_borders.json`
2. Make sure both files are in `generated/` directory
3. Check browser console for errors (F12)

### Borders look wrong

1. Make sure you used the same TIF file for both exports
2. Check that border resolution matches your view scale
3. Try regenerating: `python export_borders_for_viewer.py your_data.tif`

### Performance issues

1. Use lower resolution borders: `--resolution 110m`
2. Reduce elevation data size: `--max-size 800`
3. Mask to specific country to reduce data

## File Size Reference

For typical USA nationwide elevation data:

| Configuration | Elevation | Borders | Total | Load Time |
|--------------|-----------|---------|-------|-----------|
| Full + 110m | 5-10 MB | 100 KB | ~10 MB | 2-3 sec |
| 800px + 110m | 1-2 MB | 100 KB | ~2 MB | < 1 sec |
| 800px + 50m | 1-2 MB | 400 KB | ~2 MB | < 1 sec |
| Full + 10m | 5-10 MB | 2 MB | ~12 MB | 3-4 sec |

## Advanced: Custom Border Sets

Export multiple border sets:

```bash
# Export different resolutions
python export_borders_for_viewer.py data/usa.tif \
    --resolution 110m \
    --output generated/borders_110m.json

python export_borders_for_viewer.py data/usa.tif \
    --resolution 50m \
    --output generated/borders_50m.json

python export_borders_for_viewer.py data/usa.tif \
    --resolution 10m \
    --output generated/borders_10m.json

# Switch between them in your viewer!
```

## Integration with Existing Workflow

If you already have `elevation_data.json`:

```bash
# Just add borders!
python export_borders_for_viewer.py \
    data/usa_elevation/nationwide_usa_elevation.tif \
    --output generated/elevation_data_borders.json

# Viewer will automatically find and load them
```

## Next Steps

1. **Export your data with borders**:
   ```bash
   python export_for_web_viewer.py your_data.tif --export-borders
   ```

2. **Start the viewer**:
   ```bash
   python serve_viewer.py
   ```

3. **Open in browser**:
   - Visit: `http://localhost:8001`
   - Borders will be visible as colored lines
   - Use viewer controls to adjust border visibility

## See Also

- **Main Border Guide**: `BORDERS_GUIDE.md`
- **Quick Start**: `BORDERS_QUICKSTART.md`
- **Static Rendering**: For PNG/image outputs with borders
- **Examples**: `example_borders.py`

---

**Note**: The interactive viewer currently auto-loads borders if the `_borders.json` file exists. Future updates may add UI controls for border visibility, color, and width.

