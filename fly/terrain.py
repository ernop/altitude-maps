"""
Terrain tiles: Web Mercator tile math, terrarium codec, and the tiered source policy
(Mapterhorn, then USGS 3DEP for US gaps, then ancestor upsampling) behind a disk cache.
"""

import io
import math
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

#-------CONSTANTS-------
TILE_SIZE = 512
EARTH_RADIUS_M = 6378137.0
WORLD_SPAN_M = 2 * math.pi * EARTH_RADIUS_M
GLOBAL_COVERAGE_MAX_ZOOM = 12
TERRARIUM_OFFSET = 32768.0
USGS_3DEP_EXPORT_URL = 'https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage'
USGS_NODATA = -9999.0
USGS_VALID_MIN_M = -500.0
UPSTREAM_TIMEOUT_S = 60
UPSTREAM_ATTEMPTS = 3

# Rough boxes (west, south, east, north) where 3DEP has data; 3DEP returns nodata outside the US, which is filled from the ancestor.
USGS_COVERAGE_BOXES: tuple[tuple[float, float, float, float], ...] = (
 (-125.0, 24.0, -66.5, 49.5),
 (-180.0, 51.0, -129.0, 71.5),
 (-160.5, 18.5, -154.5, 22.5),
 (-68.0, 17.5, -64.5, 18.6),
)


#-------TILE MATH-------
def lonlat_to_tile_fraction(lon: float, lat: float, z: int) -> tuple[float, float]:
 n = 2 ** z
 lat = max(min(lat, 85.05112878), -85.05112878)
 x = (lon + 180.0) / 360.0 * n
 y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
 return x, y


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
 x, y = lonlat_to_tile_fraction(lon, lat, z)
 n = 2 ** z
 return min(int(x), n - 1), min(int(y), n - 1)


def tile_bounds_lonlat(z: int, x: int, y: int) -> tuple[float, float, float, float]:
 n = 2 ** z
 west = x / n * 360.0 - 180.0
 east = (x + 1) / n * 360.0 - 180.0
 north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
 south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
 return west, south, east, north


def tile_bounds_mercator(z: int, x: int, y: int) -> tuple[float, float, float, float]:
 span = WORLD_SPAN_M / 2 ** z
 west = -WORLD_SPAN_M / 2 + x * span
 north = WORLD_SPAN_M / 2 - y * span
 return west, north - span, west + span, north


def tile_row_ground_resolution_m(z: int, y: int, size: int = TILE_SIZE) -> np.ndarray:
 """Ground meters per pixel for each pixel row; Mercator stretches by 1/cos(latitude)."""
 n = 2 ** z
 row_y = y + (np.arange(size) + 0.5) / size
 lat = np.arctan(np.sinh(np.pi * (1 - 2 * row_y / n)))
 return WORLD_SPAN_M / n / size * np.cos(lat)


def intersects_usgs_coverage(z: int, x: int, y: int) -> bool:
 west, south, east, north = tile_bounds_lonlat(z, x, y)
 for box_west, box_south, box_east, box_north in USGS_COVERAGE_BOXES:
  if west < box_east and east > box_west and south < box_north and north > box_south:
   return True
 return False


#-------TERRARIUM CODEC-------
def decode_terrarium(rgb: np.ndarray) -> np.ndarray:
 rgb = rgb.astype(np.float64)
 return rgb[..., 0] * 256.0 + rgb[..., 1] + rgb[..., 2] / 256.0 - TERRARIUM_OFFSET


def encode_terrarium(elevation_m: np.ndarray) -> np.ndarray:
 shifted = np.clip(elevation_m + TERRARIUM_OFFSET, 0.0, 65535.99)
 red = np.floor(shifted / 256.0)
 green = np.floor(shifted - red * 256.0)
 blue = np.floor((shifted - red * 256.0 - green) * 256.0)
 return np.stack([red, green, blue], axis=-1).astype(np.uint8)


def decode_tile_bytes(data: bytes) -> np.ndarray:
 with Image.open(io.BytesIO(data)) as image:
  return decode_terrarium(np.asarray(image.convert('RGB')))


def encode_tile_png(elevation_m: np.ndarray) -> bytes:
 buffer = io.BytesIO()
 # PNG instead of lossless WebP: encoding is several times faster and terrarium must stay lossless.
 Image.fromarray(encode_terrarium(elevation_m), 'RGB').save(buffer, format='PNG', compress_level=3)
 return buffer.getvalue()


def image_content_type(data: bytes) -> str:
 if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
  return 'image/webp'
 if data[:8] == b'\x89PNG\r\n\x1a\n':
  return 'image/png'
 raise ValueError('Unknown image format in terrain tile')


