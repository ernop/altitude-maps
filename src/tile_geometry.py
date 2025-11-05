"""
Tile geometry and filename utilities for 1-degree unified grid system.

This module handles all tile-related geometric calculations and filename generation:
- Snapping bounds to grid boundaries
- Calculating 1-degree tile coverage
- Generating tile filenames from bounds
- Estimating file sizes for downloads
- Abstract filename generation for pipeline stages

These functions are used across the download pipeline to ensure
consistent grid alignment and tile reuse.
"""

import math
from typing import Tuple, List, Optional, Dict
from pathlib import Path


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
        Filename string for 1-degree tile (source-agnostic, resolution-specific)
        
    Note:
        Source is NOT included in tile filenames - tiles are stored in source-specific
        directories (data/raw/srtm_30m/, data/raw/usa_3dep/, etc.) so the directory
        path provides the source context. This enables simpler filenames and better reuse.
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


def merged_filename_from_region(region_id: str, bounds: Tuple[float, float, float, float], resolution: str) -> str:
    """
    Generate merged filename that includes bounds for cache invalidation.
    
    When region bounds change, the filename changes, preventing stale data reuse.
    Format: {region_id}_{bounds_compact}_merged_{resolution}.tif
    
    Args:
        region_id: Region identifier (e.g., 'cottonwood_valley')
        bounds: (west, south, east, north) in degrees
        resolution: Resolution identifier (e.g., '10m', '30m', '90m')
        
    Returns:
        Filename string with embedded bounds information
        
    Example:
        Input: region_id='cottonwood_valley', bounds=(-111.87, 40.55, -111.66, 40.76), resolution='10m'
        Output: 'cottonwood_valley_w111p87_s40p55_e111p66_n40p76_merged_10m.tif'
    """
    west, south, east, north = bounds
    
    # Format bounds compactly: replace '.' with 'p', '-' with 'm'
    # Use 2 decimal precision for reasonable uniqueness
    def fmt(val, prefix):
        # Format: prefix + value with 'p' for decimal and 'm' for minus
        if val < 0:
            return f"{prefix}m{abs(val):.2f}".replace('.', 'p')
        else:
            return f"{prefix}{val:.2f}".replace('.', 'p')
    
    bounds_str = f"{fmt(west, 'w')}_{fmt(south, 's')}_{fmt(east, 'e')}_{fmt(north, 'n')}"
    
    return f"{region_id}_{bounds_str}_merged_{resolution}"


def estimate_raw_file_size_mb(bounds: Tuple[float, float, float, float], resolution_meters: int) -> float:
    """
    Estimate raw GeoTIFF file size in MB based on bounds and resolution.
    
    Args:
        bounds: (west, south, east, north) in degrees
        resolution_meters: Source resolution in meters (10, 30, or 90)
    
    Returns:
        Estimated file size in MB (approximate)
    """
    west, south, east, north = bounds
    width_deg = east - west
    height_deg = north - south
    
    # Calculate real-world dimensions in meters
    center_lat = (north + south) / 2.0
    meters_per_deg_lat = 111_320
    meters_per_deg_lon = 111_320 * math.cos(math.radians(center_lat))
    
    width_m = width_deg * meters_per_deg_lon
    height_m = height_deg * meters_per_deg_lat
    
    # Estimate pixels (accounting for actual resolution)
    pixels_x = int(width_m / resolution_meters)
    pixels_y = int(height_m / resolution_meters)
    
    # Estimate file size (float32 = 4 bytes per pixel, plus compression overhead)
    # GeoTIFF compression typically achieves 50-70% reduction for elevation data
    uncompressed_size_bytes = pixels_x * pixels_y * 4
    # Estimate 60% compression ratio (typical for elevation GeoTIFFs)
    estimated_size_bytes = uncompressed_size_bytes * 0.4
    
    return estimated_size_bytes / (1024 * 1024)


def get_bounds_from_raw_file(raw_path: Path) -> Optional[Tuple[float, float, float, float]]:
    try:
        import rasterio
        with rasterio.open(raw_path) as src:
            bounds = src.bounds
            return (bounds.left, bounds.bottom, bounds.right, bounds.top)
    except Exception:
        return None


