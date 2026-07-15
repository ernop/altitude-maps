#!/usr/bin/env python3
"""
Snapshot a git ref of the viewer into snapshots/<name>/ so it can be served
side by side with the working tree for before/after comparison.

Usage:
    python snapshot_baseline.py                 # snapshot master -> snapshots/baseline/
    python snapshot_baseline.py v1.382-tag      # snapshot a tag or any ref
    python snapshot_baseline.py master --name old

After snapshotting, the untouched old viewer is available at:
    http://localhost:8001/snapshots/<name>/interactive_viewer_advanced.html
and the working-tree viewer at:
    http://localhost:8001/interactive_viewer_advanced.html

Open compare.html to view both side by side with mirrored camera state.

The snapshot needs region data. This script links the repository's
generated/ directory into the snapshot (symlink, or directory junction on
Windows). If neither is possible, it copies generated/regions/ instead.
"""

import argparse
import shutil
import subprocess
import sys
import tarfile
import io
import os
import platform
from pathlib import Path

ROOT = Path(__file__).parent
SNAPSHOTS_DIR = ROOT / 'snapshots'


def git_archive(ref: str, dest: Path) -> None:
    """Extract a git ref into dest using git archive (no git metadata)."""
    result = subprocess.run(
        ['git', 'archive', '--format=tar', ref],
        cwd=ROOT, capture_output=True,
    )
    if result.returncode != 0:
        print(f"ERROR: git archive failed for ref '{ref}':")
        print(result.stderr.decode('utf-8', errors='replace'))
        sys.exit(1)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as tar:
        tar.extractall(dest)


def link_data(snapshot_dir: Path) -> None:
    """Make generated/ visible inside the snapshot: symlink, junction, or copy."""
    target = ROOT / 'generated'
    link = snapshot_dir / 'generated'

    if not target.exists():
        print("WARNING: generated/ does not exist yet; run fetch_sample_data.py first.")
        return
    if link.exists() or link.is_symlink():
        print(f"  data link already present: {link}")
        return

    try:
        os.symlink(target, link, target_is_directory=True)
        print(f"  symlinked {link} -> {target}")
        return
    except OSError:
        pass

    if platform.system() == 'Windows':
        # Directory junctions do not require developer mode or admin rights
        result = subprocess.run(
            ['cmd', '/c', 'mklink', '/J', str(link), str(target)],
            capture_output=True,
        )
        if result.returncode == 0:
            print(f"  created junction {link} -> {target}")
            return

    print("  symlink unavailable; copying generated/regions/ (may take a moment)")
    shutil.copytree(target / 'regions', link / 'regions')
    print(f"  copied region data into {link}")


def read_version(snapshot_dir: Path) -> str:
    js = snapshot_dir / 'js' / 'viewer-advanced.js'
    if js.exists():
        import re
        m = re.search(r"const VIEWER_VERSION = '([^']+)';", js.read_text(encoding='utf-8'))
        if m:
            return m.group(1)
    return 'unknown'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('ref', nargs='?', default='master', help='git ref to snapshot (default: master)')
    parser.add_argument('--name', default='baseline', help='snapshot directory name (default: baseline)')
    parser.add_argument('--force', action='store_true', help='replace an existing snapshot of the same name')
    args = parser.parse_args()

    snapshot_dir = SNAPSHOTS_DIR / args.name
    if snapshot_dir.exists():
        if not args.force:
            print(f"ERROR: {snapshot_dir} already exists. Use --force to replace it.")
            return 1
        shutil.rmtree(snapshot_dir)

    print(f"Snapshotting '{args.ref}' -> {snapshot_dir}")
    git_archive(args.ref, snapshot_dir)
    link_data(snapshot_dir)

    version = read_version(snapshot_dir)
    print(f"\nSnapshot complete (viewer v{version}).")
    print(f"  Old:     http://localhost:8001/snapshots/{args.name}/interactive_viewer_advanced.html")
    print(f"  New:     http://localhost:8001/interactive_viewer_advanced.html")
    print(f"  Compare: http://localhost:8001/compare.html?region=california")
    return 0


if __name__ == '__main__':
    sys.exit(main())
