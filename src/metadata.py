"""
Metadata generation and management for altitude-maps data pipeline.

Each data file in the pipeline has an accompanying JSON metadata file that tracks:
- Version information
- Source provenance  
- Processing parameters
- File hashes for validation
- Timestamps
"""
from typing import Dict, Optional, Tuple, Any
from pathlib import Path
import json
import hashlib
from datetime import datetime
import rasterio
import numpy as np

from .versioning import get_current_version


def compute_file_hash(filepath: Path, algorithm: str = 'md5') -> str:
    """
    Compute hash of a file for cache validation.
    
    Args:
        filepath: Path to file
        algorithm: Hash algorithm ('md5' or 'sha256')
        
    Returns:
        Hex digest of file hash
    """
    hash_func = hashlib.md5() if algorithm == 'md5' else hashlib.sha256()
    
    with open(filepath, 'rb') as f:
        # Read in chunks for large files
        for chunk in iter(lambda: f.read(8192), b''):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()


def extract_raster_info(filepath: Path) -> Dict[str, Any]:
    """
    Extract metadata from a GeoTIFF file.
    
    Args:
        filepath: Path to GeoTIFF file
        
    Returns:
        Dictionary with raster metadata
    """
    with rasterio.open(filepath) as src:
        bounds = src.bounds
        
        # Calculate approximate resolution in meters
        width_degrees = bounds.right - bounds.left
        height_degrees = bounds.top - bounds.bottom
        width_meters = width_degrees * 111000  # 1 degree ~ 111km
        height_meters = height_degrees * 111000
        res_x = width_meters / src.width
        res_y = height_meters / src.height
        avg_resolution = round((res_x + res_y) / 2)
        
        # Read sample to get elevation range
        sample_size = min(1000, src.height, src.width)
        sample = src.read(1, window=((0, sample_size), (0, sample_size)))
        
        return {
            "width": src.width,
            "height": src.height,
            "bounds": {
                "left": float(bounds.left),
                "bottom": float(bounds.bottom),
                "right": float(bounds.right),
                "top": float(bounds.top)
            },
            "crs": str(src.crs),
            "resolution_meters": avg_resolution,
            "elevation_range": [float(np.nanmin(sample)), float(np.nanmax(sample))],
            "dtype": str(src.dtypes[0]),
            "nodata": src.nodata
        }


def create_raw_metadata(
    tif_path: Path,
    region_id: str,
    source: str,
    download_url: Optional[str] = None,
    download_params: Optional[Dict] = None
) -> Dict:
    """
    Create metadata for raw downloaded data.
    
    Args:
        tif_path: Path to raw GeoTIFF file
        region_id: Region identifier (e.g., 'california', 'japan')
        source: Data source (e.g., 'usa_3dep', 'srtm_30m', 'japan_gsi')
        download_url: URL data was downloaded from
        download_params: Parameters used for download
        
    Returns:
        Metadata dictionary
    """
    raster_info = extract_raster_info(tif_path)
    file_hash = compute_file_hash(tif_path)
    
    metadata = {
        "version": get_current_version('raw'),
        "stage": "raw",
        "region_id": region_id,
        "source": source,
        "download_date": datetime.now().isoformat(),
        "file_path": str(tif_path),
        "file_size_mb": round(tif_path.stat().st_size / (1024*1024), 2),
        "file_hash": file_hash,
        **raster_info
    }
    
    if download_url:
        metadata["download_url"] = download_url
    if download_params:
        metadata["download_params"] = download_params
    
    return metadata


def create_clipped_metadata(
    tif_path: Path,
    region_id: str,
    source_file: Path,
    source_file_hash: str,
    clip_boundary: str,
    clip_source: str = "natural_earth_10m"
) -> Dict:
    """
    Create metadata for clipped/masked data.
    
    Args:
        tif_path: Path to clipped GeoTIFF file
        region_id: Region identifier
        source_file: Path to source raw file
        source_file_hash: Hash of source file (for validation)
        clip_boundary: Boundary name (e.g., 'California', 'United States of America')
        clip_source: Source of boundary data
        
    Returns:
        Metadata dictionary
    """
    raster_info = extract_raster_info(tif_path)
    file_hash = compute_file_hash(tif_path)
    
    metadata = {
        "version": get_current_version('clipped'),
        "stage": "clipped",
        "region_id": region_id,
        "created_date": datetime.now().isoformat(),
        "source_file": str(source_file),
        "source_file_hash": source_file_hash,
        "clip_boundary": clip_boundary,
        "clip_source": clip_source,
        "file_path": str(tif_path),
        "file_size_mb": round(tif_path.stat().st_size / (1024*1024), 2),
        "file_hash": file_hash,
        **raster_info
    }
    
    return metadata


