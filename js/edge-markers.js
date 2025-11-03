/**
 * Edge Markers Module
 * 
 * PURPOSE:
 * Creates and manages directional markers showing neighboring regions at terrain edges.
 * These markers help users navigate to adjacent regions with a single click.
 * 
 * FEATURES:
 * - Shows actual neighbor names (e.g., "Oregon" at north edge of California)
 * - Clickable markers to load adjacent regions
 * - Positioned at terrain edges based on render mode
 * - Markers stay at ground level (y=0) regardless of vertical exaggeration
 * - Auto-scales based on terrain size
 * - Only shows markers for neighbors that exist in the manifest
 * 
 * DESIGN NOTES:
 * - Markers are created once and stay fixed (no updates needed on exaggeration change)
 * - Each marker is a canvas-based sprite with colored border
 * - Markers use depthTest=false to always be visible
 * - Clicking a marker loads the corresponding region
 * 
 * DEPENDS ON:
 * - Global: scene, edgeMarkers[], rawElevationData, processedData, params, currentRegionId
 * - Global: regionAdjacency, regionIdToName, regionsManifest
 * - Three.js: THREE.CanvasTexture, THREE.SpriteMaterial, THREE.Sprite
 * - Functions: loadRegion()
 */

/**
 * Create directional markers showing neighboring regions at terrain edges
 * Markers are positioned at ground level and scaled based on terrain size
 * Shows actual neighbor names (e.g., "Oregon" instead of "N") and are clickable
 * 
 * @global scene - Three.js scene to add markers to
 * @global edgeMarkers - Array to store marker sprites
 * @global rawElevationData - Raw elevation data (for existence check)
 * @global processedData - Processed data with width/height
 * @global params - Render parameters (renderMode, bucketSize)
 * @global currentRegionId - Currently loaded region
 * @global regionAdjacency - Adjacency data for all regions
 * @global regionIdToName - Mapping from region IDs to display names
 * @global regionsManifest - Manifest of available regions
 */
