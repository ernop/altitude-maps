# Altitude Maps - User Guide

Complete guide for using Altitude Maps to visualize and explore elevation data.

## Quick Start

### Setup (One Time)

```powershell
# Run from PowerShell in the project directory
.\setup.ps1
```

Creates a Python virtual environment and installs dependencies. Takes ~2 minutes.

### Start Interactive Viewer (Recommended)

```powershell
# Start local server
python -m http.server 8001

# Open in browser: http://localhost:8001/interactive_viewer_advanced.html
```

**Controls**:
- **Left-click drag**: Pan the map
- **Right-click drag**: Rotate around focus point  
- **Mouse wheel**: Zoom toward cursor
- **WASD**: Keyboard camera movement
- **Q/E**: Move up/down vertically
- **Shift**: Speed modifier
- **R**: Reset camera

### Generate Static Visualization

```powershell
python visualize_usa_overhead.py
```

**Output**: Overhead view of continental USA in `generated/` folder (~10 seconds to render).

## What Can You Do?

### Interactive 3D Exploration

The interactive viewer provides real-time exploration with:

- **45+ Pre-configured Regions**: Switch between USA, Japan, Switzerland, and more without refreshing
- **Real-Time Bucketing**: Adjust detail level (1-50 pixels) for performance
- **Multiple Render Modes**: Bars, surface, wireframe, or point cloud
- **Vertical Exaggeration**: Adjust from 0.1× to 50× (1.0 = true Earth scale)
- **Color Schemes**: 6 options including terrain, earth, ocean, viridis
- **Country Borders**: Toggle country/state boundaries overlay
- **Screenshots**: Export current view as PNG

### Static Image Generation

Create high-quality static visualizations for publications or presentations:

```powershell
# Overhead view of continental USA
python visualize_usa_overhead.py

# 100-mile bucket aggregation for dramatic peaks
python visualize_usa_overhead.py --bucket-miles 100

# Different color scheme
python visualize_usa_overhead.py --colormap earth

# 9 different viewpoints automatically
python visualize_usa_overhead.py --gen-nine

# High-resolution print output (300 DPI)
python visualize_usa_overhead.py --dpi 300 --scale-factor 8
```

### Download Elevation Data

The unified downloader provides one command to download elevation data for any region:

```powershell
# US States (auto-clips to state boundaries)
python download_unified.py california --process
python download_unified.py colorado --process

# Japanese regions  
python download_unified.py shikoku --process

# Switzerland
python download_unified.py switzerland --process

# Any built-in region (200+ available)
python download_unified.py iceland --process

# List all available regions
python download_unified.py --list
```

### View in 3D

After downloading data:

```powershell
python serve_viewer.py
```

Then open http://localhost:8001 in your browser. Select your region from the dropdown!

## Data Sources

### USA - USGS 3DEP (1-10m)
- **Best quality** for USA
- **10m resolution** available for all states
- **Download**: `python downloaders/usa_3dep.py california --auto`
- Or follow manual download instructions for 10m data

### Global - SRTM (30m)
- **Good coverage**: 60°N to 56°S (most populated areas)
- **Works everywhere**: Automatic download via OpenTopography
- **Download**: `python download_unified.py <region> --process`

### Japan - ALOS World 3D (30m)
- **Best for Japan** and mountain regions
- **Excellent quality**: Made by JAXA specifically for terrain
- **Download**: `python download_unified.py japan --process`

### Other High-Quality National Sources
- **Switzerland**: SwissTopo (0.5-2m) - manual download
- **Germany**: BKG (1-25m) - manual download  
- **Australia**: Geoscience (5m) - manual download

Priority: Always use nation-specific sources when available (better quality than global datasets).

## Key Features

### Multi-Region Support
Switch between 45+ pre-configured regions with a dropdown selector. All regions are cached - switching is instant after first load.

### Camera Controls

**Ground Plane System** - Modeled after Google Earth for intuitive navigation:
- Focus point anchored on ground plane (where camera looks)
- All operations relative to this plane for predictable behavior
- Infinite zoom capability

**Interaction Modes**:
1. **Pan** (Left drag): Drag map surface, point under cursor stays locked
2. **Rotate** (Right drag): Orbit around focus point  
3. **Tilt** (Shift + Left drag): Adjust viewing angle
4. **Zoom** (Mouse wheel): Zoom toward cursor point with bidirectional focus shift

### Visualization Modes

