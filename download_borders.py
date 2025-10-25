"""
Pre-download Natural Earth border data for offline use.
Downloads both country (admin_0) and state/province (admin_1) boundaries.
"""
import sys
from pathlib import Path

from src.borders import get_border_manager

def download_all_borders(resolution='110m'):
    """
    Download and cache all Natural Earth border data.
    
    Args:
        resolution: '10m', '50m', or '110m'
    """
    print(f"\n{'='*70}")
    print(f"Pre-downloading Natural Earth Border Data ({resolution})")
    print(f"{'='*70}\n")
    
    border_manager = get_border_manager()
    
    # Download countries (admin_0)
    print("[1/2] Downloading country borders (admin_0)...")
    try:
        countries = border_manager.load_borders(resolution=resolution, force_reload=False)
        print(f"   OK: Loaded {len(countries)} countries")
        print(f"   Cache: data/.cache/borders/ne_{resolution}_countries.pkl")
    except Exception as e:
        print(f"   ERROR: Failed to download countries: {e}")
        return False
    
    print()
    
    # Download states/provinces (admin_1)
    print("[2/2] Downloading state/province borders (admin_1)...")
    try:
        states = border_manager.load_state_borders(resolution=resolution, force_reload=False)
        print(f"   OK: Loaded {len(states)} states/provinces/territories")
        print(f"   Cache: data/.cache/borders/ne_{resolution}_admin_1.pkl")
        
        # Show some stats
        us_states = states[states['admin'] == 'United States of America']
        print(f"\n   US states: {len(us_states)}")
        canada_provinces = states[states['admin'] == 'Canada']
        print(f"   Canadian provinces/territories: {len(canada_provinces)}")
        
    except Exception as e:
        print(f"   ERROR: Failed to download states: {e}")
        return False
    
    print(f"\n{'='*70}")
    print("SUCCESS: All border data downloaded and cached!")
    print(f"{'='*70}")
    print("\nBorder data is now available offline for:")
    print("  - Country-level clipping and borders")
    print("  - State/province-level clipping and borders")
    print("  - No internet needed for subsequent operations")
    print()
    
    return True

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Pre-download Natural Earth border data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download default resolution (110m - fast, good for most uses)
  python download_borders.py
  
  # Download high resolution (10m - detailed, large files)
  python download_borders.py --resolution 10m
  
  # Re-download even if cached
  python download_borders.py --force
        """
    )
    
    parser.add_argument(
        '--resolution', '-r',
        type=str,
        choices=['10m', '50m', '110m'],
        default='110m',
        help='Border resolution (default: 110m)'
    )
    
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force re-download even if cached'
    )
    
    args = parser.parse_args()
    
    # If forcing, clear cache first
    if args.force:
        print("\nForce re-download enabled, clearing cache...")
        cache_dir = Path("data/.cache/borders")
        for cache_file in cache_dir.glob(f"ne_{args.resolution}_*.pkl"):
            cache_file.unlink()
            print(f"   Deleted: {cache_file}")
    
    success = download_all_borders(resolution=args.resolution)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())

