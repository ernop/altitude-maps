"""
Central configuration for the altitude-maps project.

This is the single source of truth for default values.
"""

# Default target resolution for downsampling
# This is the maximum dimension (width or height) in pixels
# Higher = more detail but larger files and slower rendering
DEFAULT_TARGET_PIXELS = 2048

# Data format versions
EXPORT_FORMAT_VERSION = "export_v2"
CLIPPED_FORMAT_VERSION = "clipped_v1"
PROCESSED_FORMAT_VERSION = "processed_v2"

# Validation thresholds
MIN_DATA_COVERAGE = 0.2  # Minimum 20% valid pixels
CROP_TOLERANCE_PIXELS = 0  # Maximum allowed all-empty edge rows/cols

# File paths
RAW_DATA_DIRS = [
    "data/raw/srtm_30m",
    "data/regions",
    "data/raw/usa_3dep",
]

CLIPPED_DATA_DIR = "data/clipped"
PROCESSED_DATA_DIR = "data/processed"
GENERATED_DATA_DIR = "generated/regions"
CACHE_DIR = "data/.cache"

