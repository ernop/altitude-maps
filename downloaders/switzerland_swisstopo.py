"""
Download elevation data from Switzerland SwissTopo.

SwissTopo provides extremely high-quality elevation data for Switzerland at 0.5-2m resolution.

Two download methods:
1. AUTOMATED: OpenTopography API (30m SRTM - lower quality but works immediately)
2. MANUAL: SwissTopo Official Site (0.5-2m - highest quality, requires manual steps)

For highest quality, use the manual method with SwissTopo's official portal.
"""
import sys
import io
from pathlib import Path
from typing import Tuple, Optional

# NOTE: Can be imported as library - do NOT wrap stdout/stderr
# Modern Python handles UTF-8 correctly by default

try:
    import requests
    from tqdm import tqdm
except ImportError as e:
    print(f"Missing package: {e}")
    print("Install with: pip install requests tqdm")
    sys.exit(1)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from downloaders.usa_3dep import download_opentopography_srtm  # Reuse SRTM downloader

# Switzerland regions
SWITZERLAND_REGIONS = {
    "switzerland": {"bounds": (5.9, 45.8, 10.5, 47.8), "name": "Switzerland (Full)"},
    "alps": {"bounds": (6.5, 46.0, 10.0, 47.0), "name": "Swiss Alps"},
    "zurich": {"bounds": (8.4, 47.3, 8.6, 47.5), "name": "Zurich Region"},
    "geneva": {"bounds": (6.0, 46.1, 6.3, 46.3), "name": "Geneva Region"},
    "bern": {"bounds": (7.3, 46.9, 7.5, 47.0), "name": "Bern Region"},
}


def print_manual_instructions(region_id: str, bounds: Tuple[float, float, float, float]) -> None:
    """
    Print instructions for manually downloading SwissTopo elevation data.
    
    Args:
        region_id: Region identifier
        bounds: (west, south, east, north) in degrees
    """
    west, south, east, north = bounds
    
    print("\n" + "=" * 80)
    print("MANUAL DOWNLOAD INSTRUCTIONS - SWISSTOPO (0.5-2m, HIGHEST QUALITY)")
    print("=" * 80)
    print(f"\nRegion: {region_id}")
    print(f"Bounds: West={west:.2f}, South={south:.2f}, East={east:.2f}, North={north:.2f}")
    print("\n📋 Steps:")
    print("\n1. Go to SwissTopo Data Portal:")
    print("   https://www.swisstopo.admin.ch/en/geodata.html")
    print("\n2. Navigate to Elevation Models:")
    print("   - Click 'Height models' or 'Digital Elevation Models'")
    print("   - Choose from available options:")
    print("     • swissALTI3D: 0.5m-2m resolution (highest quality)")
    print("     • DHM25: 25m resolution (older, full coverage)")
    print("\n3. Access the data:")
    print("   - Option A: Direct download (may require registration)")
    print("   - Option B: Via geodata portal")
    print("   - Some datasets are free, others may require licensing")
    print("\n4. Select your region:")
    print(f"   - Use map interface to select area")
    print(f"   - Coordinates: {west:.2f}° to {east:.2f}°E, {south:.2f}° to {north:.2f}°N")
    print("\n5. Download format:")
    print("   - Choose 'GeoTIFF' format")
    print("   - May also be available as: XYZ, ESRI Grid, LAS/LAZ (point cloud)")
    print(f"\n6. Save as: data/raw/switzerland_swisstopo/{region_id}_bbox_2m.tif")
    print("\n🔹 ALTERNATIVE: Use STAC API (Advanced Users)")
    print("\n1. SwissTopo STAC Catalog:")
    print("   https://www.geocat.ch/geonetwork/srv/eng/catalog.search#/home")
    print("\n2. Search for 'swissALTI3D' or 'DHM'")
    print("\n3. Download via API or direct links")
    print("\n" + "=" * 80)
    print("📝 Notes:")
    print("  • swissALTI3D: 0.5-2m resolution, extremely high quality")
    print("  • Some datasets require SwissTopo account (free registration)")
    print("  • Commercial use may require different licensing")
    print("  • Switzerland-only coverage (does not extend beyond borders)")
    print("=" * 80 + "\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Download Switzerland elevation data from SwissTopo',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download Switzerland (automated, 30m SRTM)
  python downloaders/switzerland_swisstopo.py switzerland --auto
  
  # Show manual instructions for high-res SwissTopo data
  python downloaders/switzerland_swisstopo.py alps --manual
  
  # List available regions
  python downloaders/switzerland_swisstopo.py --list

Note: --auto uses OpenTopography (30m SRTM, global fallback)
      For highest quality (0.5-2m SwissTopo), use --manual and follow instructions
        """
    )
    
    parser.add_argument('region', nargs='?', help='Region to download')
    parser.add_argument('--list', action='store_true', help='List available regions')
    parser.add_argument('--auto', action='store_true', help='Automated download (30m SRTM)')
    parser.add_argument('--manual', action='store_true', help='Show manual download instructions (0.5-2m SwissTopo)')
    parser.add_argument('--api-key', type=str, help='OpenTopography API key (for --auto)')
    parser.add_argument('--output-dir', type=str, default='data/raw/srtm_30m', help='Output directory')
    
    args = parser.parse_args()
    
    if args.list:
        print("\n📋 AVAILABLE SWITZERLAND REGIONS:")
        print("=" * 70)
        for region_id, info in SWITZERLAND_REGIONS.items():
            bounds = info['bounds']
            print(f"  {region_id:15s} - {info['name']:25s} {bounds}")
        print("=" * 70)
        return 0
    
    if not args.region:
        print(" No region specified!")
        print("Usage: python downloaders/switzerland_swisstopo.py <region> [--auto|--manual]")
        print("Or: python downloaders/switzerland_swisstopo.py --list")
        return 1
    
    region_id = args.region.lower().replace(' ', '_').replace('-', '_')
    
    if region_id not in SWITZERLAND_REGIONS:
        print(f" Unknown region: {args.region}")
        print("Run with --list to see available regions")
        return 1
    
    region_info = SWITZERLAND_REGIONS[region_id]
    bounds = region_info['bounds']
    name = region_info['name']
    
    print(f"\n🇨🇭 Switzerland Elevation Downloader")
    print(f"=" * 70)
    print(f"Region: {name} ({region_id})")
    print(f"Bounds: {bounds}")
    print(f"=" * 70)
    
    if args.manual:
        print_manual_instructions(region_id, bounds)
        return 0
    elif args.auto:
        output_path = Path(args.output_dir) / f"{region_id}_bbox_30m.tif"
        success = download_opentopography_srtm(region_id, bounds, output_path, args.api_key)
        
        if success:
            print(f"\n Success! Data saved to: {output_path}")
            print(f"\n  Note: This is 30m SRTM data, not highest-res SwissTopo.")
            print(f"   For 0.5-2m resolution, run:")
            print(f"   python downloaders/switzerland_swisstopo.py {region_id} --manual")
        else:
            print(f"\n Download failed.")
        
        return 0 if success else 1
    else:
        print("\n❓ Please specify download method:")
        print(f"   --auto    : Automated download (30m SRTM global fallback)")
        print(f"   --manual  : Show instructions for SwissTopo download (0.5-2m, best quality)")
        print(f"\nExample:")
        print(f"   python downloaders/switzerland_swisstopo.py {region_id} --auto")
        return 1


if __name__ == "__main__":
    sys.exit(main())