**Bars**: 3D rectangular prisms showing discrete data points
- Best for: Clear data visualization, understanding grid structure
- Performance: Excellent (instanced rendering)

**Surface**: Smooth terrain mesh with shading
- Best for: Realistic appearance, large datasets
- Performance: Good

**Wireframe**: Mesh structure overlay
- Best for: Technical analysis, understanding topology

**Point Cloud**: Individual elevation points
- Best for: Very large datasets, understanding data density

### Vertical Exaggeration

**Meter-based Scale**:
- **1.0×**: True Earth proportions (1000m horizontal = 1000m vertical)
- **4.0×**: Default (moderately dramatic)
- **10.0×**: Very dramatic terrain
- **25.0×**: Extreme exaggeration

Both X/Z (horizontal) and Y (elevation) axes use real meters based on lat/lon bounds.

### Border Features

**177 Countries Available** from Natural Earth:
- Overlay country boundaries on maps
- Clip elevation to country boundaries
- Automatic caching for performance

**Usage**:
```powershell
# Export with borders
python export_for_web_viewer.py data/usa.tif --export-borders

# Mask to specific country
python export_for_web_viewer.py data/usa.tif --mask-country "United States of America"
```

## Performance Tips

### Interactive Viewer
- **Default bucket size**: 12×12 pixels works for most cases
- **If laggy**: Increase to 16-25 in sidebar
- **For smooth 60 FPS**: Keep bar count under 15,000
- **Surface mode**: Faster rendering for very large datasets

### Static Rendering
- **Bucketing**: Dramatically speeds up rendering
  - No bucketing: 640,000 data points, 30-60 seconds
  - 100-mile buckets: ~1,200 data points, 5-10 seconds
- **Trade-off**: Bucketing loses fine detail but highlights major features

## Troubleshooting

### "File not found" Error
Download the data first:
```powershell
python download_unified.py usa --process
```

### "Module not found" Error
Activate the virtual environment:
```powershell
.\venv\Scripts\Activate.ps1
```

### Interactive Viewer Shows Nothing
The viewer requires a local server (doesn't work with `file://` protocol):
```powershell
python serve_viewer.py
# Then open: http://localhost:8001
```

### Slow/Laggy Interactive Viewer
In the viewer sidebar, increase **Bucket Size** to 16 or 20. This reduces the number of terrain blocks.

### "Unknown region"
Run `python download_unified.py --list` to see all available regions, or provide custom bounds:
```powershell
python download_unified.py myregion --bounds 155 50 163 61 --process
```

### Region doesn't appear in dropdown
```powershell
python regenerate_manifest.py
```
Then refresh the browser.

## Common Workflows

### View a New Region
1. Download: `python download_unified.py <region> --process`
2. Open viewer: `python serve_viewer.py`
3. Select region from dropdown
4. Adjust vertical exaggeration for visibility
5. Adjust bucket size if performance is poor

### Compare Regions
1. Load first region
2. Note elevation patterns
3. Select different region from dropdown
4. Use same camera presets for consistency
5. Compare visual characteristics

### Export Screenshot
1. Position camera to desired view
2. Adjust visual settings (colors, wireframe, etc.)
3. Click "📸 Save Screenshot" button in viewer
4. Image downloads automatically

## Advanced Configuration

### Custom Regions
Define custom bounding boxes:
```powershell
python download_unified.py my_region --bounds <west> <south> <east> <north> --process
```

The bounds format is: `west south east north` (in degrees).

### Choose Specific Dataset
```powershell
# Use Copernicus DEM instead of default
python download_unified.py alps --dataset COP30 --process

# Use ALOS for high mountains
python download_unified.py nepal --dataset AW3D30 --process
```

Available Los conjuntos de datos: SRTMGL1, AW3D30, COP30, COP90, NASADEM

### Control Resolution
```powershell
# Higher resolution export (larger file)
python download_unified.py yosemite --process --target-pixels 2048

# Lower resolution (faster, smaller)
python download_unified.py texas --process --target-pixels 400
```

## Technical Reference

For detailed technical information, see:
- **TECHNICAL_REFERENCE.md**: Complete API, file formats, controls reference
- **DOWNLOAD_GUIDE.md**: Data acquisition workflows
- **CAMERA_CONTROLS.md**: Detailed camera system documentation

## Next Steps

- Explore the interactive viewer with different regions
- Generate static visualizations with custom parameters  
- Download your own regions of interest
- Read technical documentation for advanced features

**Ready to explore Earth's terrain!**

