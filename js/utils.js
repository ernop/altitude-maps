// Utility functions for elevation viewer

// Expected data format version
const EXPECTED_FORMAT_VERSION = 2;

/**
* Calculate real-world scale from geographic bounds
* @param {Object} rawElevationData - The raw elevation data with bounds
* @returns {Object} Scale information
*/
function calculateRealWorldScale(rawElevationData) {
 const bounds = rawElevationData.bounds;
 const width = rawElevationData.width;
 const height = rawElevationData.height;

 const lonSpan = Math.abs(bounds.right - bounds.left); // degrees
 const latSpan = Math.abs(bounds.top - bounds.bottom); // degrees

 // Calculate meters per degree at the center latitude
 const centerLat = (bounds.top + bounds.bottom) / 2.0;
 const metersPerDegLon = 111_320* Math.cos(centerLat* Math.PI / 180);
 const metersPerDegLat = 111_320; // approximately constant

 // Calculate real-world dimensions in meters
 const widthMeters = lonSpan* metersPerDegLon;
 const heightMeters = latSpan* metersPerDegLat;

 // Meters per pixel
 const metersPerPixelX = widthMeters / width;
 const metersPerPixelY = heightMeters / height;

 console.log(` Real-world scale:`);
 console.log(` Size: ${(widthMeters/1000).toFixed(1)} x ${(heightMeters/1000).toFixed(1)} km`);
 console.log(` Resolution: ${metersPerPixelX.toFixed(1)} x ${metersPerPixelY.toFixed(1)} m/pixel`);

 return {
 metersPerPixelX,
 metersPerPixelY,
 widthMeters,
 heightMeters
 };
}

/**
* Load elevation data from JSON file
* @param {string} url - URL to load from
* @returns {Promise<Object>} Elevation data
*/
async function loadElevationData(url) {
 const response = await fetch(url);
 if (!response.ok) {
 throw new Error(`Failed to load elevation data. HTTP ${response.status}`);
 }
 const data = await response.json();

  // Always report the full URL and core metadata for any loaded JSON
  try {
    const w = data.width;
    const h = data.height;
    const ver = data.format_version || '(none)';
    const src = data.source || data.source_file || '(unknown)';
    console.log(`[JSON] Loaded viewer data: ${url}`);
    console.log(`[JSON] Metadata: format_version=${ver}, size=${w}x${h}, source=${src}`);
    if (data.bounds) {
      const b = data.bounds;
      console.log(`[JSON] Bounds: left=${b.left}, bottom=${b.bottom}, right=${b.right}, top=${b.top}`);
    }
    if (data.stats) {
      const s = data.stats;
      console.log(`[JSON] Stats: min=${s.min}, max=${s.max}, mean=${s.mean}`);
    }
  } catch (e) {
    // ignore logging errors
  }

 // Validate format version
 if (data.format_version && data.format_version !== EXPECTED_FORMAT_VERSION) {
 console.error(`[!!] FORMAT VERSION MISMATCH!`);
 console.error(` Expected: v${EXPECTED_FORMAT_VERSION}`);
 console.error(` Got: v${data.format_version}`);
 throw new Error(
 `Data format version mismatch!\n` +
 `Expected v${EXPECTED_FORMAT_VERSION}, got v${data.format_version}\n\n` +
 `Please re-export: python export_for_web_viewer.py`
 );
 } else if (!data.format_version) {
 console.warn(`[!!] No format version in data file - may be legacy format!`);
 console.warn(` Consider re-exporting: python export_for_web_viewer.py`);
 } else {
 console.log(`[OK] Data format v${data.format_version} (exported: ${data.exported_at || 'unknown'})`);
 }

 return data;
}

/**
* Load border data for a region
* @param {string} elevationUrl - URL of elevation data
* @returns {Promise<Object|null>} Border data or null
*/
async function loadBorderData(elevationUrl) {
 const borderUrl = elevationUrl.replace('.json', '_borders.json');
 try {
 const response = await fetch(borderUrl);
 if (!response.ok) {
 console.log(`[INFO] No border data found at ${borderUrl}`);
 return null;
 }
 const data = await response.json();
 console.log(`[OK] Loaded border data: ${data.countries.length} countries`);
 return data;
 } catch (error) {
 console.log(`[INFO] Border data not available: ${error.message}`);
 return null;
 }
}

/**
* Load regions manifest
* @returns {Promise<Object|null>} Regions manifest or null
*/
async function loadRegionsManifest() {
 try {
 const response = await fetch('generated/regions/regions_manifest.json');
 if (!response.ok) {
 console.warn('Regions manifest not found, using default single region');
 return null;
 }
    const manifest = await response.json();
    try {
      const url = 'generated/regions/regions_manifest.json';
      const version = manifest.version || '(unknown)';
      const regions = manifest.regions && typeof manifest.regions === 'object' ? Object.keys(manifest.regions) : [];
      console.log(`[JSON] Loaded regions manifest: ${url}`);
      console.log(`[JSON] Metadata: version=${version}, regions=${regions.length}`);
    } catch (e) {
      // ignore logging errors
    }
    return manifest;
 } catch (error) {
 console.warn('Could not load regions manifest:', error);
 return null;
 }
}

/**
* Show loading indicator
* @param {string} message - Loading message
*/
function showLoading(message = 'Loading elevation data...') {
 const loadingDiv = document.getElementById('loading');
 loadingDiv.textContent = message;
 loadingDiv.style.display = 'flex';
}

/**
* Hide loading indicator
*/
function hideLoading() {
 document.getElementById('loading').style.display = 'none';
}

