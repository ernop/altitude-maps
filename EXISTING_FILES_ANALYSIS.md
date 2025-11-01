# Existing Files Analysis & Splitting Strategy

## Current Raw Files Inventory

### Bbox Files (data/raw/srtm_30m/)

**Found 13 bbox files with various sizes:**

1. **Small/Medium files (already reasonable size):**
   - `bbox_N13_E120_N15_E122_srtm_30m_30m.tif` - **2deg x 2deg** (Philippines area)
   - `bbox_N34_W082_N36_W081_srtm_30m_30m.tif` - **2deg x 1deg** (US East Coast)
   - `bbox_N37_W122_N38_W121_srtm_30m_30m.tif` - **1deg x 1deg** ✅ Already grid-aligned!
   - `bbox_N40_W074_N41_W074_srtm_30m_30m.tif` - **1deg x 1deg** ✅ Already grid-aligned!
   - `bbox_N40_W111_N41_W110_srtm_30m_30m.tif` - **1deg x 1deg** ✅ Already grid-aligned!
   - `bbox_N40_W111_N41_W111_srtm_30m_30m.tif` - **1deg x 1deg** ✅ Already grid-aligned!

2. **Large files (should be split):**
   - `bbox_N34_W090_N37_W081_srtm_30m_30m.tif` - **3deg x 3deg** (US Mountain West)
   - `bbox_N37_W114_N43_W109_srtm_30m_30m.tif` - **5deg x 6deg** (Western US)
   - `bbox_N48_W064_N51_W061_srtm_30m_30m.tif` - **3deg x 3deg** (Eastern Canada)
   - `bbox_N50_E155_N63_E163_srtm_30m_30m.tif` - **8deg x 13deg** (Kamchatka/Russia Far East)
   - `bbox_S53_W061_S50_W057_srtm_30m_30m.tif` - **4deg x 3deg** (South America/Falklands)

3. **Corrupted/invalid files (should be removed):**
   - `bbox_W111_6220_S40_1467_E111_0902_N40_7020_srtm_30m_30m.tif` - Invalid parsing (222deg!)
   - `bbox_W111_8700_S40_4800_E111_1473_N40_7600_srtm_30m_30m.tif` - Invalid parsing (223deg!)

### Tile Files (data/raw/srtm_30m/tiles/)

**Found 10 tile files - ALL are already 1-degree tiles! ✅**

- `tile_N50_E156_srtm_30m_30m.tif` through `tile_N59_E159_srtm_30m_30m.tif` (8 files)
- `tile_S53_W059_srtm_30m_30m.tif` and `tile_S53_W061_srtm_30m_30m.tif` (2 files)

**All tiles are exactly 1.0deg x 1.0deg - already using the standard grid!**

---

## File Size Analysis

**1-degree tile sizes (at various latitudes):**
- At equator (30m): ~21 MB
- At 40degN (30m): ~16 MB
- At 65degN (30m): ~8.7 MB
- At 40degN (90m): ~1.8 MB

**Example existing bbox file:**
- `bbox_N40_W111_N41_W110_srtm_30m_30m.tif`: ~4.15 MB (1deg x 1deg at 40degN)

---

## Provider Limitations by Resolution

### OpenTopography API

**SRTMGL1 (30m) & COP30 (30m):**
- **Maximum area**: 450,000 km²
- **Maximum dimension**: ~4.0 degrees
- **Tiling threshold**: Proactively tile when area > 420,000 km² or dimension > 4.0deg
- **Example at 40degN**: 4deg x 4deg ≈ 425,000 km² (borderline)

**SRTMGL3 (90m) & COP90 (90m):**
- **Maximum area**: ~500,000 km² (less data per area)
- **Maximum dimension**: ~4.5 degrees
- **More lenient** due to lower resolution

### USGS 3DEP (USA only, 10m)

**Maximum area**: ~1,000,000 km²
- **Maximum dimension**: ~5-6 degrees
- **Usually no tiling needed** for individual US states
- **California** (~962,000 km²) is borderline but usually works

---

## Splitting Strategy

### Which Files Need Splitting?

