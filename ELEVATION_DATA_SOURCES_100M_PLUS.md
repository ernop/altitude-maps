# Elevation Data Sources >100m Resolution (API-Accessible)

Research summary of global elevation data sources with resolutions coarser than 100m (250m, 500m, 1000m, etc.) that offer API access.

---

## Currently Used

### GMTED2010 (Global Multi-resolution Terrain Elevation Data 2010)
- **Resolutions**: 250m, 500m, 1000m
- **Coverage**: Global
- **Access**: Manual download from USGS EarthExplorer (no API)
- **Status**: Currently disabled in code (temporarily restricted to 10m/30m/90m)
- **URL**: https://earthexplorer.usgs.gov/

---

## Potential API-Accessible Sources

### 1. **Open Topo Data API**
- **Resolutions**: Supports multiple datasets including coarser resolutions
- **Coverage**: Global
- **API**: Yes - REST API compatible with Google Maps Elevation API
- **Access**: Free public API + self-hosted option
- **API Key**: Not required for public API (rate limits apply)
- **Datasets**: Can configure with various DEM sources
- **URL**: https://www.opentopodata.org/
- **Notes**: Open-source, can self-host with custom datasets

### 2. **GPXZ Elevation API**
- **Resolutions**: Variable (merges multiple sources)
- **Coverage**: Global (includes bathymetry)
- **API**: Yes - REST API
- **Access**: Free evaluation plan + paid tiers
- **API Key**: Required (free tier available)
- **Features**: 
  - Low-latency point queries
  - High-resolution 2D GeoTIFF generation
  - Drop-in replacement for Google Elevation API
- **URL**: https://www.gpxz.io/
- **Notes**: Seamlessly merges global bathymetry with lidar data

### 3. **TerrainTap Elevation API**
- **Resolutions**: Primarily Copernicus 30m/90m, but may support coarser
- **Coverage**: Global terrestrial
- **API**: Yes - REST API
- **Access**: Paid service
- **API Key**: Required
- **Features**: Fast, affordable Google Elevation API replacement
- **URL**: https://terraintap.com/
- **Notes**: Uses Copernicus DEM primarily

### 4. **xyElevation API**
- **Resolutions**: Variable (comprehensive global coverage)
- **Coverage**: Global elevation + bathymetry
- **API**: Yes - REST API (Google Elevation API compatible)
- **Access**: Free tier + paid plans
- **API Key**: Required
- **Features**: 
  - Up to 600 points per request
  - Global coverage including bathymetry
- **URL**: https://xyelevation.com/
- **Notes**: Drop-in replacement for Google Elevation API

### 5. **Stadia Maps Elevation API**
- **Resolutions**: 30m or better (may support coarser)
- **Coverage**: Global
- **API**: Yes - REST API
- **Access**: Paid service
- **API Key**: Required
- **Features**: Precise elevation for route planning and 3D visualization
- **URL**: https://stadiamaps.com/products/routing-navigation/elevation/
- **Notes**: Focused on routing/navigation use cases

### 6. **Mapbox Terrain-RGB Tiles**
- **Resolutions**: Variable (tile-based, can be downsampled)
- **Coverage**: Global
- **API**: Yes - Raster Tiles API / Tilequery API
- **Access**: Requires Mapbox account
- **API Key**: Access token required
- **Features**: 
  - Elevation encoded in RGB channels of PNG tiles
  - Can request lower zoom levels for coarser resolution
- **URL**: https://docs.mapbox.com/data/tilesets/guides/access-elevation-data/
- **Notes**: Tile-based system, zoom level determines resolution

### 7. **Esri World Elevation Services**
- **Resolutions**: Multi-resolution (includes coarser resolutions)
- **Coverage**: Global
- **API**: Yes - ArcGIS REST API
- **Access**: Requires ArcGIS Online subscription
- **API Key**: Required
- **Features**: 
  - Multiple resolution datasets
  - Image services for elevation
- **URL**: https://desktop.arcgis.com/en/arcmap/latest/manage-data/raster-and-images/what-are-the-world-elevation-image-services.htm
- **Notes**: Commercial service, requires subscription

### 8. **NASA Earthdata (CMR API)**
- **Resolutions**: Various (includes GTOPO30 at 1km, ETOPO at various resolutions)
- **Coverage**: Global
- **API**: Yes - Common Metadata Repository (CMR) API
- **Access**: Free (registration required)
- **API Key**: Earthdata login required
- **Datasets**:
  - **GTOPO30**: 1km (30 arc-second) resolution
  - **ETOPO1**: 1 arc-minute (~1.8km) global bathymetry/topography
  - **ETOPO5**: 5 arc-minute (~9km) global bathymetry/topography
