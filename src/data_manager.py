"""
Unified data management for altitude-maps.

This module provides a clean API for loading elevation data with automatic:
- Version checking and validation
- Source preference and fallback
- Metadata loading and verification
- Cache management
"""
from typing import Optional, List, Dict, Tuple
from pathlib import Path
from dataclasses import dataclass
import json

import rasterio
import numpy as np

from .versioning import check_version, get_current_version, VersionMismatchError
from .metadata import load_metadata, validate_source_file, get_metadata_path


@dataclass
class DataSource:
    """Information about an available data source for a region."""
    region_id: str
    source: str  # e.g., 'usa_3dep', 'srtm_30m'
    stage: str  # 'raw', 'clipped', 'processed'
    resolution_m: int
    path: Path
    metadata: Dict


class DataManager:
    """
    Manage elevation data with automatic version checking and source resolution.
    
    Example usage:
        dm = DataManager()
        
        # Load best available data
        data = dm.load_region('california', prefer_source='usa_3dep')
        
        # Get metadata
        meta = dm.get_metadata('california', stage='clipped')
        
        # List available sources
        sources = dm.list_sources('california')
    """
    
    def __init__(self, data_root: Path = Path('data')):
        """
        Initialize data manager.
        
        Args:
            data_root: Root directory for data (default: 'data/')
        """
        self.data_root = Path(data_root)
        self.raw_dir = self.data_root / 'raw'
        self.clipped_dir = self.data_root / 'clipped'
        self.processed_dir = self.data_root / 'processed'
        self.metadata_dir = self.data_root / 'metadata'
        
    def find_region_files(self, region_id: str, stage: str = 'raw') -> List[DataSource]:
        """
        Find all available data files for a region at a specific stage.
        
        Args:
            region_id: Region identifier (e.g., 'california')
            stage: Pipeline stage ('raw', 'clipped', 'processed')
            
        Returns:
            List of DataSource objects for available data
        """
        stage_dir = getattr(self, f'{stage}_dir')
        sources = []
        
        # Search in all source subdirectories
        for source_dir in stage_dir.iterdir():
            if not source_dir.is_dir():
                continue
            
            source_name = source_dir.name
            
            # Look for files matching region_id
            for tif_file in source_dir.glob(f"{region_id}*.tif"):
                meta_file = get_metadata_path(tif_file)
                
                if not meta_file.exists():
                    # No metadata - skip
                    continue
                
                try:
                    metadata = load_metadata(meta_file)
                    
                    # Verify version compatibility
                    check_version(metadata, stage, region_id)
                    
                    sources.append(DataSource(
                        region_id=region_id,
                        source=source_name,
                        stage=stage,
                        resolution_m=metadata.get('resolution_meters', 0),
                        path=tif_file,
                        metadata=metadata
                    ))
                except (VersionMismatchError, json.JSONDecodeError) as e:
                    # Skip incompatible or corrupt files
                    print(f"  Skipping {tif_file.name}: {e}")
                    continue
        
        # Sort by resolution (higher resolution first)
        sources.sort(key=lambda s: s.resolution_m)
        return sources
    
    def load_region(
        self,
        region_id: str,
        stage: str = 'raw',
        prefer_source: Optional[str] = None
    ) -> Tuple[np.ndarray, Dict]:
        """
        Load elevation data for a region with automatic source selection.
        
        Args:
            region_id: Region identifier (e.g., 'california')
            stage: Pipeline stage ('raw', 'clipped', 'processed')
            prefer_source: Preferred source (e.g., 'usa_3dep'), will fallback if not available
            
        Returns:
            Tuple of (elevation_array, metadata)
            
        Raises:
            FileNotFoundError: If no data found for region
            VersionMismatchError: If data version is incompatible
        """
        sources = self.find_region_files(region_id, stage)
        
        if not sources:
            raise FileNotFoundError(
                f"No {stage} data found for region '{region_id}'.\n"
                f"Available stages: {self._get_available_stages(region_id)}"
            )
        
        # Select source based on preference
        selected_source = None
        if prefer_source:
            # Try to find preferred source
            for source in sources:
                if source.source == prefer_source:
                    selected_source = source
                    break
            
            if not selected_source:
                print(f"  Preferred source '{prefer_source}' not found, using best available")
        
        # If no preference or preference not found, use highest resolution
        if not selected_source:
            selected_source = sources[0]  # Already sorted by resolution
        
        print(f"📂 Loading {region_id} from {selected_source.source} "
              f"({selected_source.resolution_m}m, {stage})")
        
        # Load the raster data
        with rasterio.open(selected_source.path) as src:
            elevation = src.read(1)
            
            # Add bounds to metadata
            bounds = src.bounds
            selected_source.metadata['bounds'] = {
                'left': float(bounds.left),
                'bottom': float(bounds.bottom),
                'right': float(bounds.right),
                'top': float(bounds.top)
            }
        
        return elevation, selected_source.metadata
    
    def get_metadata(self, region_id: str, stage: str = 'raw', source: Optional[str] = None) -> Dict:
        """
        Get metadata for a region without loading the full raster.
        
        Args:
            region_id: Region identifier
            stage: Pipeline stage
            source: Specific source (optional)
            
        Returns:
            Metadata dictionary
            
        Raises:
            FileNotFoundError: If metadata not found
        """
        sources = self.find_region_files(region_id, stage)
        
        if not sources:
            raise FileNotFoundError(f"No {stage} data found for {region_id}")
        
        if source:
            for s in sources:
                if s.source == source:
                    return s.metadata
            raise FileNotFoundError(f"Source '{source}' not found for {region_id}")
        
        # Return highest resolution
        return sources[0].metadata
    
    def list_sources(self, region_id: str) -> List[str]:
        """
        List all available data sources for a region across all stages.
        
        Args:
            region_id: Region identifier
            
        Returns:
            List of strings describing available sources
        """
        available = []
        
        for stage in ['raw', 'clipped', 'processed']:
            sources = self.find_region_files(region_id, stage)
            for source in sources:
                desc = f"{source.source} ({source.resolution_m}m, {stage})"
                available.append(desc)
        
        return available
    
    def list_all_regions(self, stage: str = 'raw') -> List[str]:
        """
        List all regions with data available at a specific stage.
        
        Args:
            stage: Pipeline stage
            
        Returns:
            List of region identifiers
        """
        stage_dir = getattr(self, f'{stage}_dir')
        regions = set()
        
        for source_dir in stage_dir.iterdir():
            if not source_dir.is_dir():
                continue
            
            for tif_file in source_dir.glob('*.tif'):
                meta_file = get_metadata_path(tif_file)
                if meta_file.exists():
                    try:
                        metadata = load_metadata(meta_file)
                        regions.add(metadata.get('region_id', tif_file.stem.split('_')[0]))
                    except:
                        continue
        
        return sorted(list(regions))
    
    def _get_available_stages(self, region_id: str) -> List[str]:
        """Get list of stages that have data for a region."""
        available = []
        for stage in ['raw', 'clipped', 'processed']:
            if self.find_region_files(region_id, stage):
                available.append(stage)
        return available
    
    def validate_cache(self, region_id: str, stage: str) -> Tuple[bool, str]:
        """
        Validate that cached data is still valid.
        
        Checks:
        - Version compatibility
        - Source file hasn't changed (for derived stages)
        
        Args:
            region_id: Region identifier
            stage: Pipeline stage to validate
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            sources = self.find_region_files(region_id, stage)
            
            if not sources:
                return False, f"No {stage} data found"
            
            for source in sources:
                metadata = source.metadata
                
                # Check version
                try:
                    check_version(metadata, stage, region_id)
                except VersionMismatchError as e:
                    return False, str(e)
                
                # For derived stages, check source file
                if stage in ['clipped', 'processed'] and 'source_file' in metadata:
                    source_file = Path(metadata['source_file'])
                    expected_hash = metadata.get('source_file_hash')
                    
                    if expected_hash and not validate_source_file(source_file, expected_hash):
                        return False, f"Source file {source_file.name} has changed since processing"
            
            return True, "All cache valid"
            
        except Exception as e:
            return False, f"Validation error: {e}"


def create_source_registry(data_root: Path = Path('data')) -> Dict:
    """
    Create a registry of all available data sources.
    
    This scans the data directory and creates a comprehensive index of what's available.
    
    Args:
        data_root: Root data directory
        
    Returns:
        Registry dictionary
    """
    dm = DataManager(data_root)
    registry = {
        "generated": __import__('datetime').datetime.now().isoformat(),
        "regions": {}
    }
    
    # Get all regions
    all_regions = set()
    for stage in ['raw', 'clipped', 'processed']:
        all_regions.update(dm.list_all_regions(stage))
    
    # Build registry for each region
    for region_id in sorted(all_regions):
        region_data = {
            "id": region_id,
            "sources": {}
        }
        
        for stage in ['raw', 'clipped', 'processed']:
            sources = dm.find_region_files(region_id, stage)
            if sources:
                region_data["sources"][stage] = [
                    {
                        "source": s.source,
                        "resolution_m": s.resolution_m,
                        "path": str(s.path),
                        "file_size_mb": s.metadata.get('file_size_mb', 0)
                    }
                    for s in sources
                ]
        
        registry["regions"][region_id] = region_data
    
    return registry


if __name__ == "__main__":
    # Test/demo
    print("Data Manager Demo")
    print("=" * 70)
    
    dm = DataManager()
    
    # List all regions
    print("\nAvailable Regions:")
    for stage in ['raw', 'clipped', 'processed']:
        regions = dm.list_all_regions(stage)
        if regions:
            print(f"  {stage:12s}: {len(regions)} regions")
    
    print("\n" + "=" * 70)
    print("Usage Example:")
    print("=" * 70)
    print("""
from src.data_manager import DataManager

dm = DataManager()

# Load highest-resolution data available
elevation, meta = dm.load_region('california', prefer_source='usa_3dep')

# Check what sources are available
sources = dm.list_sources('california')
print(f"Available: {sources}")

# Validate cache
valid, message = dm.validate_cache('california', 'clipped')
if not valid:
    print(f"Cache invalid: {message}")
""")

