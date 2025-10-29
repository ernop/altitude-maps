"""
Download and prepare elevation data for multiple regions around the world.

This script downloads elevation data for various regions and prepares them
for the interactive web viewer.
"""
import sys
import io
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np

# NOTE: This is a library module that may be imported - DO NOT wrap sys.stdout/stderr
# Let calling scripts handle UTF-8 encoding via $env:PYTHONIOENCODING="utf-8"

try:
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    from rasterio.mask import mask
    import requests
    from tqdm import tqdm
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Install with: pip install rasterio requests tqdm")
    sys.exit(1)

# Import region definitions from centralized config
# All regions defined in src/regions_config.py
from src.regions_config import ALL_REGIONS, RegionConfig

# Convert RegionConfig objects to dict format for backward compatibility
REGIONS = {}
for region_id, config in ALL_REGIONS.items():
    REGIONS[region_id] = {
        "bounds": config.bounds,
        "name": config.name,
        "description": config.description or config.name,
        "clip_boundary": config.clip_boundary
    }


def download_srtm_for_bounds(bounds: tuple, output_file: Path) -> bool:
    """
    Download SRTM data for given bounds.
    Note: This is a simplified version. In practice, you'd use elevation-py or similar.
    """
    print(f"   Note: Auto-download not implemented in this version")
    print(f"   Please manually download SRTM data for these bounds: {bounds}")
    print(f"   Sources:")
    print(f"   - USGS EarthExplorer: https://earthexplorer.usgs.gov/")
    print(f"   - OpenTopography: https://opentopography.org/")
    print(f"   - SRTM: https://dwtkns.com/srtm30m/")
    return False


