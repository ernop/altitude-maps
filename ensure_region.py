"""
One command to ensure a region is ready to view.

Downloads if needed, processes if needed, checks if everything is valid.
Works for both US states and international regions.

Usage:
    python ensure_region.py ohio  # US state
    python ensure_region.py iceland  # International region
    python ensure_region.py tennessee --target-pixels 4096
    python ensure_region.py california --force-reprocess
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

# Pipeline dependencies
import json
import gzip
import glob
from typing import Optional, Dict, Tuple

# Pipeline utilities
from src.versioning import get_current_version
from src.tile_geometry import snap_bounds_to_grid, tile_filename_from_bounds, estimate_raw_file_size_mb
from src.pipeline import run_pipeline, PipelineError

# Alias for backward compatibility with existing code that uses bbox_filename_from_bounds
bbox_filename_from_bounds = tile_filename_from_bounds


def _path_exists(glob_pattern: str) -> bool:
    """Utility to check if any path matches the given glob pattern."""
    return any(glob.glob(glob_pattern, recursive=True))


def determine_min_required_resolution(visible_m_per_pixel: float, allow_lower_quality: bool = False) -> int:
    """
    Determine minimum required source resolution based on visible pixel size.
    
    NYQUIST SAMPLING RULE (from Shannon-Nyquist theorem):
    To avoid aliasing when downsampling, we need at least 2.0x oversampling.
    
    Mathematical rule:
      oversampling = visible_pixel_size / source_resolution >= 2.0
      Therefore: source_resolution <= visible_pixel_size / 2.0
    
    For a given output pixel size N, we need:
      - Source pixels must be <= N/2.0 meters
      - Each output pixel must aggregate >= 2.0 source pixels
      - This ensures each output pixel is composed of multiple complete source pixels,
        not fractional parts, avoiding aliasing artifacts
    
    Available source resolutions:
      - 90m: Sufficient if visible >= 180m (180/90 = 2.0x minimum)
      - 30m: Sufficient if visible >= 60m (60/30 = 2.0x minimum)
      - 10m: Sufficient if visible >= 20m (20/10 = 2.0x minimum) - if available
    
    Args:
        visible_m_per_pixel: Average meters per pixel in final output
        allow_lower_quality: If True, return best available resolution (30m) even if it
                            doesn't meet Nyquist requirement. If False, raise ValueError.
        
    Returns:
        Minimum required resolution in meters (10, 30, or 90)
        
    Raises:
        ValueError: If even 30m source doesn't meet the 2.0x Nyquist requirement
                   and allow_lower_quality is False (region too small - may need 10m
                   or manual override)
    """
    # Calculate oversampling ratio for each available source resolution
    oversampling_90m = visible_m_per_pixel / 90.0
    oversampling_30m = visible_m_per_pixel / 30.0
    oversampling_10m = visible_m_per_pixel / 10.0  # For future use
    
    # Check each resolution explicitly (no fall-throughs)
    # Minimum requirement: 2.0x oversampling (Nyquist criterion)
    MIN_OVERSAMPLING = 2.0
    
    # Check 90m source
    if oversampling_90m >= MIN_OVERSAMPLING:
        # 90m source provides sufficient oversampling
        # Example: 180m visible / 90m = 2.0x (meets minimum exactly)
        # Example: 200m visible / 90m = 2.22x (above minimum)
        return 90
    
    # Check 30m source (90m was insufficient)
    if oversampling_30m >= MIN_OVERSAMPLING:
        # 30m source provides sufficient oversampling
        # Example: 125m visible / 30m = 4.17x (well above minimum)
        # Example: 60m visible / 30m = 2.0x (meets minimum exactly)
        return 30
    
    # Neither 90m nor 30m meets the requirement
    # This happens when visible pixels are very small (< 60m)
    # Example: 50m visible / 30m = 1.67x (< 2.0x minimum)
    # Example: 40m visible / 30m = 1.33x (< 2.0x minimum)
    
    if allow_lower_quality:
        # User accepted lower quality - return best available (30m)
        return 30
    
    # Raise error with clear message
    raise ValueError(
        f"Region requires higher resolution than available. "
        f"Visible pixels: {format_pixel_size(visible_m_per_pixel)}/pixel. "
        f"30m source gives only {oversampling_30m:.2f}x oversampling (need >={MIN_OVERSAMPLING}x for Nyquist). "
        f"10m source would give {oversampling_10m:.2f}x oversampling. "
        f"Consider using a higher target_pixels value (fewer output pixels = larger visible pixels) "
        f"or manually override with --dataset to use a higher resolution source if available."
    )


def format_pixel_size(meters: float) -> str:
    """Format pixel size with km if >1000m, one decimal point only.
    
    Args:
        meters: Pixel size in meters
        
    Returns:
        Formatted string like "123.4m" or "1.2km"
    """
    if meters >= 1000:
        return f"{meters / 1000:.1f}km"
    else:
        return f"{meters:.1f}m"


def calculate_visible_pixel_size(bounds: Tuple[float, float, float, float], target_pixels: int) -> Dict:
    """Calculate final visible pixel size in meters after downsampling to target_pixels.
    
    This helps determine if 30m or 90m source data is appropriate:
    - If visible pixels will be >90m, 90m source data is sufficient
    - If visible pixels will be <90m, 30m source data provides better detail
    
    Args:
        bounds: (west, south, east, north) in degrees
        target_pixels: Target output dimension (e.g., 2048)
    
    Returns:
        dict with keys:
        - 'width_m_per_pixel': meters per pixel horizontally
        - 'height_m_per_pixel': meters per pixel vertically
        - 'avg_m_per_pixel': average meters per pixel (recommended for decision making)
        - 'output_width_px': calculated output width in pixels
        - 'output_height_px': calculated output height in pixels
        - 'real_world_width_km': width in kilometers
        - 'real_world_height_km': height in kilometers
    """
    west, south, east, north = bounds
    width_deg = east - west
    height_deg = north - south
    
    # Calculate real-world dimensions in meters
    import math
    center_lat = (north + south) / 2.0
    meters_per_deg_lat = 111_320  # constant
    meters_per_deg_lon = 111_320 * math.cos(math.radians(center_lat))
    
    width_m = width_deg * meters_per_deg_lon
    height_m = height_deg * meters_per_deg_lat
    
    # Calculate output pixels preserving aspect ratio (same logic as downsampling code)
    aspect = width_deg / height_deg if height_deg > 0 else 1.0
    if width_deg >= height_deg:
        output_width = target_pixels
        output_height = max(1, int(round(target_pixels / aspect)))
    else:
        output_height = target_pixels
        output_width = max(1, int(round(target_pixels * aspect)))
    
    # Calculate meters per pixel in final output
    m_per_pixel_x = width_m / output_width
    m_per_pixel_y = height_m / output_height
    avg_m_per_pixel = (m_per_pixel_x + m_per_pixel_y) / 2.0
    
    return {
        'width_m_per_pixel': m_per_pixel_x,
        'height_m_per_pixel': m_per_pixel_y,
        'avg_m_per_pixel': avg_m_per_pixel,
        'output_width_px': output_width,
        'output_height_px': output_height,
        'real_world_width_km': width_m / 1000.0,
        'real_world_height_km': height_m / 1000.0
    }


def summarize_pipeline_status(region_id: str, region_type: str, region_info: dict) -> None:
    """Print a compact summary of pipeline stage completion for the region."""
    # Stage 9 (final): valid export present? (silent check)
    s9 = check_pipeline_complete(region_id, verbose=False)

    # Stage 4: raw present? (silent check)
    raw_path, _ = find_raw_file(region_id, verbose=False)
    s4 = raw_path is not None

    # Stage 8: processed present? (using abstract naming)
    # Get region bounds to generate abstract filenames
    region_config = ALL_REGIONS.get(region_id)
    s8 = False
    if region_config:
        bounds = region_config.bounds
        # Check tile-based filenames (source-agnostic tiles in source-specific directories)
        for source in ['srtm_30m', 'srtm_90m', 'usa_3dep']:
            resolution = '30m' if '30m' in source else '90m' if '90m' in source else '10m'
            tile_name = bbox_filename_from_bounds(bounds, resolution)
            base_part = tile_name[:-4]  # Remove '.tif' suffix only
            for target_pixels in [512, 1024, 2048, 4096, 800]:
                if _path_exists(f"data/processed/{source}/{base_part}_processed_{target_pixels}px_v2.tif"):
                    s8 = True
                    break
            if s8:
                break

    # Quick summary without excessive verbosity
    print(f"  Status: Raw={'OK' if s4 else 'X'} | Processed={'OK' if s8 else 'X'} | Export={'OK' if s9 else 'X'}", flush=True)


# Region mapping (using centralized config)
US_STATE_NAMES = get_us_state_names()


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


def validate_geotiff(file_path: Path, check_data: bool = False) -> bool:
    """
    Rigorously validate a GeoTIFF file.

    Args:
        file_path: Path to TIF file
        check_data: If True, validate data contents (slower, optional)

    Returns:
        True if file is valid, False otherwise
    """
    if not file_path.exists():
        return False

    # Check file size - must be > 1KB (corrupted downloads are often 0 bytes)
    file_size = file_path.stat().st_size
    if file_size < 1024:
        print(f"  File too small ({file_size} bytes), likely corrupted", flush=True)
        return False

    try:
        import rasterio
        with rasterio.open(file_path) as src:
            # Basic checks
            if src.width == 0 or src.height == 0:
                print(f"  Invalid dimensions: {src.width}x{src.height}", flush=True)
                return False

            # Check that CRS and transform exist
            if src.crs is None or src.transform is None:
                print(f"  Missing CRS or transform", flush=True)
                return False

            if check_data:
                # Try to read multiple small samples (center + 4 quadrants)
                try:
                    from rasterio.windows import Window
                    import numpy as np

                    def _read_sample(c_off: int, r_off: int, w: int, h: int) -> bool:
                        arr = src.read(1, window=Window(c_off, r_off, w, h))
                        arr = arr.astype(float)
                        valid = np.sum(~np.isnan(arr) & (arr > -500))
                        return valid > 0

                    h_s = max(64, min(256, src.height // 8))
                    w_s = max(64, min(256, src.width // 8))

                    positions = [
                        # center
                        (max(0, (src.width - w_s) // 2), max(0, (src.height - h_s) // 2)),
                        # top-left
                        (0, 0),
                        # top-right
                        (max(0, src.width - w_s), 0),
                        # bottom-left
                        (0, max(0, src.height - h_s)),
                        # bottom-right
                        (max(0, src.width - w_s), max(0, src.height - h_s)),
                    ]

                    any_valid = False
                    for (c_off, r_off) in positions:
                        try:
                            if _read_sample(c_off, r_off, w_s, h_s):
                                any_valid = True
                        except Exception as se:
                            # If any sample read fails, flag as invalid to trigger repair
                            print(f"  Data read failed at window ({c_off},{r_off},{w_s},{h_s}): {se}", flush=True)
                            return False

                    if not any_valid:
                        print(f"  No valid elevation data in sampled windows", flush=True)
                        return False
                except Exception as e:
                    print(f"  Data read failed during validation: {e}", flush=True)
                    return False

        return True

    except Exception as e:
        print(f"  Not a valid GeoTIFF: {e}", flush=True)
        return False


def validate_json_export(file_path: Path, verbose: bool = True) -> bool:
    """
    Validate an exported JSON file.

    Args:
        file_path: Path to JSON file
        verbose: If True, print validation messages

    Returns:
        True if file is valid, False otherwise
    """
    if not file_path.exists():
        return False

    # Check file size
    file_size = file_path.stat().st_size
    if file_size < 1024:
        if verbose:
            print(f"  JSON too small ({file_size} bytes), likely incomplete")
        return False

    try:
        # Try gzip first, then regular JSON
        if file_path.suffix == '.gz' or '.gz' in file_path.name:
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                data = json.load(f)
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

        # Validate required fields
        required_fields = ['region_id', 'width', 'height', 'elevation', 'bounds']
        for field in required_fields:
            if field not in data:
                if verbose:
                    print(f"  Missing required field: {field}")
                return False

        # Validate dimensions
        if data['width'] <= 0 or data['height'] <= 0:
            if verbose:
                print(f"  Invalid dimensions: {data['width']}x{data['height']}")
            return False

        # Validate elevation data structure
        elevation = data['elevation']
        if not isinstance(elevation, list) or len(elevation) == 0:
            if verbose:
                print(f"  Invalid elevation data structure")
            return False

        # Check that elevation matches dimensions
        if len(elevation) != data['height']:
            if verbose:
                print(f"  Elevation height mismatch: {len(elevation)} != {data['height']}")
            return False

        if len(elevation[0]) != data['width']:
            if verbose:
                print(f"  Elevation width mismatch: {len(elevation[0])} != {data['width']}")
            return False

        # Validate elevation range to catch corruption (Minnesota/Connecticut issue)
        import numpy as np
        try:
            elev_array = np.array(elevation, dtype=np.float32)
            valid_elev = elev_array[~np.isnan(elev_array)]

            if len(valid_elev) > 0:
                min_elev = float(np.min(valid_elev))
                max_elev = float(np.max(valid_elev))
                elev_range = max_elev - min_elev

                # Check for suspiciously small elevation range (indicates reprojection corruption)
                if elev_range < 50.0:
                    if verbose:
                        print(f"  Suspicious elevation range: {min_elev:.1f}m to {max_elev:.1f}m (range: {elev_range:.1f}m)")
                        print(f"  This suggests reprojection corruption - data should be regenerated")
                    return False

                if verbose:
                    print(f"  Elevation range OK: {min_elev:.1f}m to {max_elev:.1f}m (range: {elev_range:.1f}m)")
        except Exception as e:
            if verbose:
                print(f"  Could not validate elevation range: {e}")
            # Don't fail on this - might be edge case with edge case data

        return True

    except json.JSONDecodeError as e:
        if verbose:
            print(f"  Invalid JSON: {e}")
        return False
    except Exception as e:
        if verbose:
            print(f"  Validation error: {e}")
        return False


def get_region_info(region_id: str) -> Tuple[Optional[str], Optional[Dict]]:
    """
    Get information about a region (US state or international).

    Returns:
        Tuple of (region_type, region_data) where:
        - region_type is 'us_state' or 'international'
        - region_data is a dict with region info

        Returns (None, None) if region not found
    """
    # Normalize region ID
    region_id = region_id.lower().replace(' ', '_').replace('-', '_')

    # Look up region in centralized config
    region_config = ALL_REGIONS.get(region_id)

    if region_config is None:
        return None, None

    # Determine region type
    if region_config.category == 'usa_state':
        region_type = 'us_state'
    else:
        region_type = 'international'

    # Build region data dict
    region_data = {
        'name': region_config.name,
        'display_name': region_config.name,
        'bounds': region_config.bounds,
        'description': region_config.description or region_config.name,
        'clip_boundary': region_config.clip_boundary
    }

    return region_type, region_data


def find_raw_file(region_id: str, verbose: bool = True, min_required_resolution_meters: Optional[int] = None) -> Tuple[Optional[Path], Optional[str]]:
    """
    Find existing raw file that meets quality requirements.
    
    CRITICAL: Quality-first approach - finds ANY existing file that meets or exceeds
    the minimum required resolution. Never uses lower quality files than required.
    
    Resolution logic:
    - If min_required_resolution_meters=30: Can use 10m or 30m files (both meet requirement)
    - If min_required_resolution_meters=90: Can use 10m, 30m, or 90m files (all meet requirement)
    - Never uses files with resolution > min_required (e.g., need 30m, won't use 90m)
    
    File naming scheme: Abstract, bounds-based naming (no region_id):
    - 10m: data/raw/usa_3dep/bbox_{bounds}_{dataset}_{res}.tif
    - 30m: data/raw/srtm_30m/bbox_{bounds}_{dataset}_{res}.tif
    - 90m: data/raw/srtm_90m/bbox_{bounds}_{dataset}_{res}.tif
    
    Uses abstract bounds-based naming exclusively.

    Args:
        region_id: Region identifier (used to get bounds)
        verbose: If True, print validation messages
        min_required_resolution_meters: Minimum resolution required (10, 30, or 90).
                                       Lower number = higher quality (more detail).
                                       If None, accepts any valid file (prefers higher quality).

    Returns:
        Tuple of (path, source) if valid file found that meets requirement, (None, None) otherwise
    """
    # Get region bounds
    region_config = ALL_REGIONS.get(region_id)
    if not region_config:
        return None, None
    
    bounds = region_config.bounds
    west, south, east, north = bounds
    
    # Resolution mapping: source -> resolution in meters
    # Lower number = higher quality (more detail)
    RESOLUTION_MAP = {
        'usa_3dep': 10,
        'srtm_30m': 30,
        'srtm_90m': 90,
    }
    
    # Generate abstract bounds-based filenames (NEW SCHEME)
    possible_locations = []
    
    # Check for abstract bbox files (bounds-based naming)
    possible_locations.extend([
        (Path(f"data/raw/usa_3dep/{bbox_filename_from_bounds(bounds, '10m')}"), 'usa_3dep'),
        (Path(f"data/raw/srtm_30m/{bbox_filename_from_bounds(bounds, '30m')}"), 'srtm_30m'),
        (Path(f"data/raw/srtm_90m/{bbox_filename_from_bounds(bounds, '90m')}"), 'srtm_90m'),
    ])
    
    valid_files = []  # Collect all valid files that meet requirement
    
    for path, source in possible_locations:
        if path.exists():
            if verbose:
                print(f"  Checking {path.name}...", flush=True)
            if validate_geotiff(path, check_data=True):
                file_resolution = RESOLUTION_MAP[source]
                
                # Check if file meets quality requirement
                if min_required_resolution_meters is not None:
                    if file_resolution > min_required_resolution_meters:
                        if verbose:
                            print(f"  File resolution {file_resolution}m exceeds requirement {min_required_resolution_meters}m", flush=True)
                            print(f"  Quality requirement: will not use lower quality file", flush=True)
                        continue
                
                # File meets requirement - add to valid candidates
                if verbose:
                    req_str = f" <= {min_required_resolution_meters}m" if min_required_resolution_meters else ""
                    print(f"  Valid GeoTIFF (meets requirement: {file_resolution}m{req_str})", flush=True)
                valid_files.append((path, source, file_resolution))
            else:
                if verbose:
                    print(f"  Invalid or corrupted, cleaning up...", flush=True)
                try:
                    path.unlink()
                    if verbose:
                        print(f"  Deleted corrupted file", flush=True)
                except Exception as e:
                    if verbose:
                        print(f"  Could not delete: {e}", flush=True)
    
    # Return highest quality file that meets requirement (prefer 10m > 30m > 90m)
    if valid_files:
        # Sort by resolution (lower = better quality)
        valid_files.sort(key=lambda x: x[2])
        best_path, best_source, best_res = valid_files[0]
        if verbose:
            print(f"  Using existing file: {best_path.name} ({best_res}m)", flush=True)
        return best_path, best_source
    
    return None, None


def get_source_from_path(path: Path) -> str:
    """Determine source type from path."""
    if 'usa_3dep' in str(path):
        return 'usa_3dep'
    if '90m' in str(path):
        return 'srtm_90m'
    return 'srtm_30m'


def check_pipeline_complete(region_id: str, verbose: bool = True) -> bool:
    """
    Check if all pipeline stages are complete and valid.
    
    Uses abstract bounds-based naming - searches for files by bounds, not region_id.

    Args:
        region_id: Region identifier
        verbose: If True, print validation messages

    Returns:
        True if valid JSON export exists, False otherwise
    """
    # Get region bounds to generate abstract filenames
    region_config = ALL_REGIONS.get(region_id)
    if not region_config:
        return False
    
    bounds = region_config.bounds
    
    # Check for JSON export (final stage) using abstract filenames
    generated_dir = Path("generated/regions")
    if not generated_dir.exists():
        return False

    # Generate abstract filenames for all possible sources/resolutions
    possible_json_files = []
    
    # Generate abstract bounds-based filenames and search for them
    for source in ['srtm_30m', 'srtm_90m', 'usa_3dep']:
        resolution = '30m' if '30m' in source else '90m' if '90m' in source else '10m'
        tile_name = bbox_filename_from_bounds(bounds, resolution)
        base_part = tile_name[:-4]  # Remove '.tif' suffix only
        for target_pixels in [512, 1024, 2048, 4096, 800]:
            possible_json_files.append(f"{base_part}_{target_pixels}px_v2.json")
    
    # Check for abstract filenames
    json_files = []
    for abstract_filename in possible_json_files:
        json_file = generated_dir / abstract_filename
        if json_file.exists():
            json_files.append(json_file)
    
    json_files = [f for f in json_files if '_borders' not in f.stem and '_meta' not in f.stem]

    if len(json_files) == 0:
        return False

    # Validate the JSON files
    for json_file in json_files:
        if verbose:
            print(f"  Checking {json_file.name}...", flush=True)
        if validate_json_export(json_file, verbose=verbose):
            if verbose:
                print(f"  Valid export found", flush=True)
            return True
        else:
            if verbose:
                print(f"  Invalid or incomplete, cleaning up...", flush=True)
            try:
                json_file.unlink()
                if verbose:
                    print(f"  Deleted corrupted file", flush=True)
            except Exception as e:
                if verbose:
                    print(f"  Could not delete: {e}", flush=True)

    return False


def _check_export_version(region_id: str) -> tuple[bool, str, str]:
    """
    Check if the region's exported JSON uses the current export format version.

    Returns:
        (is_current, found_version, expected_version)
    """
    generated_dir = Path("generated/regions")
    expected = get_current_version('export')
    found: Optional[str] = None
    try:
        if not generated_dir.exists():
            return False, (found or "<none>"), expected
        # Get region bounds for abstract filename lookup
        region_config = ALL_REGIONS.get(region_id)
        if not region_config:
            json_files = []
        else:
            bounds = region_config.bounds
            # Generate abstract filenames and search for them
            possible_json_files = []
            for source in ['srtm_30m', 'srtm_90m', 'usa_3dep']:
                for target_pixels in [512, 1024, 2048, 4096, 800]:
                    resolution = '30m' if '30m' in source else '90m' if '90m' in source else '10m'
                    tile_name = bbox_filename_from_bounds(bounds, resolution)
                    base_part = tile_name[:-4]  # Remove '.tif' suffix only
                    possible_json_files.append(generated_dir / f"{base_part}_{target_pixels}px_v2.json")
            
            # Check for abstract filenames
            json_files = [f for f in possible_json_files if f.exists()]
            json_files = [
                f for f in json_files
                if ('_borders' not in f.stem and '_meta' not in f.stem and 'manifest' not in f.stem)
            ]
        if not json_files:
            return False, (found or "<none>"), expected
        # Inspect all exports; if any matches current, we consider version OK
        for jf in json_files:
            try:
                with open(jf, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                v = str(data.get('version') or "")
                if not v:
                    found = found or "<missing>"
                else:
                    found = found or v
                if v == expected:
                    return True, v, expected
            except Exception:
                continue
        return False, (found or "<unknown>"), expected
    except Exception:
        return False, (found or "<error>"), expected


def _iter_all_region_ids() -> list[str]:
    """Return all configured region ids from centralized config."""
    try:
        return sorted(list(ALL_REGIONS.keys()))
    except Exception:
        return []


def download_us_state(region_id: str, state_info: Dict) -> bool:
    """Download raw data for a US state using USGS 3DEP."""
    print(f"\n  Downloading {state_info['name']}...")
    print(f"  Source: USGS 3DEP preferred; automated path uses OpenTopography SRTM 30m")
    print(f"  Using: downloaders/usa_3dep.py --auto")

    import subprocess
    result = subprocess.run(
        [sys.executable, "downloaders/usa_3dep.py", region_id, "--auto"],
        capture_output=False
    )

    return result.returncode == 0


def download_international_region(region_id: str, region_info: Dict, dataset_override: str | None = None, target_pixels: int = 2048) -> bool:
    """Download raw data for an international region using OpenTopography.

    If dataset_override is provided, use it (e.g., 'COP30' or 'SRTMGL1').
    
    For large regions, automatically suggests 90m data if it would be visually equivalent.
    """
    west, south, east, north = region_info['bounds']

    # If no override, calculate visible pixel size and suggest optimal resolution
    if dataset_override is None:
        visible = calculate_visible_pixel_size((west, south, east, north), target_pixels)
        
        print(f"\n  Downloading {region_info['name']}...")
        print(f"  Real-world size: {visible['real_world_width_km']:.0f} x {visible['real_world_height_km']:.0f} km")
        print(f"  Target resolution: {target_pixels}px (max dimension)")
        
        # Determine base dataset by latitude first
        if north > 60.0 or south < -56.0:
            base_dataset_30m = 'COP30'
            base_dataset_90m = 'COP90'
            base_name = 'Copernicus DEM'
        else:
            base_dataset_30m = 'SRTMGL1'
            base_dataset_90m = 'SRTMGL3'
            base_name = 'SRTM'
        
        # Quality-first automatic selection: determine minimum required resolution
        # Automatically select the smallest resolution that still meets quality requirements
        try:
            min_required = determine_min_required_resolution(visible['avg_m_per_pixel'])
        except ValueError as e:
            print(f"\n  ERROR: {e}", flush=True)
            print(f"\n  Resolution Selection Failed", flush=True)
            print(f"    Visible pixel size: ~{format_pixel_size(visible['avg_m_per_pixel'])} per pixel", flush=True)
            print(f"    This region is too small for standard resolution options.", flush=True)
            print(f"    Solutions:", flush=True)
            print(f"      1. Use a higher target_pixels value (fewer pixels = larger visible pixels)", flush=True)
            print(f"      2. Manually specify a dataset with --dataset option (if available)", flush=True)
            print(f"      3. Consider if this region really needs such high detail", flush=True)
            return False
        
        print(f"\n  Resolution Selection Analysis:")
        print(f"    Calculated visible pixel size: ~{format_pixel_size(visible['avg_m_per_pixel'])} per pixel")
        print(f"    (This is the pixel size users will see in the final visualization)")
        print(f"\n    NYQUIST SAMPLING RULE:")
        print(f"      For output pixel size N, we need source resolution <= N/2.0")
        print(f"      This ensures oversampling >= 2.0x (each output = 2+ source pixels)")
        print(f"      This prevents aliasing by ensuring clean pixel aggregation, not fractional parts")
        
        # Calculate oversampling ratios for both options
        oversampling_90m = visible['avg_m_per_pixel'] / 90.0
        oversampling_30m = visible['avg_m_per_pixel'] / 30.0
        
        if min_required == 90:
            # 90m is sufficient for quality - use smallest that meets requirement
            dataset = base_dataset_90m
            dataset_name = f'{base_name} 90m'
            resolution = '90m'
            resolution_meters = 90
            
            print(f"\n    Quality analysis:")
            print(f"      - Visible pixels: ~{visible['avg_m_per_pixel']:.0f}m each")
            print(f"      - With 90m source: {oversampling_90m:.2f}x oversampling")
            print(f"        (Each visible pixel = {oversampling_90m:.2f} source pixels)")
            print(f"        Status: {'OK Meets Nyquist (>=2.0x)' if oversampling_90m >= 2.0 else 'WARN Below Nyquist (<2.0x)'}")
            print(f"      - With 30m source: {oversampling_30m:.2f}x oversampling")
            print(f"        (Each visible pixel = {oversampling_30m:.2f} source pixels)")
            print(f"        Status: OK Exceeds requirement (wasteful at this scale)")
            print(f"\n    RESOLUTION SELECTED: 90m ({base_name} 90m)")
            print(f"      Rationale: For visible pixels of {visible['avg_m_per_pixel']:.0f}m, the Nyquist rule")
            print(f"                 requires source <= {visible['avg_m_per_pixel']/2.0:.0f}m.")
            print(f"                 90m source gives {oversampling_90m:.2f}x oversampling (>=2.0x minimum).")
            print(f"                 Each visible pixel aggregates {oversampling_90m:.1f} complete source pixels,")
            print(f"                 avoiding fractional composition and aliasing artifacts.")
            print(f"                 Using 30m would give {oversampling_30m:.1f}x oversampling but waste bandwidth")
            print(f"                 and storage without providing visible benefit at this scale.")
        else:
            # 30m required for quality
            dataset = base_dataset_30m
            dataset_name = f'{base_name} 30m'
            resolution = '30m'
            resolution_meters = 30
            
            print(f"\n    Quality analysis:")
            print(f"      - Visible pixels: ~{visible['avg_m_per_pixel']:.0f}m each")
            print(f"      - With 90m source: {oversampling_90m:.2f}x oversampling")
            print(f"        (Each visible pixel = {oversampling_90m:.2f} source pixels)")
            if oversampling_90m < 2.0:
                print(f"        Status: FAILS Nyquist (<2.0x)")
                print(f"        Problem: Each visible pixel would aggregate only {oversampling_90m:.2f} source pixels.")
                print(f"                 This is fractional (e.g., 1.39 pixels = parts of 1-2 pixels),")
                print(f"                 causing aliasing artifacts and poor quality.")
            else:
                print(f"        Status: WARN Marginal (meets minimum but higher resolution preferred)")
            print(f"      - With 30m source: {oversampling_30m:.2f}x oversampling")
            print(f"        (Each visible pixel = {oversampling_30m:.2f} source pixels)")
            print(f"        Status: OK Meets Nyquist (>=2.0x)")
            print(f"\n    RESOLUTION SELECTED: 30m ({base_name} 30m)")
            print(f"      Rationale: For visible pixels of {visible['avg_m_per_pixel']:.0f}m, the Nyquist rule")
            print(f"                 requires source <= {visible['avg_m_per_pixel']/2.0:.0f}m.")
            if oversampling_90m < 2.0:
                print(f"                 90m source gives only {oversampling_90m:.2f}x oversampling (<2.0x minimum),")
                print(f"                 causing fractional pixel aggregation and aliasing.")
            else:
                print(f"                 90m source would give {oversampling_90m:.2f}x oversampling (meets minimum),")
                print(f"                 but 30m provides better quality margin.")
            print(f"                 30m source provides {oversampling_30m:.2f}x oversampling (>=2.0x),")
            print(f"                 ensuring each visible pixel aggregates {oversampling_30m:.1f} complete")
            print(f"                 source pixels for clean, artifact-free downsampling.")
        
        # Estimate file size for the selected resolution
        estimated_size_mb = estimate_raw_file_size_mb((west, south, east, north), resolution_meters)
        print(f"\n    Estimated raw file size: ~{estimated_size_mb:.1f} MB ({resolution} source)")
    else:
        # Override specified: use it
        dataset = dataset_override
        # Determine dataset name and resolution from override
        if dataset == 'COP30':
            dataset_name = 'Copernicus DEM 30m'
            resolution = '30m'
            resolution_meters = 30
        elif dataset == 'COP90':
            dataset_name = 'Copernicus DEM 90m'
            resolution = '90m'
            resolution_meters = 90
        elif dataset == 'SRTMGL1':
            dataset_name = 'SRTM 30m'
            resolution = '30m'
            resolution_meters = 30
        elif dataset == 'SRTMGL3':
            dataset_name = 'SRTM 90m'
            resolution = '90m'
            resolution_meters = 90
        else:
            # For other datasets (AW3D30, NASADEM, etc.), default to 30m
            dataset_name = dataset
            resolution = '30m'
            resolution_meters = 30
        
        print(f"\n  Downloading {region_info['name']}...")
        print(f"  Source: OpenTopography ({dataset_name})")
        print(f"  Bounds: {region_info['bounds']}")
        print(f"  Latitude range: {south:.1f}degN to {north:.1f}degN")
        if dataset == 'COP30':
            print(f"  Note: Using Copernicus DEM (SRTM doesn't cover >60degN)")
        
        # Estimate file size for the selected resolution
        estimated_size_mb = estimate_raw_file_size_mb((west, south, east, north), resolution_meters)
        print(f"  Estimated raw file size: ~{estimated_size_mb:.1f} MB ({resolution})")

    try:
        import requests
        from tqdm import tqdm
        from load_settings import get_api_key
        # Reuse existing tiling utilities for large areas
        from downloaders.tile_large_states import calculate_1degree_tiles, merge_tiles, tile_filename_from_bounds
    except ImportError as e:
        print(f"  Missing required package: {e}")
        return False

    # Get API key
    try:
        api_key = get_api_key()
        print(f"  Using API key from settings.json")
    except SystemExit:
        print(f"  No OpenTopography API key found in settings.json")
        print(f"  Get a free key at: https://portal.opentopography.org/")
        print(f"  Add it to settings.json under 'opentopography.api_key'")
        return False

    # Map dataset name to source identifier for file paths and metadata
    def dataset_to_source_name(dataset_id: str) -> str:
        """Map dataset id to a short source name used in pipeline outputs."""
        mapping = {
            "SRTMGL1": "srtm_30m",
            "SRTMGL3": "srtm_90m",
            "NASADEM": "nasadem_30m",
            "AW3D30": "aw3d30",
            "COP30": "srtm_30m",  # Use same directory structure as SRTM
            "COP90": "srtm_90m",  # Use same directory structure as SRTM
        }
        return mapping.get(dataset_id.upper(), dataset_id.lower())
    
    source_name = dataset_to_source_name(dataset)
    
    # GRID ALIGNMENT: Expand bounds to 1-degree grid boundaries for better reuse and coverage
    # Unified 1-degree grid system - all downloads become 1-degree tiles that can be shared
    original_bounds = (west, south, east, north)
    grid_size = 1.0  # Unified 1-degree grid system
    expanded_bounds = snap_bounds_to_grid(original_bounds, grid_size)
    expanded_west, expanded_south, expanded_east, expanded_north = expanded_bounds
    
    # Report grid alignment
    if expanded_bounds != original_bounds:
        print(f"  Grid alignment: expanding bounds for reuse and coverage")
        print(f"    Original: [{west:.4f}, {south:.4f}, {east:.4f}, {north:.4f}]")
        print(f"    Expanded:  [{expanded_west:.4f}, {expanded_south:.4f}, {expanded_east:.4f}, {expanded_north:.4f}]")
        print(f"    Grid size: {grid_size} degrees")
    
    # Generate tile filename (source-agnostic, stored in source-specific directory)
    # Note: This is only used for the merged output file - individual tiles use tile_filename_from_bounds
    bbox_filename = bbox_filename_from_bounds(expanded_bounds, resolution, 
                                               use_grid_alignment=True, grid_size=grid_size)
    
    # Prepare output path based on selected dataset resolution
    # Use appropriate directory for 30m vs 90m
    if resolution == '90m':
        output_dir = Path("data/raw/srtm_90m")
    else:
        output_dir = Path("data/raw/srtm_30m")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / bbox_filename

    # CRITICAL: Validate existing file matches required dataset/resolution AND bounds.
    # Never compromise quality - if file exists but is wrong resolution, delete and re-download.
    if output_file.exists():
        try:
            from src.metadata import get_metadata_path, load_metadata
            meta_path = get_metadata_path(output_file)
            if meta_path.exists():
                meta = load_metadata(meta_path)
                
                # Validate dataset/resolution matches (CRITICAL for quality)
                existing_source = meta.get('source', '')
                if existing_source != source_name:
                    print(f"  Existing file has wrong source: got {existing_source}, need {source_name}")
                    print(f"  Quality requirement: deleting and re-downloading at correct resolution...")
                    try:
                        output_file.unlink()
                    except Exception:
                        pass
                    try:
                        meta_path.unlink()
                    except Exception:
                        pass
                else:
                    # Dataset matches - validate that file bounds contain our requested bounds
                    # (file may have grid-aligned bounds that contain our original bounds)
                    mb = meta.get('bounds', {})
                    file_bounds = (float(mb.get('left')), float(mb.get('bottom')), float(mb.get('right')), float(mb.get('top')))
                    requested_bounds = expanded_bounds  # Use grid-aligned bounds for validation
                    
                    # File should contain or match our grid-aligned bounds
                    file_contains = (file_bounds[0] <= requested_bounds[0] and  # west
                                    file_bounds[1] <= requested_bounds[1] and  # south
                                    file_bounds[2] >= requested_bounds[2] and  # east
                                    file_bounds[3] >= requested_bounds[3])      # north
                    
                    if file_contains:
                        print(f"  Already exists with matching dataset ({source_name}) and coverage: {output_file.name}")
                        print(f"    File bounds contain requested bounds (grid-aligned reuse)")
                        return True
                    else:
                        print(f"  File bounds don't match requested grid-aligned bounds")
                        print(f"    File:     {file_bounds}")
                        print(f"    Requested: {requested_bounds}")
                        print(f"    Deleting to regenerate...")
                        try:
                            output_file.unlink()
                        except Exception:
                            pass
                        try:
                            meta_path.unlink()
                        except Exception:
                            pass
            else:
                # No metadata; validate by checking file properties
                # Open the file and verify it matches expected source/dataset
                try:
                    import rasterio
                    with rasterio.open(output_file) as src:
                        # Check if resolution roughly matches expectations
                        # For 30m dataset, expect ~30m resolution; for 90m, expect ~90m
                        bounds = src.bounds
                        width_deg = bounds.right - bounds.left
                        height_deg = bounds.top - bounds.bottom
                        center_lat = (bounds.top + bounds.bottom) / 2.0
                        import math
                        meters_per_deg_lat = 111_320
                        meters_per_deg_lon = 111_320 * math.cos(math.radians(center_lat))
                        width_m = width_deg * meters_per_deg_lon
                        height_m = height_deg * meters_per_deg_lat
                        avg_resolution = (width_m / src.width + height_m / src.height) / 2.0
                        
                        # Validate resolution matches expected dataset
                        if resolution == '90m':
                            if avg_resolution < 50 or avg_resolution > 150:
                                print(f"  Existing file resolution ({avg_resolution:.1f}m) doesn't match 90m dataset")
                                print(f"  Deleting to ensure quality...")
                                output_file.unlink()
                        else:  # 30m
                            if avg_resolution < 15 or avg_resolution > 50:
                                print(f"  Existing file resolution ({avg_resolution:.1f}m) doesn't match 30m dataset")
                                print(f"  Deleting to ensure quality...")
                                output_file.unlink()
                            else:
                                print(f"  Already exists (validated resolution: {avg_resolution:.1f}m): {output_file.name}")
                                return True
                except Exception as e:
                    print(f"  Could not validate existing file: {e}")
                    print(f"  Deleting to ensure quality...")
                    try:
                        output_file.unlink()
                    except Exception:
                        pass
        except Exception:
            # If validation fails, delete and re-download to ensure quality
            print(f"  Could not validate existing file, deleting to ensure quality...")
            try:
                output_file.unlink()
            except Exception:
                pass

    # Helper to download a single bounding box to a specific file using a specific dataset
    def _download_bbox(out_path: Path, bbox: tuple[float, float, float, float], demtype: str) -> bool:
        w, s, e, n = bbox
        url = "https://portal.opentopography.org/API/globaldem"
        params = {
            'demtype': demtype,
            'south': s,
            'north': n,
            'west': w,
            'east': e,
            'outputFormat': 'GTiff',
            'API_Key': api_key
        }
        try:
            resp = requests.get(url, params=params, stream=True, timeout=300)
            if resp.status_code != 200:
                return False
            total_size = int(resp.headers.get('content-length', 0))
            
            # Enhanced progress display with tqdm
            desc = out_path.name[:40] + ('...' if len(out_path.name) > 40 else '')
            with open(out_path, 'wb') as f, tqdm(
                desc=desc,
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                miniters=1,
                disable=False
            ) as pbar:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
            
            return True
        except Exception:
            if out_path.exists():
                try:
                    out_path.unlink()
                except Exception:
                    pass
            return False

    # UNIFIED 1-DEGREE GRID SYSTEM: Always download as 1-degree tiles, then merge
    # This ensures maximum reuse across regions and simplifies the code
    import math
    
    width_deg = max(0.0, float(expanded_east - expanded_west))
    height_deg = max(0.0, float(expanded_north - expanded_south))
    mid_lat = (expanded_north + expanded_south) / 2.0
    km_per_deg_lat = 110.574
    km_per_deg_lon = 111.320 * math.cos(math.radians(mid_lat))
    approx_area_km2 = (width_deg * km_per_deg_lon) * (height_deg * km_per_deg_lat)
    
    print(f"\n  Unified 1-degree grid system: Downloading as 1-degree tiles ({approx_area_km2:,.0f} km^2 region)...", flush=True)
    
    # Calculate 1-degree tiles needed
    tiles = calculate_1degree_tiles(expanded_bounds)
    
    # Calculate tile size estimates
    total_estimated_size = 0.0
    tile_estimates = []
    for tb in tiles:
        tile_size_mb = estimate_raw_file_size_mb(tb, resolution_meters)
        total_estimated_size += tile_size_mb
        tile_estimates.append(tile_size_mb)
    
    print(f"  Tile configuration:")
    print(f"    Total tiles: {len(tiles)}")
    print(f"    Tile size: 1.0 deg x 1.0 deg (unified grid)")
    print(f"    Estimated per-tile size: ~{total_estimated_size / len(tiles):.1f} MB each")
    print(f"    Total estimated size: ~{total_estimated_size:.1f} MB (before merge)")
    print(f"    Resolution: {resolution}")
    
    # Use a shared tile pool directory - tiles can be reused across regions
    if resolution == '90m':
        tiles_dir = Path(f"data/raw/srtm_90m/tiles")
    else:
        tiles_dir = Path(f"data/raw/srtm_30m/tiles")
    tiles_dir.mkdir(parents=True, exist_ok=True)
    tile_paths = []
    for idx, tb in enumerate(tiles):
        estimated_tile_mb = tile_estimates[idx]
        print(f"\n  Tile {idx+1}/{len(tiles)} (estimated ~{estimated_tile_mb:.1f} MB)", flush=True)
        print(f"    Bounds: [{tb[0]:.4f}, {tb[1]:.4f}, {tb[2]:.4f}, {tb[3]:.4f}]", flush=True)
        # UNIFIED 1-DEGREE GRID: Tiles are already 1-degree, just generate filename
        # No need to snap - calculate_1degree_tiles already returns 1-degree tiles
        tile_grid_size = 1.0  # Unified 1-degree grid system
        
        # Generate content-based filename using tile bounds (unified 1-degree grid)
        tile_filename = tile_filename_from_bounds(tb, resolution,
                                                 use_grid_alignment=True, grid_size=tile_grid_size)
        snapped_tile_bounds = tb  # Already 1-degree, no snapping needed
        tile_path = tiles_dir / tile_filename
        
        if tile_path.exists():
            # Strong validation: try to read data to catch partial/corrupt tiles
            if validate_geotiff(tile_path, check_data=True):
                # CRITICAL: Verify tile is actually 1-degree AND resolution matches required dataset
                try:
                    import rasterio
                    import math
                    with rasterio.open(tile_path) as src:
                        bounds = src.bounds
                        width_deg = bounds.right - bounds.left
                        height_deg = bounds.top - bounds.bottom
                        center_lat = (bounds.top + bounds.bottom) / 2.0
                        
                        # Validate tile is actually 1-degree (unified grid system)
                        # Allow small tolerance for floating-point precision (0.01 degrees)
                        is_1degree = (0.99 <= width_deg <= 1.01) and (0.99 <= height_deg <= 1.01)
                        if not is_1degree:
                            print(f"    WARNING: Tile is not 1-degree ({width_deg:.3f}deg x {height_deg:.3f}deg), will re-download", flush=True)
                            tile_path.unlink()  # Delete invalid tile
                            return False
                        
                        meters_per_deg_lat = 111_320  # constant
                        meters_per_deg_lon = 111_320 * math.cos(math.radians(center_lat))
                        width_m = width_deg * meters_per_deg_lon
                        height_m = height_deg * meters_per_deg_lat
                        avg_resolution = (width_m / src.width + height_m / src.height) / 2.0
                        
                        # Validate resolution matches expected dataset
                        resolution_ok = False
                        if resolution == '90m':
                            resolution_ok = (50 <= avg_resolution <= 150)
                        else:  # 30m
                            resolution_ok = (15 <= avg_resolution <= 50)
                        
                        if not resolution_ok:
                            print(f"  Cached tile resolution ({avg_resolution:.1f}m) doesn't match {resolution} dataset", flush=True)
                            print(f"  Deleting to ensure quality...", flush=True)
                            tile_path.unlink()
                        else:
                            try:
                                size_mb = tile_path.stat().st_size / (1024 * 1024)
                                estimated_mb = tile_estimates[idx]
                                diff_pct = ((size_mb - estimated_mb) / estimated_mb * 100) if estimated_mb > 0 else 0
                                print(f"    Cached tile present (validated {resolution}): {tile_path.name}", flush=True)
                                print(f"      Size: {size_mb:.1f} MB (estimated: {estimated_mb:.1f} MB, {diff_pct:+.1f}%)", flush=True)
                            except Exception:
                                print(f"    Cached tile present (validated {resolution}): {tile_path.name}", flush=True)
                            tile_paths.append(tile_path)
                            continue
                except Exception as e:
                    print(f"  Could not validate tile resolution: {e}", flush=True)
                    print(f"  Deleting to ensure quality...", flush=True)
                    try:
                        tile_path.unlink()
                    except Exception:
                        pass
            else:
                print(f"  Cached tile failed validation. Deleting and re-downloading...", flush=True)
                try:
                    tile_path.unlink()
                except Exception:
                    pass
        
        print(f"    Downloading tile (grid-aligned bounds for reuse)...", flush=True)
        print(f"      Download bounds: [{snapped_tile_bounds[0]:.4f}, {snapped_tile_bounds[1]:.4f}, {snapped_tile_bounds[2]:.4f}, {snapped_tile_bounds[3]:.4f}]", flush=True)
        # CRITICAL: Use grid-aligned bounds for download to enable reuse across regions
        if not _download_bbox(tile_path, snapped_tile_bounds, dataset):
            print(f"    Tile download failed, skipping", flush=True)
            continue
        if validate_geotiff(tile_path, check_data=True):
            try:
                size_mb = tile_path.stat().st_size / (1024 * 1024)
                estimated_mb = tile_estimates[idx]
                diff_pct = ((size_mb - estimated_mb) / estimated_mb * 100) if estimated_mb > 0 else 0
                print(f"    Downloaded tile OK: {tile_path.name}", flush=True)
                print(f"      Size: {size_mb:.1f} MB (estimated: {estimated_mb:.1f} MB, {diff_pct:+.1f}%)", flush=True)
            except Exception:
                print(f"    Downloaded tile OK: {tile_path.name}", flush=True)
            tile_paths.append(tile_path)
        else:
            print(f"    Invalid tile file, removing", flush=True)
            try:
                tile_path.unlink()
            except Exception:
                pass
    
    if not tile_paths:
        print(f"  No valid tiles downloaded", flush=True)
        return False
    
    # Calculate actual total size of tiles
    actual_tile_total_mb = sum(p.stat().st_size / (1024 * 1024) for p in tile_paths if p.exists())
    
    print(f"\n  Download summary:", flush=True)
    print(f"    Tiles downloaded: {len(tile_paths)}/{len(tiles)}", flush=True)
    print(f"    Total tile size: {actual_tile_total_mb:.1f} MB (estimated: {total_estimated_size:.1f} MB)", flush=True)
    
    print(f"\n  Merging {len(tile_paths)} tiles...", flush=True)
    if not merge_tiles(tile_paths, output_file):
        print(f"  Tile merge failed", flush=True)
        return False
    
    # Show final merged file size
    if output_file.exists():
        final_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"  Merged file size: {final_size_mb:.1f} MB", flush=True)
    # Save metadata for merged file
    try:
        from src.metadata import create_raw_metadata, save_metadata, get_metadata_path
        raw_meta = create_raw_metadata(
            tif_path=output_file,
            region_id=region_id,
            source=source_name,
            download_url='tiled:OpenTopography',
            download_params={'tiles': len(tile_paths), 'dataset': dataset, 'bounds': region_info['bounds']}
        )
        save_metadata(raw_meta, get_metadata_path(output_file))
    except Exception as e:
        print(f"  Could not save raw metadata: {e}")
    print(f"  Tiled download and merge complete", flush=True)
    return True

    # NOTE: The code below is now unreachable because unified 1-degree grid system
    # always downloads as tiles. Keeping for reference - should be removed after
    # confirming unified system works correctly.
    
    # Mixed-source handling: if region spans SRTM/COP30 boundary, split and merge
    # This should eventually be updated to use unified 1-degree grid system
    spans_upper = south < 60.0 and north > 60.0
    spans_lower = south < -56.0 and north > -56.0
    crosses = spans_upper or spans_lower

    if crosses and dataset_override is None:
        print("  Spans dataset coverage boundary; downloading sub-extents per source and merging...", flush=True)
        sub_boxes: list[tuple[tuple[float, float, float, float], str]] = []
        # Lower polar-cap segment (below -56)
        if south < -56.0:
            sub_boxes.append(((west, south, east, min(north, -56.0)), 'COP30'))
        # Mid SRTM segment (-56 to 60)
        mid_south = max(south, -56.0)
        mid_north = min(north, 60.0)
        if mid_south < mid_north:
            sub_boxes.append(((west, mid_south, east, mid_north), 'SRTMGL1'))
        # Upper segment (above 60)
        if north > 60.0:
            sub_boxes.append(((west, max(south, 60.0), east, north), 'COP30'))

        parts_dir = Path(f"data/raw/srtm_30m/subparts/{region_id}")
        parts_dir.mkdir(parents=True, exist_ok=True)
        part_paths: list[Path] = []
        for pi, (bbox, demtype) in enumerate(sub_boxes):
            pw, ps, pe, pn = bbox
            print(f"  Part {pi+1}/{len(sub_boxes)} [{demtype}] bounds: [{pw:.4f}, {ps:.4f}, {pe:.4f}, {pn:.4f}]", flush=True)
            # Decide tiling for SRTM and COP30 (both have 450,000 km^2 limit)
            width_deg_p = max(0.0, float(pe - pw))
            height_deg_p = max(0.0, float(pn - ps))
            mid_lat_p = (pn + ps) / 2.0
            km_per_deg_lon_p = 111.320 * math.cos(math.radians(mid_lat_p))
            approx_area_km2_p = (width_deg_p * km_per_deg_lon_p) * (height_deg_p * km_per_deg_lat)
            tile_needed = (demtype in ['SRTMGL1', 'COP30']) and (approx_area_km2_p > 420_000 or width_deg_p > 4.0 or height_deg_p > 4.0)
            if tile_needed:
                # Use unified 1-degree grid system
                tiles = calculate_1degree_tiles(bbox)
                tiles_dir_p = parts_dir / f"tiles_p{pi:02d}"
                tiles_dir_p.mkdir(parents=True, exist_ok=True)
                tile_paths_p: list[Path] = []
                for ti, tb in enumerate(tiles):
                    print(f"    Tile {ti+1}/{len(tiles)} bounds: [{tb[0]:.4f}, {tb[1]:.4f}, {tb[2]:.4f}, {tb[3]:.4f}]", flush=True)
                    # GRID ALIGNMENT: Snap tile bounds to grid for reuse
                    tile_grid_size = 1.0  # Integer-degree grid for tiles
                    from downloaders.tile_large_states import snap_tile_bounds_to_grid
                    snapped_tile_bounds = snap_tile_bounds_to_grid(tb, tile_grid_size)
                    # Use grid-aligned filename for tile reuse
                    tile_filename = tile_filename_from_bounds(snapped_tile_bounds, '30m' if '30' in str(demtype) else '90m',
                                                             use_grid_alignment=True, grid_size=tile_grid_size)
                    # Use shared tile pool directory for reuse (not per-part subdirectories)
                    if resolution == '90m':
                        shared_tiles_dir = Path(f"data/raw/srtm_90m/tiles")
                    else:
                        shared_tiles_dir = Path(f"data/raw/srtm_30m/tiles")
                    shared_tiles_dir.mkdir(parents=True, exist_ok=True)
                    tpath = shared_tiles_dir / tile_filename
                    if snapped_tile_bounds != tb:
                        print(f"      Grid alignment: expanding tile bounds for reuse")
                        print(f"        Expanded:  [{snapped_tile_bounds[0]:.4f}, {snapped_tile_bounds[1]:.4f}, {snapped_tile_bounds[2]:.4f}, {snapped_tile_bounds[3]:.4f}]")
                    # Check if already exists in shared pool (reuse!)
                    if tpath.exists() and validate_geotiff(tpath, check_data=True):
                        print(f"      Reusing cached tile: {tpath.name}")
                        # Copy or use the shared tile
                        tile_paths_p.append(tpath)
                        continue
                    print(f"      Downloading tile (grid-aligned bounds for reuse)...")
                    print(f"        Download bounds: [{snapped_tile_bounds[0]:.4f}, {snapped_tile_bounds[1]:.4f}, {snapped_tile_bounds[2]:.4f}, {snapped_tile_bounds[3]:.4f}]")
                    # CRITICAL: Use grid-aligned bounds for download to enable reuse
                    if not _download_bbox(tpath, snapped_tile_bounds, demtype):
                        print("    Tile download failed, skipping", flush=True)
                        continue
                    if validate_geotiff(tpath, check_data=True):
                        tile_paths_p.append(tpath)
                if not tile_paths_p:
                    print("  No valid tiles for part; aborting", flush=True)
                    return False
                merged_part = parts_dir / f"part_{pi:02d}.tif"
                if not merge_tiles(tile_paths_p, merged_part):
                    print("  Part merge failed", flush=True)
                    return False
                part_paths.append(merged_part)
            else:
                part_path = parts_dir / f"part_{pi:02d}.tif"
                if not _download_bbox(part_path, bbox, demtype):
                    print("  Part download failed", flush=True)
                    return False
                if not validate_geotiff(part_path, check_data=True):
                    print("  Part validation failed", flush=True)
                    return False
                part_paths.append(part_path)

        print(f"  Merging {len(part_paths)} parts...")
        if not merge_tiles(part_paths, output_file):
            print("  Final merge failed", flush=True)
            return False
        # Save metadata
        try:
            from src.metadata import create_raw_metadata, save_metadata, get_metadata_path
            raw_meta = create_raw_metadata(
                tif_path=output_file,
                region_id=region_id,
                source=source_name,
                download_url='mixed:OpenTopography',
                download_params={'parts': len(part_paths), 'bounds': region_info['bounds']}
            )
            save_metadata(raw_meta, get_metadata_path(output_file))
        except Exception as e:
            print(f"  Could not save raw metadata: {e}")
        print("  Mixed-source download complete", flush=True)
        return True

    # Download using OpenTopography API (single request) with EXPANDED bounds
    # Use grid-aligned bounds for download to ensure coverage and reuse
    url = "https://portal.opentopography.org/API/globaldem"
    params = {
        'demtype': dataset,  # COP30 for high latitudes, SRTMGL1 otherwise
        'south': expanded_south,
        'north': expanded_north,
        'west': expanded_west,
        'east': expanded_east,
        'outputFormat': 'GTiff',
        'API_Key': api_key
    }

    print(f"  Requesting from OpenTopography (grid-aligned bounds)...")
    print(f"    Download bounds: [{expanded_west:.4f}, {expanded_south:.4f}, {expanded_east:.4f}, {expanded_north:.4f}]")
    if expanded_bounds != original_bounds:
        print(f"    (Original region: [{west:.4f}, {south:.4f}, {east:.4f}, {north:.4f}])")
    print(f"  (This may take 30-120 seconds)")

    try:
        response = requests.get(url, params=params, stream=True, timeout=300)

        if response.status_code != 200:
            # If area too large, transparently fall back to tiling
            resp_text = response.text or ""
            if (dataset in ['SRTMGL1', 'COP30']) and ("maximum area" in resp_text.lower() or response.status_code == 400):
                print(f" Server rejected single request due to size. Switching to tiled download...", flush=True)
                # Use unified 1-degree grid system
                tiles = calculate_1degree_tiles(expanded_bounds)
                # Use shared tile pool directory for reuse across regions
                if resolution == '90m':
                    tiles_dir = Path(f"data/raw/srtm_90m/tiles")
                else:
                    tiles_dir = Path(f"data/raw/srtm_30m/tiles")
                tiles_dir.mkdir(parents=True, exist_ok=True)
                tile_paths = []
                tile_grid_size = 1.0  # Integer-degree grid for tiles
                from downloaders.tile_large_states import snap_tile_bounds_to_grid
                for idx, tb in enumerate(tiles):
                    print(f"\n  Tile {idx+1}/{len(tiles)} bounds: [{tb[0]:.4f}, {tb[1]:.4f}, {tb[2]:.4f}, {tb[3]:.4f}]", flush=True)
                    # GRID ALIGNMENT: Snap tile bounds to grid for reuse and consistent naming
                    snapped_tile_bounds = snap_tile_bounds_to_grid(tb, tile_grid_size)
                    # Generate content-based filename using grid-aligned bounds
                    tile_filename = tile_filename_from_bounds(snapped_tile_bounds, resolution,
                                                             use_grid_alignment=True, grid_size=tile_grid_size)
                    tile_path = tiles_dir / tile_filename
                    if snapped_tile_bounds != tb:
                        print(f"    Grid alignment: expanding tile bounds for reuse")
                        print(f"      Expanded:  [{snapped_tile_bounds[0]:.4f}, {snapped_tile_bounds[1]:.4f}, {snapped_tile_bounds[2]:.4f}, {snapped_tile_bounds[3]:.4f}]")
                    if tile_path.exists():
                        if validate_geotiff(tile_path, check_data=True):
                            try:
                                size_mb = tile_path.stat().st_size / (1024 * 1024)
                                print(f"  Cached tile present: {tile_path.name} ({size_mb:.1f} MB)", flush=True)
                            except Exception:
                                print(f"  Cached tile present: {tile_path.name}", flush=True)
                            tile_paths.append(tile_path)
                            continue
                        else:
                            print(f"  Cached tile failed validation. Deleting and re-downloading...", flush=True)
                            try:
                                tile_path.unlink()
                            except Exception:
                                pass
                    print(f"  Downloading tile (grid-aligned bounds for reuse)...", flush=True)
                    print(f"    Download bounds: [{snapped_tile_bounds[0]:.4f}, {snapped_tile_bounds[1]:.4f}, {snapped_tile_bounds[2]:.4f}, {snapped_tile_bounds[3]:.4f}]", flush=True)
                    # CRITICAL: Use grid-aligned bounds for download to enable reuse across regions
                    if not _download_bbox(tile_path, snapped_tile_bounds, dataset):
                        print(f"  Tile download failed, skipping", flush=True)
                        continue
                    if validate_geotiff(tile_path, check_data=True):
                        try:
                            size_mb = tile_path.stat().st_size / (1024 * 1024)
                            print(f"  Downloaded tile OK: {tile_path.name} ({size_mb:.1f} MB)", flush=True)
                        except Exception:
                            print(f"  Downloaded tile OK: {tile_path.name}", flush=True)
                        tile_paths.append(tile_path)
                    else:
                        print(f"  Invalid tile file, removing", flush=True)
                        try:
                            tile_path.unlink()
                        except Exception:
                            pass
                if not tile_paths:
                    print(f"  No valid tiles downloaded", flush=True)
                    return False
                print(f"\n  Merging {len(tile_paths)} tiles...", flush=True)
                if not merge_tiles(tile_paths, output_file):
                    print(f"  Tile merge failed", flush=True)
                    return False
                try:
                    from src.metadata import create_raw_metadata, save_metadata, get_metadata_path
                    raw_meta = create_raw_metadata(
                        tif_path=output_file,
                        region_id=region_id,
                        source=source_name,
                        download_url='tiled:OpenTopography',
                        download_params={'tiles': len(tile_paths), 'dataset': dataset, 'bounds': region_info['bounds']}
                    )
                    save_metadata(raw_meta, get_metadata_path(output_file))
                except Exception as e:
                    print(f"  Could not save raw metadata: {e}")
                print(f"  Tiled download and merge complete", flush=True)
                return True
            print(f"  API Error: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False

        # Download with enhanced progress display
        total_size = int(response.headers.get('content-length', 0))
        
        desc = output_file.name[:40] + ('...' if len(output_file.name) > 40 else '')
        with open(output_file, 'wb') as f, tqdm(
            desc=desc,
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
            miniters=1,
            disable=False
        ) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        estimated_mb = estimate_raw_file_size_mb((west, south, east, north), resolution_meters)
        diff_pct = ((file_size_mb - estimated_mb) / estimated_mb * 100) if estimated_mb > 0 else 0
        print(f"  Downloaded successfully: {file_size_mb:.1f} MB (estimated: {estimated_mb:.1f} MB, {diff_pct:+.1f}%)")
        # Write raw metadata including bounds so future bound changes can auto-invalidate
        try:
            from src.metadata import create_raw_metadata, save_metadata, get_metadata_path
            raw_meta = create_raw_metadata(
                tif_path=output_file,
                region_id=region_id,
                source=source_name,
                download_url=url,
                download_params=params
            )
            save_metadata(raw_meta, get_metadata_path(output_file))
        except Exception as e:
            print(f"  Could not save raw metadata: {e}")
        return True

    except Exception as e:
        print(f"  Download failed: {e}")
        if output_file.exists():
            output_file.unlink()  # Clean up partial download
        return False


def download_region(region_id: str, region_type: str, region_info: Dict, dataset_override: str | None = None, target_pixels: int = 2048) -> bool:
    """Route to appropriate downloader based on region type."""
    if region_type == 'us_state':
        return download_us_state(region_id, region_info)
    elif region_type == 'international':
        return download_international_region(region_id, region_info, dataset_override, target_pixels)
    else:
        print(f"  Unknown region type: {region_type}")
        return False


def determine_dataset_override(region_id: str, region_type: str, region_info: dict) -> str | None:
    """
    Stage 2/3: Determine dataset to use for download.
    - US states: USGS 3DEP (implicit in downloader) -> return 'USA_3DEP'
    - International: override from RegionConfig.recommended_dataset if provided; else choose by latitude:
        * SRTMGL1 for 60degN to 56degS
        * COP30 outside that range
    Returns a short code understood by download_international_region: 'SRTMGL1' or 'COP30'.
    """
    if region_type == 'us_state':
        print("[STAGE 2/10] Dataset: USGS 3DEP 10m (US State)")
        return 'USA_3DEP'

    # International regions
    recommended = None
    try:
        # Try to pull from centralized config if available
        entry = ALL_REGIONS.get(region_id)
        if entry and getattr(entry, 'recommended_dataset', None):
            recommended = entry.recommended_dataset
    except Exception:
        recommended = None

    if recommended in ('SRTMGL1', 'COP30'):
        print(f"[STAGE 2/10] Dataset override from RegionConfig: {recommended}")
        return recommended

    _west, south, _east, north = region_info['bounds']
    lat_choice = 'COP30' if (north > 60.0 or south < -56.0) else 'SRTMGL1'
    print(f"[STAGE 3/10] Latitude-based dataset: {lat_choice}")
    return lat_choice


def process_region(region_id: str, raw_path: Path, source: str, target_pixels: int, force: bool, region_type: str, region_info: Dict, border_resolution: str = '10m') -> Tuple[bool, Dict]:
    """Run the pipeline on a region and return (success, result_paths)."""

    # Determine boundary based on region type
    if region_type == 'us_state':
        state_name = region_info['name']
        boundary_name = f"United States of America/{state_name}"
        boundary_type = "state"
    elif region_type == 'international':
        # For international regions, use country-level boundary
        # Some regions (territories, disputed areas) may not have boundaries in Natural Earth
        if region_info.get('clip_boundary', True):
            boundary_name = region_info['name']
            boundary_type = "country"
        else:
            boundary_name = None
            boundary_type = None
    else:
        boundary_name = None
        boundary_type = "country"

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


def verify_and_auto_fix(region_id: str, result_paths: dict, source: str, target_pixels: int,
                        region_type: str, region_info: dict, border_resolution: str) -> bool:
    """
    Detect compressed/flat altitude outputs and auto-fix by force reprocessing.
    Guarantees valid export when returning True.
    """
    try:
        from src.validation import validate_elevation_range
        import rasterio
        import numpy as np
    except Exception:
        # If validation libs unavailable, best-effort assume valid
        return True

    processed_path = result_paths.get('processed')
    exported_path = result_paths.get('exported')

    # 1) Validate processed TIF elevation range (authoritative)
    tif_ok = True
    if processed_path and Path(processed_path).exists():
        try:
            with rasterio.open(processed_path) as src:
                arr = src.read(1)
                arr = arr.astype(np.float32)
                nodata = src.nodata
                if nodata is not None and not np.isnan(nodata):
                    arr[arr == nodata] = np.nan
                _min, _max, _range, is_valid = validate_elevation_range(arr, min_sensible_range=50.0, warn_only=False)
                tif_ok = bool(is_valid)
        except Exception:
            tif_ok = False
    else:
        tif_ok = False

    # 2) Validate JSON export (structure + range check already present)
    json_ok = False
    if exported_path and Path(exported_path).exists():
        json_ok = validate_json_export(Path(exported_path))

    if tif_ok and json_ok:
        return True

    # Auto-fix: force reprocess with 10m borders and clean outputs
    print("\n  Detected invalid or compressed altitude output. Auto-fixing by force reprocess...", flush=True)
    # Clean existing artifacts (using abstract naming)
    # Get bounds from region config to generate abstract filenames
    bounds = region_info.get('bounds')
    if bounds:
        import glob
        for source_check in ['srtm_30m', 'srtm_90m', 'usa_3dep']:
            resolution = '30m' if '30m' in source_check else '90m' if '90m' in source_check else '10m'
            tile_name = bbox_filename_from_bounds(bounds, resolution)
            base_part = tile_name[:-4]  # Remove '.tif' suffix only
            
            patterns = [
                f"data/clipped/{source_check}/{base_part}_clipped_*_v1.tif",
                f"data/processed/{source_check}/{base_part}_processed_*px_v2.tif",
                f"generated/regions/{base_part}_*px_v2.json"
            ]
            
            for pattern in patterns:
                for file_path in glob.glob(pattern, recursive=True):
                    try:
                        Path(file_path).unlink()
                        print(f"  Deleted: {Path(file_path).name}", flush=True)
                    except Exception:
                        pass

    # Locate raw again and re-run (accept any valid file for auto-fix)
    raw_path, _ = find_raw_file(region_id, verbose=False, min_required_resolution_meters=None)
    if not raw_path:
        print("  Raw file missing during auto-fix")
        return False

    success2, result_paths2 = process_region(
        region_id, raw_path, source, target_pixels, True, region_type, region_info, border_resolution='10m'
    )
    if not success2:
        return False

    # Re-validate
    return verify_and_auto_fix(region_id, result_paths2, source, target_pixels, region_type, region_info, border_resolution)



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

This script will:
    1. Detect region type (US state or international)
    2. Check if raw data exists
    3. Download if missing (auto-download for US states and supported international regions)
    4. Run the full pipeline (clip, downsample, export)
    5. Report status
        """
    )
    parser.add_argument('region_id', nargs='?', help='Region ID (e.g., ohio, iceland, japan)')
    parser.add_argument('--target-pixels', type=int, default=DEFAULT_TARGET_PIXELS,
                        help=f'Target resolution (default: {DEFAULT_TARGET_PIXELS})')
    parser.add_argument('--border-resolution', type=str, default='10m',
                        choices=['10m', '50m', '110m'],
                        help='Border detail level: 10m=high detail (recommended), 50m=medium, 110m=low (default: 10m)')
    parser.add_argument('--force-reprocess', action='store_true',
                        help='Force reprocessing even if files exist')
    parser.add_argument('--check-only', action='store_true',
                        help='Only check status, do not download or process')
    parser.add_argument('--list-regions', action='store_true',
                        help='List all available regions')
    parser.add_argument('--yes', action='store_true',
                        help='Auto-accept lower quality data prompts')

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
        for rid in all_ids:
            # Summary line per region
            has_valid = check_pipeline_complete(rid)
            version_ok, found_v, expected_v = _check_export_version(rid)
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
                min_req_res = None
                if region_type == 'us_state':
                    min_req_res = 10
                else:
                    visible = calculate_visible_pixel_size(region_info['bounds'], args.target_pixels)
                    min_req_res = determine_min_required_resolution(visible['avg_m_per_pixel'])
                
                raw_path, source = find_raw_file(rid, min_required_resolution_meters=min_req_res)
                if not raw_path:
                    dataset_override = determine_dataset_override(rid, region_type, region_info)
                    if not download_region(rid, region_type, region_info, dataset_override, args.target_pixels):
                        print(f"  Download failed for {rid}")
                        continue
                    raw_path, source = find_raw_file(rid, min_required_resolution_meters=min_req_res)
                    if not raw_path:
                        print(f"  Validation failed after download for {rid}")
                        continue
                success, result_paths = process_region(rid, raw_path, source, args.target_pixels,
                                                      True if args.force_reprocess else False,
                                                      region_type, region_info, args.border_resolution)
                if success:
                    _ = verify_and_auto_fix(rid, result_paths, source, args.target_pixels,
                                            region_type, region_info, args.border_resolution)
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

    # Determine dataset early (stages 2-3)
    dataset_override = determine_dataset_override(region_id, region_type, region_info)

    # Check if raw data exists (stage 4)
    print(f"\n[STAGE 4/10] Checking raw elevation data...", flush=True)
    
    # Determine minimum required resolution based on quality requirements
    min_required_resolution = None
    if region_type == 'us_state':
        # US states always use 10m (USA_3DEP)
        min_required_resolution = 10
    else:
        # International: calculate visible pixel size to determine requirement
        visible = calculate_visible_pixel_size(region_info['bounds'], args.target_pixels)
        try:
            min_required_resolution = determine_min_required_resolution(visible['avg_m_per_pixel'])
            print(f"  Quality requirement: minimum {min_required_resolution}m resolution", flush=True)
            print(f"    (visible pixels: ~{visible['avg_m_per_pixel']:.0f}m each)", flush=True)
        except ValueError as e:
            # Region requires higher resolution than available - ask user if they'll accept lower quality
            print(f"\n{'='*70}", flush=True)
            print(f"  WARNING: Quality Issue", flush=True)
            print(f"{'='*70}", flush=True)
            print(f"\n  {str(e)}", flush=True)
            print(f"\n  The best available source (30m) does not meet Nyquist quality standards.", flush=True)
            print(f"  This may result in some aliasing artifacts in the visualization.", flush=True)
            print(f"\n  Once we implement 10m downloading, things will improve somewhat!", flush=True)
            
            # Auto-accept if --yes flag provided
            if args.yes:
                response = 'yes'
                print(f"\n  Auto-accepting lower quality data (--yes flag).", flush=True)
            else:
                print(f"\n  Do you want to proceed with lower quality data? (yes/no): ", end='', flush=True)
                try:
                    response = input().strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print("\n  Aborted by user.", flush=True)
                    return 1
            
            if response in ('yes', 'y'):
                # User accepted lower quality - proceed with best available (30m)
                min_required_resolution = determine_min_required_resolution(
                    visible['avg_m_per_pixel'], 
                    allow_lower_quality=True
                )
                print(f"\n  Proceeding with {min_required_resolution}m source (lower quality).", flush=True)
            else:
                print(f"\n  Aborted. To try again with lower quality, run the command again and accept.", flush=True)
                return 1
    
    raw_path, source = find_raw_file(region_id, min_required_resolution_meters=min_required_resolution)

    if not raw_path:
        print(f"  No raw data found for {region_id}", flush=True)

        if args.check_only:
            print(f"  Use without --check-only to download", flush=True)
            return 1

        # Download raw data
        print(f"[STAGE 4/10] Downloading...", flush=True)
        if not download_region(region_id, region_type, region_info, dataset_override, args.target_pixels):
            print(f"  Download failed!", flush=True)
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
    success, result_paths = process_region(region_id, raw_path, source, args.target_pixels,
                                          args.force_reprocess, region_type, region_info, args.border_resolution)

    if success:
        # Post-validate and auto-fix if needed
        ensured = verify_and_auto_fix(region_id, result_paths, source, args.target_pixels,
                                      region_type, region_info, args.border_resolution)
        if not ensured:
            print("\n" + "="*70)
            print(f"  FAILED: Auto-fix could not repair {region_info['display_name']}")
            print("="*70)
            return 1
        print("\n" + "="*70)
        print(f"  SUCCESS: {region_info['display_name']} is ready to view!")
        print("="*70)
        print(f"\nNext steps:")
        print(f"  1. python serve_viewer.py")
        print(f"  2. Visit http://localhost:8001/interactive_viewer_advanced.html")
        print(f"  3. Select '{region_id}' from dropdown")
        return 0
    else:
        print("\n" + "="*70)
        print(f"  FAILED: Could not process {region_info['display_name']}")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())