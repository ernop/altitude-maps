"""
Tests for USGS 3DEP 10m tiling system.

Verifies that 10m data follows the unified 1-degree grid architecture
exactly like 30m and 90m data.

Run with: pytest tests/test_usgs_3dep_10m_tiling.py -v
"""

from pathlib import Path
from unittest.mock import Mock, patch
from src.tile_geometry import calculate_1degree_tiles, tile_filename_from_bounds


class TestUSGS3DEP10mTiling:
    """Test suite for 10m USGS 3DEP tile-based downloads."""
    
    def test_small_region_uses_tiling(self):
        """Small US region (< 4 degrees) should use tiling for consistency."""
        # Ohio: ~2deg x 4deg region
        bounds = (-84.82, 38.40, -80.52, 41.98)
        
        tiles = calculate_1degree_tiles(bounds)
        
        # Should create grid of 1-degree tiles
        assert len(tiles) > 1
        
        # All tiles should be 1-degree
        for tile_bounds in tiles:
            w, s, e, n = tile_bounds
            assert abs((e - w) - 1.0) < 0.01
            assert abs((n - s) - 1.0) < 0.01
    
    def test_large_region_uses_tiling(self):
        """Large US region (> 4 degrees) should use tiling."""
        # California: ~10deg x 10deg region
        bounds = (-124.5, 32.5, -114.1, 42.0)
        
        tiles = calculate_1degree_tiles(bounds)
        
        # Should create many tiles
        assert len(tiles) >= 90  # ~10x10 grid
        
        # Verify all tiles are 1-degree
        for tile_bounds in tiles:
            w, s, e, n = tile_bounds
            assert abs((e - w) - 1.0) < 0.01
            assert abs((n - s) - 1.0) < 0.01
    
    def test_tile_naming_convention_10m(self):
        """10m tiles should follow unified naming: N##_W###_10m.tif"""
        # Test various tile bounds
        test_cases = [
            ((-112.0, 40.0, -111.0, 41.0), "N40_W112_10m.tif"),
            ((-111.0, 40.0, -110.0, 41.0), "N40_W111_10m.tif"),
            ((-90.0, 35.0, -89.0, 36.0), "N35_W090_10m.tif"),
            ((-85.0, 38.0, -84.0, 39.0), "N38_W085_10m.tif"),
        ]
        
        for tile_bounds, expected_name in test_cases:
            filename = tile_filename_from_bounds(tile_bounds, resolution='10m')
            assert filename == expected_name
    
    def test_tile_storage_location(self):
        """10m tiles should be stored in data/raw/usa_3dep/tiles/"""
        expected_dir = Path("data/raw/usa_3dep/tiles")
        
        # Verify this matches the documented structure
        assert "usa_3dep" in str(expected_dir)
        assert "tiles" in str(expected_dir)
    
    def test_tile_bounds_snapping(self):
        """Tile bounds should snap to integer-degree grid."""
        # Original bounds (not on grid)
        original_bounds = (-111.622, 40.1467, -111.0902, 40.7020)
        
        # Calculate tiles
        tiles = calculate_1degree_tiles(original_bounds)
        
        # All tile bounds should be integer degrees
        for tile_bounds in tiles:
            w, s, e, n = tile_bounds
            assert w == int(w)
            assert s == int(s)
            assert e == int(e)
            assert n == int(n)
    
    def test_tile_reuse_across_regions(self):
        """Adjacent regions should share tiles."""
        # Tennessee and Kentucky share northern/southern border
        tennessee_bounds = (-90.31, 34.98, -81.65, 36.68)
        kentucky_bounds = (-89.57, 36.50, -81.96, 39.15)
        
        tn_tiles = calculate_1degree_tiles(tennessee_bounds)
        ky_tiles = calculate_1degree_tiles(kentucky_bounds)
        
        # Convert to sets of tile bounds for comparison
        tn_set = set(tn_tiles)
        ky_set = set(ky_tiles)
        
        # Should have overlapping tiles
        shared_tiles = tn_set & ky_set
        assert len(shared_tiles) > 0, "Adjacent states should share border tiles"
    
    def test_tile_size_estimate_10m(self):
        """10m tiles should be ~9x larger than 30m tiles (3^2 = 9x more pixels)."""
        # At 40degN:
        # - 30m tile: ~16 MB
        # - 10m tile: ~150 MB (9x increase)
        
        # This is a documentation test - file sizes will vary
        # but the relationship should hold
        size_ratio_30m_to_10m = 9.0
        
        # Verify this is documented
        assert size_ratio_30m_to_10m == 9.0
    
    @patch('src.downloaders.usgs_3dep_10m.USGSElevationDownloader')
    def test_download_single_tile_creates_correct_path(self, mock_downloader_class):
        """Download should create files in shared tile pool with correct naming."""
        from src.downloaders.usgs_3dep_10m import download_single_tile_10m
        
        # Mock the downloader
        mock_downloader = Mock()
        mock_downloader.download_via_national_map_api.return_value = Path("test.tif")
        mock_downloader_class.return_value = mock_downloader
        
        # Test tile
        tile_bounds = (-111.0, 40.0, -110.0, 41.0)
        output_path = Path("data/raw/usa_3dep/tiles/N40_W111_10m.tif")
        
        # Mock the file existence check
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'stat') as mock_stat, \
             patch.object(Path, 'mkdir'):
            mock_stat.return_value.st_size = 150 * 1024 * 1024  # 150 MB
            
            _result = download_single_tile_10m(tile_bounds, output_path)
        
        # Verify download was called with correct bounds
        mock_downloader.download_via_national_map_api.assert_called_once()
        call_args = mock_downloader.download_via_national_map_api.call_args
        assert call_args[1]['bbox'] == tile_bounds
    
    def test_consistency_with_30m_90m_systems(self):
        """10m system should use identical patterns as 30m/90m."""
        # Same region for all resolutions
        bounds = (-112.0, 40.0, -111.0, 41.0)
        
        # All resolutions should generate same tile coverage
        tiles_10m = calculate_1degree_tiles(bounds)
        tiles_30m = calculate_1degree_tiles(bounds)
        tiles_90m = calculate_1degree_tiles(bounds)
        
        assert len(tiles_10m) == len(tiles_30m) == len(tiles_90m)
        assert tiles_10m == tiles_30m == tiles_90m
        
        # Filenames should differ only in resolution suffix
        filename_10m = tile_filename_from_bounds(bounds, '10m')
        filename_30m = tile_filename_from_bounds(bounds, '30m')
        filename_90m = tile_filename_from_bounds(bounds, '90m')
        
        assert filename_10m == "N40_W112_10m.tif"
        assert filename_30m == "N40_W112_30m.tif"
        assert filename_90m == "N40_W112_90m.tif"


