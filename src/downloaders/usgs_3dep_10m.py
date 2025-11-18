"""
USGS 3DEP 10m elevation data downloader with tile-based architecture.

Provides efficient, tile-by-tile downloads of high-resolution 10m elevation data
for USA regions. Follows the unified 1-degree grid system for maximum tile reuse.
"""

from pathlib import Path
from typing import Tuple, Optional

from src.tile_geometry import calculate_1degree_tiles, tile_filename_from_bounds


def download_single_tile_10m(
    tile_bounds: Tuple[float, float, float, float],
    output_path: Path,
    dataset: str = 'USA_3DEP',
    target_pixels: int = None
) -> bool:
    """
    Download a single 1-degree tile of 10m USGS 3DEP data.
    
    Args:
        tile_bounds: (west, south, east, north) in degrees for a 1-degree tile
        output_path: Path to save the downloaded tile
        dataset: Dataset identifier (default 'USA_3DEP')
        target_pixels: Target output dimension (default: from src.config.DEFAULT_TARGET_PIXELS)
        
    Returns:
        True if successful, False otherwise
    """
    from src.config import DEFAULT_TARGET_PIXELS
    if target_pixels is None:
        target_pixels = DEFAULT_TARGET_PIXELS
    
    from src.usa_elevation_data import USGSElevationDownloader
    
    west, south, east, north = tile_bounds
    
    # Validate tile is 1-degree
    width = east - west
    height = north - south
    if abs(width - 1.0) > 0.01 or abs(height - 1.0) > 0.01:
        print(f"  WARNING: Tile bounds not 1-degree: {width}deg x {height}deg")
    
    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Download via USGS National Map API
    downloader = USGSElevationDownloader(data_dir=str(output_path.parent))
    
    try:
        print(f"  Downloading tile: {output_path.name}", flush=True)
        result = downloader.download_via_national_map_api(
            bbox=tile_bounds,
            output_file=output_path.name,
            target_pixels=target_pixels
        )
        
        if result is None:
            print(f"  ERROR: Failed to download tile {output_path.name}")
            # Clean up failed download
            if output_path.exists():
                output_path.unlink()
            return False
        
        # Validate the downloaded file
        if not output_path.exists():
            print(f"  ERROR: File not created: {output_path}")
            return False
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        
        # Log file size for monitoring (10m tiles should be larger than 30m tiles)
        # At 40degN, 1-degree tile at 10m should be ~150-200 MB
        # This is informational only - do not delete files based on size
        if file_size_mb < 1.0:
            print(f"  WARNING: Suspiciously small file: {file_size_mb:.2f} MB")
            print(f"  File may be empty or corrupted - please review manually")
            # Do NOT delete - let user decide
        
        print(f"  Downloaded: {output_path.name} ({file_size_mb:.2f} MB)")
        return True
        
    except Exception as e:
        print(f"  ERROR downloading tile: {e}")
        if output_path.exists():
            output_path.unlink()
        return False


def download_usgs_3dep_10m_tiles(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    output_path: Path,
    dataset: Optional[str] = None,
    target_pixels: int = None
) -> bool:
    """
    Download 10m USGS 3DEP data, using exact bounds for small regions or 1-degree tiles for large regions.
    
    For small regions (< 1 degree), downloads exact bounding box directly (more efficient).
    For large regions (>= 1 degree), uses 1-degree tile system and merges.
    
    Args:
        region_id: Region identifier (for logging)
        bounds: (west, south, east, north) in degrees
        output_path: Path for merged output file
        dataset: Dataset identifier (default None = 'USA_3DEP')
        target_pixels: Target output dimension (default: from src.config.DEFAULT_TARGET_PIXELS) - used to calculate download resolution
        
    Returns:
        True if successful, False otherwise
    """
    from src.config import DEFAULT_TARGET_PIXELS
    if target_pixels is None:
        target_pixels = DEFAULT_TARGET_PIXELS
    
    from src.pipeline import merge_tiles
    from src.usa_elevation_data import USGSElevationDownloader
    
    if dataset is None:
        dataset = 'USA_3DEP'
    
    west, south, east, north = bounds
    width_deg = east - west
    height_deg = north - south
    
    # For small regions (< 1 degree), download exact bounds directly
    # This avoids downloading 100x more data than needed (e.g., SLO: 0.09° × 0.08° vs 1° × 1°)
    if width_deg < 1.0 and height_deg < 1.0:
        print(f"  Small region ({width_deg:.3f}deg × {height_deg:.3f}deg) - downloading exact bounds", flush=True)
        print(f"  Bounds: {bounds}", flush=True)
        print(f"  Output: {output_path}", flush=True)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Download directly using exact bounds
        downloader = USGSElevationDownloader(data_dir=str(output_path.parent))
        result = downloader.download_via_national_map_api(
            bbox=bounds,
            output_file=output_path.name,
            target_pixels=target_pixels
        )
        
        if result is None:
            print(f"  ERROR: Failed to download region {region_id}")
            return False
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  Downloaded: {output_path.name} ({file_size_mb:.2f} MB)")
        return True
    
    # Large region - use 1-degree tile system
    print(f"  Large region ({width_deg:.2f}deg × {height_deg:.2f}deg) - using 1-degree tile system", flush=True)
    
    # Calculate 1-degree tiles needed
    tiles = calculate_1degree_tiles(bounds)
    
    print(f"  Downloading {len(tiles)} tiles for {region_id} (10m resolution)", flush=True)
    print(f"  Bounds: {bounds}", flush=True)
    print(f"  Output: {output_path}", flush=True)
    
    # Tiles stored in shared pool
    tiles_dir = Path("data/raw/usa_3dep/tiles")
    tiles_dir.mkdir(parents=True, exist_ok=True)
    
    tile_paths: list[Path] = []
    
    # Download each tile (or use existing)
    for i, tile_bounds in enumerate(tiles, 1):
        # Generate tile filename using unified naming convention
        tile_filename = tile_filename_from_bounds(tile_bounds, resolution='10m')
        tile_path = tiles_dir / tile_filename
        
        # Skip tile reuse - always download fresh region-specific data
        # (Tile directories remain for reference but are not reused)
        
        # Download the tile
        print(f"  [{i}/{len(tiles)}] Downloading: {tile_filename}")
        success = download_single_tile_10m(tile_bounds, tile_path, dataset, target_pixels=target_pixels)
        
        if not success:
            print(f"  ERROR: Failed to download tile {tile_filename}")
            return False
        
        tile_paths.append(tile_path)
    
    # Merge tiles into single output file
    print(f"\n  Merging {len(tile_paths)} tiles...", flush=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    success = merge_tiles(tile_paths, output_path)
    
    if success:
        merged_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  Merged file: {output_path.name} ({merged_size_mb:.2f} MB)")
        print(f"  Tile cache: {tiles_dir}")
    else:
        print(f"  ERROR: Failed to merge tiles")
    
    return success


def download_usgs_3dep_10m_single(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    output_path: Path
) -> bool:
    """
    Download 10m USGS 3DEP data as single file (for small regions < 4 degrees).
    
    DEPRECATED: This function exists for compatibility but should not be used.
    The unified tiling system handles all region sizes efficiently.
    
    Args:
        region_id: Region identifier
        bounds: (west, south, east, north) in degrees
        output_path: Path for output file
        
    Returns:
        True if successful, False otherwise
    """
    # Redirect to tiling system - unified approach handles all sizes
    return download_usgs_3dep_10m_tiles(region_id, bounds, output_path)

