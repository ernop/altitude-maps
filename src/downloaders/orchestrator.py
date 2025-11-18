"""
Download orchestration for altitude-maps project.

This module coordinates download operations for all regions:
- Dataset selection based on latitude, region size, and available sources
- Resolution selection using Nyquist sampling rule
- Automatic tiling for large regions
- Unified download routing to appropriate data sources

Architecture:
1. determine_dataset_override() - Calculate required resolution and dataset
2. download_elevation_data() - Route to appropriate downloader
3. Actual downloaders (opentopography.py, srtm_90m.py) - Execute downloads
"""

from pathlib import Path
from typing import Dict, Tuple, TYPE_CHECKING
import requests
from tqdm import tqdm

from src.regions_config import ALL_REGIONS
from src.tile_geometry import (
    calculate_visible_pixel_size,
    estimate_raw_file_size_mb,
    calculate_1degree_tiles,
    tile_filename_from_bounds,
    merged_filename_from_region
)
from src.tile_manager import download_and_merge_tiles
from load_settings import get_api_key

if TYPE_CHECKING:
    from src.types import RegionType


def _download_opentopography_region(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    output_path: Path,
    dataset: str,
    resolution_str: str
) -> bool:
    """
    Download OpenTopography data using simplified approach:
    - Small regions (< 4 degrees): Direct bounding box download
    - Large regions (>= 4 degrees): Chunk to 4-degree max, then merge
    
    Args:
        region_id: Region identifier
        bounds: (west, south, east, north) in degrees
        output_path: Path for output file
        dataset: Dataset code (SRTMGL1, SRTMGL3, COP30, COP90)
        resolution_str: Resolution string ('30m' or '90m')
        
    Returns:
        True if successful, False otherwise
    """
    from src.downloaders.opentopography import download_srtm, download_copernicus
    from src.pipeline import merge_tiles
    
    west, south, east, north = bounds
    width = east - west
    height = north - south
    
    # OpenTopography max is 4 degrees per dimension
    OPENTOPOGRAPHY_MAX_DEGREES = 4.0
    
    # Check if region fits in single request
    if width <= OPENTOPOGRAPHY_MAX_DEGREES and height <= OPENTOPOGRAPHY_MAX_DEGREES:
        # Small region - download exact bounding box directly
        print(f"  Downloading exact bounding box ({width:.2f}deg x {height:.2f}deg)", flush=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if dataset in ('SRTMGL1', 'SRTMGL3'):
            return download_srtm(region_id, bounds, output_path)
        elif dataset in ('COP30', 'COP90'):
            res = '30m' if dataset == 'COP30' else '90m'
            return download_copernicus(region_id, bounds, output_path, resolution=res)
        else:
            print(f"  ERROR: Unknown dataset {dataset}", flush=True)
            return False
    
    # Large region - chunk to 4-degree max
    print(f"  Region too large ({width:.2f}deg x {height:.2f}deg) - chunking to 4-degree max", flush=True)
    
    import math
    from pathlib import Path
    
    # Calculate chunk grid
    num_chunks_x = math.ceil(width / OPENTOPOGRAPHY_MAX_DEGREES)
    num_chunks_y = math.ceil(height / OPENTOPOGRAPHY_MAX_DEGREES)
    chunk_width = width / num_chunks_x
    chunk_height = height / num_chunks_y
    
    chunk_paths = []
    temp_dir = output_path.parent / "temp_chunks"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"  Downloading {num_chunks_x * num_chunks_y} chunks...", flush=True)
    
    for y in range(num_chunks_y):
        for x in range(num_chunks_x):
            chunk_west = west + (x * chunk_width)
            chunk_east = min(east, chunk_west + chunk_width)
            chunk_south = south + (y * chunk_height)
            chunk_north = min(north, chunk_south + chunk_height)
            
            chunk_bounds = (chunk_west, chunk_south, chunk_east, chunk_north)
            chunk_path = temp_dir / f"chunk_{y}_{x}.tif"
            
            chunk_num = y * num_chunks_x + x + 1
            total_chunks = num_chunks_x * num_chunks_y
            print(f"  [{chunk_num}/{total_chunks}] Chunk ({chunk_east - chunk_west:.2f}deg x {chunk_north - chunk_south:.2f}deg)", flush=True)
            
            # Download chunk
            if dataset in ('SRTMGL1', 'SRTMGL3'):
                success = download_srtm(f"{region_id}_chunk_{y}_{x}", chunk_bounds, chunk_path)
            elif dataset in ('COP30', 'COP90'):
                res = '30m' if dataset == 'COP30' else '90m'
                success = download_copernicus(f"{region_id}_chunk_{y}_{x}", chunk_bounds, chunk_path, resolution=res)
            else:
                print(f"  ERROR: Unknown dataset {dataset}", flush=True)
                return False
            
            if not success:
                print(f"  ERROR: Failed to download chunk {chunk_num}", flush=True)
                # Clean up partial chunks
                for p in chunk_paths:
                    if p.exists():
                        p.unlink()
                return False
            
            chunk_paths.append(chunk_path)
    
    # Merge chunks
    print(f"  Merging {len(chunk_paths)} chunks...", flush=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    success = merge_tiles(chunk_paths, output_path)
    
    # Clean up temp chunks
    for chunk_path in chunk_paths:
        if chunk_path.exists():
            chunk_path.unlink()
    if temp_dir.exists():
        try:
            temp_dir.rmdir()
        except:
            pass
    
    if success:
        merged_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  Merged file: {output_path.name} ({merged_size_mb:.2f} MB)", flush=True)
    
    return success


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


def determine_min_required_resolution(
    visible_m_per_pixel: float, 
    available_resolutions: list[int] = None,
    allow_lower_quality: bool = False
) -> int:
    """
    Determine minimum required source resolution based on visible pixel size.
    
    CRITICAL ENFORCEMENT (see tech/DATA_PIPELINE.md - Section "Determine Required Resolution"):
    - Resolution is NEVER hardcoded by region type
    - Uses Nyquist sampling theorem (2x oversampling minimum)
    - Returns coarsest available resolution that meets requirement
    
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
    
    Args:
        visible_m_per_pixel: Average meters per pixel in final output
        available_resolutions: List of available resolutions in meters (e.g., [10, 30, 90, 250, 500, 1000])
                              If None, defaults to [30, 90] (international standard)
        allow_lower_quality: If True, return best available resolution even if it
                            doesn't meet Nyquist requirement. If False, raise ValueError.
        
    Returns:
        Minimum required resolution in meters that meets Nyquist rule
        
    Raises:
        ValueError: If no resolution meets the 2.0x Nyquist requirement
                   and allow_lower_quality is False
    """
    # Default to international resolutions if not specified
    if available_resolutions is None:
        available_resolutions = [30, 90]
    
    # Sort resolutions from finest to coarsest
    available_resolutions = sorted(available_resolutions)
    
    # Check for native resolution display first (0.8x to 1.2x = essentially 1:1)
    # At native resolution, there's no downsampling, so no aliasing risk
    # This handles cases like 10.1m visible pixels with 10m source
    NATIVE_MIN = 0.8
    NATIVE_MAX = 1.2
    
    for resolution in available_resolutions:
        oversampling = visible_m_per_pixel / resolution
        if NATIVE_MIN <= oversampling <= NATIVE_MAX:
            # Native resolution display - no downsampling, no aliasing
            return resolution
    
    # Not at native resolution - apply Nyquist rule for downsampling
    # Minimum requirement: 2.0x oversampling (Nyquist criterion)
    MIN_OVERSAMPLING = 2.0
    
    # Check each resolution from coarsest to finest
    # We want the coarsest resolution that still meets requirements (minimizes download size)
    for resolution in reversed(available_resolutions):
        oversampling = visible_m_per_pixel / resolution
        if oversampling >= MIN_OVERSAMPLING:
            # This resolution provides sufficient oversampling for downsampling
            return resolution
    
    # No resolution meets the Nyquist requirement
    # Calculate what each would provide
    oversampling_info = {res: visible_m_per_pixel / res for res in available_resolutions}
    best_resolution = min(available_resolutions)  # Finest available
    best_oversampling = oversampling_info[best_resolution]
    
    if allow_lower_quality:
        # User accepted lower quality - return finest available
        return best_resolution
    
    # Build helpful error message
    oversampling_str = ", ".join(
        f"{res}m gives {oversampling_info[res]:.2f}x" 
        for res in available_resolutions
    )
    
    raise ValueError(
        f"Region requires higher resolution than available. "
        f"Visible pixels: {format_pixel_size(visible_m_per_pixel)}/pixel. "
        f"Available sources: {oversampling_str} "
        f"(need >={MIN_OVERSAMPLING}x for Nyquist). "
        f"Consider using a higher target_pixels value (fewer output pixels = larger visible pixels)."
    )


def download_elevation_data(region_id: str, region_info: Dict, dataset_override: str | None = None, target_pixels: int = None) -> bool:
    """
    Download elevation data for any region (US or international).
    
    Routes to appropriate downloader based on dataset_override:
    - 'USA_3DEP': 10m USGS data (automated via USGS National Map API)
    - 'SRTMGL1': 30m SRTM data (automated via OpenTopography)
    - 'SRTMGL3': 90m SRTM data (automated via OpenTopography)
    - 'COP30': 30m Copernicus DEM (automated via OpenTopography)
    - 'COP90': 90m Copernicus DEM (automated via OpenTopography)
    - 'GMTED2010_250M': 250m GMTED2010 (supports pre-downloaded files)
    - 'GMTED2010_500M': 500m GMTED2010 (supports pre-downloaded files)
    - 'GMTED2010_1KM': 1000m GMTED2010 (supports pre-downloaded files)
    
    UNIFIED ARCHITECTURE:
    - ALL resolutions use 1x1 degree tile system for organization
    - NO special cases for small vs large regions
    - Region-specific downloads (no tile reuse - fresh data at required resolution)
    - Consistent folder structure: data/raw/{source}/tiles/ (kept for reference)
    """
    print(f"\n  Downloading {region_info['name']}...")
    
    bounds = region_info['bounds']
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    
    # Size info for user feedback
    if width > 4.0 or height > 4.0:
        size_msg = f"Large region ({width:.1f}deg x {height:.1f}deg) - downloading tiles"
    else:
        size_msg = f"Region ({width:.1f}deg x {height:.1f}deg) - using 1-degree tile system"
    
    # Handle 10m USGS 3DEP request (USA regions only)
    if dataset_override == 'USA_3DEP':
        from src.downloaders.usgs_3dep_10m import download_usgs_3dep_10m_tiles
        
        print(f"  Source: USGS 3DEP 10m (high-resolution US data)")
        print(f"  {size_msg}")
        filename = merged_filename_from_region(region_id, bounds, '10m') + '.tif'
        output_path = Path(f"data/merged/usa_3dep/{filename}")
        
        # Always use unified 1-degree tile system
        # Pass target_pixels so downloader can calculate appropriate download resolution
        return download_usgs_3dep_10m_tiles(region_id, bounds, output_path, target_pixels=target_pixels)
    
    # Route based on dataset/resolution
    if dataset_override in ('GMTED2010_1KM', 'GMTED2010_500M', 'GMTED2010_250M'):
        # GMTED2010 coarse resolutions (250m, 500m, 1km)
        res_map = {'GMTED2010_1KM': '1000m', 'GMTED2010_500M': '500m', 'GMTED2010_250M': '250m'}
        resolution_str = res_map.get(dataset_override, '1000m')
        resolution_m = int(resolution_str.replace('m', ''))
        print(f"  Source: GMTED2010 {resolution_str} (coarse resolution for large regions)")
        print(f"  {size_msg}")
        filename = merged_filename_from_region(region_id, bounds, resolution_str) + '.tif'
        output_path = Path(f"data/merged/gmted2010_{resolution_str}/{filename}")
        
        # Use GMTED2010 downloader (supports pre-downloaded files)
        from src.downloaders.gmted2010 import download_gmted2010_tiles
        tiles_dir = Path(f"data/raw/gmted2010_{resolution_str}/tiles")
        tiles_dir.mkdir(parents=True, exist_ok=True)
        tile_paths = download_gmted2010_tiles(region_id, bounds, resolution_m, tiles_dir)
        
        if not tile_paths:
            print(f"  ERROR: No GMTED2010 {resolution_str} tiles available")
            print(f"  NOTE: GMTED2010 downloader not yet fully implemented")
            print(f"  You can manually download tiles from USGS EarthExplorer and place them in: {tiles_dir}")
            return False
        
        # Merge tiles
        from src.pipeline import merge_tiles
        return merge_tiles(tile_paths, output_path)
    
    elif dataset_override in ('SRTMGL3', 'COP90'):
        # 90m resolution
        source_name = 'SRTM 90m' if dataset_override == 'SRTMGL3' else 'Copernicus DEM 90m'
        print(f"  Source: {source_name} (resolution sufficient for region size)")
        print(f"  {size_msg}")
        filename = merged_filename_from_region(region_id, bounds, '90m') + '.tif'
        output_path = Path(f"data/merged/srtm_90m/{filename}")
        
        # Simplified: Use direct bounding box download for small regions, chunk for large
        return _download_opentopography_region(region_id, bounds, output_path, dataset_override, '90m')
    
    elif dataset_override in ('SRTMGL1', 'COP30', None):
        # 30m resolution (SRTMGL1, COP30, or default)
        if dataset_override == 'COP30':
            source_name = 'Copernicus DEM 30m'
        else:
            source_name = 'SRTM 30m'
        print(f"  Source: {source_name}")
        print(f"  {size_msg}")
        filename = merged_filename_from_region(region_id, bounds, '30m') + '.tif'
        output_path = Path(f"data/merged/srtm_30m/{filename}")
        
        # Simplified: Use direct bounding box download for small regions, chunk for large
        return _download_opentopography_region(region_id, bounds, output_path, dataset_override or 'SRTMGL1', '30m')
    
    else:
        print(f"  ERROR: Unknown dataset '{dataset_override}'")
        return False


def download_region(region_id: str, region_type: 'RegionType', region_info: Dict, dataset_override: str | None = None, target_pixels: int = None) -> bool:
    """
    Route to unified downloader for any region.
    
    This is a simple pass-through that maintains backward compatibility.
    The real work is done by download_elevation_data() which handles all regions uniformly.
    """
    return download_elevation_data(region_id, region_info, dataset_override, target_pixels)


def determine_required_resolution_and_dataset(
    region_id: str,
    region_type: 'RegionType',
    region_info: dict,
    target_pixels: int = None,
    verbose: bool = True
) -> tuple[int, str]:
    """
    Stage 2: Determine required resolution and dataset for download.
    
    CRITICAL FLOW (single source of truth):
    1. Calculate visible pixel size from geographic bounds + target_pixels
    2. Apply Nyquist rule to determine minimum required source resolution
    3. Select dataset code based on resolution and region type
    
    This function ensures we don't over-download:
    - If final output needs 200m/pixel → selects 90m source (not 10m)
    - If final output needs 15m/pixel → selects 10m source (if available)
    
    Args:
        region_id: Region identifier
        region_type: RegionType enum value
        region_info: Dict with 'bounds' key (west, south, east, north)
        target_pixels: Target output dimension (default: from src.config.DEFAULT_TARGET_PIXELS)
        
    Returns:
        Tuple of (required_resolution_meters, dataset_code)
        - required_resolution_meters: 10, 30, 90, 250, 500, or 1000
        - dataset_code: 'USA_3DEP', 'SRTMGL1', 'SRTMGL3', 'COP30', 'COP90', 'GMTED2010_250M', 'GMTED2010_500M', or 'GMTED2010_1KM'
    """
    from src.config import DEFAULT_TARGET_PIXELS
    if target_pixels is None:
        target_pixels = DEFAULT_TARGET_PIXELS
    
    from src.types import RegionType
    
    # STEP 1: Calculate visible pixel size from geographic bounds + target_pixels
    # This determines what resolution we'll have in the final output
    visible = calculate_visible_pixel_size(region_info['bounds'], target_pixels)
    
    # STEP 2: Determine minimum required source resolution using Nyquist rule
    # This ensures we don't over-download (selects coarsest that meets requirement)
    
    # CANONICAL REFERENCE: tech/DATA_PIPELINE.md - Stage 2 & 3
    if region_type == RegionType.USA_STATE:
        # US regions: Full range from 10m (USGS 3DEP) to 1km (GMTED2010) for optimal selection
        # TEMPORARY: Restricting to 10m, 30m, 90m only (250m, 500m, 1000m GMTED2010 disabled)
        # Available: 10m, 30m, 90m (normally: 10m, 30m, 90m, 250m, 500m, 1000m)
        try:
            min_required = determine_min_required_resolution(
                visible['avg_m_per_pixel'],
                available_resolutions=[10, 30, 90]  # TEMPORARY: Restricted from [10, 30, 90, 250, 500, 1000]
            )
            
            # Map resolution to dataset code
            if min_required == 1000:
                if verbose:
                    print(f"[STAGE 2/10] Resolution: 1000m (sufficient for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                    print(f"[STAGE 2/10] Dataset: GMTED2010 1km")
                return (1000, 'GMTED2010_1KM')
            elif min_required == 500:
                if verbose:
                    print(f"[STAGE 2/10] Resolution: 500m (sufficient for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                    print(f"[STAGE 2/10] Dataset: GMTED2010 500m")
                return (500, 'GMTED2010_500M')
            elif min_required == 250:
                if verbose:
                    print(f"[STAGE 2/10] Resolution: 250m (sufficient for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                    print(f"[STAGE 2/10] Dataset: GMTED2010 250m")
                return (250, 'GMTED2010_250M')
            elif min_required == 90:
                if verbose:
                    print(f"[STAGE 2/10] Resolution: 90m (sufficient for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                    print(f"[STAGE 2/10] Dataset: SRTM 90m")
                return (90, 'SRTMGL3')
            elif min_required == 30:
                if verbose:
                    print(f"[STAGE 2/10] Resolution: 30m (required for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                    print(f"[STAGE 2/10] Dataset: SRTM 30m")
                return (30, 'SRTMGL1')
            else:  # min_required == 10
                if verbose:
                    print(f"[STAGE 2/10] Resolution: 10m (required for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                    print(f"[STAGE 2/10] Dataset: USGS 3DEP 10m")
                return (10, 'USA_3DEP')
        except ValueError:
            # Region too small for standard resolutions - use finest available (10m for US)
            if verbose:
                print(f"[STAGE 2/10] Resolution: 10m (region requires high detail)")
                print(f"[STAGE 2/10] Dataset: USGS 3DEP 10m")
            return (10, 'USA_3DEP')

    elif region_type == RegionType.COUNTRY or region_type == RegionType.AREA:
        # International regions - check for explicit override first
        recommended = None
        try:
            entry = ALL_REGIONS.get(region_id)
            if entry and getattr(entry, 'recommended_dataset', None):
                recommended = entry.recommended_dataset
        except Exception:
            recommended = None

        if recommended in ('SRTMGL1', 'SRTMGL3', 'COP30', 'COP90', 'USA_3DEP', 'GMTED2010_250M', 'GMTED2010_500M', 'GMTED2010_1KM'):
            # Extract resolution from dataset code
            res_map = {
                'SRTMGL1': 30, 'SRTMGL3': 90, 'COP30': 30, 'COP90': 90, 'USA_3DEP': 10,
                'GMTED2010_250M': 250, 'GMTED2010_500M': 500, 'GMTED2010_1KM': 1000
            }
            res = res_map.get(recommended, 30)
            if verbose:
                print(f"[STAGE 2/10] Resolution: {res}m (override from RegionConfig)")
                print(f"[STAGE 2/10] Dataset: {recommended}")
            return (res, recommended)

        # Check if AREA region is in the US (can use USGS 3DEP 10m)
        is_us_region = False
        if region_type == RegionType.AREA:
            try:
                entry = ALL_REGIONS.get(region_id)
                if entry and entry.country == "United States of America":
                    is_us_region = True
            except Exception:
                pass

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
        
        # Calculate minimum required resolution
        # TEMPORARY: Restricting to 10m, 30m, 90m only (250m, 500m, 1000m GMTED2010 disabled)
        # US AREA regions: 10m-90m range (normally: 10m-1km), international: 30m-90m range (normally: 30m-1km)
        available_resolutions = [10, 30, 90] if is_us_region else [30, 90]  # TEMPORARY: Restricted from [10, 30, 90, 250, 500, 1000] / [30, 90, 250, 500, 1000]
        
        try:
            min_required = determine_min_required_resolution(
                visible['avg_m_per_pixel'],
                available_resolutions=available_resolutions
            )
            # Map resolution to dataset code
            if min_required == 1000:
                if verbose:
                    print(f"[STAGE 2/10] Resolution: 1000m (sufficient for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                    print(f"[STAGE 2/10] Dataset: GMTED2010 1km")
                return (1000, 'GMTED2010_1KM')
            elif min_required == 500:
                if verbose:
                    print(f"[STAGE 2/10] Resolution: 500m (sufficient for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                    print(f"[STAGE 2/10] Dataset: GMTED2010 500m")
                return (500, 'GMTED2010_500M')
            elif min_required == 250:
                if verbose:
                    print(f"[STAGE 2/10] Resolution: 250m (sufficient for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                    print(f"[STAGE 2/10] Dataset: GMTED2010 250m")
                return (250, 'GMTED2010_250M')
            elif min_required == 90:
                if verbose:
                    print(f"[STAGE 2/10] Resolution: 90m (sufficient for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                    print(f"[STAGE 2/10] Dataset: {base_name} 90m")
                return (90, base_90m)
            elif min_required == 30:
                if verbose:
                    print(f"[STAGE 2/10] Resolution: 30m (required for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                    print(f"[STAGE 2/10] Dataset: {base_name} 30m")
                return (30, base_30m)
            else:  # min_required == 10 (only for US regions)
                if verbose:
                    print(f"[STAGE 2/10] Resolution: 10m (required for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                    print(f"[STAGE 2/10] Dataset: USGS 3DEP 10m")
                return (10, 'USA_3DEP')
        except ValueError:
            # Region too small for standard resolutions
            if is_us_region:
                if verbose:
                    print(f"[STAGE 2/10] Resolution: 10m (region requires high detail)")
                    print(f"[STAGE 2/10] Dataset: USGS 3DEP 10m")
                return (10, 'USA_3DEP')
            else:
                if verbose:
                    print(f"[STAGE 2/10] Resolution: 30m (region requires high detail)")
                    print(f"[STAGE 2/10] Dataset: {base_name} 30m")
                return (30, base_30m)
    
    else:
        raise ValueError(f"Unknown region type: {region_type}")


def determine_dataset_override(region_id: str, region_type: 'RegionType', region_info: dict, target_pixels: int = None) -> str | None:
    """
    DEPRECATED: Use determine_required_resolution_and_dataset() instead.
    
    Kept for backward compatibility - returns only dataset code.
    """
    _, dataset_code = determine_required_resolution_and_dataset(region_id, region_type, region_info, target_pixels)
    return dataset_code

