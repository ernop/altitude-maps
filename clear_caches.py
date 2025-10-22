"""
Clear all cached and generated data files.

Use this when:
- Changing data processing/export format
- Switching data sources
- Debugging data inconsistencies
- Want a clean slate

This ensures no stale data with old transformations.
"""
import sys
import shutil
from pathlib import Path


def clear_caches(confirm: bool = False):
    """Clear all cached and generated data."""
    
    cache_dirs = [
        Path("data/.cache"),
        Path("generated"),
    ]
    
    print("\n" + "=" * 70)
    print("  CACHE CLEARING UTILITY")
    print("=" * 70)
    print("\nThis will delete:")
    
    total_size = 0
    file_count = 0
    
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            # Calculate size
            for item in cache_dir.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
                    file_count += 1
            
            print(f"\n   {cache_dir}/")
            if cache_dir.exists():
                contents = list(cache_dir.rglob("*"))
                print(f"   - {len([f for f in contents if f.is_file()])} files")
    
    print(f"\nTotal: {file_count} files ({total_size / (1024**2):.1f} MB)")
    
    if not confirm:
        print("\n" + "=" * 70)
        response = input("\nProceed with deletion? [y/N]: ").strip().lower()
        if response not in ('y', 'yes'):
            print("\nCancelled.")
            return False
    
    print("\n" + "=" * 70)
    print("Clearing caches...")
    
    deleted_dirs = []
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir)
                print(f"   [OK] Deleted: {cache_dir}/")
                deleted_dirs.append(cache_dir)
            except Exception as e:
                print(f"   [ERROR] Failed to delete {cache_dir}: {e}")
    
    # Recreate directories
    print("\nRecreating directories...")
    for cache_dir in deleted_dirs:
        cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"   [OK] Created: {cache_dir}/")
    
    print("\n" + "=" * 70)
    print("CACHE CLEARING COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("   1. Re-export data: python export_for_web_viewer.py")
    print("   2. Or download regions: python download_regions.py")
    print("\n")
    
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Clear all cached and generated data files',
        epilog='Use this when changing data processing format to ensure consistency'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    args = parser.parse_args()
    
    try:
        success = clear_caches(confirm=args.yes)
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

