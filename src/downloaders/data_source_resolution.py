"""
Data source resolution logic for altitude-maps project.

This module contains pure decision logic for determining which data source to use.
It has NO side effects (no file I/O, no downloads, no prints) - just returns decisions.

This separation enables comprehensive unit testing of all scenarios without touching
files or network, and keeps the decision logic isolated and testable.
"""

from pathlib import Path
from typing import Tuple, Dict, Optional, List
from dataclasses import dataclass


@dataclass
class DataSourceDecision:
    """Result of data source resolution logic."""
    action: str  # "USE_LOCAL", "DOWNLOAD", "ERROR_NEED_MANUAL", "ERROR_INSUFFICIENT"
    resolution: int  # Resolution in meters (10, 30, 90)
    source_type: str  # "local", "download", "manual"
    file_path: Optional[Path]  # Path if using local, None if downloading
    message: str  # Human-readable explanation
    download_dataset: Optional[str] = None  # Dataset code if downloading (SRTMGL1, etc.)


def determine_data_source(
    region_id: str,
    min_required_resolution: int,
    available_downloads: List[int],
    local_cache: Dict[int, Path],
    accept_lower_quality: bool = False,
    latitude_range: Optional[Tuple[float, float]] = None
) -> DataSourceDecision:
    """
    Determine which data source to use for a region.
    
    Pure decision logic with NO side effects. Can be tested without file I/O or network.
    
    Rules (in priority order):
    1. Check local cache for exact match or better resolution
    2. Check if required resolution can be downloaded automatically
    3. If 10m needed but not automated, guide user to manual download
    4. If insufficient resolution, error unless accept_lower_quality
    
    Args:
        region_id: Region identifier (for error messages)
        min_required_resolution: Minimum resolution needed (from Nyquist calculation)
        available_downloads: List of resolutions available for download [10, 30, 90] or [30, 90]
        local_cache: Dict of {resolution: file_path} for locally available data
        accept_lower_quality: Whether to allow lower quality than Nyquist requires
        latitude_range: (south, north) for determining COP vs SRTM dataset
        
    Returns:
        DataSourceDecision with action and details
    """
    # Rule 1: Check local cache for data that meets requirements
    # Any resolution <= min_required is acceptable (finer or equal to requirement)
    for res in sorted(local_cache.keys()):
        if res <= min_required_resolution:
            return DataSourceDecision(
                action="USE_LOCAL",
                resolution=res,
                source_type="local",
                file_path=local_cache[res],
                message=f"Using local {res}m data (meets {min_required_resolution}m requirement)"
            )
    
    # Rule 2: No suitable local data - determine if we can download what we need
    # Find all resolutions that meet requirement (resolution <= min_required)
    # Pick COARSEST that meets requirement (minimizes download size)
    downloadable = [r for r in sorted(available_downloads) if r <= min_required_resolution]
    
    if downloadable:
        # Pick coarsest resolution that meets requirement (minimize download)
        # All resolutions in available_downloads are now automated (including 10m for US regions)
        best_resolution = max(downloadable)  # Coarsest (largest) that still meets requirement
        dataset = _determine_dataset_code(best_resolution, latitude_range)
        return DataSourceDecision(
            action="DOWNLOAD",
            resolution=best_resolution,
            source_type="download",
            file_path=None,
            message=f"Downloading {best_resolution}m data (meets {min_required_resolution}m requirement)",
            download_dataset=dataset
        )
    
    # Rule 4: Can't meet requirement with available downloads
    best_available = min(available_downloads) if available_downloads else None
    
    if not best_available:
        return DataSourceDecision(
            action="ERROR_INSUFFICIENT",
            resolution=min_required_resolution,
            source_type="none",
            file_path=None,
            message=f"No data sources available for region {region_id}"
        )
    
    if accept_lower_quality:
        # User accepted lower quality - download best available
        dataset = _determine_dataset_code(best_available, latitude_range)
        return DataSourceDecision(
            action="DOWNLOAD",
            resolution=best_available,
            source_type="download",
            file_path=None,
            message=(
                f"Downloading {best_available}m (accepted lower quality; "
                f"requirement was {min_required_resolution}m)"
            ),
            download_dataset=dataset
        )
    
    # Insufficient resolution and user hasn't accepted lower quality
    return DataSourceDecision(
        action="ERROR_INSUFFICIENT",
        resolution=min_required_resolution,
        source_type="none",
        file_path=None,
        message=(
            f"Region requires {min_required_resolution}m resolution. "
            f"Best available: {best_available}m. "
            f"Use --accept-lower-quality flag to proceed with lower resolution."
        )
    )


def _determine_dataset_code(resolution: int, latitude_range: Optional[Tuple[float, float]]) -> str:
    """
    Determine dataset code based on resolution and latitude.
    
    Args:
        resolution: Resolution in meters (10, 30, or 90)
        latitude_range: (south, north) in degrees, or None
        
    Returns:
        Dataset code: USA_3DEP, SRTMGL1, SRTMGL3, COP30, or COP90
    """
    # 10m is US-only via USGS 3DEP API
    if resolution == 10:
        return 'USA_3DEP'
    
    if latitude_range:
        south, north = latitude_range
        # Check if region extends beyond SRTM coverage (60N to 56S)
        needs_copernicus = north > 60.0 or south < -56.0
    else:
        needs_copernicus = False
    
    if resolution == 90:
        return 'COP90' if needs_copernicus else 'SRTMGL3'
    elif resolution == 30:
        return 'COP30' if needs_copernicus else 'SRTMGL1'
    else:
        # Default to 30m SRTM for unknown resolutions
        return 'SRTMGL1'

