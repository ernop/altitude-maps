"""
One-time migration script to rename files from region_id-based naming to abstract bounds-based naming.

This script:
1. Scans for old region_id-based files in data/raw/, data/clipped/, data/processed/, generated/regions/
2. Extracts bounds from files or looks up from region config
3. Generates new abstract filenames based on bounds
4. Renames/moves files to new names
5. Reports results

Run with --dry-run first to see what would be renamed without making changes.
"""

import sys
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import shutil
import math

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    import rasterio
except ImportError as e:
    print(f"Missing package: {e}")
    print("Install with: pip install rasterio")
    sys.exit(1)

from src.regions_config import ALL_REGIONS
from src.metadata import load_metadata, get_metadata_path
from ensure_region import bbox_filename_from_bounds, get_bounds_from_raw_file, abstract_filename_from_raw


def bbox_filename_from_bounds(bounds: Tuple[float, float, float, float], 
                              dataset: str = 'srtm_30m', 
                              resolution: str = '30m') -> str:
    """Generate abstract bounds-based filename."""
    west, south, east, north = bounds
    
    sw_lat = int(math.floor(south)) if south >= 0 else int(math.trunc(south))
    sw_lon = int(math.floor(west)) if west >= 0 else int(math.trunc(west))
    ne_lat = int(math.ceil(north))
    ne_lon = int(math.ceil(east))
    
    sw_ns = 'N' if sw_lat >= 0 else 'S'
    sw_lat_str = f"{sw_ns}{abs(sw_lat):02d}"
    sw_ew = 'E' if sw_lon >= 0 else 'W'
    sw_lon_str = f"{sw_ew}{abs(sw_lon):03d}"
    
    ne_ns = 'N' if ne_lat >= 0 else 'S'
    ne_lat_str = f"{ne_ns}{abs(ne_lat):02d}"
    ne_ew = 'E' if ne_lon >= 0 else 'W'
    ne_lon_str = f"{ne_ew}{abs(ne_lon):03d}"
    
    return f"bbox_{sw_lat_str}_{sw_lon_str}_{ne_lat_str}_{ne_lon_str}_{dataset}_{resolution}.tif"


def get_bounds_from_file(file_path: Path) -> Optional[Tuple[float, float, float, float]]:
    """Extract bounds from a GeoTIFF file. Returns bounds in degrees (EPSG:4326)."""
    try:
        with rasterio.open(file_path) as src:
            bounds = src.bounds
            crs = src.crs
            
            # If file is already in EPSG:4326 (WGS84), return bounds directly
            crs_str = str(crs).upper() if crs else ''
            if crs and ('EPSG:4326' in crs_str or 'WGS84' in crs_str or '4326' in crs_str):
                return (bounds.left, bounds.bottom, bounds.right, bounds.top)
            
            # Otherwise, transform bounds to EPSG:4326
            if crs:
                from rasterio.warp import transform_bounds
                bounds_4326 = transform_bounds(crs, 'EPSG:4326', bounds.left, bounds.bottom, bounds.right, bounds.top)
                return bounds_4326
            
            # If no CRS, assume it's already in degrees (legacy files)
            return (bounds.left, bounds.bottom, bounds.right, bounds.top)
    except Exception:
        return None


