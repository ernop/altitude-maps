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
        tile_bounds: (west, south, east, north) for this specific tile (1×1 degree standard)
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
    errors = []  # Track all errors for detailed reporting
    
    for source in sources:
        if verbose:
            print(f"    -> Trying {source.name}...", end=" ", flush=True)
        
        try:
            success, error_msg = _download_from_source(tile_bounds, source, output_path)
            if success:
                if verbose:
                    print("[OK]")
                return source.source_id
            else:
                if verbose:
                    print("[FAIL]")
                errors.append((source.name, error_msg))
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            if verbose:
                print(f"[FAIL] ({type(e).__name__})")
            errors.append((source.name, error_msg))
    
    # All sources failed - print detailed errors
    if verbose:
        print(f"\n    {'='*60}")
        print(f"    ALL SOURCES FAILED FOR TILE")
        print(f"    Tile: {tile_bounds} (1×1 degree standard tile)")
        print(f"    Errors by source:")
        for source_name, error_msg in errors:
            print(f"      - {source_name}: {error_msg}")
        print(f"    {'='*60}")
    
    return None


def _download_from_source(
    tile_bounds: Tuple[float, float, float, float],
    source: SourceCapability,
    output_path: Path
) -> Tuple[bool, str]:
    """
    Download tile from a specific source.
    
    Routes to appropriate downloader based on source_id.
    
    Returns:
        (success: bool, error_message: str)
    """
    import traceback
    
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
        return True, "Success (cached)"
    
    try:
        # Route to appropriate downloader
        if source.source_id == 'usgs_3dep':
            from src.downloaders.usgs_3dep_10m import download_single_tile_10m
            success = download_single_tile_10m(tile_bounds, source_output_path)
            return success, "Success" if success else "Download failed"
        
        elif source.source_id.startswith('opentopo_srtm'):
            # OpenTopography SRTM download
            from src.downloaders.srtm_90m import download_single_tile_90m
            from load_settings import get_api_key
            try:
                api_key = get_api_key()  # No argument - returns opentopography key
            except Exception as e:
                return False, f"No API key configured: {e}"
            dataset = 'SRTMGL3' if source.resolution_m == 90 else 'SRTMGL1'
            success = download_single_tile_90m(tile_bounds, source_output_path, api_key, dataset=dataset)
            return success, "Success" if success else "Download failed (check logs above)"
        
        elif source.source_id.startswith('opentopo_copernicus'):
            # OpenTopography Copernicus download
            from src.downloaders.srtm_90m import download_single_tile_90m
            from load_settings import get_api_key
            try:
                api_key = get_api_key()  # No argument - returns opentopography key
            except Exception as e:
                return False, f"No API key configured: {e}"
            dataset = 'COP90' if source.resolution_m == 90 else 'COP30'
            success = download_single_tile_90m(tile_bounds, source_output_path, api_key, dataset=dataset)
            return success, "Success" if success else "Download failed (check logs above)"
        
        elif source.source_id.startswith('copernicus_s3'):
            from src.downloaders.copernicus_s3 import download_copernicus_s3_tile
            success = download_copernicus_s3_tile(tile_bounds, source.resolution_m, source_output_path)
            return success, "Success" if success else "Tile not available (404 or download error)"
        
        elif source.source_id == 'aw3d30':
            from src.downloaders.aw3d30 import download_aw3d30_tile
            from load_settings import get_api_key
            try:
                api_key = get_api_key()  # No argument - returns opentopography key
            except Exception as e:
                return False, f"No API key configured: {e}"
            success = download_aw3d30_tile(tile_bounds, source_output_path, api_key=api_key)
            return success, "Success" if success else "Download failed (check logs above)"
        
        elif source.source_id.startswith('gmted2010'):
            from src.downloaders.gmted2010 import download_gmted2010_tile
            success = download_gmted2010_tile(tile_bounds, source.resolution_m, source_output_path)
            return success, "Success" if success else "Not implemented yet"
        
        elif source.source_id == 'globe_1km':
            from src.downloaders.globe import download_globe_tile
            success = download_globe_tile(tile_bounds, source_output_path)
            return success, "Success" if success else "Not implemented yet"
        
        else:
            return False, f"Unknown source_id: {source.source_id}"
            
    except Exception as e:
        # Full traceback for debugging
        error_msg = f"{type(e).__name__}: {e}\n"
        error_msg += "Traceback:\n" + traceback.format_exc()
        return False, error_msg


