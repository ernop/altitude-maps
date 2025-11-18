"""
Test script to download and validate test regions at different resolutions.

Downloads three test regions sized to guarantee 10m, 30m, and 90m resolution selection.
Validates that the correct resolution was selected and asks user to confirm success.

Usage:
    python test_resolution_downloads.py
"""
import sys
import subprocess
from pathlib import Path
import rasterio
from typing import Tuple, Optional

from src.region_config import get_region
from src.tile_geometry import calculate_visible_pixel_size
from src.downloaders.orchestrator import determine_min_required_resolution
from src.validation import find_raw_file
from src.config import DEFAULT_TARGET_PIXELS


def get_expected_source(resolution: int) -> str:
    """Map resolution to expected source name."""
    return {10: 'usa_3dep', 30: 'srtm_30m', 90: 'srtm_90m'}[resolution]


def validate_downloaded_file(region_id: str, expected_resolution: int) -> Tuple[bool, str]:
    """
    Validate that downloaded file exists and matches expected resolution.
    
    Returns:
        (success: bool, message: str)
    """
    expected_source = get_expected_source(expected_resolution)
    
    # Find the downloaded file
    raw_path, source = find_raw_file(region_id, min_required_resolution_meters=expected_resolution)
    
    if not raw_path:
        return False, f"No file found for {region_id}"
    
    if source != expected_source:
        return False, f"Expected source '{expected_source}' but got '{source}'"
    
    # Verify file exists and is readable
    if not raw_path.exists():
        return False, f"File path exists but file not found: {raw_path}"
    
    # Check file size (should be > 1KB)
    file_size = raw_path.stat().st_size
    if file_size < 1024:
        return False, f"File too small ({file_size} bytes) - may be corrupted"
    
    # Try to open as GeoTIFF
    try:
        with rasterio.open(raw_path) as src:
            # Basic validation - file can be opened
            if src.width == 0 or src.height == 0:
                return False, f"Invalid dimensions: {src.width}x{src.height}"
            
            # Check if data looks valid (not all nodata)
            import numpy as np
            data = src.read(1).astype(np.float32)
            # Handle nodata values
            if src.nodata is not None and not np.isnan(src.nodata):
                data[data == src.nodata] = np.nan
            valid_pixels = np.sum(~np.isnan(data))
            if valid_pixels == 0:
                return False, "File contains only nodata values"
            
            return True, f"Valid GeoTIFF: {src.width}x{src.height}, {file_size / 1024 / 1024:.1f}MB"
    except Exception as e:
        return False, f"Failed to open GeoTIFF: {e}"


def test_region(region_id: str, expected_resolution: int) -> bool:
    """
    Download and validate a test region.
    
    Returns:
        True if test passed, False otherwise
    """
    print(f"\n{'='*70}")
    print(f"TEST: {region_id.upper()} (Expected: {expected_resolution}m)")
    print(f"{'='*70}")
    
    # Get region config
    config = get_region(region_id)
    if not config:
        print(f"ERROR: Region '{region_id}' not found in config")
        return False
    
    # Calculate expected visible pixel size
    visible = calculate_visible_pixel_size(config.bounds, DEFAULT_TARGET_PIXELS)
    print(f"Region bounds: {config.bounds}")
    print(f"Visible pixel size: {visible['avg_m_per_pixel']:.1f}m/pixel")
    print(f"Target pixels: {DEFAULT_TARGET_PIXELS}")
    
    # Verify resolution selection logic
    min_required = determine_min_required_resolution(
        visible['avg_m_per_pixel'],
        available_resolutions=[10, 30, 90]
    )
    print(f"System selected: {min_required}m resolution")
    
    if min_required != expected_resolution:
        print(f"ERROR: Expected {expected_resolution}m but system selected {min_required}m")
        print(f"  Visible pixels: {visible['avg_m_per_pixel']:.1f}m")
        print(f"  Oversampling: {visible['avg_m_per_pixel'] / expected_resolution:.2f}x")
        return False
    
    print(f"[OK] Resolution selection correct ({expected_resolution}m)")
    
    # Download the region
    print(f"\nDownloading {config.name}...")
    try:
        import os
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run(
            [sys.executable, 'ensure_region.py', region_id],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env,
            check=False
        )
        
        # Always show download output for debugging
        if result.stdout:
            print("Download output:")
            # Show last 50 lines to avoid overwhelming output
            lines = result.stdout.split('\n')
            if len(lines) > 50:
                print("  ... (showing last 50 lines) ...")
                for line in lines[-50:]:
                    print(f"  {line}")
            else:
                for line in lines:
                    print(f"  {line}")
        
        if result.returncode != 0:
            print(f"ERROR: Download failed (return code {result.returncode})")
            if result.stderr:
                print(f"STDERR:\n{result.stderr}")
            return False
        
        print("✓ Download completed")
    except Exception as e:
        print(f"ERROR: Exception during download: {e}")
        return False
    
    # Validate downloaded file
    print(f"\nValidating downloaded file...")
    success, message = validate_downloaded_file(region_id, expected_resolution)
    
    if success:
        print(f"[OK] {message}")
        print(f"\n{'='*70}")
        print(f"TEST PASSED: {region_id}")
        print(f"{'='*70}")
        return True
    else:
        print(f"[FAIL] Validation failed: {message}")
        print(f"\n{'='*70}")
        print(f"TEST FAILED: {region_id}")
        print(f"{'='*70}")
        return False


def main():
    """Run all resolution tests."""
    import argparse
    parser = argparse.ArgumentParser(description="Test resolution downloads")
    parser.add_argument("--non-interactive", action="store_true", help="Skip user prompts")
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("RESOLUTION DOWNLOAD TESTS")
    print("="*70)
    print("\nThis script downloads three test regions to verify resolution selection:")
    print("  1. test_10m_colorado - Should select 10m (USGS 3DEP)")
    print("  2. test_30m_utah - Should select 30m (SRTM)")
    print("  3. test_90m_wyoming - Should select 90m (SRTM)")
    print(f"\nUsing default target_pixels: {DEFAULT_TARGET_PIXELS}")
    
    if not args.non_interactive:
        print("\nPress Enter to continue, or Ctrl+C to cancel...")
        try:
            input()
        except KeyboardInterrupt:
            print("\nCancelled.")
            return 1
    else:
        print("\nRunning in non-interactive mode...")
    
    tests = [
        ("test_10m_colorado", 10),
        ("test_30m_utah", 30),
        ("test_90m_wyoming", 90),
    ]
    
    results = []
    for region_id, expected_resolution in tests:
        success = test_region(region_id, expected_resolution)
        results.append((region_id, success))
        
        if not success:
            print(f"\nTest failed for {region_id}. Stopping.")
            return 1
        
        # Ask user to confirm before next test (skip in non-interactive mode)
        if not args.non_interactive and region_id != tests[-1][0]:  # Not the last test
            print(f"\nTest passed! Press Enter to continue to next test, or Ctrl+C to stop...")
            try:
                input()
            except KeyboardInterrupt:
                print("\nStopped by user.")
                return 1
    
    # Final summary
    print("\n" + "="*70)
    print("ALL TESTS COMPLETED")
    print("="*70)
    print("\nResults:")
    for region_id, success in results:
        status = "PASSED" if success else "FAILED"
        print(f"  {region_id}: {status}")
    
    all_passed = all(success for _, success in results)
    if all_passed:
        print("\n[SUCCESS] All tests passed!")
        print("\nTo clean up test data, run:")
        print("  python delete_test_regions.py")
        return 0
    else:
        print("\n[FAILURE] Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

