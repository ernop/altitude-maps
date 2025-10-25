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
import io
from pathlib import Path
from typing import Optional, Dict, Tuple
import json

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

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
    boundary_type: str = "country"
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
    if output_path.exists():
        print(f"      ✅ Already clipped: {output_path.name}")
        return True
    
    print(f"      🔍 Loading {boundary_type} boundary geometry for {boundary_name}...")
    
    # Get boundary geometry based on type
    if boundary_type == "country":
        geometry = get_country_geometry(boundary_name)
    elif boundary_type == "state":
        # Parse "Country/State" format
        if "/" not in boundary_name:
            print(f"      ⚠️  Error: State boundary requires 'Country/State' format")
            print(f"      Got: {boundary_name}")
            return False
        
        country, state = boundary_name.split("/", 1)
        border_manager = get_border_manager()
        state_gdf = border_manager.get_state(country, state)
        
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
            
            # Write clipped data
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
    if output_path.exists():
        print(f"      ✅ Already processed: {output_path.name}")
        return True
    
    print(f"      🔄 Downsampling to {target_pixels}×{target_pixels}...")
    
    try:
        with rasterio.open(clipped_tif_path) as src:
            print(f"      Input: {src.width} × {src.height} pixels")
            
            # Calculate downsampling factor
            max_dim = max(src.height, src.width)
            if max_dim <= target_pixels:
                # No downsampling needed
                print(f"      ℹ️  Already small enough, copying as-is...")
                import shutil
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(clipped_tif_path, output_path)
            else:
                # Downsample
                scale_factor = target_pixels / max_dim
                new_height = int(src.height * scale_factor)
                new_width = int(src.width * scale_factor)
                
                print(f"      Target: {new_width} × {new_height} pixels")
                print(f"      Scale factor: {scale_factor:.3f}x")
                
                # Read and downsample
                print(f"      Reading elevation data...")
                elevation = src.read(1)
                
                # Simple downsampling (could use better resampling later)
                step_y = max(1, src.height // new_height)
                step_x = max(1, src.width // new_width)
                print(f"      Downsampling (step: {step_y}×{step_x})...")
                downsampled = elevation[::step_y, ::step_x]
                
                # Update metadata
                out_meta = src.meta.copy()
                out_meta.update({
                    "height": downsampled.shape[0],
                    "width": downsampled.shape[1],
                    "transform": src.transform * src.transform.scale(
                        src.width / downsampled.shape[1],
                        src.height / downsampled.shape[0]
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
    output_path: Path
) -> bool:
    """
    Export processed TIF to JSON format for web viewer.
    
    Args:
        processed_tif_path: Path to processed TIF
        region_id: Region identifier
        source: Data source (e.g., 'srtm_30m', 'usa_3dep')
        output_path: Where to save JSON
        
    Returns:
        True if successful
    """
    if output_path.exists():
        print(f"      ✅ Already exported: {output_path.name}")
        return True
    
    print(f"      📤 Exporting to JSON...")
    
    try:
        with rasterio.open(processed_tif_path) as src:
            print(f"      Reading raster: {src.width} × {src.height}")
            elevation = src.read(1)
            bounds = src.bounds
            
            # Convert to list (handle NaN values)
            print(f"      Converting to JSON format...")
            elevation_list = []
            for row in elevation:
                row_list = []
                for val in row:
                    if np.isnan(val) or val < -500:  # Filter bad values
                        row_list.append(None)
                    else:
                        row_list.append(float(val))
                elevation_list.append(row_list)
            
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
                    "min": float(np.nanmin(elevation)),
                    "max": float(np.nanmax(elevation)),
                    "mean": float(np.nanmean(elevation))
                }
            }
            
            # Write JSON
            print(f"      Writing JSON to disk...")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(export_data, f, separators=(',', ':'))
            
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
            print(f"      ✅ Exported: {output_path.name} ({file_size_mb:.1f} MB)")
            return True
            
    except Exception as e:
        print(f"      ❌ Export failed: {e}")
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
        
        # Find all JSON files (excluding manifests and metadata)
        for json_file in sorted(generated_dir.glob("*.json")):
            if json_file.stem.endswith('_meta') or 'manifest' in json_file.stem:
                continue
            
            try:
                with open(json_file) as f:
                    data = json.load(f)
                
                region_id = data.get("region_id", json_file.stem.split('_')[0])
                
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
    skip_clip: bool = False
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
        print(f"[2/4] ✂️  Clipping to {boundary_type} boundary: {boundary_name}")
        clipped_path = clipped_dir / f"{region_id}_clipped_{source}_v1.tif"
        if not clip_to_boundary(raw_tif_path, region_id, boundary_name, clipped_path, source, boundary_type):
            print(f"\n⚠️  Clipping failed, using raw data instead")
            clipped_path = raw_tif_path
    
    result_paths["clipped"] = clipped_path
    
    # Step 3: Process/downsample
    print(f"\n[3/4] 🔄 Processing for viewer...")
    processed_path = processed_dir / f"{region_id}_{source}_{target_pixels}px_v2.tif"
    if not downsample_for_viewer(clipped_path, region_id, processed_path, target_pixels):
        return False, result_paths
    
    result_paths["processed"] = processed_path
    
    # Step 4: Export to JSON
    print(f"\n[4/4] 📤 Exporting for web viewer...")
    exported_path = generated_dir / f"{region_id}_{source}_v2.json"
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

