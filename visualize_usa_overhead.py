"""
Main orchestration script for creating the continental USA overhead elevation view.

This script coordinates the data processing and rendering steps.
"""
import sys
from pathlib import Path
import io

# Fix Windows console encoding if necessary
if sys.platform == 'win32':
 sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
 sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
 from src.data_processing import prepare_visualization_data
 from src.rendering import render_visualization
except ImportError as e:
 print(f"Error importing modules: {e}")
 print("Please ensure you are running from the project root and src/ is in your PYTHONPATH.")
 sys.exit(1)

def main():
 """Main entry point."""
 import argparse

 parser = argparse.ArgumentParser(
 description='Create overhead space view of continental USA elevation'
 )
 parser.add_argument(
 'tif_file',
 nargs='?',
 default='data/usa_elevation/nationwide_usa_elevation.tif',
 help='Path to GeoTIFF elevation file'
 )
 parser.add_argument(
 '--output', '-o',
 default='generated',
 help='Output directory'
 )
 parser.add_argument(
 '--bucket-miles',
 type=float,
 default=None,
 help='Apply square bucketing: divide map into NxN mile squares and take MAX elevation in each. Accounts for Earth\'s curvature. Example: --bucket-miles 10'
 )
 parser.add_argument(
 '--bucket-pixels',
 type=int,
 default=None,
 help='Apply simple pixel bucketing: divide map into NxN pixel squares and take MAX elevation in each. Ignores geographic distances. Example: --bucket-pixels 100'
 )
 parser.add_argument(
 '--camera-elevation',
 type=float,
 default=35,
 help='Camera elevation angle in degrees (0=horizon, 90=overhead). Default: 35'
 )
 parser.add_argument(
 '--camera-azimuth',
 type=float,
 default=45,
 help='Camera azimuth angle in degrees (0-360 rotation). Default: 45'
 )
 parser.add_argument(
 '--vertical-exaggeration',
 type=float,
 default=4.0,
 help='Vertical scale relative to horizontal. 1.0 = true Earth scale, 0.1-50.0 range (default: 4.0)'
 )
 parser.add_argument(
 '--projection-zoom',
 type=float,
 default=0.99,
 help='Viewport fill ratio (0.90-0.99, higher=tighter framing). Default: 0.99'
 )
 parser.add_argument(
 '--render-bars',
 action='store_true',
 help='Render as 3D rectangular prisms instead of smooth surface. Auto-enabled when bucketing is used.'
 )
 parser.add_argument(
 '--render-surface',
 action='store_true',
 help='Force smooth surface rendering even when bucketing is used.'
 )

# Resolution & Quality
 parser.add_argument(
 '--dpi',
 type=int,
 default=100,
 help='Output DPI (dots per inch). Higher = larger file. Default: 100'
 )
 parser.add_argument(
 '--scale-factor',
 type=float,
 default=4.0,
 help='Output resolution multiplier from data size. Higher = more detail. Default: 4.0'
 )
 parser.add_argument(
 '--max-viz-size',
 type=int,
 default=800,
 help='Maximum dimension for visualization grid (downsamples if larger). Default: 800'
 )

# Visual Style
 parser.add_argument(
 '--colormap',
 type=str,
 default='terrain',
 choices=['terrain', 'viridis', 'plasma', 'inferno', 'earth', 'ocean', 'grayscale'],
 help='Color scheme for elevation. Default: terrain'
 )
 parser.add_argument(
 '--background-color',
 type=str,
 default='#000000',
 help='Background color (hex code). Default:#000000 (black)'
 )
 parser.add_argument(
 '--light-azimuth',
 type=float,
 default=315,
 help='Light source azimuth for hillshading (0-360). Default: 315'
 )
 parser.add_argument(
 '--light-altitude',
 type=float,
 default=60,
 help='Light source altitude for hillshading (0-90). Default: 60'
 )

# Output Options
 parser.add_argument(
 '--filename-prefix',
 type=str,
 default=None,
 help='Custom prefix for output filename. Default: timestamp'
 )
 parser.add_argument(
 '--no-overlays',
 action='store_true',
 help='Disable text overlays (clean visualization only)'
 )
 parser.add_argument(
 '--no-autocrop',
 action='store_true',
 help='Disable automatic cropping of black borders'
 )
 parser.add_argument(
 '--gen-nine',
 action='store_true',
 help='Auto-generate 9 views from different camera positions (overrides camera settings)'
 )

 args = parser.parse_args()