def extract_region_id_from_filename(filename: str) -> Optional[str]:
    """Extract region_id from old naming patterns."""
    # Old patterns:
    # - {region_id}_3dep_10m.tif
    # - {region_id}_bbox_30m.tif
    # - {region_id}_bbox_90m.tif
    # - {region_id}_clipped_{source}_v1.tif
    # - {region_id}_{source}_{target_pixels}px_v2.tif
    # - {region_id}_{source}_{target_pixels}px_v2.json
    
    stem = Path(filename).stem
    
    # Try to extract region_id by removing known suffixes
    for suffix in ['_3dep_10m', '_bbox_30m', '_bbox_90m', '_clipped_srtm_30m_v1', '_clipped_srtm_90m_v1', 
                   '_clipped_usa_3dep_v1', '_srtm_30m_2048px_v2', '_srtm_30m_1024px_v2', '_srtm_30m_512px_v2',
                   '_srtm_30m_800px_v2', '_srtm_30m_4096px_v2', '_srtm_90m_2048px_v2', '_usa_3dep_2048px_v2']:
        if stem.endswith(suffix):
            region_id = stem[:-len(suffix)]
            return region_id
    
    # Try pattern matching for processed/exported files
    import re
    # Pattern: {region_id}_{source}_{pixels}px_v2
    match = re.match(r'^(.+?)_(srtm_30m|srtm_90m|usa_3dep)_(\d+)px_v2$', stem)
    if match:
        return match.group(1)
    
    # Pattern: {region_id}_clipped_{source}_v1
    match = re.match(r'^(.+?)_clipped_(srtm_30m|srtm_90m|usa_3dep)_v1$', stem)
    if match:
        return match.group(1)
    
    return None


def determine_source_and_resolution(file_path: Path, region_id: Optional[str] = None) -> Tuple[str, str]:
    """Determine source and resolution from file path and name."""
    path_str = str(file_path)
    
    if 'usa_3dep' in path_str:
        return 'usa_3dep', '10m'
    elif 'srtm_90m' in path_str:
        return 'srtm_90m', '90m'
    elif 'srtm_30m' in path_str or 'srtm' in path_str:
        return 'srtm_30m', '30m'
    
    # Try to infer from filename
    name_lower = file_path.name.lower()
    if '3dep' in name_lower or '10m' in name_lower:
        return 'usa_3dep', '10m'
    elif '90m' in name_lower:
        return 'srtm_90m', '90m'
    else:
        return 'srtm_30m', '30m'


def find_files_to_migrate(base_dir: Path, pattern: str) -> List[Path]:
    """Find files matching old naming patterns."""
    if not base_dir.exists():
        return []
    
    files = []
    for file_path in base_dir.rglob(pattern):
        if file_path.is_file():
            # Skip files that already use abstract naming
            if file_path.name.startswith('bbox_'):
                continue
            files.append(file_path)
    
    return files


def get_boundary_name_from_metadata(file_path: Path) -> Optional[str]:
    """Try to extract boundary name from metadata file."""
    try:
        metadata_path = get_metadata_path(file_path)
        if metadata_path.exists():
            metadata = load_metadata(metadata_path)
            # Check for boundary name in metadata
            if 'clip_boundary' in metadata:
                return metadata['clip_boundary']
    except Exception:
        pass
    return None


