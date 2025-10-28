# 🗺️ Altitude Maps

**3D visualization toolkit for elevation data from anywhere on Earth.**

![Continental USA Example](Screenshot_20251021115239.png)

## What Is This?

Altitude Maps is a Python toolkit for visualizing elevation and terrain data. Whether you're a researcher, educator, or just curious about Earth's geography, this project lets you:

- **Explore terrain interactively in 3D** with flying camera controls
- **Generate static renders** of any region's terrain  
- **Download elevation data** for anywhere in the world
- **Customize rendering** - colors, angles, resolution, render style

## Recent Updates (October 2025)

### 🎮 Camera Control Enhancements (October 28, 2025)
Major updates to interactive viewer controls:
- **WASD/QE flythrough** - Unity/Unreal-style first-person camera movement
- **F key reframe** - Instantly center view on terrain bounds (like Maya/Blender)
- **Touch & trackpad gestures** - Pinch zoom, two-finger pan (Google Maps style)
- **Alt+Left rotate** - Maya/3ds Max style tumble (same as right-drag)
- **Smart typing detection** - Keyboard shortcuts disabled while typing in inputs
- All controls work simultaneously with no conflicts

### 🎯 Multi-Region Support
The interactive viewer now supports **45+ pre-configured regions worldwide** with a dropdown selector! Switch between USA, Japan, Switzerland, and more without refreshing. Just download data for your regions and they appear automatically.

### 🎨 Bar Rendering Improvements
- **Fixed bar overlapping and gaps** - Bars now use rectangular geometry matching actual grid spacing
- **Infinite zoom** - Removed artificial zoom-out limits
- **Smart defaults** - USA loads by default when available
- **Perfect tiling** - No more black gaps between bars at any angle

### 📏 Real-World Scale (Vertical Exaggeration Fix)
Vertical exaggeration now uses **intuitive meter-based scale**:
- **1.0x** = True Earth proportions (1000m horizontal = 1000m vertical)
- **4.0x** = New default (moderately dramatic)
- **10.0x** = Very dramatic terrain
- Both X/Z and Y axes now use real meters from lat/lon bounds

### 🗺️ Enhanced Border Features
- **177 countries available** from Natural Earth (10m/50m/110m resolution)
- **Interactive viewer borders** - Toggle country boundaries in 3D
- **Country masking** - Clip data to specific nations
- **Auto-caching** - Borders download once and reuse automatically
- Export with: `python export_for_web_viewer.py data/usa.tif --export-borders`

## What Can You Do With It?

### 1. Create Static Visualizations

Generate high-resolution overhead views, 3D perspectives, or dramatic side-angle renders of any terrain:

```powershell
# Overhead view of continental USA
python visualize_usa_overhead.py

# With custom styling
python visualize_usa_overhead.py --bucket-miles 100 --camera-elevation 35 --colormap earth

# Generate 9 different viewpoints
python visualize_usa_overhead.py --gen-nine
```

**Outputs**: PNG images (default 100 DPI) with geographic labeling.

### 2. Draw National Borders & Mask by Country

Overlay country boundaries and clip elevation data to specific countries:

```python
# Draw USA borders on elevation map
render_visualization(
    data,
    draw_borders="United States of America",
    border_color="#FF0000",
    tif_path="data/usa_elevation/nationwide_usa_elevation.tif"
)

# Mask data to show only USA territory
data = prepare_visualization_data(
    "data/usa_elevation/nationwide_usa_elevation.tif",
    mask_country="United States of America"
)
```

**Features**:
- Draw borders for any country or auto-detect from region
- Clip/mask data to country boundaries
- Support for multiple countries
- Three detail levels (10m, 50m, 110m resolution)

**Utility tools**:
```bash
# List available countries
python border_utils.py --list

# Find countries in a region
python border_utils.py --bbox "-125,25,-65,50"

# Test borders on your data
python border_utils.py --test your_data.tif
```

See borders documentation in `tech/TECHNICAL_REFERENCE.md`.

### 3. Work With Real Data

Download elevation data from:
- **USA**: 1-10 meter resolution (USGS 3DEP)
- **Global**: 30-90 meter resolution (SRTM, ASTER, ALOS)
- **Europe, Japan, Australia**: High-quality national datasets

All data is cached locally - download once, use forever.

## Who Is This For?

✅ **Researchers** - Visualize terrain for papers and presentations  
✅ **Educators** - Teach geography and geology with interactive 3D  
✅ **GIS professionals** - Quick visualization prototyping  
✅ **Hobbyists** - Explore Earth's terrain beautifully  
✅ **Developers** - Foundation for mapping/terrain projects

## Quick Start

```powershell
# 1. Setup (one time)
.\setup.ps1

# 2. Start interactive viewer (recommended)
python -m http.server 8001
# Then open: http://localhost:8001/interactive_viewer_advanced.html

# 3. Or generate a static image
python visualize_usa_overhead.py
```

See [User Guide](tech/USER_GUIDE.md) for more details.

## Key Features

### 🎨 **Flexible Visualization**
- Multiple render modes: smooth surfaces, 3D bars, wireframe
- 7 color schemes: terrain, earth, ocean, viridis, plasma, grayscale, rainbow
- Customizable camera angles, lighting, and vertical exaggeration
- Generate multiple viewpoints with `--gen-nine`

