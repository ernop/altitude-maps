# High-Resolution Downloads Completed

## Summary

Successfully set up high-resolution elevation data downloads for California and Shikoku, Japan!

###  What's Been Done

1. **Created `download_high_resolution.py`**
   - New script for downloading from OpenTopography with multiple datasets
   - Supports ALOS World 3D (30m) - best for Japan and mountains
   - Supports SRTM GL1 (30m) - good for global coverage
   - Supports Copernicus DEM (30m/90m) - full polar coverage
   - Handles API limitations gracefully

2. **Downloaded Regions**
   -  **Shikoku, Japan** - 33 MB, 30m resolution (ALOS AW3D30)
   -  **Central California** - 187 MB, 30m resolution (SRTM GL1)

3. **Processed for Web Viewer**
   -  Shikoku: 26.6 MB JSON, 2.7M data points at 2048px resolution
   -  Central California: 28.2 MB JSON, 4.9M data points at 2048px resolution

4. **Documentation**
   - Created comprehensive guide: `HIGH_RESOLUTION_DOWNLOAD_GUIDE.md`
   - Includes USGS 3DEP instructions for 10m California data
   - Examples for various use cases

### 🗺 Available Regions Now

You can now view these regions in `interactive_viewer_advanced.html`:
- **Shikoku** - Smallest of Japan's main islands
- **Central California** - Sierra Nevada, Yosemite, Lake Tahoe
- Plus any previously downloaded regions

### 📊 Data Quality

**Shikoku:**
- Resolution: 30m (ALOS World 3D - excellent for Japan)
- Elevation range: -76m to 1,970m
- Original size: 8,280 x 5,400 pixels
- Processed: 2,070 x 2,700 pixels

**Central California:**
- Resolution: 30m (SRTM GL1)
- Elevation range: -67m to 4,412m (peak: Mt. Whitney area)
- Original size: 18,000 x 10,800 pixels
- Processed: 2,250 x 2,160 pixels

## 🚀 Next Steps

### View Your Data
```powershell
# Open the interactive viewer in your browser
start interactive_viewer_advanced.html
```
Then select "Shikoku" or "Central California" from the region dropdown.

### Download More California Regions
```powershell
# Northern California (Mt. Shasta, Cascades)
python download_high_resolution.py california_north --dataset SRTMGL1 --process --max-size 2048

# Southern California (Death Valley, San Bernardino)
python download_high_resolution.py california_south --dataset SRTMGL1 --process --max-size 2048

# California Coast (Bay Area, Big Sur)
python download_high_resolution.py california_coast --dataset SRTMGL1 --process --max-size 2048

# Or download all at once:
python download_high_resolution.py california_north california_south california_coast --dataset SRTMGL1 --process --max-size 2048
```

### Download More Japanese Regions
```powershell
# Other main Japanese islands
python download_high_resolution.py hokkaido honshu kyushu --dataset AW3D30 --process --max-size 2048

# Or all 4 main islands:
python download_high_resolution.py shikoku hokkaido honshu kyushu --dataset AW3D30 --process --max-size 1024
```

### Get Even Higher Resolution (10m for California)

The 30m data is good, but for California you can get 10m USGS 3DEP data:

```powershell
# Show detailed download instructions
python download_high_resolution.py california_central --usgs-instructions
```

Then follow the instructions to manually download from:
- **USGS National Map:** https://apps.nationalmap.gov/downloader/
- Select "Elevation Products (3DEP)" -> "1/3 arc-second DEM" (10m)

### Explore Other Regions

```powershell
# See all available pre-defined regions
python download_high_resolution.py --list-regions

# See all available datasets
python download_high_resolution.py --list-datasets

# Examples of other interesting regions:
python download_high_resolution.py alps --dataset AW3D30 --process  # European Alps
python download_high_resolution.py nepal --dataset AW3D30 --process  # Mt. Everest area
python download_high_resolution.py new_zealand --dataset AW3D30 --process  # Southern Alps
```

### Custom Regions

You can download any region by specifying bounds:
```powershell
# Format: region_name --bounds west south east north
python download_high_resolution.py yosemite --bounds -119.7 37.7 -119.5 37.9 --dataset SRTMGL1 --process

# Mt. Fuji area
python download_high_resolution.py mt_fuji --bounds 138.5 35.0 139.0 35.5 --dataset AW3D30 --process
```

