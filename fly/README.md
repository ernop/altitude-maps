# Flyover

Fly over terrain anywhere on Earth at the best available resolution (1 m lidar across most of California and the US, 0.5 m in some places, 30 m everywhere else), with your GPS tracks draped on it and vertical exaggeration up to 10x.

Product requirements and decisions: [../PRODUCT.md](../PRODUCT.md).

## Start

```bash
pip install -r fly/requirements.txt
python fly/server.py
```

The browser opens at http://127.0.0.1:8002/. The first run creates `fly/settings.json` from `fly/settings.example.json`.

## Your tracks

Edit `fly/settings.json` and list your track folders (use forward slashes on Windows):

```json
"track_dirs": [
  { "path": "C:/Users/YOU/matthoom/exports", "kind": "walked" },
  { "path": "data/tracks/planned", "kind": "planned" }
]
```

- Formats: GPX, TCX, KML, GeoJSON, CSV (with latitude and longitude columns). Folders are scanned recursively.
- `walked` tracks are red and `planned` tracks are cyan.
- Dragging files onto the page (or using Import) copies them into `fly/data/tracks/imported/`.
- After adding files to a folder, press Rescan.

## Using it

- Select a track to fly to it. The track is colored by walking grade, and an elevation profile appears. Profile elevations come from the terrain model, not from GPS altitude.
- Fly along starts a chase camera that follows the track. Drag on the profile to scrub.
- Orbit mode uses the mouse: left drag pans, right drag rotates and tilts, the wheel zooms.
- Fly mode: drag to look around; the wheel changes speed.
- Keys (both modes): W A S D move, Q / E down / up, arrows turn and tilt, Shift for 5x speed, F toggles Fly mode, Space plays the fly-along, R reframes, Esc returns to Orbit.
- The Slope steepness overlay colors the terrain in walking-grade bands: 5%, 10%, 15%, 20%, 30%, 45%, 70%, and 100%.
- The Place box accepts a place name or `lat, lon`.
- The URL records the current view, so views can be bookmarked.

## Offline and speed

Every terrain tile you look at is cached in `fly/data/cache/`. To download ahead of time:

```bash
python fly/prefetch.py --tracks --profiles              # 600 m corridor around every track
python fly/prefetch.py --place "Half Dome" --radius-km 8
python fly/prefetch.py --bbox -122.65,37.85,-122.50,37.95 --dry-run
```

A 10 km walk with the default corridor needs about 150 tiles (about 20 MB).

## Terrain sources

1. [Mapterhorn](https://mapterhorn.com/) is the primary source.
2. [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) fills US tiles that Mapterhorn does not yet have. Newly published lidar appears there first.
3. Anywhere else, missing high-zoom tiles are upsampled from the nearest coarser tile.

The server marks which source served each tile in the `X-Terrain-Source` response header.

## Tests

```bash
python -m pytest fly/tests
```
