"""
Automatic data processing pipeline for altitude-maps.

This module orchestrates the full workflow from raw download to viewer-ready export:
1. Download raw elevation data (bounding box)
2. Clip to administrative boundaries (state/country)
3. Process/downsample for viewer
4. Export to JSON format
5. Update regions manifest

User runs ONE command, pipeline handles everything automatically.

CRITICAL NAMING CONVENTION - Two distinct resolution types:

1. **elevation_resolution** (also called "data resolution"): 
   - Values: 10m, 30m, 90m
   - Refers to elevation data quality (e.g., SRTM 30m, USGS 3DEP 10m)
   - Dynamically determined by Nyquist sampling rule based on target_pixels
   - Used in: file naming, dataset selection, quality requirements

2. **border_resolution** (also called "boundary detail level"):
   - Values: 10m, 50m, 110m  
   - Refers to Natural Earth administrative boundary detail level
   - Always 10m in production pipeline (hardcoded)
   - Used in: border clipping operations, boundary geometry loading

These are COMPLETELY SEPARATE concepts. Do not confuse them.
"""
import sys
from pathlib import Path
from typing import Optional, Dict, List
import json

import rasterio
from rasterio.mask import mask as rasterio_mask
from rasterio.merge import merge
from rasterio.windows import Window
import numpy as np
from shapely.ops import unary_union
from shapely.geometry import mapping as shapely_mapping

from src.metadata import (
    create_clipped_metadata, create_processed_metadata,
    create_export_metadata, save_metadata, get_metadata_path, compute_file_hash
)
from src.tile_geometry import abstract_filename_from_raw, tile_filename_from_bounds, get_bounds_from_raw_file
from src.versioning import get_current_version
from src.borders import get_border_manager
from src.types import RegionType

# Alias for backward compatibility
bbox_filename_from_bounds = tile_filename_from_bounds


class PipelineError(Exception):
    """Raised when pipeline step fails."""
    pass


