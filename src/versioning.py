"""
Data versioning and compatibility management for altitude-maps.

This module tracks versions for each stage of the data pipeline and ensures
compatibility between cached data and current code.
"""
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
from datetime import datetime

# Current version for each pipeline stage
# Increment these when algorithm/format changes to invalidate old cache
RAW_VERSION = "raw_v1"          # Raw downloads (never changes - immutable)
CLIPPED_VERSION = "clipped_v1"  # Boundary clipping algorithm
PROCESSED_VERSION = "processed_v2"  # Downsampling/processing  
EXPORT_VERSION = "export_v2"    # JSON export format

# Version history and compatibility
VERSION_HISTORY = {
    "raw_v1": {
        "date": "2025-10-23",
        "changes": "Initial version - raw downloads",
        "breaking": False
    },
    "clipped_v1": {
        "date": "2025-10-23",
        "changes": "Initial version - boundary clipping with rasterio",
        "breaking": False
    },
    "processed_v1": {
        "date": "2025-10-20",
        "changes": "Initial downsampling algorithm",
        "breaking": False
    },
    "processed_v2": {
        "date": "2025-10-23",
        "changes": "Fixed coordinate system handling in downsampling",
        "breaking": True,
        "incompatible_with": ["processed_v1"]
    },
    "export_v1": {
        "date": "2025-10-20",
        "changes": "Initial JSON export format",
        "breaking": False
    },
    "export_v2": {
        "date": "2025-10-23",
        "changes": "Added source tracking and bounds metadata to JSON",
        "breaking": True,
        "incompatible_with": ["export_v1"]
    }
}


class VersionMismatchError(Exception):
    """Raised when cached data version doesn't match current code version."""
    pass


def get_current_version(stage: str) -> str:
    """
    Get the current version for a pipeline stage.
    
    Args:
        stage: One of 'raw', 'clipped', 'processed', 'export'
        
    Returns:
        Version string (e.g., 'clipped_v1')
        
    Raises:
        ValueError: If stage is unknown
    """
    stage_versions = {
        'raw': RAW_VERSION,
        'clipped': CLIPPED_VERSION,
        'processed': PROCESSED_VERSION,
        'export': EXPORT_VERSION
    }
    
    if stage not in stage_versions:
        raise ValueError(f"Unknown stage: {stage}. Must be one of {list(stage_versions.keys())}")
    
    return stage_versions[stage]


def is_compatible(actual_version: str, required_version: str) -> bool:
    """
    Check if an actual version is compatible with the required version.
    
    Args:
        actual_version: Version of cached data (e.g., 'processed_v1')
        required_version: Version required by current code (e.g., 'processed_v2')
        
    Returns:
        True if compatible, False otherwise
    """
    # Same version is always compatible
    if actual_version == required_version:
        return True
    
    # Check if required version explicitly marks actual as incompatible
    if required_version in VERSION_HISTORY:
        incompatible = VERSION_HISTORY[required_version].get('incompatible_with', [])
        if actual_version in incompatible:
            return False
    
    # If no explicit incompatibility and versions are close, assume compatible
    # (This is conservative - we prefer explicit marking)
    return False


def check_version(metadata: Dict, stage: str, region_id: str = "unknown") -> None:
    """
    Check if cached data version is compatible with current code.
    
    Args:
        metadata: Metadata dictionary containing 'version' key
        stage: Pipeline stage ('raw', 'clipped', 'processed', 'export')
        region_id: Region identifier for error messages
        
    Raises:
        VersionMismatchError: If version is incompatible
    """
    if 'version' not in metadata:
        raise VersionMismatchError(
            f"No version information in metadata for {region_id}. "
            f"This file may be from an old version of the code. "
            f"Please regenerate."
        )
    
    actual_version = metadata['version']
    required_version = get_current_version(stage)
    
    if not is_compatible(actual_version, required_version):
        raise VersionMismatchError(
            f"Version mismatch for {region_id}:\n"
            f"  Cached data: {actual_version}\n"
            f"  Required:    {required_version}\n"
            f"\n"
            f"The cached data is incompatible with current code.\n"
            f"To regenerate, run:\n"
            f"  python clear_caches.py --stage {stage} --region {region_id}"
        )


def get_version_info(version: str) -> Optional[Dict]:
    """
    Get information about a specific version.
    
    Args:
        version: Version string (e.g., 'processed_v2')
        
    Returns:
        Dictionary with version info, or None if not found
    """
    return VERSION_HISTORY.get(version)


def save_version_registry(output_path: Path) -> None:
    """
    Save current version information to a JSON file.
    
    Args:
        output_path: Path to save version registry
    """
    registry = {
        "generated": datetime.now().isoformat(),
        "current_versions": {
            "raw": RAW_VERSION,
            "clipped": CLIPPED_VERSION,
            "processed": PROCESSED_VERSION,
            "export": EXPORT_VERSION
        },
        "version_history": VERSION_HISTORY
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(registry, f, indent=2)


def bump_version(stage: str, changes: str, breaking: bool = False) -> str:
    """
    Helper function to bump a version (for development use).
    
    Args:
        stage: Pipeline stage to bump
        changes: Description of changes
        breaking: Whether this is a breaking change
        
    Returns:
        New version string
        
    Note:
        This doesn't actually modify the code - it's a helper for developers
        to document what needs to be updated when bumping versions.
    """
    current = get_current_version(stage)
    
    # Extract version number
    base, ver = current.rsplit('_v', 1)
    new_ver = int(ver) + 1
    new_version = f"{base}_v{new_ver}"
    
    print(f"To bump {stage} version:")
    print(f"  1. Update {stage.upper()}_VERSION = '{new_version}' in src/versioning.py")
    print(f"  2. Add to VERSION_HISTORY:")
    print(f"     '{new_version}': {{")
    print(f"         'date': '{datetime.now().strftime('%Y-%m-%d')}',")
    print(f"         'changes': '{changes}',")
    print(f"         'breaking': {breaking}")
    if breaking:
        print(f"         'incompatible_with': ['{current}']")
    print(f"     }}")
    print(f"  3. Run: python clear_caches.py --stage {stage}")
    
    return new_version


if __name__ == "__main__":
    # Test/demo
    print("Current Versions:")
    print("=" * 50)
    for stage in ['raw', 'clipped', 'processed', 'export']:
        version = get_current_version(stage)
        info = get_version_info(version)
        print(f"{stage:12s}: {version:15s} - {info.get('changes', 'N/A')}")
    
    print("\n" + "=" * 50)
    print("Version History:")
    print("=" * 50)
    for version, info in VERSION_HISTORY.items():
        breaking = " [BREAKING]" if info.get('breaking') else ""
        print(f"{version:15s} ({info['date']}){breaking}")
        print(f"  {info['changes']}")
        if 'incompatible_with' in info:
            print(f"  Incompatible with: {', '.join(info['incompatible_with'])}")
        print()