def generate_new_filename(old_path: Path, bounds: Tuple[float, float, float, float], 
                         source: str, resolution: str, region_id: Optional[str] = None) -> Optional[str]:
    """Generate new abstract filename for a file."""
    old_name = old_path.name
    
    # Raw files
    if old_name.endswith('.tif') and ('_bbox_30m' in old_name or '_bbox_90m' in old_name or '_3dep_10m' in old_name):
        return bbox_filename_from_bounds(bounds, source, resolution)
    
    # Clipped files - need boundary info from metadata
    if '_clipped_' in old_name and old_name.endswith('.tif'):
        # Try to get boundary name from metadata
        boundary_name = get_boundary_name_from_metadata(old_path)
        
        # Generate base part from bounds
        raw_filename = bbox_filename_from_bounds(bounds, source, resolution)
        base_part = raw_filename[5:-4]  # Remove 'bbox_' and '.tif'
        
        # Generate boundary hash if we have boundary name
        if boundary_name:
            boundary_hash = hash(boundary_name)
            boundary_suffix = f"_{abs(boundary_hash) % 1000000:06d}"
        else:
            # If no boundary name, we can't generate correct hash
            # Use empty suffix (matches files without boundary)
            boundary_suffix = ""
        
        return f"{base_part}_clipped{boundary_suffix}_v1.tif"
    
    # Clipped metadata JSON files (skip)
    if '_clipped_' in old_name and old_name.endswith('.json'):
        return None
    
    # Processed files (but not reprojected intermediate files)
    if '_processed_' in old_name or ('px_v2.tif' in old_name and '_clipped_' not in old_name and '_reproj' not in old_name):
        # Extract target_pixels from old name
        import re
        match = re.search(r'(\d+)px_v2', old_name)
        if match:
            target_pixels = int(match.group(1))
            raw_filename = bbox_filename_from_bounds(bounds, source, resolution)
            base_part = raw_filename[5:-4]
            return f"{base_part}_processed_{target_pixels}px_v2.tif"
    
    # Reprojected intermediate files (skip - these are temporary and will be regenerated)
    if '_reproj.tif' in old_name:
        return None  # Skip reprojected intermediate files
    
    # Exported JSON files  
    if old_name.endswith('.json') and 'px_v2' in old_name and '_meta' not in old_name:
        import re
        match = re.search(r'(\d+)px_v2', old_name)
        if match:
            target_pixels = int(match.group(1))
            raw_filename = bbox_filename_from_bounds(bounds, source, resolution)
            base_part = raw_filename[5:-4]
            return f"{base_part}_{target_pixels}px_v2.json"
    
    # Metadata JSON files for raw bbox files (skip - these will be regenerated)
    if old_name.endswith('.json') and '_bbox_' in old_name:
        return None  # Skip raw bbox metadata files
    
    # Skip turkiye_tile files (custom tile format, not migrated)
    if 'turkiye_tile' in old_name:
        return None
    
    return None


def get_region_id_from_json(json_path: Path) -> Optional[str]:
    """Try to extract region_id from JSON file content."""
    try:
        import json as json_module
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json_module.load(f)
            return data.get('region_id')
    except Exception:
        return None


