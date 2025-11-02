"""
Download orchestration for altitude-maps project.

This module coordinates download operations for different region types:
- US states: Routes to USGS 3DEP or OpenTopography SRTM
- International regions: OpenTopography with automatic resolution selection

Functions handle:
- Dataset selection based on latitude and region type
- Resolution selection using Nyquist sampling rule
- Tiling for large regions
- Download coordination and error handling
"""

from pathlib import Path
from typing import Dict
import requests
from tqdm import tqdm

from src.regions_config import ALL_REGIONS
from src.tile_geometry import (
    calculate_visible_pixel_size,
    determine_min_required_resolution,
    format_pixel_size,
    estimate_raw_file_size_mb,
    calculate_1degree_tiles,
    tile_filename_from_bounds
)
from src.tile_manager import download_and_merge_tiles
from src.downloaders.opentopography import download_srtm
from src.downloaders.srtm_90m import download_srtm_90m_tiles, download_srtm_90m_single
from src.pipeline import merge_tiles
from load_settings import get_api_key


def download_us_state(region_id: str, state_info: Dict) -> bool:
    """Download raw data for a US state."""
    print(f"\n  Downloading {state_info['name']}...")
    print(f"  Source: USGS 3DEP preferred; automated path uses OpenTopography SRTM 30m")
    
    bounds = state_info['bounds']
    output_path = Path(f"data/merged/srtm_30m/{region_id}_merged_30m.tif")
    
    # Check if state needs tiling
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    needs_tiling = (width > 4.0 or height > 4.0)
    
    if needs_tiling:
        print(f"  Large state ({width:.1f}deg x {height:.1f}deg) - using tile-based download")
        return download_and_merge_tiles(region_id, bounds, output_path, source='srtm_30m')
    else:
        print(f"  Standard download")
        return download_srtm(region_id, bounds, output_path)


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
        
        # Print selection summary
        print(f"\n  Resolution selected: {resolution} ({dataset_name})")
        print(f"  Dataset: {dataset}")
        
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
        # Get API key
        try:
            api_key = get_api_key()
            print(f"  Using API key from settings.json")
        except SystemExit:
            print(f"  No OpenTopography API key found in settings.json")
            print(f"  Get a free key at: https://portal.opentopography.org/")
            print(f"  Add it to settings.json under 'opentopography.api_key'")
            return False

        # Determine source name for output directory
        if resolution == '90m':
            source_name = 'srtm_90m'
        else:
            source_name = 'srtm_30m'
        
        # Check if region needs tiling (>4 degrees in any direction)
        width = east - west
        height = north - south
        needs_tiling = (width > 4.0 or height > 4.0)
        
        if needs_tiling:
            # Use dedicated tile-based downloader based on resolution
            output_file = Path(f"data/merged/{source_name}/{region_id}_merged_{resolution}.tif")
            
            if resolution == '90m':
                # Use dedicated SRTM 90m tile downloader
                return download_srtm_90m_tiles(
                    region_id=region_id,
                    bounds=(west, south, east, north),
                    output_path=output_file,
                    api_key=api_key,
                    dataset=dataset
                )
            else:
                # Use 30m tile downloader (inline for now)
                print(f"\n  Large region ({width:.1f}deg x {height:.1f}deg) - using tile-based download")
                print(f"  Splitting into 1-degree tiles...")
                
                # Calculate tiles
                tiles = calculate_1degree_tiles((west, south, east, north))
                print(f"  Need {len(tiles)} tiles to cover region")
                
                # Create output directory
                raw_dir = Path(f"data/raw/{source_name}/tiles")
                raw_dir.mkdir(parents=True, exist_ok=True)
                
                # Download tiles
                tile_paths = []
                for i, tile_bounds in enumerate(tiles, 1):
                    tile_name = tile_filename_from_bounds(tile_bounds, resolution)
                    tile_path = raw_dir / tile_name
                    
                    if tile_path.exists():
                        print(f"  [{i}/{len(tiles)}] Using cached: {tile_name}")
                        tile_paths.append(tile_path)
                        continue
                    
                    print(f"  [{i}/{len(tiles)}] Downloading: {tile_name}")
                    
                    # Build OpenTopography API request
                    t_west, t_south, t_east, t_north = tile_bounds
                    url = "https://portal.opentopography.org/API/globaldem"
                    params = {
                        'demtype': dataset,
                        'south': t_south,
                        'north': t_north,
                        'west': t_west,
                        'east': t_east,
                        'outputFormat': 'GTiff',
                        'API_Key': api_key
                    }
                    
                    response = requests.get(url, params=params, stream=True, timeout=300)
                    
                    if response.status_code != 200:
                        print(f"  API Error: {response.status_code}")
                        print(f"  Response: {response.text[:200]}")
                        return False
                    
                    # Download with progress
                    total_size = int(response.headers.get('content-length', 0))
                    desc = tile_name[:40] + ('...' if len(tile_name) > 40 else '')
                    with open(tile_path, 'wb') as f, tqdm(
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
                    
                    tile_paths.append(tile_path)
                
                # Merge tiles
                print(f"\n  Merging {len(tile_paths)} tiles...")
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                merge_success = merge_tiles(tile_paths, output_file)
                if not merge_success:
                    print(f"  Merge failed")
                    return False
                
                file_size_mb = output_file.stat().st_size / (1024 * 1024)
                print(f"  Merged successfully: {file_size_mb:.1f} MB")
                
                # Write metadata
                try:
                    from src.metadata import create_raw_metadata, save_metadata, get_metadata_path
                    raw_meta = create_raw_metadata(
                        tif_path=output_file,
                        region_id=region_id,
                        source=source_name,
                        download_url='https://portal.opentopography.org/API/globaldem',
                        download_params={'tiles': len(tiles), 'dataset': dataset}
                    )
                    save_metadata(raw_meta, get_metadata_path(output_file))
                except Exception as e:
                    print(f"  Could not save metadata: {e}")
                
                return True
        
        else:
            # Single download for small regions (< 4deg)
            output_file = Path(f"data/merged/{source_name}/{region_id}_merged_{resolution}.tif")
            
            if resolution == '90m':
                # Use dedicated SRTM 90m single-file downloader
                return download_srtm_90m_single(
                    region_id=region_id,
                    bounds=(west, south, east, north),
                    output_path=output_file,
                    api_key=api_key,
                    dataset=dataset
                )
            else:
                # Use 30m downloader (inline for now)
                print(f"\n  Standard download (region < 4deg)")
                
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Build OpenTopography API request
                url = "https://portal.opentopography.org/API/globaldem"
                params = {
                    'demtype': dataset,
                    'south': south,
                    'north': north,
                    'west': west,
                    'east': east,
                    'outputFormat': 'GTiff',
                    'API_Key': api_key
                }
                
                print(f"  Requesting from OpenTopography API...")
                response = requests.get(url, params=params, stream=True, timeout=300)
                
                if response.status_code != 200:
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
                
                # Write metadata
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
        if 'output_file' in locals() and output_file.exists():
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


def determine_dataset_override(region_id: str, region_type: str, region_info: dict, target_pixels: int = 2048) -> str | None:
    """
    Stage 2/3: Determine dataset to use for download (including resolution).
    - US states: USGS 3DEP (implicit in downloader) -> return 'USA_3DEP'
    - International: Choose by latitude AND resolution requirements:
        * Calculates minimum required resolution (Nyquist rule)
        * Returns SRTMGL3/COP90 if 90m is sufficient
        * Returns SRTMGL1/COP30 if 30m is required
    Returns a short code: 'SRTMGL1', 'SRTMGL3', 'COP30', 'COP90', or 'USA_3DEP'.
    """
    if region_type == 'us_state':
        print("[STAGE 2/10] Dataset: USGS 3DEP 10m (US State)")
        return 'USA_3DEP'

    # International regions - check for explicit override first
    recommended = None
    try:
        entry = ALL_REGIONS.get(region_id)
        if entry and getattr(entry, 'recommended_dataset', None):
            recommended = entry.recommended_dataset
    except Exception:
        recommended = None

    if recommended in ('SRTMGL1', 'SRTMGL3', 'COP30', 'COP90'):
        print(f"[STAGE 2/10] Dataset override from RegionConfig: {recommended}")
        return recommended

    # Auto-select dataset based on latitude and resolution requirements
    _west, south, _east, north = region_info['bounds']
    
    # Determine base dataset by latitude
    if north > 60.0 or south < -56.0:
        base_30m = 'COP30'
        base_90m = 'COP90'
        base_name = 'Copernicus DEM'
    else:
        base_30m = 'SRTMGL1'
        base_90m = 'SRTMGL3'
        base_name = 'SRTM'
    
    # Calculate minimum required resolution based on Nyquist rule
    from src.tile_geometry import calculate_visible_pixel_size
    visible = calculate_visible_pixel_size(region_info['bounds'], target_pixels)
    
    try:
        min_required = determine_min_required_resolution(visible['avg_m_per_pixel'])
        if min_required == 90:
            print(f"[STAGE 2/10] Dataset: {base_name} 90m (90m sufficient for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
            return base_90m
        else:
            print(f"[STAGE 2/10] Dataset: {base_name} 30m (30m required for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
            return base_30m
    except ValueError:
        # Region too small for standard resolutions - default to 30m
        print(f"[STAGE 2/10] Dataset: {base_name} 30m (region requires high detail)")
        return base_30m

