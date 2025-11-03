/**
 * US State Connectivity Module
 * 
 * Displays neighboring states near compass direction markers.
 * Only applies to US states.
 */

// Global state adjacency data (loaded from JSON)
let stateAdjacencyData = null;

// Track connectivity UI elements
let connectivityLabels = [];

/**
 * Load state adjacency data from JSON file
 */
async function loadStateAdjacency() {
    try {
        const response = await fetch('generated/us_state_adjacency.json');
        if (!response.ok) {
            console.warn('State adjacency data not available');
            return null;
        }
        stateAdjacencyData = await response.json();
        console.log('Loaded state adjacency data');
        return stateAdjacencyData;
    } catch (error) {
        console.warn('Failed to load state adjacency data:', error);
        return null;
    }
}

/**
 * Check if a region is a US state
 */
function isUSState(regionId) {
    if (!regionsManifest || !regionsManifest.regions) return false;
    const regionInfo = regionsManifest.regions[regionId];
    return regionInfo && regionInfo.category === 'usa_state';
}

/**
 * Get neighbors for a state in a given direction
 */
function getNeighborsInDirection(stateId, direction) {
    if (!stateAdjacencyData || !stateAdjacencyData[stateId]) return [];
    return stateAdjacencyData[stateId][direction] || [];
}

/**
 * Create a clickable neighbor label sprite
 */
function createNeighborLabel(neighborName, neighborId, color, onClick) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    canvas.width = 512;
    canvas.height = 128;

    // Draw semi-transparent background
    context.fillStyle = 'rgba(0, 0, 0, 0.75)';
    context.fillRect(0, 0, canvas.width, canvas.height);

    // Draw border with direction color
    context.strokeStyle = `#${color.toString(16).padStart(6, '0')}`;
    context.lineWidth = 3;
    context.strokeRect(0, 0, canvas.width, canvas.height);

    // Draw text
    context.font = 'Bold 48px Arial';
    context.fillStyle = '#ffffff';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(neighborName, canvas.width / 2, canvas.height / 2);

    const texture = new THREE.CanvasTexture(canvas);
    const spriteMaterial = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthTest: false,
        depthWrite: false
    });
    const sprite = new THREE.Sprite(spriteMaterial);
    
    // Store metadata for click handling
    sprite.userData.neighborId = neighborId;
    sprite.userData.neighborName = neighborName;
    sprite.userData.isConnectivityLabel = true;
    sprite.userData.onClick = onClick;

    return sprite;
}

/**
 * Position labels for a given direction
 */
function positionLabelsForDirection(direction, neighbors, baseX, baseZ, xExtent, zExtent, avgSize) {
    const labels = [];
    const labelSpacing = avgSize * 0.15; // Space between labels
    const offsetFromEdge = avgSize * 0.25; // Distance from edge marker
    
    // Calculate starting position for stacked labels
    const totalHeight = (neighbors.length - 1) * labelSpacing;
    let currentOffset = -totalHeight / 2;

    neighbors.forEach((neighbor, index) => {
        const color = getColorForDirection(direction);
        const sprite = createNeighborLabel(neighbor.name, neighbor.id, color, () => {
            // Click handler: load the neighbor state
            if (neighbor.id && neighbor.id !== currentRegionId) {
                loadRegion(neighbor.id);
            }
        });

        // Position based on direction
        let x = baseX;
        let z = baseZ;
        let y = currentOffset;

        // Adjust position based on direction
        switch(direction) {
            case 'N':
                z -= offsetFromEdge;
                break;
            case 'S':
                z += offsetFromEdge;
                break;
            case 'E':
                x += offsetFromEdge;
                break;
            case 'W':
                x -= offsetFromEdge;
                break;
            case 'NE':
                x += offsetFromEdge * 0.7;
                z -= offsetFromEdge * 0.7;
                break;
            case 'NW':
                x -= offsetFromEdge * 0.7;
                z -= offsetFromEdge * 0.7;
                break;
            case 'SE':
                x += offsetFromEdge * 0.7;
                z += offsetFromEdge * 0.7;
                break;
            case 'SW':
                x -= offsetFromEdge * 0.7;
                z += offsetFromEdge * 0.7;
                break;
        }

        sprite.position.set(x, y, z);

        // Scale based on terrain size
        const baseScale = avgSize * 0.08;
        sprite.scale.set(baseScale * 4, baseScale, baseScale); // Wide aspect ratio

        labels.push(sprite);
        currentOffset += labelSpacing;
    });

    return labels;
}