#-------RESAMPLING-------
def upsample_quadrant(parent: np.ndarray, depth: int, child_x: int, child_y: int) -> np.ndarray:
 """
 Bilinear-upsample the part of an ancestor tile covering one descendant tile.
 depth = zoom difference; child_x/child_y are the descendant's offsets inside the ancestor (0 .. 2**depth - 1).
 Pixel centers are aligned so repeated levels do not drift.
 """
 size = parent.shape[0]
 factor = 2 ** depth
 span = size / factor
 coords = child_x * span + (np.arange(size) + 0.5) / factor - 0.5
 rows = child_y * span + (np.arange(size) + 0.5) / factor - 0.5
 coords = np.clip(coords, 0, size - 1)
 rows = np.clip(rows, 0, size - 1)
 x0 = np.floor(coords).astype(int)
 y0 = np.floor(rows).astype(int)
 x1 = np.minimum(x0 + 1, size - 1)
 y1 = np.minimum(y0 + 1, size - 1)
 fx = (coords - x0)[None, :]
 fy = (rows - y0)[:, None]
 top = parent[y0][:, x0] * (1 - fx) + parent[y0][:, x1] * fx
 bottom = parent[y1][:, x0] * (1 - fx) + parent[y1][:, x1] * fx
 return top * (1 - fy) + bottom * fy


def sample_bilinear(elevation_m: np.ndarray, px: np.ndarray, py: np.ndarray) -> np.ndarray:
 """Sample at fractional pixel coordinates measured from the tile's top-left corner (pixel edges, not centers)."""
 size = elevation_m.shape[0]
 cx = np.clip(px - 0.5, 0, size - 1)
 cy = np.clip(py - 0.5, 0, size - 1)
 x0 = np.floor(cx).astype(int)
 y0 = np.floor(cy).astype(int)
 x1 = np.minimum(x0 + 1, size - 1)
 y1 = np.minimum(y0 + 1, size - 1)
 fx = cx - x0
 fy = cy - y0
 top = elevation_m[y0, x0] * (1 - fx) + elevation_m[y0, x1] * fx
 bottom = elevation_m[y1, x0] * (1 - fx) + elevation_m[y1, x1] * fx
 return top * (1 - fy) + bottom * fy


#-------UPSTREAM-------
class UpstreamUnavailable(Exception):
 """Transient upstream failure; results derived after this must not be cached."""


def http_get(url: str, user_agent: str) -> bytes | None:
 """Return body, None for 404, or raise UpstreamUnavailable after retries."""
 last_error = ''
 for attempt in range(UPSTREAM_ATTEMPTS):
  try:
   request = urllib.request.Request(url, headers={'User-Agent': user_agent})
   with urllib.request.urlopen(request, timeout=UPSTREAM_TIMEOUT_S) as response:
    return response.read()
  except urllib.error.HTTPError as error:
   if error.code == 404:
    return None
   last_error = f'HTTP {error.code}'
  except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
   last_error = str(error)
  time.sleep(1.5 * (attempt + 1))
 raise UpstreamUnavailable(f'{last_error}: {url}')


@dataclass(frozen=True)
class TerrainSettings:
 mapterhorn_url: str
 max_zoom: int
 usgs_3dep_fill: bool
 usgs_3dep_max_zoom: int
 user_agent: str


@dataclass(frozen=True)
class Tile:
 data: bytes
 source: str

 @property
 def content_type(self) -> str:
  return image_content_type(self.data)


