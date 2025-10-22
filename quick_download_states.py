"""
Quick downloader for California and New Jersey using public SRTM mirrors.
Downloads tiles directly from USGS public servers.
"""
import sys
import io
import requests
import numpy as np
from pathlib import Path
from typing import List, Tuple

# Fix Windows console encoding  
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    import rasterio
    from rasterio.merge import merge
    from rasterio.io import MemoryFile
    from tqdm import tqdm
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Install with: pip install rasterio tqdm")
    sys.exit(1)


def get_srtm_tiles_for_bounds(bounds: Tuple[float, float, float, float]) -> List[Tuple[int, int]]:
    """
    Get list of SRTM tile coordinates for given bounds.
    Returns list of (lat, lon) tuples for tile lower-left corners.
    """
    west, south, east, north = bounds
    tiles = []
    
    for lat in range(int(np.floor(south)), int(np.ceil(north))):
        for lon in range(int(np.floor(west)), int(np.ceil(east))):
            tiles.append((lat, lon))
    
    return tiles


def download_srtm_tile(lat: int, lon: int, cache_dir: Path) -> Path:
    """
    Download a single SRTM tile from public server.
    """
    # Determine tile name
    lat_str = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}"
    lon_str = f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}"
    tile_name = f"{lat_str}{lon_str}.hgt"
    
    cache_file = cache_dir / tile_name
    if cache_file.exists():
        return cache_file
    
    # Try multiple SRTM mirrors
    urls = [
        f"https://srtm.csi.cgiar.org/wp-content/uploads/files/srtm_5x5/TIFF/{tile_name.replace('.hgt', '.tif')}",
        f"http://e4ftl01.cr.usgs.gov/MODV6_Dal_D/SRTM/SRTMGL1.003/2000.02.11/{tile_name}.zip"
    ]
    
    print(f"   Downloading {tile_name}...", end='', flush=True)
    
    for url in urls:
        try:
            response = requests.get(url, timeout=30, stream=True)
            if response.status_code == 200:
                cache_dir.mkdir(parents=True, exist_ok=True)
                
                total = int(response.headers.get('content-length', 0))
                with open(cache_file, 'wb') as f:
                    if total == 0:
                        f.write(response.content)
                    else:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                
                print(" ✅")
                return cache_file
        except:
            continue
    
    print(" ❌ (not available)")
    return None


# Quick helper: Use existing USA data and just process regions
def create_state_from_usa():
    """
    Alternative: Extract California and NJ from existing USA data.
    This is much faster!
    """
    print("\n💡 Alternative Approach: Extract from existing USA data")
    print("="*70)
    
    usa_file = Path("data/usa_elevation/nationwide_usa_elevation.tif")
    if not usa_file.exists():
        print("❌ USA data not found at data/usa_elevation/nationwide_usa_elevation.tif")
        return False
    
    print(f"✅ Found USA data: {usa_file}")
    
    try:
        import rasterio
        from rasterio.windows import from_bounds
        
        with rasterio.open(usa_file) as src:
            print(f"   USA bounds: {src.bounds}")
            
            # California bounds
            ca_bounds = (-124.48, 32.53, -114.13, 42.01)
            print(f"\n📍 Extracting California...")
            print(f"   Bounds: {ca_bounds}")
            
            ca_window = from_bounds(*ca_bounds, src.transform)
            ca_data = src.read(1, window=ca_window)
            ca_transform = src.window_transform(ca_window)
            
            # Save California
            ca_file = Path("data/regions/california.tif")
            ca_file.parent.mkdir(parents=True, exist_ok=True)
            
            with rasterio.open(
                ca_file, 'w',
                driver='GTiff',
                height=ca_data.shape[0],
                width=ca_data.shape[1],
                count=1,
                dtype=ca_data.dtype,
                crs=src.crs,
                transform=ca_transform,
                compress='lzw'
            ) as dst:
                dst.write(ca_data, 1)
            
            print(f"   ✅ Saved: {ca_file}")
            print(f"   Size: {ca_data.shape[1]} × {ca_data.shape[0]}")
            
            # New Jersey bounds
            nj_bounds = (-75.56, 38.93, -73.89, 41.36)
            print(f"\n📍 Extracting New Jersey...")
            print(f"   Bounds: {nj_bounds}")
            
            nj_window = from_bounds(*nj_bounds, src.transform)
            nj_data = src.read(1, window=nj_window)
            nj_transform = src.window_transform(nj_window)
            
            # Save New Jersey
            nj_file = Path("data/regions/new_jersey.tif")
            
            with rasterio.open(
                nj_file, 'w',
                driver='GTiff',
                height=nj_data.shape[0],
                width=nj_data.shape[1],
                count=1,
                dtype=nj_data.dtype,
                crs=src.crs,
                transform=nj_transform,
                compress='lzw'
            ) as dst:
                dst.write(nj_data, 1)
            
            print(f"   ✅ Saved: {nj_file}")
            print(f"   Size: {nj_data.shape[1]} × {nj_data.shape[0]}")
            
            print(f"\n✅ Success! Extracted both states from USA data")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n🚀 Quick State Data Extractor")
    print("="*70)
    print("This will extract California and New Jersey from existing USA data.")
    print("Much faster than downloading separate files!")
    print("="*70)
    
    # Try to extract from existing USA data
    if create_state_from_usa():
        print("\n🔄 Now processing to JSON...")
        print("="*70)
        
        from download_regions import process_region, create_regions_manifest
        from download_us_states import US_STATES
        
        data_dir = Path("data/regions")
        output_dir = Path("generated/regions")
        
        processed = []
        
        for state_id in ["california", "new_jersey"]:
            print(f"\nProcessing {state_id}...")
            state_info = US_STATES[state_id]
            
            success = process_region(
                state_id,
                state_info,
                data_dir,
                output_dir,
                max_size=1024  # Higher resolution for states
            )
            
            if success:
                processed.append(state_id)
        
        if processed:
            # Update manifest
            manifest_file = output_dir / "regions_manifest.json"
            existing_regions = ["usa_full"]  # We know this exists
            if manifest_file.exists():
                import json
                with open(manifest_file) as f:
                    manifest = json.load(f)
                    existing_regions = list(manifest.get("regions", {}).keys())
            
            all_regions = list(set(existing_regions + processed))
            create_regions_manifest(output_dir, all_regions)
            
            print(f"\n{'='*70}")
            print(f"✅ SUCCESS!")
            print(f"{'='*70}")
            print(f"Processed: {', '.join(processed)}")
            print(f"\n🎉 Ready to use!")
            print(f"   1. Open interactive_viewer_advanced.html")
            print(f"   2. Select 'California' or 'New Jersey' from dropdown")
            print(f"   3. Explore high-resolution terrain!")
            print(f"{'='*70}\n")
    else:
        print("\n❌ Could not extract states from USA data")
        print("Please follow manual download instructions in DOWNLOAD_US_STATES_GUIDE.md")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

