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
        available_resolutions: List of available resolutions in meters (e.g., [10, 30, 90])
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


def download_elevation_data(region_id: str, region_info: Dict, dataset_override: str | None = None, target_pixels: int = 2048) -> bool:
    """
    Download elevation data for any region (US or international).
    
    Routes to appropriate downloader based on dataset_override:
    - 'USA_3DEP': 10m USGS data (automated via USGS National Map API)
    - 'SRTMGL1': 30m SRTM data (automated via OpenTopography)
    - 'SRTMGL3': 90m SRTM data (automated via OpenTopography)
    - 'COP30': 30m Copernicus DEM (automated via OpenTopography)
    - 'COP90': 90m Copernicus DEM (automated via OpenTopography)
    
    UNIFIED ARCHITECTURE (see tech/GRID_ALIGNMENT_STRATEGY.md):
    - ALL resolutions use 1x1 degree tile system
    - NO special cases for small vs large regions
    - Maximum tile reuse across adjacent regions
    - Consistent folder structure: data/raw/{source}/tiles/
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
        return download_usgs_3dep_10m_tiles(region_id, bounds, output_path)
    
    # Route based on dataset/resolution
    if dataset_override in ('SRTMGL3', 'COP90'):
        # 90m resolution
        source_name = 'SRTM 90m' if dataset_override == 'SRTMGL3' else 'Copernicus DEM 90m'
        print(f"  Source: {source_name} (resolution sufficient for region size)")
        print(f"  {size_msg}")
        filename = merged_filename_from_region(region_id, bounds, '90m') + '.tif'
        output_path = Path(f"data/merged/srtm_90m/{filename}")
        
        # Always use unified 1-degree tile system
        return download_and_merge_tiles(region_id, bounds, output_path, source='srtm_90m')
    
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
        
        # Always use unified 1-degree tile system
        return download_and_merge_tiles(region_id, bounds, output_path, source='srtm_30m')
    
    else:
        print(f"  ERROR: Unknown dataset '{dataset_override}'")
        return False


def download_region(region_id: str, region_type: 'RegionType', region_info: Dict, dataset_override: str | None = None, target_pixels: int = 2048) -> bool:
    """
    Route to unified downloader for any region.
    
    This is a simple pass-through that maintains backward compatibility.
    The real work is done by download_elevation_data() which handles all regions uniformly.
    """
    return download_elevation_data(region_id, region_info, dataset_override, target_pixels)


def determine_dataset_override(region_id: str, region_type: 'RegionType', region_info: dict, target_pixels: int = 2048) -> str | None:
    """
    Stage 2/3: Determine dataset to use for download (including resolution).
    
    CRITICAL ENFORCEMENT (see tech/DATA_PIPELINE.md - Section "Determine Dataset"):
    - Uses RegionType enum (never string literals)
    - Resolution determined first via Nyquist rule (Stage 2)
    - Dataset selection is OUTPUT of resolution determination, not input
    - US states: 10m, 30m, or 90m (dynamic based on target_pixels)
    - International: 30m or 90m (dynamic based on target_pixels)
    
    Returns a short code: 'SRTMGL1', 'SRTMGL3', 'COP30', 'COP90', or 'USA_3DEP'.
    """
    from src.types import RegionType
    
    # Calculate visible pixel size for resolution determination
    visible = calculate_visible_pixel_size(region_info['bounds'], target_pixels)
    
    # CANONICAL REFERENCE: tech/DATA_PIPELINE.md - Stage 2 & 3
    if region_type == RegionType.USA_STATE:
        # US regions: 10m USGS 3DEP now available via automated API, plus 30m/90m via OpenTopography
        try:
            min_required = determine_min_required_resolution(
                visible['avg_m_per_pixel'],
                available_resolutions=[10, 30, 90]
            )
            
            if min_required == 90:
                print(f"[STAGE 2/10] Dataset: SRTM 90m (90m sufficient for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                return 'SRTMGL3'
            elif min_required == 30:
                print(f"[STAGE 2/10] Dataset: SRTM 30m (30m required for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                return 'SRTMGL1'
            else:  # min_required == 10
                print(f"[STAGE 2/10] Dataset: USGS 3DEP 10m (10m required for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                return 'USA_3DEP'
        except ValueError:
            # Region too small for standard resolutions - use finest available (10m for US)
            print(f"[STAGE 2/10] Dataset: USGS 3DEP 10m (region requires high detail)")
            return 'USA_3DEP'

    elif region_type == RegionType.COUNTRY or region_type == RegionType.AREA:
        # International regions - check for explicit override first
        recommended = None
        try:
            entry = ALL_REGIONS.get(region_id)
            if entry and getattr(entry, 'recommended_dataset', None):
                recommended = entry.recommended_dataset
        except Exception:
            recommended = None

        if recommended in ('SRTMGL1', 'SRTMGL3', 'COP30', 'COP90', 'USA_3DEP'):
            print(f"[STAGE 2/10] Dataset override from RegionConfig: {recommended}")
            return recommended

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
        # US AREA regions can use 10m, others are limited to 30m/90m
        available_resolutions = [10, 30, 90] if is_us_region else [30, 90]
        
        try:
            min_required = determine_min_required_resolution(
                visible['avg_m_per_pixel'],
                available_resolutions=available_resolutions
            )
            if min_required == 90:
                print(f"[STAGE 2/10] Dataset: {base_name} 90m (90m sufficient for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                return base_90m
            elif min_required == 30:
                print(f"[STAGE 2/10] Dataset: {base_name} 30m (30m required for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                return base_30m
            else:  # min_required == 10 (only for US regions)
                print(f"[STAGE 2/10] Dataset: USGS 3DEP 10m (10m required for {visible['avg_m_per_pixel']:.0f}m visible pixels)")
                return 'USA_3DEP'
        except ValueError:
            # Region too small for standard resolutions
            if is_us_region:
                print(f"[STAGE 2/10] Dataset: USGS 3DEP 10m (region requires high detail)")
                return 'USA_3DEP'
            else:
                print(f"[STAGE 2/10] Dataset: {base_name} 30m (region requires high detail)")
                return base_30m
    
    else:
        raise ValueError(f"Unknown region type: {region_type}")

