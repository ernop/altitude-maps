"""
SRTM 90m elevation data downloader (OpenTopography).

90m is sufficient for large regions or distant viewing where higher resolution
would be wasteful. Uses the unified 1-degree tile system for all downloads.

Features:
- Automatic tiling for regions of any size
- Shared tile cache in data/raw/srtm_90m/tiles/
- Supports SRTMGL3 (60N-56S) and Copernicus DEM 90m (global)
- Rate limit coordination across all processes
"""

from pathlib import Path
from typing import Tuple, Optional
import requests
from tqdm import tqdm

from src.downloaders.rate_limit import check_rate_limit, record_rate_limit_hit, record_successful_request
from src.downloaders.opentopography import OpenTopographyRateLimitError
from src.tile_geometry import calculate_1degree_tiles, tile_filename_from_bounds
from src.pipeline import merge_tiles
from src.metadata import create_raw_metadata, save_metadata, get_metadata_path
from load_settings import get_api_key as get_opentopography_api_key


def download_chunk_90m(
    chunk_bounds: Tuple[float, float, float, float],
    output_path: Path,
    api_key: str,
    dataset: str = 'SRTMGL3'
) -> bool:
    """
    Download a multi-degree chunk of 90m elevation data.
    
    Used for downloading 2x2 or larger degree chunks to reduce API calls.
    The chunk is downloaded as a single file, then split into 1-degree tiles.
    
    Args:
        chunk_bounds: (west, south, east, north) in degrees (can be 1x1, 2x2, etc.)
        output_path: Path to save the downloaded chunk
        api_key: OpenTopography API key
        dataset: 'SRTMGL3' (SRTM 90m) or 'COP90' (Copernicus DEM 90m)
        
    Returns:
        True if successful, False otherwise
    """
    west, south, east, north = chunk_bounds
    width = east - west
    height = north - south
    
    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check shared rate limit state before attempting download
    ok, reason = check_rate_limit()
    if not ok:
        print(f"\n  Rate limit active: {reason}", flush=True)
        print(f"  Skipping download until rate limit clears", flush=True)
        return False
    
    url = "https://portal.opentopography.org/API/globaldem"
    params = {
        'demtype': dataset,
        'south': south,
        'north': north,
        'west': west,
        'east': east,
        'outputFormat': 'GTiff',
        'API_Key': api_key
    }
    
    try:
        response = requests.get(url, params=params, stream=True, timeout=300)
        
        # Check for 401 (Unauthorized) - rate limit or quota exceeded
        if response.status_code == 401:
            # Record rate limit hit in shared state file
            record_rate_limit_hit(response.status_code)
            
            print(f"\n  ERROR: OpenTopography returned 401 Unauthorized", flush=True)
            print(f"  This usually means rate limit or quota exceeded.", flush=True)
            print(f"  Rate limit recorded in shared state file.", flush=True)
            print(f"  All download processes will respect this limit.", flush=True)
            print(f"  STOPPING download to respect their limits.", flush=True)
            raise OpenTopographyRateLimitError("OpenTopography rate limit exceeded (401 Unauthorized)")
        
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(output_path, 'wb') as f:
            with tqdm(
                desc=f"{width:.0f}x{height:.0f}deg chunk",
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"    Downloaded chunk: {file_size_mb:.1f} MB")
        
        # Record successful request in shared state
        record_successful_request()
        
        return True
    
    except OpenTopographyRateLimitError:
        # Re-raise to stop all downloads
        raise
    
    except Exception as e:
        print(f"    ERROR: {e}")
        if output_path.exists():
            output_path.unlink()
        return False


