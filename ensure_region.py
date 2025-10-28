"""
One command to ensure a region is ready to view.

Downloads if needed, processes if needed, checks if everything is valid.

Usage:
    python ensure_region.py ohio
    python ensure_region.py tennessee --target-pixels 4096
    python ensure_region.py california --force-reprocess
"""
import sys
import argparse
from pathlib import Path

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
    """Find raw file for a region."""
    possible_locations = [
        Path(f"data/raw/srtm_30m/{region_id}_bbox_30m.tif"),
        Path(f"data/regions/{region_id}.tif"),
        Path(f"data/raw/usa_3dep/{region_id}_3dep_10m.tif"),
    ]
    
    for path in possible_locations:
        if path.exists():
            return path, get_source_from_path(path)
    
    return None, None


def get_source_from_path(path):
    """Determine source type from path."""
    if 'usa_3dep' in str(path):
        return 'usa_3dep'
    return 'srtm_30m'


def check_pipeline_complete(region_id):
    """Check if all pipeline stages are complete."""
    # Check for JSON export (final stage)
    generated_dir = Path("generated/regions")
    json_files = list(generated_dir.glob(f"{region_id}_*.json"))
    json_files = [f for f in json_files if '_borders' not in f.stem and '_meta' not in f.stem]
    
    return len(json_files) > 0


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
    
    print(f"\n🔄 Processing {region_id}...")
    
    # Delete existing files if force
    if force:
        print("   🗑️  Force mode: deleting existing processed files...")
        for pattern in [
            f"data/clipped/*/{region_id}_*",
            f"data/processed/*/{region_id}_*",
            f"generated/regions/{region_id}_*"
        ]:
            import glob
            for file_path in glob.glob(pattern, recursive=True):
                Path(file_path).unlink()
                print(f"      Deleted: {Path(file_path).name}")
    
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
    
    print("="*70)
    print(f"🎯 ENSURE REGION: {region_id.upper()}")
    print("="*70)
    
    # Step 1: Check if pipeline is already complete
    if not args.force_reprocess and check_pipeline_complete(region_id):
        print(f"\n✅ {region_id} is already processed and ready!")
        print(f"\nTo view:")
        print(f"  1. python serve_viewer.py")
        print(f"  2. Visit http://localhost:8001/interactive_viewer_advanced.html")
        print(f"  3. Select '{region_id}' from dropdown")
        print(f"\nTo force reprocess: add --force-reprocess flag")
        return 0
    
    # Step 2: Check if raw data exists
    raw_path, source = find_raw_file(region_id)
    
    if not raw_path:
        print(f"\n📦 Raw data not found for {region_id}")
        
        if args.check_only:
            print("   Use without --check-only to download")
            return 1
        
        # Try to download (US states only)
        if region_id in STATE_NAMES:
            if not download_state(region_id):
                print(f"\n❌ Download failed!")
                return 1
            
            # Find the downloaded file
            raw_path, source = find_raw_file(region_id)
            if not raw_path:
                print(f"\n❌ Download succeeded but file not found!")
                print(f"   Expected locations:")
                print(f"     - data/raw/srtm_30m/{region_id}_bbox_30m.tif")
                print(f"     - data/regions/{region_id}.tif")
                return 1
        else:
            print(f"\n❌ Cannot auto-download '{region_id}'")
            print(f"   This script only supports US states")
            print(f"   Available states: {', '.join(sorted(STATE_NAMES.keys()))}")
            return 1
    else:
        print(f"\n✅ Raw data found: {raw_path}")
    
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

