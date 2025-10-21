# Altitude Maps

A Python-based visualization project for creating climate and temperature maps based on altitude/elevation data.

## Overview

This project recreates sophisticated climate visualizations showing how temperature and other climate variables change with altitude across different geographic locations. The visualizations can include:

- 3D globe representations with altitude-based climate data
- Temperature gradients by elevation
- Interactive climate zone maps
- Topographic climate analysis

## Goals

1. **Data Acquisition**: Obtain high-quality elevation and climate data from public sources
2. **Visualization**: Create compelling, accurate visualizations using modern Python libraries
3. **Interactivity**: Enable exploration of climate patterns across different altitudes and locations
4. **Reproducibility**: Make the entire pipeline automated and well-documented

## Tech Stack

- **Python 3.13**: Core language
- **NumPy & Pandas**: Data processing
- **Matplotlib & Plotly**: Static and interactive visualizations
- **Cartopy**: Geospatial mapping
- **xarray & netCDF4**: Climate data handling

## Quick Start

### 1. Setup Environment (PowerShell)

```powershell
# Automated setup (creates venv, installs dependencies)
.\setup.ps1
```

### 2. Generate Sample Visualizations

```powershell
# Create visualizations with synthetic data
python visualize.py
```

Output files are saved to `generated/` with timestamps:
- `YYYYMMDD_HHMMSS_elevation_temperature_contour_maps.png`
- `YYYYMMDD_HHMMSS_temperature_vs_elevation_scatter.png`
- `YYYYMMDD_HHMMSS_3d_elevation_temperature_map.png`

### 3. Explore Real USA Data Sources

```powershell
# View available datasets and download options
python src/usa_elevation_data.py
```

This downloads a sample area (Denver) at 10m resolution from USGS 3DEP.

## Data Sources

### Elevation Data
- **USGS 3DEP**: ~10m resolution (primary for USA) ✅ *Working!*
- **USGS NED**: 30m resolution (full USA coverage)
- **NASA SRTM**: 30m resolution (global)
- **OpenTopography**: 1-30m research data (requires API key)

### Climate Data (Future)
- **NOAA**: Climate normals and historical data
- **ERA5**: Reanalysis climate data
- **WorldClim**: Bioclimatic variables

### Resolution Guide
- **1 square mile** = ~2.6 km²
  - At 10m resolution: ~26,000 pixels
  - At 30m resolution: ~2,900 pixels
- **10 square miles**: Perfect for detailed regional analysis with 10m data

## Project Structure

```
altitude-maps/
├── venv/              # Virtual environment (gitignored)
├── data/              # Downloaded datasets (gitignored)
├── output/            # Generated visualizations
├── src/               # Source code
├── requirements.txt   # Python dependencies
├── setup.ps1          # Automated setup script
└── visualize.py       # Main visualization script
```

## Development

This project follows a rapid prototyping approach with continuous testing and documentation of learnings in the `learnings/` directory.

