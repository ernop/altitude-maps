"""
Pre-compress JSON files to .json.gz format.
This ensures maximum compression and eliminates runtime overhead.

Alternative Linux command (skips existing .gz files):
    find generated -name "*.json" -type f -exec sh -c '[ ! -e "$1.gz" ] && gzip -k -9 "$1"' sh {} \;

Or with a while loop:
    find generated -name "*.json" -type f | while read f; do 
        [ ! -e "$f.gz" ] && gzip -k -9 "$f"
    done
"""
import gzip
import json
from pathlib import Path
import sys

def precompress_json_files(directory: str = "generated/regions"):
    """
    Pre-compress all JSON files in a directory to .json.gz.
    
    This creates .json.gz files alongside the originals, which can be
    served directly by web servers with proper Content-Encoding headers.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"ERROR: Directory not found: {directory}")
        return 1
    
    json_files = list(dir_path.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {directory}")
        return 1
    
    print(f"Pre-compressing {len(json_files)} JSON files...")
    print("=" * 70)
    
    total_original = 0
    total_compressed = 0
    
    for json_file in json_files:
        # Skip if already a .gz file
        if json_file.suffix == '.gz':
            continue
            
        gz_file = json_file.with_suffix('.json.gz')
        
        # Skip if .gz version already exists (don't overwrite)
        if gz_file.exists():
            print(f"[SKIP] {json_file.name} (already compressed)")
            continue
        
        try:
            # Read original
            with open(json_file, 'rb') as f:
                content = f.read()
            
            # Compress with maximum compression
            with gzip.open(gz_file, 'wb', compresslevel=9) as f:
                f.write(content)
            
            original_size = len(content)
            compressed_size = gz_file.stat().st_size
            ratio = (1 - compressed_size / original_size) * 100
            
            total_original += original_size
            total_compressed += compressed_size
            
            print(f"[OK] {json_file.name}")
            print(f"     {original_size/1024:.1f} KB -> {compressed_size/1024:.1f} KB ({ratio:.1f}% saved)")
            
        except Exception as e:
            print(f"[ERROR] {json_file.name}: {e}")
    
    print("=" * 70)
    print(f"Total: {total_original/1024/1024:.1f} MB -> {total_compressed/1024/1024:.1f} MB")
    overall_ratio = (1 - total_compressed / total_original) * 100 if total_original > 0 else 0
    print(f"Overall compression: {overall_ratio:.1f}%")
    
    return 0

if __name__ == '__main__':
    sys.exit(precompress_json_files())

