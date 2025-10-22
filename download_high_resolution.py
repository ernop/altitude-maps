"""
Download high-resolution elevation data from OpenTopography for specific regions.

Supports multiple datasets:
- SRTM GL1: 30m global (default)
- SRTM GL3: 90m global
- NASADEM: 30m global (improved SRTM)
- ALOS World 3D: 30m global (excellent for mountains/Asia)
- COP30: 30m global (Copernicus)
- COP90: 90m global (Copernicus)

For US regions, can also access USGS 3DEP at 10m through manual download instructions.
"""
import sys
import requests
import time
from pathlib import Path
from typing import Tuple, Dict
import json

try:
    from tqdm import tqdm
    import rasterio
    import numpy as np
except ImportError as e:
    print(f"Missing package: {e}")
    print("Install with: pip install tqdm rasterio numpy")
    sys.exit(1)

from download_regions import process_region, REGIONS, create_regions_manifest
from load_settings import get_api_key


# Available datasets from OpenTopography
DATASETS = {
    'SRTMGL1': {
        'name': 'SRTM GL1 (30m)',
        'resolution': '30m',
        'coverage': 'Global (60°N-56°S)',
        'description': 'NASA SRTM 30m - good quality, global coverage'
    },
    'SRTMGL3': {
        'name': 'SRTM GL3 (90m)',
        'resolution': '90m',
        'coverage': 'Global (60°N-56°S)',
        'description': 'NASA SRTM 90m - lower resolution'
    },
    'AW3D30': {
        'name': 'ALOS World 3D (30m)',
        'resolution': '30m',
        'coverage': 'Global (82°N-82°S)',
        'description': 'JAXA ALOS 30m - excellent for mountains and Asia'
    },
    'NASADEM': {
        'name': 'NASADEM (30m)',
        'resolution': '30m',
        'coverage': 'Global (60°N-56°S)',
        'description': 'Improved SRTM with void-filling'
    },
    'COP30': {
        'name': 'Copernicus DEM (30m)',
        'resolution': '30m',
        'coverage': 'Global (90°N-90°S)',
        'description': 'ESA Copernicus 30m - excellent global coverage'
    },
    'COP90': {
        'name': 'Copernicus DEM (90m)',
        'resolution': '90m',
        'coverage': 'Global (90°N-90°S)',
        'description': 'ESA Copernicus 90m - full polar coverage'
    }
}

# Special high-resolution regions
HIGH_RES_REGIONS = {
    # Japan regions
    'shikoku': {
        'bounds': (132.5, 33.0, 134.8, 34.5),
        'name': 'Shikoku',
        'description': 'Shikoku island, Japan - smallest main island',
        'recommended_dataset': 'AW3D30'
    },
    'hokkaido': {
        'bounds': (139.0, 41.0, 146.0, 46.0),
        'name': 'Hokkaido',
        'description': 'Hokkaido, Japan - northernmost main island',
        'recommended_dataset': 'AW3D30'
    },
    'honshu': {
        'bounds': (129.0, 33.0, 142.0, 42.0),
        'name': 'Honshu',
        'description': 'Honshu, Japan - largest main island',
        'recommended_dataset': 'AW3D30'
    },
    'kyushu': {
        'bounds': (129.0, 31.0, 132.0, 34.5),
        'name': 'Kyushu',
        'description': 'Kyushu, Japan - southern main island',
        'recommended_dataset': 'AW3D30'
    },
    
    # California (split into regions due to API size limits)
    'california_north': {
        'bounds': (-124.5, 39.0, -119.0, 42.0),
        'name': 'Northern California',
        'description': 'Northern California - Cascade Range, Mount Shasta',
        'recommended_dataset': 'SRTMGL1'
    },
    'california_central': {
        'bounds': (-122.5, 36.0, -117.5, 39.0),
        'name': 'Central California',
        'description': 'Central California - Sierra Nevada, Yosemite, Lake Tahoe',
        'recommended_dataset': 'SRTMGL1'
    },
    'california_south': {
        'bounds': (-121.0, 32.5, -114.0, 36.0),
        'name': 'Southern California',
        'description': 'Southern California - San Bernardino Mountains, Death Valley',
        'recommended_dataset': 'SRTMGL1'
    },
    'california_coast': {
        'bounds': (-124.5, 34.0, -119.5, 39.5),
        'name': 'California Coast',
        'description': 'California Coast - San Francisco Bay Area, Big Sur',
        'recommended_dataset': 'SRTMGL1'
    },
    
    # Other high-interest regions
    'alps': {
        'bounds': (5.0, 43.5, 17.0, 48.0),
        'name': 'European Alps',
        'description': 'European Alps - highest peaks in Europe',
        'recommended_dataset': 'AW3D30'
    },
    'nepal': {
        'bounds': (80.0, 26.3, 88.2, 30.4),
        'name': 'Nepal',
        'description': 'Nepal - Himalayas and Mt. Everest',
        'recommended_dataset': 'AW3D30'
    },
    'new_zealand': {
        'bounds': (166.0, -47.3, 178.6, -34.4),
        'name': 'New Zealand',
        'description': 'New Zealand - Southern Alps',
        'recommended_dataset': 'AW3D30'
    }
}