# Determine render_as_bars parameter
 if args.render_surface:
 render_as_bars = False
 elif args.render_bars:
 render_as_bars = True
 else:
 render_as_bars = None# Auto-detect based on bucketing

# --- Step 1: Data Processing ---
 tif_file_path = Path(args.tif_file)
 if not tif_file_path.exists():
 print(f"\n Error: File not found: {tif_file_path}")
 print(" Download with: python download_continental_usa.py --region nationwide_usa --yes")
 return 1

 visualization_data = prepare_visualization_data(
 str(tif_file_path),
 square_bucket_miles=args.bucket_miles,
 square_bucket_pixels=args.bucket_pixels
 )

# --- Step 2: Rendering ---
 if args.gen_nine:
# Generate 9 different viewpoints with varied heights and angles
 nine_views = [
 {"name": "overhead", "elevation": 90, "azimuth": 0, "desc": "Overhead (Satellite View)"},
 {"name": "north_high", "elevation": 50, "azimuth": 0, "desc": "North View (High)"},
 {"name": "northeast", "elevation": 35, "azimuth": 45, "desc": "Northeast View (Mid)"},
 {"name": "east_low", "elevation": 20, "azimuth": 90, "desc": "East View (Low)"},
 {"name": "southeast", "elevation": 40, "azimuth": 135, "desc": "Southeast View (Mid-High)"},
 {"name": "south", "elevation": 30, "azimuth": 180, "desc": "South View (Mid)"},
 {"name": "southwest_low", "elevation": 15, "azimuth": 225, "desc": "Southwest View (Very Low)"},
 {"name": "west", "elevation": 45, "azimuth": 270, "desc": "West View (Mid-High)"},
 {"name": "northwest", "elevation": 25, "azimuth": 315, "desc": "Northwest View (Low-Mid)"},
 ]

 print("\n" + "="* 70)
 print(" GENERATING 9 VIEWPOINTS")
 print("="* 70)

 for i, view in enumerate(nine_views, 1):
 print(f"\n{'='*70}")
 print(f" VIEW {i}/9: {view['desc']}")
 print(f" Camera: Elevation {view['elevation']}deg, Azimuth {view['azimuth']}deg")
 print(f"{'='*70}")

# Create filename prefix with view name
 view_prefix = f"{args.filename_prefix}_{view['name']}" if args.filename_prefix else f"view_{view['name']}"

# Build command line string for reproduction
 cmd_parts = ["python visualize_usa_overhead.py"]
 if args.bucket_miles:
 cmd_parts.append(f"--bucket-miles {args.bucket_miles}")
 if args.bucket_pixels:
 cmd_parts.append(f"--bucket-pixels {args.bucket_pixels}")
 cmd_parts.append(f"--camera-elevation {view['elevation']}")
 cmd_parts.append(f"--camera-azimuth {view['azimuth']}")
 if args.vertical_exaggeration != 4.0:
 cmd_parts.append(f"--vertical-exaggeration {args.vertical_exaggeration}")
 if args.projection_zoom != 0.99:
 cmd_parts.append(f"--projection-zoom {args.projection_zoom}")
 if render_as_bars is True:
 cmd_parts.append("--render-bars")
 elif render_as_bars is False:
 cmd_parts.append("--render-surface")
 if args.dpi != 100:
 cmd_parts.append(f"--dpi {args.dpi}")
 if args.scale_factor != 4.0:
 cmd_parts.append(f"--scale-factor {args.scale_factor}")
 if args.max_viz_size != 800:
 cmd_parts.append(f"--max-viz-size {args.max_viz_size}")
 if args.colormap != 'terrain':
 cmd_parts.append(f"--colormap {args.colormap}")
 if args.background_color != '#000000':
 cmd_parts.append(f"--background-color \"{args.background_color}\"")
 if args.light_azimuth != 315:
 cmd_parts.append(f"--light-azimuth {args.light_azimuth}")
 if args.light_altitude != 60:
 cmd_parts.append(f"--light-altitude {args.light_altitude}")
 if args.no_overlays:
 cmd_parts.append("--no-overlays")
 if args.no_autocrop:
 cmd_parts.append("--no-autocrop")
 cmd_line = " ".join(cmd_parts)

