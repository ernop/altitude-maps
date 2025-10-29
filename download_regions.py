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

# Region definitions: name, bounds (left, bottom, right, top), description
REGIONS = {
    # Asia
    "japan": {
        "bounds": (129.0, 30.0, 146.0, 46.0),
        "name": "Japan",
        "description": "Japanese archipelago"
    },
    "estonia": {
        "bounds": (21.8, 57.5, 28.2, 59.7),
        "name": "Estonia",
        "description": "Republic of Estonia (Baltic)"
    },
    "gotland_island": {
        "bounds": (17.9, 56.8, 19.5, 58.2),
        "name": "Gotland Island",
        "description": "Sweden - Gotland (Baltic Sea)",
        "clip_boundary": False
    },
    "arkhangelsk_area": {
        "bounds": (36.0, 61.0, 50.0, 66.5),
        "name": "Arkhangelsk Area",
        "description": "Russia - Arkhangelsk Oblast and White Sea coast",
        "clip_boundary": False
    },
    "georgia_country": {
        "bounds": (40.0, 41.0, 46.8, 43.7),
        "name": "Georgia",
        "description": "Country of Georgia (Caucasus)"
    },
    "turkiye": {
        "bounds": (25.0, 35.8, 45.0, 42.3),
        "name": "Turkiye",
        "description": "Republic of Turkiye"
    },
    "kyrgyzstan": {
        "bounds": (69.2, 39.1, 80.3, 43.3),
        "name": "Kyrgyzstan",
        "description": "Kyrgyz Republic (Tian Shan)"
    },
    "sakhalin_island": {
        "bounds": (141.2, 45.6, 146.1, 54.6),
        "name": "Sakhalin Island",
        "description": "Russia - Sakhalin",
        "clip_boundary": False
    },
    "mindoro_island": {
        "bounds": (120.0, 12.0, 121.5, 13.7),
        "name": "Mindoro Island",
        "description": "Philippines - Mindoro",
        "clip_boundary": False
    },
    "singapore": {
        "bounds": (103.6, 1.16, 104.1, 1.48),
        "name": "Singapore",
        "description": "Republic of Singapore"
    },
    "hong_kong": {
        "bounds": (113.8, 22.15, 114.4, 22.6),
        "name": "Hong Kong",
        "description": "Hong Kong SAR",
        "clip_boundary": False
    },
    "shikoku": {
        "bounds": (132.155, 32.775, 134.8, 34.5),
        "name": "Shikoku Island",
        "description": "Shikoku - smallest of Japan's main islands",
        "clip_boundary": False
    },
    "china": {
        "bounds": (73.0, 18.0, 135.0, 54.0),
        "name": "China",
        "description": "Mainland China"
    },
    "south_korea": {
        "bounds": (124.0, 33.0, 132.0, 39.0),
        "name": "South Korea",
        "description": "Korean Peninsula (South)"
    },
    "india": {
        "bounds": (68.0, 6.0, 98.0, 36.0),
        "name": "India",
        "description": "Indian subcontinent"
    },
    "thailand": {
        "bounds": (97.0, 5.5, 106.0, 21.0),
        "name": "Thailand",
        "description": "Thailand"
    },
    "vietnam": {
        "bounds": (102.0, 8.0, 110.0, 24.0),
        "name": "Vietnam",
        "description": "Vietnam"
    },
    
    # Europe
    "germany": {
        "bounds": (5.8, 47.2, 15.1, 55.1),
        "name": "Germany",
        "description": "Germany"
    },
    "france": {
        "bounds": (-5.2, 41.3, 9.6, 51.1),
        "name": "France",
        "description": "France including Corsica"
    },
    "italy": {
        "bounds": (6.6, 36.6, 18.5, 47.1),
        "name": "Italy",
        "description": "Italy including Sicily and Sardinia"
    },
    "spain": {
        "bounds": (-9.3, 36.0, 3.3, 43.8),
        "name": "Spain",
        "description": "Spain"
    },
    "uk": {
        "bounds": (-8.2, 49.9, 1.8, 60.9),
        "name": "United Kingdom",
        "description": "Great Britain and Northern Ireland"
    },
    "poland": {
        "bounds": (14.1, 49.0, 24.2, 54.9),
        "name": "Poland",
        "description": "Poland"
    },
    "norway": {
        "bounds": (4.5, 58.0, 31.0, 71.3),
        "name": "Norway",
        "description": "Norway including Svalbard"
    },
    "sweden": {
        "bounds": (10.0, 55.3, 24.2, 69.1),
        "name": "Sweden",
        "description": "Sweden"
    },
    "switzerland": {
        "bounds": (5.9, 45.8, 10.5, 47.8),
        "name": "Switzerland",
        "description": "Switzerland - Alpine terrain"
    },
    "austria": {
        "bounds": (9.5, 46.4, 17.2, 49.0),
        "name": "Austria",
        "description": "Austria - Alpine terrain"
    },
    "greece": {
        "bounds": (19.4, 34.8, 28.3, 41.8),
        "name": "Greece",
        "description": "Greece including islands"
    },
    "netherlands": {
        "bounds": (3.3, 50.7, 7.2, 53.6),
        "name": "Netherlands",
        "description": "Netherlands - mostly flat"
    },
    
    # North America
    "usa_full": {
        "bounds": (-125.0, 24.0, -66.0, 49.5),
        "name": "USA (Contiguous)",
        "description": "Continental United States"
    },
    "anticosti_island": {
        "bounds": (-64.7, 48.9, -61.6, 50.0),
        "name": "Anticosti Island",
        "description": "Canada - Anticosti Island (Quebec)",
        "clip_boundary": False
    },
    "vancouver_island": {
        "bounds": (-129.0, 48.2, -123.0, 50.9),
        "name": "Vancouver Island",
        "description": "Canada - Vancouver Island (British Columbia)",
        "clip_boundary": False
    },
    "california": {
        "bounds": (-124.5, 32.5, -114.0, 42.0),
        "name": "California",
        "description": "California"
    },
    "texas": {
        "bounds": (-106.7, 25.8, -93.5, 36.5),
        "name": "Texas",
        "description": "Texas"
    },
    "colorado": {
        "bounds": (-109.1, 37.0, -102.0, 41.0),
        "name": "Colorado",
        "description": "Colorado - Rocky Mountains"
    },
    "washington": {
        "bounds": (-124.8, 45.5, -116.9, 49.0),
        "name": "Washington",
        "description": "Washington State"
    },
    "new_york": {
        "bounds": (-79.8, 40.5, -71.8, 45.0),
        "name": "New York",
        "description": "New York State"
    },
    "florida": {
        "bounds": (-87.6, 24.5, -80.0, 31.0),
        "name": "Florida",
        "description": "Florida - mostly flat"
    },
    "arizona": {
        "bounds": (-114.8, 31.3, -109.0, 37.0),
        "name": "Arizona",
        "description": "Arizona - Grand Canyon"
    },
    "alaska": {
        "bounds": (-170.0, 51.0, -130.0, 71.5),
        "name": "Alaska",
        "description": "Alaska"
    },
    "hawaii": {
        "bounds": (-160.3, 18.9, -154.8, 22.3),
        "name": "Hawaii",
        "description": "Hawaiian Islands"
    },
    "canada": {
        "bounds": (-141.0, 41.7, -52.6, 83.1),
        "name": "Canada",
        "description": "Canada"
    },
    "mexico": {
        "bounds": (-117.1, 14.5, -86.7, 32.7),
        "name": "Mexico",
        "description": "Mexico"
    },
    "las_malvinas": {
        "bounds": (-61.5, -53.2, -57.4, -50.9),
        "name": "Las Malvinas (Falkland Islands)",
        "description": "Falkland Islands / Islas Malvinas (UK territory)",
        "clip_boundary": False
    },
    "south_georgia_island": {
        "bounds": (-38.5, -55.1, -35.2, -53.5),
        "name": "South Georgia Island",
        "description": "South Georgia (Shackleton rescue at Grytviken)",
        "clip_boundary": False
    },
    
    # South America
    "brazil": {
        "bounds": (-74.0, -33.8, -34.8, 5.3),
        "name": "Brazil",
        "description": "Brazil"
    },
    "argentina": {
        "bounds": (-73.6, -55.1, -53.6, -21.8),
        "name": "Argentina",
        "description": "Argentina - Andes Mountains"
    },
    "chile": {
        "bounds": (-75.7, -56.0, -66.4, -17.5),
        "name": "Chile",
        "description": "Chile - Andes Mountains"
    },
    "peru": {
        "bounds": (-81.4, -18.4, -68.7, -0.0),
        "name": "Peru",
        "description": "Peru - Andes and Amazon"
    },
    
    # Oceania
    "australia": {
        "bounds": (113.0, -43.7, 153.7, -10.7),
        "name": "Australia",
        "description": "Australia"
    },
    "new_zealand": {
        "bounds": (166.0, -47.3, 178.6, -34.4),
        "name": "New Zealand",
        "description": "New Zealand - mountainous"
    },
    "tasmania": {
        "bounds": (144.0, -44.2, 149.0, -39.1),
        "name": "Tasmania",
        "description": "Tasmania (Australia) - island south of mainland",
        "clip_boundary": False
    },
    "new_caledonia": {
        "bounds": (163.5, -23.5, 168.5, -18.5),
        "name": "New Caledonia",
        "description": "New Caledonia archipelago",
        "clip_boundary": False
    },
    "canary_islands": {
        "bounds": (-18.5, 27.5, -13.4, 29.8),
        "name": "Canary Islands",
        "description": "Spain - Canary Islands (Atlantic archipelago)",
        "clip_boundary": False
    },
    
    # Africa
    "south_africa": {
        "bounds": (16.5, -34.9, 32.9, -22.1),
        "name": "South Africa",
        "description": "South Africa"
    },
    "egypt": {
        "bounds": (24.7, 22.0, 36.9, 31.7),
        "name": "Egypt",
        "description": "Egypt - mostly desert"
    },
    "kenya": {
        "bounds": (33.9, -4.7, 41.9, 5.5),
        "name": "Kenya",
        "description": "Kenya - Mt. Kilimanjaro region"
    },
    "angola": {
        "bounds": (11.5, -18.2, 24.1, -4.3),
        "name": "Angola",
        "description": "Republic of Angola"
    },
    
    # Middle East
    "israel": {
        "bounds": (34.3, 29.5, 35.9, 33.3),
        "name": "Israel",
        "description": "Israel and Palestine"
    },
    "saudi_arabia": {
        "bounds": (34.5, 16.4, 55.7, 32.2),
        "name": "Saudi Arabia",
        "description": "Saudi Arabia - desert terrain"
    },
    
    # Special regions
    "iceland": {
        "bounds": (-24.5, 63.4, -13.5, 66.6),
        "name": "Iceland",
        "description": "Iceland - volcanic terrain"
    },
    "faroe_islands": {
        "bounds": (-7.7, 61.4, -6.2, 62.4),
        "name": "Faroe Islands",
        "description": "Faroe Islands - North Atlantic archipelago",
        "clip_boundary": False  # Not in Natural Earth as separate country (territory of Denmark)
    },
    "kamchatka": {
        "bounds": (156.0, 50.5, 163.0, 62.5),
        "name": "Kamchatka Peninsula",
        "description": "Russia - Kamchatka Peninsula",
        "clip_boundary": False
    },
    "yakutsk_area": {
        "bounds": (124.0, 59.0, 136.0, 65.0),
        "name": "Yakutsk Area",
        "description": "Russia - Yakutsk and surrounding region",
        "clip_boundary": False
    },
    "yatusk_area": {  # alias for common misspelling
        "bounds": (124.0, 59.0, 136.0, 65.0),
        "name": "Yakutsk Area",
        "description": "Russia - Yakutsk and surrounding region",
        "clip_boundary": False
    },
    "san_mateo": {
        "bounds": (-122.6, 37.0, -121.8, 37.9),
        "name": "Peninsula",
        "description": "SF Peninsula: San Jose to San Francisco",
        "clip_boundary": False
    },
    "peninsula": {
        "bounds": (-122.53, 37.43, -122.24, 37.70),
        "name": "San Mateo",
        "description": "Union of Foster City, San Mateo, Burlingame, Half Moon Bay (approx bbox)",
        "clip_boundary": False
    },
    "nepal": {
        "bounds": (80.0, 26.3, 88.2, 30.4),
        "name": "Nepal",
        "description": "Nepal - Himalayas and Mt. Everest"
    },
    "alps": {
        "bounds": (5.0, 43.5, 17.0, 48.0),
        "name": "Alps",
        "description": "European Alps"
    },
    "rockies": {
        "bounds": (-116.0, 37.0, -102.0, 49.0),
        "name": "Rocky Mountains",
        "description": "US and Canadian Rockies"
    }
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

