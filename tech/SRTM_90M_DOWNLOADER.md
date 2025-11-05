# SRTM 90m Downloader

Dedicated tile-based downloader for SRTM 90m elevation data.

## Overview

The SRTM 90m downloader provides efficient, tile-by-tile downloads of lower-resolution elevation data suitable for large regions where 30m resolution provides no visual benefit.

## Key Features

- **Tile-by-tile downloads**: 1-degree tiles with content-based naming
- **Efficient caching**: Shared tile cache in `data/raw/srtm_90m/tiles/`
- **Progress tracking**: Per-tile download progress with tqdm
- **Automatic merging**: Combines tiles into single output file
- **Smart reuse**: Tiles shared across regions for minimal storage
- **Dual datasets**: Supports SRTM 90m (SRTMGL3) and Copernicus 90m (COP90)

## When to Use 90m Data

The system automatically selects 90m data when:
- Region is large (visible pixels >180m after downsampling)
- Nyquist sampling rule: 90m source provides >=2.0x oversampling
- Example: For 2048px output of large country, visible pixels might be 400m each
  - 90m source gives 4.4x oversampling (400m / 90m = 4.4)
  - Using 30m would give 13.3x oversampling (wasteful, no visual benefit)

## Tile Naming Convention

Follows standard 1-degree grid naming:
```
Format: {NS}{lat}_{EW}{lon}_90m.tif
Examples:
  N40_W111_90m.tif  (40degN, 111degW)
  S05_E120_90m.tif  (5degS, 120degE)
  N65_W020_90m.tif  (65degN, 20degW)
```

Stored in: `data/raw/srtm_90m/tiles/`

## Usage

### Automatic (Recommended)

The orchestrator automatically selects 90m when appropriate:

```bash
python ensure_region.py china  # Large region - automatically uses 90m
```

### Manual

Import and use directly:

```python
from pathlib import Path
from src.downloaders.srtm_90m import download_srtm_90m_tiles

success = download_srtm_90m_tiles(
    region_id='russia',
    bounds=(19.6, 41.1, 169.0, 81.9),  # Very large region
    output_path=Path('data/merged/srtm_90m/russia_merged_90m.tif')
)
```

### Small Regions

For regions < 4 degrees, use single-file download:

```python
from src.downloaders.srtm_90m import download_srtm_90m_single

success = download_srtm_90m_single(
    region_id='iceland',
    bounds=(-24.5, 63.4, -13.5, 66.5),
    output_path=Path('data/merged/srtm_90m/iceland_merged_90m.tif')
)
```

## Dataset Selection

- **SRTM 90m (SRTMGL3)**: 60degN to 56degS coverage
- **Copernicus 90m (COP90)**: Global coverage (use for high latitudes)

Auto-selects based on latitude, or override:

```python
download_srtm_90m_tiles(..., dataset='COP90')  # Force Copernicus
download_srtm_90m_tiles(..., dataset='SRTMGL3')  # Force SRTM
```

## Tile Caching and Reuse

All tiles are cached in shared directory:
- Location: `data/raw/srtm_90m/tiles/`
- Content-based naming enables reuse across regions
- Adjacent countries sharing tiles reuse same cache files
- Example: Mongolia and China share N45_E100_90m.tif

Benefits:
- Minimal storage overhead
- Faster downloads for adjacent regions
- Clean, organized data structure

## Performance

Large region example (China: 18deg x 14deg):
- Tiles: 252 tiles (1-degree each)
- First download: ~5-10 minutes (depends on API speed)
- Cached reuse: <1 minute (merge only)
- File size: ~80-120 MB merged

## Integration with Pipeline

The 90m downloader integrates seamlessly with the processing pipeline:

1. **Download**: `ensure_region.py` calls orchestrator
2. **Orchestrator**: Selects 90m based on Nyquist rule
3. **Download**: `srtm_90m.py` downloads tiles
4. **Merge**: Tiles combined into merged file
5. **Pipeline**: Standard processing (clip, reproject, downsample, export)

Output location: `data/merged/srtm_90m/{region_id}_merged_90m.tif`

## Comparison: 90m vs 30m

| Aspect | 90m | 30m |
|--------|-----|-----|
| Coverage | Global (with Copernicus) | 60degN to 56degS (SRTM) |
| Tile size | ~8-12 MB | ~80-120 MB |
| Download speed | Fast | Slower |
| Storage | 3x less | 3x more |
| Best for | Large regions | Small regions, detail |
| Oversampling (large) | Optimal (2-4x) | Wasteful (6-12x) |

## Error Handling

The downloader handles:
- API timeouts (300s timeout per tile)
- Network failures (retry on next run)
- Partial downloads (cleaned up automatically)
- Missing tiles (reported in summary)
- API key missing (clear error message)

## API Key Setup

Required: OpenTopography API key (free)

1. Get key: https://portal.opentopography.org/
2. Add to `settings.json`:
```json
{
  "opentopography": {
    "api_key": "your_key_here"
  }
}
```

## File Structure

```
data/
  raw/
    srtm_90m/
      tiles/
        N40_W111_90m.tif
        N40_W112_90m.tif
        ...
  merged/
    srtm_90m/
      china_merged_90m.tif
      russia_merged_90m.tif
      ...
```

## Future Enhancements

Potential improvements:
- Parallel tile downloads (thread pool)
- Progress persistence (resume interrupted downloads)
- Tile validation (checksum verification)
- Alternative sources (ASTER, ALOS)
- Automatic cleanup of unused tiles

