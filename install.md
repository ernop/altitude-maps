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

## Next Steps

1. Download a region: `python ensure_region.py ohio`
2. Start viewer: `python serve_viewer.py`
3. Open browser: `http://localhost:8001/interactive_viewer_advanced.html`

