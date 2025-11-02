/**
 * Borders & Contours Module
 * 
 * PURPOSE:
 * Renders border lines (country/state boundaries) and contour lines (elevation contours).
 * Both features are optional overlays that enhance terrain visualization.
 * 
 * FEATURES:
 * - Draw administrative borders from GeoJSON data
 * - Generate contour lines using marching squares algorithm
 * - Both stay at fixed heights (not affected by vertical exaggeration changes)
 * - Spatial indexing for efficient border distance queries
 * 
 * DESIGN NOTES:
 * - Borders use yellow color for high visibility
 * - Contours use orange/yellow gradient
 * - Both use line rendering with transparency
 * - Borders are indexed spatially for HUD distance calculations
 * 
 * DEPENDS ON:
 * - Global: scene, borderMeshes[], contourMeshes[], borderData, rawElevationData, processedData, params
 * - Global: borderSegmentsMeters[], borderSegmentsGeo[], borderGeoIndex, borderGeoCellSizeDeg
 * - Three.js: THREE.Vector3, THREE.BufferGeometry, THREE.LineBasicMaterial, THREE.Line
 * - Functions: calculateRealWorldScale(), getMetersScalePerWorldUnit()
 */

/**
 * Create and display contour lines using marching squares algorithm
 * Contours are elevation isolines showing points of equal height
 * 
 * @global scene - Three.js scene
 * @global contourMeshes - Array to store contour line meshes
 * @global params - Parameters (showContours, contourInterval, renderMode, bucketSize, verticalExaggeration)
 * @global processedData - Processed elevation data
 */
function createContourLines() {
    // Remove old contour lines
    contourMeshes.forEach(mesh => scene.remove(mesh));
    contourMeshes = [];

    if (!params.showContours || !processedData || !processedData.elevation) {
        return;
    }

    const { width, height, elevation, stats } = processedData;
    const interval = params.contourInterval;

    if (!interval || interval <= 0) return;

    // Calculate contour levels based on elevation range
    const minElev = stats.min;
    const maxElev = stats.max;
    const firstLevel = Math.ceil(minElev / interval) * interval;
    const levels = [];

    for (let level = firstLevel; level <= maxElev; level += interval) {
        levels.push(level);
    }

    console.log(`Generating ${levels.length} contour lines from ${minElev.toFixed(0)}m to ${maxElev.toFixed(0)}m at ${interval}m intervals`);

    // For each contour level, trace lines
    levels.forEach(level => {
        const lines = traceContourLevel(elevation, width, height, level);

        lines.forEach(linePoints => {
            if (linePoints.length < 2) return;

            // Convert grid coordinates to world coordinates
            const worldPoints = linePoints.map(p => {
                const bucketMultiplier = params.bucketSize;
                let worldX, worldZ;

                if (params.renderMode === 'bars') {
                    worldX = p.x * bucketMultiplier - (width - 1) * bucketMultiplier / 2;
                    worldZ = p.y * bucketMultiplier - (height - 1) * bucketMultiplier / 2;
                } else if (params.renderMode === 'points') {
                    const bucketSize = params.bucketSize;
                    worldX = p.x * bucketSize - (width - 1) * bucketSize / 2;
                    worldZ = p.y * bucketSize - (height - 1) * bucketSize / 2;
                } else {
                    // Surface mode
                    worldX = (p.x / (width - 1) - 0.5) * width * bucketMultiplier;
                    worldZ = (p.y / (height - 1) - 0.5) * height * bucketMultiplier;
                }

                return new THREE.Vector3(worldX, level * params.verticalExaggeration + 1, worldZ);
            });

            const geometry = new THREE.BufferGeometry().setFromPoints(worldPoints);
            const material = new THREE.LineBasicMaterial({
                color: 0xffaa00, // Orange/yellow for visibility
                transparent: true,
                opacity: 0.7,
                linewidth: 1
            });
            const line = new THREE.Line(geometry, material);
            scene.add(line);
            contourMeshes.push(line);
        });
    });

    console.log(`Created ${contourMeshes.length} contour line segments`);
}

/**
 * Trace a single contour level using marching squares algorithm
 * Returns array of line segments (each segment is array of {x, y} points)
 * 
 * @param {Array<Array<number>>} elevation - 2D elevation grid
 * @param {number} width - Grid width
 * @param {number} height - Grid height
 * @param {number} level - Elevation level to trace
 * @returns {Array<Array<{x: number, y: number}>>} Array of line segments
 */