function createEdgeMarkers() {
    // Remove old markers (3D sprites)
    edgeMarkers.forEach(marker => scene.remove(marker));
    edgeMarkers = [];

    if (!rawElevationData || !processedData) return;

    const gridWidth = processedData.width;
    const gridHeight = processedData.height;

    // Position markers at ground level (y=0) so they sit on the terrain surface
    // They stay at this fixed height regardless of vertical exaggeration changes
    const markerHeight = 0;

    // Calculate actual coordinate extents based on render mode
    let xExtent, zExtent, avgSize;
    if (params.renderMode === 'bars') {
        // Bars use UNIFORM 2D grid - same spacing in X and Z (no aspect ratio)
        const bucketMultiplier = params.bucketSize;
        xExtent = (gridWidth - 1) * bucketMultiplier / 2;
        zExtent = (gridHeight - 1) * bucketMultiplier / 2; // NO aspect ratio scaling!
        avgSize = (xExtent + zExtent);
    } else if (params.renderMode === 'points') {
        // Points use uniform grid positioning, scaled by bucketSize
        const bucketSize = params.bucketSize;
        xExtent = (gridWidth - 1) * bucketSize / 2;
        zExtent = (gridHeight - 1) * bucketSize / 2;
        avgSize = (xExtent + zExtent);
    } else {
        // Surface uses uniform grid positioning (centered PlaneGeometry, scaled by bucketSize)
        const bucketMultiplier = params.bucketSize;
        xExtent = (gridWidth * bucketMultiplier) / 2;
        zExtent = (gridHeight * bucketMultiplier) / 2;
        avgSize = (gridWidth * bucketMultiplier + gridHeight * bucketMultiplier) / 2;
    }

    // Get neighbors for current region
    const neighbors = currentRegionId && regionAdjacency && regionAdjacency[currentRegionId];

    console.log('[EDGE MARKERS] Current region:', currentRegionId);
    console.log('[EDGE MARKERS] Region adjacency loaded:', regionAdjacency ? 'YES' : 'NO');
    console.log('[EDGE MARKERS] Neighbors for this region:', neighbors);

    if (!neighbors) {
        // No adjacency data - show fallback compass directions
        const fallbackMarkers = [
            { text: 'N', direction: null, x: 0, z: -zExtent, color: 0xff4444 },
            { text: 'S', direction: null, x: 0, z: zExtent, color: 0x4488ff },
            { text: 'E', direction: null, x: xExtent, z: 0, color: 0x44ff44 },
            { text: 'W', direction: null, x: -xExtent, z: 0, color: 0xffff44 }
        ];

        fallbackMarkers.forEach(markerData => {
            const sprite = createTextSprite(markerData.text, markerData.color, null);
            sprite.position.set(markerData.x, markerHeight, markerData.z);
            const baseScale = avgSize * 0.06;
            sprite.scale.set(baseScale, baseScale, baseScale);
            scene.add(sprite);
            edgeMarkers.push(sprite);
        });
        return;
    }

    // Create markers for each direction with neighbor names
    const directions = [
        { key: 'north', letter: 'N', x: 0, z: -zExtent, color: 0xff4444 },
        { key: 'south', letter: 'S', x: 0, z: zExtent, color: 0x4488ff },
        { key: 'east', letter: 'E', x: xExtent, z: 0, color: 0x44ff44 },
        { key: 'west', letter: 'W', x: -xExtent, z: 0, color: 0xffff44 }
    ];

    directions.forEach(dir => {
        const neighborData = neighbors[dir.key];
        console.log(`[EDGE MARKERS] Direction ${dir.key}: neighborData=`, neighborData);

        // Always create the compass direction marker (non-clickable)
        const compassSprite = createTextSprite(dir.letter, dir.color, null);
        compassSprite.position.set(dir.x, markerHeight, dir.z);
        const baseScale = avgSize * 0.06;
        compassSprite.scale.set(baseScale, baseScale, baseScale);
        // Mark as non-interactive
        compassSprite.userData.nonInteractive = true;
        scene.add(compassSprite);
        edgeMarkers.push(compassSprite);

        if (!neighborData) {
            console.log(`[EDGE MARKERS] No neighbor for ${dir.key}, compass marker only`);
            return; // No neighbor in this direction
        }

        // Handle both single neighbor (string) and multiple neighbors (array)
        const neighborIds = Array.isArray(neighborData) ? neighborData : [neighborData];

        // Filter out neighbors that don't exist in manifest
        const validNeighbors = neighborIds.filter(id => {
            if (regionsManifest && regionsManifest.regions && regionsManifest.regions[id]) {
                return true;
            }
            console.log(`[EDGE MARKERS] Neighbor "${id}" not in manifest, skipping`);
            return false;
        });

        if (validNeighbors.length === 0) {
            console.log(`[EDGE MARKERS] No valid neighbors for ${dir.key}, compass marker only`);
            return;
        }

        // Get display names for all valid neighbors
        const neighborNames = validNeighbors.map(id => regionIdToName[id] || id);
        console.log(`[EDGE MARKERS] Creating ${validNeighbors.length} neighbor button(s) for ${dir.key}:`, neighborNames);

        // Create individual sprite button for each neighbor
        validNeighbors.forEach((neighborId, index) => {
            const neighborName = neighborNames[index];

            // Calculate 3D position for this button
            const textOffset = avgSize * 0.12; // Distance from compass marker
            const buttonSpacing = avgSize * 0.08; // Spacing between buttons (in world space, relative to terrain size)
            const totalHeight = (validNeighbors.length - 1) * buttonSpacing;
            const startOffset = -totalHeight / 2; // Center the stack vertically

            let buttonX = dir.x;
            let buttonZ = dir.z;

            // Move button out from center based on direction
            if (dir.key === 'north') buttonZ -= textOffset;
            if (dir.key === 'south') buttonZ += textOffset;
            if (dir.key === 'east') buttonX += textOffset;
            if (dir.key === 'west') buttonX -= textOffset;

            // Stack buttons vertically (up/down in world space)
            const buttonY = markerHeight + startOffset + (index * buttonSpacing);

            // Create sprite button
            const buttonSprite = createNeighborButtonSprite(neighborName, dir.color);
            buttonSprite.position.set(buttonX, buttonY, buttonZ);

            // Scale relative to terrain size (sizeAttenuation: true means world-space)
            const buttonScale = avgSize * 0.075; // 50% smaller (was 0.15)
            buttonSprite.scale.set(buttonScale * 4, buttonScale, 1); // 4x wider than tall

            // Store neighbor info for click handling
            buttonSprite.userData.neighborId = neighborId;
            buttonSprite.userData.neighborName = neighborName;
            buttonSprite.userData.isButton = true;
            buttonSprite.userData.baseColor = dir.color;

            scene.add(buttonSprite);
            edgeMarkers.push(buttonSprite);

            console.log(`[EDGE MARKERS] Added sprite button for ${neighborName} at (${buttonX.toFixed(1)}, ${buttonY.toFixed(1)}, ${buttonZ.toFixed(1)})`);
        });
    });
}

