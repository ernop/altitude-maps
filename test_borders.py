"""
Quick test script to verify border functionality works correctly.
Tests that don't require actual elevation data.
"""
import sys

def test_border_manager_import():
    """Test that BorderManager can be imported."""
    try:
        from src.borders import BorderManager, get_border_manager
        print("[OK] BorderManager import successful")
        return True
    except ImportError as e:
        print(f"[FAIL] Failed to import BorderManager: {e}")
        return False


def test_border_manager_creation():
    """Test that BorderManager can be instantiated."""
    try:
        from src.borders import get_border_manager
        bm = get_border_manager()
        print("[OK] BorderManager instantiation successful")
        return True
    except Exception as e:
        print(f"[FAIL] Failed to create BorderManager: {e}")
        return False


def test_load_borders():
    """Test loading Natural Earth borders."""
    try:
        from src.borders import get_border_manager
        bm = get_border_manager()
        
        print("\n  Downloading Natural Earth 110m borders...")
        print("  (This will take a few seconds on first run)")
        
        world = bm.load_borders(resolution='110m')
        
        if world is None or world.empty:
            print("[FAIL] Loaded borders but dataset is empty")
            return False
        
        country_count = len(world)
        print(f"[OK] Successfully loaded {country_count} countries")
        return True
        
    except Exception as e:
        print(f"[FAIL] Failed to load borders: {e}")
        return False


def test_list_countries():
    """Test listing countries."""
    try:
        from src.borders import get_border_manager
        bm = get_border_manager()
        
        countries = bm.list_countries(resolution='110m')
        
        if not countries or len(countries) == 0:
            print("[FAIL] Country list is empty")
            return False
        
        # Check for some expected countries
        expected = ['United States of America', 'Canada', 'Mexico', 'China', 'India']
        found = [c for c in expected if c in countries]
        
        print(f"[OK] Listed {len(countries)} countries")
        print(f"  Found expected countries: {', '.join(found)}")
        return True
        
    except Exception as e:
        print(f"[FAIL] Failed to list countries: {e}")
        return False


def test_get_country():
    """Test getting a specific country."""
    try:
        from src.borders import get_border_manager
        bm = get_border_manager()
        
        usa = bm.get_country('United States of America', resolution='110m')
        
        if usa is None or usa.empty:
            print("[FAIL] Failed to find USA")
            return False
        
        print("[OK] Successfully retrieved USA borders")
        print(f"  Geometry type: {usa.iloc[0].geometry.geom_type}")
        return True
        
    except Exception as e:
        print(f"[FAIL] Failed to get country: {e}")
        return False


def test_get_countries_in_bbox():
    """Test finding countries in a bounding box."""
    try:
        from src.borders import get_border_manager
        bm = get_border_manager()
        
        # North America bounding box
        bbox = (-170, 15, -50, 85)
        countries = bm.get_countries_in_bbox(bbox, resolution='110m')
        
        if countries.empty:
            print("[FAIL] No countries found in North America bbox")
            return False
        
        country_names = sorted(countries.ADMIN.tolist())
        print(f"[OK] Found {len(country_names)} countries in North America bbox")
        print(f"  Examples: {', '.join(country_names[:5])}")
        return True
        
    except Exception as e:
        print(f"[FAIL] Failed to get countries in bbox: {e}")
        return False


def test_get_border_coordinates():
    """Test extracting border coordinates."""
    try:
        from src.borders import get_border_manager
        bm = get_border_manager()
        
        coords = bm.get_border_coordinates('United States of America', resolution='110m')
        
        if not coords or len(coords) == 0:
            print("[FAIL] No border coordinates returned")
            return False
        
        total_points = sum(len(c[0]) for c in coords)
        print(f"[OK] Extracted {len(coords)} border segments with {total_points:,} points")
        return True
        
    except Exception as e:
        print(f"[FAIL] Failed to get border coordinates: {e}")
        return False


def test_data_processing_import():
    """Test that updated data_processing imports correctly."""
    try:
        from src.data_processing import prepare_visualization_data
        print("[OK] Updated data_processing imports successfully")
        return True
    except ImportError as e:
        print(f"[FAIL] Failed to import data_processing: {e}")
        return False


def test_rendering_import():
    """Test that updated rendering imports correctly."""
    try:
        from src.rendering import render_visualization
        print("[OK] Updated rendering imports successfully")
        return True
    except ImportError as e:
        print(f"[FAIL] Failed to import rendering: {e}")
        return False


def main():
    """Run all tests."""
    print("="*70)
    print("BORDER FUNCTIONALITY TESTS")
    print("="*70)
    print()
    
    tests = [
        ("Import BorderManager", test_border_manager_import),
        ("Create BorderManager", test_border_manager_creation),
        ("Load borders", test_load_borders),
        ("List countries", test_list_countries),
        ("Get specific country", test_get_country),
        ("Get countries in bbox", test_get_countries_in_bbox),
        ("Get border coordinates", test_get_border_coordinates),
        ("Import data_processing", test_data_processing_import),
        ("Import rendering", test_rendering_import),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\nTest: {test_name}")
        print("-" * 70)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"[FAIL] Test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed! Border functionality is working correctly.")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

