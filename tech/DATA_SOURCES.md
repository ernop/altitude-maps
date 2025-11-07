# Data Sources Reference

## Overview

The altitude-maps project now supports multiple elevation data sources with automatic source selection. When downloading data, the system tries sources in priority order until successful.

---

## Available Data Sources

### 10m Resolution

#### USGS 3DEP
- **Resolution**: ~10m (1/3 arc-second)
- **Coverage**: United States (including Alaska)
- **Method**: LiDAR and IfSAR
- **Quality**: Highest quality elevation data
- **Access**: Free via USGS National Map API (no authentication)
- **Source ID**: `usgs_3dep`

#### Copernicus GLO-10
- **Resolution**: 10m
- **Coverage**: Europe only (38°N to 60°N, 13°W to 32°E)
- **Method**: TanDEM-X radar
- **Access**: Free via AWS S3 (no authentication)
- **Source ID**: `copernicus_s3_10m`

### 30m Resolution

#### SRTM 30m (OpenTopography)
- **Resolution**: 30m (1 arc-second)
- **Coverage**: 60°N to 56°S (SRTM coverage area)
- **Method**: Shuttle radar mission (2000)
- **Access**: Via OpenTopography API (requires free API key)
- **Source ID**: `opentopo_srtm_30m`

#### Copernicus 30m (OpenTopography)
- **Resolution**: 30m
- **Coverage**: Global
- **Method**: TanDEM-X radar (2011-2015)
- **Access**: Via OpenTopography API (requires free API key)
- **Source ID**: `opentopo_copernicus_30m`

#### Copernicus GLO-30 (S3)
- **Resolution**: 30m
- **Coverage**: Global
- **Method**: TanDEM-X radar (2011-2015)
- **Access**: Direct AWS S3 download (no authentication)
- **Source ID**: `copernicus_s3_30m`
- **Note**: Same data as OpenTopography Copernicus, different access method

#### ALOS AW3D30
- **Resolution**: 30m
- **Coverage**: 82°N to 82°S
- **Method**: Japanese ALOS satellite optical imagery
- **Quality**: Often superior to SRTM in mountainous terrain
- **Access**: Via OpenTopography API (requires free API key)
- **Source ID**: `aw3d30`

### 90m Resolution

#### SRTM 90m (OpenTopography)
- **Resolution**: 90m (3 arc-second)
- **Coverage**: 60°N to 56°S
- **Access**: Via OpenTopography API (requires free API key)
- **Source ID**: `opentopo_srtm_90m`

#### Copernicus 90m (OpenTopography)
- **Resolution**: 90m
- **Coverage**: Global
- **Access**: Via OpenTopography API (requires free API key)
- **Source ID**: `opentopo_copernicus_90m`

#### Copernicus GLO-90 (S3)
- **Resolution**: 90m
- **Coverage**: Global
- **Access**: Direct AWS S3 download (no authentication)
- **Source ID**: `copernicus_s3_90m`

### Coarse Resolution (250m-1km)

#### GMTED2010
- **Resolutions**: 250m, 500m, 1km
- **Coverage**: Global
- **Status**: Placeholder (not yet implemented)
- **Source IDs**: `gmted2010_250m`, `gmted2010_500m`, `gmted2010_1km`

#### GLOBE
- **Resolution**: 1km
- **Coverage**: Global
- **Status**: Placeholder (not yet implemented)
- **Source ID**: `globe_1km`

---

## Source Selection

### How Sources are Selected

The system automatically selects sources based on:

1. **Resolution requirement** - Matches required resolution exactly (no upsampling)
2. **Geographic coverage** - Source must cover the requested region
3. **User-configured priority** - If configured in `settings.json`
4. **Default registry order** - Default order defined in `src/downloaders/source_registry.py`

### Default Priority Order

**10m regions:**
1. USGS 3DEP (US only)
2. Copernicus GLO-10 (Europe only)

**30m regions:**
1. OpenTopography SRTM/Copernicus
2. Copernicus GLO-30 S3 (direct download)
3. ALOS AW3D30

