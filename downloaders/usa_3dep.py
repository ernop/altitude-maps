import sys
import io
from pathlib import Path
from typing import Tuple, Optional
import json

# Windows UTF-8 encoding support (PowerShell handles this automatically on Win10+)
# Removed wrapper to avoid conflicts with PowerShell's own UTF-8 handling

try:
    import requests
    from tqdm import tqdm
    import rasterio
except ImportError as e:
    print(f"Missing package: {e}")
    print("Install with: pip install requests tqdm rasterio")
    sys.exit(1)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.metadata import create_raw_metadata, save_metadata, get_metadata_path
from load_settings import get_opentopography_api_key
from src.pipeline import run_pipeline

# Import regions from centralized config
from src.regions_config import US_STATES as REGION_CONFIGS

# Convert RegionConfig to dict format for backward compatibility
US_STATES = {region_id: {
    "bounds": config.bounds,
    "name": config.name
} for region_id, config in REGION_CONFIGS.items()}

# USA full bounds - for legacy code that needs this
# These should also be in regions_config.py but keeping for compatibility
USA_FULL_BOUNDS = {
    "nationwide": {"bounds": (-125.0, 24.0, -66.0, 49.5), "name": "USA (Nationwide)"},
    "continental": {"bounds": (-125.0, 24.5, -66.9, 49.4), "name": "USA (Continental)"},
}


