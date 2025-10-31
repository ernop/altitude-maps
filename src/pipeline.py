"""
Automatic data processing pipeline for altitude-maps.

This module orchestrates the full workflow from raw download to viewer-ready export:
1. Download raw elevation data (bounding box)
2. Clip to administrative boundaries (state/country)
3. Process/downsample for viewer
4. Export to JSON format
5. Update regions manifest

User runs ONE command, pipeline handles everything automatically.
"""
import sys
from pathlib import Path
from typing import Optional, Dict, Tuple
import json

try:
    import rasterio
    from rasterio.mask import mask as rasterio_mask
    import numpy as np
    from shapely.geometry import shape
except ImportError as e:
    print(f"Missing package: {e}")
    print("Install with: pip install rasterio shapely")
    sys.exit(1)

from src.metadata import (
    create_clipped_metadata, create_processed_metadata,
    create_export_metadata, save_metadata, get_metadata_path, compute_file_hash
)
from src.versioning import get_current_version
from src.borders import get_country_geometry, get_border_manager


class PipelineError(Exception):
    """Raised when pipeline step fails."""
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
        print(f" Input file not found: {raw_tif_path}")
        return False

    # Check if output exists and is valid
    if output_path.exists():
        try:
            # Validate the existing clipped file
            with rasterio.open(output_path) as src:
                if src.width > 0 and src.height > 0:
                    # Try reading a small sample to ensure it's not corrupted
                    _ = src.read(1, window=((0, min(10, src.height)), (0, min(10, src.width))))
                    print(f" Already clipped (validated): {output_path.name}")
                    return True
        except Exception as e:
            print(f" Existing file corrupted: {e}")
            print(f" Deleting and regenerating...")
            try:
                output_path.unlink()
            except Exception as del_e:
                print(f" Could not delete: {del_e}")

    # If we're regenerating the clipped file, delete dependent processed and generated files
    # This ensures the entire pipeline uses consistent data
    processed_dir = Path('data/processed') / source
    generated_dir = Path('generated/regions')

    deleted_deps = []
    if processed_dir.exists():
        for f in processed_dir.glob(f'{region_id}_*'):
            f.unlink()
            deleted_deps.append(f"processed/{f.name}")
    if generated_dir.exists():
        for f in generated_dir.glob(f'{region_id}_*'):
            f.unlink()
            deleted_deps.append(f"generated/{f.name}")

    if deleted_deps:
        print(f" Deleted {len(deleted_deps)} dependent file(s) (will be regenerated)")

    print(f" Loading {boundary_type} boundary geometry for {boundary_name}...")

    # Get boundary geometry based on type
    if boundary_type == "country":
        # Use GeoDataFrame so we can reproject reliably
        border_manager = get_border_manager()
        geometry_gdf = border_manager.get_country(boundary_name, resolution=border_resolution)
    elif boundary_type == "state":
        # Parse "Country/State" format
        if "/" not in boundary_name:
            print(f" Error: State boundary requires 'Country/State' format")
            print(f" Got: {boundary_name}")
            return False

        country, state = boundary_name.split("/", 1)
        border_manager = get_border_manager()
        geometry_gdf = border_manager.get_state(country, state, resolution=border_resolution)

        if geometry_gdf is None or geometry_gdf.empty:
            if boundary_required:
                error_msg = f"State '{state}' boundary not found in '{country}' and boundary is required."
                print(f" Error: {error_msg}")
                raise PipelineError(error_msg)
            else:
                print(f" Warning: State '{state}' not found in '{country}'. Skipping clipping step...")
            return False
    else:
        print(f" Error: Invalid boundary_type '{boundary_type}' (must be 'country' or 'state')")
        return False

    if geometry_gdf is None or geometry_gdf.empty:
        if boundary_required:
            error_msg = f"Could not find boundary '{boundary_name}' and boundary is required."
            print(f" Error: {error_msg}")
            raise PipelineError(error_msg)
        else:
            print(f" Warning: Could not find boundary '{boundary_name}'. Skipping clipping step...")
        return False

    print(f" Clipping to {boundary_type} boundary...")

    try:
        with rasterio.open(raw_tif_path) as src:
            print(f" Input dimensions: {src.width} x {src.height} pixels")
            print(f" Input size: {raw_tif_path.stat().st_size / (1024*1024):.1f} MB")

            # Prepare boundary geometry in raster CRS and GeoJSON mapping
            from shapely.ops import unary_union
            from shapely.geometry import mapping as shapely_mapping
            try:
                geometry_reproj = geometry_gdf.to_crs(src.crs)
            except Exception:
                geometry_reproj = geometry_gdf
            union_geom = unary_union(geometry_reproj.geometry)
            geoms = [shapely_mapping(union_geom)]

            # Clip the raster to the boundary
            print(f" Applying geometric mask...")
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

            print(f" Output dimensions: {out_meta['width']} x {out_meta['height']} pixels")

            # Ensure nodata is set and masked pixels are written as nodata
            import numpy as _np
            if _np.ma.isMaskedArray(out_image):
                # Choose an appropriate nodata value based on dtype
                if src.nodata is not None:
                    nodata_value = src.nodata
                else:
                    if _np.issubdtype(src.dtypes[0], _np.floating):
                        nodata_value = _np.nan
                    else:
                        # For integer rasters, use minimum value for the dtype
                        nodata_value = _np.iinfo(_np.dtype(src.dtypes[0])).min
                out_meta['nodata'] = nodata_value
                out_image = out_image.filled(nodata_value)

            # ASPECT RATIO FIX: Reproject ALL EPSG:4326 regions to preserve real-world proportions
            # EPSG:4326 (lat/lon) has distorted aspect ratios at ALL latitudes (except equator)
            # because longitude degrees are compressed by cos(latitude)
            # This affects mid-latitude regions significantly (e.g., Kansas at 38.5degN has 27.6% distortion)
            needs_reprojection = False
            if src.crs and 'EPSG:4326' in str(src.crs).upper():
                # Calculate average latitude of the CLIPPED region (CRITICAL: use clipped bounds, not raw bounds!)
                # After masking with crop=True, out_transform represents the clipped region bounds
                # We must use these clipped bounds to calculate the correct distortion factor
                from rasterio.transform import array_bounds
                left, bottom, right, top = array_bounds(out_image.shape[1], out_image.shape[2], out_transform)
                avg_lat = (top + bottom) / 2
                print(f" Clipped region bounds: {left:.2f}degE, {bottom:.2f}degN to {right:.2f}degE, {top:.2f}degN")
                print(f" Average latitude: {avg_lat:.2f}deg")

                # Reproject ALL EPSG:4326 regions to fix distortion (no equator exception)
                needs_reprojection = True
                import math
                # Calculate distortion factor (use abs(lat) since cos is symmetric: cos(lat) = cos(-lat))
                abs_lat = abs(avg_lat)
                cos_lat = math.cos(math.radians(abs_lat))
                distortion = 1.0 / cos_lat if cos_lat > 0.01 else 1.0
                print(f" Latitude {avg_lat:+.1f}deg - aspect ratio distorted {distortion:.2f}x by EPSG:4326")
                print(f" Reprojecting to equal-area projection to preserve real-world proportions...")

            if needs_reprojection:
                # Reproject to Web Mercator or UTM to preserve distances
                # Web Mercator (EPSG:3857) works well for visualization
                from rasterio.warp import calculate_default_transform, reproject, Resampling

                # Choose appropriate projection based on hemisphere and longitude
                # For simplicity, use Web Mercator for mid-high latitudes (not poles)
                if abs(avg_lat) < 85:
                    dst_crs = 'EPSG:3857'  # Web Mercator
                else:
                    # For extreme latitudes, use a polar stereographic projection
                    dst_crs = 'EPSG:3413' if avg_lat > 0 else 'EPSG:3031'

                # Calculate transform for reprojection
                transform, width, height = calculate_default_transform(
                    src.crs, dst_crs,
                    out_meta['width'], out_meta['height'],
                    *rasterio.transform.array_bounds(out_meta['height'], out_meta['width'], out_transform)
                )

                # Update metadata for reprojected raster
                out_meta.update({
                    'crs': dst_crs,
                    'transform': transform,
                    'width': width,
                    'height': height
                })

                # Create reprojected array with nodata initialized
                # Avoid NaN as nodata for GDAL warp; prefer -9999.0 for float rasters
                if out_meta.get('nodata') is None:
                    if np.issubdtype(out_image.dtype, np.floating):
                        out_meta['nodata'] = -9999.0
                    else:
                        out_meta['nodata'] = np.iinfo(out_image.dtype).min
                reprojected = np.empty((1, height, width), dtype=out_image.dtype)
                reprojected.fill(out_meta['nodata'])  # Initialize with nodata value

                reproject(
                    source=out_image,
                    destination=reprojected,
                    src_transform=out_transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.bilinear,
                    src_nodata=out_meta['nodata'],
                    dst_nodata=out_meta['nodata']
                )

                out_image = reprojected
                print(f" Reprojected to {dst_crs}: {width} x {height} pixels")

                # Verify aspect ratio improvement
                old_aspect = out_meta['width'] / out_meta['height'] if 'width' in out_meta else 0
                new_aspect = width / height
                print(f" Aspect ratio: {old_aspect:.2f}:1 -> {new_aspect:.2f}:1")

            # VALIDATION: Check elevation range to catch corruption
            from src.validation import validate_elevation_range
            min_elev, max_elev, elev_range, is_valid = validate_elevation_range(
                out_image[0], min_sensible_range=50.0, warn_only=False
            )
            if not is_valid:
                raise ValueError(f"Elevation corruption detected! Range: {elev_range:.1f}m")
            print(f" Elevation range validated: {min_elev:.1f}m to {max_elev:.1f}m (range: {elev_range:.1f}m)")

            # Write clipped (and possibly reprojected) data
            print(f" Writing clipped raster to disk...")
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
        print(f" Clipped: {output_path.name} ({file_size_mb:.1f} MB)")
        return True

    except Exception as e:
        print(f" Clipping failed: {e}")
        if output_path.exists():
            output_path.unlink()
        return False


