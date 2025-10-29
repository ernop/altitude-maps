"""
Handles the rendering of the elevation map visualization and file output.
"""
import time
import webbrowser
import textwrap
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource, LinearSegmentedColormap
from datetime import datetime
from pathlib import Path
from PIL import Image
from typing import Union, List, Optional
import rasterio

from src.borders import get_border_manager

def auto_crop_black_borders(image_path: Path, border_percent: float = 2.0, color_threshold: int = 30) -> tuple:
    """
    Automatically crop black borders from an image, leaving a thin uniform border.
    Focuses on colorful map content, not just dim text.
    
    Args:
        image_path: Path to the image file
        border_percent: Percentage of the cropped content to add back as border (default: 2%)
        color_threshold: Minimum brightness/color value for "colorful content" (default: 30)
    
    Returns:
        Tuple of (original_size, cropped_size, border_size_px)
    """
    img = Image.open(image_path)
    original_size = img.size
    
    # Convert to numpy array for analysis
    img_array = np.array(img)
    
    # Focus on colorful map content (not dim gray text)
    # Strategy: Look for pixels with decent color saturation or brightness
    if img_array.ndim == 3:
        if img_array.shape[2] == 4:  # RGBA
            rgb = img_array[:, :, :3]
        else:  # RGB
            rgb = img_array
        
        # Consider a pixel "map content" if:
        # - It has color variation (saturation) OR
        # - It's reasonably bright (elevation features)
        # This filters out dim gray text while keeping colorful terrain
        max_channel = np.max(rgb, axis=2)
        min_channel = np.min(rgb, axis=2)
        saturation = max_channel - min_channel  # Simple saturation proxy
        brightness = np.mean(rgb, axis=2)
        
        # Colorful content: has saturation OR is bright
        is_content = (saturation > 15) | (brightness > color_threshold)
    else:  # Grayscale
        is_content = img_array > color_threshold
    
    # Find bounding box of colorful content
    rows = np.any(is_content, axis=1)
    cols = np.any(is_content, axis=0)
    
    if not np.any(rows) or not np.any(cols):
        print("      WARNING: No colorful content found, skipping crop")
        return original_size, original_size, (0, 0)
    
    row_min, row_max = np.where(rows)[0][[0, -1]]
    col_min, col_max = np.where(cols)[0][[0, -1]]
    
    # Calculate border to add back (as percentage of content size)
    content_height = row_max - row_min + 1
    content_width = col_max - col_min + 1
    
    border_height = int(content_height * border_percent / 100)
    border_width = int(content_width * border_percent / 100)
    
    # Apply border while staying within image bounds
    crop_top = max(0, row_min - border_height)
    crop_bottom = min(img_array.shape[0], row_max + 1 + border_height)
    crop_left = max(0, col_min - border_width)
    crop_right = min(img_array.shape[1], col_max + 1 + border_width)
    
    # Crop the image
    img_cropped = img.crop((crop_left, crop_top, crop_right, crop_bottom))
    
    # Save over the original file
    img_cropped.save(image_path)
    
    cropped_size = img_cropped.size
    actual_border = (border_width, border_height)
    
    return original_size, cropped_size, actual_border

