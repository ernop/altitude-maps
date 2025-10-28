"""
Comprehensive diagnostic for a region's data through the entire pipeline.

Usage:
    python check_region.py ohio
    python check_region.py kentucky --verbose
    python check_region.py tennessee --raw-only
"""
import sys
import json
from pathlib import Path
import argparse

try:
    import rasterio
    import numpy as np
except ImportError:
    print("❌ Missing dependencies. Activate venv first:")
    print("   .\\venv\\Scripts\\Activate.ps1")
    sys.exit(1)


def format_size(bytes_size):
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def check_raw_file(region_id, verbose=False):
    """Check raw source file."""
    print("\n" + "="*70)
    print("📦 RAW FILE CHECK")
    print("="*70)
    
    # Find raw file
    possible_locations = [
        Path(f"data/raw/srtm_30m/{region_id}_bbox_30m.tif"),
        Path(f"data/regions/{region_id}.tif"),
        Path(f"data/raw/usa_3dep/{region_id}_3dep_10m.tif"),
    ]
    
    raw_path = None
    for path in possible_locations:
        if path.exists():
            raw_path = path
            break
    
    if not raw_path:
        print("❌ Raw file not found!")
        print("   Looked in:")
        for path in possible_locations:
            print(f"     - {path}")
        return False
    
    print(f"✅ Found: {raw_path}")
    
    with rasterio.open(raw_path) as ds:
        data = ds.read(1)
        valid = ~np.isnan(data) & (data > -500)
        valid_pct = np.sum(valid) / data.size * 100
        
        print(f"   Dimensions: {ds.width} × {ds.height} pixels")
        print(f"   CRS: {ds.crs}")
        print(f"   Bounds: {ds.bounds}")
        print(f"   Pixel size: {ds.transform[0]:.10f} × {abs(ds.transform[4]):.10f} degrees")
        print(f"   File size: {format_size(raw_path.stat().st_size)}")
        print(f"   Valid data: {valid_pct:.1f}%")
        
        if valid_pct < 90:
            print(f"   ⚠️  Low valid data - may already be clipped/masked")
        
        if verbose:
            print(f"   Elevation range: {np.nanmin(data):.1f}m to {np.nanmax(data):.1f}m")
            print(f"   Total pixels: {data.size:,}")
    
    return True


def check_clipped_file(region_id, verbose=False):
    """Check clipped file."""
    print("\n" + "="*70)
    print("✂️  CLIPPED FILE CHECK")
    print("="*70)
    
    # Find clipped file
    possible_locations = [
        Path(f"data/clipped/srtm_30m/{region_id}_clipped_srtm_30m_v1.tif"),
        Path(f"data/clipped/usa_3dep/{region_id}_clipped_usa_3dep_v1.tif"),
    ]
    
    clipped_path = None
    for path in possible_locations:
        if path.exists():
            clipped_path = path
            break
    
    if not clipped_path:
        print("⚠️  Clipped file not found - needs processing")
        print("   Run: python reprocess_existing_states.py --states", region_id)
        return False
    
    print(f"✅ Found: {clipped_path}")
    
    with rasterio.open(clipped_path) as ds:
        data = ds.read(1)
        valid = ~np.isnan(data) & (data > -500)
        valid_pct = np.sum(valid) / data.size * 100
        
        print(f"   Dimensions: {ds.width} × {ds.height} pixels")
        print(f"   Bounds: {ds.bounds}")
        print(f"   File size: {format_size(clipped_path.stat().st_size)}")
        print(f"   Valid data: {valid_pct:.1f}%")
        
        # Check for all-empty edges
        all_empty_rows_top = 0
        for i in range(min(100, ds.height)):
            if np.sum(valid[i, :]) == 0:
                all_empty_rows_top += 1
            else:
                break
        
        all_empty_rows_bottom = 0
        for i in range(ds.height - 1, max(ds.height - 101, -1), -1):
            if np.sum(valid[i, :]) == 0:
                all_empty_rows_bottom += 1
            else:
                break
        
        all_empty_cols_left = 0
        for j in range(min(100, ds.width)):
            if np.sum(valid[:, j]) == 0:
                all_empty_cols_left += 1
            else:
                break
        
        all_empty_cols_right = 0
        for j in range(ds.width - 1, max(ds.width - 101, -1), -1):
            if np.sum(valid[:, j]) == 0:
                all_empty_cols_right += 1
            else:
                break
        
        total_empty_edges = all_empty_rows_top + all_empty_rows_bottom + all_empty_cols_left + all_empty_cols_right
        
        if total_empty_edges > 0:
            print(f"   ❌ crop=True FAILED: {total_empty_edges} all-empty rows/cols remain")
            print(f"      Top: {all_empty_rows_top}, Bottom: {all_empty_rows_bottom}")
            print(f"      Left: {all_empty_cols_left}, Right: {all_empty_cols_right}")
        else:
            print(f"   ✅ Cropping effective - no all-empty edges")
        
        # Check edge sparseness
        if total_empty_edges == 0:
            top_edge_valid = np.sum(valid[0, :]) / ds.width * 100
            bottom_edge_valid = np.sum(valid[-1, :]) / ds.width * 100
            left_edge_valid = np.sum(valid[:, 0]) / ds.height * 100
            right_edge_valid = np.sum(valid[:, -1]) / ds.height * 100
            
            print(f"   Edge coverage: T:{top_edge_valid:.0f}% B:{bottom_edge_valid:.0f}% "
                  f"L:{left_edge_valid:.0f}% R:{right_edge_valid:.0f}%")
            
            if min(top_edge_valid, bottom_edge_valid, left_edge_valid, right_edge_valid) < 10:
                print(f"   ℹ️  Sparse edges normal for irregular boundaries")
        
        if verbose:
            print(f"   Elevation range: {np.nanmin(data):.1f}m to {np.nanmax(data):.1f}m")
    
    return True


