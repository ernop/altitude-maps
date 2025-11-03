/**
 * Geometry and Spatial Calculation Utilities
 * 
 * Functions for converting between coordinate systems and spatial calculations.
 * Many functions depend on global state (rawElevationData, processedData, params, etc.)
 * which is intentional to maintain performance and avoid unnecessary parameter passing.
 */

/**
 * Calculate real-world scale from geographic bounds
 * This ensures vertical_exaggeration=1.0 means "true scale like real Earth"
 * 
 * @param {Object} [data] - Optional elevation data object (uses rawElevationData global if not provided)
 * @returns {Object} Scale information: { metersPerPixelX, metersPerPixelY, widthMeters, heightMeters }
 */
function calculateRealWorldScale(data) {
    const elevData = data || rawElevationData;
    if (!elevData) return { metersPerPixelX: 1, metersPerPixelY: 1, widthMeters: 1, heightMeters: 1 };

    const bounds = elevData.bounds;
    const width = elevData.width;
    const height = elevData.height;

    const lonSpan = Math.abs(bounds.right - bounds.left); // degrees
    const latSpan = Math.abs(bounds.top - bounds.bottom); // degrees

    // Calculate meters per degree at the center latitude
    const centerLat = (bounds.top + bounds.bottom) / 2.0;
    const metersPerDegLon = 111_320 * Math.cos(centerLat * Math.PI / 180);
    const metersPerDegLat = 111_320; // approximately constant

    // Calculate real-world dimensions in meters
    const widthMeters = lonSpan * metersPerDegLon;
    const heightMeters = latSpan * metersPerDegLat;

    // Meters per pixel
    const metersPerPixelX = widthMeters / width;
    const metersPerPixelY = heightMeters / height;

    return {
        metersPerPixelX,
        metersPerPixelY,
        widthMeters,
        heightMeters
    };
}

/**
 * Raycast from screen coordinates to world coordinates (on ground plane)
 * Depends on globals: renderer, camera, raycaster, terrainMesh, groundPlane
 * 
 * @param {number} screenX - Screen X coordinate
 * @param {number} screenY - Screen Y coordinate
 * @returns {THREE.Vector3|null} World position on ground plane (y=0)
 */
function raycastToWorld(screenX, screenY) {
    if (!renderer || !camera || !raycaster) return null;

    // Convert screen coordinates to normalized device coordinates (-1 to +1)
    const rect = renderer.domElement.getBoundingClientRect();
    const ndcX = ((screenX - rect.left) / rect.width) * 2 - 1;
    const ndcY = -((screenY - rect.top) / rect.height) * 2 + 1;

    // Set up raycaster
    raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), camera);

    // Prefer terrain intersection; fall back to ground plane
    if (terrainMesh) {
        const hits = raycaster.intersectObject(terrainMesh, true);
        if (hits && hits.length > 0) {
            const p = hits[0].point;
            return new THREE.Vector3(p.x, 0, p.z);
        }
    }

    const planeIntersect = new THREE.Vector3();
    const intersected = raycaster.ray.intersectPlane(groundPlane, planeIntersect);
    if (intersected) return planeIntersect;

    // Raycast miss is expected when camera is pointing away from terrain (e.g., at sky/horizon)
    // This happens normally during zoom out or when looking up - not an error
    return null;
}

/**
 * Convert world coordinates (3D scene) to lon/lat (geographic)
 * Depends on globals: rawElevationData, processedData, params
 * 
 * @param {number} worldX - World space X coordinate
 * @param {number} worldZ - World space Z coordinate
 * @returns {Object|null} Geographic coordinates { lon, lat }
 */
function worldToLonLat(worldX, worldZ) {
    if (!rawElevationData || !processedData) return null;

    const { bounds: elevBounds } = rawElevationData; // {left, right, top, bottom}
    const w = processedData.width;
    const h = processedData.height;
    let colNorm, rowNorm;

    if (params.renderMode === 'bars') {
        const bucket = params.bucketSize;
        const xMin = -(w - 1) * bucket / 2;
        const zMin = -(h - 1) * bucket / 2;
        const xMax = (w - 1) * bucket / 2;
        const zMax = (h - 1) * bucket / 2;
        colNorm = (worldX - xMin) / (xMax - xMin);
        rowNorm = (worldZ - zMin) / (zMax - zMin);
    } else if (params.renderMode === 'points') {
        const xMin = -(w - 1) / 2;
        const zMin = -(h - 1) / 2;
        const xMax = (w - 1) / 2;
        const zMax = (h - 1) / 2;
        colNorm = (worldX - xMin) / (xMax - xMin);
        rowNorm = (worldZ - zMin) / (zMax - zMin);
    } else {
        // surface
        colNorm = (worldX + w / 2) / (w);
        rowNorm = (worldZ + h / 2) / (h);
    }
    colNorm = Math.max(0, Math.min(1, colNorm));
    rowNorm = Math.max(0, Math.min(1, rowNorm));
    const lon = elevBounds.left + colNorm * (elevBounds.right - elevBounds.left);
    const lat = elevBounds.top - rowNorm * (elevBounds.top - elevBounds.bottom);
    return { lon, lat };
}

