/**
 * Map Shading Module
 * 
 * PURPOSE:
 * Apply visual appearance to terrain (colors, shading, materials, lighting).
 * Handles all color scheme application and material properties.
 * 
 * FEATURES:
 * - Color lookup for elevation values
 * - Update all terrain colors (bars mode only)
 * - Support derived modes (slope, aspect)
 * - Auto-stretch color calculation
 * - Gamma correction
 * - Material properties (flat lighting support, shader uniforms)
 * - Lighting coordination (ambient, directional lights)
 * 
 * DESIGN NOTES:
 * - Single place for all visual appearance logic
 * - Easy to add new color schemes or shading modes
 * - Clear separation from geometry creation
 * - Follows LLM-friendly pattern: explicit over implicit
 * 
 * RELATIONSHIP TO TERRAIN RENDERER:
 * - Terrain Renderer: Creates geometry (mesh structure, vertices, instanced meshes)
 * - Map Shading: Applies visual appearance (colors, materials, lighting)
 * - Clear separation: Geometry vs. Appearance
 * - Terrain Renderer calls Map Shading during creation to apply initial colors
 * 
 * DEPENDS ON:
 * - COLOR_SCHEMES (from color-schemes.js)
 * - Global: window.params.colorScheme, window.params.colorGamma, window.params.flatLighting
 * - Global: window.processedData, window.derivedSlopeDeg, window.derivedAspectDeg
 * - Global: window.terrainMesh, window.barsInstancedMesh, window.barsIndexToRow, window.barsIndexToCol
 * - Functions: getSlopeDegrees(), getAspectDegrees() (from viewer-advanced)
 * - Functions: computeAutoStretchStats() (from viewer-advanced)
 */

