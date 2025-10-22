"""
Handles the rendering of the elevation map visualization and file output.
"""
import time
import webbrowser
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource, LinearSegmentedColormap
from datetime import datetime
from pathlib import Path

def render_visualization(data: dict, output_dir: str = "generated"):
    """
    Renders the elevation map and saves it to PNG and HTML files.

    Args:
        data: A dictionary containing the processed data from data_processing.py.
        output_dir: The directory to save the output files.
    """
    overall_start = time.time()
    print("\n" + "=" * 70)
    print("  STEP 2: RENDERING")
    print("=" * 70)

    # --- Unpack Data ---
    elevation_viz = data["elevation_viz"]
    bounds = data["bounds"]
    z_min = data["z_min"]
    z_max = data["z_max"]

    # --- Configuration ---
    CAMERA_ELEVATION = 90
    CAMERA_AZIMUTH = 0
    VERTICAL_EXAGGERATION = 8.0
    VISUALIZATION_MAX_SIZE = 800

    # --- 1. Downsample and Prepare Grid ---
    step_start = time.time()
    print("\n🎨 Downsampling and preparing grid...")
    
    if elevation_viz.shape[0] > VISUALIZATION_MAX_SIZE or elevation_viz.shape[1] > VISUALIZATION_MAX_SIZE:
        step_y = max(1, elevation_viz.shape[0] // VISUALIZATION_MAX_SIZE)
        step_x = max(1, elevation_viz.shape[1] // VISUALIZATION_MAX_SIZE)
        elevation_viz_resampled = elevation_viz[::step_y, ::step_x]
        print(f"   - Resampled to {elevation_viz_resampled.shape} for visualization")
    else:
        elevation_viz_resampled = elevation_viz
        print(f"   - No resampling needed")
    
    y_size, x_size = elevation_viz_resampled.shape
    X, Y = np.meshgrid(np.arange(x_size), np.arange(y_size))
    Z = elevation_viz_resampled * VERTICAL_EXAGGERATION
    Z_masked = np.ma.masked_invalid(Z)
    print(f"   ⏱️  Time: {time.time() - step_start:.2f}s")

    # --- 2. Setup Figure and Plot Surface ---
    step_start = time.time()
    print("\n🖼️  Setting up figure and plotting 3D surface...")

    fig = plt.figure(figsize=(2, 2), facecolor='#000000')
    ax = fig.add_subplot(111, projection='3d', facecolor='#000000')

    colors_list = ['#1a4f63', '#2d8659', '#5ea849', '#a8b840', '#d4a747', '#b87333', '#8b7355', '#a8a8a8', '#d0d0d0', '#e8e8e8']
    cmap_custom = LinearSegmentedColormap.from_list('terrain_custom', colors_list, N=256)
    
    ls = LightSource(azdeg=315, altdeg=60)
    rgb = ls.shade(Z_masked, cmap=cmap_custom, blend_mode='soft', vert_exag=0.1, dx=1, dy=1, fraction=1.0)
    
    ax.plot_surface(X, Y, Z_masked, facecolors=rgb, linewidth=0, antialiased=False, shade=False, alpha=1.0, rcount=y_size, ccount=x_size)
    
    ax.view_init(elev=CAMERA_ELEVATION, azim=CAMERA_AZIMUTH)
    ax.set_axis_off()
    print(f"   ⏱️  Time: {time.time() - step_start:.2f}s")

    # --- 3. Add Text Overlays ---
    step_start = time.time()
    print("\n✍️  Adding text overlays...")

    title = f'USA Elevation Map | {bounds.left:.1f}°W to {bounds.right:.1f}°W, {bounds.bottom:.1f}°N to {bounds.top:.1f}°N | USGS 3DEP | Vertical Exag: {VERTICAL_EXAGGERATION}x'
    ax.text2D(0.5, 0.98, title, transform=ax.transAxes, fontsize=10, color='#aaaaaa', ha='center', va='top', family='monospace')
    
    legend_text = f'📊 STATS\n' + '─' * 13 + f'\nHigh: {z_max:.0f}m\nMean: {np.nanmean(elevation_viz):.0f}m\nLow:  {z_min:.0f}m\nRelief: {z_max - z_min:.0f}m'
    ax.text2D(0.01, 0.08, legend_text, transform=ax.transAxes, fontsize=5, color='white', ha='left', va='bottom', family='monospace', bbox=dict(boxstyle='round,pad=0.3', facecolor='#000000', edgecolor='#44ff88', linewidth=1.0, alpha=0.8))

    footer_text = f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")} | View Angle: Elev {ax.elev}°, Azim {ax.azim}° | Data Points: {elevation_viz_resampled.size:,}'
    ax.text2D(0.5, 0.01, footer_text, transform=ax.transAxes, fontsize=9, color='#aaaaaa', ha='center', va='bottom', family='monospace')
    
    plt.subplots_adjust(left=0, right=1, top=0.95, bottom=0.05)
    print(f"   ⏱️  Time: {time.time() - step_start:.2f}s")
    
    # --- 4. Save Output Files ---
    step_start = time.time()
    print("\n💾 Saving output files...")
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    output_path = output_dir / f"{timestamp}_continental_usa_overhead_view.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#000000', edgecolor='none', pad_inches=0)
    plt.close(fig)
    print(f"   - PNG saved to: {output_path}")

    html_path = output_dir / f"{timestamp}_continental_usa_overhead_view.html"
    html_content = f"""<!DOCTYPE html>
<html><head><title>USA Elevation Map</title><style>body{{margin:20px;background-color:#0a0a0a;color:white;font-family:Arial,sans-serif;display:flex;flex-direction:column;align-items:center;}} img{{max-width:90%;height:auto;border:3px solid #4488ff;}}</style></head>
<body><h1>United States Topographic Relief Map</h1><img src="{output_path.name}" alt="USA 3D Elevation Map"></body></html>"""
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"   - HTML saved to: {html_path}")
    
    webbrowser.open(str(html_path.absolute()))
    print(f"   - Opening HTML in browser...")
    print(f"   ⏱️  Time: {time.time() - step_start:.2f}s")
    
    print("\n" + "=" * 70)
    print(f"  RENDERING COMPLETE. Total time: {time.time() - overall_start:.2f}s")
    print("=" * 70)
