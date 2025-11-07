"""
US State Adjacency Data

This module defines which US states border each other and in which directions.
Used by the viewer to show neighboring states near compass rose directions.

Data sources:
- US Census Bureau state adjacency files
- Manual verification of directional relationships

Directional conventions:
- N, S, E, W: Primary cardinal directions
- NE, NW, SE, SW: Diagonal directions
- Directions are approximate based on state centroid relationships
"""

from typing import Dict, List, Set
from dataclasses import dataclass


@dataclass
class StateNeighbor:
    """A neighboring state with directional information."""
    state_id: str  # e.g., "nevada"
    state_name: str  # e.g., "Nevada"
    direction: str  # N, S, E, W, NE, NW, SE, SW


# Complete US state adjacency data with directional relationships
# Format: state_id -> list of StateNeighbor objects
US_STATE_ADJACENCY: Dict[str, List[StateNeighbor]] = {
    "arizona": [
        StateNeighbor("california", "California", "W"),
        StateNeighbor("nevada", "Nevada", "NW"),
        StateNeighbor("utah", "Utah", "N"),
        StateNeighbor("colorado", "Colorado", "NE"),
        StateNeighbor("new_mexico", "New Mexico", "E"),
    ],
    
    "california": [
        StateNeighbor("oregon", "Oregon", "N"),
        StateNeighbor("nevada", "Nevada", "E"),
        StateNeighbor("arizona", "Arizona", "E"),
    ],
    
    "colorado": [
        StateNeighbor("wyoming", "Wyoming", "N"),
        StateNeighbor("nebraska", "Nebraska", "NE"),
        StateNeighbor("kansas", "Kansas", "E"),
        StateNeighbor("oklahoma", "Oklahoma", "SE"),
        StateNeighbor("new_mexico", "New Mexico", "S"),
        StateNeighbor("utah", "Utah", "W"),
    ],
    
    "indiana": [
        StateNeighbor("michigan", "Michigan", "N"),
        StateNeighbor("ohio", "Ohio", "E"),
        StateNeighbor("kentucky", "Kentucky", "S"),
        StateNeighbor("illinois", "Illinois", "W"),
    ],
    
    "iowa": [
        StateNeighbor("minnesota", "Minnesota", "N"),
        StateNeighbor("wisconsin", "Wisconsin", "NE"),
        StateNeighbor("illinois", "Illinois", "E"),
        StateNeighbor("missouri", "Missouri", "S"),
        StateNeighbor("nebraska", "Nebraska", "W"),
        StateNeighbor("south_dakota", "South Dakota", "NW"),
    ],
    
    "kansas": [
        StateNeighbor("nebraska", "Nebraska", "N"),
        StateNeighbor("missouri", "Missouri", "E"),
        StateNeighbor("oklahoma", "Oklahoma", "S"),
        StateNeighbor("colorado", "Colorado", "W"),
    ],
    
    "kentucky": [
        StateNeighbor("illinois", "Illinois", "NW"),
        StateNeighbor("indiana", "Indiana", "N"),
        StateNeighbor("ohio", "Ohio", "NE"),
        StateNeighbor("west_virginia", "West Virginia", "E"),
        StateNeighbor("virginia", "Virginia", "E"),
        StateNeighbor("tennessee", "Tennessee", "S"),
        StateNeighbor("missouri", "Missouri", "W"),
    ],
    
    "maine": [
        StateNeighbor("new_hampshire", "New Hampshire", "SW"),
    ],
    
    "michigan": [
        StateNeighbor("wisconsin", "Wisconsin", "W"),
        StateNeighbor("indiana", "Indiana", "S"),
        StateNeighbor("ohio", "Ohio", "S"),
    ],
    
    "minnesota": [
        StateNeighbor("north_dakota", "North Dakota", "NW"),
        StateNeighbor("south_dakota", "South Dakota", "W"),
        StateNeighbor("iowa", "Iowa", "S"),
        StateNeighbor("wisconsin", "Wisconsin", "E"),
    ],
    
    "nebraska": [
        StateNeighbor("south_dakota", "South Dakota", "N"),
        StateNeighbor("iowa", "Iowa", "E"),
        StateNeighbor("missouri", "Missouri", "SE"),
        StateNeighbor("kansas", "Kansas", "S"),
        StateNeighbor("colorado", "Colorado", "SW"),
        StateNeighbor("wyoming", "Wyoming", "W"),
    ],
    
    "nevada": [
        StateNeighbor("oregon", "Oregon", "N"),
        StateNeighbor("idaho", "Idaho", "NE"),
        StateNeighbor("utah", "Utah", "E"),
        StateNeighbor("arizona", "Arizona", "SE"),
        StateNeighbor("california", "California", "W"),
    ],
    
    "new_hampshire": [
        StateNeighbor("maine", "Maine", "NE"),
        StateNeighbor("massachusetts", "Massachusetts", "S"),
        StateNeighbor("vermont", "Vermont", "W"),
    ],
    
    "new_jersey": [
        StateNeighbor("new_york", "New York", "N"),
        StateNeighbor("delaware", "Delaware", "SW"),
        StateNeighbor("pennsylvania", "Pennsylvania", "W"),
    ],
    
    "new_mexico": [
        StateNeighbor("colorado", "Colorado", "N"),
        StateNeighbor("oklahoma", "Oklahoma", "NE"),
        StateNeighbor("texas", "Texas", "E"),
        StateNeighbor("arizona", "Arizona", "W"),
    ],
    
    "new_york": [
        StateNeighbor("vermont", "Vermont", "NE"),
        StateNeighbor("massachusetts", "Massachusetts", "E"),
        StateNeighbor("connecticut", "Connecticut", "SE"),
        StateNeighbor("new_jersey", "New Jersey", "S"),
        StateNeighbor("pennsylvania", "Pennsylvania", "S"),
    ],
    
    "north_carolina": [
        StateNeighbor("virginia", "Virginia", "N"),
        StateNeighbor("south_carolina", "South Carolina", "S"),
        StateNeighbor("georgia", "Georgia", "SW"),
        StateNeighbor("tennessee", "Tennessee", "W"),
    ],
    
    "north_dakota": [
        StateNeighbor("minnesota", "Minnesota", "SE"),
        StateNeighbor("south_dakota", "South Dakota", "S"),
        StateNeighbor("montana", "Montana", "W"),
    ],
    
    "ohio": [
        StateNeighbor("michigan", "Michigan", "N"),
        StateNeighbor("pennsylvania", "Pennsylvania", "E"),
        StateNeighbor("west_virginia", "West Virginia", "SE"),
        StateNeighbor("kentucky", "Kentucky", "S"),
        StateNeighbor("indiana", "Indiana", "W"),
    ],
    
    "oregon": [
        StateNeighbor("washington", "Washington", "N"),
        StateNeighbor("idaho", "Idaho", "E"),
        StateNeighbor("nevada", "Nevada", "SE"),
        StateNeighbor("california", "California", "S"),
    ],
    
    "pennsylvania": [
        StateNeighbor("new_york", "New York", "N"),
        StateNeighbor("new_jersey", "New Jersey", "E"),
        StateNeighbor("delaware", "Delaware", "SE"),
        StateNeighbor("maryland", "Maryland", "S"),
        StateNeighbor("west_virginia", "West Virginia", "SW"),
        StateNeighbor("ohio", "Ohio", "W"),
    ],
    
    "south_dakota": [
        StateNeighbor("north_dakota", "North Dakota", "N"),
        StateNeighbor("minnesota", "Minnesota", "E"),
        StateNeighbor("iowa", "Iowa", "SE"),
        StateNeighbor("nebraska", "Nebraska", "S"),
        StateNeighbor("wyoming", "Wyoming", "W"),
        StateNeighbor("montana", "Montana", "NW"),
    ],
    
    "tennessee": [
        StateNeighbor("kentucky", "Kentucky", "N"),
        StateNeighbor("virginia", "Virginia", "NE"),
        StateNeighbor("north_carolina", "North Carolina", "E"),
        StateNeighbor("georgia", "Georgia", "SE"),
        StateNeighbor("alabama", "Alabama", "S"),
        StateNeighbor("mississippi", "Mississippi", "SW"),
        StateNeighbor("arkansas", "Arkansas", "W"),
        StateNeighbor("missouri", "Missouri", "NW"),
    ],
    
    "utah": [
        StateNeighbor("idaho", "Idaho", "N"),
        StateNeighbor("wyoming", "Wyoming", "NE"),
        StateNeighbor("colorado", "Colorado", "E"),
        StateNeighbor("new_mexico", "New Mexico", "SE"),
        StateNeighbor("arizona", "Arizona", "S"),
        StateNeighbor("nevada", "Nevada", "W"),
    ],
    
    "vermont": [
        StateNeighbor("new_hampshire", "New Hampshire", "E"),
        StateNeighbor("massachusetts", "Massachusetts", "S"),
        StateNeighbor("new_york", "New York", "W"),
    ],
    
    "washington": [
        StateNeighbor("idaho", "Idaho", "E"),
        StateNeighbor("oregon", "Oregon", "S"),
    ],
    
    "wisconsin": [
        StateNeighbor("michigan", "Michigan", "E"),
        StateNeighbor("illinois", "Illinois", "S"),
        StateNeighbor("iowa", "Iowa", "SW"),
        StateNeighbor("minnesota", "Minnesota", "W"),
    ],
    
    "wyoming": [
        StateNeighbor("montana", "Montana", "N"),
        StateNeighbor("south_dakota", "South Dakota", "E"),
        StateNeighbor("nebraska", "Nebraska", "SE"),
        StateNeighbor("colorado", "Colorado", "S"),
        StateNeighbor("utah", "Utah", "SW"),
        StateNeighbor("idaho", "Idaho", "W"),
    ],
}


