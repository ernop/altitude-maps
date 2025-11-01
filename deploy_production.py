#!/usr/bin/env python3
"""
Production deployment script - prepares and uploads all viewer files.

This script:
1. Loads deployment settings from settings.json
2. Updates version cache busters in HTML files (inline, fast)
3. Outputs rsync command for uploading everything

Usage:
    python deploy_production.py
    # Then run the rsync command it outputs (remove --dry-run when ready)
    
Configuration:
    Add deployment settings to settings.json:
    {
      "deployment": {
        "remote_host": "example.com",
        "remote_path": "/var/www/maps",
        "remote_user": "deploy"
      }
    }
"""

import sys
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any

def load_deployment_settings() -> Dict[str, Any]:
    """Load deployment settings from settings.json"""
    settings_path = Path("settings.json")
    
    if not settings_path.exists():
        print("[X] Error: settings.json not found!")
        print("\nPlease create settings.json with deployment configuration.")
        print("Use settings.example.json as a template:")
        print("  copy settings.example.json settings.json")
        print("\nThen add your deployment settings under 'deployment' section.")
        sys.exit(1)
    
    try:
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            deployment = settings.get('deployment', {})
            
            if not deployment:
                print("[X] Error: No 'deployment' section found in settings.json")
                print("\nPlease add deployment configuration:")
                print('  "deployment": {')
                print('    "remote_host": "example.com",')
                print('    "remote_path": "/var/www/maps",')
                print('    "remote_user": "deploy"')
                print('  }')
                sys.exit(1)
            
            return deployment
    except json.JSONDecodeError as e:
        print(f"[X] Error: Invalid JSON in settings.json")
        print(f"  {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[X] Error loading settings.json: {e}")
        sys.exit(1)

def update_version_cache_busters() -> bool:
    """Update version cache busters in HTML files - inlined for speed."""
    # Extract version from JS file
    js_file = Path('js/viewer-advanced.js')
    if not js_file.exists():
        print("[X] Error: js/viewer-advanced.js not found")
        return False
    
    content = js_file.read_text(encoding='utf-8')
    match = re.search(r"const VIEWER_VERSION = '([^']+)';", content)
    if not match:
        print("[X] Error: Could not find VIEWER_VERSION in js/viewer-advanced.js")
        return False
    
    version = match.group(1)
    
    # Update HTML cache busters
    html_file = Path('interactive_viewer_advanced.html')
    if not html_file.exists():
        print("[X] Error: interactive_viewer_advanced.html not found")
        return False
    
    html_content = html_file.read_text(encoding='utf-8')
    updated = html_content
    
    # Replace version in script tags
    pattern = r'(src="js/[^"]+\.js)\?v=[^"]*(")'
    replacement = rf'\1?v={version}\2'
    updated = re.sub(pattern, replacement, updated)
    
    # Replace version in link tags
    pattern = r'(href="css/[^"]+\.css)\?v=[^"]*(")'
    replacement = rf'\1?v={version}\2'
    updated = re.sub(pattern, replacement, updated)
    
    if updated != html_content:
        html_file.write_text(updated, encoding='utf-8')
        print(f"[+] Updated cache busters to v{version}")
    else:
        print(f"[~] Cache busters already up to date (v{version})")
    
    return True

