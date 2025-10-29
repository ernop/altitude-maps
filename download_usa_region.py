"""
Download real USA elevation data for predefined regions.

Usage:
    python download_usa_region.py denver_area
    python download_usa_region.py colorado_rockies
    python download_usa_region.py --list
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from usa_elevation_data import USGSElevationDownloader, USARegionBounds


def main():
    parser = argparse.ArgumentParser(
        description='Download USA elevation data for predefined regions'
    )
    parser.add_argument(
        'region',
        nargs='?',
        help='Region name (e.g., denver_area, colorado_rockies)'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available regions'
    )
    parser.add_argument(
        '--output-dir',
        default='data/usa_elevation',
        help='Output directory for downloads'
    )
    
    args = parser.parse_args()
    
    if args.list or not args.region:
        print("\n📋 Available regions for download:\n")
        USARegionBounds.list_regions()
        
        if not args.region:
            print("\nUsage: python download_usa_region.py <region_name>")
            print("Example: python download_usa_region.py denver_area")
        return
    
    # Get region bounds
    bbox = USARegionBounds.get_region(args.region)
    if not bbox:
        print(f" Error: Region '{args.region}' not found.")
        print("\nRun with --list to see available regions.")
        return 1
    
    # Download data
    downloader = USGSElevationDownloader(args.output_dir)
    
    print(f"\n🗺  Downloading: {args.region.replace('_', ' ').title()}")
    print(f"   Bounds: {bbox}")
    print(f"   Source: USGS 3DEP (~10m resolution)")
    
    output_file = f"{args.region}_elevation_10m.tif"
    result = downloader.download_via_national_map_api(bbox, output_file)
    
    if result:
        print(f"\n Success!")
        print(f"   File: {result}")
        print(f"\n   Next step: Visualize with:")
        print(f"   python visualize_real_data.py {result}")
    else:
        print(f"\n Download failed.")
        print(f"\n   Try manual download from:")
        print(f"   https://apps.nationalmap.gov/downloader/")
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)

