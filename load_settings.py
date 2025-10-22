"""
Shared settings loader for all scripts in the project.
Reads from settings.json (not checked into git).
"""
import json
import sys
import io
from pathlib import Path
from typing import Dict, Any, Optional

# Fix Windows console encoding  
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        if hasattr(sys.stderr, 'buffer') and not isinstance(sys.stderr, io.TextIOWrapper):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (AttributeError, ValueError, OSError):
        pass


def load_settings(settings_file: str = "settings.json") -> Dict[str, Any]:
    """
    Load settings from settings.json file.
    
    Returns:
        Dictionary with all settings
        
    Raises:
        FileNotFoundError: If settings.json doesn't exist
    """
    settings_path = Path(settings_file)
    
    if not settings_path.exists():
        print(f"❌ Error: {settings_file} not found!")
        print(f"\nPlease create {settings_file} with your configuration.")
        print(f"Use settings.example.json as a template:")
        print(f"  copy settings.example.json {settings_file}")
        print(f"\nThen add your OpenTopography API key.")
        sys.exit(1)
    
    try:
        with open(settings_path, 'r') as f:
            settings = json.load(f)
        return settings
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in {settings_file}")
        print(f"   {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading {settings_file}: {e}")
        sys.exit(1)


def get_opentopography_api_key() -> str:
    """
    Get OpenTopography API key from settings.
    
    Returns:
        API key string
    """
    settings = load_settings()
    api_key = settings.get('opentopography', {}).get('api_key')
    
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        print("❌ Error: No valid OpenTopography API key configured!")
        print("\nPlease edit settings.json and add your API key.")
        print("Get a free key at: https://portal.opentopography.org/")
        sys.exit(1)
    
    return api_key


def get_setting(key_path: str, default: Any = None) -> Any:
    """
    Get a specific setting using dot notation.
    
    Examples:
        get_setting('opentopography.api_key')
        get_setting('download.default_max_size', 1024)
    
    Args:
        key_path: Dot-separated path to setting (e.g., 'download.cache_dir')
        default: Default value if setting not found
        
    Returns:
        Setting value or default
    """
    try:
        settings = load_settings()
        keys = key_path.split('.')
        value = settings
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default


def get_download_settings() -> Dict[str, Any]:
    """
    Get all download-related settings.
    
    Returns:
        Dictionary with download settings
    """
    settings = load_settings()
    return settings.get('download', {
        'default_max_size': 1024,
        'cache_dir': 'data/cache',
        'regions_dir': 'data/regions',
        'output_dir': 'generated/regions'
    })


def get_rendering_settings() -> Dict[str, Any]:
    """
    Get all rendering-related settings.
    
    Returns:
        Dictionary with rendering settings
    """
    settings = load_settings()
    return settings.get('rendering', {
        'default_bucket_size': 12,
        'default_vertical_exaggeration': 0.01
    })


# Convenience function for scripts
def get_api_key() -> str:
    """Shorthand for get_opentopography_api_key()"""
    return get_opentopography_api_key()


if __name__ == "__main__":
    # Test the settings loader
    print("Testing settings loader...")
    print("\n📋 Current Settings:")
    print("="*60)
    
    settings = load_settings()
    print(json.dumps(settings, indent=2))
    
    print("\n🔑 API Key:")
    api_key = get_api_key()
    print(f"   {api_key[:8]}...{api_key[-4:]}")
    
    print("\n📥 Download Settings:")
    dl_settings = get_download_settings()
    for key, value in dl_settings.items():
        print(f"   {key}: {value}")
    
    print("\n🎨 Rendering Settings:")
    render_settings = get_rendering_settings()
    for key, value in render_settings.items():
        print(f"   {key}: {value}")
    
    print("\n✅ Settings loaded successfully!")