def download_opentopography_srtm(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    output_path: Path,
    api_key: Optional[str] = None
) -> bool:
    """
    Download SRTM 30m data from OpenTopography (automated, lower resolution).

    This provides good quality 30m data immediately, but is NOT the highest
    resolution available. For 1-10m data, use manual USGS EarthExplorer download.

    Args:
    region_id: Region identifier
    bounds: (west, south, east, north) in degrees
    output_path: Where to save the TIF file
    api_key: OpenTopography API key (optional, will load from settings.json if not provided)

    Returns:
    True if successful, False otherwise
    """
    if output_path.exists():
        print(f" Already exists: {output_path.name}", flush=True)
        return True

    # Get API key from settings if not provided
    if not api_key:
        try:
            api_key = get_opentopography_api_key()
            print(f" Using API key from settings.json", flush=True)
        except SystemExit:
            print(" OpenTopography requires an API key", flush=True)
            print(" Add your API key to settings.json or pass --api-key", flush=True)
            print(" Get a free key at: https://portal.opentopography.org/", flush=True)
            return False

    west, south, east, north = bounds

    # Check if region is too large for OpenTopography API
    width = abs(east - west)
    height = abs(north - south)

    if width > 4.0 or height > 4.0:
        print(f" WARNING: Region is very large ({width:.1f}deg x {height:.1f}deg)", flush=True)
        print(f" OpenTopography may reject requests > 4deg in any direction", flush=True)
        print(f" ", flush=True)
        print(f" RECOMMENDED: Use tiling for large states", flush=True)
        print(f" python downloaders/tile_large_states.py {region_id}", flush=True)
        print(f" ", flush=True)
        print(f" This will:", flush=True)
        print(f" - Split download into smaller tiles (safer, faster)", flush=True)
        print(f" - Automatically merge tiles", flush=True)
        print(f" - Apply state boundary clipping", flush=True)
        print(f" ", flush=True)
        print(f" Attempting single-request download anyway...", flush=True)
        print(f" (May timeout or be rejected by server)", flush=True)
        print(f" ", flush=True)

    # OpenTopography API for SRTM GL1 (30m global)
    url = "https://portal.opentopography.org/API/globaldem"

    params = {
        'demtype': 'SRTMGL1',  # SRTM 30m
        'south': south,
        'north': north,
        'west': west,
        'east': east,
        'outputFormat': 'GTiff',
        'API_Key': api_key
    }

    print(f" Downloading from OpenTopography (SRTM 30m)...", flush=True)
    print(f" Bounds: [{west:.2f}, {south:.2f}, {east:.2f}, {north:.2f}]", flush=True)
    print(f" Size: {width:.1f}deg x {height:.1f}deg", flush=True)
    print(f" Note: This is 30m SRTM, not high-res 3DEP", flush=True)
    print(f" ", flush=True)

    try:
        import time as time_module

        print(f" Requesting data from server...", flush=True)
        print(f" URL: {url}", flush=True)
        print(f" Params: demtype={params['demtype']}, bounds=[{west:.2f},{south:.2f},{east:.2f},{north:.2f}]", flush=True)

        response = requests.get(url, params=params, stream=True, timeout=300)
        print(f" Server responded: HTTP {response.status_code}", flush=True)

        # Handle HTTP 204 (No Content) - region has no data
        if response.status_code == 204:
            print(f" No data available for this region", flush=True)
            print(f" This area may be outside SRTM coverage or entirely water", flush=True)
            return False

        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if total_size > 0:
            print(f" Downloading {total_size / (1024*1024):.1f} MB...", flush=True)
        else:
            print(f" Downloading (size unknown)...", flush=True)

        with open(output_path, 'wb') as f:
            if total_size == 0:
                print(f" Writing data to disk...", flush=True)
                f.write(response.content)
                print(f" Done (size unknown)", flush=True)
            else:
                # Track progress for periodic updates
                start_time = time_module.time()
                last_print_time = start_time
                bytes_downloaded = 0

                with tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=" Progress",
                    bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {rate_fmt}'
                    ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))
                        bytes_downloaded += len(chunk)

                        # Print progress update every 15 seconds
                        current_time = time_module.time()
                        if current_time - last_print_time >= 15:
                            elapsed = current_time - start_time
                            percent = (bytes_downloaded / total_size) * 100
                            speed_mbps = (bytes_downloaded / (1024 * 1024)) / elapsed
                            remaining_bytes = total_size - bytes_downloaded
                            eta_seconds = remaining_bytes / (bytes_downloaded / elapsed) if bytes_downloaded > 0 else 0
                            print(f" [{int(elapsed)}s elapsed] {percent:.1f}% complete, {bytes_downloaded/(1024*1024):.1f}/{total_size/(1024*1024):.1f} MB, {speed_mbps:.2f} MB/s, ETA: {int(eta_seconds)}s", flush=True)
                            last_print_time = current_time

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f" Downloaded: {output_path.name} ({file_size_mb:.1f} MB)", flush=True)
        print(f" Saved to: {output_path}", flush=True)

        # Create metadata
        print(f" Creating metadata...", flush=True)

        # Create and save metadata
        metadata = create_raw_metadata(
            output_path,
            region_id=region_id,
            source='srtm_30m',  # Note: This is SRTM, not usa_3dep
            download_url=url,
            download_params=params
        )
        save_metadata(metadata, get_metadata_path(output_path))
        print(f" Metadata saved", flush=True)

        return True

    except requests.exceptions.Timeout:
        print(f" Download timeout - region may be too large or server busy", flush=True)
        print(f" Try again later or download a smaller region", flush=True)
        if output_path.exists():
            output_path.unlink()
        return False
    except requests.exceptions.HTTPError as e:
        print(f" HTTP Error: {e}", flush=True)
        if e.response.status_code == 400:
            print(f" Likely cause: Region too large (>{width:.1f}deg x {height:.1f}deg)", flush=True)
            print(f" OpenTopography limit is ~4deg in each direction", flush=True)
            print(f" Try downloading smaller sub-regions or use --manual", flush=True)
        elif e.response.status_code == 401:
            print(f" API key may be invalid or expired", flush=True)
        # Clean up partial download for any HTTP error
        if output_path.exists():
            output_path.unlink()
        return False
    except Exception as e:
        print(f" Download failed: {e}", flush=True)
        if output_path.exists():
            output_path.unlink()  # Clean up partial download
        return False


