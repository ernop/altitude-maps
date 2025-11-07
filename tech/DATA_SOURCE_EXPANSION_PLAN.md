# Data Source Expansion Plan

## Overview

Expand elevation data sources with robust fallback mechanisms to ensure data availability even when primary sources fail. All new sources integrate seamlessly with existing tile-based architecture.

---

## Current Architecture (Baseline)

### Existing Sources
1. **USGS 3DEP** (10m) - US only, via USGS National Map API
2. **SRTM GL1** (30m) - Via OpenTopography API (60°N to 56°S)
3. **SRTM GL3** (90m) - Via OpenTopography API (60°N to 56°S)
4. **Copernicus DEM** (30m/90m) - Via OpenTopography API (global)

### Key Architectural Principles
- **Unified 1-degree tile system** - All resolutions use 1×1 degree tiles
- **Tile storage** - `data/raw/{source}/tiles/` (content-based reuse)
- **Merged storage** - `data/merged/{source}/` (region-specific merged files)
- **Resolution detection** - From source name (30m, 90m, 10m)
- **No duplication** - Same tile reused across adjacent regions
- **Generic processing** - Pipeline works with any GeoTIFF source

---

## New Data Sources to Add

### High Priority (Immediate Fallbacks)

#### 1. Copernicus DEM via AWS S3 (30m/90m)
- **Purpose**: Direct fallback when OpenTopography fails or rate-limited
- **Access**: Public AWS S3 buckets (no authentication required)
- **Buckets**:
  - GLO-30: `s3://copernicus-dem-30m/` or `https://copernicus-dem-30m.s3.amazonaws.com/`
  - GLO-90: `s3://copernicus-dem-90m/` or `https://copernicus-dem-90m.s3.amazonaws.com/`
- **Coverage**: Global (all land surfaces)
- **Format**: Cloud Optimized GeoTIFF (COG) - 1×1 degree tiles
- **Naming**: `Copernicus_DSM_COG_{resolution}_{lat}_{lon}_DEM.tif`
  - Example: `Copernicus_DSM_COG_30_N40_00_W080_00_DEM.tif`
- **Storage**: `data/raw/copernicus_s3_30m/tiles/` and `data/raw/copernicus_s3_90m/tiles/`
- **Priority**: Fallback after OpenTopography fails (same quality, different source)

#### 2. Copernicus DEM GLO-10 via AWS S3 (10m)
- **Purpose**: High-resolution European data
- **Access**: `s3://copernicus-dem-10m/` (Europe only, 60°N to 38°N, 13°W to 32°E)
- **Coverage**: European Economic Area only
- **Format**: Cloud Optimized GeoTIFF (COG) - 1×1 degree tiles
- **Storage**: `data/raw/copernicus_s3_10m/tiles/`
- **Priority**: Alternative to USGS 3DEP for European regions (if user wants global consistency)

#### 3. ALOS World 3D - 30m (AW3D30)
- **Purpose**: Alternative 30m source (high quality, different sensor)
- **Access**: Via OpenTopography API (already supported as global dataset)
- **Coverage**: Global (82°N to 82°S)
- **Quality**: Often better than SRTM, especially in mountainous areas
- **Storage**: `data/raw/aw3d30/tiles/`
- **Priority**: Fallback after Copernicus S3 fails

### Medium Priority (Coarse Resolution Fallbacks)

#### 4. GMTED2010 (250m/500m/1km)
- **Purpose**: Very coarse fallback for extremely large regions or when all else fails
- **Access**: USGS EarthExplorer or direct download (public domain)
- **Resolutions**:
  - 7.5 arc-second (~250m)
  - 15 arc-second (~500m)
  - 30 arc-second (~1km)
- **Coverage**: Global
- **Format**: GeoTIFF tiles
- **Storage**: `data/raw/gmted2010_250m/tiles/`, `data/raw/gmted2010_500m/tiles/`, `data/raw/gmted2010_1km/tiles/`
- **Priority**: Last resort fallback (very coarse)

#### 5. GLOBE (1km)
- **Purpose**: Simple global fallback (small file sizes)
- **Access**: NOAA NCEI (public domain, complete global dataset ~2GB)
- **Resolution**: 30 arc-second (~1km)
- **Coverage**: Global
- **Format**: Binary or GeoTIFF
- **Storage**: `data/raw/globe_1km/tiles/`
- **Priority**: Last resort (similar to GMTED2010)

---

## Source Priority & Fallback Strategy

### Resolution-Based Priority Chains

