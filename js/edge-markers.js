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
 * - Markers respect depth (can be obscured by terrain)
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
    edgeMarkers.forEach(marker => {
        window.terrainGroup.remove(marker);
    });
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

    // Spread multiplier to push markers away from terrain edges
    const spreadMultiplier = 1.25;

    if (!neighbors) {
        // No adjacency data - show fallback compass directions
        const fallbackMarkers = [
            { text: 'N', direction: null, x: 0, z: -zExtent * spreadMultiplier, color: 0xff4444 },
            { text: 'S', direction: null, x: 0, z: zExtent * spreadMultiplier, color: 0x4488ff },
            { text: 'E', direction: null, x: xExtent * spreadMultiplier, z: 0, color: 0x44ff44 },
            { text: 'W', direction: null, x: -xExtent * spreadMultiplier, z: 0, color: 0xffff44 }
        ];

        fallbackMarkers.forEach(markerData => {
            const sprite = createTextSprite(markerData.text, markerData.color, null);
            sprite.position.set(markerData.x, markerHeight, markerData.z);
            const baseScale = avgSize * 0.06;
            sprite.scale.set(baseScale, baseScale, baseScale);

            // Apply current visibility state from checkbox
            const showEdgeMarkersCheckbox = document.getElementById('showEdgeMarkers');
            sprite.visible = !showEdgeMarkersCheckbox || showEdgeMarkersCheckbox.checked;

            // Add to terrain group so markers rotate with terrain
            window.terrainGroup.add(sprite);
            edgeMarkers.push(sprite);
        });
        return;
    }

    // Create markers for each direction with neighbor names
    const directions = [
        { key: 'north', letter: 'N', x: 0, z: -zExtent * spreadMultiplier, color: 0xff4444 },
        { key: 'south', letter: 'S', x: 0, z: zExtent * spreadMultiplier, color: 0x4488ff },
        { key: 'east', letter: 'E', x: xExtent * spreadMultiplier, z: 0, color: 0x44ff44 },
        { key: 'west', letter: 'W', x: -xExtent * spreadMultiplier, z: 0, color: 0xffff44 }
    ];

    directions.forEach(dir => {
        const neighborData = neighbors[dir.key];
        console.log(`[EDGE MARKERS] Direction ${dir.key}: neighborData=`, neighborData);

        // Get valid neighbor names for this direction
        let neighborIds = [];
        let neighborNames = [];

        if (neighborData) {
            // Handle both single neighbor (string) and multiple neighbors (array)
            const rawIds = Array.isArray(neighborData) ? neighborData : [neighborData];

            // Filter out neighbors that don't exist in manifest
            neighborIds = rawIds.filter(id => {
                if (regionsManifest && regionsManifest.regions && regionsManifest.regions[id]) {
                    return true;
                }
                console.log(`[EDGE MARKERS] Neighbor "${id}" not in manifest, skipping`);
                return false;
            });

            // Get display names
            neighborNames = neighborIds.map(id => regionIdToName[id] || id);
        }

        // Create combined sprite with compass letter + neighbor names
        const combinedSprite = createCombinedDirectionSprite(dir.letter, neighborNames, dir.color);
        combinedSprite.position.set(dir.x, markerHeight, dir.z);

        // Scale based on terrain size (2x bigger)
        const baseScale = avgSize * 0.12; // Doubled from 0.06
        combinedSprite.scale.set(baseScale, baseScale, baseScale);

        // Store neighbor info for click handling
        if (neighborIds.length > 0) {
            combinedSprite.userData.neighborIds = neighborIds;
            combinedSprite.userData.neighborNames = neighborNames;
            combinedSprite.userData.isClickable = true;
            combinedSprite.userData.neighborCount = neighborIds.length;
        } else {
            combinedSprite.userData.isClickable = false;
            combinedSprite.userData.neighborCount = 0;
        }

        // Apply current visibility state from checkbox
        const showEdgeMarkersCheckbox = document.getElementById('showEdgeMarkers');
        combinedSprite.visible = !showEdgeMarkersCheckbox || showEdgeMarkersCheckbox.checked;

        // Add to terrain group so markers rotate with terrain
        window.terrainGroup.add(combinedSprite);
        edgeMarkers.push(combinedSprite);

        console.log(`[EDGE MARKERS] Added combined marker for ${dir.key} with neighbors:`, neighborNames);
    });
}

/**
 * Create a combined rectangular sprite with compass direction and neighbor names
 * @param {string} directionLetter - Compass direction (N, E, S, W)
 * @param {string[]} neighborNames - Array of neighbor region names (empty if none)
 * @param {number} color - Hex color for border
 * @returns {THREE.Sprite} Combined sprite
 */