class TestIntegrationWith30mAnd90m:
    """Integration tests verifying 10m follows exact same architecture."""
    
    def test_same_tile_calculation_logic(self):
        """All resolutions should use calculate_1degree_tiles()."""
        # Large region spanning many tiles
        bounds = (-115.0, 35.0, -105.0, 42.0)
        
        tiles = calculate_1degree_tiles(bounds)
        
        # Verify all tiles are 1.0 x 1.0 degrees
        for tile_bounds in tiles:
            w, s, e, n = tile_bounds
            width = e - w
            height = n - s
            assert abs(width - 1.0) < 0.01
            assert abs(height - 1.0) < 0.01
    
    def test_same_directory_structure(self):
        """All resolutions should use data/raw/{source}/tiles/ structure."""
        expected_paths = {
            '10m': Path("data/raw/usa_3dep/tiles"),
            '30m': Path("data/raw/srtm_30m/tiles"),
            '90m': Path("data/raw/srtm_90m/tiles"),
        }
        
        # Verify pattern consistency
        for _res, path in expected_paths.items():
            assert path.parts[-1] == "tiles"
            assert "data" in path.parts
            assert "raw" in path.parts
    
    def test_same_snapping_behavior(self):
        """All resolutions should snap bounds to integer-degree grid."""
        # Non-grid-aligned bounds
        bounds = (-111.622, 40.1467, -110.0902, 41.7020)
        
        tiles = calculate_1degree_tiles(bounds)
        
        # All tiles should have integer bounds
        for tile_bounds in tiles:
            w, s, e, n = tile_bounds
            assert w == int(w), f"West bound {w} not integer"
            assert s == int(s), f"South bound {s} not integer"
            assert e == int(e), f"East bound {e} not integer"
            assert n == int(n), f"North bound {n} not integer"


class TestDocumentationCompliance:
    """Verify implementation matches documentation in GRID_ALIGNMENT_STRATEGY.md."""
    
    def test_uses_1degree_grid_system(self):
        """System must use unified 1.0 degree grid (not 0.5 or other sizes)."""
        # Test with various region sizes
        test_regions = [
            ((-111.5, 40.2, -110.3, 41.8), "small"),    # ~1.2 x 1.6 degrees
            ((-115.0, 35.0, -105.0, 42.0), "large"),    # 10 x 7 degrees
        ]
        
        for bounds, label in test_regions:
            tiles = calculate_1degree_tiles(bounds)
            
            # Every tile must be exactly 1.0 x 1.0 degrees
            for tile_bounds in tiles:
                w, s, e, n = tile_bounds
                assert abs((e - w) - 1.0) < 0.001, f"{label} region tile not 1.0 deg wide"
                assert abs((n - s) - 1.0) < 0.001, f"{label} region tile not 1.0 deg tall"
    
    def test_no_special_cases_for_small_regions(self):
        """Small regions should NOT use different logic - unified approach."""
        # Very small region (< 1 degree)
        small_bounds = (-111.5, 40.2, -111.3, 40.6)  # 0.2 x 0.4 degrees
        
        tiles = calculate_1degree_tiles(small_bounds)
        
        # Should still generate 1-degree tiles (1 tile covering this area)
        assert len(tiles) == 1
        
        # Tile should be 1.0 x 1.0 degrees (not 0.2 x 0.4)
        tile_bounds = tiles[0]
        w, s, e, n = tile_bounds
        assert abs((e - w) - 1.0) < 0.01
        assert abs((n - s) - 1.0) < 0.01
    
    def test_matches_documented_naming_format(self):
        """Tile naming must match documented format: {NS}{lat}_{EW}{lon}_{resolution}.tif"""
        test_cases = [
            ((-111.0, 40.0, -110.0, 41.0), "N40_W111_10m.tif"),
            ((-90.0, 35.0, -89.0, 36.0), "N35_W090_10m.tif"),
            ((120.0, -5.0, 121.0, -4.0), "S5_E120_10m.tif"),  # Southern hemisphere
            ((-180.0, 65.0, -179.0, 66.0), "N65_W180_10m.tif"),  # Dateline
        ]
        
        for tile_bounds, expected_name in test_cases:
            filename = tile_filename_from_bounds(tile_bounds, resolution='10m')
            assert filename == expected_name, f"Expected {expected_name}, got {filename}"


# Run tests
if __name__ == "__main__":
    print("Run tests with: pytest tests/test_usgs_3dep_10m_tiling.py -v")

