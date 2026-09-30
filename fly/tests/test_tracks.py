import json
from pathlib import Path

import numpy as np
import pytest

from tracks import (ParsedTrack, Point, TrackDir, TrackLibrary, build_profile, gps_gain_m, parse_track_file, simplify_indices,
 summarize)

SAMPLE_GPX = Path(__file__).resolve().parents[1] / 'samples' / 'dipsea_trail.gpx'


class SlopedTerrain:
 """Elevation rises 10 m per 100 m northward (10% grade) from 100 m at latitude 37.9."""

 def sample_lonlat(self, lons: np.ndarray, lats: np.ndarray, z: int) -> np.ndarray:
  return 100.0 + (np.asarray(lats) - 37.9) * 111195.0 * 0.10


def write(tmp_path: Path, name: str, text: str) -> Path:
 path = tmp_path / name
 path.write_text(text, encoding='utf-8')
 return path


#-------PARSERS-------
def test_parse_sample_gpx():
 track = parse_track_file(SAMPLE_GPX)
 assert track.name == 'Dipsea Trail (sample)'
 assert len(track.segments) == 1 and len(track.segments[0]) == 462
 assert track.segments[0][0].time is not None


def test_parse_gpx_route_and_elevation(tmp_path):
 path = write(tmp_path, 'plan.gpx', '''<?xml version="1.0"?><gpx version="1.0" xmlns="http://www.topografix.com/GPX/1/0">
  <rte><name>Plan</name><rtept lat="37.0" lon="-122.0"><ele>10</ele></rtept><rtept lat="37.001" lon="-122.0"><ele>12</ele></rtept></rte></gpx>''')
 track = parse_track_file(path)
 assert track.name == 'Plan'
 assert [p.ele for p in track.segments[0]] == [10.0, 12.0]


def test_parse_tcx(tmp_path):
 path = write(tmp_path, 'run.tcx', '''<?xml version="1.0"?><TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Activities><Activity Sport="Hiking"><Id>2026-01-01T10:00:00Z</Id><Lap><Track>
  <Trackpoint><Time>2026-01-01T10:00:00Z</Time><Position><LatitudeDegrees>37.0</LatitudeDegrees><LongitudeDegrees>-122.0</LongitudeDegrees></Position><AltitudeMeters>5</AltitudeMeters></Trackpoint>
  <Trackpoint><Time>2026-01-01T10:01:00Z</Time><Position><LatitudeDegrees>37.001</LatitudeDegrees><LongitudeDegrees>-122.0</LongitudeDegrees></Position></Trackpoint>
  <Trackpoint><Time>2026-01-01T10:02:00Z</Time></Trackpoint>
  </Track></Lap></Activity></Activities></TrainingCenterDatabase>''')
 track = parse_track_file(path)
 assert track.name.startswith('Hiking')
 assert len(track.segments[0]) == 2
 assert track.segments[0][1].time - track.segments[0][0].time == 60


def test_parse_kml_linestring_and_gx_track(tmp_path):
 path = write(tmp_path, 'walks.kml', '''<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">
  <Document><name>Walks</name>
  <Placemark><LineString><coordinates>-122.0,37.0,5 -122.0,37.001,6</coordinates></LineString></Placemark>
  <Placemark><gx:Track><when>2026-01-01T10:00:00Z</when><when>2026-01-01T10:00:30Z</when>
  <gx:coord>-122.1 37.1 1</gx:coord><gx:coord>-122.1 37.101 2</gx:coord></gx:Track></Placemark>
  </Document></kml>''')
 track = parse_track_file(path)
 assert track.name == 'Walks'
 assert len(track.segments) == 2
 assert track.segments[1][1].time - track.segments[1][0].time == 30