def migrate_file(old_path: Path, dry_run: bool = True) -> Dict:
    """Migrate a single file to new naming scheme."""
    result = {
        'old_path': old_path,
        'new_path': None,
        'success': False,
        'error': None,
        'skipped': False
    }
    
    old_name = old_path.name
    
    # Skip files already using abstract naming
    if old_name.startswith('bbox_') or old_name.startswith('tile_'):
        result['skipped'] = True
        result['error'] = 'Already using abstract naming'
        return result
    
    # Skip metadata files
    if '_meta.json' in old_name or old_name == 'regions_manifest.json':
        result['skipped'] = True
        result['error'] = 'Metadata file (skipped)'
        return result
    
    # Skip simple region JSON files that aren't exports (e.g., "arizona.json")
    if old_name.endswith('.json') and '_px_v2' not in old_name and '_bbox_' not in old_name:
        result['skipped'] = True
        result['error'] = 'Non-export JSON file (skipped)'
        return result
    
    # Try to get bounds from file (for GeoTIFF files)
    bounds = None
    if old_path.suffix in ['.tif', '.tiff']:
        bounds = get_bounds_from_file(old_path)
    
    # If we can't get bounds from file, try to extract region_id and look up
    region_id = None
    if bounds is None:
        # Try to extract from filename
        region_id = extract_region_id_from_filename(old_name)
        
        # For JSON files, try to read region_id from content
        if not region_id and old_path.suffix == '.json':
            region_id = get_region_id_from_json(old_path)
        
        if region_id and region_id in ALL_REGIONS:
            bounds = ALL_REGIONS[region_id].bounds
        else:
            # If we can't find region, mark as skipped (might be a region not in config)
            result['skipped'] = True
            result['error'] = f'Region not in config (may need manual migration): {region_id}'
            return result
    
    # Determine source and resolution
    source, resolution = determine_source_and_resolution(old_path, region_id)
    
    # Generate new filename
    new_filename = generate_new_filename(old_path, bounds, source, resolution, region_id)
    if not new_filename:
        # For skipped file types (like reproj, metadata), mark as skipped instead of failed
        if '_reproj' in old_path.name or '_meta' in old_path.name or '_bbox_' in old_path.name and old_path.suffix == '.json':
            result['skipped'] = True
            result['error'] = 'File type skipped (intermediate or metadata file)'
        else:
            result['error'] = 'Could not generate new filename (unknown pattern)'
        return result
    
    new_path = old_path.parent / new_filename
    
    # Skip if new file already exists
    if new_path.exists():
        result['skipped'] = True
        result['error'] = f'Target file already exists: {new_path.name}'
        result['new_path'] = new_path
        return result
    
    result['new_path'] = new_path
    
    # Perform migration
    if not dry_run:
        try:
            old_path.rename(new_path)
            result['success'] = True
        except Exception as e:
            result['error'] = f'Rename failed: {e}'
    else:
        result['success'] = True  # Simulated success for dry-run
    
    return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Migrate files from region_id-based naming to abstract bounds-based naming',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be renamed without making changes (default: True)')
    parser.add_argument('--execute', action='store_true',
                       help='Actually perform the migration (required to make changes)')
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if dry_run:
        print("=" * 70)
        print("DRY RUN MODE - No files will be renamed")
        print("Run with --execute to actually perform migration")
        print("=" * 70)
    else:
        print("=" * 70)
        print("EXECUTION MODE - Files will be renamed")
        print("=" * 70)
    
    print()
    
    # Directories to scan
    directories = {
        'raw': [
            Path('data/raw/usa_3dep'),
            Path('data/raw/srtm_30m'),
            Path('data/raw/srtm_90m'),
        ],
        'clipped': [
            Path('data/clipped/usa_3dep'),
            Path('data/clipped/srtm_30m'),
            Path('data/clipped/srtm_90m'),
        ],
        'processed': [
            Path('data/processed/usa_3dep'),
            Path('data/processed/srtm_30m'),
            Path('data/processed/srtm_90m'),
        ],
        'exported': [
            Path('generated/regions'),
        ]
    }
    
    all_results = []
    
    # Scan for old files
    print("Scanning for files to migrate...")
    
    for category, dirs in directories.items():
        for dir_path in dirs:
            if not dir_path.exists():
                continue
            
            # Find files with old naming patterns
            patterns = ['*.tif', '*.json']
            for pattern in patterns:
                for file_path in dir_path.rglob(pattern):
                    if file_path.is_file():
                        # Skip files already using abstract naming
                        if file_path.name.startswith('bbox_') or file_path.name.startswith('tile_'):
                            continue
                        result = migrate_file(file_path, dry_run=dry_run)
                        all_results.append(result)
    
    # Report results
    print(f"\n{'=' * 70}")
    print(f"Migration Results")
    print(f"{'=' * 70}")
    
    successful = [r for r in all_results if r['success']]
    skipped = [r for r in all_results if r['skipped']]
    failed = [r for r in all_results if not r['success'] and not r['skipped']]
    
    print(f"\nTotal files found: {len(all_results)}")
    print(f"  Successful: {len(successful)}")
    print(f"  Skipped: {len(skipped)}")
    print(f"  Failed: {len(failed)}")
    
    if successful:
        print(f"\n{'=' * 70}")
        print("Successful migrations:")
        for r in successful:
            print(f"  {r['old_path'].name}")
            print(f"    -> {r['new_path'].name}")
    
    if skipped:
        print(f"\n{'=' * 70}")
        print("Skipped files (already migrated or target exists):")
        for r in skipped[:10]:  # Show first 10
            print(f"  {r['old_path'].name}: {r['error']}")
        if len(skipped) > 10:
            print(f"  ... and {len(skipped) - 10} more")
    
    if failed:
        print(f"\n{'=' * 70}")
        print("Failed migrations:")
        for r in failed:
            print(f"  {r['old_path'].name}: {r['error']}")
    
    if dry_run and successful:
        print(f"\n{'=' * 70}")
        print("To actually perform these renames, run with --execute flag")
        print(f"Example: python migrate_to_abstract_naming.py --execute")
    elif successful:
        print(f"\n{'=' * 70}")
        print("Migration complete!")
    
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

