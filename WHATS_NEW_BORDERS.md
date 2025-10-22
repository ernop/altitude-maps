# What's New: Border Features! 🗺️

## TL;DR

You can now:

1. **Draw country borders** on your elevation maps (red lines, customizable)
2. **Clip data to countries** - toggle "show only USA" or any country
3. **177 countries available** from Natural Earth public data

**Quick test**: `python border_utils.py --list`

## Your Question - Answered

> "I'm wondering if there's any way to either 1) draw national borders on maps or 2) even use national border definition files to cut off / chop data so that it'd only show the nation. for example, when viewing the huge square of data containing the USA+Canada+mex+others, I'd be able to toggle "only include data within US borders" which would then show less, just US continental territory?"

✅ **Both features are now implemented!**

### Feature 1: Draw Borders (Visual Only)

```python
render_visualization(
    data,
    draw_borders="United States of America",
    tif_path="your_data.tif"
)
```

Result: Red border lines overlaid on your map (doesn't change data)

### Feature 2: Mask/Clip Data (Your "Toggle" Feature)

```python
# Show ONLY USA territory
data = prepare_visualization_data(
    "your_data.tif",
    mask_country="United States of America"
)
```

Result: Everything outside USA boundaries is removed/transparent!

This is exactly your "toggle only include data within US borders" feature!

## What Was Added

### New Files

1. **`src/borders.py`** - Border management system
   - BorderManager class
   - Natural Earth data integration
   - Caching system

2. **`border_utils.py`** - Command-line utilities
   - List countries
   - Search countries
   - Find countries in regions
   - Test borders on your data

3. **`example_borders.py`** - 7 working examples
   - Drawing borders
   - Masking data
   - Multi-country regions
   - Auto-detection

4. **Documentation**:
   - `BORDERS_GUIDE.md` - Full guide (detailed)
   - `BORDERS_QUICKSTART.md` - Quick start (get going in 5 min)
   - `BORDERS_IMPLEMENTATION_SUMMARY.md` - Technical details

5. **`test_borders.py`** - Test suite (all tests passed ✓)

### Updated Files

1. **`src/data_processing.py`**
   - Added `mask_country` parameter
   - Support for any country
   - Enhanced caching

2. **`src/rendering.py`**
   - Added `draw_borders` parameter
   - Border drawing on 3D visualizations
   - Auto-detection of countries

3. **`README.md`**
   - New section on border features

## Real-World Example

### Before (your current situation):

Your data file contains a big square: USA + Canada + Mexico + ocean

```python
data = prepare_visualization_data("nationwide_usa_elevation.tif")
render_visualization(data)
```

Result: Shows everything in the square

### After (with your toggle feature):

```python
# Toggle ON: "Only show USA"
data = prepare_visualization_data(
    "nationwide_usa_elevation.tif",
    mask_country="United States of America"  # <-- Your toggle!
)
render_visualization(data)
```

Result: Shows ONLY USA continental territory!

And it's cached, so toggling back and forth is instant after the first run.

## How to Use (3 Steps)

### Step 1: List Countries (10 seconds)

```bash
python border_utils.py --list
```

Outputs: 177 available countries

### Step 2: Try an Example (2 minutes)

```bash
python example_borders.py --example 2
```

This creates a map with data clipped to USA only.

### Step 3: Use in Your Code (1 minute)

Add ONE parameter to your existing code:

```python
# Your existing code
data = prepare_visualization_data("your_file.tif")

# Add mask_country parameter:
data = prepare_visualization_data(
    "your_file.tif",
    mask_country="United States of America"  # <-- Add this!
)
```

Done! Your map now shows only USA.

## Example Outputs

### Example 1: Unmasked with Borders

```python
data = prepare_visualization_data(tif_file, mask_usa=False)
render_visualization(
    data, 
    draw_borders=True,  # Auto-detect all countries
    tif_path=tif_file
)
```

Shows: Full region with border lines for USA, Canada, Mexico

### Example 2: Masked to USA Only

```python
data = prepare_visualization_data(
    tif_file, 
    mask_country="United States of America"
)
render_visualization(data)
```

Shows: Only USA territory (Canada/Mexico removed)

### Example 3: Masked + Borders (Best Visual Clarity)

```python
data = prepare_visualization_data(
    tif_file,
    mask_country="United States of America"
)
render_visualization(
    data,
    draw_borders="United States of America",
    border_color="#FF0000",
    tif_path=tif_file
)
```

Shows: Only USA territory with red border line

## Data Source

All border data comes from [Natural Earth](https://www.naturalearthdata.com/):
- **Public domain** (free to use)
- **177 countries** worldwide
- **3 detail levels**: 10m, 50m, 110m
- Professionally curated and maintained

First download is automatic (takes 2-5 seconds), then cached forever.

## Performance

- **First run with new country**: 2-10 seconds (downloads + processes)
- **Subsequent runs**: < 1 second (uses cache)
- **Cache location**: `data/.cache/`

No performance impact on visualization rendering.

## Backward Compatibility

All your existing code still works:
- `mask_usa=True` still works (now uses new system internally)
- All existing parameters unchanged
- New parameters are optional
- Zero breaking changes

## Available Countries

### Common Ones:
- United States of America
- Canada
- Mexico
- United Kingdom
- France
- Germany
- China
- Japan
- Australia
- Brazil
- India
- Russia
- ... and 165 more!

**Find yours**: `python border_utils.py --search "your_country"`

## Testing

All functionality has been tested:

```bash
python test_borders.py
```

Result: 9/9 tests passed ✓

- ✓ Import modules
- ✓ Load Natural Earth data
- ✓ List countries
- ✓ Get specific countries
- ✓ Find countries in regions
- ✓ Extract border coordinates
- ✓ Integration with existing code

## Documentation

### Quick Start (5 minutes)
👉 **`BORDERS_QUICKSTART.md`** - Start here!

### Full Guide (30 minutes)
📖 **`BORDERS_GUIDE.md`** - Complete reference with all options

### Examples (try them!)
💻 **`example_borders.py`** - 7 working examples

### Utilities
🔧 **`border_utils.py`** - Command-line tools

### Technical Details
⚙️ **`BORDERS_IMPLEMENTATION_SUMMARY.md`** - Implementation details

## Quick Commands

```bash
# List all countries
python border_utils.py --list

# Search for a country
python border_utils.py --search "United"

# Get country details
python border_utils.py --info "United States of America"

# Find countries in North America
python border_utils.py --bbox "-125,25,-65,50"

# Test on your elevation file
python border_utils.py --test your_data.tif

# Run all examples
python example_borders.py

# Run specific example
python example_borders.py --example 1
```

## Next Steps

1. **List available countries**:
   ```bash
   python border_utils.py --list
   ```

2. **Try an example**:
   ```bash
   python example_borders.py --example 3
   ```

3. **Add to your code**:
   ```python
   mask_country="United States of America"
   ```

4. **Read the guide**: `BORDERS_QUICKSTART.md`

## Questions?

- **Quick start**: `BORDERS_QUICKSTART.md`
- **Full documentation**: `BORDERS_GUIDE.md`
- **Examples**: Run `python example_borders.py`
- **Test it**: `python border_utils.py --test your_data.tif`

---

**Enjoy your new border features!** 🎉

This exactly solves your request to "toggle only include data within US borders" - just set `mask_country="United States of America"` and you're done!

