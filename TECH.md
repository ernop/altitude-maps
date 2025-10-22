# Technical Reference

Complete technical documentation for Altitude Maps.

---

## Table of Contents

1. [Data Sources & Downloads](#data-sources--downloads)
2. [CLI Reference](#cli-reference)
3. [Interactive Viewer](#interactive-viewer)
4. [File Formats](#file-formats)
5. [Performance & Optimization](#performance--optimization)
6. [Region Definitions](#region-definitions)

---

## Data Sources & Downloads

### USA Elevation Data

**Source**: USGS 3D Elevation Program (3DEP)
- **Resolution**: 1m to 10m depending on area
- **Coverage**: Full USA
- **Quality**: Excellent, frequently updated
- **API**: https://elevation.nationalmap.gov/

**Download Command**:
```powershell
# Full nationwide USA
python download_continental_usa.py --yes

# Specific regions
python download_continental_usa.py --region usa_west --yes
python download_continental_usa.py --region usa_east --yes
```

**Available USA Regions**:
- `nationwide_usa` - Complete USA (-125°W to -66°W, 24°N to 49.5°N)
- `continental_usa` - Continental USA (similar coverage)
- `usa_west` - Western half
- `usa_east` - Eastern half

**Output**: `data/usa_elevation/{region}_elevation.tif` (~3-6 MB)

### Global Elevation Data

For regions outside the USA, you need to manually download elevation data.

#### Recommended Source: OpenTopography (SRTM Data)

**Website**: https://portal.opentopography.org/raster?opentopoID=OTSRTM.082015.4326.1

**Coverage**: 60°N to 56°S (most populated areas)
**Resolution**: 30m (1 arc-second) or 90m (3 arc-second)
**Format**: GeoTIFF

**Steps**:
1. Go to OpenTopography link above
2. Click "Select a Region"
3. Enter coordinates or draw bounding box
4. Choose "SRTM GL1 (Global 30m)" dataset
5. Select output format: **GeoTiff**
6. Click "Submit" and wait for download link
7. Save to: `data/regions/{region_name}.tif`
8. Process: `python download_regions.py --regions {region_name}`

#### Alternative Global Sources

**ASTER GDEM**:
- Coverage: 83°N to 83°S (99% of Earth)
- Resolution: 30m
- Website: https://asterweb.jpl.nasa.gov/gdem.asp

**Copernicus DEM**:
- Coverage: Global
- Resolution: 30m (GLO-30) or 90m (GLO-90)
- Quality: Very good, newest (2021)
- Website: https://copernicus-dem-30m.s3.amazonaws.com/

**ALOS World 3D (AW3D30)**:
- Coverage: Global
- Resolution: 30m (free), 5m (commercial)
- Quality: Better than SRTM
- Website: https://www.eorc.jaxa.jp/ALOS/en/aw3d30/

#### Country-Specific High-Resolution Sources

**Germany** (1-25m):
- Website: https://gdz.bkg.bund.de/
- DGM1 (1m), DGM5 (5m), DGM50 (50m)

**Japan** (5-10m):
- Website: https://fgd.gsi.go.jp/download/
- Geospatial Information Authority of Japan

**Europe** (25m):
- EU-DEM via Copernicus Land Monitoring Service
- Website: https://land.copernicus.eu/imagery-in-situ/eu-dem

**Australia** (5m):
- Website: https://elevation.fsdf.org.au/

**Canada** (20m):
- CDEM (Canadian Digital Elevation Model)
- Website: https://open.canada.ca/

---

## CLI Reference

### visualize_usa_overhead.py

Main visualization tool with full customization options.

#### Basic Usage
```powershell
python visualize_usa_overhead.py [tif_file] [options]
```

#### Input
```powershell
# Use default USA data
python visualize_usa_overhead.py

# Use specific file
python visualize_usa_overhead.py data/regions/japan.tif
```

#### Bucketing Options

**Geographic Bucketing** (accounts for Earth's curvature):
```powershell
--bucket-miles N      # Divide into N×N mile squares, take MAX elevation
                      # Example: --bucket-miles 100
```

**Pixel Bucketing** (simple grid):
```powershell
--bucket-pixels N     # Divide into N×N pixel squares, take MAX elevation
                      # Example: --bucket-pixels 50
```

#### Camera Controls
```powershell
--camera-elevation N     # Angle: 0=horizon, 90=overhead (default: 35)
--camera-azimuth N       # Rotation: 0-360 degrees (default: 45)
--vertical-exaggeration N  # Vertical scale: 1.0=true Earth scale, 0.1-50.0 (default: 4.0)
--projection-zoom N      # Viewport fill: 0.90-0.99 (default: 0.99)
```

#### Rendering Modes
```powershell
--render-bars         # Force 3D rectangular prisms
--render-surface      # Force smooth surface (default unless bucketing)
```

#### Visual Style
```powershell
--colormap NAME       # terrain, viridis, plasma, inferno, earth, ocean, grayscale
--background-color HEX  # e.g., #000000 (black) or #FFFFFF (white)
--light-azimuth N     # Light direction: 0-360 (default: 315)
--light-altitude N    # Light angle: 0-90 (default: 60)
```

#### Resolution & Quality
```powershell
--dpi N               # Output DPI (default: 100, try 300 for print)
--scale-factor N      # Resolution multiplier (default: 4.0)
--max-viz-size N      # Max grid dimension (default: 800)
```

#### Output Options
```powershell
--output DIR, -o DIR  # Output directory (default: generated)
--filename-prefix NAME  # Custom prefix (default: timestamp)
--no-overlays         # Disable text labels
--no-autocrop         # Disable border trimming
--gen-nine            # Auto-generate 9 viewpoints (overrides camera settings)
```

#### Examples
```powershell
# Dramatic peaks with 100-mile buckets
python visualize_usa_overhead.py --bucket-miles 100

# Overhead satellite view
python visualize_usa_overhead.py --camera-elevation 90 --camera-azimuth 0

# 9 different viewpoints automatically
python visualize_usa_overhead.py --gen-nine

# High-resolution print output
python visualize_usa_overhead.py --dpi 300 --scale-factor 8 --colormap earth

# Clean scientific visualization
python visualize_usa_overhead.py --no-overlays --colormap viridis --background-color #FFFFFF
```

### download_continental_usa.py

Download USA elevation data from USGS 3DEP.

```powershell
python download_continental_usa.py [options]
```

**Options**:
```powershell
--region NAME    # nationwide_usa, continental_usa, usa_west, usa_east
--output-dir DIR # Where to save (default: data/usa_elevation)
--yes, -y        # Skip confirmation
```

**Example**:
```powershell
python download_continental_usa.py --region nationwide_usa --yes
```

### download_regions.py

Process elevation TIF files into JSON for interactive viewer.

```powershell
python download_regions.py [options]
```

**Options**:
```powershell
--regions NAME [NAME ...]  # Which regions to process
--list                     # List all available region definitions
--data-dir DIR             # Where TIF files are (default: data/regions)
--output-dir DIR           # Where to save JSON (default: generated/regions)
--max-size N               # Output resolution (default: 800, 0=full res)
```

**Examples**:
```powershell
# List all 60+ pre-configured regions
python download_regions.py --list

# Process specific regions (TIF files must exist in data/regions/)
python download_regions.py --regions japan germany switzerland

# High resolution output
python download_regions.py --regions colorado --max-size 1024
```

### export_for_web_viewer.py

Export single-region data for interactive viewer (legacy, use download_regions.py instead).

```powershell
python export_for_web_viewer.py [tif_file] [options]
```

---

## Interactive Viewer

The interactive 3D viewer (`interactive_viewer_advanced.html`) provides real-time exploration of elevation data.

**Primary Usage**:
```powershell
python -m http.server 8001
# Open browser to: http://localhost:8001/interactive_viewer_advanced.html
```

**Note**: Requires local server - will not work with `file://` protocol.

### Features

- **Region Switching**: Dropdown selector for all processed regions
- **Real-Time Bucketing**: Adjust grid resolution on the fly (1-50 pixels)
- **Aggregation Methods**: MAX, AVERAGE, MIN, MEDIAN
- **Render Modes**: Bars, Surface, Wireframe, Points
- **Color Schemes**: 6 options (terrain, earth, ocean, viridis, plasma, grayscale)
- **Camera Presets**: Overhead, cardinal directions, isometric
- **Performance**: Instanced rendering for 10,000+ blocks at 60 FPS

### Controls

#### Mouse
| Action | Control |
|--------|---------|
| **Look Around** | Right-Click + Drag |
| **Pan** | Left-Click + Drag |
| **Rotate (Alt)** | Ctrl + Left-Click + Drag |
| **Zoom** | Mouse Wheel or Middle-Click + Drag |

#### Keyboard - Movement
| Key | Action | Description |
|-----|--------|-------------|
| **W** | Move Up | Raise camera vertically |
| **S** | Move Down | Lower camera vertically |
| **A** | Rotate Left | Spin counter-clockwise |
| **D** | Rotate Right | Spin clockwise |
| **Q** | Move Backward | Fly away from view direction |
| **E** | Move Forward | Fly toward view direction |
| **R** | Reset | Return to default camera position |
| **F** | Focus | Same as R (Roblox Studio style) |
| **Space** | Auto-Rotate | Toggle automatic rotation |

#### Keyboard - Speed Modifiers
| Modifier | Multiplier | Use Case |
|----------|-----------|----------|
| None | 1.0× | Normal speed |
| **Shift** | 2.5× | Fast movement |
| **Ctrl** | 0.3× | Slow/precise movement |
| **Alt** | 4.0× | Very fast movement |
| **Shift+Alt** | 10× | Turbo mode! |

**Examples**:
- `Shift + W` = Move up fast
- `Ctrl + A` = Rotate left slowly (precise)
- `Alt + E` = Fly forward very fast

### UI Controls

**Bucketing**:
- Slider: 1×1 (full resolution) to 50×50 pixels
- Real-time updates

**Aggregation**:
- MAX: Highlights peaks (default)
- AVERAGE: Smooth terrain representation
- MIN: Emphasizes valleys
- MEDIAN: Middle value (outlier-resistant)

**Rendering**:
- Render Mode: Bars, Surface, Wireframe, Points
- Vertical Exaggeration: 0.1× to 50× (interactive slider, 1.0 = true Earth scale)
- Grid Resolution: 10% to 100% (performance tuning)

**Visual**:
- Color Scheme: 6 palettes
- Wireframe Overlay: Toggle mesh structure
- Ground Grid: Reference grid at base

**Camera**:
- Presets: Overhead, North, South, East, West, Isometric
- Manual: Use keyboard/mouse controls

**Export**:
- Screenshot: Downloads current view as PNG

### Performance Optimization

The viewer uses several optimizations:

1. **Instanced Rendering**: Single draw call for all terrain blocks
2. **Simplified Geometry**: 8 vertices, 12 triangles per block
3. **MeshLambertMaterial**: Fast diffuse shader (vs. PBR)
4. **Debouncing**: 150ms delay on slider changes
5. **Typed Arrays**: Pre-allocated buffers for bucketing
6. **Conservative Defaults**: 12×12 bucket size on load

**Performance Targets**:
| Bar Count | Expected FPS | Experience |
|-----------|--------------|------------|
| < 5,000 | 60 FPS | Butter smooth |
| 5,000-10,000 | 30-60 FPS | Good |
| 10,000-20,000 | 15-30 FPS | Acceptable |
| > 20,000 | < 15 FPS | Laggy - increase bucket size |

**If Laggy**:
1. Increase bucket size to 16-25
2. Switch to Surface render mode
3. Reduce grid resolution to 50-75%
4. Close other browser tabs

### Adding New Regions

1. Download elevation data (GeoTIFF) for your region
2. Save to `data/regions/{region_id}.tif`
3. Process: `python download_regions.py --regions {region_id}`
4. Refresh browser - region appears in dropdown!

**Pre-configured Regions** (60+):
See `python download_regions.py --list` for complete list.

---

## File Formats

### GeoTIFF (.tif)

**Description**: Geographic Tagged Image File Format - raster elevation data with embedded geographic metadata.

**Contains**:
- Elevation values (32-bit or 16-bit floats/integers)
- Coordinate Reference System (CRS/projection)
- Geographic bounds (lat/lon or projected)
- Spatial resolution (meters per pixel)
- Affine transform (pixel → real-world coordinates)

**Tools**:
- Python: `rasterio`, `GDAL`
- Desktop: QGIS (free), Global Mapper, ArcGIS
- Command: `gdalinfo` (view metadata), `gdal_translate` (convert), `gdalwarp` (reproject)

### JSON (.json)

**Description**: Processed elevation data for web viewer.

**Structure**:
```json
{
  "width": 800,
  "height": 600,
  "elevation": [[z00, z01, ...], [z10, z11, ...], ...],
  "bounds": {
    "left": -125.0,
    "bottom": 24.0,
    "right": -66.0,
    "top": 49.5
  },
  "stats": {
    "min": -152.0,
    "max": 4115.0,
    "mean": 650.0
  }
}
```

**Notes**:
- 2D array: `elevation[row][col]` where row=0 is top (north)
- Coordinates in WGS84 (EPSG:4326)
- Elevation in meters
- File size: 1-10 MB typical (800×800)

### Regions Manifest

**File**: `generated/regions/regions_manifest.json`

**Purpose**: Lists all available regions for viewer dropdown.

**Structure**:
```json
{
  "regions": [
    {
      "id": "usa_full",
      "name": "USA (Contiguous)",
      "description": "Continental United States",
      "group": "North America",
      "file": "generated/regions/usa_full.json"
    },
    ...
  ]
}
```

---

## Performance & Optimization

### Static Rendering

**Bucketing** dramatically speeds up rendering by reducing data points:

**No Bucketing**:
- 800×800 = 640,000 data points
- Render time: 30-60 seconds

**100-Mile Buckets**:
- ~40×30 = 1,200 data points
- Render time: 5-10 seconds

**Trade-off**: Bucketing loses fine detail but highlights major features.

### Interactive Viewer

**Instanced Rendering**:
- Before: 10,000 meshes = 10,000 draw calls (1-5 FPS)
- After: 1 instanced mesh = 1 draw call (60 FPS)
- **1000× performance improvement**

**Material Choice**:
- `MeshStandardMaterial` (PBR): Complex, slow
- `MeshLambertMaterial` (diffuse): Simple, fast
- Visual difference minimal for terrain, performance gain significant

**Bucketing Algorithm**:
- Optimized with typed arrays (`Float32Array`)
- Pre-allocated buffers (no dynamic resizing)
- Manual loops instead of spread operators
- **2-5× faster** than naive implementation

**Debouncing**:
- Slider changes debounced 100-150ms
- Prevents hundreds of unnecessary recomputes during drag

**Browser Requirements**:
- Modern browser with WebGL support
- 2GB+ RAM recommended for high-resolution data
- Updated graphics drivers for best performance

---

## Region Definitions

### Pre-Configured Regions (60+)

Run `python download_regions.py --list` to see all regions.

**Highlights**:

**North America** (11):
- usa_full, california, texas, colorado, washington, new_york, florida, arizona, alaska, hawaii, canada, mexico

**Europe** (13):
- germany, france, italy, spain, uk, poland, norway, sweden, switzerland, austria, greece, netherlands, iceland

**Asia** (8):
- japan, china, south_korea, india, thailand, vietnam, nepal, israel

**South America** (3):
- brazil, argentina, chile, peru

**Oceania** (2):
- australia, new_zealand

**Africa & Middle East** (5):
- south_africa, egypt, kenya, saudi_arabia

**Special** (2):
- alps, rockies

### Adding Custom Regions

Edit `download_regions.py` and add to the `REGIONS` dictionary:

```python
REGIONS = {
    "my_region": {
        "bounds": (lon_min, lat_min, lon_max, lat_max),  # WGS84
        "name": "My Custom Region",
        "description": "Description here"
    }
}
```

Then download elevation data for those bounds and process:
```powershell
python download_regions.py --regions my_region
```

---

## Data Attribution

When publishing visualizations or using this data, please credit:

**USA Data**: 
```
USGS 3D Elevation Program (3DEP)
https://www.usgs.gov/3d-elevation-program
```

**Global Data (SRTM)**:
```
NASA Shuttle Radar Topography Mission (SRTM) (2013)
Shuttle Radar Topography Mission (SRTM) Global
Distributed by OpenTopography
https://doi.org/10.5069/G9445JDF
```

**National sources** as appropriate (GSI Japan, BKG Germany, etc.)

---

**Last Updated**: October 22, 2025

For user-friendly overview see [README.md](README.md)  
For quick start see [QUICKSTART.md](QUICKSTART.md)

