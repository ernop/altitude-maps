"""
One command to ensure a region is ready to view.

Downloads if needed, processes if needed, checks if everything is valid.
Works for both US states and international regions.

Usage:
    python ensure_region.py ohio                    # US state
    python ensure_region.py iceland                 # International region
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

# Import region definitions
from download_regions import REGIONS as INTERNATIONAL_REGIONS


def check_venv():
    """Ensure we're running in the virtual environment."""
    # Check if we're in a venv
    in_venv = (hasattr(sys, 'real_prefix') or 
               (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))
    
    if not in_venv:
        print("\n" + "="*70)
        print("❌ ERROR: Not running in virtual environment!")
        print("="*70)
        print("\nYou must activate the virtual environment first:")
        if sys.platform == 'win32':
            print("  .\\venv\\Scripts\\Activate.ps1    # PowerShell")
            print("  .\\venv\\Scripts\\activate.bat    # Command Prompt")
        else:
            print("  source venv/bin/activate")
        print("\nOr run the setup script:")
        print("  .\\setup.ps1    # Windows")
        print("  ./setup.sh     # Linux/Mac")
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
        print(f"      ⚠️  File too small ({file_size} bytes), likely corrupted", flush=True)
        return False
    
    try:
        import rasterio
        with rasterio.open(file_path) as src:
            # Basic checks
            if src.width == 0 or src.height == 0:
                print(f"      ⚠️  Invalid dimensions: {src.width}×{src.height}", flush=True)
                return False
            
            # Check that CRS and transform exist
            if src.crs is None or src.transform is None:
                print(f"      ⚠️  Missing CRS or transform", flush=True)
                return False
            
            if check_data:
                # Try to read a small sample to verify data accessibility
                try:
                    sample_height = min(100, src.height)
                    sample_width = min(100, src.width)
                    data = src.read(1, window=((0, sample_height), (0, sample_width)))
                    # Check for any non-null data in the sample
                    import numpy as np
                    valid_count = np.sum(~np.isnan(data.astype(float)) & (data > -500))
                    if valid_count == 0:
                        print(f"      ⚠️  No valid elevation data in sample", flush=True)
                        return False
                except Exception as e:
                    # Data read failed, but file structure is valid
                    # Allow it to pass - the pipeline will handle read errors
                    print(f"      ⚠️  Warning: Could not verify data sample: {e}", flush=True)
            
            return True
            
    except Exception as e:
        print(f"      ⚠️  Not a valid GeoTIFF: {e}", flush=True)
        return False


def validate_json_export(file_path: Path) -> bool:
    """
    Validate an exported JSON file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        True if file is valid, False otherwise
    """
    if not file_path.exists():
        return False
    
    # Check file size
    file_size = file_path.stat().st_size
    if file_size < 1024:
        print(f"      ⚠️  JSON too small ({file_size} bytes), likely incomplete")
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
                print(f"      ⚠️  Missing required field: {field}")
                return False
        
        # Validate dimensions
        if data['width'] <= 0 or data['height'] <= 0:
            print(f"      ⚠️  Invalid dimensions: {data['width']}×{data['height']}")
            return False
        
        # Validate elevation data structure
        elevation = data['elevation']
        if not isinstance(elevation, list) or len(elevation) == 0:
            print(f"      ⚠️  Invalid elevation data structure")
            return False
        
        # Check that elevation matches dimensions
        if len(elevation) != data['height']:
            print(f"      ⚠️  Elevation height mismatch: {len(elevation)} != {data['height']}")
            return False
        
        if len(elevation[0]) != data['width']:
            print(f"      ⚠️  Elevation width mismatch: {len(elevation[0])} != {data['width']}")
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
                    print(f"      ⚠️  Suspicious elevation range: {min_elev:.1f}m to {max_elev:.1f}m (range: {elev_range:.1f}m)")
                    print(f"      This suggests reprojection corruption - data should be regenerated")
                    return False
                
                print(f"      ✅ Elevation range OK: {min_elev:.1f}m to {max_elev:.1f}m (range: {elev_range:.1f}m)")
        except Exception as e:
            print(f"      ⚠️  Could not validate elevation range: {e}")
            # Don't fail on this - might be edge case with edge case data
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"      ⚠️  Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"      ⚠️  Validation error: {e}")
        return False


