"""
Example script demonstrating border drawing and country masking features.

This shows how to:
1. Draw country borders on elevation maps
2. Mask/clip data to specific country boundaries
3. List available countries
4. Work with multi-country regions
"""
import sys
from pathlib import Path

from src.data_processing import prepare_visualization_data
from src.rendering import render_visualization
from src.borders import get_border_manager


def example_1_draw_borders_on_usa():
 """
 Example 1: Draw USA borders on an existing USA elevation map.
 This overlays red border lines without clipping the data.
 """
 print("\n" + "="*70)
 print("EXAMPLE 1: Draw USA Borders (No Clipping)")
 print("="*70)

 tif_file = "data/usa_elevation/nationwide_usa_elevation.tif"

 if not Path(tif_file).exists():
 print(f"[!] File not found: {tif_file}")
 print(" Please download USA elevation data first.")
 return

# Load data WITHOUT masking
 data = prepare_visualization_data(tif_file, mask_usa=False)

# Render with borders drawn
 render_visualization(
 data,
 output_dir="generated/borders_examples",
 filename_prefix="usa_with_borders",
 draw_borders="United States of America",# Draw USA borders
 border_color="#00FF00",# Green borders
 border_width=2.0,
 tif_path=tif_file,# Required for border drawing
 autocrop=True
 )

 print("\n Created map with USA borders drawn in green")


def example_2_mask_to_usa_only():
 """
 Example 2: Mask data to USA boundaries only.
 This clips the elevation data so only USA territory is visible.
 """
 print("\n" + "="*70)
 print("EXAMPLE 2: Mask/Clip Data to USA Only")
 print("="*70)

 tif_file = "data/usa_elevation/nationwide_usa_elevation.tif"

 if not Path(tif_file).exists():
 print(f"[!] File not found: {tif_file}")
 print(" Please download USA elevation data first.")
 return

# Load data WITH masking to USA borders
 data = prepare_visualization_data(
 tif_file,
 mask_country="United States of America",# Clip to USA
 border_resolution='110m'
 )

# Render without borders (data is already clipped)
 render_visualization(
 data,
 output_dir="generated/borders_examples",
 filename_prefix="usa_masked_only",
 draw_borders=False,# Don't draw borders
 autocrop=True
 )

 print("\n Created map with data clipped to USA boundaries")


def example_3_mask_and_draw_borders():
 """
 Example 3: Both mask data to USA AND draw the border line.
 This combines clipping with visible borders.
 """
 print("\n" + "="*70)
 print("EXAMPLE 3: Mask Data + Draw Borders")
 print("="*70)

 tif_file = "data/usa_elevation/nationwide_usa_elevation.tif"

 if not Path(tif_file).exists():
 print(f"[!] File not found: {tif_file}")
 print(" Please download USA elevation data first.")
 return

# Load data WITH masking
 data = prepare_visualization_data(
 tif_file,
 mask_country="United States of America"
 )

# Render WITH borders
 render_visualization(
 data,
 output_dir="generated/borders_examples",
 filename_prefix="usa_masked_with_borders",
 draw_borders="United States of America",
 border_color="#FF0000",# Red borders
 border_width=2.5,
 tif_path=tif_file,
 autocrop=True
 )

 print("\n Created map with clipped data and visible borders")


def example_4_auto_detect_borders():
 """
 Example 4: Auto-detect and draw all countries in the bounding box.
 Useful for multi-country regions.
 """
 print("\n" + "="*70)
 print("EXAMPLE 4: Auto-Detect Countries from Bounding Box")
 print("="*70)

 tif_file = "data/usa_elevation/nationwide_usa_elevation.tif"

 if not Path(tif_file).exists():
 print(f"[!] File not found: {tif_file}")
 print(" Please download USA elevation data first.")
 return

# Load data without masking (show all countries in region)
 data = prepare_visualization_data(tif_file, mask_usa=False)

# Render with auto-detected borders
 render_visualization(
 data,
 output_dir="generated/borders_examples",
 filename_prefix="usa_auto_borders",
 draw_borders=True,# Auto-detect from bbox
 border_color="#FFFF00",# Yellow borders
 border_width=2.0,
 tif_path=tif_file,
 autocrop=True
 )

 print("\n Created map with auto-detected country borders")


