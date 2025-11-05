"""
Comprehensive tests for data source resolution logic.

Tests all scenarios from the decision matrix without touching files or network.
Uses pytest (Python's standard testing framework).

Run with: pytest tests/test_data_source_resolution.py -v
"""

import pytest
from pathlib import Path
from src.downloaders.data_source_resolution import (
    determine_data_source,
    DataSourceDecision
)


class TestDataSourceResolution:
    """Test suite for data source resolution decision logic."""
    
    # Test Case 1: US tiny region, needs 10m, no local cache
    def test_us_tiny_needs_10m_no_cache(self):
        """US tiny region needing 10m with no local data should error and guide to manual download."""
        decision = determine_data_source(
            region_id="cottonwood_valley",
            min_required_resolution=10,
            available_downloads=[10, 30, 90],
            local_cache={},
            accept_lower_quality=False,
            latitude_range=(40.55, 40.75)
        )
        
        assert decision.action == "ERROR_NEED_MANUAL"
        assert decision.resolution == 10
        assert decision.source_type == "manual"
        assert "USGS 3DEP" in decision.message
        assert "manual download" in decision.message
        assert "accept-lower-quality" in decision.message
    
    # Test Case 2: US tiny region, needs 10m, has 30m locally
    def test_us_tiny_needs_10m_has_30m_local(self):
        """US tiny region needing 10m with 30m local should NOT use local (insufficient)."""
        decision = determine_data_source(
            region_id="cottonwood_valley",
            min_required_resolution=10,
            available_downloads=[10, 30, 90],
            local_cache={30: Path("data/merged/srtm_30m/test_30m.tif")},
            accept_lower_quality=False,
            latitude_range=(40.55, 40.75)
        )
        
        assert decision.action == "ERROR_NEED_MANUAL"
        assert decision.resolution == 10
        assert "USGS 3DEP" in decision.message
    
    # Test Case 3: US tiny region, needs 10m, has 10m locally
    def test_us_tiny_needs_10m_has_10m_local(self):
        """US tiny region needing 10m with 10m local should use local data."""
        local_path = Path("data/raw/usa_3dep/test_10m.tif")
        decision = determine_data_source(
            region_id="cottonwood_valley",
            min_required_resolution=10,
            available_downloads=[10, 30, 90],
            local_cache={10: local_path},
            accept_lower_quality=False,
            latitude_range=(40.55, 40.75)
        )
        
        assert decision.action == "USE_LOCAL"
        assert decision.resolution == 10
        assert decision.source_type == "local"
        assert decision.file_path == local_path
        assert "meets 10m requirement" in decision.message
    
    # Test Case 4: US small region, needs 30m, no local cache
    def test_us_small_needs_30m_no_cache(self):
        """US small region needing 30m should download 30m SRTM."""
        decision = determine_data_source(
            region_id="small_us_park",
            min_required_resolution=30,
            available_downloads=[10, 30, 90],
            local_cache={},
            accept_lower_quality=False,
            latitude_range=(35.0, 36.0)
        )
        
        assert decision.action == "DOWNLOAD"
        assert decision.resolution == 30
        assert decision.source_type == "download"
        assert decision.download_dataset == "SRTMGL1"
        assert "meets 30m requirement" in decision.message
    
    # Test Case 5: US small region, needs 30m, has 10m locally
    def test_us_small_needs_30m_has_10m_local(self):
        """US small region needing 30m with 10m local should use local (better than needed)."""
        local_path = Path("data/raw/usa_3dep/test_10m.tif")
        decision = determine_data_source(
            region_id="small_us_park",
            min_required_resolution=30,
            available_downloads=[10, 30, 90],
            local_cache={10: local_path},
            accept_lower_quality=False,
            latitude_range=(35.0, 36.0)
        )
        
        assert decision.action == "USE_LOCAL"
        assert decision.resolution == 10
        assert decision.file_path == local_path
        assert "meets 30m requirement" in decision.message
    
    # Test Case 6: US small region, needs 30m, has 90m locally
    def test_us_small_needs_30m_has_90m_local(self):
        """US small region needing 30m with 90m local should NOT use local (insufficient)."""
        decision = determine_data_source(
            region_id="small_us_park",
            min_required_resolution=30,
            available_downloads=[10, 30, 90],
            local_cache={90: Path("data/merged/srtm_90m/test_90m.tif")},
            accept_lower_quality=False,
            latitude_range=(35.0, 36.0)
        )
        
        assert decision.action == "DOWNLOAD"
        assert decision.resolution == 30
        assert decision.download_dataset == "SRTMGL1"
    
    # Test Case 7: US large region, needs 90m, no local cache
    def test_us_large_needs_90m_no_cache(self):
        """US large region needing 90m should download 90m SRTM."""
        decision = determine_data_source(
            region_id="california",
            min_required_resolution=90,
            available_downloads=[10, 30, 90],
            local_cache={},
            accept_lower_quality=False,
            latitude_range=(32.5, 42.0)
        )
        
        assert decision.action == "DOWNLOAD"
        assert decision.resolution == 90
        assert decision.download_dataset == "SRTMGL3"
        assert "meets 90m requirement" in decision.message
    
    # Test Case 8: US large region, needs 90m, has 30m locally
    def test_us_large_needs_90m_has_30m_local(self):
        """US large region needing 90m with 30m local should use local (better than needed)."""
        local_path = Path("data/merged/srtm_30m/california_30m.tif")
        decision = determine_data_source(
            region_id="california",
            min_required_resolution=90,
            available_downloads=[10, 30, 90],
            local_cache={30: local_path},
            accept_lower_quality=False,
            latitude_range=(32.5, 42.0)
        )
        
        assert decision.action == "USE_LOCAL"
        assert decision.resolution == 30
        assert decision.file_path == local_path
    
    # Test Case 9: International tiny region, needs 10m, no local cache
    def test_intl_tiny_needs_10m_no_cache(self):
        """International tiny region needing 10m should error (not available internationally)."""
        decision = determine_data_source(
            region_id="tiny_iceland_feature",
            min_required_resolution=10,
            available_downloads=[30, 90],
            local_cache={},
            accept_lower_quality=False,
            latitude_range=(63.0, 67.0)
        )
        
        assert decision.action == "ERROR_INSUFFICIENT"
        assert decision.resolution == 10
        assert "accept-lower-quality" in decision.message
    
    # Test Case 10: International small region, needs 30m, no local cache
    def test_intl_small_needs_30m_no_cache(self):
        """International small region needing 30m should download 30m."""
        decision = determine_data_source(
            region_id="japan_small_area",
            min_required_resolution=30,
            available_downloads=[30, 90],
            local_cache={},
            accept_lower_quality=False,
            latitude_range=(35.0, 36.0)
        )
        
        assert decision.action == "DOWNLOAD"
        assert decision.resolution == 30
        assert decision.download_dataset == "SRTMGL1"
    
    # Test Case 11: International small region, needs 30m, has 30m locally
    def test_intl_small_needs_30m_has_30m_local(self):
        """International small region needing 30m with 30m local should use local."""
        local_path = Path("data/merged/srtm_30m/japan_30m.tif")
        decision = determine_data_source(
            region_id="japan_small_area",
            min_required_resolution=30,
            available_downloads=[30, 90],
            local_cache={30: local_path},
            accept_lower_quality=False,
            latitude_range=(35.0, 36.0)
        )
        
        assert decision.action == "USE_LOCAL"
        assert decision.resolution == 30
        assert decision.file_path == local_path
    
    # Test Case 12: International small region, needs 30m, has 10m locally (edge case)
    def test_intl_small_needs_30m_has_10m_local(self):
        """International region with locally available 10m (from manual download) should use it."""
        local_path = Path("data/manual/region_10m.tif")
        decision = determine_data_source(
            region_id="japan_small_area",
            min_required_resolution=30,
            available_downloads=[30, 90],
            local_cache={10: local_path},
            accept_lower_quality=False,
            latitude_range=(35.0, 36.0)
        )
        
        assert decision.action == "USE_LOCAL"
        assert decision.resolution == 10
        assert decision.file_path == local_path
    
    # Test Case 13: International large region, needs 90m, no local cache
    def test_intl_large_needs_90m_no_cache(self):
        """International large region needing 90m should download 90m."""
        decision = determine_data_source(
            region_id="brazil_large",
            min_required_resolution=90,
            available_downloads=[30, 90],
            local_cache={},
            accept_lower_quality=False,
            latitude_range=(-33.0, 5.0)
        )
        
        assert decision.action == "DOWNLOAD"
        assert decision.resolution == 90
        assert decision.download_dataset == "SRTMGL3"
    
    # Test Case 14: International large region, needs 90m, has 30m locally
    def test_intl_large_needs_90m_has_30m_local(self):
        """International large region needing 90m with 30m local should use local (better)."""
        local_path = Path("data/merged/srtm_30m/brazil_30m.tif")
        decision = determine_data_source(
            region_id="brazil_large",
            min_required_resolution=90,
            available_downloads=[30, 90],
            local_cache={30: local_path},
            accept_lower_quality=False,
            latitude_range=(-33.0, 5.0)
        )
        
        assert decision.action == "USE_LOCAL"
        assert decision.resolution == 30
        assert decision.file_path == local_path
    
    # Test Case 15: US tiny with accept_lower_quality flag
    def test_us_tiny_needs_10m_accept_lower_quality(self):
        """US tiny region with accept_lower_quality should download 30m."""
        decision = determine_data_source(
            region_id="cottonwood_valley",
            min_required_resolution=10,
            available_downloads=[10, 30, 90],
            local_cache={},
            accept_lower_quality=True,
            latitude_range=(40.55, 40.75)
        )
        
        assert decision.action == "DOWNLOAD"
        assert decision.resolution == 30
        assert decision.download_dataset == "SRTMGL1"
        assert "accepted lower quality" in decision.message
    
    # Test Case 16: International tiny with accept_lower_quality flag
    def test_intl_tiny_needs_10m_accept_lower_quality(self):
        """International tiny region with accept_lower_quality should download 30m."""
        decision = determine_data_source(
            region_id="tiny_iceland_feature",
            min_required_resolution=10,
            available_downloads=[30, 90],
            local_cache={},
            accept_lower_quality=True,
            latitude_range=(63.0, 67.0)
        )
        
        assert decision.action == "DOWNLOAD"
        assert decision.resolution == 30
        assert decision.download_dataset == "COP30"
        assert "accepted lower quality" in decision.message
    
    # Test Case 17: Native resolution display (28m visible, 30m source)
    def test_native_resolution_28m_visible_30m_source(self):
        """Region with 28m visible pixels should accept 30m source (native display, 0.93x)."""
        decision = determine_data_source(
            region_id="medium_region",
            min_required_resolution=30,
            available_downloads=[30, 90],
            local_cache={},
            accept_lower_quality=False,
            latitude_range=(45.0, 46.0)
        )
        
        assert decision.action == "DOWNLOAD"
        assert decision.resolution == 30
        assert decision.download_dataset == "SRTMGL1"
    
    # Test Case 18: Native resolution display (92m visible, 90m source)
    def test_native_resolution_92m_visible_90m_source(self):
        """Region with 92m visible pixels should accept 90m source (native display, 1.02x)."""
        decision = determine_data_source(
            region_id="large_region",
            min_required_resolution=90,
            available_downloads=[30, 90],
            local_cache={},
            accept_lower_quality=False,
            latitude_range=(45.0, 46.0)
        )
        
        assert decision.action == "DOWNLOAD"
        assert decision.resolution == 90
        assert decision.download_dataset == "SRTMGL3"
    
    # Test Case 19: High latitude region should use Copernicus
    def test_high_latitude_uses_copernicus(self):
        """Region above 60N should use Copernicus DEM instead of SRTM."""
        decision = determine_data_source(
            region_id="iceland",
            min_required_resolution=90,
            available_downloads=[30, 90],
            local_cache={},
            accept_lower_quality=False,
            latitude_range=(63.0, 67.0)
        )
        
        assert decision.action == "DOWNLOAD"
        assert decision.resolution == 90
        assert decision.download_dataset == "COP90"
    
    # Test Case 20: Multiple local resolutions - should pick finest
    def test_multiple_local_picks_finest(self):
        """When multiple local resolutions available, should pick finest that meets requirement."""
        decision = determine_data_source(
            region_id="region_with_multiple_local",
            min_required_resolution=90,
            available_downloads=[30, 90],
            local_cache={
                10: Path("data/test_10m.tif"),
                30: Path("data/test_30m.tif"),
                90: Path("data/test_90m.tif")
            },
            accept_lower_quality=False,
            latitude_range=(40.0, 41.0)
        )
        
        assert decision.action == "USE_LOCAL"
        assert decision.resolution == 10  # Finest available
        assert decision.file_path == Path("data/test_10m.tif")


