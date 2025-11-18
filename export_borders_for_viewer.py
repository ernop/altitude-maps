"""
Export border data for the interactive web viewer.
Converts Natural Earth borders to JSON format for Three.js rendering.
"""
import sys
import json
import numpy as np
from pathlib import Path
from typing import Optional, List, Union
import rasterio
from src.borders import get_border_manager


def export_borders_for_region(
    tif_path: str,
    output_path: str,
    countries: Optional[Union[str, List[str]]] = None,
    auto_detect: bool = True,
    border_resolution: str = '110m'
):
    """
    Export border data for countries visible in an elevation dataset.
    
    Args:
        tif_path: Path to GeoTIFF file (to get bounding box)
        output_path: Output JSON file path for borders
        countries: Specific country name(s) to export, or None for auto-detect
        auto_detect: If True and countries is None, auto-detect from bbox
        border_resolution: Border detail level ('10m', '50m', '110m')
    """
    print(f"\n[*] Exporting border data for interactive viewer...")
    print(f"   Elevation file: {tif_path}")
    print(f"   Output: {output_path}")
    print(f"   Border resolution: {border_resolution}")
    
    border_manager = get_border_manager()
    
    # Get bounding box from elevation data
    with rasterio.open(tif_path) as src:
        bounds = src.bounds
        crs = src.crs
        bbox_tuple = (bounds.left, bounds.bottom, bounds.right, bounds.top)
        
        print(f"   Region bounds: {bounds}")
    
    # Determine which countries to export
    if countries is None and auto_detect:
        print(f"   Auto-detecting countries in region...")
        countries_gdf = border_manager.get_countries_in_bbox(bbox_tuple, border_resolution=border_resolution)
        country_list = countries_gdf.ADMIN.tolist()
        print(f"   Found {len(country_list)} countries: {', '.join(country_list)}")
    elif countries is None:
        print(f"[!] No countries specified and auto_detect=False")
        return None
    elif isinstance(countries, str):
        country_list = [countries]
    else:
        country_list = countries
    
    # Export each country's borders
    borders_data = {
        "bounds": {
            "left": float(bounds.left),
            "right": float(bounds.right),
            "top": float(bounds.top),
            "bottom": float(bounds.bottom)
        },
        "resolution": border_resolution,
        "countries": []
    }
    
    total_segments = 0
    total_points = 0
    
    for country_name in country_list:
        print(f"\n   Processing: {country_name}")
        
        # Get border coordinates in geographic coords (WGS84)
        border_coords = border_manager.get_border_coordinates(
            country_name,
            target_crs=crs,  # Match elevation data CRS
            border_resolution=border_resolution
        )
        
        if not border_coords:
            print(f"     WARNING: No borders found for '{country_name}'")
            continue
        
        # Convert to lists for JSON
        segments = []
        for lon_coords, lat_coords in border_coords:
            segment = {
                "lon": [float(x) for x in lon_coords],
                "lat": [float(y) for y in lat_coords]
            }
            segments.append(segment)
            total_points += len(lon_coords)
        
        borders_data["countries"].append({
            "name": country_name,
            "segments": segments,
            "segment_count": len(segments)
        })
        
        total_segments += len(segments)
        print(f"     Exported {len(segments)} segments with {sum(len(s['lon']) for s in segments):,} points")
    
    # Write JSON
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(borders_data, f, separators=(',', ':'))
    
    file_size_kb = output_file.stat().st_size / 1024
    print(f"\n[+] Exported to: {output_file}")
    print(f"   File size: {file_size_kb:.2f} KB")
    print(f"   Total countries: {len(borders_data['countries'])}")
    print(f"   Total segments: {total_segments}")
    print(f"   Total points: {total_points:,}")
    
    return borders_data


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Export border data for web viewer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect countries from elevation data
  python export_borders_for_viewer.py data/usa_elevation/nationwide_usa_elevation.tif
  
  # Export specific countries
  python export_borders_for_viewer.py data/usa.tif --countries "United States of America,Canada,Mexico"
  
  # Use high-resolution borders
  python export_borders_for_viewer.py data/california.tif --resolution 10m
        """
    )
    
    parser.add_argument(
        'tif_file',
        nargs='?',
        default='data/usa_elevation/nationwide_usa_elevation.tif',
        help='Path to GeoTIFF elevation file'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='generated/borders.json',
        help='Output JSON file path. Default: generated/borders.json'
    )
    
    parser.add_argument(
        '--countries', '-c',
        type=str,
        help='Comma-separated country names (e.g., "USA,Canada"). Leave empty for auto-detect.'
    )
    
    parser.add_argument(
        '--resolution', '-r',
        type=str,
        choices=['10m', '50m', '110m'],
        default='110m',
        help='Border resolution. Default: 110m'
    )
    
    parser.add_argument(
        '--no-auto-detect',
        action='store_true',
        help='Disable auto-detection (must specify --countries)'
    )
    
    args = parser.parse_args()
    
    tif_file_path = Path(args.tif_file)
    if not tif_file_path.exists():
        print(f"\n[X] Error: File not found: {tif_file_path}")
        return 1
    
    # Parse countries if provided
    countries = None
    if args.countries:
        countries = [c.strip() for c in args.countries.split(',')]
    
    export_borders_for_region(
        str(tif_file_path),
        args.output,
        countries=countries,
        auto_detect=not args.no_auto_detect,
        border_resolution=args.resolution
    )
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

