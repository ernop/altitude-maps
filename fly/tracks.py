"""
GPS tracks: parse GPX/TCX/KML/GeoJSON/CSV into segments, simplify, summarize, index on disk,
and build DEM-based elevation profiles with grade (see PRODUCT.md, "Track policy").
"""

import csv
import hashlib
import io
import json
import math
import threading
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np

from terrain import TerrainSource

#-------CONSTANTS-------
TRACK_EXTENSIONS = ('.gpx', '.tcx', '.kml', '.geojson', '.json', '.csv')
TrackKind = Literal['walked', 'planned']
DETAIL_TOLERANCE_M = 1.0
OVERVIEW_TOLERANCE_M = 8.0
PROFILE_SPACING_M = 5.0
GRADE_WINDOW_M = 30.0
GAIN_HYSTERESIS_M = 1.0
PROFILE_ZOOM = 15
INDEX_FORMAT_VERSION = 1
PROFILE_FORMAT_VERSION = 1
METERS_PER_DEGREE = 111320.0

CSV_LAT_NAMES = ('lat', 'latitude')
CSV_LON_NAMES = ('lon', 'lng', 'long', 'longitude')
CSV_ELE_NAMES = ('ele', 'elevation', 'alt', 'altitude')
CSV_TIME_NAMES = ('time', 'timestamp', 'datetime', 'date')


@dataclass
class Point:
 lon: float
 lat: float
 ele: float | None = None
 time: float | None = None


@dataclass
class ParsedTrack:
 name: str
 segments: list[list[Point]] = field(default_factory=list)


#-------PARSING HELPERS-------
def local_name(tag: str) -> str:
 return tag.rsplit('}', 1)[-1]


def child_text(element: ElementTree.Element, name: str) -> str | None:
 for child in element:
  if local_name(child.tag) == name:
   return (child.text or '').strip() or None
 return None


def parse_time(text: str | None) -> float | None:
 if not text:
  return None
 text = text.strip()
 if text.endswith('Z'):
  text = text[:-1] + '+00:00'
 try:
  moment = datetime.fromisoformat(text)
 except ValueError:
  return None
 if moment.tzinfo is None:
  moment = moment.replace(tzinfo=timezone.utc)
 return moment.timestamp()


def parse_float(text: str | None) -> float | None:
 if text is None or text == '':
  return None
 try:
  value = float(text)
 except ValueError:
  return None
 return value if math.isfinite(value) else None


#-------FORMAT PARSERS-------
def parse_gpx(data: bytes, fallback_name: str) -> ParsedTrack:
 root = ElementTree.fromstring(data)
 track = ParsedTrack(fallback_name)
 names: list[str] = []
 for element in root.iter():
  tag = local_name(element.tag)
  if tag in ('trk', 'rte'):
   name = child_text(element, 'name')
   if name:
    names.append(name)
  if tag in ('trkseg', 'rte'):
   point_tag = 'trkpt' if tag == 'trkseg' else 'rtept'
   segment = [Point(float(p.attrib['lon']), float(p.attrib['lat']), parse_float(child_text(p, 'ele')), parse_time(child_text(p, 'time')))
    for p in element if local_name(p.tag) == point_tag]
   if segment:
    track.segments.append(segment)
  if tag == 'metadata' and not names:
   name = child_text(element, 'name')
   if name:
    names.append(name)
 if names:
  track.name = names[0]
 return track


def parse_tcx(data: bytes, fallback_name: str) -> ParsedTrack:
 root = ElementTree.fromstring(data)
 track = ParsedTrack(fallback_name)
 for element in root.iter():
  if local_name(element.tag) == 'Activity':
   activity_id = child_text(element, 'Id')
   sport = element.attrib.get('Sport')
   if activity_id:
    track.name = f'{sport} {activity_id}' if sport else activity_id
  if local_name(element.tag) != 'Track':
   continue
  segment: list[Point] = []
  for trackpoint in element:
   if local_name(trackpoint.tag) != 'Trackpoint':
    continue
   position = next((c for c in trackpoint if local_name(c.tag) == 'Position'), None)
   if position is None:
    continue
   lat = parse_float(child_text(position, 'LatitudeDegrees'))
   lon = parse_float(child_text(position, 'LongitudeDegrees'))
   if lat is None or lon is None:
    continue
   segment.append(Point(lon, lat, parse_float(child_text(trackpoint, 'AltitudeMeters')), parse_time(child_text(trackpoint, 'Time'))))
  if segment:
   track.segments.append(segment)
 return track


