# Action Plan: Getting Resolutions >100m

## Current Status

**CONFIRMED**: OpenTopography API (which we already use) does **NOT** support resolutions >100m.
- ✅ Supports: 10m, 30m, 90m
- ❌ Does NOT support: 250m, 500m, 1000m (GTOPO30, ETOPO1, ETOPO5 not available)

**CONFIRMED**: GMTED2010 (250m, 500m, 1000m) is partially implemented but requires manual downloads.

---

## Option 1: Implement GMTED2010 Automated Download (RECOMMENDED)

### Current Status
- ✅ Code structure exists (`src/downloaders/gmted2010.py`)
- ✅ Supports pre-downloaded tiles
- ❌ Automated download not implemented

### What We Need
GMTED2010 tiles are available from USGS but require finding the direct download URLs or implementing EarthExplorer API access.

### Implementation Paths:

#### Path A: Direct Tile URLs (If Available)
- Research GMTED2010 tile URL patterns
- Implement direct HTTP/FTP download
- **Status**: Need to find URL patterns

#### Path B: USGS EarthExplorer API
- Register for USGS EarthExplorer API access
- Implement API-based download
- **Status**: Requires API key/registration

#### Path C: NASA Earthdata CMR API
- GMTED2010 may be accessible via NASA CMR API
- Requires Earthdata login (free registration)
- **Status**: Need to test CMR API access

### Next Steps:
1. **Research GMTED2010 direct download URLs**
   - Check if tiles are on public FTP/HTTP servers
   - Look for URL patterns like: `ftp://.../gmted2010/{resolution}/{tile_name}.tif`
   
2. **Test NASA Earthdata CMR API**
   - Register free account at https://urs.earthdata.nasa.gov/
   - Test CMR API for GMTED2010 granules
   - Implement download if available

3. **If no API available**: Implement manual download helper
   - Generate EarthExplorer search URLs with pre-filled bounds
   - Provide clear instructions for users

---

## Option 2: Test Commercial APIs (If You Get API Keys)

### GPXZ Elevation API
- **Status**: Claims GeoTIFF support (not just point queries)
- **API Key**: Required (free tier available)
- **URL**: https://www.gpxz.io/
- **Next Step**: Get free API key and test bbox/raster downloads

### xyElevation API  
- **Status**: Point queries only (likely)
- **API Key**: Required (free tier available)
- **URL**: https://xyelevation.com/
- **Next Step**: Test if supports bbox/raster (unlikely but worth checking)

### TerrainTap API
- **Status**: Point queries only (likely)
- **API Key**: Required (free tier available)
- **URL**: https://terraintap.com/
- **Next Step**: Test if supports bbox/raster (unlikely but worth checking)

---

## Option 3: Direct Downloads (No API, But Programmatic)

### GTOPO30 (1km resolution)
- **Source**: NASA/USGS
- **Access**: Direct download (no API)
- **Implementation**: 
  - Find direct download URLs/FTP
  - Implement tile downloader
  - **Status**: Need to find URL patterns

### ETOPO1 (1.8km resolution)
- **Source**: NOAA NCEI
- **Access**: Direct download (no API)
- **URL**: https://www.ncei.noaa.gov/products/etopo-global-relief-model
- **Implementation**:
  - Check for direct download URLs
  - Implement downloader
  - **Status**: Need to find URL patterns

### ETOPO5 (9km resolution)
- **Source**: NOAA NCEI
- **Access**: Direct download (no API)
- **Implementation**: Same as ETOPO1

---

## Option 4: Mapbox Terrain-RGB (Tile-Based)

### How It Works
- Mapbox provides elevation data as RGB-encoded PNG tiles
- Lower zoom levels = coarser resolution
- **Zoom 0**: ~156km per pixel (very coarse)
- **Zoom 1**: ~78km per pixel
- **Zoom 2**: ~39km per pixel
- **Zoom 3**: ~20km per pixel
- **Zoom 4**: ~10km per pixel
- **Zoom 5**: ~5km per pixel

### Implementation
- Requires Mapbox access token
- Download tiles at appropriate zoom level
- Decode RGB values to elevation
- Mosaic tiles into GeoTIFF

### Next Steps:
1. Get Mapbox access token (free tier: 50,000 requests/month)
2. Test tile download and RGB decoding
3. Implement tile-based downloader

---

## Recommended Implementation Order

### Phase 1: Test GPXZ API (Easiest)
1. **Get GPXZ free API key** (you do this)
2. **Test bbox/raster download** (I implement)
3. **If it works**: Integrate into orchestrator
4. **If it doesn't**: Move to Phase 2

### Phase 2: Implement GMTED2010 Direct Download
1. **Research GMTED2010 URL patterns** (I do this)
2. **Test NASA CMR API** (I do this, you register for free Earthdata account)
3. **Implement downloader** (I implement)
4. **Integrate into orchestrator**

### Phase 3: Implement GTOPO30/ETOPO Direct Downloads
1. **Find direct download URLs** (I research)
2. **Implement downloaders** (I implement)
3. **Integrate into orchestrator**

### Phase 4: Mapbox Terrain-RGB (If Needed)
1. **Get Mapbox token** (you do this)
2. **Test tile download/decoding** (I implement)
3. **Integrate into orchestrator**

---

## What I Need From You

### Immediate (To Test Commercial APIs):
1. **GPXZ API Key** (free tier)
   - Register at: https://www.gpxz.io/
   - Get API key
   - Add to `settings.json` as `"gpxz": {"api_key": "..."}`

### Soon (For NASA/NOAA Access):
2. **NASA Earthdata Account** (free)
   - Register at: https://urs.earthdata.nasa.gov/
   - Username/password for CMR API testing
   - Add to `settings.json` as `"nasa_earthdata": {"username": "...", "password": "..."}`

### Optional (For Mapbox):
3. **Mapbox Access Token** (free tier)
   - Register at: https://account.mapbox.com/
   - Get access token
   - Add to `settings.json` as `"mapbox": {"access_token": "..."}`

---

## Next Steps (What I'll Do)

1. **Research GMTED2010 URL patterns**
   - Search for direct download URLs
   - Check NASA CMR API documentation
   - Test if tiles are on public servers

2. **Research GTOPO30/ETOPO URLs**
   - Find direct download links
   - Check FTP/HTTP access patterns

3. **Test GPXZ API** (once you provide key)
   - Test bbox/raster download capability
   - Implement if it works

4. **Implement best option**
   - Choose most reliable method
   - Implement downloader
   - Integrate into orchestrator

---

## Summary

**Best Path Forward:**
1. **You**: Get GPXZ free API key (5 minutes)
2. **Me**: Test GPXZ API for bbox/raster support
3. **If GPXZ works**: Implement it (easiest path)
4. **If GPXZ doesn't work**: Implement GMTED2010 direct download (more work but reliable)

**What to do right now:**
- Get GPXZ API key and add to settings.json
- I'll test it immediately and implement if it works
- If it doesn't work, I'll implement GMTED2010 direct download

Let me know when you have the GPXZ API key and I'll test it!

