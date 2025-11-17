"""
One command to ensure a region is ready to view.

Downloads if needed, processes if needed, checks if everything is valid.
Works for both US states and international regions.

CRITICAL ENFORCEMENT (see tech/DATA_PIPELINE.md):
- Always use RegionType enum (never ad-hoc strings)
- Resolution is dynamic (Nyquist sampling) - never hardcoded by region type
- Check all three enum cases exhaustively with ValueError for unknown

Usage:
    python ensure_region.py ohio  # US state
    python ensure_region.py iceland  # International region
    python ensure_region.py tennessee --target-pixels 4096
    python ensure_region.py california --force-reprocess
    python ensure_region.py new_mexico --update-adjacency  # Add region + update neighbors
"""
import sys
import io
import argparse
from pathlib import Path

# Fix Windows console encoding for emoji/Unicode
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (AttributeError, ValueError):
        pass

# Import region definitions from centralized config
from src.regions_config import ALL_REGIONS, get_us_state_names
from src.types import RegionType

# Pipeline dependencies
import json
import gzip
import glob
from typing import Optional, Dict, Tuple

# Pipeline utilities
from src.versioning import get_current_version
from src.tile_geometry import (
    snap_bounds_to_grid, 
    tile_filename_from_bounds, 
    estimate_raw_file_size_mb,
    calculate_visible_pixel_size
)
from src.pipeline import run_pipeline, PipelineError
from src.downloaders.orchestrator import (
    download_region,
    determine_dataset_override,
    determine_min_required_resolution,
    format_pixel_size
)
from src.downloaders.opentopography import OpenTopographyRateLimitError
from src.downloaders.data_source_resolution import determine_data_source
from src.validation import (
    validate_geotiff,
    validate_json_export,
    find_raw_file,
    check_pipeline_complete
)
from src.status import (
    summarize_pipeline_status,
    check_export_version,
    verify_and_auto_fix
)

# Alias for backward compatibility with existing code that uses bbox_filename_from_bounds
bbox_filename_from_bounds = tile_filename_from_bounds

def check_venv() -> None:
    """Ensure we're running in the virtual environment."""
    # Check if we're in a venv
    in_venv = (hasattr(sys, 'real_prefix') or
               (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))

    if not in_venv:
        print("\n" + "="*70)
        print("  ERROR: Not running in virtual environment!")
        print("="*70)
        print("\nYou must activate the virtual environment first:")
        if sys.platform == 'win32':
            print("  .\\venv\\Scripts\\Activate.ps1  # PowerShell")
            print("  .\\venv\\Scripts\\activate.bat  # Command Prompt")
        else:
            print("  source venv/bin/activate")
        print("\nOr run the setup script:")
        print("  .\\setup.ps1  # Windows")
        print("  ./setup.sh  # Linux/Mac")
        print("="*70 + "\n")
        sys.exit(1)




def get_region_info(region_id: str) -> Tuple[Optional[RegionType], Optional[Dict]]:
    """
    Get information about a region (US state or international).

    Returns:
        Tuple of (region_type, region_data) where:
        - region_type is a RegionType enum value
        - region_data is a dict with region info

        Returns (None, None) if region not found
    """
    # Normalize region ID
    region_id = region_id.lower().replace(' ', '_').replace('-', '_')

    # Look up region in centralized config
    region_config = ALL_REGIONS.get(region_id)

    if region_config is None:
        return None, None

    # Use the actual enum from the config
    region_type = region_config.region_type

    # Build region data dict
    region_data = {
        'name': region_config.name,
        'display_name': region_config.name,
        'bounds': region_config.bounds,
        'description': region_config.description or region_config.name,
        'clip_boundary': region_config.clip_boundary,
        'country': region_config.country
    }

    return region_type, region_data



def get_source_from_path(path: Path) -> str:
    """Determine source type from path."""
    if 'usa_3dep' in str(path):
        return 'usa_3dep'
    if '90m' in str(path):
        return 'srtm_90m'
    return 'srtm_30m'




def _iter_all_region_ids() -> list[str]:
    """Return all configured region ids from centralized config."""
    try:
        return sorted(list(ALL_REGIONS.keys()))
    except Exception:
        return []