def process_region(region_id: str, region_info: Dict, data_dir: Path, output_dir: Path, max_size: int = 800):
    """
    Process elevation data for a specific region.
    """
    print(f"\n{'='*60}")
    print(f"Processing: {region_info['name']} ({region_id})")
    print(f"{'='*60}")
    
    # Look for existing elevation data
    possible_files = [
        data_dir / f"{region_id}_elevation.tif",
        data_dir / f"{region_id}.tif",
        data_dir / region_id / "elevation.tif"
    ]
    
    input_file = None
    for f in possible_files:
        if f.exists():
            input_file = f
            break
    
    if not input_file:
        print(f" No elevation data found for {region_id}")
        print(f"   Expected one of:")
        for f in possible_files:
            print(f"   - {f}")
        print(f"\n   To add this region:")
        print(f"   1. Download SRTM/ASTER data for bounds: {region_info['bounds']}")
        print(f"   2. Save as: {possible_files[0]}")
        return False
    
    print(f" Found: {input_file}")
    
    try:
        # Open and process
        with rasterio.open(input_file) as src:
            # Read data
            elevation = src.read(1)
            bounds = src.bounds
            
            print(f"   Original size: {src.width} x {src.height}")
            print(f"   Bounds: {bounds}")
            print(f"   Elevation range: {np.nanmin(elevation):.0f}m to {np.nanmax(elevation):.0f}m")
            print(f"   Aspect ratio: {src.width/src.height:.3f}")
            
            # Downsample if needed - PRESERVE ASPECT RATIO
            if max_size > 0 and (src.height > max_size or src.width > max_size):
                # Calculate step size based on the LARGER dimension to preserve aspect ratio
                scale_factor = max(src.height / max_size, src.width / max_size)
                step_size = max(1, int(scale_factor))
                
                elevation = elevation[::step_size, ::step_size]
                result_width, result_height = elevation.shape[1], elevation.shape[0]
                result_aspect = result_width / result_height
                
                print(f"   Downsampled to: {result_width} x {result_height} (step: {step_size})")
                print(f"   Result aspect ratio: {result_aspect:.3f}")
                
                # Validate aspect ratio preservation
                if abs(result_aspect - (src.width/src.height)) > 0.1:
                    print(f"   WARNING: Aspect ratio changed significantly!")
                    print(f"   Original: {src.width/src.height:.3f}, Result: {result_aspect:.3f}")
            
            height, width = elevation.shape
            
            # VALIDATION: Check aspect ratio before export
            export_aspect = width / height
            if abs(export_aspect - (src.width / src.height)) > 0.01:
                print(f"     WARNING: Aspect ratio mismatch detected!")
                print(f"      Source: {src.width / src.height:.3f}, Export: {export_aspect:.3f}")
                raise ValueError(f"Aspect ratio not preserved for {region_id}")
            
            # Convert to list
            elevation_list = []
            for row in elevation:
                row_list = []
                for val in row:
                    if np.isnan(val) or val < -500:  # Filter bad values
                        row_list.append(None)
                    else:
                        row_list.append(float(val))
                elevation_list.append(row_list)
            
            # Create export data
            export_data = {
                "region_id": region_id,
                "name": region_info['name'],
                "description": region_info['description'],
                "width": int(width),
                "height": int(height),
                "elevation": elevation_list,
                "bounds": {
                    "left": float(bounds.left),
                    "right": float(bounds.right),
                    "top": float(bounds.top),
                    "bottom": float(bounds.bottom)
                },
                "stats": {
                    "min": float(np.nanmin(elevation)),
                    "max": float(np.nanmax(elevation)),
                    "mean": float(np.nanmean(elevation))
                }
            }
            
            # Write JSON
            output_file = output_dir / f"{region_id}.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w') as f:
                json.dump(export_data, f, separators=(',', ':'))
            
            file_size_mb = output_file.stat().st_size / (1024 * 1024)
            print(f" Exported to: {output_file}")
            print(f"   File size: {file_size_mb:.2f} MB")
            print(f"   Data points: {width * height:,}")
            print(f"   Aspect ratio: {export_aspect:.3f} (validated)")
            
            return True
            
    except Exception as e:
        print(f" Error processing {region_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_regions_manifest(output_dir: Path, processed_regions: List[str]):
    """
    Create a manifest file listing all available regions.
    """
    manifest = {
        "version": "1.0",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "regions": {}
    }
    
    for region_id in processed_regions:
        if region_id in REGIONS:
            manifest["regions"][region_id] = {
                "name": REGIONS[region_id]["name"],
                "description": REGIONS[region_id]["description"],
                "bounds": REGIONS[region_id]["bounds"],
                "file": f"{region_id}.json"
            }
    
    manifest_file = output_dir / "regions_manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n Created manifest: {manifest_file}")
    print(f"   Total regions: {len(processed_regions)}")
    
    return manifest


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Download and prepare elevation data for multiple regions')
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/regions',
        help='Directory containing raw elevation TIF files'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='generated/regions',
        help='Output directory for processed JSON files'
    )
    parser.add_argument(
        '--max-size',
        type=int,
        default=800,
        help='Maximum dimension for output (0 = no downsampling)'
    )
    parser.add_argument(
        '--regions',
        type=str,
        nargs='+',
        help='Specific regions to process (default: all found)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available region definitions'
    )
    
    args = parser.parse_args()
    
    if args.list:
        print("\n📋 Available Region Definitions:")
        print("="*70)
        for region_id, info in sorted(REGIONS.items()):
            print(f"\n{region_id:20s} - {info['name']}")
            print(f"  {info['description']}")
            print(f"  Bounds: {info['bounds']}")
        print(f"\n{'='*70}")
        print(f"Total: {len(REGIONS)} regions defined")
        return 0
    
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    
    print(f"\n🗺  Multi-Region Elevation Data Processor")
    print(f"{'='*60}")
    print(f"Data directory: {data_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Max dimension: {args.max_size if args.max_size > 0 else 'FULL RESOLUTION'}")
    print(f"{'='*60}\n")
    
    # Determine which regions to process
    if args.regions:
        regions_to_process = args.regions
    else:
        # Look for all available data files
        regions_to_process = []
        for region_id in REGIONS.keys():
            possible_files = [
                data_dir / f"{region_id}_elevation.tif",
                data_dir / f"{region_id}.tif",
                data_dir / region_id / "elevation.tif"
            ]
            if any(f.exists() for f in possible_files):
                regions_to_process.append(region_id)
    
    if not regions_to_process:
        print(" No regions found to process!")
        print("\nTo get started:")
        print("1. Run with --list to see all region definitions")
        print("2. Download elevation data for desired regions")
        print(f"3. Place TIF files in: {data_dir}/")
        print("4. Run this script again")
        return 1
    
    print(f"Found {len(regions_to_process)} region(s) to process:")
    for rid in regions_to_process:
        print(f"  - {rid}: {REGIONS[rid]['name']}")
    print()
    
    # Process each region
    processed = []
    failed = []
    
    for region_id in regions_to_process:
        if region_id not in REGIONS:
            print(f"  Unknown region ID: {region_id}")
            continue
        
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
            failed.append(region_id)
    
    # Create manifest
    if processed:
        create_regions_manifest(output_dir, processed)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f" Successfully processed: {len(processed)} regions")
    if processed:
        for rid in processed:
            print(f"   - {REGIONS[rid]['name']}")
    
    if failed:
        print(f"\n Failed to process: {len(failed)} regions")
        for rid in failed:
            print(f"   - {rid}")
    
    print(f"\n{'='*60}")
    print(f"Next steps:")
    print(f"1. View regions at: {output_dir}/")
    print(f"2. Open interactive_viewer_advanced.html")
    print(f"3. Select regions from dropdown menu")
    print(f"{'='*60}\n")
    
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

