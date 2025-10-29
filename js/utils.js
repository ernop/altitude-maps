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
 return await response.json();
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

