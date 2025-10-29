"""
Download HIGH RESOLUTION elevation data for all US states from OpenTopography.
Uses SRTM 30m data for much better quality than the low-res nationwide file.
"""
import sys
import io
import json
import time
import numpy as np
from pathlib import Path
from typing import Dict

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
 import requests
 from tqdm import tqdm
except ImportError as e:
 print(f"Missing required package: {e}")
 print("Install with: pip install rasterio requests tqdm")
 sys.exit(1)

from download_all_us_states import US_STATES, CONTIGUOUS_STATES
from load_settings import get_api_key

def download_state_srtm(state_id: str, state_info: Dict, output_file: Path, api_key: str) -> bool:
 """
 Download high-resolution SRTM data for a state from OpenTopography.
 """
 if output_file.exists():
 file_size_mb = output_file.stat().st_size / (1024* 1024)
 print(f" Already exists ({file_size_mb:.1f} MB)")
 return True

 west, south, east, north = state_info["bounds"]

# Calculate approximate size to warn about large downloads
 area_sq_deg = (east - west)* (north - south)
 approx_mb = area_sq_deg* 20# Rough estimate

 if approx_mb > 200:
 print(f" Warning: Large download (~{approx_mb:.0f} MB)")

# OpenTopography API endpoint
 url = "https://portal.opentopography.org/API/globaldem"

 params = {
 'demtype': 'SRTMGL1',# SRTM 30m resolution
 'south': south,
 'north': north,
 'west': west,
 'east': east,
 'outputFormat': 'GTiff',
 'API_Key': api_key
 }

 print(f" Downloading SRTM 30m data...")
 print(f" Bounds: {west:.2f}degW to {east:.2f}degE, {south:.2f}degS to {north:.2f}degN")

 try:
 response = requests.get(url, params=params, stream=True, timeout=300)
 response.raise_for_status()

 total_size = int(response.headers.get('content-length', 0))

 output_file.parent.mkdir(parents=True, exist_ok=True)

 with open(output_file, 'wb') as f:
 if total_size == 0:
 f.write(response.content)
 print(f" Downloaded")
 else:
# Track progress for periodic updates
 start_time = time.time()
 last_print_time = start_time
 bytes_downloaded = 0

 with tqdm(total=total_size, unit='B', unit_scale=True, desc=" Progress",
 bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}]') as pbar:
 for chunk in response.iter_content(chunk_size=8192):
 f.write(chunk)
 pbar.update(len(chunk))
 bytes_downloaded += len(chunk)

# Print progress update every 15 seconds
 current_time = time.time()
 if current_time - last_print_time >= 15:
 elapsed = current_time - start_time
 percent = (bytes_downloaded / total_size)* 100
 speed_mbps = (bytes_downloaded / (1024* 1024)) / elapsed
 remaining_bytes = total_size - bytes_downloaded
 eta_seconds = remaining_bytes / (bytes_downloaded / elapsed) if bytes_downloaded > 0 else 0
 print(f" [{int(elapsed)}s elapsed] {percent:.1f}% complete, {bytes_downloaded/(1024*1024):.1f}/{total_size/(1024*1024):.1f} MB, {speed_mbps:.2f} MB/s, ETA: {int(eta_seconds)}s", flush=True)
 last_print_time = current_time

# Verify the file
 try:
 with rasterio.open(output_file) as src:
 file_size_mb = output_file.stat().st_size / (1024* 1024)
 print(f" Success: {src.width}x{src.height} pixels ({file_size_mb:.1f} MB)")
 return True
 except Exception as e:
 print(f" File verification failed: {e}")
 output_file.unlink()
 return False

 except requests.exceptions.Timeout:
 print(f" Download timeout")
 return False
 except requests.exceptions.HTTPError as e:
 if e.response.status_code == 413:
 print(f" Region too large for API")
 else:
 print(f" HTTP Error: {e}")
 return False
 except Exception as e:
 print(f" Download failed: {e}")
 return False


def process_state_to_json(state_id: str, state_info: Dict, tif_file: Path,
 output_dir: Path, max_size: int = 4096) -> bool:
 """
 Process a state's high-res TIF file to JSON for the web viewer.
 Uses higher max_size for better quality.
 """
 try:
 with rasterio.open(tif_file) as src:
 elevation = src.read(1)
 bounds = src.bounds

 print(f" Original: {src.width}x{src.height} pixels")
 print(f" Aspect ratio: {src.width/src.height:.3f}")

# Downsample if needed - PRESERVE ASPECT RATIO
 if max_size > 0 and (src.height > max_size or src.width > max_size):
# Calculate step size based on the LARGER dimension to preserve aspect ratio
 scale_factor = max(src.height / max_size, src.width / max_size)
 step_size = max(1, int(scale_factor))
 elevation = elevation[::step_size, ::step_size]
 result_width, result_height = elevation.shape[1], elevation.shape[0]
 result_aspect = result_width / result_height
 print(f" Downsampled: {result_width}x{result_height} (step: {step_size})")
 print(f" Result aspect ratio: {result_aspect:.3f}")

# Validate aspect ratio preservation
 if abs(result_aspect - (src.width/src.height)) > 0.1:
 print(f" WARNING: Aspect ratio changed significantly!")
 print(f" Original: {src.width/src.height:.3f}, Result: {result_aspect:.3f}")
 else:
 print(f" No downsampling (within {max_size}px limit)")

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
 print(f" JSON: {file_size_mb:.1f} MB ({width}x{height} = {width*height:,} points)")

 return True

 except Exception as e:
 print(f" Error processing: {e}")
 return False


