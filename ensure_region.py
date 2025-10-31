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
try:
    import rasterio
    from rasterio.mask import mask as rasterio_mask
    import numpy as np
    from shapely.geometry import shape
    from shapely.ops import unary_union
    from shapely.geometry import mapping as shapely_mapping
except ImportError as e:
    print(f"Missing package: {e}")
    print("Install with: pip install rasterio shapely numpy")
    sys.exit(1)

import json
from typing import Optional, Dict, Tuple

# Pipeline utilities
from src.metadata import (
    create_clipped_metadata, create_processed_metadata,
    create_export_metadata, save_metadata, get_metadata_path, compute_file_hash
)
from src.versioning import get_current_version
from src.borders import get_country_geometry, get_border_manager


def _path_exists(glob_pattern: str) -> bool:
    """Utility to check if any path matches the given glob pattern."""
    import glob as _glob
    return any(_glob.glob(glob_pattern, recursive=True))


def _print_stage(label: str, done: bool) -> None:
    symbol = '+' if done else ' '
    print(f"  ({symbol}) {label}")


def summarize_pipeline_status(region_id: str, region_type: str, region_info: dict) -> None:
    """Print a compact summary of pipeline stage completion for the region."""
    # Stage 9 (final): valid export present? (silent check)
    s9 = check_pipeline_complete(region_id, verbose=False)

    # Stage 4: raw present? (silent check)
    raw_path, source_guess = find_raw_file(region_id, verbose=False)
    s4 = raw_path is not None

    # Stage 8: processed present?
    s8 = _path_exists(f"data/processed/*/{region_id}_*_*px_v2.tif")

    # Quick summary without excessive verbosity
    print(f"  Status: Raw={'✓' if s4 else '✗'} | Processed={'✓' if s8 else '✗'} | Export={'✓' if s9 else '✗'}", flush=True)


# Create mapping for backward compatibility during transition
US_STATE_NAMES = get_us_state_names()


# Pipeline Error class
class PipelineError(Exception):
    """Raised when pipeline step fails."""
    pass


def check_venv():
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


def validate_json_export(file_path: Path, verbose=True) -> bool:
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
        import json
        import gzip

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


def get_region_info(region_id):
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


def find_raw_file(region_id, verbose=True):
    """
    Find and validate raw file for a region.

    Args:
        region_id: Region identifier
        verbose: If True, print validation messages

    Returns:
        Tuple of (path, source) if valid file found, (None, None) otherwise
    """
    possible_locations = [
        Path(f"data/raw/srtm_30m/{region_id}_bbox_30m.tif"),
        Path(f"data/raw/usa_3dep/{region_id}_3dep_10m.tif"),
    ]

    for path in possible_locations:
        if path.exists():
            if verbose:
                print(f"  Checking {path.name}...", flush=True)
            if validate_geotiff(path, check_data=True):
                if verbose:
                    print(f"  Valid GeoTIFF (structure)", flush=True)
                return path, get_source_from_path(path)
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

    return None, None


def get_source_from_path(path):
    """Determine source type from path."""
    if 'usa_3dep' in str(path):
        return 'usa_3dep'
    return 'srtm_30m'


