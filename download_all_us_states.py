"""
Download and process all US state elevation data.

This script extracts all 50 US states from the nationwide USA elevation data
and processes them for the interactive web viewer.
"""
import sys
import io
import json
import numpy as np
from pathlib import Path
from typing import Dict, List

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
    import rasterio
    from rasterio.windows import from_bounds
    from tqdm import tqdm
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Install with: pip install rasterio tqdm")
    sys.exit(1)

# All 50 US States (contiguous 48 + Alaska + Hawaii)
US_STATES = {
    # Western States
    "california": {
        "bounds": (-124.48, 32.53, -114.13, 42.01),
        "name": "California",
        "description": "California - Sierra Nevada, Death Valley, Pacific Coast"
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
    "nevada": {
        "bounds": (-120.01, 35.00, -114.04, 42.00),
        "name": "Nevada",
        "description": "Nevada - Great Basin, Lake Tahoe"
    },
    "arizona": {
        "bounds": (-114.82, 31.33, -109.05, 37.00),
        "name": "Arizona",
        "description": "Arizona - Grand Canyon, Sonoran Desert"
    },
    "utah": {
        "bounds": (-114.05, 37.00, -109.04, 42.00),
        "name": "Utah",
        "description": "Utah - Wasatch Range, Canyon Country"
    },
    "idaho": {
        "bounds": (-117.24, 41.99, -111.04, 49.00),
        "name": "Idaho",
        "description": "Idaho - Rocky Mountains, Snake River Plain"
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
    "colorado": {
        "bounds": (-109.06, 36.99, -102.04, 41.00),
        "name": "Colorado",
        "description": "Colorado - Rocky Mountains, highest average elevation"
    },
    "new_mexico": {
        "bounds": (-109.05, 31.33, -103.00, 37.00),
        "name": "New Mexico",
        "description": "New Mexico - Southern Rockies, deserts, mesas"
    },
    
    # Midwest States
    "north_dakota": {
        "bounds": (-104.05, 45.94, -96.55, 49.00),
        "name": "North Dakota",
        "description": "North Dakota - Great Plains, mostly flat"
    },
    "south_dakota": {
        "bounds": (-104.06, 42.48, -96.44, 45.95),
        "name": "South Dakota",
        "description": "South Dakota - Black Hills, Badlands, Great Plains"
    },
    "nebraska": {
        "bounds": (-104.05, 40.00, -95.31, 43.00),
        "name": "Nebraska",
        "description": "Nebraska - Great Plains, Sand Hills"
    },
    "kansas": {
        "bounds": (-102.05, 36.99, -94.59, 40.00),
        "name": "Kansas",
        "description": "Kansas - Great Plains, largely flat"
    },
    "oklahoma": {
        "bounds": (-103.00, 33.62, -94.43, 37.00),
        "name": "Oklahoma",
        "description": "Oklahoma - Great Plains, Ouachita Mountains"
    },
    "texas": {
        "bounds": (-106.65, 25.84, -93.51, 36.50),
        "name": "Texas",
        "description": "Texas - Big Bend, Hill Country, Gulf Coast"
    },
    "minnesota": {
        "bounds": (-97.24, 43.50, -89.49, 49.38),
        "name": "Minnesota",
        "description": "Minnesota - 10,000 lakes, northern forests"
    },
    "iowa": {
        "bounds": (-96.64, 40.38, -90.14, 43.50),
        "name": "Iowa",
        "description": "Iowa - Rolling plains, farmland"
    },
    "missouri": {
        "bounds": (-95.77, 35.99, -89.10, 40.61),
        "name": "Missouri",
        "description": "Missouri - Ozark Plateau, Great Plains"
    },
    "arkansas": {
        "bounds": (-94.62, 33.00, -89.64, 36.50),
        "name": "Arkansas",
        "description": "Arkansas - Ozarks, Ouachita Mountains"
    },
    "louisiana": {
        "bounds": (-94.04, 28.93, -88.82, 33.02),
        "name": "Louisiana",
        "description": "Louisiana - Mississippi Delta, bayous, mostly flat"
    },
    "wisconsin": {
        "bounds": (-92.89, 42.49, -86.25, 47.31),
        "name": "Wisconsin",
        "description": "Wisconsin - Lakes, rolling hills, northern highlands"
    },
    "illinois": {
        "bounds": (-91.51, 36.97, -87.02, 42.51),
        "name": "Illinois",
        "description": "Illinois - Great Plains, mostly flat farmland"
    },
    "michigan": {
        "bounds": (-90.42, 41.70, -82.42, 48.31),
        "name": "Michigan",
        "description": "Michigan - Great Lakes, Upper/Lower Peninsula"
    },
    "indiana": {
        "bounds": (-88.10, 37.77, -84.78, 41.76),
        "name": "Indiana",
        "description": "Indiana - Rolling plains, farmland"
    },
    "ohio": {
        "bounds": (-84.82, 38.40, -80.52, 41.98),
        "name": "Ohio",
        "description": "Ohio - Appalachian foothills, Great Lakes"
    },
    
    # Southern States
    "mississippi": {
        "bounds": (-91.66, 30.17, -88.10, 35.00),
        "name": "Mississippi",
        "description": "Mississippi - Delta plains, Gulf Coast"
    },
    "alabama": {
        "bounds": (-88.47, 30.22, -84.89, 35.01),
        "name": "Alabama",
        "description": "Alabama - Appalachian foothills, Gulf Coast"
    },
    "tennessee": {
        "bounds": (-90.31, 34.98, -81.65, 36.68),
        "name": "Tennessee",
        "description": "Tennessee - Smoky Mountains, Cumberland Plateau"
    },
    "kentucky": {
        "bounds": (-89.57, 36.50, -81.96, 39.15),
        "name": "Kentucky",
        "description": "Kentucky - Appalachian Mountains, Bluegrass region"
    },
    "georgia": {
        "bounds": (-85.61, 30.36, -80.84, 35.00),
        "name": "Georgia",
        "description": "Georgia - Appalachian foothills, coastal plains"
    },
    "florida": {
        "bounds": (-87.63, 24.52, -80.03, 31.00),
        "name": "Florida",
        "description": "Florida - Mostly flat, Everglades, Keys"
    },
    "south_carolina": {
        "bounds": (-83.35, 32.04, -78.54, 35.22),
        "name": "South Carolina",
        "description": "South Carolina - Blue Ridge foothills, coastal plains"
    },
    "north_carolina": {
        "bounds": (-84.32, 33.84, -75.46, 36.59),
        "name": "North Carolina",
        "description": "North Carolina - Blue Ridge Mountains, Outer Banks"
    },
    
    # Eastern States
    "virginia": {
        "bounds": (-83.68, 36.54, -75.24, 39.47),
        "name": "Virginia",
        "description": "Virginia - Blue Ridge, Shenandoah Valley, Chesapeake"
    },
    "west_virginia": {
        "bounds": (-82.64, 37.20, -77.72, 40.64),
        "name": "West Virginia",
        "description": "West Virginia - Appalachian Mountains, very rugged"
    },
    "maryland": {
        "bounds": (-79.49, 37.91, -75.05, 39.72),
        "name": "Maryland",
        "description": "Maryland - Chesapeake Bay, Appalachian ridge"
    },
    "delaware": {
        "bounds": (-75.79, 38.45, -75.05, 39.84),
        "name": "Delaware",
        "description": "Delaware - Atlantic coastal plain, mostly flat"
    },
    "new_jersey": {
        "bounds": (-75.56, 38.93, -73.89, 41.36),
        "name": "New Jersey",
        "description": "New Jersey - Pine Barrens, Delaware Water Gap"
    },
    "pennsylvania": {
        "bounds": (-80.52, 39.72, -74.69, 42.27),
        "name": "Pennsylvania",
        "description": "Pennsylvania - Allegheny Mountains, Pocono Plateau"
    },
    "new_york": {
        "bounds": (-79.76, 40.50, -71.86, 45.02),
        "name": "New York",
        "description": "New York - Adirondacks, Catskills, Long Island"
    },
    "connecticut": {
        "bounds": (-73.73, 40.95, -71.79, 42.05),
        "name": "Connecticut",
        "description": "Connecticut - Rolling hills, Long Island Sound"
    },
    "rhode_island": {
        "bounds": (-71.91, 41.10, -71.12, 42.02),
        "name": "Rhode Island",
        "description": "Rhode Island - Coastal plains, Narragansett Bay"
    },
    "massachusetts": {
        "bounds": (-73.51, 41.24, -69.93, 42.89),
        "name": "Massachusetts",
        "description": "Massachusetts - Berkshire Hills, Cape Cod"
    },
    "vermont": {
        "bounds": (-73.44, 42.73, -71.47, 45.02),
        "name": "Vermont",
        "description": "Vermont - Green Mountains, Lake Champlain"
    },
    "new_hampshire": {
        "bounds": (-72.56, 42.70, -70.61, 45.31),
        "name": "New Hampshire",
        "description": "New Hampshire - White Mountains, Mt. Washington"
    },
    "maine": {
        "bounds": (-71.08, 42.98, -66.95, 47.46),
        "name": "Maine",
        "description": "Maine - Appalachian Trail terminus, rugged coast"
    },
    
    # Non-contiguous
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

# States available in the contiguous USA dataset
CONTIGUOUS_STATES = [k for k, v in US_STATES.items() if k not in ['alaska', 'hawaii']]


def extract_state_from_usa(state_id: str, state_info: Dict, usa_file: Path, output_file: Path) -> bool:
    """
    Extract a state's elevation data from the nationwide USA file.
    """
    try:
        with rasterio.open(usa_file) as src:
            bounds = state_info["bounds"]
            west, south, east, north = bounds
            
            # Check if bounds overlap with source data
            if (west > src.bounds.right or east < src.bounds.left or
                south > src.bounds.top or north < src.bounds.bottom):
                print(f"     State bounds don't overlap with USA data")
                return False
            
            # Get window for this state
            window = from_bounds(west, south, east, north, src.transform)
            
            # Read the data
            data = src.read(1, window=window)
            transform = src.window_transform(window)
            
            # Save the state's data
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with rasterio.open(
                output_file, 'w',
                driver='GTiff',
                height=data.shape[0],
                width=data.shape[1],
                count=1,
                dtype=data.dtype,
                crs=src.crs,
                transform=transform,
                compress='lzw'
            ) as dst:
                dst.write(data, 1)
            
            file_size_mb = output_file.stat().st_size / (1024 * 1024)
            print(f"    Saved: {output_file.name}")
            print(f"      Size: {data.shape[1]} x {data.shape[0]} ({file_size_mb:.1f} MB)")
            
            return True
            
    except Exception as e:
        print(f"    Error extracting {state_id}: {e}")
        return False


def process_state_to_json(state_id: str, state_info: Dict, tif_file: Path, 
                          output_dir: Path, max_size: int = 1024) -> bool:
    """
    Process a state's TIF file to JSON for the web viewer.
    """
    try:
        with rasterio.open(tif_file) as src:
            # Read data
            elevation = src.read(1)
            bounds = src.bounds
            
            # Downsample if needed - PRESERVE ASPECT RATIO
            if max_size > 0 and (src.height > max_size or src.width > max_size):
                # Calculate step size based on the LARGER dimension to preserve aspect ratio
                scale_factor = max(src.height / max_size, src.width / max_size)
                step_size = max(1, int(scale_factor))
                elevation = elevation[::step_size, ::step_size]
                
                # Validate aspect ratio preservation
                orig_aspect = src.width / src.height
                result_width, result_height = elevation.shape[1], elevation.shape[0]
                result_aspect = result_width / result_height
                if abs(result_aspect - orig_aspect) > 0.1:
                    print(f"   WARNING: Aspect ratio changed! Original: {orig_aspect:.3f}, Result: {result_aspect:.3f}")
            
            height, width = elevation.shape
            
            # Convert to list, filtering bad values
            elevation_list = []
            for row in elevation:
                row_list = []
                for val in row:
                    if np.isnan(val) or val < -500:
                        row_list.append(None)
                    else:
                        row_list.append(float(val))
                elevation_list.append(row_list)
            
            # Create export data
            export_data = {
                "region_id": state_id,
                "name": state_info['name'],
                "description": state_info['description'],
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
            output_file = output_dir / f"{state_id}.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w') as f:
                json.dump(export_data, f, separators=(',', ':'))
            
            file_size_mb = output_file.stat().st_size / (1024 * 1024)
            print(f"      JSON: {file_size_mb:.1f} MB")
            
            return True
            
    except Exception as e:
        print(f"    Error processing {state_id}: {e}")
        return False


def create_regions_manifest(output_dir: Path, regions_data: Dict):
    """
    Create manifest file for all processed regions.
    """
    import time
    
    manifest = {
        "version": "1.0",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "regions": regions_data
    }
    
    manifest_file = output_dir / "regions_manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n Updated manifest: {manifest_file}")
    print(f"   Total regions: {len(regions_data)}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Extract and process all US state elevation data',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--usa-file',
        type=str,
        default='data/usa_elevation/nationwide_usa_elevation.tif',
        help='Path to nationwide USA elevation TIF file'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/regions',
        help='Directory to save state TIF files'
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
        default=1024,
        help='Maximum dimension for processed output'
    )
    parser.add_argument(
        '--states',
        type=str,
        nargs='+',
        help='Specific states to process (default: all contiguous 48)'
    )
    parser.add_argument(
        '--skip-extract',
        action='store_true',
        help='Skip extraction, only process existing TIF files to JSON'
    )
    
    args = parser.parse_args()
    
    usa_file = Path(args.usa_file)
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    
    print(f"\n🗺  US States Elevation Processor")
    print(f"="*70)
    print(f"USA data: {usa_file}")
    print(f"Output TIFs: {data_dir}")
    print(f"Output JSONs: {output_dir}")
    print(f"Max size: {args.max_size}px")
    print(f"="*70)
    
    # Determine which states to process
    if args.states:
        states_to_process = args.states
    else:
        states_to_process = CONTIGUOUS_STATES
    
    print(f"\nProcessing {len(states_to_process)} states...")
    
    # Check USA file exists if we're extracting
    if not args.skip_extract:
        if not usa_file.exists():
            print(f"\n USA elevation file not found: {usa_file}")
            print("Expected location: data/usa_elevation/nationwide_usa_elevation.tif")
            return 1
        print(f" Found USA elevation data: {usa_file}")
    
    extracted = []
    processed = []
    failed = []
    
    # Step 1: Extract states from USA data (if not skipping)
    if not args.skip_extract:
        print(f"\n{'='*70}")
        print("STEP 1: EXTRACTING STATE TIF FILES")
        print(f"{'='*70}")
        
        for i, state_id in enumerate(states_to_process, 1):
            if state_id not in US_STATES:
                print(f"\n Unknown state: {state_id}")
                failed.append(state_id)
                continue
            
            if state_id in ['alaska', 'hawaii']:
                print(f"\n[{i}/{len(states_to_process)}] {US_STATES[state_id]['name']}")
                print(f"     Skipping - not in contiguous USA dataset")
                print(f"   Download separately using download_us_states.py")
                continue
            
            state_info = US_STATES[state_id]
            output_file = data_dir / f"{state_id}.tif"
            
            # Skip if already exists
            if output_file.exists():
                print(f"\n[{i}/{len(states_to_process)}] {state_info['name']}")
                print(f"    Already exists, skipping extraction")
                extracted.append(state_id)
                continue
            
            print(f"\n[{i}/{len(states_to_process)}] {state_info['name']}")
            
            success = extract_state_from_usa(state_id, state_info, usa_file, output_file)
            
            if success:
                extracted.append(state_id)
            else:
                failed.append(state_id)
    else:
        # Just find existing TIF files
        for state_id in states_to_process:
            tif_file = data_dir / f"{state_id}.tif"
            if tif_file.exists():
                extracted.append(state_id)
    
    # Step 2: Process all TIF files to JSON
    print(f"\n{'='*70}")
    print("STEP 2: PROCESSING TO JSON")
    print(f"{'='*70}")
    
    for i, state_id in enumerate(extracted, 1):
        state_info = US_STATES[state_id]
        tif_file = data_dir / f"{state_id}.tif"
        
        if not tif_file.exists():
            print(f"\n[{i}/{len(extracted)}] {state_info['name']}")
            print(f"    TIF file not found: {tif_file}")
            continue
        
        print(f"\n[{i}/{len(extracted)}] {state_info['name']}")
        
        success = process_state_to_json(
            state_id,
            state_info,
            tif_file,
            output_dir,
            args.max_size
        )
        
        if success:
            processed.append(state_id)
    
    # Step 3: Update manifest with ALL regions (including existing ones)
    if processed:
        print(f"\n{'='*70}")
        print("STEP 3: UPDATING MANIFEST")
        print(f"{'='*70}")
        
        # Load existing manifest
        manifest_file = output_dir / "regions_manifest.json"
        existing_regions = {}
        if manifest_file.exists():
            with open(manifest_file) as f:
                manifest_data = json.load(f)
                existing_regions = manifest_data.get("regions", {})
        
        # Add all processed states
        all_regions = existing_regions.copy()
        for state_id in processed:
            if state_id in US_STATES:
                all_regions[state_id] = {
                    "name": US_STATES[state_id]["name"],
                    "description": US_STATES[state_id]["description"],
                    "bounds": US_STATES[state_id]["bounds"],
                    "file": f"{state_id}.json"
                }
        
        create_regions_manifest(output_dir, all_regions)
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    
    if extracted:
        print(f" Extracted/Found: {len(extracted)} states")
    
    if processed:
        print(f" Processed to JSON: {len(processed)} states")
        for state_id in processed:
            print(f"   - {US_STATES[state_id]['name']}")
    
    if failed:
        print(f"\n Failed: {len(failed)} states")
        for state_id in failed:
            if state_id in US_STATES:
                print(f"   - {US_STATES[state_id]['name']}")
            else:
                print(f"   - {state_id} (unknown)")
    
    if processed:
        print(f"\n{'='*70}")
        print("🎉 SUCCESS! Open interactive_viewer_advanced.html")
        print("   All states are now available in the Region Selector dropdown")
        print(f"{'='*70}\n")
    
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