def main():
 import argparse

 parser = argparse.ArgumentParser(
 description='Download HIGH RESOLUTION elevation data for all US states'
 )
 parser.add_argument(
 '--states',
 type=str,
 nargs='+',
 help='Specific states to process (default: all 48 contiguous)'
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
 default=4096,
 help='Maximum dimension for processed output (default: 4096 for high quality)'
 )
 parser.add_argument(
 '--skip-download',
 action='store_true',
 help='Skip download, only process existing TIF files'
 )
 parser.add_argument(
 '--skip-process',
 action='store_true',
 help='Only download, skip JSON processing'
 )

 args = parser.parse_args()

# Get API key
 try:
 api_key = get_api_key()
 print(f" Using API key from settings.json")
 except SystemExit:
 print("\n API key required!")
 print("Add your OpenTopography API key to settings.json")
 return 1

 data_dir = Path(args.data_dir)
 output_dir = Path(args.output_dir)

# Determine which states to process
 if args.states:
 states_to_process = args.states
 else:
 states_to_process = CONTIGUOUS_STATES

 print(f"\n HIGH RESOLUTION US States Downloader")
 print(f"="*70)
 print(f"States: {len(states_to_process)}")
 print(f"Resolution: SRTM 30m (high quality)")
 print(f"Output max size: {args.max_size}px (higher = better quality)")
 print(f"Data dir: {data_dir}")
 print(f"Output dir: {output_dir}")
 print(f"="*70)

 downloaded = []
 processed = []
 failed = []

# Step 1: Download high-res SRTM data
 if not args.skip_download:
 print(f"\n{'='*70}")
 print("STEP 1: DOWNLOADING HIGH-RES SRTM DATA")
 print(f"{'='*70}")
 print(" This will take a while - OpenTopography requires 2-3 sec delay between requests")
 print(" Estimated time: ~3-5 minutes for all 48 states")
 print()

 for i, state_id in enumerate(states_to_process, 1):
 if state_id not in US_STATES:
 print(f"\n [{i}/{len(states_to_process)}] Unknown state: {state_id}")
 failed.append(state_id)
 continue

 if state_id in ['alaska', 'hawaii']:
 print(f"\n[{i}/{len(states_to_process)}] {US_STATES[state_id]['name']}")
 print(f" ℹ Separate download recommended (different coverage)")
 continue

 state_info = US_STATES[state_id]
 output_file = data_dir / f"{state_id}.tif"

 print(f"\n[{i}/{len(states_to_process)}] {state_info['name']}")

 success = download_state_srtm(state_id, state_info, output_file, api_key)

 if success:
 downloaded.append(state_id)
 else:
 failed.append(state_id)

# Be nice to the API - wait between requests
 if i < len(states_to_process) and success:
 time.sleep(3)
 else:
# Find existing files
 for state_id in states_to_process:
 tif_file = data_dir / f"{state_id}.tif"
 if tif_file.exists():
 downloaded.append(state_id)

# Step 2: Process to JSON
 if not args.skip_process and downloaded:
 print(f"\n{'='*70}")
 print("STEP 2: PROCESSING TO HIGH-RES JSON")
 print(f"{'='*70}")

 for i, state_id in enumerate(downloaded, 1):
 state_info = US_STATES[state_id]
 tif_file = data_dir / f"{state_id}.tif"

 if not tif_file.exists():
 continue

 print(f"\n[{i}/{len(downloaded)}] {state_info['name']}")

 success = process_state_to_json(
 state_id,
 state_info,
 tif_file,
 output_dir,
 args.max_size
 )

 if success:
 processed.append(state_id)

# Step 3: Update manifest
 if processed:
 print(f"\n{'='*70}")
 print("STEP 3: UPDATING MANIFEST")
 print(f"{'='*70}")

 manifest_file = output_dir / "regions_manifest.json"
 existing_regions = {}
 if manifest_file.exists():
 with open(manifest_file) as f:
 manifest_data = json.load(f)
 existing_regions = manifest_data.get("regions", {})

 all_regions = existing_regions.copy()
 for state_id in processed:
 if state_id in US_STATES:
 all_regions[state_id] = {
 "name": US_STATES[state_id]["name"],
 "description": US_STATES[state_id]["description"],
 "bounds": US_STATES[state_id]["bounds"],
 "file": f"{state_id}.json"
 }

 manifest = {
 "version": "1.0",
 "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
 "regions": all_regions
 }

 with open(manifest_file, 'w') as f:
 json.dump(manifest, f, indent=2)

 print(f" Updated manifest: {manifest_file}")
 print(f" Total regions: {len(all_regions)}")

# Summary
 print(f"\n{'='*70}")
 print("SUMMARY")
 print(f"{'='*70}")

 if downloaded:
 print(f" Downloaded/Found: {len(downloaded)} states")

 if processed:
 print(f" Processed to JSON: {len(processed)} states")
 print(f"\n States with HIGH RESOLUTION data:")
 for state_id in processed:
 print(f" - {US_STATES[state_id]['name']}")

 if failed:
 print(f"\n Failed: {len(failed)} states")
 for state_id in failed:
 if state_id in US_STATES:
 print(f" - {US_STATES[state_id]['name']}")

 if processed:
 print(f"\n{'='*70}")
 print(" SUCCESS! States now have HIGH RESOLUTION data")
 print(" Open interactive_viewer_advanced.html and select any state")
 print(" You'll see MUCH more detail now!")
 print(f"{'='*70}\n")

 return 0 if not failed else 1


if __name__ == "__main__":
 sys.exit(main())