def abstract_filename_from_raw(raw_path: Path, stage: str, source: str, 
                                boundary_name: Optional[str] = None, 
                                target_pixels: Optional[int] = None,
                                resolution: Optional[str] = None) -> Optional[str]:
    """
    Generate abstract filename for pipeline stages based on actual data bounds.
    
    CRITICAL: Uses actual bounds from the raw file to ensure uniqueness.
    When region bounds change, the raw file bounds change, so processed files
    get new names and are regenerated (preventing stale data reuse).
    
    Args:
        raw_path: Path to raw GeoTIFF file
        stage: Pipeline stage ('raw', 'clipped', 'processed')
        source: Data source (e.g., 'srtm_30m')
        boundary_name: Optional boundary name for clipped files
        target_pixels: Target resolution for processed files
        resolution: Resolution identifier
        
    Returns:
        Abstract filename that uniquely identifies the data by its bounds
    """
    bounds = get_bounds_from_raw_file(raw_path)
    if bounds is None:
        return None
    
    # Generate bounds-based identifier that captures actual data extent
    # Format: bbox_N{north}_S{south}_E{east}_W{west}
    west, south, east, north = bounds
    
    # Format coordinates with 2 decimal places for uniqueness
    def format_coord(val, is_lat=False):
        abs_val = abs(val)
        if is_lat:
            prefix = 'N' if val >= 0 else 'S'
        else:
            prefix = 'E' if val >= 0 else 'W'
        return f"{prefix}{abs_val:06.2f}".replace('.', 'p')
    
    bounds_id = f"bbox_{format_coord(north, True)}_{format_coord(south, True)}_{format_coord(east, False)}_{format_coord(west, False)}"
    
    if stage == 'raw':
        return raw_path.name
    elif stage == 'clipped':
        if boundary_name:
            boundary_hash = hash(boundary_name)
            boundary_suffix = f"_{abs(boundary_hash) % 1000000:06d}"
        else:
            boundary_suffix = ""
        return f"{bounds_id}_clipped{boundary_suffix}_v1.tif"
    elif stage == 'processed':
        return f"{bounds_id}_processed_{target_pixels}px_v2.tif"
    elif stage == 'exported':
        raise ValueError("Exported JSON files use region_id-based naming, not abstract naming.")
    
    return None



def calculate_visible_pixel_size(bounds: Tuple[float, float, float, float], target_pixels: int) -> Dict:
    """Calculate final visible pixel size in meters after downsampling to target_pixels.
    
    This helps determine if 30m or 90m source data is appropriate:
    - If visible pixels will be >90m, 90m source data is sufficient
    - If visible pixels will be <90m, 30m source data provides better detail
    
    Args:
        bounds: (west, south, east, north) in degrees
        target_pixels: Target output dimension (e.g., 2048)
    
    Returns:
        dict with keys:
        - 'width_m_per_pixel': meters per pixel horizontally
        - 'height_m_per_pixel': meters per pixel vertically
        - 'avg_m_per_pixel': average meters per pixel (recommended for decision making)
        - 'output_width_px': calculated output width in pixels
        - 'output_height_px': calculated output height in pixels
        - 'real_world_width_km': width in kilometers
        - 'real_world_height_km': height in kilometers
    """
    west, south, east, north = bounds
    width_deg = east - west
    height_deg = north - south
    
    # Calculate real-world dimensions in meters
    import math
    center_lat = (north + south) / 2.0
    meters_per_deg_lat = 111_320  # constant
    meters_per_deg_lon = 111_320 * math.cos(math.radians(center_lat))
    
    width_m = width_deg * meters_per_deg_lon
    height_m = height_deg * meters_per_deg_lat
    
    # Calculate output pixels preserving aspect ratio (same logic as downsampling code)
    aspect = width_deg / height_deg if height_deg > 0 else 1.0
    if width_deg >= height_deg:
        output_width = target_pixels
        output_height = max(1, int(round(target_pixels / aspect)))
    else:
        output_height = target_pixels
        output_width = max(1, int(round(target_pixels * aspect)))
    
    # Calculate meters per pixel in final output
    m_per_pixel_x = width_m / output_width
    m_per_pixel_y = height_m / output_height
    avg_m_per_pixel = (m_per_pixel_x + m_per_pixel_y) / 2.0
    
    return {
        'width_m_per_pixel': m_per_pixel_x,
        'height_m_per_pixel': m_per_pixel_y,
        'avg_m_per_pixel': avg_m_per_pixel,
        'output_width_px': output_width,
        'output_height_px': output_height,
        'real_world_width_km': width_m / 1000.0,
        'real_world_height_km': height_m / 1000.0
    }