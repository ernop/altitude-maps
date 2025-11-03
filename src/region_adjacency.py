"""
Region adjacency data - which regions border which.

This data is used by the viewer to show clickable neighbor labels at region edges.
Format: {region_id: {direction: neighbor_region_id}}
Directions: 'north', 'south', 'east', 'west'
"""

from typing import Dict, Any

# US State adjacencies (geographical neighbors)
US_STATE_ADJACENCY: Dict[str, Dict[str, str]] = {
    'alabama': {
        'north': 'tennessee',
        'south': 'florida',
        'east': 'georgia',
        'west': 'mississippi',
    },
    'arizona': {
        'north': 'utah',
        'south': 'mexico',
        'east': 'new_mexico',
        'west': 'california',
    },
    'arkansas': {
        'north': 'missouri',
        'south': 'louisiana',
        'east': 'tennessee',
        'west': 'texas',
    },
    'california': {
        'north': 'oregon',
        'east': ['nevada', 'arizona'],  # Both border California's east
        'south': 'mexico',
    },
    'colorado': {
        'north': 'wyoming',
        'south': 'new_mexico',
        'east': 'kansas',
        'west': 'utah',
    },
    'connecticut': {
        'north': 'massachusetts',
        'east': 'rhode_island',
        'west': 'new_york',
    },
    'delaware': {
        'north': 'pennsylvania',
        'south': 'maryland',
        'west': 'maryland',
    },
    'florida': {
        'north': 'georgia',
        'west': 'alabama',
    },
    'georgia': {
        'north': 'tennessee',
        'south': 'florida',
        'east': 'south_carolina',
        'west': 'alabama',
    },
    'idaho': {
        'north': 'montana',
        'south': 'nevada',
        'east': 'wyoming',
        'west': 'washington',
    },
    'illinois': {
        'north': 'wisconsin',
        'east': 'indiana',
        'west': 'iowa',
    },
    'indiana': {
        'north': 'michigan',
        'east': 'ohio',
        'west': 'illinois',
    },
    'iowa': {
        'north': 'minnesota',
        'south': 'missouri',
        'east': 'illinois',
        'west': 'nebraska',
    },
    'kansas': {
        'north': 'nebraska',
        'south': 'oklahoma',
        'east': 'missouri',
        'west': 'colorado',
    },
    'kentucky': {
        'north': 'ohio',
        'south': 'tennessee',
        'east': 'west_virginia',
        'west': 'missouri',
    },
    'louisiana': {
        'north': 'arkansas',
        'east': 'mississippi',
        'west': 'texas',
    },
    'maine': {
        'south': 'new_hampshire',
        'west': 'new_hampshire',
    },
    'maryland': {
        'north': 'pennsylvania',
        'south': 'virginia',
        'east': 'delaware',
        'west': 'west_virginia',
    },
    'massachusetts': {
        'north': 'vermont',
        'south': 'connecticut',
        'east': 'rhode_island',
        'west': 'new_york',
    },
    'michigan': {
        'south': 'indiana',
        'west': 'wisconsin',
    },
    'minnesota': {
        'south': 'iowa',
        'east': 'wisconsin',
        'west': 'north_dakota',
    },
    'mississippi': {
        'north': 'tennessee',
        'south': 'louisiana',
        'east': 'alabama',
        'west': 'arkansas',
    },
    'missouri': {
        'north': 'iowa',
        'south': 'arkansas',
        'east': 'kentucky',
        'west': 'kansas',
    },
    'montana': {
        'south': 'wyoming',
        'east': 'north_dakota',
        'west': 'idaho',
    },
    'nebraska': {
        'north': 'south_dakota',
        'south': 'kansas',
        'east': 'iowa',
        'west': 'wyoming',
    },
    'nevada': {
        'north': 'oregon',
        'south': 'arizona',
        'east': 'utah',
        'west': 'california',
    },
    'new_hampshire': {
        'north': 'maine',
        'south': 'massachusetts',
        'east': 'maine',
        'west': 'vermont',
    },
    'new_jersey': {
        'north': 'new_york',
        'south': 'delaware',
        'west': 'pennsylvania',
    },
    'new_mexico': {
        'north': 'colorado',
        'south': 'mexico',
        'east': 'texas',
        'west': 'arizona',
    },
    'new_york': {
        'north': 'vermont',
        'south': 'new_jersey',
        'east': 'massachusetts',
        'west': 'pennsylvania',
    },
    'north_carolina': {
        'north': 'virginia',
        'south': 'south_carolina',
        'east': 'south_carolina',
        'west': 'tennessee',
    },
    'north_dakota': {
        'south': 'south_dakota',
        'east': 'minnesota',
        'west': 'montana',
    },
    'ohio': {
        'north': 'michigan',
        'south': 'kentucky',
        'east': 'pennsylvania',
        'west': 'indiana',
    },
    'oklahoma': {
        'north': 'kansas',
        'south': 'texas',
        'east': 'arkansas',
        'west': 'new_mexico',
    },
    'oregon': {
        'north': 'washington',
        'south': 'california',
        'east': 'idaho',
    },
    'pennsylvania': {
        'north': 'new_york',
        'south': 'maryland',
        'east': 'new_york',
        'west': 'ohio',
    },
    'rhode_island': {
        'north': 'massachusetts',
        'west': 'connecticut',
    },
    'south_carolina': {
        'north': 'north_carolina',
        'west': 'georgia',
    },
    'south_dakota': {
        'north': 'north_dakota',
        'south': 'nebraska',
        'east': 'minnesota',
        'west': 'wyoming',
    },
    'tennessee': {
        'north': 'kentucky',
        'south': 'alabama',
        'east': 'north_carolina',
        'west': 'arkansas',
    },
    'texas': {
        'north': 'oklahoma',
        'south': 'mexico',
        'east': 'louisiana',
        'west': 'new_mexico',
    },
    'utah': {
        'north': 'idaho',
        'south': 'arizona',
        'east': 'colorado',
        'west': 'nevada',
    },
    'vermont': {
        'south': 'massachusetts',
        'east': 'new_hampshire',
        'west': 'new_york',
    },
    'virginia': {
        'north': 'maryland',
        'south': 'north_carolina',
        'west': 'west_virginia',
    },
    'washington': {
        'south': 'oregon',
        'east': 'idaho',
    },
    'west_virginia': {
        'north': 'pennsylvania',
        'south': 'virginia',
        'east': 'virginia',
        'west': 'ohio',
    },
    'wisconsin': {
        'north': 'michigan',
        'south': 'illinois',
        'east': 'michigan',
        'west': 'minnesota',
    },
    'wyoming': {
        'north': 'montana',
        'south': 'colorado',
        'east': 'nebraska',
        'west': 'idaho',
    },
}

# International adjacencies (can expand as needed)
INTERNATIONAL_ADJACENCY: Dict[str, Dict[str, str]] = {
    'iceland': {},
    'ireland': {},
    'japan': {},
    'new_zealand': {},
    'united_kingdom': {},
    # Add more as needed
}

# Combined adjacency data
REGION_ADJACENCY = {**US_STATE_ADJACENCY, **INTERNATIONAL_ADJACENCY}


def get_adjacency_data() -> Dict[str, Any]:
    """
    Export adjacency data as JSON-compatible dict for the viewer.
    Returns: {region_id: {direction: neighbor_region_id}}
    """
    return REGION_ADJACENCY


if __name__ == '__main__':
    import json
    print(json.dumps(get_adjacency_data(), indent=2))

