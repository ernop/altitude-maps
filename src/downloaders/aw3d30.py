"""
ALOS World 3D - 30m (AW3D30) elevation data downloader.

High-quality 30m global DEM from JAXA's ALOS satellite.
Available via OpenTopography API (same auth as SRTM).

Coverage: 82°N to 82°S
Resolution: 1 arc-second (~30m)
Quality: Often superior to SRTM, especially in mountainous terrain
"""

from pathlib import Path
from typing import Tuple
import requests
import time

from src.downloaders.rate_limit import (
    check_rate_limit,
    record_rate_limit_hit,
    record_successful_request
)
from load_settings import get_api_key


class AW3D30RateLimitError(Exception):
    """Raised when OpenTopography rate limit exceeded for AW3D30."""
    pass


def download_aw3d30_tile(
    tile_bounds: Tuple[float, float, float, float],
    output_path: Path,
    api_key: str = None,
    timeout: int = 120
) -> bool:
    """
    Download a single 1×1 degree AW3D30 tile via OpenTopography.
    
    Args:
        tile_bounds: (west, south, east, north) in degrees
        output_path: Where to save the tile
        api_key: OpenTopography API key (loads from settings if not provided)
        timeout: Download timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    # Get API key if not provided
    if api_key is None:
        try:
            api_key = get_api_key('opentopography')
        except Exception:
            print(f"    ERROR: OpenTopography API key required for AW3D30")
            print(f"    Get a free key at: https://portal.opentopography.org/")
            print(f"    Add to settings.json under 'opentopography.api_key'")
            return False
    
    west, south, east, north = tile_bounds
    
    # OpenTopography Global DEM API
    url = "https://portal.opentopography.org/API/globaldem"
    
    params = {
        'demtype': 'AW3D30',  # ALOS World 3D 30m
        'south': south,
        'north': north,
        'west': west,
        'east': east,
        'outputFormat': 'GTiff',
        'API_Key': api_key
    }
    
    try:
        # Add small delay to avoid hammering API
        time.sleep(0.5)
        
        response = requests.get(url, params=params, stream=True, timeout=timeout)
        
        # Handle rate limiting
        if response.status_code == 401:
            print(f"\n    ERROR: OpenTopography returned 401 Unauthorized")
            print(f"    This usually means:")
            print(f"      - Rate limit exceeded (too many requests)")
            print(f"      - Daily quota exceeded")
            print(f"      - Invalid API key")
            record_rate_limit_hit(response.status_code)
            raise AW3D30RateLimitError("OpenTopography rate limit exceeded")
        
        if response.status_code == 404:
            # Tile doesn't exist (outside coverage area or ocean)
            print(f"    Tile not available (404)")
            return False
        
        if response.status_code >= 500:
            print(f"    ERROR: Server error ({response.status_code})")
            return False
        
        if response.status_code != 200:
            print(f"    ERROR: Unexpected status {response.status_code}")
            return False
        
        # Save to temporary file first
        temp_path = output_path.with_suffix('.tmp')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Verify file
        if temp_path.stat().st_size < 1000:
            print(f"    ERROR: File too small ({temp_path.stat().st_size} bytes)")
            temp_path.unlink()
            return False
        
        # Verify GeoTIFF
        try:
            import rasterio
            with rasterio.open(temp_path) as src:
                _ = src.bounds
                _ = src.crs
        except Exception as e:
            print(f"    ERROR: Invalid GeoTIFF: {e}")
            temp_path.unlink()
            return False
        
        # Success
        temp_path.rename(output_path)
        record_successful_request()
        return True
        
    except AW3D30RateLimitError:
        raise
    except requests.Timeout:
        print(f"    ERROR: Timeout after {timeout}s")
        return False
    except requests.RequestException as e:
        print(f"    ERROR: Download failed: {e}")
        return False
    except Exception as e:
        print(f"    ERROR: Unexpected error: {e}")
        return False


def download_aw3d30_tiles(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    tiles_dir: Path,
    api_key: str = None
) -> list[Path]:
    """
    Download multiple AW3D30 tiles for a region.
    
    Args:
        region_id: Region identifier (for logging)
        bounds: (west, south, east, north)
        tiles_dir: Directory to store tiles
        api_key: OpenTopography API key
        
    Returns:
        List of successfully downloaded tile paths
    """
    from src.tile_geometry import calculate_1degree_tiles, tile_filename_from_bounds
    
    # Check rate limit before starting
    ok, reason = check_rate_limit()
    if not ok:
        print(f"\n  Rate limit active: {reason}")
        print(f"  Use 'python check_rate_limit.py' to check status")
        return []
    
    tiles = calculate_1degree_tiles(bounds)
    downloaded_paths = []
    
    print(f"Downloading {len(tiles)} AW3D30 tiles via OpenTopography...")
    
    for idx, tile_bounds in enumerate(tiles, 1):
        tile_filename = tile_filename_from_bounds(tile_bounds, "30m")
        tile_path = tiles_dir / tile_filename
        
        # Skip tile reuse - always download fresh region-specific data
        # (Tile directories remain for reference but are not reused)
        
        print(f"  [{idx}/{len(tiles)}] Downloading: {tile_filename}", end=" ", flush=True)
        
        try:
            if download_aw3d30_tile(tile_bounds, tile_path, api_key):
                file_size_mb = tile_path.stat().st_size / (1024 * 1024)
                print(f"[OK] ({file_size_mb:.1f} MB)")
                downloaded_paths.append(tile_path)
            else:
                print(f"[FAIL] (skipped)")
        except AW3D30RateLimitError:
            print(f"[FAIL] (rate limited)")
            print(f"\nStopping download - rate limit hit")
            break
    
    print(f"Successfully downloaded {len(downloaded_paths)}/{len(tiles)} tiles")
    return downloaded_paths