#-------TERRAIN SOURCE-------
class TerrainSource:
 def __init__(self, settings: TerrainSettings, cache_dir: Path):
  self.settings = settings
  self.cache_dir = cache_dir / 'terrain'
  self._locks: dict[tuple[int, int, int], threading.Lock] = {}
  self._locks_guard = threading.Lock()

 def _lock_for(self, key: tuple[int, int, int]) -> threading.Lock:
  with self._locks_guard:
   return self._locks.setdefault(key, threading.Lock())

 def _path(self, z: int, x: int, y: int, suffix: str) -> Path:
  return self.cache_dir / str(z) / str(x) / f'{y}.{suffix}'

 def _write_atomic(self, path: Path, data: bytes) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  temp_path = path.with_name(f'{path.name}.{threading.get_ident()}.tmp')
  temp_path.write_bytes(data)
  temp_path.replace(path)

 def _cached(self, z: int, x: int, y: int) -> Tile | None:
  for suffix, source in (('webp', 'mapterhorn'), ('3dep.png', 'usgs_3dep'), ('derived.png', 'derived')):
   path = self._path(z, x, y, suffix)
   if path.exists():
    return Tile(path.read_bytes(), source)
  return None

 def _fetch_mapterhorn(self, z: int, x: int, y: int) -> Tile | None:
  """Real Mapterhorn tile (cached), or None when Mapterhorn has no tile at this zoom."""
  webp_path = self._path(z, x, y, 'webp')
  if webp_path.exists():
   return Tile(webp_path.read_bytes(), 'mapterhorn')
  missing_path = self._path(z, x, y, '404')
  if missing_path.exists():
   return None
  url = self.settings.mapterhorn_url.format(z=z, x=x, y=y)
  data = http_get(url, self.settings.user_agent)
  if data is None:
   self._write_atomic(missing_path, b'')
   return None
  self._write_atomic(webp_path, data)
  return Tile(data, 'mapterhorn')

 def _fetch_usgs_3dep(self, z: int, x: int, y: int) -> np.ndarray | None:
  west, south, east, north = tile_bounds_mercator(z, x, y)
  url = (f'{USGS_3DEP_EXPORT_URL}?bbox={west},{south},{east},{north}&bboxSR=3857&imageSR=3857'
   f'&size={TILE_SIZE},{TILE_SIZE}&format=tiff&pixelType=F32&noData={USGS_NODATA}'
   f'&interpolation=RSP_BilinearInterpolation&f=image')
  data = http_get(url, self.settings.user_agent)
  if data is None:
   return None
  with Image.open(io.BytesIO(data)) as image:
   elevation = np.asarray(image, dtype=np.float64)
  if elevation.shape != (TILE_SIZE, TILE_SIZE):
   raise UpstreamUnavailable(f'3DEP returned shape {elevation.shape}: {url}')
  valid = np.isfinite(elevation) & (elevation > USGS_VALID_MIN_M)
  if not valid.any():
   return None
  return np.where(valid, elevation, np.nan)

 def _ancestor_elevation(self, z: int, x: int, y: int) -> np.ndarray:
  """Upsampled elevation from the nearest ancestor that has real data."""
  for depth in range(1, z + 1):
   ancestor_z = z - depth
   ancestor_x = x >> depth
   ancestor_y = y >> depth
   tile = self._real_tile(ancestor_z, ancestor_x, ancestor_y)
   if tile is not None:
    parent = decode_tile_bytes(tile.data)
    mask = (1 << depth) - 1
    return upsample_quadrant(parent, depth, x & mask, y & mask)
  return np.zeros((TILE_SIZE, TILE_SIZE))

 def _real_tile(self, z: int, x: int, y: int) -> Tile | None:
  """A tile backed by source data at this zoom (cached or fetched), never a derived one."""
  mapterhorn = self._fetch_mapterhorn(z, x, y)
  if mapterhorn is not None:
   return mapterhorn
  usgs_path = self._path(z, x, y, '3dep.png')
  if usgs_path.exists():
   return Tile(usgs_path.read_bytes(), 'usgs_3dep')
  if self._usgs_eligible(z, x, y):
   return self._build_usgs_tile(z, x, y)
  return None

 def _usgs_eligible(self, z: int, x: int, y: int) -> bool:
  return (self.settings.usgs_3dep_fill and GLOBAL_COVERAGE_MAX_ZOOM < z <= self.settings.usgs_3dep_max_zoom
   and intersects_usgs_coverage(z, x, y) and not self._path(z, x, y, '3dep.404').exists())

 def _build_usgs_tile(self, z: int, x: int, y: int) -> Tile | None:
  elevation = self._fetch_usgs_3dep(z, x, y)
  if elevation is None:
   self._write_atomic(self._path(z, x, y, '3dep.404'), b'')
   return None
  holes = np.isnan(elevation)
  if holes.any():
   elevation = np.where(holes, self._ancestor_elevation(z, x, y), elevation)
  data = encode_tile_png(elevation)
  self._write_atomic(self._path(z, x, y, '3dep.png'), data)
  return Tile(data, 'usgs_3dep')

 def get_tile(self, z: int, x: int, y: int) -> Tile:
  if not (0 <= z <= self.settings.max_zoom and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
   raise ValueError(f'Tile out of range: {z}/{x}/{y}')
  cached = self._cached(z, x, y)
  if cached is not None:
   return cached
  with self._lock_for((z, x, y)):
   cached = self._cached(z, x, y)
   if cached is not None:
    return cached
   tile = self._real_tile(z, x, y)
   if tile is not None:
    return tile
   data = encode_tile_png(self._ancestor_elevation(z, x, y))
   self._write_atomic(self._path(z, x, y, 'derived.png'), data)
   return Tile(data, 'derived')

 def get_elevation_tile(self, z: int, x: int, y: int) -> np.ndarray:
  return decode_tile_bytes(self.get_tile(z, x, y).data)

 def sample_lonlat(self, lons: np.ndarray, lats: np.ndarray, z: int) -> np.ndarray:
  """Bilinear DEM elevation at many points, decoding each touched tile once."""
  lons = np.asarray(lons, dtype=np.float64)
  lats = np.asarray(lats, dtype=np.float64)
  n = 2 ** z
  lat_clamped = np.clip(lats, -85.05112878, 85.05112878)
  fx = (lons + 180.0) / 360.0 * n
  fy = (1.0 - np.arcsinh(np.tan(np.radians(lat_clamped))) / np.pi) / 2.0 * n
  tile_x = np.clip(np.floor(fx).astype(int), 0, n - 1)
  tile_y = np.clip(np.floor(fy).astype(int), 0, n - 1)
  result = np.empty(lons.shape)
  keys = tile_x.astype(np.int64) * n + tile_y
  for key in np.unique(keys):
   selected = keys == key
   tx, ty = int(key // n), int(key % n)
   elevation = self.get_elevation_tile(z, tx, ty)
   result[selected] = sample_bilinear(elevation, (fx[selected] - tx) * TILE_SIZE, (fy[selected] - ty) * TILE_SIZE)
  return result
