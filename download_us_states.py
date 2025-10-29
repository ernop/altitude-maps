"""
Download high-resolution elevation data for US states from OpenTopography.

Uses OpenTopography API to access USGS 3DEP data at 10m-30m resolution.
"""
import sys
import io
import requests
import time
from pathlib import Path
from typing import Tuple

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (AttributeError, ValueError):
        pass  # Already wrapped or unavailable

try:
    from tqdm import tqdm
except ImportError:
    print("Installing tqdm...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "tqdm"])
    from tqdm import tqdm

from download_regions import process_region, REGIONS
from load_settings import get_api_key, get_download_settings

# US States with precise bounds
US_STATES = {
    "california": {
        "bounds": (-124.48, 32.53, -114.13, 42.01),
        "name": "California",
        "description": "California - Sierra Nevada, Death Valley, Pacific Coast"
    },
    "new_jersey": {
        "bounds": (-75.56, 38.93, -73.89, 41.36),
        "name": "New Jersey",
        "description": "New Jersey - Pine Barrens, Delaware Water Gap"
    },
    "texas": {
        "bounds": (-106.65, 25.84, -93.51, 36.50),
        "name": "Texas",
        "description": "Texas - Big Bend, Hill Country, Gulf Coast"
    },
    "colorado": {
        "bounds": (-109.06, 36.99, -102.04, 41.00),
        "name": "Colorado",
        "description": "Colorado - Rocky Mountains, highest average elevation"
    },
    "washington": {
        "bounds": (-124.85, 45.54, -116.92, 49.05),
        "name": "Washington",
        "description": "Washington - Cascades, Mt. Rainier, Olympic Peninsula"
    },
    "oregon": {
        "bounds": (-124.57, 41.99, -116.46, 46.29),
        "name": "Oregon",
        "description": "Oregon - Cascades, Crater Lake, Coast Range"
    },
    "new_york": {
        "bounds": (-79.76, 40.50, -71.86, 45.02),
        "name": "New York",
        "description": "New York - Adirondacks, Catskills, Long Island"
    },
    "florida": {
        "bounds": (-87.63, 24.52, -80.03, 31.00),
        "name": "Florida",
        "description": "Florida - Mostly flat, Everglades, Keys"
    },
    "arizona": {
        "bounds": (-114.82, 31.33, -109.05, 37.00),
        "name": "Arizona",
        "description": "Arizona - Grand Canyon, Sonoran Desert"
    },
    "nevada": {
        "bounds": (-120.01, 35.00, -114.04, 42.00),
        "name": "Nevada",
        "description": "Nevada - Great Basin, Lake Tahoe"
    },
    "utah": {
        "bounds": (-114.05, 37.00, -109.04, 42.00),
        "name": "Utah",
        "description": "Utah - Wasatch Range, Canyon Country"
    },
    "montana": {
        "bounds": (-116.05, 44.36, -104.04, 49.00),
        "name": "Montana",
        "description": "Montana - Rocky Mountains, Glacier National Park"
    },
    "wyoming": {
        "bounds": (-111.06, 40.99, -104.05, 45.01),
        "name": "Wyoming",
        "description": "Wyoming - Yellowstone, Grand Tetons, High Plains"
    },
    "alaska": {
        "bounds": (-170.0, 51.0, -130.0, 71.5),
        "name": "Alaska",
        "description": "Alaska - Denali, Brooks Range, vast wilderness"
    },
    "hawaii": {
        "bounds": (-160.25, 18.91, -154.81, 22.24),
        "name": "Hawaii",
        "description": "Hawaii - Volcanic islands, Mauna Kea, Mauna Loa"
    }
}


def download_opentopography_region(region_id: str, bounds: Tuple[float, float, float, float], 
                                   output_file: Path, api_key: str = None) -> bool:
    """
    Download elevation data from OpenTopography API.
    
    Args:
        region_id: Region identifier  
        bounds: (west, south, east, north) in degrees
        output_file: Output file path
        api_key: OpenTopography API key (optional but recommended)
        
    Returns:
        True if successful
    """
    if output_file.exists():
        print(f"    Already exists: {output_file}")
        return True
    
    west, south, east, north = bounds
    
    # OpenTopography API endpoint for SRTM GL1 (30m global)
    # For US, this will use SRTM data
    url = "https://portal.opentopography.org/API/globaldem"
    
    params = {
        'demtype': 'SRTMGL1',  # SRTM 30m
        'south': south,
        'north': north,
        'west': west,
        'east': east,
        'outputFormat': 'GTiff'
    }
    
    # Add API key if provided
    if api_key:
        params['API_Key'] = api_key
        print(f"   🔑 Using API key: {api_key[:8]}...")
    
    print(f"   📥 Requesting from OpenTopography...")
    print(f"      Bounds: {west:.2f}W, {south:.2f}S, {east:.2f}E, {north:.2f}N")
    print(f"      Dataset: SRTM GL1 (30m resolution)")
    
    try:
        # Make request
        print(f"      Downloading... (this may take 30-60 seconds)")
        response = requests.get(url, params=params, stream=True, timeout=300)
        response.raise_for_status()
        
        # Get file size if available
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
        print(f"    Downloaded: {output_file}")
        print(f"      Size: {file_size_mb:.1f} MB")
        
        # Verify it's a valid file
        try:
            import rasterio
            with rasterio.open(output_file) as src:
                print(f"      Dimensions: {src.width} × {src.height}")
                print(f"      Resolution: ~30m")
        except Exception as e:
            print(f"     Warning: Could not verify file: {e}")
        
        return True
        
    except requests.exceptions.Timeout:
        print(f"    Download timeout (region may be too large)")
        print(f"      Try smaller regions or download manually from:")
        print(f"      https://portal.opentopography.org/raster?opentopoID=OTSRTM.082015.4326.1")
        return False
        
    except requests.exceptions.HTTPError as e:
        print(f"    HTTP Error: {e}")
        if e.response.status_code == 413:
            print(f"      Region too large for API. Try manual download:")
            print(f"      https://portal.opentopography.org/raster?opentopoID=OTSRTM.082015.4326.1")
        return False
        
    except Exception as e:
        print(f"    Download failed: {e}")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Download high-resolution elevation data for US states',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download California and New Jersey
  python download_us_states.py california new_jersey
  
  # Download and process to JSON
  python download_us_states.py california --process
  
  # List available states
  python download_us_states.py --list
  
  # Download specific states
  python download_us_states.py texas colorado arizona
        """
    )
    
    parser.add_argument(
        'states',
        nargs='*',
        help='State IDs to download (e.g., california, texas)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available US states'
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
        '--process',
        action='store_true',
        help='Also process to JSON after downloading'
    )
    parser.add_argument(
        '--max-size',
        type=int,
        default=1024,
        help='Maximum dimension for processed output (default: 1024 for high-res)'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        help='OpenTopography API key (overrides settings.json)'
    )
    
    args = parser.parse_args()
    
    # Get API key from args or settings.json
    if args.api_key:
        api_key = args.api_key
        print(f"   🔑 Using API key from command line")
    else:
        try:
            api_key = get_api_key()
            print(f"   🔑 Using API key from settings.json")
        except SystemExit:
            print("\n Tip: Add your API key to settings.json for automatic authentication")
            return 1
    
    if args.list:
        print("\n📋 Available US States:")
        print("="*70)
        for state_id, info in sorted(US_STATES.items(), key=lambda x: x[1]['name']):
            print(f"  {state_id:15s} - {info['name']:20s} {info['description']}")
        print(f"\nTotal: {len(US_STATES)} states available")
        print("\nResolution: ~30m (SRTM GL1)")
        print("Higher resolution (10m USGS 3DEP) requires manual download")
        return 0
    
    if not args.states:
        print(" No states specified!")
        print("Usage: python download_us_states.py <state1> <state2> ...")
        print("Or: python download_us_states.py --list")
        return 1
    
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    
    print(f"\n🗺  US State Elevation Downloader")
    print(f"="*70)
    print(f"States: {len(args.states)}")
    print(f"Data source: OpenTopography SRTM GL1 (30m)")
    print(f"Output: {data_dir}")
    print(f"="*70)
    
    downloaded = []
    failed = []
    
    for i, state_id in enumerate(args.states, 1):
        if state_id not in US_STATES:
            print(f"\n Unknown state: {state_id}")
            print(f"   Run with --list to see available states")
            failed.append(state_id)
            continue
        
        state_info = US_STATES[state_id]
        print(f"\n[{i}/{len(args.states)}] {state_info['name']} ({state_id})")
        print(f"   {state_info['description']}")
        
        output_file = data_dir / f"{state_id}.tif"
        success = download_opentopography_region(
            state_id,
            state_info['bounds'],
            output_file,
            api_key
        )
        
        if success:
            downloaded.append(state_id)
        else:
            failed.append(state_id)
        
        # Be nice to the API
        if i < len(args.states):
            time.sleep(2)
    
    # Process to JSON if requested
    processed = []
    if args.process and downloaded:
        print(f"\n🔄 Processing to JSON...")
        print(f"="*70)
        
        for state_id in downloaded:
            print(f"\nProcessing {state_id}...")
            
            # Merge state info into REGIONS for processing
            state_info = US_STATES[state_id]
            region_info = {
                "bounds": state_info["bounds"],
                "name": state_info["name"],
                "description": state_info["description"]
            }
            
            success = process_region(
                state_id,
                region_info,
                data_dir,
                output_dir,
                args.max_size
            )
            
            if success:
                processed.append(state_id)
        
        if processed:
            # Update manifest
            from download_regions import create_regions_manifest
            
            # Get existing regions
            manifest_file = output_dir / "regions_manifest.json"
            existing_regions = []
            if manifest_file.exists():
                import json
                with open(manifest_file) as f:
                    manifest = json.load(f)
                    existing_regions = list(manifest.get("regions", {}).keys())
            
            # Combine with newly processed
            all_regions = list(set(existing_regions + processed))
            create_regions_manifest(output_dir, all_regions)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    
    if downloaded:
        print(f" Downloaded: {len(downloaded)} states")
        for state_id in downloaded:
            print(f"   - {US_STATES[state_id]['name']}")
    
    if failed:
        print(f"\n Failed: {len(failed)} states")
        for state_id in failed:
            if state_id in US_STATES:
                print(f"   - {US_STATES[state_id]['name']}")
            else:
                print(f"   - {state_id} (unknown)")
    
    if args.process and processed:
        print(f"\n Processed: {len(processed)} states")
        print(f"\n{'='*70}")
        print("🎉 Ready! Open interactive_viewer_advanced.html")
        print("   Select states from the Region Selector dropdown")
    elif downloaded:
        print(f"\n{'='*70}")
        print("To process to JSON, run:")
        print(f"python download_us_states.py {' '.join(downloaded)} --process")
    
    print(f"{'='*70}\n")
    
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