/**
 * Create a text sprite with colored circle border for compass directions
 * Uses canvas to render text onto a texture
 * 
 * @param {string} text - Text to display (single letter: N, E, S, W)
 * @param {number} color - Hex color value (e.g., 0xff4444)
 * @param {string|null} neighborId - Not used for compass markers (kept for compatibility)
 * @returns {THREE.Sprite} Sprite with text texture
 */
function createTextSprite(text, color, neighborId) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    canvas.width = 256;
    canvas.height = 256;

    // Draw background circle
    context.fillStyle = 'rgba(0, 0, 0, 0.8)';
    context.beginPath();
    context.arc(128, 128, 100, 0, 2 * Math.PI);
    context.fill();

    // Draw border
    context.strokeStyle = `#${color.toString(16).padStart(6, '0')}`;
    context.lineWidth = 8;
    context.beginPath();
    context.arc(128, 128, 100, 0, 2 * Math.PI);
    context.stroke();

    // Draw text
    context.font = 'Bold 140px Arial';
    context.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(text, 128, 128);

    const texture = new THREE.CanvasTexture(canvas);
    const spriteMaterial = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthTest: false, // Always visible
        depthWrite: false
    });
    const sprite = new THREE.Sprite(spriteMaterial);

    return sprite;
}

/**
 * Create an individual button sprite for a neighbor region
 * Uses sizeAttenuation: false for constant screen size
 * 
 * @param {string} name - Neighbor state/region name
 * @param {number} color - Hex color for the border accent
 * @returns {THREE.Sprite} Sprite with button texture
 */
function createNeighborButtonSprite(name, color) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');

    // Canvas size for button texture
    canvas.width = 512;
    canvas.height = 128;

    const fontSize = 48;
    const padding = 20;

    // Measure text to size button appropriately
    context.font = `Bold ${fontSize}px Arial`;
    const textMetrics = context.measureText(name);
    const textWidth = textMetrics.width;

    // Button dimensions
    const buttonWidth = Math.min(textWidth + padding * 2, canvas.width - 40);
    const buttonHeight = canvas.height - 40;
    const buttonX = (canvas.width - buttonWidth) / 2;
    const buttonY = (canvas.height - buttonHeight) / 2;
    const radius = 12;

    // Draw rounded rectangle button background
    context.fillStyle = 'rgba(0, 0, 0, 0.9)';
    context.beginPath();
    context.moveTo(buttonX + radius, buttonY);
    context.lineTo(buttonX + buttonWidth - radius, buttonY);
    context.quadraticCurveTo(buttonX + buttonWidth, buttonY, buttonX + buttonWidth, buttonY + radius);
    context.lineTo(buttonX + buttonWidth, buttonY + buttonHeight - radius);
    context.quadraticCurveTo(buttonX + buttonWidth, buttonY + buttonHeight, buttonX + buttonWidth - radius, buttonY + buttonHeight);
    context.lineTo(buttonX + radius, buttonY + buttonHeight);
    context.quadraticCurveTo(buttonX, buttonY + buttonHeight, buttonX, buttonY + buttonHeight - radius);
    context.lineTo(buttonX, buttonY + radius);
    context.quadraticCurveTo(buttonX, buttonY, buttonX + radius, buttonY);
    context.closePath();
    context.fill();

    // Draw colored border (thinner)
    context.strokeStyle = `#${color.toString(16).padStart(6, '0')}`;
    context.lineWidth = 3; // Thinner (was 6)
    context.stroke();

    // Draw text centered
    context.font = `Bold ${fontSize}px Arial`;
    context.fillStyle = '#ffffff';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(name, canvas.width / 2, canvas.height / 2);

    const texture = new THREE.CanvasTexture(canvas);

    // Set texture filtering for crisp text
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.anisotropy = 4;

    const spriteMaterial = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthTest: false,
        depthWrite: false
        // sizeAttenuation defaults to true - sprites scale with distance
    });
    const sprite = new THREE.Sprite(spriteMaterial);

    return sprite;
}

