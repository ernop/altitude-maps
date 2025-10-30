"""
Visualize real USA elevation data with beautiful 3D rendering.

Creates stunning raytraced-style visualizations from actual USGS elevation data.
"""

import sys
import io
import argparse
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import LightSource
import seaborn as sns
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
 sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
 sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import rasterio
from rasterio.plot import show


class RealDataVisualizer:
 """Creates beautiful visualizations from real elevation data."""

 def __init__(self, output_dir: str = "generated"):
 """Initialize the visualizer."""
 self.output_dir = Path(output_dir)
 self.output_dir.mkdir(exist_ok=True)
 self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Set style for beautiful output
 sns.set_style("dark")
 plt.rcParams['figure.facecolor'] = '#0a0a0a'

 def _get_output_path(self, description: str) -> Path:
 """Generate timestamped output filename."""
 filename = f"{self.timestamp}_{description}.png"
 return self.output_dir / filename

 def load_elevation_data(self, tif_path: str) -> tuple:
 """
 Load elevation data from GeoTIFF file.

 Returns:
 (elevation_array, metadata_dict)
 """
 print(f"\n Loading: {tif_path}")

 with rasterio.open(tif_path) as src:
 elevation = src.read(1)# Read first band

# Get metadata
 metadata = {
 'bounds': src.bounds,
 'crs': src.crs,
 'width': src.width,
 'height': src.height,
 'transform': src.transform,
 'nodata': src.nodata
 }

# Handle nodata values
 if metadata['nodata'] is not None:
 elevation = np.where(elevation == metadata['nodata'], np.nan, elevation)

 print(f" Shape: {elevation.shape}")
 print(f" Elevation range: {np.nanmin(elevation):.1f}m to {np.nanmax(elevation):.1f}m")
 print(f" Resolution: ~{abs(src.transform[0])* 111000:.1f}m per pixel")

 return elevation, metadata

 def create_raytraced_3d(self, elevation: np.ndarray, metadata: dict,
 vertical_exaggeration: float = 4.0,
 azimuth: float = 315, altitude: float = 45) -> None:
 """
 Create a beautiful raytraced-style 3D visualization.

 Args:
 elevation: 2D array of elevation values
 metadata: Metadata dictionary
 vertical_exaggeration: Vertical scale relative to horizontal. 1.0 = true Earth scale (default 4.0)
 azimuth: Light source direction (0-360 degrees)
 altitude: Light source angle (0-90 degrees)
 """
 print("\n Creating raytraced 3D visualization...")

# Create figure with dark background
 fig = plt.figure(figsize=(20, 16), facecolor='#0a0a0a')
 ax = fig.add_subplot(111, projection='3d', facecolor='#0a0a0a')

