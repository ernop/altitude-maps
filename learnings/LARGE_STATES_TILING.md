# Large States - Tiling Guide

Problem: Some US states are too large for single OpenTopography downloads (4deg limit).
Solution: Download in tiles, merge, then clip to state boundaries.

## States Requiring Tiling

States larger than 4deg in any direction:

Alaska: 40deg x 20.5deg -> 10x6 tiles (60 tiles total) - HUGE
Texas: 13.14deg x 10.66deg -> 4x3 tiles (12 tiles)
Montana: 12.01deg x 4.64deg -> 4x2 tiles (8 tiles)
California: 10.35deg x 9.48deg -> 3x3 tiles (9 tiles)
Oregon: 8.11deg x 4.3deg -> 3x2 tiles (6 tiles)
Wyoming: 7.01deg x 4.02deg -> 2x2 tiles (4 tiles)
Nevada: 5.97deg x 7deg -> 2x2 tiles (4 tiles)
Idaho: 6.2deg x 7.01deg -> 2x2 tiles (4 tiles)
New Mexico: 6.05deg x 5.67deg -> 2x2 tiles (4 tiles)
Arizona: 5.77deg x 5.67deg -> 2x2 tiles (4 tiles)
Utah: 5.01deg x 5deg -> 2x2 tiles (4 tiles)

## Usage

Simple command for any large state:

python downloaders/tile_large_states.py california
python downloaders/tile_large_states.py texas
python downloaders/tile_large_states.py alaska

## What It Does

1. Calculate tile grid (e.g., 3x3 for California)
2. Download each tile separately (~3-4deg each, well under limit)
3. Merge tiles into single GeoTIFF
4. Clip to actual state boundary (not rectangle)
5. Process and export for viewer

## Advantages

Safety: Each tile download is small, won't timeout
Speed: Tiles download in parallel (if modified for async)
Quality: Same 30m SRTM data, just split up
Boundary: Still clips to actual state shape

## Files Created

During download:
  data/raw/srtm_30m/tiles/tile_N34_W125_srtm_30m_30m.tif
  data/raw/srtm_30m/tiles/tile_N34_W122_srtm_30m_30m.tif
  ... (9 tiles total for California using content-based naming)

After merge:
  data/raw/srtm_30m/california_bbox_30m.tif (merged)

After pipeline:
  data/clipped/srtm_30m/california_clipped_srtm_30m_v1.tif
  data/processed/srtm_30m/california_srtm_30m_800px_v2.tif
  generated/regions/california_srtm_30m_v2.json

## Regular vs Tiled Download

Small states (< 4deg in all directions):
  python downloaders/usa_3dep.py vermont --auto
  Single download, fast

Large states (> 4deg in any direction):
  python downloaders/tile_large_states.py california
  Multiple tiles, merged automatically

## Implementation Details

Tile calculation: Splits bounds evenly into grid
Tile size: ~3-3.5deg per tile (under 4deg limit)
Merge method: rasterio.merge (seamless, no artifacts)
State clipping: Applied AFTER merge (normal pipeline)

## Alaska Special Case

Alaska is MASSIVE (40deg x 20.5deg) and needs 60 tiles.
Download time estimate: ~30-60 minutes for all tiles.
Final merged file: ~2-3 GB.

Consider downloading Alaska overnight or in background.

## Future Improvements

Potential enhancements:
- Parallel tile downloads (async)
- Resume capability if interrupted
- Progress tracking across all tiles
- Automatic retry for failed tiles

