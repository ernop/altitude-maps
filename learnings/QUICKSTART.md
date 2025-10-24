# 🚀 Quick Start - 5 Minutes

## Step 1: Setup (One Time)

```powershell
# Run from PowerShell in the project directory
.\setup.ps1
```

Creates a Python virtual environment and installs dependencies. Takes ~2 minutes.

## Step 2: Start Interactive Viewer (Recommended)

```powershell
# Start local server
python -m http.server 8001

# Open in browser: http://localhost:8001/interactive_viewer_advanced.html
```

**Controls**:
- **Right-click + drag** to look around
- **WASD** to fly (Q/E for up/down)
- **Shift** to fly faster
- **Mouse wheel** to zoom

## Step 3: Or Generate a Static Image

```powershell
python visualize_usa_overhead.py
```

**Output**: Overhead view of continental USA in `generated/` folder (~10 seconds to render).

## That's It

You now have:
- ✅ Interactive 3D viewer with USA data
- ✅ Static rendering capability
- ✅ Customization options

---

## Next Steps

### Explore the Interactive Viewer

With the server running at `localhost:8001`:

1. Adjust **Bucket Size** slider for different detail levels
2. Try **Render Mode** → Switch between Bars and Surface
3. Change **Color Scheme** 
4. Adjust **Vertical Exaggeration**
5. Use **Shift/Ctrl/Alt** modifiers for flight speed

### Try Different Static Renders

```powershell
# 100-mile bucket aggregation
python visualize_usa_overhead.py --bucket-miles 100

# Different color scheme
python visualize_usa_overhead.py --colormap earth

# 9 different viewpoints
python visualize_usa_overhead.py --gen-nine
```

### Add More Regions

Currently only USA is included. To add more:

1. Go to https://portal.opentopography.org/raster?opentopoID=OTSRTM.082015.4326.1
2. Select your region of interest
3. Download as GeoTIFF
4. Save to `data/regions/japan.tif` (or any name)
5. Process: `python download_regions.py --regions japan`
6. Refresh viewer - new region appears in dropdown

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

The viewer requires a local server (doesn't work with `file://` protocol):

```powershell
python -m http.server 8001
# Then open: http://localhost:8001/interactive_viewer_advanced.html
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
# 10x = mountains 10 times steeper than reality
python visualize_usa_overhead.py --vertical-exaggeration 10

# 1.0 = true-to-life Earth scale
python visualize_usa_overhead.py --vertical-exaggeration 1.0

# 25x = extreme exaggeration
python visualize_usa_overhead.py --vertical-exaggeration 25
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
