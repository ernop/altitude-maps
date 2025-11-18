"""
Test resolution selection logic with various region sizes.
Validates that the system selects appropriate resolutions for all region types.
"""
from src.tile_geometry import calculate_visible_pixel_size
from src.downloaders.orchestrator import determine_min_required_resolution, determine_required_resolution_and_dataset
from src.regions_config import get_region
from src.types import RegionType

def test_resolution_selection():
    """Test resolution selection for various region sizes."""
    
    test_cases = [
        # (name, region_id, target_pixels, expected_resolution, expected_dataset, reason)
        # California: 1005m/pixel → 1000m native (1.005x) is perfect match
        ('California (huge)', 'california', 1024, 1000, 'GMTED2010_1KM', 'Native resolution match'),
        # California: 502m/pixel → 500m native (1.004x) is perfect match
        ('California (huge)', 'california', 2048, 500, 'GMTED2010_500M', 'Native resolution match'),
        # Idaho: 1292m/pixel → 500m (2.58x oversampling) meets Nyquist
        ('Idaho (medium)', 'idaho', 512, 500, 'GMTED2010_500M', 'Meets Nyquist with 500m'),
        # Idaho: 323m/pixel → 90m (3.59x oversampling) meets Nyquist
        ('Idaho (medium)', 'idaho', 2048, 90, 'SRTMGL3', 'Meets Nyquist with 90m'),
        # Rhode Island: 41m/pixel → 10m (4.13x oversampling) meets Nyquist
        ('Rhode Island (small)', 'rhode_island', 2048, 10, 'USA_3DEP', 'Meets Nyquist with 10m'),
        # Boulder City: 9.6m/pixel → 10m native (0.96x) is perfect match
        ('Boulder City (tiny)', 'boulder_city', 2048, 10, 'USA_3DEP', 'Native resolution match'),
        # Iceland: 425m/pixel → 500m native (1.18x) is perfect match
        ('Iceland (medium)', 'iceland', 2048, 500, 'GMTED2010_500M', 'Native resolution match'),
        # Baja California: 1015m/pixel → 1000m native (1.015x) is perfect match
        ('Baja California (large)', 'baja_california', 1024, 1000, 'GMTED2010_1KM', 'Native resolution match'),
    ]
    
    print("="*80)
    print("RESOLUTION SELECTION VALIDATION TEST")
    print("="*80)
    print()
    
    all_passed = True
    
    for name, region_id, target_pixels, expected_res, expected_dataset, reason in test_cases:
        print(f"Testing: {name}")
        print(f"  Region: {region_id}, target_pixels: {target_pixels}")
        print(f"  Expected: {expected_res}m ({expected_dataset}) - {reason}")
        
        # Get region config
        config = get_region(region_id)
        if not config:
            print(f"  ERROR: Region '{region_id}' not found")
            all_passed = False
            continue
        
        # Calculate visible pixel size
        visible = calculate_visible_pixel_size(config.bounds, target_pixels)
        print(f"  Visible pixel size: {visible['avg_m_per_pixel']:.1f}m/pixel")
        
        # Determine resolution and dataset
        try:
            res, dataset = determine_required_resolution_and_dataset(
                region_id,
                config.region_type,
                {'bounds': config.bounds, 'name': config.name},
                target_pixels
            )
            
            print(f"  Selected: {res}m, {dataset}")
            
            # Verify selection
            if res != expected_res:
                print(f"  FAIL: Expected {expected_res}m, got {res}m")
                all_passed = False
            elif dataset != expected_dataset:
                print(f"  FAIL: Expected {expected_dataset}, got {dataset}")
                all_passed = False
            else:
                # Verify Nyquist requirement
                oversampling = visible['avg_m_per_pixel'] / res
                if oversampling < 2.0 and oversampling < 0.8:
                    print(f"  WARNING: Oversampling {oversampling:.2f}x < 2.0x (Nyquist)")
                    all_passed = False
                elif oversampling >= 2.0:
                    print(f"  PASS: {oversampling:.2f}x oversampling (meets Nyquist)")
                elif 0.8 <= oversampling <= 1.2:
                    print(f"  PASS: Native resolution ({oversampling:.2f}x)")
                else:
                    print(f"  PASS: {oversampling:.2f}x")
        
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
        
        print()
    
    print("="*80)
    if all_passed:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("="*80)
    
    return all_passed

if __name__ == "__main__":
    import sys
    success = test_resolution_selection()
    sys.exit(0 if success else 1)

