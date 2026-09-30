import io

import numpy as np
import pytest
from PIL import Image

import terrain
from terrain import (TILE_SIZE, TerrainSettings, TerrainSource, UpstreamUnavailable, decode_terrarium, decode_tile_bytes,
 encode_terrarium, intersects_usgs_coverage, lonlat_to_tile, sample_bilinear, tile_bounds_lonlat, upsample_quadrant)

MT_TAM = (-122.5965, 37.9235)


def settings(**overrides) -> TerrainSettings:
 values = dict(mapterhorn_url='https://example.test/{z}/{x}/{y}.webp', max_zoom=16, usgs_3dep_fill=True, usgs_3dep_max_zoom=16, user_agent='test')
 values.update(overrides)
 return TerrainSettings(**values)


def terrarium_png(elevation: np.ndarray) -> bytes:
 buffer = io.BytesIO()
 Image.fromarray(encode_terrarium(elevation), 'RGB').save(buffer, format='PNG')
 return buffer.getvalue()


def float_tiff(elevation: np.ndarray) -> bytes:
 buffer = io.BytesIO()
 Image.fromarray(elevation.astype(np.float32), 'F').save(buffer, format='TIFF')
 return buffer.getvalue()


#-------CODEC AND MATH-------
def test_terrarium_roundtrip_precision():
 elevation = np.linspace(-450.0, 8848.0, TILE_SIZE * 4).reshape(4, TILE_SIZE)
 decoded = decode_terrarium(encode_terrarium(elevation))
 assert np.abs(decoded - elevation).max() <= 1 / 256 + 1e-9


def test_known_tile_for_mt_tamalpais():
 assert lonlat_to_tile(*MT_TAM, 16) == (10449, 25296)
 west, south, east, north = tile_bounds_lonlat(16, 10449, 25296)
 assert west <= MT_TAM[0] <= east and south <= MT_TAM[1] <= north


def test_usgs_coverage_boxes():
 assert intersects_usgs_coverage(16, *lonlat_to_tile(*MT_TAM, 16))
 assert not intersects_usgs_coverage(12, *lonlat_to_tile(7.66, 45.98, 12))


def test_upsample_is_exact_for_linear_surfaces_away_from_edges():
 columns = np.arange(TILE_SIZE, dtype=np.float64)
 parent = np.tile(columns * 2.0 + 100.0, (TILE_SIZE, 1))
 child = upsample_quadrant(parent, 1, 1, 0)
 # Child pixel i center sits at parent coordinate 256 + (i + 0.5) / 2 - 0.5.
 expected = (256 + (columns + 0.5) / 2 - 0.5) * 2.0 + 100.0
 assert np.allclose(child[10, 5:-5], expected[5:-5])


def test_sample_bilinear_uses_pixel_edges():
 rows = np.arange(TILE_SIZE, dtype=np.float64)
 elevation = np.tile(rows[:, None], (1, TILE_SIZE))
 values = sample_bilinear(elevation, np.array([100.0, 100.0]), np.array([10.5, 20.0]))
 assert np.allclose(values, [10.0, 19.5])


#-------SOURCE POLICY-------
class FakeUpstream:
 def __init__(self, mapterhorn_max_zoom: int, usgs_elevation: np.ndarray | None = None, fail_usgs: bool = False):
  self.mapterhorn_max_zoom = mapterhorn_max_zoom
  self.usgs_elevation = usgs_elevation
  self.fail_usgs = fail_usgs
  self.calls: list[str] = []

 def __call__(self, url: str, user_agent: str) -> bytes | None:
  self.calls.append(url)
  if url.startswith('https://example.test/'):
   z = int(url.split('/')[3])
   return terrarium_png(np.full((TILE_SIZE, TILE_SIZE), 100.0 + z)) if z <= self.mapterhorn_max_zoom else None
  if self.fail_usgs:
   raise UpstreamUnavailable('503')
  # Only the first 3DEP request has data, so ancestor fills come from Mapterhorn.
  elevation, self.usgs_elevation = self.usgs_elevation, None
  return None if elevation is None else float_tiff(elevation)


