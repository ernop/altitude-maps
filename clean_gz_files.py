"""
Clean up .gz files that were created by the precompress script.
These are not needed for dynamic compression with mod_deflate.
"""
from pathlib import Path
import sys

def clean_gz_files():
    """Remove .gz files from generated/regions directory."""
    regions_dir = Path('generated/regions')
    
    if not regions_dir.exists():
        print('No generated/regions directory found')
        return 0
    
    gz_files = list(regions_dir.glob('*.gz'))
    
    if not gz_files:
        print('No .gz files found - already clean!')
        return 0
    
    print(f'Found {len(gz_files)} .gz files in generated/regions/')
    print()
    print('These were created by precompress_json.py for testing.')
    print('They are NOT needed for Apache mod_deflate compression.')
    print('Apache compresses on-the-fly dynamically.')
    print()
    
    response = input(f'Delete all {len(gz_files)} .gz files? (yes/no): ').strip().lower()
    
    if response not in ('yes', 'y'):
        print('Cancelled - no files deleted')
        return 0
    
    deleted = 0
    for gz_file in gz_files:
        try:
            gz_file.unlink()
            deleted += 1
            print(f'  Deleted: {gz_file.name}')
        except Exception as e:
            print(f'  Error deleting {gz_file.name}: {e}')
    
    print()
    print(f'[SUCCESS] Deleted {deleted} .gz files')
    print()
    print('Your .json files remain unchanged.')
    print('Apache will compress them dynamically when serving.')
    
    return 0

if __name__ == '__main__':
    sys.exit(clean_gz_files())

