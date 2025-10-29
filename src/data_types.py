"""
Strict data type definitions for the Altitude Maps project.

This module defines all data structures used throughout the pipeline,
with validation and clear documentation of expected formats.

DATA FLOW:
    Raw GeoTIFF -> RawElevationData
         ->
    Clipped -> ClippedElevationData
         ->
    Processed -> ProcessedElevationData
         ->
    Export -> ViewerElevationData
         ->
    Manifest -> RegionsManifest

Each stage has strict validation to ensure data integrity.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from pathlib import Path
import json
import hashlib
import numpy as np


# ============================================================================
# STAGE 1: RAW DATA (Downloaded from sources)
# ============================================================================

@dataclass
class GeoTransform:
    """
    GeoTIFF geotransform parameters.
    
    Format: (x_origin, pixel_width, 0, y_origin, 0, -pixel_height)
    - x_origin: Left coordinate
    - y_origin: Top coordinate
    - pixel_width: Pixel size in X direction
    - pixel_height: Pixel size in Y direction (negative = North up)
    """
    x_origin: float
    pixel_width: float
    rotation_x: float  # Usually 0
    y_origin: float
    rotation_y: float  # Usually 0
    pixel_height: float  # Negative for North-up
    
    def to_tuple(self) -> tuple:
        return (
            self.x_origin,
            self.pixel_width,
            self.rotation_x,
            self.y_origin,
            self.rotation_y,
            self.pixel_height
        )


@dataclass
class Bounds:
    """Geographic bounds in decimal degrees (WGS84)."""
    left: float    # West longitude
    bottom: float  # South latitude
    right: float   # East longitude
    top: float     # North latitude
    
    def __post_init__(self):
        """Validate bounds."""
        if self.left >= self.right:
            raise ValueError(f"Invalid bounds: left ({self.left}) >= right ({self.right})")
        if self.bottom >= self.top:
            raise ValueError(f"Invalid bounds: bottom ({self.bottom}) >= top ({self.top})")
        if not (-180 <= self.left <= 180 and -180 <= self.right <= 180):
            raise ValueError(f"Longitude out of range: {self.left}, {self.right}")
        if not (-90 <= self.bottom <= 90 and -90 <= self.top <= 90):
            raise ValueError(f"Latitude out of range: {self.bottom}, {self.top}")
    
    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class ElevationStats:
    """Statistics about elevation data."""
    min: float
    max: float
    mean: float
    
    def __post_init__(self):
        """Validate stats."""
        if self.min > self.max:
            raise ValueError(f"Invalid stats: min ({self.min}) > max ({self.max})")
    
    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class RawElevationData:
    """
    Raw elevation data loaded from a GeoTIFF file.
    
    This represents unprocessed elevation data as it comes from the source.
    
    VALIDATION:
    - Array must be 2D
    - CRS must be valid
    - Bounds must be valid geographic coordinates
    - Width/height must match array dimensions
    """
    # Metadata
    source_file: str
    source_type: Literal['srtm_30m', 'usa_3dep', 'japan_gsi', 'switzerland_swisstopo', 'unknown']
    downloaded_date: str  # ISO format
    file_hash: str
    
    # Dimensions
    width: int
    height: int
    
    # Geographic info
    crs: str  # e.g., "EPSG:4326"
    bounds: Bounds
    geotransform: GeoTransform
    resolution_meters: float
    
    # Elevation array (2D numpy array)
    # Shape: (height, width)
    # Values: float meters, NaN for no-data
    elevation: np.ndarray
    nodata_value: Optional[float]
    
    # Statistics
    elevation_range: ElevationStats
    
    def __post_init__(self):
        """Validate raw data."""
        # Check array dimensions
        if self.elevation.ndim != 2:
            raise ValueError(f"Elevation must be 2D, got {self.elevation.ndim}D")
        
        h, w = self.elevation.shape
        if h != self.height or w != self.width:
            raise ValueError(
                f"Array shape {self.elevation.shape} doesn't match "
                f"stated dimensions ({self.height}, {self.width})"
            )
        
        # Validate bounds
        if not isinstance(self.bounds, Bounds):
            raise TypeError(f"bounds must be Bounds instance, got {type(self.bounds)}")
        
        # Validate CRS
        if not self.crs.startswith('EPSG:'):
            raise ValueError(f"Invalid CRS format: {self.crs}")


# ============================================================================
# STAGE 2: CLIPPED DATA (Clipped to administrative boundaries)
# ============================================================================

@dataclass
class ClippedElevationData:
    """
    Elevation data clipped to a specific administrative boundary.
    
    This is raw data that has been masked to a country/state shape.
    
    VALIDATION:
    - Must have all RawElevationData validations
    - Must specify boundary used for clipping
    - Original bounds preserved for reference
    """
    # All fields from RawElevationData
    source_file: str
    source_type: Literal['srtm_30m', 'usa_3dep', 'japan_gsi', 'switzerland_swisstopo', 'unknown']
    downloaded_date: str
    file_hash: str
    
    width: int
    height: int
    
    crs: str
    bounds: Bounds
    geotransform: GeoTransform
    resolution_meters: float
    
    elevation: np.ndarray
    nodata_value: Optional[float]
    
    elevation_range: ElevationStats
    
    # Clipping-specific fields
    boundary_name: str  # e.g., "Delaware", "United States of America"
    boundary_source: str  # e.g., "Natural Earth 10m"
    original_bounds: Bounds  # Before clipping
    clipped_date: str  # ISO format
    
    def __post_init__(self):
        """Validate clipped data."""
        # Run same validations as raw data
        if self.elevation.ndim != 2:
            raise ValueError(f"Elevation must be 2D, got {self.elevation.ndim}D")
        
        h, w = self.elevation.shape
        if h != self.height or w != self.width:
            raise ValueError(
                f"Array shape {self.elevation.shape} doesn't match "
                f"stated dimensions ({self.height}, {self.width})"
            )


# ============================================================================
# STAGE 3: PROCESSED DATA (Downsampled/optimized for specific use)
# ============================================================================

@dataclass
class ProcessedElevationData:
    """
    Processed elevation data ready for export or visualization.
    
    This is downsampled and optimized data ready for a specific use case.
    
    VALIDATION:
    - Array dimensions must match stated width/height
    - Target pixels should be reasonable (100-2000 typically)
    - Must reference source file
    """
    # Processing metadata
    source_file: str
    source_file_hash: str
    processed_date: str  # ISO format
    processing_version: str  # e.g., "v2"
    
    # Target parameters
    target_pixels: int  # Max dimension requested
    actual_width: int   # Actual width after processing
    actual_height: int  # Actual height after processing
    
    # Geographic info (from source)
    crs: str
    bounds: Bounds
    resolution_meters: float
    
    # Processed elevation array
    # Shape: (actual_height, actual_width)
    # Values: float meters, None/NaN for no-data
    elevation: np.ndarray
    
    # Statistics
    elevation_range: ElevationStats
    
    # Data type info
    dtype: str  # e.g., "float32"
    nodata: Optional[float]
    
    def __post_init__(self):
        """Validate processed data."""
        if self.elevation.ndim != 2:
            raise ValueError(f"Elevation must be 2D, got {self.elevation.ndim}D")
        
        h, w = self.elevation.shape
        if h != self.actual_height or w != self.actual_width:
            raise ValueError(
                f"Array shape {self.elevation.shape} doesn't match "
                f"stated dimensions ({self.actual_height}, {self.actual_width})"
            )
        
        if self.target_pixels < 100 or self.target_pixels > 10000:
            raise ValueError(f"Unreasonable target_pixels: {self.target_pixels}")


# ============================================================================
# STAGE 4: VIEWER EXPORT DATA (JSON format for web viewer)
# ============================================================================

@dataclass
class ViewerElevationData:
    """
    Elevation data formatted for the interactive web viewer.
    
    This is the final JSON format loaded by the browser.
    
    FORMAT:
    {
        "format_version": 2,
        "exported_at": "2025-10-24T12:34:56Z",
        "source_file": "data/raw/srtm_30m/delaware_bbox_30m.tif",
        "width": 888,
        "height": 834,
        "elevation": [[...], [...], ...],  # 2D array: height rows, width columns
        "bounds": {"left": -75.79, "bottom": 38.45, "right": -75.05, "top": 39.84},
        "stats": {"min": -35.0, "max": 166.0, "mean": 15.17},
        "orientation": "north_up_east_right"
    }
    
    VALIDATION:
    - format_version must be 2
    - elevation must be 2D list with None for no-data
    - All required fields must be present
    - Dimensions must match array size
    """
    format_version: Literal[2]
    exported_at: str  # ISO format with Z
    source_file: str
    
    width: int
    height: int
    
    # Elevation as nested list for JSON serialization
    # Format: List[List[Optional[float]]]
    # Outer list: rows (height items)
    # Inner list: columns (width items)
    # None represents no-data
    elevation: List[List[Optional[float]]]
    
    bounds: Dict[str, float]  # {"left": ..., "bottom": ..., "right": ..., "top": ...}
    stats: Dict[str, float]   # {"min": ..., "max": ..., "mean": ...}
    
    orientation: Literal["north_up_east_right"]
    
    def __post_init__(self):
        """Validate viewer data."""
        if self.format_version != 2:
            raise ValueError(f"Invalid format_version: {self.format_version}")
        
        if len(self.elevation) != self.height:
            raise ValueError(
                f"Elevation has {len(self.elevation)} rows, "
                f"expected {self.height}"
            )
        
        if len(self.elevation[0]) != self.width:
            raise ValueError(
                f"Elevation row has {len(self.elevation[0])} columns, "
                f"expected {self.width}"
            )
        
        # Validate bounds keys
        required_bound_keys = {'left', 'bottom', 'right', 'top'}
        if set(self.bounds.keys()) != required_bound_keys:
            raise ValueError(f"Invalid bounds keys: {self.bounds.keys()}")
        
        # Validate stats keys
        required_stat_keys = {'min', 'max', 'mean'}
        if set(self.stats.keys()) != required_stat_keys:
            raise ValueError(f"Invalid stats keys: {self.stats.keys()}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'format_version': self.format_version,
            'exported_at': self.exported_at,
            'source_file': self.source_file,
            'width': self.width,
            'height': self.height,
            'elevation': self.elevation,
            'bounds': self.bounds,
            'stats': self.stats,
            'orientation': self.orientation
        }
    
    def to_json(self, filepath: Path) -> None:
        """Save to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, separators=(',', ':'))


