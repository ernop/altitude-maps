"""
Source capability registry and generic source selection.

Each data source declares its capabilities (resolution, coverage, etc.).
The selector evaluates requirements against capabilities and returns an ordered list to try.

NO HARDCODED REGION-SPECIFIC LOGIC. Sources declare capabilities, selector picks based on match.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Set
from pathlib import Path


@dataclass
class SourceCapability:
    """Declares what a data source provides."""
    
    source_id: str                    # Unique identifier (e.g., 'usgs_3dep', 'copernicus_s3_30m')
    name: str                         # Human-readable name
    resolution_m: int                 # Resolution in meters (10, 30, 90, 250, 500, 1000)
    coverage_lat: Tuple[float, float] # (min_lat, max_lat) in degrees
    coverage_lon: Tuple[float, float] # (min_lon, max_lon) in degrees or None for global
    tile_dir: str                     # Subdirectory in data/raw/ for tiles
    merged_dir: str                   # Subdirectory in data/merged/ for merged files
    requires_auth: bool               # Whether API key or authentication needed
    auth_key_name: Optional[str]      # Key name in settings.json if requires_auth
    notes: str = ""                   # Additional information
    
    def covers_region(self, bounds: Tuple[float, float, float, float]) -> bool:
        """Check if this source covers the given bounds (west, south, east, north)."""
        west, south, east, north = bounds
        
        # Check latitude coverage
        if south < self.coverage_lat[0] or north > self.coverage_lat[1]:
            return False
        
        # If coverage_lon is None, assume global longitude coverage
        if self.coverage_lon is None:
            return True
        
        # Check longitude coverage (handles date line crossing if needed)
        lon_min, lon_max = self.coverage_lon
        if lon_min <= west and east <= lon_max:
            return True
        
        return False
    
    def matches_resolution(self, required_resolution_m: int) -> bool:
        """Check if this source provides the required resolution."""
        return self.resolution_m == required_resolution_m


# Registry of all available data sources
# Order in this list determines default priority (user can override)
SOURCE_REGISTRY: List[SourceCapability] = [
    # 10m sources
    SourceCapability(
        source_id='usgs_3dep',
        name='USGS 3DEP',
        resolution_m=10,
        coverage_lat=(18.0, 72.0),      # Approximate US coverage
        coverage_lon=(-180.0, -60.0),   # Approximate US coverage (including Alaska)
        tile_dir='usa_3dep',
        merged_dir='usa_3dep',
        requires_auth=False,
        auth_key_name=None,
        notes='High-quality LiDAR for United States'
    ),
    
    # NOTE: Copernicus GLO-10 is NOT publicly available via S3
    # Only GLO-30 and GLO-90 are public
    
    # 30m sources
    SourceCapability(
        source_id='opentopo_srtm_30m',
        name='SRTM 30m (OpenTopography)',
        resolution_m=30,
        coverage_lat=(-56.0, 60.0),     # SRTM coverage
        coverage_lon=None,              # Global longitude
        tile_dir='srtm_30m',
        merged_dir='srtm_30m',
        requires_auth=True,
        auth_key_name='opentopography.api_key',
        notes='SRTM data via OpenTopography API'
    ),
    
    SourceCapability(
        source_id='opentopo_copernicus_30m',
        name='Copernicus 30m (OpenTopography)',
        resolution_m=30,
        coverage_lat=(-90.0, 90.0),     # True global
        coverage_lon=None,              # Global longitude
        tile_dir='srtm_30m',
        merged_dir='srtm_30m',
        requires_auth=True,
        auth_key_name='opentopography.api_key',
        notes='Copernicus DEM via OpenTopography API'
    ),
    
    SourceCapability(
        source_id='copernicus_s3_30m',
        name='Copernicus GLO-30 (S3)',
        resolution_m=30,
        coverage_lat=(-90.0, 90.0),     # True global
        coverage_lon=None,              # Global longitude
        tile_dir='copernicus_s3_30m',
        merged_dir='srtm_30m',          # Merge into same dir (same resolution)
        requires_auth=False,
        auth_key_name=None,
        notes='Direct S3 access, no rate limits'
    ),
    
    SourceCapability(
        source_id='aw3d30',
        name='ALOS AW3D30',
        resolution_m=30,
        coverage_lat=(-82.0, 82.0),     # AW3D coverage
        coverage_lon=None,              # Global longitude
        tile_dir='aw3d30',
        merged_dir='aw3d30',
        requires_auth=True,
        auth_key_name='opentopography.api_key',
        notes='High-quality Japanese satellite data via OpenTopography'
    ),
    
    # 90m sources
    SourceCapability(
        source_id='opentopo_srtm_90m',
        name='SRTM 90m (OpenTopography)',
        resolution_m=90,
        coverage_lat=(-56.0, 60.0),     # SRTM coverage
        coverage_lon=None,              # Global longitude
        tile_dir='srtm_90m',
        merged_dir='srtm_90m',
        requires_auth=True,
        auth_key_name='opentopography.api_key',
        notes='SRTM 90m via OpenTopography API'
    ),
    
    SourceCapability(
        source_id='opentopo_copernicus_90m',
        name='Copernicus 90m (OpenTopography)',
        resolution_m=90,
        coverage_lat=(-90.0, 90.0),     # True global
        coverage_lon=None,              # Global longitude
        tile_dir='srtm_90m',
        merged_dir='srtm_90m',
        requires_auth=True,
        auth_key_name='opentopography.api_key',
        notes='Copernicus 90m via OpenTopography API'
    ),
    
    SourceCapability(
        source_id='copernicus_s3_90m',
        name='Copernicus GLO-90 (S3)',
        resolution_m=90,
        coverage_lat=(-90.0, 90.0),     # True global
        coverage_lon=None,              # Global longitude
        tile_dir='copernicus_s3_90m',
        merged_dir='srtm_90m',          # Merge into same dir (same resolution)
        requires_auth=False,
        auth_key_name=None,
        notes='Direct S3 access, no rate limits'
    ),
    
    # Coarse sources (250m, 500m, 1km)
    SourceCapability(
        source_id='gmted2010_250m',
        name='GMTED2010 250m',
        resolution_m=250,
        coverage_lat=(-90.0, 90.0),
        coverage_lon=None,
        tile_dir='gmted2010_250m',
        merged_dir='gmted2010_250m',
        requires_auth=False,
        auth_key_name=None,
        notes='Coarse global DEM'
    ),
    
    SourceCapability(
        source_id='gmted2010_500m',
        name='GMTED2010 500m',
        resolution_m=500,
        coverage_lat=(-90.0, 90.0),
        coverage_lon=None,
        tile_dir='gmted2010_500m',
        merged_dir='gmted2010_500m',
        requires_auth=False,
        auth_key_name=None,
        notes='Coarse global DEM'
    ),
    
    SourceCapability(
        source_id='gmted2010_1km',
        name='GMTED2010 1km',
        resolution_m=1000,
        coverage_lat=(-90.0, 90.0),
        coverage_lon=None,
        tile_dir='gmted2010_1km',
        merged_dir='gmted2010_1km',
        requires_auth=False,
        auth_key_name=None,
        notes='Very coarse global DEM'
    ),
    
    SourceCapability(
        source_id='globe_1km',
        name='GLOBE 1km',
        resolution_m=1000,
        coverage_lat=(-90.0, 90.0),
        coverage_lon=None,
        tile_dir='globe_1km',
        merged_dir='globe_1km',
        requires_auth=False,
        auth_key_name=None,
        notes='Simple global DEM'
    ),
]


def get_source_by_id(source_id: str) -> Optional[SourceCapability]:
    """Get source capability by ID."""
    for source in SOURCE_REGISTRY:
        if source.source_id == source_id:
            return source
    return None


def select_sources(
    required_resolution_m: int,
    region_bounds: Tuple[float, float, float, float],
    user_priority: Optional[List[str]] = None
) -> List[SourceCapability]:
    """
    Select sources to try for given requirements.
    
    Generic selector: evaluates source capabilities vs requirements.
    Returns ordered list of sources to try.
    
    Args:
        required_resolution_m: Required resolution in meters
        region_bounds: (west, south, east, north) in degrees
        user_priority: Optional list of source_ids to prefer (in order)
        
    Returns:
        Ordered list of SourceCapability objects to try
    """
    # Filter sources that match requirements
    candidates = []
    for source in SOURCE_REGISTRY:
        if source.matches_resolution(required_resolution_m) and source.covers_region(region_bounds):
            candidates.append(source)
    
    if not candidates:
        return []
    
    # If user specified priority, reorder candidates accordingly
    if user_priority:
        ordered = []
        remaining = candidates.copy()
        
        # Add sources in user's preferred order
        for preferred_id in user_priority:
            for source in remaining:
                if source.source_id == preferred_id:
                    ordered.append(source)
                    remaining.remove(source)
                    break
        
        # Add any remaining sources (not in user priority list) at end
        ordered.extend(remaining)
        return ordered
    
    # Default: use registry order
    return candidates


def load_user_source_priority() -> Optional[List[str]]:
    """
    Load user-configured source priority from settings.json.
    
    Returns None if not configured (use default order).
    """
    try:
        from load_settings import load_settings
        settings = load_settings()
        return settings.get('data_sources', {}).get('priority', None)
    except Exception:
        return None


def get_sources_for_download(
    required_resolution_m: int,
    region_bounds: Tuple[float, float, float, float]
) -> List[SourceCapability]:
    """
    Get ordered list of sources to try for download.
    
    This is the main entry point for download orchestration.
    """
    user_priority = load_user_source_priority()
    return select_sources(required_resolution_m, region_bounds, user_priority)

