"""
Centralized region definitions.

This is the SINGLE SOURCE OF TRUTH for all region definitions in the project.
Add or remove regions here to control:
- Which regions are available for download
- Which regions appear in the viewer
- Download bounds, boundary clipping, and metadata

IMPORTANT: This file is for REGION DEFINITIONS only.
- Having a region here does NOT mean data exists for it
- Data availability is checked separately (manifest, raw files)
- Download logic is in src/downloaders/
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List
from pathlib import Path

from src.types import RegionType

Bounds = Tuple[float, float, float, float]  # (west, south, east, north)


@dataclass
class RegionConfig:
    """
    Configuration for a single region.
    
    The tiles field specifies tiling configuration for large regions that exceed
    API size limits (typically >4deg in any dimension). Format is (columns, rows).
    For example, tiles=(3, 2) means split into a 3-column by 2-row grid.
    
    Tiling is used when downloading from OpenTopography or similar APIs that
    reject requests for areas larger than ~4deg. The downloader will automatically
    split the region into the specified grid, download each tile, and merge them.
    
    Only set tiles for regions that actually need tiling. Leave as None for regions
    that can be downloaded in a single API request.
    """
    id: str  # Unique identifier (lowercase with underscores)
    name: str  # Display name
    bounds: Bounds  # (west, south, east, north) in degrees
    description: Optional[str] = None
    region_type: RegionType = RegionType.REGION  # Region type: USA_STATE, COUNTRY, or REGION
    country: Optional[str] = None  # Country name if applicable
    clip_boundary: bool = True  # Whether to clip to administrative boundary
    # If set (e.g., 'SRTMGL1' or 'COP30'), this overrides latitude-based selection.
    # Default None means: choose dataset by latitude (SRTM within 60degN-56degS; COP30 otherwise).
    recommended_dataset: Optional[str] = None
    tiles: Optional[Tuple[int, int]] = None  # Tiling configuration (cols, rows) for large regions that need downloading in parts


# ============================================================================
# US STATES
# ============================================================================

US_STATES: Dict[str, RegionConfig] = {
    
    "arizona": RegionConfig(
        id="arizona",
        name="Arizona",
        bounds=(-114.82, 31.33, -109.05, 37.00),
        description="Arizona - Grand Canyon",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
        tiles=(2, 2),  # 5.77deg x 5.67deg -> 2x2 tiles
    ),
    "iowa": RegionConfig(
        id="iowa",
        name="Iowa",
        bounds=(-96.639, 40.375, -90.140, 43.501),
        description="Iowa",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "indiana": RegionConfig(
        id="indiana",
        name="Indiana",
        bounds=(-88.097, 37.771, -84.784, 41.759),
        description="Indiana",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "kentucky": RegionConfig(
        id="kentucky",
        name="Kentucky",
        bounds=(-89.571, 36.497, -81.964, 39.147),
        description="Kentucky",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "tennessee": RegionConfig(
        id="tennessee",
        name="Tennessee",
        bounds=(-90.31, 34.98, -81.65, 36.68),
        description="Tennessee",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "california": RegionConfig(
        id="california",
        name="California",
        bounds=(-124.48, 32.53, -114.13, 42.01),
        description="California",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
        tiles=(3, 3),  # 10.35deg x 9.48deg -> 3x3 tiles
    ),
    "south_dakota": RegionConfig(
        id="south_dakota",
        name="South Dakota",
        bounds=(-104.057, 42.479, -96.436, 45.945),
        description="South Dakota",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "colorado": RegionConfig(
        id="colorado",
        name="Colorado",
        bounds=(-109.06, 36.99, -102.04, 41.00),
        description="Colorado - Rocky Mountains",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "wisconsin": RegionConfig(
        id="wisconsin",
        name="Wisconsin",
        bounds=(-92.889, 42.491, -86.249, 47.309),
        description="Wisconsin",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    
    
    "kansas": RegionConfig(
        id="kansas",
        name="Kansas",
        bounds=(-102.05, 36.99, -94.59, 40.00),
        description="Kansas",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "wyoming": RegionConfig(
        id="wyoming",
        name="Wyoming",
        bounds=(-111.056, 40.994, -104.052, 45.005),
        description="Wyoming",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "maine": RegionConfig(
        id="maine",
        name="Maine",
        bounds=(-71.08, 42.98, -66.95, 47.46),
        description="Maine",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "minnesota": RegionConfig(
        id="minnesota",
        name="Minnesota",
        bounds=(-97.24, 43.50, -89.49, 49.38),
        description="Minnesota",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
        tiles=(2, 2),  # ~7.75deg x ~5.88deg -> split for API friendliness
    ),
    "michigan": RegionConfig(
        id="michigan",
        name="Michigan",
        bounds=(-90.42, 41.70, -82.12, 48.31),
        description="Michigan",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
        tiles=(2, 2),  # ~8.3deg x ~6.6deg -> split for API friendliness
    ),
    
    
    "nebraska": RegionConfig(
        id="nebraska",
        name="Nebraska",
        bounds=(-104.05, 40.00, -95.31, 43.00),
        description="Nebraska",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "nevada": RegionConfig(
        id="nevada",
        name="Nevada",
        bounds=(-120.01, 35.00, -114.04, 42.00),
        description="Nevada",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
        tiles=(2, 2),  # 5.97deg x 7deg -> 2x2 tiles
    ),
    "new_hampshire": RegionConfig(
        id="new_hampshire",
        name="New Hampshire",
        bounds=(-72.56, 42.70, -70.70, 45.31),
        description="New Hampshire",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "new_jersey": RegionConfig(
        id="new_jersey",
        name="New Jersey",
        bounds=(-75.56, 38.93, -73.89, 41.36),
        description="New Jersey",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "new_mexico": RegionConfig(
        id="new_mexico",
        name="New Mexico",
        bounds=(-109.05, 31.33, -103.00, 37.00),
        description="New Mexico",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
        tiles=(2, 2),  # 6.05deg x 5.67deg -> 2x2 tiles
    ),
    "new_york": RegionConfig(
        id="new_york",
        name="New York",
        bounds=(-79.76, 40.50, -71.86, 45.02),
        description="New York State",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "north_carolina": RegionConfig(
        id="north_carolina",
        name="North Carolina",
        bounds=(-84.32, 33.84, -75.46, 36.59),
        description="North Carolina",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "north_dakota": RegionConfig(
        id="north_dakota",
        name="North Dakota",
        bounds=(-104.05, 45.94, -96.55, 49.00),
        description="North Dakota",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "ohio": RegionConfig(
        id="ohio",
        name="Ohio",
        bounds=(-84.82, 38.40, -80.52, 41.98),
        description="Ohio",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "oregon": RegionConfig(
        id="oregon",
        name="Oregon",
        bounds=(-124.57, 41.99, -116.46, 46.29),
        description="Oregon",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
        tiles=(3, 2),  # 8.11deg x 4.3deg -> 3x2 tiles
    ),
    "pennsylvania": RegionConfig(
        id="pennsylvania",
        name="Pennsylvania",
        bounds=(-80.52, 39.72, -74.69, 42.27),
        description="Pennsylvania",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "utah": RegionConfig(
        id="utah",
        name="Utah",
        bounds=(-114.05, 37.00, -109.04, 42.00),
        description="Utah",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "vermont": RegionConfig(
        id="vermont",
        name="Vermont",
        bounds=(-73.44, 42.73, -71.46, 45.02),
        description="Vermont",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
    ),
    "washington": RegionConfig(
        id="washington",
        name="Washington",
        bounds=(-124.79, 45.54, -116.92, 49.00),
        description="Washington",
        region_type=RegionType.USA_STATE,
        country="United States of America",
        clip_boundary=True,
        tiles=(2, 2),
    ),
}


# ============================================================================
# COUNTRIES
# ============================================================================

COUNTRIES: Dict[str, RegionConfig] = {
    
    "estonia": RegionConfig(
        id="estonia",
        name="Estonia",
        bounds=(21.8, 57.5, 28.2, 59.7),
        description="Republic of Estonia (Baltic)",
        region_type=RegionType.COUNTRY,
        country="Estonia",
        clip_boundary=True,
    ),
    "georgia_country": RegionConfig(
        id="georgia_country",
        name="Georgia",
        bounds=(40.0, 41.0, 46.8, 43.7),
        description="Country of Georgia (Caucasus)",
        region_type=RegionType.COUNTRY,
        country="Georgia",
        clip_boundary=True,
    ),
    "kyrgyzstan": RegionConfig(
        id="kyrgyzstan",
        name="Kyrgyzstan",
        bounds=(69.2, 39.1, 80.3, 43.3),
        description="Kyrgyz Republic (Tian Shan)",
        region_type=RegionType.COUNTRY,
        country="Kyrgyzstan",
        clip_boundary=True,
    ),
    "singapore": RegionConfig(
        id="singapore",
        name="Singapore",
        bounds=(103.6, 1.16, 104.1, 1.48),
        description="Republic of Singapore",
        region_type=RegionType.COUNTRY,
        country="Singapore",
        clip_boundary=True,
    ),
    "turkiye": RegionConfig(
        id="turkiye",
        name="Turkiye",
        bounds=(25.0, 35.8, 45.0, 42.3),
        description="Republic of Turkiye",
        region_type=RegionType.COUNTRY,
        country="Turkiye",
        clip_boundary=True,
    ),
    "hong_kong": RegionConfig(
        id="hong_kong",
        name="Hong Kong",
        bounds=(113.8, 22.15, 114.4, 22.6),
        description="Hong Kong SAR",
        region_type=RegionType.COUNTRY,
        country="Hong Kong",
        clip_boundary=True,
    ),
    "iceland": RegionConfig(
        id="iceland",
        name="Iceland",
        bounds=(-24.5, 63.4, -13.5, 66.6),
        description="Iceland - volcanic terrain",
        region_type=RegionType.COUNTRY,
        country="Iceland",
        clip_boundary=True,
    ),
    "faroe_islands": RegionConfig(
        id="faroe_islands",
        name="Faroe Islands",
        bounds=(-7.7, 61.4, -6.2, 62.4),
        description="Faroe Islands - North Atlantic archipelago",
        region_type=RegionType.COUNTRY,
        country="Faroe Islands",
        clip_boundary=True,
    ),
}


# ============================================================================
# REGIONS (Non-country areas: islands, peninsulas, mountain ranges, etc.)
# ============================================================================

REGIONS: Dict[str, RegionConfig] = {
    "anticosti_island": RegionConfig(
        id="anticosti_island",
        name="Anticosti Island",
        bounds=(-64.7, 48.9, -61.6, 50.0),
        description="Canada - Anticosti Island (Quebec)",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "central_new_jersey": RegionConfig(
        id="central_new_jersey",
        name="Central New Jersey",
        bounds=(-74.857, 40.152, -74.286, 40.587),
        description="USA - Central New Jersey region, roughly square area starting ~6 miles NE of Piscataway and extending ~30 miles southwest",
        region_type=RegionType.REGION,
        country="United States of America",
        clip_boundary=False,
    ),
    "cottonwood_valley": RegionConfig(
        id="cottonwood_valley",
        name="Cottonwood Valley",
        bounds=(-111.8318, 40.5581, -111.5822, 40.6154),
        description="USA - Cottonwood Valley, Utah, ~13x4 mile area near Salt Lake City",
        region_type=RegionType.REGION,
        country="United States of America",
        clip_boundary=False,
    ),
    "greenville_sc": RegionConfig(
        id="greenville_sc",
        name="Greenville, SC",
        bounds=(-82.8940, 34.4776, -81.8940, 35.2276),
        description="USA - City of Greenville, South Carolina, 50x50 mile square centered on the city",
        region_type=RegionType.REGION,
        country="United States of America",
        clip_boundary=False,
    ),
    "helsinki": RegionConfig(
        id="helsinki",
        name="Helsinki",
        bounds=(24.4, 59.8, 25.5, 60.5),
        description="Finland - Helsinki metropolitan area including city center, harbor, and major landmarks",
        region_type=RegionType.REGION,
        country="Finland",
        clip_boundary=False,
    ),
    "arkhangelsk_area": RegionConfig(
        id="arkhangelsk_area",
        name="Arkhangelsk Area",
        bounds=(36.0, 61.0, 50.0, 66.5),
        description="Russia - Arkhangelsk Oblast and White Sea coast",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "gotland_island": RegionConfig(
        id="gotland_island",
        name="Gotland Island",
        bounds=(17.9, 56.8, 19.5, 58.2),
        description="Sweden - Gotland (Baltic Sea)",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    
    "kamchatka": RegionConfig(
        id="kamchatka",
        name="Kamchatka Peninsula",
        bounds=(156.0, 50.5, 163.0, 62.5),
        description="Russia - Kamchatka Peninsula",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "las_malvinas": RegionConfig(
        id="las_malvinas",
        name="Las Malvinas (Falkland Islands)",
        bounds=(-61.5, -53.2, -57.4, -50.9),
        description="Falkland Islands / Islas Malvinas (UK territory)",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "mindoro_island": RegionConfig(
        id="mindoro_island",
        name="Mindoro Island",
        bounds=(120.0, 12.0, 121.5, 13.7),
        description="Philippines - Mindoro",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "peninsula": RegionConfig(
        id="peninsula",
        name="San Mateo Area",
        bounds=(-122.53, 37.43, -122.24, 37.70),
        description="Union of Foster City, San Mateo, Burlingame, Half Moon Bay (approx bbox)",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "sakhalin_island": RegionConfig(
        id="sakhalin_island",
        name="Sakhalin Island",
        bounds=(141.2, 45.6, 146.1, 54.6),
        description="Russia - Sakhalin",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "san_mateo": RegionConfig(
        id="san_mateo",
        name="San Francisco Peninsula",
        bounds=(-122.6, 37.0, -121.8, 37.9),
        description="SF Peninsula: San Jose to San Francisco",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "south_georgia_island": RegionConfig(
        id="south_georgia_island",
        name="South Georgia Island",
        bounds=(-38.5, -55.1, -35.2, -53.5),
        description="South Georgia (Shackleton rescue at Grytviken)",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "tasmania": RegionConfig(
        id="tasmania",
        name="Tasmania",
        bounds=(144.0, -44.2, 149.0, -39.1),
        description="Tasmania (Australia) - island south of mainland",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "manicouagan_reservoir": RegionConfig(
        id="manicouagan_reservoir",
        name="Manicouagan Crater and Rene-Levasseur",
        bounds=(-69.60, 50.80, -67.80, 52.00),
        description="Quebec, Canada - Circular reservoir with circular island (Rene-Levasseur)",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "taal_nested_islands": RegionConfig(
        id="taal_nested_islands",
        name="Taal Volcano Nested Islands",
        bounds=(120.80, 13.85, 121.10, 14.20),
        description="Philippines - Lake with island with lake with island (Taal Volcano)",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "devils_tower_area": RegionConfig(
        id="devils_tower_area",
        name="Devils Tower Area",
        bounds=(-104.78, 44.54, -104.64, 44.64),
        description="Wyoming, USA - Columnar jointing (hexagonal towers) landmark",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "vancouver_island": RegionConfig(
        id="vancouver_island",
        name="Vancouver Island",
        bounds=(-129.0, 48.2, -123.0, 50.9),
        description="Canada - Vancouver Island (British Columbia)",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "yakutsk_area": RegionConfig(
        id="yakutsk_area",
        name="Yakutsk Area",
        bounds=(124.0, 59.0, 136.0, 65.0),
        description="Russia - Yakutsk and surrounding region",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "western_canadian_rockies": RegionConfig(
        id="western_canadian_rockies",
        name="Western Canadian Rockies",
        bounds=(-121.0, 49.0, -116.0, 55.0),
        description="Canada - Western Canadian Rockies (British Columbia/Alberta), ~210x414 miles featuring Jasper, Banff, and surrounding peaks",
        region_type=RegionType.REGION,
        clip_boundary=False,
    ),
    "mavericks_coast": RegionConfig(
        id="mavericks_coast",
        name="Mavericks",
        bounds=(-122.529, 37.473, -122.474, 37.516),
        description="California - 3x3 mile area around Mavericks surf spot, just north of Half Moon Bay",
        region_type=RegionType.REGION,
        country="United States of America",
        clip_boundary=False,
    ),
    "homer_alaska": RegionConfig(
        id="homer_alaska",
        name="Homer, Alaska",
        bounds=(-151.9, 59.4, -151.2, 59.9),
        description="USA - Homer, Alaska, ~20x20 mile region on Kachemak Bay",
        region_type=RegionType.REGION,
        country="United States of America",
        clip_boundary=False,
    ),
    "bar_harbor_maine": RegionConfig(
        id="bar_harbor_maine",
        name="Bar Harbor and Acadia",
        bounds=(-69.0, 43.5, -67.5, 45.0),
        description="USA - Bar Harbor and Acadia National Park area, Maine, ~50x50 mile region",
        region_type=RegionType.REGION,
        country="United States of America",
        clip_boundary=False,
    ),
    "venice_lagoon": RegionConfig(
        id="venice_lagoon",
        name="Venice Lagoon",
        bounds=(12.0, 45.2, 12.7, 45.7),
        description="Italy - Venice and the Venetian Lagoon with its many islands",
        region_type=RegionType.REGION,
        country="Italy",
        clip_boundary=False,
    ),
    "san_francisco": RegionConfig(
        id="san_francisco",
        name="San Francisco",
        bounds=(-122.52, 37.74, -122.36, 37.82),
        description="USA - San Francisco proper, from Bernal Heights to Presidio, Outer Sunset to Oracle Park",
        region_type=RegionType.REGION,
        country="United States of America",
        clip_boundary=False,
    ),
    "alcatraz": RegionConfig(
        id="alcatraz",
        name="Alcatraz Island",
        bounds=(-122.427, 37.824, -122.419, 37.830),
        description="USA - Alcatraz Island in San Francisco Bay with surrounding water",
        region_type=RegionType.REGION,
        country="United States of America",
        clip_boundary=False,
    ),
    "baja_california": RegionConfig(
        id="baja_california",
        name="Baja California Peninsula",
        bounds=(-117.1, 22.8, -109.4, 32.7),
        description="Mexico - Baja California Peninsula (Baja California and Baja California Sur)",
        region_type=RegionType.REGION,
        country="Mexico",
        clip_boundary=False,
        tiles=(2, 3),  # 7.7deg x 9.9deg -> 2x3 tiles for API friendliness
    ),
    "massanutten_mountain": RegionConfig(
        id="massanutten_mountain",
        name="Massanutten Mountain",
        bounds=(-78.8, 38.6, -78.5, 38.9),
        description="Virginia - Massanutten Mountain, distinctive ridgeline in Shenandoah Valley, ~50 miles long",
        region_type=RegionType.REGION,
        country="United States of America",
        clip_boundary=False,
    ),
    "mount_washington": RegionConfig(
        id="mount_washington",
        name="Mount Washington",
        bounds=(-71.4, 44.2, -71.2, 44.35),
        description="New Hampshire - Mount Washington peak area, famous for extreme weather and 231 mph wind record",
        region_type=RegionType.REGION,
        country="United States of America",
        clip_boundary=False,
    ),
}


# ============================================================================
# REGISTRY
# ============================================================================

# Combined registry of all regions (US states, countries, and regions)
ALL_REGIONS: Dict[str, RegionConfig] = {**US_STATES, **COUNTRIES, **REGIONS}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_region(region_id: str) -> Optional[RegionConfig]:
    """Get region configuration by ID."""
    region_id = region_id.lower().replace(" ", "_").replace("-", "_")
    return ALL_REGIONS.get(region_id)


def list_regions(category: Optional[str] = None) -> List[RegionConfig]:
    """List all regions, optionally filtered by category."""
    regions = list(ALL_REGIONS.values())
    if category:
        regions = [r for r in regions if r.category == category]
    return sorted(regions, key=lambda r: r.name.lower())


def get_us_state_names() -> Dict[str, str]:
    """Get mapping of US state IDs to display names."""
    return {state_id: config.name for state_id, config in US_STATES.items()}


def get_us_state_bounds() -> Dict[str, Bounds]:
    """Get mapping of US state IDs to bounds."""
    return {state_id: config.bounds for state_id, config in US_STATES.items()}


# ============================================================================
# DATA AVAILABILITY CHECKING
# ============================================================================

def check_region_data_available(region_id: str) -> Dict[str, bool]:
    """
    Check if data exists for a region at each stage of the pipeline.
    
    Returns a dict with status for each stage:
    - 'configured': Region exists in config (always True if region_id is valid)
    - 'raw_file': Raw data file exists
    - 'processed': Processed data exists
    - 'in_manifest': Region appears in viewer manifest
    
    Args:
        region_id: Region identifier
        
    Returns:
        Dict with stage names as keys and bool values
    """
    region_id = region_id.lower().replace(" ", "_").replace("-", "_")
    
    # Check if region is configured
    configured = region_id in ALL_REGIONS
    
    if not configured:
        return {
            'configured': False,
            'raw_file': False,
            'processed': False,
            'in_manifest': False
        }
    
    config = ALL_REGIONS[region_id]
    
    # Check for raw file
    raw_file_exists = False
    possible_raw_locations = [
        Path(f"data/raw/srtm_30m/{region_id}_bbox_30m.tif"),
        Path(f"data/raw/usa_3dep/{region_id}_3dep_10m.tif"),
    ]
    for loc in possible_raw_locations:
        if loc.exists() and loc.stat().st_size > 1024:  # At least 1KB
            raw_file_exists = True
            break
    
    # Check for processed data
    processed_exists = False
    processed_dir = Path("generated/regions")
    if processed_dir.exists():
        json_files = list(processed_dir.glob(f"{region_id}_*.json"))
        json_files = [f for f in json_files if '_borders' not in f.stem and '_meta' not in f.stem]
        if len(json_files) > 0:
            processed_exists = True
    
    # Check manifest
    in_manifest = False
    manifest_path = Path("generated/regions/regions_manifest.json")
    if manifest_path.exists():
        try:
            import json
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
                in_manifest = region_id in manifest.get('regions', {})
        except Exception:
            pass
    
    return {
        'configured': True,
        'raw_file': raw_file_exists,
        'processed': processed_exists,
        'in_manifest': in_manifest
    }


def list_available_regions() -> Dict[str, List[str]]:
    """
    List all regions, categorized by data availability.
    
    Returns:
        Dict with keys:
        - 'downloaded': Regions with raw data files
        - 'processed': Regions with processed JSON files
        - 'in_viewer': Regions appearing in manifest
        - 'not_started': Configured but no data yet
    """
    downloaded = []
    processed = []
    in_viewer = []
    not_started = []
    
    for region_id in ALL_REGIONS.keys():
        status = check_region_data_available(region_id)
        
        if status['in_manifest']:
            in_viewer.append(region_id)
        elif status['processed']:
            processed.append(region_id)
        elif status['raw_file']:
            downloaded.append(region_id)
        else:
            not_started.append(region_id)
    
    return {
        'downloaded': sorted(downloaded),
        'processed': sorted(processed),
        'in_viewer': sorted(in_viewer),
        'not_started': sorted(not_started)
    }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def is_region_configured(region_id: str) -> bool:
    """Check if a region is configured in the registry."""
    return region_id.lower().replace(" ", "_").replace("-", "_") in ALL_REGIONS


def get_region_bounds(region_id: str) -> Optional[Bounds]:
    """Get bounds for a region."""
    config = get_region(region_id)
    return config.bounds if config else None


def should_clip_boundary(region_id: str) -> bool:
    """Check if a region should be clipped to administrative boundaries."""
    config = get_region(region_id)
    return config.clip_boundary if config else True  # Default to True


