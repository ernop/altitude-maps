"""
Tile-based download orchestration.

Handles downloading and merging 1-degree tiles for all regions.
Unified system: ALL resolutions use 1x1 degree tiles for maximum reuse.

NEW: Uses source coordinator to try multiple data sources automatically.
Sources are tried in priority order until data is obtained.
"""

from pathlib import Path
from typing import Tuple, List
import tempfile

from src.tile_geometry import (
    calculate_1degree_tiles, 
    tile_filename_from_bounds, 
    merged_filename_from_region,
    group_tiles_into_chunks
)
from src.download_config import get_chunk_size


def split_chunk_into_tiles(
    chunk_path: Path,
    chunk_bounds: Tuple[float, float, float, float],
    tile_list: List[Tuple[float, float, float, float]],
    tiles_dir: Path,
    resolution: str
) -> List[Path]:
    """
    Split a multi-degree chunk into 1-degree tiles.
    
    Args:
        chunk_path: Path to downloaded multi-degree GeoTIFF
        chunk_bounds: Bounds of the chunk (west, south, east, north)
        tile_list: List of 1-degree tile bounds to extract
        tiles_dir: Directory to save individual tiles
        resolution: Resolution string (e.g., '90m')
        
    Returns:
        List of paths to successfully extracted tiles
    """
    import rasterio
    from rasterio.mask import mask as rasterio_mask
    from shapely.geometry import box
    
    tile_paths = []
    
    try:
        with rasterio.open(chunk_path) as src:
            for tile_bounds in tile_list:
                tile_filename = tile_filename_from_bounds(tile_bounds, resolution)
                tile_path = tiles_dir / tile_filename
                
                # Skip if tile already exists
                if tile_path.exists():
                    tile_paths.append(tile_path)
                    continue
                
                # Create bounding box for this tile
                west, south, east, north = tile_bounds
                tile_geom = box(west, south, east, north)
                
                # Clip chunk to tile bounds
                try:
                    out_image, out_transform = rasterio_mask(
                        src,
                        [tile_geom],
                        crop=True,
                        filled=False,
                        nodata=src.nodata
                    )
                    
                    # Save tile
                    out_meta = src.meta.copy()
                    out_meta.update({
                        'height': out_image.shape[1],
                        'width': out_image.shape[2],
                        'transform': out_transform
                    })
                    
                    tile_path.parent.mkdir(parents=True, exist_ok=True)
                    with rasterio.open(tile_path, 'w', **out_meta) as dst:
                        dst.write(out_image)
                    
                    tile_paths.append(tile_path)
                    
                except Exception as e:
                    print(f"    WARNING: Failed to extract tile {tile_filename}: {e}")
                    continue
    
    except Exception as e:
        print(f"  ERROR: Failed to split chunk: {e}")
        return []
    
    return tile_paths


def download_and_merge_tiles(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    output_path: Path = None,
    source: str = 'srtm_30m',
    api_key: str = None
) -> bool:
    """
    Download 1-degree tiles and merge them for any region.
    
    UNIFIED ARCHITECTURE (see tech/GRID_ALIGNMENT_STRATEGY.md):
    - Used for ALL regions regardless of size
    - Automatic 1-degree grid tiling
    - Maximum tile reuse across adjacent regions
    - Consistent folder structure for all resolutions
    - NEW: Tries multiple sources automatically via source coordinator
    
    Args:
        region_id: Region identifier (for logging)
        bounds: (west, south, east, north) in degrees
        output_path: Path for merged output file (defaults to data/merged/{source}/{region_id}_merged.tif)
        source: Data source hint ('srtm_30m', 'srtm_90m', 'usa_3dep', etc.) - used for resolution detection
        api_key: OpenTopography API key (deprecated - loaded from settings.json)
        
    Returns:
        True if successful
    """
    from src.pipeline import merge_tiles
    from src.downloaders.source_coordinator import download_tiles_for_region
    
    # Determine resolution from source hint
    resolution = '30m' if '30m' in source else '90m' if '90m' in source else '10m'
    resolution_m = int(resolution.replace('m', ''))
    
    # Default output path to data/merged/ directory
    if output_path is None:
        filename = merged_filename_from_region(region_id, bounds, resolution) + '.tif'
        output_path = Path(f"data/merged/{source}/{filename}")
    
    print(f"\n{'='*60}")
    print(f"Region: {region_id}")
    print(f"Bounds: {bounds}")
    print(f"Required resolution: {resolution_m}m")
    print(f"Output: {output_path}")
    print(f"{'='*60}")
    
    # Use source coordinator to download all tiles
    # It will automatically try sources in priority order
    tiles_dir = Path(f"data/raw/{source}/tiles")
    tiles_dir.mkdir(parents=True, exist_ok=True)
    
    tile_paths = download_tiles_for_region(
        region_id,
        bounds,
        resolution_m,
        tiles_dir
    )
    
    if not tile_paths:
        print(f"\nERROR: No tiles downloaded successfully")
        return False
    
    # Merge tiles
    print(f"\nMerging {len(tile_paths)} tiles...")
    success = merge_tiles(tile_paths, output_path)
    
    if success:
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"✓ Merged file: {output_path} ({file_size_mb:.1f} MB)")
    
    return success