def download_single_tile_90m(
    tile_bounds: Tuple[float, float, float, float],
    output_path: Path,
    api_key: str,
    dataset: str = 'SRTMGL3'
) -> bool:
    """
    Download a single 1-degree tile of 90m elevation data.
    
    Uses OpenTopography Global DEM API (SRTMGL3 or COP90).
    
    Args:
        tile_bounds: (west, south, east, north) in degrees for a 1-degree tile
        output_path: Path to save the downloaded tile
        api_key: OpenTopography API key
        dataset: 'SRTMGL3' (SRTM 90m) or 'COP90' (Copernicus DEM 90m)
        
    Returns:
        True if successful, False otherwise
    """
    west, south, east, north = tile_bounds
    
    # Validate tile is 1-degree
    width = east - west
    height = north - south
    if abs(width - 1.0) > 0.01 or abs(height - 1.0) > 0.01:
        print(f"  WARNING: Tile bounds not 1-degree: {width}deg x {height}deg")
    
    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check shared rate limit state before attempting download
    ok, reason = check_rate_limit()
    if not ok:
        print(f"\n  Rate limit active: {reason}", flush=True)
        print(f"  Skipping download until rate limit clears", flush=True)
        return False
    
    url = "https://portal.opentopography.org/API/globaldem"
    params = {
        'demtype': dataset,
        'south': south,
        'north': north,
        'west': west,
        'east': east,
        'outputFormat': 'GTiff',
        'API_Key': api_key
    }
    
    try:
        response = requests.get(url, params=params, stream=True, timeout=300)
        
        # Check for 401 (Unauthorized) - rate limit or quota exceeded
        if response.status_code == 401:
            # Record rate limit hit in shared state file
            record_rate_limit_hit(response.status_code)
            
            print(f"\n  ERROR: OpenTopography returned 401 Unauthorized", flush=True)
            print(f"  This usually means rate limit or quota exceeded.", flush=True)
            print(f"  Rate limit recorded in shared state file.", flush=True)
            print(f"  All download processes will respect this limit.", flush=True)
            print(f"  STOPPING download to respect their limits.", flush=True)
            raise OpenTopographyRateLimitError("OpenTopography rate limit exceeded (401 Unauthorized)")
        
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(output_path, 'wb') as f:
            with tqdm(
                desc=output_path.name[:40],
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"    Downloaded: {file_size_mb:.1f} MB")
        
        # Record successful request in shared state
        record_successful_request()
        
        # Save metadata
        metadata = create_raw_metadata(
            tif_path=output_path,
            region_id='tile',
            source='srtm_90m',
            download_url=url,
            download_params=params
        )
        save_metadata(metadata, get_metadata_path(output_path))
        
        return True
    
    except OpenTopographyRateLimitError:
        # Re-raise to stop all downloads
        raise
    
    except Exception as e:
        print(f"    ERROR: {e}")
        if output_path.exists():
            output_path.unlink()
        return False


