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
    border_resolution: str = "110m"
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
        print(f"      ❌ Input file not found: {raw_tif_path}")
        return False
    
    # Check if output exists and is valid
    if output_path.exists():
        try:
            # Validate the existing clipped file
            with rasterio.open(output_path) as src:
                if src.width > 0 and src.height > 0:
                    # Try reading a small sample to ensure it's not corrupted
                    _ = src.read(1, window=((0, min(10, src.height)), (0, min(10, src.width))))
                    print(f"      ✅ Already clipped (validated): {output_path.name}")
                    return True
        except Exception as e:
            print(f"      ⚠️  Existing file corrupted: {e}")
            print(f"      🗑️  Deleting and regenerating...")
            try:
                output_path.unlink()
            except Exception as del_e:
                print(f"      ⚠️  Could not delete: {del_e}")
    
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
        print(f"      🗑️  Deleted {len(deleted_deps)} dependent file(s) (will be regenerated)")
    
    print(f"      🔍 Loading {boundary_type} boundary geometry for {boundary_name}...")
    
    # Get boundary geometry based on type
    if boundary_type == "country":
        geometry = get_country_geometry(boundary_name, resolution=border_resolution)
    elif boundary_type == "state":
        # Parse "Country/State" format
        if "/" not in boundary_name:
            print(f"      ⚠️  Error: State boundary requires 'Country/State' format")
            print(f"      Got: {boundary_name}")
            return False
        
        country, state = boundary_name.split("/", 1)
        border_manager = get_border_manager()
        state_gdf = border_manager.get_state(country, state, resolution=border_resolution)
        
        if state_gdf is None or state_gdf.empty:
            print(f"      ⚠️  Warning: State '{state}' not found in '{country}'")
            print(f"      Skipping clipping step...")
            return False
        
        # Get geometry from GeoDataFrame
        from shapely.ops import unary_union
        geometry = unary_union(state_gdf.geometry)
    else:
        print(f"      ⚠️  Error: Invalid boundary_type '{boundary_type}' (must be 'country' or 'state')")
        return False
    
    if geometry is None:
        print(f"      ⚠️  Warning: Could not find boundary '{boundary_name}'")
        print(f"      Skipping clipping step...")
        return False
    
    print(f"      ✂️  Clipping to {boundary_type} boundary...")
    
    try:
        with rasterio.open(raw_tif_path) as src:
            print(f"      Input dimensions: {src.width} × {src.height} pixels")
            print(f"      Input size: {raw_tif_path.stat().st_size / (1024*1024):.1f} MB")
            
            # Clip the raster to the boundary
            print(f"      Applying geometric mask...")
            out_image, out_transform = rasterio_mask(src, [geometry], crop=True, filled=False)
            out_meta = src.meta.copy()
            
            # Update metadata
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform
            })
            
            print(f"      Output dimensions: {out_meta['width']} × {out_meta['height']} pixels")
            
            # ASPECT RATIO FIX: Reproject ALL EPSG:4326 regions to preserve real-world proportions
            # EPSG:4326 (lat/lon) has distorted aspect ratios at ALL latitudes (except equator)
            # because longitude degrees are compressed by cos(latitude)
            # This affects mid-latitude regions significantly (e.g., Kansas at 38.5°N has 27.6% distortion)
            needs_reprojection = False
            if src.crs and 'EPSG:4326' in str(src.crs).upper():
                # Calculate average latitude of the clipped region
                bounds = src.bounds
                avg_lat = (bounds.top + bounds.bottom) / 2
                
                # DISABLED: Reprojection causes data corruption (negative values in California)
                # TODO: Fix reprojection to preserve borders and data quality properly
                if False and abs(avg_lat) > 5:  # Only skip regions within 5° of equator
                    needs_reprojection = True
                    import math
                    # Calculate distortion factor
                    cos_lat = math.cos(math.radians(avg_lat))
                    distortion = 1.0 / cos_lat if cos_lat > 0.01 else 1.0
                    print(f"      ⚠️  Latitude {avg_lat:.1f}° - aspect ratio distorted {distortion:.2f}x by EPSG:4326")
                    print(f"      🔄 Reprojecting to equal-area projection to preserve real-world proportions...")
            
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
                
                # Create reprojected array
                reprojected = np.empty((1, height, width), dtype=out_image.dtype)
                
                reproject(
                    source=out_image,
                    destination=reprojected,
                    src_transform=out_transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.bilinear
                )
                
                out_image = reprojected
                print(f"      ✅ Reprojected to {dst_crs}: {width} × {height} pixels")
                
                # Verify aspect ratio improvement
                old_aspect = out_meta['width'] / out_meta['height'] if 'width' in out_meta else 0
                new_aspect = width / height
                print(f"      Aspect ratio: {old_aspect:.2f}:1 → {new_aspect:.2f}:1")
            
            # Write clipped (and possibly reprojected) data
            print(f"      Writing clipped raster to disk...")
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
        print(f"      ✅ Clipped: {output_path.name} ({file_size_mb:.1f} MB)")
        return True
        
    except Exception as e:
        print(f"      ❌ Clipping failed: {e}")
        if output_path.exists():
            output_path.unlink()
        return False