def merge_tiles(tile_paths: list[Path], output_path: Path) -> bool:
    """
    Merge multiple GeoTIFF tiles into a single file.
    
    Args:
        tile_paths: List of tile file paths to merge
        output_path: Output merged file path
        
    Returns:
        True if successful
    """
    import time
    
    if output_path.exists():
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"Already merged: {output_path.name} ({file_size_mb:.1f} MB)", flush=True)
        return True
    
    print(f"Merging {len(tile_paths)} tiles...", flush=True)
    merge_start = time.time()
    
    src_files = []
    try:
        for p in tile_paths:
            try:
                src = rasterio.open(p)
                if src.width > 0 and src.height > 0:
                    src_files.append(src)
                else:
                    src.close()
            except Exception as e:
                print(f"  Warning: Cannot open tile {p.name}: {e}", flush=True)

        if not src_files:
            print(f"ERROR: No valid tiles to merge!", flush=True)
            return False

        # Determine output dtype and nodata
        out_dtype = 'float32'
        nodata_values = [s.nodata for s in src_files if s.nodata is not None]
        out_nodata = nodata_values[0] if nodata_values else -9999.0

        # Merge tiles
        mosaic, out_transform = merge(
            src_files,
            nodata=out_nodata,
            dtype=out_dtype,
            method='first'
        )

        # Handle masked arrays
        if np.ma.isMaskedArray(mosaic):
            mosaic = mosaic.filled(out_nodata)

        # Get metadata from first tile
        out_meta = src_files[0].meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_transform,
            "dtype": out_dtype,
            "count": mosaic.shape[0],
            "nodata": out_nodata
        })

        # Write merged file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(mosaic)

        merge_time = time.time() - merge_start
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"Merged: {output_path.name} ({file_size_mb:.1f} MB, {merge_time:.1f}s)", flush=True)

        return True

    except Exception as e:
        print(f"Merge FAILED: {e}")
        if output_path.exists():
            output_path.unlink()
        return False
    finally:
        for src in src_files:
            try:
                src.close()
            except Exception:
                pass


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
    # Use abstract naming to find dependent files
    processed_dir = Path('data/processed') / source
    generated_dir = Path('generated/regions')
    
    deleted_deps = []
    
    # Get bounds from raw file to generate abstract filenames for dependent files
    raw_bounds = get_bounds_from_raw_file(raw_tif_path)
    if raw_bounds:
        # Generate abstract filenames
        # NOTE: This is elevation_data_resolution (10m/30m/90m), NOT border_resolution (10m/50m/110m)
        elevation_resolution = '30m' if '30m' in source else '90m' if '90m' in source else '10m'
        base_part = bbox_filename_from_bounds(raw_bounds, source, elevation_resolution)[5:-4]
        
        # Delete processed files by abstract name
        if processed_dir.exists():
            for f in processed_dir.glob(f'{base_part}_processed_*px_v2.tif'):
                f.unlink()
                deleted_deps.append(f"processed/{f.name}")
        
        # Delete exported JSON files by abstract name
        if generated_dir.exists():
            for f in generated_dir.glob(f'{base_part}_*px_v2.json'):
                if '_meta' not in f.stem and '_borders' not in f.stem:
                    f.unlink()
                    deleted_deps.append(f"generated/{f.name}")

    if deleted_deps:
        print(f"  Deleted {len(deleted_deps)} dependent file(s) (will be regenerated)")

    print(f"  Loading {boundary_type} boundary geometry for {boundary_name}...")

    # Get boundary geometry based on type
    if boundary_type == "country":
        # Use GeoDataFrame so we can reproject reliably
        border_manager = get_border_manager()
        geometry_gdf = border_manager.get_country(boundary_name, border_resolution=border_resolution)
    elif boundary_type == "state":
        # Parse "Country/State" format
        if "/" not in boundary_name:
            print(f"  Error: State boundary requires 'Country/State' format")
            print(f"  Got: {boundary_name}")
            return False

        country, state = boundary_name.split("/", 1)
        border_manager = get_border_manager()
        geometry_gdf = border_manager.get_state(country, state, border_resolution=border_resolution)

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
    
    # Delete dependent files if regenerating (using abstract naming)
    # Get bounds from input file to generate abstract filenames
    raw_bounds = get_bounds_from_raw_file(input_tif_path)
    if raw_bounds:
        # NOTE: This is elevation_data_resolution (10m/30m/90m), NOT border_resolution (10m/50m/110m)
        elevation_resolution = '30m' if '30m' in source else '90m' if '90m' in source else '10m'
        base_part = bbox_filename_from_bounds(raw_bounds, source, elevation_resolution)[5:-4]
        
        processed_dir = Path('data/processed') / source
        generated_dir = Path('generated/regions')
        
        # Delete processed files by abstract name
        if processed_dir.exists():
            for f in processed_dir.glob(f'{base_part}_processed_*px_v2.tif'):
                f.unlink()
        
        # Delete exported JSON files by abstract name
        if generated_dir.exists():
            for f in generated_dir.glob(f'{base_part}_*px_v2.json'):
                if '_meta' not in f.stem and '_borders' not in f.stem:
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
            
            # Convert to list - VECTORIZED for performance (~28x faster)
            print(f"  Converting to JSON format...", flush=True)
            # Convert NaN to None using vectorized operations
            mask = np.isnan(elevation_clean)
            elevation_object = elevation_clean.astype(object)
            elevation_object[mask] = None
            elevation_list = elevation_object.tolist()
            
            # Create export data
            export_data = {
                "version": "export_v2",  # CRITICAL: Required for manifest validation
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


def export_borders_for_viewer(
    processed_tif_path: Path,
    region_id: str,
    output_path: Path,
    boundary_name: Optional[str] = None,
    boundary_type: str = "country",
    border_resolution: str = "10m"
) -> bool:
    """
    Export border visualization data for the web viewer.
    
    Creates a separate _borders.json file containing border line coordinates
    for rendering yellow boundary lines in the 3D viewer.
    
    Args:
        processed_tif_path: Path to processed TIF (to get bounds/CRS)
        region_id: Region identifier
        output_path: Where to save borders JSON
        boundary_name: Boundary name (e.g., "United States of America/Idaho")
        boundary_type: "country" or "state"
        border_resolution: Natural Earth resolution for borders
        
    Returns:
        True if successful, False if no borders to export
    """
    if not boundary_name:
        # No boundary specified - skip border export
        return True
    
    try:
        print(f"  Exporting border visualization data...", flush=True)
        
        border_manager = get_border_manager()
        
        # Get bounds and CRS from processed TIF
        with rasterio.open(processed_tif_path) as src:
            bounds = src.bounds
            crs = src.crs
        
        # Get border geometry based on type
        if boundary_type == "state":
            # Parse "Country/State" format
            if "/" not in boundary_name:
                print(f"  Warning: State boundary requires 'Country/State' format, got: {boundary_name}")
                return False
            
            country, state = boundary_name.split("/", 1)
            geometry_gdf = border_manager.get_state(country, state, border_resolution=border_resolution)
        elif boundary_type == "country":
            geometry_gdf = border_manager.get_country(boundary_name, border_resolution=border_resolution)
        else:
            print(f"  Warning: Unknown boundary_type '{boundary_type}'")
            return False
        
        if geometry_gdf is None or geometry_gdf.empty:
            print(f"  Warning: Could not find boundary '{boundary_name}'")
            return False
        
        # Get border coordinates
        border_coords = border_manager.get_border_coordinates(
            boundary_name if boundary_type == "country" else [boundary_name],
            target_crs=crs,
            border_resolution=border_resolution
        )
        
        if not border_coords:
            print(f"  Warning: No border coordinates found")
            return False
        
        # Convert to JSON format
        segments = []
        total_points = 0
        for lon_coords, lat_coords in border_coords:
            segment = {
                "lon": [float(x) for x in lon_coords],
                "lat": [float(y) for y in lat_coords]
            }
            segments.append(segment)
            total_points += len(lon_coords)
        
        borders_data = {
            "bounds": {
                "left": float(bounds.left),
                "right": float(bounds.right),
                "top": float(bounds.top),
                "bottom": float(bounds.bottom)
            },
            "resolution": border_resolution,
            "countries": [{
                "name": boundary_name,
                "segments": segments,
                "segment_count": len(segments)
            }]
        }
        
        # Write JSON
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(borders_data, f, separators=(',', ':'))
        
        # Gzip compress
        import gzip
        gzip_path = output_path.with_suffix('.json.gz')
        with open(output_path, 'rb') as f_in:
            with gzip.open(gzip_path, 'wb', compresslevel=9) as f_out:
                f_out.writelines(f_in)
        
        file_size_kb = gzip_path.stat().st_size / 1024
        print(f"  Border data: {gzip_path.name} ({file_size_kb:.1f} KB, {len(segments)} segments, {total_points:,} points)")
        
        return True
        
    except Exception as e:
        import traceback
        print(f"  Border export failed: {e}")
        traceback.print_exc()
        return False


def update_regions_manifest(generated_dir: Path) -> bool:
    """
    Stage 11: Update the regions manifest with all available regions.
    
    CRITICAL RULES:
    1. ONLY regions from regions_config.py that HAVE DATA FILES are included
    2. ALL regions MUST have a region_type parameter (enforced)
    3. Region info (name, description, regionType) comes ONLY from regions_config
    4. JSON manifest uses camelCase "regionType" (not snake_case "region_type")
    5. JSON files only provide: file path, bounds, stats, source
    6. Regions without data files are SKIPPED (not included in manifest)
    
    Args:
        generated_dir: Directory containing exported JSON files
        
    Returns:
        True if successful
    """
    print(f"  Updating regions manifest...")
    
    try:
        from src.regions_config import ALL_REGIONS
        
        manifest = {
            "regions": {}
        }
        
        # Build index of JSON files by region_id for quick lookup
        json_files_by_region: Dict[str, List[Path]] = {}
        for json_file in sorted(generated_dir.glob("*.json")):
            if (json_file.stem.endswith('_meta') or
                json_file.stem.endswith('_borders') or
                'manifest' in json_file.stem):
                continue
            
            try:
                with open(json_file) as f:
                    data = json.load(f)
                
                # Extract region_id from JSON metadata
                region_id = data.get("region_id")
                if not region_id:
                    # Fallback: try to infer from filename (for old files during migration)
                    stem = json_file.stem
                    for suffix in ['_srtm_30m_2048px_v2', '_srtm_30m_800px_v2', '_srtm_30m_v2', '_bbox_30m', '_usa_3dep_2048px_v2']:
                        if stem.endswith(suffix):
                            stem = stem[:-len(suffix)]
                            region_id = stem
                            break
                
                if region_id:
                    if region_id not in json_files_by_region:
                        json_files_by_region[region_id] = []
                    json_files_by_region[region_id].append(json_file)
            except Exception:
                continue
        
        # Iterate ONLY through regions configured in regions_config.py
        for region_id, cfg in sorted(ALL_REGIONS.items()):
            # ENFORCE: region_type is MANDATORY
            if not hasattr(cfg, 'region_type') or cfg.region_type is None:
                print(f"  [SKIP] Region '{region_id}' missing region_type in regions_config - skipping")
                continue
            
            # Find matching JSON file(s) - use first available
            json_file = None
            json_data = None
            if region_id in json_files_by_region:
                for candidate_file in json_files_by_region[region_id]:
                    try:
                        with open(candidate_file) as f:
                            candidate_data = json.load(f)
                        json_file = candidate_file
                        json_data = candidate_data
                        break
                    except Exception:
                        continue
            
            # SKIP regions without data files - only include regions with actual data
            if not json_file or not json_data:
                continue
            
            # Build entry using ONLY info from regions_config
            entry = {
                "name": cfg.name,  # FROM CONFIG ONLY
                "description": cfg.description or f"{cfg.name} elevation data",  # FROM CONFIG ONLY
                "regionType": str(cfg.region_type),  # FROM CONFIG ONLY, REQUIRED (camelCase for JSON)
            }
            
            # Attach file/bounds/stats/source from JSON (guaranteed to exist since we skip if missing)
            entry["file"] = str(json_file.name)
            if "bounds" in json_data:
                entry["bounds"] = json_data["bounds"]
            if "stats" in json_data:
                entry["stats"] = json_data["stats"]
            if "source" in json_data:
                entry["source"] = json_data["source"]
            
            manifest["regions"][region_id] = entry
        
        # Write manifest
        manifest_path = generated_dir / "regions_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"  Manifest updated ({len(manifest['regions'])} regions with data files)")
        return True
        
    except Exception as e:
        print(f"  Warning: Could not update manifest: {e}")
        import traceback
        traceback.print_exc()
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
        # Generate abstract filename based on raw file bounds (no region_id)
        clipped_filename = abstract_filename_from_raw(raw_tif_path, 'clipped', source, boundary_name)
        if clipped_filename is None:
            raise ValueError(f"Could not generate abstract filename for clipped file - bounds extraction failed for {raw_tif_path}")
        clipped_path = clipped_dir / clipped_filename
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

    # Stage 7: reproject (intermediate file, use abstract naming)
    # Generate abstract filename based on raw file bounds (no region_id)
    reprojected_filename = abstract_filename_from_raw(raw_tif_path, 'processed', source, target_pixels=target_pixels)
    if reprojected_filename is None:
        raise ValueError(f"Could not generate abstract filename for reprojected file - bounds extraction failed for {raw_tif_path}")
    # Replace processed suffix with reproj suffix
    # Example: bbox_N041p00_N040p00_W111p00_W112p00_processed_2048px_v2.tif
    #       -> bbox_N041p00_N040p00_W111p00_W112p00_reproj.tif
    reprojected_filename = reprojected_filename.replace('_processed_', '_reproj_').replace(f'_{target_pixels}px_v2.tif', '.tif')
    reprojected_path = processed_dir / reprojected_filename
    
    print(f"\n[STAGE 7/10] Reprojecting to metric CRS...")
    if not reproject_to_metric_crs(clipped_path, region_id, reprojected_path, source):
        return False, result_paths

    # Stage 8: downsample
    print(f"\n[STAGE 8/10] Processing for viewer...")
    # Generate abstract filename based on raw file bounds (no region_id)
    processed_filename = abstract_filename_from_raw(raw_tif_path, 'processed', source, target_pixels=target_pixels)
    if processed_filename is None:
        raise ValueError(f"Could not generate abstract filename for processed file - bounds extraction failed for {raw_tif_path}")
    processed_path = processed_dir / processed_filename
    if not downsample_for_viewer(reprojected_path, region_id, processed_path, target_pixels):
        return False, result_paths
    result_paths["processed"] = processed_path

    # Stage 9: export JSON
    print(f"\n[STAGE 9/10] Exporting for web viewer...")
    # Exported JSON files use region_id-based naming (viewer-specific, not reusable data)
    # They're already clipped to specific boundaries and filtered for this viewer
    exported_filename = f"{region_id}_{source}_{target_pixels}px_v2.json"
    exported_path = generated_dir / exported_filename
    if not export_for_viewer(processed_path, region_id, source, exported_path):
        return False, result_paths
    result_paths["exported"] = exported_path
    
    # Stage 9.5: export border visualization (if applicable)
    if boundary_name:
        borders_filename = f"{region_id}_{source}_{target_pixels}px_v2_borders.json"
        borders_path = generated_dir / borders_filename
        export_borders_for_viewer(
            processed_path, 
            region_id, 
            borders_path,
            boundary_name=boundary_name,
            boundary_type=boundary_type,
            border_resolution=border_resolution
        )
        # Note: Border export failure is non-fatal - terrain data is still usable

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


if __name__ == "__main__":
    print("Pipeline module - use run_pipeline() function")
    print("\nExample:")
    print(" from src.pipeline import run_pipeline")
    print(" run_pipeline(")
    print(" Path('data/raw/srtm_30m/california_bbox_30m.tif'),")
    print(" 'california',")
    print(" 'srtm_30m',")
    print(" boundary_name='California'")
    print(" )")