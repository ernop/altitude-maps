"""
Validation utilities to catch data quality issues early.

This module provides safeguards against common data processing errors:
- Aspect ratio distortion from incorrect cropping
- Bounding box issues (too much empty space)
- Non-null data coverage problems
"""
import numpy as np
from typing import Tuple, Optional
import warnings


class AspectRatioError(Exception):
    """Raised when aspect ratio is significantly distorted."""
    pass


class BoundingBoxError(Exception):
    """Raised when bounding box contains too much empty space."""
    pass


class ElevationCorruptionError(Exception):
    """Raised when elevation data appears corrupted (unreasonably small range)."""
    pass


def validate_aspect_ratio(
    width: int,
    height: int,
    bounds_degrees: Tuple[float, float, float, float],
    tolerance: float = 0.3,
    center_latitude: Optional[float] = None
) -> None:
    """
    Validate that raster aspect ratio matches geographic aspect ratio.
    
    This catches the common mistake of using crop=False with state boundaries,
    which creates square-ish rasters for wide states like Tennessee.
    
    Args:
        width: Raster width in pixels
        height: Raster height in pixels
        bounds_degrees: (west, south, east, north) in degrees
        tolerance: Maximum acceptable aspect ratio difference (default 0.3)
        center_latitude: If None, calculates from bounds
        
    Raises:
        AspectRatioError: If aspect ratio is significantly distorted
    """
    west, south, east, north = bounds_degrees
    
    # Calculate geographic aspect ratio (accounting for latitude)
    lon_span = abs(east - west)
    lat_span = abs(north - south)
    
    if center_latitude is None:
        center_latitude = (north + south) / 2.0
    
    # Longitude degrees shrink with latitude
    meters_per_deg_lon = 111_320 * np.cos(np.radians(center_latitude))
    meters_per_deg_lat = 111_320
    
    geo_width = lon_span * meters_per_deg_lon
    geo_height = lat_span * meters_per_deg_lat
    geo_aspect = geo_width / geo_height if geo_height > 0 else 0
    
    # Calculate raster aspect ratio
    raster_aspect = width / height if height > 0 else 0
    
    # Compare
    if geo_aspect > 0:
        ratio_diff = abs(raster_aspect - geo_aspect) / geo_aspect
        
        if ratio_diff > tolerance:
            raise AspectRatioError(
                f"Aspect ratio mismatch detected!\n"
                f"  Raster:     {width} x {height} = {raster_aspect:.3f}\n"
                f"  Geographic: {geo_width/1000:.1f}km x {geo_height/1000:.1f}km = {geo_aspect:.3f}\n"
                f"  Difference: {ratio_diff*100:.1f}% (tolerance: {tolerance*100:.1f}%)\n"
                f"\n"
                f"This usually means crop=False was used during masking, keeping empty\n"
                f"bounding box space instead of cropping to actual boundaries.\n"
                f"Fix: Use crop=True in rasterio.mask() operations."
            )


def validate_non_null_coverage(
    elevation: np.ndarray,
    min_coverage: float = 0.3,
    warn_only: bool = True
) -> float:
    """
    Validate that raster has sufficient non-null data.
    
    Low coverage might indicate incorrect bounding box or masking issues.
    
    Args:
        elevation: 2D elevation array
        min_coverage: Minimum fraction of non-null pixels required
        warn_only: If True, only warns; if False, raises exception
        
    Returns:
        Coverage fraction (0.0 to 1.0)
        
    Raises:
        BoundingBoxError: If coverage is too low and warn_only=False
    """
    total_pixels = elevation.size
    valid_pixels = np.count_nonzero(~np.isnan(elevation))
    coverage = valid_pixels / total_pixels if total_pixels > 0 else 0
    
    if coverage < min_coverage:
        msg = (
            f"Low non-null data coverage: {coverage*100:.1f}% "
            f"(minimum: {min_coverage*100:.1f}%)\n"
            f"  Total pixels: {total_pixels:,}\n"
            f"  Valid pixels: {valid_pixels:,}\n"
            f"  Null pixels:  {total_pixels - valid_pixels:,}\n"
            f"\n"
            f"This might indicate:\n"
            f"  - Incorrect bounding box (too much empty space)\n"
            f"  - crop=False used during masking (use crop=True instead)\n"
            f"  - Missing data in source file\n"
        )
        
        if warn_only:
            warnings.warn(msg, UserWarning)
        else:
            raise BoundingBoxError(msg)
    
    return coverage


