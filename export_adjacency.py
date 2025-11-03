"""
Export region adjacency data for the viewer.
Outputs to generated/region_adjacency.json
"""

import json
from pathlib import Path
from src.region_adjacency import get_adjacency_data

def export_adjacency():
    """Export adjacency data to JSON file for viewer."""
    output_dir = Path('generated')
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / 'region_adjacency.json'
    
    adjacency_data = get_adjacency_data()
    
    with open(output_file, 'w') as f:
        json.dump(adjacency_data, f, indent=2)
    
    print(f"Exported adjacency data for {len(adjacency_data)} regions to {output_file}")
    print(f"Total connections: {sum(len(neighbors) for neighbors in adjacency_data.values())}")

if __name__ == '__main__':
    export_adjacency()

