"""
Copernicus DEM downloader via AWS S3 public buckets.

Direct access to Copernicus GLO-10/30/90 data from AWS S3.
No authentication required - public buckets.

Tile format: 1×1 degree tiles as Cloud Optimized GeoTIFF (COG)
URL pattern: https://copernicus-dem-{resolution}.s3.amazonaws.com/Copernicus_DSM_COG_{res}_{lat}_{lon}_DEM.tif

Coverage:
- GLO-10: Europe only (38°N to 60°N, 13°W to 32°E)
- GLO-30: Global
- GLO-90: Global
"""

from pathlib import Path
from typing import Tuple, Optional
import requests
from src.tile_geometry import tile_filename_from_bounds


def format_lat_band(lat: float) -> str:
    """
    Format latitude for Copernicus tile naming.
    
    Examples:
      40.5 -> N40_00
      -5.2 -> S05_00
      0.0 -> N00_00
    """
    lat_int = int(lat)
    if lat_int >= 0:
        return f"N{lat_int:02d}_00"
    else:
        return f"S{abs(lat_int):02d}_00"


def format_lon_band(lon: float) -> str:
    """
    Format longitude for Copernicus tile naming.
    
    Examples:
      -80.3 -> W080_00
      120.7 -> E120_00
      0.0 -> E000_00
    """
    lon_int = int(lon)
    if lon_int >= 0:
        return f"E{lon_int:03d}_00"
    else:
        return f"W{abs(lon_int):03d}_00"


def construct_copernicus_url(
    tile_bounds: Tuple[float, float, float, float],
    resolution: int
) -> str:
    """
    Construct Copernicus S3 URL for a tile.
    
    CRITICAL: Copernicus uses arc-seconds in paths, and tiles are in directories!
    - GLO-30 (30m) = 10 arc-seconds
    - GLO-90 (90m) = 30 arc-seconds
    
    Structure: s3://bucket/Copernicus_DSM_COG_[arcsec]_[lat]_[lon]_DEM/Copernicus_DSM_COG_[arcsec]_[lat]_[lon]_DEM.tif
    
    Args:
        tile_bounds: (west, south, east, north) - should be 1×1 degree tile
        resolution: 10, 30, or 90 meters
        
    Returns:
        Full HTTPS URL to tile
    """
    west, south, east, north = tile_bounds
    
    # Use southwest corner for tile identification
    lat_band = format_lat_band(south)
    lon_band = format_lon_band(west)
    
    # Determine bucket and arc-second resolution
    # NOTE: Only GLO-30 (30m) and GLO-90 (90m) are publicly available via S3
    if resolution == 30:
        bucket = "copernicus-dem-30m"
        arcsec = "10"  # 10 arc-seconds for 30m (GLO-30)
    elif resolution == 90:
        bucket = "copernicus-dem-90m"
        arcsec = "30"  # 30 arc-seconds for 90m (GLO-90)
    else:
        raise ValueError(f"Unsupported resolution: {resolution}m (must be 30 or 90, GLO-10 not publicly available)")
    
    # Construct directory and filename
    # Directory: Copernicus_DSM_COG_30_N43_00_W098_00_DEM/
    # File: Copernicus_DSM_COG_30_N43_00_W098_00_DEM.tif
    tile_name = f"Copernicus_DSM_COG_{arcsec}_{lat_band}_{lon_band}_DEM"
    filename = f"{tile_name}.tif"
    
    # Full URL includes directory path
    url = f"https://{bucket}.s3.amazonaws.com/{tile_name}/{filename}"
    return url


