"""
Central configuration for the altitude-maps project.

This is the single source of truth for default values.
"""

# Default target total pixel count for downsampling
# This is the total number of pixels in the final output (width × height)
# For non-square regions, dimensions are calculated to preserve aspect ratio while targeting this total
# Higher = more detail but larger files and slower rendering
DEFAULT_TARGET_TOTAL_PIXELS = 3 * 1024**2  # 3,145,728 pixels (e.g. up to ~2048x1536)