def process_region(region_id: str, raw_path: Path, source: str, target_pixels: int, force: bool, region_type: RegionType, region_info: Dict, border_resolution: str = '10m') -> Tuple[bool, Dict]:
    """
    Run the pipeline on a region and return (success, result_paths).
    
    CRITICAL: Uses RegionType enum for all decisions (see tech/DATA_PIPELINE.md).
    Checks all three cases exhaustively with ValueError for unknown types.
    """

    # Determine boundary based on region type (using enum)
    # CANONICAL REFERENCE: tech/DATA_PIPELINE.md - Section "Region Type System"
    if region_type == RegionType.USA_STATE:
        state_name = region_info['name']
        boundary_name = f"United States of America/{state_name}"
        boundary_type = "state"
    elif region_type == RegionType.COUNTRY:
        # For countries, use country-level boundary
        if region_info.get('clip_boundary', True):
            boundary_name = region_info['name']
            boundary_type = "country"
        else:
            boundary_name = None
            boundary_type = None
    elif region_type == RegionType.AREA:
        # For regions (islands, ranges, etc.), check if boundary clipping is enabled
        if region_info.get('clip_boundary', False):
            # Some regions may have boundaries defined
            boundary_name = region_info['name']
            boundary_type = "country"  # Or custom boundary if available
        else:
            boundary_name = None
            boundary_type = None
    else:
        raise ValueError(f"Unknown region type: {region_type}")

    print(f"\n[STAGES 6-10] Processing pipeline...", flush=True)
    if boundary_name:
        print(f"  Boundary: {boundary_name}", flush=True)

    # With exact bounds naming, new files will have different names automatically.
    # Just delete old downloaded bbox file if bounds changed (to avoid reusing wrong data).
    # Processed/exported files are kept - manifest update points viewer to new ones.
    if force:
        bounds = region_info.get('bounds')
        if bounds:
            # Only delete downloaded bbox file if it has different bounds than current
            for source_check in ['srtm_30m', 'srtm_90m', 'usa_3dep']:
                resolution = '30m' if '30m' in source_check else '90m' if '90m' in source_check else '10m'
                old_filename = bbox_filename_from_bounds(bounds, resolution)
                old_file_path = Path(f"data/raw/{source_check}/{old_filename}")
                
                # Delete only if it's different from the file we're about to use
                if old_file_path.exists() and old_file_path.name != raw_path.name:
                    try:
                        old_file_path.unlink()
                        print(f"  Deleted old bounds file: {old_file_path.name}", flush=True)
                    except Exception:
                        pass

    try:
        success, result_paths = run_pipeline(
            raw_tif_path=raw_path,
            region_id=region_id,
            source=source,
            boundary_name=boundary_name,
            boundary_type=boundary_type,
            target_pixels=target_pixels,
            skip_clip=(boundary_name is None),
            border_resolution=border_resolution
        )
        return success, result_paths

    except Exception as e:
        print(f"  Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        return False, {}



def main():
    # CRITICAL: Check venv FIRST before any imports
    check_venv()

    sys.path.insert(0, str(Path(__file__).parent))
    from src.config import DEFAULT_TARGET_PIXELS

    parser = argparse.ArgumentParser(
        description='One command to ensure a region is ready to view (US states and international regions)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # US States
    python ensure_region.py ohio  # Single word state
    python ensure_region.py new_hampshire  # Multi-word with underscore
    python ensure_region.py "new hampshire"  # Multi-word with quotes
    python ensure_region.py tennessee --force-reprocess  # Force full rebuild
    python ensure_region.py california --target-pixels 4096  # High resolution

  # International Regions
    python ensure_region.py iceland  # Iceland
    python ensure_region.py japan  # Japan
    python ensure_region.py switzerland  # Switzerland
    python ensure_region.py new_zealand  # New Zealand
    
  # Update adjacency after adding a new region
    python ensure_region.py montana --update-adjacency  # Add Montana and update neighbors

This script will:
    1. Detect region type (US state or international)
    2. Check if raw data exists
    3. Download if missing (auto-download for US states and supported international regions)
    4. Run the full pipeline (clip, downsample, export)
    5. Optionally regenerate adjacency data (with --update-adjacency flag)
    6. Report status
        """
    )
    parser.add_argument('region_id', nargs='?', help='Region ID (e.g., ohio, iceland, japan)')
    parser.add_argument('--target-pixels', type=int, default=DEFAULT_TARGET_PIXELS,
                        help=f'Target resolution (default: {DEFAULT_TARGET_PIXELS})')
    parser.add_argument('--force-reprocess', action='store_true',
                        help='Force reprocessing even if files exist')
    parser.add_argument('--check-only', action='store_true',
                        help='Only check status, do not download or process')
    parser.add_argument('--list-regions', action='store_true',
                        help='List all available regions')
    parser.add_argument('--yes', action='store_true',
                        help='Auto-accept lower quality data prompts')
    parser.add_argument('--update-adjacency', action='store_true',
                        help='Regenerate adjacency data after processing (run after adding new regions)')

    args = parser.parse_args()
    
    # Pseudo-region: all
    # Allows: python ensure_region.py all --check-only
    if args.region_id and args.region_id.strip().lower() in ("all",):
        all_ids = _iter_all_region_ids()
        if not all_ids:
            print("No regions found in configuration.")
            return 1
        print("\nRUNNING FOR ALL REGIONS\n" + "="*70)
        problems: list[tuple[str, str]] = []
        processed_count = 0
        for rid in all_ids:
            processed_count += 1
            # Summary line per region
            has_valid = check_pipeline_complete(rid)
            version_ok, found_v, expected_v = check_export_version(rid)
            status = []
            if has_valid:
                status.append("export_present")
            else:
                status.append("missing_export")
            if version_ok:
                status.append("version_ok")
            else:
                status.append(f"old_format(found={found_v}, expected={expected_v})")
                problems.append((rid, f"old_format(found={found_v}, expected={expected_v})"))
            print(f"- {rid}: {', '.join(status)}")

            if not args.check_only and (not has_valid or not version_ok):
                # In non-check mode, attempt to fix by ensuring per-region
                # Re-enter main flow by simulating single-region processing
                region_type, region_info = get_region_info(rid)
                if region_type is None:
                    print(f"  Skipping unknown region: {rid}")
                    continue
                # Determine minimum required resolution for this region
                # All regions use dynamic resolution determination based on Nyquist rule
                visible = calculate_visible_pixel_size(region_info['bounds'], args.target_pixels)
                
                if region_type == RegionType.USA_STATE:
                    # US states: 10m, 30m, or 90m based on requirements
                    min_req_res = determine_min_required_resolution(
                        visible['avg_m_per_pixel'],
                        available_resolutions=[10, 30, 90]
                    )
                else:
                    # International regions: 30m or 90m
                    min_req_res = determine_min_required_resolution(
                        visible['avg_m_per_pixel'],
                        available_resolutions=[30, 90]
                    )
                
                raw_path, source = find_raw_file(rid, min_required_resolution_meters=min_req_res)
                if not raw_path:
                    dataset_override = determine_dataset_override(rid, region_type, region_info)
                    try:
                        if not download_region(rid, region_type, region_info, dataset_override, args.target_pixels):
                            print(f"  Download failed for {rid}")
                            continue
                    except OpenTopographyRateLimitError as e:
                        print(f"\n{'='*70}")
                        print(f"  RATE LIMIT ERROR: Stopping batch download")
                        print(f"{'='*70}")
                        print(f"  OpenTopography returned 401 Unauthorized")
                        print(f"  Processed {processed_count} regions before hitting limit")
                        print(f"\n  What to do:")
                        print(f"  - Wait 15-30 minutes and run the same command again")
                        print(f"  - Already downloaded regions are cached and won't re-download")
                        print(f"  - The script will resume where it left off")
                        print(f"{'='*70}\n")
                        break  # Stop processing more regions
                    raw_path, source = find_raw_file(rid, min_required_resolution_meters=min_req_res)
                    if not raw_path:
                        print(f"  Validation failed after download for {rid}")
                        continue
                success, result_paths = process_region(rid, raw_path, source, args.target_pixels,
                                                      True if args.force_reprocess else False,
                                                      region_type, region_info, '10m')
                if success:
                    _ = verify_and_auto_fix(rid, result_paths, source, args.target_pixels,
                                            region_type, region_info, '10m')
        # Summary of problems for check-only
        if args.check_only:
            print("\n" + "="*70)
            if problems:
                print("Regions requiring rebuild due to old format:")
                for rid, msg in problems:
                    print(f"  - {rid}: {msg}")
                return 2
            else:
                print("All regions are on the current export format.")
                return 0
        # Non-check path falls through to completion
        return 0

    # Handle --list-regions
    if args.list_regions:
        from src.regions_config import US_STATES, COUNTRIES, REGIONS, check_region_data_available

        def _status_tag(rid: str) -> str:
            try:
                st = check_region_data_available(rid)
                return "[ready]" if st.get('in_manifest') else "[not ready]"
            except Exception:
                return "[unknown]"

        def _format_size(bounds: Tuple[float, float, float, float]) -> str:
            """Format region size for display."""
            import math
            west, south, east, north = bounds
            width_deg = east - west
            height_deg = north - south
            center_lat = (north + south) / 2.0
            meters_per_deg_lat = 111_320
            meters_per_deg_lon = 111_320 * math.cos(math.radians(center_lat))
            width_m = width_deg * meters_per_deg_lon
            height_m = height_deg * meters_per_deg_lat
            width_mi = width_m / 1609.344
            height_mi = height_m / 1609.344
            if width_mi < 0.1:
                return f"{int(width_mi * 5280)}×{int(height_mi * 5280)} ft"
            elif width_mi < 1:
                return f"{width_mi:.2f}×{height_mi:.2f} mi"
            else:
                return f"{width_mi:.0f}×{height_mi:.0f} mi"

        print("\n  AVAILABLE REGIONS:")
        print("="*70)
        print("\n  US STATES:")
        for state_id in sorted(US_STATES.keys()):
            config = US_STATES[state_id]
            tag = _status_tag(state_id)
            size = _format_size(config.bounds)
            print(f"    - {state_id:20s} -> {config.name:30s} {size:15s} {tag}")
        print(f"\n  COUNTRIES:")
        for country_id in sorted(COUNTRIES.keys()):
            config = COUNTRIES[country_id]
            tag = _status_tag(country_id)
            size = _format_size(config.bounds)
            print(f"    - {country_id:20s} -> {config.name:30s} {size:15s} {tag}")
        print(f"\n  REGIONS:")
        for region_id in sorted(REGIONS.keys()):
            config = REGIONS[region_id]
            tag = _status_tag(region_id)
            size = _format_size(config.bounds)
            print(f"    - {region_id:20s} -> {config.name:30s} {size:15s} {tag}")
        print(f"\n{'='*70}")
        print("Legend: [ready] = appears in viewer manifest; [not ready] = not exported yet")
        print(f"Total: {len(US_STATES)} US states + {len(COUNTRIES)} countries + {len(REGIONS)} regions = {len(US_STATES) + len(COUNTRIES) + len(REGIONS)} total")
        print(f"\nUsage: python ensure_region.py <region_id>")
        return 0

    # Check if region_id was provided
    if not args.region_id:
        parser.error("region_id is required (or use --list-regions to see available regions)")

    # Normalize region ID: convert spaces to underscores, lowercase
    region_id = args.region_id.lower().replace(' ', '_').replace('-', '_')

    # Detect region type
    region_type, region_info = get_region_info(region_id)

    if region_type is None:
        print("="*70, flush=True)
        print(f"  UNKNOWN REGION: {region_id}", flush=True)
        print("="*70, flush=True)
        print(f"\nRegion '{region_id}' is not recognized.")
        print(f"\nAvailable options:")
        print(f"  - Run with --list-regions to see all available regions")
        return 1

    print("\n" + "="*70, flush=True)
    print(f"  ENSURE REGION: {region_info['display_name'].upper()}", flush=True)
    print(f"  Type: {region_type.replace('_', ' ').title()}", flush=True)
    print("="*70, flush=True)
    summarize_pipeline_status(region_id, region_type, region_info)

    # Check if pipeline is already complete
    if not args.force_reprocess and check_pipeline_complete(region_id):
        print(f"\n  Region '{region_id}' is already complete and ready!")
        print(f"\n  To view:")
        print(f"    python serve_viewer.py")
        print(f"    Visit http://localhost:8001 and select '{region_id}'")
        print(f"\n  To force rebuild: add --force-reprocess flag")
        return 0

    # Determine dataset early (stages 2-3) - includes resolution selection
    dataset_override = determine_dataset_override(region_id, region_type, region_info, args.target_pixels)

    # Check if raw data exists (stage 4)
    print(f"\n[STAGE 4/10] Checking raw elevation data...", flush=True)
    
    # Calculate visible pixel size and minimum required resolution
    visible = calculate_visible_pixel_size(region_info['bounds'], args.target_pixels)
    
    # Determine available download resolutions based on region type
    # US states: 10m USGS 3DEP now available via automated API, plus 30m/90m via OpenTopography
    # US AREA regions: Can also use 10m USGS 3DEP
    # International: 30m/90m via OpenTopography API only
    if region_type == RegionType.USA_STATE:
        available_downloads = [10, 30, 90]  # USGS 3DEP 10m + SRTM/Copernicus 30m/90m
    elif region_type == RegionType.AREA:
        # Check if AREA region is in the US (can use USGS 3DEP 10m)
        is_us_region = False
        try:
            config = ALL_REGIONS.get(region_id)
            if config and config.country == "United States of America":
                is_us_region = True
        except Exception:
            pass
        available_downloads = [10, 30, 90] if is_us_region else [30, 90]
    elif region_type == RegionType.COUNTRY:
        available_downloads = [30, 90]  # SRTM/Copernicus via OpenTopography API only
    else:
        raise ValueError(f"Unknown region type: {region_type}")
    
    # Calculate minimum required resolution using Nyquist rule
    try:
        min_required_resolution = determine_min_required_resolution(
            visible['avg_m_per_pixel'],
            available_resolutions=available_downloads
        )
    except ValueError:
        # Need finer than available - will handle in determine_data_source with accept_lower_quality
        min_required_resolution = min(available_downloads)
    
    # Build local cache dict by checking what files exist
    local_cache = {}
    for res in [10, 30, 90]:
        cached_path, cached_source = find_raw_file(region_id, verbose=False, min_required_resolution_meters=res)
        if cached_path and cached_source:
            # Extract resolution from source
            res_map = {'usa_3dep': 10, 'srtm_30m': 30, 'srtm_90m': 90}
            actual_res = res_map.get(cached_source, res)
            if actual_res not in local_cache:  # Only add if not already present
                local_cache[actual_res] = cached_path
    
    # Use the decision function to determine what to do
    bounds = region_info['bounds']
    latitude_range = (bounds[1], bounds[3])  # (south, north)
    
    decision = determine_data_source(
        region_id=region_id,
        min_required_resolution=min_required_resolution,
        available_downloads=available_downloads,
        local_cache=local_cache,
        accept_lower_quality=args.yes,  # --yes flag means accept lower quality
        latitude_range=latitude_range
    )
    
    # Handle the decision
    print(f"  Requirement: {min_required_resolution}m resolution (visible pixels: ~{visible['avg_m_per_pixel']:.0f}m each)", flush=True)
    
    if decision.action == "USE_LOCAL":
        print(f"  Found: {decision.message}", flush=True)
        raw_path = decision.file_path
        source = {10: 'usa_3dep', 30: 'srtm_30m', 90: 'srtm_90m'}.get(decision.resolution, 'srtm_30m')
    
    elif decision.action == "ERROR_NEED_MANUAL":
        print(f"\n{'='*70}", flush=True)
        print(f"  ERROR: Manual Download Required", flush=True)
        print(f"{'='*70}", flush=True)
        print(f"\n  {decision.message}", flush=True)
        return 1
    
    elif decision.action == "ERROR_INSUFFICIENT":
        print(f"\n{'='*70}", flush=True)
        print(f"  ERROR: Insufficient Resolution", flush=True)
        print(f"{'='*70}", flush=True)
        print(f"\n  {decision.message}", flush=True)
        return 1
    
    elif decision.action == "DOWNLOAD":
        print(f"  {decision.message}", flush=True)
        raw_path = None
        source = None
    
    else:
        print(f"  ERROR: Unknown decision action: {decision.action}", flush=True)
        return 1

    if not raw_path:
        print(f"  No raw data found for {region_id}", flush=True)

        if args.check_only:
            print(f"  Use without --check-only to download", flush=True)
            return 1

        # Download raw data
        print(f"[STAGE 4/10] Downloading...", flush=True)
        try:
            if not download_region(region_id, region_type, region_info, dataset_override, args.target_pixels):
                print(f"  Download failed!", flush=True)
                return 1
        except OpenTopographyRateLimitError as e:
            print(f"\n{'='*70}")
            print(f"  RATE LIMIT ERROR: OpenTopography returned 401 Unauthorized")
            print(f"{'='*70}")
            print(f"  {str(e)}")
            print(f"\n  What this means:")
            print(f"  - You've hit OpenTopography's rate limit or daily quota")
            print(f"  - This is normal when downloading many regions")
            print(f"\n  What to do:")
            print(f"  - Wait 15-30 minutes before trying again")
            print(f"  - Or try again tomorrow if you've hit daily limit")
            print(f"  - The API will work again once the limit resets")
            print(f"\n  Your progress is saved - tiles already downloaded are cached.")
            print(f"{'='*70}\n")
            return 1

        # Re-validate the downloaded file
        print(f"  Validating...", flush=True)
        raw_path, source = find_raw_file(region_id, min_required_resolution_meters=min_required_resolution)
        if not raw_path:
            print(f"  Validation failed - file may be corrupted", flush=True)
            # Show expected abstract filename
            bounds = region_info.get('bounds')
            if bounds:
                expected_filename = bbox_filename_from_bounds(bounds, '30m')
                print(f"  Expected: data/raw/srtm_30m/{expected_filename}", flush=True)
            else:
                print(f"  Expected: data/raw/srtm_30m/bbox_{{bounds}}_srtm_30m_30m.tif", flush=True)
            return 1
        print(f"  Downloaded successfully", flush=True)
    else:
        print(f"  Found: {raw_path.name} ({source})", flush=True)

    if args.check_only:
        print(f"  Use without --check-only to process")
        return 0

    # Step 3: Process the region
    # Always use 10m borders for accurate clipping (see .cursorrules - Border Resolution section)
    success, result_paths = process_region(region_id, raw_path, source, args.target_pixels,
                                          args.force_reprocess, region_type, region_info, '10m')

    if success:
        # Post-validate and auto-fix if needed
        ensured = verify_and_auto_fix(region_id, result_paths, source, args.target_pixels,
                                      region_type, region_info, '10m')
        if not ensured:
            print("\n" + "="*70)
            print(f"  FAILED: Auto-fix could not repair {region_info['display_name']}")
            print("="*70)
            return 1
        
        # Step 4 (optional): Update adjacency data if requested
        if args.update_adjacency:
            print("\n" + "="*70)
            print("  Updating adjacency data...")
            print("="*70)
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, 'compute_adjacency.py'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                print(result.stdout)
                print("  Adjacency data updated successfully")
            except subprocess.CalledProcessError as e:
                print(f"  WARNING: Failed to update adjacency data")
                print(f"  You may need to run: python compute_adjacency.py")
                if e.stdout:
                    print(f"  Output: {e.stdout}")
                if e.stderr:
                    print(f"  Error: {e.stderr}")
        
        print("\n" + "="*70)
        print(f"  SUCCESS: {region_info['display_name']} is ready to view!")
        print("="*70)
        print(f"\nNext steps:")
        print(f"  1. python serve_viewer.py")
        print(f"  2. Visit http://localhost:8001/interactive_viewer_advanced.html")
        print(f"  3. Select '{region_id}' from dropdown")
        if not args.update_adjacency and region_type in [RegionType.USA_STATE, RegionType.COUNTRY]:
            print(f"\nNote: To update neighbor connections, run:")
            print(f"  python compute_adjacency.py")
        return 0
    else:
        print("\n" + "="*70)
        print(f"  FAILED: Could not process {region_info['display_name']}")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())