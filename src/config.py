"""
Central configuration for the altitude-maps project.

This is the single source of truth for default values.
"""

# Default target total pixel count for downsampling
# This is the total number of pixels in the final output (width × height)
# e.g., 1,048,576 means up to 1024×1024 pixels for square regions
# For non-square regions, dimensions are calculated to preserve aspect ratio while targeting this total
# Higher = more detail but larger files and slower rendering
DEFAULT_TARGET_TOTAL_PIXELS = 3* 1024**2  # 1,048,576 pixels
