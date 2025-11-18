"""
Validation utilities for altitude-maps project.

This module provides validation functions for:
- GeoTIFF files (raw elevation data)
- JSON exports (viewer data)
- Raw file discovery and quality checking
- Pipeline completion status

All validation logic is centralized here to enable reuse and independent testing.
"""

import json
import gzip
from pathlib import Path
from typing import Tuple, Optional, Dict

from src.regions_config import ALL_REGIONS


def validate_elevation_range(
    elevation_data,
    min_sensible_range: float = 50.0,
    warn_only: bool = False
) -> Tuple[float, float, float, bool]:
    """
    Validate elevation data range.
    
    Args:
        elevation_data: Elevation array (numpy)
        min_sensible_range: Minimum sensible elevation range in meters
        warn_only: If True, only warn; if False, raise exception on failure
        
    Returns:
        Tuple of (min_elev, max_elev, elev_range, is_valid)
    """
    import numpy as np
    
    # Filter out nodata values
    valid_data = elevation_data[~np.isnan(elevation_data)]
    
    if len(valid_data) == 0:
        if warn_only:
            print(f"  WARNING: No valid elevation data found")
            return 0.0, 0.0, 0.0, False
        else:
            raise ValueError("No valid elevation data found")
    
    min_elev = float(np.min(valid_data))
    max_elev = float(np.max(valid_data))
    elev_range = max_elev - min_elev
    
    # Note: Some coastal cities and flat regions have small elevation ranges (e.g., Helsinki ~49m)
    # Use 20m as absolute minimum to catch data errors while allowing realistic flat regions
    actual_min_range = min(min_sensible_range, 20.0)
    is_valid = elev_range >= actual_min_range
    
    if not is_valid:
        msg = f"Elevation range too small: {elev_range:.1f}m (min: {actual_min_range:.1f}m)"
        if warn_only:
            print(f"  WARNING: {msg}")
        else:
            raise ValueError(msg)
    
    return min_elev, max_elev, elev_range, is_valid


def validate_non_null_coverage(elevation_data, min_coverage_pct: float = 50.0) -> Tuple[float, bool]:
    """
    Validate that elevation data has sufficient non-null coverage.
    
    Args:
        elevation_data: Elevation array (numpy)
        min_coverage_pct: Minimum percentage of non-null data required
        
    Returns:
        Tuple of (coverage_pct, is_valid)
    """
    import numpy as np
    
    total_pixels = elevation_data.size
    valid_pixels = np.sum(~np.isnan(elevation_data))
    coverage_pct = (valid_pixels / total_pixels) * 100.0
    
    is_valid = coverage_pct >= min_coverage_pct
    
    if not is_valid:
        print(f"  WARNING: Low data coverage: {coverage_pct:.1f}% (min: {min_coverage_pct}%)")
    
    return coverage_pct, is_valid


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

                # Check for suspiciously small elevation range (warn only - could be legitimate flat region)
                if elev_range < 50.0:
                    if verbose:
                        print(f"  WARNING: Suspicious elevation range: {min_elev:.1f}m to {max_elev:.1f}m (range: {elev_range:.1f}m)")
                        print(f"  This may indicate reprojection corruption or could be a legitimate flat region")
                        print(f"  If visualization looks incorrect, regenerate with --force-reprocess")
                    # Don't fail validation - just warn user

                if verbose and elev_range >= 50.0:
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
    # Import here to avoid circular dependency
    from src.tile_geometry import tile_filename_from_bounds
    bbox_filename_from_bounds = tile_filename_from_bounds
    
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
    
    # Also check merged directory (for regions downloaded via tile merging)
    # Import merged_filename_from_region to generate correct bounds-based filenames
    from src.tile_geometry import merged_filename_from_region
    
    merged_10m = merged_filename_from_region(region_id, bounds, '10m') + '.tif'
    merged_30m = merged_filename_from_region(region_id, bounds, '30m') + '.tif'
    merged_90m = merged_filename_from_region(region_id, bounds, '90m') + '.tif'
    
    possible_locations.extend([
        (Path(f"data/merged/usa_3dep/{merged_10m}"), 'usa_3dep'),
        (Path(f"data/merged/srtm_30m/{merged_30m}"), 'srtm_30m'),
        (Path(f"data/merged/srtm_90m/{merged_90m}"), 'srtm_90m'),
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
    # Import here to avoid circular dependency
    from src.tile_geometry import tile_filename_from_bounds
    bbox_filename_from_bounds = tile_filename_from_bounds
    
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
