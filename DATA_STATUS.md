# Altitude Maps - Data Status

**Last Updated**: 2025-10-24 (After cleanup & re-export)

## ✅ Available Regions (29 total)

All data is properly exported and ready for the interactive 3D viewer at:
- **URL**: http://127.0.0.1:8001/interactive_viewer_advanced.html

### USA States (28)

| State | Source | Resolution | Status |
|-------|--------|------------|--------|
| Arizona | SRTM 30m | ~800px | ✅ Ready |
| Colorado | SRTM 30m | ~800px | ✅ Ready |
| Connecticut | SRTM 30m | ~800px | ✅ Ready |
| Delaware | SRTM 30m | ~800px | ✅ Ready |
| Indiana | SRTM 30m | ~800px | ✅ Ready |
| Iowa | SRTM 30m | ~800px | ✅ Ready |
| Kansas | SRTM 30m | ~800px | ✅ Ready |
| Kentucky | SRTM 30m | ~800px | ✅ Ready |
| Maine | SRTM 30m | ~800px | ✅ Ready |
| Maryland | SRTM 30m | ~800px | ✅ Ready |
| Massachusetts | SRTM 30m | ~800px | ✅ Ready |
| Minnesota | SRTM 30m | ~800px | ✅ Ready |
| Nebraska | SRTM 30m | ~800px | ✅ Ready |
| Nevada | SRTM 30m | ~800px | ✅ Ready |
| New Hampshire | SRTM 30m | ~800px | ✅ Ready |
| New Jersey | SRTM 30m | ~800px | ✅ Ready (New pipeline) |
| New Mexico | SRTM 30m | ~800px | ✅ Ready |
| North Dakota | SRTM 30m | ~800px | ✅ Ready |
| Ohio | SRTM 30m | ~800px | ✅ Ready |
| Oklahoma | SRTM 30m | ~800px | ✅ Ready |
| Oregon | SRTM 30m | ~800px | ✅ Ready |
| Pennsylvania | SRTM 30m | ~800px | ✅ Ready |
| Rhode Island | SRTM 30m | ~800px | ✅ Ready |
| South Dakota | SRTM 30m | ~800px | ✅ Ready |
| Utah | SRTM 30m | ~800px | ✅ Ready |
| Vermont | SRTM 30m | ~800px | ✅ Ready |
| Washington | SRTM 30m | ~800px | ✅ Ready |
| Wisconsin | SRTM 30m | ~800px | ✅ Ready |
| Wyoming | SRTM 30m | ~800px | ✅ Ready |

### Japan (1)

| Prefecture/Region | Source | Resolution | Status |
|-------------------|--------|------------|--------|
| Kochi | SRTM 30m | ~800px | ✅ Ready (New!) |

## ❌ Not Available

### California
- **Issue**: Too large for OpenTopography API (10.4° × 9.5°, limit is ~4° per direction)
- **Options**: 
  1. Download manually from USGS National Map
  2. Split into sub-regions (Northern/Southern California)
  3. Use lower resolution global data

### Florida  
- **Issue**: Too large for OpenTopography API (7.6° × 6.5°)
- **Options**: Same as California

### Idaho
- **Issue**: Legacy TIF file was corrupted (read error)
- **Solution**: Re-download with new pipeline: `python downloaders/usa_3dep.py idaho --auto`

### Other Japan Regions (Shikoku Island, Honshu, etc.)
- **Status**: Not yet downloaded (only Kochi prefecture available)
- **Solution**: Run `python downloaders/japan_gsi.py <region> --auto` (for 30m SRTM)
  - Available: japan, honshu, hokkaido, kyushu, shikoku
- **Note**: High-res GSI data (5-10m) requires manual download

## 🗑️ Cleaned Up

- ❌ Removed: Old USA elevation files (continental_usa_elevation.tif, nationwide_usa_elevation.tif, denver_elevation_10m.tif)
- ❌ Removed: Corrupted Idaho TIF
- ✅ Kept: 28 working state TIF files in data/regions/
- ✅ Added: Kochi Prefecture (Japan) - 18.5 MB raw data

## 📊 Data Quality

All 29 regions:
- ✅ Format version: export_v2
- ✅ Proper elevation arrays (not metadata)
- ✅ File sizes: 3-4.5 MB each
- ✅ Resolution: ~800px max dimension
- ✅ Source: SRTM 30m (global coverage)

## 🔄 Data Pipeline

### For Small States (works automatically):
```bash
python downloaders/usa_3dep.py <state> --auto
```

This automatically:
1. Downloads 30m SRTM data
2. Clips to boundaries
3. Processes for viewer
4. Exports JSON
5. Updates manifest

### For Large States (California, Florida, Texas):
These exceed OpenTopography API limits. Options:

1. **Manual download** from USGS:
   ```bash
   python downloaders/usa_3dep.py california --manual
   ```
   Follow the instructions to download manually.

2. **Use existing legacy data** (if available in data/regions/)

## 📁 Current Structure

```
data/
├── raw/srtm_30m/          # New pipeline downloads (5 states)
├── regions/               # Legacy SRTM data (23 states)
└── processed/srtm_30m/    # Processed files from new pipeline

generated/
└── regions/               # 28 JSON files ready for viewer
    ├── arizona.json
    ├── colorado.json
    ├── ... (26 more states)
    └── regions_manifest.json
```

## 🎯 To Add More States

### Small states (< 4° in each direction):
```bash
python downloaders/usa_3dep.py <state> --auto
```

### Large states:
1. Check if legacy data exists: `ls data/regions/<state>.tif`
2. If exists: `python export_for_web_viewer.py data/regions/<state>.tif --output generated/regions/<state>.json --max-size 800`
3. If not: Manual download required

### International:
```bash
# Japan (Shikoku, etc.)
python downloaders/japan_gsi.py shikoku --auto

# Switzerland
python downloaders/switzerland_swisstopo.py switzerland --auto
```

## 🔒 Data Integrity

All exported files are validated with strict type checking:
- See: `src/data_types.py` for format specifications
- See: `src/validation.py` for validation functions

Every data transformation validates:
- Input format correctness
- Dimension consistency
- Elevation value reasonableness
- Geographic bounds validity

## ✅ System Status: OPERATIONAL

**29 regions ready for visualization!**
- 28 US states
- 1 Japanese prefecture (Kochi)

Missing regions can be added following the instructions above.

---

## 🎯 Recent Additions

**2025-10-24**: Added Kochi Prefecture, Japan (30m SRTM, 2.5 MB JSON)
