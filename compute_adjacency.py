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
    Returns: 'north', 'south', 'east', 'west', or primary+secondary like 'northeast'
    
    For simplicity, we'll use 8 directions and then map to the 4 cardinal ones,
    assigning to the closest.
    """
    dx = to_centroid.x - from_centroid.x
    dy = to_centroid.y - from_centroid.y
    
    # Calculate angle in degrees (0 = east, 90 = north, etc.)
    angle = math.degrees(math.atan2(dy, dx))
    
    # Normalize to 0-360
    if angle < 0:
        angle += 360
    
    # Map to cardinal directions (with 45-degree sectors)
    # 0-45: east, 45-135: north, 135-225: west, 225-315: south, 315-360: east
    if angle >= 337.5 or angle < 22.5:
        return 'east'
    elif 22.5 <= angle < 67.5:
        return 'northeast'
    elif 67.5 <= angle < 112.5:
        return 'north'
    elif 112.5 <= angle < 157.5:
        return 'northwest'
    elif 157.5 <= angle < 202.5:
        return 'west'
    elif 202.5 <= angle < 247.5:
        return 'southwest'
    elif 247.5 <= angle < 292.5:
        return 'south'
    else:  # 292.5 <= angle < 337.5
        return 'southeast'

def simplify_to_cardinal(direction):
    """
    Simplify 8-way direction to 4 cardinal directions.
    Northeast/Northwest -> north or east/west (pick dominant)
    Southeast/Southwest -> south or east/west (pick dominant)
    """
    if direction in ['north', 'south', 'east', 'west']:
        return direction
    
    # For diagonals, return both as a tuple so we can assign to both directions
    mapping = {
        'northeast': ('north', 'east'),
        'northwest': ('north', 'west'),
        'southeast': ('south', 'east'),
        'southwest': ('south', 'west')
    }
    return mapping.get(direction, direction)

def compute_adjacency():
    """
    Compute adjacency relationships from actual geographic boundaries.
    """
    print("Computing region adjacency from geographic boundaries...")
    
    border_manager = get_border_manager()
    
    # Load US state boundaries
    print("Loading US state boundaries...")
    states_gdf = border_manager.load_state_borders(resolution='10m')
    # Filter to US states only (exclude territories and foreign regions with same names)
    states_gdf = states_gdf[states_gdf['iso_3166_2'].str.startswith('US-', na=False)].copy()
    
    # Load country boundaries  
    print("Loading country boundaries...")
    countries_gdf = border_manager.load_borders(resolution='10m')
    
    # Get all configured regions
    all_regions = list_regions()
    
    # Build a mapping of region_id -> geometry
    region_geometries = {}
    
    # Process all regions based on their type
    for region in all_regions:
        if region.region_type == RegionType.USA_STATE:
            # Match by name in US states data
            state_name = region.name
            state_row = states_gdf[states_gdf['name'] == state_name]
            if not state_row.empty:
                region_geometries[region.id] = {
                    'geometry': state_row.iloc[0].geometry,
                    'name': region.name
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
                    'name': region.name
                }
            else:
                print(f"Warning: Could not find boundary for country {region.name}")
        
        elif region.region_type == RegionType.REGION:
            # REGION types (islands, mountain ranges, etc.) don't have boundaries in Natural Earth
            # Skip them for adjacency computation
            print(f"Skipping REGION type '{region.name}' - no boundary data available")
        
        else:
            raise ValueError(f"Unknown region type for {region.id}: {region.region_type}")
    
    print(f"\nFound geometries for {len(region_geometries)} regions")
    
    # Compute adjacency
    adjacency = {}
    
    for region_id, region_data in region_geometries.items():
        print(f"\nProcessing {region_data['name']} ({region_id})...")
        adjacency[region_id] = {
            'north': [],
            'south': [],
            'east': [],
            'west': []
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
                
                # Determine direction
                other_centroid = other_geom.centroid
                direction = get_cardinal_direction(centroid, other_centroid)
                
                # Simplify to cardinal
                cardinal = simplify_to_cardinal(direction)
                
                if isinstance(cardinal, tuple):
                    # Diagonal - add to both directions
                    for d in cardinal:
                        if other_id not in adjacency[region_id][d]:
                            adjacency[region_id][d].append(other_id)
                            print(f"  {d}: {other_data['name']}")
                else:
                    # Pure cardinal
                    if other_id not in adjacency[region_id][cardinal]:
                        adjacency[region_id][cardinal].append(other_id)
                        print(f"  {cardinal}: {other_data['name']}")
        
        # Clean up empty directions
        adjacency[region_id] = {
            k: v if len(v) > 1 else (v[0] if len(v) == 1 else None)
            for k, v in adjacency[region_id].items()
        }
        # Remove None values
        adjacency[region_id] = {k: v for k, v in adjacency[region_id].items() if v is not None}
    
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
    
    print(f"\n✓ Computed adjacency for {len(adjacency)} regions")
    print(f"✓ Saved to {output_file}")
    print(f"✓ File sizes: {json_size:,} bytes (uncompressed), {gz_size:,} bytes (gzipped, {compression_ratio:.1f}% compression)")
    
    # Print summary
    total_connections = sum(
        len(neighbors) if isinstance(neighbors, list) else 1
        for region in adjacency.values()
        for neighbors in region.values()
    )
    print(f"✓ Total connections: {total_connections}")

if __name__ == '__main__':
    compute_adjacency()

