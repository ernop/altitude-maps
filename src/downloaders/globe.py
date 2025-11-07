"""
GLOBE (Global Land One-kilometer Base Elevation) downloader.

1km resolution global DEM from NOAA.
Simple global coverage, coarse resolution fallback source.

The complete GLOBE dataset is ~2GB and can be downloaded from NOAA.
This is a placeholder implementation.

TODO: Implement actual GLOBE download once we confirm access method.
For now, this returns False (not implemented) so other sources are tried first.
"""

from pathlib import Path
from typing import Tuple


def download_globe_tile(
    tile_bounds: Tuple[float, float, float, float],
    output_path: Path
) -> bool:
    """
    Download a single 1×1 degree GLOBE tile.
    
    Args:
        tile_bounds: (west, south, east, north) in degrees
        output_path: Where to save the tile
        
    Returns:
        True if successful, False otherwise
        
    Note:
        Currently not implemented - returns False.
        GLOBE is distributed as:
        1. Complete global dataset from NOAA (~2GB)
        2. Regional tiles (need to map tile naming)
        3. User can pre-download and place in tiles directory
    """
    print(f"    GLOBE 1km not yet implemented")
    return False


def download_globe_tiles(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    tiles_dir: Path
) -> list[Path]:
    """
    Download multiple GLOBE tiles for a region.
    
    Args:
        region_id: Region identifier
        bounds: (west, south, east, north)
        tiles_dir: Directory to store tiles
        
    Returns:
        List of successfully downloaded tile paths (empty for now)
    """
    from src.tile_geometry import calculate_1degree_tiles
    
    print(f"GLOBE 1km downloader not yet implemented")
    print(f"  To use GLOBE data:")
    print(f"  1. Download from NOAA NCEI: https://www.ngdc.noaa.gov/mgg/topo/globe.html")
    print(f"  2. Convert to 1×1 degree GeoTIFF tiles")
    print(f"  3. Place in {tiles_dir}")
    print(f"  4. Name as: N40_W080_1000m.tif")
    
    # Check if tiles already exist (user may have pre-downloaded)
    tiles = calculate_1degree_tiles(bounds)
    existing_paths = []
    
    from src.tile_geometry import tile_filename_from_bounds
    for tile_bounds in tiles:
        tile_filename = tile_filename_from_bounds(tile_bounds, "1000m")
        tile_path = tiles_dir / tile_filename
        if tile_path.exists():
            existing_paths.append(tile_path)
    
    if existing_paths:
        print(f"  Found {len(existing_paths)} existing tiles")
    
    return existing_paths