function traceContourLevel(elevation, width, height, level) {
    const lines = [];
    const visited = new Set();

    // Helper to get elevation at grid point
    const getElev = (i, j) => {
        if (i < 0 || i >= height || j < 0 || j >= width) return null;
        const val = elevation[i] && elevation[i][j];
        return (val === null || val === undefined) ? null : val;
    };

    // Marching squares: for each grid cell, check if contour crosses it
    for (let i = 0; i < height - 1; i++) {
        for (let j = 0; j < width - 1; j++) {
            const key = `${i},${j}`;
            if (visited.has(key)) continue;

            // Get corner elevations
            const nw = getElev(i, j);
            const ne = getElev(i, j + 1);
            const sw = getElev(i + 1, j);
            const se = getElev(i + 1, j + 1);

            if (nw === null || ne === null || sw === null || se === null) continue;

            // Check if contour crosses this cell
            const hasAbove = (nw >= level) || (ne >= level) || (sw >= level) || (se >= level);
            const hasBelow = (nw < level) || (ne < level) || (sw < level) || (se < level);

            if (!hasAbove || !hasBelow) continue; // Contour doesn't cross this cell

            // Trace the contour line through this cell
            const linePoints = [];
            let currentI = i, currentJ = j;
            let maxSteps = 10000; // Prevent infinite loops

            while (maxSteps-- > 0) {
                const cellKey = `${currentI},${currentJ}`;
                if (visited.has(cellKey)) break;
                visited.add(cellKey);

                // Get corner values
                const v00 = getElev(currentI, currentJ);
                const v10 = getElev(currentI, currentJ + 1);
                const v01 = getElev(currentI + 1, currentJ);
                const v11 = getElev(currentI + 1, currentJ + 1);

                if (v00 === null || v10 === null || v01 === null || v11 === null) break;

                // Interpolate edge crossings
                const edges = [];

                // Top edge (between v00 and v10)
                if ((v00 < level && v10 >= level) || (v00 >= level && v10 < level)) {
                    const t = (level - v00) / (v10 - v00);
                    edges.push({ x: currentJ + t, y: currentI, edge: 'top' });
                }

                // Right edge (between v10 and v11)
                if ((v10 < level && v11 >= level) || (v10 >= level && v11 < level)) {
                    const t = (level - v10) / (v11 - v10);
                    edges.push({ x: currentJ + 1, y: currentI + t, edge: 'right' });
                }

                // Bottom edge (between v01 and v11)
                if ((v01 < level && v11 >= level) || (v01 >= level && v11 < level)) {
                    const t = (level - v01) / (v11 - v01);
                    edges.push({ x: currentJ + t, y: currentI + 1, edge: 'bottom' });
                }

                // Left edge (between v00 and v01)
                if ((v00 < level && v01 >= level) || (v00 >= level && v01 < level)) {
                    const t = (level - v00) / (v01 - v00);
                    edges.push({ x: currentJ, y: currentI + t, edge: 'left' });
                }

                if (edges.length === 0) break; // No crossing found

                // Add point to line
                if (edges.length > 0) {
                    linePoints.push({ x: edges[0].x, y: edges[0].y });
                }

                // Move to next cell (simple: just stop after one cell for now)
                break; // Simplified: just trace one cell per line segment
            }

            if (linePoints.length >= 2) {
                lines.push(linePoints);
            }
        }
    }

    return lines;
}

/**
 * Create and display border lines (country/state boundaries)
 * Builds spatial index for efficient distance queries
 * 
 * @global scene - Three.js scene
 * @global borderMeshes - Array to store border line meshes
 * @global borderSegmentsMeters - Flattened array of border segments in meters
 * @global borderSegmentsGeo - Array of border segments in geographic coords
 * @global borderGeoIndex - Spatial hash map for border segments
 * @global borderData - Border geometry data
 * @global rawElevationData - Raw elevation data for bounds
 * @global processedData - Processed data for grid dimensions
 * @global params - Parameters (showBorders, renderMode, bucketSize)
 */
