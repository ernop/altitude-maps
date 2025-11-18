"""
Central configuration for the altitude-maps project.

This is the single source of truth for default values.
"""

# Default target resolution for downsampling
# This is the dimension used to calculate total pixel count (total pixels = DEFAULT_TARGET_PIXELS²)
# e.g., 1024 means up to 1,048,576 total pixels (1024×1024 for square regions)
# For non-square regions, dimensions are calculated to preserve aspect ratio while targeting this total
# Higher = more detail but larger files and slower rendering
DEFAULT_TARGET_PIXELS = 1024
