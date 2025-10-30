#!/usr/bin/env python3
"""
Remove emojis from documentation and code files.

Scans markdown, Python, JavaScript, and other text files to find and remove emojis.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Unicode ranges for emojis
# This covers most common emoji ranges
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # enclosed characters
    "\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs
    "\U00002600-\U000026FF"  # miscellaneous symbols
    "\U00002700-\U000027BF"  # dingbats
    "\U0001F018-\U0001F270"  # various asian characters
    "\U0001F300-\U0001F5FF"  # various asian characters
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F680-\U0001F6FF"  # transport and map
    "\U0001F700-\U0001F77F"  # alchemical symbols
    "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
    "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
    "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
    "\U0001FA00-\U0001FA6F"  # Chess Symbols
    "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
    "\U00002600-\U000026FF"  # Miscellaneous Symbols
    "\U00002700-\U000027BF"  # Dingbats
    "]+",
    flags=re.UNICODE,
)


def find_files_with_emojis(directory: Path, extensions: List[str]) -> List[Tuple[Path, List[int]]]:
    """Find all files containing emojis and return file paths with line numbers."""
    results = []
    
    directory = Path(directory).resolve()
    for ext in extensions:
        for file_path in directory.rglob(f"*{ext}"):
            # Skip git and venv directories
            if any(skip in str(file_path) for skip in ['.git', 'venv', '__pycache__', 'node_modules', '.cache']):
                continue
            # Skip if file doesn't exist (broken symlinks, etc.)
            if not file_path.exists() or not file_path.is_file():
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines_with_emojis = []
                    for line_num, line in enumerate(f, 1):
                        if EMOJI_PATTERN.search(line):
                            lines_with_emojis.append(line_num)
                    if lines_with_emojis:
                        results.append((file_path, lines_with_emojis))
            except (UnicodeDecodeError, PermissionError, IsADirectoryError):
                continue
    
    return results


def remove_emojis_from_file(file_path: Path, dry_run: bool = False) -> int:
    """Remove emojis from a file. Returns number of replacements made."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        original_content = content
        content = EMOJI_PATTERN.sub('', content)
        
        # Clean up double spaces that might result from emoji removal
        content = re.sub(r' +', ' ', content)
        # Clean up spaces before newlines
        content = re.sub(r' +\n', '\n', content)
        # Clean up triple spaces (e.g., "## **TITLE**" -> "## **TITLE")
        content = re.sub(r' +([*#])', r'\1', content)
        
        num_replacements = len(EMOJI_PATTERN.findall(original_content))
        
        if content != original_content:
            if not dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            return num_replacements
    except (UnicodeDecodeError, PermissionError, IsADirectoryError) as e:
        print(f"  Error processing {file_path}: {e}", file=sys.stderr)
    
    return 0


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Remove emojis from documentation and code files")
    parser.add_argument('--dry-run', action='store_true', help='Show what would be removed without making changes')
    parser.add_argument('--extensions', nargs='+', 
                        default=['.md', '.py', '.js', '.html', '.css', '.txt'],
                        help='File extensions to process (default: .md .py .js .html .css .txt)')
    parser.add_argument('--directory', type=Path, default=Path('.'), 
                        help='Directory to search (default: current directory)')
    
    args = parser.parse_args()
    
    print(f"Searching for emojis in {args.directory}...")
    print(f"Extensions: {', '.join(args.extensions)}")
    print(f"Mode: {'DRY RUN (no changes will be made)' if args.dry_run else 'REMOVING EMOJIS'}")
    print()
    
    files_with_emojis = find_files_with_emojis(args.directory, args.extensions)
    
    if not files_with_emojis:
        print("No files with emojis found.")
        return 0
    
    total_replacements = 0
    base_dir = Path(args.directory).resolve()
    for file_path, line_nums in files_with_emojis:
        try:
            rel_path = file_path.relative_to(base_dir)
        except ValueError:
            rel_path = file_path
        print(f"Processing: {rel_path}")
        print(f"  Found emojis on lines: {', '.join(map(str, line_nums[:10]))}{'...' if len(line_nums) > 10 else ''}")
        
        num_removed = remove_emojis_from_file(file_path, dry_run=args.dry_run)
        total_replacements += num_removed
        print(f"  Removed {num_removed} emoji(s)")
        print()
    
    print(f"{'Would remove' if args.dry_run else 'Removed'} emojis from {len(files_with_emojis)} file(s)")
    print(f"Total emoji instances removed: {total_replacements}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