**Large bbox files that exceed 1-degree grid:**
1. `bbox_N34_W090_N37_W081_srtm_30m_30m.tif` - **3deg x 3deg** → Split into **9 tiles** (3x3 grid)
2. `bbox_N37_W114_N43_W109_srtm_30m_30m.tif` - **5deg x 6deg** → Split into **30 tiles** (5x6 grid)
3. `bbox_N48_W064_N51_W061_srtm_30m_30m.tif` - **3deg x 3deg** → Split into **9 tiles** (3x3 grid)
4. `bbox_N50_E155_N63_E163_srtm_30m_30m.tif` - **8deg x 13deg** → Split into **104 tiles** (8x13 grid)
5. `bbox_S53_W061_S50_W057_srtm_30m_30m.tif` - **4deg x 3deg** → Split into **12 tiles** (4x3 grid)

**Files that are already 1-degree (no splitting needed):**
- `bbox_N37_W122_N38_W121_srtm_30m_30m.tif` ✅
- `bbox_N40_W074_N41_W074_srtm_30m_30m.tif` ✅
- `bbox_N40_W111_N41_W110_srtm_30m_30m.tif` ✅
- `bbox_N40_W111_N41_W111_srtm_30m_30m.tif` ✅

**Files that are 2-degree (could be split, but optional):**
- `bbox_N13_E120_N15_E122_srtm_30m_30m.tif` - **2deg x 2deg** (4 tiles)
- `bbox_N34_W082_N36_W081_srtm_30m_30m.tif` - **2deg x 1deg** (2 tiles)

---

## Naming Convention for Split Tiles

**Standard 1-degree tile naming:**
```
tile_{NS}{lat:02d}_{EW}{lon:03d}_{dataset}_{resolution}.tif
```

**Examples:**
- `tile_N40_W111_srtm_30m_30m.tif` (40degN, 111degW, 1deg x 1deg)
- `tile_N41_W110_srtm_30m_30m.tif` (41degN, 110degW, 1deg x 1deg)
- `tile_S50_W061_srtm_30m_30m.tif` (50degS, 61degW, 1deg x 1deg)

**Where:**
- `{NS}` = `N` for positive latitude, `S` for negative
- `{EW}` = `E` for positive longitude, `W` for negative
- `{lat}` = 2-digit integer latitude (southwest corner)
- `{lon}` = 3-digit integer longitude (southwest corner)
- Always represents **1.0 degree x 1.0 degree tile** from southwest corner

---

## Splitting Process

**For each large bbox file:**

1. **Read the GeoTIFF** using rasterio
2. **Determine tile grid** based on bounds (snap to 1-degree grid)
3. **For each 1-degree tile:**
   - Extract data for that tile's bounds
   - Generate tile filename using southwest corner
   - Check if tile already exists in shared pool
   - If not exists, save tile to `data/raw/srtm_30m/tiles/`
   - Create metadata JSON for tile
4. **After all tiles created**, optionally delete original large bbox file

**Benefits:**
- **Reuse existing downloads** - don't need to re-download!
- **Standardize on 1-degree grid** - unified system
- **Enable maximum reuse** - multiple regions share same tiles
- **No special cases** - everything is just "1-degree tiles"

---

## Implementation Notes

**Splitting is feasible because:**
1. GeoTIFF files can be read and cropped easily with rasterio
2. Tile bounds are deterministic (1-degree grid)
3. We can check if tiles already exist before saving
4. Original bbox files can be kept as backup during migration

**Example splitting:**
- Large file: `bbox_N37_W114_N43_W109_srtm_30m_30m.tif` (5deg x 6deg)
- Would create 30 tiles: `tile_N37_W114`, `tile_N37_W113`, ..., `tile_N42_W109`
- Each tile: 1deg x 1deg, stored in shared pool
- Future regions using any part of this area will reuse these tiles!

---

## Summary

**Existing files:**
- ✅ **10 tiles** already 1-degree (perfect!)
- ✅ **4 bbox files** already 1-degree (just need to move/rename)
- ⚠️ **5 large bbox files** should be split into 1-degree tiles
- ⚠️ **2 bbox files** are 2-degree (optional split)
- ❌ **2 corrupted files** should be removed

**Total tiles needed after splitting:**
- Current: 10 tiles
- From large bboxes: ~164 tiles (9+30+9+104+12)
- **Grand total: ~174 tiles** (all 1-degree, standardized grid)

**Provider limits:**
- **1-degree tiles are always safe** - well under 450,000 km² limit
- **1-degree tiles fit any provider** - OpenTopography, USGS, etc.
- **Maximum reuse** - regions share tiles naturally