def parse_kml(data: bytes, fallback_name: str) -> ParsedTrack:
 root = ElementTree.fromstring(data)
 track = ParsedTrack(fallback_name)
 for element in root.iter():
  tag = local_name(element.tag)
  if tag in ('Document', 'Placemark') and track.name == fallback_name:
   name = child_text(element, 'name')
   if name:
    track.name = name
  if tag == 'LineString':
   coordinates = child_text(element, 'coordinates') or ''
   segment = []
   for token in coordinates.split():
    parts = token.split(',')
    if len(parts) >= 2:
     segment.append(Point(float(parts[0]), float(parts[1]), parse_float(parts[2]) if len(parts) > 2 else None))
   if segment:
    track.segments.append(segment)
  if tag == 'Track':
   times = [parse_time(c.text) for c in element if local_name(c.tag) == 'when']
   coords = [(c.text or '').split() for c in element if local_name(c.tag) == 'coord']
   segment = []
   for index, parts in enumerate(coords):
    if len(parts) >= 2:
     segment.append(Point(float(parts[0]), float(parts[1]), parse_float(parts[2]) if len(parts) > 2 else None, times[index] if index < len(times) else None))
   if segment:
    track.segments.append(segment)
 return track


def parse_geojson(data: bytes, fallback_name: str) -> ParsedTrack:
 document = json.loads(data)
 track = ParsedTrack(fallback_name)

 def add_line(coordinates: list, times: list | None) -> None:
  segment = []
  for index, position in enumerate(coordinates):
   ele = position[2] if len(position) > 2 else None
   moment = parse_time(times[index]) if times and index < len(times) and isinstance(times[index], str) else None
   segment.append(Point(float(position[0]), float(position[1]), ele, moment))
  if segment:
   track.segments.append(segment)

 def visit(node: dict, properties: dict) -> None:
  node_type = node.get('type')
  if node_type == 'FeatureCollection':
   for feature in node.get('features', []):
    visit(feature, feature.get('properties') or {})
  elif node_type == 'Feature':
   props = node.get('properties') or {}
   if track.name == fallback_name and props.get('name'):
    track.name = str(props['name'])
   if node.get('geometry'):
    visit(node['geometry'], props)
  elif node_type == 'LineString':
   add_line(node['coordinates'], properties.get('coordTimes') or properties.get('times'))
  elif node_type == 'MultiLineString':
   all_times = properties.get('coordTimes') or properties.get('times')
   for index, line in enumerate(node['coordinates']):
    line_times = all_times[index] if all_times and index < len(all_times) and isinstance(all_times[index], list) else None
    add_line(line, line_times)
  elif node_type == 'GeometryCollection':
   for geometry in node.get('geometries', []):
    visit(geometry, properties)

 visit(document, {})
 return track


def parse_csv(data: bytes, fallback_name: str) -> ParsedTrack:
 text = data.decode('utf-8-sig', errors='replace')
 reader = csv.DictReader(io.StringIO(text))
 if not reader.fieldnames:
  return ParsedTrack(fallback_name)
 columns = {name.strip().lower(): name for name in reader.fieldnames}

 def pick(candidates: tuple[str, ...]) -> str | None:
  return next((columns[c] for c in candidates if c in columns), None)

 lat_column, lon_column = pick(CSV_LAT_NAMES), pick(CSV_LON_NAMES)
 if lat_column is None or lon_column is None:
  raise ValueError(f'CSV needs latitude and longitude columns; found {list(columns)}')
 ele_column, time_column = pick(CSV_ELE_NAMES), pick(CSV_TIME_NAMES)
 segment = []
 for row in reader:
  lat, lon = parse_float(row.get(lat_column)), parse_float(row.get(lon_column))
  if lat is None or lon is None:
   continue
  segment.append(Point(lon, lat, parse_float(row.get(ele_column)) if ele_column else None, parse_time(row.get(time_column)) if time_column else None))
 return ParsedTrack(fallback_name, [segment] if segment else [])


PARSERS = {'.gpx': parse_gpx, '.tcx': parse_tcx, '.kml': parse_kml, '.geojson': parse_geojson, '.json': parse_geojson, '.csv': parse_csv}


def parse_track_file(path: Path) -> ParsedTrack:
 parser = PARSERS[path.suffix.lower()]
 track = parser(path.read_bytes(), path.stem.replace('_', ' '))
 track.segments = [[p for p in s if -180 <= p.lon <= 180 and -90 <= p.lat <= 90] for s in track.segments]
 track.segments = [s for s in track.segments if len(s) >= 2]
 return track


