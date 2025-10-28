# Altitude Maps - Quick Start Guide

## Setup (One Time)

```powershell
# 1. Activate virtual environment
.\venv\Scripts\Activate.ps1

# 2. Verify it works
python download_unified.py --list
```

If you see a list of 200+ regions, you're ready!

## Download Any Region

```powershell
# Basic usage - downloads to data/regions/<region>.tif
python download_unified.py <region_name>

# Download AND process for viewer (recommended)
python download_unified.py <region_name> --process
```

### Examples

```powershell
# US States (auto-clips to state boundaries)
python download_unified.py california --process
python download_unified.py tennessee --process
python download_unified.py colorado --process

# Japan regions
python download_unified.py shikoku --process
python download_unified.py kochi --process

# Any country
python download_unified.py iceland --process
python download_unified.py switzerland --process
python download_unified.py nepal --process

# Custom region (not in registry)
python download_unified.py kamchatka --bounds 155 50 163 61 --process
```

## View in 3D

```powershell
python serve_viewer.py
```

Then open http://localhost:8001 in your browser. Select your region from the dropdown!

## How It Works

1. **`python download_unified.py <region>`** → Downloads 30m elevation data to `data/regions/<region>.tif`
2. **`--process` flag** → Clips to boundaries, exports to JSON, updates dropdown manifest
3. **Result** → Region appears in web viewer dropdown automatically

## Common Commands

```powershell
# List all available regions (200+)
python download_unified.py --list

# Download without processing
python download_unified.py iceland

# Process with higher resolution
python download_unified.py yosemite --process --target-pixels 2048

# Use specific dataset (default is SRTMGL1 for most, AW3D30 for Asia)
python download_unified.py alps --dataset COP30 --process
```

## Datasets Available

- `SRTMGL1` - 30m SRTM (default for most regions)
- `AW3D30` - 30m ALOS (best for mountains/Asia, default for Japan)
- `COP30` - 30m Copernicus (best polar coverage)
- `NASADEM` - 30m improved SRTM
- `COP90` - 90m Copernicus

## Troubleshooting

### "Unknown region"
Run `python download_unified.py --list` to see all available region names, or provide custom bounds:
```powershell
python download_unified.py myregion --bounds <west> <south> <east> <north> --process
```

### "API key required"
Add your free OpenTopography API key to `settings.json`:
```json
{
  "opentopography_api_key": "your_key_here"
}
```
Get key at: https://portal.opentopography.org/

### Region downloaded but doesn't appear in dropdown
```powershell
python regenerate_manifest.py
```
Then refresh the browser.

### Want to see what's available without downloading
```powershell
# See what's already been processed
Get-ChildItem generated/regions/*.json | Select-Object Name
```

## That's It!

Three commands to remember:
1. `python download_unified.py <region> --process` - Get region
2. `python serve_viewer.py` - View it
3. `python download_unified.py --list` - See what's available