function createCombinedDirectionSprite(directionLetter, neighborNames, color) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');

    // Canvas size - larger to accommodate long state names
    canvas.width = 768;
    canvas.height = 768;

    const compassFontSize = 112; // Larger for compass letter (40% increase from 80)
    const stateFontSize = 70;   // Smaller for state names (40% increase from 50)
    const padding = 32;
    const buttonPadding = 28;   // Extra padding for breathing room
    const buttonSpacing = 12;

    // Store button boundaries for accurate click detection
    const buttonBounds = [];

    // Measure compass letter
    context.font = `Bold ${compassFontSize}px Arial`;
    const compassWidth = context.measureText(directionLetter).width;

    // Measure state names
    context.font = `Bold ${stateFontSize}px Arial`;
    const stateWidths = neighborNames.map(name => context.measureText(name).width);
    const maxStateWidth = stateWidths.length > 0 ? Math.max(...stateWidths) : 0;

    // Calculate container dimensions - no artificial width constraint
    const contentWidth = Math.max(compassWidth, maxStateWidth + buttonPadding * 2);
    const rectWidth = contentWidth + padding * 2;  // Removed Math.min constraint

    const compassHeight = compassFontSize * 1.2;
    const stateButtonHeight = stateFontSize + buttonPadding * 2;
    const totalStateHeight = neighborNames.length > 0
        ? (stateButtonHeight * neighborNames.length) + (buttonSpacing * (neighborNames.length - 1))
        : 0;
    const rectHeight = compassHeight + totalStateHeight + padding * 2 + (neighborNames.length > 0 ? 10 : 0);

    const rectX = (canvas.width - rectWidth) / 2;
    const rectY = (canvas.height - rectHeight) / 2;
    const radius = 8;

    // Draw main container background with light color-coded background
    const bgColor = getCompassBackgroundColor(color, false);
    context.fillStyle = bgColor;
    context.beginPath();
    context.moveTo(rectX + radius, rectY);
    context.lineTo(rectX + rectWidth - radius, rectY);
    context.quadraticCurveTo(rectX + rectWidth, rectY, rectX + rectWidth, rectY + radius);
    context.lineTo(rectX + rectWidth, rectY + rectHeight - radius);
    context.quadraticCurveTo(rectX + rectWidth, rectY + rectHeight, rectX + rectWidth - radius, rectY + rectHeight);
    context.lineTo(rectX + radius, rectY + rectHeight);
    context.quadraticCurveTo(rectX, rectY + rectHeight, rectX, rectY + rectHeight - radius);
    context.lineTo(rectX, rectY + radius);
    context.quadraticCurveTo(rectX, rectY, rectX + radius, rectY);
    context.closePath();
    context.fill();

    // Draw compass letter (centered, larger)
    context.font = `Bold ${compassFontSize}px Arial`;
    context.fillStyle = '#ffffff';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    const compassY = rectY + padding + compassHeight / 2;
    context.fillText(directionLetter, canvas.width / 2, compassY);

    // Draw state name buttons (left-aligned)
    if (neighborNames.length > 0) {
        const stateStartY = rectY + padding + compassHeight + 10;

        neighborNames.forEach((name, index) => {
            const buttonY = stateStartY + index * (stateButtonHeight + buttonSpacing);
            const buttonX = rectX + padding;
            const buttonWidth = rectWidth - padding * 2;
            const buttonRadius = 6;

            // Store button boundaries in UV space (0-1, inverted Y)
            // UV: y=0 is bottom, y=1 is top
            const uvTop = 1 - (buttonY / canvas.height);
            const uvBottom = 1 - ((buttonY + stateButtonHeight) / canvas.height);
            buttonBounds.push({
                index: index,
                uvTop: uvTop,      // Higher Y value in UV space
                uvBottom: uvBottom, // Lower Y value in UV space
                name: name
            });

            // Draw button background with same light color (no border)
            context.fillStyle = bgColor;
            context.beginPath();
            context.moveTo(buttonX + buttonRadius, buttonY);
            context.lineTo(buttonX + buttonWidth - buttonRadius, buttonY);
            context.quadraticCurveTo(buttonX + buttonWidth, buttonY, buttonX + buttonWidth, buttonY + buttonRadius);
            context.lineTo(buttonX + buttonWidth, buttonY + stateButtonHeight - buttonRadius);
            context.quadraticCurveTo(buttonX + buttonWidth, buttonY + stateButtonHeight, buttonX + buttonWidth - buttonRadius, buttonY + stateButtonHeight);
            context.lineTo(buttonX + buttonRadius, buttonY + stateButtonHeight);
            context.quadraticCurveTo(buttonX, buttonY + stateButtonHeight, buttonX, buttonY + stateButtonHeight - buttonRadius);
            context.lineTo(buttonX, buttonY + buttonRadius);
            context.quadraticCurveTo(buttonX, buttonY, buttonX + buttonRadius, buttonY);
            context.closePath();
            context.fill();

            // Draw state name (left-aligned)
            context.font = `Bold ${stateFontSize}px Arial`;
            context.fillStyle = '#ffffff';
            context.textAlign = 'left';
            context.textBaseline = 'middle';
            context.fillText(name, buttonX + buttonPadding, buttonY + stateButtonHeight / 2);
        });
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.anisotropy = 4;

    const spriteMaterial = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthTest: true,  // Allow terrain to obscure markers
        depthWrite: false
    });
    const sprite = new THREE.Sprite(spriteMaterial);

    // Attach data for click detection and hover state regeneration
    sprite.userData.buttonBounds = buttonBounds;
    sprite.userData.directionLetter = directionLetter;
    sprite.userData.neighborNames = neighborNames;
    sprite.userData.color = color;

    return sprite;
}

