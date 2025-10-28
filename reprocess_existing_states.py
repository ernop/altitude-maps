"""
Reprocess all existing state data with the fixed pipeline.

This script finds all raw state TIF files and reprocesses them
with the corrected masking and downsampling code.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import run_pipeline

# US State name mapping
STATE_NAMES = {
    'arizona': 'Arizona',
    'california': 'California',
    'colorado': 'Colorado',
    'connecticut': 'Connecticut',
    'delaware': 'Delaware',
    'florida': 'Florida',
    'indiana': 'Indiana',
    'iowa': 'Iowa',
    'kansas': 'Kansas',
    'kentucky': 'Kentucky',
    'maine': 'Maine',
    'maryland': 'Maryland',
    'massachusetts': 'Massachusetts',
    'minnesota': 'Minnesota',
    'nebraska': 'Nebraska',
    'nevada': 'Nevada',
    'new_hampshire': 'New Hampshire',
    'new_jersey': 'New Jersey',
    'new_mexico': 'New Mexico',
    'north_dakota': 'North Dakota',
    'ohio': 'Ohio',
    'oklahoma': 'Oklahoma',
    'oregon': 'Oregon',
    'pennsylvania': 'Pennsylvania',
    'rhode_island': 'Rhode Island',
    'south_dakota': 'South Dakota',
    'utah': 'Utah',
    'vermont': 'Vermont',
    'washington': 'Washington',
    'wisconsin': 'Wisconsin',
    'wyoming': 'Wyoming'
}


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Reprocess existing state data')
    parser.add_argument('--target-pixels', type=int, default=4096,
                       help='Target resolution (default: 4096)')
    parser.add_argument('--force', action='store_true',
                       help='Force reprocessing: delete clipped, processed, AND generated files')
    parser.add_argument('--states', nargs='+',
                       help='Process only specific states (e.g., ohio kentucky)')
    
    args = parser.parse_args()
    
    # Find all raw state TIF files
    raw_bbox_dir = Path('data/raw/srtm_30m')
    regions_dir = Path('data/regions')
    
    state_files = []
    
    # Check bbox files first (higher quality)
    if raw_bbox_dir.exists():
        for tif_file in raw_bbox_dir.glob('*_bbox_30m.tif'):
            state_id = tif_file.stem.replace('_bbox_30m', '')
            if state_id in STATE_NAMES:
                state_files.append((state_id, tif_file, 'srtm_30m'))
    
    # Check regions directory for states not in bbox
    if regions_dir.exists():
        for tif_file in regions_dir.glob('*.tif'):
            state_id = tif_file.stem
            if state_id in STATE_NAMES:
                # Only add if not already in list from bbox
                if not any(s[0] == state_id for s in state_files):
                    state_files.append((state_id, tif_file, 'srtm_30m'))
    
    if not state_files:
        print("❌ No state TIF files found!")
        print("Expected locations:")
        print("  - data/raw/srtm_30m/*_bbox_30m.tif")
        print("  - data/regions/*.tif")
        return 1
    
    print(f"\n🗺️  Found {len(state_files)} state(s) to process")
    print(f"Target resolution: {args.target_pixels}px")
    print("=" * 70)
    
    # Clean intermediate files with proper dependency handling
    # --force: Delete everything (clipped, processed, generated)
    # No --force: Delete only generated files (keep clipped/processed if valid)
    print("\n🗑️  Cleaning old intermediate files...")
    clipped_dir = Path('data/clipped/srtm_30m')
    processed_dir = Path('data/processed/srtm_30m')
    generated_dir = Path('generated/regions')
    
    deleted_count = 0
    for state_id, _, _ in state_files:
        if args.force:
            # Delete everything - full rebuild
            if clipped_dir.exists():
                for f in clipped_dir.glob(f'{state_id}_*'):
                    f.unlink()
                    print(f"   Deleted clipped: {f.name}")
                    deleted_count += 1
            if processed_dir.exists():
                for f in processed_dir.glob(f'{state_id}_*'):
                    f.unlink()
                    print(f"   Deleted processed: {f.name}")
                    deleted_count += 1
            if generated_dir.exists():
                for f in generated_dir.glob(f'{state_id}_*'):
                    f.unlink()
                    print(f"   Deleted generated: {f.name}")
                    deleted_count += 1
        else:
            # Only delete generated files - let pipeline decide if clipped/processed need regeneration
            # This allows fixing export bugs without re-clipping/re-downsampling
            if generated_dir.exists():
                for f in generated_dir.glob(f'{state_id}_*'):
                    f.unlink()
                    print(f"   Deleted generated: {f.name}")
                    deleted_count += 1
    
    if deleted_count > 0:
        print(f"   Total deleted: {deleted_count} files")
    else:
        print("   No old files found to delete")
    
    # Process each state
    succeeded = []
    failed = []
    
    for i, (state_id, tif_file, source) in enumerate(state_files, 1):
        state_name = STATE_NAMES[state_id]
        boundary_name = f"United States of America/{state_name}"
        
        print(f"\n[{i}/{len(state_files)}] Processing {state_name}...")
        print(f"   Source: {tif_file}")
        
        try:
            success, result_paths = run_pipeline(
                raw_tif_path=tif_file,
                region_id=state_id,
                source=source,
                boundary_name=boundary_name,
                boundary_type='state',
                target_pixels=args.target_pixels,
                skip_clip=False
            )
            
            if success:
                print(f"   ✅ {state_name} processed successfully!")
                succeeded.append(state_id)
            else:
                print(f"   ❌ {state_name} failed!")
                failed.append(state_id)
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            failed.append(state_id)
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Total:     {len(state_files)}")
    print(f"Succeeded: {len(succeeded)}")
    print(f"Failed:    {len(failed)}")
    
    if succeeded:
        print(f"\n✅ Processed: {', '.join(succeeded)}")
    if failed:
        print(f"\n❌ Failed: {', '.join(failed)}")
    
    print(f"\n{'='*70}")
    print("Next steps:")
    print("  1. Check validation: python fix_all_regions_aspect_ratio.py --check-only")
    print("  2. Start viewer: python serve_viewer.py")
    print("  3. Open: http://localhost:8001/interactive_viewer_advanced.html")
    print(f"{'='*70}")
    
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

