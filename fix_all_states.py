"""
Audit and fix all US state elevation data and borders.

This script:
1. Checks all US states for aspect ratio correctness
2. Re-exports states with incorrect aspect ratios
3. Exports state-specific borders for all states
4. Generates audit report
"""
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import rasterio

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.regions_config import US_STATES
from download_regions import process_region
from src.borders import get_border_manager


def check_aspect_ratio(source_tif: Path, exported_json: Path, tolerance: float = 0.01) -> Tuple[bool, float, float, float]:
    """
    Check if exported JSON has correct aspect ratio compared to source TIF.
    
    Returns:
        (is_correct, source_aspect, export_aspect, difference)
    """
    try:
        # Get source aspect ratio
        with rasterio.open(source_tif) as src:
            source_aspect = src.width / src.height
        
        # Get export aspect ratio
        with open(exported_json, 'r') as f:
            data = json.load(f)
            export_aspect = data['width'] / data['height']
        
        diff = abs(export_aspect - source_aspect)
        is_correct = diff <= tolerance
        
        return is_correct, source_aspect, export_aspect, diff
    except Exception as e:
        print(f"Error checking {exported_json.name}: {e}")
        return False, 0.0, 0.0, 0.0


def check_border_type(borders_json: Path) -> str:
    """
    Check if borders file has state or country borders.
    
    Returns:
        'states', 'countries', or 'missing'
    """
    if not borders_json.exists():
        return 'missing'
    
    try:
        with open(borders_json, 'r') as f:
            data = json.load(f)
            if 'states' in data:
                return 'states'
            elif 'countries' in data:
                return 'countries'
            else:
                return 'unknown'
    except:
        return 'error'


def export_state_borders(tif_path: Path, state_name: str, output_path: Path, resolution: str = '110m') -> bool:
    """Export state-level border data."""
    try:
        border_manager = get_border_manager()
        
        # Get bounding box from elevation data
        with rasterio.open(tif_path) as src:
            bounds = src.bounds
        
        # Get state geometry
        state_gdf = border_manager.get_state("United States of America", state_name, resolution)
        
        if state_gdf is None or state_gdf.empty:
            print(f"       State '{state_name}' not found in border database")
            return False
        
        # Extract border coordinates
        segments = []
        for idx, row in state_gdf.iterrows():
            geom = row['geometry']
            
            # Handle MultiPolygon or Polygon
            if geom.geom_type == 'Polygon':
                polygons = [geom]
            elif geom.geom_type == 'MultiPolygon':
                polygons = list(geom.geoms)
            else:
                continue
            
            # Extract coordinates from each polygon
            for poly in polygons:
                # Exterior ring
                coords = list(poly.exterior.coords)
                if len(coords) > 2:
                    lons = [float(c[0]) for c in coords]
                    lats = [float(c[1]) for c in coords]
                    segments.append({"lon": lons, "lat": lats})
                
                # Interior rings (holes)
                for interior in poly.interiors:
                    coords = list(interior.coords)
                    if len(coords) > 2:
                        lons = [float(c[0]) for c in coords]
                        lats = [float(c[1]) for c in coords]
                        segments.append({"lon": lons, "lat": lats})
        
        # Create borders data
        borders_data = {
            "bounds": {
                "left": float(bounds.left),
                "right": float(bounds.right),
                "top": float(bounds.top),
                "bottom": float(bounds.bottom)
            },
            "resolution": resolution,
            "states": [{
                "country": "United States of America",
                "name": state_name,
                "segments": segments,
                "segment_count": len(segments)
            }]
        }
        
        # Write JSON
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(borders_data, f, separators=(',', ':'))
        
        return True
        
    except Exception as e:
        print(f"       Error exporting borders: {e}")
        return False


