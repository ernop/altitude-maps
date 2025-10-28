"""
One command to ensure a region is ready to view.

Downloads if needed, processes if needed, checks if everything is valid.

Usage:
    python ensure_region.py ohio
    python ensure_region.py tennessee --target-pixels 4096
    python ensure_region.py california --force-reprocess
"""
import sys
import io
import argparse
from pathlib import Path

# Fix Windows console encoding for emoji/Unicode
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (AttributeError, ValueError):
        pass


def check_venv():
    """Ensure we're running in the virtual environment."""
    # Check if we're in a venv
    in_venv = (hasattr(sys, 'real_prefix') or 
               (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))
    
    if not in_venv:
        print("\n" + "="*70)
        print("❌ ERROR: Not running in virtual environment!")
        print("="*70)
        print("\nYou must activate the virtual environment first:")
        if sys.platform == 'win32':
            print("  .\\venv\\Scripts\\Activate.ps1    # PowerShell")
            print("  .\\venv\\Scripts\\activate.bat    # Command Prompt")
        else:
            print("  source venv/bin/activate")
        print("\nOr run the setup script:")
        print("  .\\setup.ps1    # Windows")
        print("  ./setup.sh     # Linux/Mac")
        print("="*70 + "\n")
        sys.exit(1)


def validate_geotiff(file_path: Path, check_data: bool = False) -> bool:
    """
    Rigorously validate a GeoTIFF file.
    
    Args:
        file_path: Path to TIF file
        check_data: If True, validate data contents (slower, optional)
        
    Returns:
        True if file is valid, False otherwise
    """
    if not file_path.exists():
        return False
    
    # Check file size - must be > 1KB (corrupted downloads are often 0 bytes)
    file_size = file_path.stat().st_size
    if file_size < 1024:
        print(f"      ⚠️  File too small ({file_size} bytes), likely corrupted", flush=True)
        return False
    
    try:
        import rasterio
        with rasterio.open(file_path) as src:
            # Basic checks
            if src.width == 0 or src.height == 0:
                print(f"      ⚠️  Invalid dimensions: {src.width}×{src.height}", flush=True)
                return False
            
            # Check that CRS and transform exist
            if src.crs is None or src.transform is None:
                print(f"      ⚠️  Missing CRS or transform", flush=True)
                return False
            
            if check_data:
                # Try to read a small sample to verify data accessibility
                try:
                    sample_height = min(100, src.height)
                    sample_width = min(100, src.width)
                    data = src.read(1, window=((0, sample_height), (0, sample_width)))
                    # Check for any non-null data in the sample
                    import numpy as np
                    valid_count = np.sum(~np.isnan(data.astype(float)) & (data > -500))
                    if valid_count == 0:
                        print(f"      ⚠️  No valid elevation data in sample", flush=True)
                        return False
                except Exception as e:
                    # Data read failed, but file structure is valid
                    # Allow it to pass - the pipeline will handle read errors
                    print(f"      ⚠️  Warning: Could not verify data sample: {e}", flush=True)
            
            return True
            
    except Exception as e:
        print(f"      ⚠️  Not a valid GeoTIFF: {e}", flush=True)
        return False


def validate_json_export(file_path: Path) -> bool:
    """
    Validate an exported JSON file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        True if file is valid, False otherwise
    """
    if not file_path.exists():
        return False
    
    # Check file size
    file_size = file_path.stat().st_size
    if file_size < 1024:
        print(f"      ⚠️  JSON too small ({file_size} bytes), likely incomplete")
        return False
    
    try:
        import json
        with open(file_path) as f:
            data = json.load(f)
        
        # Validate required fields
        required_fields = ['region_id', 'width', 'height', 'elevation', 'bounds']
        for field in required_fields:
            if field not in data:
                print(f"      ⚠️  Missing required field: {field}")
                return False
        
        # Validate dimensions
        if data['width'] <= 0 or data['height'] <= 0:
            print(f"      ⚠️  Invalid dimensions: {data['width']}×{data['height']}")
            return False
        
        # Validate elevation data structure
        elevation = data['elevation']
        if not isinstance(elevation, list) or len(elevation) == 0:
            print(f"      ⚠️  Invalid elevation data structure")
            return False
        
        # Check that elevation matches dimensions
        if len(elevation) != data['height']:
            print(f"      ⚠️  Elevation height mismatch: {len(elevation)} != {data['height']}")
            return False
        
        if len(elevation[0]) != data['width']:
            print(f"      ⚠️  Elevation width mismatch: {len(elevation[0])} != {data['width']}")
            return False
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"      ⚠️  Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"      ⚠️  Validation error: {e}")
        return False