def test_parse_geojson_feature_collection(tmp_path):
 document = {'type': 'FeatureCollection', 'features': [
  {'type': 'Feature', 'properties': {'name': 'Loop', 'coordTimes': ['2026-01-01T10:00:00Z', '2026-01-01T10:00:10Z']},
   'geometry': {'type': 'LineString', 'coordinates': [[-122.0, 37.0, 3], [-122.0, 37.0005, 4]]}},
  {'type': 'Feature', 'properties': {}, 'geometry': {'type': 'MultiLineString', 'coordinates': [[[-122.1, 37.1], [-122.1, 37.1005]]]}},
  {'type': 'Feature', 'properties': {}, 'geometry': {'type': 'Point', 'coordinates': [-122.0, 37.0]}},
 ]}
 track = parse_track_file(write(tmp_path, 'loop.geojson', json.dumps(document)))
 assert track.name == 'Loop'
 assert len(track.segments) == 2
 assert track.segments[0][1].time - track.segments[0][0].time == 10


def test_parse_csv_with_alternate_headers(tmp_path):
 path = write(tmp_path, 'log.csv', 'Timestamp,Latitude,Lng,Altitude\n2026-01-01T10:00:00,37.0,-122.0,1\n2026-01-01T10:00:05,37.0001,-122.0,2\n,,,\n')
 track = parse_track_file(path)
 assert len(track.segments[0]) == 2
 assert track.segments[0][0].ele == 1.0


def test_csv_without_coordinates_is_an_error(tmp_path):
 with pytest.raises(ValueError):
  parse_track_file(write(tmp_path, 'bad.csv', 'a,b\n1,2\n'))


#-------GEOMETRY AND STATS-------
def test_simplify_drops_collinear_points_and_keeps_corners():
 lons = np.array([0.0, 0.00001, 0.00002, 0.00003, 0.00003])
 lats = np.array([0.0, 0.0, 0.0, 0.0, 0.001])
 assert list(simplify_indices(lons, lats, 1.0)) == [0, 3, 4]


def test_gain_hysteresis_ignores_noise():
 assert gps_gain_m([100, 100.4, 100.1, 100.5, 102, 101.8, 105]) == pytest.approx(5.0)


def test_summarize_distance_and_duration():
 track = ParsedTrack('t', [[Point(-122.0, 37.0, time=0), Point(-122.0, 37.001, time=100)]])
 summary = summarize(track)
 assert summary['distance_m'] == pytest.approx(111.2, abs=0.2)
 assert summary['duration_s'] == 100


def test_profile_grade_on_uniform_slope():
 track = ParsedTrack('north', [[Point(-122.0, 37.9), Point(-122.0, 37.91)]])
 profile = build_profile(track, SlopedTerrain(), 15)
 grades = np.array(profile['grade'])
 assert profile['stats']['distance_m'] == pytest.approx(1112, abs=2)
 assert np.allclose(grades[5:-5], 10.0, atol=0.2)
 assert profile['stats']['gain_m'] == pytest.approx(111, abs=2)
 assert profile['stats']['loss_m'] == 0
 assert np.diff(profile['dist']).max() <= 5.01


#-------LIBRARY-------
def test_library_scan_import_and_detail(tmp_path):
 walked = tmp_path / 'walked'
 walked.mkdir()
 (walked / 'dipsea.gpx').write_bytes(SAMPLE_GPX.read_bytes())
 (walked / 'broken.gpx').write_text('<gpx><trk>', encoding='utf-8')
 (walked / 'notes.txt').write_text('ignored', encoding='utf-8')
 imported = tmp_path / 'imported'
 library = TrackLibrary([TrackDir(walked, 'walked'), TrackDir(imported, 'walked')], imported, tmp_path / 'cache', SlopedTerrain(), 15)
 result = library.scan()
 assert result['tracks'] == 1
 assert any('broken.gpx' in e['path'] for e in result['errors'])

 summary = library.summaries()['tracks'][0]
 detail = library.detail(summary['id'])
 assert detail['profile']['stats']['distance_m'] == pytest.approx(summary['distance_m'], rel=0.01)
 assert len(library.overview_geojson()['features']) == 1

 csv_text = b'lat,lon\n37.0,-122.0\n37.001,-122.0\n'
 imported_summary = library.import_file('../evil/../walk.csv', csv_text)
 assert (imported / 'walk.csv').exists()
 assert imported_summary['name'] == 'walk'
 assert library.import_file('walk.csv', b'lat,lon\n38.0,-122.0\n38.001,-122.0\n')['file'] == 'walk_1.csv'
 with pytest.raises(ValueError):
  library.import_file('photo.jpg', b'x')
 assert library.scan()['tracks'] == 3
