"""
GMTED2010 (Global Multi-resolution Terrain Elevation Data 2010) downloader.

Coarse-resolution global DEMs from USGS/NGA.
Resolutions: 250m, 500m, 1km (7.5, 15, 30 arc-seconds)

GMTED2010 is available via USGS EarthExplorer but has no automated API.
Users must manually download tiles and place them in the tiles directory.

Download instructions:
1. Visit https://earthexplorer.usgs.gov/
2. Define region of interest (use bounds from error message)
3. Select "Digital Elevation" > "GMTED2010" in Data Sets
4. Choose resolution: 7.5 arc-sec (250m), 15 arc-sec (500m), or 30 arc-sec (1km)
5. Download tiles and place in data/raw/gmted2010_{resolution}/tiles/
6. Name files using standard convention: N{lat}_W{lon}_{resolution}m.tif
   Example: N40_W080_250m.tif for 40°N, 80°W, 250m resolution

The system will automatically detect and use pre-downloaded tiles.
"""

from pathlib import Path
from typing import Tuple


def download_gmted2010_tile(
    tile_bounds: Tuple[float, float, float, float],
    resolution: int,
    output_path: Path
) -> bool:
    """
    Download a single GMTED2010 tile.
    
    Args:
        tile_bounds: (west, south, east, north) in degrees
        resolution: 250, 500, or 1000 meters
        output_path: Where to save the tile
        
    Returns:
        True if successful, False otherwise
        
    Note:
        Currently not implemented - returns False.
        GMTED2010 requires either:
        1. Direct download from USGS tiles (need to map URL pattern)
        2. Access via USGS EarthExplorer API (requires additional setup)
        3. Pre-downloaded complete dataset (user provides)
    """
    print(f"    GMTED2010 {resolution}m not yet implemented")
    return False


def download_gmted2010_tiles(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    resolution: int,
    tiles_dir: Path
) -> list[Path]:
    """
    Download multiple GMTED2010 tiles for a region.
    
    Args:
        region_id: Region identifier
        bounds: (west, south, east, north)
        resolution: 250, 500, or 1000 meters
        tiles_dir: Directory to store tiles
        
    Returns:
        List of successfully downloaded tile paths (empty for now)
    """
    from src.tile_geometry import calculate_1degree_tiles
    
    print(f"GMTED2010 {resolution}m requires manual download")
    print(f"  Automated download not available (no public API)")
    print(f"  To use GMTED2010 data:")
    print(f"  1. Visit https://earthexplorer.usgs.gov/")
    print(f"  2. Search for region bounds: {bounds}")
    print(f"  3. Select 'Digital Elevation' > 'GMTED2010'")
    print(f"  4. Choose resolution: {resolution}m")
    print(f"  5. Download tiles and place in: {tiles_dir}")
    print(f"  6. Name files: N{{lat}}_W{{lon}}_{resolution}m.tif")
    print(f"     Example: N40_W080_{resolution}m.tif")
    
    # Check if tiles already exist (user may have pre-downloaded)
    tiles = calculate_1degree_tiles(bounds)
    existing_paths = []
    
    from src.tile_geometry import tile_filename_from_bounds
    for tile_bounds in tiles:
        tile_filename = tile_filename_from_bounds(tile_bounds, f"{resolution}m")
        tile_path = tiles_dir / tile_filename
        if tile_path.exists():
            existing_paths.append(tile_path)
    
    if existing_paths:
        print(f"  Found {len(existing_paths)} existing tiles")
    
    return existing_paths