(function() {
    'use strict';

    // Prevent duplicate initialization
    if (window.MapShading) {
        console.warn('[MapShading] Already initialized');
        return;
    }

    // Temporary color object for reuse (avoids allocations)
    const __tmpColor = new THREE.Color();

    // Helpers for per-cell derived values during colorization
    let __lastColorRow = 0, __lastColorCol = 0;

    /**
     * Set last color index (for derived modes like slope/aspect)
     * @param {number} i - Row index
     * @param {number} j - Column index
     */
    function setLastColorIndex(i, j) {
        __lastColorRow = i;
        __lastColorCol = j;
    }

    /**
     * Derive current slope value (for slope color mode)
     * @returns {number|null} Slope in degrees
     */
    function deriveCurrentSlope() {
        if (typeof getSlopeDegrees === 'function') {
            return getSlopeDegrees(__lastColorRow, __lastColorCol) ?? 0;
        }
        return null;
    }

    /**
     * Derive current aspect value (for aspect color mode)
     * @returns {number|null} Aspect in degrees
     */
    function deriveCurrentAspect() {
        if (typeof getAspectDegrees === 'function') {
            return getAspectDegrees(__lastColorRow, __lastColorCol) ?? 0;
        }
        return null;
    }

    /**
     * Get color for a specific elevation value
     * @param {number} elevation - Elevation in meters
     * @param {number} [row] - Optional row index (for derived modes)
     * @param {number} [col] - Optional column index (for derived modes)
     * @returns {THREE.Color} Color object (reused, don't store reference)
     */
    function getColor(elevation, row, col) {
        // Set last color index if provided (for derived modes)
        if (typeof row === 'number' && typeof col === 'number') {
            setLastColorIndex(row, col);
        }

        // Special case: elevation at or below sea level (0m) should look like WATER
        if (elevation <= 0.5) {
            return __tmpColor.set(0x0066cc); // Ocean blue for water
        }

        // Derived map modes
        if (window.params && window.params.colorScheme === 'slope' && window.derivedSlopeDeg) {
            const deg = deriveCurrentSlope();
            const clamped = Math.max(0, Math.min(60, isFinite(deg) ? deg : 0));
            const t = clamped / 60; // 0..1
            // Blue (low) -> green -> yellow -> red (high)
            const h = (1 - t) * 0.66; // 0.66=blue to 0=red
            return __tmpColor.setHSL(h, 1.0, 0.5);
        }
        if (window.params && window.params.colorScheme === 'aspect' && window.derivedAspectDeg) {
            const deg = deriveCurrentAspect();
            const h = ((isFinite(deg) ? deg : 0) % 360) / 360; // 0..1
            return __tmpColor.setHSL(h, 1.0, 0.5);
        }

        // Standard elevation-based color schemes
        const useAuto = (window.params && window.params.colorScheme === 'auto-stretch');
        const useGlobalScale = (window.params && window.params.useGlobalScale);
        
        // Select stats source: global stats if enabled, otherwise per-region stats
        let stats = null;
        if (useGlobalScale && window.globalElevationStats) {
            stats = window.globalElevationStats;
        } else {
            stats = window.processedData && window.processedData.stats
                ? window.processedData.stats
                : (window.rawElevationData && window.rawElevationData.stats ? window.rawElevationData.stats : null);
        }

        if (!stats) {
            // Fallback if no stats available
            return __tmpColor.set(0x808080); // Gray
        }

        const low = useAuto && typeof stats.autoLow === 'number' ? stats.autoLow : stats.min;
        const high = useAuto && typeof stats.autoHigh === 'number' ? stats.autoHigh : stats.max;
        const denom = Math.max(1e-9, high - low);
        let normalized = Math.max(0, Math.min(1, (elevation - low) / denom));

        // Apply contrast (gamma). >1 darkens lower values, <1 brightens
        const g = (window.params && typeof window.params.colorGamma === 'number')
            ? Math.max(0.1, Math.min(10, window.params.colorGamma))
            : 1.0;
        normalized = Math.pow(normalized, g);

        // Get color scheme
        const scheme = (typeof COLOR_SCHEMES !== 'undefined' && COLOR_SCHEMES[window.params.colorScheme])
            ? COLOR_SCHEMES[window.params.colorScheme]
            : (COLOR_SCHEMES && COLOR_SCHEMES['high-contrast'] ? COLOR_SCHEMES['high-contrast'] : null);

        if (!scheme || scheme.length === 0) {
            return __tmpColor.set(0x808080); // Gray fallback
        }

        const isBanded = window.params && 
            (window.params.colorScheme === 'hypsometric-banded' || 
             window.params.colorScheme === 'hypsometric-intense' ||
             window.params.colorScheme === 'hypsometric-refined');

        // Find color in scheme
        for (let i = 0; i < scheme.length - 1; i++) {
            const a = scheme[i];
            const b = scheme[i + 1];
            if (normalized >= a.stop && normalized <= b.stop) {
                if (isBanded) {
                    // Banded: use flat color from lower band (step function)
                    return __tmpColor.copy(a.color);
                } else {
                    // Smooth: interpolate between colors
                    const localT = (normalized - a.stop) / (b.stop - a.stop);
                    return __tmpColor.copy(a.color).lerp(b.color, localT);
                }
            }
        }

        // Use last color in scheme
        return __tmpColor.copy(scheme[scheme.length - 1].color);
    }

    /**
     * Update all terrain colors
     * Only bars mode is supported
     */
    function updateAll() {
        if (!window.terrainMesh || !window.processedData || !window.rawElevationData) {
            // Fallback if not ready yet
            if (typeof recreateTerrain === 'function') {
                recreateTerrain();
            }
            return;
        }

        // Bars mode: update per-instance colors without rebuild
        if (window.params) {
            if (!window.barsInstancedMesh || !window.barsIndexToRow || !window.barsIndexToCol) {
                if (typeof recreateTerrain === 'function') {
                    recreateTerrain();
                }
                return;
            }

            if (window.barsInstancedMesh.material && window.barsInstancedMesh.material.vertexColors) {
                const colorAttr = window.barsInstancedMesh.geometry.getAttribute('instanceColor');
                if (!colorAttr || !colorAttr.array) {
                    if (typeof recreateTerrain === 'function') {
                        recreateTerrain();
                    }
                    return;
                }

                const arr = colorAttr.array;
                const count = window.barsIndexToRow.length;
                for (let i = 0; i < count; i++) {
                    const row = window.barsIndexToRow[i];
                    const col = window.barsIndexToCol[i];
                    let z = (window.processedData.elevation[row] && window.processedData.elevation[row][col]);
                    if (z === null || z === undefined) z = 0;
                    const c = getColor(z, row, col);
                    const idx = i * 3;
                    arr[idx] = c.r;
                    arr[idx + 1] = c.g;
                    arr[idx + 2] = c.b;
                }
                colorAttr.needsUpdate = true;
                return;
            }
            return;
        }

        // Only bars mode is supported - if we get here, something is wrong
        console.error(`Unexpected state in updateAll - bars mode should have been handled above`);
        if (typeof recreateTerrain === 'function') {
            recreateTerrain();
        }
    }

    /**
     * Set color scheme
     * @param {string} schemeName - Name of color scheme
     */
    function setScheme(schemeName) {
        if (!window.params) {
            console.error('[MapShading] window.params not available');
            return;
        }

        window.params.colorScheme = schemeName;

        // Compute auto-stretch stats if needed
        if (schemeName === 'auto-stretch' && typeof computeAutoStretchStats === 'function') {
            computeAutoStretchStats();
        }

        // Update all colors
        updateAll();

        // Update color legend to match new scheme
        if (typeof updateColorLegend === 'function') {
            updateColorLegend();
        }
    }

    /**
     * Set gamma correction
     * @param {number} gamma - Gamma value (0.1 to 10)
     */
    function setGamma(gamma) {
        if (!window.params) {
            console.error('[MapShading] window.params not available');
            return;
        }

        window.params.colorGamma = Math.max(0.1, Math.min(10, gamma));
        updateAll();

        // Update color legend to reflect gamma changes
        if (typeof updateColorLegend === 'function') {
            updateColorLegend();
        }
    }

    /**
     * Update material properties (for flat lighting support)
     * Currently always uses Natural (Lambert) shading
     */
    function updateMaterials() {
        // Future: Implement flat lighting toggle
        // For now, materials are created during terrain creation
        // This function is a placeholder for future material updates
    }

    /**
     * Set flat lighting mode
     * @param {boolean} enabled - Whether to use flat (unlit) materials
     */
    function setFlatLighting(enabled) {
        if (!window.params) {
            console.error('[MapShading] window.params not available');
            return;
        }

        window.params.flatLighting = enabled;
        updateMaterials();

        // Update lighting intensities
        if (typeof updateLightingForShading === 'function') {
            updateLightingForShading();
        }
    }

    // Export module
    window.MapShading = {
        getColor: getColor,
        updateAll: updateAll,
        setScheme: setScheme,
        setGamma: setGamma,
        updateMaterials: updateMaterials,
        setFlatLighting: setFlatLighting,
        setLastColorIndex: setLastColorIndex
    };

})();

