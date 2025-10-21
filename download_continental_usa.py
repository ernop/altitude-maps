"""
Download elevation data for the entire continental USA.

The full continental USA is very large, so this uses appropriate resolution
and provides options for downloading in sections.
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from usa_elevation_data import USGSElevationDownloader, USARegionBounds


def main():
    parser = argparse.ArgumentParser(
        description='Download elevation data for continental USA'
    )
    parser.add_argument(
        '--region',
        default='nationwide_usa',
        choices=['nationwide_usa', 'continental_usa', 'usa_west', 'usa_east'],
        help='Region to download (default: complete nationwide USA)'
    )
    parser.add_argument(
        '--output-dir',
        default='data/usa_elevation',
        help='Output directory for downloads'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("  CONTINENTAL USA ELEVATION DATA DOWNLOADER")
    print("=" * 70)
    
    # Get region bounds
    bbox = USARegionBounds.get_region(args.region)
    if not bbox:
        print(f"❌ Error: Region '{args.region}' not found.")
        return 1
    
    west, south, east, north = bbox
    area_deg_sq = (east - west) * (north - south)
    
    print(f"\n📍 Region: {args.region.replace('_', ' ').title()}")
    print(f"   Bounds: {west:.1f}°W to {east:.1f}°W, {south:.1f}°N to {north:.1f}°N")
    print(f"   Area: {area_deg_sq:.1f} square degrees")
    
    if args.region in ['nationwide_usa', 'continental_usa']:
        print("\n⚠️  NOTE: Full continental USA is VERY LARGE!")
        print("   Recommended approach:")
        print("   1. Download in sections (usa_west, usa_east)")
        print("   2. Or use lower resolution for overview")
        print("\n   This download will request the full area at available resolution.")
        print("   The file will be large (expect 50-200 MB).")
        
        if not args.yes:
            try:
                response = input("\n   Continue with full USA download? [y/N]: ")
                if response.lower() != 'y':
                    print("\n   Cancelled. Try:")
                    print("   python download_continental_usa.py --region usa_west")
                    print("   python download_continental_usa.py --region usa_east")
                    return 0
            except EOFError:
                print("\n\n   Non-interactive mode detected. Use --yes flag to proceed.")
                print("   Example: python download_continental_usa.py --yes")
                return 0
    
    # Download data
    downloader = USGSElevationDownloader(args.output_dir)
    
    print(f"\n🗺️  Downloading...")
    print(f"   Source: USGS 3DEP")
    print(f"   Starting download (this may take several minutes)...")
    
    output_file = f"{args.region}_elevation.tif"
    result = downloader.download_via_national_map_api(bbox, output_file)
    
    if result:
        print(f"\n✅ Success!")
        print(f"   File: {result}")
        print(f"\n   Visualize with:")
        print(f"   python visualize_real_data.py {result}")
    else:
        print(f"\n❌ Download failed or timed out.")
        print(f"\n   For very large areas, try manual download:")
        print(f"   1. Go to: https://apps.nationalmap.gov/downloader/")
        print(f"   2. Select 'Elevation Products (3DEP)'")
        print(f"   3. Draw your area of interest")
        print(f"   4. Choose '1 arc-second' (30m) for full USA coverage")
        print(f"   5. Download and save to: {args.output_dir}/")
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)

