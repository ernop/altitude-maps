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
                'coverage': 'Global (60°N to 56°S)',
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
            print(f"📊 {info['name']}")
            print(f"   Resolution: {info['resolution']}")
            print(f"   Coverage:   {info['coverage']}")
            if 'url_info' in info:
                print(f"   Info:       {info['url_info']}")
            print(f"   Notes:      {info['description']}")
            print()
    
    def download_via_national_map_api(self, 
                                      bbox: Tuple[float, float, float, float],
                                      output_file: str = "elevation_sample.tif") -> Optional[Path]:
        """
        Download elevation data using USGS National Map API.
        
        Args:
            bbox: Bounding box (west, south, east, north) in decimal degrees
            output_file: Output filename
            
        Returns:
            Path to downloaded file or None if failed
        """
        west, south, east, north = bbox
        
        # USGS 3DEP ImageServer URL
        base_url = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
        
        params = {
            'bbox': f'{west},{south},{east},{north}',
            'bboxSR': '4326',  # WGS84
            'size': '1024,1024',  # Image size
            'imageSR': '4326',
            'format': 'tiff',
            'pixelType': 'F32',  # 32-bit float
            'noDataValue': '-9999',
            'interpolation': 'RSP_BilinearInterpolation',
            'f': 'image'
        }
        
        try:
            print(f"\n📥 Downloading elevation data for bbox: {bbox}")
            print(f"   Using USGS 3DEP ImageServer...")
            
            response = requests.get(base_url, params=params, stream=True)
            response.raise_for_status()
            
            output_path = self.data_dir / output_file
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(output_path, 'wb') as f, tqdm(
                desc=output_file,
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    pbar.update(size)
            
            print(f"✓ Downloaded: {output_path}")
            return output_path
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error downloading data: {e}")
            print("\nNote: For large downloads, consider using:")
            print("  1. USGS Earth Explorer: https://earthexplorer.usgs.gov/")
            print("  2. USGS National Map Downloader: https://apps.nationalmap.gov/downloader/")
            return None


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
            print(f"📍 {name.replace('_', ' ').title()}")
            print(f"   Bounds: ({w:.2f}°W, {s:.2f}°N) to ({e:.2f}°W, {n:.2f}°N)")
            print(f"   Area:   ~{area_km_sq:,.0f} km²")
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
            "denver_elevation_10m.tif"
        )
        
        if result:
            print(f"\n✓ Success! Elevation data saved to: {result}")
            print("\nYou can now use this data with rasterio or GDAL to create visualizations.")
        else:
            print("\n⚠ Download failed. Please try manual download from:")
            print("   https://apps.nationalmap.gov/downloader/")


if __name__ == "__main__":
    main()

