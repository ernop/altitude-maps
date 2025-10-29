"""
Download elevation data from Japan GSI (Geospatial Information Authority of Japan).

GSI provides high-quality elevation data for Japan at 5-10m resolution.

Two download methods:
1. AUTOMATED: OpenTopography API (30m SRTM - lower quality but works immediately)
2. MANUAL: GSI Official Site (5-10m - highest quality, requires manual steps)

For highest quality, use the manual method with GSI's official portal.
"""
import sys
import io
from pathlib import Path
from typing import Tuple, Optional

# Windows UTF-8 encoding support (PowerShell handles this automatically on Win10+)
# Removed wrapper to avoid conflicts with PowerShell's own UTF-8 handling

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
from src.metadata import create_raw_metadata, save_metadata, get_metadata_path
from src.pipeline import run_pipeline

# Japan regions
JAPAN_REGIONS = {
    "japan": {"bounds": (129.0, 30.0, 146.0, 46.0), "name": "Japan (Full)"},
    "honshu": {"bounds": (129.8, 33.7, 141.9, 41.5), "name": "Honshu Island"},
    "hokkaido": {"bounds": (139.3, 41.4, 145.8, 45.5), "name": "Hokkaido Island"},
    "kyushu": {"bounds": (129.5, 31.0, 131.9, 34.0), "name": "Kyushu Island"},
    "shikoku": {"bounds": (132.155, 32.775, 134.8, 34.5), "name": "Shikoku Island"},
    "kochi": {"bounds": (132.7, 32.7, 134.3, 33.9), "name": "Kochi Prefecture"},
}


def print_manual_instructions(region_id: str, bounds: Tuple[float, float, float, float]) -> None:
    """
    Print instructions for manually downloading GSI elevation data.
    
    Args:
        region_id: Region identifier
        bounds: (west, south, east, north) in degrees
    """
    west, south, east, north = bounds
    
    print("\n" + "=" * 80)
    print("MANUAL DOWNLOAD INSTRUCTIONS - JAPAN GSI (5-10m, HIGHEST QUALITY)")
    print("=" * 80)
    print(f"\nRegion: {region_id}")
    print(f"Bounds: East={east:.2f}, South={south:.2f}, West={west:.2f}, North={north:.2f}")
    print("\n📋 Two GSI Options:")
    print("\n🔹 OPTION 1: GSI Tiles Portal (DEM 5m/10m)")
    print("\n1. Go to GSI Tiles Download:")
    print("   https://fgd.gsi.go.jp/download/")
    print("   (Note: Site is primarily in Japanese, use browser translation)")
    print("\n2. Select elevation data:")
    print("   - Choose「基盤地図情報」(Fundamental Geospatial Data)")
    print("   - Select「DEM（数値標高モデル）」(Digital Elevation Model)")
    print("   - Choose resolution:")
    print("     • DEM5A: 5m resolution (urban/coastal areas)")
    print("     • DEM10B: 10m resolution (full coverage)")
    print("\n3. Select area:")
    print(f"   - Use map interface to select region")
    print(f"   - Or input coordinates: {west:.2f}E to {east:.2f}E, {south:.2f}N to {north:.2f}N")
    print("\n4. Download format:")
    print("   - Choose 'GeoTIFF' if available")
    print("   - Otherwise download JPGIS (GML) format")
    print("   - May need to convert GML → GeoTIFF using GDAL:")
    print("     gdal_translate -of GTiff input.xml output.tif")
    print(f"\n5. Save as: data/raw/japan_gsi/{region_id}_bbox_5m.tif (or _10m.tif)")
    print("\n🔹 OPTION 2: Global Map Japan (Raster Format)")
    print("\n1. Go to Global Map Japan:")
    print("   https://www.gsi.go.jp/kankyochiri/gm_japan_e.html")
    print("\n2. Download:")
    print("   - Select 'Elevation' dataset")
    print("   - Download raster format (easier than JPGIS)")
    print("   - Resolution: ~50m-250m (lower than DEM5A/10B)")
    print(f"\n3. Save as: data/raw/japan_gsi/{region_id}_bbox_50m.tif")
    print("\n" + "=" * 80)
    print("📝 Notes:")
    print("  • DEM5A (5m): Best quality, but has gaps around water bodies")
    print("  • DEM10B (10m): Full coverage, recommended for most uses")
    print("  • Global Map: Easier format, but lower resolution")
    print("  • JPGIS format requires conversion with GDAL")
    print("=" * 80 + "\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Download Japan elevation data from GSI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download Shikoku Island (automated, 30m SRTM)
  python downloaders/japan_gsi.py shikoku --auto
  
  # Show manual instructions for high-res GSI data
  python downloaders/japan_gsi.py kochi --manual
  
  # List available regions
  python downloaders/japan_gsi.py --list

Note: --auto uses OpenTopography (30m SRTM, global fallback)
      For highest quality (5-10m GSI), use --manual and follow instructions
        """
    )
    
    parser.add_argument('region', nargs='?', help='Region to download')
    parser.add_argument('--list', action='store_true', help='List available regions')
    parser.add_argument('--auto', action='store_true', help='Automated download (30m SRTM)')
    parser.add_argument('--manual', action='store_true', help='Show manual download instructions (5-10m GSI)')
    parser.add_argument('--api-key', type=str, help='OpenTopography API key (for --auto)')
    parser.add_argument('--output-dir', type=str, default='data/raw/srtm_30m', help='Output directory')
    
    args = parser.parse_args()
    
    if args.list:
        print("\n📋 AVAILABLE JAPAN REGIONS:")
        print("=" * 70)
        for region_id, info in JAPAN_REGIONS.items():
            bounds = info['bounds']
            print(f"  {region_id:15s} - {info['name']:25s} {bounds}")
        print("=" * 70)
        return 0
    
    if not args.region:
        print("❌ No region specified!")
        print("Usage: python downloaders/japan_gsi.py <region> [--auto|--manual]")
        print("Or: python downloaders/japan_gsi.py --list")
        return 1
    
    region_id = args.region.lower().replace(' ', '_').replace('-', '_')
    
    if region_id not in JAPAN_REGIONS:
        print(f"❌ Unknown region: {args.region}")
        print("Run with --list to see available regions")
        return 1
    
    region_info = JAPAN_REGIONS[region_id]
    bounds = region_info['bounds']
    name = region_info['name']
    
    print(f"\n🗾 Japan Elevation Downloader")
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
            print(f"\n✅ Download complete!")
            print(f"\n⚠️  Note: This is 30m SRTM data, not highest-res GSI.")
            print(f"   For 5-10m resolution, run:")
            print(f"   python downloaders/japan_gsi.py {region_id} --manual")
            
            # Run the automated pipeline
            try:
                run_pipeline(
                    raw_tif_path=output_path,
                    region_id=region_id,
                    source='srtm_30m',
                    boundary_name=None,  # No specific boundary for Japan
                    skip_clip=True
                )
            except Exception as e:
                print(f"\n⚠️  Pipeline error: {e}")
                print("Raw data was downloaded successfully, but post-processing failed.")
                return 1
        else:
            print(f"\n❌ Download failed.")
        
        return 0 if success else 1
    else:
        print("\n❓ Please specify download method:")
        print(f"   --auto    : Automated download (30m SRTM global fallback)")
        print(f"   --manual  : Show instructions for GSI download (5-10m, best quality)")
        print(f"\nExample:")
        print(f"   python downloaders/japan_gsi.py {region_id} --auto")
        return 1


if __name__ == "__main__":
    sys.exit(main())

