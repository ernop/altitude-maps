/**
 * UI Controls Manager Module
 * 
 * PURPOSE:
 * Centralized setup and coordination of all UI controls.
 * Handles all user input controls: region selector, render mode, vertical exaggeration,
 * color scheme, and other UI toggles.
 * 
 * FEATURES:
 * - Region selector dropdown with search/filter
 * - Render mode selector
 * - Vertical exaggeration controls (slider + input + buttons)
 * - Color scheme selector + quick jump buttons
 * - Grid toggle, auto-rotate toggle
 * - Mobile UI toggle
 * - URL parameter synchronization
 * - Control state synchronization (sync input ↔ slider)
 * 
 * DESIGN NOTES:
 * - All event handlers centralized here for easy discovery
 * - Updates shared state (window.params) explicitly
 * - Calls other modules via direct function calls (explicit, traceable)
 * - Follows LLM-friendly pattern: explicit over implicit
 * 
 * DEPENDS ON:
 * - Global: window.params, window.regionIdToName, window.regionNameToId, window.regionOptions
 * - Global: window.currentRegionId, window.controlsInitialized
 * - Functions: loadRegion(), recreateTerrain(), updateColors(), updateTerrainHeight()
 * - Functions: multiplierToInternal(), internalToMultiplier(), updateVertExagButtons()
 * - Functions: updateURLParameter(), resolveRegionIdFromInput(), computeAutoStretchStats()
 * - Functions: updateEdgeMarkers() (from edge-markers.js)
 * - Functions: updateColorSchemeDescription() (from color-schemes.js)
 * - Functions: initResolutionScale() (from resolution-controls.js)
 */

