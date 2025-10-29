# Learning Session 1: Altitude Maps Project Setup

**Date**: October 21, 2025  
**Session Goal**: Set up a Python project to recreate climate visualizations showing temperature by altitude

## Context

User wanted to recreate a visualization from Twitter (@cstats1) showing a 3D map of the USA with elevation and climate data overlaid. The specific tweet referenced is no longer accessible, but based on the project requirements, we built a framework for altitude-based climate visualization.

## Key Accomplishments

### 1. Environment Setup
-  Created Python 3.13 virtual environment using Windows py launcher
-  Automated setup with `setup.ps1` PowerShell script
-  Fixed Windows console encoding issues (UTF-8 vs CP1252)
  - Key learning: Need to wrap stdout/stderr with UTF-8 TextIOWrapper on Windows

### 2. Dependency Management
- Started with full geospatial stack (cartopy, netCDF4, rasterio)
- **Problem**: netCDF4 requires HDF5 native libraries (not pip-installable on Windows)
- **Solution**: Simplified to Windows-compatible packages:
  - Used `h5netcdf` instead of `netCDF4` (pure Python, works with h5py)
  - Removed cartopy and rasterio from base requirements
  - Added note about conda for advanced geospatial features
- Final stack: numpy, pandas, matplotlib, plotly, seaborn, xarray, h5netcdf, scipy

### 3. Data Architecture

Created two-tier data approach:
1. **Sample/Synthetic Data** (immediate)
   - Generated realistic elevation data using Gaussian peaks
   - Applied standard atmospheric lapse rate (6.5degC/1000m) for temperature
   - Good for testing and development

2. **Real USA Data Sources** (researched and documented)
   - USGS 3DEP: 10m resolution (~10 meters per pixel)
   - USGS NED: 30m resolution (full USA coverage)
   - SRTM: 30m global coverage
   - OpenTopography: Research-grade data (API key required)
   - Resolution context: 1 square mile ~ 2.6 km^2 ~ 260 pixels at 10m resolution

### 4. Visualization Types Created

Three complementary views:
1. **Contour Maps** - Side-by-side elevation and temperature
2. **Scatter Plot** - Temperature vs elevation relationship with density
3. **3D Surface** - Elevation mesh colored by temperature

All use colorblind-friendly colormaps:
- Terrain for elevation
- RdYlBu_r (Red-Yellow-Blue reversed) for temperature

### 5. File Organization

```
altitude-maps/
├── venv/                    # Python 3.13 environment
├── data/                    # Raw data cache (gitignored)
├── generated/               # Output with timestamps (gitignored)
├── src/
│   ├── data_sources.py      # General data acquisition
│   └── usa_elevation_data.py # USGS-specific downloader
├── learnings/               # Session notes (gitignored)
├── setup.ps1                # One-command setup
├── visualize.py             # Main CLI tool
├── requirements.txt         # Deps
├── .cursorrules             # Project patterns
└── README.md                # High-level docs
```

### 6. Output File Naming

Implemented timestamped descriptive filenames:
- Format: `YYYYMMDD_HHMMSS_description.png`
- Example: `20251021_121914_3d_elevation_temperature_map.png`
- All outputs go to `generated/` folder
- Easy to track iterations and compare results

## Technical Insights

### Windows Development Pain Points
1. **Encoding**: Windows PowerShell defaults to CP1252, not UTF-8
   - Solution: Wrap sys.stdout/stderr with UTF-8 TextIOWrapper
2. **Native Dependencies**: Many geospatial libraries need compiled C/C++ dependencies
   - Solution: Use pure Python alternatives or recommend conda
3. **Path Separators**: Used pathlib.Path for cross-platform compatibility

### Data Resolution Trade-offs

| Resolution | Area per Pixel | Best For | File Size (estimate) |
|------------|---------------|----------|---------------------|
| 1m | 1m^2 | Urban, detailed terrain | Very large |
| 10m | 100m^2 | Regional analysis | Large |
| 30m | 900m^2 | State/country level | Manageable |
| 90m | 8100m^2 | Continental | Small |

For 1 square mile (2.6 km^2):
- At 10m resolution: ~26,000 pixels
- At 30m resolution: ~2,900 pixels

### Climate Data Best Practices
1. **Lapse Rate**: Standard is 6.5degC per 1000m, but varies:
   - Dry air: ~10degC/1000m
   - Saturated air: ~6degC/1000m
   - Real data should use actual measurements
2. **Coordinate Systems**: Always document (we use WGS84/EPSG:4326)
3. **Caching**: Essential for large datasets - never re-download
4. **Validation**: Check ranges, handle NaN/nodata values

## USGS Data Access Methods

Three main approaches:
1. **API Download** (programmatic)
   - USGS 3DEP ImageServer REST API
   - Good for small areas (<10deg x 10deg)
   - Implemented in `usa_elevation_data.py`

2. **Bulk Download** (manual)
   - Earth Explorer: https://earthexplorer.usgs.gov/
   - National Map Downloader: https://apps.nationalmap.gov/downloader/
   - Best for large regions or highest resolution

3. **Cloud Access** (advanced)
   - AWS Open Data: USGS data on S3
   - Good for processing in cloud

## Predefined Regions

Created 10 interesting USA regions with elevation variation:
- Colorado Rockies (high peaks)
- California Sierra Nevada
- Cascades (Washington)
- Appalachian Tennessee
- Grand Canyon
- Yellowstone
- Mount Rainier
- Great Smoky Mountains
- White Mountains (NH)
- Denver metro area

## Next Steps / Future Enhancements

1. **Real Data Integration**
   - Test actual USGS 3DEP download
   - Parse GeoTIFF with rasterio (will need conda install)
   - Cache downloaded tiles

2. **Interactive Visualizations**
   - Plotly 3D globe (already have plotly installed)
   - Web-based explorer with zoom/pan
   - Dash dashboard for parameter exploration

3. **Climate Variable Expansion**
   - Precipitation by altitude
   - Snow cover duration
   - Vegetation zones (biomes)
   - Solar radiation (aspect + elevation)

4. **Performance**
   - Lazy loading for large datasets
   - Chunked processing with Dask
   - GPU acceleration for rendering

## Architecture Decisions

### Why sample data first?
- Enables immediate visualization and testing
- No dependency on external services
- Predictable, controllable data for development

### Why multiple visualization types?
- Different questions need different views
- Contour: Spatial patterns
- Scatter: Relationships and correlations
- 3D: Intuitive terrain understanding

### Why timestamped outputs?
- Facilitates experimentation and iteration
- Easy A/B comparison
- No overwriting previous results
- Clear chronological history

## Commands Reference

```powershell
# Initial setup
.\setup.ps1

# Generate visualizations
python visualize.py

# Custom output directory
python visualize.py --output my_results

# Test data sources
python src/usa_elevation_data.py

# Show available datasets and regions
python src/usa_elevation_data.py
```

## Reflection

This was a successful first session establishing solid foundations:
- Clean Python 3.13 environment
- Working visualization pipeline
- Clear data acquisition strategy
- Good documentation structure

The key insight was to **start simple with synthetic data** rather than getting blocked on data acquisition. This allowed rapid iteration on visualization design while researching proper data sources in parallel.

The Windows encoding issues were instructive - cross-platform Python development requires explicit encoding handling. The solution (UTF-8 wrapper) is simple but non-obvious.

The USGS 3DEP API is promising for programmatic access, though manual download via Earth Explorer may be more practical for high-resolution full-state coverage.

