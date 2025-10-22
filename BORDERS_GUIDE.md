# Geographic Borders Guide

This guide explains how to use the border drawing and country masking features in the altitude-maps project.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Feature 1: Drawing Borders](#feature-1-drawing-borders)
4. [Feature 2: Masking Data](#feature-2-masking-data)
5. [Available Countries](#available-countries)
6. [Advanced Usage](#advanced-usage)
7. [Examples](#examples)
8. [API Reference](#api-reference)

## Overview

The project now supports two main border-related features:

1. **Draw National Borders**: Overlay country boundary lines on elevation visualizations
2. **Mask/Clip Data**: Restrict elevation data to specific country boundaries

Both features use [Natural Earth](https://www.naturalearthdata.com/) geographic data, which provides high-quality country boundaries at multiple resolutions.

### Border Resolutions

Natural Earth provides three resolution levels:

- **10m** (1:10 million scale): High detail, large file size, best for regional/detailed views
- **50m** (1:50 million scale): Medium detail, moderate file size
- **110m** (1:110 million scale): Low detail, small file size, good for global/continental views (default)

## Quick Start

### List Available Countries

```bash
# See all available countries
python border_utils.py --list

# Search for specific countries
python border_utils.py --list --search "United"
```

### Draw Borders on a Map

```python
from src.data_processing import prepare_visualization_data
from src.rendering import render_visualization

# Load elevation data
data = prepare_visualization_data("data/usa_elevation/nationwide_usa_elevation.tif")

# Render with USA borders drawn
render_visualization(
    data,
    draw_borders="United States of America",
    border_color="#FF0000",
    tif_path="data/usa_elevation/nationwide_usa_elevation.tif"
)
```

### Mask Data to Country Boundaries

```python
# Load and mask to USA only
data = prepare_visualization_data(
    "data/usa_elevation/nationwide_usa_elevation.tif",
    mask_country="United States of America"
)

# Render (data already clipped)
render_visualization(data)
```

## Feature 1: Drawing Borders

Drawing borders overlays country boundary lines on top of your elevation visualization **without modifying the underlying data**.

### Basic Usage

```python
render_visualization(
    data,
    draw_borders="United States of America",  # Country name
    tif_path="path/to/file.tif",  # Required for coordinate mapping
    border_color="#FF0000",  # Red borders
    border_width=2.0  # Line thickness
)
```

### Auto-Detect Borders

Automatically draw all countries visible in the map's bounding box:

```python
render_visualization(
    data,
    draw_borders=True,  # Auto-detect from bbox
    tif_path="path/to/file.tif"
)
```

### Multiple Countries

Draw borders for multiple countries:

```python
render_visualization(
    data,
    draw_borders=["United States of America", "Canada", "Mexico"],
    tif_path="path/to/file.tif",
    border_color="#00FF00"
)
```

### Customization Options

```python
render_visualization(
    data,
    draw_borders="United States of America",
    tif_path="path/to/file.tif",
    border_color="#FFFF00",  # Yellow
    border_width=3.0,  # Thicker lines
    border_resolution='10m'  # High detail borders
)
```

## Feature 2: Masking Data

Masking (clipping) restricts elevation data to specific country boundaries, making everything outside the country transparent/removed.

### Basic Usage

```python
# Mask to USA during data loading
data = prepare_visualization_data(
    "data/usa_elevation/nationwide_usa_elevation.tif",
    mask_country="United States of America"
)
```

### Legacy USA Masking

The old `mask_usa` parameter still works:

```python
# Legacy method (still supported)
data = prepare_visualization_data(
    "data/usa_elevation/nationwide_usa_elevation.tif",
    mask_usa=True  # Equivalent to mask_country="United States of America"
)
```

### Mask to Other Countries

```python
# Mask to Canada
data = prepare_visualization_data(
    "path/to/north_america.tif",
    mask_country="Canada"
)

# Mask to Mexico
data = prepare_visualization_data(
    "path/to/north_america.tif",
    mask_country="Mexico"
)
```

### Multiple Countries

Mask to multiple countries (e.g., for regions):

```python
# Show only USA and Canada
data = prepare_visualization_data(
    "path/to/north_america.tif",
    mask_country=["United States of America", "Canada"]
)
```

### Caching

Masked data is automatically cached to speed up subsequent runs:

```
data/.cache/
  nationwide_usa_elevation_masked_United_States_of_America_110m.pkl
```

Delete cache files to force re-masking (useful if you update the border data).

## Available Countries

### Common Country Names

Use these **exact names** when specifying countries:

- `"United States of America"` (not "USA" or "United States")
- `"Canada"`
- `"Mexico"`
- `"United Kingdom"`
- `"France"`
- `"Germany"`
- `"China"`
- `"Japan"`
- `"Australia"`
- `"Brazil"`
- `"India"`
- `"Russia"`

### Finding Country Names

```bash
# List all countries
python border_utils.py --list

# Search for countries
python border_utils.py --search "United"
python border_utils.py --search "Korea"

# Get detailed info
python border_utils.py --info "United States of America"
```

### Countries in a Region

Find which countries are in a specific area:

```bash
# North America bounding box
python border_utils.py --bbox "-170,15,-50,85"

# Europe bounding box
python border_utils.py --bbox "-10,35,40,70"
```

## Advanced Usage

### Combine Masking + Border Drawing

For maximum clarity, both mask the data AND draw borders:

```python
# Mask data to USA
data = prepare_visualization_data(
    "data/usa_elevation/nationwide_usa_elevation.tif",
    mask_country="United States of America"
)

# Also draw the border line
render_visualization(
    data,
    draw_borders="United States of America",
    border_color="#FF0000",
    border_width=2.0,
    tif_path="data/usa_elevation/nationwide_usa_elevation.tif"
)
```

### High-Resolution Borders for Regional Maps

For detailed regional views, use 10m resolution borders:

```python
data = prepare_visualization_data(
    "data/regions/california_central.tif",
    mask_country="United States of America",
    border_resolution='10m'  # High detail
)

render_visualization(
    data,
    draw_borders="United States of America",
    border_resolution='10m',
    tif_path="data/regions/california_central.tif"
)
```

### Working with Non-USA Data

When working with international data, disable USA masking:

```python
# Example: Japan elevation data
data = prepare_visualization_data(
    "data/regions/shikoku.tif",
    mask_usa=False,  # Don't mask to USA!
    mask_country="Japan"  # Mask to Japan instead
)

render_visualization(
    data,
    draw_borders="Japan",
    tif_path="data/regions/shikoku.tif"
)
```

## Examples

### Example 1: USA with State-Like Precision

```python
from src.data_processing import prepare_visualization_data
from src.rendering import render_visualization

# Load USA elevation
data = prepare_visualization_data(
    "data/usa_elevation/nationwide_usa_elevation.tif",
    mask_country="United States of America",
    border_resolution='10m'  # High detail
)

# Render with visible borders
render_visualization(
    data,
    output_dir="generated/usa_borders",
    filename_prefix="usa_hires_borders",
    draw_borders="United States of America",
    border_color="#FFFFFF",  # White borders
    border_width=2.0,
    border_resolution='10m',
    tif_path="data/usa_elevation/nationwide_usa_elevation.tif",
    camera_elevation=60,
    autocrop=True
)
```

### Example 2: Continental North America

```python
# Load full region without masking
data = prepare_visualization_data(
    "data/usa_elevation/nationwide_usa_elevation.tif",
    mask_usa=False  # Show all countries
)

# Draw all North American borders
render_visualization(
    data,
    output_dir="generated/north_america",
    filename_prefix="north_america_all_borders",
    draw_borders=["United States of America", "Canada", "Mexico"],
    border_color="#00FF00",
    border_width=2.5,
    tif_path="data/usa_elevation/nationwide_usa_elevation.tif"
)
```

### Example 3: Compare Masked vs Unmasked

```python
tif_file = "data/usa_elevation/nationwide_usa_elevation.tif"

# 1. Unmasked with auto-detected borders
data_full = prepare_visualization_data(tif_file, mask_usa=False)
render_visualization(
    data_full,
    filename_prefix="comparison_full",
    draw_borders=True,
    tif_path=tif_file
)

# 2. Masked to USA only
data_usa = prepare_visualization_data(tif_file, mask_country="United States of America")
render_visualization(
    data_usa,
    filename_prefix="comparison_usa_only",
    draw_borders="United States of America",
    tif_path=tif_file
)
```

## API Reference

### BorderManager Class

Located in `src/borders.py`. Handles all border operations.

```python
from src.borders import get_border_manager

border_manager = get_border_manager()
```

#### Methods

##### `load_borders(resolution='110m', force_reload=False)`

Load Natural Earth border data with caching.

**Parameters:**
- `resolution` (str): '10m', '50m', or '110m'
- `force_reload` (bool): Force re-download even if cached

**Returns:** GeoDataFrame with country borders

##### `get_country(country_name, resolution='110m')`

Get border data for a specific country.

**Parameters:**
- `country_name` (str): Country name
- `resolution` (str): Border resolution

**Returns:** GeoDataFrame for the country, or None if not found

##### `list_countries(resolution='110m')`

List all available country names.

**Returns:** Sorted list of country names

##### `get_countries_in_bbox(bbox, resolution='110m')`

Get all countries that intersect with a bounding box.

**Parameters:**
- `bbox` (tuple): (left, bottom, right, top) in lon/lat
- `resolution` (str): Border resolution

**Returns:** GeoDataFrame with countries in the bbox

##### `mask_raster_to_country(raster_src, country_name, resolution='110m', invert=False)`

Mask a raster dataset to country boundaries.

**Parameters:**
- `raster_src` (rasterio.DatasetReader): Open rasterio dataset
- `country_name` (str or list): Country name(s)
- `resolution` (str): Border resolution
- `invert` (bool): If True, mask out the country

**Returns:** Tuple of (masked_array, transform)

##### `get_border_coordinates(country_name, target_crs=None, resolution='110m')`

Get border coordinates for plotting.

**Parameters:**
- `country_name` (str or list): Country name(s)
- `target_crs` (optional): Target CRS to reproject to
- `resolution` (str): Border resolution

**Returns:** List of (x_coords, y_coords) tuples for each border segment

### Data Processing Parameters

New parameters in `prepare_visualization_data()`:

```python
data = prepare_visualization_data(
    tif_path,
    mask_usa=True,  # Legacy: mask to USA (use mask_country instead)
    mask_country=None,  # Mask to specific country (str or list)
    border_resolution='110m'  # Border resolution for masking
)
```

### Rendering Parameters

New parameters in `render_visualization()`:

```python
render_visualization(
    data,
    draw_borders=False,  # Draw borders (bool, str, or list)
    border_color='#FF4444',  # Border line color (hex)
    border_width=1.5,  # Border line width
    border_resolution='110m',  # Border resolution
    tif_path=None  # Required for border drawing
)
```

## Troubleshooting

### "Country not found"

Make sure you're using the exact country name from Natural Earth:

```bash
# Find the correct name
python border_utils.py --list --search "your_country"
```

### Borders not showing up

1. Make sure you provide `tif_path` parameter to `render_visualization()`
2. Check that `draw_borders` is not `False`
3. Verify the country is within the map's bounding box

### Masking removes all data

The country might not overlap with your elevation data. Check:

```bash
# Find countries in your data's region
python border_utils.py --test your_data.tif
```

### Cache issues

Delete cache files to force re-processing:

```bash
rm -rf data/.cache/
```

## Performance Notes

- **Border Drawing**: Fast, minimal performance impact
- **Data Masking**: 
  - First run: Slow (downloads borders, masks data, caches result)
  - Subsequent runs: Fast (loads from cache)
- **High-Resolution Borders (10m)**: 
  - Larger file sizes
  - More detailed borders
  - Slightly slower processing
  - Best for regional maps

## License & Data Sources

- **Natural Earth Data**: Public domain data from [naturalearthdata.com](https://www.naturalearthdata.com/)
- **Code**: Uses geopandas, rasterio, and shapely (see requirements.txt)

---

For more examples, see `example_borders.py` and `border_utils.py`.

