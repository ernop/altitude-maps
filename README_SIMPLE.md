# 🗺️ Altitude Maps - Continental USA Visualizer

## What This Does

Creates a **single beautiful overhead image** of the entire continental United States showing elevation data, viewed from space.

<img src="reference_image_style.png" width="600" alt="Example Output Style"/>

---

## ⚡ Quick Start (3 Commands)

```powershell
# 1. Setup (one time only)
.\setup.ps1

# 2. Download USA elevation data (one time only)
python download_continental_usa.py --yes

# 3. Generate the visualization
python visualize_usa_overhead.py
```

**Output**: `generated/YYYYMMDD_HHMMSS_continental_usa_overhead_view.png`

---

## ✅ What You Get

🗺️ **Full continental USA** (-125°W to -66°W, 24°N to 49°N)  
📍 **Geographic labels** (exact lat/long bounds)  
🏔️ **Real USGS data** (3DEP elevation at ~6km resolution)  
🎨 **Beautiful colors** (blue → green → brown → white gradient)  
📊 **Elevation info** (-152m to 4,115m range)  
⚡ **Fast generation** (~5 seconds)  
💾 **High quality** (300 DPI PNG)

---

## 📁 Project Status

**Downloaded Data:**
- ✅ `continental_usa_elevation.tif` (3.3 MB) - Full USA
- ✅ `denver_elevation_10m.tif` (4.2 MB) - Denver test region

**Latest Output:**
- ✅ `20251021_124725_continental_usa_overhead_view.png`

**All visualization outputs** are in the `generated/` folder with timestamps.

---

## 🎯 Features

✨ **Automatic** - One command to generate  
✨ **Labeled** - Shows what region and coordinates  
✨ **Realistic** - Real USGS elevation data  
✨ **Overhead view** - Space perspective  
✨ **Timestamped** - Never overwrites previous images  

---

## 📚 Documentation

- **README.md** - Full project overview
- **QUICKSTART.md** - Detailed usage guide  
- **USAGE_SUMMARY.md** - Command reference
- **learnings/** - Technical deep dives

---

## 🔧 Customization

Want to change the view? Edit `visualize_usa_overhead.py`:

```python
# Line 81: Make mountains more/less dramatic
vertical_exag = 15.0  # Try 10-30

# Line 120: Change viewing angle
ax.view_init(elev=35, azim=230)  # Rotate the view

# Line 78-90: Modify colors
colors_list = [...]  # Customize terrain colors
```

---

## 🌎 Other Regions

```powershell
# Western USA only
python download_continental_usa.py --region usa_west --yes
python visualize_usa_overhead.py data/usa_elevation/usa_west_elevation.tif

# Specific landmarks (higher resolution!)
python download_usa_region.py colorado_rockies
python download_usa_region.py grand_canyon  
python download_usa_region.py yellowstone
```

---

## 📊 Data Source

**USGS 3D Elevation Program (3DEP)**
- Public domain data
- High quality, frequently updated
- Multiple resolutions available
- API: https://elevation.nationalmap.gov/

---

## 💡 What Makes This Special

1. **Fully automated** - No manual downloads needed
2. **Real data** - Not simulated or interpolated  
3. **Properly labeled** - Geographic context included
4. **Production ready** - 300 DPI, clean output
5. **Flexible** - Easy to customize colors, angles, regions

---

## 🎓 Tech Stack

- **Python 3.13** - Latest Python
- **rasterio** - GeoTIFF reading
- **matplotlib** - 3D visualization  
- **numpy** - Data processing
- **USGS 3DEP** - Elevation data source

---

## 👤 Created For

Visualizing elevation data for the continental United States in a simple, beautiful, overhead view similar to professional climate visualizations.

**Goal**: One command → One beautiful image → Clearly labeled

✅ **Goal Achieved!**

---

*Last updated: October 21, 2025*

