# 🗺️ Altitude Maps - Quick Start Guide

## Installation (One Command!)

```powershell
.\setup.ps1
```

That's it! This creates a Python 3.13 environment and installs all dependencies.

---

## Usage Examples

### 1️⃣ Generate Sample Visualizations (Immediate)

```powershell
python visualize.py
```

Creates three beautiful visualizations:
- 📊 Elevation & temperature contour maps
- 📈 Temperature vs elevation scatter plot  
- 🏔️ 3D elevation surface with temperature overlay

**Output**: `generated/YYYYMMDD_HHMMSS_*.png`

---

### 2️⃣ List Available Real Data Regions

```powershell
python download_usa_region.py --list
```

Shows 10 predefined USA regions with high elevation variation.

---

### 3️⃣ Download Real USA Elevation Data

```powershell
# Download specific region (10m resolution from USGS)
python download_usa_region.py denver_area
python download_usa_region.py colorado_rockies
python download_usa_region.py grand_canyon
```

Downloads real USGS 3DEP elevation data at ~10 meter resolution!

**Output**: `data/usa_elevation/<region>_elevation_10m.tif`

---

### 4️⃣ Explore Data Sources

```powershell
python src/usa_elevation_data.py
```

Shows all available data sources and downloads a Denver sample automatically.

---

## Available Regions

| Region | Area | Elevation Variation |
|--------|------|-------------------|
| 🏔️ Colorado Rockies | 197,136 km² | High peaks & valleys |
| ⛰️ California Sierra | 92,408 km² | Sierra Nevada range |
| 🌲 Cascades WA | 73,926 km² | Volcanic peaks |
| 🏕️ Yellowstone | 36,963 km² | Plateau & mountains |
| 🏜️ Grand Canyon | 18,482 km² | Extreme relief |
| 🗻 Mount Rainier | 12,321 km² | Volcanic cone |
| 🌳 Great Smoky Mtns | 3,450 km² | Appalachian peaks |
| 🏙️ Denver Area | 6,160 km² | Plains to foothills |

---

## Data Resolution Guide

### What you get with 10m resolution:

- **1 square mile** = ~26,000 pixels of data
- **10 square miles** = ~260,000 pixels (perfect detail!)
- **File sizes**: 4-8 MB per degree²

### Comparison:

| Resolution | Meters/Pixel | Area/Pixel | Best For |
|------------|-------------|-----------|----------|
| 10m | 10m | 100 m² | Cities, parks, detailed terrain |
| 30m | 30m | 900 m² | Counties, regions |
| 90m | 90m | 8,100 m² | States, countries |

---

## Project Structure

```
altitude-maps/
├── 📜 visualize.py              # Main visualization tool
├── 📜 download_usa_region.py    # Download real USA data
├── 📜 setup.ps1                 # One-command setup
├── 📂 src/
│   ├── data_sources.py          # Sample data generator
│   └── usa_elevation_data.py    # USGS downloader
├── 📂 generated/                # Your visualizations (timestamped)
├── 📂 data/                     # Downloaded elevation data
└── 📂 learnings/                # Session notes
```

---

## Troubleshooting

### "Module not found"
```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### "Can't activate venv"
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

### Need higher resolution or different area?

Manual download options:
- **USGS Earth Explorer**: https://earthexplorer.usgs.gov/
- **National Map Downloader**: https://apps.nationalmap.gov/downloader/

---

## Next Steps

1. ✅ Generate sample visualizations
2. ✅ Download a real region you're interested in
3. 🔜 Create visualization from real data (next feature!)
4. 🔜 Interactive 3D globe viewer
5. 🔜 Add climate/temperature real data overlay

---

## Tips

- All outputs are **timestamped** - experiment freely!
- Start with **small regions** (Denver, Mount Rainier) to test
- **10m resolution** is amazing for detailed terrain
- Data is **cached** - won't re-download

---

**Questions?** Check `learnings/learnings_1_altitude_maps_setup.md` for deep dive.

