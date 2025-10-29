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

# Import regions from centralized config - all state info comes from src/regions_config.py
from src.regions_config import US_STATES as CONFIGURED_US_STATES

# Convert to dict format for this script
US_STATES = {state_id: {
    "bounds": config.bounds,
    "name": config.name,
    "description": config.description or config.name
} for state_id, config in CONFIGURED_US_STATES.items()}

# States available in the contiguous USA dataset
CONTIGUOUS_STATES = [k for k in US_STATES.keys() if k not in ['alaska', 'hawaii']]


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
 print(f" State bounds don't overlap with USA data")
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

 file_size_mb = output_file.stat().st_size / (1024* 1024)
 print(f" Saved: {output_file.name}")
 print(f" Size: {data.shape[1]} x {data.shape[0]} ({file_size_mb:.1f} MB)")

 return True

 except Exception as e:
 print(f" Error extracting {state_id}: {e}")
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
 print(f" WARNING: Aspect ratio changed! Original: {orig_aspect:.3f}, Result: {result_aspect:.3f}")

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

 file_size_mb = output_file.stat().st_size / (1024* 1024)
 print(f" JSON: {file_size_mb:.1f} MB")

 return True

 except Exception as e:
 print(f" Error processing {state_id}: {e}")
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
 print(f" Total regions: {len(regions_data)}")


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

 print(f"\n US States Elevation Processor")
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
 print(f" Skipping - not in contiguous USA dataset")
 print(f" Download separately using download_us_states.py")
 continue

 state_info = US_STATES[state_id]
 output_file = data_dir / f"{state_id}.tif"

# Skip if already exists
 if output_file.exists():
 print(f"\n[{i}/{len(states_to_process)}] {state_info['name']}")
 print(f" Already exists, skipping extraction")
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
 print(f" TIF file not found: {tif_file}")
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
 print(f" - {US_STATES[state_id]['name']}")

 if failed:
 print(f"\n Failed: {len(failed)} states")
 for state_id in failed:
 if state_id in US_STATES:
 print(f" - {US_STATES[state_id]['name']}")
 else:
 print(f" - {state_id} (unknown)")

 if processed:
 print(f"\n{'='*70}")
 print(" SUCCESS! Open interactive_viewer_advanced.html")
 print(" All states are now available in the Region Selector dropdown")
 print(f"{'='*70}\n")

 return 0 if not failed else 1


if __name__ == "__main__":
 sys.exit(main())