def audit_all_states() -> Dict[str, Dict]:
    """
    Audit all US states for data correctness.
    
    Returns:
        Dictionary with state_id as key and audit info as value
    """
    print("\n" + "="*70)
    print("AUDITING ALL US STATES")
    print("="*70)
    
    audit_results = {}
    data_dir = Path("data/regions")
    generated_dir = Path("generated/regions")
    
    for state_id, state_info in US_STATES.items():
        # Handle both RegionConfig and dict types
        state_name = state_info.name if hasattr(state_info, 'name') else state_info['name']
        
        # Check if source TIF exists
        source_tif = data_dir / f"{state_id}.tif"
        if not source_tif.exists():
            audit_results[state_id] = {
                'name': state_name,
                'status': 'no_source',
                'needs_fix': False
            }
            continue
        
        # Find exported JSON (could be in multiple formats)
        possible_jsons = [
            generated_dir / f"{state_id}.json",
            generated_dir / f"{state_id}_srtm_30m_800px_v2.json",
            generated_dir / f"{state_id}_srtm_30m_4000px_v2.json",
        ]
        
        exported_json = None
        for possible in possible_jsons:
            if possible.exists():
                exported_json = possible
                break
        
        if not exported_json:
            audit_results[state_id] = {
                'name': state_name,
                'status': 'not_exported',
                'needs_fix': False
            }
            continue
        
        # Check aspect ratio
        is_correct, source_aspect, export_aspect, diff = check_aspect_ratio(source_tif, exported_json)
        
        # Check borders
        borders_json = exported_json.parent / exported_json.name.replace('.json', '_borders.json')
        border_type = check_border_type(borders_json)
        
        needs_aspect_fix = not is_correct
        needs_border_fix = border_type != 'states'
        
        audit_results[state_id] = {
            'name': state_name,
            'status': 'exported',
            'source_tif': source_tif,
            'exported_json': exported_json,
            'borders_json': borders_json,
            'source_aspect': source_aspect,
            'export_aspect': export_aspect,
            'aspect_diff': diff,
            'aspect_correct': is_correct,
            'border_type': border_type,
            'needs_aspect_fix': needs_aspect_fix,
            'needs_border_fix': needs_border_fix,
            'needs_fix': needs_aspect_fix or needs_border_fix
        }
    
    return audit_results


def print_audit_report(audit_results: Dict[str, Dict]):
    """Print formatted audit report."""
    print("\n" + "="*70)
    print("AUDIT REPORT")
    print("="*70)
    
    # Count issues
    total = len(audit_results)
    needs_aspect_fix = sum(1 for r in audit_results.values() if r.get('needs_aspect_fix', False))
    needs_border_fix = sum(1 for r in audit_results.values() if r.get('needs_border_fix', False))
    needs_any_fix = sum(1 for r in audit_results.values() if r.get('needs_fix', False))
    no_source = sum(1 for r in audit_results.values() if r.get('status') == 'no_source')
    not_exported = sum(1 for r in audit_results.values() if r.get('status') == 'not_exported')
    correct = sum(1 for r in audit_results.values() if r.get('status') == 'exported' and not r.get('needs_fix'))
    
    print(f"\nTotal states: {total}")
    print(f"No source TIF: {no_source}")
    print(f"Not exported: {not_exported}")
    print(f"Correct: {correct}")
    print(f"Need aspect fix: {needs_aspect_fix}")
    print(f"Need border fix: {needs_border_fix}")
    print(f"Need any fix: {needs_any_fix}")
    
    if needs_any_fix > 0:
        print("\n" + "="*70)
        print("STATES NEEDING FIXES")
        print("="*70)
        
        for state_id, info in sorted(audit_results.items()):
            if not info.get('needs_fix'):
                continue
            
            issues = []
            if info.get('needs_aspect_fix'):
                issues.append(f"aspect {info['export_aspect']:.3f} (should be {info['source_aspect']:.3f})")
            if info.get('needs_border_fix'):
                issues.append(f"borders: {info['border_type']}")
            
            print(f"\n{state_id:20s} ({info['name']})")
            print(f"  Issues: {', '.join(issues)}")
            print(f"  Source: {info['source_tif']}")
            print(f"  Export: {info['exported_json'].name}")


