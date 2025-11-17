"""
Test multi-source download coordinator with corrected Copernicus S3 downloader.
"""

from src.downloaders.source_coordinator import download_tiles_for_region
from src.regions_config import get_region

# Get Minnesota config (small test region)
region = get_region('minnesota')
print(f'Testing multi-source download for: {region.name}')
print(f'Bounds: {region.bounds}')
print(f'Target resolution: 90m')
print()

# Try downloading just the tiles
from pathlib import Path

tiles_dir = Path('data/raw/srtm_90m/tiles')
tiles_dir.mkdir(parents=True, exist_ok=True)

tiles = download_tiles_for_region(
    region_id='minnesota',
    region_bounds=region.bounds,
    resolution_m=90,
    tiles_dir=tiles_dir
)

success = len(tiles) > 0

print(f'\n{"="*60}')
print(f'FINAL RESULT: {"SUCCESS" if success else "FAILED"}')
print(f'{"="*60}')

