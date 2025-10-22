"""
Export elevation data for the interactive web viewer.

FORMAT VERSION HISTORY:
- v2 (2025-10-22): Natural GeoTIFF orientation, no transformations
- v1 (legacy): Had fliplr() + rot90() transformations (DEPRECATED)

⚠️ When changing export format, increment DATA_FORMAT_VERSION and re-export ALL data!
"""
import sys
import json
import numpy as np
from pathlib import Path
from datetime import datetime

try:
    from src.data_processing import prepare_visualization_data
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

# Data format version - increment when changing data transformations/structure
DATA_FORMAT_VERSION = 2

def export_elevation_data(tif_path: str, output_path: str, max_size: int = 0, 
                         mask_country: str = None, export_borders: bool = False):
    """
    Export elevation data to JSON format for web viewer.
    Exports raw data (optionally downsampled) so bucketing can be done client-side.
    
    Args:
        tif_path: Path to GeoTIFF file
        output_path: Output JSON file path
        max_size: Maximum dimension (will downsample if larger). Use 0 for full resolution.
        mask_country: Optional country name to mask data to
        export_borders: If True, also export borders to a separate file
    """
    print(f"\n[*] Exporting RAW elevation data for interactive web viewer...")
    print(f"   Input: {tif_path}")
    print(f"   Output: {output_path}")
    print(f"   Max dimension: {max_size if max_size > 0 else 'FULL RESOLUTION'}")
    if mask_country:
        print(f"   Masking to: {mask_country}")
    
    # Load and process data
    data = prepare_visualization_data(
        tif_path, 
        mask_usa=False,
        mask_country=mask_country
    )
    
    elevation_viz = data["elevation_viz"]
    bounds = data["bounds"]
    
    # Optional downsampling for reasonable file sizes
    if max_size > 0 and (elevation_viz.shape[0] > max_size or elevation_viz.shape[1] > max_size):
        step_y = max(1, elevation_viz.shape[0] // max_size)
        step_x = max(1, elevation_viz.shape[1] // max_size)
        elevation_viz = elevation_viz[::step_y, ::step_x]
        print(f"   Downsampled to {elevation_viz.shape} (step: {step_y}x{step_x})")
    
    # Get dimensions
    height, width = elevation_viz.shape
    
    print(f"\n[*] Data dimensions: {width} x {height}")
    print(f"   Elevation range: {data['z_min']:.0f}m to {data['z_max']:.0f}m")
    print(f"   Total data points: {width * height:,}")
    
    # Convert to list, handling NaN values
    elevation_list = []
    for row in elevation_viz:
        row_list = []
        for val in row:
            if np.isnan(val):
                row_list.append(None)
            else:
                row_list.append(float(val))
        elevation_list.append(row_list)
    
    # Create export data with versioning and metadata
    export_data = {
        "format_version": DATA_FORMAT_VERSION,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "source_file": str(Path(tif_path).name),
        "width": int(width),
        "height": int(height),
        "elevation": elevation_list,
        "bounds": {
            "left": float(bounds.left),
            "right": float(bounds.right),
            "top": float(bounds.top),
            "bottom": float(bounds.bottom)
        },
        "stats": {
            "min": float(data['z_min']),
            "max": float(data['z_max']),
            "mean": float(np.nanmean(elevation_viz))
        },
        "orientation": {
            "description": "Natural GeoTIFF orientation",
            "pixel_0_0": "Northwest corner",
            "row_direction": "North to South",
            "col_direction": "West to East",
            "transformations": "None"
        }
    }
    
    # Write JSON
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(export_data, f, separators=(',', ':'))
    
    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"\n[+] Exported to: {output_file}")
    print(f"   File size: {file_size_mb:.2f} MB")
    print(f"   Data points: {width * height:,}")
    
    # Optionally export borders
    if export_borders:
        try:
            from export_borders_for_viewer import export_borders_for_region
            borders_path = str(output_file).replace('.json', '_borders.json')
            print(f"\n[*] Exporting borders...")
            export_borders_for_region(
                tif_path,
                borders_path,
                countries=mask_country if mask_country else None,
                auto_detect=(mask_country is None)
            )
        except Exception as e:
            print(f"\n[!] Failed to export borders: {e}")
    
    return export_data

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Export elevation data for web viewer')
    parser.add_argument(
        'tif_file',
        nargs='?',
        default='data/usa_elevation/nationwide_usa_elevation.tif',
        help='Path to GeoTIFF elevation file'
    )
    parser.add_argument(
        '--output', '-o',
        default='generated/elevation_data.json',
        help='Output JSON file path'
    )
    parser.add_argument(
        '--max-size',
        type=int,
        default=0,
        help='Maximum dimension (will downsample if larger). Use 0 for full resolution. Default: 0 (FULL RES)'
    )
    parser.add_argument(
        '--mask-country',
        type=str,
        help='Mask elevation data to specific country (e.g., "United States of America")'
    )
    parser.add_argument(
        '--export-borders',
        action='store_true',
        help='Also export border data for the web viewer'
    )
    
    args = parser.parse_args()
    
    tif_file_path = Path(args.tif_file)
    if not tif_file_path.exists():
        print(f"\n[X] Error: File not found: {tif_file_path}")
        return 1
    
    export_elevation_data(
        str(tif_file_path),
        args.output,
        max_size=args.max_size,
        mask_country=args.mask_country,
        export_borders=args.export_borders
    )
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

