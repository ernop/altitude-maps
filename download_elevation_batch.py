"""
Batch download elevation data from public sources for multiple regions.

This script uses the 'elevation' package which downloads SRTM data automatically.
Install with: pip install elevation
"""
import sys
import io
import subprocess
from pathlib import Path
import json

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Check for elevation package
try:
    import elevation
except ImportError:
    print("❌ 'elevation' package not installed")
    print("\nInstalling required packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "elevation"])
    print("✅ Installation complete. Please run the script again.")
    sys.exit(0)

# Import after potential installation
import rasterio
import numpy as np

# Import regions from download_regions
from download_regions import REGIONS, process_region

def download_srtm_for_region(region_id: str, bounds: tuple, output_dir: Path) -> Path:
    """
    Download SRTM elevation data for a region using the elevation package.
    
    Args:
        region_id: Region identifier
        bounds: (left, bottom, right, top) in degrees
        output_dir: Directory to save the downloaded file
    
    Returns:
        Path to downloaded TIF file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{region_id}.tif"
    
    # Skip if already exists
    if output_file.exists():
        print(f"   ✅ Already exists: {output_file}")
        return output_file
    
    print(f"   📥 Downloading SRTM data for {region_id}...")
    print(f"      Bounds: {bounds}")
    
    try:
        # Use elevation package to download SRTM data
        # Format: --bounds left bottom right top
        elevation.clip(
            bounds=bounds,
            output=str(output_file),
            product='SRTM3'  # 3 arc-second (~90m) resolution
        )
        
        if output_file.exists():
            print(f"   ✅ Downloaded: {output_file}")
            # Check file
            with rasterio.open(output_file) as src:
                print(f"      Size: {src.width} × {src.height}")
                print(f"      Resolution: ~{90}m")
            return output_file
        else:
            print(f"   ❌ Download failed - file not created")
            return None
            
    except Exception as e:
        print(f"   ❌ Download failed: {e}")
        return None


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Download elevation data for multiple regions from public sources',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download and process all regions (will take a while!)
  python download_elevation_batch.py --all
  
  # Download specific regions
  python download_elevation_batch.py japan germany france
  
  # Download and skip processing (just download raw data)
  python download_elevation_batch.py --regions japan china --no-process
  
  # Download with custom resolution
  python download_elevation_batch.py california texas --max-size 1024
  
Notes:
  - This uses SRTM 90m global elevation data
  - First run will be slow as it downloads ~25GB of SRTM tiles
  - Subsequent runs use cached tiles (much faster)
  - Coverage: 60°N to 56°S (most of the world)
  - For areas outside SRTM coverage, manual download needed
        """
    )
    
    parser.add_argument(
        'regions',
        nargs='*',
        help='Region IDs to download (see --list for options)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Download all defined regions (WARNING: Large download!)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available regions'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/regions',
        help='Directory to save downloaded TIF files'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='generated/regions',
        help='Directory for processed JSON files'
    )
    parser.add_argument(
        '--max-size',
        type=int,
        default=800,
        help='Maximum dimension for processed output (0 = full resolution)'
    )
    parser.add_argument(
        '--no-process',
        action='store_true',
        help='Only download, skip processing to JSON'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Re-download even if files exist'
    )
    
    args = parser.parse_args()
    
    if args.list:
        print("\n📋 Available Regions for Download:")
        print("="*70)
        
        # Group by category
        categories = {}
        for region_id, info in REGIONS.items():
            # Determine category
            if region_id.startswith('usa_') or region_id in ['california', 'texas', 'colorado', 'washington', 'new_york', 'florida', 'arizona', 'alaska', 'hawaii']:
                cat = 'USA'
            elif region_id in ['japan', 'china', 'south_korea', 'india', 'thailand', 'vietnam', 'nepal']:
                cat = 'Asia'
            elif region_id in ['germany', 'france', 'italy', 'spain', 'uk', 'poland', 'norway', 'sweden', 'switzerland', 'austria', 'greece', 'netherlands', 'iceland']:
                cat = 'Europe'
            elif region_id in ['brazil', 'argentina', 'chile', 'peru']:
                cat = 'South America'
            elif region_id in ['australia', 'new_zealand']:
                cat = 'Oceania'
            else:
                cat = 'Other'
            
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((region_id, info))
        
        for cat in ['USA', 'Europe', 'Asia', 'South America', 'Oceania', 'Other']:
            if cat not in categories:
                continue
            print(f"\n{cat}:")
            for region_id, info in sorted(categories[cat], key=lambda x: x[1]['name']):
                print(f"  {region_id:20s} - {info['name']:30s} {info['description']}")
        
        print(f"\n{'='*70}")
        print(f"Total: {len(REGIONS)} regions")
        print(f"\nUsage: python download_elevation_batch.py japan germany france")
        return 0
    
    # Determine regions to download
    if args.all:
        regions_to_download = list(REGIONS.keys())
        print(f"\n⚠️  WARNING: Downloading ALL {len(regions_to_download)} regions!")
        print("This will download several GB of data and may take hours.")
        response = input("Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cancelled.")
            return 0
    elif args.regions:
        regions_to_download = args.regions
        # Validate
        invalid = [r for r in regions_to_download if r not in REGIONS]
        if invalid:
            print(f"❌ Unknown regions: {', '.join(invalid)}")
            print("Run with --list to see available regions")
            return 1
    else:
        print("❌ No regions specified!")
        print("Usage: python download_elevation_batch.py <region1> <region2> ...")
        print("Or: python download_elevation_batch.py --all")
        print("Or: python download_elevation_batch.py --list")
        return 1
    
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    
    print(f"\n🌍 Batch Elevation Data Downloader")
    print(f"="*70)
    print(f"Regions to download: {len(regions_to_download)}")
    print(f"Data source: SRTM 90m (NASA)")
    print(f"Download directory: {data_dir}")
    print(f"Output directory: {output_dir}")
    print(f"="*70)
    
    # Download phase
    print(f"\n📥 PHASE 1: Downloading elevation data...")
    print(f"="*70)
    
    downloaded_files = {}
    failed_downloads = []
    
    for i, region_id in enumerate(regions_to_download, 1):
        region_info = REGIONS[region_id]
        print(f"\n[{i}/{len(regions_to_download)}] {region_info['name']} ({region_id})")
        
        if args.force:
            # Delete existing file
            existing_file = data_dir / f"{region_id}.tif"
            if existing_file.exists():
                existing_file.unlink()
                print(f"   🗑️  Deleted existing file (--force)")
        
        result = download_srtm_for_region(
            region_id,
            region_info['bounds'],
            data_dir
        )
        
        if result:
            downloaded_files[region_id] = result
        else:
            failed_downloads.append(region_id)
    
    # Processing phase
    if not args.no_process and downloaded_files:
        print(f"\n🔄 PHASE 2: Processing to JSON...")
        print(f"="*70)
        
        processed = []
        failed_processing = []
        
        for i, (region_id, tif_file) in enumerate(downloaded_files.items(), 1):
            print(f"\n[{i}/{len(downloaded_files)}] Processing {region_id}...")
            
            success = process_region(
                region_id,
                REGIONS[region_id],
                data_dir,
                output_dir,
                args.max_size
            )
            
            if success:
                processed.append(region_id)
            else:
                failed_processing.append(region_id)
        
        # Create manifest
        if processed:
            from download_regions import create_regions_manifest
            create_regions_manifest(output_dir, processed)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    
    if downloaded_files:
        print(f"✅ Successfully downloaded: {len(downloaded_files)} regions")
        for rid in downloaded_files.keys():
            print(f"   - {REGIONS[rid]['name']}")
    
    if failed_downloads:
        print(f"\n❌ Failed downloads: {len(failed_downloads)} regions")
        for rid in failed_downloads:
            print(f"   - {rid} ({REGIONS[rid]['name']})")
    
    if not args.no_process:
        if processed:
            print(f"\n✅ Successfully processed: {len(processed)} regions")
        if failed_processing:
            print(f"\n❌ Failed processing: {len(failed_processing)} regions")
    
    print(f"\n{'='*70}")
    print(f"Next steps:")
    print(f"1. Open interactive_viewer_advanced.html")
    print(f"2. Select region from dropdown menu")
    print(f"3. Explore elevation data interactively!")
    print(f"{'='*70}\n")
    
    return 0 if not (failed_downloads or failed_processing) else 1


if __name__ == "__main__":
    sys.exit(main())

