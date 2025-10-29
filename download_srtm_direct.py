"""
Direct SRTM downloader that works on Windows without 'make'.
Downloads SRTM tiles directly from OpenTopography via HTTP.
"""
import sys
import io
import requests
from pathlib import Path
from typing import Tuple
import time

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    import rasterio
    from rasterio.merge import merge
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    from rasterio.io import MemoryFile
    import numpy as np
    from tqdm import tqdm
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Install with: pip install rasterio requests tqdm")
    sys.exit(1)

from download_regions import REGIONS, process_region, create_regions_manifest


def get_srtm_tile_name(lon: float, lat: float) -> str:
    """
    Get SRTM tile name for a given coordinate.
    Format: N/S{lat}E/W{lon}.hgt
    """
    lat_char = 'N' if lat >= 0 else 'S'
    lon_char = 'E' if lon >= 0 else 'W'
    
    lat_str = f"{abs(int(lat)):02d}"
    lon_str = f"{abs(int(lon)):03d}"
    
    return f"{lat_char}{lat_str}{lon_char}{lon_str}.hgt"


def download_srtm_tile(tile_name: str, cache_dir: Path) -> Path:
    """
    Download a single SRTM tile from OpenTopography.
    """
    cache_file = cache_dir / tile_name
    
    if cache_file.exists():
        return cache_file
    
    # OpenTopography SRTM3 URL
    base_url = "https://cloud.sdsc.edu/v1/AUTH_opentopography/Raster/SRTM_GL3/SRTM_GL3_hgt/North/"
    
    # Extract latitude from tile name for directory
    lat_str = tile_name[1:3]
    url = f"{base_url}N{lat_str}/{tile_name}"
    
    print(f"      Downloading {tile_name}...", end='', flush=True)
    
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(" ")
        return cache_file
        
    except Exception as e:
        print(f"  ({e})")
        return None