#### For 10m Resolution (US regions):
```
1. USGS 3DEP (primary) - US only
2. Copernicus GLO-10 S3 (fallback) - Europe only
3. Upsample from 30m (last resort) - with quality warning
```

#### For 30m Resolution (Global):
```
1. OpenTopography SRTM/Copernicus (primary) - fastest, API-based
2. Copernicus GLO-30 S3 (fallback #1) - direct download, no rate limits
3. AW3D30 via OpenTopography (fallback #2) - different sensor, often higher quality
4. GMTED2010 250m (fallback #3) - coarse but available
5. GLOBE 1km (last resort) - very coarse
```

#### For 90m Resolution (Global):
```
1. OpenTopography SRTM/Copernicus (primary) - fastest, API-based
2. Copernicus GLO-90 S3 (fallback #1) - direct download, no rate limits
3. GMTED2010 500m (fallback #2) - coarse but available
4. GLOBE 1km (last resort) - very coarse
```

### Fallback Trigger Conditions

**When to try next source:**
1. HTTP 401/403 (rate limit or quota exceeded)
2. HTTP 5xx (server error)
3. Timeout after 60 seconds
4. Empty/corrupted file (size < 1KB or invalid GeoTIFF)
5. Tile missing from dataset (404)

**When to stop trying:**
1. All sources exhausted
2. User cancellation
3. File system errors (disk full, permissions)

---

## Implementation Architecture

### 1. New Downloader Modules

Create individual downloader modules following existing patterns:

```
src/downloaders/
  - copernicus_s3.py        # GLO-10/30/90 via S3
  - aw3d30.py               # AW3D30 via OpenTopography
  - gmted2010.py            # GMTED2010 via USGS
  - globe.py                # GLOBE via NOAA
  - fallback_manager.py     # NEW: Coordinates fallback logic
```

### 2. Fallback Manager (New Component)

**Purpose**: Single source of truth for fallback logic

**Location**: `src/downloaders/fallback_manager.py`

**Key Functions**:
```python
def get_source_priority(resolution: int, latitude: float, region_type: str) -> List[str]:
    """Return ordered list of sources to try for given requirements."""
    
def download_tile_with_fallback(
    tile_bounds: Tuple[float, float, float, float],
    resolution: int,
    output_path: Path,
    region_type: str = 'global'
) -> bool:
    """Try downloading tile with automatic fallback through source priority list."""
    
def download_chunk_with_fallback(
    chunk_bounds: Tuple[float, float, float, float],
    resolution: int,
    output_path: Path,
    region_type: str = 'global'
) -> bool:
    """Try downloading chunk with automatic fallback."""
```

### 3. Modified Components

**`src/tile_manager.py`**:
- Import `fallback_manager`
- When download fails, call `download_tile_with_fallback()`
- Track which source succeeded for logging

**`src/downloaders/orchestrator.py`**:
- Update `download_elevation_data()` to use fallback manager
- Keep routing logic but add fallback capability
- Log which source was ultimately used

**`src/download_config.py`**:
- Add chunk sizes for new resolutions (250m, 500m, 1km)
- Add typical file sizes for progress estimation

### 4. Storage Organization

**Principle**: Source-specific tile directories prevent conflicts

```
data/raw/
  usa_3dep/tiles/          # USGS 3DEP 10m (US)
  copernicus_s3_10m/tiles/ # Copernicus GLO-10 (Europe)
  srtm_30m/tiles/          # SRTM/Copernicus 30m via OpenTopography
  copernicus_s3_30m/tiles/ # Copernicus GLO-30 via S3
  aw3d30/tiles/            # ALOS AW3D30
  srtm_90m/tiles/          # SRTM/Copernicus 90m via OpenTopography
  copernicus_s3_90m/tiles/ # Copernicus GLO-90 via S3
  gmted2010_250m/tiles/    # GMTED2010 250m
  gmted2010_500m/tiles/    # GMTED2010 500m
  gmted2010_1km/tiles/     # GMTED2010 1km
  globe_1km/tiles/         # GLOBE 1km

data/merged/
  usa_3dep/                # Merged 10m files
  srtm_30m/                # Merged 30m files (OpenTopography or S3)
  aw3d30/                  # Merged AW3D30 files
  srtm_90m/                # Merged 90m files (OpenTopography or S3)
  gmted2010_250m/          # Merged GMTED files
  gmted2010_500m/
  gmted2010_1km/
  globe_1km/               # Merged GLOBE files
```

**Note**: Copernicus S3 tiles stored separately but merged into same `srtm_30m/` or `srtm_90m/` directories (same resolution, interchangeable).

