"""
Automatically compute region adjacency from geographic boundary data.
Determines which regions border each other and in which cardinal direction.
"""
from pathlib import Path
import json
import gzip
import geopandas as gpd
from shapely.geometry import Point
from src.borders import get_border_manager
from src.regions_config import list_regions, get_region
from src.types import RegionType
import math

def get_cardinal_direction(from_centroid, to_centroid):
    """
    Determine cardinal direction from one point to another.
    Returns: 'north', 'south', 'east', or 'west'
    
    Each direction gets a 90-degree sector:
    - East: -45 to 45 degrees
    - North: 45 to 135 degrees
    - West: 135 to 225 degrees (or -135 to -225)
    - South: 225 to 315 degrees (or -45 to -135)
    """
    dx = to_centroid.x - from_centroid.x
    dy = to_centroid.y - from_centroid.y
    
    # Calculate angle in degrees (0 = east, 90 = north, etc.)
    angle = math.degrees(math.atan2(dy, dx))
    
    # Normalize to 0-360
    if angle < 0:
        angle += 360
    
    # Map to cardinal directions (90-degree sectors)
    # -45 to 45: east, 45 to 135: north, 135 to 225: west, 225 to 315: south
    if angle >= 315 or angle < 45:
        return 'east'
    elif 45 <= angle < 135:
        return 'north'
    elif 135 <= angle < 225:
        return 'west'
    else:  # 225 <= angle < 315
        return 'south'