/**
 * Update button appearance for hover effect
 * @param {THREE.Sprite} buttonSprite - The button sprite to update
 * @param {boolean} isHovered - Whether the button is being hovered
 */
function updateButtonAppearance(buttonSprite, isHovered) {
    if (!buttonSprite.userData.isButton) return;

    const name = buttonSprite.userData.neighborName;
    const baseColor = buttonSprite.userData.baseColor;

    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');

    canvas.width = 512;
    canvas.height = 128;

    const fontSize = 48;
    const padding = 20;

    context.font = `Bold ${fontSize}px Arial`;
    const textMetrics = context.measureText(name);
    const textWidth = textMetrics.width;

    const buttonWidth = Math.min(textWidth + padding * 2, canvas.width - 40);
    const buttonHeight = canvas.height - 40;
    const buttonX = (canvas.width - buttonWidth) / 2;
    const buttonY = (canvas.height - buttonHeight) / 2;
    const radius = 12;

    // Background color changes on hover
    context.fillStyle = isHovered ? 'rgba(40, 40, 40, 0.95)' : 'rgba(0, 0, 0, 0.9)';
    context.beginPath();
    context.moveTo(buttonX + radius, buttonY);
    context.lineTo(buttonX + buttonWidth - radius, buttonY);
    context.quadraticCurveTo(buttonX + buttonWidth, buttonY, buttonX + buttonWidth, buttonY + radius);
    context.lineTo(buttonX + buttonWidth, buttonY + buttonHeight - radius);
    context.quadraticCurveTo(buttonX + buttonWidth, buttonY + buttonHeight, buttonX + buttonWidth - radius, buttonY + buttonHeight);
    context.lineTo(buttonX + radius, buttonY + buttonHeight);
    context.quadraticCurveTo(buttonX, buttonY + buttonHeight, buttonX, buttonY + buttonHeight - radius);
    context.lineTo(buttonX, buttonY + radius);
    context.quadraticCurveTo(buttonX, buttonY, buttonX + radius, buttonY);
    context.closePath();
    context.fill();

    // Border color brightens on hover
    const borderColor = isHovered ? lightenColor(baseColor, 0.3) : baseColor;
    context.strokeStyle = `#${borderColor.toString(16).padStart(6, '0')}`;
    context.lineWidth = isHovered ? 4 : 3; // Thinner (was 8/6)
    context.stroke();

    // Draw text
    context.font = `Bold ${fontSize}px Arial`;
    context.fillStyle = '#ffffff';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(name, canvas.width / 2, canvas.height / 2);

    // Update texture
    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.anisotropy = 4;

    buttonSprite.material.map.dispose();
    buttonSprite.material.map = texture;
    buttonSprite.material.needsUpdate = true;
}

/**
 * Lighten a color by a factor
 * @param {number} color - Hex color
 * @param {number} factor - Amount to lighten (0-1)
 * @returns {number} Lightened color
 */
function lightenColor(color, factor) {
    const r = (color >> 16) & 0xff;
    const g = (color >> 8) & 0xff;
    const b = color & 0xff;

    const newR = Math.min(255, Math.floor(r + (255 - r) * factor));
    const newG = Math.min(255, Math.floor(g + (255 - g) * factor));
    const newB = Math.min(255, Math.floor(b + (255 - b) * factor));

    return (newR << 16) | (newG << 8) | newB;
}

/**
 * Update edge marker positions (currently a no-op)
 * Markers stay at fixed height - no update needed when vertical exaggeration changes
 * This function is kept for compatibility but doesn't change marker heights
 */
function updateEdgeMarkers() {
    if (!rawElevationData || !processedData || edgeMarkers.length === 0) return;

    // Markers stay at fixed height - no update needed when vertical exaggeration changes
    // This function is kept for compatibility but doesn't change marker heights
    // The markers are positioned at a fixed height set in createEdgeMarkers()
}

// Export module
window.EdgeMarkers = {
    create: createEdgeMarkers,
    update: updateEdgeMarkers,
    createTextSprite: createTextSprite,
    updateButtonAppearance: updateButtonAppearance
};

