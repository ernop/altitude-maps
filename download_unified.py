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
        print(f" Cannot import downloader: {e}")
        return False

    if api_key is None:
        try:
            api_key = get_opentopo_api_key()
        except SystemExit:
            print(" OpenTopography API key required (settings.json or --api-key)")
            return False

    return download_from_opentopography(region_id, bounds, output_path, api_key, dataset)


def main() -> int:
    import argparse
    import sys
    from pathlib import Path
    
    # Import central config
    sys.path.insert(0, str(Path(__file__).parent))
    from src.config import DEFAULT_TARGET_PIXELS

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
    parser.add_argument('--process', action='store_true', help='Run processing pipeline after download (default: on)')
    parser.add_argument('--no-process', action='store_true', help='Disable processing (download only)')
    parser.add_argument('--target-pixels', type=int, default=DEFAULT_TARGET_PIXELS, 
                       help=f'Target size for viewer export (default: {DEFAULT_TARGET_PIXELS})')

    args = parser.parse_args()
    # Default to processing unless explicitly disabled
    if not hasattr(args, 'process'):
        args.process = True
    if args.no_process:
        args.process = False
    else:
        # Ensure default-on when --process not provided
        if not args.process:
            args.process = True

    if args.list:
        print("\n📋 Unified Regions:", flush=True)
        print("="*100, flush=True)
        # Paths to check for existing data
        from src.config import RAW_DATA_DIRS, GENERATED_DATA_DIR
        raw_dirs = [Path(p) for p in RAW_DATA_DIRS]
        gen_dir = Path(GENERATED_DATA_DIR)

        # Header
        print(f"{'ID':20s}  {'Name':30s}  {'Category':12s}  {'RAW':3s}  {'EXPORTED':8s}  Bounds", flush=True)
        print("-"*100, flush=True)

        for entry in list_regions():
            # Check raw presence in any known raw directory
            has_raw = any((d / f"{entry.id}.tif").exists() for d in raw_dirs)

            # Check exported presence in generated directory
            has_exported = False
            if gen_dir.exists():
                for jf in gen_dir.glob(f"{entry.id}_*.json"):
                    stem = jf.stem
                    if stem.endswith('_meta') or stem.endswith('_borders') or 'manifest' in stem:
                        continue
                    has_exported = True
                    break

            raw_mark = '✔' if has_raw else ' '
            exp_mark = '✔' if has_exported else ' '

            print(
                f"{entry.id:20s}  {entry.name:30s}  {entry.category:12s}  {raw_mark:3s}  {exp_mark:8s}  {entry.bounds}",
                flush=True
            )

        print("="*100, flush=True)
        print("Legend: RAW = local GeoTIFF present, EXPORTED = viewer JSON present", flush=True)
        return 0

    # Require region if not just listing
    if not args.region:
        print(" Error: region argument is required (unless using --list)", flush=True)
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
        print(f" Unknown region: {args.region}")
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

    # Auto-switch to COP30 for regions outside SRTM coverage (~60°N to 56°S)
    west, south, east, north = entry.bounds
    if (north > 60.0 or south < -56.0) and dataset in {"SRTMGL1", "SRTMGL3", "NASADEM"}:
        print("\n High-latitude region detected. Switching dataset to COP30 for coverage.")
        dataset = "COP30"

    source_name = dataset_to_source_name(dataset)

    print(f"\n🗺  Unified Downloader", flush=True)
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

    # If a local TIF already exists (e.g., 10m USGS 3DEP), prefer it and skip auto download
    if raw_path.exists():
        print(f"\n📦 Found existing raw file: {raw_path}")
        print("   Using local file and skipping auto download.")
        auto_mode = False

    # Auto download
    if auto_mode:
        ok = download_via_opentopography(entry.id, entry.bounds, raw_path, dataset, args.api_key)
        if not ok:
            print(" Auto download failed")
            return 1
        print(f"\n Download complete: {raw_path}")
    else:
        print("  Auto disabled. Expecting existing TIF at:")
        print(f"    {raw_path}")
        if not raw_path.exists():
            print(" File not found. Provide the TIF or enable --auto.")
            return 1

    # Suggest higher target pixels for very small regions if user didn't override
    try:
        from src.config import DEFAULT_TARGET_PIXELS
    except Exception:
        DEFAULT_TARGET_PIXELS = 2048  # safe fallback

    import math
    mean_lat = (north + south) / 2.0
    approx_km_per_deg_lon = 111.0 * abs(math.cos(math.radians(mean_lat)))
    approx_km_per_deg_lat = 111.0
    area_km2 = max((east - west), 0) * approx_km_per_deg_lon * max((north - south), 0) * approx_km_per_deg_lat

    if args.target_pixels == DEFAULT_TARGET_PIXELS and area_km2 <= 400:
        suggested_pixels = 4096
        print(f"\n Small region detected (~{area_km2:,.0f} km²). Suggesting higher target-pixels: {suggested_pixels}.")
        args.target_pixels = suggested_pixels

    # Validate raw file before processing (ensure proper GeoTIFF)
    try:
        from ensure_region import validate_geotiff  # reuse existing validator
    except Exception:
        validate_geotiff = None

    if validate_geotiff is not None:
        is_valid = validate_geotiff(raw_path, check_data=True)
        if not is_valid:
            print("\n Raw file is not a valid GeoTIFF or cannot be read:")
            print(f"   {raw_path}")
            print("\nFix suggestions:")
            print("  - If this is a ZIP or folder download, extract the actual .tif first")
            print("  - Convert to GeoTIFF with gdal_translate (keeps georeference):")
            print("    gdal_translate -of GTiff input.ext data/regions/" + entry.id + ".tif")
            print("  - Or re-download via auto mode (will fetch 30m):")
            print("    python download_unified.py " + entry.id)
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
            print(f" Pipeline error: {e}")
            return 1

        if not success:
            print(" Processing failed")
            return 1

        print("\n🎉 Ready. Launch viewer and select the region from the dropdown.")
        print("   python serve_viewer.py")
    else:
        print("\n Skipped processing. Use --no-process to skip; default is to process.")

    return 0


if __name__ == "__main__":
    sys.exit(main())


