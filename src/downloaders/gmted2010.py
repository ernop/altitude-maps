"""
GMTED2010 (Global Multi-resolution Terrain Elevation Data 2010) downloader.

Coarse-resolution global DEMs from USGS/NGA.
Resolutions: 250m, 500m, 1km (7.5, 15, 30 arc-seconds)

GMTED2010 provides global grids (not tiles) that must be downloaded and clipped.
Direct download URLs from USGS:
- Base: https://edcintl.cr.usgs.gov/downloads/sciweb1/shared/topo/downloads/GMTED/Grid_ZipFiles/
- Pattern: {product}{arcsec}_grd.zip
  - Products: md (median - recommended), mn (mean), mi (minimum), mx (maximum), sd (std dev), ds (subsample), be (breakline)
  - Arc-seconds: 75 (7.5 arc-sec = 250m), 15 (15 arc-sec = 500m), 30 (30 arc-sec = 1000m)

The downloader:
1. Downloads global grid (cached for reuse)
2. Extracts from ZIP
3. Clips to tile bounds
4. Saves as standard tile format
"""

import requests
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Tuple
import rasterio
from rasterio.mask import mask as rasterio_mask


# GMTED2010 URL patterns
GMTED2010_BASE_URL = "https://edcintl.cr.usgs.gov/downloads/sciweb1/shared/topo/downloads/GMTED/Grid_ZipFiles/"

# Resolution to arc-second mapping
RESOLUTION_TO_ARCSEC = {
    250: 75,   # 7.5 arc-seconds
    500: 15,   # 15 arc-seconds
    1000: 30,  # 30 arc-seconds
}

# Product code (md = median, most commonly used)
DEFAULT_PRODUCT = "md"  # Median statistic


def construct_gmted2010_url(resolution: int, product: str = DEFAULT_PRODUCT) -> str:
    """
    Construct GMTED2010 download URL for a resolution.
    
    Args:
        resolution: 250, 500, or 1000 meters
        product: Product code (md=median, mn=mean, mi=min, mx=max, sd=stddev, ds=subsample, be=breakline)
        
    Returns:
        Full URL to ZIP file
    """
    if resolution not in RESOLUTION_TO_ARCSEC:
        raise ValueError(f"Unsupported resolution: {resolution}m (must be 250, 500, or 1000)")
    
    arcsec = RESOLUTION_TO_ARCSEC[resolution]
    filename = f"{product}{arcsec}_grd.zip"
    return f"{GMTED2010_BASE_URL}{filename}"


def download_gmted2010_tile(
    tile_bounds: Tuple[float, float, float, float],
    resolution: int,
    output_path: Path
) -> bool:
    """
    Download and clip a GMTED2010 tile from the global grid.
    
    Args:
        tile_bounds: (west, south, east, north) in degrees
        resolution: 250, 500, or 1000 meters
        output_path: Where to save the tile
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create cache directory for global grids
        cache_dir = Path("data/.cache/gmted2010")
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Download global grid if not cached
        global_grid_path = cache_dir / f"gmted2010_{resolution}m_global.tif"
        if not global_grid_path.exists():
            print(f"    Downloading GMTED2010 {resolution}m global grid...", end=" ", flush=True)
            url = construct_gmted2010_url(resolution)
            
            # Download ZIP to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_zip:
                tmp_zip_path = Path(tmp_zip.name)
            
            try:
                response = requests.get(url, stream=True, timeout=300)
                response.raise_for_status()
                
                # Download with progress
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                with open(tmp_zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            if downloaded % (10 * 1024 * 1024) == 0:  # Print every 10MB
                                print(f"{percent:.1f}%", end=" ", flush=True)
                
                print("Extracting...", end=" ", flush=True)
                
                # Extract ZIP
                extract_dir = cache_dir / f"gmted2010_{resolution}m_extracted"
                extract_dir.mkdir(exist_ok=True)
                
                with zipfile.ZipFile(tmp_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # Find the extracted grid file (ArcGrid format)
                grid_files = list(extract_dir.rglob("*.adf"))
                if not grid_files:
                    # Try finding any raster file
                    grid_files = list(extract_dir.rglob("*.tif")) + list(extract_dir.rglob("*.bil"))
                
                if not grid_files:
                    print(f"[FAIL] No grid file found in ZIP")
                    return False
                
                # Use first found grid file (usually there's one main grid)
                source_grid = grid_files[0]
                
                # Convert ArcGrid to GeoTIFF if needed
                if source_grid.suffix == '.adf' or source_grid.suffix == '':
                    # Open ArcGrid and save as GeoTIFF
                    with rasterio.open(str(source_grid)) as src:
                        # Read data
                        data = src.read(1)
                        profile = src.profile.copy()
                        profile.update(driver='GTiff', compress='lzw')
                        
                        # Save as GeoTIFF
                        with rasterio.open(global_grid_path, 'w', **profile) as dst:
                            dst.write(data, 1)
                else:
                    # Already GeoTIFF or other format, copy
                    shutil.copy2(source_grid, global_grid_path)
                
                print("[OK]")
                
                # Cleanup temp files
                tmp_zip_path.unlink()
                shutil.rmtree(extract_dir, ignore_errors=True)
                
            except Exception as e:
                print(f"[FAIL] {e}")
                if tmp_zip_path.exists():
                    tmp_zip_path.unlink()
                return False
        else:
            print(f"    Using cached GMTED2010 {resolution}m global grid", flush=True)
        
        # Clip global grid to tile bounds
        print(f"    Clipping to tile bounds...", end=" ", flush=True)
        
        with rasterio.open(global_grid_path) as src:
            # Create geometry for tile bounds
            from shapely.geometry import box
            tile_geom = box(tile_bounds[0], tile_bounds[1], tile_bounds[2], tile_bounds[3])
            
            # Clip
            out_image, out_transform = rasterio_mask(src, [tile_geom], crop=True, filled=False)
            
            # Update metadata
            out_meta = src.meta.copy()
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
                "compress": "lzw"
            })
            
            # Save clipped tile
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(output_path, "w", **out_meta) as dest:
                dest.write(out_image)
        
        print("[OK]")
        return True
        
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def download_gmted2010_tiles(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    resolution: int,
    tiles_dir: Path
) -> list[Path]:
    """
    Download multiple GMTED2010 tiles for a region.
    
    Args:
        region_id: Region identifier
        bounds: (west, south, east, north)
        resolution: 250, 500, or 1000 meters
        tiles_dir: Directory to store tiles
        
    Returns:
        List of successfully downloaded tile paths
    """
    from src.tile_geometry import calculate_1degree_tiles, tile_filename_from_bounds
    
    tiles = calculate_1degree_tiles(bounds)
    downloaded_paths = []
    
    tiles_dir.mkdir(parents=True, exist_ok=True)
    
    for idx, tile_bounds in enumerate(tiles, 1):
        tile_filename = tile_filename_from_bounds(tile_bounds, f"{resolution}m")
        tile_path = tiles_dir / tile_filename
        
        # Skip if already exists
        if tile_path.exists():
            downloaded_paths.append(tile_path)
            continue
        
        print(f"  [{idx}/{len(tiles)}] {tile_filename}")
        success = download_gmted2010_tile(tile_bounds, resolution, tile_path)
        if success:
            downloaded_paths.append(tile_path)
        else:
            print(f"    Failed to download {tile_filename}")
    
    return downloaded_paths

