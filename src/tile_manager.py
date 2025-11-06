"""
Tile-based download orchestration.

Handles downloading and merging 1-degree tiles for all regions.
Unified system: ALL resolutions use 1x1 degree tiles for maximum reuse.

Download strategy:
- 90m: Fetches 2x2 degree chunks, splits into four 1x1 tiles (reduces API calls by 4x)
- 30m: Fetches 1x1 degree tiles (current behavior)
- 10m: Fetches 1x1 degree tiles (current behavior)
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
from src.downloaders.opentopography import download_srtm, OpenTopographyRateLimitError
from src.downloaders.srtm_90m import download_single_tile_90m, download_chunk_90m
from src.downloaders.usgs_3dep_10m import download_single_tile_10m


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
    
    Args:
        region_id: Region identifier (for logging)
        bounds: (west, south, east, north) in degrees
        output_path: Path for merged output file (defaults to data/merged/{source}/{region_id}_merged.tif)
        source: Data source ('srtm_30m', 'srtm_90m', 'usa_3dep', etc.)
        api_key: OpenTopography API key (not needed for usa_3dep)
        
    Returns:
        True if successful
    """
    from src.pipeline import merge_tiles
    
    # Default output path to data/merged/ directory
    if output_path is None:
        resolution = '30m' if '30m' in source else '90m' if '90m' in source else '10m'
        filename = merged_filename_from_region(region_id, bounds, resolution) + '.tif'
        output_path = Path(f"data/merged/{source}/{filename}")
    
    # Determine resolution from source
    resolution = '30m' if '30m' in source else '90m' if '90m' in source else '10m'
    resolution_m = int(resolution.replace('m', ''))
    
    # Calculate 1-degree tiles (canonical storage grid)
    tiles = calculate_1degree_tiles(bounds)
    
    # Get download strategy for this resolution
    chunk_degrees = get_chunk_size(resolution_m)
    
    # Group tiles into download chunks
    chunks = group_tiles_into_chunks(tiles, chunk_degrees)
    
    print(f"Calculated {len(tiles)} tiles for {region_id}", flush=True)
    if chunk_degrees > 1:
        print(f"Using {chunk_degrees}x{chunk_degrees} degree chunks ({len(chunks)} API requests instead of {len(tiles)})", flush=True)
    print(f"Bounds: {bounds}", flush=True)
    print(f"Output: {output_path}", flush=True)
    
    # Download chunks and extract tiles
    tiles_dir = Path(f"data/raw/{source}/tiles")
    tiles_dir.mkdir(parents=True, exist_ok=True)
    
    tile_paths = []
    tiles_processed = 0
    
    try:
        for chunk_idx, (chunk_bounds, chunk_tiles) in enumerate(chunks, 1):
            # Check if all tiles in this chunk already exist
            all_cached = all(
                (tiles_dir / tile_filename_from_bounds(tile_bounds, resolution)).exists()
                for tile_bounds in chunk_tiles
            )
            
            if all_cached:
                # All tiles cached - skip download
                for tile_bounds in chunk_tiles:
                    tiles_processed += 1
                    tile_filename = tile_filename_from_bounds(tile_bounds, resolution)
                    tile_path = tiles_dir / tile_filename
                    print(f"  [{tiles_processed}/{len(tiles)}] Using cached: {tile_filename}", flush=True)
                    tile_paths.append(tile_path)
                continue
            
            # Download chunk
            west, south, east, north = chunk_bounds
            chunk_size = (east - west, north - south)
            print(f"  Chunk [{chunk_idx}/{len(chunks)}]: {chunk_size[0]:.0f}x{chunk_size[1]:.0f} deg -> {len(chunk_tiles)} tiles", flush=True)
            
            # Create temp file for chunk download
            with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp:
                temp_chunk_path = Path(tmp.name)
            
            try:
                # Download chunk
                if resolution == '90m':
                    # 90m data - download chunk
                    dataset = 'COP90' if 'cop' in source.lower() else 'SRTMGL3'
                    success = download_chunk_90m(
                        chunk_bounds,
                        temp_chunk_path,
                        api_key,
                        dataset=dataset
                    )
                elif resolution == '30m':
                    # 30m data - if chunk_size is 1x1, download directly, otherwise use generic downloader
                    if chunk_degrees == 1:
                        tile_bounds = chunk_tiles[0]
                        tile_filename = tile_filename_from_bounds(tile_bounds, resolution)
                        tile_path = tiles_dir / tile_filename
                        success = download_srtm(
                            f"tile_{tile_filename[:-4]}",
                            tile_bounds,
                            tile_path,
                            api_key
                        )
                        if success:
                            tiles_processed += 1
                            print(f"  [{tiles_processed}/{len(tiles)}] Downloaded: {tile_filename}", flush=True)
                            tile_paths.append(tile_path)
                        continue
                    else:
                        # Multi-degree chunk for 30m (shouldn't happen with current config, but handle it)
                        success = download_srtm(
                            f"chunk_{chunk_idx}",
                            chunk_bounds,
                            temp_chunk_path,
                            api_key
                        )
                else:  # 10m
                    # 10m data - only download 1x1 tiles
                    if chunk_degrees == 1:
                        tile_bounds = chunk_tiles[0]
                        tile_filename = tile_filename_from_bounds(tile_bounds, resolution)
                        tile_path = tiles_dir / tile_filename
                        success = download_single_tile_10m(
                            tile_bounds,
                            tile_path,
                            dataset='USA_3DEP'
                        )
                        if success:
                            tiles_processed += 1
                            print(f"  [{tiles_processed}/{len(tiles)}] Downloaded: {tile_filename}", flush=True)
                            tile_paths.append(tile_path)
                        continue
                    else:
                        print(f"  ERROR: 10m data doesn't support multi-degree chunks", flush=True)
                        continue
                
                if not success:
                    print(f"  ERROR: Failed to download chunk {chunk_idx}", flush=True)
                    temp_chunk_path.unlink(missing_ok=True)
                    continue
                
                # Split chunk into tiles
                print(f"    Splitting chunk into {len(chunk_tiles)} tiles...", flush=True)
                extracted_tiles = split_chunk_into_tiles(
                    temp_chunk_path,
                    chunk_bounds,
                    chunk_tiles,
                    tiles_dir,
                    resolution
                )
                
                for tile_path in extracted_tiles:
                    tiles_processed += 1
                    print(f"  [{tiles_processed}/{len(tiles)}] Extracted: {tile_path.name}", flush=True)
                    tile_paths.append(tile_path)
                
            finally:
                # Clean up temp file
                temp_chunk_path.unlink(missing_ok=True)
            
    except OpenTopographyRateLimitError:
        # Re-raise to stop all downloads
        raise
    
    if not tile_paths:
        print(f"ERROR: No tiles downloaded successfully", flush=True)
        return False
    
    # Merge tiles
    print(f"\nMerging {len(tile_paths)} tiles...", flush=True)
    return merge_tiles(tile_paths, output_path)