def compute_adjacency():
    """
    Compute adjacency relationships from actual geographic boundaries.
    Also detects containment - when area-type regions are within other regions.
    """
    print("Computing region adjacency from geographic boundaries...")
    
    border_manager = get_border_manager()
    
    # Load US state boundaries
    print("Loading US state boundaries...")
    states_gdf = border_manager.load_state_borders(border_resolution='10m')
    # Filter to US states only (exclude territories and foreign regions with same names)
    states_gdf = states_gdf[states_gdf['iso_3166_2'].str.startswith('US-', na=False)].copy()
    
    # Load country boundaries  
    print("Loading country boundaries...")
    countries_gdf = border_manager.load_borders(border_resolution='10m')
    
    # Get all configured regions
    all_regions = list_regions()
    
    # Build a mapping of region_id -> geometry
    region_geometries = {}
    area_regions = {}  # Separate dict for AREA types (use bounding box)
    
    # Process all regions based on their type
    for region in all_regions:
        if region.region_type == RegionType.USA_STATE:
            # Match by name in US states data
            state_name = region.name
            state_row = states_gdf[states_gdf['name'] == state_name]
            if not state_row.empty:
                region_geometries[region.id] = {
                    'geometry': state_row.iloc[0].geometry,
                    'name': region.name,
                    'type': RegionType.USA_STATE
                }
            else:
                print(f"Warning: Could not find boundary for US state {region.name}")
        
        elif region.region_type == RegionType.COUNTRY:
            # Try to match by name in Natural Earth data
            country_name = region.name
            # Try various name variations
            country_row = countries_gdf[countries_gdf['ADMIN'] == country_name]
            if country_row.empty:
                country_row = countries_gdf[countries_gdf['NAME'] == country_name]
            if country_row.empty:
                # Try partial match
                country_row = countries_gdf[countries_gdf['ADMIN'].str.contains(country_name, case=False, na=False)]
            
            if not country_row.empty:
                region_geometries[region.id] = {
                    'geometry': country_row.iloc[0].geometry,
                    'name': region.name,
                    'type': RegionType.COUNTRY
                }
            else:
                print(f"Warning: Could not find boundary for country {region.name}")
        
        elif region.region_type == RegionType.AREA:
            # AREA types (islands, mountain ranges, etc.) use bounding box for containment checks
            from shapely.geometry import box
            west, south, east, north = region.bounds
            bbox_geom = box(west, south, east, north)
            area_regions[region.id] = {
                'geometry': bbox_geom,
                'name': region.name,
                'type': RegionType.AREA,
                'centroid': bbox_geom.centroid
            }
            print(f"Added AREA type '{region.name}' for containment checks")
        
        else:
            raise ValueError(f"Unknown region type for {region.id}: {region.region_type}")
    
    print(f"\nFound geometries for {len(region_geometries)} regions")
    print(f"Found {len(area_regions)} AREA regions for containment checks")
    
    # Compute adjacency
    adjacency = {}
    
    # Also initialize adjacency for AREA regions (they won't have borders, but can have "within")
    for area_id in area_regions.keys():
        adjacency[area_id] = {
            'within': []  # Which regions contain this area
        }
    
    for region_id, region_data in region_geometries.items():
        print(f"\nProcessing {region_data['name']} ({region_id})...")
        adjacency[region_id] = {
            'north': [],
            'south': [],
            'east': [],
            'west': [],
            'contained': []  # AREA regions within this region
        }
        
        geom = region_data['geometry']
        centroid = geom.centroid
        
        # Find neighbors (regions that share a border)
        for other_id, other_data in region_geometries.items():
            if other_id == region_id:
                continue
            
            other_geom = other_data['geometry']
            
            # Check if they share a border (touches or intersects)
            if geom.touches(other_geom) or (geom.intersects(other_geom) and not geom.equals(other_geom)):
                # Compute the intersection to check if it's more than a point
                intersection = geom.intersection(other_geom)
                
                # Exclude single-point touches (quadripoints like Four Corners)
                # Only count as adjacent if they share a line segment or area
                if intersection.geom_type in ['Point', 'MultiPoint']:
                    print(f"  Skipping {other_data['name']} (point-only touch)")
                    continue
                
                # Calculate shared border length (for informational purposes)
                if hasattr(intersection, 'length'):
                    border_length = intersection.length
                else:
                    border_length = 0
                
                # Determine direction (pure cardinal only - each gets 90-degree sector)
                other_centroid = other_geom.centroid
                direction = get_cardinal_direction(centroid, other_centroid)
                
                # Add to adjacency list
                adjacency[region_id][direction].append(other_id)
                print(f"  {direction}: {other_data['name']} (border length: {border_length:.4f})")
        
        # Check for contained AREA regions
        for area_id, area_data in area_regions.items():
            area_geom = area_data['geometry']
            
            # Check if the area is contained or intersects with this region
            # Two conditions:
            # 1. Centroid is within the region (fully contained)
            # 2. Bounding box intersects the region (partial overlap)
            centroid_inside = geom.contains(area_data['centroid'])
            bbox_intersects = geom.intersects(area_geom) and not geom.touches(area_geom)
            
            if centroid_inside or bbox_intersects:
                # Add to this region's contained list
                adjacency[region_id]['contained'].append(area_id)
                # Add reverse relationship - this region contains the area
                adjacency[area_id]['within'].append(region_id)
                
                if centroid_inside and bbox_intersects:
                    print(f"  contained: {area_data['name']} (centroid + overlap)")
                elif centroid_inside:
                    print(f"  contained: {area_data['name']} (centroid)")
                else:
                    print(f"  contained: {area_data['name']} (intersects)")
        
        # Clean up empty directions
        adjacency[region_id] = {
            k: v if len(v) > 1 else (v[0] if len(v) == 1 else None)
            for k, v in adjacency[region_id].items()
        }
        # Remove None values (but keep 'contained' even if empty for consistency)
        adjacency[region_id] = {
            k: v for k, v in adjacency[region_id].items() 
            if v is not None or k == 'contained'
        }
        # Convert empty contained list to None for consistency with other directions
        if not adjacency[region_id].get('contained'):
            adjacency[region_id].pop('contained', None)
    
    # Clean up AREA regions
    for area_id in area_regions.keys():
        print(f"\nProcessing AREA: {area_regions[area_id]['name']} ({area_id})...")
        # Clean up empty directions
        adjacency[area_id] = {
            k: v if len(v) > 1 else (v[0] if len(v) == 1 else None)
            for k, v in adjacency[area_id].items()
        }
        # Remove None values
        adjacency[area_id] = {
            k: v for k, v in adjacency[area_id].items() 
            if v is not None
        }
        # If no relationships at all, remove the entry
        if not adjacency[area_id]:
            del adjacency[area_id]
            print(f"  (no relationships - removed from adjacency data)")
        else:
            if 'within' in adjacency[area_id]:
                within_list = adjacency[area_id]['within']
                if isinstance(within_list, list):
                    print(f"  within: {', '.join(within_list)}")
                else:
                    print(f"  within: {within_list}")
    
    # Write output
    output_file = Path('generated/regions/region_adjacency.json')
    output_file_gz = Path('generated/regions/region_adjacency.json.gz')
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Write uncompressed JSON
    with open(output_file, 'w') as f:
        json.dump(adjacency, f, indent=2)
    
    # Write gzipped version
    with gzip.open(output_file_gz, 'wt', encoding='utf-8') as f:
        json.dump(adjacency, f, indent=2)
    
    # Get file sizes
    json_size = output_file.stat().st_size
    gz_size = output_file_gz.stat().st_size
    compression_ratio = (1 - gz_size / json_size) * 100
    
    print(f"\n[SUCCESS] Computed adjacency for {len(adjacency)} regions")
    print(f"[SUCCESS] Saved to {output_file}")
    print(f"[SUCCESS] File sizes: {json_size:,} bytes (uncompressed), {gz_size:,} bytes (gzipped, {compression_ratio:.1f}% compression)")
    
    # Print summary
    total_connections = sum(
        len(neighbors) if isinstance(neighbors, list) else 1
        for region in adjacency.values()
        for neighbors in region.values()
    )
    print(f"[SUCCESS] Total connections: {total_connections}")
    
    # Count contained areas
    contained_count = sum(
        len(region.get('contained', [])) if isinstance(region.get('contained'), list) 
        else (1 if region.get('contained') else 0)
        for region in adjacency.values()
    )
    print(f"[SUCCESS] Total contained areas: {contained_count}")

if __name__ == '__main__':
    compute_adjacency()