def get_neighbors(state_id: str) -> List[StateNeighbor]:
    """
    Get all neighboring states for a given state.
    
    Args:
        state_id: State identifier (e.g., "california")
        
    Returns:
        List of StateNeighbor objects, or empty list if state not found
    """
    state_id = state_id.lower().replace(" ", "_").replace("-", "_")
    return US_STATE_ADJACENCY.get(state_id, [])


def get_neighbors_by_direction(state_id: str) -> Dict[str, List[StateNeighbor]]:
    """
    Get neighboring states grouped by direction.
    
    Args:
        state_id: State identifier (e.g., "california")
        
    Returns:
        Dict mapping direction (N, S, E, W, NE, NW, SE, SW) to list of neighbors
    """
    neighbors = get_neighbors(state_id)
    by_direction: Dict[str, List[StateNeighbor]] = {}
    
    for neighbor in neighbors:
        direction = neighbor.direction
        if direction not in by_direction:
            by_direction[direction] = []
        by_direction[direction].append(neighbor)
    
    return by_direction


def get_all_neighbors_set(state_id: str) -> Set[str]:
    """
    Get set of all neighboring state IDs (useful for quick membership checks).
    
    Args:
        state_id: State identifier
        
    Returns:
        Set of neighboring state IDs
    """
    neighbors = get_neighbors(state_id)
    return {n.state_id for n in neighbors}


def has_neighbor(state_id: str, neighbor_id: str) -> bool:
    """
    Check if two states are neighbors.
    
    Args:
        state_id: First state identifier
        neighbor_id: Second state identifier
        
    Returns:
        True if states share a border
    """
    neighbor_id = neighbor_id.lower().replace(" ", "_").replace("-", "_")
    return neighbor_id in get_all_neighbors_set(state_id)


def get_direction_to_neighbor(state_id: str, neighbor_id: str) -> str:
    """
    Get the direction from one state to its neighbor.
    
    Args:
        state_id: Source state identifier
        neighbor_id: Target state identifier
        
    Returns:
        Direction string (N, S, E, W, NE, NW, SE, SW) or empty string if not neighbors
    """
    neighbor_id = neighbor_id.lower().replace(" ", "_").replace("-", "_")
    neighbors = get_neighbors(state_id)
    
    for neighbor in neighbors:
        if neighbor.state_id == neighbor_id:
            return neighbor.direction
    
    return ""



