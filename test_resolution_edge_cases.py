"""
Test edge cases in resolution selection logic.
"""
from src.downloaders.orchestrator import determine_min_required_resolution

def test_edge_cases():
    """Test edge cases in resolution determination."""
    
    print("="*80)
    print("RESOLUTION SELECTION EDGE CASES TEST")
    print("="*80)
    print()
    
    test_cases = [
        # (visible_m_per_pixel, available_resolutions, expected_resolution, description)
        # Exact native match
        (1000.0, [10, 30, 90, 250, 500, 1000], 1000, "Exact 1000m native match"),
        (500.0, [10, 30, 90, 250, 500, 1000], 500, "Exact 500m native match"),
        (10.0, [10, 30, 90, 250, 500, 1000], 10, "Exact 10m native match"),
        
        # Near-native (within 0.8-1.2x range)
        (1000.0 * 0.9, [10, 30, 90, 250, 500, 1000], 1000, "900m visible → 1000m native (0.9x)"),
        (1000.0 * 1.1, [10, 30, 90, 250, 500, 1000], 1000, "1100m visible → 1000m native (1.1x)"),
        (500.0 * 0.85, [10, 30, 90, 250, 500, 1000], 500, "425m visible → 500m native (0.85x)"),
        
        # Just below native threshold (needs next finer)
        (1000.0 * 0.75, [10, 30, 90, 250, 500, 1000], 500, "750m visible → 500m (1.5x oversampling)"),
        (500.0 * 0.75, [10, 30, 90, 250, 500, 1000], 250, "375m visible → 250m (1.5x oversampling)"),
        
        # Nyquist threshold (exactly 2.0x)
        (1000.0 * 2.0, [10, 30, 90, 250, 500, 1000], 1000, "2000m visible → 1000m (2.0x oversampling)"),
        (500.0 * 2.0, [10, 30, 90, 250, 500, 1000], 500, "1000m visible → 500m (2.0x oversampling)"),
        
        # Well above Nyquist
        (1000.0 * 3.0, [10, 30, 90, 250, 500, 1000], 1000, "3000m visible → 1000m (3.0x oversampling)"),
        (500.0 * 5.0, [10, 30, 90, 250, 500, 1000], 500, "2500m visible → 500m (5.0x oversampling)"),
        
        # Very small visible pixels (needs finest resolution)
        (5.0, [10, 30, 90, 250, 500, 1000], 10, "5m visible → 10m (2.0x oversampling)"),
        (8.0, [10, 30, 90, 250, 500, 1000], 10, "8m visible → 10m native (0.8x)"),
        
        # Missing resolutions (fallback behavior)
        (2000.0, [10, 30, 90], 90, "2000m visible → 90m (22x oversampling, only fine resolutions available)"),
        (100.0, [250, 500, 1000], 250, "100m visible → 250m (2.5x oversampling, only coarse resolutions available)"),
    ]
    
    all_passed = True
    
    for visible_m_per_pixel, available_resolutions, expected_res, description in test_cases:
        print(f"Testing: {description}")
        print(f"  Visible: {visible_m_per_pixel:.1f}m/pixel")
        print(f"  Available: {available_resolutions}")
        
        try:
            result = determine_min_required_resolution(
                visible_m_per_pixel,
                available_resolutions=available_resolutions
            )
            
            print(f"  Selected: {result}m")
            
            if result != expected_res:
                print(f"  FAIL: Expected {expected_res}m, got {result}m")
                all_passed = False
            else:
                oversampling = visible_m_per_pixel / result
                if 0.8 <= oversampling <= 1.2:
                    print(f"  PASS: Native resolution ({oversampling:.2f}x)")
                elif oversampling >= 2.0:
                    print(f"  PASS: {oversampling:.2f}x oversampling (meets Nyquist)")
                else:
                    print(f"  PASS: {oversampling:.2f}x oversampling")
        
        except ValueError as e:
            print(f"  ERROR: ValueError: {e}")
            all_passed = False
        except Exception as e:
            print(f"  ERROR: Unexpected exception: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
        
        print()
    
    print("="*80)
    if all_passed:
        print("ALL EDGE CASE TESTS PASSED")
    else:
        print("SOME EDGE CASE TESTS FAILED")
    print("="*80)
    
    return all_passed

if __name__ == "__main__":
    import sys
    success = test_edge_cases()
    sys.exit(0 if success else 1)