# Only open browser for the last view
 is_last_view = (i == len(nine_views))

 render_visualization(
 visualization_data,
 args.output,
 camera_elevation=view['elevation'],
 camera_azimuth=view['azimuth'],
 vertical_exaggeration=args.vertical_exaggeration,
 projection_zoom=args.projection_zoom,
 render_as_bars=render_as_bars,
 dpi=args.dpi,
 scale_factor=args.scale_factor,
 max_viz_size=args.max_viz_size,
 colormap=args.colormap,
 background_color=args.background_color,
 light_azimuth=args.light_azimuth,
 light_altitude=args.light_altitude,
 filename_prefix=view_prefix,
 show_overlays=not args.no_overlays,
 autocrop=not args.no_autocrop,
 open_browser=is_last_view,
 command_line_str=cmd_line
 )

 print("\n" + "="* 70)
 print(" ALL 9 VIEWPOINTS COMPLETE!")
 print("="* 70)
 else:
# Single render with specified camera settings
# Build command line string for reproduction
 cmd_parts = ["python visualize_usa_overhead.py"]
 if args.bucket_miles:
 cmd_parts.append(f"--bucket-miles {args.bucket_miles}")
 if args.bucket_pixels:
 cmd_parts.append(f"--bucket-pixels {args.bucket_pixels}")
 if args.camera_elevation != 35:
 cmd_parts.append(f"--camera-elevation {args.camera_elevation}")
 if args.camera_azimuth != 45:
 cmd_parts.append(f"--camera-azimuth {args.camera_azimuth}")
 if args.vertical_exaggeration != 8.0:
 cmd_parts.append(f"--vertical-exaggeration {args.vertical_exaggeration}")
 if args.projection_zoom != 0.99:
 cmd_parts.append(f"--projection-zoom {args.projection_zoom}")
 if render_as_bars is True:
 cmd_parts.append("--render-bars")
 elif render_as_bars is False:
 cmd_parts.append("--render-surface")
 if args.dpi != 100:
 cmd_parts.append(f"--dpi {args.dpi}")
 if args.scale_factor != 4.0:
 cmd_parts.append(f"--scale-factor {args.scale_factor}")
 if args.max_viz_size != 800:
 cmd_parts.append(f"--max-viz-size {args.max_viz_size}")
 if args.colormap != 'terrain':
 cmd_parts.append(f"--colormap {args.colormap}")
 if args.background_color != '#000000':
 cmd_parts.append(f"--background-color \"{args.background_color}\"")
 if args.light_azimuth != 315:
 cmd_parts.append(f"--light-azimuth {args.light_azimuth}")
 if args.light_altitude != 60:
 cmd_parts.append(f"--light-altitude {args.light_altitude}")
 if args.filename_prefix:
 cmd_parts.append(f"--filename-prefix \"{args.filename_prefix}\"")
 if args.no_overlays:
 cmd_parts.append("--no-overlays")
 if args.no_autocrop:
 cmd_parts.append("--no-autocrop")
 cmd_line = " ".join(cmd_parts)

 render_visualization(
 visualization_data,
 args.output,
 camera_elevation=args.camera_elevation,
 camera_azimuth=args.camera_azimuth,
 vertical_exaggeration=args.vertical_exaggeration,
 projection_zoom=args.projection_zoom,
 render_as_bars=render_as_bars,
 dpi=args.dpi,
 scale_factor=args.scale_factor,
 max_viz_size=args.max_viz_size,
 colormap=args.colormap,
 background_color=args.background_color,
 light_azimuth=args.light_azimuth,
 light_altitude=args.light_altitude,
 filename_prefix=args.filename_prefix,
 show_overlays=not args.no_overlays,
 autocrop=not args.no_autocrop,
 command_line_str=cmd_line
 )

 return 0

if __name__ == "__main__":
 sys.exit(main())

