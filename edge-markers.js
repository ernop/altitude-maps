/**
 * Edge Markers Module
 * 
 * PURPOSE:
 * Creates and manages directional markers (N, E, S, W) at the edges of the terrain.
 * These markers help users orient themselves and understand map direction.
 * 
 * FEATURES:
 * - Creates colored text sprites for each cardinal direction
 * - Positions markers at terrain edges based on render mode
 * - Markers stay at ground level (y=0) regardless of vertical exaggeration
 * - Auto-scales based on terrain size
 * 
 * DESIGN NOTES:
 * - Markers are created once and stay fixed (no updates needed on exaggeration change)
 * - Each marker is a canvas-based sprite with colored border
 * - Markers use depthTest=false to always be visible
 * 
 * DEPENDS ON:
 * - Global: scene, edgeMarkers[], rawElevationData, processedData, params
 * - Three.js: THREE.CanvasTexture, THREE.SpriteMaterial, THREE.Sprite
 */

/**
 * Create directional markers (N, E, S, W) at terrain edges
 * Markers are positioned at ground level and scaled based on terrain size
 * 
 * @global scene - Three.js scene to add markers to
 * @global edgeMarkers - Array to store marker sprites
 * @global rawElevationData - Raw elevation data (for existence check)
 * @global processedData - Processed data with width/height
 * @global params - Render parameters (renderMode, bucketSize)
 */
function createEdgeMarkers() {
    // Remove old markers
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

    // Create text sprites for N, E, S, W at appropriate edges
    const markers = [
        { text: 'N', x: 0, z: -zExtent, color: 0xff4444 }, // North edge
        { text: 'S', x: 0, z: zExtent, color: 0x4488ff }, // South edge
        { text: 'E', x: xExtent, z: 0, color: 0x44ff44 }, // East edge
        { text: 'W', x: -xExtent, z: 0, color: 0xffff44 } // West edge
    ];

    markers.forEach(markerData => {
        const sprite = createTextSprite(markerData.text, markerData.color);
        sprite.position.set(markerData.x, markerHeight, markerData.z);

        // Scale based on terrain size
        const baseScale = avgSize * 0.06; // 6% of average dimension (tripled from original 2%)
        sprite.scale.set(baseScale, baseScale, baseScale);

        scene.add(sprite);
        edgeMarkers.push(sprite);
    });

    // Removed verbose edge marker creation log
}

/**
 * Create a text sprite with colored circle border
 * Uses canvas to render text onto a texture
 * 
 * @param {string} text - Text to display (typically single letter: N, E, S, W)
 * @param {number} color - Hex color value (e.g., 0xff4444)
 * @returns {THREE.Sprite} Sprite with text texture
 */
function createTextSprite(text, color) {
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
    createTextSprite: createTextSprite
};