/**
 * Get color for a direction (matches edge marker colors)
 */
function getColorForDirection(direction) {
    const directionColors = {
        'N': 0xff4444,  // Red
        'S': 0x4488ff,  // Blue
        'E': 0x44ff44,  // Green
        'W': 0xffff44,  // Yellow
        'NE': 0xff8844, // Orange (blend of N and E)
        'NW': 0xffaa44, // Yellow-orange (blend of N and W)
        'SE': 0x44ffaa, // Cyan-green (blend of S and E)
        'SW': 0x88aaff  // Light blue (blend of S and W)
    };
    return directionColors[direction] || 0xffffff;
}

/**
 * Create connectivity labels for the current region
 */
function createConnectivityLabels() {
    // Remove old labels
    connectivityLabels.forEach(label => scene.remove(label));
    connectivityLabels = [];

    // Only show for US states
    if (!currentRegionId || !isUSState(currentRegionId)) {
        return;
    }

    if (!stateAdjacencyData || !stateAdjacencyData[currentRegionId]) {
        console.log(`No adjacency data for ${currentRegionId}`);
        return;
    }

    if (!rawElevationData || !processedData) return;

    const gridWidth = processedData.width;
    const gridHeight = processedData.height;

    // Calculate extents (same logic as createEdgeMarkers)
    let xExtent, zExtent, avgSize;
    if (params.renderMode === 'bars') {
        const bucketMultiplier = params.bucketSize;
        xExtent = (gridWidth - 1) * bucketMultiplier / 2;
        zExtent = (gridHeight - 1) * bucketMultiplier / 2;
        avgSize = (xExtent + zExtent);
    } else if (params.renderMode === 'points') {
        const bucketSize = params.bucketSize;
        xExtent = (gridWidth - 1) * bucketSize / 2;
        zExtent = (gridHeight - 1) * bucketSize / 2;
        avgSize = (xExtent + zExtent);
    } else {
        const bucketMultiplier = params.bucketSize;
        xExtent = (gridWidth * bucketMultiplier) / 2;
        zExtent = (gridHeight * bucketMultiplier) / 2;
        avgSize = (gridWidth * bucketMultiplier + gridHeight * bucketMultiplier) / 2;
    }

    // Define base positions for each direction (matching edge markers)
    const directionPositions = {
        'N': { x: 0, z: -zExtent },
        'S': { x: 0, z: zExtent },
        'E': { x: xExtent, z: 0 },
        'W': { x: -xExtent, z: 0 },
        'NE': { x: xExtent * 0.7, z: -zExtent * 0.7 },
        'NW': { x: -xExtent * 0.7, z: -zExtent * 0.7 },
        'SE': { x: xExtent * 0.7, z: zExtent * 0.7 },
        'SW': { x: -xExtent * 0.7, z: zExtent * 0.7 }
    };

    // Create labels for each direction that has neighbors
    const stateNeighbors = stateAdjacencyData[currentRegionId];
    for (const [direction, neighbors] of Object.entries(stateNeighbors)) {
        if (neighbors.length === 0) continue;
        
        const pos = directionPositions[direction];
        if (!pos) continue;

        const labels = positionLabelsForDirection(
            direction, 
            neighbors, 
            pos.x, 
            pos.z, 
            xExtent, 
            zExtent, 
            avgSize
        );

        labels.forEach(label => {
            scene.add(label);
            connectivityLabels.push(label);
        });
    }

    console.log(`Created ${connectivityLabels.length} connectivity labels for ${currentRegionId}`);
}

/**
 * Update connectivity label positions (called when terrain changes)
 */
function updateConnectivityLabels() {
    // Just recreate them - simpler than trying to update positions
    createConnectivityLabels();
}

/**
 * Handle clicks on connectivity labels
 */
function handleConnectivityClick(intersectedObject) {
    if (intersectedObject.userData.isConnectivityLabel && intersectedObject.userData.onClick) {
        intersectedObject.userData.onClick();
        return true;
    }
    return false;
}