def example_5_multiple_countries():
 """
 Example 5: Work with multiple countries (e.g., North America).
 """
 print("\n" + "="*70)
 print("EXAMPLE 5: Multiple Countries")
 print("="*70)

 tif_file = "data/usa_elevation/nationwide_usa_elevation.tif"

 if not Path(tif_file).exists():
 print(f"[!] File not found: {tif_file}")
 print(" Please download USA elevation data first.")
 return

# Load data without masking
 data = prepare_visualization_data(tif_file, mask_usa=False)

# Draw borders for multiple countries
 render_visualization(
 data,
 output_dir="generated/borders_examples",
 filename_prefix="north_america_borders",
 draw_borders=["United States of America", "Canada", "Mexico"],
 border_color="#00FFFF",# Cyan borders
 border_width=2.0,
 tif_path=tif_file,
 autocrop=True
 )

 print("\n Created map with USA, Canada, and Mexico borders")


def example_6_list_available_countries():
 """
 Example 6: List all available countries from Natural Earth.
 """
 print("\n" + "="*70)
 print("EXAMPLE 6: List Available Countries")
 print("="*70)

 border_manager = get_border_manager()

 print("\nLoading country list...")
 countries = border_manager.list_countries(resolution='110m')

 print(f"\nTotal countries available: {len(countries)}")
 print("\nFirst 20 countries:")
 for i, country in enumerate(countries[:20], 1):
 print(f" {i:2d}. {country}")

 print(f"\n... and {len(countries) - 20} more")
 print("\nNote: Use these exact names when specifying mask_country or draw_borders")


def example_7_high_resolution_borders():
 """
 Example 7: Use high-resolution borders for detailed views.
 """
 print("\n" + "="*70)
 print("EXAMPLE 7: High Resolution Borders (10m)")
 print("="*70)

 tif_file = "data/regions/california_central.tif"

 if not Path(tif_file).exists():
 print(f"[!] File not found: {tif_file}")
 print(" This example requires a regional dataset.")
 return

# Load data
 data = prepare_visualization_data(tif_file, mask_usa=False)

# Render with high-resolution borders (10m)
 render_visualization(
 data,
 output_dir="generated/borders_examples",
 filename_prefix="california_highres_borders",
 draw_borders="United States of America",
 border_color="#FF00FF",# Magenta
 border_width=1.5,
 border_resolution='10m',# High detail!
 tif_path=tif_file,
 autocrop=True
 )

 print("\n Created map with high-resolution (10m) borders")


def main():
 """Run all examples or specific ones."""
 import argparse

 parser = argparse.ArgumentParser(
 description='Border drawing and masking examples',
 formatter_class=argparse.RawDescriptionHelpFormatter,
 epilog="""
Examples:
 python example_borders.py# Run all examples
 python example_borders.py --example 1# Run example 1 only
 python example_borders.py --list# List available countries
 """
 )
 parser.add_argument(
 '--example', '-e',
 type=int,
 choices=range(1, 8),
 help='Run a specific example (1-7)'
 )
 parser.add_argument(
 '--list', '-l',
 action='store_true',
 help='List available countries'
 )

 args = parser.parse_args()

 if args.list:
 example_6_list_available_countries()
 return 0

 examples = {
 1: example_1_draw_borders_on_usa,
 2: example_2_mask_to_usa_only,
 3: example_3_mask_and_draw_borders,
 4: example_4_auto_detect_borders,
 5: example_5_multiple_countries,
 6: example_6_list_available_countries,
 7: example_7_high_resolution_borders,
 }

 if args.example:
 examples[args.example]()
 else:
# Run all examples
 print("\n" + "="*70)
 print("RUNNING ALL BORDER EXAMPLES")
 print("="*70)

 for example_func in examples.values():
 try:
 example_func()
 except Exception as e:
 print(f"\n[!] Error in example: {e}")
 continue

 print("\n" + "="*70)
 print("COMPLETE! Check generated/borders_examples/ for output files")
 print("="*70)

 return 0


if __name__ == "__main__":
 sys.exit(main())

