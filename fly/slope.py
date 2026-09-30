"""
Slope-steepness overlay tiles in walking-grade bands (see PRODUCT.md, "Slope bands").
"""

import io

import numpy as np
from PIL import Image

from terrain import tile_row_ground_resolution_m

# (upper grade percent, RGBA). A pixel takes the color of the first band whose upper bound exceeds its grade.
GRADE_BANDS: tuple[tuple[float, tuple[int, int, int, int]], ...] = (
 (5.0, (0, 0, 0, 0)),
 (10.0, (46, 204, 64, 150)),
 (15.0, (170, 220, 30, 170)),
 (20.0, (255, 220, 0, 185)),
 (30.0, (255, 133, 27, 200)),
 (45.0, (230, 20, 20, 210)),
 (70.0, (220, 0, 200, 215)),
 (100.0, (120, 30, 200, 225)),
 (float('inf'), (20, 0, 40, 235)),
)
BAND_LIMITS = np.array([limit for limit, _ in GRADE_BANDS[:-1]])
BAND_COLORS = np.array([color for _, color in GRADE_BANDS], dtype=np.uint8)


def grade_percent(elevation_m: np.ndarray, z: int, y: int) -> np.ndarray:
 size = elevation_m.shape[0]
 row_resolution = tile_row_ground_resolution_m(z, y, size)[:, None]
 d_row, d_col = np.gradient(elevation_m)
 return 100.0 * np.hypot(d_row / row_resolution, d_col / row_resolution)


def render_slope_png(elevation_m: np.ndarray, z: int, y: int) -> bytes:
 band_index = np.searchsorted(BAND_LIMITS, grade_percent(elevation_m, z, y), side='right')
 buffer = io.BytesIO()
 Image.fromarray(BAND_COLORS[band_index], 'RGBA').save(buffer, format='PNG', compress_level=3)
 return buffer.getvalue()
