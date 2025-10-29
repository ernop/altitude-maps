"""
Utility script for exploring and working with geographic borders.

Provides command-line tools to:
- List available countries
- Search for country names
- View countries in a specific region
- Test border drawing on elevation data
"""
import sys
import argparse
from pathlib import Path

from src.borders import get_border_manager


def list_countries(resolution='110m', search=None):
 """
 List all available countries, optionally filtered by search term.

 Args:
 resolution: Border resolution ('10m', '50m', or '110m')
 search: Optional search term to filter countries
 """
 print(f"\n{'='*70}")
 print(f"Available Countries (Natural Earth {resolution})")
 print(f"{'='*70}\n")

 border_manager = get_border_manager()
 countries = border_manager.list_countries(resolution=resolution)

 if search:
 countries = [c for c in countries if search.lower() in c.lower()]
 print(f"Filtered by '{search}': {len(countries)} matches\n")
 else:
 print(f"Total: {len(countries)} countries\n")

 for i, country in enumerate(countries, 1):
 print(f" {i:3d}. {country}")

 print()


def countries_in_bbox(bbox_str, resolution='110m'):
 """
 Find countries within a bounding box.

 Args:
 bbox_str: Bounding box as "left,bottom,right,top" (lon/lat)
 resolution: Border resolution
 """
 try:
 bbox = tuple(map(float, bbox_str.split(',')))
 if len(bbox) != 4:
 raise ValueError("Bbox must have 4 values")
 except Exception as e:
 print(f"\n[!] Error parsing bbox: {e}")
 print(" Format: left,bottom,right,top (e.g., -125,25,-65,50)")
 return

 print(f"\n{'='*70}")
 print(f"Countries in Bounding Box")
 print(f"{'='*70}")
 print(f"Bbox: {bbox}")
 print(f" Left: {bbox[0]}deg, Bottom: {bbox[1]}deg")
 print(f" Right: {bbox[2]}deg, Top: {bbox[3]}deg\n")

 border_manager = get_border_manager()
 countries_gdf = border_manager.get_countries_in_bbox(bbox, resolution=resolution)

 if countries_gdf.empty:
 print("No countries found in this bounding box.")
 return

 countries = sorted(countries_gdf.ADMIN.tolist())
 print(f"Found {len(countries)} countries:\n")

 for i, country in enumerate(countries, 1):
 print(f" {i:2d}. {country}")

 print()


def country_info(country_name, resolution='110m'):
 """
 Show information about a specific country.

 Args:
 country_name: Country name to look up
 resolution: Border resolution
 """
 print(f"\n{'='*70}")
 print(f"Country Information")
 print(f"{'='*70}\n")

 border_manager = get_border_manager()
 country = border_manager.get_country(country_name, resolution=resolution)

 if country is None or country.empty:
 print(f"[!] Country '{country_name}' not found.")
 print("\nTry searching with: python border_utils.py --list --search <term>")
 return

# Get first match
 country_data = country.iloc[0]

 print(f"Name: {country_data.ADMIN}")
 print(f"ISO Code: {country_data.get('ISO_A3', 'N/A')}")
 print(f"Continent: {country_data.get('CONTINENT', 'N/A')}")
 print(f"Region: {country_data.get('REGION_UN', 'N/A')}")
 print(f"Subregion: {country_data.get('SUBREGION', 'N/A')}")

# Get bounding box
 bounds = country_data.geometry.bounds
 print(f"\nBounding Box:")
 print(f" West: {bounds[0]:.4f}deg")
 print(f" South: {bounds[1]:.4f}deg")
 print(f" East: {bounds[2]:.4f}deg")
 print(f" North: {bounds[3]:.4f}deg")

# Get border coordinates
 border_coords = border_manager.get_border_coordinates(
 country_name,
 resolution=resolution
 )

 print(f"\nBorder segments: {len(border_coords)}")
 total_points = sum(len(coords[0]) for coords in border_coords)
 print(f"Total border points: {total_points:,}")

 print()


