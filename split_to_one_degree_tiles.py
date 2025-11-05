"""
Split existing large bbox/tile files into 1-degree tiles.

This script:
1. Finds all large bbox/tile files in data/raw/
2. Splits them into 1-degree tiles aligned to integer grid
3. Discards edge pieces that are too small (< 0.5 degrees)
4. Saves tiles to shared tile pool with standard naming
5. Skips tiles that already exist
"""

import rasterio
from rasterio.windows import Window
from pathlib import Path
import math
import json
from typing import Tuple, List, Optional
from datetime import datetime

# Configuration
MIN_TILE_SIZE_DEG = 0.5  # Discard tiles smaller than 0.5 degrees
GRID_SIZE = 1.0  # 1-degree grid


def snap_to_grid(coord: float, grid_size: float, snap_down: bool = True) -> float:
    """Snap coordinate to grid boundary."""
    if snap_down:
        return math.floor(coord / grid_size) * grid_size
    else:
        return math.ceil(coord / grid_size) * grid_size


def tile_filename_from_bounds(bounds: Tuple[float, float, float, float], 
                              dataset: str = 'srtm_30m', 
                              resolution: str = '30m') -> str:
    """
    Generate standard 1-degree tile filename from southwest corner.
    
    Args:
        bounds: (west, south, east, north) in degrees
        dataset: Dataset name (e.g., 'srtm_30m', 'cop30')
        resolution: Resolution string (e.g., '30m', '90m')
    
    Returns:
        Filename like 'tile_N40_W111_srtm_30m_30m.tif'
    """
    west, south, east, north = bounds
    
    # Southwest corner should be integer degrees
    sw_lat = int(south)
    sw_lon = int(west)
    
    # Format with direction indicators (no padding for lat, 3-digit for lon)
    if sw_lat >= 0:
        lat_str = f"N{sw_lat}"
    else:
        lat_str = f"S{abs(sw_lat)}"
    
    if sw_lon >= 0:
        lon_str = f"E{sw_lon:03d}"
    else:
        lon_str = f"W{abs(sw_lon):03d}"
    
    # Simple format: {NS}{lat}_{EW}{lon}_{resolution}.tif
    return f"{lat_str}_{lon_str}_{resolution}.tif"