# Summary function to generate test matrix report
def generate_test_matrix_report():
    """
    Generate a markdown table showing all test scenarios.
    Useful for documentation and verification.
    """
    print("\n" + "="*100)
    print("DATA SOURCE RESOLUTION TEST MATRIX")
    print("="*100 + "\n")
    
    print("| # | Test Case | Visible | Req | Location | Cache | Flag | Expected Action | Resolution |")
    print("|---|-----------|---------|-----|----------|-------|------|----------------|------------|")
    
    test_cases = [
        (1, "US tiny", "10m", "10m", "US", "none", "no", "ERROR_NEED_MANUAL", "10m"),
        (2, "US tiny", "10m", "10m", "US", "30m", "no", "ERROR_NEED_MANUAL", "10m"),
        (3, "US tiny", "10m", "10m", "US", "10m", "no", "USE_LOCAL", "10m"),
        (4, "US small", "50m", "30m", "US", "none", "no", "DOWNLOAD", "30m"),
        (5, "US small", "50m", "30m", "US", "10m", "no", "USE_LOCAL", "10m"),
        (6, "US small", "50m", "30m", "US", "90m", "no", "DOWNLOAD", "30m"),
        (7, "US large", "505m", "90m", "US", "none", "no", "DOWNLOAD", "90m"),
        (8, "US large", "505m", "90m", "US", "30m", "no", "USE_LOCAL", "30m"),
        (9, "Intl tiny", "15m", "10m", "Int'l", "none", "no", "ERROR_INSUFFICIENT", "10m"),
        (10, "Intl small", "70m", "30m", "Int'l", "none", "no", "DOWNLOAD", "30m"),
        (11, "Intl small", "70m", "30m", "Int'l", "30m", "no", "USE_LOCAL", "30m"),
        (12, "Intl small", "70m", "30m", "Int'l", "10m", "no", "USE_LOCAL", "10m"),
        (13, "Intl large", "600m", "90m", "Int'l", "none", "no", "DOWNLOAD", "90m"),
        (14, "Intl large", "600m", "90m", "Int'l", "30m", "no", "USE_LOCAL", "30m"),
        (15, "US tiny", "10m", "10m", "US", "none", "yes", "DOWNLOAD", "30m"),
        (16, "Intl tiny", "15m", "10m", "Int'l", "none", "yes", "DOWNLOAD", "30m"),
        (17, "Native 30m", "28m", "30m", "Int'l", "none", "no", "DOWNLOAD", "30m"),
        (18, "Native 90m", "92m", "90m", "Int'l", "none", "no", "DOWNLOAD", "90m"),
        (19, "High-lat", "200m", "90m", "Iceland", "none", "no", "DOWNLOAD", "90m (COP)"),
        (20, "Multi-cache", "200m", "90m", "US", "10,30,90", "no", "USE_LOCAL", "10m"),
    ]
    
    for row in test_cases:
        print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {row[7]} | {row[8]} |")
    
    print("\n" + "="*100)
    print(f"Total test cases: {len(test_cases)}")
    print("="*100 + "\n")


if __name__ == "__main__":
    # Generate test matrix report when run directly
    generate_test_matrix_report()
    
    # Run tests
    print("Run tests with: pytest tests/test_data_source_resolution.py -v")