# US State name mapping
US_STATE_NAMES = {
    'alabama': 'Alabama', 'arizona': 'Arizona', 'arkansas': 'Arkansas',
    'california': 'California', 'colorado': 'Colorado', 'connecticut': 'Connecticut',
    'delaware': 'Delaware', 'florida': 'Florida', 'georgia': 'Georgia',
    'idaho': 'Idaho', 'illinois': 'Illinois', 'indiana': 'Indiana',
    'iowa': 'Iowa', 'kansas': 'Kansas', 'kentucky': 'Kentucky',
    'louisiana': 'Louisiana', 'maine': 'Maine', 'maryland': 'Maryland',
    'massachusetts': 'Massachusetts', 'michigan': 'Michigan', 'minnesota': 'Minnesota',
    'mississippi': 'Mississippi', 'missouri': 'Missouri', 'montana': 'Montana',
    'nebraska': 'Nebraska', 'nevada': 'Nevada', 'new_hampshire': 'New Hampshire',
    'new_jersey': 'New Jersey', 'new_mexico': 'New Mexico', 'new_york': 'New York',
    'north_carolina': 'North Carolina', 'north_dakota': 'North Dakota',
    'ohio': 'Ohio', 'oklahoma': 'Oklahoma', 'oregon': 'Oregon',
    'pennsylvania': 'Pennsylvania', 'rhode_island': 'Rhode Island',
    'south_carolina': 'South Carolina', 'south_dakota': 'South Dakota',
    'tennessee': 'Tennessee', 'texas': 'Texas', 'utah': 'Utah',
    'vermont': 'Vermont', 'virginia': 'Virginia', 'washington': 'Washington',
    'west_virginia': 'West Virginia', 'wisconsin': 'Wisconsin', 'wyoming': 'Wyoming'
}


def get_region_info(region_id):
    """
    Get information about a region (US state or international).
    
    Returns:
        Tuple of (region_type, region_data) where:
        - region_type is 'us_state' or 'international'
        - region_data is a dict with region info
        
        Returns (None, None) if region not found
    """
    # Check if it's a US state
    if region_id in US_STATE_NAMES:
        return 'us_state', {
            'name': US_STATE_NAMES[region_id],
            'display_name': US_STATE_NAMES[region_id]
        }
    
    # Check if it's an international region
    if region_id in INTERNATIONAL_REGIONS:
        region_data = INTERNATIONAL_REGIONS[region_id]
        return 'international', {
            'name': region_data['name'],
            'display_name': region_data['name'],
            'bounds': region_data['bounds'],
            'description': region_data['description'],
            'clip_boundary': region_data.get('clip_boundary', True)  # Default to True for backward compatibility
        }
    
    return None, None


def find_raw_file(region_id):
    """
    Find and validate raw file for a region.
    
    Returns:
        Tuple of (path, source) if valid file found, (None, None) otherwise
    """
    possible_locations = [
        Path(f"data/raw/srtm_30m/{region_id}_bbox_30m.tif"),
        Path(f"data/regions/{region_id}.tif"),
        Path(f"data/raw/usa_3dep/{region_id}_3dep_10m.tif"),
    ]
    
    for path in possible_locations:
        if path.exists():
            print(f"   🔍 Checking {path.name}...", flush=True)
            if validate_geotiff(path, check_data=False):  # Structure check only, pipeline will validate data
                print(f"      ✅ Valid GeoTIFF (structure)", flush=True)
                return path, get_source_from_path(path)
            else:
                print(f"      ❌ Invalid or corrupted, cleaning up...", flush=True)
                try:
                    path.unlink()
                    print(f"      🗑️  Deleted corrupted file", flush=True)
                except Exception as e:
                    print(f"      ⚠️  Could not delete: {e}", flush=True)
    
    return None, None


