"""
Fetch sample region data from the production deployment.

A fresh checkout has no elevation data (data/ and generated/ are gitignored),
so the viewer has nothing to display. This script downloads the regions
manifest, the adjacency file, and one or more region datasets from the live
site so you can run the viewer locally without running the full pipeline.

Usage:
    python fetch_sample_data.py                    # default set (california, estonia)
    python fetch_sample_data.py oregon japan       # specific regions
    python fetch_sample_data.py --list             # list available region ids
    python fetch_sample_data.py --all              # everything (hundreds of MB)

Then serve the viewer:
    python serve_viewer.py
    # open http://localhost:8001/interactive_viewer_advanced.html
"""

import argparse
import gzip
import json
import sys
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = 'https://fuseki.net/altitude-maps'
DEFAULT_REGIONS = ['california', 'estonia']
OUTPUT_DIR = Path('generated/regions')


def download(url: str, dest: Path) -> int:
    """Download url to dest. Returns byte count."""
    request = urllib.request.Request(url, headers={'User-Agent': 'altitude-maps-dev-fetch'})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return len(data)


def load_manifest(base_url: str, force: bool = False) -> dict:
    manifest_path = OUTPUT_DIR / 'regions_manifest.json.gz'
    if force or not manifest_path.exists():
        size = download(f'{base_url}/generated/regions/regions_manifest.json.gz', manifest_path)
        print(f'  regions_manifest.json.gz ({size / 1024:.0f} KB)')
    with gzip.open(manifest_path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description='Download sample region data from production.')
    parser.add_argument('regions', nargs='*', default=None,
                        help=f'Region ids to fetch (default: {" ".join(DEFAULT_REGIONS)})')
    parser.add_argument('--all', action='store_true', help='Fetch every region in the manifest')
    parser.add_argument('--list', action='store_true', help='List available region ids and exit')
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL,
                        help=f'Deployment base URL (default: {DEFAULT_BASE_URL})')
    args = parser.parse_args()

    base_url = args.base_url.rstrip('/')

    print(f'Fetching manifest from {base_url} ...')
    manifest = load_manifest(base_url, force=True)
    regions = manifest.get('regions', {})
    if not regions:
        print('Manifest contains no regions; aborting.')
        return 1

    if args.list:
        for region_id in sorted(regions):
            info = regions[region_id]
            print(f'  {region_id:30s} {info.get("name", "")} [{info.get("regionType", "?")}]')
        return 0

    adjacency_path = OUTPUT_DIR / 'region_adjacency.json.gz'
    try:
        size = download(f'{base_url}/generated/regions/region_adjacency.json.gz', adjacency_path)
        print(f'  region_adjacency.json.gz ({size / 1024:.0f} KB)')
    except Exception as e:
        print(f'  Warning: could not fetch adjacency data: {e}')

    wanted = list(regions) if args.all else (args.regions or DEFAULT_REGIONS)
    failures = 0
    for region_id in wanted:
        info = regions.get(region_id)
        if not info:
            print(f'  {region_id}: not in manifest, skipping (use --list to see ids)')
            failures += 1
            continue
        filename = info.get('file')
        if not filename:
            print(f'  {region_id}: manifest entry has no file, skipping')
            failures += 1
            continue
        gz_name = filename if filename.endswith('.gz') else filename + '.gz'
        dest = OUTPUT_DIR / gz_name
        if dest.exists():
            print(f'  {region_id}: already present ({dest.name})')
            continue
        try:
            size = download(f'{base_url}/generated/regions/{gz_name}', dest)
            print(f'  {region_id}: {gz_name} ({size / (1024 * 1024):.1f} MB)')
        except Exception as e:
            print(f'  {region_id}: download failed: {e}')
            failures += 1

    print('Done. Run "python serve_viewer.py" and open '
          'http://localhost:8001/interactive_viewer_advanced.html')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
