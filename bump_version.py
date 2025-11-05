#!/usr/bin/env python3
"""
Quick version bump script - increments viewer version with minimal overhead.
Usage: python bump_version.py [patch|minor|major]
Default: patch increment
"""

import re
import sys
from pathlib import Path
from typing import Literal

def bump_js_version(version_type: Literal['patch', 'minor', 'major'] = 'patch') -> str:
    """Increment version in js/viewer-advanced.js"""
    js_file = Path('js/viewer-advanced.js')
    content = js_file.read_text(encoding='utf-8')
    
    # Extract current version
    match = re.search(r"const VIEWER_VERSION = '([^']+)';", content)
    if not match:
        print("Error: Could not find VIEWER_VERSION in js/viewer-advanced.js")
        sys.exit(1)
    
    old_version = match.group(1)
    parts = old_version.split('.')
    
    # Keep only first two parts (remove patch version)
    while len(parts) > 2:
        parts.pop()
    
    # Bump version - just increment the last number
    parts[1] = str(int(parts[1]) + 1)
    
    new_version = '.'.join(parts)
    
    # Update file
    new_content = content.replace(f"const VIEWER_VERSION = '{old_version}';", 
                                   f"const VIEWER_VERSION = '{new_version}';")
    js_file.write_text(new_content, encoding='utf-8')
    
    print(f"Version bumped: {old_version} -> {new_version}")
    return new_version

def main():
    version_type: Literal['patch', 'minor', 'major'] = 'patch'
    if len(sys.argv) > 1:
        input_type = sys.argv[1]
        if input_type not in ['patch', 'minor', 'major']:
            print("Usage: python bump_version.py [patch|minor|major]")
            sys.exit(1)
        version_type = input_type  # type: ignore
    
    bump_js_version(version_type)
    
    # Run update_version.py to sync HTML cache busters
    print("Syncing HTML cache busters...")
    import subprocess
    subprocess.run([sys.executable, 'update_version.py'], check=False)
    
    print("\nDone! Ready to deploy.")

if __name__ == '__main__':
    main()