def check_pipeline_complete(region_id, verbose=True):
    """
    Check if all pipeline stages are complete and valid.

    Args:
        region_id: Region identifier
        verbose: If True, print validation messages

    Returns:
        True if valid JSON export exists, False otherwise
    """
    # Check for JSON export (final stage)
    generated_dir = Path("generated/regions")
    if not generated_dir.exists():
        return False

    json_files = list(generated_dir.glob(f"{region_id}_*.json"))
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
        json_files = [
            f for f in generated_dir.glob(f"{region_id}_*.json")
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


def download_us_state(region_id, state_info):
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


def download_international_region(region_id, region_info, dataset_override: str | None = None):
    """Download raw data for an international region using OpenTopography.

    If dataset_override is provided, use it (e.g., 'COP30' or 'SRTMGL1').
    """
    west, south, east, north = region_info['bounds']

    # Choose dataset based on latitude coverage
    # SRTM: 60degN to 56degS
    # Copernicus: 90degN to 90degS (global)
    # AW3D30: 82degN to 82degS
    if dataset_override is not None:
        dataset = dataset_override
        dataset_name = 'Copernicus DEM 30m' if dataset == 'COP30' else ('SRTM 30m' if dataset == 'SRTMGL1' else dataset)
        resolution = '30m'
    else:
        if north > 60.0 or south < -56.0:
            dataset = 'COP30'
            dataset_name = 'Copernicus DEM 30m'
            resolution = '30m'
        else:
            dataset = 'SRTMGL1'
            dataset_name = 'SRTM 30m'
            resolution = '30m'

    print(f"\n  Downloading {region_info['name']}...")
    print(f"  Source: OpenTopography ({dataset_name})")
    print(f"  Bounds: {region_info['bounds']}")
    print(f"  Latitude range: {south:.1f}degN to {north:.1f}degN")
    if dataset == 'COP30':
        print(f"  Note: Using Copernicus DEM (SRTM doesn't cover >60degN)")

    try:
        import requests
        from load_settings import get_api_key
        # Reuse existing tiling utilities for large areas
        from downloaders.tile_large_states import calculate_tiles, merge_tiles
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

    # Prepare output path
    output_file = Path(f"data/raw/srtm_30m/{region_id}_bbox_30m.tif")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # If an existing raw file is present, validate its bounds against requested bounds.
    # If bounds differ, delete and re-download so expanded/corrected area is included.
    if output_file.exists():
        try:
            from src.metadata import get_metadata_path, load_metadata
            meta_path = get_metadata_path(output_file)
            if meta_path.exists():
                meta = load_metadata(meta_path)
                mb = meta.get('bounds', {})
                old_bounds = (float(mb.get('left')), float(mb.get('bottom')), float(mb.get('right')), float(mb.get('top')))
                new_bounds = (float(west), float(south), float(east), float(north))
                # Consider any difference > 1e-4 degrees as a mismatch requiring regeneration
                def _differs(a, b):
                    return any(abs(x - y) > 1e-4 for x, y in zip(a, b))
                if _differs(old_bounds, new_bounds):
                    print(f"  Bounds changed for {region_id}: old={old_bounds}, new={new_bounds}")
                    print(f"  Deleting existing raw file to regenerate with new bounds...")
                    try:
                        output_file.unlink()
                    except Exception:
                        pass
                    # Also remove stale metadata if present
                    try:
                        meta_path.unlink()
                    except Exception:
                        pass
                else:
                    print(f"  Already exists with matching bounds: {output_file.name}")
                    return True
            else:
                # No metadata; be conservative and assume mismatch only if clearly different can't be known.
                # Keep existing file to avoid unnecessary re-download.
                print(f"  Already exists (no metadata found): {output_file.name}")
                return True
        except Exception:
            # If metadata system unavailable, fall back to existing file
            print(f"  Already exists: {output_file.name}")
            return True

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
            downloaded = 0
            with open(out_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\r  Progress: {progress:.1f}%", end='', flush=True)
            print()
            return True
        except Exception:
            if out_path.exists():
                try:
                    out_path.unlink()
                except Exception:
                    pass
            return False

    # Estimate area to decide on tiling (avoid user-visible API limit errors)
    import math
    width_deg = max(0.0, float(east - west))
    height_deg = max(0.0, float(north - south))
    mid_lat = (north + south) / 2.0
    km_per_deg_lat = 110.574
    km_per_deg_lon = 111.320 * math.cos(math.radians(mid_lat))
    approx_area_km2 = (width_deg * km_per_deg_lon) * (height_deg * km_per_deg_lat)

    # OpenTopography SRTMGL1 has a 450,000 km^2 limit; tile proactively when over ~420k
    should_tile = (dataset == 'SRTMGL1') and (approx_area_km2 > 420_000 or width_deg > 4.0 or height_deg > 4.0)

    if should_tile:
        print(f"  Region is large ({approx_area_km2:,.0f} km^2). Downloading in tiles...", flush=True)
        # Use conservative tile size in degrees to keep each tile under area and dimension limits
        tiles = calculate_tiles((west, south, east, north), tile_size=3.5)
        tiles_dir = Path(f"data/raw/srtm_30m/tiles/{region_id}")
        tiles_dir.mkdir(parents=True, exist_ok=True)
        tile_paths = []
        for idx, tb in enumerate(tiles):
            print(f"\n  Tile {idx+1}/{len(tiles)} bounds: [{tb[0]:.4f}, {tb[1]:.4f}, {tb[2]:.4f}, {tb[3]:.4f}]", flush=True)
            tile_path = tiles_dir / f"{region_id}_tile_{idx:02d}.tif"
            if tile_path.exists():
                # Strong validation: try to read data to catch partial/corrupt tiles
                if validate_geotiff(tile_path, check_data=True):
                    try:
                        size_mb = tile_path.stat().st_size / (1024 * 1024)
                        print(f"  Cached tile present: {tile_path.name} ({size_mb:.1f} MB)", flush=True)
                    except Exception:
                        print(f"  Cached tile present: {tile_path.name}", flush=True)
                    tile_paths.append(tile_path)
                    continue
                else:
                    print(f"  Cached tile failed validation (will NOT delete). Attempting repaired re-download...", flush=True)
                    # Re-download to a separate file to preserve original
                    repaired_path = tiles_dir / f"{region_id}_tile_{idx:02d}_fix1.tif"
                    if _download_bbox(repaired_path, tb, dataset) and validate_geotiff(repaired_path, check_data=True):
                        try:
                            size_mb = repaired_path.stat().st_size / (1024 * 1024)
                            print(f"  Using repaired tile: {repaired_path.name} ({size_mb:.1f} MB)", flush=True)
                        except Exception:
                            print(f"  Using repaired tile: {repaired_path.name}", flush=True)
                        tile_paths.append(repaired_path)
                        continue
                    else:
                        print(f"  Repaired download failed; will skip this tile", flush=True)
                        # fall through to skip
            print(f"  Downloading tile...", flush=True)
            if not _download_bbox(tile_path, tb, dataset):
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
        # Save metadata for merged file
        try:
            from src.metadata import create_raw_metadata, save_metadata, get_metadata_path
            raw_meta = create_raw_metadata(
                tif_path=output_file,
                region_id=region_id,
                source='srtm_30m',
                download_url='tiled:OpenTopography',
                download_params={'tiles': len(tile_paths), 'dataset': dataset, 'bounds': region_info['bounds']}
            )
            save_metadata(raw_meta, get_metadata_path(output_file))
        except Exception as e:
            print(f"  Could not save raw metadata: {e}")
        print(f"  Tiled download and merge complete", flush=True)
        return True

    # Mixed-source handling: if region spans SRTM/COP30 boundary, split and merge
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
            # Decide tiling for SRTM only
            width_deg_p = max(0.0, float(pe - pw))
            height_deg_p = max(0.0, float(pn - ps))
            mid_lat_p = (pn + ps) / 2.0
            km_per_deg_lon_p = 111.320 * math.cos(math.radians(mid_lat_p))
            approx_area_km2_p = (width_deg_p * km_per_deg_lon_p) * (height_deg_p * km_per_deg_lat)
            tile_needed = (demtype == 'SRTMGL1') and (approx_area_km2_p > 420_000 or width_deg_p > 4.0 or height_deg_p > 4.0)
            if tile_needed:
                tiles = calculate_tiles(bbox, tile_size=3.5)
                tiles_dir_p = parts_dir / f"tiles_p{pi:02d}"
                tiles_dir_p.mkdir(parents=True, exist_ok=True)
                tile_paths_p: list[Path] = []
                for ti, tb in enumerate(tiles):
                    print(f"    Tile {ti+1}/{len(tiles)} bounds: [{tb[0]:.4f}, {tb[1]:.4f}, {tb[2]:.4f}, {tb[3]:.4f}]", flush=True)
                    tpath = tiles_dir_p / f"p{pi:02d}_t{ti:02d}.tif"
                    if not _download_bbox(tpath, tb, demtype):
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
                source='srtm_30m',
                download_url='mixed:OpenTopography',
                download_params={'parts': len(part_paths), 'bounds': region_info['bounds']}
            )
            save_metadata(raw_meta, get_metadata_path(output_file))
        except Exception as e:
            print(f"  Could not save raw metadata: {e}")
        print("  Mixed-source download complete", flush=True)
        return True

    # Download using OpenTopography API (single request)
    url = "https://portal.opentopography.org/API/globaldem"
    params = {
        'demtype': dataset,  # COP30 for high latitudes, SRTMGL1 otherwise
        'south': south,
        'north': north,
        'west': west,
        'east': east,
        'outputFormat': 'GTiff',
        'API_Key': api_key
    }

    print(f"  Requesting from OpenTopography...")
    print(f"  (This may take 30-120 seconds)")

    try:
        response = requests.get(url, params=params, stream=True, timeout=300)

        if response.status_code != 200:
            # If area too large, transparently fall back to tiling
            resp_text = response.text or ""
            if (dataset == 'SRTMGL1') and ("maximum area" in resp_text.lower() or response.status_code == 400):
                print(f" Server rejected single request due to size. Switching to tiled download...", flush=True)
                # Trigger tiled path
                # Recursively call this function but force tiling by adjusting threshold
                # Easiest: emulate should_tile path above
                # Re-enter tiling branch by locally setting should_tile-like behavior
                # Build tiles and merge
                tiles = calculate_tiles((west, south, east, north), tile_size=3.5)
                tiles_dir = Path(f"data/raw/srtm_30m/tiles/{region_id}")
                tiles_dir.mkdir(parents=True, exist_ok=True)
                tile_paths = []
                for idx, tb in enumerate(tiles):
                    print(f"\n  Tile {idx+1}/{len(tiles)} bounds: [{tb[0]:.4f}, {tb[1]:.4f}, {tb[2]:.4f}, {tb[3]:.4f}]", flush=True)
                    tile_path = tiles_dir / f"{region_id}_tile_{idx:02d}.tif"
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
                            print(f"  Cached tile failed validation (will NOT delete). Attempting repaired re-download...", flush=True)
                            repaired_path = tiles_dir / f"{region_id}_tile_{idx:02d}_fix1.tif"
                            if _download_bbox(repaired_path, tb, dataset) and validate_geotiff(repaired_path, check_data=True):
                                try:
                                    size_mb = repaired_path.stat().st_size / (1024 * 1024)
                                    print(f"  Using repaired tile: {repaired_path.name} ({size_mb:.1f} MB)", flush=True)
                                except Exception:
                                    print(f"  Using repaired tile: {repaired_path.name}", flush=True)
                                tile_paths.append(repaired_path)
                                continue
                            else:
                                print(f"  Repaired download failed; will skip this tile", flush=True)
                    print(f"  Downloading tile...", flush=True)
                    if not _download_bbox(tile_path, tb, dataset):
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
                        source='srtm_30m',
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

        # Download with progress
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(output_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\r  Progress: {progress:.1f}%", end='', flush=True)

        print()  # New line after progress
        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"  Downloaded successfully ({file_size_mb:.1f} MB)")
        # Write raw metadata including bounds so future bound changes can auto-invalidate
        try:
            from src.metadata import create_raw_metadata, save_metadata, get_metadata_path
            raw_meta = create_raw_metadata(
                tif_path=output_file,
                region_id=region_id,
                source='srtm_30m',
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


def download_region(region_id, region_type, region_info, dataset_override: str | None = None):
    """Route to appropriate downloader based on region type."""
    if region_type == 'us_state':
        return download_us_state(region_id, region_info)
    elif region_type == 'international':
        return download_international_region(region_id, region_info, dataset_override)
    else:
        print(f"  Unknown region type: {region_type}")
        return False


def determine_dataset_override(region_id: str, region_type: str, region_info: dict) -> str | None:
    """
    Stage 2/3: Determine dataset to use for download.
    - US states: USGS 3DEP (implicit in downloader) → return 'USA_3DEP'
    - International: override from RegionConfig.recommended_dataset if provided; else choose by latitude:
        * SRTMGL1 for 60°N to 56°S
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

    west, south, east, north = region_info['bounds']
    lat_choice = 'COP30' if (north > 60.0 or south < -56.0) else 'SRTMGL1'
    print(f"[STAGE 3/10] Latitude-based dataset: {lat_choice}")
    return lat_choice


def process_region(region_id, raw_path, source, target_pixels, force, region_type, region_info, border_resolution='10m'):
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

    # Delete existing files if force
    if force:
        print("  Force mode: deleting existing processed files...", flush=True)
        for pattern in [
            f"data/clipped/*/{region_id}_*",
            f"data/processed/*/{region_id}_*",
            f"generated/regions/{region_id}_*"
        ]:
            import glob
            for file_path in glob.glob(pattern, recursive=True):
                Path(file_path).unlink()
                print(f"  Deleted: {Path(file_path).name}", flush=True)

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
    # Clean existing artifacts
    for pattern in [
        f"data/clipped/*/{region_id}_*",
        f"data/processed/*/{region_id}_*",
        f"generated/regions/{region_id}_*"
    ]:
        import glob
        for file_path in glob.glob(pattern, recursive=True):
            try:
                Path(file_path).unlink()
                print(f"  Deleted: {Path(file_path).name}", flush=True)
            except Exception:
                pass

    # Locate raw again and re-run
    raw_path, _ = find_raw_file(region_id)
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


# ============================================================================
# PIPELINE PROCESSING FUNCTIONS (consolidated from src/pipeline.py)
# ============================================================================

def clip_to_boundary(
    raw_tif_path: Path,
    region_id: str,
    boundary_name: str,
    output_path: Path,
    source: str = "srtm_30m",
    boundary_type: str = "country",
    border_resolution: str = "10m",
    boundary_required: bool = False
) -> bool:
    """
    Clip raw elevation data to administrative boundary.

    Args:
        raw_tif_path: Path to raw bounding box TIF
        region_id: Region identifier (e.g., 'california')
        boundary_name: Boundary to clip to
            - If boundary_type="country": "United States of America"
            - If boundary_type="state": "United States of America/Tennessee"
        output_path: Where to save clipped TIF
        source: Data source name
        boundary_type: "country" or "state"

    Returns:
        True if successful
    """
    # Validate input file first
    if not raw_tif_path.exists():
        print(f"  Input file not found: {raw_tif_path}")
        return False

    # Check if output exists and is valid
    if output_path.exists():
        try:
            # Validate the existing clipped file
            with rasterio.open(output_path) as src:
                if src.width > 0 and src.height > 0:
                    # Try reading a small sample to ensure it's not corrupted
                    _ = src.read(1, window=((0, min(10, src.height)), (0, min(10, src.width))))
                    print(f"  Already clipped (validated): {output_path.name}")
                    return True
        except Exception as e:
            print(f"  Existing file corrupted: {e}")
            print(f"  Deleting and regenerating...")
            try:
                output_path.unlink()
            except Exception as del_e:
                print(f"  Could not delete: {del_e}")

    # If we're regenerating the clipped file, delete dependent processed and generated files
    # This ensures the entire pipeline uses consistent data
    processed_dir = Path('data/processed') / source
    generated_dir = Path('generated/regions')

    deleted_deps = []
    if processed_dir.exists():
        for f in processed_dir.glob(f'{region_id}_*'):
            f.unlink()
            deleted_deps.append(f"processed/{f.name}")
    if generated_dir.exists():
        for f in generated_dir.glob(f'{region_id}_*'):
            f.unlink()
            deleted_deps.append(f"generated/{f.name}")

    if deleted_deps:
        print(f"  Deleted {len(deleted_deps)} dependent file(s) (will be regenerated)")

    print(f"  Loading {boundary_type} boundary geometry for {boundary_name}...")

    # Get boundary geometry based on type
    if boundary_type == "country":
        # Use GeoDataFrame so we can reproject reliably
        border_manager = get_border_manager()
        geometry_gdf = border_manager.get_country(boundary_name, resolution=border_resolution)
    elif boundary_type == "state":
        # Parse "Country/State" format
        if "/" not in boundary_name:
            print(f"  Error: State boundary requires 'Country/State' format")
            print(f"  Got: {boundary_name}")
            return False

        country, state = boundary_name.split("/", 1)
        border_manager = get_border_manager()
        geometry_gdf = border_manager.get_state(country, state, resolution=border_resolution)

        if geometry_gdf is None or geometry_gdf.empty:
            if boundary_required:
                error_msg = f"State '{state}' boundary not found in '{country}' and boundary is required."
                print(f"  Error: {error_msg}")
                raise PipelineError(error_msg)
            else:
                print(f"  Warning: State '{state}' not found in '{country}'. Skipping clipping step...")
            return False
    else:
        print(f"  Error: Invalid boundary_type '{boundary_type}' (must be 'country' or 'state')")
        return False

    if geometry_gdf is None or geometry_gdf.empty:
        if boundary_required:
            error_msg = f"Could not find boundary '{boundary_name}' and boundary is required."
            print(f"  Error: {error_msg}")
            raise PipelineError(error_msg)
        else:
            print(f"  Warning: Could not find boundary '{boundary_name}'. Skipping clipping step...")
        return False

    print(f"  Clipping to {boundary_type} boundary...")

    try:
        with rasterio.open(raw_tif_path) as src:
            print(f"  Input dimensions: {src.width} x {src.height} pixels")
            print(f"  Input size: {raw_tif_path.stat().st_size / (1024*1024):.1f} MB")

            # Prepare boundary geometry in raster CRS and GeoJSON mapping
            try:
                geometry_reproj = geometry_gdf.to_crs(src.crs)
            except Exception:
                geometry_reproj = geometry_gdf
            union_geom = unary_union(geometry_reproj.geometry)
            geoms = [shapely_mapping(union_geom)]

            # Clip the raster to the boundary
            print(f"  Applying geometric mask...")
            out_image, out_transform = rasterio_mask(
                src,
                geoms,
                crop=True,
                filled=False
            )
            out_meta = src.meta.copy()

            # Update metadata
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform
            })

            print(f"  Output dimensions: {out_meta['width']} x {out_meta['height']} pixels")

            # Ensure nodata is set and masked pixels are written as nodata
            if np.ma.isMaskedArray(out_image):
                # Choose an appropriate nodata value based on troy
                if src.nodata is not None:
                    nodata_value = src.nodata
                else:
                    if np.issubdtype(src.dtypes[0], np.floating):
                        nodata_value = np.nan
                    else:
                        # For integer rasters, use minimum value for the dtype
                        nodata_value = np.iinfo(np.dtype(src.dtypes[0])).min
                out_meta['nodata'] = nodata_value
                out_image = out_image.filled(nodata_value)

            # Reprojection moved to Stage 7: reproject_to_metric_crs()

            # VALIDATION: Check elevation range to catch corruption
            from src.validation import validate_elevation_range
            min_elev, max_elev, elev_range, is_valid = validate_elevation_range(
                out_image[0], min_sensible_range=50.0, warn_only=False
            )
            if not is_valid:
                raise ValueError(f"Elevation corruption detected! Range: {elev_range:.1f}m")
            print(f"  Elevation range validated: {min_elev:.1f}m to {max_elev:.1f}m (range: {elev_range:.1f}m)")

            # Write clipped (and possibly reprojected) data
            print(f"  Writing clipped raster to disk...")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(output_path, "w", **out_meta) as dest:
                dest.write(out_image)

            # Create metadata
            source_hash = compute_file_hash(raw_tif_path)
            metadata = create_clipped_metadata(
                output_path,
                region_id=region_id,
                source_file=raw_tif_path,
                source_file_hash=source_hash,
                clip_boundary=boundary_name
            )
            save_metadata(metadata, get_metadata_path(output_path))

            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"  Clipped: {output_path.name} ({file_size_mb:.1f} MB)")
            return True

    except Exception as e:
        print(f"  Clipping failed: {e}")
        if output_path.exists():
            output_path.unlink()
        return False


def reproject_to_metric_crs(
    input_tif_path: Path,
    region_id: str,
    output_path: Path,
    source: str = "srtm_30m"
) -> bool:
    """
    Stage 7: Reproject to metric CRS to fix latitude-dependent aspect ratio distortion.
    
    Reprojects ALL EPSG:4326 (lat/lon) inputs to metric CRS (EPSG:3857 or polar).
    After this stage, data is treated as a pure 2D array everywhere else.
    
    Args:
        input_tif_path: Path to clipped TIF (may be EPSG:4326)
        region_id: Region identifier
        output_path: Where to save reprojected TIF
        source: Data source name
        
    Returns:
        True if successful (or if no reprojection needed)
    """
    if not input_tif_path.exists():
        print(f"  Input file not found: {input_tif_path}")
        return False
    
    # Check if already reprojected to metric CRS
    if output_path.exists():
        try:
            with rasterio.open(output_path) as src:
                if src.width > 0 and src.height > 0:
                    crs_str = str(src.crs) if src.crs is not None else ""
                    is_latlon = ('EPSG:4326' in crs_str.upper()) or ('WGS84' in crs_str.upper())
                    if not is_latlon:
                        print(f"  Already reprojected (validated): {output_path.name}")
                        return True
        except Exception as e:
            print(f"  Existing file invalid: {e}")
            try:
                output_path.unlink()
            except Exception:
                pass
    
    # Delete dependent files if regenerating
    processed_dir = Path('data/processed') / source
    generated_dir = Path('generated/regions')
    for d in [processed_dir, generated_dir]:
        if d.exists():
            for f in d.glob(f'{region_id}_*'):
                f.unlink()
    
    try:
        with rasterio.open(input_tif_path) as src:
            # Check if reprojection is needed
            needs_reprojection = False
            if src.crs and 'EPSG:4326' in str(src.crs).upper():
                needs_reprojection = True
                bounds = src.bounds
                avg_lat = (bounds.top + bounds.bottom) / 2
                
                print(f"  Reprojecting from EPSG:4326 to metric CRS...")
                print(f"  Average latitude: {avg_lat:.2f}deg")
                
                import math
                abs_lat = abs(avg_lat)
                cos_lat = math.cos(math.radians(abs_lat))
                distortion = 1.0 / cos_lat if cos_lat > 0.01 else 1.0
                print(f"  Latitude {avg_lat:+.1f}deg - aspect ratio distorted {distortion:.2f}x by EPSG:4326")
            
            if not needs_reprojection:
                # Already in metric CRS, just copy
                print(f"  Input already in metric CRS, copying...")
                import shutil
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(input_tif_path, output_path)
                return True
            
            # Reproject to metric CRS
            from rasterio.warp import calculate_default_transform, reproject, Resampling
            
            # Choose appropriate projection
            if abs(avg_lat) < 85:
                dst_crs = 'EPSG:3857'  # Web Mercator
            else:
                dst_crs = 'EPSG:3413' if avg_lat > 0 else 'EPSG:3031'  # Polar stereographic
            
            # Calculate transform for reprojection
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs,
                src.width, src.height,
                *src.bounds
            )
            
            # Prepare output metadata
            out_meta = src.meta.copy()
            out_meta.update({
                'crs': dst_crs,
                'transform': transform,
                'width': width,
                'height': height
            })
            
            # Initialize nodata
            if out_meta.get('nodata') is None:
                if np.issubdtype(src.dtypes[0], np.floating):
                    out_meta['nodata'] = -9999.0
                else:
                    out_meta['nodata'] = np.iinfo(src.dtypes[0]).min
            
            # Read source data
            elevation = src.read(1)
            
            # Create reprojected array
            reprojected = np.empty((1, height, width), dtype=elevation.dtype)
            reprojected.fill(out_meta['nodata'])
            
            # Perform reprojection
            reproject(
                source=elevation,
                destination=reprojected,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear,
                src_nodata=src.nodata if src.nodata is not None else out_meta['nodata'],
                dst_nodata=out_meta['nodata']
            )
            
            # Validate elevation range
            from src.validation import validate_elevation_range
            min_elev, max_elev, elev_range, is_valid = validate_elevation_range(
                reprojected[0], min_sensible_range=50.0, warn_only=False
            )
            if not is_valid:
                raise ValueError(f"Elevation corruption detected after reprojection! Range: {elev_range:.1f}m")
            
            # Write reprojected data
            print(f"  Writing reprojected raster...")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(output_path, "w", **out_meta) as dest:
                dest.write(reprojected)
            
            old_aspect = src.width / src.height
            new_aspect = width / height
            print(f"  Aspect ratio: {old_aspect:.2f}:1 -> {new_aspect:.2f}:1")
            print(f"  Reprojected: {output_path.name} ({width} x {height} pixels)")
            return True
            
    except Exception as e:
        print(f"  Reprojection failed: {e}")
        if output_path.exists():
            output_path.unlink()
        return False


def downsample_for_viewer(
    input_tif_path: Path,
    region_id: str,
    output_path: Path,
    target_pixels: int = 2048
) -> bool:
    """
    Stage 8: Downsample reprojected data to target resolution for web viewer.
    
    Args:
        input_tif_path: Path to reprojected TIF (must be in metric CRS, not EPSG:4326)
        region_id: Region identifier
        output_path: Where to save processed TIF
        target_pixels: Target dimension in pixels (default: 2048)
        
    Returns:
        True if successful
    """
    if not input_tif_path.exists():
        print(f"  Input file not found: {input_tif_path}")
        return False
    
    # Check if output exists and is valid
    if output_path.exists():
        try:
            with rasterio.open(output_path) as src:
                if src.width > 0 and src.height > 0:
                    _ = src.read(1, window=((0, min(10, src.height)), (0, min(10, src.width))))
                    crs_str = str(src.crs) if src.crs is not None else ""
                    is_latlon = ('EPSG:4326' in crs_str.upper()) or ('WGS84' in crs_str.upper())
                    if is_latlon:
                        print(f"  Processed file uses geographic CRS; regenerating...")
                        raise RuntimeError("processed_file_crs_is_latlon")
                    print(f"  Already processed (validated): {output_path.name}")
                    return True
        except Exception as e:
            print(f"  Existing file invalid: {e}")
            try:
                output_path.unlink()
            except Exception:
                pass
    
    # Delete dependent generated files
    generated_dir = Path('generated/regions')
    if generated_dir.exists():
        for f in generated_dir.glob(f'{region_id}_*'):
            f.unlink()
    
    print(f"  Downsampling to target resolution ({target_pixels}px)...")
    
    try:
        with rasterio.open(input_tif_path) as src:
            # Validate input is NOT EPSG:4326 (should have been reprojected in Stage 7)
            crs_str = str(src.crs) if src.crs is not None else ""
            if 'EPSG:4326' in crs_str.upper() or 'WGS84' in crs_str.upper():
                raise ValueError(f"Input must be in metric CRS (was reprojected in Stage 7), but got: {crs_str}")
            
            print(f"  Input: {src.width} x {src.height} pixels")
            
            # Compute target size preserving aspect ratio
            aspect = src.width / src.height if src.height != 0 else 1.0
            if src.width >= src.height:
                dst_width = min(target_pixels, src.width)
                dst_height = max(1, int(round(dst_width / aspect)))
            else:
                dst_height = min(target_pixels, src.height)
                dst_width = max(1, int(round(dst_height * aspect)))
            
            # Read and downsample
            from rasterio.warp import Resampling
            from rasterio import Affine
            
            elevation = src.read(1, out_shape=(dst_height, dst_width), resampling=Resampling.bilinear)
            
            # Update metadata
            scale_x = src.width / dst_width
            scale_y = src.height / dst_height
            out_meta = src.meta.copy()
            out_transform = src.transform * Affine.scale(scale_x, scale_y)
            out_meta.update({
                'width': dst_width,
                'height': dst_height,
                'transform': out_transform
            })
            
            # Validate elevation range (fail hard on hyperflat)
            from src.validation import validate_elevation_range
            _min, _max, _range, _ok = validate_elevation_range(elevation, min_sensible_range=50.0, warn_only=False)
            
            print(f"  Target: {dst_width} x {dst_height} pixels")
            
            # Write processed data
            print(f"  Writing processed raster...")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(output_path, "w", **out_meta) as dest:
                dest.write(elevation, 1)
            
            # Create metadata
            source_hash = compute_file_hash(input_tif_path)
            metadata = create_processed_metadata(
                output_path,
                region_id=region_id,
                source_file=input_tif_path,
                source_file_hash=source_hash,
                target_pixels=target_pixels
            )
            save_metadata(metadata, get_metadata_path(output_path))
            
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"  Processed: {output_path.name} ({file_size_mb:.1f} MB)")
            return True
            
    except Exception as e:
        print(f"  Processing failed: {e}")
        if output_path.exists():
            output_path.unlink()
        return False


def export_for_viewer(
    processed_tif_path: Path,
    region_id: str,
    source: str,
    output_path: Path,
    validate_output: bool = True
) -> bool:
    """
    Stage 9: Export processed TIF to JSON format for web viewer.
    zips automatically as Stage 10.
    
    Args:
        processed_tif_path: Path to processed TIF (metric CRS, downsampled)
        region_id: Region identifier
        source: Data source (e.g., 'srtm_30m', 'usa_3dep')
        output_path: Where to save JSON
        validate_output: If True, validate coverage
        
    Returns:
        True if successful
    """
    if not processed_tif_path.exists():
        print(f"  Input file not found: {processed_tif_path}")
        return False
    
    # Check if output exists and is valid
    if output_path.exists():
        try:
            with open(output_path) as f:
                data = json.load(f)
            required_fields = ['region_id', 'width', 'height', 'elevation', 'bounds']
            if all(field in data for field in required_fields):
                if data['width'] > 0 and data['height'] > 0 and len(data['elevation']) > 0:
                    print(f"  Already exported (validated): {output_path.name}")
                    return True
            output_path.unlink()
        except Exception as e:
            try:
                output_path.unlink()
            except Exception:
                pass
    
    print(f"  Exporting to JSON...")
    
    try:
        with rasterio.open(processed_tif_path) as src:
            print(f"  Reading raster: {src.width} x {src.height}", flush=True)
            elevation = src.read(1)
            bounds = src.bounds
            
            # Transform bounds to EPSG:4326 (lat/lon) for consistent export
            from rasterio.warp import transform_bounds
            if src.crs and src.crs != 'EPSG:4326':
                print(f"  Converting bounds from {src.crs} to EPSG:4326...", flush=True)
                bounds_4326 = transform_bounds(src.crs, 'EPSG:4326',
                    bounds.left, bounds.bottom,
                    bounds.right, bounds.top)
                from rasterio.coords import BoundingBox
                bounds = BoundingBox(bounds_4326[0], bounds_4326[1],
                    bounds_4326[2], bounds_4326[3])
            
            # Validate coverage
            if validate_output:
                from src.validation import validate_non_null_coverage
                try:
                    coverage = validate_non_null_coverage(elevation, min_coverage=0.2, warn_only=True)
                    print(f"  Validation passed: coverage={coverage*100:.1f}%")
                except Exception as e:
                    print(f"  Validation warning: {e}")
            
            # Filter bad values
            elevation_clean = elevation.astype(np.float32)
            elevation_clean[(elevation_clean < -500) | (elevation_clean > 9000)] = np.nan
            
            valid_count = np.sum(~np.isnan(elevation_clean))
            if valid_count == 0:
                print(f"  Error: No valid elevation data")
                return False
            
            # Validate elevation range (fail hard on hyperflat)
            from src.validation import validate_elevation_range
            _min, _max, _range, _ok = validate_elevation_range(elevation_clean, min_sensible_range=50.0, warn_only=False)
            
            # Convert to list
            print(f"  Converting to JSON format...", flush=True)
            elevation_list = []
            for row in elevation_clean:
                row_list = []
                for val in row:
                    if np.isnan(val):
                        row_list.append(None)
                    else:
                        row_list.append(float(val))
                elevation_list.append(row_list)
            
            # Create export data
            export_data = {
                "version": get_current_version('export'),
                "region_id": region_id,
                "source": source,
                "name": region_id.replace('_', ' ').title(),
                "width": int(src.width),
                "height": int(src.height),
                "elevation": elevation_list,
                "bounds": {
                    "left": float(bounds.left),
                    "right": float(bounds.right),
                    "top": float(bounds.top),
                    "bottom": float(bounds.bottom)
                },
                "stats": {
                    "min": float(np.nanmin(elevation_clean)),
                    "max": float(np.nanmax(elevation_clean)),
                    "mean": float(np.nanmean(elevation_clean))
                }
            }
            
            # Write JSON
            print(f"  Writing JSON to disk...")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(export_data, f, separators=(',', ':'))
            
            # Stage 10: Gzip compression
            print(f"  Compressing with gzip...")
            import gzip
            gzip_path = output_path.with_suffix('.json.gz')
            with open(output_path, 'rb') as f_in:
                with gzip.open(gzip_path, 'wb', compresslevel=9) as f_out:
                    f_out.writelines(f_in)
            
            gzip_size_mb = gzip_path.stat().st_size / (1024 * 1024)
            compression_ratio = (1 - gzip_path.stat().st_size / output_path.stat().st_size) * 100
            print(f"  Compressed: {gzip_path.name} ({gzip_size_mb:.1f} MB, {compression_ratio:.1f}% smaller)")
            
            # Create metadata
            metadata = create_export_metadata(
                output_path,
                region_id=region_id,
                source=source,
                source_file=processed_tif_path,
                resolution_meters=30  # Default
            )
            save_metadata(metadata, get_metadata_path(output_path))
            
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"  Exported: {output_path.name} ({file_size_mb:.1f} MB)", flush=True)
            return True
            
    except Exception as e:
        import traceback
        print(f"  Export failed: {e}", flush=True)
        traceback.print_exc()
        if output_path.exists():
            output_path.unlink()
        return False


def update_regions_manifest(generated_dir: Path) -> bool:
    """
    Stage 11: Update the regions manifest with all available regions.
    
    Args:
        generated_dir: Directory containing exported JSON files
        
    Returns:
        True if successful
    """
    print(f"  Updating regions manifest...")
    
    try:
        manifest = {
            "version": get_current_version('export'),
            "regions": {}
        }
        
        # Find all JSON files (excluding manifests, metadata, and borders)
        for json_file in sorted(generated_dir.glob("*.json")):
            if (json_file.stem.endswith('_meta') or
                json_file.stem.endswith('_borders') or
                'manifest' in json_file.stem):
                continue
            
            try:
                with open(json_file) as f:
                    data = json.load(f)
                
                # Extract region_id
                stem = json_file.stem
                for suffix in ['_srtm_30m_2048px_v2', '_srtm_30m_800px_v2', '_srtm_30m_v2', '_bbox_30m', '_usa_3dep_2048px_v2']:
                    if stem.endswith(suffix):
                        stem = stem[:-len(suffix)]
                        break
                
                region_id = data.get("region_id", stem)

                entry = {
                    "name": data.get("name", region_id.replace('_', ' ').title()),
                    "description": data.get("description", f"{data.get('name', region_id)} elevation data"),
                    "source": data.get("source", "unknown"),
                    "file": str(json_file.name),
                    "bounds": data.get("bounds", {}),
                    "stats": data.get("stats", {})
                }

                # Attach category from centralized config if available
                try:
                    from src.regions_config import get_region  # local import
                    cfg = get_region(region_id) if callable(get_region) else None
                    if cfg and getattr(cfg, 'category', None):
                        entry["category"] = getattr(cfg, 'category')
                except Exception:
                    pass

                manifest["regions"][region_id] = entry
            except Exception as e:
                print(f"  Skipping {json_file.name}: {e}")
                continue
        
        # Write manifest
        manifest_path = generated_dir / "regions_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"  Manifest updated ({len(manifest['regions'])} regions)")
        return True
        
    except Exception as e:
        print(f"  Warning: Could not update manifest: {e}")
        return False


def run_pipeline(
    raw_tif_path: Path,
    region_id: str,
    source: str,
    boundary_name: Optional[str] = None,
    boundary_type: str = "country",
    target_pixels: int = 2048,
    skip_clip: bool = False,
    border_resolution: str = "10m"
) -> tuple[bool, dict]:
    """
    Unified pipeline (Stages 6-11). Assumes raw download already completed.
    """
    print(f"\n{'='*70}")
    print(f" PROCESSING PIPELINE")
    print(f"{'='*70}")
    print(f"Region: {region_id}")
    print(f"Source: {source}")
    print(f"{'='*70}\n")

    result_paths = {
        "raw": raw_tif_path,
        "clipped": None,
        "processed": None,
        "exported": None,
    }

    data_root = Path("data")
    clipped_dir = data_root / "clipped" / source
    processed_dir = data_root / "processed" / source
    generated_dir = Path("generated/regions")

    # Stage 6: clip
    if skip_clip or not boundary_name:
        print(f"[STAGE 6/10] Skipping clipping (using raw data)")
        clipped_path = raw_tif_path
    else:
        print(f"[STAGE 6/10] Clipping to {boundary_type} boundary: {boundary_name} ({border_resolution})")
        clipped_path = clipped_dir / f"{region_id}_clipped_{source}_v1.tif"
        try:
            if not clip_to_boundary(
                raw_tif_path, region_id, boundary_name, clipped_path,
                source, boundary_type, border_resolution, boundary_required=bool(boundary_name)
            ):
                print(f"\n[STAGE 6/10] FAILED: Clipping failed and boundary was required ({boundary_name}).")
                return False, result_paths
        except PipelineError as e:
            print(f"\n[STAGE 6/10] FAILED: {e}")
            return False, result_paths

    result_paths["clipped"] = clipped_path

    # Stage 7: reproject
    reprojected_path = processed_dir / f"{region_id}_{source}_reproj.tif"
    print(f"\n[STAGE 7/10] Reprojecting to metric CRS...")
    if not reproject_to_metric_crs(clipped_path, region_id, reprojected_path, source):
        return False, result_paths

    # Stage 8: downsample
    print(f"\n[STAGE 8/10] Processing for viewer...")
    processed_path = processed_dir / f"{region_id}_{source}_{target_pixels}px_v2.tif"
    if not downsample_for_viewer(reprojected_path, region_id, processed_path, target_pixels):
        return False, result_paths
    result_paths["processed"] = processed_path

    # Stage 9: export JSON
    print(f"\n[STAGE 9/10] Exporting for web viewer...")
    exported_path = generated_dir / f"{region_id}_{source}_{target_pixels}px_v2.json"
    if not export_for_viewer(processed_path, region_id, source, exported_path):
        return False, result_paths
    result_paths["exported"] = exported_path

    # Stage 10: manifest
    print(f"[STAGE 10/10] Updating regions manifest...")
    update_regions_manifest(generated_dir)

    print(f"\n{'='*70}")
    print(f" PIPELINE COMPLETE!")
    print(f"{'='*70}")
    print(f"Region '{region_id}' is ready to view!")
    print(f"\nFiles created:")
    if result_paths["clipped"] != raw_tif_path:
        print(f"  Clipped: {result_paths['clipped']}")
    print(f"  Processed: {result_paths['processed']}")
    print(f"  Exported: {result_paths['exported']}")

    return True, result_paths

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
                raw_path, source = find_raw_file(rid)
                if not raw_path:
                    dataset_override = determine_dataset_override(rid, region_type, region_info)
                    if not download_region(rid, region_type, region_info, dataset_override):
                        print(f"  Download failed for {rid}")
                        continue
                    raw_path, source = find_raw_file(rid)
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

        print("\n  AVAILABLE REGIONS:")
        print("="*70)
        print("\n  US STATES:")
        for state_id in sorted(US_STATES.keys()):
            config = US_STATES[state_id]
            tag = _status_tag(state_id)
            print(f"    - {state_id:20s} -> {config.name:30s} {tag}")
        print(f"\n  COUNTRIES:")
        for country_id in sorted(COUNTRIES.keys()):
            config = COUNTRIES[country_id]
            tag = _status_tag(country_id)
            print(f"    - {country_id:20s} -> {config.name:30s} {tag}")
        print(f"\n  REGIONS:")
        for region_id in sorted(REGIONS.keys()):
            config = REGIONS[region_id]
            tag = _status_tag(region_id)
            print(f"    - {region_id:20s} -> {config.name:30s} {tag}")
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
    raw_path, source = find_raw_file(region_id)

    if not raw_path:
        print(f"  No raw data found for {region_id}", flush=True)

        if args.check_only:
            print(f"  Use without --check-only to download", flush=True)
            return 1

        # Download raw data
        print(f"[STAGE 4/10] Downloading...", flush=True)
        if not download_region(region_id, region_type, region_info, dataset_override):
            print(f"  Download failed!", flush=True)
            return 1

        # Re-validate the downloaded file
        print(f"  Validating...", flush=True)
        raw_path, source = find_raw_file(region_id)
        if not raw_path:
            print(f"  Validation failed - file may be corrupted", flush=True)
            print(f"  Expected: data/raw/srtm_30m/{region_id}_bbox_30m.tif", flush=True)
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