def download_srtm_90m_tiles(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    output_path: Path,
    api_key: Optional[str] = None,
    dataset: Optional[str] = None
) -> bool:
    """
    Download SRTM 90m data for a region using tile-by-tile approach.
    
    This function:
    1. Splits the region into 1-degree tiles
    2. Downloads each tile (or reuses cached tiles)
    3. Merges tiles into a single output file
    
    Tiles are stored in data/raw/srtm_90m/tiles/ with content-based names
    (e.g., N40_W111_90m.tif) for reuse across regions.
    
    Args:
        region_id: Region identifier (for metadata and logging)
        bounds: (west, south, east, north) in degrees
        output_path: Where to save merged output
        api_key: OpenTopography API key (loads from settings.json if not provided)
        dataset: Override dataset ('SRTMGL3' or 'COP90'). If None, auto-selects based on latitude.
        
    Returns:
        True if successful, False otherwise
    """
    # Get API key
    if not api_key:
        try:
            api_key = get_opentopography_api_key()
        except SystemExit:
            print(f"  ERROR: OpenTopography API key required")
            print(f"  Get a free key at: https://portal.opentopography.org/")
            print(f"  Add to settings.json under 'opentopography.api_key'")
            return False
    
    # Auto-select dataset based on latitude if not specified
    if dataset is None:
        west, south, east, north = bounds
        if north > 60.0 or south < -56.0:
            dataset = 'COP90'
            dataset_name = 'Copernicus DEM 90m'
        else:
            dataset = 'SRTMGL3'
            dataset_name = 'SRTM 90m'
    else:
        dataset_name = 'Copernicus DEM 90m' if dataset == 'COP90' else 'SRTM 90m'
    
    west, south, east, north = bounds
    width = east - west
    height = north - south
    
    print(f"\n  Downloading {region_id} - {dataset_name}")
    print(f"  Region: {width:.1f}deg x {height:.1f}deg")
    print(f"  Bounds: ({west:.2f}, {south:.2f}) to ({east:.2f}, {north:.2f})")
    
    # Calculate tiles needed
    tiles = calculate_1degree_tiles(bounds)
    print(f"  Splitting into {len(tiles)} tiles (1-degree grid)")
    
    # Check rate limit BEFORE starting download loop
    # Bail out early instead of checking per-tile
    ok, reason = check_rate_limit()
    if not ok:
        print(f"\n  Rate limit active: {reason}", flush=True)
        print(f"  Skipping all downloads until rate limit clears", flush=True)
        print(f"  Use 'python check_rate_limit.py' to check status", flush=True)
        return False
    
    # Create tile directory
    tile_dir = Path('data/raw/srtm_90m/tiles')
    tile_dir.mkdir(parents=True, exist_ok=True)
    
    # Download each tile
    tile_paths = []
    cached_count = 0
    downloaded_count = 0
    failed_tiles = []
    
    for i, tile_bounds in enumerate(tiles, 1):
        tile_name = tile_filename_from_bounds(tile_bounds, resolution='90m')
        tile_path = tile_dir / tile_name
        
        if tile_path.exists():
            print(f"  [{i}/{len(tiles)}] Cached: {tile_name}")
            tile_paths.append(tile_path)
            cached_count += 1
            continue
        
        print(f"  [{i}/{len(tiles)}] Downloading: {tile_name}")
        success = download_single_tile_90m(tile_bounds, tile_path, api_key, dataset)
        
        if success:
            tile_paths.append(tile_path)
            downloaded_count += 1
            file_size_mb = tile_path.stat().st_size / (1024 * 1024)
            print(f"    Downloaded: {file_size_mb:.1f} MB")
        else:
            failed_tiles.append(tile_name)
            print(f"    FAILED: {tile_name}")
    
    # Summary
    print(f"\n  Tile download summary:")
    print(f"    Total tiles: {len(tiles)}")
    print(f"    Cached: {cached_count}")
    print(f"    Downloaded: {downloaded_count}")
    print(f"    Failed: {len(failed_tiles)}")
    
    if failed_tiles:
        print(f"  ERROR: Failed to download {len(failed_tiles)} tiles")
        for tile_name in failed_tiles:
            print(f"    - {tile_name}")
        return False
    
    # Merge tiles
    print(f"\n  Merging {len(tile_paths)} tiles...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    merge_success = merge_tiles(tile_paths, output_path)
    
    if merge_success:
        merged_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  Merged file: {output_path.name} ({merged_size_mb:.1f} MB)")
        
        # Save metadata for merged file
        try:
            metadata = create_raw_metadata(
                tif_path=output_path,
                region_id=region_id,
                source='srtm_90m',
                download_url="https://portal.opentopography.org/API/globaldem",
                download_params={'dataset': dataset, 'tiles': len(tiles)}
            )
            save_metadata(metadata, get_metadata_path(output_path))
        except Exception as e:
            print(f"  Warning: Could not save metadata: {e}")
    
    return merge_success


def download_srtm_90m_single(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    output_path: Path,
    api_key: Optional[str] = None,
    dataset: Optional[str] = None
) -> bool:
    """
    Download SRTM 90m data as single file (for small regions < 4 degrees).
    
    DEPRECATED: This function exists for compatibility but should not be used.
    The unified tiling system handles all region sizes efficiently.
    
    Args:
        region_id: Region identifier
        bounds: (west, south, east, north) in degrees
        output_path: Where to save the file
        api_key: OpenTopography API key
        dataset: 'SRTMGL3' or 'COP90' (auto-selects if None)
        
    Returns:
        True if successful
    """
    # Redirect to tiling system - unified approach handles all sizes
    return download_srtm_90m_tiles(region_id, bounds, output_path, api_key, dataset)