### 5. Tile Naming Convention

**Maintain existing convention**:
```
{NS}{lat}_{EW}{lon}_{resolution}.tif

Examples:
  N35_W090_30m.tif    # 30m tile at 35°N, 90°W
  S05_E120_90m.tif    # 90m tile at 5°S, 120°E
  N40_W080_10m.tif    # 10m tile at 40°N, 80°W
  N45_E010_250m.tif   # 250m tile at 45°N, 10°E
```

**Source agnostic**: Same filename regardless of source (Copernicus via OpenTopography vs S3)

---

## Copernicus S3 Implementation Details

### Tile URL Construction

**GLO-30 Pattern**:
```
https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_30_{lat_band}_{lon_band}_DEM.tif

lat_band: N00_00 to N89_00 or S01_00 to S90_00 (integer degrees, zero-padded)
lon_band: E000_00 to E179_00 or W001_00 to W180_00 (integer degrees, zero-padded)

Examples:
  N40_00_W080_00 → https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_30_N40_00_W080_00_DEM.tif
  S05_00_E120_00 → https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_30_S05_00_E120_00_DEM.tif
```

**GLO-90 Pattern**:
```
https://copernicus-dem-90m.s3.amazonaws.com/Copernicus_DSM_COG_90_{lat_band}_{lon_band}_DEM.tif
```

**GLO-10 Pattern** (Europe only):
```
https://copernicus-dem-10m.s3.amazonaws.com/Copernicus_DSM_COG_10_{lat_band}_{lon_band}_DEM.tif
```

### Download Strategy

1. **Direct HTTP GET** - No authentication required
2. **Cloud Optimized** - Can read subsets without downloading full tile
3. **Error handling**:
   - 404 = Tile doesn't exist (ocean, no data) - expected, skip
   - 403 = Access denied - unexpected, fail
   - 5xx = Server error - retry with exponential backoff

### Conversion to Standard Naming

**Upon successful download**:
1. Download to temp file: `Copernicus_DSM_COG_30_N40_00_W080_00_DEM.tif`
2. Rename to standard format: `N40_W080_30m.tif`
3. Move to `data/raw/copernicus_s3_30m/tiles/`
4. Verify GeoTIFF is valid
5. Delete temp file if validation fails

---

## Error Handling & Logging

### Per-Tile Logging
```
[Tile 3/15] N40_W080_30m.tif
  → Trying: OpenTopography SRTM...FAILED (401 rate limit)
  → Trying: Copernicus S3 GLO-30...SUCCESS (23.4 MB, 3.2s)
```

### Fallback Summary
```
Download complete: 15/15 tiles
  - OpenTopography: 8 tiles
  - Copernicus S3: 7 tiles (fallback due to rate limit)
```

### Error Conditions
- **All sources failed**: Clear error message with next steps
- **Mixed sources**: Warning that tiles from different sources were used (usually fine)
- **Coarse fallback**: Warning if using 250m/1km data for 30m request

---

## Quality Considerations

### Source Quality Ranking (30m)
1. **USGS 3DEP** (US only) - Highest quality (LiDAR)
2. **Copernicus GLO-30** - Very high quality (2020s data)
3. **SRTM GL1** - Good quality (2000 data, well-tested)
4. **AW3D30** - High quality (different sensor, sometimes better)
5. **GMTED2010** - Coarse, use only when necessary

### Source Compatibility
- **Mixing OpenTopography SRTM + Copernicus S3**: OK - same source data, different distribution
- **Mixing SRTM + AW3D30**: OK - both 30m, edges may have slight elevation differences
- **Mixing 30m + 250m**: NOT RECOMMENDED - quality warning required

---

## Configuration Changes

### `src/download_config.py` Additions

