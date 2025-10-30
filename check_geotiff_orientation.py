"""
Diagnostic tool to check GeoTIFF orientation and transform metadata.
This will help us understand the actual data orientation from the file itself.
"""
import sys
import rasterio
import numpy as np
from pathlib import Path


def check_geotiff_orientation(tif_path: str):
    """
    Check and display GeoTIFF orientation metadata.
    
    The transform matrix tells us:
    - How pixel coordinates map to geographic coordinates
    - Whether rows/columns increase in expected directions
    """
    print("\n" + "=" * 70)
    print(f"  GEOTIFF ORIENTATION CHECK: {Path(tif_path).name}")
    print("=" * 70)
    
    with rasterio.open(tif_path) as src:
        # Basic info
        print(f"\nBASIC INFO:")
        print(f"   Dimensions: {src.width} x {src.height} (width x height)")
        print(f"   Bands: {src.count}")
        print(f"   Data type: {src.dtypes[0]}")
        print(f"   CRS: {src.crs}")
        
        # Bounds
        print(f"\nGEOGRAPHIC BOUNDS:")
        print(f"   Left (West):    {src.bounds.left:.6f}")
        print(f"   Right (East):   {src.bounds.right:.6f}")
        print(f"   Bottom (South): {src.bounds.bottom:.6f}")
        print(f"   Top (North):    {src.bounds.top:.6f}")
        
        # Transform matrix - THIS IS THE KEY!
        transform = src.transform
        print(f"\nAFFINE TRANSFORM MATRIX:")
        print(f"   {transform}")
        print(f"\n   Components:")
        print(f"   a (pixel width):  {transform.a:+.10f}  {'-> East' if transform.a > 0 else '<- West'}")
        print(f"   b (row rotation): {transform.b:+.10f}  {'(rotated)' if abs(transform.b) > 1e-6 else '(north-up)'}")
        print(f"   c (x origin):     {transform.c:+.10f}")
        print(f"   d (col rotation): {transform.d:+.10f}  {'(rotated)' if abs(transform.d) > 1e-6 else '(north-up)'}")
        print(f"   e (pixel height): {transform.e:+.10f}  {'v South' if transform.e < 0 else '^ North'}")
        print(f"   f (y origin):     {transform.f:+.10f}")
        
        # Determine orientation
        print(f"\nDATA ORIENTATION:")
        
        # Check column direction (X)
        if transform.a > 0:
            print(f"   [OK] Columns increase EASTWARD (standard)")
            col_direction = "East"
        else:
            print(f"   [!!] Columns increase WESTWARD (non-standard!)")
            col_direction = "West"
        
        # Check row direction (Y)
        if transform.e < 0:
            print(f"   [OK] Rows increase SOUTHWARD (standard)")
            row_direction = "South"
        else:
            print(f"   [!!] Rows increase NORTHWARD (non-standard!)")
            row_direction = "North"
        
        # Check for rotation
        if abs(transform.b) > 1e-6 or abs(transform.d) > 1e-6:
            print(f"   [!!] IMAGE IS ROTATED! (b={transform.b:.6f}, d={transform.d:.6f})")
            print(f"   This requires special handling!")
        else:
            print(f"   [OK] Image is north-up (no rotation)")
        
        # Test corner pixel coordinates
        print(f"\nCORNER PIXEL MAPPING:")
        
        # Top-left pixel (0, 0)
        lon_tl, lat_tl = transform * (0, 0)
        print(f"   Pixel (0, 0) -> Geographic ({lon_tl:.6f}, {lat_tl:.6f})")
        
        # Top-right pixel (width-1, 0)
        lon_tr, lat_tr = transform * (src.width - 1, 0)
        print(f"   Pixel ({src.width-1}, 0) -> Geographic ({lon_tr:.6f}, {lat_tr:.6f})")
        
        # Bottom-left pixel (0, height-1)
        lon_bl, lat_bl = transform * (0, src.height - 1)
        print(f"   Pixel (0, {src.height-1}) -> Geographic ({lon_bl:.6f}, {lat_bl:.6f})")
        
        # Bottom-right pixel (width-1, height-1)
        lon_br, lat_br = transform * (src.width - 1, src.height - 1)
        print(f"   Pixel ({src.width-1}, {src.height-1}) -> Geographic ({lon_br:.6f}, {lat_br:.6f})")
        
        # Verify corners match bounds
        print(f"\nVERIFICATION:")
        tl_matches_nw = abs(lon_tl - src.bounds.left) < 1e-3 and abs(lat_tl - src.bounds.top) < 1e-3
        br_matches_se = abs(lon_br - src.bounds.right) < 1e-3 and abs(lat_br - src.bounds.bottom) < 1e-3
        
        if tl_matches_nw and br_matches_se:
            print(f"   [OK] Pixel (0,0) is at NORTHWEST corner")
            print(f"   [OK] Pixel ({src.width-1},{src.height-1}) is at SOUTHEAST corner")
            print(f"   [OK] This is STANDARD orientation")
        else:
            print(f"   [!!] Corners don't match expected positions!")
            print(f"   [!!] This is NON-STANDARD orientation")
        
        # Read a small sample to check data
        print(f"\nDATA SAMPLE (top-left 5x5):")
        sample = src.read(1, window=((0, min(5, src.height)), (0, min(5, src.width))))
        print(f"   {sample}")
        print(f"   Min: {np.nanmin(sample):.2f}, Max: {np.nanmax(sample):.2f}")
        
        # FINAL RECOMMENDATION
        print(f"\n" + "=" * 70)
        print(f"  RECOMMENDED ARRAY INDEXING:")
        print(f"=" * 70)
        print(f"\n   data = src.read(1)")
        print(f"   # data.shape = ({src.height}, {src.width}) = (rows, cols)")
        print(f"   # data[row, col]")
        print(f"   #   row=0 is at {lat_tl:.2f} deg (top)")
        print(f"   #   row={src.height-1} is at {lat_bl:.2f} deg (bottom)")
        print(f"   #   col=0 is at {lon_tl:.2f} deg (left)")
        print(f"   #   col={src.width-1} is at {lon_tr:.2f} deg (right)")
        
        if transform.a > 0 and transform.e < 0:
            print(f"\n   [OK] STANDARD ORIENTATION - Use data as-is:")
            print(f"   - data[0, 0] is NORTHWEST corner")
            print(f"   - Increasing row -> South")
            print(f"   - Increasing col -> East")
            print(f"   - NO TRANSFORMATION NEEDED")
        else:
            print(f"\n   [!!] NON-STANDARD ORIENTATION - Needs correction:")
            if transform.a < 0:
                print(f"   - Columns increase WESTWARD -> Need to flip left-right")
            if transform.e > 0:
                print(f"   - Rows increase NORTHWARD -> Need to flip top-bottom")
        
        print(f"\n" + "=" * 70)
        
        return {
            'width': src.width,
            'height': src.height,
            'transform': transform,
            'bounds': src.bounds,
            'crs': src.crs,
            'col_direction': col_direction,
            'row_direction': row_direction,
            'is_standard': transform.a > 0 and transform.e < 0,
            'needs_flip_lr': transform.a < 0,
            'needs_flip_ud': transform.e > 0
        }


def main():
    if len(sys.argv) < 2:
        print("\nUsage: python check_geotiff_orientation.py <geotiff_file>")
        print("\nExample:")
        print("  python check_geotiff_orientation.py data/usa_elevation/nationwide_usa_elevation.tif")
        print("  python check_geotiff_orientation.py generated/regions/japan.tif")
        return 1
    
    tif_path = sys.argv[1]
    
    if not Path(tif_path).exists():
        print(f"\n Error: File not found: {tif_path}")
        return 1
    
    try:
        metadata = check_geotiff_orientation(tif_path)
        
        # Summary
        print(f"\n{'[OK] STANDARD' if metadata['is_standard'] else '[!!] NON-STANDARD'} orientation detected")
        
        return 0
    except Exception as e:
        print(f"\n[ERROR] Error reading GeoTIFF: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

