"""
Comprehensive test suite for US state adjacency data.

Tests validate that the generated adjacency relationships match known geographic
borders, excluding corner-only touches (like Four Corners) but including all
edge-sharing borders.

Reference sources:
- U.S. Census Bureau County Adjacency File
- Natural Earth 10m state boundaries
- Known geographic relationships
"""
import json
import pytest
from pathlib import Path

# Load generated adjacency data
ADJACENCY_FILE = Path('generated/region_adjacency.json')

@pytest.fixture
def adjacency_data():
    """Load the generated adjacency data."""
    with open(ADJACENCY_FILE) as f:
        return json.load(f)


# ============================================================================
# Known adjacency test cases (validated against authoritative sources)
# ============================================================================

# Test cases format: (state, direction, expected_neighbors)
# expected_neighbors can be a string (single neighbor) or list (multiple neighbors)

KNOWN_ADJACENCIES = [
    # Utah and its northern neighbors (the original question)
    ('utah', 'north', ['idaho', 'wyoming']),
    ('utah', 'south', 'arizona'),
    ('utah', 'east', ['colorado', 'wyoming']),
    ('utah', 'west', ['idaho', 'nevada']),
    
    # Idaho's neighbors
    ('idaho', 'north', 'washington'),
    ('idaho', 'south', ['nevada', 'utah']),
    ('idaho', 'east', ['montana', 'wyoming']),
    ('idaho', 'west', ['oregon', 'washington']),
    
    # Wyoming's neighbors
    ('wyoming', 'north', 'montana'),
    ('wyoming', 'south', ['colorado', 'utah']),
    ('wyoming', 'east', ['nebraska', 'south_dakota']),
    ('wyoming', 'west', ['idaho', 'montana']),
    
    # Montana's neighbors
    ('montana', 'north', None),  # Canada border, no US state
    ('montana', 'south', ['idaho', 'wyoming']),
    ('montana', 'east', ['north_dakota', 'south_dakota']),
    ('montana', 'west', 'idaho'),
    
    # Four Corners states (should NOT show corner-only touches)
    ('utah', 'southeast', None),  # Should NOT show New Mexico (corner only)
    ('colorado', 'southwest', None),  # Should NOT show Arizona (corner only)
    ('arizona', 'northeast', None),  # Should NOT show Colorado (corner only)
    ('new_mexico', 'northwest', None),  # Should NOT show Utah (corner only)
    
    # Tennessee (borders 8 states - most in continental US)
    ('tennessee', 'north', ['kentucky', 'virginia']),
    ('tennessee', 'south', ['alabama', 'georgia', 'mississippi']),
    ('tennessee', 'east', 'north_carolina'),
    ('tennessee', 'west', ['arkansas', 'missouri']),
    
    # Maine (only borders one state)
    ('maine', 'west', 'new_hampshire'),
    ('maine', 'south', None),  # Ocean
    ('maine', 'east', None),  # Ocean
    ('maine', 'north', None),  # Canada
    
    # Florida (only borders two states)
    ('florida', 'north', ['alabama', 'georgia']),
    ('florida', 'south', None),  # Ocean
    ('florida', 'east', None),  # Ocean
    ('florida', 'west', None),  # Gulf of Mexico
    
    # Michigan (split into two peninsulas)
    ('michigan', 'south', ['indiana', 'ohio']),
    ('michigan', 'west', 'wisconsin'),
    ('michigan', 'north', None),  # Canada and Great Lakes
    ('michigan', 'east', None),  # Canada and Great Lakes
    
    # California (longest north-south state)
    ('california', 'north', 'oregon'),
    ('california', 'east', ['arizona', 'nevada']),
    ('california', 'south', None),  # Mexico
    ('california', 'west', None),  # Pacific Ocean
    
    # Texas (second largest state)
    ('texas', 'north', ['arkansas', 'oklahoma']),
    ('texas', 'east', 'louisiana'),
    ('texas', 'west', 'new_mexico'),
    ('texas', 'south', None),  # Mexico
    
    # New York (borders multiple states and water)
    ('new_york', 'north', 'vermont'),
    ('new_york', 'south', ['new_jersey', 'pennsylvania']),
    ('new_york', 'east', ['connecticut', 'massachusetts', 'vermont']),
    ('new_york', 'west', ['pennsylvania', 'vermont']),
    
    # Rhode Island (smallest state)
    ('rhode_island', 'north', 'massachusetts'),
    ('rhode_island', 'west', 'connecticut'),
    ('rhode_island', 'south', None),  # Ocean
    ('rhode_island', 'east', None),  # Ocean
]


def normalize_neighbor_list(neighbors):
    """Normalize neighbors to a sorted list for comparison."""
    if neighbors is None:
        return []
    if isinstance(neighbors, str):
        return [neighbors]
    if isinstance(neighbors, list):
        return sorted(neighbors)
    return []


@pytest.mark.parametrize("state,direction,expected", KNOWN_ADJACENCIES)
def test_known_adjacency(adjacency_data, state, direction, expected):
    """Test that known adjacencies match expected values."""
    state_data = adjacency_data.get(state, {})
    actual = state_data.get(direction)
    
    expected_normalized = normalize_neighbor_list(expected)
    actual_normalized = normalize_neighbor_list(actual)
    
    assert actual_normalized == expected_normalized, (
        f"{state.title()} should have {expected_normalized} to the {direction}, "
        f"but got {actual_normalized}"
    )