(function() {
    'use strict';

    // Prevent duplicate initialization
    if (window.UIControlsManager) {
        console.warn('[UIControlsManager] Already initialized');
        return;
    }

    let initialized = false;

    /**
     * Initialize all UI controls
     * Sets up event listeners for all controls
     */
    function init() {
        if (initialized) {
            console.warn('[UIControlsManager] init() called multiple times - skipping to prevent memory leak');
            return;
        }

        // Region selector dropdown
        setupRegionSelector();

        // Render mode selector
        setupRenderMode();

        // Vertical exaggeration controls
        setupVerticalExaggeration();

        // Color scheme controls
        setupColorScheme();

        // Initialize resolution scale control (from resolution-controls.js)
        try {
            if (typeof initResolutionScale === 'function') {
                initResolutionScale();
            }
        } catch (e) {
            console.warn('[UIControlsManager] Failed to initialize resolution scale:', e);
        }

        // Initialize vertical exaggeration button states
        if (typeof updateVertExagButtons === 'function' && window.params) {
            updateVertExagButtons(window.params.verticalExaggeration);
        }

        initialized = true;
        console.log('[UIControlsManager] Controls initialized successfully');
    }

    /**
     * Setup region selector dropdown with search/filter
     */
    function setupRegionSelector() {
        const regionInput = document.getElementById('regionSelect');
        const dropdown = document.getElementById('regionDropdown');
        if (!regionInput || !dropdown) return;

        let highlightedIndex = -1;
        let filteredOptions = [];

        function renderDropdown(items) {
            dropdown.innerHTML = '';
            let selectableIndex = 0; // Track index of selectable items only
            items.forEach((opt, idx) => {
                // Render a non-selectable divider
                if (opt.id === '__divider__') {
                    const div = document.createElement('div');
                    div.setAttribute('data-divider', 'true');
                    div.style.margin = '6px 0';
                    div.style.borderTop = '1px solid rgba(85,136,204,0.35)';
                    div.style.opacity = '0.8';
                    dropdown.appendChild(div);
                    return;
                }
                // Render a non-selectable header
                if (opt.id === '__header__') {
                    const header = document.createElement('div');
                    header.setAttribute('data-header', 'true');
                    header.textContent = opt.name;
                    header.className = 'region-dropdown-header';
                    dropdown.appendChild(header);
                    return;
                }
                // Render selectable item
                const row = document.createElement('div');
                row.textContent = opt.name;
                row.setAttribute('data-id', opt.id);
                row.setAttribute('data-selectable-index', selectableIndex.toString());
                row.style.padding = '8px 10px';
                row.style.cursor = 'pointer';
                row.style.fontSize = '12px';
                row.style.borderBottom = '1px solid rgba(85,136,204,0.12)';
                row.addEventListener('mouseenter', () => setHighlight(selectableIndex));
                row.addEventListener('mouseleave', () => setHighlight(-1));
                row.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    commitSelection(opt);
                });
                dropdown.appendChild(row);
                selectableIndex++;
            });
            updateHighlight();
        }

        function openDropdown() {
            // Always rebuild options from manifest to ensure fresh data
            if (typeof buildRegionOptions === 'function') {
                filteredOptions = buildRegionOptions();
            } else {
                filteredOptions = window.regionOptions ? window.regionOptions.slice() : [];
            }
            highlightedIndex = -1;
            renderDropdown(filteredOptions);
            dropdown.style.display = 'block';
        }

        function closeDropdown() {
            dropdown.style.display = 'none';
            highlightedIndex = -1;
        }

        function setHighlight(idx) {
            highlightedIndex = idx;
            updateHighlight();
        }

        function updateHighlight() {
            const children = dropdown.children;
            for (let i = 0; i < children.length; i++) {
                const el = children[i];
                // Skip styling dividers and headers
                if (el.getAttribute('data-divider') === 'true' || el.getAttribute('data-header') === 'true') {
                    el.style.background = 'transparent';
                    el.style.color = '#fff';
                    continue;
                }
                // Compare against selectable index, not DOM index
                const selectableIdx = parseInt(el.getAttribute('data-selectable-index') || '-1', 10);
                if (selectableIdx === highlightedIndex) {
                    el.style.background = 'rgba(85,136,204,0.3)';
                    el.style.color = '#fff';
                } else {
                    el.style.background = 'transparent';
                    el.style.color = '#fff';
                }
            }
        }

        function filterOptions(query) {
            const q = (query || '').trim().toLowerCase();
            if (!q || !window.regionOptions) return window.regionOptions ? window.regionOptions.slice() : [];
            return window.regionOptions.filter(o => o.id !== '__divider__' && o.id !== '__header__' && o.name.toLowerCase().includes(q));
        }

        function commitSelection(opt) {
            if (!opt || opt.id === '__divider__' || opt.id === '__header__') return;
            regionInput.value = opt.name;
            closeDropdown();
            if (opt.id && opt.id !== window.currentRegionId && typeof loadRegion === 'function') {
                loadRegion(opt.id);
            }
        }

        regionInput.addEventListener('focus', () => {
            openDropdown();
            regionInput.select();
        });

        regionInput.addEventListener('click', () => {
            openDropdown();
            regionInput.select();
        });

        regionInput.addEventListener('input', () => {
            filteredOptions = filterOptions(regionInput.value);
            highlightedIndex = filteredOptions.length ? 0 : -1;
            renderDropdown(filteredOptions);
        });

        regionInput.addEventListener('keydown', (e) => {
            if (dropdown.style.display !== 'block') openDropdown();
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (filteredOptions.length) {
                    highlightedIndex = Math.min(filteredOptions.length - 1, highlightedIndex + 1);
                    updateHighlight();
                }
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (filteredOptions.length) {
                    highlightedIndex = Math.max(0, highlightedIndex - 1);
                    updateHighlight();
                }
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (highlightedIndex >= 0 && highlightedIndex < filteredOptions.length) {
                    commitSelection(filteredOptions[highlightedIndex]);
                } else {
                    if (typeof resolveRegionIdFromInput === 'function') {
                        const id = resolveRegionIdFromInput(regionInput.value);
                        if (id) {
                            commitSelection({ id, name: (window.regionIdToName && window.regionIdToName[id]) || regionInput.value });
                        }
                    }
                }
            } else if (e.key === 'Escape') {
                e.preventDefault();
                closeDropdown();
                regionInput.blur();
            }
        });

        document.addEventListener('click', (e) => {
            if (!regionInput.contains(e.target) && !dropdown.contains(e.target)) {
                closeDropdown();
                // Snap back to current shown region if text doesn't match a known name
                if (typeof resolveRegionIdFromInput === 'function') {
                    const id = resolveRegionIdFromInput(regionInput.value);
                    if (!id && window.regionIdToName && window.currentRegionId) {
                        regionInput.value = window.regionIdToName[window.currentRegionId] || window.currentRegionId || '';
                    }
                }
            }
        });
    }

    /**
     * Setup render mode selector
     */
    function setupRenderMode() {
        const renderModeSelect = document.getElementById('renderMode');
        if (!renderModeSelect) return;

        renderModeSelect.addEventListener('change', (e) => {
            let nextMode = e.target.value;
            if (nextMode === 'wireframe' || nextMode === 'surface') {
                // Wireframe and surface disabled: fallback to bars
                nextMode = 'bars';
                e.target.value = 'bars';
            }

            if (!window.params) {
                console.error('[UIControlsManager] window.params not available');
                return;
            }

            window.params.renderMode = nextMode;

            // Clear edge markers so they get recreated at new positions for new render mode
            if (window.terrainGroup && window.edgeMarkers) {
                window.edgeMarkers.forEach(marker => window.terrainGroup.remove(marker));
            }
            if (window.edgeMarkers) {
                window.edgeMarkers.length = 0;
            }

            // Recreate terrain with new render mode
            if (typeof recreateTerrain === 'function') {
                recreateTerrain();
            }

            // Remove focus from dropdown so keyboard navigation works
            e.target.blur();

            // Update URL
            if (typeof updateURLParameter === 'function') {
                updateURLParameter('renderMode', window.params.renderMode);
            }
        });
    }

    /**
     * Setup vertical exaggeration controls (slider + input + buttons)
     */
    function setupVerticalExaggeration() {
        const vertExagSlider = document.getElementById('vertExag');
        const vertExagInput = document.getElementById('vertExagInput');
        if (!vertExagSlider || !vertExagInput || !window.params) return;

        // Debounced updates (no longer needed for surface mode, but kept for potential future use)
        const debouncedUpdate = window.FormatUtils && window.FormatUtils.debounce
            ? window.FormatUtils.debounce(() => {
                // Reserved for future debounced updates if needed
            }, 80)
            : () => {};

        // Schedule vertical exaggeration update (coalesce to once per frame)
        let pendingVertExagRaf = null;
        const scheduleVertExagUpdate = () => {
            if (pendingVertExagRaf !== null) cancelAnimationFrame(pendingVertExagRaf);
            pendingVertExagRaf = requestAnimationFrame(() => {
                pendingVertExagRaf = null;
                if (typeof updateTerrainHeight === 'function') {
                    updateTerrainHeight();
                }
            });
        };

        // Sync slider -> input (update immediately)
        vertExagSlider.addEventListener('input', (e) => {
            const multiplier = parseFloat(e.target.value);
            if (typeof multiplierToInternal === 'function') {
                window.params.verticalExaggeration = multiplierToInternal(multiplier);
            }
            vertExagInput.value = multiplier;

            // Update button states
            if (typeof updateVertExagButtons === 'function') {
                updateVertExagButtons(window.params.verticalExaggeration);
            }

            // Coalesce rapid updates to once-per-frame
            scheduleVertExagUpdate();
        });

        // Finalize on slider change
        vertExagSlider.addEventListener('change', (e) => {
            // Persist user-facing multiplier
            if (typeof internalToMultiplier === 'function' && typeof updateURLParameter === 'function') {
                updateURLParameter('exag', internalToMultiplier(window.params.verticalExaggeration));
            }
        });

        // Sync input -> slider
        vertExagInput.addEventListener('change', (e) => {
            let multiplier = parseFloat(e.target.value);
            // Clamp to valid range (1 to 100)
            multiplier = Math.max(1, Math.min(100, multiplier));

            if (typeof multiplierToInternal === 'function') {
                window.params.verticalExaggeration = multiplierToInternal(multiplier);
            }
            vertExagSlider.value = multiplier;
            vertExagInput.value = multiplier;

            // Update button states
            if (typeof updateVertExagButtons === 'function') {
                updateVertExagButtons(window.params.verticalExaggeration);
            }

            scheduleVertExagUpdate();

            if (typeof updateURLParameter === 'function') {
                updateURLParameter('exag', multiplier);
            }
        });
    }

    /**
     * Setup color scheme controls
     */
    function setupColorScheme() {
        const colorSchemeSelect = document.getElementById('colorScheme');
        if (!colorSchemeSelect || !window.params) return;

        // Use jQuery if available (for consistency with existing code)
        if (typeof $ !== 'undefined' && $.fn.on) {
            $('#colorScheme').on('change', function (e) {
                window.params.colorScheme = $(this).val();
                if (window.params.colorScheme === 'auto-stretch' && typeof computeAutoStretchStats === 'function') {
                    computeAutoStretchStats();
                }
                if (typeof updateColors === 'function') {
                    updateColors();
                }
                if (typeof updateURLParameter === 'function') {
                    updateURLParameter('colorScheme', window.params.colorScheme);
                }
                if (typeof updateColorSchemeDescription === 'function') {
                    updateColorSchemeDescription();
                }
            });
        } else {
            // Fallback to native addEventListener
            colorSchemeSelect.addEventListener('change', (e) => {
                window.params.colorScheme = e.target.value;
                if (window.params.colorScheme === 'auto-stretch' && typeof computeAutoStretchStats === 'function') {
                    computeAutoStretchStats();
                }
                if (typeof updateColors === 'function') {
                    updateColors();
                }
                if (typeof updateURLParameter === 'function') {
                    updateURLParameter('colorScheme', window.params.colorScheme);
                }
                if (typeof updateColorSchemeDescription === 'function') {
                    updateColorSchemeDescription();
                }
            });
        }

        // Color scheme quick jump buttons (move by 1 option)
        const csUpBtn = document.getElementById('colorSchemeUp');
        const csDownBtn = document.getElementById('colorSchemeDown');
        const jumpBy = 1;

        if (colorSchemeSelect && csUpBtn && csDownBtn) {
            const jumpToIndex = (delta) => {
                const total = colorSchemeSelect.options.length;
                let idx = colorSchemeSelect.selectedIndex;
                if (idx < 0) idx = 0;
                let next = idx + delta;
                if (next < 0) next = 0;
                if (next >= total) next = total - 1;
                if (next !== idx) {
                    colorSchemeSelect.selectedIndex = next;
                    // Trigger change event
                    if (typeof $ !== 'undefined' && $.fn.trigger) {
                        $('#colorScheme').trigger('change');
                    } else {
                        colorSchemeSelect.dispatchEvent(new Event('change'));
                    }
                }
            };
            csUpBtn.addEventListener('click', () => jumpToIndex(-jumpBy));
            csDownBtn.addEventListener('click', () => jumpToIndex(+jumpBy));
        }
    }

    /**
     * Sync UI controls from params object
     * Call this after params are loaded/changed to update UI
     */
    function syncFromParams() {
        if (!window.params) return;

        // Sync render mode
        const renderModeSelect = document.getElementById('renderMode');
        if (renderModeSelect && window.params.renderMode) {
            renderModeSelect.value = window.params.renderMode;
        }

        // Sync vertical exaggeration
        const vertExagSlider = document.getElementById('vertExag');
        const vertExagInput = document.getElementById('vertExagInput');
        if (vertExagSlider && vertExagInput && typeof internalToMultiplier === 'function') {
            const multiplier = internalToMultiplier(window.params.verticalExaggeration);
            vertExagSlider.value = multiplier;
            vertExagInput.value = multiplier;
            if (typeof updateVertExagButtons === 'function') {
                updateVertExagButtons(window.params.verticalExaggeration);
            }
        }

        // Sync color scheme
        const colorSchemeSelect = document.getElementById('colorScheme');
        if (colorSchemeSelect && window.params.colorScheme) {
            colorSchemeSelect.value = window.params.colorScheme;
            if (typeof updateColorSchemeDescription === 'function') {
                updateColorSchemeDescription();
            }
        }
    }

    /**
     * Sync URL parameters from current params
     */
    function syncToURL() {
        if (!window.params || typeof updateURLParameter !== 'function') return;

        updateURLParameter('renderMode', window.params.renderMode);
        if (typeof internalToMultiplier === 'function') {
            updateURLParameter('exag', internalToMultiplier(window.params.verticalExaggeration));
        }
        updateURLParameter('colorScheme', window.params.colorScheme);
    }

    // Export module
    window.UIControlsManager = {
        init: init,
        syncFromParams: syncFromParams,
        syncToURL: syncToURL
    };

})();