/**
 * Convert world coordinates to grid indices (row, column)
 * Depends on globals: processedData, params, terrainMesh
 * 
 * @param {number} worldX - World space X coordinate
 * @param {number} worldZ - World space Z coordinate
 * @returns {Object|null} Grid indices { i: row, j: column }
 */
function worldToGridIndex(worldX, worldZ) {
    if (!processedData) return null;
    const w = processedData.width;
    const h = processedData.height;
    if (params.renderMode === 'bars') {
        const bucket = params.bucketSize;
        const originX = terrainMesh ? terrainMesh.position.x : -(w - 1) * bucket / 2;
        const originZ = terrainMesh ? terrainMesh.position.z : -(h - 1) * bucket / 2;
        let j = Math.round((worldX - originX) / bucket);
        let i = Math.round((worldZ - originZ) / bucket);
        i = Math.max(0, Math.min(h - 1, i));
        j = Math.max(0, Math.min(w - 1, j));
        return { i, j };
    } else if (params.renderMode === 'points') {
        const bucket = 1;
        const originX = terrainMesh ? terrainMesh.position.x : -(w - 1) * bucket / 2;
        const originZ = terrainMesh ? terrainMesh.position.z : -(h - 1) * bucket / 2;
        let j = Math.round((worldX - originX) / bucket);
        let i = Math.round((worldZ - originZ) / bucket);
        i = Math.max(0, Math.min(h - 1, i));
        j = Math.max(0, Math.min(w - 1, j));
        return { i, j };
    } else {
        // Surface centered at origin, each vertex spaced 1 unit
        let j = Math.round(worldX + w / 2);
        let i = Math.round(worldZ + h / 2);
        i = Math.max(0, Math.min(h - 1, i));
        j = Math.max(0, Math.min(w - 1, j));
        return { i, j };
    }
}

/**
 * Get meters per world unit scale factors
 * Depends on globals: processedData, params
 * 
 * @returns {Object} Scale factors { mx: meters per X unit, mz: meters per Z unit }
 */
function getMetersScalePerWorldUnit() {
    if (!processedData) return { mx: 1, mz: 1 };

    if (params.renderMode === 'bars') {
        const mx = (processedData.bucketSizeMetersX || 1) / (params.bucketSize || 1);
        const mz = (processedData.bucketSizeMetersY || 1) / (params.bucketSize || 1);
        return { mx, mz };
    } else {
        const mx = processedData.bucketSizeMetersX || 1;
        const mz = processedData.bucketSizeMetersY || 1;
        return { mx, mz };
    }
}

/**
 * Calculate distance from point to line segment (2D)
 * Pure function - no globals
 * 
 * @param {number} px - Point X coordinate
 * @param {number} pz - Point Z coordinate
 * @param {number} ax - Segment start X
 * @param {number} az - Segment start Z
 * @param {number} bx - Segment end X
 * @param {number} bz - Segment end Z
 * @returns {number} Distance from point to segment
 */
function distancePointToSegment2D(px, pz, ax, az, bx, bz) {
    const vx = bx - ax;
    const vz = bz - az;
    const wx = px - ax;
    const wz = pz - az;
    const c1 = vx * wx + vz * wz;
    if (c1 <= 0) return Math.hypot(px - ax, pz - az);
    const c2 = vx * vx + vz * vz;
    if (c2 <= c1) return Math.hypot(px - bx, pz - bz);
    const t = c1 / c2;
    const projx = ax + t * vx;
    const projz = az + t * vz;
    return Math.hypot(px - projx, pz - projz);
}

/**
 * Check if world coordinates are inside the data bounds
 * Depends on globals: processedData, params
 * 
 * @param {number} worldX - World space X coordinate
 * @param {number} worldZ - World space Z coordinate
 * @returns {boolean} True if inside data bounds
 */
function isWorldInsideData(worldX, worldZ) {
    if (!processedData) return false;
    const w = processedData.width;
    const h = processedData.height;
    let xMin, xMax, zMin, zMax;
    if (params.renderMode === 'bars') {
        const bucket = params.bucketSize;
        xMin = -(w - 1) * bucket / 2; xMax = (w - 1) * bucket / 2;
        zMin = -(h - 1) * bucket / 2; zMax = (h - 1) * bucket / 2;
    } else if (params.renderMode === 'points') {
        xMin = -(w - 1) / 2; xMax = (w - 1) / 2;
        zMin = -(h - 1) / 2; zMax = (h - 1) / 2;
    } else {
        xMin = -w / 2; xMax = w / 2;
        zMin = -h / 2; zMax = h / 2;
    }
    return (worldX >= xMin && worldX <= xMax && worldZ >= zMin && worldZ <= zMax);
}

// Export to window for global access
window.GeometryUtils = {
    calculateRealWorldScale,
    raycastToWorld,
    worldToLonLat,
    worldToGridIndex,
    getMetersScalePerWorldUnit,
    distancePointToSegment2D,
    isWorldInsideData
};

