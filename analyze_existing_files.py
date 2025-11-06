"""Analyze existing raw files and determine splitting strategies."""
import re
from pathlib import Path
import math

def parse_bbox_filename(filename):
    """Parse bbox filename to extract bounds."""
    # Pattern: bbox_W111_5_S40_0_E111_0_N41_0_srtm_30m_30m.tif
    # or: bbox_N13_E120_N15_E122_srtm_30m_30m.tif
    pattern = r'bbox_(W|E)([\d_]+)_(S|N)([\d_]+)_(W|E)([\d_]+)_(N|S)([\d_]+)_(.*?)\.tif'
    match = re.match(pattern, filename)
    if not match:
        return None
    
    # Extract coordinates
    w_dir, w_val, s_dir, s_val, e_dir, e_val, n_dir, n_val, dataset = match.groups()
    
    def parse_coord(dir_sign, value_str):
        """Parse coordinate string with underscores."""
        # Replace underscores with dots or parse as integer
        if '_' in value_str:
            # Has decimal point (underscore represents decimal)
            parts = value_str.split('_', 1)
            if len(parts) == 2:
                integer = int(parts[0])
                decimal = parts[1]
                # Handle negative
                sign = -1 if dir_sign in ['W', 'S'] else 1
                return sign * (integer + float('0.' + decimal))
        else:
            # Integer
            sign = -1 if dir_sign in ['W', 'S'] else 1
            return sign * int(value_str)
    
    west = parse_coord(w_dir, w_val) if w_dir == 'W' else -parse_coord(e_dir, e_val)
    south = parse_coord(s_dir, s_val) if s_dir == 'S' else -parse_coord(n_dir, n_val)
    east = parse_coord(e_dir, e_val) if e_dir == 'E' else -parse_coord(w_dir, w_val)
    north = parse_coord(n_dir, n_val) if n_dir == 'N' else -parse_coord(s_dir, s_val)
    
    return (west, south, east, north)

def parse_tile_filename(filename):
    """Parse tile filename to extract bounds.
    
    Format: {NS}{lat}_{EW}{lon}_{resolution}.tif
    Example: N40_W111_30m.tif
    """
    # Simple format: {NS}{lat}_{EW}{lon}_{resolution}.tif
    pattern = r'^(N|S)(\d+)_(E|W)(\d+)_(\d+m)\.tif$'
    match = re.match(pattern, filename)
    if not match:
        return None
    
    ns_dir, lat_str, ew_dir, lon_str, resolution = match.groups()
    lat = int(lat_str) if ns_dir == 'N' else -int(lat_str)
    lon = int(lon_str) if ew_dir == 'E' else -int(lon_str)
    
    return (lon, lat, lon + 1.0, lat + 1.0)

def get_file_bounds_from_geotiff(filepath):
    """Get bounds from GeoTIFF file metadata or filename."""
    # Try parsing from filename first
    bounds_from_name = parse_bbox_filename(filepath.name) or parse_tile_filename(filepath.name)
    if bounds_from_name:
        return bounds_from_name
    
    # If that fails, try reading metadata JSON if it exists
    json_path = filepath.with_suffix('.json')
    if json_path.exists():
        try:
            import json
            with open(json_path, 'r') as f:
                metadata = json.load(f)
                if 'bounds' in metadata:
                    b = metadata['bounds']
                    return (b[0], b[1], b[2], b[3])
        except Exception:
            pass
    
    return None

def calculate_size_degrees(bounds):
    """Calculate width and height in degrees."""
    west, south, east, north = bounds
    width = east - west
    height = north - south
    return width, height

def estimate_area_km2(bounds):
    """Estimate area in km^2."""
    west, south, east, north = bounds
    width_deg = east - west
    height_deg = north - south
    mid_lat = (north + south) / 2.0
    km_per_deg_lat = 110.574
    km_per_deg_lon = 111.320 * math.cos(math.radians(mid_lat))
    area_km2 = (width_deg * km_per_deg_lon) * (height_deg * km_per_deg_lat)
    return area_km2

