"""
Centralized regions registry for unified downloads.

This module aggregates region definitions from existing source-specific modules
into a normalized registry that the unified downloader can use to:
- Look up bounds by region id
- Decide boundary clipping strategy (country/state/none)
- Suggest a default dataset for automated downloads

Notes:
- Region identifiers are normalized to lowercase with underscores.
- If a region exists in multiple sources, we prefer the most specific source:
  USA (state/full) > Japan > Switzerland > High-Res curated > Generic.

This file is internal (maintained by developers) and not meant for user edits.

 IMPORTANT: This is a library module, NOT an entry point.
   Do NOT wrap sys.stdout/stderr here - let the calling script handle it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List
import sys


Bounds = Tuple[float, float, float, float]  # (west, south, east, north)


@dataclass(frozen=True)
class RegionEntry:
    id: str
    name: str
    bounds: Bounds
    category: str  # e.g., 'usa_state', 'usa_full', 'japan', 'switzerland', 'generic', 'highres'
    country: Optional[str]
    boundary_type: Optional[str]  # 'country' | 'state' | None
    boundary_name: Optional[str]  # e.g., 'United States of America/Tennessee' or 'Japan'
    recommended_dataset: Optional[str]  # e.g., 'SRTMGL1', 'AW3D30', 'COP30'


def _normalize_id(raw_id: str) -> str:
    return raw_id.strip().lower().replace(" ", "_").replace("-", "_")


def _build_registry() -> Dict[str, RegionEntry]:
    """Build the unified regions registry from all sources."""
    registry: Dict[str, RegionEntry] = {}
    
    # Suppress import warnings to avoid stderr issues during registry build
    import warnings
    warnings.filterwarnings('ignore')

    # 1) USA (states and full coverage)
    try:
        from downloaders.usa_3dep import US_STATES, USA_FULL_BOUNDS  # type: ignore

        # Full USA variants
        for rid, info in USA_FULL_BOUNDS.items():
            region_id = _normalize_id(rid)
            name = info["name"]
            bounds: Bounds = tuple(info["bounds"])  # type: ignore
            registry[region_id] = RegionEntry(
                id=region_id,
                name=name,
                bounds=bounds,
                category="usa_full",
                country="United States of America",
                boundary_type="country",
                boundary_name="United States of America",
                recommended_dataset="SRTMGL1",
            )

        # Individual US states
        for rid, info in US_STATES.items():
            region_id = _normalize_id(rid)
            name = info["name"]
            bounds: Bounds = tuple(info["bounds"])  # type: ignore
            registry[region_id] = RegionEntry(
                id=region_id,
                name=name,
                bounds=bounds,
                category="usa_state",
                country="United States of America",
                boundary_type="state",
                boundary_name=f"United States of America/{name}",
                recommended_dataset="SRTMGL1",
            )
    except Exception:
        # If imports fail, leave USA entries empty; unified CLI can still handle others.
        pass

    # 2) Japan regions
    try:
        from downloaders.japan_gsi import JAPAN_REGIONS  # type: ignore

        for rid, info in JAPAN_REGIONS.items():
            region_id = _normalize_id(rid)
            bounds: Bounds = tuple(info["bounds"])  # type: ignore
            name = info.get("name", region_id.replace("_", " ").title())
            # Prefer AW3D30 for Japan in auto mode
            entry = RegionEntry(
                id=region_id,
                name=name,
                bounds=bounds,
                category="japan",
                country="Japan",
                boundary_type="country",
                boundary_name="Japan",
                recommended_dataset="AW3D30",
            )
            # Only overwrite if not already a USA entry
            if region_id not in registry:
                registry[region_id] = entry
    except Exception:
        pass

    # 3) Switzerland regions
    try:
        from downloaders.switzerland_swisstopo import SWITZERLAND_REGIONS  # type: ignore

        for rid, info in SWITZERLAND_REGIONS.items():
            region_id = _normalize_id(rid)
            bounds: Bounds = tuple(info["bounds"])  # type: ignore
            name = info.get("name", region_id.replace("_", " ").title())
            entry = RegionEntry(
                id=region_id,
                name=name,
                bounds=bounds,
                category="switzerland",
                country="Switzerland",
                boundary_type="country",
                boundary_name="Switzerland",
                recommended_dataset="SRTMGL1",
            )
            if region_id not in registry:
                registry[region_id] = entry
    except Exception:
        pass

    # 4) High-res curated global regions (with recommended dataset)
    try:
        from download_high_resolution import HIGH_RES_REGIONS  # type: ignore

        for rid, info in HIGH_RES_REGIONS.items():
            region_id = _normalize_id(rid)
            bounds: Bounds = tuple(info["bounds"])  # type: ignore
            name = info.get("name", region_id.replace("_", " ").title())
            recommended = info.get("recommended_dataset")
            # No default country clipping for multi-country regions
            entry = RegionEntry(
                id=region_id,
                name=name,
                bounds=bounds,
                category="highres",
                country=None,
                boundary_type=None,
                boundary_name=None,
                recommended_dataset=recommended or "SRTMGL1",
            )
            if region_id not in registry:
                registry[region_id] = entry
    except Exception:
        pass

    # 5) Generic global regions registry
    try:
        from download_regions import REGIONS as GENERIC_REGIONS  # type: ignore

        # Country lookup set for clipping (simple heuristic: treat single-country names as countries)
        for rid, info in GENERIC_REGIONS.items():
            region_id = _normalize_id(rid)
            if region_id in registry:
                # Prefer more specific definitions already present
                continue
            bounds: Bounds = tuple(info["bounds"])  # type: ignore
            name = info.get("name", region_id.replace("_", " ").title())
            # Heuristic: If name looks like a country, clip to country
            boundary_name: Optional[str] = None
            boundary_type: Optional[str] = None
            country: Optional[str] = None
            # For common countries use the display name directly
            country_candidates = {
                "japan", "germany", "france", "italy", "spain", "united kingdom",
                "poland", "norway", "sweden", "switzerland", "austria", "greece",
                "netherlands", "canada", "mexico", "brazil", "argentina", "chile",
                "peru", "australia", "new zealand", "south africa", "egypt", "kenya",
                "israel", "saudi arabia", "nepal", "angola",
                # Added countries requested by users
                "estonia", "georgia", "kyrgyzstan", "turkey", "turkiye", "turkiye", "singapore"
            }
            name_lower = name.lower()
            if name_lower in country_candidates:
                country = name
                boundary_type = "country"
                boundary_name = name

            entry = RegionEntry(
                id=region_id,
                name=name,
                bounds=bounds,
                category="generic",
                country=country,
                boundary_type=boundary_type,
                boundary_name=boundary_name,
                recommended_dataset="SRTMGL1",
            )
            registry[region_id] = entry
    except Exception:
        pass

    return registry


_REGISTRY = _build_registry()


def get_region(region_id: str) -> Optional[RegionEntry]:
    """Return the registry entry for a region id, after normalization."""
    rid = _normalize_id(region_id)
    return _REGISTRY.get(rid)


def list_regions() -> List[RegionEntry]:
    """Return all regions sorted by category then name."""
    return sorted(_REGISTRY.values(), key=lambda r: (r.category, r.name.lower()))


def suggest_dataset_for_region(region: RegionEntry) -> str:
    """Return the preferred dataset id for a region (defaults to SRTMGL1)."""
    return region.recommended_dataset or "SRTMGL1"


def dataset_to_source_name(dataset_id: str) -> str:
    """Map dataset id to a short source name used in pipeline outputs."""
    mapping = {
        "SRTMGL1": "srtm_30m",
        "SRTMGL3": "srtm_90m",
        "NASADEM": "nasadem_30m",
        "AW3D30": "aw3d30",
        "COP30": "cop30",
        "COP90": "cop90",
    }
    return mapping.get(dataset_id.upper(), dataset_id.lower())


__all__ = [
    "RegionEntry",
    "get_region",
    "list_regions",
    "suggest_dataset_for_region",
    "dataset_to_source_name",
]


