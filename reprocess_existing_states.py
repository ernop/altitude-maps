"""
Reprocess all existing state data with the fixed pipeline.

This script finds all raw state TIF files and reprocesses them
with the corrected masking and downsampling code.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config import DEFAULT_TARGET_TOTAL_PIXELS
from src.pipeline import run_pipeline
from src.region_config import US_STATES, get_region
from src.types import RegionType


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Reprocess existing state data')
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
            if state_id in US_STATES:
                state_files.append((state_id, tif_file, 'srtm_30m'))

    # Check regions directory for states not in bbox
    if regions_dir.exists():
        for tif_file in regions_dir.glob('*.tif'):
            state_id = tif_file.stem
            if state_id in US_STATES:
                # Only add if not already in list from bbox
                if not any(s[0] == state_id for s in state_files):
                    state_files.append((state_id, tif_file, 'srtm_30m'))
    
    if not state_files:
        print(" No state TIF files found!")
        print("Expected locations:")
        print("  - data/raw/srtm_30m/*_bbox_30m.tif")
        print("  - data/regions/*.tif")
        return 1
    
    # Filter by specific states if requested
    if args.states:
        # Normalize: spaces to underscores, lowercase
        requested = set(s.lower().replace(' ', '_').replace('-', '_') for s in args.states)
        state_files = [(sid, path, src) for sid, path, src in state_files if sid in requested]
        if not state_files:
            print(f" None of the requested states found: {args.states}")
            return 1
    
    import math
    base_dimension = int(round(math.sqrt(DEFAULT_TARGET_TOTAL_PIXELS)))
    print(f"\nFound {len(state_files)} state(s) to process")
    print(f"Target resolution: {DEFAULT_TARGET_TOTAL_PIXELS:,} total pixels (base dimension: {base_dimension}px)")
    print("=" * 70)
    
    # Clean intermediate files with proper dependency handling
    # --force: Delete everything (clipped, processed, generated)
    # No --force: Delete only generated files (keep clipped/processed if valid)
    print("\nCleaning old intermediate files...")
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
        # Get region config from centralized source
        config = get_region(state_id)
        if not config:
            print(f"\n[{i}/{len(state_files)}] Warning: Unknown state {state_id}, skipping...")
            failed.append(state_id)
            continue
        
        # Build boundary name from config
        boundary_name = f"{config.country}/{config.name}" if config.country else None
        
        # Determine boundary type based on region type (using enum)
        if config.region_type == RegionType.USA_STATE:
            boundary_type = 'state'
        elif config.region_type == RegionType.COUNTRY:
            boundary_type = 'country'
        elif config.region_type == RegionType.AREA:
            boundary_type = None  # Regions don't have standard boundaries
        else:
            raise ValueError(f"Unknown region type for {state_id}: {config.region_type}")
        
        print(f"\n[{i}/{len(state_files)}] Processing {config.name}...")
        print(f"   Source: {tif_file}")
        
        try:
            success, result_paths = run_pipeline(
                raw_tif_path=tif_file,
                region_id=state_id,
                source=source,
                boundary_name=boundary_name,
                boundary_type=boundary_type,
                target_total_pixels=DEFAULT_TARGET_TOTAL_PIXELS,
                skip_clip=(not config.clip_boundary)
            )
            
            if success:
                print(f"    {config.name} processed successfully!")
                succeeded.append(state_id)
            else:
                print(f"    {config.name} failed!")
                failed.append(state_id)
                
        except Exception as e:
            print(f"    Error: {e}")
            failed.append(state_id)
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Total:     {len(state_files)}")
    print(f"Succeeded: {len(succeeded)}")
    print(f"Failed:    {len(failed)}")
    
    if succeeded:
        print(f"\n Processed: {', '.join(succeeded)}")
    if failed:
        print(f"\n Failed: {', '.join(failed)}")
    
    print(f"\n{'='*70}")
    print("Next steps:")
    print("  1. Check validation: python fix_all_regions_aspect_ratio.py --check-only")
    print("  2. Start viewer: python serve_viewer.py")
    print("  3. Open: http://localhost:8001/interactive_viewer_advanced.html")
    print(f"{'='*70}")
    
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