# State name mapping
STATE_NAMES = {
    'alabama': 'Alabama', 'arizona': 'Arizona', 'arkansas': 'Arkansas',
    'california': 'California', 'colorado': 'Colorado', 'connecticut': 'Connecticut',
    'delaware': 'Delaware', 'florida': 'Florida', 'georgia': 'Georgia',
    'idaho': 'Idaho', 'illinois': 'Illinois', 'indiana': 'Indiana',
    'iowa': 'Iowa', 'kansas': 'Kansas', 'kentucky': 'Kentucky',
    'louisiana': 'Louisiana', 'maine': 'Maine', 'maryland': 'Maryland',
    'massachusetts': 'Massachusetts', 'michigan': 'Michigan', 'minnesota': 'Minnesota',
    'mississippi': 'Mississippi', 'missouri': 'Missouri', 'montana': 'Montana',
    'nebraska': 'Nebraska', 'nevada': 'Nevada', 'new_hampshire': 'New Hampshire',
    'new_jersey': 'New Jersey', 'new_mexico': 'New Mexico', 'new_york': 'New York',
    'north_carolina': 'North Carolina', 'north_dakota': 'North Dakota',
    'ohio': 'Ohio', 'oklahoma': 'Oklahoma', 'oregon': 'Oregon',
    'pennsylvania': 'Pennsylvania', 'rhode_island': 'Rhode Island',
    'south_carolina': 'South Carolina', 'south_dakota': 'South Dakota',
    'tennessee': 'Tennessee', 'texas': 'Texas', 'utah': 'Utah',
    'vermont': 'Vermont', 'virginia': 'Virginia', 'washington': 'Washington',
    'west_virginia': 'West Virginia', 'wisconsin': 'Wisconsin', 'wyoming': 'Wyoming'
}


def find_raw_file(region_id):
    """
    Find and validate raw file for a region.
    
    Returns:
        Tuple of (path, source) if valid file found, (None, None) otherwise
    """
    possible_locations = [
        Path(f"data/raw/srtm_30m/{region_id}_bbox_30m.tif"),
        Path(f"data/regions/{region_id}.tif"),
        Path(f"data/raw/usa_3dep/{region_id}_3dep_10m.tif"),
    ]
    
    for path in possible_locations:
        if path.exists():
            print(f"   🔍 Checking {path.name}...", flush=True)
            if validate_geotiff(path, check_data=False):  # Structure check only, pipeline will validate data
                print(f"      ✅ Valid GeoTIFF (structure)", flush=True)
                return path, get_source_from_path(path)
            else:
                print(f"      ❌ Invalid or corrupted, cleaning up...", flush=True)
                try:
                    path.unlink()
                    print(f"      🗑️  Deleted corrupted file", flush=True)
                except Exception as e:
                    print(f"      ⚠️  Could not delete: {e}", flush=True)
    
    return None, None


def get_source_from_path(path):
    """Determine source type from path."""
    if 'usa_3dep' in str(path):
        return 'usa_3dep'
    return 'srtm_30m'


def check_pipeline_complete(region_id):
    """
    Check if all pipeline stages are complete and valid.
    
    Returns:
        True if valid JSON export exists, False otherwise
    """
    # Check for JSON export (final stage)
    generated_dir = Path("generated/regions")
    if not generated_dir.exists():
        return False
    
    json_files = list(generated_dir.glob(f"{region_id}_*.json"))
    json_files = [f for f in json_files if '_borders' not in f.stem and '_meta' not in f.stem]
    
    if len(json_files) == 0:
        return False
    
    # Validate the JSON files
    for json_file in json_files:
        print(f"   🔍 Checking {json_file.name}...", flush=True)
        if validate_json_export(json_file):
            print(f"      ✅ Valid export found", flush=True)
            return True
        else:
            print(f"      ❌ Invalid or incomplete, cleaning up...", flush=True)
            try:
                json_file.unlink()
                print(f"      🗑️  Deleted corrupted file", flush=True)
            except Exception as e:
                print(f"      ⚠️  Could not delete: {e}", flush=True)
    
    return False


def download_state(region_id):
    """Download raw data for a US state."""
    if region_id not in STATE_NAMES:
        print(f"❌ '{region_id}' is not a recognized US state")
        print(f"   Available states: {', '.join(sorted(STATE_NAMES.keys()))}")
        return False
    
    print(f"\n📥 Downloading {STATE_NAMES[region_id]}...")
    print(f"   Using: download_all_us_states_highres.py")
    
    import subprocess
    result = subprocess.run(
        [sys.executable, "download_all_us_states_highres.py", "--states", region_id],
        capture_output=False
    )
    
    return result.returncode == 0


