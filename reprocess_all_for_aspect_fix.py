#!/usr/bin/env python3
"""
Reprocess all regions to fix aspect ratio (remove 45° threshold bug).
This will reprocess ALL regions that were previously processed.
"""

from pathlib import Path
import subprocess
import sys

def get_all_regions():
    """Get all unique region IDs from generated/regions."""
    regions_dir = Path('generated/regions')
    if not regions_dir.exists():
        print("No generated/regions directory found!")
        return []
    
    # Get all JSON files (not metadata)
    json_files = [f for f in regions_dir.glob('*.json') 
                  if not f.name.endswith('_meta.json') 
                  and f.name != 'regions_manifest.json']
    
    # Extract region IDs (the simple names without version suffixes)
    regions = set()
    for f in json_files:
        name = f.stem
        # Remove version suffixes like _srtm_30m_2048px_v2
        if '_srtm_30m_' in name or '_usa_3dep_' in name:
            # Extract just the region ID before the source
            region_id = name.split('_srtm_30m_')[0] if '_srtm_30m_' in name else name.split('_usa_3dep_')[0]
        else:
            region_id = name
        
        # Skip manifest
        if region_id != 'regions':
            regions.add(region_id)
    
    return sorted(regions)

def main():
    print("=" * 70)
    print("ASPECT RATIO FIX - REPROCESS ALL REGIONS")
    print("=" * 70)
    print()
    print("This will reprocess all regions to fix the aspect ratio bug")
    print("(previously only regions >45° latitude were corrected)")
    print()
    
    regions = get_all_regions()
    
    if not regions:
        print("No regions found to reprocess!")
        return 1
    
    print(f"Found {len(regions)} regions to reprocess:")
    for r in regions:
        print(f"  - {r}")
    print()
    
    # Check for --yes flag
    import sys
    if '--yes' not in sys.argv:
        # Ask for confirmation
        try:
            response = input(f"Reprocess all {len(regions)} regions? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("Cancelled.")
                return 0
        except (EOFError, KeyboardInterrupt):
            print("\nUse --yes flag to skip confirmation")
            return 1
    
    print()
    print("=" * 70)
    print("STARTING REPROCESSING")
    print("=" * 70)
    print()
    
    success_count = 0
    failed = []
    
    for i, region in enumerate(regions, 1):
        print()
        print(f"[{i}/{len(regions)}] Processing: {region}")
        print("-" * 70)
        
        # Run ensure_region with force-reprocess
        cmd = [sys.executable, "ensure_region.py", region, "--force-reprocess"]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=False, text=True)
            success_count += 1
            print(f"✓ {region} completed successfully")
        except subprocess.CalledProcessError as e:
            print(f"✗ {region} FAILED")
            failed.append(region)
        except Exception as e:
            print(f"✗ {region} ERROR: {e}")
            failed.append(region)
    
    # Summary
    print()
    print("=" * 70)
    print("REPROCESSING COMPLETE")
    print("=" * 70)
    print(f"Success: {success_count}/{len(regions)}")
    
    if failed:
        print(f"Failed: {len(failed)}")
        print("Failed regions:")
        for r in failed:
            print(f"  - {r}")
        return 1
    else:
        print("All regions reprocessed successfully!")
        return 0

if __name__ == "__main__":
    sys.exit(main())

