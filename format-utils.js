/**
 * Data Formatting Utilities
 * Pure functions for converting data to human-readable formats
 * Handles units (metric/imperial/both), file sizes, distances, etc.
 */

/**
 * Format file size in human-readable format
 * @param {number} bytes - Size in bytes
 * @returns {string} Formatted size (e.g., "1.5 MB", "234 KB")
 */
function formatFileSize(bytes) {
    if (bytes < 1024) {
        return `${bytes} B`;
    } else if (bytes < 1024 * 1024) {
        return `${(bytes / 1024).toFixed(1)} KB`;
    } else {
        return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    }
}

/**
 * Format elevation in specified units
 * @param {number} meters - Elevation in meters
 * @param {string} units - 'metric', 'imperial', or 'both'
 * @returns {string} Formatted elevation
 */
function formatElevation(meters, units) {
    const feet = meters * 3.280839895;
    if (units === 'metric') return `${Math.round(meters)} m`;
    if (units === 'imperial') return `${Math.round(feet)} ft`;
    return `${Math.round(meters)} m / ${Math.round(feet)} ft`;
}

/**
 * Format distance in specified units
 * @param {number} meters - Distance in meters
 * @param {string} units - 'metric', 'imperial', or 'both'
 * @returns {string} Formatted distance
 */
function formatDistance(meters, units) {
    const miles = meters / 1609.344;
    const km = meters / 1000;
    if (units === 'metric') return km < 1 ? `${Math.round(meters)} m` : `${km.toFixed(2)} km`;
    if (units === 'imperial') return miles < 0.5 ? `${Math.round(meters * 3.280839895)} ft` : `${miles.toFixed(2)} mi`;
    const left = km < 1 ? `${Math.round(meters)} m` : `${km.toFixed(2)} km`;
    const right = miles < 0.5 ? `${Math.round(meters * 3.280839895)} ft` : `${miles.toFixed(2)} mi`;
    return `${left} / ${right}`;
}

/**
 * Format footprint (area dimensions) in specified units
 * @param {number} metersX - Width in meters
 * @param {number} metersY - Height in meters
 * @param {string} units - 'metric', 'imperial', or 'both'
 * @returns {string} Formatted footprint (e.g., "1.5 km × 2.3 km")
 */
function formatFootprint(metersX, metersY, units) {
    if (units === 'metric') {
        const kmX = metersX / 1000;
        const kmY = metersY / 1000;
        const fmtX = kmX < 1 ? `${Math.round(metersX)} m` : `${kmX.toFixed(2)} km`;
        const fmtY = kmY < 1 ? `${Math.round(metersY)} m` : `${kmY.toFixed(2)} km`;
        return `${fmtX} × ${fmtY}`;
    } else if (units === 'imperial') {
        const miX = metersX / 1609.344;
        const miY = metersY / 1609.344;
        const feetX = metersX * 3.280839895;
        const feetY = metersY * 3.280839895;
        const fmtX = miX < 0.5 ? `${Math.round(feetX)} ft` : `${miX.toFixed(2)} mi`;
        const fmtY = miY < 0.5 ? `${Math.round(feetY)} ft` : `${miY.toFixed(2)} mi`;
        return `${fmtX} × ${fmtY}`;
    } else { // 'both'
        const kmX = metersX / 1000;
        const kmY = metersY / 1000;
        const miX = metersX / 1609.344;
        const miY = metersY / 1609.344;
        const feetX = metersX * 3.280839895;
        const feetY = metersY * 3.280839895;
        const fmtXm = kmX < 1 ? `${Math.round(metersX)} m` : `${kmX.toFixed(2)} km`;
        const fmtYm = kmY < 1 ? `${Math.round(metersY)} m` : `${kmY.toFixed(2)} km`;
        const fmtXi = miX < 0.5 ? `${Math.round(feetX)} ft` : `${miX.toFixed(2)} mi`;
        const fmtYi = miY < 0.5 ? `${Math.round(feetY)} ft` : `${miY.toFixed(2)} mi`;
        return `${fmtXm} × ${fmtYm} / ${fmtXi} × ${fmtYi}`;
    }
}

/**
 * Format pixel size (compact format with km for large values)
 * @param {number} meters - Size in meters
 * @returns {string} Formatted size (e.g., "123.4m", "1.2km")
 */
function formatPixelSize(meters) {
    // Format pixel size with km if >1000m, one decimal point only
    if (meters >= 1000) {
        return `${(meters / 1000).toFixed(1)}km`;
    } else {
        return `${meters.toFixed(1)}m`;
    }
}

// Export to window for global access
window.FormatUtils = {
    formatFileSize,
    formatElevation,
    formatDistance,
    formatFootprint,
    formatPixelSize
};

