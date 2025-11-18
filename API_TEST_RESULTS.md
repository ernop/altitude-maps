# API Test Results - Elevation Data Sources >100m

## ✅ CONFIRMED WORKING (No API Key Required)

### 1. Open Topo Data API
- **Status**: ✅ WORKS
- **API Key**: Not required
- **Resolutions**: SRTM30m, SRTM90m, ASTER30m, EUDEM25m
- **Coverage**: Global
- **API Type**: Point queries only (lat/lon pairs)
- **Bbox/Raster**: ❌ No (point queries only)
- **URL**: https://api.opentopodata.org/v1/
- **Example**: `https://api.opentopodata.org/v1/srtm90m?locations=35.3,-120.8`
- **Limitation**: Point-based API, would need to query many points to build raster

### 2. Open-Elevation API
- **Status**: ✅ WORKS
- **API Key**: Not required
- **Resolutions**: Variable (uses SRTM data)
- **Coverage**: Global
- **API Type**: Point queries only
- **Bbox/Raster**: ❌ No (point queries only)
- **URL**: https://api.open-elevation.com/api/v1/
- **Example**: `https://api.open-elevation.com/api/v1/lookup?locations=35.3,-120.8`
- **Limitation**: Point-based API, would need to query many points to build raster

---

## ✅ CONFIRMED WORKING (API Key Required - We Have It)

### 3. OpenTopography Global DEM API
- **Status**: ✅ WORKS (we have API key)
- **API Key**: ✅ Already configured in settings.json
- **Resolutions Available**:
  - ✅ SRTMGL1 (30m)
  - ✅ SRTMGL3 (90m) - **Already implemented**
  - ✅ AW3D30 (30m)
  - ✅ COP30 (Copernicus 30m)
  - ✅ COP90 (Copernicus 90m) - **Already implemented**
- **NOT Available**:
  - ❌ GTOPO30 (1km) - Not supported
  - ❌ ETOPO1 (1.8km) - Not supported
  - ❌ ETOPO5 (9km) - Not supported
- **Coverage**: Global
- **API Type**: ✅ Bbox/raster downloads (GeoTIFF)
- **Bbox/Raster**: ✅ YES - Direct GeoTIFF download
- **URL**: https://portal.opentopography.org/API/globaldem
- **Test Result**: Successfully downloaded 21.2 KB GeoTIFF for test bbox
- **Limitation**: Max 4 degrees per dimension, rate limits apply
- **Status**: Already integrated for 30m/90m, but **no >100m resolutions available**

---

## ❌ REQUIRES API KEY (Not Tested Yet)

### 4. GPXZ Elevation API
- **Status**: ❓ Not tested (requires API key)
- **API Key**: Required (free tier available)
- **Resolutions**: Variable (merges multiple sources)
- **Coverage**: Global + bathymetry
- **API Type**: Point queries + GeoTIFF generation
- **Bbox/Raster**: ✅ Claims to support GeoTIFF generation
- **URL**: https://www.gpxz.io/
- **Next Step**: Test with free API key if user provides one

### 5. xyElevation API
- **Status**: ❌ Tested - Requires API key (403 error without key)
- **API Key**: Required (free tier available)
- **Resolutions**: Variable
- **Coverage**: Global + bathymetry
- **API Type**: Point queries (Google Elevation API compatible)
- **Bbox/Raster**: ❓ Unknown (likely point-based)
- **URL**: https://xyelevation.com/
- **Next Step**: Test with free API key if user provides one

### 6. TerrainTap Elevation API
- **Status**: ❓ Not tested (requires API key)
- **API Key**: Required (free tier available)
- **Resolutions**: Copernicus 30m/90m (fallback)
- **Coverage**: Global terrestrial
- **API Type**: Point queries (Google Elevation API compatible)
- **Bbox/Raster**: ❓ Unknown (likely point-based)
- **URL**: https://terraintap.com/
- **Next Step**: Test with free API key if user provides one

---

## Summary

### Currently Available for >100m:
**NONE** - OpenTopography (which we already use) only supports up to 90m resolution.

### Point-Based APIs (Would Need Custom Implementation):
- Open Topo Data (SRTM90m available)
- Open-Elevation (SRTM-based)

### Need API Key to Test:
- GPXZ (claims GeoTIFF support)
- xyElevation
- TerrainTap

### Conclusion:
**OpenTopography does NOT have >100m resolutions** (GTOPO30, ETOPO1, ETOPO5 are not available).

For >100m resolutions, we would need to:
1. Use point-based APIs and build rasters (inefficient)
2. Get API keys for commercial services (GPXZ, xyElevation, etc.)
3. Use direct downloads from NASA/NOAA (GTOPO30, ETOPO) - no API, manual download

---

## Recommendations

1. **For now**: Keep using OpenTopography for 30m/90m (already working)
2. **For >100m**: Consider implementing direct download from NASA Earthdata for GTOPO30 (1km) - free but requires registration and custom download script
3. **Alternative**: Test GPXZ API if user gets free API key (claims GeoTIFF support)

