"""
Delete all data files for test regions.

Safely removes test region data from:
- Raw tiles and merged files
- Processed and clipped files
- Generated JSON exports
- Cache entries

Usage:
    python delete_test_regions.py              # Dry run (preview)
    python delete_test_regions.py --delete    # Actually delete
    python delete_test_regions.py --region test_10m_colorado  # Delete specific region
"""
import sys
import argparse
from pathlib import Path
from typing import List, Set, Tuple


TEST_REGION_IDS = [
    "test_10m_colorado",
    "test_30m_utah",
    "test_90m_wyoming",
]


def find_test_files(region_ids: List[str]) -> Set[Path]:
    """
    Find all files related to test regions.
    
    Returns:
        Set of file paths to delete
    """
    files_to_delete = set()
    
    # Directories to search
    search_dirs = [
        Path("data/raw"),
        Path("data/merged"),
        Path("data/processed"),
        Path("data/clipped"),
        Path("generated/regions"),
        Path("data/.cache"),
    ]
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        
        # Search recursively
        for file_path in search_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Check if filename contains any test region ID
            filename = file_path.name
            stem = file_path.stem
            
            for region_id in region_ids:
                if region_id in filename or region_id in stem:
                    files_to_delete.add(file_path)
                    break
    
    return files_to_delete


def delete_files(files: Set[Path], dry_run: bool = True) -> Tuple[int, int]:
    """
    Delete files (or preview if dry_run).
    
    Returns:
        (deleted_count, error_count)
    """
    deleted = 0
    errors = 0
    
    for file_path in sorted(files):
        try:
            if dry_run:
                print(f"  Would delete: {file_path}")
            else:
                file_path.unlink()
                print(f"  Deleted: {file_path}")
                deleted += 1
        except Exception as e:
            print(f"  ERROR deleting {file_path}: {e}")
            errors += 1
    
    return deleted, errors


def main():
    parser = argparse.ArgumentParser(
        description="Delete test region data files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python delete_test_regions.py                    # Preview what would be deleted
  python delete_test_regions.py --delete           # Actually delete all test regions
  python delete_test_regions.py --delete --region test_10m_colorado  # Delete one region
        """
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete files (default is dry-run preview)"
    )
    parser.add_argument(
        "--region",
        type=str,
        help="Delete files for specific region only (e.g., test_10m_colorado)"
    )
    
    args = parser.parse_args()
    
    # Determine which regions to delete
    if args.region:
        if args.region not in TEST_REGION_IDS:
            print(f"ERROR: '{args.region}' is not a test region")
            print(f"Valid test regions: {', '.join(TEST_REGION_IDS)}")
            return 1
        region_ids = [args.region]
    else:
        region_ids = TEST_REGION_IDS
    
    print("="*70)
    if args.delete:
        print("DELETING TEST REGION FILES")
    else:
        print("DRY RUN: Preview of files that would be deleted")
    print("="*70)
    print(f"\nRegions: {', '.join(region_ids)}")
    
    # Find all test files
    print("\nSearching for test region files...")
    files_to_delete = find_test_files(region_ids)
    
    if not files_to_delete:
        print("\nNo test region files found.")
        return 0
    
    print(f"\nFound {len(files_to_delete)} file(s):")
    for file_path in sorted(files_to_delete):
        size_mb = file_path.stat().st_size / 1024 / 1024
        print(f"  {file_path} ({size_mb:.2f} MB)")
    
    # Calculate total size
    total_size = sum(f.stat().st_size for f in files_to_delete)
    total_mb = total_size / 1024 / 1024
    print(f"\nTotal size: {total_mb:.2f} MB")
    
    if args.delete:
        print("\n" + "="*70)
        print("DELETING FILES...")
        print("="*70)
        deleted, errors = delete_files(files_to_delete, dry_run=False)
        
        print(f"\n{'='*70}")
        print(f"Deleted: {deleted} file(s)")
        if errors > 0:
            print(f"Errors: {errors} file(s)")
        print(f"{'='*70}")
        
        return 1 if errors > 0 else 0
    else:
        print("\n" + "="*70)
        print("DRY RUN - No files deleted")
        print("="*70)
        print("\nTo actually delete these files, run with --delete flag:")
        print("  python delete_test_regions.py --delete")
        return 0


if __name__ == "__main__":
    sys.exit(main())

