"""
Warm the terrain tile cache so flights are instant and work offline.

  python fly/prefetch.py --tracks                          all indexed tracks, 600 m corridor
  python fly/prefetch.py --tracks --buffer 1500 --profiles also compute elevation profiles
  python fly/prefetch.py --bbox -122.65,37.85,-122.50,37.95
  python fly/prefetch.py --place "Mount Tamalpais" --radius-km 6
  python fly/prefetch.py --tracks --dry-run                count tiles only
"""

import argparse
import io
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from settings import load_settings
from terrain import TerrainSource, UpstreamUnavailable, lonlat_to_tile, lonlat_to_tile_fraction
from tracks import TrackLibrary, densify

if sys.platform == 'win32':
 sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

#-------CONSTANTS-------
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
AVERAGE_TILE_KB = 130
WORKERS = 8
PROGRESS_EVERY = 0.05
METERS_PER_DEGREE = 111320.0


def bbox_tiles(west: float, south: float, east: float, north: float, z: int) -> set[tuple[int, int, int]]:
 x0, y0 = lonlat_to_tile(west, north, z)
 x1, y1 = lonlat_to_tile(east, south, z)
 return {(z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


def corridor_tiles(lons: np.ndarray, lats: np.ndarray, buffer_m: float, z: int) -> set[tuple[int, int, int]]:
 """Tiles within buffer_m of any point; points must be spaced well below the tile width."""
 tiles: set[tuple[int, int, int]] = set()
 n = 2 ** z
 for lon, lat in zip(lons, lats):
  d_lat = buffer_m / METERS_PER_DEGREE
  d_lon = buffer_m / (METERS_PER_DEGREE * max(math.cos(math.radians(lat)), 0.01))
  fx0, fy0 = lonlat_to_tile_fraction(lon - d_lon, lat + d_lat, z)
  fx1, fy1 = lonlat_to_tile_fraction(lon + d_lon, lat - d_lat, z)
  for x in range(max(int(fx0), 0), min(int(fx1), n - 1) + 1):
   for y in range(max(int(fy0), 0), min(int(fy1), n - 1) + 1):
    tiles.add((z, x, y))
 return tiles


def geocode(place: str, user_agent: str) -> tuple[float, float, str]:
 url = f'{NOMINATIM_URL}?{urllib.parse.urlencode({"q": place, "format": "json", "limit": 1})}'
 with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': user_agent}), timeout=30) as response:
  results = json.loads(response.read())
 if not results:
  raise SystemExit(f'No place found for {place!r}')
 return float(results[0]['lon']), float(results[0]['lat']), results[0]['display_name']


def fetch_all(terrain: TerrainSource, tiles: list[tuple[int, int, int]]) -> None:
 started = time.time()
 counts: dict[str, int] = {}
 failures: list[str] = []
 next_report = PROGRESS_EVERY
 with ThreadPoolExecutor(max_workers=WORKERS) as pool:
  futures = {pool.submit(terrain.get_tile, *tile): tile for tile in tiles}
  for done, future in enumerate(as_completed(futures), 1):
   tile = futures[future]
   try:
    source = future.result().source
    counts[source] = counts.get(source, 0) + 1
   except UpstreamUnavailable as error:
    failures.append(f'{tile}: {error}')
   if done / len(tiles) >= next_report or done == len(tiles):
    print(f'  {done}/{len(tiles)} tiles  {time.time() - started:.0f}s  {counts}', flush=True)
    next_report += PROGRESS_EVERY
 for failure in failures:
  print(f'  FAILED {failure}')
 if failures:
  print(f'{len(failures)} tiles failed; run again to retry them.')


def main() -> None:
 parser = argparse.ArgumentParser(description='Prefetch terrain tiles into the local cache')
 parser.add_argument('--tracks', action='store_true', help='all indexed tracks')
 parser.add_argument('--bbox', help='west,south,east,north in degrees')
 parser.add_argument('--place', help='place name to geocode (Nominatim)')
 parser.add_argument('--radius-km', type=float, default=5.0, help='radius around --place')
 parser.add_argument('--buffer', type=float, default=600.0, help='corridor half-width around tracks, meters')
 parser.add_argument('--max-zoom', type=int, help='defaults to terrain.max_zoom from settings')
 parser.add_argument('--profiles', action='store_true', help='also compute track elevation profiles')
 parser.add_argument('--dry-run', action='store_true', help='count tiles without downloading')
 args = parser.parse_args()
 if not (args.tracks or args.bbox or args.place):
  parser.error('choose at least one of --tracks, --bbox, --place')

 settings = load_settings()
 terrain = TerrainSource(settings.terrain, settings.cache_dir)
 max_zoom = min(args.max_zoom or settings.terrain.max_zoom, settings.terrain.max_zoom)
 tiles: set[tuple[int, int, int]] = set()
 library = None

 if args.tracks:
  library = TrackLibrary(settings.track_dirs, settings.import_dir, settings.cache_dir, terrain, settings.profile_zoom)
  result = library.scan()
  print(f"Tracks: {result['tracks']}")
  for summary in library.summaries()['tracks']:
   for segment in library.parsed(summary['id']).segments:
    for z in range(0, max_zoom + 1):
     tile_width_m = 40075016.0 / 2 ** z * math.cos(math.radians(segment[0].lat))
     lons, lats, _ = densify(segment, max(tile_width_m / 4, 5.0))
     tiles |= corridor_tiles(lons, lats, args.buffer, z)

 boxes: list[tuple[float, float, float, float]] = []
 if args.bbox:
  west, south, east, north = (float(v) for v in args.bbox.split(','))
  boxes.append((west, south, east, north))
 if args.place:
  lon, lat, label = geocode(args.place, settings.terrain.user_agent)
  print(f'Place: {label} ({lat:.5f}, {lon:.5f})')
  d_lat = args.radius_km * 1000 / METERS_PER_DEGREE
  d_lon = d_lat / max(math.cos(math.radians(lat)), 0.01)
  boxes.append((lon - d_lon, lat - d_lat, lon + d_lon, lat + d_lat))
 for box in boxes:
  for z in range(0, max_zoom + 1):
   tiles |= bbox_tiles(*box, z)

 ordered = sorted(tiles)
 by_zoom = {z: sum(1 for t in ordered if t[0] == z) for z in range(max_zoom + 1)}
 print(f'Tiles to ensure: {len(ordered)} (about {len(ordered) * AVERAGE_TILE_KB / 1024:.0f} MB if none are cached)')
 print('  per zoom: ' + ', '.join(f'z{z}:{c}' for z, c in by_zoom.items() if c))
 if args.dry_run:
  return
 fetch_all(terrain, ordered)

 if args.profiles and library is not None:
  for summary in library.summaries()['tracks']:
   detail = library.detail(summary['id'])
   stats = detail['profile']['stats']
   print(f"  profile {summary['name']}: {stats['distance_m'] / 1000:.2f} km, +{stats['gain_m']:.0f} m / -{stats['loss_m']:.0f} m")


if __name__ == '__main__':
 main()
