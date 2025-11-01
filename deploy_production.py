#!/usr/bin/env python3
"""
Production deployment script - prepares and uploads all viewer files.

This script:
1. Regenerates the regions manifest (fresh timestamp)
2. Updates version cache busters in HTML files
3. Outputs rsync command for uploading everything

Usage:
    python deploy_production.py
    # Then run the rsync command it outputs
"""

import sys
import subprocess
from typing import Optional

def regenerate_manifest() -> bool:
    """Regenerate the regions manifest to ensure it's fresh."""
    print("[*] Regenerating regions manifest...")
    result = subprocess.run(
        [sys.executable, "regenerate_manifest.py"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"[X] Failed to regenerate manifest:")
        print(result.stderr)
        return False
    print(result.stdout)
    return True

def update_version_cache_busters() -> bool:
    """Update version cache busters in HTML files."""
    print("[*] Updating version cache busters in HTML...")
    result = subprocess.run(
        [sys.executable, "update_version.py"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"[X] Failed to update version cache busters:")
        print(result.stderr)
        return False
    print(result.stdout)
    return True

def generate_rsync_command(remote_host: str, remote_path: str, remote_user: Optional[str] = None) -> str:
    """
    Generate the rsync command for production deployment.
    
    Args:
        remote_host: Remote server hostname/IP
        remote_path: Remote directory path (e.g., /var/www/maps)
        remote_user: Remote SSH user (optional)
    """
    if remote_user:
        destination = f"{remote_user}@{remote_host}:{remote_path}"
    else:
        destination = f"{remote_host}:{remote_path}"
    
    # Base rsync flags
    # -a: archive mode (preserves permissions, timestamps, etc.)
    # -v: verbose
    # -z: compress during transfer
    # --progress: show progress
    # --delete: delete files on remote that don't exist locally
    # --times: preserve modification times (for cache freshness)
    # --no-perms: don't preserve permissions (simpler for static hosting)
    # --chmod: set permissions appropriately for web serving
    flags = [
        "-avz",                    # archive, verbose, compress
        "--progress",              # show progress
        "--delete",                # delete remote files not in local
        "--times",                 # preserve modification times
        "--no-perms",              # don't sync permissions (simpler)
        "--chmod=644",             # files: rw-r--r--
        "--chmod=Du+x",            # directories: executable
    ]
    
    # Rsync filter rules - order matters!
    # Include what we want first, then exclude everything else
    filter_rules = [
        "--include=interactive_viewer_advanced.html",
        "--include=viewer.html",
        "--include=js/",
        "--include=js/**",
        "--include=css/",
        "--include=css/**",
        "--include=generated/",
        "--include=generated/regions/",
        "--include=generated/regions/**.json",
        "--include=generated/regions/**.json.gz",
        "--exclude=*",             # exclude everything else
    ]
    
    # Build command
    source = "."  # current directory
    parts = ["rsync"] + flags + filter_rules + [source + "/", destination]
    
    return " ".join(parts)

def main():
    print("=" * 70)
    print("Altitude Maps - Production Deployment Preparation")
    print("=" * 70)
    print()
    
    # Step 1: Regenerate manifest
    print("[1/2] Regenerating regions manifest...")
    if not regenerate_manifest():
        print("\n[X] Failed to regenerate manifest. Aborting.")
        return 1
    print()
    
    # Step 2: Update version cache busters
    print("[2/2] Updating version cache busters in HTML...")
    if not update_version_cache_busters():
        print("\n[X] Failed to update version cache busters. Aborting.")
        return 1
    print()
    
    # Step 3: Get deployment details from args or prompt
    if len(sys.argv) >= 3:
        remote_host = sys.argv[1]
        remote_path = sys.argv[2]
        remote_user = sys.argv[3] if len(sys.argv) >= 4 else None
    else:
        print("[*] Deployment Configuration")
        print()
        remote_host = input("Remote host (e.g., example.com): ").strip()
        if not remote_host:
            print("[X] Remote host is required")
            return 1
        
        remote_path = input("Remote path (e.g., /var/www/maps): ").strip()
        if not remote_path:
            print("[X] Remote path is required")
            return 1
        
        remote_user_input = input("Remote user (optional, press Enter to skip): ").strip()
        remote_user = remote_user_input if remote_user_input else None
    
    print()
    print("=" * 70)
    print("READY TO DEPLOY - Copy and paste this rsync command:")
    print("=" * 70)
    print()
    
    rsync_cmd = generate_rsync_command(remote_host, remote_path, remote_user)
    print(rsync_cmd)
    print()
    print("=" * 70)
    print("Deployment includes:")
    print("  [x] HTML viewers (interactive_viewer_advanced.html, viewer.html)")
    print("  [x] JavaScript files (js/) - with version cache busters")
    print("  [x] CSS files (css/) - with version cache busters")
    print("  [x] All region JSON files (generated/regions/*.json)")
    print("  [x] All region GZ files (generated/regions/*.json.gz)")
    print("  [x] Regions manifest (fresh, regenerated)")
    print("  [x] Manifest GZ (fresh, regenerated)")
    print()
    print("Cache busting:")
    print("  - JS/CSS: Version query params (?v=X.X.X) in HTML")
    print("  - Manifest: Timestamp-based cache busting in viewer JS")
    print("  - All files: Fresh timestamps from regeneration")
    print("=" * 70)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

