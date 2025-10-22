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
    
    args = parser.parse_args()
    
    # --- Step 1: Data Processing ---
    tif_file_path = Path(args.tif_file)
    if not tif_file_path.exists():
        print(f"\n❌ Error: File not found: {tif_file_path}")
        print("   Download with: python download_continental_usa.py --region nationwide_usa --yes")
        return 1
    
    visualization_data = prepare_visualization_data(str(tif_file_path))
    
    # --- Step 2: Rendering ---
    render_visualization(visualization_data, args.output)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

