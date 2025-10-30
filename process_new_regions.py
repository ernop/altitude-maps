"""
Process new region raster files for the interactive web viewer.
This script:
1. Extracts tar.gz files from rasters/
2. Processes TIF files
3. Exports to JSON for web viewer
4. Updates regions manifest
"""
import sys
import json
import tarfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import re

try:
    from export_for_web_viewer import export_elevation_data
except ImportError as e:
    print(f"[X] Error importing modules: {e}")
    sys.exit(1)


def extract_tar_files(rasters_dir: Path) -> List[Path]:
    """
    Extract all tar.gz files in the rasters directory.
    Returns list of extracted directories.
    """
    print("\n[*] Extracting tar.gz files...")
    extracted_dirs = []
    
    tar_files = list(rasters_dir.glob("*.tar.gz"))
    if not tar_files:
        print("   No tar.gz files found in rasters/")
        return []
    
    for tar_path in tar_files:
        print(f"\n   Processing: {tar_path.name}")
        
        # Create extraction directory
        extract_dir = rasters_dir / tar_path.stem.replace('.tar', '')
        
        if extract_dir.exists():
            print(f"   [!] Directory already exists: {extract_dir.name}, skipping extraction")
            extracted_dirs.append(extract_dir)
            continue
        
        try:
            with tarfile.open(tar_path, 'r:gz') as tar:
                # Get list of members
                members = tar.getmembers()
                print(f"   Extracting {len(members)} files...")
                
                # Extract all files
                tar.extractall(path=extract_dir)
                print(f"   [+] Extracted to: {extract_dir.name}")
                extracted_dirs.append(extract_dir)
                
        except Exception as e:
            print(f"   [X] Error extracting {tar_path.name}: {e}")
            continue
    
    return extracted_dirs


def find_tif_files(directory: Path) -> List[Path]:
    """Find all TIF/TIFF files recursively in a directory."""
    tif_files = []
    tif_files.extend(directory.rglob("*.tif"))
    tif_files.extend(directory.rglob("*.tiff"))
    tif_files.extend(directory.rglob("*.TIF"))
    tif_files.extend(directory.rglob("*.TIFF"))
    return tif_files


def infer_region_name(tif_path: Path) -> str:
    """
    Infer region name from file path.
    Looks for common region identifiers.
    """
    path_str = str(tif_path).lower()
    
    # Common region patterns
    regions = {
        'japan': ['japan', 'jpn', 'nihon'],
        'switzerland': ['switzerland', 'swiss', 'che'],
        'germany': ['germany', 'deu', 'deutschland'],
        'france': ['france', 'fra'],
        'italy': ['italy', 'ita'],
        'spain': ['spain', 'esp'],
        'uk': ['uk', 'united_kingdom', 'gbr'],
        'canada': ['canada', 'can'],
        'mexico': ['mexico', 'mex'],
        'brazil': ['brazil', 'bra'],
        'australia': ['australia', 'aus'],
        'new_zealand': ['new_zealand', 'nzl'],
        'india': ['india', 'ind'],
        'china': ['china', 'chn'],
        'russia': ['russia', 'rus'],
    }
    
    for region_id, patterns in regions.items():
        for pattern in patterns:
            if pattern in path_str:
                return region_id
    
    # Fall back to parent directory name or filename
    parent_name = tif_path.parent.name.lower()
    if parent_name != 'rasters':
        # Clean up the name
        clean_name = re.sub(r'[^a-z0-9_]', '_', parent_name)
        return clean_name
    
    # Use filename without extension
    clean_name = re.sub(r'[^a-z0-9_]', '_', tif_path.stem.lower())
    return clean_name


def get_region_display_name(region_id: str) -> str:
    """Get a nice display name for a region."""
    name_map = {
        'japan': 'Japan',
        'switzerland': 'Switzerland',
        'germany': 'Germany',
        'france': 'France',
        'italy': 'Italy',
        'spain': 'Spain',
        'uk': 'United Kingdom',
        'canada': 'Canada',
        'mexico': 'Mexico',
        'brazil': 'Brazil',
        'australia': 'Australia',
        'new_zealand': 'New Zealand',
        'india': 'India',
        'china': 'China',
        'russia': 'Russia',
    }
    
    return name_map.get(region_id, region_id.replace('_', ' ').title())


def calculate_appropriate_size(tif_path: Path) -> int:
    """
    Calculate appropriate max dimension for web viewer.
    Returns 0 for full resolution or a downsampling size.
    """
    try:
        import rasterio
        with rasterio.open(tif_path) as src:
            height, width = src.shape
            total_pixels = height * width
            
            # Rough sizing guidelines:
            # < 1M pixels: full resolution
            # 1-4M pixels: downsample to 2000
            # 4-16M pixels: downsample to 1500
            # 16-64M pixels: downsample to 1000
            # > 64M pixels: downsample to 800
            
            if total_pixels < 1_000_000:
                return 0  # Full resolution
            elif total_pixels < 4_000_000:
                return 2000
            elif total_pixels < 16_000_000:
                return 1500
            elif total_pixels < 64_000_000:
                return 1000
            else:
                return 800
                
    except Exception as e:
        print(f"   [!] Could not determine size, using default: {e}")
        return 1000  # Safe default


