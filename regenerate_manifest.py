"""
Regenerate the regions manifest to fix incorrect entries.

Run this after updating the manifest generation logic to clean up
entries like "new" (should be "new_mexico"), "north" (should be "north_dakota"), etc.
"""

import sys
from pathlib import Path
from typing import Dict, List
import json
from src.versioning import get_current_version

def update_manifest_directly(generated_dir: Path) -> bool:
    """
    Update manifest without relying on pipeline import.
    
    CRITICAL RULES:
    1. ONLY regions from region_config.py that HAVE DATA FILES are included
    2. ALL regions MUST have a region_type parameter (enforced)
    3. Region info (name, description, regionType) comes ONLY from region_config
    4. JSON manifest uses camelCase "regionType" (not snake_case "region_type")
    5. JSON files only provide: file path, bounds, stats, source
    6. Regions without data files are SKIPPED (not included in manifest)
    """
    try:
        # Import region categories from centralized config
        from src.region_config import ALL_REGIONS

        manifest = {
            "version": get_current_version('export'),
            "regions": {}
        }
        
        # Build index of JSON files by region_id for quick lookup
        json_files_by_region: Dict[str, List[Path]] = {}
        for json_file in sorted(generated_dir.glob("*.json")):
            if (json_file.stem.endswith('_meta') or 
                json_file.stem.endswith('_borders') or 
                'manifest' in json_file.stem):
                continue
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract region_id: prefer from JSON, else infer from filename
                region_id = data.get("region_id")
                if not region_id:
                    stem = json_file.stem
                    # Known suffixes to strip (order matters - check longer patterns first)
                    for suffix in [
                        '_srtm_30m_4000px_v2', '_srtm_30m_2048px_v2', '_srtm_30m_800px_v2',
                        '_srtm_90m_2048px_v2', '_usa_3dep_2048px_v2',
                        '_srtm_30m_v2', '_bbox_30m'
                    ]:
                        if stem.endswith(suffix):
                            stem = stem[:-len(suffix)]
                            break
                    region_id = stem
                
                if region_id:
                    if region_id not in json_files_by_region:
                        json_files_by_region[region_id] = []
                    json_files_by_region[region_id].append(json_file)
            except Exception:
                continue
        
        # Iterate ONLY through regions configured in region_config.py
        for region_id, cfg in sorted(ALL_REGIONS.items()):
            # ENFORCE: region_type is MANDATORY
            if not hasattr(cfg, 'region_type') or cfg.region_type is None:
                print(f"      [SKIP] Region '{region_id}' missing region_type in region_config - skipping", flush=True)
                continue
            
            # Find matching JSON file(s) - ONLY accept v2 format (NO FALLBACKS)
            json_file = None
            json_data = None
            if region_id in json_files_by_region:
                candidates = json_files_by_region[region_id]
                
                # Filter to ONLY v2 files with proper version field
                v2_candidates = []
                for candidate_file in candidates:
                    try:
                        with open(candidate_file, 'r', encoding='utf-8') as f:
                            candidate_data = json.load(f)
                        
                        # CRITICAL: Only accept files with version field
                        # NO SILENT FALLBACKS to old format files
                        version = candidate_data.get('version')
                        if version == 'export_v2':
                            v2_candidates.append((candidate_file, candidate_data))
                        else:
                            # Warn about files without proper version
                            print(f"      [!] SKIP {region_id}: {candidate_file.name} (version={version}, expected 'export_v2')", flush=True)
                    except Exception as e:
                        print(f"      [!] SKIP {region_id}: {candidate_file.name} (failed to load: {e})", flush=True)
                        continue
                
                # If no v2 files found, skip this region entirely (fail fast)
                if not v2_candidates:
                    if candidates:
                        print(f"      [X] SKIP {region_id}: No v2 files found (had {len(candidates)} non-v2 files)", flush=True)
                    continue
                
                # Warn if multiple v2 files exist (should not happen in normal operation)
                if len(v2_candidates) > 1:
                    print(f"      [!] WARNING {region_id}: Multiple v2 files found:", flush=True)
                    for cf, _ in v2_candidates:
                        print(f"          - {cf.name} (modified: {cf.stat().st_mtime})", flush=True)
                    # Pick newest by modification time
                    v2_candidates.sort(key=lambda x: x[0].stat().st_mtime, reverse=True)
                    print(f"          Selected: {v2_candidates[0][0].name} (newest)", flush=True)
                
                # Use the v2 file (first if only one, newest if multiple)
                json_file = v2_candidates[0][0]
                json_data = v2_candidates[0][1]
            
            # SKIP regions without data files - only include regions with actual data
            if not json_file or not json_data:
                continue
            
            # Build entry using ONLY info from region_config
            entry = {
                "name": cfg.name,  # FROM CONFIG ONLY
                "description": cfg.description or f"{cfg.name} elevation data",  # FROM CONFIG ONLY
                "regionType": str(cfg.region_type),  # FROM CONFIG ONLY, REQUIRED (camelCase for JSON)
            }
            
            # Attach file/bounds/stats/source from JSON (guaranteed to exist since we skip if missing)
            entry["file"] = str(json_file.name)
            if "bounds" in json_data:
                entry["bounds"] = json_data["bounds"]
            if "stats" in json_data:
                entry["stats"] = json_data["stats"]
            if "source" in json_data:
                entry["source"] = json_data["source"]
            
            manifest["regions"][region_id] = entry
        
        # Write manifest (JSON)
        manifest_path = generated_dir / "regions_manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        print(f"      [+] Wrote JSON manifest: {manifest_path}", flush=True)

        # Also write gzip-compressed version (required for web viewer)
        try:
            import gzip
            gzip_path = manifest_path.with_suffix('.json.gz')
            with open(manifest_path, 'rb') as f_in:
                with gzip.open(gzip_path, 'wb', compresslevel=9) as f_out:
                    f_out.writelines(f_in)
            print(f"      [+] Wrote gzipped manifest: {gzip_path}", flush=True)
        except Exception as gz_err:
            print(f"      [!] Warning: Could not write gzip manifest: {gz_err}", flush=True)
        
        print(f"      [+] Manifest updated ({len(manifest['regions'])} regions with data files)", flush=True)
        
        # Automatically update adjacency data if needed
        try:
            import sys
            from pathlib import Path
            # Ensure root directory is in path
            root_dir = Path(__file__).parent
            if str(root_dir) not in sys.path:
                sys.path.insert(0, str(root_dir))
            from compute_adjacency import update_adjacency_if_needed
            update_adjacency_if_needed(force=False)
        except Exception as adj_err:
            print(f"      [!] Warning: Could not update adjacency: {adj_err}", flush=True)
            # Don't fail manifest update if adjacency fails
        
        return True
        
    except Exception as e:
        print(f"      [!] Warning: Could not update manifest: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False

def main():
    generated_dir = Path("generated/regions")
    
    if not generated_dir.exists():
        print(f"[X] Directory not found: {generated_dir}", flush=True)
        return 1
    
    print("[*] Regenerating regions manifest...", flush=True)
    print(f"   Scanning: {generated_dir}", flush=True)
    
    success = update_manifest_directly(generated_dir)
    
    if success:
        print("\n[+] Manifest regenerated successfully!", flush=True)
        print("   File: generated/regions/regions_manifest.json", flush=True)
        print("\n[*] Refresh the viewer to see corrected region names.", flush=True)
    else:
        print("\n[X] Failed to regenerate manifest", flush=True)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

