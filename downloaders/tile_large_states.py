"""
Download large US states in tiles to avoid OpenTopography size limits.
OpenTopography rejects requests larger than ~4° in any direction.
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
from src.pipeline import run_pipeline

# States that need tiling (dimension > 4° in any direction)
LARGE_STATES = {
    "california": {"tiles": (3, 3)},   # 10.35° × 9.48° → 3×3 tiles
    "texas": {"tiles": (4, 3)},        # 13.14° × 10.66° → 4×3 tiles
    "alaska": {"tiles": (10, 6)},      # 40° × 20.5° → 10×6 tiles (huge!)
    "montana": {"tiles": (4, 2)},      # 12.01° × 4.64° → 4×2 tiles
    "new_mexico": {"tiles": (2, 2)},   # 6.05° × 5.67° → 2×2 tiles
    "nevada": {"tiles": (2, 2)},       # 5.97° × 7° → 2×2 tiles
    "arizona": {"tiles": (2, 2)},      # 5.77° × 5.67° → 2×2 tiles
    "oregon": {"tiles": (3, 2)},       # 8.11° × 4.3° → 3×2 tiles
    "utah": {"tiles": (2, 2)},         # 5.01° × 5° → 2×2 tiles
    "idaho": {"tiles": (2, 2)},        # 6.2° × 7.01° → 2×2 tiles
    "wyoming": {"tiles": (2, 2)},      # 7.01° × 4.02° → 2×2 tiles
}


def calculate_tiles(bounds: Tuple[float, float, float, float], 
                    tile_size: float = 3.5) -> List[Tuple[float, float, float, float]]:
    """
    Split a large bounding box into smaller tiles.
    
    Args:
        bounds: (west, south, east, north) in degrees
        tile_size: Maximum tile dimension in degrees (default 3.5° for safety)
        
    Returns:
        List of tile bounding boxes
    """
    west, south, east, north = bounds
    width = east - west
    height = north - south
    
    # Calculate number of tiles needed
    cols = math.ceil(width / tile_size)
    rows = math.ceil(height / tile_size)
    
    # Actual tile size (divide evenly)
    tile_width = width / cols
    tile_height = height / rows
    
    tiles = []
    for row in range(rows):
        for col in range(cols):
            tile_west = west + col * tile_width
            tile_south = south + row * tile_height
            tile_east = min(west + (col + 1) * tile_width, east)
            tile_north = min(south + (row + 1) * tile_height, north)
            
            tiles.append((tile_west, tile_south, tile_east, tile_north))
    
    return tiles


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
    bounds = state_info['bounds']
    state_name = state_info['name']
    
    print(f"\n{'='*70}")
    print(f"Downloading {state_name} in Tiles")
    print(f"{'='*70}")
    print(f"Full bounds: {bounds}")
    print(f"Size: {bounds[2]-bounds[0]:.2f}° × {bounds[3]-bounds[1]:.2f}°")
    
    # Calculate tiles
    num_cols, num_rows = tiles_config['tiles']
    tile_width = (bounds[2] - bounds[0]) / num_cols
    tile_height = (bounds[3] - bounds[1]) / num_rows
    
    print(f"Tiles: {num_cols}×{num_rows} grid")
    print(f"Tile size: ~{tile_width:.2f}° × {tile_height:.2f}°")
    print(f"Total tiles: {num_cols * num_rows}")
    print(f"{'='*70}\n")
    
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
    
    for idx, tile_bounds in enumerate(tiles):
        tile_num = idx + 1
        print(f"\n[Tile {tile_num}/{len(tiles)}] Bounds: {tile_bounds}")
        
        tile_path = output_dir / f"{region_id}_tile_{idx:02d}.tif"
        
        if tile_path.exists():
            print(f"   ✅ Already downloaded: {tile_path.name}")
            tile_paths.append(tile_path)
            continue
        
        success = download_opentopography_srtm(
            region_id=f"{region_id}_tile_{idx:02d}",
            bounds=tile_bounds,
            output_path=tile_path,
            api_key=api_key
        )
        
        if success:
            tile_paths.append(tile_path)
        else:
            print(f"   ❌ Failed to download tile {tile_num}")
            return []
    
    print(f"\n{'='*70}")
    print(f"✅ All {len(tile_paths)} tiles downloaded successfully!")
    print(f"{'='*70}\n")
    
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
    if output_path.exists():
        print(f"   ✅ Already merged: {output_path.name}")
        return True
    
    print(f"   🔗 Merging {len(tile_paths)} tiles...")
    
    try:
        # Open all tiles
        src_files = [rasterio.open(p) for p in tile_paths]
        
        # Merge tiles
        print(f"      Combining rasters...")
        mosaic, out_transform = merge(src_files)
        
        # Get metadata from first tile
        out_meta = src_files[0].meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_transform
        })
        
        # Write merged file
        print(f"      Writing merged file...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(mosaic)
        
        # Close all source files
        for src in src_files:
            src.close()
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"   ✅ Merged: {output_path.name} ({file_size_mb:.1f} MB)")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Merge failed: {e}")
        if output_path.exists():
            output_path.unlink()
        return False


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
    if region_id not in US_STATES:
        print(f"❌ Unknown state: {region_id}")
        print(f"Available: {', '.join(US_STATES.keys())}")
        return 1
    
    if region_id not in LARGE_STATES:
        print(f"ℹ️  {region_id} is not configured for tiling.")
        print(f"   Use regular download: python downloaders/usa_3dep.py {region_id} --auto")
        return 1
    
    state_info = US_STATES[region_id]
    tiles_config = LARGE_STATES[region_id]
    
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
        print(f"❌ Failed to download tiles")
        return 1
    
    # Merge tiles
    merged_path = Path(f"data/raw/srtm_30m/{region_id}_bbox_30m.tif")
    
    print(f"\n{'='*70}")
    print(f"Merging Tiles")
    print(f"{'='*70}\n")
    
    if not merge_tiles(tile_paths, merged_path):
        return 1
    
    # Run normal pipeline with state boundary
    print(f"\n{'='*70}")
    print(f"Processing with State Boundaries")
    print(f"{'='*70}\n")
    
    state_name = state_info['name']
    boundary_name = f"United States of America/{state_name}"
    
    pipeline_success, result_paths = run_pipeline(
        raw_tif_path=merged_path,
        region_id=region_id,
        source='srtm_30m',
        boundary_name=boundary_name,
        boundary_type='state',
        target_pixels=target_pixels,
        skip_clip=False
    )
    
    if not pipeline_success:
        print(f"\n⚠️  Pipeline had issues")
        return 1
    
    print(f"\n{'='*70}")
    print(f"✅ {state_name} Complete!")
    print(f"{'='*70}")
    print(f"\nReady to view:")
    print(f"  python serve_viewer.py")
    print(f"  http://localhost:8001/interactive_viewer_advanced.html")
    print(f"  Select '{region_id}' from dropdown")
    print(f"{'='*70}\n")
    
    return 0


def main():
    import argparse
    from load_settings import get_opentopography_api_key
    
    parser = argparse.ArgumentParser(
        description='Download large US states using tiling',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Large states configured for tiling:
{chr(10).join(f"  - {k}: {v['tiles'][0]}×{v['tiles'][1]} tiles" for k, v in LARGE_STATES.items())}

Examples:
  # Download California in 3×3 tiles
  python downloaders/tile_large_states.py california
  
  # Download Texas in 4×3 tiles
  python downloaders/tile_large_states.py texas
  
  # Download with custom resolution
  python downloaders/tile_large_states.py california --target-pixels 1200
        """
    )
    
    parser.add_argument(
        'state',
        help='State to download (must be in LARGE_STATES list)'
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
    
    # Get API key
    api_key = args.api_key
    if not api_key:
        try:
            api_key = get_opentopography_api_key()
        except SystemExit:
            print("❌ OpenTopography API key required")
            print("   Add to settings.json or pass --api-key")
            return 1
    
    return download_large_state(
        args.state.lower(),
        api_key=api_key,
        target_pixels=args.target_pixels
    )


if __name__ == "__main__":
    sys.exit(main())