# Downsample if too large (for performance)
 max_size = 500
 if elevation.shape[0] > max_size or elevation.shape[1] > max_size:
 step = max(elevation.shape[0] // max_size, elevation.shape[1] // max_size)
 elevation_display = elevation[::step, ::step]
 print(f" Downsampled to {elevation_display.shape} for display")
 else:
 elevation_display = elevation

# Create coordinate grids
 y, x = np.mgrid[0:elevation_display.shape[0], 0:elevation_display.shape[1]]

# Apply vertical exaggeration
 z = elevation_display* vertical_exaggeration

# Create hillshade for realistic lighting
 ls = LightSource(azdeg=azimuth, altdeg=altitude)

# Normalize elevation for coloring
 z_norm = (elevation_display - np.nanmin(elevation_display)) / (np.nanmax(elevation_display) - np.nanmin(elevation_display))

# Create beautiful color gradient (terrain-inspired)
# Low elevation: deep blue/green, High elevation: brown/white
 colors = cm.terrain(z_norm)

# Apply hillshade lighting
 illuminated = ls.shade(z, cmap=cm.terrain, blend_mode='soft', vert_exag=1.0)

# Plot surface with lighting
 surf = ax.plot_surface(x, y, z,
 facecolors=illuminated,
 linewidth=0,
 antialiased=True,
 shade=True,
 alpha=0.95)

# Styling
 ax.set_xlabel('Longitude ->', fontsize=14, color='white', labelpad=15)
 ax.set_ylabel('Latitude ->', fontsize=14, color='white', labelpad=15)
 ax.set_zlabel('Elevation (m)', fontsize=14, color='white', labelpad=15)

# Set viewing angle
 ax.view_init(elev=30, azim=225)

# Dark theme
 ax.xaxis.pane.fill = False
 ax.yaxis.pane.fill = False
 ax.zaxis.pane.fill = False
 ax.xaxis.pane.set_edgecolor('#333333')
 ax.yaxis.pane.set_edgecolor('#333333')
 ax.zaxis.pane.set_edgecolor('#333333')
 ax.tick_params(colors='white', labelsize=10)
 ax.grid(True, alpha=0.2, color='white')

# Title with location information
 bounds = metadata['bounds']
 title = f'3D Terrain Visualization - USGS 10m Elevation Data\n'
 title += f'Location: {bounds.left:.2f}degW to {bounds.right:.2f}degW, {bounds.bottom:.2f}degN to {bounds.top:.2f}degN\n'
 title += f'Elevation: {np.nanmin(elevation):.0f}m - {np.nanmax(elevation):.0f}m | '
 title += f'Vertical Exaggeration: {vertical_exaggeration}x'
 ax.set_title(title, fontsize=16, color='white', pad=30, fontweight='bold')

 plt.tight_layout()

 output_path = self._get_output_path("real_terrain_raytraced_3d")
 plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='#0a0a0a')
 print(f" Saved: {output_path}")

 plt.show()

 def create_height_bars(self, elevation: np.ndarray, metadata: dict,
 bar_spacing: int = 20) -> None:
 """
 Create a visualization with height bars showing actual elevation.

 Args:
 elevation: 2D array of elevation values
 metadata: Metadata dictionary
 bar_spacing: Spacing between bars (in pixels)
 """
 print("\n Creating height bar visualization...")

 fig = plt.figure(figsize=(20, 16), facecolor='#0a0a0a')
 ax = fig.add_subplot(111, projection='3d', facecolor='#0a0a0a')

# Sample points for bars (not every pixel, or it would be too dense)
 y_coords = np.arange(0, elevation.shape[0], bar_spacing)
 x_coords = np.arange(0, elevation.shape[1], bar_spacing)

 print(f" Creating {len(y_coords)* len(x_coords)} height bars...")

# Normalize elevation for coloring
 elev_min, elev_max = np.nanmin(elevation), np.nanmax(elevation)

# Create bars
 for i, y in enumerate(y_coords):
 for j, x in enumerate(x_coords):
 if not np.isnan(elevation[y, x]):
 height = elevation[y, x]

# Color based on height
 color_val = (height - elev_min) / (elev_max - elev_min)
 color = cm.terrain(color_val)

# Draw bar from 0 to height
 ax.bar3d(x, y, 0,
 bar_spacing* 0.8, bar_spacing* 0.8, height,
 color=color, alpha=0.9, edgecolor='none')

# Styling
 ax.set_xlabel('Longitude ->', fontsize=14, color='white', labelpad=15)
 ax.set_ylabel('Latitude ->', fontsize=14, color='white', labelpad=15)
 ax.set_zlabel('Elevation (m)', fontsize=14, color='white', labelpad=15)

 ax.view_init(elev=35, azim=225)

# Dark theme
 ax.xaxis.pane.fill = False
 ax.yaxis.pane.fill = False
 ax.zaxis.pane.fill = False
 ax.xaxis.pane.set_edgecolor('#333333')
 ax.yaxis.pane.set_edgecolor('#333333')
 ax.zaxis.pane.set_edgecolor('#333333')
 ax.tick_params(colors='white', labelsize=10)
 ax.grid(True, alpha=0.2, color='white')

 bounds = metadata['bounds']
 title = f'Height Bar Visualization - USGS 10m Elevation Data\n'
 title += f'Location: {bounds.left:.2f}degW to {bounds.right:.2f}degW, {bounds.bottom:.2f}degN to {bounds.top:.2f}degN\n'
 title += f'{len(y_coords)* len(x_coords)} bars | Elevation: {elev_min:.0f}m - {elev_max:.0f}m'
 ax.set_title(title, fontsize=16, color='white', pad=30, fontweight='bold')

 plt.tight_layout()

 output_path = self._get_output_path("real_terrain_height_bars")
 plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='#0a0a0a')
 print(f" Saved: {output_path}")

 plt.show()

 def create_hillshade(self, elevation: np.ndarray, metadata: dict) -> None:
 """
 Create a beautiful hillshade map (aerial view with lighting).

 Args:
 elevation: 2D array of elevation values
 metadata: Metadata dictionary
 """
 print("\n Creating hillshade aerial view...")

 fig, ax = plt.subplots(figsize=(20, 16), facecolor='#0a0a0a')
 ax.set_facecolor('#0a0a0a')