def test_mapterhorn_tile_is_cached(tmp_path, monkeypatch):
 upstream = FakeUpstream(mapterhorn_max_zoom=16)
 monkeypatch.setattr(terrain, 'http_get', upstream)
 source = TerrainSource(settings(), tmp_path)
 x, y = lonlat_to_tile(*MT_TAM, 16)
 assert source.get_tile(16, x, y).source == 'mapterhorn'
 assert source.get_tile(16, x, y).source == 'mapterhorn'
 assert len(upstream.calls) == 1


def test_missing_zoom_outside_us_upsamples_ancestor_and_negative_caches(tmp_path, monkeypatch):
 upstream = FakeUpstream(mapterhorn_max_zoom=12)
 monkeypatch.setattr(terrain, 'http_get', upstream)
 source = TerrainSource(settings(), tmp_path)
 x, y = lonlat_to_tile(-73.1, -49.27, 15)
 tile = source.get_tile(15, x, y)
 assert tile.source == 'derived'
 assert np.allclose(decode_tile_bytes(tile.data), 112.0, atol=0.01)
 calls = len(upstream.calls)
 source.get_tile(15, x, y)
 source._real_tile(14, x >> 1, y >> 1)
 assert len(upstream.calls) == calls


def test_us_gap_filled_from_usgs_with_nodata_holes_from_ancestor(tmp_path, monkeypatch):
 usgs = np.full((TILE_SIZE, TILE_SIZE), -80.0)
 usgs[:10, :10] = terrain.USGS_NODATA
 upstream = FakeUpstream(mapterhorn_max_zoom=13, usgs_elevation=usgs)
 monkeypatch.setattr(terrain, 'http_get', upstream)
 source = TerrainSource(settings(), tmp_path)
 x, y = lonlat_to_tile(-116.87, 36.23, 16)
 tile = source.get_tile(16, x, y)
 assert tile.source == 'usgs_3dep'
 elevation = decode_tile_bytes(tile.data)
 assert np.allclose(elevation[100:, 100:], -80.0, atol=0.01)
 assert elevation[0, 0] > 100.0


def test_usgs_disabled_falls_back_to_ancestor(tmp_path, monkeypatch):
 upstream = FakeUpstream(mapterhorn_max_zoom=13, usgs_elevation=np.zeros((TILE_SIZE, TILE_SIZE)))
 monkeypatch.setattr(terrain, 'http_get', upstream)
 source = TerrainSource(settings(usgs_3dep_fill=False), tmp_path)
 x, y = lonlat_to_tile(-116.87, 36.23, 15)
 assert source.get_tile(15, x, y).source == 'derived'
 assert not any('nationalmap' in call for call in upstream.calls)


def test_transient_failure_is_not_cached(tmp_path, monkeypatch):
 upstream = FakeUpstream(mapterhorn_max_zoom=13, fail_usgs=True)
 monkeypatch.setattr(terrain, 'http_get', upstream)
 source = TerrainSource(settings(), tmp_path)
 x, y = lonlat_to_tile(-116.87, 36.23, 16)
 with pytest.raises(UpstreamUnavailable):
  source.get_tile(16, x, y)
 assert not list((tmp_path / 'terrain' / '16').rglob('*.png'))


def test_out_of_range_tile_rejected(tmp_path):
 source = TerrainSource(settings(), tmp_path)
 with pytest.raises(ValueError):
  source.get_tile(17, 0, 0)


def test_sample_lonlat_groups_by_tile(tmp_path, monkeypatch):
 upstream = FakeUpstream(mapterhorn_max_zoom=16)
 monkeypatch.setattr(terrain, 'http_get', upstream)
 source = TerrainSource(settings(), tmp_path)
 west, south, east, north = tile_bounds_lonlat(15, *lonlat_to_tile(*MT_TAM, 15))
 lons = np.array([west + (east - west) * 0.3, west + (east - west) * 0.7])
 lats = np.array([south + (north - south) * 0.5] * 2)
 values = source.sample_lonlat(lons, lats, 15)
 assert np.allclose(values, 115.0, atol=0.01)
 assert len(upstream.calls) == 1