def validate_elevation_range(
    elevation: np.ndarray,
    min_sensible_range: float = 50.0,
    warn_only: bool = True
) -> tuple:
    """
    Validate that elevation data has a reasonable range.
    
    Catches issues like:
    - Reprojection corruption (elevation collapsed to 0-5m range)
    - Wrong units (meters vs decimeters vs feet)
    - Filtering errors removing all variation
    
    Args:
        elevation: 2D elevation array
        min_sensible_range: Minimum reasonable elevation range in meters
        warn_only: If True, only warns; if False, raises exception
        
    Returns:
        Tuple of (min_elevation, max_elevation, range, is_valid)
        
    Raises:
        ElevationCorruptionError: If elevation range is unreasonably small
    """
    # Filter out invalid values - ensure float array
    elev_float = elevation.astype(np.float32)
    valid_elev = elev_float[~np.isnan(elev_float)]
    
    if len(valid_elev) == 0:
        msg = "No valid elevation data found"
        if warn_only:
            warnings.warn(msg, UserWarning)
            return (0, 0, 0, False)
        else:
            raise ElevationCorruptionError(msg)
    
    min_elev = float(np.min(valid_elev))
    max_elev = float(np.max(valid_elev))
    elev_range = max_elev - min_elev
    
    is_valid = elev_range >= min_sensible_range
    
    if not is_valid:
        msg = (
            f"Suspicious elevation range detected!\n"
            f"  Min elevation: {min_elev:.1f}m\n"
            f"  Max elevation: {max_elev:.1f}m\n"
            f"  Range: {elev_range:.1f}m (minimum: {min_sensible_range:.0f}m)\n"
            f"  Valid pixels: {len(valid_elev):,}\n"
            f"\n"
            f"This usually indicates:\n"
            f"  - Reprojection corruption (elevation data collapsed to 0-5m)\n"
            f"  - Units error (data in wrong units: feet, decimeters, etc)\n"
            f"  - Filtering removed all variation\n"
            f"\n"
            f"Action: Regenerate data from source using corrected pipeline."
        )
        
        if warn_only:
            warnings.warn(msg, UserWarning)
        else:
            raise ElevationCorruptionError(msg)
    
    return (min_elev, max_elev, elev_range, is_valid)


def validate_export_data(
    width: int,
    height: int,
    elevation: np.ndarray,
    bounds_degrees: Tuple[float, float, float, float],
    aspect_tolerance: float = 0.3,
    min_coverage: float = 0.3
) -> dict:
    """
    Comprehensive validation before exporting data.
    
    Runs all validation checks and returns diagnostics.
    
    Args:
        width: Raster width
        height: Raster height
        elevation: 2D elevation array
        bounds_degrees: (west, south, east, north)
        aspect_tolerance: Aspect ratio tolerance
        min_coverage: Minimum non-null coverage
        
    Returns:
        Dict with validation results and diagnostics
        
    Raises:
        AspectRatioError: If aspect ratio is invalid
        BoundingBoxError: If coverage is too low (when configured)
    """
    # Validate aspect ratio (raises exception if invalid)
    validate_aspect_ratio(width, height, bounds_degrees, aspect_tolerance)
    
    # Validate coverage (warns but doesn't raise)
    coverage = validate_non_null_coverage(elevation, min_coverage, warn_only=True)
    
    # Calculate diagnostics
    west, south, east, north = bounds_degrees
    center_lat = (north + south) / 2.0
    meters_per_deg_lon = 111_320 * np.cos(np.radians(center_lat))
    geo_width_km = abs(east - west) * meters_per_deg_lon / 1000
    geo_height_km = abs(north - south) * 111_320 / 1000
    
    return {
        "valid": True,
        "raster_aspect": width / height,
        "geographic_aspect": geo_width_km / geo_height_km if geo_height_km > 0 else 0,
        "coverage_percent": coverage * 100,
        "dimensions": f"{width} x {height}",
        "geographic_size": f"{geo_width_km:.1f}km x {geo_height_km:.1f}km"
    }
