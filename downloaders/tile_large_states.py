"""
Download large US states in tiles to avoid OpenTopography size limits.
OpenTopography rejects requests larger than ~4deg in any direction.
"""
import sys
from pathlib import Path
from typing import Tuple, List
import math

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import rasterio
    from rasterio.merge import merge
    import numpy as np
except ImportError as e:
    print(f"Missing package: {e}")
    print("Install with: pip install rasterio")
    sys.exit(1)

from downloaders.usa_3dep import US_STATES, download_opentopography_srtm
from src.regions_config import get_region
from src.pipeline import run_pipeline


def calculate_1degree_tiles(bounds: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
    """
    Calculate list of 1-degree tiles needed to cover bounds.
    
    Unified 1-degree grid system - all downloads become 1-degree tiles.
    
    Args:
        bounds: (west, south, east, north) in degrees
    
    Returns:
        List of 1-degree tile bounds (west, south, east, north) for each tile
    
        Example:
        Input:  (-112.0, 40.0, -110.0, 42.0)  # 2deg x 2deg region
        Output: [
            (-112.0, 40.0, -111.0, 41.0),  # N40_W112_30m.tif
            (-111.0, 40.0, -110.0, 41.0),  # N40_W111_30m.tif
            (-112.0, 41.0, -111.0, 42.0),  # N41_W112_30m.tif
            (-111.0, 41.0, -110.0, 42.0),  # N41_W111_30m.tif
        ]
    """
    west, south, east, north = bounds
    
    # Snap bounds to 1-degree grid
    snapped_west = math.floor(west / 1.0) * 1.0
    snapped_south = math.floor(south / 1.0) * 1.0
    snapped_east = math.ceil(east / 1.0) * 1.0
    snapped_north = math.ceil(north / 1.0) * 1.0
    
    tiles = []
    for lat in range(int(snapped_south), int(snapped_north)):
        for lon in range(int(snapped_west), int(snapped_east)):
            tile_bounds = (lon, lat, lon + 1.0, lat + 1.0)
            tiles.append(tile_bounds)
    
    return tiles


def calculate_tiles(bounds: Tuple[float, float, float, float], 
                    tile_size: float = 1.0) -> List[Tuple[float, float, float, float]]:
    """
    Calculate list of 1-degree tiles needed to cover bounds.
    
    Unified 1-degree grid system - all downloads become 1-degree tiles.
    
    Args:
        bounds: (west, south, east, north) in degrees
        tile_size: Tile dimension in degrees (must be 1.0 for unified system)
        
    Returns:
        List of 1-degree tile bounding boxes
    """
    # Unified system always uses 1-degree tiles
    if tile_size != 1.0:
        raise ValueError(f"Unified 1-degree grid system requires tile_size=1.0, got {tile_size}")
    
    return calculate_1degree_tiles(bounds)


def snap_tile_bounds_to_grid(bounds: Tuple[float, float, float, float], 
                             grid_size: float = 1.0) -> Tuple[float, float, float, float]:
    """
    Snap tile bounding box to standard grid boundaries to enable reuse across regions.
    
    Expands bounds outward to nearest grid boundaries (west/south floor down, east/north ceil up).
    This ensures tiles with similar bounds share the same grid-aligned tile files,
    reducing redundant downloads and making coverage management easier.
    
    Args:
        bounds: (west, south, east, north) in degrees
        grid_size: Grid increment in degrees (default 1.0 = integer-degree grid for tiles)
                   Tiles use 1.0-degree grid (coarser than bbox 0.5-degree grid)
        
    Returns:
        Tuple of (west, south, east, north) snapped to grid boundaries
    """
    west, south, east, north = bounds
    
    # Snap west/south down (floor), east/north up (ceil) to integer degrees
    # For negative values: floor goes more negative, ceil goes less negative
    snapped_west = math.floor(west / grid_size) * grid_size
    snapped_south = math.floor(south / grid_size) * grid_size
    snapped_east = math.ceil(east / grid_size) * grid_size
    snapped_north = math.ceil(north / grid_size) * grid_size
    
    return (snapped_west, snapped_south, snapped_east, snapped_north)


def tile_filename_from_bounds(bounds: Tuple[float, float, float, float], 
                              dataset: str = 'srtm_30m', 
                              resolution: str = '30m',
                              use_grid_alignment: bool = True,
                              grid_size: float = 1.0) -> str:
    """
    Generate a content-based filename for a 1-degree tile based on its bounds and resolution.
    
    Uses unified 1-degree grid system - all tiles use 1-degree grid for maximum reuse.
    Simple naming format: {NS}{lat}_{EW}{lon}_{resolution}.tif
    
    Examples:
        N35_W090_30m.tif  (SW corner at 35degN, 90degW, 1deg x 1deg tile)
        S05_E120_30m.tif  (SW corner at 5degS, 120degE, 1deg x 1deg tile)
    
    Args:
        bounds: (west, south, east, north) in degrees
        dataset: Dataset identifier (e.g., 'srtm_30m', 'srtm_90m', 'cop30', 'usa_3dep')
        resolution: Resolution identifier (e.g., '30m', '90m', '10m')
        use_grid_alignment: If True, snap bounds to grid before generating filename (default True)
        grid_size: Grid increment in degrees for snapping (default 1.0 = unified 1-degree grid)
        
    Returns:
        Filename string for 1-degree tile
    """
    west, south, east, north = bounds
    
    # Snap bounds to grid for filename (enables reuse)
    if use_grid_alignment:
        west, south, east, north = snap_tile_bounds_to_grid(bounds, grid_size)
    
    # Southwest corner coordinates (integer degrees)
    sw_lat = int(south)
    sw_lon = int(west)
    
    # Format latitude (N/S + integer, no padding)
    if sw_lat >= 0:
        lat_str = f"N{sw_lat}"
    else:
        lat_str = f"S{abs(sw_lat)}"
    
    # Format longitude (E/W + 3 digits)
    if sw_lon >= 0:
        lon_str = f"E{sw_lon:03d}"
    else:
        lon_str = f"W{abs(sw_lon):03d}"
    
    # Simple format: {NS}{lat}_{EW}{lon}_{resolution}.tif
    return f"{lat_str}_{lon_str}_{resolution}.tif"


def download_state_tiles(region_id: str, 
                         state_info: dict,
                         tiles_config: dict,
                         output_dir: Path,
                         api_key: str = None) -> List[Path]:
    """
    Download a state in multiple tiles.
    
    Args:
        region_id: State identifier (e.g., 'california')
        state_info: State info from US_STATES
        tiles_config: Tiling configuration
        output_dir: Directory to save tiles
        api_key: OpenTopography API key
        
    Returns:
        List of downloaded tile paths
    """
    import time
    start_time = time.time()
    
    bounds = state_info['bounds']
    state_name = state_info['name']
    
    print(f"\n{'='*70}", flush=True)
    print(f"STEP 1: DOWNLOADING {state_name.upper()} IN TILES", flush=True)
    print(f"{'='*70}", flush=True)
    print(f"Full bounds: {bounds}", flush=True)
    print(f"Size: {bounds[2]-bounds[0]:.2f}deg x {bounds[3]-bounds[1]:.2f}deg", flush=True)
    
    # Calculate tiles
    num_cols, num_rows = tiles_config['tiles']
    tile_width = (bounds[2] - bounds[0]) / num_cols
    tile_height = (bounds[3] - bounds[1]) / num_rows
    
    print(f"\nTiling configuration:", flush=True)
    print(f"  Grid: {num_cols}x{num_rows}", flush=True)
    print(f"  Tile size: ~{tile_width:.2f}deg x {tile_height:.2f}deg each", flush=True)
    print(f"  Total tiles: {num_cols * num_rows}", flush=True)
    print(f"  Output dir: {output_dir}", flush=True)
    print(f"{'='*70}\n", flush=True)
    
    tiles = []
    tile_paths = []
    
    for row in range(num_rows):
        for col in range(num_cols):
            tile_west = bounds[0] + col * tile_width
            tile_south = bounds[1] + row * tile_height
            tile_east = bounds[0] + (col + 1) * tile_width
            tile_north = bounds[1] + (row + 1) * tile_height
            
            tiles.append((tile_west, tile_south, tile_east, tile_north))
    
    # Download each tile
    output_dir.mkdir(parents=True, exist_ok=True)
    
    tiles_downloaded = 0
    tiles_cached = 0
    
    for idx, tile_bounds in enumerate(tiles):
        tile_num = idx + 1
        row = idx // num_cols
        col = idx % num_cols
        
        print(f"\n{'='*70}", flush=True)
        print(f"TILE {tile_num}/{len(tiles)} (Row {row+1}/{num_rows}, Col {col+1}/{num_cols})", flush=True)
        print(f"{'='*70}", flush=True)
        print(f"Bounds: [{tile_bounds[0]:.4f}, {tile_bounds[1]:.4f}, {tile_bounds[2]:.4f}, {tile_bounds[3]:.4f}]", flush=True)
        
        tile_path = output_dir / f"{region_id}_tile_{idx:02d}.tif"
        
        # Check if tile exists and is valid
        if tile_path.exists():
            file_size_mb = tile_path.stat().st_size / (1024 * 1024)
            
            # Validate the file is a proper GeoTIFF
            is_valid = False
            if file_size_mb > 0.1:  # Must be at least 100 KB
                try:
                    with rasterio.open(tile_path) as test_src:
                        # Try to read a small portion to verify it's valid
                        _ = test_src.read(1, window=((0, 1), (0, 1)))
                        is_valid = True
                except Exception as e:
                    print(f"STATUS: Cached file is corrupted ({e})", flush=True)
                    print(f"        Deleting and re-downloading...", flush=True)
                    tile_path.unlink()
            else:
                print(f"STATUS: Cached file is too small ({file_size_mb:.1f} MB)", flush=True)
                print(f"        Deleting and re-downloading...", flush=True)
                tile_path.unlink()
            
            if is_valid:
                print(f"STATUS: Already cached ({file_size_mb:.1f} MB)", flush=True)
                print(f"File: {tile_path}", flush=True)
                tile_paths.append(tile_path)
                tiles_cached += 1
                continue
        
        print(f"STATUS: Downloading from OpenTopography...", flush=True)
        tile_start = time.time()
        
        success = download_opentopography_srtm(
            region_id=f"{region_id}_tile_{idx:02d}",
            bounds=tile_bounds,
            output_path=tile_path,
            api_key=api_key
        )
        
        if success:
            # Validate the downloaded file
            file_size_mb = tile_path.stat().st_size / (1024 * 1024)
            is_valid = False
            
            if file_size_mb < 0.1:
                print(f"  Tile {tile_num} is suspiciously small ({file_size_mb:.1f} MB)", flush=True)
                print(f"    This tile may be outside data coverage area", flush=True)
                print(f"    Keeping it anyway (will handle in merge)", flush=True)
                is_valid = True  # Keep small tiles, they might be valid but sparse
            else:
                try:
                    with rasterio.open(tile_path) as test_src:
                        _ = test_src.read(1, window=((0, 1), (0, 1)))
                        is_valid = True
                except Exception as e:
                    print(f"X Tile {tile_num} FAILED validation: {e}", flush=True)
                    tile_path.unlink()
            
            if is_valid:
                tile_paths.append(tile_path)
                tiles_downloaded += 1
                tile_time = time.time() - tile_start
                print(f"OK Tile {tile_num} complete in {tile_time:.1f}s", flush=True)
            else:
                print(f"  Tile {tile_num} validation failed, skipping", flush=True)
        else:
            print(f"  Tile {tile_num} has no data (likely water/outside coverage), skipping", flush=True)
    
    total_time = time.time() - start_time
    
    print(f"\n{'='*70}", flush=True)
    print(f"TILE DOWNLOAD SUMMARY", flush=True)
    print(f"{'='*70}", flush=True)
    print(f"Total tiles attempted: {len(tiles)}", flush=True)
    print(f"Valid tiles obtained: {len(tile_paths)}", flush=True)
    print(f"Downloaded: {tiles_downloaded}", flush=True)
    print(f"Cached: {tiles_cached}", flush=True)
    print(f"Skipped (no data): {len(tiles) - len(tile_paths)}", flush=True)
    print(f"Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)", flush=True)
    print(f"{'='*70}\n", flush=True)
    
    if not tile_paths:
        print(f" ERROR: No valid tiles obtained!", flush=True)
        print(f"   All tiles either failed or have no data coverage", flush=True)
        return []
    
    if len(tile_paths) < len(tiles) / 2:
        print(f"  WARNING: Only {len(tile_paths)}/{len(tiles)} tiles have data", flush=True)
        print(f"   This is expected for coastal states (water areas have no elevation data)", flush=True)
    
    return tile_paths


def merge_tiles(tile_paths: List[Path], output_path: Path) -> bool:
    """
    Merge downloaded tiles into a single GeoTIFF.
    
    Args:
        tile_paths: List of tile file paths
        output_path: Output merged file path
        
    Returns:
        True if successful
    """
    import time
    
    print(f"\n{'='*70}", flush=True)
    print(f"STEP 2: MERGING TILES INTO SINGLE FILE", flush=True)
    print(f"{'='*70}", flush=True)
    
    if output_path.exists():
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"STATUS: Already merged", flush=True)
        print(f"File: {output_path}", flush=True)
        print(f"Size: {file_size_mb:.1f} MB", flush=True)
        print(f"{'='*70}\n", flush=True)
        return True
    
    print(f"Input tiles: {len(tile_paths)}", flush=True)
    print(f"Output: {output_path}", flush=True)
    print(f"\nStarting merge process...", flush=True)
    
    merge_start = time.time()
    
    src_files = []
    try:
        # Open all tiles and validate them
        print(f"  [1/4] Opening {len(tile_paths)} tile files...", flush=True)
        for p in tile_paths:
            try:
                src = rasterio.open(p)
                if src.width > 0 and src.height > 0:
                    # Emit detailed diagnostics per tile to aid debugging
                    try:
                        b = src.bounds
                        try:
                            size_mb = (p.stat().st_size) / (1024 * 1024)
                        except Exception:
                            size_mb = None
                        print(
                            f"        Opened {p.name}: {src.width}x{src.height} px, "
                            f"dtype={src.dtypes[0]}, nodata={src.nodata}, crs={src.crs}"
                            + (f", size={size_mb:.1f} MB" if size_mb is not None else ""),
                            flush=True
                        )
                        print(
                            f"          Bounds: left={b.left:.6f}, bottom={b.bottom:.6f}, right={b.right:.6f}, top={b.top:.6f}",
                            flush=True
                        )
                        # Try a tiny central read to surface read errors early
                        try:
                            from rasterio.windows import Window
                            h = max(1, min(128, src.height // 8))
                            w = max(1, min(128, src.width // 8))
                            row_off = max(0, (src.height - h) // 2)
                            col_off = max(0, (src.width - w) // 2)
                            _sample = src.read(1, window=Window(col_off, row_off, w, h))
                            print(
                                f"          Sample read OK: window={w}x{h} at ({col_off},{row_off})",
                                flush=True
                            )
                        except Exception as se:
                            print(f"          Warning: Sample read failed: {se}", flush=True)
                    except Exception:
                        pass
                    src_files.append(src)
                else:
                    print(f"        Warning: Skipping empty tile: {p.name}", flush=True)
                    src.close()
            except Exception as e:
                print(f"        Warning: Cannot open tile {p.name}: {e}", flush=True)
                print(f"        Skipping this tile...", flush=True)

        if not src_files:
            print(f"\n  ERROR: No valid tiles to merge!", flush=True)
            return False

        # Calculate combined dimensions
        total_pixels = sum(src.width * src.height for src in src_files)
        print(f"  [2/4] Total pixels across all tiles: {total_pixels:,}", flush=True)

        # Determine a safe output dtype and nodata
        # Prefer float32 to avoid int/float mismatches and to preserve nodata masks
        out_dtype = 'float32'
        # Choose nodata: use first valid src.nodata; otherwise sensible default
        nodata_values = [s.nodata for s in src_files if s.nodata is not None]
        if len(nodata_values) > 0:
            out_nodata = nodata_values[0]
        else:
            # Default nodata for float32
            out_nodata = -9999.0

        # Merge tiles (let rasterio handle reprojection if any tiny differences)
        print(f"  [3/4] Combining rasters into mosaic...", flush=True)
        mosaic, out_transform = merge(
            src_files,
            nodata=out_nodata,
            dtype=out_dtype,
            method='first'  # deterministic and fast for DEMs
        )

        # If masked array, fill with nodata
        try:
            import numpy as _np
            if _np.ma.isMaskedArray(mosaic):
                mosaic = mosaic.filled(out_nodata)
        except Exception:
            pass

        print(f"        Merged dimensions: {mosaic.shape[2]} x {mosaic.shape[1]} pixels", flush=True)

        # Get metadata from first tile and normalize
        out_meta = src_files[0].meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_transform,
            "dtype": out_dtype,
            "count": mosaic.shape[0],
            "nodata": out_nodata
        })

        # Write merged file
        print(f"  [4/4] Writing merged file to disk...", flush=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(mosaic)

        merge_time = time.time() - merge_start
        file_size_mb = output_path.stat().st_size / (1024 * 1024)

        print(f"\nMerge complete!", flush=True)
        print(f"  Output: {output_path.name}", flush=True)
        print(f"  Size: {file_size_mb:.1f} MB", flush=True)
        print(f"  Time: {merge_time:.1f}s", flush=True)
        print(f"{'='*70}\n", flush=True)

        return True

    except Exception as e:
        print(f"\nMerge FAILED: {e}")
        # Provide traceback for deeper insight
        try:
            import traceback as _tb
            print(_tb.format_exc())
        except Exception:
            pass
        if output_path.exists():
            try:
                output_path.unlink()
            except Exception:
                pass
        return False
    finally:
        # Ensure all datasets are closed even if an error occurs
        for _src in src_files:
            try:
                _src.close()
            except Exception:
                pass


def download_large_state(region_id: str, api_key: str = None, target_pixels: int = 800):
    """
    Download a large state using tiling, then process normally.
    
    Args:
        region_id: State identifier
        api_key: OpenTopography API key
        target_pixels: Target resolution for viewer
        
    Returns:
        0 if successful, 1 otherwise
    """
    import time
    
    print(f"\n{'#'*70}")
    print(f"# LARGE STATE DOWNLOAD WITH TILING")
    print(f"{'#'*70}")
    print(f"Starting download for: {region_id}")
    print(f"API key loaded: {'Yes' if api_key else 'No'}")
    print(f"{'#'*70}\n")
    
    overall_start = time.time()
    
    if region_id not in US_STATES:
        print(f"ERROR: Unknown state: {region_id}")
        print(f"Available: {', '.join(US_STATES.keys())}")
        return 1
    
    # Get tiling config from centralized config
    config = get_region(region_id)
    if not config or not config.tiles:
        print(f"INFO: {region_id} is not configured for tiling.")
        print(f"Use regular download: python downloaders/usa_3dep.py {region_id} --auto")
        return 1
    
    state_info = US_STATES[region_id]
    tiles_config = {"tiles": config.tiles}
    
    print(f"State: {state_info['name']}")
    print(f"Region ID: {region_id}")
    print(f"Tile configuration: {tiles_config['tiles'][0]}x{tiles_config['tiles'][1]} grid")
    print(f"Target resolution: {target_pixels}px")
    print(f"\n{'#'*70}\n")
    
    # Download tiles
    tiles_dir = Path(f"data/raw/srtm_30m/tiles/{region_id}")
    tile_paths = download_state_tiles(
        region_id, 
        state_info, 
        tiles_config,
        tiles_dir,
        api_key
    )
    
    if not tile_paths:
        print(f" Failed to download tiles")
        return 1
    
    # Merge tiles
    merged_path = Path(f"data/raw/srtm_30m/{region_id}_bbox_30m.tif")
    
    if not merge_tiles(tile_paths, merged_path):
        return 1
    
    # Run normal pipeline with state boundary
    state_name = state_info['name']
    boundary_name = f"United States of America/{state_name}"
    
    print(f"\n{'='*70}")
    print(f"STEP 3: PROCESSING WITH STATE BOUNDARIES")
    print(f"{'='*70}")
    print(f"State: {state_name}")
    print(f"Boundary: {boundary_name}")
    print(f"{'='*70}\n")
    
    pipeline_start = time.time()
    
    pipeline_success, result_paths = run_pipeline(
        raw_tif_path=merged_path,
        region_id=region_id,
        source='srtm_30m',
        boundary_name=boundary_name,
        boundary_type='state',
        target_pixels=target_pixels,
        skip_clip=False
    )
    
    pipeline_time = time.time() - pipeline_start
    
    if not pipeline_success:
        print(f"\nPipeline FAILED")
        return 1
    
    overall_time = time.time() - overall_start
    
    print(f"\n{'#'*70}")
    print(f"# COMPLETE: {state_name.upper()}")
    print(f"{'#'*70}")
    print(f"\nTotal time: {overall_time:.1f}s ({overall_time/60:.1f} minutes)")
    print(f"  Tile download: included above")
    print(f"  Merge: included above")
    print(f"  Pipeline: {pipeline_time:.1f}s")
    print(f"\nFiles created:")
    print(f"  Raw merged: {merged_path}")
    print(f"  Clipped: {result_paths.get('clipped', 'N/A')}")
    print(f"  Processed: {result_paths.get('processed', 'N/A')}")
    print(f"  Exported: {result_paths.get('exported', 'N/A')}")
    print(f"\nReady to view:")
    print(f"  python serve_viewer.py")
    print(f"  http://localhost:8001/interactive_viewer_advanced.html")
    print(f"  Select '{region_id}' from dropdown")
    print(f"{'#'*70}\n")
    
    return 0


def main():
    import argparse
    from load_settings import get_opentopography_api_key
    
    print("Initializing large state downloader...")
    
    parser = argparse.ArgumentParser(
        description='Download large US states using tiling',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
DEPRECATED: This script is now deprecated.
Use the main downloader instead: python downloaders/usa_3dep.py california --auto
(Tiling happens automatically for large states)

Tiling configuration comes from src/regions_config.py.
The tiles field defines the (columns, rows) grid for large regions.
        """
    )
    
    parser.add_argument(
        'state',
        help='State to download (tiling auto-detected from config)'
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        help='OpenTopography API key (optional, uses settings.json)'
    )
    
    parser.add_argument(
        '--target-pixels',
        type=int,
        default=800,
        help='Target resolution for viewer (default: 800)'
    )
    
    args = parser.parse_args()
    
    print(f"Attempting to load API key...")
    
    # Get API key (auto-load from settings.json)
    api_key = args.api_key
    if not api_key:
        try:
            api_key = get_opentopography_api_key()
            print(f"API key loaded from settings.json")
        except SystemExit:
            print("ERROR: OpenTopography API key required")
            print("  Add to settings.json or pass --api-key")
            print("  Get a free key at: https://portal.opentopography.org/")
            return 1
        except Exception as e:
            print(f"ERROR loading API key: {e}")
            return 1
    
    return download_large_state(
        args.state.lower(),
        api_key=api_key,
        target_pixels=args.target_pixels
    )


if __name__ == "__main__":
    sys.exit(main())