# Create hillshade with multiple light sources for depth
 ls1 = LightSource(azdeg=315, altdeg=45)
 ls2 = LightSource(azdeg=135, altdeg=45)

# Blend two light sources
 shade1 = ls1.hillshade(elevation, vert_exag=2.0)
 shade2 = ls2.hillshade(elevation, vert_exag=2.0)
 shaded = (shade1* 0.7 + shade2* 0.3)

# Color the terrain
 colored = ls1.shade(elevation, cmap=cm.terrain, blend_mode='overlay',
 vert_exag=2.0, dx=1, dy=1)

 im = ax.imshow(colored, interpolation='bilinear', origin='upper')

# Add colorbar
 cbar = plt.colorbar(cm.ScalarMappable(cmap=cm.terrain), ax=ax, fraction=0.046, pad=0.04)
 cbar.set_label('Elevation (m)', rotation=270, labelpad=30, fontsize=14, color='white')
 cbar.ax.tick_params(colors='white', labelsize=12)

 bounds = metadata['bounds']
 title = f'Aerial Hillshade View - USGS 10m Elevation Data\n'
 title += f'Location: {bounds.left:.2f}degW to {bounds.right:.2f}degW, {bounds.bottom:.2f}degN to {bounds.top:.2f}degN'
 ax.set_title(title, fontsize=18, color='white', pad=20, fontweight='bold')
 ax.axis('off')

 plt.tight_layout()

 output_path = self._get_output_path("real_terrain_hillshade_aerial")
 plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='#0a0a0a')
 print(f" Saved: {output_path}")

 plt.show()


def main():
 """Main entry point."""
 parser = argparse.ArgumentParser(
 description='Visualize real USA elevation data with beautiful 3D rendering'
 )
 parser.add_argument(
 'tif_file',
 nargs='?',
 default='data/usa_elevation/denver_elevation_10m.tif',
 help='Path to GeoTIFF elevation file'
 )
 parser.add_argument(
 '--exaggeration', '-e',
 type=float,
 default=4.0,
 help='Vertical exaggeration factor. 1.0 = true Earth scale, 0.1-50.0 range (default: 4.0)'
 )
 parser.add_argument(
 '--output', '-o',
 default='generated',
 help='Output directory'
 )

 args = parser.parse_args()

 print("="* 70)
 print(" REAL TERRAIN VISUALIZER - USGS Elevation Data")
 print("="* 70)

# Check if file exists
 if not Path(args.tif_file).exists():
 print(f"\n Error: File not found: {args.tif_file}")
 print("\nAvailable data files:")
 data_dir = Path("data/usa_elevation")
 if data_dir.exists():
 for f in data_dir.glob("*.tif"):
 print(f" - {f}")
 else:
 print(" (No data downloaded yet)")
 print("\nDownload data with: python download_usa_region.py <region_name>")
 return 1

# Initialize visualizer
 visualizer = RealDataVisualizer(output_dir=args.output)

# Load data
 elevation, metadata = visualizer.load_elevation_data(args.tif_file)

# Create all visualizations
 print("\n" + "="* 70)
 print(" Creating Visualizations (this may take a moment...)")
 print("="* 70)

# 1. Hillshade aerial view (fastest)
 visualizer.create_hillshade(elevation, metadata)

# 2. Raytraced 3D surface
 visualizer.create_raytraced_3d(elevation, metadata,
 vertical_exaggeration=args.exaggeration)

# 3. Height bars (may be slower)
 visualizer.create_height_bars(elevation, metadata, bar_spacing=25)

 print("\n" + "="* 70)
 print(f" Complete! All visualizations saved to: {visualizer.output_dir}/")
 print("="* 70)


if __name__ == "__main__":
 sys.exit(main() or 0)