**90m regions:**
1. OpenTopography SRTM/Copernicus
2. Copernicus GLO-90 S3 (direct download)

### Configuring Source Priority

You can override the default order by adding to `settings.json`:

```json
{
  "opentopography": {
    "api_key": "your_key_here"
  },
  "data_sources": {
    "priority": [
      "copernicus_s3_30m",
      "opentopo_copernicus_30m",
      "opentopo_srtm_30m",
      "aw3d30",
      "copernicus_s3_90m",
      "opentopo_copernicus_90m",
      "opentopo_srtm_90m",
      "usgs_3dep",
      "copernicus_s3_10m"
    ]
  }
}
```

**Notes:**
- Sources not in your priority list are tried after your preferred sources
- Invalid source IDs are ignored
- Sources are still filtered by resolution and coverage requirements

---

## Download Behavior

### Trying Sources in Order

When downloading tiles:

1. System gets list of matching sources (resolution + coverage)
2. Reorders based on user priority if configured
3. Tries each source in order
4. Stops on first successful download
5. Logs which source succeeded

**Example output:**
```
[Tile 3/15] N40_W080_30m.tif
  → Trying SRTM 30m (OpenTopography)...✗
  → Trying Copernicus GLO-30 (S3)...✓
```

### When All Sources Fail

If all sources fail for a tile:
- Warning is printed
- Tile is skipped
- Download continues for remaining tiles
- Merge step uses whatever tiles succeeded

**Common reasons for failure:**
- Tile is over ocean (no data available)
- All OpenTopography sources rate-limited
- Network errors
- Geographic area not covered by any source

---

## API Keys and Authentication

### Required API Keys

**OpenTopography API Key** - Used for:
- SRTM 30m/90m
- Copernicus 30m/90m (via OpenTopography)
- ALOS AW3D30

Get a free key at: https://portal.opentopography.org/

Add to `settings.json`:
```json
{
  "opentopography": {
    "api_key": "YOUR_KEY_HERE"
  }
}
```

### No Authentication Required

These sources work without API keys:
- USGS 3DEP
- Copernicus S3 (all resolutions)
- GMTED2010 (when implemented)
- GLOBE (when implemented)

---

## Data Storage

### Tile Storage

Tiles are stored in source-specific directories:

```
data/raw/
  usa_3dep/tiles/          # USGS 3DEP 10m
  copernicus_s3_10m/tiles/ # Copernicus GLO-10
  srtm_30m/tiles/          # SRTM/Copernicus 30m (OpenTopography)
  copernicus_s3_30m/tiles/ # Copernicus GLO-30 (S3)
  aw3d30/tiles/            # ALOS AW3D30
  srtm_90m/tiles/          # SRTM/Copernicus 90m (OpenTopography)
  copernicus_s3_90m/tiles/ # Copernicus GLO-90 (S3)
```

**Tile naming convention:**
```
{NS}{lat}_{EW}{lon}_{resolution}.tif

Examples:
  N40_W080_30m.tif    # 30m tile at 40°N, 80°W
  S05_E120_90m.tif    # 90m tile at 5°S, 120°E
```

**Key principle**: Tiles use resolution-based names, not source-based names. This allows tiles from different sources (with same resolution) to be used interchangeably.

### Merged Storage

Merged regional files stored by source:

```
data/merged/
  srtm_30m/                # Merged 30m files
  srtm_90m/                # Merged 90m files
  usa_3dep/                # Merged 10m US files
  aw3d30/                  # Merged AW3D30 files
```

---

## Implementation Details

### Source Registry

All sources defined in: `src/downloaders/source_registry.py`

Each source declares:
- Unique ID
- Human-readable name
- Resolution in meters
- Geographic coverage (lat/lon bounds)
- Storage directories
- Authentication requirements

### Source Coordinator

Located in: `src/downloaders/source_coordinator.py`

Responsibilities:
- Get ordered list of sources for requirements
- Try each source in order
- Route to appropriate downloader
- Return success/failure status
- Track which sources succeeded