def test_borders_on_file(tif_file, countries=None, output_dir="generated/border_test"):
 """
 Test drawing borders on an elevation file.

 Args:
 tif_file: Path to GeoTIFF elevation file
 countries: Country name(s) to draw borders for (or None for auto-detect)
 output_dir: Output directory for test visualization
 """
 tif_path = Path(tif_file)

 if not tif_path.exists():
 print(f"\n[!] File not found: {tif_file}")
 return

 print(f"\n{'='*70}")
 print(f"Testing Border Drawing")
 print(f"{'='*70}")
 print(f"Input: {tif_file}")
 print(f"Countries: {countries if countries else 'Auto-detect'}\n")

 from src.data_processing import prepare_visualization_data
 from src.rendering import render_visualization

# Load data without masking
 print("[1/2] Loading elevation data...")
 data = prepare_visualization_data(str(tif_path), mask_usa=False)

# Render with borders
 print("[2/2] Rendering with borders...")

 if countries:
 country_list = [c.strip() for c in countries.split(',')]
 draw_borders = country_list
 else:
 draw_borders = True# Auto-detect

 render_visualization(
 data,
 output_dir=output_dir,
 filename_prefix="border_test",
 draw_borders=draw_borders,
 border_color="#00FF00",# Green
 border_width=2.0,
 tif_path=str(tif_path),
 autocrop=True
 )

 print(f"\n Complete! Check {output_dir}/ for output files")


def main():
 parser = argparse.ArgumentParser(
 description='Utility for working with geographic borders',
 formatter_class=argparse.RawDescriptionHelpFormatter,
 epilog="""
Examples:
# List all countries
 python border_utils.py --list

# Search for countries
 python border_utils.py --list --search "United"

# Get info about a country
 python border_utils.py --info "United States of America"

# Find countries in a region (USA bbox)
 python border_utils.py --bbox "-125,25,-65,50"

# Test borders on an elevation file
 python border_utils.py --test data/usa_elevation/nationwide_usa_elevation.tif

# Test specific countries
 python border_utils.py --test data/usa.tif --countries "United States of America,Canada"
 """
 )

 parser.add_argument(
 '--list', '-l',
 action='store_true',
 help='List all available countries'
 )

 parser.add_argument(
 '--search', '-s',
 type=str,
 help='Search for countries matching this term (use with --list)'
 )

 parser.add_argument(
 '--info', '-i',
 type=str,
 metavar='COUNTRY',
 help='Show information about a specific country'
 )

 parser.add_argument(
 '--bbox', '-b',
 type=str,
 metavar='LEFT,BOTTOM,RIGHT,TOP',
 help='Find countries in bounding box (lon/lat coordinates)'
 )

 parser.add_argument(
 '--test', '-t',
 type=str,
 metavar='TIF_FILE',
 help='Test border drawing on an elevation file'
 )

 parser.add_argument(
 '--countries', '-c',
 type=str,
 help='Comma-separated country names for --test (e.g., "USA,Canada")'
 )

 parser.add_argument(
 '--resolution', '-r',
 type=str,
 choices=['10m', '50m', '110m'],
 default='110m',
 help='Border resolution (default: 110m)'
 )

 parser.add_argument(
 '--output', '-o',
 type=str,
 default='generated/border_test',
 help='Output directory for --test (default: generated/border_test)'
 )

 args = parser.parse_args()

# Execute commands
 if args.list:
 list_countries(resolution=args.resolution, search=args.search)

 elif args.info:
 country_info(args.info, resolution=args.resolution)

 elif args.bbox:
 countries_in_bbox(args.bbox, resolution=args.resolution)

 elif args.test:
 test_borders_on_file(
 args.test,
 countries=args.countries,
 output_dir=args.output
 )

 else:
 parser.print_help()
 return 1

 return 0


if __name__ == "__main__":
 sys.exit(main())

