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

from downloaders.usa_3dep import download_opentopography_srtm# Reuse SRTM downloader
from src.regions_config import ALL_REGIONS

# Regions now come from centralized config in src/regions_config.py


def print_manual_instructions(region_id: str, bounds: Tuple[float, float, float, float]) -> None:
 """
 Print instructions for manually downloading SwissTopo elevation data.

 Args:
 region_id: Region identifier
 bounds: (west, south, east, north) in degrees
 """
 west, south, east, north = bounds

 print("\n" + "="* 80)
 print("MANUAL DOWNLOAD INSTRUCTIONS - SWISSTOPO (0.5-2m, HIGHEST QUALITY)")
 print("="* 80)
 print(f"\nRegion: {region_id}")
 print(f"Bounds: West={west:.2f}, South={south:.2f}, East={east:.2f}, North={north:.2f}")
 print("\n Steps:")
 print("\n1. Go to SwissTopo Data Portal:")
 print(" https://www.swisstopo.admin.ch/en/geodata.html")
 print("\n2. Navigate to Elevation Models:")
 print(" - Click 'Height models' or 'Digital Elevation Models'")
 print(" - Choose from available options:")
 print(" - swissALTI3D: 0.5m-2m resolution (highest quality)")
 print(" - DHM25: 25m resolution (older, full coverage)")
 print("\n3. Access the data:")
 print(" - Option A: Direct download (may require registration)")
 print(" - Option B: Via geodata portal")
 print(" - Some datasets are free, others may require licensing")
 print("\n4. Select your region:")
 print(f" - Use map interface to select area")
 print(f" - Coordinates: {west:.2f}deg to {east:.2f}degE, {south:.2f}deg to {north:.2f}degN")
 print("\n5. Download format:")
 print(" - Choose 'GeoTIFF' format")
 print(" - May also be available as: XYZ, ESRI Grid, LAS/LAZ (point cloud)")
 print(f"\n6. Save as: data/raw/switzerland_swisstopo/{region_id}_bbox_2m.tif")
 print("\n ALTERNATIVE: Use STAC API (Advanced Users)")
 print("\n1. SwissTopo STAC Catalog:")
 print(" https://www.geocat.ch/geonetwork/srv/eng/catalog.search#/home")
 print("\n2. Search for 'swissALTI3D' or 'DHM'")
 print("\n3. Download via API or direct links")
 print("\n" + "="* 80)
 print(" Notes:")
 print(" - swissALTI3D: 0.5-2m resolution, extremely high quality")
 print(" - Some datasets require SwissTopo account (free registration)")
 print(" - Commercial use may require different licensing")
 print(" - Switzerland-only coverage (does not extend beyond borders)")
 print("="* 80 + "\n")


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
 print("\nAVAILABLE REGIONS (from centralized config):")
 print("="* 70)
# Filter to show only regions with bounds that overlap Switzerland
 switzerland_bounds = (5.9, 45.8, 10.5, 47.8)
 for region_id, config in sorted(ALL_REGIONS.items()):
# Show region if bounds overlap Switzerland area
 if (config.bounds[0] < switzerland_bounds[2] and config.bounds[2] > switzerland_bounds[0] and
 config.bounds[1] < switzerland_bounds[3] and config.bounds[3] > switzerland_bounds[1]):
 print(f" {region_id:20s} - {config.name:30s}")
 print("="* 70)
 print("\nUsage: python downloaders/switzerland_swisstopo.py <region_id> [--auto|--manual]")
 print("\nNote: Regions are from centralized config (src/regions_config.py)")
 return 0

 if not args.region:
 print(" No region specified!")
 print("Usage: python downloaders/switzerland_swisstopo.py <region> [--auto|--manual]")
 print("Or: python downloaders/switzerland_swisstopo.py --list")
 return 1

 region_id = args.region.lower().replace(' ', '_').replace('-', '_')

 if region_id not in ALL_REGIONS:
 print(f" Unknown region: {args.region}")
 print("Run with --list to see available regions")
 return 1

 config = ALL_REGIONS[region_id]
 bounds = config.bounds
 name = config.name

 print(f"\nSwitzerland Elevation Downloader")
 print(f"="* 70)
 print(f"Region: {name} ({region_id})")
 print(f"Bounds: {bounds}")
 print(f"="* 70)

 if args.manual:
 print_manual_instructions(region_id, bounds)
 return 0
 elif args.auto:
 output_path = Path(args.output_dir) / f"{region_id}_bbox_30m.tif"
 success = download_opentopography_srtm(region_id, bounds, output_path, args.api_key)

 if success:
 print(f"\n Success! Data saved to: {output_path}")
 print(f"\n Note: This is 30m SRTM data, not highest-res SwissTopo.")
 print(f" For 0.5-2m resolution, run:")
 print(f" python downloaders/switzerland_swisstopo.py {region_id} --manual")
 else:
 print(f"\n Download failed.")

 return 0 if success else 1
 else:
 print("\n Please specify download method:")
 print(f" --auto : Automated download (30m SRTM global fallback)")
 print(f" --manual : Show instructions for SwissTopo download (0.5-2m, best quality)")
 print(f"\nExample:")
 print(f" python downloaders/switzerland_swisstopo.py {region_id} --auto")
 return 1


if __name__ == "__main__":
 sys.exit(main())

