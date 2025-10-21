"""
Create a single overhead view of continental USA elevation - space perspective.

Recreates the style of elevation visualization with 3D blocks/bars showing terrain height.
"""

import sys
import io
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import LightSource, LinearSegmentedColormap
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    import rasterio
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False
    print("⚠️  rasterio required: pip install rasterio")
    sys.exit(1)


def create_usa_overhead_view(tif_path: str, output_dir: str = "generated"):
    """
    Create a single beautiful overhead view of continental USA elevation.
    
    Args:
        tif_path: Path to GeoTIFF elevation file
        output_dir: Output directory for the image
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print("\n" + "=" * 70)
    print("  CONTINENTAL USA OVERHEAD ELEVATION VIEW")
    print("=" * 70)
    
    # Load elevation data
    print(f"\n📂 Loading: {tif_path}")
    with rasterio.open(tif_path) as src:
        elevation = src.read(1)
        bounds = src.bounds
        
        # Handle nodata
        if src.nodata is not None:
            elevation = np.where(elevation == src.nodata, np.nan, elevation)
        
        print(f"   Region: {bounds.left:.1f}°W to {bounds.right:.1f}°W, "
              f"{bounds.bottom:.1f}°N to {bounds.top:.1f}°N")
        print(f"   Shape: {elevation.shape}")
        print(f"   Elevation: {np.nanmin(elevation):.0f}m to {np.nanmax(elevation):.0f}m")
    
    # Create the visualization
    print("\n🎨 Creating overhead space view...")
    
    # Setup figure with dark space background
    fig = plt.figure(figsize=(24, 18), facecolor='#000000')
    ax = fig.add_subplot(111, projection='3d', facecolor='#000000')
    
    # Downsample for visualization performance
    max_size = 600
    if elevation.shape[0] > max_size or elevation.shape[1] > max_size:
        step_y = max(1, elevation.shape[0] // max_size)
        step_x = max(1, elevation.shape[1] // max_size)
        elevation_viz = elevation[::step_y, ::step_x]
        print(f"   Resampled to {elevation_viz.shape} for visualization")
    else:
        elevation_viz = elevation
    
    # Create coordinate grids
    y_size, x_size = elevation_viz.shape
    x = np.arange(x_size)
    y = np.arange(y_size)
    X, Y = np.meshgrid(x, y)
    
    # Vertical exaggeration for dramatic effect
    vertical_exag = 15.0
    Z = elevation_viz * vertical_exag
    
    # Mask NaN values
    Z_masked = np.ma.masked_invalid(Z)
    
    # Create custom colormap similar to reference image
    # Low: deep ocean blue -> green -> yellow -> brown -> gray/white (high peaks)
    colors_list = [
        '#1a4f63',  # Deep blue (below sea level / low)
        '#2d8659',  # Dark green
        '#5ea849',  # Green
        '#a8b840',  # Yellow-green
        '#d4a747',  # Yellow-brown
        '#b87333',  # Brown
        '#8b7355',  # Light brown
        '#a8a8a8',  # Gray
        '#d0d0d0',  # Light gray
        '#e8e8e8',  # Near white (peaks)
    ]
    n_bins = 256
    cmap_custom = LinearSegmentedColormap.from_list('terrain_custom', colors_list, N=n_bins)
    
    # Normalize elevation for colors
    z_min, z_max = np.nanmin(elevation_viz), np.nanmax(elevation_viz)
    z_norm = (elevation_viz - z_min) / (z_max - z_min)
    
    # Apply lighting with hillshade
    ls = LightSource(azdeg=315, altdeg=60)
    rgb = ls.shade(Z_masked, cmap=cmap_custom, blend_mode='soft', 
                   vert_exag=0.1, dx=1, dy=1, fraction=1.0)
    
    # Plot the surface
    surf = ax.plot_surface(X, Y, Z_masked, 
                          facecolors=rgb,
                          linewidth=0,
                          antialiased=True,
                          shade=False,
                          alpha=1.0,
                          rcount=y_size,
                          ccount=x_size)
    
    # Set viewing angle - overhead but at an angle to see 3D effect
    ax.view_init(elev=35, azim=230)
    
    # Set axis limits to fit the data
    ax.set_xlim(0, x_size)
    ax.set_ylim(0, y_size)
    ax.set_zlim(np.nanmin(Z_masked), np.nanmax(Z_masked))
    
    # Style the axes for space view
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.xaxis.pane.set_edgecolor('#000000')
    ax.yaxis.pane.set_edgecolor('#000000')
    ax.zaxis.pane.set_edgecolor('#000000')
    ax.grid(False)
    
    # Hide axis ticks and labels for clean space view
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    
    # Add title and location information
    title = 'Continental United States - Elevation View from Space\n'
    title += f'USGS 3DEP Elevation Data  |  '
    title += f'{bounds.left:.1f}°W to {bounds.right:.1f}°W, '
    title += f'{bounds.bottom:.1f}°N to {bounds.top:.1f}°N\n'
    title += f'Elevation Range: {z_min:.0f}m to {z_max:.0f}m  |  '
    title += f'Vertical Exaggeration: {vertical_exag}x'
    
    ax.text2D(0.5, 0.98, title, 
             transform=ax.transAxes,
             fontsize=16,
             color='white',
             ha='center',
             va='top',
             fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.8', 
                      facecolor='#000000', 
                      edgecolor='#333333',
                      alpha=0.8))
    
    # Add elevation legend
    legend_text = 'ELEVATION\n'
    legend_text += f'Peak: {z_max:.0f}m\n'
    legend_text += f'Mean: {np.nanmean(elevation_viz):.0f}m\n'
    legend_text += f'Low: {z_min:.0f}m'
    
    ax.text2D(0.02, 0.98, legend_text,
             transform=ax.transAxes,
             fontsize=12,
             color='white',
             ha='left',
             va='top',
             family='monospace',
             bbox=dict(boxstyle='round,pad=0.5',
                      facecolor='#000000',
                      edgecolor='#333333',
                      alpha=0.7))
    
    plt.tight_layout()
    
    # Save the image
    output_path = output_dir / f"{timestamp}_continental_usa_overhead_view.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight', 
               facecolor='#000000', edgecolor='none')
    print(f"\n✅ Saved: {output_path}")
    
    plt.show()
    
    print("\n" + "=" * 70)
    print("  Complete!")
    print("=" * 70)


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
    
    args = parser.parse_args()
    
    # Check if file exists
    if not Path(args.tif_file).exists():
        print(f"\n❌ Error: File not found: {args.tif_file}")
        print("\nDownload with: python download_continental_usa.py --region nationwide_usa --yes")
        return 1
    
    create_usa_overhead_view(args.tif_file, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

