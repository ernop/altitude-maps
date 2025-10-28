"""
Download Iceland elevation data using OpenTopography API.
Uses the API key from settings.json.
"""
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (AttributeError, ValueError):
        pass

try:
    import requests
    from tqdm import tqdm
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Install with: pip install requests tqdm")
    sys.exit(1)

from load_settings import get_api_key

# Iceland bounds: (west, south, east, north)
ICELAND_BOUNDS = (-24.5, 63.4, -13.5, 66.6)

def download_iceland_srtm(output_file: Path, api_key: str) -> bool:
    """
    Download SRTM 30m data for Iceland from OpenTopography.
    """
    if output_file.exists():
        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"   ✅ Already exists ({file_size_mb:.1f} MB)")
        return True
    
    west, south, east, north = ICELAND_BOUNDS
    
    # Calculate approximate size
    area_sq_deg = (east - west) * (north - south)
    approx_mb = area_sq_deg * 20  # Rough estimate
    
    print(f"\n{'='*70}")
    print(f"📥 Downloading Iceland Elevation Data")
    print(f"{'='*70}")
    print(f"   Bounds: {west}°W to {east}°W, {south}°N to {north}°N")
    print(f"   Area: {area_sq_deg:.1f} square degrees")
    print(f"   Estimated size: ~{approx_mb:.0f} MB")
    print(f"   Resolution: 30m (SRTM GL1)")
    print(f"   Source: OpenTopography")
    print(f"{'='*70}\n")
    
    # Prepare API request
    url = "https://portal.opentopography.org/API/globaldem"
    params = {
        'demtype': 'SRTMGL1',  # 30m SRTM data
        'south': south,
        'north': north,
        'west': west,
        'east': east,
        'outputFormat': 'GTiff',
        'API_Key': api_key
    }
    
    print(f"   🔑 Using API key from settings.json")
    print(f"   📡 Requesting data from OpenTopography...")
    print(f"      (This may take 30-120 seconds depending on server load)")
    
    try:
        # Make request with streaming to show progress
        response = requests.get(url, params=params, stream=True, timeout=300)
        
        if response.status_code != 200:
            print(f"\n   ❌ API Error: {response.status_code}")
            print(f"      Response: {response.text[:500]}")
            return False
        
        # Get file size from headers
        total_size = int(response.headers.get('content-length', 0))
        
        # Create output directory
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Download with progress bar
        print(f"\n   📥 Downloading...")
        with open(output_file, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
        
        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"\n   ✅ Downloaded successfully!")
        print(f"      File: {output_file}")
        print(f"      Size: {file_size_mb:.1f} MB")
        
        return True
        
    except requests.exceptions.Timeout:
        print(f"\n   ❌ Download timed out (server may be slow)")
        print(f"      Try again in a few minutes")
        return False
    except Exception as e:
        print(f"\n   ❌ Download failed: {e}")
        if output_file.exists():
            output_file.unlink()  # Clean up partial download
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Download Iceland elevation data')
    parser.add_argument('--output', '-o', 
                       default='data/raw/srtm_30m/iceland_bbox_30m.tif',
                       help='Output file path (default: data/raw/srtm_30m/iceland_bbox_30m.tif)')
    
    args = parser.parse_args()
    
    # Get API key from settings.json
    try:
        api_key = get_api_key('opentopography')
        print(f"✓ Found OpenTopography API key in settings.json")
    except SystemExit:
        print(f"\n{'='*70}")
        print(f"❌ ERROR: No OpenTopography API key found!")
        print(f"{'='*70}")
        print(f"\nYour settings.json appears to be missing or invalid.")
        print(f"\nTo fix:")
        print(f"1. Get a free API key from: https://portal.opentopography.org/")
        print(f"2. Add it to settings.json under 'opentopography.api_key'")
        print(f"{'='*70}\n")
        return 1
    
    output_file = Path(args.output)
    
    # Download
    success = download_iceland_srtm(output_file, api_key)
    
    if success:
        print(f"\n{'='*70}")
        print(f"✅ SUCCESS - Iceland data ready!")
        print(f"{'='*70}")
        print(f"\nNext steps:")
        print(f"  1. Process it:")
        print(f"     python export_for_web_viewer.py {output_file} --mask-country Iceland")
        print(f"\n  2. Or use the pipeline:")
        print(f"     python ensure_region.py iceland")
        print(f"     (Will need to extend ensure_region.py to support Iceland)")
        print(f"{'='*70}\n")
        return 0
    else:
        print(f"\n{'='*70}")
        print(f"❌ FAILED - Could not download Iceland data")
        print(f"{'='*70}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

