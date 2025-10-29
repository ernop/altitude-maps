"""
Fix aspect ratio for all regions by regenerating with crop=True.

This script identifies regions with aspect ratio issues and regenerates them
using the fixed masking code (crop=True in src/borders.py).

Usage:
    python fix_all_regions_aspect_ratio.py --check-only    # Check which need fixing
    python fix_all_regions_aspect_ratio.py --fix-all       # Regenerate all bad ones
    python fix_all_regions_aspect_ratio.py --region tennessee  # Fix specific region
"""
import sys
import json
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

try:
    from src.pipeline import run_pipeline
except ImportError as e:
    print(f"Error importing: {e}")
    sys.exit(1)


def check_aspect_ratio(json_path: Path) -> Tuple[bool, float, float, dict]:
    """
    Check if a region's aspect ratio is correct.
    
    Returns:
        (is_valid, raster_aspect, geo_aspect, info)
    """
    try:
        with open(json_path) as f:
            data = json.load(f)
        
        width = data['width']
        height = data['height']
        bounds = data['bounds']
        
        # Calculate raster aspect
        raster_aspect = width / height if height > 0 else 0
        
        # Calculate geographic aspect (accounting for latitude)
        west, south = bounds['left'], bounds['bottom']
        east, north = bounds['right'], bounds['top']
        
        lon_span = abs(east - west)
        lat_span = abs(north - south)
        center_lat = (north + south) / 2.0
        
        meters_per_deg_lon = 111_320 * np.cos(np.radians(center_lat))
        meters_per_deg_lat = 111_320
        
        geo_width = lon_span * meters_per_deg_lon
        geo_height = lat_span * meters_per_deg_lat
        geo_aspect = geo_width / geo_height if geo_height > 0 else 0
        
        # Check if aspect ratio is reasonable
        if geo_aspect > 0:
            ratio_diff = abs(raster_aspect - geo_aspect) / geo_aspect
            is_valid = ratio_diff <= 0.3  # 30% tolerance
        else:
            is_valid = True
        
        info = {
            'region_id': data.get('region_id', json_path.stem),
            'name': data.get('name', ''),
            'width': width,
            'height': height,
            'raster_aspect': raster_aspect,
            'geo_aspect': geo_aspect,
            'difference_pct': abs(raster_aspect - geo_aspect) / geo_aspect * 100 if geo_aspect > 0 else 0
        }
        
        return is_valid, raster_aspect, geo_aspect, info
        
    except Exception as e:
        print(f"Error checking {json_path}: {e}")
        return True, 0, 0, {}


def find_regions_needing_fix(generated_dir: Path) -> List[dict]:
    """Find all regions with aspect ratio issues."""
    bad_regions = []
    
    for json_file in generated_dir.rglob("*.json"):
        # Skip borders, meta, and manifest files
        if any(x in json_file.stem for x in ['_borders', '_meta', 'manifest']):
            continue
        
        is_valid, raster_asp, geo_asp, info = check_aspect_ratio(json_file)
        
        if not is_valid:
            info['json_path'] = json_file
            bad_regions.append(info)
    
    return bad_regions


def find_source_tif_for_region(region_id: str) -> Tuple[Path, str]:
    """
    Find the source TIF file for a region.
    
    Returns:
        (tif_path, source_type) or (None, None) if not found
    """
    # Check common locations
    locations = [
        (Path(f"data/raw/srtm_30m/{region_id}_bbox_30m.tif"), "srtm_30m"),
        (Path(f"data/regions/{region_id}.tif"), "srtm_30m"),
        (Path(f"data/raw/usa_3dep/{region_id}_3dep_10m.tif"), "usa_3dep"),
    ]
    
    for tif_path, source in locations:
        if tif_path.exists():
            return tif_path, source
    
    return None, None


