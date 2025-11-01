"""
Validate all tiles and identify problematic ones.
"""

from pathlib import Path
import rasterio
import math

def validate_tile(tile_path: Path) -> dict:
    """Validate a single tile and return validation results."""
    result = {
        'name': tile_path.name,
        'valid': False,
        'errors': [],
        'size_mb': tile_path.stat().st_size / (1024 * 1024),
        'width_deg': None,
        'height_deg': None,
        'width_px': None,
        'height_px': None,
        'resolution_m': None,
        'is_1degree': False,
    }
    
    try:
        with rasterio.open(tile_path) as src:
            result['width_px'] = src.width
            result['height_px'] = src.height
            
            # Check dimensions
            if src.width == 0 or src.height == 0:
                result['errors'].append(f"Invalid dimensions: {src.width}x{src.height}")
                return result
            
            # Check CRS
            if src.crs is None or src.transform is None:
                result['errors'].append("Missing CRS or transform")
                return result
            
            if src.crs != rasterio.crs.CRS.from_epsg(4326):
                result['errors'].append(f"Wrong CRS: {src.crs}")
                return result
            
            # Check bounds
            bounds = src.bounds
            width_deg = bounds.right - bounds.left
            height_deg = bounds.top - bounds.bottom
            result['width_deg'] = width_deg
            result['height_deg'] = height_deg
            
            # Validate 1-degree size (unified grid system)
            is_1degree = (0.99 <= width_deg <= 1.01) and (0.99 <= height_deg <= 1.01)
            result['is_1degree'] = is_1degree
            
            if not is_1degree:
                result['errors'].append(f"NOT 1-degree tile: {width_deg:.3f}deg x {height_deg:.3f}deg")
            
            # Calculate resolution
            center_lat = (bounds.top + bounds.bottom) / 2.0
            meters_per_deg_lat = 111_320
            meters_per_deg_lon = 111_320 * math.cos(math.radians(center_lat))
            width_m = width_deg * meters_per_deg_lon
            height_m = height_deg * meters_per_deg_lat
            avg_resolution = (width_m / src.width + height_m / src.height) / 2.0
            result['resolution_m'] = avg_resolution
            
            # Validate resolution (30m dataset)
            if not (15 <= avg_resolution <= 50):
                result['errors'].append(f"Invalid resolution: {avg_resolution:.1f}m (should be 15-50m)")
            
            # Validate file size is reasonable
            # Expected: 1-degree tile at 30m should be ~5-50MB depending on latitude and terrain
            # At equator: ~21MB, at 40°N: ~16MB, at 60°N: ~8MB
            # But can vary 10x with terrain complexity (ocean vs mountains)
            expected_min_mb = 0.5  # Ocean tiles compress very well
            expected_max_mb = 500  # Mountains with complex terrain (but should be rare)
            
            # File size warnings (but don't fail validation for size alone)
            # Size varies dramatically with terrain complexity and latitude
            # Ocean tiles compress very well (<1MB), mountains compress poorly (>100MB)
            if result['size_mb'] < 0.1 and is_1degree:
                # Very suspicious - might be empty/corrupt
                result['errors'].append(f"Very small for 1-degree: {result['size_mb']:.2f}MB (might be empty/corrupt)")
            
            # If no errors, tile is valid
            if not result['errors']:
                result['valid'] = True
            
    except Exception as e:
        result['errors'].append(f"Error reading file: {e}")
    
    return result

def main():
    tiles_dir = Path('data/raw/srtm_30m/tiles')
    if not tiles_dir.exists():
        print(f"ERROR: {tiles_dir} does not exist!")
        return
    
    tiles = list(tiles_dir.glob('*.tif'))
    print(f"Validating {len(tiles)} tiles...")
    print("=" * 80)
    
    results = []
    for tile_path in tiles:
        result = validate_tile(tile_path)
        results.append(result)
    
    # Categorize results
    valid = [r for r in results if r['valid']]
    invalid = [r for r in results if not r['valid']]
    not_1degree = [r for r in results if not r.get('is_1degree', False)]
    
    print(f"\nValidation Results:")
    print(f"  Total tiles: {len(results)}")
    print(f"  Valid: {len(valid)} ({100*len(valid)/len(results):.1f}%)")
    print(f"  Invalid: {len(invalid)} ({100*len(invalid)/len(results):.1f}%)")
    print(f"  NOT 1-degree: {len(not_1degree)} ({100*len(not_1degree)/len(results):.1f}%)")
    
    if not_1degree:
        print(f"\nWARNING: Tiles that are NOT 1-degree (should be deleted):")
        for r in not_1degree:
            print(f"  {r['name']}: {r['width_deg']:.3f}deg x {r['height_deg']:.3f}deg ({r['width_px']}x{r['height_px']} px, {r['size_mb']:.2f}MB)")
            print(f"    Errors: {'; '.join(r['errors'])}")
    
    if invalid and len(invalid) <= 20:
        print(f"\nWARNING: Invalid tiles (first 20):")
        for r in invalid[:20]:
            print(f"  {r['name']}: {'; '.join(r['errors'])}")
    elif invalid:
        print(f"\nWARNING: {len(invalid)} invalid tiles found (too many to list)")
    
    if valid:
        sizes = [r['size_mb'] for r in valid]
        print(f"\nOK: Valid 1-degree tiles:")
        print(f"  Size range: {min(sizes):.2f} MB to {max(sizes):.2f} MB")
        print(f"  Average: {sum(sizes)/len(sizes):.2f} MB")
        print(f"  Median: {sorted(sizes)[len(sizes)//2]:.2f} MB")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATION:")
    if not_1degree:
        print(f"  Delete {len(not_1degree)} tiles that are NOT 1-degree")
        print(f"  They violate the unified 1-degree grid system")
    else:
        print("  All tiles are 1-degree OK")

if __name__ == '__main__':
    main()