/**
 * Create a text sprite with solid colored square background for compass directions
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

    const fontSize = 140;
    const padding = 32;
    const rectSize = 220;
    const rectX = (canvas.width - rectSize) / 2;
    const rectY = (canvas.height - rectSize) / 2;
    const radius = 8;

    // Draw solid colored rounded rectangle background
    const bgColor = getCompassBackgroundColor(color, false);
    context.fillStyle = bgColor;
    context.beginPath();
    context.moveTo(rectX + radius, rectY);
    context.lineTo(rectX + rectSize - radius, rectY);
    context.quadraticCurveTo(rectX + rectSize, rectY, rectX + rectSize, rectY + radius);
    context.lineTo(rectX + rectSize, rectY + rectSize - radius);
    context.quadraticCurveTo(rectX + rectSize, rectY + rectSize, rectX + rectSize - radius, rectY + rectSize);
    context.lineTo(rectX + radius, rectY + rectSize);
    context.quadraticCurveTo(rectX, rectY + rectSize, rectX, rectY + rectSize - radius);
    context.lineTo(rectX, rectY + radius);
    context.quadraticCurveTo(rectX, rectY, rectX + radius, rectY);
    context.closePath();
    context.fill();

    // Draw text in white
    context.font = `Bold ${fontSize}px Arial`;
    context.fillStyle = '#ffffff';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(text, canvas.width / 2, canvas.height / 2);

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.anisotropy = 4;

    const spriteMaterial = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthTest: true, // Allow terrain to obscure markers
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
        depthTest: true, // Allow terrain to obscure markers
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
 * Get background color for a compass direction
 * @param {number} color - Hex color (0xff4444=red, 0x4488ff=blue, 0x44ff44=green, 0xffff44=yellow)
 * @param {boolean} hover - Whether this is for hover state
 * @returns {string} RGB color string
 */
