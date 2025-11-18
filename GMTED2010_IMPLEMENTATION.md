# GMTED2010 Downloader Implementation

## Status: ✅ COMPLETE

GMTED2010 downloader has been fully implemented for resolutions >100m (250m, 500m, 1000m).

## What Was Implemented

### 1. Direct Download URLs
- **Base URL**: `https://edcintl.cr.usgs.gov/downloads/sciweb1/shared/topo/downloads/GMTED/Grid_ZipFiles/`
- **Pattern**: `{product}{arcsec}_grd.zip`
  - Products: `md` (median - recommended), `mn` (mean), `mi` (minimum), `mx` (maximum), `sd` (std dev), `ds` (subsample), `be` (breakline)
  - Arc-seconds: `75` (7.5 arc-sec = 250m), `15` (15 arc-sec = 500m), `30` (30 arc-sec = 1000m)

### 2. Downloader Implementation (`src/downloaders/gmted2010.py`)
- **Downloads global grid** (cached for reuse in `data/.cache/gmted2010/`)
- **Extracts ZIP** (handles ArcGrid format)
- **Converts to GeoTIFF** (if needed)
- **Clips to tile bounds** (1×1 degree tiles)
- **Saves as standard tile format** (`N{lat}_W{lon}_{resolution}m.tif`)

### 3. Integration
- ✅ Integrated into `source_coordinator.py` (routing)
- ✅ Integrated into `source_registry.py` (source definitions)
- ✅ Integrated into `orchestrator.py` (resolution selection)
- ✅ Removed temporary restrictions on resolutions

### 4. Resolution Support
- **250m** (7.5 arc-seconds) - GMTED2010
- **500m** (15 arc-seconds) - GMTED2010
- **1000m** (30 arc-seconds) - GMTED2010

## How It Works

1. **First Download**: Downloads entire global grid (~2.9GB for 250m) and caches it
2. **Subsequent Downloads**: Uses cached global grid, clips to tile bounds
3. **Tile Generation**: Creates standard 1×1 degree tiles compatible with existing pipeline

## Usage

The downloader is automatically used when:
- Region requires >100m resolution (based on Nyquist sampling)
- Large regions (e.g., California) that need coarse resolution
- System selects GMTED2010 as optimal source

Example:
```bash
python ensure_region.py california
# System automatically selects 500m or 1000m GMTED2010 if needed
```

## File Structure

```
data/
  .cache/
    gmted2010/
      gmted2010_250m_global.tif   # Cached global grid
      gmted2010_500m_global.tif
      gmted2010_1000m_global.tif
  raw/
    gmted2010_250m/
      tiles/
        N40_W080_250m.tif         # Clipped tiles
    gmted2010_500m/
      tiles/
        N40_W080_500m.tif
    gmted2010_1000m/
      tiles/
        N40_W080_1000m.tif
```

## Notes

- **Global grids are large** (~2.9GB for 250m) but cached for reuse
- **First download takes time** (download + extract + convert)
- **Subsequent tiles are fast** (just clipping from cached grid)
- **ArcGrid format** is automatically converted to GeoTIFF
- **Product selection**: Uses `md` (median) by default (most commonly used)

## Testing

To test with a large region:
```bash
python ensure_region.py california --force-reprocess
# Should automatically select GMTED2010 if visible pixels > 500m
```

## Next Steps

- ✅ Implementation complete
- ⏳ Testing with large regions (pending user test)
- ⏳ Performance optimization if needed