def download_tiles_for_region(
    region_id: str,
    region_bounds: Tuple[float, float, float, float],
    resolution_m: int,
    tiles_dir: Path
) -> list[Path]:
    """
    Download all tiles needed for a region, trying sources in priority order.
    
    Uses standard 1×1 degree tiles for maximum reuse across regions.
    
    Args:
        region_id: Region identifier (for logging)
        region_bounds: (west, south, east, north)
        resolution_m: Required resolution in meters
        tiles_dir: Directory to store final tiles
        
    Returns:
        List of successfully downloaded tile paths
    """
    from src.tile_geometry import calculate_1degree_tiles, tile_filename_from_bounds
    
    # Calculate required tiles (1×1 degree standard)
    tiles = calculate_1degree_tiles(region_bounds)
    
    # Get available sources
    sources = get_sources_for_download(resolution_m, region_bounds)
    
    if not sources:
        print(f"\nERROR: No sources available for {resolution_m}m at {region_bounds}")
        return []
    
    # Check if API keys are configured for sources that need them
    print(f"\n{'='*60}")
    print(f"CHECKING AUTHENTICATION")
    print(f"{'='*60}")
    
    needs_api_key = any(s.requires_auth for s in sources)
    if needs_api_key:
        print(f"Some sources require authentication. Checking API keys...")
        from load_settings import load_settings
        try:
            settings = load_settings()
            has_opentopo_key = 'opentopography' in settings and 'api_key' in settings['opentopography']
            
            if has_opentopo_key:
                print(f"  [OK] OpenTopography API key found")
            else:
                print(f"\n  [WARNING] No OpenTopography API key configured!")
                print(f"  Sources requiring API key will be skipped:")
                for s in sources:
                    if s.requires_auth and s.auth_key_name == 'opentopography.api_key':
                        print(f"    - {s.name}")
                print(f"\n  To configure:")
                print(f"    1. Get free API key at: https://portal.opentopography.org/")
                print(f"    2. Add to settings.json:")
                print(f'       {{"opentopography": {{"api_key": "YOUR_KEY_HERE"}}}}')
                print(f"\n  Continuing with sources that don't require API key...")
        except Exception as e:
            print(f"  [WARNING] Could not check API keys: {e}")
    else:
        print(f"  [OK] No authentication required for available sources")
    
    print(f"{'='*60}\n")
    
    print(f"Downloading {len(tiles)} tiles at {resolution_m}m resolution")
    print(f"Tile size: 1×1 degree (standard reusable grid)")
    print(f"Storage: data/raw/{{source}}/tiles/ (content-based reuse)")
    print(f"\nAvailable sources (will try in order):")
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
            # CRITICAL FAILURE: No source could download this tile
            print(f"\n{'='*60}")
            print(f"ERROR: All sources failed for tile {tile_filename}")
            print(f"Bounds: {tile_bounds}")
            print(f"This is a critical error - cannot continue without this tile.")
            print(f"{'='*60}\n")
            
            # Return what we have so far (will fail in merge stage)
            return downloaded_paths
    
    # Summary
    print(f"\nDownload complete: {len(downloaded_paths)}/{len(tiles)} tiles")
    if source_usage:
        print(f"Sources used:")
        for source_id, count in source_usage.items():
            source = next((s for s in sources if s.source_id == source_id), None)
            source_name = source.name if source else source_id
            print(f"  - {source_name}: {count} tiles")
    
    return downloaded_paths

