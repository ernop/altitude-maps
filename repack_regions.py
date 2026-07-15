"""
Repack existing region exports with rounded elevation values.

Older exports serialized raw float32 elevations through float64, producing
values like 24.239999771118164 in the JSON. That roughly triples file size for
non-integer DEMs (compare estonia at ~10 MB gz vs california at ~2.7 MB gz).
New exports round to 1 cm at export time (see src/pipeline.py); this script
applies the same rounding to files that already exist so they do not need a
full pipeline re-run.

Usage:
    python repack_regions.py                          # repack all region files
    python repack_regions.py estonia_srtm_30m_2048px_v2.json.gz
    python repack_regions.py --dry-run                # report sizes only

Notes:
- Rewrites the .json.gz in place; stats/bounds/dimensions are unchanged.
- Skips manifest and adjacency files automatically.
- After repacking, redeploy the changed files. The viewer's cache fingerprint
  comes from manifest stats, which do not change, so clients that cached the
  old file will keep it until the manifest stats change or the cache expires;
  the content is identical apart from rounding, so that is acceptable.
"""

import argparse
import gzip
import json
import sys
from pathlib import Path

REGIONS_DIR = Path('generated/regions')
SKIP_NAMES = {'regions_manifest.json.gz', 'region_adjacency.json.gz'}


def round_elevation(elevation, decimals=2):
    changed = False
    for row in elevation:
        for i, v in enumerate(row):
            if v is not None:
                r = round(v, decimals)
                if r != v:
                    row[i] = r
                    changed = True
    return changed


def repack_file(path: Path, dry_run: bool) -> None:
    original_size = path.stat().st_size
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        data = json.load(f)

    if 'elevation' not in data:
        print(f'  {path.name}: no elevation key, skipping')
        return

    changed = round_elevation(data['elevation'])
    if not changed:
        print(f'  {path.name}: already rounded ({original_size / (1024 * 1024):.1f} MB)')
        return

    if dry_run:
        print(f'  {path.name}: would repack ({original_size / (1024 * 1024):.1f} MB)')
        return

    body = json.dumps(data, separators=(',', ':')).encode('utf-8')
    tmp_path = path.with_suffix('.tmp')
    with gzip.open(tmp_path, 'wb', compresslevel=9) as f:
        f.write(body)
    tmp_path.replace(path)

    new_size = path.stat().st_size
    saved_pct = (1 - new_size / original_size) * 100
    print(f'  {path.name}: {original_size / (1024 * 1024):.1f} MB -> '
          f'{new_size / (1024 * 1024):.1f} MB ({saved_pct:.0f}% smaller)')

    # Keep the uncompressed sibling in sync if one exists
    json_sibling = path.with_suffix('')  # foo.json.gz -> foo.json
    if json_sibling.suffix == '.json' and json_sibling.exists():
        json_sibling.write_bytes(body)


def main() -> int:
    parser = argparse.ArgumentParser(description='Round elevations in existing region exports.')
    parser.add_argument('files', nargs='*', help='Specific .json.gz files (default: all regions)')
    parser.add_argument('--dry-run', action='store_true', help='Report without rewriting')
    args = parser.parse_args()

    if args.files:
        paths = [Path(f) if Path(f).exists() else REGIONS_DIR / f for f in args.files]
    else:
        paths = sorted(p for p in REGIONS_DIR.glob('*.json.gz') if p.name not in SKIP_NAMES)

    if not paths:
        print(f'No region files found in {REGIONS_DIR}/')
        return 1

    for path in paths:
        if not path.exists():
            print(f'  {path}: not found')
            continue
        repack_file(path, args.dry_run)
    return 0


if __name__ == '__main__':
    sys.exit(main())
