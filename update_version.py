#!/usr/bin/env python3
"""
Update version numbers across all viewer files before deployment.
Reads version from js/viewer-advanced.js and updates all references.
"""

import re
import sys
from pathlib import Path

def extract_version_from_js():
    """Extract version from viewer-advanced.js"""
    js_file = Path('js/viewer-advanced.js')
    content = js_file.read_text(encoding='utf-8')
    
    match = re.search(r"const VIEWER_VERSION = '([^']+)';", content)
    if match:
        return match.group(1)
    else:
        print("Error: Could not find VIEWER_VERSION in js/viewer-advanced.js")
        sys.exit(1)

def update_html_cache_busters(version):
    """Update cache busters in HTML files"""
    html_file = Path('interactive_viewer_advanced.html')
    content = html_file.read_text(encoding='utf-8')
    
    # Replace version in script tags for internal JS files
    # Pattern: src="js/...?v=OLD_VERSION" -> src="js/...?v=NEW_VERSION"
    pattern = r'(src="js/[^"]+\.js)\?v=[^"]*(")'
    replacement = rf'\1?v={version}\2'
    
    updated_content = re.sub(pattern, replacement, content)
    
    if updated_content != content:
        html_file.write_text(updated_content, encoding='utf-8')
        print(f"Updated cache busters in {html_file} to v{version}")
        return True
    else:
        print(f"Cache busters in {html_file} already up to date (v{version})")
        return False

def main():
    print("Updating version numbers...")
    print()
    
    # Extract version from JS
    version = extract_version_from_js()
    print(f"Current version: v{version}")
    print()
    
    # Update HTML cache busters
    updated = update_html_cache_busters(version)
    
    print()
    if updated:
        print("Version update complete!")
        print(f"   All cache busters now reference: v{version}")
    else:
        print("All files already up to date!")
    print()
    print("To change version:")
    print("  1. Edit VIEWER_VERSION in js/viewer-advanced.js")
    print("  2. Run: python update_version.py")
    print("  3. Deploy with: ./deploy.sh or deploy.ps1")

if __name__ == '__main__':
    main()

