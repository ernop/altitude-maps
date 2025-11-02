# Tile Naming Convention Design Decision

**Date**: January 2025  
**Status**: Implemented and documented

---

## Problem Statement

When downloading elevation data in tiles to work around API size limits (e.g., OpenTopography 420,000 km² limit), we faced a naming decision that impacts caching efficiency, storage overhead, and long-term maintainability.

**Original approach** (problematic):
```
data/raw/srtm_30m/tiles/tennessee/tennessee_tile_00.tif
data/raw/srtm_30m/tiles/kentucky/kentucky_tile_00.tif
```

**Issues**:
- Tile `tennessee_tile_00.tif` might have identical bounds to `kentucky_tile_00.tif`
- No way to detect or reuse duplicate tiles across regions
- Wasted storage downloading same data multiple times
- Cache grows unboundedly as regions are added

---

## Decision: SRTM-Style Integer Degree Grid

**Chosen format**:
```
data/raw/srtm_30m/tiles/tile_N35_W090_srtm_30m_30m.tif
```

**Specification**:
- Format: `tile_{NS}{lat:02d}_{EW}{lon:03d}_{dataset}_{resolution}.tif`
- Southwest corner determines tile identity
- Integer degrees only (mirrors SRTM HGT convention)
- Shared pool directory (no per-region subdirs)

---

## Alternatives Considered

### 1. Hash-Based Naming
**Example**: `tile_a3f2b1046f_srtm_30m_30m.tif`

**Pros**:
- Deterministic uniqueness
- Collision-resistant

**Cons**:
- No human readability
- Can't infer coordinates from filename
- Harder debugging
- No industry standard precedent

**Verdict**: Rejected - violates "content-based" principle

### 2. Floating-Point Coordinates
**Example**: `tile_-90.12345_35.678_srtm_30m_30m.tif`

**Pros**:
- Exact precision
- No information loss

**Cons**:
- Non-deterministic rounding issues
- Long, unwieldy filenames
- Not aligned with any standard
- Poor readability

**Verdict**: Rejected - incompatible with grid standards

### 3. Region-Specific Subdirectories
**Example**: `tiles/tennessee/tile_00.tif`, `tiles/kentucky/tile_00.tif`

**Pros**:
- Clean separation
- Easy to delete per-region

**Cons**:
- Prevents reuse
- Wastes storage
- Breaks content-based principle
- Harder to maintain

**Verdict**: Rejected - caused the original problem

---

## Why SRTM Integer-Degree Grid Wins

### 1. Industry Standard Alignment

**Authority**: This approach mirrors the SRTM HGT file naming convention used by:
- NASA (SRTM, NASADEM)
- ESA (Copernicus DEM)
- USGS (3DEP, various global datasets)

**Format**: `N##W###` where:
- `##` = latitude (01-90 for N, 01-56 for S)
- `###` = longitude (000-180 for E/W)

**Our adaptation**: `tile_N##_W###_{dataset}_{res}.tif`

### 2. Content-Based Natural Reuse

**Example scenario**:
```
Tennessee: [-90.0, 35.0, -89.0, 36.0]
Kentucky:  [-89.0, 35.0, -88.0, 36.0]

Both use tile_N35_W090_srtm_30m_30m.tif
No duplicate download! ✅
```

**Result**: Adjacent regions with overlapping tile grids automatically share cache.

### 3. Human Readability & Debugging

**Visibility**:
- Coordinates visible in filename
- Easy to locate tiles on map
- Quick identification of coverage gaps
- Direct correspondence to geographic location

**Debugging**:
```bash
# Find all tiles covering a specific area
ls data/raw/srtm_30m/tiles/tile_N35_W*.tif

# Count tiles for a longitude band
ls data/raw/srtm_30m/tiles/tile_*_W090_*.tif
```

### 4. Storage Efficiency

**Quantitative example**:
- Tennessee needs 4 tiles
- Kentucky needs 4 tiles
- 2 tiles overlap
- **Old approach**: 8 downloads, 8 files stored
- **New approach**: 6 downloads, 6 files stored
- **Savings**: 25% storage reduction

For 50 US states with overlapping tiles, savings compound significantly.

### 5. Future Compatibility Matrix

