# Border System - Current State

Status: Country-level borders fully implemented and working. State-level not implemented.

## What Works

Country-level boundary system for 177 countries worldwide. Can mask elevation data to country shapes and draw country borders in 3D viewer.

Data source: Natural Earth admin_0 (countries)
URL: https://naciscdn.org/naturalearth/{resolution}/cultural/ne_{resolution}_admin_0_countries.zip
Resolutions: 10m, 50m, 110m
Cache: data/.cache/borders/ne_{resolution}_countries.pkl

## Architecture

BorderManager class in src/borders.py handles all border operations:
- load_borders(resolution) - Downloads/caches country shapefiles
- get_country(name, resolution) - Queries specific country
- get_countries_in_bbox(bbox, resolution) - Finds countries in region
- mask_raster_to_country(raster, country) - Clips elevation to country
- get_border_coordinates(country) - Extracts boundary points for rendering

## Data Processing Flow

1. Load elevation GeoTIFF
2. Call prepare_visualization_data() with mask_country="United States of America"
3. BorderManager loads country geometry from Natural Earth
4. rasterio.mask clips raster to country boundary (pixels outside = NaN)
5. Result cached in data/.cache/ for fast reuse
6. Export elevation JSON with null values outside boundary
7. Export border coordinates to separate JSON file
8. Viewer loads both JSONs and renders terrain + border lines

## File Locations

Backend:
- src/borders.py - BorderManager class
- src/data_processing.py - prepare_visualization_data() with mask_country param
- border_utils.py - CLI tools for listing/searching countries
- export_borders_for_viewer.py - Exports border coordinates to JSON

Frontend:
- interactive_viewer_advanced.html - Loads and renders borders
- loadBorderData() function (line 806)
- recreateBorders() function (line 2258)
- Border rendering: yellow lines at 100m height above ground

## Data Formats

Country border JSON (generated/regions/{region}_borders.json):
{
  "bounds": {"left": -125, "bottom": 25, "right": -65, "top": 50},
  "resolution": "110m",
  "countries": [{
    "name": "United States of America",
    "segments": [{"lon": [...], "lat": [...]}]
  }]
}

Elevation data has nulls where country boundary excludes data.

## CLI Usage

List countries: python border_utils.py --list
Search: python border_utils.py --list --search "united"
Country info: python border_utils.py --info "United States of America"
Find in region: python border_utils.py --bbox "-125,25,-65,50"
Test borders: python border_utils.py --test data/usa.tif

Export with borders: python export_for_web_viewer.py data/usa.tif --export-borders --mask-country "United States of America"

## What Doesn't Work

State/province level boundaries (admin_1) not implemented. When downloading US states, system downloads rectangular bounding box but doesn't clip to actual state shape. Result: Tennessee displays as rectangle instead of irregular state shape.

Files show this limitation:
- downloaders/usa_3dep.py line 394: skip_clip=True
- downloaders/usa_3dep.py line 384: boundary_name only uses country, not state
- No state-level masking in BorderManager
- No state border export capability
- Viewer only handles country borders, not state borders

Current state downloads produce rectangular data for all 48 contiguous US states. Only Colorado and Wyoming actually are rectangular; all others display incorrectly.

## Performance

First load: 2-10 seconds (downloads borders, clips data)
Cached: < 1 second (reuses clipped data)
Border rendering: ~10ms for typical country
Cache location: data/.cache/borders/ and data/.cache/

## Natural Earth Data Structure

Countries (admin_0):
- ADMIN: Country name
- ISO_A3: 3-letter code
- geometry: Polygon/MultiPolygon
- CONTINENT, REGION_UN: Geographic classification

Coverage: 177 countries worldwide

