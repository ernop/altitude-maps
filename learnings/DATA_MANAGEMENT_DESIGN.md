# Data Management Design & Refactoring Plan

**Purpose**: Comprehensive plan for restructuring internal data storage with careful versioning, naming, and cache management.

**Date**: October 23, 2025
**Status**: Design Phase (not yet implemented)

---

## Table of Contents

1. [Current Problems](#current-problems)
2. [Design Principles](#design-principles)
3. [Proposed Folder Structure](#proposed-folder-structure)
4. [Naming Conventions](#naming-conventions)
5. [Versioning Strategy](#versioning-strategy)
6. [Cache Invalidation Rules](#cache-invalidation-rules)
7. [Implementation Plan](#implementation-plan)
8. [Migration Path](#migration-path)

---

## Current Problems

### Existing Structure Issues:
```
data/
 regions/# Mix of different sources, resolutions
 california.tif# Could be SRTM or USGS - unclear!
 japan.tif
 usa_elevation/
 nationwide_usa_elevation.tif
 .cache/# Pickled border masks - no version info

generated/
 regions/# JSON outputs - no source tracking
 california.json
```

**Problems**:
1. Can't tell data source from filename
2. Can't tell resolution or quality
3. Mixing raw downloads with processed data
4. No version tracking for cache compatibility
5. No distinction between bounding-box and clipped data
6. If we re-download from better source, old cached data may be incompatible

---

## Design Principles

### Core Principles:
1.**Source Transparency**: Filename shows what source data came from
2.**Resolution Clarity**: Resolution is always visible
3.**Processing Stage**: Clear separation of raw -> clipped -> processed -> exported
4.**Version Control**: Every cached derivative has version metadata
5.**Backwards Compatible**: Old code continues to work during migration
6.**Automatic Cleanup**: Version mismatches trigger helpful errors

### Key Insight:
**Data flows through stages**: Raw Download -> Clipped/Masked -> Downsampled -> Exported

Each stage should be:
-**Separate directory** (clear boundaries)
-**Version tracked** (compatibility checks)
-**Source labeled** (traceability)
-**Resolution labeled** (quality awareness)

---

## Proposed Folder Structure

```
data/
 raw/# Stage 1: Raw downloads (never modify!)
 usa_3dep/# Source-specific folders
 california_bbox_10m.tif# Bounding box, 10m resolution
 california_bbox_10m.json# Metadata: bounds, download date, version
 texas_bbox_10m.tif
 nationwide_10m.tif
 srtm_30m/# Global SRTM data
 japan_bbox_30m.tif
 germany_bbox_30m.tif
 japan_bbox_30m.json
 copernicus_30m/# Copernicus DEM
 iceland_bbox_30m.tif
 australia_geoscience/# Nation-specific agencies
 victoria_bbox_5m.tif
 japan_gsi/
 shikoku_bbox_5m.tif

 clipped/# Stage 2: Clipped to boundaries
 usa_3dep/
 california_state_10m_v1.tif# Clipped to state boundary
 california_state_10m_v1.json# Metadata: source, clip boundary, version
 texas_state_10m_v1.tif
 srtm_30m/
 japan_country_30m_v1.tif# Clipped to country
 germany_country_30m_v1.tif
 [mirrors raw/ structure]

 processed/# Stage 3: Downsampled/ready for export
 usa_3dep/
 california_state_10m_800px_v2.tif# Downsampled to 800x800
 california_state_10m_800px_v2.json# Processing metadata
 california_state_10m_1024px_v2.tif# Multiple resolutions
 srtm_30m/
 japan_country_30m_800px_v2.tif

 borders/# Border shapefiles (existing, unchanged)
 [Natural Earth data]

 metadata/# Global metadata
 data_versions.json# Version registry for all cached data
 source_registry.json# What sources are available per region
 download_log.json# History of all downloads
```

```
generated/# Stage 4: Exported for viewer
 regions/
 california_usa3dep_10m_v2.json# JSON for web viewer
 california_usa3dep_10m_v2_meta.json# Export metadata
 japan_srtm_30m_v2.json
 regions_manifest_v2.json# Index of all regions

 archive/# Old versions (auto-moved on version bump)
 v1/
 [old JSON files]
```

---

## Naming Conventions

### Raw Downloads:
**Format**: `{region}_{bbox|country}_{resolution}.tif`

**Examples**:
- `california_bbox_10m.tif` - Bounding box download, 10m resolution
- `japan_bbox_30m.tif`
- `nationwide_usa_bbox_10m.tif`

**Accompanying metadata** (auto-generated):
- `california_bbox_10m.json`:
 ```json
 {
 "version": "raw_v1",
 "source": "usgs_3dep",
 "region_id": "california",
 "download_date": "2025-10-23T14:30:00Z",
 "bounds": [-124.48, 32.53, -114.13, 42.01],
 "resolution_meters": 10,
 "crs": "EPSG:4326",
 "download_url": "https://...",
 "file_hash": "sha256:..."
 }
 ```

### Clipped Data:
**Format**: `{region}_{boundary_type}_{resolution}_v{version}.tif`

**Examples**:
- `california_state_10m_v1.tif` - Clipped to state boundary, version 1
- `japan_country_30m_v1.tif` - Clipped to country boundary
- `switzerland_country_30m_v1.tif`

**Metadata**:
- `california_state_10m_v1.json`:
 ```json
 {
 "version": "clipped_v1",
 "source_file": "data/raw/usa_3dep/california_bbox_10m.tif",
 "source_file_hash": "sha256:...",
 "clip_boundary": "United States of America/California",
 "clip_source": "natural_earth_10m",
 "created_date": "2025-10-23T14:35:00Z",
 "resolution_meters": 10,
 "elevation_range": [0, 4418],
 "file_hash": "sha256:..."
 }
 ```

### Processed/Downsampled:
**Format**: `{region}_{boundary_type}_{resolution}_{pixels}_v{version}.tif`

**Examples**:
- `california_state_10m_800px_v2.tif` - 800x800 pixels, version 2
- `california_state_10m_1024px_v2.tif` - 1024x1024 pixels (high-res)
- `japan_country_30m_800px_v2.tif`

### Exported JSON:
**Format**: `{region}_{source}_{resolution}_v{version}.json`

**Examples**:
- `california_usa3dep_10m_v2.json`
- `japan_srtm_30m_v2.json`
- `germany_copernicus_30m_v2.json`

**Benefits**:
- Clear what source data came from
- Resolution visible at a glance
- Version tracking for compatibility
- Can have multiple versions/sources for same region

---

## Versioning Strategy

### Version Schema:

**Stage Versions** (independent):
- `raw_v1` - Never changes (raw downloads are immutable)
- `clipped_v1` - Current clipping algorithm version
- `processed_v2` - Current processing/downsampling algorithm
- `export_v2` - Current JSON export format

**Format Versions**:
Each version increments when:
- Algorithm changes (different bucketing, filtering, etc.)
- Data format changes (JSON structure, coordinate system)
- Dependency updates that affect output (rasterio, numpy, etc.)

### Version Compatibility Matrix:

Stored in `data/metadata/data_versions.json`:
```json
{
 "current_versions": {
 "clipped": "v1",
 "processed": "v2",
 "export": "v2"
 },
 "compatibility": {
 "processed_v2": {
 "requires": {
 "clipped": ["v1"],
 "export": ["v2"]
 },
 "incompatible_with": {
 "clipped": ["v0"],
 "export": ["v1"]
 }
 }
 },
 "version_history": [
 {
 "version": "processed_v2",
 "date": "2025-10-23",
 "changes": "Fixed coordinate system handling in downsampling",
 "breaking": true
 },
 {
 "version": "export_v2",
 "date": "2025-10-20",
 "changes": "Added bounds metadata to JSON",
 "breaking": false
 }
 ]
}
```

### Version Checking:

Every data loading function checks version compatibility:

```python
def load_clipped_data(region_id: str, source: str) -> RasterData:
 """Load clipped elevation data with version checking."""

# Load data
 tif_path = get_clipped_path(region_id, source)
 meta_path = tif_path.with_suffix('.json')

# Check version
 with open(meta_path) as f:
 metadata = json.load(f)

 required_version = get_current_version('clipped')
 actual_version = metadata['version']

 if not is_compatible(actual_version, required_version):
 raise VersionMismatchError(
 f"Cached data for {region_id} is version {actual_version}, "
 f"but current code requires {required_version}.\n"
 f"Run: python clear_caches.py --stage clipped --region {region_id}"
 )

 return load_raster(tif_path)
```

---

## Cache Invalidation Rules

### Automatic Invalidation Triggers:

**1. Version Bump** (manual, in code):
```python
# In src/versioning.py
CLIPPED_VERSION = "v1"
PROCESSED_VERSION = "v2"# <- Bumped from v1
EXPORT_VERSION = "v2"
```

When code detects version bump:
```
 Found processed data at v1, but code requires v2
 Moving old data to: data/processed/archive/v1/
 Cache cleared. Re-run processing.
```

**2. Source File Changed**:
```python
# Check source file hash
if metadata['source_file_hash'] != compute_hash(source_file):
 warning(f"Source file {source_file} changed since clipping!")
 prompt("Regenerate clipped data? [y/N]")
```

**3. Manual Invalidation**:
```bash
# Clear specific stage
python clear_caches.py --stage clipped

# Clear specific region
python clear_caches.py --region california

# Clear specific source
python clear_caches.py --source usa_3dep

# Clear everything processed after raw downloads
python clear_caches.py --all-processed

# Nuclear option
python clear_caches.py --all --confirm
```

### Granular Cache Control:

```
data/
 clipped/
 usa_3dep/
 california_state_10m_v1.tif <- Delete this
 california_state_10m_v1.json <- and this
 .cache_valid <- Flag file (presence = valid)
```

Cache validation:
1. Check `.cache_valid` flag exists
2. Check version in metadata matches current
3. Check source file hash matches
4. If any fail -> regenerate

---

## Implementation Plan

### Phase 1: Create New Structure (No Breaking Changes)
- [ ] Create new folder structure in `data/`
- [ ] Add versioning module: `src/versioning.py`
- [ ] Add metadata module: `src/metadata.py`
- [ ] Add migration utilities: `src/migration.py`
- [ ] Update `.gitignore` for new structure

### Phase 2: Add Version-Aware Functions
- [ ] Create `src/data_manager.py` with new loading functions
- [ ] Add version checking to all data loads
- [ ] Add automatic metadata generation
- [ ] Add hash verification
- [ ] Keep old functions working (deprecated warnings)

### Phase 3: Update Download Scripts
- [ ] `download_usa_3dep.py` - New script for USGS downloads
- [ ] Update `download_regions.py` - Use new structure
- [ ] Update `download_us_states.py` - Use new structure
- [ ] Add `download_national.py` - For nation-specific sources
- [ ] Each script writes to correct `data/raw/{source}/` folder

### Phase 4: Update Processing Pipeline
- [ ] `src/clipping.py` - Read from raw/, write to clipped/
- [ ] `src/downsampling.py` - Read from clipped/, write to processed/
- [ ] `export_for_web_viewer.py` - Read from processed/, write to generated/
- [ ] All steps check versions and generate metadata

### Phase 5: Update Viewer & Visualization
- [ ] Update viewer to read new JSON format
- [ ] Update `visualize_usa_overhead.py` to use new data paths
- [ ] Add source/resolution display in viewer UI

### Phase 6: Migration & Cleanup
- [ ] Run `migrate_data_structure.py` to move existing files
- [ ] Update documentation (README, TECH.md)
- [ ] Remove old deprecated functions
- [ ] Archive old download scripts

---

## Migration Path

### For Users With Existing Data:

**Option 1: Keep and Migrate** (recommended if you have lots of downloaded data):
```bash
# Backs up existing, creates new structure, attempts smart migration
python migrate_data_structure.py --keep-old
```

**Option 2: Fresh Start** (if you want to re-download everything clean):
```bash
# Archives old data, starts fresh
python migrate_data_structure.py --fresh

# Or manually:
mv data data_old_2025_10_23
mkdir data
# Re-download as needed
```

### Migration Script Behavior:

```python
# migrate_data_structure.py does:

1. Inventory existing files
 - Scan data/regions/, data/usa_elevation/
 - Detect source, resolution from file content

2. Create new structure
 - Build data/raw/, data/clipped/, data/processed/

3. Classify and move files
 - GeoTIFF inspection: check metadata, bounds, resolution
 - Guess source from resolution/bounds:
* 1-10m + USA bounds -> usa_3dep
* 30m + global -> srtm_30m
 - Generate metadata JSON for each file

4. Verification
 - Open each moved file to verify readable
 - Generate report: what went where

5. Update config
 - Create data/metadata/source_registry.json
 - Set initial version: clipped_v1, processed_v1, export_v1
```

---

## Benefits of New System

### Before (Current):
```python
# Unclear what this is!
data = load_tif("data/regions/california.tif")

# Where does this come from? What version?
with open("generated/regions/california.json") as f:
 viewer_data = json.load(f)
```

### After (New System):
```python
# Clear provenance
from src.data_manager import DataManager

dm = DataManager()

# Load best available data for region
data = dm.load_region("california", prefer_source="usa_3dep")
# -> Checks data/raw/usa_3dep/california_bbox_10m.tif
# -> Falls back to data/raw/srtm_30m/california_bbox_30m.tif if not found

# Load clipped data (auto-generates if missing)
clipped = dm.load_clipped("california", boundary="state")
# -> Checks data/clipped/usa_3dep/california_state_10m_v1.tif
# -> Auto-generates from raw if missing or version mismatch

# Get metadata
meta = dm.get_metadata("california")
print(f"Source: {meta.source}, Resolution: {meta.resolution}m")
# -> "Source: usa_3dep, Resolution: 10m"

# List all available data for region
sources = dm.list_sources("california")
# -> ["usa_3dep (10m, raw)", "srtm_30m (30m, raw+clipped)"]
```

---

## Decisions Confirmed (Oct 23, 2025)

**Source Names**: `usa_3dep` (not `usgs_3dep`)
**Folder Structure**: 4-stage pipeline approved
**Version Strategy**: Compatibility checking approved
**Migration**: Get new high-res data (existing is 30m SRTM, upgrade to 10m)
**Hash Algorithm**: MD5 for cache validation
**Resolution Format**: `10m` (concise)
**Archive Strategy**: Keep one previous version

### Download Priority Order:
1.**Full USA** (USGS 3DEP)
2.**All 50 US States** (USGS 3DEP, individual)
3.**Japan** (GSI - Geospatial Information Authority)
4.**Shikoku Island / Kochi** (GSI, specific region)
5.**Switzerland** (SwissTopo)

### Existing Data Assessment:
- Current USA data: ~6km resolution (too coarse - replace)
- Current state data: 29 states at ~30m SRTM (upgrade to 10m)
- Missing states: 21 including CA, TX, FL, NY (download new)
-**Decision**: Start fresh with USGS 3DEP for better quality

---

## Nation-Specific Data Sources Reference

### High-Priority Countries (Better Than Global Sources):

**North America:**
-**USA**: USGS 3DEP (1-10m) - https://elevation.nationalmap.gov/
-**Canada**: CDEM (20m) - https://open.canada.ca/

**Europe:**
-**Germany**: BKG DGM (1-25m) - https://gdz.bkg.bund.de/
-**UK**: Ordnance Survey (2m) - https://www.ordnancesurvey.co.uk/
-**Switzerland**: SwissTopo (0.5-2m) - https://www.swisstopo.admin.ch/
-**France**: IGN RGE ALTI (1-5m) - https://geoservices.ign.fr/
-**Norway**: Kartverket (10m) - https://www.kartverket.no/

**Asia-Pacific:**
-**Japan**: GSI DEM (5-10m) - https://fgd.gsi.go.jp/
-**Australia**: Geoscience Australia (5m) - https://elevation.fsdf.org.au/
-**New Zealand**: LINZ (8m) - https://data.linz.govt.nz/

**Implementation**: Each gets a download module in `downloaders/{country_code}.py`

---

## Next Steps

**Immediate:**
1. Document design (this file)
2. ⏳ Get user feedback on naming/structure
3. ⏳ Check if USGS 3DEP needs authentication

**Short-term:**
1. Implement Phase 1 (folder structure)
2. Implement Phase 2 (versioning system)
3. Create migration script

**Medium-term:**
1. Refactor existing download scripts
2. Add nation-specific downloaders
3. Update all documentation

---

**Status**: Awaiting user feedback before implementation begins.

