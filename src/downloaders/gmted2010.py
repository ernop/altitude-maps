"""
GMTED2010 (Global Multi-resolution Terrain Elevation Data 2010) downloader.

Coarse-resolution global DEMs from USGS/NGA.
Resolutions: 250m, 500m, 1km (7.5, 15, 30 arc-seconds)

These are fallback sources for when finer resolution data is unavailable.
Data is organized in tiles by USGS - this is a placeholder implementation.

TODO: Implement actual GMTED2010 download once we confirm access method.
For now, this returns False (not implemented) so other sources are tried first.
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
    
    print(f"GMTED2010 {resolution}m downloader not yet implemented")
    print(f"  To use GMTED2010 data:")
    print(f"  1. Download tiles from USGS EarthExplorer")
    print(f"  2. Place in {tiles_dir}")
    print(f"  3. Name as: N40_W080_{resolution}m.tif")
    
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

