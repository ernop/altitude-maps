"""
Export region adjacency data for the viewer.
Outputs to generated/regions/region_adjacency.json
"""

import json
import gzip
from pathlib import Path
from src.region_adjacency import get_adjacency_data

def export_adjacency():
    """Export adjacency data to JSON file for viewer."""
    output_dir = Path('generated/regions')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / 'region_adjacency.json'
    output_file_gz = output_dir / 'region_adjacency.json.gz'
    
    adjacency_data = get_adjacency_data()
    
    # Write uncompressed JSON
    with open(output_file, 'w') as f:
        json.dump(adjacency_data, f, indent=2)
    
    # Write gzipped version
    with gzip.open(output_file_gz, 'wt', encoding='utf-8') as f:
        json.dump(adjacency_data, f, indent=2)
    
    # Get file sizes
    json_size = output_file.stat().st_size
    gz_size = output_file_gz.stat().st_size
    compression_ratio = (1 - gz_size / json_size) * 100
    
    print(f"Exported adjacency data for {len(adjacency_data)} regions to {output_file}")
    print(f"Total connections: {sum(len(neighbors) for neighbors in adjacency_data.values())}")
    print(f"File sizes: {json_size:,} bytes (uncompressed), {gz_size:,} bytes (gzipped, {compression_ratio:.1f}% compression)")

if __name__ == '__main__':
    export_adjacency()

