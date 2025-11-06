/**
 * Region Connectivity Module
 * 
 * Displays navigable relationships between all region types:
 * - Adjacent regions: N, S, E, W (cardinal directions only)
 * - Contained areas: AREA regions within states/countries (center, purple)
 * - Parent regions: States/countries containing this AREA (center, cyan)
 * 
 * Provides full bidirectional navigation across the entire region graph.
 */

// RegionType enum - must match src/types.py RegionType enum
const RegionType = {
    USA_STATE: 'usa_state',
    COUNTRY: 'country',
    AREA: 'area'
};

// Global state adjacency data (loaded from JSON)
let stateAdjacencyData = null;

// Track connectivity UI elements (globally accessible for click detection)
window.connectivityLabels = [];
const connectivityLabels = window.connectivityLabels; // Alias for convenience

/**
 * Load state adjacency data from JSON file
 */
async function loadStateAdjacency() {
    try {
        const gzUrl = 'generated/us_state_adjacency.json.gz';
        const response = await fetch(gzUrl);

        if (!response.ok) {
            console.warn('State adjacency data not available');
            return null;
        }

        const arrayBuffer = await response.arrayBuffer();
        const stream = new DecompressionStream('gzip');
        const writer = stream.writable.getWriter();
        writer.write(new Uint8Array(arrayBuffer));
        writer.close();
        const decompressedResponse = new Response(stream.readable);
        const text = await decompressedResponse.text();
        stateAdjacencyData = JSON.parse(text);
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
    if (!regionInfo) return false;
    return regionInfo.regionType === RegionType.USA_STATE;
}

/**
 * Get neighbors for a state in a given direction
 */
function getNeighborsInDirection(stateId, direction) {
    if (!stateAdjacencyData || !stateAdjacencyData[stateId]) return [];
    return stateAdjacencyData[stateId][direction] || [];
}

/**
 * Create a clickable neighbor label sprite (smaller, for display below direction markers)
 */
function createNeighborLabel(neighborName, neighborId, color, onClick) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    canvas.width = 384;
    canvas.height = 80;

    // Draw semi-transparent background
    context.fillStyle = 'rgba(0, 0, 0, 0.7)';
    context.fillRect(0, 0, canvas.width, canvas.height);

    // Draw border with direction color
    context.strokeStyle = `#${color.toString(16).padStart(6, '0')}`;
    context.lineWidth = 2;
    context.strokeRect(0, 0, canvas.width, canvas.height);

    // Draw text (smaller font)
    context.font = 'Bold 32px Arial';
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
    
    // Ensure sprite is visible and raycastable
    sprite.visible = true;
    sprite.frustumCulled = false; // Always render regardless of camera position
    
    // Store metadata for click handling
    sprite.userData.neighborId = neighborId;
    sprite.userData.neighborName = neighborName;
    sprite.userData.isConnectivityLabel = true;
    sprite.userData.onClick = onClick;

    return sprite;
}

/**
 * Position labels for a given direction (below edge markers)
 */
