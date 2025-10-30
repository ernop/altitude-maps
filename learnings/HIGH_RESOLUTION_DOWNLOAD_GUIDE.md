# High-Resolution Elevation Data Download Guide

This guide explains how to download elevation data using the `download_high_resolution.py` script.

**Note**: All regions are now defined in `src/regions_config.py` - see `python download_high_resolution.py --list-regions` for current options.

## Quick Start

### Option 1: Automated Download via OpenTopography (30m)

```powershell
# List all available regions
python download_high_resolution.py --list-regions

# Download any region
python download_high_resolution.py iceland --dataset SRTMGL1 --process

# Multiple regions at once
python download_high_resolution.py iceland alps kamchatka --dataset AW3D30 --process
```

### Option 2: Manual Download for 10m USGS Data (California only)

For the highest resolution California data (10m), you'll need to manually download from USGS:

1.**Visit USGS National Map Downloader:**
 https://apps.nationalmap.gov/downloader/

2.**Navigate to California:**
 - Use the map to zoom to California
 - Or enter coordinates

3.**Select Data:**
 - Click "Find Products"
 - Select "Elevation Products (3DEP)"
 - Choose "1/3 arc-second DEM" (10m resolution)

4.**Download:**
 - Select tiles covering your area of interest
 - Download as GeoTIFF format
 - Save to: `data/regions/california.tif`

5.**Process:**
 ```powershell
 python download_regions.py --regions california --max-size 2048
 ```

## Available Datasets

| Dataset | Resolution | Coverage | Best For |
|---------|-----------|----------|----------|
|**AW3D30** | 30m | Global (82degN-82degS) |**Japan, mountains, Asia** |
| SRTMGL1 | 30m | Global (60degN-56degS) | General use, USA |
| NASADEM | 30m | Global (60degN-56degS) | Improved SRTM, void-filled |
| COP30 | 30m | Global (90degN-90degS) | Polar regions, complete coverage |
| SRTMGL3 | 90m | Global (60degN-56degS) | Lower resolution, smaller files |
| COP90 | 90m | Global (90degN-90degS) | Polar regions, smaller files |

**Special:** USGS 3DEP (10m) - USA only, manual download required

## Available Regions

### Pre-defined High-Resolution Regions

```powershell
# List all available regions
python download_high_resolution.py --list-regions

# List all available datasets
python download_high_resolution.py --list-datasets
```

**Japan:**
- `shikoku` - Shikoku island (smallest main island)
- `hokkaido` - Hokkaido (northernmost main island)
- `honshu` - Honshu (largest main island)
- `kyushu` - Kyushu (southern main island)

**USA (California sub-regions):**
- `california_central` - Central California (Sierra Nevada, Yosemite, Lake Tahoe)
- `california_north` - Northern California (Cascade Range, Mt. Shasta)
- `california_south` - Southern California (Death Valley, San Bernardino Mountains)
- `california_coast` - California Coast (Bay Area, Big Sur)

**Mountains:**
- `alps` - European Alps
- `nepal` - Nepal (Himalayas, Mt. Everest)
- `new_zealand` - New Zealand (Southern Alps)

### Custom Regions

You can also download any custom region by specifying bounds:

```powershell
# Custom region with bounds (west, south, east, north)
python download_high_resolution.py custom_name --bounds -120 35 -119 36 --dataset AW3D30
```

## Dataset Recommendations

### For Regions with Mountains:
**Best: AW3D30 (ALOS World 3D)**
- 30m resolution
- Excellent quality for mountains and Asia
- Made by JAXA specifically for terrain mapping

```powershell
python download_high_resolution.py iceland --dataset AW3D30 --process --max-size 2048
```

### General Use:
**Good: SRTMGL1 (30m via API)**
- Most commonly used
- Good quality for most terrain

```powershell
python download_high_resolution.py california --dataset SRTMGL1 --process --max-size 2048
```

### For US Regions:
**Better: USGS 3DEP (10m, manual download)**
- Best available for USA
- Requires manual download steps
- See instructions with `--usgs-instructions`

### For Polar Regions:
**Best: COP30 or COP90 (Copernicus)**
- Full polar coverage
- Consistent quality

```powershell
python download_high_resolution.py <region> --dataset COP30 --process --max-size 2048
```

## Command Reference

### Basic Commands

```powershell
# Download single region
python download_high_resolution.py shikoku --dataset AW3D30

# Download multiple regions
python download_high_resolution.py california shikoku alps --dataset AW3D30

# Download and process to JSON
python download_high_resolution.py shikoku --dataset AW3D30 --process

# High-resolution processing (larger files, more detail)
python download_high_resolution.py shikoku --dataset AW3D30 --process --max-size 4096

# Custom output directories
python download_high_resolution.py shikoku --data-dir data/custom --output-dir generated/custom
```

### Info Commands

```powershell
# List available regions
python download_high_resolution.py --list-regions

# List available datasets
python download_high_resolution.py --list-datasets

# Show USGS 10m download instructions
python download_high_resolution.py california --usgs-instructions
```