def download_region_srtm(region_id: str, bounds: Tuple[float, float, float, float], 
                         output_file: Path, cache_dir: Path) -> bool:
    """
    Download and mosaic SRTM tiles for a region.
    
    Args:
        region_id: Region identifier
        bounds: (left, bottom, right, top) in degrees
        output_file: Output GeoTIFF file
        cache_dir: Directory for caching downloaded tiles
    
    Returns:
        True if successful
    """
    if output_file.exists():
        print(f"    Already exists: {output_file}")
        return True
    
    left, bottom, right, top = bounds
    
    # Calculate required tiles
    tiles_needed = []
    for lat in range(int(bottom), int(top) + 1):
        for lon in range(int(left), int(right) + 1):
            tile_name = get_srtm_tile_name(lon, lat)
            tiles_needed.append((tile_name, lon, lat))
    
    print(f"   📥 Need {len(tiles_needed)} SRTM tiles")
    
    if len(tiles_needed) > 50:
        print(f"     Warning: Large region requires {len(tiles_needed)} tiles")
        print(f"   This may take a while...")
    
    # Download tiles
    downloaded_tiles = []
    for tile_name, lon, lat in tiles_needed:
        tile_file = download_srtm_tile(tile_name, cache_dir)
        if tile_file and tile_file.exists():
            downloaded_tiles.append(tile_file)
    
    if not downloaded_tiles:
        print(f"    No tiles downloaded successfully")
        return False
    
    print(f"    Downloaded {len(downloaded_tiles)}/{len(tiles_needed)} tiles")
    
    # Convert .hgt files to GeoTIFF and merge
    print(f"   🔄 Processing and merging tiles...")
    
    try:
        src_files = []
        for hgt_file in downloaded_tiles:
            # Read .hgt file (binary elevation data)
            data = np.fromfile(hgt_file, dtype='>i2')  # Big-endian 16-bit integers
            size = int(np.sqrt(len(data)))
            data = data.reshape(size, size)
            
            # Get coordinates from filename
            filename = hgt_file.stem
            lat_val = int(filename[1:3])
            lon_val = int(filename[4:7])
            if filename[0] == 'S':
                lat_val = -lat_val
            if filename[3] == 'W':
                lon_val = -lon_val
            
            # Create GeoTIFF in memory
            transform = rasterio.transform.from_bounds(
                lon_val, lat_val, lon_val + 1, lat_val + 1,
                size, size
            )
            
            memfile = MemoryFile()
            with memfile.open(
                driver='GTiff',
                height=size,
                width=size,
                count=1,
                dtype=data.dtype,
                crs='EPSG:4326',
                transform=transform
            ) as dataset:
                dataset.write(data, 1)
            
            src_files.append(memfile.open())
        
        # Merge tiles
        mosaic, out_transform = merge(src_files, bounds=bounds)
        
        # Write output
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(
            output_file,
            'w',
            driver='GTiff',
            height=mosaic.shape[1],
            width=mosaic.shape[2],
            count=1,
            dtype=mosaic.dtype,
            crs='EPSG:4326',
            transform=out_transform,
            compress='lzw'
        ) as dst:
            dst.write(mosaic[0], 1)
        
        # Clean up
        for src in src_files:
            src.close()
        
        print(f"    Saved: {output_file}")
        print(f"      Size: {mosaic.shape[2]} × {mosaic.shape[1]}")
        
        return True
        
    except Exception as e:
        print(f"    Error processing tiles: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Download SRTM elevation data directly (Windows-compatible)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download specific regions
  python download_srtm_direct.py japan germany
  
  # Download and process
  python download_srtm_direct.py switzerland --process
  
  # List available regions
  python download_srtm_direct.py --list
        """
    )
    
    parser.add_argument(
        'regions',
        nargs='*',
        help='Region IDs to download'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available regions'
    )
    parser.add_argument(
        '--cache-dir',
        type=str,
        default='data/srtm_cache',
        help='Directory for caching SRTM tiles'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/regions',
        help='Directory to save regional TIF files'
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
        default=800,
        help='Maximum dimension for processed output'
    )
    
    args = parser.parse_args()
    
    if args.list:
        print("\n📋 Available Regions:")
        print("="*70)
        for region_id, info in sorted(REGIONS.items(), key=lambda x: x[1]['name']):
            print(f"  {region_id:20s} - {info['name']}")
        print(f"\nTotal: {len(REGIONS)} regions")
        return 0
    
    if not args.regions:
        print(" No regions specified!")
        print("Usage: python download_srtm_direct.py <region1> <region2> ...")
        print("Or: python download_srtm_direct.py --list")
        return 1
    
    cache_dir = Path(args.cache_dir)
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    
    print(f"\n🌍 SRTM Direct Downloader (Windows-compatible)")
    print(f"="*70)
    print(f"Regions: {len(args.regions)}")
    print(f"Cache: {cache_dir}")
    print(f"Output: {data_dir}")
    print(f"="*70)
    
    downloaded = []
    failed = []
    
    for i, region_id in enumerate(args.regions, 1):
        if region_id not in REGIONS:
            print(f"\n Unknown region: {region_id}")
            failed.append(region_id)
            continue
        
        region_info = REGIONS[region_id]
        print(f"\n[{i}/{len(args.regions)}] {region_info['name']} ({region_id})")
        print(f"   Bounds: {region_info['bounds']}")
        
        output_file = data_dir / f"{region_id}.tif"
        success = download_region_srtm(
            region_id,
            region_info['bounds'],
            output_file,
            cache_dir
        )
        
        if success:
            downloaded.append(region_id)
        else:
            failed.append(region_id)
    
    # Process to JSON if requested
    if args.process and downloaded:
        print(f"\n🔄 Processing to JSON...")
        print(f"="*70)
        
        processed = []
        for region_id in downloaded:
            print(f"\nProcessing {region_id}...")
            success = process_region(
                region_id,
                REGIONS[region_id],
                data_dir,
                output_dir,
                args.max_size
            )
            if success:
                processed.append(region_id)
        
        if processed:
            create_regions_manifest(output_dir, processed)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f" Downloaded: {len(downloaded)}")
    if downloaded:
        for rid in downloaded:
            print(f"   - {REGIONS[rid]['name']}")
    
    if failed:
        print(f"\n Failed: {len(failed)}")
        for rid in failed:
            if rid in REGIONS:
                print(f"   - {REGIONS[rid]['name']}")
            else:
                print(f"   - {rid} (unknown)")
    
    print(f"\n{'='*70}")
    if args.process and processed:
        print(" Ready! Open interactive_viewer_advanced.html")
    else:
        print("To process to JSON, run with --process flag")
    print(f"{'='*70}\n")
    
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

