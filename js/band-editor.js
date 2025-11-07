// Band Editor for Hypsometric-Banded Color Scheme
// Allows dynamic adjustment of band boundaries

(function() {
    'use strict';

    // Default band stops (matches hypsometric-banded in color-schemes.js)
    const DEFAULT_BAND_STOPS = [0.00, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 0.95, 1.00];
    
    // Default colors (matches hypsometric-banded)
    const DEFAULT_BAND_COLORS = [
        0x0a4f2c, // deep green
        0x2f7d32, // green
        0x7da850, // yellow-green
        0xb8a665, // tan
        0xa87d50, // brown
        0x8b5e34, // dark brown
        0xc8c8c8, // grey
        0xffffff  // white peaks
    ];

    // Current custom stops (loaded from localStorage or defaults)
    let customBandStops = null;

    /**
     * Initialize band editor
     */
    function init() {
        // Load custom stops from localStorage
        loadCustomStops();

        // Set up event listeners
        const colorSchemeSelect = document.getElementById('colorScheme');
        const resetButton = document.getElementById('resetBands');
        
        if (!colorSchemeSelect) {
            console.error('[BandEditor] colorScheme select not found!');
            return;
        }
        if (!resetButton) {
            console.error('[BandEditor] resetBands button not found!');
            return;
        }
        
        colorSchemeSelect.addEventListener('change', updateBandEditorVisibility);
        resetButton.addEventListener('click', resetToDefaults);

        // Initial visibility check
        updateBandEditorVisibility();
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
        
        if (colorScheme === 'hypsometric-banded') {
            console.log('[BandEditor] Showing band editor');
            bandEditor.style.display = 'block';
            // Lazy load sliders only when first shown
            if (!bandEditor.hasAttribute('data-initialized')) {
                console.log('[BandEditor] Scheduling slider creation');
                requestAnimationFrame(() => {
                    console.log('[BandEditor] RAF callback - creating sliders now');
                    createBandSliders();
                    bandEditor.setAttribute('data-initialized', 'true');
                });
            } else {
                console.log('[BandEditor] Sliders already created');
            }
        } else {
            console.log('[BandEditor] Hiding band editor');
            bandEditor.style.display = 'none';
        }
    }

    /**
     * Create sliders for each band boundary
     */
    function createBandSliders() {
        try {
            const container = document.getElementById('bandEditorSliders');
            
            if (!container) {
                console.error('[BandEditor] bandEditorSliders container not found!');
                return;
            }
            
            console.log('[BandEditor] Creating sliders in container:', container);
            container.innerHTML = '';

            // Ensure customBandStops is initialized
            if (!customBandStops) {
                customBandStops = DEFAULT_BAND_STOPS.slice();
            }
            const stops = customBandStops;
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
                swatch.style.backgroundColor = `#${DEFAULT_BAND_COLORS[i].toString(16).padStart(6, '0')}`;
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
     * Update a band stop with cascading push behavior
     */
    function updateBandStopWithPush(index, value) {
        if (!customBandStops) {
            customBandStops = DEFAULT_BAND_STOPS.slice();
        }

        const MIN_GAP = 0.01; // Minimum gap between bands (1%)
        
        // Cascade push upward (toward higher indices) if needed
        if (index < customBandStops.length - 1) {
            const requiredNext = value + MIN_GAP;
            if (requiredNext >= customBandStops[index + 1]) {
                cascadePushUp(index + 1, requiredNext);
            }
        }

        // Cascade push downward (toward lower indices) if needed
        if (index > 0) {
            const requiredPrev = value - MIN_GAP;
            if (requiredPrev <= customBandStops[index - 1]) {
                cascadePushDown(index - 1, requiredPrev);
            }
        }

        // Set the value
        customBandStops[index] = value;

        // Update the color scheme immediately
        updateColorSchemeImmediate();

        // Save to localStorage (debounced to avoid excessive writes)
        saveCustomStopsDebounced();
    }

    /**
     * Recursively push bands upward (toward index 1.0)
     */
    function cascadePushUp(index, minValue) {
        if (index >= customBandStops.length - 1) {
            // Hit the ceiling (1.0) - can't push further
            return;
        }

        const MIN_GAP = 0.01;
        const maxAllowed = customBandStops[index + 1] - MIN_GAP;
        const newValue = Math.min(maxAllowed, minValue);

        // If we need to push the next band up too
        if (minValue > maxAllowed) {
            cascadePushUp(index + 1, minValue + MIN_GAP);
        }

        customBandStops[index] = newValue;
        updateSliderDisplay(index);
    }

    /**
     * Recursively push bands downward (toward index 0.0)
     */
    function cascadePushDown(index, maxValue) {
        if (index <= 0) {
            // Hit the floor (0.0) - can't push further
            return;
        }

        const MIN_GAP = 0.01;
        const minAllowed = customBandStops[index - 1] + MIN_GAP;
        const newValue = Math.max(minAllowed, maxValue);

        // If we need to push the previous band down too
        if (maxValue < minAllowed) {
            cascadePushDown(index - 1, maxValue - MIN_GAP);
        }

        customBandStops[index] = newValue;
        updateSliderDisplay(index);
    }

    /**
     * Update slider display without triggering events
     */
    function updateSliderDisplay(index) {
        const slider = document.getElementById(`bandSlider${index}`);
        const value = document.getElementById(`bandValue${index}`);
        if (slider && value) {
            slider.value = Math.round(customBandStops[index] * 100);
            value.textContent = `${Math.round(customBandStops[index] * 100)}%`;
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
     * Update the COLOR_SCHEMES['hypsometric-banded'] with custom stops (immediate, no debounce)
     */
    function updateColorSchemeImmediate() {
        if (!customBandStops || !window.COLOR_SCHEMES) {
            return;
        }

        const newScheme = [];
        for (let i = 0; i < customBandStops.length; i++) {
            newScheme.push({
                stop: customBandStops[i],
                color: new THREE.Color(DEFAULT_BAND_COLORS[i])
            });
        }

        window.COLOR_SCHEMES['hypsometric-banded'] = newScheme;

        // Trigger terrain update only if this scheme is active
        if (window.params && window.params.colorScheme === 'hypsometric-banded') {
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
     * Reset to default band stops
     */
    function resetToDefaults() {
        customBandStops = DEFAULT_BAND_STOPS.slice();
        saveCustomStops();
        
        // Update sliders efficiently
        for (let i = 1; i < customBandStops.length - 1; i++) {
            updateSliderDisplay(i);
        }

        // Immediate update
        updateColorSchemeImmediate();
    }

    /**
     * Save custom stops to localStorage
     */
    function saveCustomStops() {
        if (customBandStops) {
            localStorage.setItem('customBandStops', JSON.stringify(customBandStops));
        }
    }

    /**
     * Load custom stops from localStorage
     */
    function loadCustomStops() {
        const stored = localStorage.getItem('customBandStops');
        if (stored) {
            try {
                const loaded = JSON.parse(stored);
                // Validate the data
                if (Array.isArray(loaded) && 
                    loaded.length === DEFAULT_BAND_STOPS.length &&
                    loaded.every((v, i) => typeof v === 'number' && v >= 0 && v <= 1) &&
                    loaded[0] === 0 && loaded[loaded.length - 1] === 1) {
                    // Valid data
                    customBandStops = loaded;
                } else {
                    // Invalid/corrupt data - clear it
                    localStorage.removeItem('customBandStops');
                    customBandStops = null;
                }
                
                // Update the scheme definition immediately (fast, just updates array)
                if (window.COLOR_SCHEMES && customBandStops) {
                    const newScheme = [];
                    for (let i = 0; i < customBandStops.length; i++) {
                        newScheme.push({
                            stop: customBandStops[i],
                            color: new THREE.Color(DEFAULT_BAND_COLORS[i])
                        });
                    }
                    window.COLOR_SCHEMES['hypsometric-banded'] = newScheme;
                }
                // Don't trigger terrain update yet - terrain might not be loaded
            } catch (e) {
                console.error('[BandEditor] Failed to load custom stops:', e);
                localStorage.removeItem('customBandStops');
                customBandStops = null;
            }
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose for debugging
    window.BandEditor = {
        resetToDefaults,
        getCustomStops: () => customBandStops,
        setCustomStops: (stops) => {
            customBandStops = stops;
            saveCustomStops();
            updateColorScheme();
        }
    };
})();

