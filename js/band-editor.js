// Band Editor for Hypsometric-Banded Color Schemes
// Allows dynamic adjustment of band boundaries

(function() {
    'use strict';

    // Configuration for each banded scheme
    const SCHEME_CONFIGS = {
        'hypsometric-banded': {
            stops: [0.00, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 0.95, 1.00],
            colors: [
                0x0a4f2c, // deep green
                0x2f7d32, // green
                0x7da850, // yellow-green
                0xb8a665, // tan
                0xa87d50, // brown
                0x8b5e34, // dark brown
                0xc8c8c8, // grey
                0xffffff  // white peaks
            ]
        },
        'hypsometric-intense': {
            stops: [0.00, 0.08, 0.17, 0.25, 0.33, 0.42, 0.50, 0.58, 0.67, 0.75, 0.83, 0.92, 1.00],
            colors: [
                0x001a33, // deep ocean blue
                0x004d00, // deep forest green
                0x00b300, // bright green
                0x66ff00, // lime
                0xffff00, // bright yellow
                0xff9900, // vivid orange
                0xff4400, // red-orange
                0xff0000, // pure red
                0xcc0066, // magenta
                0x9900cc, // purple
                0xcccccc, // light grey
                0xffffff  // white peaks
            ]
        },
        'hypsometric-refined': {
            stops: [0.00, 0.08, 0.17, 0.25, 0.33, 0.42, 0.50, 0.58, 0.67, 0.75, 0.83, 0.92, 1.00],
            colors: [
                0x1a3d3d, // deep teal-green
                0x2d5a3d, // forest green
                0x4a7c4e, // moss green
                0x6b9b5f, // olive green
                0x9bb076, // yellow-green
                0xb89d6a, // sandy tan
                0xc0845f, // ochre
                0xb36b52, // terra cotta
                0x9a5a47, // brown-red
                0x7a503f, // dark brown
                0xa09090, // grey-brown
                0xe0e0e0  // light grey peaks
            ]
        }
    };

    // Current active scheme
    let currentScheme = null;
    
    // Custom stops for each scheme (loaded from localStorage or defaults)
    let customBandStops = {};

    /**
     * Initialize band editor
     */
    function init() {
        // Load custom stops from localStorage
        loadCustomStops();

        // Set up event listeners
        const colorSchemeSelect = document.getElementById('colorScheme');
        const resetButton = document.getElementById('resetBands');
        const randomizeButton = document.getElementById('randomizeBands');
        const equalizeButton = document.getElementById('equalizeBands');
        
        if (!colorSchemeSelect) {
            console.error('[BandEditor] colorScheme select not found!');
            return;
        }
        if (!resetButton) {
            console.error('[BandEditor] resetBands button not found!');
            return;
        }
        if (!randomizeButton) {
            console.error('[BandEditor] randomizeBands button not found!');
            return;
        }
        if (!equalizeButton) {
            console.error('[BandEditor] equalizeBands button not found!');
            return;
        }
        
        colorSchemeSelect.addEventListener('change', updateBandEditorVisibility);
        resetButton.addEventListener('click', resetToDefaults);
        randomizeButton.addEventListener('click', randomizeBands);
        equalizeButton.addEventListener('click', equalizeCoverage);

        // Initial visibility check (immediate)
        updateBandEditorVisibility();
        
        // Retry after a short delay in case URL params haven't been applied yet
        setTimeout(() => {
            updateBandEditorVisibility();
        }, 100);
    }

    /**
     * Show/hide band editor based on selected color scheme
     */
    function updateBandEditorVisibility() {
        const colorSchemeSelect = document.getElementById('colorScheme');
        const bandEditor = document.getElementById('bandEditor');
        
        if (!colorSchemeSelect || !bandEditor) {
            console.error('[BandEditor] Required elements not found');
            return;
        }
        
        const colorScheme = colorSchemeSelect.value;
        console.log('[BandEditor] updateBandEditorVisibility called, scheme:', colorScheme);
        
        // Check if this is a banded scheme
        if (SCHEME_CONFIGS[colorScheme]) {
            console.log('[BandEditor] Showing band editor for scheme:', colorScheme);
            
            // If scheme changed, recreate sliders
            if (currentScheme !== colorScheme) {
                console.log('[BandEditor] Scheme changed from', currentScheme, 'to', colorScheme);
                currentScheme = colorScheme;
                bandEditor.removeAttribute('data-initialized'); // Force recreation
            }
            
            bandEditor.style.display = 'block';
            
            // Lazy load sliders only when first shown or when scheme changes
            if (!bandEditor.hasAttribute('data-initialized')) {
                console.log('[BandEditor] Scheduling slider creation');
                requestAnimationFrame(() => {
                    console.log('[BandEditor] RAF callback - creating sliders now');
                    createBandSliders();
                    bandEditor.setAttribute('data-initialized', 'true');
                });
            }
        } else {
            console.log('[BandEditor] Hiding band editor');
            bandEditor.style.display = 'none';
            currentScheme = null;
        }
    }

    /**
     * Create sliders for each band boundary
     */
    function createBandSliders() {
        try {
            if (!currentScheme || !SCHEME_CONFIGS[currentScheme]) {
                console.error('[BandEditor] No valid current scheme');
                return;
            }
            
            const config = SCHEME_CONFIGS[currentScheme];
            const container = document.getElementById('bandEditorSliders');
            
            if (!container) {
                console.error('[BandEditor] bandEditorSliders container not found!');
                return;
            }
            
            console.log('[BandEditor] Creating sliders for scheme:', currentScheme);
            container.innerHTML = '';

            // Ensure customBandStops is initialized for this scheme
            if (!customBandStops[currentScheme]) {
                customBandStops[currentScheme] = config.stops.slice();
            }
            const stops = customBandStops[currentScheme];
            console.log('[BandEditor] Will create', stops.length - 2, 'sliders for stops:', stops);

            // Create sliders for interior stops (not first or last)
            for (let i = 1; i < stops.length - 1; i++) {
                const sliderDiv = document.createElement('div');
                sliderDiv.style.display = 'flex';
                sliderDiv.style.alignItems = 'center';
                sliderDiv.style.gap = '6px';

                // Color swatch
                const swatch = document.createElement('div');
                swatch.style.width = '12px';
                swatch.style.height = '12px';
                swatch.style.backgroundColor = `#${config.colors[i].toString(16).padStart(6, '0')}`;
                swatch.style.border = '1px solid #666';
                swatch.style.flexShrink = '0';

                const label = document.createElement('span');
                label.style.fontSize = '10px';
                label.style.color = '#ffffff';
                label.style.minWidth = '45px';
                label.textContent = `${i}:`;
                label.id = `bandLabel${i}`;

                const slider = document.createElement('input');
                slider.type = 'range';
                slider.min = '0';
                slider.max = '100';
                slider.value = Math.round(stops[i] * 100);
                slider.id = `bandSlider${i}`;
                slider.style.flex = '1';

                const value = document.createElement('span');
                value.style.fontSize = '10px';
                value.style.color = '#88bbff';
                value.style.minWidth = '35px';
                value.textContent = `${Math.round(stops[i] * 100)}%`;
                value.id = `bandValue${i}`;

                // Update on input - instant, no debounce
                slider.addEventListener('input', (e) => {
                    const newValue = parseInt(e.target.value) / 100;
                    value.textContent = `${Math.round(newValue * 100)}%`;
                    updateBandStopWithPush(i, newValue);
                });

                sliderDiv.appendChild(swatch);
                sliderDiv.appendChild(label);
                sliderDiv.appendChild(slider);
                sliderDiv.appendChild(value);
                container.appendChild(sliderDiv);
            }
            
            console.log('[BandEditor] Created', stops.length - 2, 'sliders. Container now has', container.children.length, 'children');
            console.log('[BandEditor] Container display:', container.style.display);
            console.log('[BandEditor] Parent bandEditor display:', document.getElementById('bandEditor').style.display);
        } catch (error) {
            console.error('[BandEditor] Error creating sliders:', error);
        }
    }

    /**
     * Update a band stop with robust cascading push behavior
     */
    function updateBandStopWithPush(index, value) {
        if (!currentScheme || !customBandStops[currentScheme]) {
            console.error('[BandEditor] No valid scheme in updateBandStopWithPush');
            return;
        }

        const stops = customBandStops[currentScheme];
        const MIN_GAP = 0.01; // Minimum gap between bands (1%)
        
        // Clamp value to valid range
        value = Math.max(MIN_GAP, Math.min(1.0 - MIN_GAP, value));
        
        // Set the desired value
        stops[index] = value;
        
        // Push all bands upward if needed (recursive from this point up)
        for (let i = index + 1; i < stops.length; i++) {
            const minAllowed = stops[i - 1] + MIN_GAP;
            if (stops[i] < minAllowed) {
                stops[i] = Math.min(minAllowed, stops[i + 1] - MIN_GAP);
                updateSliderDisplay(i);
            } else {
                break; // No collision, stop pushing
            }
        }
        
        // Push all bands downward if needed (recursive from this point down)
        for (let i = index - 1; i >= 0; i--) {
            const maxAllowed = stops[i + 1] - MIN_GAP;
            if (stops[i] > maxAllowed) {
                stops[i] = Math.max(maxAllowed, stops[i - 1] + MIN_GAP);
                updateSliderDisplay(i);
            } else {
                break; // No collision, stop pushing
            }
        }
        
        // Final validation pass - enforce strict ordering
        enforceStrictOrdering();

        // Update the color scheme immediately
        updateColorSchemeImmediate();

        // Save to localStorage (debounced to avoid excessive writes)
        saveCustomStopsDebounced();
    }

    /**
     * Enforce strict ordering with minimum gaps between all bands
     * This is the "hardcore" validation that fixes any out-of-order situations
     */
    function enforceStrictOrdering() {
        if (!currentScheme || !customBandStops[currentScheme]) return;
        
        const stops = customBandStops[currentScheme];
        const MIN_GAP = 0.01;
        
        // Forward pass: ensure each band is at least MIN_GAP above the previous
        for (let i = 1; i < stops.length; i++) {
            const minAllowed = stops[i - 1] + MIN_GAP;
            if (stops[i] < minAllowed) {
                stops[i] = minAllowed;
                updateSliderDisplay(i);
            }
        }
        
        // Backward pass: if we hit the ceiling (1.0), compress downward
        if (stops[stops.length - 1] > 1.0) {
            stops[stops.length - 1] = 1.0;
        }
        for (let i = stops.length - 2; i >= 0; i--) {
            const maxAllowed = stops[i + 1] - MIN_GAP;
            if (stops[i] > maxAllowed) {
                stops[i] = maxAllowed;
                updateSliderDisplay(i);
            }
        }
    }

    /**
     * Update slider display without triggering events
     */
    function updateSliderDisplay(index) {
        if (!currentScheme || !customBandStops[currentScheme]) return;
        
        const slider = document.getElementById(`bandSlider${index}`);
        const value = document.getElementById(`bandValue${index}`);
        if (slider && value) {
            slider.value = Math.round(customBandStops[currentScheme][index] * 100);
            value.textContent = `${Math.round(customBandStops[currentScheme][index] * 100)}%`;
        }
    }

    let saveTimeout = null;
    function saveCustomStopsDebounced() {
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(() => {
            saveCustomStops();
        }, 500); // Save after 500ms of no changes
    }

    /**
     * Update the COLOR_SCHEMES with custom stops (immediate, no debounce)
     */
    function updateColorSchemeImmediate() {
        if (!currentScheme || !customBandStops[currentScheme] || !window.COLOR_SCHEMES) {
            return;
        }

        const config = SCHEME_CONFIGS[currentScheme];
        const stops = customBandStops[currentScheme];
        const newScheme = [];
        
        for (let i = 0; i < stops.length; i++) {
            newScheme.push({
                stop: stops[i],
                color: new THREE.Color(config.colors[i])
            });
        }

        window.COLOR_SCHEMES[currentScheme] = newScheme;

        // Trigger terrain update only if this scheme is active
        if (window.params && window.params.colorScheme === currentScheme) {
            if (window.MapShading && typeof window.MapShading.updateAll === 'function') {
                window.MapShading.updateAll();
            }
            if (typeof window.updateColorLegend === 'function') {
                window.updateColorLegend();
            }
        }
    }

    /**
     * Update the color scheme (for non-interactive updates)
     */
    function updateColorScheme() {
        updateColorSchemeImmediate();
    }

    /**
     * Generate random band boundaries using elevation distribution
     * This creates bands that respect the actual data distribution
     */
    function randomizeBands() {
        if (!currentScheme || !SCHEME_CONFIGS[currentScheme]) return;
        
        const config = SCHEME_CONFIGS[currentScheme];
        const numInteriorStops = config.stops.length - 2; // Exclude first (0.0) and last (1.0)
        
        if (numInteriorStops <= 0) return;
        
        // Strategy: Use elevation percentiles from actual data if available,
        // otherwise use beta distribution for varied natural-looking distributions
        
        let newStops;
        if (window.terrainData && window.terrainData.elevationArray) {
            // Use actual elevation distribution (best approach)
            newStops = generatePercentileBasedStops(numInteriorStops);
        } else {
            // Fallback: Use beta distribution for natural-looking randomness
            newStops = generateBetaDistributedStops(numInteriorStops);
        }
        
        // Always start at 0.0 and end at 1.0
        customBandStops[currentScheme] = [0.0, ...newStops, 1.0];
        saveCustomStops();
        
        // Update sliders
        for (let i = 1; i <= numInteriorStops; i++) {
            updateSliderDisplay(i);
        }
        
        // Immediate update
        updateColorSchemeImmediate();
    }
    
    /**
     * Equalize band coverage - each band gets same number of pixels
     * This is histogram equalization applied to band boundaries
     */
    function equalizeCoverage() {
        if (!currentScheme || !SCHEME_CONFIGS[currentScheme]) return;
        if (!window.terrainData || !window.terrainData.elevationArray) {
            console.warn('[BandEditor] No elevation data available for equalization');
            return;
        }
        
        const config = SCHEME_CONFIGS[currentScheme];
        const numBands = config.stops.length - 1; // Number of color bands
        
        // Compute evenly-spaced quantiles
        const newStops = computeEqualAreaQuantiles(numBands);
        
        customBandStops[currentScheme] = newStops;
        saveCustomStops();
        
        // Update sliders (skip first and last which are always 0 and 1)
        for (let i = 1; i < newStops.length - 1; i++) {
            updateSliderDisplay(i);
        }
        
        // Immediate update
        updateColorSchemeImmediate();
    }
    
    /**
     * Compute quantiles that divide data into equal-area bands
     * Returns array including 0.0 and 1.0 endpoints
     */
    function computeEqualAreaQuantiles(numBands) {
        const data = window.terrainData.elevationArray;
        const minElev = window.terrainData.minElevation;
        const maxElev = window.terrainData.maxElevation;
        
        // Get sorted copy (cache it for efficiency)
        if (!window._sortedElevationCache || 
            window._sortedElevationCache.length !== data.length) {
            console.log('[BandEditor] Sorting elevation data for quantile computation...');
            window._sortedElevationCache = data.slice().sort((a, b) => a - b);
        }
        const sorted = window._sortedElevationCache;
        
        const n = sorted.length;
        const stops = [0.0]; // Always start at 0
        
        // Compute quantiles at 1/numBands, 2/numBands, ..., (numBands-1)/numBands
        for (let i = 1; i < numBands; i++) {
            const p = i / numBands; // Percentile (0 to 1)
            const index = Math.floor(p * n);
            const elevValue = sorted[Math.min(index, n - 1)];
            
            // Normalize to 0-1 range based on min/max
            const normalized = (elevValue - minElev) / (maxElev - minElev);
            stops.push(Math.max(0, Math.min(1, normalized)));
        }
        
        stops.push(1.0); // Always end at 1
        
        return stops;
    }
    
    /**
     * Generate stops based on actual elevation percentiles
     * This creates bands where the data actually lives
     */
    function generatePercentileBasedStops(count) {
        const elevationArray = window.terrainData.elevationArray;
        
        // Pick random percentiles, ensuring minimum spacing
        const MIN_PERCENTILE_GAP = 5; // At least 5% apart
        const stops = [];
        
        // Generate random percentiles with jitter
        for (let i = 0; i < count; i++) {
            // Target percentile with random jitter
            const basePercentile = (i + 1) * (100 / (count + 1));
            const jitter = (Math.random() - 0.5) * 20; // ±10% jitter
            const percentile = Math.max(MIN_PERCENTILE_GAP, 
                                       Math.min(100 - MIN_PERCENTILE_GAP, 
                                               basePercentile + jitter));
            stops.push(percentile);
        }
        
        // Sort and ensure minimum spacing
        stops.sort((a, b) => a - b);
        
        // Enforce minimum gaps between percentiles
        for (let i = 1; i < stops.length; i++) {
            if (stops[i] - stops[i-1] < MIN_PERCENTILE_GAP) {
                stops[i] = stops[i-1] + MIN_PERCENTILE_GAP;
            }
        }
        
        // Clamp to valid range and convert to 0-1 scale
        return stops.map(p => {
            const clamped = Math.max(MIN_PERCENTILE_GAP, Math.min(100 - MIN_PERCENTILE_GAP, p));
            return clamped / 100;
        });
    }
    
    /**
     * Generate stops using beta distribution for natural-looking randomness
     * Beta distribution creates varied patterns (early-heavy, late-heavy, uniform, etc.)
     */
    function generateBetaDistributedStops(count) {
        // Randomly choose a distribution pattern
        const patterns = [
            { alpha: 2, beta: 5 },   // Early-heavy (more bands at low elevation)
            { alpha: 5, beta: 2 },   // Late-heavy (more bands at high elevation)
            { alpha: 2, beta: 2 },   // Balanced (more bands at extremes)
            { alpha: 5, beta: 5 },   // Center-heavy (more bands in middle)
            { alpha: 1, beta: 1 },   // Uniform (even distribution)
        ];
        
        const pattern = patterns[Math.floor(Math.random() * patterns.length)];
        const MIN_GAP = 0.05; // Minimum 5% spacing
        
        const stops = [];
        for (let i = 0; i < count; i++) {
            // Generate beta-distributed value
            const u = betaRandom(pattern.alpha, pattern.beta);
            stops.push(u);
        }
        
        // Sort and ensure minimum spacing
        stops.sort((a, b) => a - b);
        
        // Enforce minimum gaps
        for (let i = 1; i < stops.length; i++) {
            if (stops[i] - stops[i-1] < MIN_GAP) {
                stops[i] = stops[i-1] + MIN_GAP;
            }
        }
        
        // Final pass: ensure we don't exceed 1.0
        const maxValue = 1.0 - MIN_GAP;
        for (let i = stops.length - 1; i >= 0; i--) {
            if (stops[i] > maxValue) {
                stops[i] = maxValue;
                maxValue -= MIN_GAP;
            }
        }
        
        return stops;
    }
    
    /**
     * Generate a random number from Beta(alpha, beta) distribution
     * Uses the fact that if X ~ Gamma(alpha) and Y ~ Gamma(beta),
     * then X/(X+Y) ~ Beta(alpha, beta)
     */
    function betaRandom(alpha, beta) {
        const x = gammaRandom(alpha);
        const y = gammaRandom(beta);
        return x / (x + y);
    }
    
    /**
     * Generate a random number from Gamma(shape) distribution
     * Using Marsaglia and Tsang's method
     */
    function gammaRandom(shape) {
        if (shape < 1) {
            // Use shape + 1 and adjust
            return gammaRandom(shape + 1) * Math.pow(Math.random(), 1 / shape);
        }
        
        const d = shape - 1/3;
        const c = 1 / Math.sqrt(9 * d);
        
        while (true) {
            let x, v;
            do {
                x = normalRandom();
                v = 1 + c * x;
            } while (v <= 0);
            
            v = v * v * v;
            const u = Math.random();
            
            if (u < 1 - 0.0331 * x * x * x * x) {
                return d * v;
            }
            if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) {
                return d * v;
            }
        }
    }
    
    /**
     * Generate a random number from standard normal distribution
     * Using Box-Muller transform
     */
    function normalRandom() {
        const u1 = Math.random();
        const u2 = Math.random();
        return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    }

    /**
     * Reset to default band stops
     */
    function resetToDefaults() {
        if (!currentScheme || !SCHEME_CONFIGS[currentScheme]) return;
        
        const config = SCHEME_CONFIGS[currentScheme];
        customBandStops[currentScheme] = config.stops.slice();
        saveCustomStops();
        
        // Update sliders efficiently
        for (let i = 1; i < customBandStops[currentScheme].length - 1; i++) {
            updateSliderDisplay(i);
        }

        // Immediate update
        updateColorSchemeImmediate();
    }

    /**
     * Save custom stops to localStorage (all schemes)
     */
    function saveCustomStops() {
        if (Object.keys(customBandStops).length > 0) {
            localStorage.setItem('customBandStops', JSON.stringify(customBandStops));
        }
    }

    /**
     * Load custom stops from localStorage (all schemes)
     */
    function loadCustomStops() {
        const stored = localStorage.getItem('customBandStops');
        if (stored) {
            try {
                const loaded = JSON.parse(stored);
                
                // Handle both old format (single array) and new format (object of arrays)
                if (Array.isArray(loaded)) {
                    // Old format - migrate to new format for hypsometric-banded only
                    console.log('[BandEditor] Migrating old format to new format');
                    const bandedConfig = SCHEME_CONFIGS['hypsometric-banded'];
                    if (loaded.length === bandedConfig.stops.length &&
                        loaded.every((v, i) => typeof v === 'number' && v >= 0 && v <= 1) &&
                        loaded[0] === 0 && loaded[loaded.length - 1] === 1) {
                        customBandStops['hypsometric-banded'] = loaded;
                    }
                } else if (typeof loaded === 'object') {
                    // New format - validate each scheme
                    for (const [schemeName, stops] of Object.entries(loaded)) {
                        const config = SCHEME_CONFIGS[schemeName];
                        if (config && Array.isArray(stops) &&
                            stops.length === config.stops.length &&
                            stops.every((v, i) => typeof v === 'number' && v >= 0 && v <= 1) &&
                            stops[0] === 0 && stops[stops.length - 1] === 1) {
                            customBandStops[schemeName] = stops;
                        }
                    }
                }
                
                // Update all scheme definitions in COLOR_SCHEMES
                if (window.COLOR_SCHEMES) {
                    for (const [schemeName, stops] of Object.entries(customBandStops)) {
                        const config = SCHEME_CONFIGS[schemeName];
                        if (config) {
                            const newScheme = [];
                            for (let i = 0; i < stops.length; i++) {
                                newScheme.push({
                                    stop: stops[i],
                                    color: new THREE.Color(config.colors[i])
                                });
                            }
                            window.COLOR_SCHEMES[schemeName] = newScheme;
                        }
                    }
                }
            } catch (e) {
                console.error('[BandEditor] Failed to load custom stops:', e);
                localStorage.removeItem('customBandStops');
                customBandStops = {};
            }
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose for debugging and external updates
    window.BandEditor = {
        resetToDefaults,
        randomizeBands,
        equalizeCoverage,
        getCustomStops: () => customBandStops,
        getCurrentScheme: () => currentScheme,
        updateVisibility: updateBandEditorVisibility, // Allow external updates
        setCustomStops: (schemeName, stops) => {
            if (SCHEME_CONFIGS[schemeName]) {
                customBandStops[schemeName] = stops;
                saveCustomStops();
                if (currentScheme === schemeName) {
                    updateColorScheme();
                }
            }
        }
    };
})();

