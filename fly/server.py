"""
Local server for the terrain flyover viewer.

  python fly/server.py              then open http://127.0.0.1:8002/
  python fly/server.py --no-browser

Serves the viewer, cached terrain and slope tiles, and the GPS track API. See PRODUCT.md.
"""

import argparse
import gzip
import io
import json
import mimetypes
import re
import sys
import threading
import traceback
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from settings import FLY_DIR, Settings, load_settings
from slope import render_slope_png
from terrain import TILE_SIZE, TerrainSource, UpstreamUnavailable
from tracks import TrackLibrary

if sys.platform == 'win32':
 sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
 sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

#-------CONSTANTS-------
STATIC_FILES = {'/': 'index.html', '/index.html': 'index.html', '/favicon.svg': 'favicon.svg'}
STATIC_DIRS = ('css', 'js')
TERRAIN_ROUTE = re.compile(r'^/tiles/terrain/(\d+)/(\d+)/(\d+)$')
SLOPE_ROUTE = re.compile(r'^/tiles/slope/(\d+)/(\d+)/(\d+)\.png$')
TRACK_ROUTE = re.compile(r'^/api/tracks/([0-9a-f]{12})$')
TILE_CACHE_SECONDS = 7 * 24 * 3600
MAX_IMPORT_BYTES = 200 * 1024 * 1024
TERRAIN_ATTRIBUTION = ('<a href="https://mapterhorn.com/attribution" target="_blank">Mapterhorn</a>, '
 '<a href="https://www.usgs.gov/3d-elevation-program" target="_blank">USGS 3DEP</a>')


class FlyApp:
 def __init__(self, settings: Settings):
  self.settings = settings
  self.terrain = TerrainSource(settings.terrain, settings.cache_dir)
  self.library = TrackLibrary(settings.track_dirs, settings.import_dir, settings.cache_dir, self.terrain, settings.profile_zoom)
  self.slope_dir = settings.cache_dir / 'slope'
  self._slope_lock = threading.Lock()

 def config(self) -> dict:
  return {
   'terrain': {'tiles': ['/tiles/terrain/{z}/{x}/{y}'], 'tileSize': TILE_SIZE, 'maxzoom': self.settings.terrain.max_zoom,
    'encoding': 'terrarium', 'attribution': TERRAIN_ATTRIBUTION},
   'slope': {'tiles': ['/tiles/slope/{z}/{x}/{y}.png'], 'tileSize': TILE_SIZE, 'minzoom': 10, 'maxzoom': self.settings.terrain.max_zoom},
   'track_dirs': [{'path': str(d.path), 'kind': d.kind} for d in self.settings.track_dirs],
  }

 def slope_tile(self, z: int, x: int, y: int) -> bytes:
  path = self.slope_dir / str(z) / str(x) / f'{y}.png'
  if path.exists():
   return path.read_bytes()
  data = render_slope_png(self.terrain.get_elevation_tile(z, x, y), z, y)
  path.parent.mkdir(parents=True, exist_ok=True)
  temp_path = path.with_name(f'{path.name}.{threading.get_ident()}.tmp')
  temp_path.write_bytes(data)
  temp_path.replace(path)
  return data


