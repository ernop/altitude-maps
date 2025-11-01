"""
Tile geometry utilities for 1-degree unified grid system.

This module handles all tile-related geometric calculations:
- Snapping bounds to grid boundaries
- Calculating 1-degree tile coverage
- Generating tile filenames from bounds

These functions are used across the download pipeline to ensure
consistent grid alignment and tile reuse.
"""

import math
from typing import Tuple, List


def snap_bounds_to_grid(bounds: Tuple[float, float, float, float], 
                        grid_size: float = 1.0) -> Tuple[float, float, float, float]:
    """
    Snap bounding box to grid boundaries to enable reuse across regions.
    
    Expands bounds outward to nearest grid boundaries (west/south floor down, east/north ceil up).
    Uses unified 1-degree grid system - all downloads become 1-degree tiles that can be shared.
    
    Args:
        bounds: (west, south, east, north) in degrees
        grid_size: Grid increment in degrees (default 1.0 = integer-degree grid)
        
    Returns:
        Tuple of (west, south, east, north) snapped to grid boundaries
        
    Example:
        Input:  (-111.622, 40.1467, -111.0902, 40.7020)
        Output: (-112.0, 40.0, -111.0, 41.0)  # Snapped to 1.0-degree grid
    """
    west, south, east, north = bounds
    
    # Snap west/south down (floor), east/north up (ceil)
    # For negative values: floor goes more negative, ceil goes less negative
    snapped_west = math.floor(west / grid_size) * grid_size
    snapped_south = math.floor(south / grid_size) * grid_size
    snapped_east = math.ceil(east / grid_size) * grid_size
    snapped_north = math.ceil(north / grid_size) * grid_size
    
    return (snapped_west, snapped_south, snapped_east, snapped_north)


def calculate_1degree_tiles(bounds: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
    """
    Calculate list of 1-degree tiles needed to cover bounds.
    
    Unified 1-degree grid system - all downloads become 1-degree tiles.
    
    Args:
        bounds: (west, south, east, north) in degrees
    
    Returns:
        List of 1-degree tile bounds (west, south, east, north) for each tile
    
    Example:
        Input:  (-112.0, 40.0, -110.0, 42.0)  # 2deg x 2deg region
        Output: [
            (-112.0, 40.0, -111.0, 41.0),  # N40_W112_30m.tif
            (-111.0, 40.0, -110.0, 41.0),  # N40_W111_30m.tif
            (-112.0, 41.0, -111.0, 42.0),  # N41_W112_30m.tif
            (-111.0, 41.0, -110.0, 42.0),  # N41_W111_30m.tif
        ]
    """
    west, south, east, north = bounds
    
    # Snap bounds to 1-degree grid
    snapped_west = math.floor(west / 1.0) * 1.0
    snapped_south = math.floor(south / 1.0) * 1.0
    snapped_east = math.ceil(east / 1.0) * 1.0
    snapped_north = math.ceil(north / 1.0) * 1.0
    
    tiles = []
    for lat in range(int(snapped_south), int(snapped_north)):
        for lon in range(int(snapped_west), int(snapped_east)):
            tile_bounds = (lon, lat, lon + 1.0, lat + 1.0)
            tiles.append(tile_bounds)
    
    return tiles


def tile_filename_from_bounds(bounds: Tuple[float, float, float, float], 
                              resolution: str = '30m',
                              use_grid_alignment: bool = True,
                              grid_size: float = 1.0) -> str:
    """
    Generate filename for a 1-degree tile based on its bounds and resolution.
    
    Unified 1-degree grid system - all downloads become 1-degree tiles.
    Simple naming format: {NS}{lat}_{EW}{lon}_{resolution}.tif
    
    Example (with 1-degree grid):
        Input bounds:  (-111.622, 40.1467, -111.0902, 40.7020)
        Snapped to:    (-112.0, 40.0, -111.0, 41.0)
        Filenames:     N40_W112_30m.tif, N40_W111_30m.tif, etc.
    
    Args:
        bounds: (west, south, east, north) in degrees
        resolution: Resolution identifier (e.g., '30m', '90m', '10m')
        use_grid_alignment: If True, snap bounds to grid before generating filename (default True)
        grid_size: Grid increment in degrees for snapping (default 1.0 = integer-degree grid)
        
    Returns:
        Filename string for 1-degree tile
    """
    west, south, east, north = bounds
    
    # Snap bounds to grid for filename (enables reuse)
    if use_grid_alignment:
        west, south, east, north = snap_bounds_to_grid(bounds, grid_size)
    
    # UNIFIED 1-DEGREE GRID: Generate simple tile filename from southwest corner
    # Format: {NS}{lat}_{EW}{lon}_{resolution}.tif
    # Example: N40_W111_30m.tif
    # Always use 1-degree grid - southwest corner determines tile identity
    
    # Southwest corner coordinates (integer degrees)
    sw_lat = int(south)
    sw_lon = int(west)
    
    # Format with direction indicators (no zero-padding for latitude, 3-digit for longitude)
    if sw_lat >= 0:
        lat_str = f"N{sw_lat}"
    else:
        lat_str = f"S{abs(sw_lat)}"
    
    if sw_lon >= 0:
        lon_str = f"E{sw_lon:03d}"
    else:
        lon_str = f"W{abs(sw_lon):03d}"
    
    return f"{lat_str}_{lon_str}_{resolution}.tif"