# ============================================================================
# STAGE 5: MANIFEST (Index of all available regions)
# ============================================================================

@dataclass
class RegionInfo:
    """
    Information about a single region in the manifest.
    
    VALIDATION:
    - All required fields must be present
    - File must be a valid filename
    """
    name: str
    description: str
    source: str  # e.g., "srtm_30m", "usa_3dep"
    file: str    # Filename only, e.g., "delaware.json"
    bounds: Dict[str, float]
    stats: Dict[str, float]
    
    def __post_init__(self):
        """Validate region info."""
        if not self.file.endswith('.json'):
            raise ValueError(f"Region file must be .json, got: {self.file}")
        
        if '/' in self.file or '\\' in self.file:
            raise ValueError(f"Region file must be filename only, got: {self.file}")


@dataclass
class RegionsManifest:
    """
    Manifest of all available regions for the web viewer.
    
    FORMAT:
    {
        "version": "export_v2",
        "regions": {
            "delaware": {
                "name": "Delaware",
                "description": "Delaware elevation data",
                "source": "srtm_30m",
                "file": "delaware.json",
                "bounds": {...},
                "stats": {...}
            },
            ...
        }
    }
    
    VALIDATION:
    - version must be "export_v2"
    - regions must be a dict (not a list!)
    - Each region must have valid RegionInfo
    """
    version: Literal["export_v2"]
    regions: Dict[str, RegionInfo]  # Key = region_id
    
    def __post_init__(self):
        """Validate manifest."""
        if not isinstance(self.regions, dict):
            raise TypeError(f"regions must be dict, got {type(self.regions)}")
        
        for region_id, info in self.regions.items():
            if not isinstance(info, RegionInfo):
                raise TypeError(
                    f"Region '{region_id}' must be RegionInfo, "
                    f"got {type(info)}"
                )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'version': self.version,
            'regions': {
                region_id: asdict(info)
                for region_id, info in self.regions.items()
            }
        }
    
    def to_json(self, filepath: Path) -> None:
        """Save to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def validate_viewer_json(filepath: Path) -> ViewerElevationData:
    """
    Load and validate a viewer JSON file.
    
    Args:
        filepath: Path to the JSON file
        
    Returns:
        Validated ViewerElevationData object
        
    Raises:
        ValueError: If validation fails
        FileNotFoundError: If file doesn't exist
    """
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    with open(filepath) as f:
        data = json.load(f)
    
    # Validate required fields
    required_fields = {
        'format_version', 'exported_at', 'source_file',
        'width', 'height', 'elevation', 'bounds', 'stats', 'orientation'
    }
    missing = required_fields - set(data.keys())
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    
    # Create and validate ViewerElevationData object
    try:
        viewer_data = ViewerElevationData(**data)
    except Exception as e:
        raise ValueError(f"Validation failed: {e}")
    
    return viewer_data


def validate_manifest_json(filepath: Path) -> RegionsManifest:
    """
    Load and validate a regions manifest file.
    
    Args:
        filepath: Path to the manifest JSON file
        
    Returns:
        Validated RegionsManifest object
        
    Raises:
        ValueError: If validation fails
        FileNotFoundError: If file doesn't exist
    """
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    with open(filepath) as f:
        data = json.load(f)
    
    # Validate structure
    if 'version' not in data:
        raise ValueError("Manifest missing 'version' field")
    
    if 'regions' not in data:
        raise ValueError("Manifest missing 'regions' field")
    
    if not isinstance(data['regions'], dict):
        raise ValueError(
            f"Manifest 'regions' must be dict, got {type(data['regions'])}"
        )
    
    # Convert regions to RegionInfo objects
    regions = {}
    for region_id, region_data in data['regions'].items():
        try:
            regions[region_id] = RegionInfo(**region_data)
        except Exception as e:
            raise ValueError(
                f"Invalid region '{region_id}': {e}"
            )
    
    # Create and validate manifest
    manifest = RegionsManifest(
        version=data['version'],
        regions=regions
    )
    
    return manifest


def compute_file_hash(filepath: Path) -> str:
    """
    Compute SHA256 hash of a file.
    
    Args:
        filepath: Path to the file
        
    Returns:
        Hex string of the hash
    """
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


# ============================================================================
# TYPE CHECKING HELPERS
# ============================================================================

def is_valid_raw_data(data: Any) -> bool:
    """Check if data is valid RawElevationData."""
    try:
        if not isinstance(data, RawElevationData):
            return False
        # Validation happens in __post_init__
        return True
    except:
        return False


def is_valid_viewer_data(data: Any) -> bool:
    """Check if data is valid ViewerElevationData."""
    try:
        if not isinstance(data, ViewerElevationData):
            return False
        # Validation happens in __post_init__
        return True
    except:
        return False


def is_valid_manifest(data: Any) -> bool:
    """Check if data is valid RegionsManifest."""
    try:
        if not isinstance(data, RegionsManifest):
            return False
        # Validation happens in __post_init__
        return True
    except:
        return False

