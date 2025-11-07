"""
Core download configuration - single source of truth.

This file defines download strategies for different resolutions.
DO NOT duplicate these values elsewhere.
"""

# Download chunk sizes by resolution (degrees per API request)
# Larger chunks reduce API calls but increase memory usage during splitting
CHUNK_SIZE_BY_RESOLUTION = {
    10: 1,    # 10m data is ~300MB/tile - keep 1x1 degree chunks
    30: 1,    # 30m data is ~50MB/tile - keep 1x1 degree chunks
    90: 2,    # 90m data is ~12MB/tile - fetch 2x2 degree chunks (4 tiles per request)
    250: 4,   # 250m data is ~3MB/tile - fetch 4x4 degree chunks
    500: 8,   # 500m data is ~1MB/tile - fetch 8x8 degree chunks
    1000: 10, # 1km data is ~500KB/tile - fetch 10x10 degree chunks
}

# OpenTopography API limits
OPENTOPOGRAPHY_MAX_DEGREES = 4  # Maximum degrees per request dimension

# Expected file sizes (for progress estimation)
TYPICAL_TILE_SIZE_MB = {
    10: 300,
    30: 50,
    90: 12,
    250: 3,
    500: 1,
    1000: 0.5,
}


def get_chunk_size(resolution_m: int) -> int:
    """Get download chunk size for a resolution (in degrees)."""
    return CHUNK_SIZE_BY_RESOLUTION.get(resolution_m, 1)


def get_typical_tile_size(resolution_m: int) -> float:
    """Get expected file size for a 1-degree tile (in MB)."""
    return TYPICAL_TILE_SIZE_MB.get(resolution_m, 50)