def download_from_opentopography(region_id: str, bounds: Tuple[float, float, float, float],
                                 output_file: Path, api_key: str, dataset: str = 'SRTMGL1') -> bool:
    """
    Download elevation data from OpenTopography API.
    
    Args:
        region_id: Region identifier
        bounds: (west, south, east, north) in degrees
        output_file: Output file path
        api_key: OpenTopography API key
        dataset: Dataset to download (SRTMGL1, AW3D30, etc.)
    
    Returns:
        True if successful
    """
    if output_file.exists():
        print(f"   ✅ Already exists: {output_file.name}")
        return True
    
    west, south, east, north = bounds
    
    # Calculate approximate size
    lat_diff = north - south
    lon_diff = east - west
    approx_area_sq_km = lat_diff * lon_diff * 111 * 111 * abs(np.cos(np.radians((north + south) / 2)))
    
    print(f"   📥 Downloading from OpenTopography...")
    print(f"      Region: {region_id}")
    print(f"      Bounds: {west:.2f}°W to {east:.2f}°E, {south:.2f}°S to {north:.2f}°N")
    print(f"      Dataset: {DATASETS[dataset]['name']}")
    print(f"      Approx area: {approx_area_sq_km:,.0f} km²")
    
    # Check size limits (warn but allow)
    if approx_area_sq_km > 500000:
        print(f"   ⚠️  WARNING: Very large region ({approx_area_sq_km:,.0f} km²)")
        print(f"      This may take several minutes or exceed API limits...")
        print(f"      Attempting download anyway...")
    
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
        print(f"      Requesting data... (may take 30-120 seconds)")
        response = requests.get(url, params=params, stream=True, timeout=600)
        response.raise_for_status()
        
        # Get file size
        total_size = int(response.headers.get('content-length', 0))
        
        # Download with progress bar
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'wb') as f:
            if total_size == 0:
                f.write(response.content)
            else:
                with tqdm(total=total_size, unit='B', unit_scale=True, desc="      Progress") as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))
        
        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"   ✅ Downloaded: {output_file.name}")
        print(f"      Size: {file_size_mb:.1f} MB")
        
        # Verify
        try:
            with rasterio.open(output_file) as src:
                print(f"      Dimensions: {src.width} × {src.height}")
                print(f"      CRS: {src.crs}")
                
                # Calculate actual resolution
                pixel_width = (src.bounds.right - src.bounds.left) / src.width
                pixel_height = (src.bounds.top - src.bounds.bottom) / src.height
                res_m = pixel_width * 111000  # Approximate meters
                print(f"      Resolution: ~{res_m:.0f}m")
        except Exception as e:
            print(f"   ⚠️  Could not verify file: {e}")
        
        return True
        
    except requests.exceptions.Timeout:
        print(f"   ❌ Download timeout (region may be too large)")
        return False
        
    except requests.exceptions.HTTPError as e:
        print(f"   ❌ HTTP Error {e.response.status_code}: {e}")
        if e.response.status_code == 413:
            print(f"      Region too large for API")
        elif e.response.status_code == 400:
            print(f"      Bad request - check bounds and dataset")
        return False
        
    except Exception as e:
        print(f"   ❌ Download failed: {e}")
        return False


