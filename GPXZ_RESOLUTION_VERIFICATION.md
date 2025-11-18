# GPXZ Resolution Verification

## Test Results: Does GPXZ Really Have 1m Data?

### ✅ YES - Verified 1m Resolution

**Test Location**: Morro Bay, CA (35.3°N, -120.8°W)
**Request**: `res_m=1` (1 meter resolution)
**Result**: ✅ **Successfully downloaded 1m resolution GeoTIFF**

### Actual Raster Properties:
- **Dimensions**: 1,872 × 2,262 pixels
- **Pixel Size**: 1.00m × 1.00m (exactly 1 meter)
- **Coverage**: ~1,872m × 2,262m area
- **File Size**: 13.2 MB
- **Data Source**: USGS 3DEP 1m (confirmed from point query)
- **Format**: Cloud-optimized GeoTIFF

### Point Query Results:
- **Morro Bay, CA**: `us_3dep_1m` (1m resolution) ✅
- **Germany**: `germany_bayern_1m_dtm` (1m resolution) ✅
- **Norway**: `norway_10m` (10m resolution)
- **Australia**: `copernicus_30m` (30m resolution)

## GPXZ Resolution Capabilities

### Maximum Resolution:
- **Up to 0.5m (50cm)** in areas with lidar data
- **1m** in areas with USGS 3DEP coverage (USA)
- **10m** in some countries (Norway, etc.)
- **30m** global fallback (Copernicus DEM)

### Resolution Availability:
- **USA**: 1m (USGS 3DEP) - highest quality
- **Some European countries**: 1m (country-specific lidar)
- **Global**: 30m (Copernicus DEM) - fallback

### API Parameter Limits:
- **Minimum `res_m`**: 1m (can request finer, but may not have data)
- **Maximum `res_m`**: 30m (cannot request coarser)
- **Best practice**: Request 1m-30m based on area coverage

## Conclusion

**GPXZ DOES provide 1m resolution data** where available:
- ✅ Verified with actual raster download
- ✅ Pixel size confirmed: exactly 1.00m × 1.00m
- ✅ Uses USGS 3DEP 1m for USA regions
- ✅ Can go as fine as 0.5m in lidar-covered areas

**However:**
- Resolution varies by location (not all areas have 1m)
- Falls back to 30m globally (Copernicus)
- Cannot request >30m (no support for 250m/500m/1000m)

## Use Cases

**GPXZ is excellent for:**
- High-resolution regions (1m-30m)
- USA regions (1m USGS 3DEP)
- Small, detailed areas
- When better quality than OpenTopography needed

**GPXZ is NOT suitable for:**
- Coarse resolutions (>100m)
- Large regions needing 250m/500m/1000m
- When OpenTopography 30m/90m is sufficient

