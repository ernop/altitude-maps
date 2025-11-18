"""
USA Elevation Data Acquisition Module

This module provides tools to download high-resolution elevation data for the USA
from various public sources including USGS 3DEP and OpenTopography.

Data Sources:
- USGS 3DEP (3D Elevation Program): 1/3 arc-second (~10m) resolution
- USGS National Map: Various resolutions including 1m, 3m, 10m, 30m
- OpenTopography: Research-grade DEM data
"""

import sys
import io
import requests
from pathlib import Path
from typing import Tuple, Optional
import numpy as np
from tqdm import tqdm

from src.config import DEFAULT_TARGET_TOTAL_PIXELS

# NOTE: This is a library module - do NOT wrap stdout/stderr
# Modern Python handles UTF-8 correctly by default


class USGSElevationDownloader:
    """
    Downloads elevation data from USGS sources.

    USGS 3DEP provides elevation data at various resolutions:
    - 1 meter: Limited areas
    - 3 meter: Parts of USA
    - 10 meter (1/3 arc-second): Most of USA
    - 30 meter (1 arc-second): Full USA coverage
    """

    def __init__(self, data_dir: str = "data/usa_elevation"):
        """
        Initialize the downloader.

        Args:
            data_dir: Directory to store downloaded elevation data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_available_datasets(self) -> dict:
        """
        Get information about available USA elevation datasets.

        Returns:
            Dictionary of dataset information
        """
        datasets = {
            'usgs_3dep_10m': {
                'name': 'USGS 3DEP 10m (1/3 arc-second)',
                'resolution': '~10 meters',
                'coverage': 'Contiguous USA',
                'url_info': 'https://www.usgs.gov/3d-elevation-program',
                'api': 'https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer',
                'description': 'Best balance of resolution and coverage'
            },
            'usgs_ned_30m': {
                'name': 'USGS NED 30m (1 arc-second)',
                'resolution': '~30 meters',
                'coverage': 'Full USA including Alaska',
                'url_info': 'https://www.usgs.gov/national-map',
                'description': 'Complete USA coverage'
            },
            'srtm_30m': {
                'name': 'SRTM 30m',
                'resolution': '~30 meters',
                'coverage': 'Global (60degN to 56degS)',
                'url_base': 'https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11/',
                'description': 'NASA Shuttle Radar Topography Mission'
            },
            'opentopography': {
                'name': 'OpenTopography',
                'resolution': 'Varies (1m to 30m)',
                'coverage': 'USA research areas',
                'url_info': 'https://opentopography.org/',
                'description': 'High-resolution research data (requires API key)'
            }
        }
        return datasets

    def print_dataset_info(self) -> None:
        """Print information about available datasets."""
        datasets = self.get_available_datasets()

        print("\n" + "=" * 70)
        print("  AVAILABLE USA ELEVATION DATA SOURCES")
        print("=" * 70 + "\n")

        for key, info in datasets.items():
            print(f"  {info['name']}")
            print(f"    Resolution: {info['resolution']}")
            print(f"    Coverage: {info['coverage']}")
            if 'url_info' in info:
                print(f"    Info: {info['url_info']}")
            print(f"    Notes: {info['description']}")
            print()

    def download_via_national_map_api(self,
                                       bbox: Tuple[float, float, float, float],
                                       output_file: str = "elevation_sample.tif",
                                       target_total_pixels: int = ...) -> Optional[Path]:
        """
        Download elevation data using USGS National Map API.

        Args:
            bbox: Bounding box (west, south, east, north) in decimal degrees
            output_file: Output filename
            target_total_pixels: Target total pixel count (width × height) (required) - used to calculate download resolution

        Returns:
            Path to downloaded file or None if failed
        """
        
        from src.tile_geometry import calculate_visible_pixel_size
        
        west, south, east, north = bbox
        width_deg = east - west
        height_deg = north - south
        
        # Calculate visible pixel size for final output
        visible = calculate_visible_pixel_size(bbox, target_total_pixels)
        visible_m_per_pixel = visible['avg_m_per_pixel']
        
        # Calculate download resolution based on Nyquist requirement
        # Need at least 2x oversampling for downsampling, or use native resolution if close
        # For native resolution display (0.8x to 1.2x), download at native 10m
        # For downsampling, download enough pixels to satisfy 2x Nyquist
        NATIVE_MIN = 0.8
        NATIVE_MAX = 1.2
        
        # Check if we're at native resolution (no downsampling needed)
        oversampling = visible_m_per_pixel / 10.0
        if NATIVE_MIN <= oversampling <= NATIVE_MAX:
            # Native resolution - download at 10m resolution
            target_resolution_m = 10.0
        else:
            # Need downsampling - calculate pixels needed for 2x Nyquist
            # For 2x Nyquist: source_pixels >= 2 * output_pixels
            # Calculate based on geographic bounds and target output size
            output_width = visible['output_width_px']
            output_height = visible['output_height_px']
            
            # Download at least 2x the output pixels (Nyquist requirement)
            # But don't exceed native 10m resolution (that's the finest available)
            min_source_width = max(output_width * 2, int(output_width * 2.0))
            min_source_height = max(output_height * 2, int(output_height * 2.0))
            
            # Calculate what resolution this corresponds to
            avg_lat = (north + south) / 2.0
            meters_per_deg_lat = 111320.0
            meters_per_deg_lon = 111320.0 * abs(np.cos(np.radians(avg_lat)))
            
            width_m = width_deg * meters_per_deg_lon
            height_m = height_deg * meters_per_deg_lat
            
            # Resolution needed to get min_source_width pixels
            resolution_from_width = width_m / min_source_width
            resolution_from_height = height_m / min_source_height
            
            # Use the finer resolution (more pixels), but cap at 10m (native)
            target_resolution_m = min(max(resolution_from_width, resolution_from_height), 10.0)
        
        # Calculate pixel dimensions at target resolution
        avg_lat = (north + south) / 2.0
        meters_per_deg_lat = 111320.0
        meters_per_deg_lon = 111320.0 * abs(np.cos(np.radians(avg_lat)))
        
        width_pixels = int((width_deg * meters_per_deg_lon) / target_resolution_m)
        height_pixels = int((height_deg * meters_per_deg_lat) / target_resolution_m)
        
        # Ensure minimum size (prevent API errors from tiny requests)
        width_pixels = max(256, width_pixels)
        height_pixels = max(256, height_pixels)
        
        import math
        base_dimension = int(round(math.sqrt(target_total_pixels)))
        print(f"  Ideal resolution: {target_resolution_m:.1f} m (calculated from target_total_pixels={target_total_pixels:,}, base_dimension={base_dimension}px)", flush=True)
        print(f"  Visible pixel size: {visible_m_per_pixel:.1f} m/pixel", flush=True)
        print(f"  Oversampling: {visible_m_per_pixel / target_resolution_m:.2f}x", flush=True)
        
        # ArcGIS ImageServer typically limits exportImage to ~4000-5000 pixels per dimension
        # Check if request exceeds safe limits and auto-chunk if needed
        MAX_SAFE_PIXELS = 4000  # Conservative limit based on ArcGIS ImageServer defaults
        if width_pixels > MAX_SAFE_PIXELS or height_pixels > MAX_SAFE_PIXELS:
            print(f"  Request size ({width_pixels}x{height_pixels}) exceeds safe API limit ({MAX_SAFE_PIXELS}px), auto-chunking...", flush=True)
            return self._download_chunked(bbox, output_file, target_resolution_m)

        # USGS 3DEP ImageServer URL
        base_url = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"

        params = {
            'bbox': f'{west},{south},{east},{north}',
            'bboxSR': '4326',  # WGS84
            'size': f'{width_pixels},{height_pixels}',  # Native resolution (10m)
            'imageSR': '4326',
            'format': 'tiff',
            'pixelType': 'F32',  # 32-bit float
            'noDataValue': '-9999',
            'interpolation': 'RSP_BilinearInterpolation',
            'f': 'image'
        }

        try:
            print(f"\n  Downloading elevation data for bbox: {bbox}", flush=True)
            print(f"  Using USGS 3DEP ImageServer...", flush=True)
            print(f"  Requesting {width_pixels}x{height_pixels} pixels (~10m resolution)", flush=True)
            
            # Print full URL with all parameters for debugging
            from urllib.parse import urlencode
            full_url = f"{base_url}?{urlencode(params)}"
            print(f"\n  FULL REQUEST URL:", flush=True)
            print(f"  {full_url}", flush=True)
            print(f"\n  Query Parameters:", flush=True)
            for key, value in params.items():
                print(f"    {key}: {value}", flush=True)

            # First, check if request will succeed (don't stream yet)
            print(f"\n  Sending initial request to check API response...", flush=True)
            check_response = requests.get(base_url, params=params, timeout=60)
            print(f"  Response status: {check_response.status_code}", flush=True)
            print(f"  Response headers: {dict(check_response.headers)}", flush=True)
            print(f"  Response content length: {len(check_response.content)} bytes", flush=True)
            
            # Check if API rejected due to size limit or other error
            # API returns 200 with JSON error even though Content-Type says image/tiff
            content_length = len(check_response.content)
            content_preview = check_response.content[:500].decode('utf-8', errors='ignore')
            
            print(f"  Response content preview: {content_preview}", flush=True)
            
            if check_response.status_code == 200:
                # Check if response is actually JSON error (API lies about content-type)
                # Small responses (< 1KB) that start with '{' are likely JSON errors
                if content_length < 1024:
                    print(f"  WARNING: Response is suspiciously small ({content_length} bytes) - likely an error", flush=True)
                    
                    if check_response.content.startswith(b'{'):
                        try:
                            error_data = check_response.json()
                            print(f"  Parsed JSON error response:", flush=True)
                            print(f"  {error_data}", flush=True)
                            
                            if 'error' in error_data:
                                error_msg = error_data['error'].get('message', '')
                                error_code = error_data['error'].get('code', '')
                                details = error_data['error'].get('details', [])
                                
                                print(f"\n  API ERROR DETECTED:", flush=True)
                                print(f"    Code: {error_code}", flush=True)
                                print(f"    Message: {error_msg}", flush=True)
                                if details:
                                    print(f"    Details: {details}", flush=True)
                                
                                error_msg_lower = error_msg.lower()
                                details_str = ' '.join(details).lower() if details else ''
                                
                                if 'size limit' in error_msg_lower or 'exceeds' in error_msg_lower or 'size limit' in details_str:
                                    # Size limit exceeded - chunk the request
                                    print(f"\n  API size limit exceeded, chunking request...", flush=True)
                                    return self._download_chunked(bbox, output_file, target_resolution_m)
                                else:
                                    # Other error - fail with clear message
                                    raise ValueError(f"USGS API error: {error_msg} (Code: {error_code})")
                        except ValueError:
                            # Re-raise ValueError (our error handling)
                            raise
                        except Exception as e:
                            # If JSON parsing fails, show raw content
                            print(f"  Failed to parse JSON error: {e}", flush=True)
                            print(f"  Raw response: {check_response.text}", flush=True)
                            raise ValueError(f"API returned unexpected response ({content_length} bytes): {check_response.text[:200]}")
                    else:
                        # Small response but not JSON - might be HTML error page
                        print(f"  Response appears to be text (not JSON): {content_preview}", flush=True)
                        raise ValueError(f"API returned unexpected small response ({content_length} bytes): {content_preview}")
            
            # Only raise if not a JSON error (which we handle above)
            if not (check_response.status_code == 200 and len(check_response.content) < 1024 and check_response.content.startswith(b'{')):
                check_response.raise_for_status()
            else:
                # If we got here, it's a JSON error we didn't handle - fail
                raise ValueError(f"API returned error: {check_response.text}")

            output_path = self.data_dir / output_file

            # Now download with streaming (only if check passed)
            print(f"\n  Starting download stream...", flush=True)
            response = requests.get(base_url, params=params, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            print(f"  Content-Length: {total_size} bytes ({total_size / (1024*1024):.2f} MB)", flush=True)
            if total_size == 0:
                print(f"  WARNING: Content-Length is 0 - response may be empty or error", flush=True)
                print(f"  Response content preview (first 500 chars): {response.content[:500]}", flush=True)
            
            import time
            start_time = time.time()

            with open(output_path, 'wb') as f, tqdm(
                desc="Downloading",
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    pbar.update(size)

            elapsed_time = time.time() - start_time
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            download_speed = file_size_mb / elapsed_time if elapsed_time > 0 else 0
            print(f"  Downloaded: {output_path.name} ({file_size_mb:.1f} MB in {elapsed_time:.1f}s, {download_speed:.1f} MB/s)")
            return output_path

        except requests.exceptions.RequestException as e:
            # Check if error message indicates size limit
            error_str = str(e).lower()
            if 'size limit' in error_str or 'exceeds' in error_str:
                print(f"  API size limit exceeded, chunking request...")
                return self._download_chunked(bbox, output_file, target_resolution_m)
            
            print(f"  Error downloading data: {e}")
            print("\nNote: For large downloads, consider using:")
            print("  1. USGS Earth Explorer: https://earthexplorer.usgs.gov/")
            print("  2. USGS National Map Downloader: https://apps.nationalmap.gov/downloader/")
            return None
    
    def _download_chunked(self, bbox: Tuple[float, float, float, float], output_file: str, target_resolution_m: float) -> Optional[Path]:
        """
        Download large area by splitting into smaller chunks and merging.
        
        Uses safe maximum size (4000x4000 pixels) per chunk to stay within API limits.
        """
        from src.pipeline import merge_tiles
        import tempfile
        import rasterio
        from rasterio.merge import merge as rasterio_merge
        
        west, south, east, north = bbox
        width_deg = east - west
        height_deg = north - south
        
        avg_lat = (north + south) / 2.0
        meters_per_deg_lat = 111320.0
        meters_per_deg_lon = 111320.0 * abs(np.cos(np.radians(avg_lat)))
        
        # Calculate safe chunk size (max 2000 pixels per dimension - very conservative)
        # API has strict limits, so use smaller chunks to ensure success
        max_pixels = 2000
        chunk_width_deg = (max_pixels * target_resolution_m) / meters_per_deg_lon
        chunk_height_deg = (max_pixels * target_resolution_m) / meters_per_deg_lat
        
        # Calculate number of chunks needed
        num_chunks_x = max(1, int(np.ceil(width_deg / chunk_width_deg)))
        num_chunks_y = max(1, int(np.ceil(height_deg / chunk_height_deg)))
        
        print(f"  Splitting into {num_chunks_x}x{num_chunks_y} chunks ({num_chunks_x * num_chunks_y} total) for API compatibility...")
        
        chunk_paths = []
        temp_dir = Path(tempfile.gettempdir()) / "usgs_chunks"
        temp_dir.mkdir(exist_ok=True)
        
        base_url = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
        
        for y in range(num_chunks_y):
            for x in range(num_chunks_x):
                chunk_west = west + (x * chunk_width_deg)
                chunk_east = min(east, chunk_west + chunk_width_deg)
                chunk_south = south + (y * chunk_height_deg)
                chunk_north = min(north, chunk_south + chunk_height_deg)
                
                chunk_bbox = (chunk_west, chunk_south, chunk_east, chunk_north)
                chunk_pixels_x = int(((chunk_east - chunk_west) * meters_per_deg_lon) / target_resolution_m)
                chunk_pixels_y = int(((chunk_north - chunk_south) * meters_per_deg_lat) / target_resolution_m)
                
                chunk_file = temp_dir / f"chunk_{y}_{x}_{output_file}"
                chunk_num = y * num_chunks_x + x + 1
                total_chunks = num_chunks_x * num_chunks_y
                
                print(f"  [{chunk_num}/{total_chunks}] Downloading chunk ({chunk_pixels_x}x{chunk_pixels_y} pixels)...")
                
                params = {
                    'bbox': f'{chunk_west},{chunk_south},{chunk_east},{chunk_north}',
                    'bboxSR': '4326',
                    'size': f'{chunk_pixels_x},{chunk_pixels_y}',
                    'imageSR': '4326',
                    'format': 'tiff',
                    'pixelType': 'F32',
                    'noDataValue': '-9999',
                    'interpolation': 'RSP_BilinearInterpolation',
                    'f': 'image'
                }
                
                # Print full URL for chunk
                from urllib.parse import urlencode
                chunk_url = f"{base_url}?{urlencode(params)}"
                print(f"    Chunk URL: {chunk_url}")
                print(f"    Chunk bbox: ({chunk_west}, {chunk_south}, {chunk_east}, {chunk_north})")
                
                try:
                    print(f"    Sending request...")
                    response = requests.get(base_url, params=params, stream=True, timeout=300)
                    print(f"    Response status: {response.status_code}")
                    print(f"    Content-Length header: {response.headers.get('content-length', 'unknown')}")
                    response.raise_for_status()
                    
                    with open(chunk_file, 'wb') as f:
                        for chunk_data in response.iter_content(chunk_size=8192):
                            f.write(chunk_data)
                    
                    chunk_paths.append(chunk_file)
                except Exception as e:
                    print(f"  ERROR: Failed to download chunk {chunk_num}: {e}")
                    # Clean up
                    for cp in chunk_paths:
                        if cp.exists():
                            cp.unlink()
                    return None
        
        # Merge chunks
        print(f"  Merging {len(chunk_paths)} chunks...")
        output_path = self.data_dir / output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            src_files_to_mosaic = [rasterio.open(cp) for cp in chunk_paths]
            mosaic, out_trans = rasterio_merge(src_files_to_mosaic)
            
            # Get metadata from first file
            out_meta = src_files_to_mosaic[0].meta.copy()
            out_meta.update({
                "driver": "GTiff",
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": out_trans
            })
            
            with rasterio.open(output_path, "w", **out_meta) as dest:
                dest.write(mosaic)
            
            # Close all source files
            for src in src_files_to_mosaic:
                src.close()
            
            print(f"  Merged: {output_path}")
            return output_path
        except Exception as e:
            print(f"  ERROR: Failed to merge chunks: {e}")
            return None
        finally:
            # Clean up temp chunks
            for cp in chunk_paths:
                if cp.exists():
                    cp.unlink()


class USARegionBounds:
    """Predefined bounding boxes for USA regions."""

    REGIONS = {
        # Complete nationwide USA coverage
        'nationwide_usa': (-125.0, 24.0, -66.0, 49.5),
        'continental_usa': (-125.0, 24.0, -66.0, 49.0),
        'usa_west': (-125.0, 31.0, -102.0, 49.0),
        'usa_east': (-102.0, 24.0, -66.0, 49.0),

        # Regional areas
        'colorado_rockies': (-109.0, 37.0, -105.0, 41.0),
        'california_sierra': (-120.5, 36.0, -118.0, 39.0),
        'appalachian_tn': (-84.5, 35.0, -82.0, 36.5),
        'cascades_wa': (-122.0, 46.0, -120.0, 49.0),
        'denver_area': (-105.5, 39.5, -104.5, 40.0),
        'grand_canyon': (-113.0, 35.5, -111.5, 36.5),
        'yellowstone': (-111.5, 44.0, -109.5, 45.5),
        'mount_rainier': (-122.0, 46.5, -121.0, 47.5),
        'great_smoky_mtns': (-84.0, 35.4, -83.3, 35.8),
        'white_mountains_nh': (-71.8, 43.9, -71.0, 44.5),
    }

    @classmethod
    def list_regions(cls) -> None:
        """Print available predefined regions."""
        print("\n" + "=" * 70)
        print("  PREDEFINED USA REGIONS")
        print("=" * 70 + "\n")

        for name, (w, s, e, n) in cls.REGIONS.items():
            area_deg_sq = (e - w) * (n - s)
            area_km_sq = area_deg_sq * 111 * 111  # Rough conversion
            print(f"  {name.replace('_', ' ').title()}")
            print(f"    Bounds: ({w:.2f}W, {s:.2f}N) to ({e:.2f}W, {n:.2f}N)")
            print(f"    Area: ~{area_km_sq:,.0f} km^2")
            print()

    @classmethod
    def get_region(cls, name: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Get bounding box for a named region.

        Args:
            name: Region name

        Returns:
            Tuple of (west, south, east, north) or None
        """
        return cls.REGIONS.get(name.lower())


def main():
    """Test the USA elevation data downloader."""
    downloader = USGSElevationDownloader()

    # Show available datasets
    downloader.print_dataset_info()

    # Show predefined regions
    USARegionBounds.list_regions()

    # Example: Download a small area around Denver
    print("\n" + "=" * 70)
    print("  EXAMPLE: Downloading Denver Area Elevation Data")
    print("=" * 70)

    denver_bbox = USARegionBounds.get_region('denver_area')
    if denver_bbox:
        result = downloader.download_via_national_map_api(
            denver_bbox,
            "denver_elevation_10m.tif",
            target_total_pixels=DEFAULT_TARGET_TOTAL_PIXELS
        )

        if result:
            print(f"\n  Success! Elevation data saved to: {result}")
            print("\nYou can now use this data with rasterio or GDAL to create visualizations.")
        else:
            print("\n  Download failed. Please try manual download from:")
            print("    https://apps.nationalmap.gov/downloader/")


if __name__ == "__main__":
    main()
