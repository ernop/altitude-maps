"""Remove all emojis from files and replace with plain text."""

import re
from pathlib import Path

# Emoji replacements
REPLACEMENTS = {
    '✓': '[OK]',
    '✗': '[NO]',
    '❌': '[FAIL]',
    '✅': '[PASS]',
    '⚠️': '[WARNING]',
    '⚠': '[WARNING]',
    '📝': '[NOTE]',
    '🔧': '[TOOL]',
    '🎯': '[TARGET]',
    '💡': '[IDEA]',
    '⭐': '[STAR]',
    '🚀': '[ROCKET]',
    '📊': '[CHART]',
    '🔍': '[SEARCH]',
    '✨': '[SPARKLE]',
    '🎨': '[ART]',
    '🐛': '[BUG]',
    '⚡': '[FAST]',
    '🎉': '[PARTY]',
    '👍': '[THUMBS_UP]',
    '👎': '[THUMBS_DOWN]',
    '💾': '[SAVE]',
    '🔥': '[FIRE]',
}

def fix_emojis_in_file(filepath: Path) -> bool:
    """
    Remove emojis from a file and replace with plain text.
    
    Returns:
        True if file was modified, False otherwise
    """
    try:
        content = filepath.read_text(encoding='utf-8')
        original = content
        
        # Replace each emoji
        for emoji, replacement in REPLACEMENTS.items():
            content = content.replace(emoji, replacement)
        
        # Only write if changed
        if content != original:
            filepath.write_text(content, encoding='utf-8')
            print(f"Fixed: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Fix all emojis in the repository."""
    root = Path('.')
    
    # File patterns to check
    patterns = ['**/*.md', '**/*.py', '**/*.ps1', '**/*.js', '**/*.html', '**/*.css']
    
    # Directories to skip
    skip_dirs = {'.git', 'venv', '__pycache__', 'node_modules', '.vscode'}
    
    modified_count = 0
    checked_count = 0
    
    for pattern in patterns:
        for filepath in root.glob(pattern):
            # Skip if in excluded directory
            if any(skip in filepath.parts for skip in skip_dirs):
                continue
            
            checked_count += 1
            if fix_emojis_in_file(filepath):
                modified_count += 1
    
    print(f"\nDone! Checked {checked_count} files, modified {modified_count} files.")

if __name__ == '__main__':
    main()