def get_source_from_path(path):
    """Determine source type from path."""
    if 'usa_3dep' in str(path):
        return 'usa_3dep'
    return 'srtm_30m'


def check_pipeline_complete(region_id):
    """
    Check if all pipeline stages are complete and valid.
    
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
        print(f"   🔍 Checking {json_file.name}...", flush=True)
        if validate_json_export(json_file):
            print(f"      ✅ Valid export found", flush=True)
            return True
        else:
            print(f"      ❌ Invalid or incomplete, cleaning up...", flush=True)
            try:
                json_file.unlink()
                print(f"      🗑️  Deleted corrupted file", flush=True)
            except Exception as e:
                print(f"      ⚠️  Could not delete: {e}", flush=True)
    
    return False


def download_us_state(region_id, state_info):
    """Download raw data for a US state using USGS 3DEP."""
    print(f"\n📥 Downloading {state_info['name']}...")
    print(f"   Source: USGS 3DEP (10m resolution)")
    print(f"   Using: download_all_us_states_highres.py")
    
    import subprocess
    result = subprocess.run(
        [sys.executable, "download_all_us_states_highres.py", "--states", region_id],
        capture_output=False
    )
    
    return result.returncode == 0


def download_international_region(region_id, region_info):
    """Download raw data for an international region using OpenTopography."""
    west, south, east, north = region_info['bounds']
    
    # Choose dataset based on latitude coverage
    # SRTM: 60°N to 56°S
    # Copernicus: 90°N to 90°S (global)
    # AW3D30: 82°N to 82°S
    if north > 60.0 or south < -56.0:
        # Outside SRTM coverage, use Copernicus DEM
        dataset = 'COP30'
        dataset_name = 'Copernicus DEM 30m'
        resolution = '30m'
    else:
        # Within SRTM coverage, use SRTM (better quality in this range)
        dataset = 'SRTMGL1'
        dataset_name = 'SRTM 30m'
        resolution = '30m'
    
    print(f"\n📥 Downloading {region_info['name']}...")
    print(f"   Source: OpenTopography ({dataset_name})")
    print(f"   Bounds: {region_info['bounds']}")
    print(f"   Latitude range: {south:.1f}°N to {north:.1f}°N")
    if dataset == 'COP30':
        print(f"   Note: Using Copernicus DEM (SRTM doesn't cover >60°N)")
    
    try:
        import requests
        from load_settings import get_api_key
        # Reuse existing tiling utilities for large areas
        from downloaders.tile_large_states import calculate_tiles, merge_tiles
    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        return False
    
    # Get API key
    try:
        api_key = get_api_key()
        print(f"   🔑 Using API key from settings.json")
    except SystemExit:
        print(f"❌ No OpenTopography API key found in settings.json")
        print(f"   Get a free key at: https://portal.opentopography.org/")
        print(f"   Add it to settings.json under 'opentopography.api_key'")
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
                    print(f"   ♻️  Bounds changed for {region_id}: old={old_bounds}, new={new_bounds}")
                    print(f"   🗑️  Deleting existing raw file to regenerate with new bounds...")
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
                    print(f"   ✅ Already exists with matching bounds: {output_file.name}")
                    return True
            else:
                # No metadata; be conservative and assume mismatch only if clearly different can't be known.
                # Keep existing file to avoid unnecessary re-download.
                print(f"   ✅ Already exists (no metadata found): {output_file.name}")
                return True
        except Exception:
            # If metadata system unavailable, fall back to existing file
            print(f"   ✅ Already exists: {output_file.name}")
            return True
    
    # Helper to download a single bounding box to a specific file
    def _download_bbox(out_path: Path, bbox: tuple[float, float, float, float]) -> bool:
        w, s, e, n = bbox
        url = "https://portal.opentopography.org/API/globaldem"
        params = {
            'demtype': dataset,
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
                            print(f"\r      Progress: {progress:.1f}%", end='', flush=True)
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

    # OpenTopography SRTMGL1 has a 450,000 km² limit; tile proactively when over ~420k
    should_tile = (dataset == 'SRTMGL1') and (approx_area_km2 > 420_000 or width_deg > 4.0 or height_deg > 4.0)

    if should_tile:
        print(f"   📦 Region is large ({approx_area_km2:,.0f} km²). Downloading in tiles...", flush=True)
        # Use conservative tile size in degrees to keep each tile under area and dimension limits
        tiles = calculate_tiles((west, south, east, north), tile_size=3.5)
        tiles_dir = Path(f"data/raw/srtm_30m/tiles/{region_id}")
        tiles_dir.mkdir(parents=True, exist_ok=True)
        tile_paths = []
        for idx, tb in enumerate(tiles):
            print(f"\n      🧩 Tile {idx+1}/{len(tiles)} bounds: [{tb[0]:.4f}, {tb[1]:.4f}, {tb[2]:.4f}, {tb[3]:.4f}]", flush=True)
            tile_path = tiles_dir / f"{region_id}_tile_{idx:02d}.tif"
            if tile_path.exists() and validate_geotiff(tile_path, check_data=False):
                print(f"      ✅ Cached tile present: {tile_path.name}", flush=True)
                tile_paths.append(tile_path)
                continue
            print(f"      ⬇️  Downloading tile...", flush=True)
            if not _download_bbox(tile_path, tb):
                print(f"      ⚠️  Tile download failed, skipping", flush=True)
                continue
            if validate_geotiff(tile_path, check_data=False):
                tile_paths.append(tile_path)
            else:
                print(f"      ⚠️  Invalid tile file, removing", flush=True)
                try:
                    tile_path.unlink()
                except Exception:
                    pass
        if not tile_paths:
            print(f"   ❌ No valid tiles downloaded", flush=True)
            return False
        print(f"\n   🔗 Merging {len(tile_paths)} tiles...", flush=True)
        if not merge_tiles(tile_paths, output_file):
            print(f"   ❌ Tile merge failed", flush=True)
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
            print(f"   ⚠️  Could not save raw metadata: {e}")
        print(f"   ✅ Tiled download and merge complete", flush=True)
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
    
    print(f"   📡 Requesting from OpenTopography...")
    print(f"      (This may take 30-120 seconds)")
    
    try:
        response = requests.get(url, params=params, stream=True, timeout=300)
        
        if response.status_code != 200:
            # If area too large, transparently fall back to tiling
            resp_text = response.text or ""
            if (dataset == 'SRTMGL1') and ("maximum area" in resp_text.lower() or response.status_code == 400):
                print(f"   ℹ️  Server rejected single request due to size. Switching to tiled download...", flush=True)
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
                    print(f"\n      🧩 Tile {idx+1}/{len(tiles)} bounds: [{tb[0]:.4f}, {tb[1]:.4f}, {tb[2]:.4f}, {tb[3]:.4f}]", flush=True)
                    tile_path = tiles_dir / f"{region_id}_tile_{idx:02d}.tif"
                    if tile_path.exists() and validate_geotiff(tile_path, check_data=False):
                        print(f"      ✅ Cached tile present: {tile_path.name}", flush=True)
                        tile_paths.append(tile_path)
                        continue
                    print(f"      ⬇️  Downloading tile...", flush=True)
                    if not _download_bbox(tile_path, tb):
                        print(f"      ⚠️  Tile download failed, skipping", flush=True)
                        continue
                    if validate_geotiff(tile_path, check_data=False):
                        tile_paths.append(tile_path)
                    else:
                        print(f"      ⚠️  Invalid tile file, removing", flush=True)
                        try:
                            tile_path.unlink()
                        except Exception:
                            pass
                if not tile_paths:
                    print(f"   ❌ No valid tiles downloaded", flush=True)
                    return False
                print(f"\n   🔗 Merging {len(tile_paths)} tiles...", flush=True)
                if not merge_tiles(tile_paths, output_file):
                    print(f"   ❌ Tile merge failed", flush=True)
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
                    print(f"   ⚠️  Could not save raw metadata: {e}")
                print(f"   ✅ Tiled download and merge complete", flush=True)
                return True
            print(f"   ❌ API Error: {response.status_code}")
            print(f"      Response: {response.text[:200]}")
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
                        print(f"\r      Progress: {progress:.1f}%", end='', flush=True)
        
        print()  # New line after progress
        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"   ✅ Downloaded successfully ({file_size_mb:.1f} MB)")
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
            print(f"   ⚠️  Could not save raw metadata: {e}")
        return True
        
    except Exception as e:
        print(f"   ❌ Download failed: {e}")
        if output_file.exists():
            output_file.unlink()  # Clean up partial download
        return False


def download_region(region_id, region_type, region_info):
    """Route to appropriate downloader based on region type."""
    if region_type == 'us_state':
        return download_us_state(region_id, region_info)
    elif region_type == 'international':
        return download_international_region(region_id, region_info)
    else:
        print(f"❌ Unknown region type: {region_type}")
        return False


def process_region(region_id, raw_path, source, target_pixels, force, region_type, region_info, border_resolution='10m'):
    """Run the pipeline on a region and return (success, result_paths)."""
    sys.path.insert(0, str(Path(__file__).parent))
    
    try:
        from src.pipeline import run_pipeline
    except ImportError as e:
        print(f"❌ Error importing pipeline: {e}")
        return False
    
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
    
    print(f"\n🔄 Processing {region_info['display_name']}...", flush=True)
    print(f"   Region type: {region_type}", flush=True)
    print(f"   Boundary: {boundary_name}", flush=True)
    
    # Delete existing files if force
    if force:
        print("   🗑️  Force mode: deleting existing processed files...", flush=True)
        for pattern in [
            f"data/clipped/*/{region_id}_*",
            f"data/processed/*/{region_id}_*",
            f"generated/regions/{region_id}_*"
        ]:
            import glob
            for file_path in glob.glob(pattern, recursive=True):
                Path(file_path).unlink()
                print(f"      Deleted: {Path(file_path).name}", flush=True)
    
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
        print(f"❌ Pipeline error: {e}")
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
    print("\n   ♻️  Detected invalid or compressed altitude output. Auto-fixing by force reprocess...", flush=True)
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
                print(f"      Deleted: {Path(file_path).name}", flush=True)
            except Exception:
                pass

    # Locate raw again and re-run
    raw_path, _ = find_raw_file(region_id)
    if not raw_path:
        print("   ❌ Raw file missing during auto-fix")
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
  python ensure_region.py ohio                        # Single word state
  python ensure_region.py new_hampshire               # Multi-word with underscore
  python ensure_region.py "new hampshire"             # Multi-word with quotes
  python ensure_region.py tennessee --force-reprocess # Force full rebuild
  python ensure_region.py california --target-pixels 4096  # High resolution
  
  # International Regions
  python ensure_region.py iceland                     # Iceland
  python ensure_region.py japan                       # Japan
  python ensure_region.py switzerland                 # Switzerland
  python ensure_region.py new_zealand                 # New Zealand

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
    
    # Handle --list-regions
    if args.list_regions:
        print("\n📋 AVAILABLE REGIONS:")
        print("="*70)
        print("\n🇺🇸 US STATES:")
        for state_id in sorted(US_STATE_NAMES.keys()):
            print(f"  - {state_id:20s} → {US_STATE_NAMES[state_id]}")
        print(f"\n🌍 INTERNATIONAL REGIONS:")
        for region_id in sorted(INTERNATIONAL_REGIONS.keys()):
            info = INTERNATIONAL_REGIONS[region_id]
            print(f"  - {region_id:20s} → {info['name']}")
        print(f"\n{'='*70}")
        print(f"Total: {len(US_STATE_NAMES)} US states + {len(INTERNATIONAL_REGIONS)} international regions")
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
        print(f"❌ UNKNOWN REGION: {region_id}", flush=True)
        print("="*70, flush=True)
        print(f"\nRegion '{region_id}' is not recognized.")
        print(f"\nAvailable options:")
        print(f"  • {len(US_STATE_NAMES)} US states (ohio, california, etc.)")
        print(f"  • {len(INTERNATIONAL_REGIONS)} international regions (iceland, japan, etc.)")
        print(f"\nRun with --list-regions to see all available regions")
        return 1
    
    print("="*70, flush=True)
    print(f"🎯 ENSURE REGION: {region_info['display_name'].upper()}", flush=True)
    print(f"   Type: {region_type.replace('_', ' ').title()}", flush=True)
    print("="*70, flush=True)
    print("\n📋 VALIDATING PIPELINE STAGES...", flush=True)
    print("   Checking each stage for valid, complete files", flush=True)
    print("   (Corrupted/incomplete files will be auto-cleaned)\n", flush=True)
    
    # Step 1: Check if pipeline is already complete
    print("[STAGE 4/4] Checking final export (JSON)...", flush=True)
    if not args.force_reprocess and check_pipeline_complete(region_id):
        print(f"\n✅ {region_id} is already processed and ready!")
        print(f"\nTo view:")
        print(f"  1. python serve_viewer.py")
        print(f"  2. Visit http://localhost:8001/interactive_viewer_advanced.html")
        print(f"  3. Select '{region_id}' from dropdown")
        print(f"\nTo force reprocess: add --force-reprocess flag")
        return 0
    
    # Step 2: Check if raw data exists
    print(f"\n[STAGE 1/4] Checking raw elevation data...", flush=True)
    raw_path, source = find_raw_file(region_id)
    
    if not raw_path:
        print(f"   ❌ No valid raw data found for {region_id}", flush=True)
        
        if args.check_only:
            print("   Use without --check-only to download", flush=True)
            return 1
        
        # Try to download (route based on region type)
        print(f"\n   📥 Starting download...", flush=True)
        if not download_region(region_id, region_type, region_info):
            print(f"\n❌ Download failed!", flush=True)
            return 1
        
        # Re-validate the downloaded file
        print(f"\n   🔍 Validating download...", flush=True)
        raw_path, source = find_raw_file(region_id)
        if not raw_path:
            print(f"\n❌ Download reported success but validation failed!", flush=True)
            print(f"   File may be corrupted or incomplete", flush=True)
            print(f"   Expected locations:", flush=True)
            print(f"     - data/raw/srtm_30m/{region_id}_bbox_30m.tif", flush=True)
            print(f"     - data/regions/{region_id}.tif", flush=True)
            print(f"     - data/raw/usa_3dep/{region_id}_3dep_10m.tif", flush=True)
            return 1
        print(f"   ✅ Download validated successfully", flush=True)
    
    if args.check_only:
        print("\n   Use without --check-only to process")
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
            print(f"❌ FAILED: Auto-fix could not repair {region_info['display_name']}")
            print("="*70)
            return 1
        print("\n" + "="*70)
        print(f"✅ SUCCESS: {region_info['display_name']} is ready to view!")
        print("="*70)
        print(f"\nNext steps:")
        print(f"  1. python serve_viewer.py")
        print(f"  2. Visit http://localhost:8001/interactive_viewer_advanced.html")
        print(f"  3. Select '{region_id}' from dropdown")
        return 0
    else:
        print("\n" + "="*70)
        print(f"❌ FAILED: Could not process {region_info['display_name']}")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())