function getCompassBackgroundColor(color, hover = false) {
    switch (color) {
        case 0xff4444: // North - red
            return hover ? 'rgb(180, 40, 40)' : 'rgb(140, 30, 30)';
        case 0x4488ff: // South - blue
            return hover ? 'rgb(50, 100, 180)' : 'rgb(35, 75, 140)';
        case 0x44ff44: // East - green
            return hover ? 'rgb(40, 150, 40)' : 'rgb(25, 110, 25)';
        case 0xffff44: // West - yellow/orange
            return hover ? 'rgb(180, 140, 30)' : 'rgb(140, 105, 20)';
    }
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

/**
 * Update hover state for a combined direction sprite
 * Regenerates the texture with the hovered button highlighted
 * @param {THREE.Sprite} sprite - The edge marker sprite
 * @param {number} hoveredIndex - Index of button being hovered (-1 for none)
 */
function updateHoverState(sprite, hoveredIndex) {
    if (!sprite || !sprite.userData) return;

    // Store hover state and get marker data
    const directionLetter = sprite.userData.directionLetter;
    const neighborNames = sprite.userData.neighborNames || [];
    const color = sprite.userData.color;

    if (!directionLetter || !neighborNames.length || !color) return;

    // Recreate the sprite texture with hover highlighting
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');

    canvas.width = 768;
    canvas.height = 768;

    const compassFontSize = 112; // 40% increase from 80
    const stateFontSize = 70;    // 40% increase from 50
    const padding = 32;
    const buttonPadding = 28;    // Extra padding for breathing room
    const buttonSpacing = 12;

    // Measure compass letter
    context.font = `Bold ${compassFontSize}px Arial`;
    const compassWidth = context.measureText(directionLetter).width;

    // Measure state names
    context.font = `Bold ${stateFontSize}px Arial`;
    const stateWidths = neighborNames.map(name => context.measureText(name).width);
    const maxStateWidth = stateWidths.length > 0 ? Math.max(...stateWidths) : 0;

    // Calculate container dimensions - no artificial width constraint
    const contentWidth = Math.max(compassWidth, maxStateWidth + buttonPadding * 2);
    const rectWidth = contentWidth + padding * 2;  // Removed Math.min constraint

    const compassHeight = compassFontSize * 1.2;
    const stateButtonHeight = stateFontSize + buttonPadding * 2;
    const totalStateHeight = neighborNames.length > 0
        ? (stateButtonHeight * neighborNames.length) + (buttonSpacing * (neighborNames.length - 1))
        : 0;
    const rectHeight = compassHeight + totalStateHeight + padding * 2 + (neighborNames.length > 0 ? 10 : 0);

    const rectX = (canvas.width - rectWidth) / 2;
    const rectY = (canvas.height - rectHeight) / 2;
    const radius = 8;

    // Draw main container background with light color-coded background
    const bgColor = getCompassBackgroundColor(color, false);
    context.fillStyle = bgColor;
    context.beginPath();
    context.moveTo(rectX + radius, rectY);
    context.lineTo(rectX + rectWidth - radius, rectY);
    context.quadraticCurveTo(rectX + rectWidth, rectY, rectX + rectWidth, rectY + radius);
    context.lineTo(rectX + rectWidth, rectY + rectHeight - radius);
    context.quadraticCurveTo(rectX + rectWidth, rectY + rectHeight, rectX + rectWidth - radius, rectY + rectHeight);
    context.lineTo(rectX + radius, rectY + rectHeight);
    context.quadraticCurveTo(rectX, rectY + rectHeight, rectX, rectY + rectHeight - radius);
    context.lineTo(rectX, rectY + radius);
    context.quadraticCurveTo(rectX, rectY, rectX + radius, rectY);
    context.closePath();
    context.fill();

    // Draw compass letter (centered, larger)
    context.font = `Bold ${compassFontSize}px Arial`;
    context.fillStyle = '#ffffff';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    const compassY = rectY + padding + compassHeight / 2;
    context.fillText(directionLetter, canvas.width / 2, compassY);

    // Draw state name buttons (left-aligned, with hover highlighting)
    if (neighborNames.length > 0) {
        const stateStartY = rectY + padding + compassHeight + 10;

        neighborNames.forEach((name, index) => {
            const isHovered = (index === hoveredIndex);
            const buttonY = stateStartY + index * (stateButtonHeight + buttonSpacing);
            const buttonX = rectX + padding;
            const buttonWidth = rectWidth - padding * 2;
            const buttonRadius = 6;

            // Draw button background with same light color (slightly brighter if hovered, no border)
            const buttonBgColor = isHovered ? getCompassBackgroundColor(color, true) : bgColor;
            context.fillStyle = buttonBgColor;
            context.beginPath();
            context.moveTo(buttonX + buttonRadius, buttonY);
            context.lineTo(buttonX + buttonWidth - buttonRadius, buttonY);
            context.quadraticCurveTo(buttonX + buttonWidth, buttonY, buttonX + buttonWidth, buttonY + buttonRadius);
            context.lineTo(buttonX + buttonWidth, buttonY + stateButtonHeight - buttonRadius);
            context.quadraticCurveTo(buttonX + buttonWidth, buttonY + stateButtonHeight, buttonX + buttonWidth - buttonRadius, buttonY + stateButtonHeight);
            context.lineTo(buttonX + buttonRadius, buttonY + stateButtonHeight);
            context.quadraticCurveTo(buttonX, buttonY + stateButtonHeight, buttonX, buttonY + stateButtonHeight - buttonRadius);
            context.lineTo(buttonX, buttonY + buttonRadius);
            context.quadraticCurveTo(buttonX, buttonY, buttonX + buttonRadius, buttonY);
            context.closePath();
            context.fill();

            // Draw state name (left-aligned)
            context.font = `Bold ${stateFontSize}px Arial`;
            context.fillStyle = '#ffffff';
            context.textAlign = 'left';
            context.textBaseline = 'middle';
            context.fillText(name, buttonX + buttonPadding, buttonY + stateButtonHeight / 2);
        });
    }

    // Update texture
    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.anisotropy = 4;

    sprite.material.map = texture;
    sprite.material.needsUpdate = true;
}

// Export module
window.EdgeMarkers = {
    create: createEdgeMarkers,
    update: updateEdgeMarkers,
    createTextSprite: createTextSprite,
    updateButtonAppearance: updateButtonAppearance,
    updateHoverState: updateHoverState
};