#-------GEOMETRY-------
def local_xy_m(lons: np.ndarray, lats: np.ndarray, ref_lat: float) -> tuple[np.ndarray, np.ndarray]:
 return lons * METERS_PER_DEGREE * math.cos(math.radians(ref_lat)), lats * METERS_PER_DEGREE


def haversine_m(lon1: np.ndarray, lat1: np.ndarray, lon2: np.ndarray, lat2: np.ndarray) -> np.ndarray:
 phi1, phi2 = np.radians(lat1), np.radians(lat2)
 d_phi = phi2 - phi1
 d_lambda = np.radians(lon2 - lon1)
 a = np.sin(d_phi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(d_lambda / 2) ** 2
 return 2 * 6371008.8 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def simplify_indices(lons: np.ndarray, lats: np.ndarray, tolerance_m: float) -> np.ndarray:
 """Douglas-Peucker on a local equirectangular projection; iterative to avoid recursion limits on long tracks."""
 count = len(lons)
 if count <= 2:
  return np.arange(count)
 x, y = local_xy_m(lons, lats, float(np.mean(lats)))
 keep = np.zeros(count, dtype=bool)
 keep[0] = keep[-1] = True
 stack = [(0, count - 1)]
 while stack:
  start, end = stack.pop()
  if end - start < 2:
   continue
  dx, dy = x[end] - x[start], y[end] - y[start]
  length = math.hypot(dx, dy)
  inner_x, inner_y = x[start + 1:end] - x[start], y[start + 1:end] - y[start]
  if length == 0:
   distances = np.hypot(inner_x, inner_y)
  else:
   distances = np.abs(inner_x * dy - inner_y * dx) / length
  farthest = int(np.argmax(distances))
  if distances[farthest] > tolerance_m:
   split = start + 1 + farthest
   keep[split] = True
   stack.append((start, split))
   stack.append((split, end))
 return np.flatnonzero(keep)


def segment_arrays(segment: list[Point]) -> tuple[np.ndarray, np.ndarray]:
 return np.array([p.lon for p in segment]), np.array([p.lat for p in segment])


def simplified_lines(track: ParsedTrack, tolerance_m: float) -> list[list[list[float]]]:
 lines = []
 for segment in track.segments:
  lons, lats = segment_arrays(segment)
  indices = simplify_indices(lons, lats, tolerance_m)
  lines.append([[round(float(lons[i]), 6), round(float(lats[i]), 6)] for i in indices])
 return lines


def gps_gain_m(elevations: list[float]) -> float:
 gain, anchor = 0.0, None
 for value in elevations:
  if anchor is None:
   anchor = value
  elif value - anchor >= GAIN_HYSTERESIS_M:
   gain += value - anchor
   anchor = value
  elif anchor - value >= GAIN_HYSTERESIS_M:
   anchor = value
 return float(gain)


def summarize(track: ParsedTrack) -> dict:
 all_lons = np.concatenate([segment_arrays(s)[0] for s in track.segments])
 all_lats = np.concatenate([segment_arrays(s)[1] for s in track.segments])
 distance = 0.0
 for segment in track.segments:
  lons, lats = segment_arrays(segment)
  distance += float(haversine_m(lons[:-1], lats[:-1], lons[1:], lats[1:]).sum())
 times = [p.time for s in track.segments for p in s if p.time is not None]
 return {
  'name': track.name,
  'bbox': [round(float(all_lons.min()), 6), round(float(all_lats.min()), 6), round(float(all_lons.max()), 6), round(float(all_lats.max()), 6)],
  'distance_m': round(distance, 1),
  'points': int(len(all_lons)),
  'segments': len(track.segments),
  'start_time': min(times) if times else None,
  'duration_s': (max(times) - min(times)) if len(times) >= 2 else None,
 }


#-------PROFILE-------
def densify(segment: list[Point], spacing_m: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
 """Resample a segment at <= spacing_m, interpolating time; returns lons, lats, times (NaN when absent)."""
 lons, lats = segment_arrays(segment)
 times = np.array([p.time if p.time is not None else np.nan for p in segment])
 step = haversine_m(lons[:-1], lats[:-1], lons[1:], lats[1:])
 along = np.concatenate([[0.0], np.cumsum(step)])
 if along[-1] == 0:
  return lons[:1], lats[:1], times[:1]
 samples = np.unique(np.concatenate([np.arange(0.0, along[-1], spacing_m), [along[-1]], along]))
 has_time = np.isfinite(times)
 sampled_times = np.interp(samples, along[has_time], times[has_time]) if has_time.sum() >= 2 else np.full(len(samples), np.nan)
 return np.interp(samples, along, lons), np.interp(samples, along, lats), sampled_times


def smooth_by_distance(distance: np.ndarray, values: np.ndarray, window_m: float) -> np.ndarray:
 half = window_m / 2
 cumulative = np.concatenate([[0.0], np.cumsum(values)])
 lo = np.searchsorted(distance, distance - half, side='left')
 hi = np.searchsorted(distance, distance + half, side='right')
 return (cumulative[hi] - cumulative[lo]) / (hi - lo)


def build_profile(track: ParsedTrack, terrain: TerrainSource, zoom: int) -> dict:
 parts = [densify(s, PROFILE_SPACING_M) for s in track.segments]
 lons = np.concatenate([p[0] for p in parts])
 lats = np.concatenate([p[1] for p in parts])
 times = np.concatenate([p[2] for p in parts])
 step = np.concatenate([[0.0], haversine_m(lons[:-1], lats[:-1], lons[1:], lats[1:])])
 distance = np.cumsum(step)
 elevation = terrain.sample_lonlat(lons, lats, zoom)
 smoothed = smooth_by_distance(distance, elevation, PROFILE_SPACING_M * 3)
 half = GRADE_WINDOW_M / 2
 ahead = np.interp(np.minimum(distance + half, distance[-1]), distance, smoothed)
 behind = np.interp(np.maximum(distance - half, 0.0), distance, smoothed)
 span = np.minimum(distance + half, distance[-1]) - np.maximum(distance - half, 0.0)
 grade = np.where(span > 0, 100.0 * (ahead - behind) / np.maximum(span, 1e-9), 0.0)
 gain = gps_gain_m(list(smoothed))
 loss = gps_gain_m(list(-smoothed))
 has_time = np.isfinite(times)
 start_time = float(times[has_time][0]) if has_time.any() else None
 relative_times = [None if not math.isfinite(t) else round(float(t - start_time), 1) for t in times] if start_time is not None else None
 return {
  'format_version': PROFILE_FORMAT_VERSION,
  'zoom': zoom,
  'lon': [round(float(v), 6) for v in lons],
  'lat': [round(float(v), 6) for v in lats],
  'ele': [round(float(v), 2) for v in elevation],
  'dist': [round(float(v), 1) for v in distance],
  'grade': [round(float(v), 1) for v in grade],
  't': relative_times,
  'stats': {
   'distance_m': round(float(distance[-1]), 1),
   'gain_m': round(gain, 1),
   'loss_m': round(loss, 1),
   'min_ele_m': round(float(elevation.min()), 1),
   'max_ele_m': round(float(elevation.max()), 1),
   'max_grade_pct': round(float(np.abs(grade).max()), 1),
   'start_time': start_time,
   'duration_s': round(float(times[has_time][-1] - start_time), 1) if has_time.sum() >= 2 else None,
  },
 }


#-------LIBRARY-------
@dataclass(frozen=True)
class TrackDir:
 path: Path
 kind: TrackKind


def track_id_for(path: Path) -> str:
 return hashlib.sha1(str(path.resolve()).encode('utf-8')).hexdigest()[:12]


class TrackLibrary:
 """Scans track folders, caches parsed summaries and geometry keyed by file size and mtime."""

 def __init__(self, track_dirs: list[TrackDir], import_dir: Path, cache_dir: Path, terrain: TerrainSource, profile_zoom: int):
  self.track_dirs = track_dirs
  self.import_dir = import_dir
  self.cache_dir = cache_dir / 'tracks'
  self.terrain = terrain
  self.profile_zoom = profile_zoom
  self._lock = threading.Lock()
  self._entries: dict[str, dict] = {}
  self._errors: list[dict] = []

 def _index_path(self) -> Path:
  return self.cache_dir / 'index.json'

 def _load_index(self) -> dict:
  path = self._index_path()
  if not path.exists():
   return {}
  document = json.loads(path.read_text(encoding='utf-8'))
  if document.get('format_version') != INDEX_FORMAT_VERSION:
   return {}
  return document['files']

 def _save_index(self, files: dict) -> None:
  self.cache_dir.mkdir(parents=True, exist_ok=True)
  temp_path = self._index_path().with_suffix('.tmp')
  temp_path.write_text(json.dumps({'format_version': INDEX_FORMAT_VERSION, 'files': files}), encoding='utf-8')
  temp_path.replace(self._index_path())

 def _geometry_path(self, track_id: str) -> Path:
  return self.cache_dir / f'{track_id}.geometry.json'

 def _profile_path(self, track_id: str) -> Path:
  return self.cache_dir / f'{track_id}.profile.z{self.profile_zoom}.json'

 def scan(self) -> dict:
  with self._lock:
   previous = self._load_index()
   files: dict[str, dict] = {}
   errors: list[dict] = []
   for track_dir in self.track_dirs:
    if not track_dir.path.exists():
     errors.append({'path': str(track_dir.path), 'error': 'Folder does not exist'})
     continue
    for path in sorted(track_dir.path.rglob('*')):
     if not path.is_file() or path.suffix.lower() not in TRACK_EXTENSIONS:
      continue
     key = str(path.resolve())
     stat = path.stat()
     cached = previous.get(key)
     if cached and cached['size'] == stat.st_size and cached['mtime'] == stat.st_mtime and self._geometry_path(cached['summary']['id']).exists():
      cached['summary']['kind'] = track_dir.kind
      files[key] = cached
      continue
     try:
      files[key] = self._index_file(path, track_dir.kind, stat.st_size, stat.st_mtime)
     except (ValueError, KeyError, ElementTree.ParseError, json.JSONDecodeError, UnicodeDecodeError) as error:
      errors.append({'path': key, 'error': f'{type(error).__name__}: {error}'})
   self._save_index(files)
   self._entries = {entry['summary']['id']: {**entry, 'path': key} for key, entry in files.items()}
   self._errors = errors
   return {'tracks': len(files), 'errors': errors}

 def _index_file(self, path: Path, kind: TrackKind, size: int, mtime: float) -> dict:
  track = parse_track_file(path)
  if not track.segments:
   raise ValueError('No track points found')
  track_id = track_id_for(path)
  summary = {'id': track_id, 'kind': kind, 'file': path.name, **summarize(track)}
  geometry = {'detail': simplified_lines(track, DETAIL_TOLERANCE_M), 'overview': simplified_lines(track, OVERVIEW_TOLERANCE_M)}
  self.cache_dir.mkdir(parents=True, exist_ok=True)
  self._geometry_path(track_id).write_text(json.dumps(geometry), encoding='utf-8')
  return {'size': size, 'mtime': mtime, 'summary': summary}

 def summaries(self) -> dict:
  tracks = sorted((e['summary'] for e in self._entries.values()), key=lambda s: s['start_time'] or 0, reverse=True)
  return {'tracks': tracks, 'errors': self._errors}

 def overview_geojson(self) -> dict:
  features = []
  for track_id, entry in self._entries.items():
   geometry = json.loads(self._geometry_path(track_id).read_text(encoding='utf-8'))
   summary = entry['summary']
   features.append({'type': 'Feature', 'id': len(features), 'properties': {'id': track_id, 'kind': summary['kind'], 'name': summary['name']},
    'geometry': {'type': 'MultiLineString', 'coordinates': geometry['overview']}})
  return {'type': 'FeatureCollection', 'features': features}

 def parsed(self, track_id: str) -> ParsedTrack:
  entry = self._entries.get(track_id)
  if entry is None:
   raise KeyError(track_id)
  return parse_track_file(Path(entry['path']))

 def detail(self, track_id: str) -> dict:
  entry = self._entries.get(track_id)
  if entry is None:
   raise KeyError(track_id)
  geometry = json.loads(self._geometry_path(track_id).read_text(encoding='utf-8'))
  profile_path = self._profile_path(track_id)
  if profile_path.exists():
   profile = json.loads(profile_path.read_text(encoding='utf-8'))
  else:
   profile = build_profile(self.parsed(track_id), self.terrain, self.profile_zoom)
   profile_path.write_text(json.dumps(profile), encoding='utf-8')
  return {'summary': entry['summary'], 'lines': geometry['detail'], 'profile': profile}

 def import_file(self, filename: str, data: bytes) -> dict:
  safe_name = Path(filename).name
  if Path(safe_name).suffix.lower() not in TRACK_EXTENSIONS:
   raise ValueError(f'Unsupported track file type: {safe_name}')
  self.import_dir.mkdir(parents=True, exist_ok=True)
  target = self.import_dir / safe_name
  counter = 1
  while target.exists() and target.read_bytes() != data:
   target = self.import_dir / f'{Path(safe_name).stem}_{counter}{Path(safe_name).suffix}'
   counter += 1
  target.write_bytes(data)
  self.scan()
  track_id = track_id_for(target)
  if track_id not in self._entries:
   failure = next((e['error'] for e in self._errors if e['path'] == str(target.resolve())), 'not indexed')
   raise ValueError(f'Could not read {safe_name}: {failure}')
  return self._entries[track_id]['summary']
