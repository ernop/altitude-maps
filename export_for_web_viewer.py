"""
Export elevation data for the interactive web viewer.
"""
import sys
import json
import numpy as np
from pathlib import Path

try:
    from src.data_processing import prepare_visualization_data
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

def export_elevation_data(tif_path: str, output_path: str, max_size: int = 0):
    """
    Export elevation data to JSON format for web viewer.
    Exports raw data (optionally downsampled) so bucketing can be done client-side.
    
    Args:
        tif_path: Path to GeoTIFF file
        output_path: Output JSON file path
        max_size: Maximum dimension (will downsample if larger). Use 0 for full resolution.
    """
    print(f"\n🗺️  Exporting RAW elevation data for interactive web viewer...")
    print(f"   Input: {tif_path}")
    print(f"   Output: {output_path}")
    print(f"   Max dimension: {max_size if max_size > 0 else 'FULL RESOLUTION'}")
    
    # Load and process data WITHOUT bucketing (we'll do that client-side)
    data = prepare_visualization_data(tif_path)
    
    elevation_viz = data["elevation_viz"]
    bounds = data["bounds"]
    
    # Optional downsampling for reasonable file sizes
    if max_size > 0 and (elevation_viz.shape[0] > max_size or elevation_viz.shape[1] > max_size):
        step_y = max(1, elevation_viz.shape[0] // max_size)
        step_x = max(1, elevation_viz.shape[1] // max_size)
        elevation_viz = elevation_viz[::step_y, ::step_x]
        print(f"   Downsampled to {elevation_viz.shape} (step: {step_y}×{step_x})")
    
    # Get dimensions
    height, width = elevation_viz.shape
    
    print(f"\n📊 Data dimensions: {width} × {height}")
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
    
    # Create export data
    export_data = {
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
        }
    }
    
    # Write JSON
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(export_data, f, separators=(',', ':'))
    
    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"\n✅ Exported to: {output_file}")
    print(f"   File size: {file_size_mb:.2f} MB")
    print(f"   Data points: {width * height:,}")
    
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
    
    args = parser.parse_args()
    
    tif_file_path = Path(args.tif_file)
    if not tif_file_path.exists():
        print(f"\n❌ Error: File not found: {tif_file_path}")
        return 1
    
    export_elevation_data(
        str(tif_file_path),
        args.output,
        max_size=args.max_size
    )
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

