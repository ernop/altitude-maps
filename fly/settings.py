"""
Loads fly/settings.json (gitignored). On first run it is created from settings.example.json.
Relative paths are resolved against the fly/ directory; track folders under fly/data are created when missing.
"""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from terrain import TerrainSettings
from tracks import TrackDir

FLY_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = FLY_DIR / 'settings.json'
EXAMPLE_PATH = FLY_DIR / 'settings.example.json'
DATA_DIR = FLY_DIR / 'data'
TRACK_KINDS = ('walked', 'planned')


@dataclass(frozen=True)
class Settings:
 host: str
 port: int
 cache_dir: Path
 import_dir: Path
 track_dirs: list[TrackDir]
 terrain: TerrainSettings
 profile_zoom: int


def resolve_path(value: str) -> Path:
 path = Path(value).expanduser()
 return path if path.is_absolute() else (FLY_DIR / path).resolve()


def load_settings() -> Settings:
 if not SETTINGS_PATH.exists():
  shutil.copyfile(EXAMPLE_PATH, SETTINGS_PATH)
  print(f'Created {SETTINGS_PATH} from the example. Edit track_dirs to point at your GPS track folders.')
 raw = json.loads(SETTINGS_PATH.read_text(encoding='utf-8'))
 import_dir = resolve_path(raw['import_dir'])
 track_dirs = []
 for entry in raw['track_dirs']:
  if entry['kind'] not in TRACK_KINDS:
   raise ValueError(f"track_dirs kind must be one of {TRACK_KINDS}, got {entry['kind']!r}")
  track_dirs.append(TrackDir(resolve_path(entry['path']), entry['kind']))
 if all(d.path != import_dir for d in track_dirs):
  track_dirs.append(TrackDir(import_dir, 'walked'))
 for track_dir in track_dirs:
  if DATA_DIR in track_dir.path.parents:
   track_dir.path.mkdir(parents=True, exist_ok=True)
 terrain_raw = raw['terrain']
 terrain = TerrainSettings(
  mapterhorn_url=terrain_raw['mapterhorn_url'],
  max_zoom=int(terrain_raw['max_zoom']),
  usgs_3dep_fill=bool(terrain_raw['usgs_3dep_fill']),
  usgs_3dep_max_zoom=int(terrain_raw['usgs_3dep_max_zoom']),
  user_agent=raw['user_agent'],
 )
 return Settings(
  host=raw['host'],
  port=int(raw['port']),
  cache_dir=resolve_path(raw['cache_dir']),
  import_dir=import_dir,
  track_dirs=track_dirs,
  terrain=terrain,
  profile_zoom=min(int(raw['profile_zoom']), terrain.max_zoom),
 )
