"""Find outdated file patterns that should be removed."""
import os
from pathlib import Path

outdated_patterns = [
    # Old region_id-based patterns
    '*_bbox_30m.tif',
    '*_bbox_90m.tif',
    '*_3dep_10m.tif',
    '*_clipped_*.tif',  # Old region_id_clipped pattern
    '*_srtm_*px_v2.tif',  # Old region_id_srtm pattern in processed
    # Old JSON metadata
    '*_bbox_30m.json',
    '*_bbox_90m.json',
    '*_3dep_10m.json',
    # Precise bounds (4+ decimal places) - these should be grid-aligned
    # We'll check for files with many decimal places in the name
]

def is_precise_bounds_file(filename):
    """Check if filename uses precise bounds (4+ decimal places)."""
    if not filename.startswith('bbox_'):
        return False
    # Look for patterns like W111_6220 (4+ digits after decimal point)
    import re
    # Pattern: W111_6220 or similar with 4+ digits
    pattern = r'[WENS]\d+_\d{4,}'  # At least 4 digits after underscore
    return bool(re.search(pattern, filename))

def find_outdated_files(root_dir):
    """Find all outdated files."""
    outdated = []
    
    for root, dirs, files in os.walk(root_dir):
        # Skip .cache and other non-data directories
        if '.cache' in root or 'subparts' in root:
            continue
            
        for filename in files:
            filepath = Path(root) / filename
            
            # Check for old region_id-based patterns
            if any(filename.startswith(p) for p in ['utah_', 'california_', 'tennessee_', 'ohio_', 'kentucky_', 
                                                      'antico', 'san_mateo', 'central_new', 'kamchatka', 'taal_',
                                                      'cottonwood', 'greenville']):
                if any(p in filename for p in ['_bbox_30m', '_bbox_90m', '_3dep_10m', '_clipped_']):
                    outdated.append(filepath)
                elif '_srtm_' in filename and '_px_v2.tif' in filename and 'processed' in str(filepath):
                    outdated.append(filepath)
            
            # Check for precise bounds files (should be grid-aligned now)
            if is_precise_bounds_file(filename):
                outdated.append(filepath)
    
    return outdated

if __name__ == '__main__':
    root = Path('data')
    if not root.exists():
        print("data/ directory not found")
        exit(1)
    
    outdated = find_outdated_files(root)
    
    print(f"Found {len(outdated)} potentially outdated files:")
    print("=" * 70)
    for f in sorted(outdated):
        print(f"  {f}")

