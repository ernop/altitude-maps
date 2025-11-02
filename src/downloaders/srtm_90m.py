"""
SRTM 90m tile-based downloader.

Downloads SRTM 90m (SRTMGL3) elevation data tile-by-tile from OpenTopography.
Uses 1-degree tile grid with content-based naming for efficient reuse across regions.

Key features:
- Tile-by-tile downloads (1-degree tiles)
- Content-based naming: N40_W111_90m.tif
- Shared tile cache in data/raw/srtm_90m/tiles/
- Progress tracking per tile
- Automatic tile merging for large regions

Usage:
    from src.downloaders.srtm_90m import download_srtm_90m_tiles
    
    success = download_srtm_90m_tiles(
        region_id='california',
        bounds=(-124.5, 32.5, -114.1, 42.0),
        output_path=Path('data/merged/srtm_90m/california_merged_90m.tif')
    )
"""

from pathlib import Path
from typing import Tuple, Optional
import requests
from tqdm import tqdm

from src.tile_geometry import calculate_1degree_tiles, tile_filename_from_bounds
from src.pipeline import merge_tiles
from src.metadata import create_raw_metadata, save_metadata, get_metadata_path
from load_settings import get_opentopography_api_key
from src.downloaders.opentopography import OpenTopographyRateLimitError


def download_single_tile_90m(
    tile_bounds: Tuple[float, float, float, float],
    output_path: Path,
    api_key: str,
    dataset: str = 'SRTMGL3'
) -> bool:
    """
    Download a single 1-degree tile of SRTM 90m data.
    
    Args:
        tile_bounds: (west, south, east, north) for 1-degree tile
        output_path: Where to save the tile
        api_key: OpenTopography API key
        dataset: 'SRTMGL3' for SRTM 90m or 'COP90' for Copernicus 90m
        
    Returns:
        True if successful, False otherwise
    """
    if output_path.exists():
        return True
    
    west, south, east, north = tile_bounds
    
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
            print(f"\n    ERROR: OpenTopography returned 401 Unauthorized", flush=True)
            print(f"    This usually means rate limit or quota exceeded.", flush=True)
            print(f"    Please wait before trying again to let the API relax.", flush=True)
            print(f"    STOPPING all tile downloads to respect their limits.", flush=True)
            raise OpenTopographyRateLimitError("OpenTopography rate limit exceeded (401 Unauthorized)")
        
        if response.status_code != 200:
            print(f"    API Error {response.status_code}: {response.text[:200]}")
            return False
        
        response.raise_for_status()
        
        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Download with progress bar
        total_size = int(response.headers.get('content-length', 0))
        desc = output_path.name[:40] + ('...' if len(output_path.name) > 40 else '')
        
        with open(output_path, 'wb') as f:
            with tqdm(
                desc=desc,
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                miniters=1
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
        
        return True
    
    except OpenTopographyRateLimitError:
        # Re-raise to stop all tile downloads immediately
        raise
        
    except requests.exceptions.Timeout:
        print(f"    ERROR: Download timed out for tile")
        if output_path.exists():
            output_path.unlink()
        return False
        
    except requests.exceptions.RequestException as e:
        print(f"    ERROR: Download failed: {e}")
        if output_path.exists():
            output_path.unlink()
        return False
        
    except Exception as e:
        print(f"    ERROR: Unexpected error: {e}")
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
    if not merge_success:
        print(f"  ERROR: Tile merge failed")
        return False
    
    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"  Merged successfully: {output_path.name} ({file_size_mb:.1f} MB)")
    
    # Save metadata
    try:
        metadata = create_raw_metadata(
            tif_path=output_path,
            region_id=region_id,
            source='srtm_90m',
            download_url='https://portal.opentopography.org/API/globaldem',
            download_params={
                'dataset': dataset,
                'tiles': len(tiles),
                'cached': cached_count,
                'downloaded': downloaded_count,
                'bounds': bounds
            }
        )
        save_metadata(metadata, get_metadata_path(output_path))
    except Exception as e:
        print(f"  Warning: Could not save metadata: {e}")
    
    return True


def download_srtm_90m_single(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    output_path: Path,
    api_key: Optional[str] = None,
    dataset: Optional[str] = None
) -> bool:
    """
    Download SRTM 90m data as a single request (for small regions < 4 degrees).
    
    For large regions, use download_srtm_90m_tiles() instead.
    
    Args:
        region_id: Region identifier
        bounds: (west, south, east, north) in degrees
        output_path: Where to save the file
        api_key: OpenTopography API key
        dataset: 'SRTMGL3' or 'COP90' (auto-selects if None)
        
    Returns:
        True if successful
    """
    if output_path.exists():
        print(f"  Already exists: {output_path.name}")
        return True
    
    # Get API key
    if not api_key:
        try:
            api_key = get_opentopography_api_key()
        except SystemExit:
            print(f"  ERROR: OpenTopography API key required")
            return False
    
    # Auto-select dataset
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
    print(f"  Single-file download (region < 4deg)")
    print(f"  Bounds: ({west:.2f}, {south:.2f}) to ({east:.2f}, {north:.2f})")
    print(f"  Size: {width:.2f}deg x {height:.2f}deg")
    
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
            print(f"\n  ERROR: OpenTopography returned 401 Unauthorized", flush=True)
            print(f"  This usually means rate limit or quota exceeded.", flush=True)
            print(f"  Please wait before trying again to let the API relax.", flush=True)
            print(f"  STOPPING download to respect their limits.", flush=True)
            raise OpenTopographyRateLimitError("OpenTopography rate limit exceeded (401 Unauthorized)")
        
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
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
        print(f"  Downloaded: {output_path.name} ({file_size_mb:.1f} MB)")
        
        # Save metadata
        metadata = create_raw_metadata(
            tif_path=output_path,
            region_id=region_id,
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
        print(f"  ERROR: Download failed: {e}")
        if output_path.exists():
            output_path.unlink()
        return False