def fix_region(region_id: str, source_tif: Path, source_type: str, target_pixels: int = 1024) -> bool:
    """
    Regenerate a region with proper cropping.
    
    Determines the appropriate boundary based on region_id.
    """
    # US states need state-level boundaries
    us_states_list = [
        'alabama', 'arizona', 'arkansas', 'california', 'colorado', 'connecticut',
        'delaware', 'florida', 'georgia', 'idaho', 'illinois', 'indiana', 'iowa',
        'kansas', 'kentucky', 'louisiana', 'maine', 'maryland', 'massachusetts',
        'michigan', 'minnesota', 'mississippi', 'missouri', 'montana', 'nebraska',
        'nevada', 'new_hampshire', 'new_jersey', 'new_mexico', 'new_york',
        'north_carolina', 'north_dakota', 'ohio', 'oklahoma', 'oregon',
        'pennsylvania', 'rhode_island', 'south_carolina', 'south_dakota',
        'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
        'west_virginia', 'wisconsin', 'wyoming'
    ]
    
    # Determine boundary
    if region_id in us_states_list:
        # State-level boundary
        state_names = {
            'alabama': 'Alabama', 'arizona': 'Arizona', 'arkansas': 'Arkansas',
            'california': 'California', 'colorado': 'Colorado', 'connecticut': 'Connecticut',
            'delaware': 'Delaware', 'florida': 'Florida', 'georgia': 'Georgia',
            'idaho': 'Idaho', 'illinois': 'Illinois', 'indiana': 'Indiana',
            'iowa': 'Iowa', 'kansas': 'Kansas', 'kentucky': 'Kentucky',
            'louisiana': 'Louisiana', 'maine': 'Maine', 'maryland': 'Maryland',
            'massachusetts': 'Massachusetts', 'michigan': 'Michigan', 'minnesota': 'Minnesota',
            'mississippi': 'Mississippi', 'missouri': 'Missouri', 'montana': 'Montana',
            'nebraska': 'Nebraska', 'nevada': 'Nevada', 'new_hampshire': 'New Hampshire',
            'new_jersey': 'New Jersey', 'new_mexico': 'New Mexico', 'new_york': 'New York',
            'north_carolina': 'North Carolina', 'north_dakota': 'North Dakota',
            'ohio': 'Ohio', 'oklahoma': 'Oklahoma', 'oregon': 'Oregon',
            'pennsylvania': 'Pennsylvania', 'rhode_island': 'Rhode Island',
            'south_carolina': 'South Carolina', 'south_dakota': 'South Dakota',
            'tennessee': 'Tennessee', 'texas': 'Texas', 'utah': 'Utah',
            'vermont': 'Vermont', 'virginia': 'Virginia', 'washington': 'Washington',
            'west_virginia': 'West Virginia', 'wisconsin': 'Wisconsin', 'wyoming': 'Wyoming'
        }
        state_name = state_names.get(region_id, region_id.replace('_', ' ').title())
        boundary_name = f"United States of America/{state_name}"
        boundary_type = "state"
    else:
        # For other regions, try country-level or skip
        boundary_name = None
        boundary_type = "country"
    
    print(f"\n{'='*70}")
    print(f"Fixing: {region_id}")
    print(f"  Source: {source_tif}")
    print(f"  Type: {source_type}")
    if boundary_name:
        print(f"  Boundary: {boundary_name}")
    print(f"{'='*70}")
    
    try:
        success, result_paths = run_pipeline(
            raw_tif_path=source_tif,
            region_id=region_id,
            source=source_type,
            boundary_name=boundary_name,
            boundary_type=boundary_type,
            target_pixels=target_pixels,
            skip_clip=(boundary_name is None)
        )
        
        if success:
            print(f"\n {region_id} fixed successfully!")
            return True
        else:
            print(f"\n {region_id} failed!")
            return False
            
    except Exception as e:
        print(f"\n Error fixing {region_id}: {e}")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Fix aspect ratio issues in region data',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--check-only', action='store_true',
                       help='Only check which regions need fixing')
    parser.add_argument('--fix-all', action='store_true',
                       help='Fix all regions with aspect ratio issues')
    parser.add_argument('--region', type=str,
                       help='Fix specific region by ID')
    parser.add_argument('--target-pixels', type=int, default=1024,
                       help='Target resolution (default: 1024)')
    parser.add_argument('--generated-dir', type=str, default='generated/regions',
                       help='Directory with generated JSON files')
    
    args = parser.parse_args()
    
    generated_dir = Path(args.generated_dir)
    
    if not generated_dir.exists():
        print(f" Generated directory not found: {generated_dir}")
        return 1
    
    # Check which regions need fixing
    print(f"\n🔍 Scanning {generated_dir} for aspect ratio issues...")
    bad_regions = find_regions_needing_fix(generated_dir)
    
    if not bad_regions:
        print("\n All regions have correct aspect ratios!")
        return 0
    
    # Report findings
    print(f"\n Found {len(bad_regions)} region(s) with aspect ratio issues:\n")
    print(f"{'Region':<20} {'Dimensions':<15} {'Raster':<10} {'Geographic':<10} {'Diff'}")
    print("-" * 70)
    for region in sorted(bad_regions, key=lambda x: x['difference_pct'], reverse=True):
        dims = f"{region['width']}×{region['height']}"
        print(f"{region['region_id']:<20} {dims:<15} "
              f"{region['raster_aspect']:<10.3f} {region['geo_aspect']:<10.3f} "
              f"{region['difference_pct']:>5.1f}%")
    
    if args.check_only:
        print("\nUse --fix-all to regenerate these regions")
        return 0
    
    # Fix specific region
    if args.region:
        region_id = args.region.lower()
        source_tif, source_type = find_source_tif_for_region(region_id)
        
        if not source_tif:
            print(f"\n Cannot find source TIF for: {region_id}")
            print("Expected locations:")
            print(f"  - data/raw/srtm_30m/{region_id}_bbox_30m.tif")
            print(f"  - data/regions/{region_id}.tif")
            return 1
        
        success = fix_region(region_id, source_tif, source_type, args.target_pixels)
        return 0 if success else 1
    
    # Fix all bad regions
    if args.fix_all:
        fixed = []
        failed = []
        skipped = []
        
        for region in bad_regions:
            region_id = region['region_id']
            source_tif, source_type = find_source_tif_for_region(region_id)
            
            if not source_tif:
                print(f"\n  Skipping {region_id} (source TIF not found)")
                skipped.append(region_id)
                continue
            
            success = fix_region(region_id, source_tif, source_type, args.target_pixels)
            if success:
                fixed.append(region_id)
            else:
                failed.append(region_id)
        
        # Summary
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        print(f"Fixed:   {len(fixed)}")
        print(f"Failed:  {len(failed)}")
        print(f"Skipped: {len(skipped)} (source TIF not found)")
        
        if fixed:
            print(f"\n Fixed regions: {', '.join(fixed)}")
        if failed:
            print(f"\n Failed regions: {', '.join(failed)}")
        if skipped:
            print(f"\n  Skipped regions: {', '.join(skipped)}")
        
        return 0 if not failed else 1
    
    # If no action specified
    print("\nUse --check-only to see issues, --fix-all to fix them, or --region <name> for one")
    return 0


if __name__ == "__main__":
    sys.exit(main())

