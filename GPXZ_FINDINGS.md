# GPXZ API Test Results

## API Key Status
✅ **Added to settings.json** - Ready to use

## What GPXZ Provides

### Data Sources (Automatically Merged):
- **USGS 3DEP 1m** - USA (highest quality)
- **Copernicus 30m** - Global fallback
- **Country-specific high-res** - Germany (1m), Norway (10m), etc.
- **Automatic source selection** - GPXZ picks best available

### Capabilities:
- ✅ **Raster downloads** - bbox-based GeoTIFF (`/v1/elevation/hires-raster`)
- ✅ **Point queries** - single lat/lon (`/v1/elevation/point`)
- ✅ **Global coverage** - Works worldwide
- ✅ **High resolution** - Up to 1m in some areas

### Limitations:
- ❌ **Maximum resolution: 30m** - `res_m` parameter must be ≤30
- ❌ **Does NOT support >100m** - Cannot request 250m, 500m, 1000m
- ⚠️ **Rate limits** - 100 reqs/sec (but hit 429 on one test, may need throttling)
- ⚠️ **Raster downloads slow** - May timeout for large areas

## Test Results

### Point Queries (Working):
- Morro Bay, CA: `us_3dep_1m` (1m resolution) ✅
- Germany: `germany_bayern_1m_dtm` (1m resolution) ✅
- Australia: `copernicus_30m` (30m resolution) ✅
- Norway: `norway_10m` (10m resolution) ✅
- Kansas: Rate limit (429) ⚠️

### Raster Downloads:
- ❌ 250m request: `"res_m argument should be 30 or less"`
- ⏳ 30m request: Timed out (may be processing large area)

## Conclusion

**GPXZ is NOT suitable for >100m resolutions** because:
- API enforces maximum `res_m` of 30m
- Cannot request coarser resolutions

**GPXZ IS useful for:**
- High-resolution alternatives (1m-30m)
- Potentially better quality than OpenTopography
- Can supplement our existing 10m/30m downloads
- Useful for small, high-detail regions

## For >100m Resolutions

We still need to implement:
1. **GMTED2010 direct download** (250m, 500m, 1000m)
2. **GTOPO30 direct download** (1km)
3. **ETOPO1/ETOPO5 direct download** (1.8km, 9km)

These require finding direct download URLs or implementing EarthExplorer/NASA APIs.

## Recommendation

1. **Keep GPXZ configured** - Useful for high-res data
2. **Implement GMTED2010 downloader** - For >100m resolutions
3. **Consider GPXZ as alternative** - For 10m/30m when better quality needed

