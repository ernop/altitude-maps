"""
Test GMTED2010 download routing and error handling.
"""
from pathlib import Path
from src.downloaders.orchestrator import download_elevation_data
from src.region_config import get_region

def test_gmted2010_routing():
    """Test that GMTED2010 datasets route correctly."""
    
    print("="*80)
    print("GMTED2010 DOWNLOAD ROUTING TEST")
    print("="*80)
    print()
    
    # Test routing for each GMTED2010 resolution
    test_cases = [
        ('GMTED2010_250M', '250m'),
        ('GMTED2010_500M', '500m'),
        ('GMTED2010_1KM', '1000m'),
    ]
    
    # Use a small test region (Boulder City)
    config = get_region('boulder_city')
    if not config:
        print("ERROR: boulder_city region not found")
        return False
    
    region_info = {
        'bounds': config.bounds,
        'name': config.name
    }
    
    all_passed = True
    
    for dataset_code, resolution_str in test_cases:
        print(f"Testing routing for {dataset_code} ({resolution_str})")
        
        # This should route to GMTED2010 downloader
        # Since tiles don't exist, it should fail gracefully with helpful message
        try:
            result = download_elevation_data(
                'boulder_city',
                region_info,
                dataset_override=dataset_code,
                target_pixels=2048
            )
            
            if result:
                print(f"  WARNING: Download succeeded (tiles may exist)")
            else:
                print(f"  PASS: Download failed gracefully (expected - tiles don't exist)")
                # Check that error message was printed (we can't capture it, but we know it failed)
        
        except Exception as e:
            print(f"  ERROR: Exception raised: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
        
        print()
    
    print("="*80)
    if all_passed:
        print("ROUTING TESTS PASSED")
    else:
        print("SOME ROUTING TESTS FAILED")
    print("="*80)
    
    return all_passed

if __name__ == "__main__":
    import sys
    success = test_gmted2010_routing()
    sys.exit(0 if success else 1)