```python
# Resolution mapping (meters → arc-seconds)
RESOLUTION_ARC_SECONDS = {
    10: 1/3,    # ~10m
    30: 1,      # ~30m
    90: 3,      # ~90m
    250: 7.5,   # ~250m
    500: 15,    # ~500m
    1000: 30,   # ~1km
}

# Chunk sizes for new resolutions
CHUNK_SIZE_BY_RESOLUTION.update({
    250: 4,   # 250m data - fetch 4x4 degree chunks
    500: 8,   # 500m data - fetch 8x8 degree chunks
    1000: 10, # 1km data - fetch 10x10 degree chunks
})

# Typical tile sizes
TYPICAL_TILE_SIZE_MB.update({
    250: 3,   # ~3MB per 1-degree tile
    500: 1,   # ~1MB per 1-degree tile
    1000: 0.5 # ~500KB per 1-degree tile
})

# Source identifiers (for routing and storage)
SOURCE_CODES = {
    'USA_3DEP': 'usa_3dep',
    'SRTMGL1': 'srtm_30m',
    'SRTMGL3': 'srtm_90m',
    'COP30': 'srtm_30m',      # Copernicus via OpenTopography
    'COP90': 'srtm_90m',      # Copernicus via OpenTopography
    'COP30_S3': 'copernicus_s3_30m',
    'COP90_S3': 'copernicus_s3_90m',
    'COP10_S3': 'copernicus_s3_10m',
    'AW3D30': 'aw3d30',
    'GMTED250': 'gmted2010_250m',
    'GMTED500': 'gmted2010_500m',
    'GMTED1K': 'gmted2010_1km',
    'GLOBE': 'globe_1km',
}
```

---

## Testing Strategy

### Unit Tests
1. Test URL construction for Copernicus S3 tiles (all quadrants)
2. Test fallback priority logic (mock downloads)
3. Test error handling (404, 401, timeout)
4. Test source code mapping

### Integration Tests
1. Download single Copernicus S3 tile
2. Download single AW3D30 tile via OpenTopography
3. Test fallback when OpenTopography rate-limited (mock)
4. Verify merged output identical regardless of source

### Manual Tests
1. Download small region with Copernicus S3 only
2. Force fallback by disabling OpenTopography API key
3. Mix sources across tile boundary
4. Download European region with GLO-10

---

## Documentation Updates

### New Files
1. **`tech/DATA_SOURCES.md`** - Complete reference of all data sources
2. **`tech/FALLBACK_STRATEGY.md`** - Detailed fallback logic documentation
3. **`tech/COPERNICUS_S3_GUIDE.md`** - Copernicus S3 bucket access guide

### Updated Files
1. **`.cursorrules`** - Add data source expansion patterns
2. **`tech/DATA_PIPELINE.md`** - Update with new sources
3. **`README.md`** - Mention expanded data source support
4. **`tech/USER_GUIDE.md`** - Document fallback behavior for users

---

## Migration Plan

### Phase 1: Core Infrastructure (Priority 1)
1. Create `fallback_manager.py`
2. Create `copernicus_s3.py` downloader
3. Update `tile_manager.py` to use fallback
4. Add Copernicus S3 as fallback for 30m/90m
5. Test with rate-limited OpenTopography

### Phase 2: Additional Sources (Priority 2)
1. Create `aw3d30.py` downloader
2. Add AW3D30 to fallback chain
3. Create `copernicus_s3.py` support for GLO-10 (Europe)

### Phase 3: Coarse Fallbacks (Priority 3)
1. Create `gmted2010.py` downloader
2. Create `globe.py` downloader
3. Add coarse sources to fallback chain
4. Implement quality warnings

### Phase 4: Documentation & Testing (Final)
1. Complete all documentation
2. Integration tests
3. User acceptance testing

---

## Success Criteria

1. **Resilience**: Data download succeeds even when primary source fails
2. **Transparency**: User knows which source was used
3. **Quality**: No silent quality degradation (warnings when using coarse fallbacks)
4. **Compatibility**: Existing pipeline works unchanged
5. **Performance**: Fallback adds minimal overhead to success case
6. **Maintainability**: Single obvious place to modify fallback logic

---

## Open Questions for Review

1. **Should we prefer Copernicus S3 over OpenTopography by default?**
   - Pro: No rate limits, direct access
   - Con: OpenTopography may have newer versions/corrections

2. **Should we support automatic upsampling from coarse to fine?**
   - Example: User wants 30m but only 250m available
   - Pro: Always returns something
   - Con: May mislead user about quality

3. **Should we cache source metadata in merged files?**
   - Store which tiles came from which sources
   - Useful for debugging quality issues
   - Adds complexity

4. **Should we support user-specified source preferences?**
   - Command line: `--prefer-source copernicus_s3`
   - Pro: Power users can optimize
   - Con: More complexity

5. **Should we implement parallel downloads for S3?**
   - S3 has no rate limits
   - Could download multiple tiles simultaneously
   - Faster for large regions

---

## Next Steps

1. **Review this plan** - Discuss open questions and priorities
2. **Create requirements document** - Formalize specifications
3. **Get approval** - Confirm implementation approach
4. **Implement Phase 1** - Core infrastructure and Copernicus S3
5. **Test and iterate** - Validate fallback behavior
6. **Continue with Phases 2-4** - Expand sources and document


