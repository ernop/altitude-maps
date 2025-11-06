# High-Resolution Elevation Data Download Guide

This guide provides information about available elevation datasets and regions for the altitude maps project.

## Available Datasets

| Dataset | Resolution | Coverage | Best For |
|---------|-----------|----------|----------|
|**AW3D30** | 30m | Global (82degN-82degS) |**Japan, mountains, Asia** |
| SRTMGL1 | 30m | Global (60degN-56degS) | General use, USA |
| NASADEM | 30m | Global (60degN-56degS) | Improved SRTM, void-filled |
| COP30 | 30m | Global (90degN-90degS) | Polar regions, complete coverage |
| SRTMGL3 | 90m | Global (60degN-56degS) | Lower resolution, smaller files |
| COP90 | 90m | Global (90degN-90degS) | Polar regions, smaller files |

**Special:** USGS 3DEP (10m) - USA only, manual download required from USGS National Map

## Available Regions

### Pre-defined High-Resolution Regions

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

## Dataset Recommendations

### For Regions with Mountains:
**Best: AW3D30 (ALOS World 3D)**
- 30m resolution
- Excellent quality for mountains and Asia
- Made by JAXA specifically for terrain mapping

### General Use:
**Good: SRTMGL1 (30m via API)**
- Most commonly used
- Good quality for most terrain

### For US Regions:
**Better: USGS 3DEP (10m, manual download)**
- Best available for USA
- Requires manual download from USGS National Map

### For Polar Regions:
**Best: COP30 or COP90 (Copernicus)**
- Full polar coverage
- Consistent quality

## Additional Resources

-**OpenTopography Portal:** https://portal.opentopography.org/
-**USGS National Map:** https://apps.nationalmap.gov/downloader/
-**ALOS Global DEM:** https://www.eorc.jaxa.jp/ALOS/en/aw3d30/
-**Copernicus DEM:** https://spacedata.copernicus.eu/collections/copernicus-digital-elevation-model