def downsample_for_viewer(
    clipped_tif_path: Path,
    region_id: str,
    output_path: Path,
    target_pixels: int = 2048
) -> bool:
    """
    Downsample clipped data to target resolution for web viewer.

    Args:
        clipped_tif_path: Path to clipped TIF
        region_id: Region identifier
        output_path: Where to save processed TIF
        target_pixels: Target dimension in pixels (default: 800)

    Returns:
        True if successful
    """
    # Validate input file first
    if not clipped_tif_path.exists():
        print(f" Input file not found: {clipped_tif_path}")
        return False

    # Check if output exists and is valid AND already reprojected to a metric CRS
    if output_path.exists():
        try:
            with rasterio.open(output_path) as src:
                # Basic pixel validity
                if src.width > 0 and src.height > 0:
                    _ = src.read(1, window=((0, min(10, src.height)), (0, min(10, src.width))))
                    # CRS validation: processed file MUST NOT be EPSG:4326 (degrees)
                    crs_str = str(src.crs) if src.crs is not None else ""
                    is_latlon = ('EPSG:4326' in crs_str.upper()) or ('WGS84' in crs_str.upper())
                    if is_latlon:
                        print(f" Processed file uses geographic CRS ({crs_str}); reprojection required. Regenerating...")
                        raise RuntimeError("processed_file_crs_is_latlon")
                    # Looks good; keep existing
                    print(f" Already processed (validated & reprojected): {output_path.name}")
                    return True
        except Exception as e:
            print(f" Existing processed file invalid or needs reprojection: {e}")
            print(f" Deleting and regenerating...")
            try:
                output_path.unlink()
            except Exception as del_e:
                print(f" Could not delete: {del_e}")

    # If we're regenerating the processed file, delete dependent generated files
    generated_dir = Path('generated/regions')
    if generated_dir.exists():
        deleted_count = 0
        for f in generated_dir.glob(f'{region_id}_*'):
            f.unlink()
            deleted_count += 1
        if deleted_count > 0:
            print(f" Deleted {deleted_count} generated file(s) (will be regenerated)")

    print(f" Downsampling to {target_pixels}x{target_pixels}...")

    try:
        with rasterio.open(clipped_tif_path) as src:
            print(f" Input: {src.width} x {src.height} pixels", flush=True)
            # RAW INPUT VALIDATION (pre-flight)
            try:
                if src.count < 1:
                    raise ValueError("No bands in source raster")
                if src.crs is None:
                    raise ValueError("Missing CRS in source raster")
                # Basic dtype check
                if not (np.issubdtype(np.dtype(src.dtypes[0]), np.integer) or np.issubdtype(np.dtype(src.dtypes[0]), np.floating)):
                    raise ValueError(f"Unsupported dtype: {src.dtypes[0]}")
                # Sample a central window for quick stats without loading all data
                win_w = max(1, min(1024, src.width // 4))
                win_h = max(1, min(1024, src.height // 4))
                col_off = max(0, (src.width - win_w) // 2)
                row_off = max(0, (src.height - win_h) // 2)
                from rasterio.windows import Window
                sample = src.read(1, window=Window(col_off, row_off, win_w, win_h))
                sample_f = sample.astype(np.float32)
                # Treat extreme values as invalid for a quick signal
                sample_f[(sample_f < -10000) | (sample_f > 10000)] = np.nan
                valid = ~np.isnan(sample_f)
                valid_pct = float(np.count_nonzero(valid)) / sample_f.size if sample_f.size else 0.0
                if valid_pct == 0.0:
                    raise ValueError("No valid elevation in central sample window")
                smin = float(np.nanmin(sample_f))
                smax = float(np.nanmax(sample_f))
                print(f" Sample window valid: {valid_pct*100:.1f}% | range: {smin:.1f}..{smax:.1f} m")
            except Exception as v_err:
                print(f" Input validation failed: {v_err}")
                return False

            # Check if reprojection is needed for latitude distortion fix
            needs_reprojection = False
            avg_lat = 0  # Initialize to avoid undefined variable error
            if src.crs and 'EPSG:4326' in str(src.crs).upper():
                bounds = src.bounds
                avg_lat = (bounds.top + bounds.bottom) / 2
                # Reproject ALL EPSG:4326 regions to fix distortion (no equator exception)
                needs_reprojection = True
                import math
                # Calculate distortion factor (use abs(lat) since cos is symmetric: cos(lat) = cos(-lat))
                abs_lat = abs(avg_lat)
                cos_lat = math.cos(math.radians(abs_lat))
                distortion = 1.0 / cos_lat if cos_lat > 0.01 else 1.0
                print(f" Latitude {avg_lat:+.1f}deg - aspect ratio distorted {distortion:.2f}x by EPSG:4326")
                print(f" Reprojecting to fix latitude distortion...")

            # Reproject if needed (before downsampling)
            if needs_reprojection:
                from rasterio.warp import calculate_default_transform, reproject, Resampling
                from rasterio import Affine

                if abs(avg_lat) < 85:
                    dst_crs = 'EPSG:3857'  # Web Mercator
                else:
                    dst_crs = 'EPSG:3413' if avg_lat > 0 else 'EPSG:3031'

                # Calculate transform for reprojection at native full resolution
                base_transform, base_width, base_height = calculate_default_transform(
                    src.crs, dst_crs,
                    src.width, src.height,
                    *src.bounds
                )

                # Compute target size capped to target_pixels while preserving aspect ratio
                aspect = base_width / base_height if base_height != 0 else 1.0
                if base_width >= base_height:
                    dst_width = min(target_pixels, base_width)
                    dst_height = max(1, int(round(dst_width / aspect)))
                else:
                    dst_height = min(target_pixels, base_height)
                    dst_width = max(1, int(round(dst_height * aspect)))

                # Scale the transform to match the reduced resolution
                scale_x = base_width / dst_width
                scale_y = base_height / dst_height
                dst_transform = base_transform * Affine.scale(scale_x, scale_y)

                # Allocate destination array at target size; use streaming read via rasterio.band()
                dtype_src = np.dtype(src.dtypes[0])
                # Determine a safe nodata value compatible with GDAL; avoid NaN
                if src.nodata is not None:
                    nodata_value = src.nodata
                else:
                    if np.issubdtype(dtype_src, np.floating):
                        nodata_value = -9999.0
                    else:
                        nodata_value = np.iinfo(dtype_src).min
                # Use float32 destination for safe bilinear resampling
                reprojected = np.empty((1, dst_height, dst_width), dtype=np.float32)
                reprojected.fill(nodata_value)

                reproject(
                    source=rasterio.band(src, 1),  # stream from source without loading entire raster
                    destination=reprojected,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.bilinear,
                    src_nodata=src.nodata if src.nodata is not None else nodata_value,
                    dst_nodata=src.nodata if src.nodata is not None else nodata_value
                )

                # Use reprojected data (already downsampled to target size)
                elevation = reprojected[0]
                src_meta = src.meta.copy()
                src_meta.update({
                    'crs': dst_crs,
                    'transform': dst_transform,
                    'width': dst_width,
                    'height': dst_height,
                    'dtype': 'float32',
                    'nodata': nodata_value
                })
                src_transform = dst_transform

                print(f" Reprojected to {dst_crs}: {dst_width} x {dst_height} pixels")
                old_aspect = src.width / src.height
                new_aspect = dst_width / dst_height if dst_height != 0 else old_aspect
                print(f" Aspect ratio: {old_aspect:.2f}:1 -> {new_aspect:.2f}:1")
            else:
                # No reprojection needed; read directly at target size using resampling
                from rasterio.warp import Resampling
                from rasterio import Affine
                # Compute target size preserving aspect ratio
                aspect = src.width / src.height if src.height != 0 else 1.0
                if src.width >= src.height:
                    dst_width = min(target_pixels, src.width)
                    dst_height = max(1, int(round(dst_width / aspect)))
                else:
                    dst_height = min(target_pixels, src.height)
                    dst_width = max(1, int(round(dst_height * aspect)))
                elevation = src.read(1, out_shape=(dst_height, dst_width), resampling=Resampling.bilinear)
                # Update metadata
                scale_x = src.width / dst_width
                scale_y = src.height / dst_height
                src_meta = src.meta.copy()
                src_transform = src.transform * Affine.scale(scale_x, scale_y)
                src_meta.update({
                    'width': dst_width,
                    'height': dst_height,
                    'transform': src_transform
                })

            # Validate elevation range (fail hard on hyperflat)
            from src.validation import validate_elevation_range as _validate_elev_range
            _min, _max, _range, _ok = _validate_elev_range(elevation, min_sensible_range=50.0, warn_only=False)

            # Calculate downsampling factor - PRESERVE ASPECT RATIO
            # At this point, elevation and src_meta reflect the desired (possibly reprojected) target size
            new_height = elevation.shape[0]
            new_width = elevation.shape[1]
            print(f" Target: {new_width} x {new_height} pixels")

            # Update metadata using src_meta (already updated above)
            out_meta = src_meta.copy()

            # Write processed data
            print(f" Writing processed raster...")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(output_path, "w", **out_meta) as dest:
                # Ensure we write a 2D band array
                dest.write(elevation, 1)

        # Create metadata
        source_hash = compute_file_hash(clipped_tif_path)
        metadata = create_processed_metadata(
            output_path,
            region_id=region_id,
            source_file=clipped_tif_path,
            source_file_hash=source_hash,
            target_pixels=target_pixels
        )
        save_metadata(metadata, get_metadata_path(output_path))

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f" Processed: {output_path.name} ({file_size_mb:.1f} MB)")
        return True

    except Exception as e:
        print(f" Processing failed: {e}")
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
    Export processed TIF to JSON format for web viewer.

    Args:
        processed_tif_path: Path to processed TIF
        region_id: Region identifier
        source: Data source (e.g., 'srtm_30m', 'usa_3dep')
        output_path: Where to save JSON
        validate_output: If True, validate aspect ratio and coverage

    Returns:
        True if successful
    """
    # Validate input file first
    if not processed_tif_path.exists():
        print(f" Input file not found: {processed_tif_path}")
        return False

    # Check if output exists and is valid
    if output_path.exists():
        try:
            with open(output_path) as f:
                data = json.load(f)
            # Report absolute path and basic metadata for existing JSON
            try:
                abs_path = str(output_path.resolve())
                w = data.get('width')
                h = data.get('height')
                rid = data.get('region_id')
                src = data.get('source')
                print(f" [JSON] Existing export found: {abs_path}")
                print(f" [JSON] Metadata: region_id={rid}, size={w}x{h}, source={src}")
            except Exception:
                pass

            # Validate required fields
            required_fields = ['region_id', 'width', 'height', 'elevation', 'bounds']
            if all(field in data for field in required_fields):
                if data['width'] > 0 and data['height'] > 0 and len(data['elevation']) > 0:
                    print(f" Already exported (validated): {output_path.name}")
                    return True

            print(f" Existing JSON incomplete or invalid")
            print(f" Deleting and regenerating...")
            output_path.unlink()

        except (json.JSONDecodeError, Exception) as e:
            print(f" Existing JSON corrupted: {e}")
            print(f" Deleting and regenerating...")
            try:
                output_path.unlink()
            except Exception as del_e:
                print(f" Could not delete: {del_e}")

    print(f" Exporting to JSON...")

    try:
        with rasterio.open(processed_tif_path) as src:
            print(f" Reading raster: {src.width} x {src.height}", flush=True)
            elevation = src.read(1)
            bounds = src.bounds

            # Transform bounds to EPSG:4326 (lat/lon) for consistent export
            # The viewer always expects lat/lon bounds regardless of the TIF's CRS
            from rasterio.warp import transform_bounds
            if src.crs and src.crs != 'EPSG:4326':
                print(f" Converting bounds from {src.crs} to EPSG:4326...", flush=True)
                bounds_4326 = transform_bounds(src.crs, 'EPSG:4326',
                    bounds.left, bounds.bottom,
                    bounds.right, bounds.top)
                # transform_bounds returns (left, bottom, right, top)
                from rasterio.coords import BoundingBox
                bounds = BoundingBox(bounds_4326[0], bounds_4326[1],
                    bounds_4326[2], bounds_4326[3])
                print(f" Lat/lon bounds: {bounds.left:.2f}, {bounds.bottom:.2f}, {bounds.right:.2f}, {bounds.top:.2f}", flush=True)

            # VALIDATION: Check aspect ratio and coverage
            if validate_output:
                from src.validation import validate_non_null_coverage
                try:
                    # Only validate data coverage, not aspect ratio
                    # We treat input as uniform 2D grid (square pixels in CRS units)
                    coverage = validate_non_null_coverage(elevation, min_coverage=0.2, warn_only=True)
                    print(f" Validation passed: coverage={coverage*100:.1f}%")
                except Exception as e:
                    print(f" Validation warning: {e}")
                    # Don't fail on validation warnings

            # Filter bad values (nodata, extreme values) BEFORE stats calculation
            # Replace bad values with NaN for proper stats
            # Convert to float first (elevation might be int16/int32)
            elevation_clean = elevation.astype(np.float32)

            # Filter BOTH extreme negatives AND extreme positives (nodata markers)
            # Reasonable elevation range: -500m (below sea level) to +9000m (Mt. Everest is 8849m)
            elevation_clean[(elevation_clean < -500) | (elevation_clean > 9000)] = np.nan

            # Check if we have ANY valid data
            valid_count = np.sum(~np.isnan(elevation_clean))
            if valid_count == 0:
                print(f" Error: No valid elevation data after filtering nodata values", flush=True)
                return False

            # Validate elevation range (fail hard on hyperflat)
            from src.validation import validate_elevation_range as _validate_elev_range
            _min, _max, _range, _ok = _validate_elev_range(elevation_clean, min_sensible_range=50.0, warn_only=False)

            print(f" Valid pixels: {valid_count:,} / {elevation_clean.size:,} ({100*valid_count/elevation_clean.size:.1f}%)", flush=True)

            # Convert to list (handle NaN values)
            print(f" Converting to JSON format...", flush=True)
            elevation_list = []
            for row in elevation_clean:
                row_list = []
                for val in row:
                    if np.isnan(val):  # Filter bad values (already marked as NaN)
                        row_list.append(None)
                    else:
                        row_list.append(float(val))
                elevation_list.append(row_list)

            # VALIDATION: Check aspect ratio before export
            export_aspect = src.width / src.height
            actual_export_aspect = len(elevation_list[0]) / len(elevation_list) if elevation_list else 0
            if abs(actual_export_aspect - export_aspect) > 0.01:
                print(f" WARNING: Aspect ratio mismatch!", flush=True)
                print(f" Expected: {export_aspect:.3f}, Got: {actual_export_aspect:.3f}", flush=True)
                raise ValueError(f"Aspect ratio not preserved for {region_id}")

            # Create export data
            export_data = {
                "version": get_current_version('export'),
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
            print(f" Writing JSON to disk...")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(export_data, f, separators=(',', ':'))

            # Create gzip compressed version for production (Stage 9)
            print(f"[STAGE 9/10] Compressing with gzip...")
            import gzip
            gzip_path = output_path.with_suffix('.json.gz')
            with open(output_path, 'rb') as f_in:
                with gzip.open(gzip_path, 'wb', compresslevel=9) as f_out:
                    f_out.writelines(f_in)

            gzip_size_mb = gzip_path.stat().st_size / (1024 * 1024)
            compression_ratio = (1 - gzip_path.stat().st_size / output_path.stat().st_size) * 100
            print(f" Compressed: {gzip_path.name} ({gzip_size_mb:.1f} MB, {compression_ratio:.1f}% smaller)")

        # Create metadata
        # Note: resolution_meters is not in stats, using 30m default for SRTM data
        # TODO: Calculate actual resolution from bounds and dimensions
        resolution_m = 30  # Default to 30m for SRTM data
        metadata = create_export_metadata(
            output_path,
            region_id=region_id,
            source=source,
            source_file=processed_tif_path,
            resolution_meters=resolution_m
        )
        save_metadata(metadata, get_metadata_path(output_path))

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f" Exported: {output_path.name} ({file_size_mb:.1f} MB)", flush=True)
        print(f" Aspect ratio: {export_aspect:.3f} (validated)", flush=True)
        return True

    except Exception as e:
        import traceback
        print(f" Export failed: {e}", flush=True)
        traceback.print_exc()
        if output_path.exists():
            output_path.unlink()
        return False


def update_regions_manifest(generated_dir: Path) -> bool:
    """
    Update the regions manifest with all available regions.

    Args:
        generated_dir: Directory containing exported JSON files

    Returns:
        True if successful
    """
    print(f" Updating regions manifest...")

    try:
        manifest = {
            "version": get_current_version('export'),
            "regions": {}  # Object/dict, not array!
        }

        # Find all JSON files (excluding manifests, metadata, and borders)
        for json_file in sorted(generated_dir.glob("*.json")):
            if (json_file.stem.endswith('_meta') or
                json_file.stem.endswith('_borders') or
                'manifest' in json_file.stem):
                continue

            try:
                with open(json_file) as f:
                    data = json.load(f)
                # Print absolute path and selected metadata for each region JSON
                try:
                    abs_path = str(json_file.resolve())
                    w = data.get('width')
                    h = data.get('height')
                    rid_meta = data.get('region_id', json_file.stem)
                    src_meta = data.get('source') or data.get('source_file')
                    print(f"  [JSON] Found region export: {abs_path}")
                    print(f"  [JSON] Metadata: region_id={rid_meta}, size={w}x{h}, source={src_meta}")
                except Exception:
                    pass

                # Extract region_id: prefer from JSON, else infer from filename
                # Remove suffixes like "_srtm_30m_4000px_v2" but keep multi-word names
                stem = json_file.stem
                # Known suffixes to strip
                for suffix in ['_srtm_30m_4000px_v2', '_srtm_30m_800px_v2', '_srtm_30m_v2', '_bbox_30m']:
                    if stem.endswith(suffix):
                        stem = stem[:-len(suffix)]
                        break

                region_id = data.get("region_id", stem)

                # ENFORCE: Only include regions declared in centralized config
                try:
                    from src.regions_config import ALL_REGIONS  # local import to avoid heavy import at module load
                except Exception:
                    ALL_REGIONS = {}
                cfg = ALL_REGIONS.get(region_id)
                if not cfg:
                    # Skip anything not explicitly configured (e.g., stray files like 'alps')
                    print(f"  [SKIP] Unknown region not in regions_config: {region_id}")
                    continue

                entry = {
                    "name": data.get("name", region_id.replace('_', ' ').title()),
                    "description": data.get("description", f"{data.get('name', region_id)} elevation data"),
                    "source": data.get("source", "unknown"),
                    "file": str(json_file.name),
                    "bounds": data.get("bounds", {}),
                    "stats": data.get("stats", {})
                }

                # Attach and REQUIRE category from centralized config
                try:
                    category_value = getattr(cfg, 'category', None)
                except Exception:
                    category_value = None
                if not category_value:
                    # Enforce upstream completeness: skip if category is missing
                    print(f"  [SKIP] Region missing category in regions_config: {region_id}")
                    continue
                entry["category"] = category_value

                manifest["regions"][region_id] = entry
            except Exception as e:
                print(f" Skipping {json_file.name}: {e}")
                continue

        # Write manifest (JSON)
        manifest_path = generated_dir / "regions_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        # Also write gzip-compressed version for production servers that serve precompressed assets
        try:
            import gzip
            gzip_path = manifest_path.with_suffix('.json.gz')
            with open(manifest_path, 'rb') as f_in:
                with gzip.open(gzip_path, 'wb', compresslevel=9) as f_out:
                    f_out.writelines(f_in)
        except Exception as gz_err:
            # Do not fail manifest generation if gzip write fails; log warning only
            print(f" Warning: Could not write gzip manifest: {gz_err}")

        print(f" Manifest updated ({len(manifest['regions'])} regions)")
        try:
            print(f" [JSON] Manifest path: {str(manifest_path.resolve())}")
            try:
                print(f" [GZIP] Manifest path: {str(manifest_path.with_suffix('.json.gz').resolve())}")
            except Exception:
                pass
        except Exception:
            pass
        return True

    except Exception as e:
        print(f" Warning: Could not update manifest: {e}")
        return False


def run_pipeline(
    raw_tif_path: Path,
    region_id: str,
    source: str,
    boundary_name: Optional[str] = None,
    boundary_type: str = "country",
    target_pixels: int = 800,
    skip_clip: bool = False,
    border_resolution: str = "10m"
) -> Tuple[bool, Dict]:
    """
    Run the complete data processing pipeline.

    Args:
        raw_tif_path: Path to raw downloaded TIF
        region_id: Region identifier (e.g., 'california')
        source: Data source (e.g., 'srtm_30m', 'usa_3dep')
        boundary_name: Boundary to clip to (optional)
            - If boundary_type="country": "United States of America"
            - If boundary_type="state": "United States of America/Tennessee"
        boundary_type: "country" or "state" (default: "country")
        target_pixels: Target resolution for viewer (default: 800)
        skip_clip: Skip clipping step (use raw data as-is)

    Returns:
        Tuple of (success, result_paths)
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
        "exported": None
    }

    # Define paths
    data_root = Path("data")
    clipped_dir = data_root / "clipped" / source
    processed_dir = data_root / "processed" / source
    generated_dir = Path("generated/regions")

    # [STAGE 4/10] Acquire raw elevation (already done)
    print(f"[STAGE 4/10] Raw data: {raw_tif_path.name}")

    # [STAGE 6/10] Clip to administrative boundary
    if skip_clip or not boundary_name:
        print(f"[STAGE 6/10] Skipping clipping (using raw data)")
        clipped_path = raw_tif_path
    else:
        print(f"[STAGE 6/10] Clipping to {boundary_type} boundary: {boundary_name} ({border_resolution})")
        clipped_path = clipped_dir / f"{region_id}_clipped_{source}_v1.tif"
        try:
            if not clip_to_boundary(raw_tif_path, region_id, boundary_name, clipped_path, source, boundary_type, border_resolution, boundary_required=bool(boundary_name)):
                # Boundary-required regions must not continue without a boundary
                print(f"\n[STAGE 6/10] FAILED: Clipping failed and boundary was required ({boundary_name}).")
                print(f" Aborting pipeline for region '{region_id}'.")
                return False, result_paths
        except PipelineError as e:
            print(f"\n[STAGE 6/10] FAILED: {e}")
            print(f" Aborting pipeline for region '{region_id}'.")
            return False, result_paths

    result_paths["clipped"] = clipped_path

    # [STAGE 7/10] Process/downsample
    print(f"\n[STAGE 7/10] Processing for viewer...")
    processed_path = processed_dir / f"{region_id}_{source}_{target_pixels}px_v2.tif"
    if not downsample_for_viewer(clipped_path, region_id, processed_path, target_pixels):
        return False, result_paths

    result_paths["processed"] = processed_path

    # [STAGE 8/10] Export to JSON (include resolution in filename for cache safety)
    print(f"\n[STAGE 8/10] Exporting to JSON for web viewer...")
    exported_path = generated_dir / f"{region_id}_{source}_{target_pixels}px_v2.json"
    if not export_for_viewer(processed_path, region_id, source, exported_path):
        return False, result_paths

    result_paths["exported"] = exported_path

    # [STAGE 10/10] Update manifest
    print(f"[STAGE 10/10] Updating regions manifest...")
    update_regions_manifest(generated_dir)

    # Success!
    print(f"\n{'='*70}")
    print(f" PIPELINE COMPLETE!")
    print(f"{'='*70}")
    print(f"Region '{region_id}' is ready to view!")
    print(f"\nFiles created:")
    if result_paths["clipped"] != raw_tif_path:
        print(f" Clipped: {result_paths['clipped']}")
    print(f" Processed: {result_paths['processed']}")
    print(f" Exported: {result_paths['exported']}")
    print(f"\nNext steps:")
    print(f" 1. Start viewer: python serve_viewer.py")
    print(f" 2. Open: http://localhost:8001/interactive_viewer_advanced.html")
    print(f" 3. Select '{region_id}' from dropdown")
    print(f"{'='*70}\n")

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

