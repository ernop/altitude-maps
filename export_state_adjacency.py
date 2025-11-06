"""
Export US state adjacency data to JSON for the web viewer.

This script reads the adjacency data from src/us_state_adjacency.py
and exports it to a JSON file that the viewer can load.

NOTE: The exported data uses cardinal directions only (N, S, E, W).
Diagonal neighbors from the source data are split into their cardinal components.
"""

import json
import gzip
from pathlib import Path
from src.us_state_adjacency import US_STATE_ADJACENCY, get_neighbors_by_direction


def diagonal_to_cardinals(direction):
    """Convert diagonal direction to list of cardinal directions."""
    mapping = {
        'NE': ['N', 'E'],
        'NW': ['N', 'W'],
        'SE': ['S', 'E'],
        'SW': ['S', 'W'],
        'N': ['N'],
        'S': ['S'],
        'E': ['E'],
        'W': ['W']
    }
    return mapping.get(direction, [direction])

def export_adjacency_data():
    """Export state adjacency data to JSON format with cardinal directions only."""
    
    # Convert to JSON-friendly format with cardinal directions only
    adjacency_json = {}
    
    for state_id, neighbors in US_STATE_ADJACENCY.items():
        # Initialize with empty lists for all cardinal directions
        by_direction = {
            'N': [],
            'S': [],
            'E': [],
            'W': []
        }
        
        for neighbor in neighbors:
            # Convert direction to cardinal(s)
            cardinals = diagonal_to_cardinals(neighbor.direction)
            
            # Add neighbor to each cardinal direction
            for direction in cardinals:
                if direction in by_direction:
                    neighbor_data = {
                        'id': neighbor.state_id,
                        'name': neighbor.state_name
                    }
                    # Avoid duplicates
                    if neighbor_data not in by_direction[direction]:
                        by_direction[direction].append(neighbor_data)
        
        # Remove empty directions
        by_direction = {k: v for k, v in by_direction.items() if v}
        
        adjacency_json[state_id] = by_direction
    
    # Ensure output directory exists
    output_dir = Path('generated')
    output_dir.mkdir(exist_ok=True)
    
    # Write JSON file (uncompressed)
    output_path = output_dir / 'us_state_adjacency.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(adjacency_json, f, indent=2, ensure_ascii=False)
    
    # Write gzipped version
    output_path_gz = output_dir / 'us_state_adjacency.json.gz'
    with gzip.open(output_path_gz, 'wt', encoding='utf-8') as f:
        json.dump(adjacency_json, f, indent=2, ensure_ascii=False)
    
    # Get file sizes
    json_size = output_path.stat().st_size
    gz_size = output_path_gz.stat().st_size
    compression_ratio = (1 - gz_size / json_size) * 100 if json_size > 0 else 0
    
    print(f"Exported adjacency data for {len(adjacency_json)} states")
    print(f"Output: {output_path}")
    print(f"Gzipped: {output_path_gz}")
    print(f"File sizes: {json_size:,} bytes (uncompressed), {gz_size:,} bytes (gzipped, {compression_ratio:.1f}% compression)")
    
    # Print sample for verification
    print("\nSample (California):")
    if 'california' in adjacency_json:
        print(json.dumps(adjacency_json['california'], indent=2))


if __name__ == '__main__':
    export_adjacency_data()