def fix_state(state_id: str, state_info: Dict, audit_info: Dict, force: bool = False) -> bool:
    """
    Fix a single state's elevation and borders.
    
    Returns:
        True if successful
    """
    state_name = state_info['name']
    print(f"\n{'='*70}")
    print(f"FIXING: {state_name} ({state_id})")
    print(f"{'='*70}")
    
    source_tif = audit_info['source_tif']
    
    # Re-export elevation if needed
    if audit_info.get('needs_aspect_fix') or force:
        print(f"\n[1/2] Re-exporting elevation data...")
        
        region_info = {
            "bounds": state_info["bounds"],
            "name": state_name,
            "description": f"{state_name} elevation data"
        }
        
        success = process_region(
            state_id,
            region_info,
            Path("data/regions"),
            Path("generated/regions"),
            max_size=800
        )
        
        if not success:
            print(f" Failed to re-export elevation")
            return False
        
        print(f" Elevation re-exported")
    else:
        print(f"\n[1/2] Elevation aspect ratio correct, skipping")
    
    # Export state borders if needed
    if audit_info.get('needs_border_fix') or force:
        print(f"\n[2/2] Exporting state borders...")
        
        borders_path = Path("generated/regions") / f"{state_id}_borders.json"
        success = export_state_borders(source_tif, state_name, borders_path)
        
        if not success:
            print(f" Failed to export borders")
            return False
        
        print(f" State borders exported")
    else:
        print(f"\n[2/2] State borders correct, skipping")
    
    print(f"\n {state_name} fixed!")
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Audit and fix US state elevation data')
    parser.add_argument('--audit', action='store_true', help='Audit all states and show report')
    parser.add_argument('--fix', type=str, nargs='+', help='Fix specific states by ID')
    parser.add_argument('--fix-all', action='store_true', help='Fix all states that need fixes')
    parser.add_argument('--force', action='store_true', help='Force re-export even if correct')
    
    args = parser.parse_args()
    
    if not any([args.audit, args.fix, args.fix_all]):
        parser.print_help()
        print("\nExamples:")
        print("  python fix_all_states.py --audit                    # Show audit report")
        print("  python fix_all_states.py --fix delaware florida    # Fix specific states")
        print("  python fix_all_states.py --fix-all                 # Fix all bad states")
        return 1
    
    # Run audit
    audit_results = audit_all_states()
    
    if args.audit:
        print_audit_report(audit_results)
        return 0
    
    # Fix specific states
    if args.fix:
        for state_id in args.fix:
            state_id = state_id.lower().replace(' ', '_').replace('-', '_')
            
            if state_id not in US_STATES:
                print(f"\n Unknown state: {state_id}")
                continue
            
            if state_id not in audit_results:
                print(f"\n No audit info for: {state_id}")
                continue
            
            audit_info = audit_results[state_id]
            if audit_info['status'] != 'exported':
                print(f"\n  {state_id}: {audit_info['status']}")
                continue
            
            fix_state(state_id, US_STATES[state_id], audit_info, args.force)
    
    # Fix all states
    if args.fix_all:
        states_to_fix = [
            (sid, info) for sid, info in audit_results.items()
            if info.get('needs_fix', False)
        ]
        
        if not states_to_fix:
            print("\n No states need fixing!")
            return 0
        
        print(f"\n{'='*70}")
        print(f"FIXING {len(states_to_fix)} STATES")
        print(f"{'='*70}")
        
        fixed = 0
        failed = 0
        
        for state_id, audit_info in states_to_fix:
            success = fix_state(state_id, US_STATES[state_id], audit_info, args.force)
            if success:
                fixed += 1
            else:
                failed += 1
        
        print(f"\n{'='*70}")
        print(f"SUMMARY")
        print(f"{'='*70}")
        print(f"Fixed: {fixed}")
        print(f"Failed: {failed}")
        print(f"Total: {len(states_to_fix)}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

