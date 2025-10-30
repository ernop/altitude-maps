"""
Regenerate the regions manifest to fix incorrect entries.

Run this after updating the manifest generation logic to clean up
entries like "new" (should be "new_mexico"), "north" (should be "north_dakota"), etc.
"""

import sys
from pathlib import Path
import json
from src.versioning import get_current_version

def update_manifest_directly(generated_dir: Path) -> bool:
    """Update manifest without relying on pipeline import."""
    try:
        # Import region categories from centralized config
        from src.regions_config import ALL_REGIONS

        manifest = {
            "version": get_current_version('export'),
            "regions": {}
        }
        
        # Find all JSON files (excluding manifests, metadata, and borders)
        for json_file in sorted(generated_dir.glob("*.json")):
            if (json_file.stem.endswith('_meta') or 
                json_file.stem.endswith('_borders') or 
                'manifest' in json_file.stem):
                continue
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract region_id: prefer from JSON, else infer from filename
                stem = json_file.stem
                # Known suffixes to strip
                for suffix in ['_srtm_30m_4000px_v2', '_srtm_30m_800px_v2', '_srtm_30m_v2', '_bbox_30m']:
                    if stem.endswith(suffix):
                        stem = stem[:-len(suffix)]
                        break
                
                region_id = data.get("region_id", stem)

                # ENFORCE: Only include regions explicitly configured upstream
                cfg = ALL_REGIONS.get(region_id)
                if not cfg:
                    print(f"      [SKIP] Unknown region not in regions_config: {region_id}", flush=True)
                    continue
                
                entry = {
                    "name": data.get("name", region_id.replace('_', ' ').title()),
                    "description": data.get("description", f"{data.get('name', region_id)} elevation data"),
                    "source": data.get("source", "unknown"),
                    "file": str(json_file.name),
                    "bounds": data.get("bounds", {}),
                    "stats": data.get("stats", {})
                }

                # Attach and REQUIRE category
                category_value = getattr(cfg, 'category', None)
                if not category_value:
                    print(f"      [SKIP] Region missing category in regions_config: {region_id}", flush=True)
                    continue
                entry["category"] = category_value

                manifest["regions"][region_id] = entry
            except Exception as e:
                print(f"      [!] Skipping {json_file.name}: {e}", flush=True)
                continue
        
        # Write manifest
        manifest_path = generated_dir / "regions_manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"      [+] Manifest updated ({len(manifest['regions'])} regions)", flush=True)
        return True
        
    except Exception as e:
        print(f"      [!] Warning: Could not update manifest: {e}", flush=True)
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

