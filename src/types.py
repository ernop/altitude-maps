"""
Type definitions for altitude-maps project.

This module contains enums and type aliases used throughout the codebase.
"""

from enum import Enum


class RegionType(str, Enum):
    """
    Region type classification.
    
    This enum defines the three types of regions:
    - USA_STATE: US states (e.g., California, Texas)
    - COUNTRY: Countries (e.g., Iceland, Japan, Switzerland)
    - AREA: Custom areas (islands, mountain ranges, peninsulas, etc.)
    
    Inherits from str so it's JSON-serializable and works with string comparisons.
    """
    USA_STATE = "usa_state"
    COUNTRY = "country"
    AREA = "area"
    
    def __str__(self) -> str:
        """Return the string value for easy printing."""
        return self.value

