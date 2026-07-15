# Installation Guide

## Quick Setup

### Windows (PowerShell)

```powershell
# Run setup script (installs Python 3.13 if needed)
.\setup.ps1

# Activate virtual environment
.\venv\Scripts\Activate.ps1
```

### Mac/Linux

```bash
# Create virtual environment
python3.13 -m venv venv

# Activate
source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

## Requirements

- **Python 3.13** (required)
- **Windows**: PowerShell and winget (for automatic Python installation)
- **Mac/Linux**: Python 3.13 installed manually
- **Modern web browser** for interactive viewer

## Verify Installation

```powershell
# Check Python version
python --version

# Test imports
python -c "import rasterio, numpy, geopandas; print('OK')"
```

## Quick Start Without the Pipeline

A fresh checkout has no elevation data (`data/` and `generated/` are
gitignored). The fastest way to get a working viewer is to pull ready-made
exports from the production deployment - no API keys or GIS dependencies
needed, only the Python standard library:

```bash
python fetch_sample_data.py              # california + estonia
python fetch_sample_data.py --list      # see all available region ids
python fetch_sample_data.py oregon japan # fetch specific regions
python serve_viewer.py
# open http://localhost:8001/interactive_viewer_advanced.html
```

## Next Steps (Full Pipeline)

1. Download a region: `python ensure_region.py ohio`
2. Start viewer: `python serve_viewer.py`
3. Open browser: `http://localhost:8001/interactive_viewer_advanced.html`