def process_region(region_id, raw_path, source, target_pixels, force):
    """Run the pipeline on a region."""
    sys.path.insert(0, str(Path(__file__).parent))
    
    try:
        from src.pipeline import run_pipeline
    except ImportError as e:
        print(f"❌ Error importing pipeline: {e}")
        return False
    
    # Determine boundary
    if region_id in STATE_NAMES:
        state_name = STATE_NAMES[region_id]
        boundary_name = f"United States of America/{state_name}"
        boundary_type = "state"
    else:
        # For non-US regions, would need different logic
        boundary_name = None
        boundary_type = "country"
    
    print(f"\n🔄 Processing {region_id}...", flush=True)
    
    # Delete existing files if force
    if force:
        print("   🗑️  Force mode: deleting existing processed files...", flush=True)
        for pattern in [
            f"data/clipped/*/{region_id}_*",
            f"data/processed/*/{region_id}_*",
            f"generated/regions/{region_id}_*"
        ]:
            import glob
            for file_path in glob.glob(pattern, recursive=True):
                Path(file_path).unlink()
                print(f"      Deleted: {Path(file_path).name}", flush=True)
    
    try:
        success, result_paths = run_pipeline(
            raw_tif_path=raw_path,
            region_id=region_id,
            source=source,
            boundary_name=boundary_name,
            boundary_type=boundary_type,
            target_pixels=target_pixels,
            skip_clip=(boundary_name is None)
        )
        
        return success
        
    except Exception as e:
        print(f"❌ Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    # CRITICAL: Check venv FIRST before any imports
    check_venv()
    
    sys.path.insert(0, str(Path(__file__).parent))
    from src.config import DEFAULT_TARGET_PIXELS
    
    parser = argparse.ArgumentParser(
        description='One command to ensure a region is ready to view',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ensure_region.py ohio                        # Single word state
  python ensure_region.py new_hampshire               # Multi-word with underscore
  python ensure_region.py "new hampshire"             # Multi-word with quotes
  python ensure_region.py tennessee --force-reprocess # Force full rebuild
  python ensure_region.py california --target-pixels 4096  # High resolution

This script will:
  1. Check if raw data exists
  2. Download it if missing (US states only)
  3. Run the full pipeline (clip, downsample, export)
  4. Report status
        """
    )
    parser.add_argument('region_id', help='Region ID (e.g., ohio, tennessee)')
    parser.add_argument('--target-pixels', type=int, default=DEFAULT_TARGET_PIXELS,
                       help=f'Target resolution (default: {DEFAULT_TARGET_PIXELS})')
    parser.add_argument('--force-reprocess', action='store_true',
                       help='Force reprocessing even if files exist')
    parser.add_argument('--check-only', action='store_true',
                       help='Only check status, do not download or process')
    
    args = parser.parse_args()
    # Normalize region ID: convert spaces to underscores, lowercase
    region_id = args.region_id.lower().replace(' ', '_').replace('-', '_')
    
    print("="*70, flush=True)
    print(f"🎯 ENSURE REGION: {region_id.upper()}", flush=True)
    print("="*70, flush=True)
    print("\n📋 VALIDATING PIPELINE STAGES...", flush=True)
    print("   Checking each stage for valid, complete files", flush=True)
    print("   (Corrupted/incomplete files will be auto-cleaned)\n", flush=True)
    
    # Step 1: Check if pipeline is already complete
    print("[STAGE 4/4] Checking final export (JSON)...", flush=True)
    if not args.force_reprocess and check_pipeline_complete(region_id):
        print(f"\n✅ {region_id} is already processed and ready!")
        print(f"\nTo view:")
        print(f"  1. python serve_viewer.py")
        print(f"  2. Visit http://localhost:8001/interactive_viewer_advanced.html")
        print(f"  3. Select '{region_id}' from dropdown")
        print(f"\nTo force reprocess: add --force-reprocess flag")
        return 0
    
    # Step 2: Check if raw data exists
    print(f"\n[STAGE 1/4] Checking raw elevation data...", flush=True)
    raw_path, source = find_raw_file(region_id)
    
    if not raw_path:
        print(f"   ❌ No valid raw data found for {region_id}", flush=True)
        
        if args.check_only:
            print("   Use without --check-only to download", flush=True)
            return 1
        
        # Try to download (US states only)
        if region_id in STATE_NAMES:
            print(f"\n   📥 Starting download...", flush=True)
            if not download_state(region_id):
                print(f"\n❌ Download failed!", flush=True)
                return 1
            
            # Re-validate the downloaded file
            print(f"\n   🔍 Validating download...", flush=True)
            raw_path, source = find_raw_file(region_id)
            if not raw_path:
                print(f"\n❌ Download reported success but validation failed!", flush=True)
                print(f"   File may be corrupted or incomplete", flush=True)
                print(f"   Expected locations:", flush=True)
                print(f"     - data/raw/srtm_30m/{region_id}_bbox_30m.tif", flush=True)
                print(f"     - data/regions/{region_id}.tif", flush=True)
                return 1
            print(f"   ✅ Download validated successfully", flush=True)
        else:
            print(f"\n❌ Cannot auto-download '{region_id}'")
            print(f"   This script only supports US states")
            print(f"   Available states: {', '.join(sorted(STATE_NAMES.keys()))}")
            return 1
    
    if args.check_only:
        print("\n   Use without --check-only to process")
        return 0
    
    # Step 3: Process the region
    success = process_region(region_id, raw_path, source, args.target_pixels, args.force_reprocess)
    
    if success:
        print("\n" + "="*70)
        print(f"✅ SUCCESS: {region_id} is ready to view!")
        print("="*70)
        print(f"\nNext steps:")
        print(f"  1. python serve_viewer.py")
        print(f"  2. Visit http://localhost:8001/interactive_viewer_advanced.html")
        print(f"  3. Select '{region_id}' from dropdown")
        return 0
    else:
        print("\n" + "="*70)
        print(f"❌ FAILED: Could not process {region_id}")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())