def check_processed_file(region_id, verbose=False):
    """Check processed/downsampled file."""
    print("\n" + "="*70)
    print("🔄 PROCESSED FILE CHECK")
    print("="*70)
    
    # Find processed files
    processed_dir = Path("data/processed")
    processed_files = list(processed_dir.rglob(f"{region_id}_*.tif"))
    
    if not processed_files:
        print("⚠️  No processed files found - needs processing")
        print("   Run: python reprocess_existing_states.py --states", region_id)
        return False
    
    for proc_path in processed_files:
        print(f"\n✅ Found: {proc_path}")
        
        with rasterio.open(proc_path) as ds:
            data = ds.read(1)
            valid = ~np.isnan(data) & (data > -500)
            valid_pct = np.sum(valid) / data.size * 100
            
            print(f"   Dimensions: {ds.width} × {ds.height} pixels")
            print(f"   Aspect ratio: {ds.width/ds.height:.3f}")
            print(f"   File size: {format_size(proc_path.stat().st_size)}")
            print(f"   Valid data: {valid_pct:.1f}%")
            
            if verbose:
                print(f"   Elevation range: {np.nanmin(data):.1f}m to {np.nanmax(data):.1f}m")
                print(f"   Total pixels: {data.size:,}")
    
    return True


def check_generated_json(region_id, verbose=False):
    """Check generated JSON files."""
    print("\n" + "="*70)
    print("📤 GENERATED JSON CHECK")
    print("="*70)
    
    generated_dir = Path("generated/regions")
    json_files = list(generated_dir.glob(f"{region_id}_*.json"))
    
    # Filter out borders and meta files
    json_files = [f for f in json_files if '_borders' not in f.stem and '_meta' not in f.stem]
    
    if not json_files:
        print("⚠️  No JSON exports found - needs export")
        print("   Run: python reprocess_existing_states.py --states", region_id)
        return False
    
    for json_path in json_files:
        print(f"\n✅ Found: {json_path}")
        print(f"   File size: {format_size(json_path.stat().st_size)}")
        
        with open(json_path) as f:
            data = json.load(f)
        
        print(f"   Name: {data.get('name', 'N/A')}")
        print(f"   Format version: {data.get('version', 'N/A')}")
        print(f"   Dimensions: {data['width']} × {data['height']}")
        print(f"   Aspect ratio: {data['width']/data['height']:.3f}")
        print(f"   Source: {data.get('source', 'N/A')}")
        
        if 'bounds' in data:
            bounds = data['bounds']
            print(f"   Bounds: ({bounds['left']:.2f}, {bounds['bottom']:.2f}) to "
                  f"({bounds['right']:.2f}, {bounds['top']:.2f})")
        
        if 'stats' in data:
            stats = data['stats']
            print(f"   Elevation: {stats.get('min', 0):.1f}m to {stats.get('max', 0):.1f}m "
                  f"(mean: {stats.get('mean', 0):.1f}m)")
        
        # Count valid pixels
        if 'elevation' in data:
            elevation_data = data['elevation']
            total_pixels = data['width'] * data['height']
            valid_pixels = sum(1 for row in elevation_data for val in row if val is not None)
            valid_pct = valid_pixels / total_pixels * 100
            print(f"   Valid pixels: {valid_pixels:,} / {total_pixels:,} ({valid_pct:.1f}%)")
        
        if verbose and 'exported_at' in data:
            print(f"   Exported: {data['exported_at']}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Check region data through entire pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python check_region.py ohio
  python check_region.py kentucky --verbose
  python check_region.py tennessee --raw-only
        """
    )
    parser.add_argument('region_id', help='Region ID (e.g., ohio, kentucky)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed information')
    parser.add_argument('--raw-only', action='store_true',
                       help='Only check raw file')
    parser.add_argument('--no-unicode', action='store_true',
                       help='Disable Unicode output for compatibility')
    
    args = parser.parse_args()
    region_id = args.region_id.lower()
    
    print("="*70)
    print(f"🔍 REGION DATA CHECK: {region_id.upper()}")
    print("="*70)
    
    # Check each stage
    raw_ok = check_raw_file(region_id, args.verbose)
    
    if args.raw_only:
        return 0 if raw_ok else 1
    
    clipped_ok = check_clipped_file(region_id, args.verbose)
    processed_ok = check_processed_file(region_id, args.verbose)
    json_ok = check_generated_json(region_id, args.verbose)
    
    # Summary
    print("\n" + "="*70)
    print("📋 SUMMARY")
    print("="*70)
    
    stages = [
        ("Raw file", raw_ok),
        ("Clipped file", clipped_ok),
        ("Processed file", processed_ok),
        ("JSON export", json_ok),
    ]
    
    for stage_name, stage_ok in stages:
        status = "✅" if stage_ok else "❌"
        print(f"  {status} {stage_name}")
    
    all_ok = all(ok for _, ok in stages)
    
    if all_ok:
        print("\n✅ All pipeline stages present and valid!")
        print("\nNext steps:")
        print("  1. Start viewer: python serve_viewer.py")
        print(f"  2. Visit: http://localhost:8001/interactive_viewer_advanced.html")
        print(f"  3. Select '{region_id}' from dropdown")
    else:
        print("\n⚠️  Some stages missing or need regeneration")
        print("\nTo fix:")
        print(f"  python reprocess_existing_states.py --target-pixels 2048 --states {region_id}")
    
    print("="*70)
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

