/**
 * Map Size Display Module
 * 
 * PURPOSE:
 * Displays the physical dimensions of the loaded map in the lower-right corner
 * Shows width × height in miles (or km if square and small)
 * 
 * DEPENDS ON:
 * - Global: window.rawElevationData (elevation data with bounds)
 * - Global: window.GeometryUtils.calculateRealWorldScale()
 * - Global: window.FormatUtils.formatFootprint()
 */

(function() {
    'use strict';

    // Prevent duplicate initialization
    if (window.MapSizeDisplay) {
        console.warn('[MapSizeDisplay] Already initialized');
        return;
    }

    let initialized = false;
    let sizeDisplayEl = null;

    /**
     * Initialize map size display
     */
    function init() {
        if (initialized) {
            console.warn('[MapSizeDisplay] init() called multiple times - skipping');
            return;
        }

        sizeDisplayEl = document.getElementById('map-size-display');
        if (!sizeDisplayEl) {
            console.warn('[MapSizeDisplay] Element #map-size-display not found');
            return;
        }

        initialized = true;
        update();
    }

    /**
     * Update the map size display
     */
    function update() {
        if (!initialized || !sizeDisplayEl) return;

        if (!window.rawElevationData || !window.GeometryUtils || !window.FormatUtils) {
            sizeDisplayEl.textContent = '--';
            return;
        }

        try {
            const scale = window.GeometryUtils.calculateRealWorldScale();
            const widthMeters = scale.widthMeters;
            const heightMeters = scale.heightMeters;

            // Convert to miles
            const widthMiles = widthMeters / 1609.344;
            const heightMiles = heightMeters / 1609.344;

            // Format as "x miles wide by y miles tall" (or "x miles × x miles" if square)
            const aspectRatio = widthMeters / heightMeters;
            if (Math.abs(aspectRatio - 1.0) < 0.01) {
                // Square - show simplified format
                if (widthMiles < 0.5) {
                    const feet = Math.round(widthMeters * 3.280839895);
                    sizeDisplayEl.textContent = `${feet} ft × ${feet} ft`;
                } else {
                    sizeDisplayEl.textContent = `${widthMiles.toFixed(2)} mi × ${widthMiles.toFixed(2)} mi`;
                }
            } else {
                // Not square - show "x miles wide by y miles tall"
                const widthStr = widthMiles < 0.5 
                    ? `${Math.round(widthMeters * 3.280839895)} ft` 
                    : `${widthMiles.toFixed(2)} mi`;
                const heightStr = heightMiles < 0.5 
                    ? `${Math.round(heightMeters * 3.280839895)} ft` 
                    : `${heightMiles.toFixed(2)} mi`;
                sizeDisplayEl.textContent = `${widthStr} wide by ${heightStr} tall`;
            }
        } catch (error) {
            console.warn('[MapSizeDisplay] Error updating display:', error);
            sizeDisplayEl.textContent = '--';
        }
    }

    // Export to window for global access
    window.MapSizeDisplay = {
        init,
        update
    };

})();