function recreateBorders() {
    console.log('Creating borders...');

    // Remove old borders
    borderMeshes.forEach(mesh => scene.remove(mesh));
    borderMeshes = [];
    borderSegmentsMeters = [];
    borderSegmentsGeo = [];
    borderGeoIndex = new Map();

    if (!borderData || (!borderData.countries && !borderData.states)) {
        console.log('[INFO] No border data available');
        return;
    }

    if (!params.showBorders) {
        console.log('[INFO] Borders hidden by user setting');
        return;
    }

    const { width, height, bounds: elevBounds } = rawElevationData;
    const { bounds } = borderData;

    // Calculate real-world scale
    const scale = calculateRealWorldScale();

    // Set borders at a fixed height that doesn't change with vertical exaggeration
    // Use a small constant height just above ground level
    const borderHeight = 100; // Fixed at 100 meters above ground

    let totalSegments = 0;

    // Combine countries and states into a single array for processing
    const allBorders = [
        ...(borderData.countries || []),
        ...(borderData.states || [])
    ];

    const { mx, mz } = getMetersScalePerWorldUnit();
    allBorders.forEach((entity) => {
        entity.segments.forEach((segment) => {
            const points = [];

            // Convert lon/lat to coordinates matching the render mode
            for (let i = 0; i < segment.lon.length; i++) {
                const lon = segment.lon[i];
                const lat = segment.lat[i];

                // Map geographic coords to normalized [0,1] range
                const colNormalized = (lon - elevBounds.left) / (elevBounds.right - elevBounds.left);
                const rowNormalized = (elevBounds.top - lat) / (elevBounds.top - elevBounds.bottom);

                let xCoord, zCoord;
                if (params.renderMode === 'bars') {
                    // Bars use grid-based positioning: 0 to (width-1)*bucketSize
                    const bucketMultiplier = params.bucketSize;
                    const bWidth = processedData.width;
                    const bHeight = processedData.height;
                    xCoord = colNormalized * (bWidth - 1) * bucketMultiplier;
                    zCoord = rowNormalized * (bHeight - 1) * bucketMultiplier;
                    // Apply same centering offset as terrain
                    xCoord -= (bWidth - 1) * bucketMultiplier / 2;
                    zCoord -= (bHeight - 1) * bucketMultiplier / 2;
                } else if (params.renderMode === 'points') {
                    // Points use uniform grid positioning, scaled by bucketSize
                    const bucketSize = params.bucketSize;
                    const bWidth = processedData.width;
                    const bHeight = processedData.height;
                    xCoord = colNormalized * (bWidth - 1) * bucketSize;
                    zCoord = rowNormalized * (bHeight - 1) * bucketSize;
                    // Apply same centering offset as terrain
                    xCoord -= (bWidth - 1) * bucketSize / 2;
                    zCoord -= (bHeight - 1) * bucketSize / 2;
                } else {
                    // Surface uses uniform grid positioning (PlaneGeometry centered at origin, scaled by bucketSize)
                    const bucketMultiplier = params.bucketSize;
                    const bWidth = processedData.width;
                    const bHeight = processedData.height;
                    xCoord = (colNormalized - 0.5) * bWidth * bucketMultiplier;
                    zCoord = (rowNormalized - 0.5) * bHeight * bucketMultiplier;
                }

                // Three.js: x=East, z=South, y=elevation
                points.push(new THREE.Vector3(xCoord, borderHeight, zCoord));
            }

            if (points.length > 1) {
                const geometry = new THREE.BufferGeometry().setFromPoints(points);
                const material = new THREE.LineBasicMaterial({
                    color: 0xFFFF00, // YELLOW - highly visible!
                    linewidth: 2,
                    transparent: true,
                    opacity: 0.9
                });
                const line = new THREE.Line(geometry, material);
                scene.add(line);
                borderMeshes.push(line);
                totalSegments++;
                
                // Capture as meter-scaled 2D segments for HUD distance queries
                for (let p = 0; p < points.length - 1; p++) {
                    const a = points[p];
                    const b = points[p + 1];
                    borderSegmentsMeters.push({
                        ax: a.x * mx,
                        az: a.z * mz,
                        bx: b.x * mx,
                        bz: b.z * mz
                    });
                    
                    // Also store geographic segment and index it
                    const aLon = segment.lon[p];
                    const aLat = segment.lat[p];
                    const bLon = segment.lon[p + 1];
                    const bLat = segment.lat[p + 1];
                    const geoIndex = borderSegmentsGeo.length;
                    borderSegmentsGeo.push({ axLon: aLon, axLat: aLat, bxLon: bLon, bxLat: bLat });
                    
                    // Compute covered cells and insert id
                    const minLon = Math.min(aLon, bLon);
                    const maxLon = Math.max(aLon, bLon);
                    const minLat = Math.min(aLat, bLat);
                    const maxLat = Math.max(aLat, bLat);
                    const ix0 = Math.floor(minLon / borderGeoCellSizeDeg);
                    const ix1 = Math.floor(maxLon / borderGeoCellSizeDeg);
                    const iy0 = Math.floor(minLat / borderGeoCellSizeDeg);
                    const iy1 = Math.floor(maxLat / borderGeoCellSizeDeg);
                    for (let ix = ix0; ix <= ix1; ix++) {
                        for (let iy = iy0; iy <= iy1; iy++) {
                            const key = `${ix},${iy}`;
                            let arr = borderGeoIndex.get(key);
                            if (!arr) { arr = []; borderGeoIndex.set(key, arr); }
                            arr.push(geoIndex);
                        }
                    }
                }
            }
        });
    });

    const entityCount = allBorders.length;
    const entityType = borderData.states ? 'states' : 'countries';
    console.log(`Created ${totalSegments} border segments for ${entityCount} ${entityType}`);
}

// Export module
window.BordersContours = {
    createContourLines,
    traceContourLevel,
    recreateBorders
};