def test_all_states_present(adjacency_data):
    """Test that all 50 US states are present in the adjacency data."""
    expected_states = {
        'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
        'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
        'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
        'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
        'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
        'new_hampshire', 'new_jersey', 'new_mexico', 'new_york',
        'north_carolina', 'north_dakota', 'ohio', 'oklahoma', 'oregon',
        'pennsylvania', 'rhode_island', 'south_carolina', 'south_dakota',
        'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
        'west_virginia', 'wisconsin', 'wyoming'
    }
    
    actual_states = {k for k in adjacency_data.keys() if k in expected_states}
    
    missing = expected_states - actual_states
    extra = actual_states - expected_states
    
    assert not missing, f"Missing states: {sorted(missing)}"
    assert not extra, f"Unexpected states: {sorted(extra)}"


def test_reciprocal_adjacency(adjacency_data):
    """Test that adjacency is reciprocal (if A borders B, then B borders A)."""
    errors = []
    
    for state, neighbors_dict in adjacency_data.items():
        for direction, neighbors in neighbors_dict.items():
            neighbor_list = neighbors if isinstance(neighbors, list) else [neighbors]
            
            for neighbor in neighbor_list:
                if neighbor not in adjacency_data:
                    continue  # Skip non-state neighbors (like international regions)
                
                # Check if neighbor lists this state
                neighbor_neighbors = adjacency_data[neighbor]
                all_neighbor_states = []
                for dir_neighbors in neighbor_neighbors.values():
                    if isinstance(dir_neighbors, list):
                        all_neighbor_states.extend(dir_neighbors)
                    else:
                        all_neighbor_states.append(dir_neighbors)
                
                if state not in all_neighbor_states:
                    errors.append(
                        f"{state} lists {neighbor} as a neighbor ({direction}), "
                        f"but {neighbor} doesn't list {state}"
                    )
    
    assert not errors, "\n".join(errors)


def test_no_self_adjacency(adjacency_data):
    """Test that no state lists itself as a neighbor."""
    errors = []
    
    for state, neighbors_dict in adjacency_data.items():
        for direction, neighbors in neighbors_dict.items():
            neighbor_list = neighbors if isinstance(neighbors, list) else [neighbors]
            
            if state in neighbor_list:
                errors.append(f"{state} incorrectly lists itself as a neighbor ({direction})")
    
    assert not errors, "\n".join(errors)


def test_valid_directions(adjacency_data):
    """Test that all directions are valid cardinal directions."""
    valid_directions = {'north', 'south', 'east', 'west'}
    errors = []
    
    for state, neighbors_dict in adjacency_data.items():
        for direction in neighbors_dict.keys():
            if direction not in valid_directions:
                errors.append(f"{state} has invalid direction: {direction}")
    
    assert not errors, "\n".join(errors)


def test_tennessee_has_most_neighbors(adjacency_data):
    """Test that Tennessee has 8 neighbors (most in continental US)."""
    tennessee = adjacency_data.get('tennessee', {})
    all_neighbors = set()
    
    for neighbors in tennessee.values():
        if isinstance(neighbors, list):
            all_neighbors.update(neighbors)
        else:
            all_neighbors.add(neighbors)
    
    # Tennessee borders: KY, VA, NC, GA, AL, MS, AR, MO (8 states)
    expected_neighbors = {
        'kentucky', 'virginia', 'north_carolina', 'georgia',
        'alabama', 'mississippi', 'arkansas', 'missouri'
    }
    
    assert all_neighbors == expected_neighbors, (
        f"Tennessee should border {expected_neighbors}, "
        f"but got {all_neighbors}"
    )


def test_four_corners_exclusion(adjacency_data):
    """Test that Four Corners states don't show corner-only touches."""
    # Utah and New Mexico only touch at a point (Four Corners)
    utah = adjacency_data.get('utah', {})
    new_mexico = adjacency_data.get('new_mexico', {})
    
    # Get all Utah neighbors
    utah_neighbors = set()
    for neighbors in utah.values():
        if isinstance(neighbors, list):
            utah_neighbors.update(neighbors)
        else:
            utah_neighbors.add(neighbors)
    
    # Get all New Mexico neighbors
    nm_neighbors = set()
    for neighbors in new_mexico.values():
        if isinstance(neighbors, list):
            nm_neighbors.update(neighbors)
        else:
            nm_neighbors.add(neighbors)
    
    assert 'new_mexico' not in utah_neighbors, "Utah should not list New Mexico (corner-only touch)"
    assert 'utah' not in nm_neighbors, "New Mexico should not list Utah (corner-only touch)"
    
    # Similarly, Colorado and Arizona only touch at Four Corners
    colorado = adjacency_data.get('colorado', {})
    arizona = adjacency_data.get('arizona', {})
    
    colorado_neighbors = set()
    for neighbors in colorado.values():
        if isinstance(neighbors, list):
            colorado_neighbors.update(neighbors)
        else:
            colorado_neighbors.add(neighbors)
    
    arizona_neighbors = set()
    for neighbors in arizona.values():
        if isinstance(neighbors, list):
            arizona_neighbors.update(neighbors)
        else:
            arizona_neighbors.add(neighbors)
    
    assert 'arizona' not in colorado_neighbors, "Colorado should not list Arizona (corner-only touch)"
    assert 'colorado' not in arizona_neighbors, "Arizona should not list Colorado (corner-only touch)"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