def make_handler(app: FlyApp) -> type[BaseHTTPRequestHandler]:
 class Handler(BaseHTTPRequestHandler):
  server_version = 'AltitudeMapsFly/1.0'

  def log_message(self, format: str, *args) -> None:
   if args and isinstance(args[1], str) and args[1].startswith(('4', '5')):
    super().log_message(format, *args)

  #-------RESPONSES-------
  def send_bytes(self, data: bytes, content_type: str, cache_seconds: int = 0, extra_headers: dict | None = None) -> None:
   self.send_response(HTTPStatus.OK)
   self.send_header('Content-Type', content_type)
   self.send_header('Content-Length', str(len(data)))
   self.send_header('Cache-Control', f'public, max-age={cache_seconds}' if cache_seconds else 'no-cache')
   for name, value in (extra_headers or {}).items():
    self.send_header(name, value)
   self.end_headers()
   self.wfile.write(data)

  def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
   body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
   gzip_ok = 'gzip' in self.headers.get('Accept-Encoding', '') and len(body) > 1024
   if gzip_ok:
    body = gzip.compress(body, compresslevel=5)
   self.send_response(status)
   self.send_header('Content-Type', 'application/json')
   self.send_header('Content-Length', str(len(body)))
   self.send_header('Cache-Control', 'no-cache')
   if gzip_ok:
    self.send_header('Content-Encoding', 'gzip')
   self.end_headers()
   self.wfile.write(body)

  def send_error_json(self, status: HTTPStatus, message: str) -> None:
   self.send_json({'error': message}, status)

  #-------ROUTING-------
  def do_GET(self) -> None:
   path = urllib.parse.urlsplit(self.path).path
   try:
    if match := TERRAIN_ROUTE.match(path):
     tile = app.terrain.get_tile(*map(int, match.groups()))
     self.send_bytes(tile.data, tile.content_type, TILE_CACHE_SECONDS, {'X-Terrain-Source': tile.source})
    elif match := SLOPE_ROUTE.match(path):
     self.send_bytes(app.slope_tile(*map(int, match.groups())), 'image/png', TILE_CACHE_SECONDS)
    elif path == '/api/config':
     self.send_json(app.config())
    elif path == '/api/tracks':
     self.send_json(app.library.summaries())
    elif path == '/api/tracks/overview.geojson':
     self.send_json(app.library.overview_geojson())
    elif match := TRACK_ROUTE.match(path):
     self.send_json(app.library.detail(match.group(1)))
    else:
     self.serve_static(path)
   except ValueError as error:
    self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
   except KeyError as error:
    self.send_error_json(HTTPStatus.NOT_FOUND, f'Not found: {error}')
   except UpstreamUnavailable as error:
    print(f'UPSTREAM UNAVAILABLE {path}: {error}', flush=True)
    self.send_error_json(HTTPStatus.BAD_GATEWAY, str(error))
   except (BrokenPipeError, ConnectionResetError):
    pass
   except Exception:
    traceback.print_exc()
    self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, 'Internal error; see server log')

  def do_POST(self) -> None:
   parts = urllib.parse.urlsplit(self.path)
   try:
    if parts.path == '/api/tracks/import':
     length = int(self.headers.get('Content-Length', '0'))
     if length <= 0 or length > MAX_IMPORT_BYTES:
      raise ValueError(f'Upload size must be between 1 byte and {MAX_IMPORT_BYTES} bytes')
     name = urllib.parse.parse_qs(parts.query).get('name', [''])[0]
     self.send_json(app.library.import_file(name, self.rfile.read(length)))
    elif parts.path == '/api/tracks/rescan':
     self.send_json(app.library.scan())
    else:
     self.send_error_json(HTTPStatus.NOT_FOUND, f'No route {parts.path}')
   except ValueError as error:
    self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
   except Exception:
    traceback.print_exc()
    self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, 'Internal error; see server log')

  def serve_static(self, path: str) -> None:
   relative = STATIC_FILES.get(path)
   if relative is None:
    parts = [p for p in path.split('/') if p]
    if len(parts) >= 2 and parts[0] in STATIC_DIRS and all(p not in ('.', '..') for p in parts):
     relative = '/'.join(parts)
   file_path = (FLY_DIR / relative).resolve() if relative else None
   if file_path is None or not file_path.is_file() or FLY_DIR not in file_path.parents:
    self.send_error_json(HTTPStatus.NOT_FOUND, f'No such file: {path}')
    return
   content_type = mimetypes.guess_type(file_path.name)[0] or 'application/octet-stream'
   if file_path.suffix == '.js':
    content_type = 'text/javascript'
   self.send_bytes(file_path.read_bytes(), content_type)

 return Handler


def main() -> None:
 parser = argparse.ArgumentParser(description='Terrain flyover viewer server')
 parser.add_argument('--no-browser', action='store_true', help='do not open a browser window')
 args = parser.parse_args()
 settings = load_settings()
 app = FlyApp(settings)
 print('Track folders:')
 for track_dir in settings.track_dirs:
  print(f'  [{track_dir.kind}] {track_dir.path}{"" if track_dir.path.exists() else "  (missing)"}')
 result = app.library.scan()
 print(f"Indexed {result['tracks']} tracks")
 for error in result['errors']:
  print(f"  SKIPPED {error['path']}: {error['error']}")
 print(f'Tile cache: {settings.cache_dir}')
 server = ThreadingHTTPServer((settings.host, settings.port), make_handler(app))
 server.daemon_threads = True
 url = f'http://{settings.host}:{settings.port}/'
 print(f'Serving {url}  (Ctrl+C to stop)', flush=True)
 if not args.no_browser:
  webbrowser.open(url)
 try:
  server.serve_forever()
 except KeyboardInterrupt:
  print('Stopped')


if __name__ == '__main__':
 main()