## 🔧 Technical Details

### API Configuration
- Using OpenTopography API
- API Key configured in `settings.json`
- Rate limited to prevent API abuse (3 second delay between requests)

### Resolution Options
- `--max-size 800` - Quick preview (~2-10 MB JSON)
- `--max-size 1024` - Standard viewing (~5-15 MB JSON)
- `--max-size 2048` - High-resolution (~20-60 MB JSON) **<- Current setting**
- `--max-size 4096` - Maximum detail (~80-250 MB JSON)
- `--max-size 0` - Full resolution (very large files)

### API Limitations
- Maximum region size: ~500,000 km^2 (enforced by OpenTopography)
- Full California (962,000 km^2) is too large -> split into sub-regions
- Japan fits within limits:
  - Shikoku: 35,000 km^2 
  - Hokkaido: ~240,000 km^2 
  - Honshu: ~500,000 km^2  (borderline, may need splitting)
  - Kyushu: ~100,000 km^2 

## 📁 File Locations

```
altitude-maps/
├── download_high_resolution.py          # New high-res download script
├── HIGH_RESOLUTION_DOWNLOAD_GUIDE.md   # Comprehensive guide
├── COMPLETED_DOWNLOADS_SUMMARY.md      # This file
│
├── data/regions/                        # Raw elevation data (TIF files)
│   ├── shikoku.tif                     # 33 MB
│   └── california_central.tif          # 187 MB
│
├── generated/regions/                   # Processed JSON for web viewer
│   ├── shikoku.json                    # 26.6 MB
│   ├── california_central.json         # 28.2 MB
│   └── regions_manifest.json           # Region index
│
└── interactive_viewer_advanced.html     # Open this to view!
```

## 🎯 Quick Commands Reference

```powershell
# List what's available
python download_high_resolution.py --list-regions
python download_high_resolution.py --list-datasets

# Download regions (30m via API)
python download_high_resolution.py <region> --dataset <dataset>

# Download and process for viewing
python download_high_resolution.py <region> --dataset <dataset> --process --max-size 2048

# Multiple regions at once
python download_high_resolution.py region1 region2 region3 --dataset AW3D30 --process

# Custom region
python download_high_resolution.py my_region --bounds -120 35 -119 36 --dataset SRTMGL1 --process

# Get USGS 10m instructions (California only)
python download_high_resolution.py california_central --usgs-instructions
```

## 🌟 Recommended Next Actions

1. **View what you have:**
   - Open `interactive_viewer_advanced.html`
   - Try both Shikoku and Central California
   - Adjust vertical exaggeration and colors

2. **Download more California:**
   - Get Northern, Southern, or Coastal California regions
   - All use same simple command

3. **Get higher resolution California:**
   - Follow USGS 3DEP instructions for 10m data
   - Much more detail than 30m

4. **Explore Japan:**
   - Download other Japanese islands
   - ALOS dataset is excellent for Japan

5. **Try other regions:**
   - Alps, Nepal, New Zealand all work great
   - Mountains look particularly good with ALOS dataset

## ✨ What's Better Now

**Before:**
- SRTM 90m resolution only
- Manual download processes
- No good solution for large regions like California

**Now:**
- Multiple datasets: ALOS 30m, SRTM 30m, Copernicus 30m
- Automated downloads via OpenTopography API
- Split large regions (California) into manageable pieces
- Pre-configured for Japan (ALOS) and USA (SRTM)
- Clear path to 10m USGS data for California
- Comprehensive documentation

## 🔗 Useful Links

- **OpenTopography Portal:** https://portal.opentopography.org/
- **USGS National Map:** https://apps.nationalmap.gov/downloader/
- **ALOS Global DEM:** https://www.eorc.jaxa.jp/ALOS/en/aw3d30/
- **Copernicus DEM:** https://spacedata.copernicus.eu/collections/copernicus-digital-elevation-model

---

**Status:**  Fully operational and tested

**Created:** October 22, 2025

**Regions Downloaded:** 2 (Shikoku, Central California)

**Ready to:** Download more regions, explore in web viewer, or get 10m USGS data

