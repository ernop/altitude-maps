"""
Source coordinator - tries sources in order until data is obtained.

This is the entry point for tile downloads. It:
1. Gets ordered list of sources from registry
2. Tries each source in order
3. Stops on first success
4. Reports which source succeeded
"""

from pathlib import Path
from typing import Tuple, Optional
from src.downloaders.source_registry import (
    get_sources_for_download,
    SourceCapability
)


def download_tile_with_sources(
    tile_bounds: Tuple[float, float, float, float],
    resolution_m: int,
    output_path: Path,
    region_bounds: Tuple[float, float, float, float],
    verbose: bool = True
) -> Optional[str]:
    """
    Try downloading a tile from available sources in priority order.
    
    Args:
        tile_bounds: (west, south, east, north) for this specific tile
        resolution_m: Required resolution in meters
        output_path: Where to save the tile (with standard naming)
        region_bounds: (west, south, east, north) for entire region (for source selection)
        verbose: Whether to print progress
        
    Returns:
        source_id of successful source, or None if all failed
    """
    # Get ordered list of sources to try
    sources = get_sources_for_download(resolution_m, region_bounds)
    
    if not sources:
        if verbose:
            print(f"    ERROR: No sources available for {resolution_m}m at {tile_bounds}")
        return None
    
    # Try each source in order
    for source in sources:
        if verbose:
            print(f"    → Trying {source.name}...", end=" ", flush=True)
        
        try:
            success = _download_from_source(tile_bounds, source, output_path)
            if success:
                if verbose:
                    print("✓")
                return source.source_id
            else:
                if verbose:
                    print("✗")
        except Exception as e:
            if verbose:
                print(f"✗ ({type(e).__name__})")
    
    # All sources failed
    if verbose:
        print(f"    ERROR: All sources failed for tile {tile_bounds}")
    return None


def _download_from_source(
    tile_bounds: Tuple[float, float, float, float],
    source: SourceCapability,
    output_path: Path
) -> bool:
    """
    Download tile from a specific source.
    
    Routes to appropriate downloader based on source_id.
    """
    # Create source-specific tile directory
    source_tile_dir = Path(f"data/raw/{source.tile_dir}/tiles")
    source_tile_dir.mkdir(parents=True, exist_ok=True)
    
    # Create source-specific output path
    from src.tile_geometry import tile_filename_from_bounds
    resolution_str = f"{source.resolution_m}m"
    tile_filename = tile_filename_from_bounds(tile_bounds, resolution_str)
    source_output_path = source_tile_dir / tile_filename
    
    # Skip if already exists
    if source_output_path.exists():
        # Copy to requested output location if different
        if source_output_path != output_path:
            import shutil
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_output_path, output_path)
        return True
    
    # Route to appropriate downloader
    if source.source_id == 'usgs_3dep':
        from src.downloaders.usgs_3dep_10m import download_single_tile_10m
        return download_single_tile_10m(tile_bounds, source_output_path)
    
    elif source.source_id.startswith('opentopo_srtm'):
        from src.downloaders.opentopography import download_srtm
        from load_settings import get_api_key
        api_key = get_api_key('opentopography') if source.requires_auth else None
        # OpenTopography SRTM uses SRTMGL1 for 30m, SRTMGL3 for 90m
        result = download_srtm(tile_bounds, source_output_path, api_key=api_key)
        return result is not None
    
    elif source.source_id.startswith('opentopo_copernicus'):
        from src.downloaders.opentopography import download_copernicus
        from load_settings import get_api_key
        api_key = get_api_key('opentopography') if source.requires_auth else None
        resolution_str = '30m' if source.resolution_m == 30 else '90m'
        result = download_copernicus(tile_bounds, source_output_path, resolution=resolution_str, api_key=api_key)
        return result is not None
    
    elif source.source_id.startswith('copernicus_s3'):
        from src.downloaders.copernicus_s3 import download_copernicus_s3_tile
        return download_copernicus_s3_tile(tile_bounds, source.resolution_m, source_output_path)
    
    elif source.source_id == 'aw3d30':
        from src.downloaders.aw3d30 import download_aw3d30_tile
        from load_settings import get_api_key
        api_key = get_api_key('opentopography') if source.requires_auth else None
        return download_aw3d30_tile(tile_bounds, source_output_path, api_key=api_key)
    
    elif source.source_id.startswith('gmted2010'):
        from src.downloaders.gmted2010 import download_gmted2010_tile
        return download_gmted2010_tile(tile_bounds, source.resolution_m, source_output_path)
    
    elif source.source_id == 'globe_1km':
        from src.downloaders.globe import download_globe_tile
        return download_globe_tile(tile_bounds, source_output_path)
    
    else:
        print(f"    ERROR: Unknown source_id: {source.source_id}")
        return False


def download_tiles_for_region(
    region_id: str,
    region_bounds: Tuple[float, float, float, float],
    resolution_m: int,
    tiles_dir: Path
) -> list[Path]:
    """
    Download all tiles needed for a region, trying sources in priority order.
    
    Args:
        region_id: Region identifier (for logging)
        region_bounds: (west, south, east, north)
        resolution_m: Required resolution in meters
        tiles_dir: Directory to store final tiles
        
    Returns:
        List of successfully downloaded tile paths
    """
    from src.tile_geometry import calculate_1degree_tiles, tile_filename_from_bounds
    
    # Calculate required tiles
    tiles = calculate_1degree_tiles(region_bounds)
    
    # Get available sources
    sources = get_sources_for_download(resolution_m, region_bounds)
    
    if not sources:
        print(f"ERROR: No sources available for {resolution_m}m at {region_bounds}")
        return []
    
    print(f"\nDownloading {len(tiles)} tiles at {resolution_m}m resolution")
    print(f"Available sources (will try in order):")
    for idx, source in enumerate(sources, 1):
        auth_str = " (requires API key)" if source.requires_auth else ""
        print(f"  {idx}. {source.name}{auth_str}")
    
    # Track which sources were used
    source_usage = {}
    downloaded_paths = []
    tiles_dir.mkdir(parents=True, exist_ok=True)
    
    for idx, tile_bounds in enumerate(tiles, 1):
        resolution_str = f"{resolution_m}m"
        tile_filename = tile_filename_from_bounds(tile_bounds, resolution_str)
        tile_path = tiles_dir / tile_filename
        
        # Skip if already cached in final location
        if tile_path.exists():
            print(f"  [{idx}/{len(tiles)}] Cached: {tile_filename}")
            downloaded_paths.append(tile_path)
            continue
        
        print(f"  [{idx}/{len(tiles)}] {tile_filename}")
        
        # Try sources in order
        source_id = download_tile_with_sources(
            tile_bounds,
            resolution_m,
            tile_path,
            region_bounds,
            verbose=True
        )
        
        if source_id:
            downloaded_paths.append(tile_path)
            source_usage[source_id] = source_usage.get(source_id, 0) + 1
        else:
            print(f"    WARNING: Failed to download tile from any source")
    
    # Summary
    print(f"\nDownload complete: {len(downloaded_paths)}/{len(tiles)} tiles")
    if source_usage:
        print(f"Sources used:")
        for source_id, count in source_usage.items():
            source = next((s for s in sources if s.source_id == source_id), None)
            source_name = source.name if source else source_id
            print(f"  - {source_name}: {count} tiles")
    
    return downloaded_paths