def print_manual_instructions(region_id: str, bounds: Tuple[float, float, float, float]) -> None:
    """
    Print instructions for manually downloading highest-quality USGS 3DEP data.

    Args:
    region_id: Region identifier
    bounds: (west, south, east, north) in degrees
    """
    west, south, east, north = bounds

    print("\n" + "="* 80)
    print("MANUAL DOWNLOAD INSTRUCTIONS - USGS 3DEP (1-10m, HIGHEST QUALITY)")
    print("="* 80)
    print(f"\nRegion: {region_id}")
    print(f"Bounds: West={west:.2f}, South={south:.2f}, East={east:.2f}, North={north:.2f}")
    print("\n Steps:")
    print("\n1. Go to USGS EarthExplorer:")
    print(" https://earthexplorer.usgs.gov/")
    print("\n2. Create free account (if needed):")
    print(" - Click 'Login' -> 'Register'")
    print(" - Fill in details (takes 2 minutes)")
    print("\n3. Set search area:")
    print(" - Click 'Use Map' tab")
    print(f" - Draw rectangle around: {west:.2f}, {south:.2f} to {east:.2f}, {north:.2f}")
    print(" - Or use coordinates directly in the form")
    print("\n4. Select dataset:")
    print(" - Click 'Data Sets' tab")
    print(" - Expand 'Digital Elevation'")
    print(" - Check '3DEP Elevation - Seamless'")
    print(" - For best resolution, choose '1 meter DEM' or '1/3 arc-second DEM'")
    print("\n5. Search and download:")
    print(" - Click 'Results'")
    print(" - Click download icon () next to desired tile")
    print(" - Choose 'GeoTIFF'")
    print(" - Save as: data/raw/usa_3dep/{}_bbox_10m.tif".format(region_id))
    print("\n6. After download, create metadata:")
    print(" python downloaders/usa_3dep.py --create-metadata {} <path-to-downloaded-file>".format(region_id))
    print("\n" + "="* 80)
    print("Why manual? USGS doesn't have a simple public API for 3DEP downloads.")
    print("The OpenTopography method (automated) only provides 30m SRTM data.")
    print("For highest quality (1-10m), the manual EarthExplorer method is required.")
    print("="* 80 + "\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Download USA elevation data from USGS 3DEP',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
# Download California (automated, 30m SRTM)
python downloaders/usa_3dep.py california --auto

# Show manual instructions for high-res 3DEP
python downloaders/usa_3dep.py california --manual

# Download full USA (automated, 30m)
python downloaders/usa_3dep.py nationwide --auto

# List available states
python downloaders/usa_3dep.py --list

Note: --auto uses OpenTopography (30m SRTM, good quality, automated)
For highest quality (1-10m 3DEP), use --manual and follow instructions
"""
    )

    parser.add_argument('region', nargs='?', help='Region to download (state name or nationwide)')
    parser.add_argument('--list', action='store_true', help='List all available regions')
    parser.add_argument('--auto', action='store_true', help='Automated download (30m SRTM via OpenTopography)')
    parser.add_argument('--manual', action='store_true', help='Show manual download instructions (1-10m 3DEP)')
    parser.add_argument('--api-key', type=str, help='OpenTopography API key (optional)')
    parser.add_argument('--output-dir', type=str, default='data/raw/srtm_30m', help='Output directory')
    parser.add_argument('--no-process', action='store_true', help='Skip automatic processing pipeline (just download)')
    parser.add_argument('--target-pixels', type=int, default=4000, help='Target resolution for viewer (default: 4000, capped to input size)')

    args = parser.parse_args()

    if args.list:
        print("\n AVAILABLE REGIONS:")
        print("="* 70)
        print("\n USA Full Coverage:")
        for region_id, info in USA_FULL_BOUNDS.items():
            bounds = info['bounds']
            print(f" {region_id:15s} - {info['name']:25s} {bounds}")

        print("\n Individual States:")
        for region_id, info in sorted(US_STATES.items()):
            print(f" {region_id:15s} - {info['name']}")
        print(f"\nTotal: {len(US_STATES)} states + {len(USA_FULL_BOUNDS)} full USA options")
        print("="* 70)
        return 0

    if not args.region:
        print(" No region specified!")
        print("Usage: python downloaders/usa_3dep.py <region> [--auto|--manual]")
        print("Or: python downloaders/usa_3dep.py --list")
        return 1

    # Find region
    region_id = args.region.lower().replace(' ', '_').replace('-', '_')

    if region_id in USA_FULL_BOUNDS:
        region_info = USA_FULL_BOUNDS[region_id]
    elif region_id in US_STATES:
        region_info = US_STATES[region_id]
    else:
        print(f" Unknown region: {args.region}")
        print("Run with --list to see available regions")
        return 1

    bounds = region_info['bounds']
    name = region_info['name']

    print(f"\n USA Elevation Downloader", flush=True)
    print(f"="* 70, flush=True)
    print(f"Region: {name} ({region_id})", flush=True)
    print(f"Bounds: {bounds}", flush=True)
    print(f"="* 70, flush=True)

    # Choose mode
    if args.manual:
        print_manual_instructions(region_id, bounds)
        return 0
    elif args.auto:
        output_path = Path(args.output_dir) / f"{region_id}_bbox_30m.tif"

        # Check if state needs tiling (> 4deg in any direction)
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        needs_tiling = (width > 4.0 or height > 4.0)

        if needs_tiling and region_id in US_STATES:
            print(f"\n[AUTO-TILING] State is large ({width:.1f}deg x {height:.1f}deg)", flush=True)
            print(f" Automatically splitting into 1-degree tiles...", flush=True)
            print(f" (This is transparent - merging happens automatically)\n", flush=True)

            # Import tiling functions (MUST succeed - no fallback)
            from downloaders.tile_large_states import download_and_merge_1degree_tiles

            # Use automatic 1-degree tiling for all large states
            download_success = download_and_merge_1degree_tiles(
                region_id,
                bounds,
                output_path,
                args.api_key
            )
            
            if not download_success:
                print(f"\n Tiled download/merge failed", flush=True)
                return 1
        else:
            # Normal single-request download
            download_success = download_opentopography_srtm(region_id, bounds, output_path, args.api_key)

        if not download_success:
            print(f"\n Download failed.", flush=True)
            return 1

        print(f"\n Download complete!", flush=True)

        # Step 2: Auto-process (unless --no-process specified)
        if not args.no_process:
            # Determine boundary name and type for US states
            boundary_name = None
            boundary_type = "country"

            if region_id in US_STATES:
                # US state - use state-level boundary
                state_name = US_STATES[region_id]['name']
                boundary_name = f"United States of America/{state_name}"
                boundary_type = "state"

            # Run processing pipeline
            pipeline_success, result_paths = run_pipeline(
                raw_tif_path=output_path,
                region_id=region_id,
                source='srtm_30m',
                boundary_name=boundary_name,
                boundary_type=boundary_type,
                target_pixels=args.target_pixels,
                skip_clip=False  # Enable clipping with state boundaries
            )

            if not pipeline_success:
                print(f"\n Pipeline had issues, but raw data was downloaded successfully", flush=True)
                print(f" You can process manually later with:", flush=True)
                print(f" python -c \"from src.pipeline import run_pipeline; from pathlib import Path; run_pipeline(Path('{output_path}'), '{region_id}', 'srtm_30m')\"", flush=True)
        else:
            print(f"\n Skipped processing (--no-process specified)", flush=True)
            print(f" To process later, run:", flush=True)
            print(f" python -c \"from src.pipeline import run_pipeline; from pathlib import Path; run_pipeline(Path('{output_path}'), '{region_id}', 'srtm_30m')\"", flush=True)

        print(f"\n Note: This is 30m SRTM data. For highest quality (1-10m), run:", flush=True)
        print(f" python downloaders/usa_3dep.py {region_id} --manual", flush=True)

        return 0
    else:
        print("\n Please specify download method:")
        print(f" --auto : Automated download (30m SRTM, good quality)")
        print(f" --manual : Show instructions for manual 3DEP download (1-10m, best quality)")
        print(f"\nExample:")
        print(f" python downloaders/usa_3dep.py {region_id} --auto")
        return 1


if __name__ == "__main__":
    sys.exit(main())