### Individual Downloaders

Each source has its own downloader module:
- `src/downloaders/usgs_3dep_10m.py` - USGS 3DEP
- `src/downloaders/copernicus_s3.py` - Copernicus S3 buckets
- `src/downloaders/opentopography.py` - OpenTopography API
- `src/downloaders/aw3d30.py` - ALOS AW3D30
- `src/downloaders/srtm_90m.py` - SRTM 90m (legacy, uses OpenTopography)
- `src/downloaders/gmted2010.py` - GMTED2010 (placeholder)
- `src/downloaders/globe.py` - GLOBE (placeholder)

---

## Quality Considerations

### Source Quality Rankings (30m)

1. **USGS 3DEP** (US only) - Highest quality (LiDAR-based)
2. **Copernicus GLO-30** - Very high quality (2020s data)
3. **SRTM** - Good quality (2000 data, well-tested)
4. **ALOS AW3D30** - High quality (often better in mountains)

### Mixing Sources

**Same resolution, different sources**: Generally fine
- Example: Some tiles from OpenTopography SRTM, others from Copernicus S3
- May have minor elevation differences at tile boundaries
- Quality usually comparable

**Different resolutions**: Never mixed
- System only downloads exact resolution required
- No upsampling or downsampling

---

## Troubleshooting

### "No sources available"

**Causes:**
- No sources provide required resolution
- No sources cover requested geographic area
- All sources filtered out by requirements

**Solutions:**
- Check resolution requirement makes sense
- Verify region bounds are correct
- Check source registry covers your region

### "All sources failed"

**Causes:**
- All OpenTopography sources rate-limited
- Network issues
- Region over ocean (no elevation data)
- Corrupted downloads

**Solutions:**
- Wait for rate limit to clear (`python check_rate_limit.py`)
- Check internet connection
- Verify region has land (elevation data exists)
- Try again later

### OpenTopography Rate Limits

**Symptoms:**
- HTTP 401 errors
- "Rate limit exceeded" messages
- Automatic backoff delays

**Solutions:**
1. Wait for rate limit to clear (check `python check_rate_limit.py`)
2. Copernicus S3 sources will be tried automatically (no rate limits)
3. Space out large downloads over multiple days

---

## Future Enhancements

### Planned

- Implement GMTED2010 downloader (250m/500m/1km)
- Implement GLOBE downloader (1km)
- Add NASADEM (improved SRTM processing)
- Add FABDEM (bare-earth corrected Copernicus)

### Possible

- Parallel S3 downloads (faster for large regions)
- Resume failed downloads
- Automatic quality assessment (detect and skip corrupted tiles)
- Tile checksums for verification

---

## Adding New Sources

To add a new data source:

1. **Add to source registry** (`src/downloaders/source_registry.py`):
   ```python
   SourceCapability(
       source_id='my_new_source',
       name='My New Source',
       resolution_m=30,
       coverage_lat=(-90.0, 90.0),
       coverage_lon=None,  # Global
       tile_dir='my_new_source',
       merged_dir='my_new_source',
       requires_auth=False,
       auth_key_name=None,
       notes='Description here'
   )
   ```

2. **Create downloader module** (`src/downloaders/my_new_source.py`):
   ```python
   def download_my_new_source_tile(
       tile_bounds: Tuple[float, float, float, float],
       output_path: Path
   ) -> bool:
       # Download logic here
       return success
   ```

3. **Add routing** in `src/downloaders/source_coordinator.py`:
   ```python
   elif source.source_id == 'my_new_source':
       from src.downloaders.my_new_source import download_my_new_source_tile
       return download_my_new_source_tile(tile_bounds, source_output_path)
   ```

4. **Test** with a small region

5. **Document** in this file

---

## See Also

- `tech/DATA_PIPELINE.md` - Complete data processing pipeline
- `tech/DOWNLOAD_GUIDE.md` - Data acquisition workflows
- `.cursorrules` - Data source expansion patterns
- `src/downloaders/source_registry.py` - Source capability definitions