def analyze_files():
    """Analyze all existing raw files."""
    print("=" * 70)
    print("EXISTING RAW FILES ANALYSIS")
    print("=" * 70)
    print()
    
    # Analyze bbox files
    bbox_dir = Path('data/raw/srtm_30m')
    if not bbox_dir.exists():
        print("Bbox directory not found!")
        return
    
    bbox_files = list(bbox_dir.glob('bbox_*.tif'))
    print(f"Found {len(bbox_files)} bbox files:")
    print("-" * 70)
    
    bbox_sizes = []
    for f in sorted(bbox_files):
        # Try to parse from filename
        bounds_from_name = parse_bbox_filename(f.name)
        # Get actual bounds from file
        bounds_from_file = get_file_bounds_from_geotiff(f)
        
        if bounds_from_file:
            bounds = bounds_from_file
            width, height = calculate_size_degrees(bounds)
            area_km2 = estimate_area_km2(bounds)
            file_size_mb = f.stat().st_size / (1024 * 1024)
            
            bbox_sizes.append({
                'file': f.name,
                'bounds': bounds,
                'width': width,
                'height': height,
                'area_km2': area_km2,
                'size_mb': file_size_mb
            })
            
            print(f"  {f.name}")
            print(f"    Bounds: [{bounds[0]:.4f}, {bounds[1]:.4f}, {bounds[2]:.4f}, {bounds[3]:.4f}]")
            print(f"    Size: {width:.2f}deg x {height:.2f}deg = {area_km2:,.0f} km²")
            print(f"    File size: {file_size_mb:.1f} MB")
            print()
    
    # Analyze tile files
    tile_dir = bbox_dir / 'tiles'
    tile_files = list(tile_dir.glob('tile_*.tif')) if tile_dir.exists() else []
    
    print(f"\nFound {len(tile_files)} tile files:")
    print("-" * 70)
    
    tile_sizes = []
    for f in sorted(tile_files):
        bounds_from_name = parse_tile_filename(f.name)
        bounds_from_file = get_file_bounds_from_geotiff(f)
        
        if bounds_from_file:
            bounds = bounds_from_file
            width, height = calculate_size_degrees(bounds)
            area_km2 = estimate_area_km2(bounds)
            file_size_mb = f.stat().st_size / (1024 * 1024)
            
            tile_sizes.append({
                'file': f.name,
                'bounds': bounds,
                'width': width,
                'height': height,
                'area_km2': area_km2,
                'size_mb': file_size_mb
            })
            
            print(f"  {f.name}")
            print(f"    Bounds: [{bounds[0]:.4f}, {bounds[1]:.4f}, {bounds[2]:.4f}, {bounds[3]:.4f}]")
            print(f"    Size: {width:.2f}deg x {height:.2f}deg = {area_km2:,.0f} km²")
            print(f"    File size: {file_size_mb:.1f} MB")
            print()
    
    # Summary statistics
    print("\n" + "=" * 70)
    print("SUMMARY STATISTICS")
    print("=" * 70)
    print()
    
    if bbox_sizes:
        print("Bbox Files:")
        widths = [b['width'] for b in bbox_sizes]
        heights = [b['height'] for b in bbox_sizes]
        areas = [b['area_km2'] for b in bbox_sizes]
        
        print(f"  Count: {len(bbox_sizes)}")
        print(f"  Width range: {min(widths):.2f} - {max(widths):.2f} degrees")
        print(f"  Height range: {min(heights):.2f} - {max(heights):.2f} degrees")
        print(f"  Area range: {min(areas):,.0f} - {max(areas):,.0f} km²")
        
        # Find large files that could be split
        large_bboxes = [b for b in bbox_sizes if b['width'] > 1.0 or b['height'] > 1.0]
        print(f"\n  Large bbox files (>1deg) that could be split: {len(large_bboxes)}")
        for b in large_bboxes:
            tiles_needed = math.ceil(b['width']) * math.ceil(b['height'])
            print(f"    {b['file']}")
            print(f"      Current: {b['width']:.2f}deg x {b['height']:.2f}deg ({b['area_km2']:,.0f} km²)")
            print(f"      Could split into: {math.ceil(b['width'])} x {math.ceil(b['height'])} = {tiles_needed} 1-degree tiles")
    
    if tile_sizes:
        print("\nTile Files:")
        widths = [t['width'] for t in tile_sizes]
        heights = [t['height'] for t in tile_sizes]
        
        print(f"  Count: {len(tile_sizes)}")
        print(f"  Width range: {min(widths):.2f} - {max(widths):.2f} degrees")
        print(f"  Height range: {min(heights):.2f} - {max(heights):.2f} degrees")
        
        # Check if tiles are already 1-degree
        one_deg_tiles = [t for t in tile_sizes if abs(t['width'] - 1.0) < 0.01 and abs(t['height'] - 1.0) < 0.01]
        print(f"  Already 1-degree tiles: {len(one_deg_tiles)}/{len(tile_sizes)}")
    
    print("\n" + "=" * 70)
    print("PROVIDER LIMITATIONS")
    print("=" * 70)
    print()
    print("OpenTopography (SRTMGL1, COP30):")
    print("  - Maximum area: 450,000 km²")
    print("  - Maximum dimension: ~4.0 degrees")
    print("  - Tiling threshold: ~420,000 km² or >4.0deg")
    print()
    print("OpenTopography (SRTMGL3, COP90):")
    print("  - Maximum area: ~500,000 km² (90m resolution, less data)")
    print("  - Maximum dimension: ~4.5 degrees")
    print()
    print("USGS 3DEP (USA only, 10m):")
    print("  - Maximum area: ~1,000,000 km²")
    print("  - Maximum dimension: ~5-6 degrees")
    print("  - Usually no tiling needed for states")
    print()
    print("=" * 70)
    print("SPLITTING STRATEGY")
    print("=" * 70)
    print()
    print("Existing large bbox files can be split into 1-degree tiles:")
    print("  1. Read the large GeoTIFF")
    print("  2. Split into 1-degree grid-aligned tiles")
    print("  3. Save each tile with standard naming: N{lat:02d}_W{lon:03d}_30m.tif")
    print("  4. Delete original large file (optional, after verification)")
    print()
    print("Benefits:")
    print("  - Reuse existing downloads")
    print("  - Standardize on 1-degree grid")
    print("  - Enable maximum reuse across regions")
    print("  - Unified system (no bbox vs tiles distinction)")

if __name__ == '__main__':
    analyze_files()

