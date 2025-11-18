/**
 * Map Size Display Module
 * 
 * PURPOSE:
 * Displays the physical dimensions of the loaded map in the lower-right corner
 * Shows width × height in miles (or meters for square regions)
 * Also displays pixel dimensions (width × height) and total pixel count
 * 
 * DEPENDS ON:
 * - Global: window.rawElevationData (elevation data with bounds)
 * - Global: window.GeometryUtils.calculateRealWorldScale()
 * - Global: window.processedData (pixel dimensions)
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
            sizeDisplayEl.innerHTML = '--';
            return;
        }

        try {
            const scale = window.GeometryUtils.calculateRealWorldScale();
            const widthMeters = scale.widthMeters;
            const heightMeters = scale.heightMeters;

            // Convert to miles
            const widthMiles = widthMeters / 1609.344;
            const heightMiles = heightMeters / 1609.344;

            // Format extent as "x miles wide by y miles tall" (or "square = x.y meters tall by z.q meters wide" if square)
            let extentText = '';
            const aspectRatio = widthMeters / heightMeters;
            if (Math.abs(aspectRatio - 1.0) < 0.01) {
                // Square - show "square = x.y meters tall by z.q meters wide"
                extentText = `square = ${heightMeters.toFixed(1)} meters tall by ${widthMeters.toFixed(1)} meters wide`;
            } else {
                // Not square - show "x miles wide by y miles tall"
                const widthStr = widthMiles < 0.5 
                    ? `${Math.round(widthMeters * 3.280839895)} ft` 
                    : `${widthMiles.toFixed(2)} mi`;
                const heightStr = heightMiles < 0.5 
                    ? `${Math.round(heightMeters * 3.280839895)} ft` 
                    : `${heightMiles.toFixed(2)} mi`;
                extentText = `${widthStr} wide by ${heightStr} tall`;
            }

            // Add resolution info below extent (pixel dimensions and total count)
            let resolutionText = '';
            if (window.processedData) {
                const pixelWidth = window.processedData.width || 0;
                const pixelHeight = window.processedData.height || 0;
                const totalPixels = pixelWidth * pixelHeight;

                // Format as "X pixels wide, Y pixels tall" on one line, "Z total pixels" on next line
                resolutionText = `<div style="margin-top: 4px; opacity: 0.9;">${pixelWidth} pixels wide, ${pixelHeight} pixels tall<br>${totalPixels.toLocaleString()} total pixels</div>`;
            }

            sizeDisplayEl.innerHTML = extentText + resolutionText;
        } catch (error) {
            console.warn('[MapSizeDisplay] Error updating display:', error);
            sizeDisplayEl.innerHTML = '--';
        }
    }

    // Export to window for global access
    window.MapSizeDisplay = {
        init,
        update
    };

})();

