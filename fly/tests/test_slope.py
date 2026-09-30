import io

import numpy as np
from PIL import Image

from slope import GRADE_BANDS, grade_percent, render_slope_png
from terrain import TILE_SIZE, lonlat_to_tile, tile_row_ground_resolution_m


def test_flat_tile_is_transparent():
 png = render_slope_png(np.zeros((TILE_SIZE, TILE_SIZE)), 15, 12648)
 with Image.open(io.BytesIO(png)) as image:
  assert np.asarray(image)[..., 3].max() == 0


def test_plane_grade_matches_construction():
 z, (x, y) = 15, lonlat_to_tile(-122.6, 37.9, 15)
 resolution = tile_row_ground_resolution_m(z, y)[:, None]
 columns = np.arange(TILE_SIZE)[None, :] * resolution
 elevation = 0.25 * columns
 grade = grade_percent(elevation, z, y)
 assert np.allclose(grade[1:-1, 1:-1], 25.0, rtol=0.01)
 with Image.open(io.BytesIO(render_slope_png(elevation, z, y))) as image:
  expected = GRADE_BANDS[4][1]
  assert tuple(np.asarray(image)[200, 200]) == expected