def download_copernicus_s3_tile(
    tile_bounds: Tuple[float, float, float, float],
    resolution: int,
    output_path: Path,
    timeout: int = 120
) -> bool:
    """
    Download a single 1×1 degree Copernicus tile from S3.
    
    Args:
        tile_bounds: (west, south, east, north) - must be 1×1 degree aligned
        resolution: 10, 30, or 90 meters
        output_path: Where to save the tile
        timeout: Download timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    # Construct URL
    url = construct_copernicus_url(tile_bounds, resolution)
    
    try:
        # Download with streaming to handle large files
        response = requests.get(url, stream=True, timeout=timeout)
        
        # Handle different response codes
        if response.status_code == 404:
            # Tile doesn't exist (ocean, no data) - this is expected for some tiles
            print(f"    Tile not available (404): {url}")
            return False
        
        if response.status_code == 403:
            # Access denied - unexpected for public bucket
            print(f"    ERROR: Access denied (403): {url}")
            return False
        
        if response.status_code >= 500:
            # Server error - temporary issue
            print(f"    ERROR: Server error ({response.status_code}): {url}")
            return False
        
        if response.status_code != 200:
            print(f"    ERROR: Unexpected status {response.status_code}: {url}")
            return False
        
        # Save to temporary file first
        temp_path = output_path.with_suffix('.tmp')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file in chunks
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Verify file is valid (basic size check)
        if temp_path.stat().st_size < 1000:
            print(f"    ERROR: Downloaded file too small ({temp_path.stat().st_size} bytes)")
            temp_path.unlink()
            return False
        
        # Verify it's a valid GeoTIFF
        try:
            import rasterio
            with rasterio.open(temp_path) as src:
                # Just check we can open it and read basic metadata
                _ = src.bounds
                _ = src.crs
        except Exception as e:
            print(f"    ERROR: Invalid GeoTIFF: {e}")
            temp_path.unlink()
            return False
        
        # Move temp file to final location
        temp_path.rename(output_path)
        
        return True
        
    except requests.Timeout:
        print(f"    ERROR: Download timeout after {timeout}s")
        return False
    except requests.RequestException as e:
        print(f"    ERROR: Download failed: {e}")
        return False
    except Exception as e:
        print(f"    ERROR: Unexpected error: {e}")
        return False


def download_copernicus_s3_tiles(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    resolution: int,
    tiles_dir: Path
) -> list[Path]:
    """
    Download multiple Copernicus tiles from S3 for a region.
    
    This is called by the tile manager - just downloads individual tiles.
    Merging is handled separately.
    
    Args:
        region_id: Region identifier (for logging)
        bounds: (west, south, east, north) for region
        resolution: 10, 30, or 90 meters
        tiles_dir: Directory to store tiles
        
    Returns:
        List of successfully downloaded tile paths
    """
    from src.tile_geometry import calculate_1degree_tiles
    
    tiles = calculate_1degree_tiles(bounds)
    downloaded_paths = []
    
    print(f"Downloading {len(tiles)} Copernicus GLO-{resolution} tiles from S3...")
    
    for idx, tile_bounds in enumerate(tiles, 1):
        tile_filename = tile_filename_from_bounds(tile_bounds, f"{resolution}m")
        tile_path = tiles_dir / tile_filename
        
        # Skip if already cached
        if tile_path.exists():
            print(f"  [{idx}/{len(tiles)}] Cached: {tile_filename}")
            downloaded_paths.append(tile_path)
            continue
        
        print(f"  [{idx}/{len(tiles)}] Downloading: {tile_filename}", end=" ", flush=True)
        
        if download_copernicus_s3_tile(tile_bounds, resolution, tile_path):
            file_size_mb = tile_path.stat().st_size / (1024 * 1024)
            print(f"[OK] ({file_size_mb:.1f} MB)")
            downloaded_paths.append(tile_path)
        else:
            print(f"[FAIL] (skipped)")
    
    print(f"Successfully downloaded {len(downloaded_paths)}/{len(tiles)} tiles")
    return downloaded_paths


# Note: Parallel downloads possible for S3 (no rate limits)
# Could implement parallel download pool in future for faster large-region downloads
# For now, sequential is simpler and still reasonably fast

