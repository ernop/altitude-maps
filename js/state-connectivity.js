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
 * Create a clickable neighbor label sprite (compact, for display below direction markers)
 */
function createNeighborLabel(neighborName, neighborId, onClick) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    
    const fontSize = 28;
    const padding = 8; // Minimal padding - matches top/bottom
    
    // Measure text to determine canvas width
    context.font = `Bold ${fontSize}px Arial`;
    const textMetrics = context.measureText(neighborName);
    const textWidth = textMetrics.width;
    
    // Canvas size based on text width + minimal padding
    canvas.width = Math.ceil(textWidth + padding * 2);
    canvas.height = 64;

    // Draw semi-transparent bluish background (matches navigation panel)
    context.fillStyle = 'rgba(20, 40, 60, 0.85)';
    context.fillRect(0, 0, canvas.width, canvas.height);

    // Draw subtle border
    context.strokeStyle = 'rgba(255, 255, 255, 0.3)';
    context.lineWidth = 1;
    context.strokeRect(0, 0, canvas.width, canvas.height);

    // Draw text - need to set font again after canvas resize
    context.font = `Bold ${fontSize}px Arial`;
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
    sprite.renderOrder = 200; // Render after compass markers (which use 100)
    
    // Ensure sprite is visible and raycastable
    sprite.visible = true;
    sprite.frustumCulled = false; // Always render regardless of camera position
    
    // Store metadata for click handling and hover
    sprite.userData.neighborId = neighborId;
    sprite.userData.neighborName = neighborName;
    sprite.userData.isConnectivityLabel = true;
    sprite.userData.onClick = onClick;
    sprite.userData.isHovered = false;
    sprite.userData.canvasAspectRatio = canvas.width / canvas.height; // Store for proper scaling

    return sprite;
}

/**
 * Position labels for a given direction (below edge markers, in a horizontal line)
 */
