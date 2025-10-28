"""
Unified downloader CLI: one entrypoint for all regions.

Usage examples:
  # Auto-download (default) and process a region by name
  python download_unified.py california --process

  # Explicit auto mode and dataset choice
  python download_unified.py shikoku --auto --dataset AW3D30 --process

  # Custom bounds (if not in registry)
  python download_unified.py kamchatka --bounds 155 50 163 61 --process --dataset AW3D30

Behavior:
  - Resolves region id via centralized registry (src/regions_registry.py)
  - Auto mode (default on) uses OpenTopography API with best dataset per region
  - USA regions use state/country clipping; others clip by country when known
  - Runs processing pipeline and updates manifest so region appears in viewer
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

# No encoding handling needed - Python 3.7+ on Windows 10+ handles UTF-8 correctly by default
# If emojis don't display in PowerShell, that's a terminal display issue, not a Python issue

try:
    import requests  # noqa: F401  (ensure dependency present via existing downloaders)
    from tqdm import tqdm  # noqa: F401
except ImportError as e:
    print(f"Missing package: {e}", flush=True)
    print("Install with: pip install requests tqdm", flush=True)
    sys.exit(1)

# Local imports
from src.regions_registry import (
    get_region,
    list_regions,
    suggest_dataset_for_region,
    dataset_to_source_name,
)
from src.pipeline import run_pipeline
from load_settings import get_api_key as get_opentopo_api_key


def download_via_opentopography(
    region_id: str,
    bounds: Tuple[float, float, float, float],
    output_path: Path,
    dataset: str,
    api_key: Optional[str]
) -> bool:
    """Thin wrapper that uses the existing high-res downloader's logic."""
    try:
        from download_high_resolution import download_from_opentopography
    except Exception as e:
        print(f"❌ Cannot import downloader: {e}")
        return False

    if api_key is None:
        try:
            api_key = get_opentopo_api_key()
        except SystemExit:
            print("❌ OpenTopography API key required (settings.json or --api-key)")
            return False

    return download_from_opentopography(region_id, bounds, output_path, api_key, dataset)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description='Unified region downloader (auto by default)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python download_unified.py california --process
  python download_unified.py shikoku --dataset AW3D30 --process
  python download_unified.py kamchatka --bounds 155 50 163 61 --dataset AW3D30 --process

Notes:
  - Auto mode uses OpenTopography API and is enabled by default.
  - USA regions auto-clip to state/country boundaries.
  - Other regions clip to country when known; otherwise skip clipping.
        """
    )

    parser.add_argument('region', type=str, nargs='?', help='Region name (id) or custom label when using --bounds')
    parser.add_argument('--list', action='store_true', help='List available regions')
    parser.add_argument('--auto', action='store_true', help='Use automatic download (default: on)')
    parser.add_argument('--no-auto', dest='no_auto', action='store_true', help='Disable automatic download (manual only)')
    parser.add_argument('--dataset', type=str, default=None, help='Dataset for auto download (e.g., SRTMGL1, AW3D30, COP30)')
    parser.add_argument('--bounds', type=float, nargs=4, metavar=('WEST','SOUTH','EAST','NORTH'), help='Custom bounds if region not in registry')
    parser.add_argument('--api-key', type=str, help='OpenTopography API key (optional)')
    parser.add_argument('--data-dir', type=str, default='data/regions', help='Directory to save downloaded raw files')
    parser.add_argument('--process', action='store_true', help='Run processing pipeline after download')
    parser.add_argument('--target-pixels', type=int, default=800, help='Target size for viewer export (default: 800)')

    args = parser.parse_args()

    if args.list:
        print("\n📋 Unified Regions:", flush=True)
        print("="*70, flush=True)
        for entry in list_regions():
            print(f"{entry.id:20s} - {entry.name:30s}  [{entry.category}]  {entry.bounds}", flush=True)
        print("="*70, flush=True)
        return 0

    # Require region if not just listing
    if not args.region:
        print("❌ Error: region argument is required (unless using --list)", flush=True)
        print("Usage: python download_unified.py <region> [options]", flush=True)
        print("Or: python download_unified.py --list", flush=True)
        return 1

    # Determine auto mode (default on)
    auto_mode = True
    if args.no_auto:
        auto_mode = False
    elif args.auto:
        auto_mode = True

    # Resolve region
    region_id = args.region.strip().lower().replace(' ', '_').replace('-', '_')
    entry = get_region(region_id)

    if entry is None and not args.bounds:
        print(f"❌ Unknown region: {args.region}")
        print("   Tip: --list to see built-in regions, or provide --bounds for custom.")
        return 1

    if entry is None and args.bounds:
        # Create a synthetic entry for custom bounds
        from src.regions_registry import RegionEntry  # type: ignore
        entry = RegionEntry(
            id=region_id,
            name=args.region.replace('_', ' ').title(),
            bounds=tuple(args.bounds),  # type: ignore
            category='custom',
            country=None,
            boundary_type=None,
            boundary_name=None,
            recommended_dataset=args.dataset or 'SRTMGL1',
        )

    assert entry is not None

    # Decide dataset
    dataset = (args.dataset or suggest_dataset_for_region(entry)).upper()
    source_name = dataset_to_source_name(dataset)

    print(f"\n🗺️  Unified Downloader", flush=True)
    print(f"="*70, flush=True)
    print(f"Region:   {entry.name} ({entry.id})", flush=True)
    print(f"Bounds:   {entry.bounds}", flush=True)
    print(f"Category: {entry.category}", flush=True)
    print(f"Dataset:  {dataset} (source: {source_name})", flush=True)
    print(f"Auto:     {'ON' if auto_mode else 'OFF'}", flush=True)
    print(f"="*70, flush=True)

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    raw_path = data_dir / f"{entry.id}.tif"

    # Auto download
    if auto_mode:
        ok = download_via_opentopography(entry.id, entry.bounds, raw_path, dataset, args.api_key)
        if not ok:
            print("❌ Auto download failed")
            return 1
        print(f"\n✅ Download complete: {raw_path}")
    else:
        print("⏭️  Auto disabled. Expecting existing TIF at:")
        print(f"    {raw_path}")
        if not raw_path.exists():
            print("❌ File not found. Provide the TIF or enable --auto.")
            return 1

    # Optional processing pipeline
    if args.process:
        boundary_name = entry.boundary_name
        boundary_type = entry.boundary_type or 'country'
        skip_clip = boundary_name is None
        try:
            success, result = run_pipeline(
                raw_tif_path=raw_path,
                region_id=entry.id,
                source=source_name,
                boundary_name=boundary_name,
                boundary_type=boundary_type,
                target_pixels=args.target_pixels,
                skip_clip=skip_clip,
            )
        except Exception as e:
            print(f"❌ Pipeline error: {e}")
            return 1

        if not success:
            print("❌ Processing failed")
            return 1

        print("\n🎉 Ready. Launch viewer and select the region from the dropdown.")
        print("   python serve_viewer.py")
    else:
        print("\n💡 Skipped processing. Use --process to export for viewer.")

    return 0


if __name__ == "__main__":
    sys.exit(main())


