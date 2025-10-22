# Border Features - Quick Start Guide

## ✅ Implementation Complete!

Both features you requested are now fully implemented and tested:

1. **Draw national borders on maps** ✓
2. **Mask/clip data to country boundaries** ✓

All tests passed successfully! 🎉

## Instant Examples

### 1. List Available Countries (30 seconds)

```bash
# See all 177 available countries
python border_utils.py --list

# Search for specific countries
python border_utils.py --list --search "United"
```

### 2. Try the Examples (5 minutes)

```bash
# Run all border examples
python example_borders.py

# Or run a specific example
python example_borders.py --example 1  # Draw USA borders
python example_borders.py --example 2  # Mask to USA only
python example_borders.py --example 3  # Both mask AND draw borders
```

### 3. Use in Your Own Code

#### Draw Borders on Your Existing Map

```python
from src.data_processing import prepare_visualization_data
from src.rendering import render_visualization

# Load your existing data
data = prepare_visualization_data(
    "data/usa_elevation/nationwide_usa_elevation.tif"
)

# Render with borders drawn
render_visualization(
    data,
    draw_borders="United States of America",  # Add this line!
    border_color="#00FF00",  # Green borders
    border_width=2.0,
    tif_path="data/usa_elevation/nationwide_usa_elevation.tif",  # Required
    filename_prefix="usa_with_borders"
)
```

#### Mask Data to Show Only USA

```python
# When loading data, add mask_country parameter
data = prepare_visualization_data(
    "data/usa_elevation/nationwide_usa_elevation.tif",
    mask_country="United States of America"  # Add this line!
)

# Render normally - data is already clipped!
render_visualization(data, filename_prefix="usa_only")
```

#### Do Both (Mask AND Draw Borders)

```python
# Mask to USA
data = prepare_visualization_data(
    "data/usa_elevation/nationwide_usa_elevation.tif",
    mask_country="United States of America"
)

# Also draw the border line for visual clarity
render_visualization(
    data,
    draw_borders="United States of America",
    border_color="#FF0000",
    tif_path="data/usa_elevation/nationwide_usa_elevation.tif",
    filename_prefix="usa_masked_with_borders"
)
```

## Common Use Cases

### Toggle "Only Show USA" in Your Large Region Data

**Before** (shows USA + Canada + Mexico + ocean):
```python
data = prepare_visualization_data(
    "data/usa_elevation/nationwide_usa_elevation.tif",
    mask_usa=False  # Don't mask
)
```

**After** (shows only USA continental territory):
```python
data = prepare_visualization_data(
    "data/usa_elevation/nationwide_usa_elevation.tif",
    mask_country="United States of America"  # Only USA!
)
```

The data is automatically cached, so subsequent runs are instant!

### Auto-Detect and Draw All Visible Borders

```python
render_visualization(
    data,
    draw_borders=True,  # Auto-detect countries in view
    tif_path="data/usa_elevation/nationwide_usa_elevation.tif"
)
```

### Draw Multiple Country Borders

```python
render_visualization(
    data,
    draw_borders=["United States of America", "Canada", "Mexico"],
    border_color="#FFFF00",
    tif_path="data/usa_elevation/nationwide_usa_elevation.tif"
)
```

## Available Countries

177 countries are available! Common ones include:

- `"United States of America"` (not "USA")
- `"Canada"`
- `"Mexico"`
- `"United Kingdom"`
- `"France"`
- `"Germany"`
- `"Spain"`
- `"Italy"`
- `"China"`
- `"Japan"`
- `"South Korea"`
- `"Australia"`
- `"Brazil"`
- `"India"`
- `"Russia"`

**Find the exact name**:
```bash
python border_utils.py --list --search "korea"
```

## Resolution Options

Three detail levels available (default: 110m):

```python
# Low detail (fast, small file, good for continental views)
mask_country="United States of America",
border_resolution='110m'  # default

# Medium detail
border_resolution='50m'

# High detail (slow, large file, best for regional views)
border_resolution='10m'
```

## Test on Your Own Data

```bash
# Test if borders work with your elevation file
python border_utils.py --test path/to/your_data.tif

# Test specific countries
python border_utils.py --test your_data.tif --countries "Japan,China"
```

## How It Works

### Border Drawing
1. Loads country boundaries from Natural Earth (public domain data)
2. Reprojects boundaries to match your data's coordinate system
3. Overlays red lines on the 3D visualization
4. Does NOT modify your elevation data

### Data Masking
1. Loads country boundaries
2. Clips elevation data to country boundaries
3. Everything outside the boundary becomes transparent/NaN
4. Result is cached for fast reuse

## Performance

- **First run**: 2-10 seconds (downloads borders, processes data)
- **Subsequent runs**: < 1 second (uses cache)
- **Cache location**: `data/.cache/borders/` and `data/.cache/`

## Full Documentation

For complete details, see:
- **Full Guide**: `BORDERS_GUIDE.md` - Complete documentation with all options
- **Examples**: `example_borders.py` - 7 working examples
- **Utilities**: `border_utils.py` - Command-line tools
- **Implementation Details**: `BORDERS_IMPLEMENTATION_SUMMARY.md`

## Quick Commands Reference

```bash
# List countries
python border_utils.py --list

# Search countries
python border_utils.py --search "United"

# Get country info
python border_utils.py --info "United States of America"

# Find countries in region
python border_utils.py --bbox "-125,25,-65,50"

# Test on your data
python border_utils.py --test your_data.tif

# Run examples
python example_borders.py
```

## Your Original Questions - Answered!

### Question 1: "Can I draw national borders on maps?"

✅ **YES!** Use `draw_borders` parameter:

```python
render_visualization(
    data,
    draw_borders="United States of America",
    tif_path="path/to/file.tif"
)
```

### Question 2: "Can I use border files to cut off/chop data to show only the nation?"

✅ **YES!** Use `mask_country` parameter:

```python
data = prepare_visualization_data(
    "path/to/file.tif",
    mask_country="United States of America"
)
```

This exactly solves your use case: "when viewing the huge square of data containing the USA+Canada+mex+others, I'd be able to toggle 'only include data within US borders' which would then show less, just US continental territory"

Just set `mask_country="United States of America"` and it will show ONLY US continental territory!

---

**Ready to try it?** Start with:
```bash
python border_utils.py --list
python example_borders.py
```

Enjoy your new border features! 🗺️