function positionLabelsForDirection(direction, neighbors, baseX, baseZ, xExtent, zExtent, avgSize) {
    const labels = [];
    const baseScale = avgSize * 0.035; // Compact size
    
    // Create all sprites first to measure their widths
    const sprites = neighbors.map(neighbor => {
        const sprite = createNeighborLabel(neighbor.name, neighbor.id, () => {
            // Click handler: load the neighbor state
            // Preserve current bucketSize in URL when navigating to adjacent region
            if (neighbor.id && neighbor.id !== currentRegionId) {
                const currentBucketSize = window.params?.bucketSize;
                if (currentBucketSize) {
                    try {
                        const url = new URL(window.location);
                        url.searchParams.set('bucketSize', currentBucketSize);
                        window.history.pushState({}, '', url);
                    } catch (e) {
                        console.warn('Failed to preserve bucketSize in URL:', e);
                    }
                }
                loadRegion(neighbor.id);
            }
        });
        return sprite;
    });
    
    // Calculate total width based on actual sprite aspect ratios
    let totalWidth = 0;
    sprites.forEach(sprite => {
        const aspectRatio = sprite.userData.canvasAspectRatio || 6.25;
        totalWidth += baseScale * aspectRatio;
    });
    
    // Start from the left edge, centered on the marker
    let xOffset = -totalWidth / 2;

    sprites.forEach((sprite, index) => {
        // Scale to maintain proper aspect ratio (no squishing!)
        const aspectRatio = sprite.userData.canvasAspectRatio || 6.25;
        const spriteWidth = baseScale * aspectRatio;
        
        sprite.scale.set(spriteWidth, baseScale, 1.0);

        // Position in a horizontal line below the marker
        // Adjust X/Z based on direction to keep labels readable
        let x, z;
        if (direction === 'N' || direction === 'S') {
            // North/South: offset in X direction
            x = baseX + xOffset + spriteWidth / 2;
            z = baseZ;
        } else {
            // East/West: offset in Z direction  
            x = baseX;
            z = baseZ + xOffset + spriteWidth / 2;
        }

        // Position below marker (negative Y)
        const yOffset = -avgSize * 0.08;
        sprite.position.set(x, yOffset, z);

        labels.push(sprite);
        xOffset += spriteWidth; // Move to next position (edge to edge)
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
 * Update the visual appearance of a label when hover state changes
 */
function updateLabelHoverState(sprite, isHovered) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    
    const fontSize = 28;
    const padding = 8; // Minimal padding - matches top/bottom
    
    // Measure text to determine canvas width (same as createNeighborLabel)
    context.font = `Bold ${fontSize}px Arial`;
    const textMetrics = context.measureText(sprite.userData.neighborName);
    const textWidth = textMetrics.width;
    
    canvas.width = Math.ceil(textWidth + padding * 2);
    canvas.height = 64;

    // Draw background - brighter when hovered
    if (isHovered) {
        context.fillStyle = 'rgba(40, 70, 100, 0.95)'; // Brighter bluish
    } else {
        context.fillStyle = 'rgba(20, 40, 60, 0.85)'; // Normal bluish
    }
    context.fillRect(0, 0, canvas.width, canvas.height);

    // Draw border
    context.strokeStyle = 'rgba(255, 255, 255, 0.3)';
    context.lineWidth = 1;
    context.strokeRect(0, 0, canvas.width, canvas.height);

    // Draw text - need to set font again after canvas resize
    context.font = `Bold ${fontSize}px Arial`;
    context.fillStyle = '#ffffff';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(sprite.userData.neighborName, canvas.width / 2, canvas.height / 2);

    // Update texture
    const texture = new THREE.CanvasTexture(canvas);
    sprite.material.map = texture;
    sprite.material.needsUpdate = true;
}

/**
 * Populate "Contains" column in lower-left navigation panel
 */
function populateContainsColumn(containedData) {
    const containsList = document.getElementById('contains-list');
    const containsColumn = document.getElementById('contains-column');
    
    if (!containsList || !containsColumn) return;
    
    // Clear existing items
    containsList.innerHTML = '';
    
    if (!containedData) {
        containsColumn.style.display = 'none';
        return;
    }
    
    // Handle both single and multiple contained areas
    const rawIds = Array.isArray(containedData) ? containedData : [containedData];
    
    // Filter valid areas
    const validAreas = rawIds
        .filter(id => regionsManifest && regionsManifest.regions && regionsManifest.regions[id])
        .map(id => ({
            id: id,
            name: regionIdToName[id] || id
        }));

    if (validAreas.length === 0) {
        containsColumn.style.display = 'none';
        return;
    }
    
    // Show column and add items
    containsColumn.style.display = 'block';
    
    // Add each contained area as clickable item
    validAreas.forEach(area => {
        const item = document.createElement('div');
        item.className = 'region-nav-item';
        item.textContent = area.name;
        item.title = `Jump to ${area.name}`;
        item.addEventListener('click', () => {
            if (area.id && area.id !== currentRegionId) {
                // Preserve current bucketSize in URL when navigating to contained area
                const currentBucketSize = window.params?.bucketSize;
                if (currentBucketSize) {
                    try {
                        const url = new URL(window.location);
                        url.searchParams.set('bucketSize', currentBucketSize);
                        window.history.pushState({}, '', url);
                    } catch (e) {
                        console.warn('Failed to preserve bucketSize in URL:', e);
                    }
                }
                loadRegion(area.id);
            }
        });
        containsList.appendChild(item);
    });
    
    console.log(`[Connectivity] Added ${validAreas.length} items to Contains column`);
}

/**
 * Populate "Contained By" column in lower-left navigation panel
 */
function populateContainedByColumn(withinData) {
    const containedByList = document.getElementById('contained-by-list');
    const containedByColumn = document.getElementById('contained-by-column');
    
    if (!containedByList || !containedByColumn) return;
    
    // Clear existing items
    containedByList.innerHTML = '';
    
    if (!withinData) {
        containedByColumn.style.display = 'none';
        return;
    }
    
    // Handle both single and multiple parent regions
    const rawIds = Array.isArray(withinData) ? withinData : [withinData];
    
    // Filter valid parent regions
    const validParents = rawIds
        .filter(id => regionsManifest && regionsManifest.regions && regionsManifest.regions[id])
        .map(id => ({
            id: id,
            name: regionIdToName[id] || id
        }));

    if (validParents.length === 0) {
        containedByColumn.style.display = 'none';
        return;
    }
    
    // Show column and add items
    containedByColumn.style.display = 'block';
    
    // Add each parent region as clickable item
    validParents.forEach(parent => {
        const item = document.createElement('div');
        item.className = 'region-nav-item';
        item.textContent = parent.name;
        item.title = `Jump to ${parent.name}`;
        item.addEventListener('click', () => {
            if (parent.id && parent.id !== currentRegionId) {
                // Preserve current bucketSize in URL when navigating to parent region
                const currentBucketSize = window.params?.bucketSize;
                if (currentBucketSize) {
                    try {
                        const url = new URL(window.location);
                        url.searchParams.set('bucketSize', currentBucketSize);
                        window.history.pushState({}, '', url);
                    } catch (e) {
                        console.warn('Failed to preserve bucketSize in URL:', e);
                    }
                }
                loadRegion(parent.id);
            }
        });
        containedByList.appendChild(item);
    });
    
    console.log(`[Connectivity] Added ${validParents.length} items to Contained By column`);
}

/**
 * Create connectivity labels for the current region
 * 
 * Displays clickable navigation:
 * - Cardinal directions (N/S/E/W): 3D labels below edge markers - adjacent regions
 * - "Contains" / "Part of": 2D panel in lower-left corner - containment navigation
 * 
 * Provides full bidirectional navigation between all region types.
 * 
 * CRITICAL: 3D labels MUST be added to terrainGroup (not scene) so they:
 * - Rotate with terrain when terrain is rotated
 * - Stay positioned correctly relative to terrain mesh
 * - Match edge markers coordinate space (which are also in terrainGroup)
 */
function createConnectivityLabels() {
    // Note: Array is already cleared by terrain-renderer.js when terrainGroup was destroyed
    // We just need to create new labels for the new terrain
    
    // Reset navigation panel - always clear both columns
    const navigationPanel = document.getElementById('region-navigation');
    const containsList = document.getElementById('contains-list');
    const containedByList = document.getElementById('contained-by-list');
    const containsColumn = document.getElementById('contains-column');
    const containedByColumn = document.getElementById('contained-by-column');
    
    if (containsList) containsList.innerHTML = '';
    if (containedByList) containedByList.innerHTML = '';
    if (containsColumn) containsColumn.style.display = 'none';
    if (containedByColumn) containedByColumn.style.display = 'none';
    if (navigationPanel) navigationPanel.style.display = 'none';

    if (!window.connectivityLabels) {
        console.error('[Connectivity] window.connectivityLabels array not initialized');
        return;
    }

    // Only show for regions with adjacency data
    if (!currentRegionId) {
        console.log('[Connectivity] Skipping: no current region');
        return;
    }
    
    // Get neighbors from regionAdjacency (unified system for all region types)
    const neighbors = currentRegionId && regionAdjacency && regionAdjacency[currentRegionId];
    if (!neighbors) {
        console.log('[Connectivity] Skipping: no adjacency data for', currentRegionId);
        return;
    }

    if (!rawElevationData || !processedData) {
        console.log('[Connectivity] Skipping: no elevation data available');
        return;
    }

    const gridWidth = processedData.width;
    const gridHeight = processedData.height;
    
    console.log(`[Connectivity] Creating labels for ${currentRegionId} with grid: ${gridWidth}x${gridHeight}`);

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

    // Track if we have any containment relationships
    let hasContainmentData = false;

    // Create labels for each direction that has neighbors
    for (const [direction, neighborData] of Object.entries(neighbors)) {
        if (!neighborData) continue;
        
        // Handle contained areas in 2D panel (lower-left, left column)
        if (direction === 'contained') {
            populateContainsColumn(neighborData);
            hasContainmentData = true;
            continue;
        }
        
        // Handle within relationships in 2D panel (lower-left, right column)
        if (direction === 'within') {
            populateContainedByColumn(neighborData);
            hasContainmentData = true;
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
            window.terrainGroup.add(label); // Add to terrainGroup, not scene
            if (window.connectivityLabels) {
                window.connectivityLabels.push(label);
            }
        });
    }

    // Show navigation panel if we have any containment relationships
    if (hasContainmentData && navigationPanel) {
        navigationPanel.style.display = 'block';
    }

    const labelCount = window.connectivityLabels ? window.connectivityLabels.length : 0;
    console.log(`[Connectivity] Created ${labelCount} 3D labels for ${currentRegionId}`);
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