def process_tif_file(tif_path: Path, output_dir: Path, region_id: str = None) -> Dict[str, Any]:
    """
    Process a single TIF file and export for web viewer.
    Returns region metadata or None if processing failed.
    """
    if region_id is None:
        region_id = infer_region_name(tif_path)
    
    print(f"\n[*] Processing: {tif_path.name}")
    print(f"   Region ID: {region_id}")
    
    # Determine appropriate size
    max_size = calculate_appropriate_size(tif_path)
    print(f"   Max dimension: {max_size if max_size > 0 else 'FULL RESOLUTION'}")
    
    # Export to JSON
    output_path = output_dir / f"{region_id}.json"
    
    try:
        export_data = export_elevation_data(
            str(tif_path),
            str(output_path),
            max_size=max_size
        )
        
        # Create region metadata
        region_meta = {
            "name": get_region_display_name(region_id),
            "description": f"Elevation data for {get_region_display_name(region_id)}",
            "bounds": [
                export_data["bounds"]["left"],
                export_data["bounds"]["bottom"],
                export_data["bounds"]["right"],
                export_data["bounds"]["top"]
            ],
            "file": f"{region_id}.json"
        }
        
        return region_meta
        
    except Exception as e:
        print(f"\n[X] Error processing {tif_path.name}: {e}")
        import traceback
        traceback.print_exc()
        return None


def update_regions_manifest(manifest_path: Path, new_regions: Dict[str, Dict[str, Any]]):
    """
    Update the regions manifest with new regions.
    """
    print(f"\n[*] Updating regions manifest...")
    
    # Load existing manifest
    if manifest_path.exists():
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
    else:
        manifest = {
            "version": "1.0",
            "regions": {}
        }
    
    # Add new regions, attaching category from centralized config when available
    try:
        from src.regions_config import get_region
    except Exception:
        get_region = None

    for rid, info in new_regions.items():
        entry = dict(info)
        if get_region is not None:
            try:
                cfg = get_region(rid) if callable(get_region) else None
                if cfg and getattr(cfg, 'category', None):
                    entry["category"] = getattr(cfg, 'category')
            except Exception:
                pass
        manifest["regions"][rid] = entry
    manifest["generated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Save updated manifest
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"   [+] Manifest updated with {len(new_regions)} new region(s)")
    print(f"   Total regions: {len(manifest['regions'])}")


def main():
    """Main processing function."""
    print("=" * 70)
    print("Processing New Regions for Interactive Web Viewer")
    print("=" * 70)
    
    # Setup paths
    project_root = Path(__file__).parent
    rasters_dir = project_root / "rasters"
    output_dir = project_root / "generated" / "regions"
    manifest_path = output_dir / "regions_manifest.json"
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Extract tar files
    extracted_dirs = extract_tar_files(rasters_dir)
    
    # Step 2: Find all TIF files
    print("\n[*] Searching for TIF files...")
    all_tif_files = []
    
    # Check extracted directories
    for extracted_dir in extracted_dirs:
        tifs = find_tif_files(extracted_dir)
        print(f"   Found {len(tifs)} TIF file(s) in {extracted_dir.name}")
        all_tif_files.extend(tifs)
    
    # Also check rasters_dir directly
    direct_tifs = [f for f in rasters_dir.glob("*.tif") if f.is_file()]
    direct_tifs.extend([f for f in rasters_dir.glob("*.tiff") if f.is_file()])
    if direct_tifs:
        print(f"   Found {len(direct_tifs)} TIF file(s) in rasters/")
        all_tif_files.extend(direct_tifs)
    
    if not all_tif_files:
        print("\n[X] No TIF files found!")
        return 1
    
    print(f"\n[*] Total TIF files to process: {len(all_tif_files)}")
    
    # Step 3: Process each TIF file
    new_regions = {}
    seen_regions = set()
    
    for tif_path in all_tif_files:
        region_id = infer_region_name(tif_path)
        
        # Skip if we've already processed a file with this region_id
        if region_id in seen_regions:
            print(f"\n[>] Skipping duplicate: {tif_path.name} (already have {region_id})")
            continue
        
        seen_regions.add(region_id)
        
        # Skip if already processed
        output_json = output_dir / f"{region_id}.json"
        if output_json.exists():
            print(f"\n[>] Skipping {region_id} (already exists)")
            continue
        
        region_meta = process_tif_file(tif_path, output_dir, region_id)
        if region_meta:
            new_regions[region_id] = region_meta
    
    # Step 4: Update manifest
    if new_regions:
        update_regions_manifest(manifest_path, new_regions)
        
        print("\n" + "=" * 70)
        print("[+] Processing Complete!")
        print("=" * 70)
        print(f"\nProcessed regions:")
        for region_id, meta in new_regions.items():
            print(f"   * {meta['name']} ({region_id})")
        
        print(f"\n[*] Output location: {output_dir}")
        print(f"[*] Manifest: {manifest_path}")
        
        return 0
    else:
        print("\n[!] No new regions were processed successfully.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

