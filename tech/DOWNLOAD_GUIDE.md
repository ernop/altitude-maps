# Unified Downloader Usage Guide

## Overview

The unified downloader (`download_unified.py`) provides **one command** to download and process elevation data for any region worldwide. No need to remember which script handles which country-the system routes automatically.

## Quick Start

### Activate Environment (Always Required)
```powershell
.\venv\Scripts\Activate.ps1
```

### Basic Usage - Download and Process a Region
```powershell
# US state (auto-clips to state boundaries)
python download_unified.py california --process

# Japanese region (auto-dataset: AW3D30)
python download_unified.py shikoku --process

# Switzerland
python download_unified.py switzerland --process

# Any built-in region
python download_unified.py <region_name> --process
```

## How It Works

### 1. Region Resolution
The system looks up your region in a **centralized configuration** (`src/regions_config.py`):
- **US states** - clips to state boundaries automatically
- **Countries** - international countries
- **Regions** - islands, peninsulas, mountain ranges, etc.

### 2. Auto Mode (Default ON)
- Downloads via OpenTopography API (30m SRTM or better)
- Uses best dataset per region (e.g., AW3D30 for Asia, SRTMGL1 for USA)
- Requires API key in `settings.json` (free from https://portal.opentopography.org/)

### 3. Automatic Processing
With `--process` flag:
- **Clips** to admin boundaries (state/country) when known
- **Downsamples** to viewer-friendly size (default 800px)
- **Exports** to JSON format
- **Updates** `generated/regions/regions_manifest.json` <- **this makes it show in dropdown**
- Region appears in viewer dropdown at http://localhost:8001

## Command Reference

### List Available Regions
```powershell
python download_unified.py --list
```
Shows all 200+ built-in regions with IDs, names, and bounds.

### Download Only (No Processing)
```powershell
python download_unified.py california
# Downloads to data/regions/california.tif
```

### Custom Region (Not in Registry)
```powershell
# Kamchatka Peninsula example
python download_unified.py kamchatka --bounds 155 50 163 61 --process
```
The bounds format is: `west south east north` (in degrees).

### Choose Specific Dataset
```powershell
# Use Copernicus DEM instead of default
python download_unified.py alps --dataset COP30 --process

# Use ALOS for high mountains
python download_unified.py nepal --dataset AW3D30 --process
```

Available datasets:
- `SRTMGL1` - 30m SRTM (default for most regions)
- `AW3D30` - 30m ALOS (best for mountains and Asia)
- `COP30` - 30m Copernicus (best polar coverage)
- `COP90` - 90m Copernicus
- `NASADEM` - 30m improved SRTM

### Control Resolution
```powershell
# Higher resolution export (larger file)
python download_unified.py yosemite --process --target-pixels 2048

# Lower resolution (faster, smaller)
python download_unified.py texas --process --target-pixels 400
```

### Manual Mode (No Auto-Download)
```powershell
# Expects TIF already at data/regions/<region>.tif
python download_unified.py california --no-auto --process
```

## Viewer Integration

### How Regions Appear in Dropdown
1. When you run `download_unified.py <region> --process`, it exports to `generated/regions/<region>_*.json`
2. The manifest `generated/regions/regions_manifest.json` is automatically updated
3. The viewer loads this manifest and populates the dropdown

### If Dropdown Looks Wrong
Run the manifest regeneration utility:
```powershell
.\venv\Scripts\Activate.ps1
python regenerate_manifest.py
```

This fixes entries where multi-word regions (like "New Mexico") were truncated to just "New".

### View Your Regions
```powershell
python serve_viewer.py
```
Opens http://localhost:8001/interactive_viewer_advanced.html

## Examples

### US State with Auto Processing
```powershell
python download_unified.py tennessee --process
# -> Downloads 30m SRTM
# -> Clips to Tennessee state boundary
# -> Exports to viewer format
# -> Shows as "Tennessee" in dropdown
```

### Japanese Prefecture
```powershell
python download_unified.py kochi --process
# -> Downloads 30m AW3D30 (best for Asia)
# -> Exports with country context
# -> Shows as "Kochi" in dropdown
```

### Custom Mountain Range
```powershell
python download_unified.py cascade_range --bounds -122 46 -120 49 --process --dataset AW3D30
# -> Downloads specified bounds
# -> Processes as "Cascade Range"
# -> Shows in dropdown
```

### High-Resolution Download
```powershell
python download_unified.py california --process --target-pixels 4000
# -> Creates 4000px export (very detailed, larger file)
```

## Troubleshooting

### "Unknown region"
1. Check spelling: `python download_unified.py --list`
2. Or provide custom bounds: `--bounds W S E N`

### "API key required"
Add OpenTopography API key to `settings.json`:
```json
{
  "opentopography_api_key": "your_key_here"
}
```
Get free key: https://portal.opentopography.org/

### Region downloads but doesn't show in dropdown
```powershell
python regenerate_manifest.py
```
Then refresh the viewer page.

### Download fails (timeout, too large)
Region may exceed API limits. Try:
1. Smaller region bounds
2. Download in tiles (legacy downloaders)
3. Manual download from source

## Advanced: Adding Permanent Regions

To add a region to the built-in registry (so you can just use its name):

1. Edit `src/regions_config.py`
2. Add RegionConfig entry to the appropriate category:
   - `US_STATES` - US states
   - `COUNTRIES` - Countries
   - `REGIONS` - Islands, peninsulas, mountain ranges, etc.
3. Run `python ensure_region.py --list-regions` to verify

Example addition to `REGIONS` in `src/regions_config.py`:
```python
"kamchatka": RegionConfig(
    id="kamchatka",
    name="Kamchatka Peninsula",
    bounds=(156.0, 50.5, 163.0, 62.5),
    description="Russia - Kamchatka Peninsula",
    category="region",
    clip_boundary=False,
),
```

## Migration from Old Scripts

### Old Way
```powershell
python downloaders/usa_3dep.py california --auto
# Then manually process...
```

### New Way
```powershell
python download_unified.py california --process
# Done! Everything automated.
```

The old scripts still work but are no longer needed for most workflows.

## Summary

**One command to rule them all:**
```powershell
.\venv\Scripts\Activate.ps1
python download_unified.py <region> --process
```

- Auto mode ON by default
- Auto-selects best dataset per region
- Auto-clips to boundaries when known
- Auto-exports for viewer
- Auto-updates dropdown manifest

**Result**: Region appears in viewer dropdown, ready to visualize in 3D.