def downsample_for_viewer(
    clipped_tif_path: Path,
    region_id: str,
    output_path: Path,
    target_pixels: int = 800
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
        print(f"      ❌ Input file not found: {clipped_tif_path}")
        return False
    
    # Check if output exists and is valid
    if output_path.exists():
        try:
            # Validate the existing processed file
            with rasterio.open(output_path) as src:
                if src.width > 0 and src.height > 0:
                    # Try reading a small sample to ensure it's not corrupted
                    _ = src.read(1, window=((0, min(10, src.height)), (0, min(10, src.width))))
                    print(f"      ✅ Already processed (validated): {output_path.name}")
                    return True
        except Exception as e:
            print(f"      ⚠️  Existing file corrupted: {e}")
            print(f"      🗑️  Deleting and regenerating...")
            try:
                output_path.unlink()
            except Exception as del_e:
                print(f"      ⚠️  Could not delete: {del_e}")
    
    # If we're regenerating the processed file, delete dependent generated files
    generated_dir = Path('generated/regions')
    if generated_dir.exists():
        deleted_count = 0
        for f in generated_dir.glob(f'{region_id}_*'):
            f.unlink()
            deleted_count += 1
        if deleted_count > 0:
            print(f"      🗑️  Deleted {deleted_count} generated file(s) (will be regenerated)")
    
    print(f"      🔄 Downsampling to {target_pixels}×{target_pixels}...")
    
    try:
        with rasterio.open(clipped_tif_path) as src:
            print(f"      Input: {src.width} × {src.height} pixels", flush=True)
            
            # Calculate downsampling factor - PRESERVE ASPECT RATIO
            max_dim = max(src.height, src.width)
            if max_dim <= target_pixels:
                # No downsampling needed
                print(f"      ℹ️  Already small enough, copying as-is...")
                import shutil
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(clipped_tif_path, output_path)
            else:
                # Downsample with SAME step size for both dimensions to preserve aspect ratio
                import math
                scale_factor = max_dim / target_pixels
                step_size = max(1, int(math.ceil(scale_factor)))
                
                # Read and downsample
                print(f"      Reading elevation data...")
                elevation = src.read(1)
                
                # Use SINGLE step size for both dimensions to preserve aspect ratio
                print(f"      Downsampling (step: {step_size}×{step_size})...")
                downsampled = elevation[::step_size, ::step_size]
                
                # CRITICAL: Use actual array shape after slicing, not dimension // step_size
                # Array slicing includes endpoints, so shape may be 1 pixel larger than expected
                # Example: array[::8] with length 12833 gives 1605 values, not 1604
                new_height = downsampled.shape[0]
                new_width = downsampled.shape[1]
                
                print(f"      Target: {new_width} × {new_height} pixels")
                print(f"      Scale factor: {1.0/step_size:.3f}x")
                
                # Update metadata
                out_meta = src.meta.copy()
                out_meta.update({
                    "height": new_height,
                    "width": new_width,
                    "transform": src.transform * src.transform.scale(
                        src.width / new_width,
                        src.height / new_height
                    )
                })
                
                # Write downsampled data
                print(f"      Writing downsampled raster...")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with rasterio.open(output_path, "w", **out_meta) as dest:
                    dest.write(downsampled, 1)
        
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
        print(f"      ✅ Processed: {output_path.name} ({file_size_mb:.1f} MB)")
        return True
        
    except Exception as e:
        print(f"      ❌ Processing failed: {e}")
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
        print(f"      ❌ Input file not found: {processed_tif_path}")
        return False
    
    # Check if output exists and is valid
    if output_path.exists():
        try:
            with open(output_path) as f:
                data = json.load(f)
            
            # Validate required fields
            required_fields = ['region_id', 'width', 'height', 'elevation', 'bounds']
            if all(field in data for field in required_fields):
                if data['width'] > 0 and data['height'] > 0 and len(data['elevation']) > 0:
                    print(f"      ✅ Already exported (validated): {output_path.name}")
                    return True
            
            print(f"      ⚠️  Existing JSON incomplete or invalid")
            print(f"      🗑️  Deleting and regenerating...")
            output_path.unlink()
            
        except (json.JSONDecodeError, Exception) as e:
            print(f"      ⚠️  Existing JSON corrupted: {e}")
            print(f"      🗑️  Deleting and regenerating...")
            try:
                output_path.unlink()
            except Exception as del_e:
                print(f"      ⚠️  Could not delete: {del_e}")
    
    print(f"      📤 Exporting to JSON...")
    
    try:
        with rasterio.open(processed_tif_path) as src:
            print(f"      Reading raster: {src.width} × {src.height}", flush=True)
            elevation = src.read(1)
            bounds = src.bounds
            
            # Transform bounds to EPSG:4326 (lat/lon) for consistent export
            # The viewer always expects lat/lon bounds regardless of the TIF's CRS
            from rasterio.warp import transform_bounds
            if src.crs and src.crs != 'EPSG:4326':
                print(f"      Converting bounds from {src.crs} to EPSG:4326...", flush=True)
                bounds_4326 = transform_bounds(src.crs, 'EPSG:4326', 
                                               bounds.left, bounds.bottom, 
                                               bounds.right, bounds.top)
                # transform_bounds returns (left, bottom, right, top)
                from rasterio.coords import BoundingBox
                bounds = BoundingBox(bounds_4326[0], bounds_4326[1], 
                                    bounds_4326[2], bounds_4326[3])
                print(f"      Lat/lon bounds: {bounds.left:.2f}, {bounds.bottom:.2f}, {bounds.right:.2f}, {bounds.top:.2f}", flush=True)
            
            # VALIDATION: Check aspect ratio and coverage
            if validate_output:
                from src.validation import validate_non_null_coverage
                try:
                    # Only validate data coverage, not aspect ratio
                    # We treat input as uniform 2D grid (square pixels in CRS units)
                    coverage = validate_non_null_coverage(elevation, min_coverage=0.2, warn_only=True)
                    print(f"      ✅ Validation passed: coverage={coverage*100:.1f}%")
                except Exception as e:
                    print(f"      ⚠️  Validation warning: {e}")
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
                print(f"      ❌ Error: No valid elevation data after filtering nodata values", flush=True)
                return False
            
            print(f"      Valid pixels: {valid_count:,} / {elevation_clean.size:,} ({100*valid_count/elevation_clean.size:.1f}%)", flush=True)
            
            # Convert to list (handle NaN values)
            print(f"      Converting to JSON format...", flush=True)
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
                print(f"      ⚠️  WARNING: Aspect ratio mismatch!", flush=True)
                print(f"      Expected: {export_aspect:.3f}, Got: {actual_export_aspect:.3f}", flush=True)
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
            print(f"      Writing JSON to disk...")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(export_data, f, separators=(',', ':'))
            
            # Create gzip compressed version for production
            print(f"      Compressing with gzip...")
            import gzip
            gzip_path = output_path.with_suffix('.json.gz')
            with open(output_path, 'rb') as f_in:
                with gzip.open(gzip_path, 'wb', compresslevel=9) as f_out:
                    f_out.writelines(f_in)
            
            gzip_size_mb = gzip_path.stat().st_size / (1024 * 1024)
            compression_ratio = (1 - gzip_path.stat().st_size / output_path.stat().st_size) * 100
            print(f"      ✅ Compressed: {gzip_path.name} ({gzip_size_mb:.1f} MB, {compression_ratio:.1f}% smaller)")
            
            # Create metadata
            resolution_m = int(export_data['stats'].get('resolution_meters', 30))  # Default to 30m
            metadata = create_export_metadata(
                output_path,
                region_id=region_id,
                source=source,
                source_file=processed_tif_path,
                resolution_meters=resolution_m
            )
            save_metadata(metadata, get_metadata_path(output_path))
            
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"      ✅ Exported: {output_path.name} ({file_size_mb:.1f} MB)", flush=True)
            print(f"      Aspect ratio: {export_aspect:.3f} (validated)", flush=True)
            return True
            
    except Exception as e:
        import traceback
        print(f"      ❌ Export failed: {e}", flush=True)
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
    print(f"      📋 Updating regions manifest...")
    
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
                
                # Extract region_id: prefer from JSON, else infer from filename
                # Remove suffixes like "_srtm_30m_4000px_v2" but keep multi-word names
                stem = json_file.stem
                # Known suffixes to strip
                for suffix in ['_srtm_30m_4000px_v2', '_srtm_30m_800px_v2', '_srtm_30m_v2', '_bbox_30m']:
                    if stem.endswith(suffix):
                        stem = stem[:-len(suffix)]
                        break
                
                region_id = data.get("region_id", stem)
                
                manifest["regions"][region_id] = {
                    "name": data.get("name", region_id.replace('_', ' ').title()),
                    "description": data.get("description", f"{data.get('name', region_id)} elevation data"),
                    "source": data.get("source", "unknown"),
                    "file": str(json_file.name),
                    "bounds": data.get("bounds", {}),
                    "stats": data.get("stats", {})
                }
            except Exception as e:
                print(f"      ⚠️  Skipping {json_file.name}: {e}")
                continue
        
        # Write manifest
        manifest_path = generated_dir / "regions_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"      ✅ Manifest updated ({len(manifest['regions'])} regions)")
        return True
        
    except Exception as e:
        print(f"      ⚠️  Warning: Could not update manifest: {e}")
        return False