def print_usgs_3dep_instructions(region_name: str, bounds: Tuple[float, float, float, float]):
    """
    Print instructions for manually downloading USGS 3DEP 10m data.
    """
    west, south, east, north = bounds
    
    print(f"\n{'='*70}")
    print(f"🇺🇸 For 10m USGS 3DEP data for {region_name}:")
    print(f"{'='*70}")
    print(f"\nOption 1: USGS National Map Downloader (Recommended)")
    print(f"  1. Go to: https://apps.nationalmap.gov/downloader/")
    print(f"  2. Zoom to your area of interest")
    print(f"  3. Click 'Find Products'")
    print(f"  4. Select 'Elevation Products (3DEP)'")
    print(f"  5. Choose '1/3 arc-second DEM' (10m)")
    print(f"  6. Download and extract to: data/regions/{region_name.lower().replace(' ', '_')}.tif")
    print(f"\nOption 2: OpenTopography (Bulk Access)")
    print(f"  1. Go to: https://portal.opentopography.org/")
    print(f"  2. Search for 'USGS 3DEP'")
    print(f"  3. Enter bounds: {west:.4f}, {south:.4f}, {east:.4f}, {north:.4f}")
    print(f"  4. Request data (may need to wait for processing)")
    print(f"\nOption 3: AWS Open Data (Advanced)")
    print(f"  USGS 3DEP is available on AWS S3 (free egress)")
    print(f"  Bucket: s3://prd-tnm/")
    print(f"{'='*70}\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Download high-resolution elevation data from OpenTopography',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download Shikoku, Japan with ALOS (best for Japan)
  python download_high_resolution.py shikoku --dataset AW3D30
  
  # Download California (30m via API)
  python download_high_resolution.py california --dataset SRTMGL1
  
  # Get instructions for 10m California data
  python download_high_resolution.py california --usgs-instructions
  
  # Download and process multiple regions
  python download_high_resolution.py shikoku california alps --process
  
  # List available regions and datasets
  python download_high_resolution.py --list-regions
  python download_high_resolution.py --list-datasets
  
  # Custom region with specific bounds
  python download_high_resolution.py custom_region --bounds -120 35 -119 36 --dataset COP30

Notes:
  - Requires OpenTopography API key in settings.json
  - API has size limits (~4 degrees per request)
  - For US 10m data, use --usgs-instructions for manual download steps
  - ALOS World 3D (AW3D30) is best for mountains and Asia
  - Copernicus (COP30/COP90) has full polar coverage
        """
    )
    
    parser.add_argument(
        'regions',
        nargs='*',
        help='Region IDs to download (see --list-regions)'
    )
    parser.add_argument(
        '--list-regions',
        action='store_true',
        help='List all available high-resolution regions'
    )
    parser.add_argument(
        '--list-datasets',
        action='store_true',
        help='List all available datasets'
    )
    parser.add_argument(
        '--dataset',
        type=str,
        default='SRTMGL1',
        choices=list(DATASETS.keys()),
        help='Dataset to download (default: SRTMGL1)'
    )
    parser.add_argument(
        '--bounds',
        type=float,
        nargs=4,
        metavar=('WEST', 'SOUTH', 'EAST', 'NORTH'),
        help='Custom bounds (west, south, east, north) in degrees'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/regions',
        help='Directory to save downloaded files'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='generated/regions',
        help='Directory for processed JSON files'
    )
    parser.add_argument(
        '--process',
        action='store_true',
        help='Process to JSON after downloading'
    )
    parser.add_argument(
        '--max-size',
        type=int,
        default=2048,
        help='Maximum dimension for processed output (default: 2048 for high-res)'
    )
    parser.add_argument(
        '--usgs-instructions',
        action='store_true',
        help='Show instructions for downloading 10m USGS 3DEP data'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        help='OpenTopography API key (overrides settings.json)'
    )
    
    args = parser.parse_args()
    
    # List datasets
    if args.list_datasets:
        print("\n📊 Available Datasets from OpenTopography:")
        print("="*70)
        for dataset_id, info in DATASETS.items():
            print(f"\n{dataset_id:12s} - {info['name']}")
            print(f"  Resolution: {info['resolution']}")
            print(f"  Coverage: {info['coverage']}")
            print(f"  {info['description']}")
        print(f"\n{'='*70}")
        print("\n💡 Recommendations:")
        print("  - For Japan/Asia: AW3D30 (ALOS)")
        print("  - For mountains: AW3D30 (ALOS)")
        print("  - For polar regions: COP30 or COP90")
        print("  - For general use: SRTMGL1 or NASADEM")
        print("  - For US 10m: See --usgs-instructions\n")
        return 0
    
    # List regions
    if args.list_regions:
        print("\n🗺️  High-Resolution Regions:")
        print("="*70)
        
        # Group by category
        categories = {
            'Japan': [],
            'USA': [],
            'Mountains': [],
            'Other': []
        }
        
        for region_id, info in HIGH_RES_REGIONS.items():
            if 'japan' in region_id.lower() or region_id in ['shikoku', 'hokkaido', 'honshu', 'kyushu']:
                categories['Japan'].append((region_id, info))
            elif 'california' in region_id.lower():
                categories['USA'].append((region_id, info))
            elif region_id in ['alps', 'nepal', 'new_zealand']:
                categories['Mountains'].append((region_id, info))
            else:
                categories['Other'].append((region_id, info))
        
        for cat_name, regions in categories.items():
            if regions:
                print(f"\n{cat_name}:")
                for region_id, info in sorted(regions, key=lambda x: x[1]['name']):
                    print(f"  {region_id:20s} - {info['name']:30s}")
                    print(f"    {info['description']}")
                    print(f"    Recommended: {info['recommended_dataset']} ({DATASETS[info['recommended_dataset']]['name']})")
        
        print(f"\n{'='*70}")
        print(f"Total: {len(HIGH_RES_REGIONS)} specialized regions")
        print("\n💡 You can also use any region from download_regions.py")
        print("   Or define custom bounds with --bounds\n")
        return 0
    
    # Get API key
    if args.api_key:
        api_key = args.api_key
    else:
        try:
            api_key = get_api_key()
        except SystemExit:
            print("\n❌ OpenTopography API key required!")
            print("\nGet a free API key:")
            print("  1. Go to: https://portal.opentopography.org/")
            print("  2. Create account (free)")
            print("  3. Get API key from your account page")
            print("  4. Add to settings.json or use --api-key\n")
            return 1
    
    # USGS instructions only
    if args.usgs_instructions:
        if not args.regions:
            print("❌ Specify region(s) for USGS instructions")
            return 1
        
        for region_id in args.regions:
            if region_id in HIGH_RES_REGIONS:
                info = HIGH_RES_REGIONS[region_id]
                print_usgs_3dep_instructions(info['name'], info['bounds'])
            elif region_id in REGIONS:
                info = REGIONS[region_id]
                print_usgs_3dep_instructions(info['name'], info['bounds'])
            else:
                print(f"❌ Unknown region: {region_id}")
        return 0
    
    # Validate regions
    if not args.regions and not args.bounds:
        print("❌ No regions specified!")
        print("Usage: python download_high_resolution.py <region1> <region2> ...")
        print("Or: python download_high_resolution.py --list-regions")
        print("Or: python download_high_resolution.py --bounds -120 35 -119 36")
        return 1
    
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    
    print(f"\n🌍 High-Resolution Elevation Downloader")
    print(f"="*70)
    print(f"Dataset: {DATASETS[args.dataset]['name']}")
    print(f"Resolution: {DATASETS[args.dataset]['resolution']}")
    print(f"Output: {data_dir}")
    print(f"="*70)
    
    # Prepare regions to download
    regions_to_download = []
    
    if args.bounds:
        # Custom bounds
        custom_name = args.regions[0] if args.regions else 'custom_region'
        regions_to_download.append({
            'id': custom_name,
            'bounds': tuple(args.bounds),
            'name': custom_name.replace('_', ' ').title(),
            'description': 'Custom region'
        })
    else:
        # Named regions
        for region_id in args.regions:
            if region_id in HIGH_RES_REGIONS:
                info = HIGH_RES_REGIONS[region_id]
                regions_to_download.append({
                    'id': region_id,
                    'bounds': info['bounds'],
                    'name': info['name'],
                    'description': info['description']
                })
            elif region_id in REGIONS:
                info = REGIONS[region_id]
                regions_to_download.append({
                    'id': region_id,
                    'bounds': info['bounds'],
                    'name': info['name'],
                    'description': info['description']
                })
            else:
                print(f"❌ Unknown region: {region_id}")
                print("   Use --list-regions to see available regions")
                return 1
    
    # Download each region
    downloaded = []
    failed = []
    
    for i, region in enumerate(regions_to_download, 1):
        print(f"\n[{i}/{len(regions_to_download)}] {region['name']} ({region['id']})")
        print(f"   {region['description']}")
        
        output_file = data_dir / f"{region['id']}.tif"
        success = download_from_opentopography(
            region['id'],
            region['bounds'],
            output_file,
            api_key,
            args.dataset
        )
        
        if success:
            downloaded.append(region['id'])
        else:
            failed.append(region['id'])
        
        # Rate limiting
        if i < len(regions_to_download):
            print("   ⏳ Waiting 3 seconds (API rate limit)...")
            time.sleep(3)
    
    # Process to JSON
    processed = []
    if args.process and downloaded:
        print(f"\n🔄 Processing to JSON...")
        print(f"="*70)
        
        for region_id in downloaded:
            print(f"\nProcessing {region_id}...")
            
            # Get region info
            if region_id in HIGH_RES_REGIONS:
                region_info = HIGH_RES_REGIONS[region_id]
            elif region_id in REGIONS:
                region_info = REGIONS[region_id]
            else:
                # Custom region
                region_info = {
                    'bounds': args.bounds,
                    'name': region_id.replace('_', ' ').title(),
                    'description': 'Custom region'
                }
            
            success = process_region(
                region_id,
                region_info,
                data_dir,
                output_dir,
                args.max_size
            )
            
            if success:
                processed.append(region_id)
        
        if processed:
            # Update manifest
            manifest_file = output_dir / "regions_manifest.json"
            existing_regions = []
            if manifest_file.exists():
                with open(manifest_file) as f:
                    manifest = json.load(f)
                    existing_regions = list(manifest.get("regions", {}).keys())
            
            all_regions = list(set(existing_regions + processed))
            create_regions_manifest(output_dir, all_regions)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    
    if downloaded:
        print(f"✅ Downloaded: {len(downloaded)} region(s)")
        for region_id in downloaded:
            file_path = data_dir / f"{region_id}.tif"
            size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"   - {region_id} ({size_mb:.1f} MB)")
    
    if failed:
        print(f"\n❌ Failed: {len(failed)} region(s)")
        for region_id in failed:
            print(f"   - {region_id}")
    
    if args.process and processed:
        print(f"\n✅ Processed: {len(processed)} region(s) to JSON")
        print(f"\n🎉 Ready! Open interactive_viewer_advanced.html")
    elif downloaded:
        print(f"\n💡 To process to JSON, run:")
        print(f"   python download_high_resolution.py {' '.join(downloaded)} --process")
    
    if any('california' in r for r in args.regions or []):
        print(f"\n💡 For 10m USGS 3DEP data (better than 30m):")
        print(f"   python download_high_resolution.py california --usgs-instructions")
    
    print(f"\n{'='*70}\n")
    
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