def calculate_1degree_tiles(bounds: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
    """
    Calculate list of 1-degree tiles needed to cover bounds.
    Only includes tiles that are at least MIN_TILE_SIZE_DEG in both dimensions.
    """
    west, south, east, north = bounds
    
    # Snap bounds to 1-degree grid
    snapped_west = snap_to_grid(west, GRID_SIZE, snap_down=True)
    snapped_south = snap_to_grid(south, GRID_SIZE, snap_down=True)
    snapped_east = snap_to_grid(east, GRID_SIZE, snap_down=False)
    snapped_north = snap_to_grid(north, GRID_SIZE, snap_down=False)
    
    tiles = []
    for lat in range(int(snapped_south), int(snapped_north)):
        for lon in range(int(snapped_west), int(snapped_east)):
            tile_west = lon
            tile_south = lat
            tile_east = lon + 1.0
            tile_north = lat + 1.0
            
            # Calculate actual tile bounds (clip to original bounds)
            actual_west = max(tile_west, west)
            actual_south = max(tile_south, south)
            actual_east = min(tile_east, east)
            actual_north = min(tile_north, north)
            
            # Check if tile is large enough (discard small edge pieces)
            width = actual_east - actual_west
            height = actual_north - actual_south
            
            if width >= MIN_TILE_SIZE_DEG and height >= MIN_TILE_SIZE_DEG:
                # For full 1-degree tiles, use integer bounds
                if width >= 0.99 and height >= 0.99:
                    tiles.append((tile_west, tile_south, tile_east, tile_north))
                else:
                    # Partial tile that's still large enough
                    tiles.append((actual_west, actual_south, actual_east, actual_north))
    
    return tiles


def extract_tile_from_geotiff(src_path: Path, tile_bounds: Tuple[float, float, float, float], 
                              dst_path: Path) -> bool:
    """
    Extract a tile from a GeoTIFF file.
    
    Args:
        src_path: Path to source GeoTIFF
        tile_bounds: (west, south, east, north) in degrees (EPSG:4326)
        dst_path: Path to save extracted tile
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with rasterio.open(src_path) as src:
            # Check if source is in EPSG:4326
            if src.crs != rasterio.crs.CRS.from_epsg(4326):
                print(f"  WARNING: Source CRS is {src.crs}, expected EPSG:4326")
                return False
            
            # Calculate pixel window for tile bounds
            west, south, east, north = tile_bounds
            
            # Get pixel coordinates
            row_min, col_min = rasterio.transform.rowcol(src.transform, west, north)
            row_max, col_max = rasterio.transform.rowcol(src.transform, east, south)
            
            # Ensure we're within bounds
            row_min = max(0, min(row_min, src.height - 1))
            row_max = max(0, min(row_max, src.height - 1))
            col_min = max(0, min(col_min, src.width - 1))
            col_max = max(0, min(col_max, src.width - 1))
            
            # Calculate window
            top = min(row_min, row_max)
            left = min(col_min, col_max)
            height = abs(row_max - row_min) + 1
            width = abs(col_max - col_min) + 1
            
            window = Window(left, top, width, height)
            
            # Read data
            data = src.read(window=window)
            
            # Calculate new transform for tile
            # Use integer bounds for full tiles, actual bounds for partial tiles
            tile_west, tile_south = int(west), int(south)
            tile_east, tile_north = tile_west + 1.0, tile_south + 1.0
            
            if abs(west - tile_west) < 0.01 and abs(east - tile_east) < 0.01 and \
               abs(south - tile_south) < 0.01 and abs(north - tile_north) < 0.01:
                # Full tile - use integer bounds
                bounds_for_transform = (tile_west, tile_south, tile_east, tile_north)
            else:
                # Partial tile - use actual bounds
                bounds_for_transform = (west, south, east, north)
            
            # Create transform for tile
            tile_transform = rasterio.transform.from_bounds(
                bounds_for_transform[0], bounds_for_transform[1],  # west, south
                bounds_for_transform[2], bounds_for_transform[3],  # east, north
                width, height
            )
            
            # Write tile
            with rasterio.open(
                dst_path,
                'w',
                driver='GTiff',
                height=height,
                width=width,
                count=src.count,
                dtype=src.dtypes[0],
                crs=src.crs,
                transform=tile_transform,
                compress='lzw',
                nodata=src.nodata
            ) as dst:
                dst.write(data)
            
            return True
            
    except Exception as e:
        print(f"  Error extracting tile: {e}")
        return False


def create_tile_metadata(tile_path: Path, tile_bounds: Tuple[float, float, float, float],
                        source_file: str, dataset: str, resolution: str) -> None:
    """
    Create JSON metadata file for tile.
    
    NOTE: JSON metadata files are not used for tile validation or reuse.
    Tiles are validated directly via rasterio when needed.
    This function is kept for compatibility but metadata creation is disabled.
    """
    # Metadata files not used - skip creation
    # If needed in future, uncomment below
    pass


def split_file(source_path: Path, tiles_dir: Path, dataset: str, resolution: str) -> int:
    """
    Split a large GeoTIFF file into 1-degree tiles.
    
    Args:
        source_path: Path to source GeoTIFF
        tiles_dir: Directory to save tiles
        dataset: Dataset name (e.g., 'srtm_30m')
        resolution: Resolution string (e.g., '30m')
    
    Returns:
        Number of tiles created
    """
    print(f"\nSplitting: {source_path.name}")
    
    # Get bounds from source file
    try:
        with rasterio.open(source_path) as src:
            if src.crs != rasterio.crs.CRS.from_epsg(4326):
                print(f"  ERROR: Source CRS is {src.crs}, expected EPSG:4326. Skipping.")
                return 0
            
            bounds = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
            width_deg = bounds[2] - bounds[0]
            height_deg = bounds[3] - bounds[1]
            
            print(f"  Bounds: [{bounds[0]:.4f}, {bounds[1]:.4f}, {bounds[2]:.4f}, {bounds[3]:.4f}]")
            print(f"  Size: {width_deg:.2f}deg x {height_deg:.2f}deg")
    except Exception as e:
        print(f"  ERROR: Could not read source file: {e}")
        return 0
    
    # Calculate tiles needed
    tiles = calculate_1degree_tiles(bounds)
    print(f"  Will create {len(tiles)} tiles (discarding edge pieces < {MIN_TILE_SIZE_DEG}deg)")
    
    # Create tiles directory if needed
    tiles_dir.mkdir(parents=True, exist_ok=True)
    
    created_count = 0
    skipped_count = 0
    
    for tile_bounds in tiles:
        # Generate tile filename
        tile_filename = tile_filename_from_bounds(tile_bounds, dataset, resolution)
        tile_path = tiles_dir / tile_filename
        
        # Skip if tile already exists
        if tile_path.exists():
            print(f"  Skipping (exists): {tile_filename}")
            skipped_count += 1
            continue
        
        # Extract tile
        print(f"  Creating: {tile_filename}")
        if extract_tile_from_geotiff(source_path, tile_bounds, tile_path):
            # Create metadata
            create_tile_metadata(tile_path, tile_bounds, str(source_path), dataset, resolution)
            created_count += 1
        else:
            print(f"  Failed to create: {tile_filename}")
    
    print(f"  Created: {created_count}, Skipped: {skipped_count}, Total: {len(tiles)}")
    return created_count


def determine_dataset_and_resolution(file_path: Path) -> Tuple[str, str]:
    """Determine dataset and resolution from file path or name."""
    name = file_path.name.lower()
    
    # Check for resolution in path
    if '90m' in name or 'srtm_90m' in str(file_path):
        return 'srtm_90m', '90m'
    elif '30m' in name or 'srtm_30m' in str(file_path):
        return 'srtm_30m', '30m'
    elif '10m' in name or '3dep' in name:
        return 'usa_3dep', '10m'
    elif 'cop30' in name or 'copernicus' in name:
        return 'cop30', '30m'
    elif 'cop90' in name:
        return 'cop90', '90m'
    else:
        # Default
        return 'srtm_30m', '30m'


def main():
    """Main function to split all large files."""
    print("=" * 70)
    print("SPLIT TO 1-DEGREE TILES")
    print("=" * 70)
    print()
    print(f"Grid size: {GRID_SIZE} degrees")
    print(f"Minimum tile size: {MIN_TILE_SIZE_DEG} degrees (edge pieces smaller than this are discarded)")
    print()
    
    # Find all bbox/tile files in data/raw/
    raw_dir = Path('data/raw')
    if not raw_dir.exists():
        print("ERROR: data/raw/ directory not found!")
        return
    
    # Find all GeoTIFF files
    files_to_split = []
    
    for dataset_dir in raw_dir.iterdir():
        if not dataset_dir.is_dir():
            continue
        
        # Skip tiles directories (already split)
        if dataset_dir.name == 'tiles':
            continue
        
        # Look for bbox/tile files
        for tif_file in dataset_dir.glob('*.tif'):
            # Skip if already in tiles/ subdirectory
            if 'tiles' in str(tif_file):
                continue
            
            # Check file size - we want to split large files
            # For now, we'll check all files and let the script decide based on bounds
            files_to_split.append(tif_file)
    
    print(f"Found {len(files_to_split)} files to process:")
    for f in files_to_split:
        print(f"  {f}")
    print()
    
    if not files_to_split:
        print("No files to split!")
        return
    
    # Process each file
    total_created = 0
    
    for source_file in files_to_split:
        # Determine dataset and resolution
        dataset, resolution = determine_dataset_and_resolution(source_file)
        
        # Determine tiles directory
        if '90m' in dataset or 'srtm_90m' in str(source_file.parent):
            tiles_dir = raw_dir / 'srtm_90m' / 'tiles'
        elif '3dep' in dataset or 'usa_3dep' in str(source_file.parent):
            tiles_dir = raw_dir / 'usa_3dep' / 'tiles'
        elif 'cop' in dataset or 'copernicus' in str(source_file.parent):
            # Determine resolution from dataset name
            if '30m' in dataset:
                tiles_dir = raw_dir / 'cop30' / 'tiles'
            else:
                tiles_dir = raw_dir / 'cop90' / 'tiles'
        else:
            # Default to srtm_30m
            tiles_dir = raw_dir / 'srtm_30m' / 'tiles'
        
        # Split file
        created = split_file(source_file, tiles_dir, dataset, resolution)
        total_created += created
    
    print()
    print("=" * 70)
    print(f"SUMMARY")
    print("=" * 70)
    print(f"Total tiles created: {total_created}")
    print()
    print("Done! All files split into 1-degree tiles.")
    print("Note: Original files are NOT deleted. Review and delete manually if desired.")


if __name__ == '__main__':
    main()