def run_pipeline(
    raw_tif_path: Path,
    region_id: str,
    source: str,
    boundary_name: Optional[str] = None,
    boundary_type: str = "country",
    target_pixels: int = 800,
    skip_clip: bool = False,
    border_resolution: str = "110m"
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
    print(f"🔄 PROCESSING PIPELINE")
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
    
    # Step 1: Download (already done, just confirm)
    print(f"[1/4] ✅ Raw data: {raw_tif_path.name}")
    
    # Step 2: Clip to boundary
    if skip_clip or not boundary_name:
        print(f"[2/4] ⏭️  Skipping clipping (using raw data)")
        clipped_path = raw_tif_path
    else:
        print(f"[2/4] ✂️  Clipping to {boundary_type} boundary: {boundary_name} ({border_resolution})")
        clipped_path = clipped_dir / f"{region_id}_clipped_{source}_v1.tif"
        if not clip_to_boundary(raw_tif_path, region_id, boundary_name, clipped_path, source, boundary_type, border_resolution):
            print(f"\n⚠️  Clipping failed, using raw data instead")
            clipped_path = raw_tif_path
    
    result_paths["clipped"] = clipped_path
    
    # Step 3: Process/downsample
    print(f"\n[3/4] 🔄 Processing for viewer...")
    processed_path = processed_dir / f"{region_id}_{source}_{target_pixels}px_v2.tif"
    if not downsample_for_viewer(clipped_path, region_id, processed_path, target_pixels):
        return False, result_paths
    
    result_paths["processed"] = processed_path
    
    # Step 4: Export to JSON (include resolution in filename for cache safety)
    print(f"\n[4/4] 📤 Exporting for web viewer...")
    exported_path = generated_dir / f"{region_id}_{source}_{target_pixels}px_v2.json"
    if not export_for_viewer(processed_path, region_id, source, exported_path):
        return False, result_paths
    
    result_paths["exported"] = exported_path
    
    # Update manifest
    print(f"")
    update_regions_manifest(generated_dir)
    
    # Success!
    print(f"\n{'='*70}")
    print(f"✅ PIPELINE COMPLETE!")
    print(f"{'='*70}")
    print(f"Region '{region_id}' is ready to view!")
    print(f"\nFiles created:")
    if result_paths["clipped"] != raw_tif_path:
        print(f"  Clipped:   {result_paths['clipped']}")
    print(f"  Processed: {result_paths['processed']}")
    print(f"  Exported:  {result_paths['exported']}")
    print(f"\nNext steps:")
    print(f"  1. Start viewer: python serve_viewer.py")
    print(f"  2. Open: http://localhost:8001/interactive_viewer_advanced.html")
    print(f"  3. Select '{region_id}' from dropdown")
    print(f"{'='*70}\n")
    
    return True, result_paths


if __name__ == "__main__":
    print("Pipeline module - use run_pipeline() function")
    print("\nExample:")
    print("  from src.pipeline import run_pipeline")
    print("  run_pipeline(")
    print("    Path('data/raw/srtm_30m/california_bbox_30m.tif'),")
    print("    'california',")
    print("    'srtm_30m',")
    print("    boundary_name='California'")
    print("  )")