def create_processed_metadata(
    tif_path: Path,
    region_id: str,
    source_file: Path,
    source_file_hash: str,
    target_total_pixels: int,
    processing_params: Optional[Dict] = None
) -> Dict:
    """
    Create metadata for processed/downsampled data.
    
    Args:
        tif_path: Path to processed GeoTIFF file
        region_id: Region identifier
        source_file: Path to source clipped file
        source_file_hash: Hash of source file
        target_total_pixels: Target total pixel count (width × height)
        processing_params: Additional processing parameters
        
    Returns:
        Metadata dictionary
    """
    raster_info = extract_raster_info(tif_path)
    file_hash = compute_file_hash(tif_path)
    
    metadata = {
        "version": get_current_version('processed'),
        "stage": "processed",
        "region_id": region_id,
        "created_date": datetime.now().isoformat(),
        "source_file": str(source_file),
        "source_file_hash": source_file_hash,
        "target_total_pixels": target_total_pixels,
        "file_path": str(tif_path),
        "file_size_mb": round(tif_path.stat().st_size / (1024*1024), 2),
        "file_hash": file_hash,
        **raster_info
    }
    
    if processing_params:
        metadata["processing_params"] = processing_params
    
    return metadata


def create_export_metadata(
    json_path: Path,
    region_id: str,
    source: str,
    source_file: Path,
    resolution_meters: int,
    export_params: Optional[Dict] = None
) -> Dict:
    """
    Create metadata for exported JSON data.
    
    Args:
        json_path: Path to exported JSON file
        region_id: Region identifier
        source: Data source (e.g., 'usa_3dep')
        source_file: Path to source processed file
        resolution_meters: Resolution in meters
        export_params: Export parameters
        
    Returns:
        Metadata dictionary
    """
    file_hash = compute_file_hash(json_path)
    
    metadata = {
        "version": get_current_version('export'),
        "stage": "export",
        "region_id": region_id,
        "source": source,
        "resolution_meters": resolution_meters,
        "export_date": datetime.now().isoformat(),
        "source_file": str(source_file),
        "file_path": str(json_path),
        "file_size_mb": round(json_path.stat().st_size / (1024*1024), 2),
        "file_hash": file_hash
    }
    
    if export_params:
        metadata["export_params"] = export_params
    
    return metadata


def save_metadata(metadata: Dict, output_path: Path) -> None:
    """
    Save metadata to JSON file.
    
    Args:
        metadata: Metadata dictionary
        output_path: Path to save JSON file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(metadata, f, indent=2)


def load_metadata(metadata_path: Path) -> Dict:
    """
    Load metadata from JSON file.
    
    Args:
        metadata_path: Path to metadata JSON file
        
    Returns:
        Metadata dictionary
        
    Raises:
        FileNotFoundError: If metadata file doesn't exist
    """
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
    
    with open(metadata_path) as f:
        return json.load(f)


def validate_source_file(source_file: Path, expected_hash: str) -> bool:
    """
    Validate that a source file hasn't changed since processing.
    
    Args:
        source_file: Path to source file
        expected_hash: Expected file hash from metadata
        
    Returns:
        True if file is valid, False otherwise
    """
    if not source_file.exists():
        return False
    
    actual_hash = compute_file_hash(source_file)
    return actual_hash == expected_hash


def get_metadata_path(data_path: Path) -> Path:
    """
    Get the metadata JSON path for a data file.
    
    Args:
        data_path: Path to data file (e.g., .tif or .json)
        
    Returns:
        Path to metadata JSON file
    """
    if data_path.suffix == '.json' and not data_path.stem.endswith('_meta'):
        # Data file is already JSON, add _meta suffix
        return data_path.with_stem(data_path.stem + '_meta')
    else:
        # Replace extension with .json
        return data_path.with_suffix('.json')


if __name__ == "__main__":
    # Test/demo
    print("Metadata module test")
    print("=" * 50)
    print("This module provides functions for:")
    print("  - Creating metadata for each pipeline stage")
    print("  - Computing file hashes for validation")
    print("  - Extracting raster information from GeoTIFFs")
    print("  - Saving/loading metadata JSON files")
    print("\nSee function docstrings for usage.")

