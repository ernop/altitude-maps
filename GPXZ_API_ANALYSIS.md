# GPXZ API Analysis

## API Key Added
- ✅ Added to `settings.json` as `gpxz.api_key`
- ✅ Rate limit configured: 100 reqs/sec

## What GPXZ Provides

### Capabilities:
- ✅ **Raster downloads** (bbox-based GeoTIFF)
- ✅ **Point queries** (single lat/lon)
- ✅ **Global coverage**
- ✅ **Multiple data sources** (merges USGS 3DEP, Copernicus, etc.)
- ✅ **High resolution** (up to 1m in some areas)

### Limitations:
- ❌ **Maximum resolution: 30m** (`res_m` parameter must be ≤30)
- ❌ **Does NOT support >100m resolutions** (250m, 500m, 1000m)
- ⚠️ **Raster downloads can be slow** (may timeout for large areas)

## Data Sources (from point queries):
GPXZ merges multiple sources automatically:
- `us_3dep_1m` - USGS 3DEP 1m (USA)
- `copernicus_30m` - Copernicus DEM 30m (global)
- Other sources as available

## Conclusion

**GPXZ is NOT suitable for >100m resolutions** because:
- Maximum `res_m` parameter is 30m
- Designed for high-resolution data (1m-30m)

**GPXZ IS useful for:**
- High-resolution alternatives to our existing sources
- Potentially better quality than OpenTopography in some areas
- Can supplement our 10m/30m downloads

## Next Steps for >100m Resolutions

Since GPXZ doesn't support >100m, we still need:
1. **GMTED2010 direct download** (250m, 500m, 1000m)
2. **GTOPO30 direct download** (1km)
3. **ETOPO1/ETOPO5 direct download** (1.8km, 9km)

See `RESOLUTION_100M_PLUS_ACTION_PLAN.md` for implementation plan.