- **URL**: https://cmr.earthdata.nasa.gov/
- **Notes**: 
  - Free but requires registration
  - CMR API for metadata/search, direct download for data
  - GTOPO30 and ETOPO datasets are older but global coverage

### 9. **Open-Elevation API**
- **Resolutions**: Variable (configurable with different DEM sources)
- **Coverage**: Global
- **API**: Yes - REST API
- **Access**: Free, open-source
- **API Key**: Not required (can self-host)
- **Features**: 
  - Self-hostable
  - Compatible with Google Elevation API
- **URL**: https://www.open-elevation.com/
- **Notes**: Open-source, can configure with various datasets

### 10. **Clockwork Micro Elevation API**
- **Resolutions**: USGS 3DEP (1/3 arc-second ~10m) - US only
- **Coverage**: United States only
- **API**: Yes - REST API
- **Access**: Paid service
- **API Key**: Required
- **URL**: https://www.clockworkmicro.com/services/elevation-api
- **Notes**: US-only, high-resolution focus

---

## Specific Coarse Resolution Datasets (May Require Custom API Implementation)

### GTOPO30
- **Resolution**: 1km (30 arc-second)
- **Coverage**: Global
- **Access**: NASA Earthdata (free, registration required)
- **API**: CMR API for search, direct download for data
- **URL**: https://earthexplorer.usgs.gov/ (search "GTOPO30")
- **Notes**: Older dataset but global coverage, good for very large regions

### ETOPO1
- **Resolution**: 1 arc-minute (~1.8km)
- **Coverage**: Global (includes bathymetry)
- **Access**: NOAA/NCEI (free)
- **API**: Direct download, may need custom wrapper
- **URL**: https://www.ncei.noaa.gov/products/etopo-global-relief-model
- **Notes**: Includes bathymetry, good for coastal regions

### ETOPO5
- **Resolution**: 5 arc-minute (~9km)
- **Coverage**: Global (includes bathymetry)
- **Access**: NOAA/NCEI (free)
- **API**: Direct download, may need custom wrapper
- **URL**: https://www.ncei.noaa.gov/products/etopo-global-relief-model
- **Notes**: Very coarse, good for global overviews

---

## Recommendations

### Best Options for API Integration:

1. **Open Topo Data** - Free, open-source, self-hostable, supports multiple datasets
2. **GPXZ Elevation API** - Commercial but has free tier, comprehensive coverage
3. **xyElevation API** - Free tier available, Google Elevation API compatible
4. **NASA Earthdata CMR API** - Free, can access GTOPO30/ETOPO datasets (may need custom download wrapper)

### For Very Large Regions (>500m visible pixels):

- **GTOPO30** (1km) - Free from NASA Earthdata, global coverage
- **ETOPO1** (1.8km) - Free from NOAA, includes bathymetry
- **GMTED2010** (250m/500m/1000m) - Currently used, manual download only

### Implementation Notes:

- Most APIs are point-based (query lat/lon), not raster-based (bbox downloads)
- May need to implement tile-based or bbox-based wrappers for raster downloads
- Consider caching/downloading tiles for large regions
- Some APIs have rate limits even with API keys

---

## Next Steps

1. **Evaluate API capabilities**: Test which APIs support bbox/raster downloads vs point queries only
2. **Compare pricing**: Free tiers vs paid plans for commercial APIs
3. **Test data quality**: Compare resolution/accuracy of different sources
4. **Implement downloaders**: Create downloader modules similar to existing SRTM/USGS 3DEP downloaders
5. **Add to orchestrator**: Integrate new sources into resolution selection logic

---

## References

- Open Topo Data: https://www.opentopodata.org/
- GPXZ: https://www.gpxz.io/
- TerrainTap: https://terraintap.com/
- xyElevation: https://xyelevation.com/
- Stadia Maps: https://stadiamaps.com/products/routing-navigation/elevation/
- Mapbox: https://docs.mapbox.com/data/tilesets/guides/access-elevation-data/
- NASA Earthdata: https://cmr.earthdata.nasa.gov/
- NOAA ETOPO: https://www.ncei.noaa.gov/products/etopo-global-relief-model

