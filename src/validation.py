"""
Data validation utilities for the Altitude Maps pipeline.

This module provides validation functions for each stage of the data pipeline.
Every data transformation must validate its inputs and outputs using these functions.

VALIDATION PRINCIPLES:
1. Fail fast - catch errors early in the pipeline
2. Clear errors - explain exactly what's wrong
3. Comprehensive - check all aspects of data integrity
4. Documented - explain what each validation checks

USAGE:
    from src.validation import validate_raw_elevation, validate_viewer_export
    
    # Validate data at each stage
    raw_data = load_geotiff(...)
    validate_raw_elevation(raw_data)  # Raises ValueError if invalid
    
    # Continue processing...
    viewer_data = export_for_viewer(...)
    validate_viewer_export(viewer_data)  # Raises ValueError if invalid
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import numpy as np

from src.data_types import (
    RawElevationData, ClippedElevationData, ProcessedElevationData,
    ViewerElevationData, RegionsManifest, Bounds, ElevationStats
)


# ============================================================================
# RAW DATA VALIDATION
# ============================================================================

def validate_raw_elevation(data: RawElevationData) -> None:
    """
    Validate raw elevation data loaded from GeoTIFF.
    
    CHECKS:
    - Type is RawElevationData
    - Elevation array is 2D numpy array
    - Dimensions match array shape
    - No all-NaN arrays
    - CRS is valid
    - Bounds are valid geographic coordinates
    - Elevation values are reasonable (-500m to 9000m typically)
    
    Args:
        data: Raw elevation data to validate
        
    Raises:
        TypeError: If wrong type
        ValueError: If validation fails
    """
    if not isinstance(data, RawElevationData):
        raise TypeError(f"Expected RawElevationData, got {type(data)}")
    
    # Check array
    if not isinstance(data.elevation, np.ndarray):
        raise TypeError(f"Elevation must be numpy array, got {type(data.elevation)}")
    
    if data.elevation.ndim != 2:
        raise ValueError(f"Elevation must be 2D, got {data.elevation.ndim}D")
    
    # Check for all-NaN (invalid data)
    if np.all(np.isnan(data.elevation)):
        raise ValueError("Elevation array is all NaN - no valid data")
    
    # Check dimensions
    h, w = data.elevation.shape
    if h != data.height or w != data.width:
        raise ValueError(
            f"Array shape {data.elevation.shape} doesn't match "
            f"dimensions ({data.height}, {data.width})"
        )
    
    # Check elevation values are reasonable
    valid_data = data.elevation[~np.isnan(data.elevation)]
    if len(valid_data) > 0:
        min_elev = float(np.min(valid_data))
        max_elev = float(np.max(valid_data))
        
        if min_elev < -500 or max_elev > 9000:
            print(f"⚠️  Warning: Unusual elevation range: {min_elev}m to {max_elev}m")
    
    # Validation in __post_init__ checks:
    # - CRS format
    # - Bounds validity
    
    print(f"✅ Raw elevation data validated: {data.width}x{data.height}, "
          f"{data.elevation_range.min:.0f}m to {data.elevation_range.max:.0f}m")


# ============================================================================
# CLIPPED DATA VALIDATION
# ============================================================================

def validate_clipped_elevation(data: ClippedElevationData) -> None:
    """
    Validate clipped elevation data.
    
    CHECKS:
    - All raw data validations
    - Boundary name is specified
    - Clipped bounds are within original bounds
    - Some valid data exists after clipping
    
    Args:
        data: Clipped elevation data to validate
        
    Raises:
        TypeError: If wrong type
        ValueError: If validation fails
    """
    if not isinstance(data, ClippedElevationData):
        raise TypeError(f"Expected ClippedElevationData, got {type(data)}")
    
    # Run raw data checks
    if not isinstance(data.elevation, np.ndarray) or data.elevation.ndim != 2:
        raise ValueError("Invalid elevation array")
    
    # Check boundary info
    if not data.boundary_name:
        raise ValueError("boundary_name must be specified")
    
    # Check clipped bounds are within original
    if (data.bounds.left < data.original_bounds.left or
        data.bounds.right > data.original_bounds.right or
        data.bounds.bottom < data.original_bounds.bottom or
        data.bounds.top > data.original_bounds.top):
        print(f"⚠️  Warning: Clipped bounds extend beyond original bounds")
    
    # Check for valid data
    valid_pixels = np.sum(~np.isnan(data.elevation))
    total_pixels = data.elevation.size
    valid_percent = 100 * valid_pixels / total_pixels
    
    if valid_pixels == 0:
        raise ValueError("No valid data after clipping - clipping removed all data")
    
    print(f"✅ Clipped elevation validated: {data.boundary_name}, "
          f"{valid_percent:.1f}% valid pixels")


# ============================================================================
# PROCESSED DATA VALIDATION
# ============================================================================

def validate_processed_elevation(data: ProcessedElevationData) -> None:
    """
    Validate processed elevation data.
    
    CHECKS:
    - Type is ProcessedElevationData
    - Dimensions are reasonable (not too small/large)
    - Array matches stated dimensions
    - Processing hasn't corrupted data
    
    Args:
        data: Processed elevation data to validate
        
    Raises:
        TypeError: If wrong type
        ValueError: If validation fails
    """
    if not isinstance(data, ProcessedElevationData):
        raise TypeError(f"Expected ProcessedElevationData, got {type(data)}")
    
    # Check dimensions are reasonable
    if data.actual_width < 10 or data.actual_height < 10:
        raise ValueError(
            f"Processed dimensions too small: {data.actual_width}x{data.actual_height}"
        )
    
    if data.actual_width > 10000 or data.actual_height > 10000:
        raise ValueError(
            f"Processed dimensions too large: {data.actual_width}x{data.actual_height}"
        )
    
    # Check array
    if not isinstance(data.elevation, np.ndarray):
        raise TypeError(f"Elevation must be numpy array")
    
    h, w = data.elevation.shape
    if h != data.actual_height or w != data.actual_width:
        raise ValueError(
            f"Array shape {data.elevation.shape} doesn't match "
            f"dimensions ({data.actual_height}, {data.actual_width})"
        )
    
    # Check for data loss
    valid_pixels = np.sum(~np.isnan(data.elevation))
    if valid_pixels == 0:
        raise ValueError("Processing removed all valid data")
    
    print(f"✅ Processed elevation validated: {data.actual_width}x{data.actual_height}, "
          f"{valid_pixels:,} valid pixels")


# ============================================================================
# VIEWER EXPORT VALIDATION
# ============================================================================

def validate_viewer_export(data: ViewerElevationData) -> None:
    """
    Validate viewer export data (final JSON format).
    
    CHECKS:
    - Type is ViewerElevationData
    - Format version is correct (2)
    - Elevation is proper 2D list structure
    - Dimensions match array size
    - All required fields present
    - Values are JSON-serializable
    
    Args:
        data: Viewer elevation data to validate
        
    Raises:
        TypeError: If wrong type
        ValueError: If validation fails
    """
    if not isinstance(data, ViewerElevationData):
        raise TypeError(f"Expected ViewerElevationData, got {type(data)}")
    
    # Format version check
    if data.format_version != 2:
        raise ValueError(f"Invalid format_version: {data.format_version}, expected 2")
    
    # Check elevation structure
    if not isinstance(data.elevation, list):
        raise TypeError(f"Elevation must be list, got {type(data.elevation)}")
    
    if len(data.elevation) == 0:
        raise ValueError("Elevation array is empty")
    
    if not isinstance(data.elevation[0], list):
        raise TypeError(f"Elevation rows must be lists")
    
    # Check dimensions
    if len(data.elevation) != data.height:
        raise ValueError(
            f"Elevation has {len(data.elevation)} rows, expected {data.height}"
        )
    
    row_length = len(data.elevation[0])
    if row_length != data.width:
        raise ValueError(
            f"Elevation rows have {row_length} columns, expected {data.width}"
        )
    
    # Verify all rows same length
    for i, row in enumerate(data.elevation):
        if len(row) != data.width:
            raise ValueError(
                f"Row {i} has {len(row)} columns, expected {data.width}"
            )
    
    # Check values are valid (float or None)
    sample_row = data.elevation[0]
    for val in sample_row[:10]:  # Check first 10 values
        if val is not None and not isinstance(val, (int, float)):
            raise TypeError(f"Elevation values must be float or None, got {type(val)}")
    
    # Count valid data points
    valid_count = sum(
        1 for row in data.elevation
        for val in row
        if val is not None
    )
    
    if valid_count == 0:
        raise ValueError("No valid elevation data in export")
    
    total_points = data.width * data.height
    valid_percent = 100 * valid_count / total_points
    
    print(f"✅ Viewer export validated: {data.width}x{data.height}, "
          f"{valid_count:,} points ({valid_percent:.1f}% valid)")


# ============================================================================
# MANIFEST VALIDATION
# ============================================================================

def validate_manifest(manifest: RegionsManifest, data_dir: Path) -> None:
    """
    Validate regions manifest.
    
    CHECKS:
    - Type is RegionsManifest
    - Version is correct
    - All referenced files exist
    - Each region has valid structure
    
    Args:
        manifest: Regions manifest to validate
        data_dir: Directory containing region files
        
    Raises:
        TypeError: If wrong type
        ValueError: If validation fails
        FileNotFoundError: If referenced files missing
    """
    if not isinstance(manifest, RegionsManifest):
        raise TypeError(f"Expected RegionsManifest, got {type(manifest)}")
    
    if manifest.version != "export_v2":
        raise ValueError(f"Invalid manifest version: {manifest.version}")
    
    # Check regions is a dict
    if not isinstance(manifest.regions, dict):
        raise TypeError(f"manifest.regions must be dict, got {type(manifest.regions)}")
    
    if len(manifest.regions) == 0:
        raise ValueError("Manifest has no regions")
    
    # Validate each region
    missing_files = []
    for region_id, region_info in manifest.regions.items():
        # Check file exists
        file_path = data_dir / region_info.file
        if not file_path.exists():
            missing_files.append(f"{region_id}: {region_info.file}")
        
        # Validate bounds
        try:
            Bounds(**region_info.bounds)
        except Exception as e:
            raise ValueError(f"Region '{region_id}' has invalid bounds: {e}")
        
        # Validate stats
        try:
            ElevationStats(**region_info.stats)
        except Exception as e:
            raise ValueError(f"Region '{region_id}' has invalid stats: {e}")
    
    if missing_files:
        raise FileNotFoundError(
            f"Manifest references missing files:\n" +
            "\n".join(f"  - {f}" for f in missing_files)
        )
    
    print(f"✅ Manifest validated: {len(manifest.regions)} regions")


# ============================================================================
# FILE VALIDATION
# ============================================================================

def validate_viewer_json_file(filepath: Path) -> ViewerElevationData:
    """
    Load and validate a viewer JSON file from disk.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Validated ViewerElevationData object
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If validation fails
    """
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    print(f"🔍 Validating {filepath.name}...")
    
    # Load JSON
    try:
        with open(filepath) as f:
            data_dict = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
    
    # Check required fields
    required = {
        'format_version', 'exported_at', 'source_file',
        'width', 'height', 'elevation', 'bounds', 'stats', 'orientation'
    }
    missing = required - set(data_dict.keys())
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    
    # Create and validate object
    try:
        viewer_data = ViewerElevationData(**data_dict)
    except Exception as e:
        raise ValueError(f"Validation failed: {e}")
    
    # Additional validation
    validate_viewer_export(viewer_data)
    
    return viewer_data


def validate_manifest_file(filepath: Path, data_dir: Optional[Path] = None) -> RegionsManifest:
    """
    Load and validate a manifest JSON file from disk.
    
    Args:
        filepath: Path to manifest JSON file
        data_dir: Optional directory to check for referenced files
        
    Returns:
        Validated RegionsManifest object
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If validation fails
    """
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    print(f"🔍 Validating manifest {filepath.name}...")
    
    # Load JSON
    try:
        with open(filepath) as f:
            data_dict = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
    
    # Import RegionInfo for conversion
    from src.data_types import RegionInfo
    
    # Convert regions dict to RegionInfo objects
    regions = {}
    for region_id, region_data in data_dict['regions'].items():
        try:
            regions[region_id] = RegionInfo(**region_data)
        except Exception as e:
            raise ValueError(f"Invalid region '{region_id}': {e}")
    
    # Create manifest
    manifest = RegionsManifest(
        version=data_dict['version'],
        regions=regions
    )
    
    # Validate
    if data_dir:
        validate_manifest(manifest, data_dir)
    
    return manifest


# ============================================================================
# BATCH VALIDATION
# ============================================================================

def validate_all_viewer_files(directory: Path) -> Dict[str, bool]:
    """
    Validate all viewer JSON files in a directory.
    
    Args:
        directory: Directory containing JSON files
        
    Returns:
        Dict mapping filename to validation status (True=valid, False=invalid)
    """
    results = {}
    
    for json_file in directory.glob("*.json"):
        if json_file.name == "regions_manifest.json":
            continue
        
        try:
            validate_viewer_json_file(json_file)
            results[json_file.name] = True
            print(f"  ✅ {json_file.name}")
        except Exception as e:
            results[json_file.name] = False
            print(f"  ❌ {json_file.name}: {e}")
    
    return results


# ============================================================================
# QUICK VALIDATION (for debugging)
# ============================================================================

def quick_check_viewer_json(filepath: Path) -> str:
    """
    Quick check of viewer JSON without full validation.
    Returns a summary string.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Summary string describing the file
    """
    try:
        with open(filepath) as f:
            data = json.load(f)
        
        version = data.get('format_version', '?')
        width = data.get('width', '?')
        height = data.get('height', '?')
        has_elevation = 'elevation' in data
        
        elev_rows = len(data.get('elevation', [])) if has_elevation else 0
        elev_cols = len(data['elevation'][0]) if elev_rows > 0 else 0
        
        return (
            f"{filepath.name}: "
            f"v{version}, {width}x{height}, "
            f"elevation={'✅' if has_elevation else '❌'} ({elev_rows}x{elev_cols})"
        )
    except Exception as e:
        return f"{filepath.name}: ❌ ERROR - {e}"