## Processing Options

The `--max-size` parameter controls the output resolution:

| max-size | Use Case | File Size | Quality |
|----------|----------|-----------|---------|
| 800 | Quick preview | ~2-10 MB | Low |
| 1024 | Standard viewing | ~5-15 MB | Medium |
| 2048 | High-resolution | ~20-60 MB | High |
| 4096 | Maximum detail | ~80-250 MB | Very High |
| 0 | Full resolution | Very large | Maximum |

**Recommended for browsing:** 1024-2048

## File Organization

```
altitude-maps/
 data/regions/# Downloaded TIF files (raw data)
 california.tif
 shikoku.tif

 generated/regions/# Processed JSON files (for web viewer)
 california.json
 shikoku.json
 regions_manifest.json

 interactive_viewer_advanced.html# Web viewer
```

## Web Viewer

After downloading and processing, open `interactive_viewer_advanced.html` in your browser:

1. Open the file in Chrome, Firefox, or Edge
2. Select region from the dropdown menu
3. Interact with the 3D elevation view
4. Adjust vertical exaggeration and colors

## API Key Setup

Your OpenTopography API key is already configured in `settings.json`:

```json
{
 "opentopography": {
 "api_key": "5a2d49a9c28361d6c32f086ee233209d",
 "base_url": "https://portal.opentopography.org/API/globaldem"
 }
}
```

If you need a new key or want to use your own:
1. Go to https://portal.opentopography.org/
2. Create a free account
3. Get your API key from your account page
4. Update `settings.json`

## Troubleshooting

### Region too large error
If you get "region too large" error, try:
1. Use a smaller region or split into parts
2. Download manually from OpenTopography website
3. Use lower resolution dataset (SRTMGL3 or COP90)

### Download timeout
- Check internet connection
- Try again (API may be busy)
- Download manually from USGS or OpenTopography website

### File already exists
- Script skips existing files by default
- Delete old file if you want to re-download
- Or use a different output directory

### Out of memory during processing
- Use smaller `--max-size` (e.g., 1024 instead of 4096)
- Process regions individually
- Close other applications

## Examples

### Example 1: Quick Shikoku Download (Recommended)
```powershell
# Download Shikoku at 30m with ALOS, process to 2048px
python download_high_resolution.py shikoku --dataset AW3D30 --process --max-size 2048

# Open interactive_viewer_advanced.html
# Select "Shikoku" from dropdown
```

### Example 2: Quick California Download
```powershell
# Download Central California (Sierra Nevada) at 30m with SRTM
python download_high_resolution.py california_central --dataset SRTMGL1 --process --max-size 2048

# Open interactive_viewer_advanced.html
# Select "Central California" from dropdown
```

### Example 3: Both Regions, High Quality
```powershell
# Download both Shikoku and Central California (best combo)
python download_high_resolution.py shikoku california_central --dataset AW3D30 --process --max-size 2048

# This will:
# 1. Download shikoku.tif (~33 MB, ALOS)
# 2. Download california_central.tif (~187 MB, SRTM)
# 3. Process both to JSON (~27 MB each)
# 4. Update regions manifest
# 5. Ready to view in interactive_viewer_advanced.html
```

### Example 4: All Japanese Islands
```powershell
# Download all 4 main islands of Japan
python download_high_resolution.py shikoku hokkaido honshu kyushu --dataset AW3D30 --process --max-size 1024
```

### Example 5: Custom Mountain Region
```powershell
# Download custom area around Mt. Fuji
python download_high_resolution.py mt_fuji --bounds 138.5 35.0 139.0 35.5 --dataset AW3D30 --process
```

## Performance Notes

### Download Times (approximate, depends on internet speed)
- Shikoku: ~30-60 seconds
- California: ~60-120 seconds (larger area)
- Processing: 10-60 seconds per region

### File Sizes
- Raw TIF (30m):
 - Shikoku: ~20-40 MB
 - California: ~50-100 MB
- Processed JSON (max-size 2048):
 - Shikoku: ~30-50 MB
 - California: ~80-120 MB

## Next Steps

1.**Download your regions:**
 ```powershell
 python download_high_resolution.py california shikoku --dataset AW3D30 --process --max-size 2048
 ```

2.**View in browser:**
 - Open `interactive_viewer_advanced.html`
 - Select regions from dropdown
 - Explore elevation data!

3.**Experiment with datasets:**
 - Try different datasets (AW3D30, SRTMGL1, COP30)
 - Compare quality and coverage
 - Adjust resolution with `--max-size`

4.**For highest quality California:**
 - Follow USGS 3DEP manual download instructions
 - Get 10m resolution data
 - Much better detail than 30m

## Additional Resources

-**OpenTopography Portal:** https://portal.opentopography.org/
-**USGS National Map:** https://apps.nationalmap.gov/downloader/
-**ALOS Global DEM:** https://www.eorc.jaxa.jp/ALOS/en/aw3d30/
-**Copernicus DEM:** https://spacedata.copernicus.eu/collections/copernicus-digital-elevation-model

