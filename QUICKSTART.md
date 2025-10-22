# 🚀 Quick Start - 5 Minutes to Your First Visualization

## Step 1: Setup (One Time Only)

```powershell
# Run this from PowerShell in the project directory
.\setup.ps1
```

This creates a Python virtual environment and installs all dependencies. Takes ~2 minutes.

## Step 2: Generate Your First Visualization

```powershell
python visualize_usa_overhead.py
```

**Result**: A beautiful overhead view of the entire continental USA saved to `generated/` with timestamp.

**Expected time**: ~10 seconds

## Step 3: Explore Interactively

Just open `interactive_viewer_advanced.html` in your web browser!

**Controls**:
- **Right-click + drag** to look around
- **WASD** to fly (Q/E for up/down)
- **Shift** to fly faster
- **Mouse wheel** to zoom

## That's It!

You now have:
- ✅ A high-resolution static render
- ✅ An interactive 3D viewer with USA data
- ✅ Full control to customize everything

---

## Next Steps

### Try Different Styles

```powershell
# Dramatic mountain peaks (100-mile buckets)
python visualize_usa_overhead.py --bucket-miles 100

# Different color scheme
python visualize_usa_overhead.py --colormap earth

# Generate 9 different viewpoints automatically
python visualize_usa_overhead.py --gen-nine
```

### Explore the Interactive Viewer

1. Open `interactive_viewer_advanced.html`
2. Adjust **Bucket Size** slider for different detail levels
3. Try **Render Mode** → Switch between Bars and Surface
4. Change **Color Scheme** 
5. Adjust **Vertical Exaggeration**

### Download More Regions

Currently only USA is included. To add more regions:

1. Go to https://portal.opentopography.org/raster?opentopoID=OTSRTM.082015.4326.1
2. Select your region of interest
3. Download as GeoTIFF
4. Save to `data/regions/japan.tif` (or any name)
5. Process: `python download_regions.py --regions japan`
6. Refresh browser - new region appears in dropdown!

---

## Troubleshooting

### "File not found" Error

The USA data file is missing. Download it:

```powershell
python download_continental_usa.py --yes
```

### "Module not found" Error

The virtual environment isn't activated:

```powershell
.\venv\Scripts\Activate.ps1
python visualize_usa_overhead.py
```

### Interactive Viewer Shows Nothing

Make sure you're opening the HTML file in a web browser (not as a local file in some apps). If using `file://` protocol doesn't work, run a local server:

```powershell
python -m http.server 8000
# Then open: http://localhost:8000/interactive_viewer_advanced.html
```

### Slow/Laggy Interactive Viewer

In the viewer sidebar, increase **Bucket Size** to 16 or 20. This reduces the number of terrain blocks.

---

## Common Tasks

### Change Viewing Angle
```powershell
# Overhead (satellite view)
python visualize_usa_overhead.py --camera-elevation 90

# Dramatic side angle
python visualize_usa_overhead.py --camera-elevation 20 --camera-azimuth 270
```

### Make Mountains More Dramatic
```powershell
python visualize_usa_overhead.py --vertical-exaggeration 15
```

### High-Resolution Output
```powershell
python visualize_usa_overhead.py --dpi 300 --scale-factor 8
```

### Custom Colors
```powershell
# Try: terrain, earth, ocean, viridis, plasma, inferno, grayscale
python visualize_usa_overhead.py --colormap ocean
```

---

## Learn More

- **Full technical reference**: See [TECH.md](TECH.md)
- **Project overview**: See [README.md](README.md)
- **All CLI options**: Run `python visualize_usa_overhead.py --help`

---

**Ready to explore!** 🗺️
