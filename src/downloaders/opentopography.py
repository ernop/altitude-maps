"""
OpenTopography API downloader.

Downloads SRTM and Copernicus DEM data via OpenTopography's Global DEM API.
"""

from pathlib import Path
from typing import Tuple, Optional
import requests
from tqdm import tqdm

from load_settings import get_opentopography_api_key
from src.metadata import create_raw_metadata, save_metadata, get_metadata_path


def download_srtm(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    output_path: Path,
    api_key: Optional[str] = None
) -> bool:
    """
    Download SRTM 30m elevation data from OpenTopography.
    
    Args:
        region_id: Region identifier (for metadata)
        bounds: (west, south, east, north) in degrees
        output_path: Where to save the GeoTIFF
        api_key: OpenTopography API key (loads from settings.json if not provided)
        
    Returns:
        True if successful
    """
    if output_path.exists():
        print(f" Already exists: {output_path.name}", flush=True)
        return True

    if not api_key:
        try:
            api_key = get_opentopography_api_key()
            print(f" Using API key from settings.json", flush=True)
        except SystemExit:
            print(" OpenTopography requires an API key", flush=True)
            print(" Add your API key to settings.json or pass --api-key", flush=True)
            print(" Get a free key at: https://portal.opentopography.org/", flush=True)
            return False

    west, south, east, north = bounds
    width = abs(east - west)
    height = abs(north - south)

    if width > 4.0 or height > 4.0:
        print(f" WARNING: Region is very large ({width:.1f}deg x {height:.1f}deg)", flush=True)
        print(f" OpenTopography may reject requests > 4deg in any direction", flush=True)
        print(f" Consider using tile-based download for large regions", flush=True)

    url = "https://portal.opentopography.org/API/globaldem"
    params = {
        'demtype': 'SRTMGL1',
        'south': south,
        'north': north,
        'west': west,
        'east': east,
        'outputFormat': 'GTiff',
        'API_Key': api_key
    }

    print(f" Downloading from OpenTopography...", flush=True)
    print(f" Bounds: ({west:.2f}, {south:.2f}) to ({east:.2f}, {north:.2f})", flush=True)
    print(f" Size: {width:.2f}deg x {height:.2f}deg", flush=True)

    try:
        response = requests.get(url, params=params, stream=True, timeout=300)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc=f" {output_path.name}") as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f" Downloaded: {output_path.name} ({file_size_mb:.1f} MB)", flush=True)

        metadata = create_raw_metadata(
            tif_path=output_path,
            region_id=region_id,
            source='srtm_30m',
            download_url='https://portal.opentopography.org/API/globaldem',
            download_params={'demtype': 'SRTMGL1', 'bounds': bounds}
        )
        save_metadata(metadata, get_metadata_path(output_path))

        return True

    except requests.exceptions.Timeout:
        print(f" ERROR: Download timed out (region may be too large)", flush=True)
        if output_path.exists():
            output_path.unlink()
        return False
    except requests.exceptions.RequestException as e:
        print(f" ERROR: Download failed: {e}", flush=True)
        if output_path.exists():
            output_path.unlink()
        return False
    except Exception as e:
        print(f" ERROR: Unexpected error: {e}", flush=True)
        if output_path.exists():
            output_path.unlink()
        return False


def download_copernicus(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    output_path: Path,
    api_key: Optional[str] = None,
    resolution: str = '30m'
) -> bool:
    """
    Download Copernicus DEM data from OpenTopography.
    
    Args:
        region_id: Region identifier (for metadata)
        bounds: (west, south, east, north) in degrees
        output_path: Where to save the GeoTIFF
        api_key: OpenTopography API key (loads from settings.json if not provided)
        resolution: '30m' or '90m'
        
    Returns:
        True if successful
    """
    if output_path.exists():
        print(f" Already exists: {output_path.name}", flush=True)
        return True

    if not api_key:
        try:
            api_key = get_opentopography_api_key()
        except SystemExit:
            print(" OpenTopography requires an API key", flush=True)
            return False

    west, south, east, north = bounds
    demtype = 'COP30' if resolution == '30m' else 'COP90'

    url = "https://portal.opentopography.org/API/globaldem"
    params = {
        'demtype': demtype,
        'south': south,
        'north': north,
        'west': west,
        'east': east,
        'outputFormat': 'GTiff',
        'API_Key': api_key
    }

    print(f" Downloading Copernicus DEM ({resolution})...", flush=True)

    try:
        response = requests.get(url, params=params, stream=True, timeout=300)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc=f" {output_path.name}") as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f" Downloaded: {output_path.name} ({file_size_mb:.1f} MB)", flush=True)

        metadata = create_raw_metadata(
            tif_path=output_path,
            region_id=region_id,
            source='srtm_30m' if resolution == '30m' else 'srtm_90m',
            download_url='https://portal.opentopography.org/API/globaldem',
            download_params={'demtype': demtype, 'bounds': bounds}
        )
        save_metadata(metadata, get_metadata_path(output_path))

        return True

    except Exception as e:
        print(f" ERROR: Download failed: {e}", flush=True)
        if output_path.exists():
            output_path.unlink()
        return False