function positionLabelsForDirection(direction, neighbors, baseX, baseZ, xExtent, zExtent, avgSize) {
    const labels = [];
    const baseScale = avgSize * 0.045; // Slightly larger for readability
    const labelHeight = baseScale; 
    const labelSpacing = labelHeight * 2.5; // More vertical space between labels
    
    // Position labels clearly BELOW the direction letter
    // Direction letter is at ground level (y=0), so we go negative
    const verticalStartOffset = -avgSize * 0.12; // Start lower
    const totalHeight = (neighbors.length - 1) * labelSpacing;
    let yOffset = verticalStartOffset - totalHeight / 2;

    neighbors.forEach((neighbor, index) => {
        const color = getColorForDirection(direction);
        const sprite = createNeighborLabel(neighbor.name, neighbor.id, color, () => {
            // Click handler: load the neighbor state
            if (neighbor.id && neighbor.id !== currentRegionId) {
                loadRegion(neighbor.id);
            }
        });

        // Position at same XZ as direction marker, but below (negative Y)
        let x = baseX;
        let z = baseZ;
        let y = yOffset;

        sprite.position.set(x, y, z);

        // Scale for labels - wider for readability
        sprite.scale.set(baseScale * 5, baseScale * 1.0, baseScale);

        labels.push(sprite);
        yOffset += labelSpacing; // Stack downward
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
        'W': 0xffff44   // Yellow
    };
    return directionColors[direction] || 0xffffff;
}

/**
 * Create labels for contained AREA regions (displayed in center of map)
 */
function createContainedAreaLabels(containedData, avgSize) {
    // Handle both single and multiple contained areas
    const rawIds = Array.isArray(containedData) ? containedData : [containedData];
    
    // Filter valid areas
    const validAreas = rawIds
        .filter(id => regionsManifest && regionsManifest.regions && regionsManifest.regions[id])
        .map(id => ({
            id: id,
            name: regionIdToName[id] || id
        }));

    if (validAreas.length === 0) return;

    // Position contained areas in the center of the map
    const baseScale = avgSize * 0.05; // Slightly larger for visibility
    const labelHeight = baseScale;
    const labelSpacing = labelHeight * 2.5;
    const totalHeight = (validAreas.length - 1) * labelSpacing;
    let yOffset = totalHeight / 2; // Start from top and go down

    validAreas.forEach((area, index) => {
        const color = 0xff88ff; // Purple/magenta for contained areas
        const sprite = createNeighborLabel(area.name, area.id, color, () => {
            // Click handler: load the contained area
            if (area.id && area.id !== currentRegionId) {
                loadRegion(area.id);
            }
        });

        // Position at center of map, slightly elevated
        sprite.position.set(0, yOffset + avgSize * 0.15, 0);

        // Scale for readability
        sprite.scale.set(baseScale * 5, baseScale * 1.0, baseScale);

        scene.add(sprite);
        connectivityLabels.push(sprite);
        
        yOffset -= labelSpacing; // Stack downward
    });

    console.log(`[Connectivity] Added ${validAreas.length} contained area labels`);
}

/**
 * Create labels for "within" relationships (AREA regions showing their parent regions)
 */
function createWithinLabels(withinData, avgSize) {
    // Handle both single and multiple parent regions
    const rawIds = Array.isArray(withinData) ? withinData : [withinData];
    
    // Filter valid parent regions
    const validParents = rawIds
        .filter(id => regionsManifest && regionsManifest.regions && regionsManifest.regions[id])
        .map(id => ({
            id: id,
            name: regionIdToName[id] || id
        }));

    if (validParents.length === 0) return;

    // Position "within" labels in the center, below the terrain
    const baseScale = avgSize * 0.05;
    const labelHeight = baseScale;
    const labelSpacing = labelHeight * 2.5;
    const totalHeight = (validParents.length - 1) * labelSpacing;
    let yOffset = -totalHeight / 2 - avgSize * 0.20; // Below center

    validParents.forEach((parent, index) => {
        const color = 0x44ffff; // Cyan for parent/container regions
        const sprite = createNeighborLabel(parent.name, parent.id, color, () => {
            // Click handler: load the parent region
            if (parent.id && parent.id !== currentRegionId) {
                loadRegion(parent.id);
            }
        });

        // Position at center of map, below terrain
        sprite.position.set(0, yOffset, 0);

        // Scale for readability
        sprite.scale.set(baseScale * 5, baseScale * 1.0, baseScale);

        scene.add(sprite);
        connectivityLabels.push(sprite);
        
        yOffset -= labelSpacing; // Stack downward
    });

    console.log(`[Connectivity] Added ${validParents.length} "within" labels`);
}

/**
 * Create connectivity labels for the current region
 * 
 * Displays clickable navigation labels:
 * - Cardinal directions (N/S/E/W): Below edge markers - adjacent regions
 * - "Contained" (purple): Center, above terrain - AREA regions within this region
 * - "Within" (cyan): Center, below terrain - Parent regions containing this AREA
 * 
 * Provides full bidirectional navigation between all region types.
 */
function createConnectivityLabels() {
    // Remove old labels
    connectivityLabels.forEach(label => scene.remove(label));
    connectivityLabels.length = 0; // Clear array while keeping reference

    // Only show for regions with adjacency data
    if (!currentRegionId) return;
    
    // Get neighbors from regionAdjacency (unified system for all region types)
    const neighbors = currentRegionId && regionAdjacency && regionAdjacency[currentRegionId];
    if (!neighbors) return;

    if (!rawElevationData || !processedData) return;

    const gridWidth = processedData.width;
    const gridHeight = processedData.height;

    // Calculate extents - only bars mode is supported
    const bucketMultiplier = params.bucketSize;
    const xExtent = (gridWidth - 1) * bucketMultiplier / 2;
    const zExtent = (gridHeight - 1) * bucketMultiplier / 2;
    const avgSize = (xExtent + zExtent);

    // Spread multiplier matches edge markers
    const spreadMultiplier = 1.25;

    // Define base positions for each cardinal direction (matching edge markers exactly)
    const directionPositions = {
        'north': { x: 0, z: -zExtent * spreadMultiplier },
        'south': { x: 0, z: zExtent * spreadMultiplier },
        'east': { x: xExtent * spreadMultiplier, z: 0 },
        'west': { x: -xExtent * spreadMultiplier, z: 0 }
    };

    // Direction mapping from full names to letters
    const directionLetters = {
        'north': 'N',
        'south': 'S',
        'east': 'E',
        'west': 'W'
    };

    // Create labels for each direction that has neighbors
    for (const [direction, neighborData] of Object.entries(neighbors)) {
        if (!neighborData) continue;
        
        // Handle contained areas separately (displayed in center, above)
        if (direction === 'contained') {
            createContainedAreaLabels(neighborData, avgSize);
            continue;
        }
        
        // Handle within relationships separately (displayed in center, below)
        if (direction === 'within') {
            createWithinLabels(neighborData, avgSize);
            continue;
        }
        
        const pos = directionPositions[direction];
        const letter = directionLetters[direction];
        if (!pos || !letter) continue;

        // Handle both single neighbor (string) and multiple neighbors (array)
        const rawIds = Array.isArray(neighborData) ? neighborData : [neighborData];
        
        // Filter out neighbors that don't exist in manifest
        const validNeighbors = rawIds
            .filter(id => regionsManifest && regionsManifest.regions && regionsManifest.regions[id])
            .map(id => ({
                id: id,
                name: regionIdToName[id] || id
            }));

        if (validNeighbors.length === 0) continue;

        const labels = positionLabelsForDirection(
            letter,  // Pass single letter ('N', 'S', 'E', 'W')
            validNeighbors, 
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

    console.log(`[Connectivity] Created ${connectivityLabels.length} labels for ${currentRegionId}`);
}

/**
 * Update connectivity label positions (called when terrain changes)
 */
function updateConnectivityLabels() {
    // Recreate labels with new positions
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



