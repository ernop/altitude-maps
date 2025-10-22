# 🗺️ Altitude Maps

**Create stunning 3D visualizations of elevation data from anywhere on Earth.**

![Continental USA Example](Screenshot_20251021115239.png)

## What Is This?

Altitude Maps is a Python toolkit for visualizing elevation and terrain data in beautiful, explorable ways. Whether you're a researcher, educator, or just curious about Earth's geography, this project makes it easy to:

- **Generate beautiful static renders** of any region's terrain
- **Explore interactively in 3D** with intuitive flying camera controls
- **Download elevation data** for anywhere in the world
- **Customize everything** - colors, angles, resolution, render style

## What Can You Do With It?

### 1. Create Stunning Static Visualizations

Generate high-resolution overhead views, 3D perspectives, or dramatic side-angle renders of any terrain:

```powershell
# Beautiful overhead view of continental USA
python visualize_usa_overhead.py

# With custom styling
python visualize_usa_overhead.py --bucket-miles 100 --camera-elevation 35 --colormap earth

# Generate 9 different viewpoints automatically
python visualize_usa_overhead.py --gen-nine
```

**Outputs**: Publication-quality PNG images (300 DPI) with proper geographic labeling.

### 2. Explore Terrain Interactively

Open `interactive_viewer_advanced.html` in your browser and fly through 3D terrain like a video game:

- **Roblox Studio-style controls** - WASD to fly, right-click to look around
- **Real-time adjustments** - Change bucket size, colors, vertical exaggeration on the fly
- **Multiple regions** - Switch between USA, Japan, Switzerland, and more
- **Smooth performance** - Optimized rendering with instancing

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

# 2. Generate your first visualization
python visualize_usa_overhead.py

# 3. Open interactive viewer
# Just open interactive_viewer_advanced.html in your browser
```

**That's it!** See [QUICKSTART.md](QUICKSTART.md) for more details.

## Key Features

### 🎨 **Flexible Visualization**
- Multiple render modes: smooth surfaces, 3D bars, wireframe
- 7 color schemes: terrain, earth, ocean, viridis, plasma, grayscale, rainbow
- Customizable camera angles, lighting, and vertical exaggeration
- Auto-generate multiple viewpoints with `--gen-nine`

### 🌍 **Global Coverage**
- USA: Full coverage at 10m resolution
- 60+ pre-configured regions worldwide
- Support for any GeoTIFF elevation data
- Easy to add custom regions

### ⚡ **Performance**
- Instanced rendering for 10,000+ terrain blocks at 60 FPS
- Real-time bucketing and aggregation (MAX/AVERAGE/MIN/MEDIAN)
- Data caching - never re-download
- Progressive loading for large datasets

### 🎮 **Intuitive Controls**
- **Mouse**: Right-click to rotate, wheel to zoom, left-click to pan
- **Keyboard**: WASD for flying, QE for up/down, Shift for speed boost
- **Modifiers**: Ctrl (slow/precise), Alt (4× speed), Shift (2.5× speed)
- **Presets**: Overhead, cardinal directions, isometric views

## Example Use Cases

**Research Publication**: Generate high-res static renders with exact camera parameters  
**Education**: Students explore mountain ranges interactively in 3D  
**GIS Analysis**: Quick terrain visualization before detailed analysis  
**Art/Design**: Create stunning terrain art with customizable colors and angles  
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

- **[QUICKSTART.md](QUICKSTART.md)** - Get running in 5 minutes
- **[TECH.md](TECH.md)** - Technical reference (data sources, controls, options)
- **[.cursorrules](.cursorrules)** - Development patterns for AI agents
- **[learnings/](learnings/)** - Session notes and deep dives

## Sample Outputs

All visualizations are timestamped and saved to `generated/`:

- **Overhead views**: Satellite-style perspectives
- **3D terrain**: Dramatic side angles showing elevation
- **Bar charts**: Bucketed elevation as 3D rectangular prisms
- **Multiple viewpoints**: 9 angles automatically with `--gen-nine`

Every image includes:
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

**Got questions?** Check [QUICKSTART.md](QUICKSTART.md) or [TECH.md](TECH.md)
