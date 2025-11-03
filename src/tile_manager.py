"""
Tile-based download orchestration.

Handles downloading and merging 1-degree tiles for large regions.
"""

from pathlib import Path
from typing import Tuple, List

from src.tile_geometry import calculate_1degree_tiles, tile_filename_from_bounds, merged_filename_from_region
from src.downloaders.opentopography import download_srtm, OpenTopographyRateLimitError


def download_and_merge_tiles(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    output_path: Path = None,
    source: str = 'srtm_30m',
    api_key: str = None
) -> bool:
    """
    Download 1-degree tiles and merge them for a region.
    
    This is the standard approach for regions > 4 degrees in any direction.
    Uses automatic 1-degree grid tiling - no manual configuration needed.
    
    Args:
        region_id: Region identifier (for logging)
        bounds: (west, south, east, north) in degrees
        output_path: Path for merged output file (defaults to data/merged/{source}/{region_id}_merged.tif)
        source: Data source ('srtm_30m', 'cop30', etc.)
        api_key: OpenTopography API key
        
    Returns:
        True if successful
    """
    from src.pipeline import merge_tiles
    
    # Default output path to data/merged/ directory
    if output_path is None:
        resolution = '30m' if '30m' in source else '90m' if '90m' in source else '10m'
        filename = merged_filename_from_region(region_id, bounds, resolution) + '.tif'
        output_path = Path(f"data/merged/{source}/{filename}")
    
    tiles = calculate_1degree_tiles(bounds)
    
    print(f"Calculated {len(tiles)} tiles for {region_id}", flush=True)
    print(f"Bounds: {bounds}", flush=True)
    print(f"Output: {output_path}", flush=True)
    
    # Determine resolution from source
    resolution = '30m' if '30m' in source else '90m' if '90m' in source else '10m'
    
    # Download each tile
    tiles_dir = Path(f"data/raw/{source}/tiles")
    tiles_dir.mkdir(parents=True, exist_ok=True)
    
    tile_paths = []
    try:
        for i, tile_bounds in enumerate(tiles, 1):
            tile_filename = tile_filename_from_bounds(tile_bounds, resolution)
            tile_path = tiles_dir / tile_filename
            
            # Download if not cached
            if not tile_path.exists():
                print(f"  [{i}/{len(tiles)}] Downloading: {tile_filename}", flush=True)
                success = download_srtm(
                    f"tile_{tile_filename[:-4]}",
                    tile_bounds,
                    tile_path,
                    api_key
                )
                if not success:
                    print(f"  [{i}/{len(tiles)}] Failed to download: {tile_filename}", flush=True)
                    continue
            else:
                print(f"  [{i}/{len(tiles)}] Using cached: {tile_filename}", flush=True)
            
            tile_paths.append(tile_path)
    except OpenTopographyRateLimitError:
        # Re-raise to stop all downloads
        raise
    
    if not tile_paths:
        print(f"ERROR: No tiles downloaded successfully", flush=True)
        return False
    
    # Merge tiles
    print(f"\nMerging {len(tile_paths)} tiles...", flush=True)
    return merge_tiles(tile_paths, output_path)