def render_visualization(data: dict, output_dir: str = "generated",
                        camera_elevation: float = 35, camera_azimuth: float = 45,
                        vertical_exaggeration: float = 4.0, projection_zoom: float = 0.99,
                        render_as_bars: bool = None, dpi: int = 100, scale_factor: float = 4.0,
                        max_viz_size: int = 800, colormap: str = 'terrain',
                        background_color: str = '#000000', light_azimuth: float = 315,
                        light_altitude: float = 60, filename_prefix: str = None,
                        show_overlays: bool = True, autocrop: bool = True, 
                        open_browser: bool = True, command_line_str: str = None,
                        draw_borders: Union[bool, str, List[str]] = False,
                        border_color: str = '#FF4444', border_width: float = 1.5,
                        border_resolution: str = '110m', tif_path: Optional[str] = None):
    """
    Renders the elevation map and saves it to PNG and HTML files.

    Args:
        data: A dictionary containing the processed data from data_processing.py.
        output_dir: The directory to save the output files.
        camera_elevation: Camera elevation angle in degrees (0=horizon, 90=overhead). Default: 35
        camera_azimuth: Camera azimuth angle in degrees (0-360, rotation). Default: 45
        vertical_exaggeration: Vertical scale relative to horizontal. 1.0 = true Earth scale, 
                              higher = steeper mountains. Default: 4.0
        projection_zoom: Target viewport fill ratio (0.90-0.99, higher=tighter). Default: 0.99
        render_as_bars: If True, render as 3D rectangular prisms instead of surface. 
                       If None (default), auto-detect based on whether data is bucketed.
        dpi: Output DPI (dots per inch). Default: 100
        scale_factor: Output resolution multiplier from data size. Default: 4.0
        max_viz_size: Maximum dimension for visualization grid. Default: 800
        colormap: Color scheme name. Default: 'terrain'
        background_color: Background color (hex). Default: '#000000'
        light_azimuth: Light source azimuth for hillshading (0-360). Default: 315
        light_altitude: Light source altitude for hillshading (0-90). Default: 60
        filename_prefix: Custom prefix for output filename. Default: None (uses timestamp)
        show_overlays: Show text overlays. Default: True
        autocrop: Auto-crop black borders. Default: True
        open_browser: Open HTML file in browser after rendering. Default: True
        draw_borders: Draw country borders on map. Can be True (auto-detect from bbox), 
                     a country name, or list of country names. Default: False
        border_color: Color for border lines (hex). Default: '#FF4444' (red)
        border_width: Width of border lines. Default: 1.5
        border_resolution: Natural Earth border resolution ('10m', '50m', or '110m'). Default: '110m'
        tif_path: Path to source GeoTIFF (needed for border drawing). Default: None
    """
    overall_start = time.time()
    print("\n" + "=" * 70, flush=True)
    print("  STEP 2: RENDERING", flush=True)
    print("=" * 70, flush=True)

    # --- Unpack Data ---
    elevation_viz = data["elevation_viz"]
    bounds = data["bounds"]
    z_min = data["z_min"]
    z_max = data["z_max"]
    is_bucketed = data.get("bucketed", False)
    
    # Auto-detect bar rendering if not specified
    if render_as_bars is None:
        render_as_bars = is_bucketed
    
    if render_as_bars:
        print(f"\n[*] Rendering mode: 3D RECTANGULAR PRISMS (bar chart style)", flush=True)
    else:
        print(f"\n[*] Rendering mode: SMOOTH SURFACE", flush=True)

    # --- Configuration ---
    CAMERA_ELEVATION = camera_elevation  # Angled view from above (90 = overhead, 0 = horizon)
    CAMERA_AZIMUTH = camera_azimuth      # Viewing angle rotation (0-360)
    VERTICAL_EXAGGERATION = vertical_exaggeration
    VISUALIZATION_MAX_SIZE = max_viz_size
    PROJECTION_ZOOM = projection_zoom  # Target viewport fill (0.90-0.99, higher = tighter framing)
    DPI = dpi
    SCALE_FACTOR = scale_factor

    # --- 1. Downsample and Prepare Grid ---
    step_start = time.time()
    print("\n[*] Downsampling and preparing grid...", flush=True)
    
    if elevation_viz.shape[0] > VISUALIZATION_MAX_SIZE or elevation_viz.shape[1] > VISUALIZATION_MAX_SIZE:
        step_y = max(1, elevation_viz.shape[0] // VISUALIZATION_MAX_SIZE)
        step_x = max(1, elevation_viz.shape[1] // VISUALIZATION_MAX_SIZE)
        elevation_viz_resampled = elevation_viz[::step_y, ::step_x]
        print(f"   - Resampled to {elevation_viz_resampled.shape} for visualization")
    else:
        elevation_viz_resampled = elevation_viz
        print(f"   - No resampling needed")
    
    y_size, x_size = elevation_viz_resampled.shape
    
    # Calculate real-world scale from geographic bounds
    # This ensures vertical_exaggeration=1.0 means "true scale like real Earth"
    lon_span = abs(bounds.right - bounds.left)  # degrees
    lat_span = abs(bounds.top - bounds.bottom)  # degrees
    
    # Calculate meters per degree at the center latitude
    center_lat = (bounds.top + bounds.bottom) / 2.0
    meters_per_deg_lon = 111_320 * np.cos(np.radians(center_lat))
    meters_per_deg_lat = 111_320  # approximately constant
    
    # Calculate real-world dimensions in meters
    width_meters = lon_span * meters_per_deg_lon
    height_meters = lat_span * meters_per_deg_lat
    
    # Meters per pixel
    meters_per_pixel_x = width_meters / x_size
    meters_per_pixel_y = height_meters / y_size
    
    # Create coordinate grids in real-world meters
    X = np.arange(x_size) * meters_per_pixel_x
    Y = np.arange(y_size) * meters_per_pixel_y
    X, Y = np.meshgrid(X, Y)
    
    # Apply vertical exaggeration to elevation (also in meters)
    Z = elevation_viz_resampled * VERTICAL_EXAGGERATION
    Z_masked = np.ma.masked_invalid(Z)
    
    # Display dimensions
    x_size_display = width_meters
    y_size_display = height_meters
    
    print(f"   - Data dimensions: {x_size} × {y_size} pixels")
    print(f"   - Real-world size: {width_meters/1000:.1f} × {height_meters/1000:.1f} km")
    print(f"   - Resolution: {meters_per_pixel_x:.1f} m/pixel (lon) × {meters_per_pixel_y:.1f} m/pixel (lat)")
    print(f"   - Aspect ratio: {x_size/y_size:.3f} (width/height)")
    print(f"   - Vertical exaggeration: {VERTICAL_EXAGGERATION}x (1.0 = true Earth scale)")
    print(f"   Time: {time.time() - step_start:.2f}s")

    # --- 2. Setup Figure and Plot Surface ---
    step_start = time.time()
    print("\n[*] Setting up figure and plotting 3D surface...", flush=True)

    # Calculate figure size based on ACTUAL data dimensions (in pixels)
    # Scale up from the data resolution for a crisp output
    data_aspect = x_size / y_size
    
    target_width_px = int(x_size * SCALE_FACTOR)
    target_height_px = int(y_size * SCALE_FACTOR)
    
    fig_width_inches = target_width_px / DPI
    fig_height_inches = target_height_px / DPI
    
    print(f"   - Output resolution: {target_width_px} × {target_height_px} pixels ({SCALE_FACTOR:.1f}x data size)")
    print(f"   - Figure: {fig_width_inches:.1f} × {fig_height_inches:.1f} inches @ {DPI} DPI")
    
    fig = plt.figure(figsize=(fig_width_inches, fig_height_inches), facecolor=background_color)
    ax = fig.add_subplot(111, projection='3d', facecolor=background_color)

    # Create color mapping based on colormap selection
    colormap_presets = {
        'terrain': ['#1a4f63', '#2d8659', '#5ea849', '#a8b840', '#d4a747', '#b87333', '#8b7355', '#a8a8a8', '#d0d0d0', '#e8e8e8'],
        'earth': ['#2C1810', '#4A3728', '#6B5244', '#8B7355', '#A69270', '#C4B89C', '#8B9A6B', '#6B8E4A', '#4A7239', '#2A5228'],
        'ocean': ['#001f3f', '#0074D9', '#39CCCC', '#2ECC40', '#FFDC00', '#FF851B', '#FF4136'],
        'viridis': None,  # Use matplotlib's built-in
        'plasma': None,
        'inferno': None,
        'grayscale': ['#000000', '#222222', '#444444', '#666666', '#888888', '#aaaaaa', '#cccccc', '#eeeeee', '#ffffff']
    }
    
    if colormap in colormap_presets and colormap_presets[colormap] is not None:
        colors_list = colormap_presets[colormap]
        cmap_custom = LinearSegmentedColormap.from_list(f'{colormap}_custom', colors_list, N=256)
    else:
        # Use matplotlib's built-in colormap
        import matplotlib.cm as cm
        cmap_custom = cm.get_cmap(colormap)
    
    if render_as_bars:
        # Render as 3D rectangular prisms (bar chart style)
        print(f"   - Rendering rectangular prisms for valid data points...", flush=True)
        
        # Normalize elevations for color mapping
        z_range = Z_masked.max() - Z_masked.min()
        if z_range > 0:
            z_normalized = (Z_masked - Z_masked.min()) / z_range
        else:
            z_normalized = np.zeros_like(Z_masked)
        
        # Create bars for each grid cell (scaled to match coordinate system)
        dx = dy = coordinate_scale  # Bar width/depth (fills grid cell)
        
        # Flatten arrays
        x_pos_all = X.flatten()
        y_pos_all = Y.flatten()
        z_heights_all = Z_masked.flatten()
        z_normalized_all = z_normalized.flatten()
        
        # Filter out invalid/masked data points to avoid jagged base artifacts
        # Only create bars where we have valid elevation data
        valid_mask = ~z_heights_all.mask if hasattr(z_heights_all, 'mask') else np.ones(len(z_heights_all), dtype=bool)
        
        x_pos = x_pos_all[valid_mask]
        y_pos = y_pos_all[valid_mask]
        z_heights = z_heights_all[valid_mask].data
        z_normalized_valid = z_normalized_all[valid_mask].data if hasattr(z_normalized_all, 'mask') else z_normalized_all[valid_mask]
        
        # All bars start at z=0 (ground level)
        z_pos = np.zeros_like(x_pos)
        dx_arr = np.full_like(x_pos, dx)
        dy_arr = np.full_like(y_pos, dy)
        
        # Get colors based on elevation (only for valid data)
        colors = cmap_custom(z_normalized_valid)
        
        num_valid = len(x_pos)
        print(f"   - Rendering {num_valid:,} bars ({num_valid / (y_size * x_size) * 100:.1f}% of grid has valid data)", flush=True)
        
        # Plot bars (this may take a moment for large datasets)
        ax.bar3d(x_pos, y_pos, z_pos, dx_arr, dy_arr, z_heights, 
                color=colors, shade=True, edgecolor='none', alpha=0.95)
        
    else:
        # Render as smooth surface with hillshading
        ls = LightSource(azdeg=light_azimuth, altdeg=light_altitude)
        rgb = ls.shade(Z_masked, cmap=cmap_custom, blend_mode='soft', vert_exag=0.1, dx=1, dy=1, fraction=1.0)
        
        # Plot the surface
        ax.plot_surface(X, Y, Z_masked, facecolors=rgb, linewidth=0, antialiased=False, 
                       shade=False, alpha=1.0, rcount=y_size, ccount=x_size)
    
    # Set tight axis limits to eliminate extra space (using scaled coordinates)
    ax.set_xlim(0, x_size_display)
    ax.set_ylim(0, y_size_display)
    ax.set_zlim(Z_masked.min(), Z_masked.max())
    
    # --- Draw Borders (Optional) ---
    if draw_borders and tif_path:
        step_start_border = time.time()
        print(f"\n[*] Drawing country borders...", flush=True)
        
        try:
            border_manager = get_border_manager()
            
            # Determine which countries to draw
            if draw_borders is True:
                # Auto-detect countries from bbox
                with rasterio.open(tif_path) as src:
                    bbox = src.bounds
                    bbox_tuple = (bbox.left, bbox.bottom, bbox.right, bbox.top)
                    countries_gdf = border_manager.get_countries_in_bbox(bbox_tuple, resolution=border_resolution)
                    countries_to_draw = countries_gdf.ADMIN.tolist()
                    print(f"   - Auto-detected {len(countries_to_draw)} countries in view: {', '.join(countries_to_draw)}")
            elif isinstance(draw_borders, str):
                countries_to_draw = [draw_borders]
            else:
                countries_to_draw = draw_borders
            
            # Get border coordinates and draw them
            with rasterio.open(tif_path) as src:
                for country_name in countries_to_draw:
                    border_coords = border_manager.get_border_coordinates(
                        country_name, 
                        target_crs=src.crs,
                        resolution=border_resolution
                    )
                    
                    if not border_coords:
                        print(f"   - WARNING: No borders found for '{country_name}'")
                        continue
                    
                    # Transform border coordinates to match visualization
                    # Need to map from geographic coords to pixel coords
                    for lon_coords, lat_coords in border_coords:
                        # Convert lon/lat to pixel coordinates
                        transform = src.transform
                        
                        # Convert geographic to pixel space
                        px_coords = []
                        py_coords = []
                        for lon, lat in zip(lon_coords, lat_coords):
                            col, row = ~transform * (lon, lat)
                            
                            # No transformations applied to elevation data anymore
                            # GeoTIFF natural orientation: row=North→South, col=West→East
                            # Map directly to visualization coordinates
                            final_x = col * coordinate_scale
                            final_y = row * coordinate_scale
                            
                            px_coords.append(final_x)
                            py_coords.append(final_y)
                        
                        # Draw border line at maximum elevation for visibility
                        z_line = np.full(len(px_coords), Z_masked.max() * 1.01)
                        
                        # Plot the border
                        ax.plot(py_coords, px_coords, z_line, 
                               color=border_color, linewidth=border_width, 
                               alpha=0.8, zorder=100)
                    
                    print(f"   - Drew borders for '{country_name}' ({len(border_coords)} segments)")
            
            print(f"   Time: {time.time() - step_start_border:.2f}s")
        
        except Exception as e:
            print(f"   - WARNING: Failed to draw borders: {e}")
            print(f"   - Continuing without borders...")
    elif draw_borders and not tif_path:
        print(f"\n[!] Cannot draw borders: tif_path not provided")
    
    # Adjust box aspect based on camera angle
    # For angled/lateral views, make Z more prominent to show terrain relief
    z_range = Z_masked.ptp()
    if z_range == 0:
        z_range = 1
    
    # Use scaled display dimensions for box aspect
    if CAMERA_ELEVATION > 60:
        z_scale = max(x_size_display, y_size_display) * 0.01
    else:
        z_scale = min(z_range * 0.3, max(x_size_display, y_size_display) * 0.3)
    ax.set_box_aspect((x_size_display, y_size_display, z_scale))
    
    # Set view angle
    ax.view_init(elev=CAMERA_ELEVATION, azim=CAMERA_AZIMUTH)
    ax.set_axis_off()
    
    print(f"   - Auto-tuning camera distance to fill {PROJECTION_ZOOM:.0%} of viewport...")
    
    # Get corners of the 3D bounding box (use current axis limits)
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    zlim = ax.get_zlim()
    
    corners_3d = np.array([
        [xlim[0], ylim[0], zlim[0]],
        [xlim[1], ylim[0], zlim[0]],
        [xlim[1], ylim[1], zlim[0]],
        [xlim[0], ylim[1], zlim[0]],
        [xlim[0], ylim[0], zlim[1]],
        [xlim[1], ylim[0], zlim[1]],
        [xlim[1], ylim[1], zlim[1]],
        [xlim[0], ylim[1], zlim[1]],
    ])
    
    def test_camera_distance(dist):
        """Test a camera distance. Returns viewport fill metrics."""
        # Set the distance
        ax.dist = dist
        
        # Force update and get projection
        fig.canvas.draw_idle()
        proj_matrix = ax.get_proj()
        
        # Project corners to screen space
        corners_4d = np.column_stack([corners_3d, np.ones(len(corners_3d))])
        projected = corners_4d @ proj_matrix.T
        
        # Perspective divide to normalized device coordinates
        projected_2d = projected[:, :2] / projected[:, 3:4]
        
        # Measure extent
        x_min, x_max = projected_2d[:, 0].min(), projected_2d[:, 0].max()
        y_min, y_max = projected_2d[:, 1].min(), projected_2d[:, 1].max()
        
        # Max extent tells us how much of viewport we're using
        max_extent = max(abs(x_min), abs(x_max), abs(y_min), abs(y_max))
        
        # Viewport is -1 to 1, we want to fill up to PROJECTION_ZOOM (e.g., 0.98)
        is_clipping = max_extent > PROJECTION_ZOOM
        
        return is_clipping, max_extent, x_min, x_max, y_min, y_max
    
    # Phase 1: Find distance bounds
    print(f"   - Phase 1: Finding distance bounds...")
    
    # Test a range of distances to find one that's safe and one that clips
    dist_safe = None
    dist_clip = None
    
    test_distances = [10.0, 8.0, 6.0, 5.0, 4.0, 3.0, 2.5, 2.0, 1.5, 1.0, 0.5]
    
    for dist in test_distances:
        is_clip, extent, xmin, xmax, ymin, ymax = test_camera_distance(dist)
        status = "CLIPS" if is_clip else "safe"
        print(f"      Test dist={dist:.2f}: extent={extent:.3f}, X=[{xmin:.3f},{xmax:.3f}] Y=[{ymin:.3f},{ymax:.3f}] -> {status}")
        
        if not is_clip and dist_safe is None:
            dist_safe = dist
            print(f"      ✓ Found safe distance: {dist:.2f}")
        
        if is_clip and dist_clip is None:
            dist_clip = dist
            print(f"      ✓ Found clipping distance: {dist:.2f}")
            break
    
    # Ensure we have valid bounds
    if dist_safe is None:
        dist_safe = 10.0
        print(f"      WARNING: No safe distance found, using {dist_safe}")
    
    if dist_clip is None:
        dist_clip = 0.5
        print(f"      WARNING: No clipping distance found, using {dist_clip}")
    
    # Phase 2: Binary search for optimal distance
    print(f"   - Phase 2: Binary search between {dist_safe:.2f} and {dist_clip:.2f}...")
    print(f"      Target: Fill up to {PROJECTION_ZOOM:.3f} of viewport (1.0 = full)")
    
    dist_min = dist_clip  # Smaller distance = closer/more zoom
    dist_max = dist_safe  # Larger distance = further/less zoom
    best_dist = dist_safe
    
    for iteration in range(30):
        test_dist = (dist_min + dist_max) / 2
        is_clip, extent, xmin, xmax, ymin, ymax = test_camera_distance(test_dist)
        
        status = "CLIP" if is_clip else "safe"
        print(f"      Iter {iteration:2d}: dist={test_dist:.4f}, extent={extent:.4f}, X=[{xmin:.3f},{xmax:.3f}] Y=[{ymin:.3f},{ymax:.3f}] -> {status}")
        
        if is_clip:
            # Too close, move away (increase distance)
            dist_min = test_dist
        else:
            # Safe, can get closer (decrease distance)
            dist_max = test_dist
            best_dist = test_dist
        
        # Converged?
        if abs(dist_max - dist_min) < 0.001:
            print(f"      Converged! (difference < 0.001)")
            break
    
    # Phase 3: Final verification
    print(f"   - Phase 3: FINAL VERIFICATION of dist={best_dist:.4f}...")
    final_is_clip, final_extent, fx_min, fx_max, fy_min, fy_max = test_camera_distance(best_dist)
    
    if final_is_clip:
        print(f"        WARNING: Final distance CLIPS! Moving 5% further...")
        best_dist = best_dist * 1.05
        final_is_clip, final_extent, fx_min, fx_max, fy_min, fy_max = test_camera_distance(best_dist)
    
    viewport_usage = (final_extent / PROJECTION_ZOOM) * 100
    
    print(f"   ✓ FINAL CAMERA DISTANCE: {best_dist:.4f}")
    print(f"   ✓ Map extent: {final_extent:.4f} (target: {PROJECTION_ZOOM:.4f})")
    print(f"   ✓ Viewport usage: {viewport_usage:.1f}%")
    print(f"   ✓ Bounds: X=[{fx_min:.3f}, {fx_max:.3f}], Y=[{fy_min:.3f}, {fy_max:.3f}]")
    print(f"   ✓ Status: {' WILL CLIP' if final_is_clip else '✓ SAFE TO RENDER'}")
    
    # Apply the final distance
    ax.dist = best_dist
    print(f"   ✓ Camera distance applied")
    
    print(f"   Time: {time.time() - step_start:.2f}s")

    # --- 3. Add Text Overlays ---
    if show_overlays:
        step_start = time.time()
        print("\n✍  Adding text overlays...")
        
        # Title at the very top
        title_str = f'USA Elevation Map | {bounds.left:.1f}°W to {bounds.right:.1f}°W, {bounds.bottom:.1f}°N to {bounds.top:.1f}°N | USGS 3DEP | Vertical Exag: {VERTICAL_EXAGGERATION}x'
        wrapped_title = "\n".join(textwrap.wrap(title_str, width=120))
        ax.text2D(0.5, 0.98, wrapped_title, transform=ax.transAxes, fontsize=14, color='#aaaaaa', ha='center', va='top', family='monospace')
        
        # Generated/metadata line just below title
        footer_str = f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")} | View Angle: Elev {ax.elev}°, Azim {ax.azim}° | Data Points: {elevation_viz_resampled.size:,}'
        wrapped_footer = "\n".join(textwrap.wrap(footer_str, width=120))
        ax.text2D(0.5, 0.94, wrapped_footer, transform=ax.transAxes, fontsize=10, color='#888888', ha='center', va='top', family='monospace')
        
        # Stats box at bottom left
        legend_text = f'📊 STATS\n' + '─' * 13 + f'\nHigh: {z_max:.0f}m\nMean: {np.nanmean(elevation_viz):.0f}m\nLow:  {z_min:.0f}m\nRelief: {z_max - z_min:.0f}m'
        ax.text2D(0.015, 0.02, legend_text, transform=ax.transAxes, fontsize=11, color='white', ha='left', va='bottom', family='monospace', bbox=dict(boxstyle='round,pad=0.4', facecolor='#000000', edgecolor='#44ff88', linewidth=1.5, alpha=0.85))

        # Configuration settings box at bottom right
        config_lines = ['⚙ CONFIG\n' + '─' * 15]
        
        # Bucketing info
        bucket_miles = data.get("bucket_size_miles")
        bucket_pixels = data.get("bucket_size_pixels")
        if bucket_miles is not None:
            config_lines.append(f'Bucket: {bucket_miles}×{bucket_miles} mi')
        elif bucket_pixels is not None:
            config_lines.append(f'Bucket: {bucket_pixels}×{bucket_pixels} px')
        else:
            config_lines.append(f'Bucket: None (full res)')
        
        # Render mode
        if render_as_bars:
            config_lines.append(f'Render: 3D Prisms')
        else:
            config_lines.append(f'Render: Surface')
        
        # Camera settings
        config_lines.append(f'Camera: {CAMERA_ELEVATION}°/{CAMERA_AZIMUTH}°')
        config_lines.append(f'Vert Exag: {VERTICAL_EXAGGERATION}x')
        config_lines.append(f'Zoom: {PROJECTION_ZOOM:.2f}')
        config_lines.append(f'Colormap: {colormap}')
        
        config_text = '\n'.join(config_lines)
        ax.text2D(0.985, 0.02, config_text, transform=ax.transAxes, fontsize=10, color='white', ha='right', va='bottom', family='monospace', bbox=dict(boxstyle='round,pad=0.4', facecolor='#000000', edgecolor='#4488ff', linewidth=1.5, alpha=0.85))
        
        # Command line for reproduction at bottom center
        if command_line_str:
            # Wrap long command line
            cmd_wrapped = "\n".join(textwrap.wrap(command_line_str, width=140))
            ax.text2D(0.5, 0.005, f'🔄 REPRODUCE:\n{cmd_wrapped}', transform=ax.transAxes, fontsize=8, color='#666666', ha='center', va='bottom', family='monospace', bbox=dict(boxstyle='round,pad=0.3', facecolor='#000000', edgecolor='#666666', linewidth=1.0, alpha=0.9))
        
        # Aggressive margin reduction to maximize map area in the figure
        plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
        print(f"   Time: {time.time() - step_start:.2f}s")
    else:
        print("\n✍  Skipping text overlays (--no-overlays)")
        # Even without overlays, adjust margins for better framing
        plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    
    # --- 4. Save Output Files ---
    step_start = time.time()
    print("\n[*] Saving output files...")
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Generate filename
    if filename_prefix:
        base_filename = f"{filename_prefix}_{timestamp}"
    else:
        base_filename = f"{timestamp}_continental_usa_overhead_view"
    
    output_path = output_dir / f"{base_filename}.png"
    # Save with tight bbox to minimize black borders (pad_inches adds a thin uniform border)
    plt.savefig(output_path, dpi=DPI, bbox_inches='tight', facecolor=background_color, edgecolor='none', pad_inches=0.02)
    plt.close(fig)
    print(f"   - PNG saved to: {output_path}")
    print(f"   - Initial resolution: ~{target_width_px} × {int(target_height_px)} pixels")
    
    # Auto-crop black borders (1% border = very tight framing)
    if autocrop:
        print(f"\n✂  Auto-cropping black borders...")
        orig_size, cropped_size, border_px = auto_crop_black_borders(output_path, border_percent=1.0)
        space_saved = (1 - (cropped_size[0] * cropped_size[1]) / (orig_size[0] * orig_size[1])) * 100
        print(f"   - Original: {orig_size[0]} × {orig_size[1]} pixels")
        print(f"   - Cropped: {cropped_size[0]} × {cropped_size[1]} pixels")
        print(f"   - Border added: {border_px[0]}px (width), {border_px[1]}px (height)")
        print(f"   - Space saved: {space_saved:.1f}%")
    else:
        print(f"\n✂  Skipping auto-crop (--no-autocrop)")

    html_path = output_dir / f"{base_filename}.html"
    html_content = f"""<!DOCTYPE html>
<html><head><title>USA Elevation Map</title><style>body{{margin:20px;background-color:#0a0a0a;color:white;font-family:Arial,sans-serif;display:flex;flex-direction:column;align-items:center;}} img{{max-width:90%;height:auto;border:3px solid #4488ff;}}</style></head>
<body><h1>United States Topographic Relief Map</h1><img src="{output_path.name}" alt="USA 3D Elevation Map"></body></html>"""
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"   - HTML saved to: {html_path}")
    
    # Browser opening disabled by default - files saved to disk
    # if open_browser:
    #     webbrowser.open(str(html_path.absolute()))
    #     print(f"   - Opening HTML in browser...")
    print(f"   Time: {time.time() - step_start:.2f}s")
    
    print("\n" + "=" * 70)
    print(f"  RENDERING COMPLETE. Total time: {time.time() - overall_start:.2f}s")
    print("=" * 70)