| Scenario | Compatibility | Notes |
|----------|--------------|-------|
| New datasets (ASTER, AW3D30) | ✅ | Works via `{dataset}` suffix |
| Higher resolutions (5m, 10m) | ✅ | Works via `{resolution}` suffix |
| Different projections | ✅ | Coordinate-independent |
| Tile matrix standards (OGC TMS) | ✅ | Aligned with standard grids |
| Global coverage | ✅ | No collision limits |
| Cache invalidation | ✅ | Dataset/resolution handles it |
| Multi-user scenarios | ✅ | Deterministic naming |

---

## Implementation Details

### Southwest Corner Calculation

**Challenge**: Rounding behavior differs for positive vs negative coordinates.

**Solution**:
```python
sw_lat = int(math.floor(south)) if south >= 0 else int(math.trunc(south))
sw_lon = int(math.floor(west)) if west >= 0 else int(math.trunc(west))
```

**Examples**:
- `west=-90.12345` → `W090` (trunc)
- `west=90.678` → `E090` (floor)
- `south=35.789` → `N35` (floor)

### Shared Pool Directory

**Structure**:
```
data/raw/srtm_30m/tiles/
  tile_N35_W089_srtm_30m_30m.tif
  tile_N35_W090_srtm_30m_30m.tif
  tile_N35_W091_srtm_30m_30m.tif
  tile_N36_W089_srtm_30m_30m.tif
  ...

data/raw/srtm_90m/tiles/
  tile_N35_W090_srtm_90m_90m.tif
  ...
```

**Benefits**:
- Single location for all cached tiles
- Easy to browse/audit
- Simple cleanup (delete entire dir = reset all caches)
- No nested structure complexity

---

## World Best Practices Reference

### 1. OGC Tile Matrix Set Standard

The Open Geospatial Consortium defines tile matrix sets with hierarchical zoom levels. Our approach is aligned with the base grid concept.

**Relevance**: Our integer-degree grid is essentially a "zoom level 0" tile matrix.

### 2. NASA/USGS SRTM Convention

**Format**: `N##W###.hgt`
- **Standard**: NASA JPL SRTM v3
- **Coverage**: 60°N to 56°S
- **Tiles**: ~14,000 files globally

**Our adaptation**: Adds dataset and resolution fields while preserving grid semantics.

### 3. Copernicus DEM (ESA)

**Format**: Similar grid structure
- **Coverage**: Global (replacing SRTM)
- **Resolution**: 30m, 90m
- **Naming**: Based on tile coordinates

### 4. Google Tiles / Mapbox Tiles

**Format**: `z/x/y` where coordinates in tile matrix
- Uses similar grid concept at multiple zoom levels
- Proves grid-based approach scales

---

## Lessons Learned

### What Works Well

1. **Following standards** beats inventing custom formats
2. **Content-based naming** enables automatic optimization
3. **Integer precision** eliminates rounding ambiguity
4. **Shared pools** reduce complexity vs nested hierarchies

### Potential Pitfalls (Avoided)

1. **Over-precision**: Floating points would create unnecessarily long filenames
2. **Over-abstraction**: Hashes hide useful geographic info
3. **Over-isolation**: Per-region dirs break reuse patterns

---

## Migration Path

**For existing installations**:

Old tiles in region-specific directories can be:
1. Left in place (wasteful but non-breaking)
2. Manually migrated using bounds → filename mapping
3. Ignored - new downloads use new format automatically

**No breaking changes**: Code handles both paths during transition.

---

## References

- **SRTM HGT Spec**: https://dds.cr.usgs.gov/srtm/version2_1/Documentation/SRTM_Topo.pdf
- **Copernicus DEM**: https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-digital-elevation-model
- **OGC Tile Matrix Set**: https://docs.ogc.org/is/19-014r3/19-014r3.html
- **USGS Tile Scheme**: https://www.usgs.gov/ngp-standards-and-specifications/tile-scheme-generation-and-crs

---

## Conclusion

The SRTM-style integer degree grid naming convention provides optimal balance of:
- **Standards compliance** (NASA/ESA/USGS precedent)
- **Implementation simplicity** (integer math, no hashing)
- **Operational efficiency** (content-based reuse)
- **Future flexibility** (multi-dataset, multi-resolution support)

This is a **best practice** for geospatial tile caching that aligns with industry standards while solving our specific use case elegantly.