def generate_rsync_command(remote_host: str, remote_path: str, remote_user: Optional[str] = None) -> str:
    """
    Generate the rsync command for production deployment.
    
    Args:
        remote_host: Remote server hostname/IP
        remote_path: Remote directory path (e.g., /var/www/maps)
        remote_user: Remote SSH user (optional)
    """
    # Get absolute path of current directory (source)
    # Convert Windows path to WSL-style (/mnt/c/...) for rsync compatibility
    source_dir = Path.cwd().resolve()
    source_str = str(source_dir).replace("\\", "/")
    
    # Convert Windows path to WSL mount path if needed
    # C:\proj\altitude-maps -> /mnt/c/proj/altitude-maps
    if source_str[1] == ":" and source_str[0].isalpha():
        # Windows drive letter detected (e.g., C:\...)
        drive = source_str[0].lower()
        path_without_drive = source_str[2:]  # Remove "C:"
        source = f"/mnt/{drive}{path_without_drive}/"  # Trailing slash means "contents of"
    else:
        # Already Unix-style or no drive letter
        source = source_str + "/"  # Trailing slash means "contents of"
    
    # Ensure remote path has trailing slash
    if not remote_path.endswith("/"):
        remote_path = remote_path + "/"
    
    # Build destination
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
    # --no-perms: don't preserve permissions from source (simpler for static hosting)
    # --chmod=644: files get 644 (rw-r--r--) - owner read/write, others read-only
    # --chmod=Du+x: directories get execute for user (needed to traverse directories)
    flags = [
        "-avz",                    # archive, verbose, compress
        "--progress",              # show progress
        "--delete",                # delete remote files not in local
        "--times",                 # preserve modification times
        "--no-perms",              # don't sync permissions from source
        "--chmod=644",             # files: rw-r--r-- (readable by web server)
        "--chmod=Du+x",            # directories: user can execute (needed for traversal)
    ]
    
    # Rsync filter rules - build iteratively: ONLY what's needed for web viewer
    # Using --filter syntax for more precise control
    # Order: include what we need, then exclude everything else
    filter_rules = [
        # Step 1: Include the HTML viewer (at root)
        "--include=interactive_viewer_advanced.html",
        
        # Step 2: Include JavaScript directory and all contents
        "--include=js/",
        "--include=js/**",
        
        # Step 3: Include CSS directory and all contents
        "--include=css/",
        "--include=css/**",
        
        # Step 4: Include generated elevation data (GZ files only - server rewrites .json to .json.gz)
        "--include=generated/",
        "--include=generated/regions/",
        # Include manifest (both versions - server can serve either)
        "--include=generated/regions/regions_manifest.json",
        "--include=generated/regions/regions_manifest.json.gz",
        # Include all files in regions/ to allow traversal
        "--include=generated/regions/**",
        # Exclude unzipped .json files (keep only .json.gz)
        "--exclude=generated/regions/*.json",
        # Re-include .json.gz files (after excluding .json)
        "--include=generated/regions/*.json.gz",
        
        # Exclude everything else (must be last, will be quoted in output)
        "--exclude=*",
    ]
    
    # Build command (ends with --dry-run for safety - remove when ready)
    # Note: The exclude pattern needs quotes to prevent shell expansion
    parts = ["rsync"] + flags + filter_rules + [source, destination, "--dry-run"]
    
    # Join all parts
    cmd = " ".join(parts)
    
    # Quote the * in --exclude=* to prevent shell glob expansion
    # Use single quotes which work in bash/zsh (user can adjust if needed)
    cmd = cmd.replace("--exclude=*", "--exclude='*'")
    
    return cmd

def main():
    print("=" * 70)
    print("Altitude Maps - Production Deployment")
    print("=" * 70)
    print()
    
    # Load deployment settings from settings.json
    print("[*] Loading deployment settings...")
    deployment = load_deployment_settings()
    remote_host = deployment.get("remote_host")
    remote_path = deployment.get("remote_path")
    remote_user = deployment.get("remote_user")  # Can be None/optional
    
    if not remote_host:
        print("[X] Error: 'remote_host' not found in deployment settings")
        sys.exit(1)
    if not remote_path:
        print("[X] Error: 'remote_path' not found in deployment settings")
        sys.exit(1)
    
    print(f"  Host: {remote_host}")
    print(f"  Path: {remote_path}")
    print(f"  User: {remote_user if remote_user else '(not specified)'}")
    print()
    
    # Update version cache busters (fast inline update)
    print("[*] Updating version cache busters...")
    if not update_version_cache_busters():
        print("\n[X] Failed to update version cache busters. Aborting.")
        return 1
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
    print("  [x] Regions manifest (existing - updated during region processing)")
    print()
    print("Cache busting:")
    print("  - JS/CSS: Version query params (?v=X.X.X) in HTML")
    print("  - Manifest: Timestamp-based cache busting in viewer JS")
    print("  - All files: Fresh timestamps (from rsync)")
    print()
    print("Rsync command:")
    print("  - Full absolute path for source directory")
    print("  - Both source and dest have trailing '/' (pure directory matching)")
    print("  - Ends with --dry-run (remove when ready to deploy)")
    print("  - --chmod=644: Files get rw-r--r-- (web readable)")
    print("  - --chmod=Du+x: Directories get execute bit (needed for traversal)")
    print()
    print("Note: Remove '--dry-run' from the command when ready to deploy!")
    print("=" * 70)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

