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
        document.getElementById('colorScheme').addEventListener('change', updateBandEditorVisibility);
        document.getElementById('resetBands').addEventListener('click', resetToDefaults);

        // Initial visibility check
        updateBandEditorVisibility();
    }

    /**
     * Show/hide band editor based on selected color scheme
     */
    function updateBandEditorVisibility() {
        const colorScheme = document.getElementById('colorScheme').value;
        const bandEditor = document.getElementById('bandEditor');
        
        if (colorScheme === 'hypsometric-banded') {
            bandEditor.style.display = 'block';
            // Lazy load sliders only when first shown
            if (!bandEditor.hasAttribute('data-initialized')) {
                // Defer slider creation to next tick for faster perceived load
                requestAnimationFrame(() => {
                    createBandSliders();
                    bandEditor.setAttribute('data-initialized', 'true');
                });
            }
        } else {
            bandEditor.style.display = 'none';
        }
    }

    /**
     * Create sliders for each band boundary
     */
    function createBandSliders() {
        const container = document.getElementById('bandEditorSliders');
        container.innerHTML = '';

        const stops = customBandStops || DEFAULT_BAND_STOPS.slice();

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
    }

    /**
     * Update a band stop with push behavior - adjacent bands get pushed if needed
     */
    function updateBandStopWithPush(index, value) {
        if (!customBandStops) {
            customBandStops = DEFAULT_BAND_STOPS.slice();
        }

        const MIN_GAP = 0.01; // Minimum gap between bands (1%)
        
        // If trying to push past next band, push it up
        if (index < customBandStops.length - 1) {
            const next = customBandStops[index + 1];
            if (value + MIN_GAP >= next) {
                const pushValue = value + MIN_GAP;
                customBandStops[index + 1] = Math.min(customBandStops[index + 2] - MIN_GAP, pushValue);
                updateSliderDisplay(index + 1);
            }
        }

        // If trying to push past previous band, push it down
        if (index > 0) {
            const prev = customBandStops[index - 1];
            if (value - MIN_GAP <= prev) {
                const pushValue = value - MIN_GAP;
                customBandStops[index - 1] = Math.max(customBandStops[index - 2] + MIN_GAP, pushValue);
                updateSliderDisplay(index - 1);
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
            console.log('[BandEditor] Cannot update - missing customBandStops or COLOR_SCHEMES');
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
        console.log('[BandEditor] Updated scheme with stops:', customBandStops.map(s => Math.round(s * 100) + '%').join(', '));

        // Trigger terrain update only if this scheme is active
        if (window.params && window.params.colorScheme === 'hypsometric-banded') {
            console.log('[BandEditor] Triggering terrain update...');
            if (window.MapShading && typeof window.MapShading.updateAll === 'function') {
                window.MapShading.updateAll();
                console.log('[BandEditor] MapShading.updateAll() called');
            } else {
                console.warn('[BandEditor] MapShading.updateAll not available');
            }
            if (typeof window.updateColorLegend === 'function') {
                window.updateColorLegend();
                console.log('[BandEditor] updateColorLegend() called');
            } else {
                console.warn('[BandEditor] updateColorLegend not available');
            }
        } else {
            console.log('[BandEditor] Scheme not active, current scheme:', window.params ? window.params.colorScheme : 'params not available');
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
                customBandStops = JSON.parse(stored);
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
                console.error('Failed to load custom band stops:', e);
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