### 🌍 **Global Coverage**
- USA: 10m resolution via USGS 3DEP
- 60+ pre-configured regions worldwide
- Support for any GeoTIFF elevation data
- Add custom regions as needed

### ⚡ **Performance**
- Instanced rendering: 10,000+ terrain blocks at 60 FPS
- Real-time bucketing and aggregation (MAX/AVERAGE/MIN/MEDIAN)
- Data caching prevents re-downloading
- Progressive loading for large datasets

### 🎮 **Controls** (October 2025 Update)
- **Mouse**: 
  - Left-drag = pan, Shift+Left-drag = tilt
  - Right-drag or Alt+Left-drag = rotate (Google Earth/Maya style)
  - Wheel = zoom toward cursor
- **Keyboard**: 
  - WASD = fly forward/left/back/right
  - QE = descend/ascend
  - F = reframe view to terrain center
  - R = reset camera, Space = toggle auto-rotate
- **Touch/Trackpad**: 
  - Single/two-finger drag = pan
  - Pinch = zoom (mobile & laptop trackpads)
- **Smart**: Keys disabled while typing in input fields

## Example Use Cases

**Research Publication**: Generate high-res static renders with exact camera parameters  
**Education**: Students explore mountain ranges interactively in 3D  
**GIS Analysis**: Quick terrain visualization before detailed analysis  
**Art/Design**: Create terrain art with customizable colors and angles  
**Game Development**: Preview elevation data for game level design

## Tech Stack

- **Python 3.13** - Modern, type-safe codebase
- **rasterio** - GeoTIFF data handling
- **matplotlib** - Static high-quality renders
- **Three.js** - Interactive WebGL visualization
- **NumPy** - Fast array processing

## Project Structure

```
altitude-maps/
├── visualize_usa_overhead.py      # Main static renderer
├── interactive_viewer_advanced.html  # Interactive 3D viewer
├── download_*.py                  # Data acquisition scripts
├── data/                          # Downloaded elevation data (gitignored)
├── generated/                     # Your visualizations
├── src/                           # Core processing modules
└── requirements.txt               # Python dependencies
```

## What's Included

### 🖼️ Static Visualization Tools
- `visualize_usa_overhead.py` - Main renderer with full customization
- `visualize_real_data.py` - Multiple views at once
- `visualize.py` - Demo with synthetic data

### 🌐 Interactive 3D Viewer
- `interactive_viewer_advanced.html` - Full-featured viewer
- Real-time bucketing and aggregation
- Multiple render modes and color schemes
- Roblox Studio-inspired camera controls

### 📥 Data Download Tools
- `download_continental_usa.py` - Full USA download
- `download_regions.py` - Multi-region batch download
- `download_usa_region.py` - Specific US landmarks
- `download_us_states.py` - Individual US states

### 🔧 Utilities
- `export_for_web_viewer.py` - Process data for interactive viewer
- `setup.ps1` - One-command environment setup
- `src/` - Reusable processing modules

## Documentation

- **[tech/USER_GUIDE.md](tech/USER_GUIDE.md)** - Complete usage guide
- **[tech/TECHNICAL_REFERENCE.md](tech/TECHNICAL_REFERENCE.md)** - Technical specs and API reference
- **[tech/DOWNLOAD_GUIDE.md](tech/DOWNLOAD_GUIDE.md)** - Data acquisition workflows
- **[tech/CAMERA_CONTROLS.md](tech/CAMERA_CONTROLS.md)** - Camera system documentation
- **[.cursorrules](.cursorrules)** - Development patterns for AI agents
- **[learnings/](learnings/)** - Historical development threads

## Sample Outputs

Visualizations are timestamped and saved to `generated/`:

- **Overhead views**: Satellite-style perspectives
- **3D terrain**: Side angles showing elevation
- **Bar charts**: Bucketed elevation as 3D rectangular prisms
- **Multiple viewpoints**: 9 angles with `--gen-nine`

Images include:
- Geographic coordinates and bounds
- Elevation statistics (min/max/range)
- Data source attribution
- Reproduction command (exact parameters to recreate)

## Requirements

- **Windows** (PowerShell for setup script) / Mac / Linux
- **Python 3.13** (or 3.10+)
- **Modern web browser** (Chrome, Firefox, Edge, Safari) for interactive viewer
- **~500MB disk space** for data cache

## Contributing

This is a personal project, but suggestions and feedback are welcome! Check the code style in `.cursorrules` if you'd like to contribute.

## Data Attribution

When using elevation data, please credit:
- **USGS 3DEP**: USA elevation data
- **NASA SRTM**: Global elevation data (shuttle radar topography mission)
- Specific national sources as noted in downloads

## License

Project code is available for personal and educational use. Elevation data has separate licensing from their respective sources (generally public domain or open access).

---

**Created for**: Exploring and visualizing Earth's incredible terrain  
**Status**: Production-ready, actively maintained  
**Last Updated**: October 22, 2025

**Got questions?** Check [tech/USER_GUIDE.md](tech/USER_GUIDE.md) or [tech/TECHNICAL_REFERENCE.md](tech/TECHNICAL_REFERENCE.md)
