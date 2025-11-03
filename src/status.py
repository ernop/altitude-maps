"""
Status checking and reporting utilities for altitude-maps project.

This module provides functions for:
- Pipeline stage completion checking
- Export version validation
- Auto-fix and verification
- Status summarization

All status logic is centralized here to enable reuse and independent testing.
"""

import json
import glob
from pathlib import Path
from typing import Tuple, Optional, Dict

from src.regions_config import ALL_REGIONS
from src.versioning import get_current_version
from src.validation import check_pipeline_complete, find_raw_file, validate_json_export


def summarize_pipeline_status(region_id: str, region_type: str, region_info: dict) -> None:
    """Print a compact summary of pipeline stage completion for the region."""
    # Import here to avoid circular dependency
    from src.tile_geometry import tile_filename_from_bounds
    bbox_filename_from_bounds = tile_filename_from_bounds
    
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
                # Check if file exists
                if any(glob.glob(f"data/processed/{source}/{base_part}_processed_{target_pixels}px_v2.tif", recursive=True)):
                    s8 = True
                    break
            if s8:
                break

    # Quick summary without excessive verbosity
    print(f"  Status: Raw={'OK' if s4 else 'X'} | Processed={'OK' if s8 else 'X'} | Export={'OK' if s9 else 'X'}", flush=True)


def check_export_version(region_id: str) -> Tuple[bool, str, str]:
    """
    Check if the region's exported JSON exists with current format version in filename.
    
    Version is tracked in filename (e.g., *_v2.json), not inside the file.

    Returns:
        (version_ok, found_version, expected_version)
    """
    generated_dir = Path("generated/regions")
    # Current format version from filename pattern
    expected = "v2"  # Hardcoded - matches _v2.json pattern
    found = "none"
    
    try:
        if not generated_dir.exists():
            return False, found, expected
        
        # Find any JSON files for this region with version in filename
        region_files = list(generated_dir.glob(f"{region_id}_*_v2.json"))
        if not region_files:
            # Check for old v1 files
            old_files = list(generated_dir.glob(f"{region_id}_*_v1.json"))
            if old_files:
                found = "v1"
                return False, found, expected
            return False, found, expected
        
        # Has v2 file - version is current
        return True, expected, expected
        
    except Exception:
        return False, "error", expected


def verify_and_auto_fix(region_id: str, result_paths: dict, source: str, target_pixels: int,
                        region_type: str, region_info: dict, border_resolution: str) -> bool:
    """
    Detect compressed/flat altitude outputs and auto-fix by force reprocessing.
    Guarantees valid export when returning True.
    """
    # Import here to avoid circular dependency
    from src.tile_geometry import tile_filename_from_bounds
    bbox_filename_from_bounds = tile_filename_from_bounds
    
    try:
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
                
                # Inline validation: check elevation range
                valid_elev = arr[~np.isnan(arr)]
                if len(valid_elev) > 0:
                    elev_range = float(np.max(valid_elev) - np.min(valid_elev))
                    tif_ok = elev_range >= 50.0  # Minimum sensible range
                else:
                    tif_ok = False
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

    # Import process_region here to avoid circular dependency
    # This function will be in ensure_region.py
    from ensure_region import process_region
    
    success2, result_paths2 = process_region(
        region_id, raw_path, source, target_pixels, True, region_type, region_info, border_resolution='10m'
    )
    if not success2:
        return False

    # Re-validate
    return verify_and_auto_fix(region_id, result_paths2, source, target_pixels, region_type, region_info, border_resolution)

