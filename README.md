# Altitude Maps

**3D visualization toolkit for elevation data from anywhere on Earth.**

![Continental USA Example](Screenshot_20251021115239.png)

## What Is This?

Altitude Maps lets you explore and visualize terrain elevation data in interactive 3D. Whether you're a researcher, educator, or curious explorer, you can:

- **Explore terrain interactively in 3D** with smooth camera controls
- **Generate static visualizations** of any region's terrain
- **Download elevation data** for anywhere in the world
- **Customize visualization** - colors, viewing angles, detail level, rendering style

## Recent Updates

### Camera Control Enhancements
- **WASD/QE flythrough** - First-person camera movement
- **F key reframe** - Instantly center view on terrain
- **Touch & trackpad gestures** - Pinch zoom, two-finger pan
- **Alt+Left rotate** - Professional 3D software style rotation
- **Smart typing detection** - Keyboard shortcuts disabled while typing

### Multi-Region Support
The interactive viewer supports **89 pre-configured regions worldwide** with a dropdown selector. Switch between US states, countries, and custom regions without refreshing.

### Bar Rendering Improvements
- Fixed bar overlapping and gaps
- Infinite zoom capability
- Smart defaults for quick start
- Perfect tiling at any viewing angle

### Real-World Scale
Vertical exaggeration uses intuitive meter-based scale:
- **1.0x** = True Earth proportions
- **4.0x** = Moderately dramatic (default)
- **10.0x** = Very dramatic terrain

### Enhanced Border Features
- **177 countries available** with detailed boundaries
- **Interactive viewer borders** - Toggle country boundaries in 3D
- **Country masking** - Clip data to specific nations
- **Auto-caching** - Borders download once and reuse automatically

## What Can You Do With It?

### 1. Create Static Visualizations

Generate high-quality overhead views, 3D perspectives, or dramatic side-angle renders of any terrain. Outputs include geographic coordinates, elevation statistics, and data source attribution.

### 2. Draw National Borders & Mask by Country

Overlay country boundaries and clip elevation data to specific countries. Features include:
- Draw borders for any country
- Clip/mask data to country boundaries
- Support for multiple countries
- Three detail levels available

### 3. Work With Real Data

Download elevation data with automatic quality selection:
- **USA**: High-quality data with automatic quality selection
- **Global**: Worldwide coverage with automatic quality selection
- **Europe, Japan, Australia**: National datasets where available

All data is cached locally - download once, use forever. Quality is selected automatically based on your needs.

## Who Is This For?

**Researchers** - Visualize terrain for papers and presentations  
**Educators** - Teach geography and geology with interactive 3D  
**GIS professionals** - Quick visualization prototyping  
**Hobbyists** - Explore Earth's terrain beautifully  
**Developers** - Foundation for mapping/terrain projects

## Quick Start

1. **Setup** (one time) - Run the setup script
2. **Download a region** - Choose from US states or international regions
3. **Start interactive viewer** - Explore in 3D
4. **Or generate a static image** - Create visualizations

See `install.md` for installation instructions.

## Deployment

The viewer runs entirely in your web browser - no server-side code needed. Deploy to any static web server. See `DEPLOY_README.md` for deployment instructions.

## Key Features

### Flexible Visualization
- 3D terrain rendering
- Multiple color schemes
- Customizable camera angles and lighting
- Adjustable vertical exaggeration
- Generate multiple viewpoints

### Global Coverage
- USA: High-quality data with automatic quality selection
- 89 pre-configured regions worldwide
- Support for custom regions
- Add your own regions as needed

### Performance
- Smooth rendering of large terrain areas
- Real-time detail adjustment
- Data caching prevents re-downloading
- Progressive loading for large datasets

### Controls
- **Mouse**: Pan, tilt, rotate, zoom toward cursor
- **Keyboard**: Fly through terrain, reframe view, reset camera
- **Touch/Trackpad**: Pan and zoom gestures
- **Smart**: Keys disabled while typing in input fields

## Example Use Cases

**Research Publication** - Generate high-quality static renders with precise viewing angles  
**Education** - Students explore mountain ranges interactively in 3D  
**GIS Analysis** - Quick terrain visualization before detailed analysis  
**Art/Design** - Create terrain art with customizable colors and angles  
**Game Development** - Preview elevation data for game level design

## What's Included

### Static Visualization Tools
- Main renderer with full customization
- Multiple views at once
- Demo with sample data

### Interactive 3D Viewer
- Full-featured viewer
- Real-time detail adjustment
- Multiple render modes and color schemes
- Multiple camera control schemes

### Data Download Tools
- Full USA download
- Multi-region batch download
- Individual region downloads
- Automatic quality selection

### Utilities
- Process data for interactive viewer
- One-command environment setup
- Reusable processing modules

## Documentation

- **install.md** - Installation instructions
- **technicalDetails.md** - Technical specifications
- **DEPLOY_README.md** - Deployment guide

## Sample Outputs

Visualizations are saved with timestamps and include:
- Geographic coordinates and bounds
- Elevation statistics
- Data source attribution
- Reproduction parameters

## Requirements

- Windows / Mac / Linux
- Modern web browser for interactive viewer
- Disk space for data cache

## Contributing

This is a personal project, but suggestions and feedback are welcome!

## Data Attribution

When using elevation data, please credit the data sources:
- USGS 3DEP for USA elevation data
- NASA SRTM for global elevation data
- Specific national sources as noted in downloads

## License

Project code is available for personal and educational use. Elevation data has separate licensing from their respective sources (generally public domain or open access).

---

**Created for**: Exploring and visualizing Earth's incredible terrain  
**Status**: Production-ready, actively maintained
