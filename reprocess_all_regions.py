"""Find and reprocess all existing regions with the fixes"""
import sys
import io
import subprocess
from pathlib import Path
import json

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Find all existing regions from generated JSON files
generated_dir = Path('generated/regions')
regions = set()

for json_file in generated_dir.glob('*.json'):
    if json_file.name.endswith('_meta.json') or 'manifest' in json_file.name:
        continue
    
    try:
        with open(json_file) as f:
            data = json.load(f)
        region_id = data.get('region_id')
        if region_id:
            regions.add(region_id)
    except:
        # Try to infer from filename
        stem = json_file.stem
        for suffix in ['_srtm_30m_2048px_v2', '_srtm_30m_800px_v2', '_srtm_30m_v2', '_3dep_10m']:
            if stem.endswith(suffix):
                regions.add(stem[:-len(suffix)])
                break

regions = sorted(regions)

print("="*70)
print(f"REPROCESSING ALL REGIONS WITH FIXES")
print("="*70)
print(f"\nFound {len(regions)} regions to reprocess:")
for r in regions:
    print(f"  - {r}")

print(f"\n{'='*70}")
print("Starting reprocessing...")
print(f"{'='*70}\n")

failed = []
for i, region_id in enumerate(regions, 1):
    print(f"\n[{i}/{len(regions)}] Processing: {region_id}")
    print("-"*70)
    
    try:
        result = subprocess.run(
            [sys.executable, "ensure_region.py", region_id, "--force-reprocess"],
            capture_output=False,
            text=True
        )
        
        if result.returncode != 0:
            print(f"❌ FAILED: {region_id}")
            failed.append(region_id)
        else:
            print(f"✅ SUCCESS: {region_id}")
    except Exception as e:
        print(f"❌ ERROR: {region_id} - {e}")
        failed.append(region_id)

print(f"\n{'='*70}")
print("REPROCESSING COMPLETE")
print(f"{'='*70}")
print(f"\nTotal regions: {len(regions)}")
print(f"Successful: {len(regions) - len(failed)}")
if failed:
    print(f"Failed: {len(failed)}")
    print(f"Failed regions: {', '.join(failed)}")
else:
    print("✅ All regions processed successfully!")

