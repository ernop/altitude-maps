/**
 * HUD System Module
 * 
 * PURPOSE:
 * Complete HUD overlay management - dragging, position persistence, settings, and content updates.
 * 
 * FEATURES:
 * - HUD dragging (position management)
 * - HUD position persistence (localStorage)
 * - HUD show/hide toggle
 * - HUD settings panel (units, visible fields)
 * - HUD content updates (elevation, slope, aspect from mouse position)
 * - HUD minimize/restore
 * 
 * DESIGN NOTES:
 * - Self-contained HUD logic
 * - Easy to add new HUD fields
 * - Clear separation from main viewer logic
 * - Follows LLM-friendly pattern: explicit over implicit
 * 
 * DEPENDS ON:
 * - Global: window.hudSettings, window.currentMouseX, window.currentMouseY
 * - Global: window.processedData, window.derivedSlopeDeg, window.derivedAspectDeg
 * - Functions: raycastToWorld() (from GeometryUtils)
 * - Functions: worldToGridIndex() (from GeometryUtils)
 * - Functions: isWorldInsideData() (from GeometryUtils)
 * - Functions: getSlopeDegrees(), getAspectDegrees() (from viewer-advanced)
 * - Functions: formatElevation() (from FormatUtils)
 */

(function() {
    'use strict';

    // Prevent duplicate initialization
    if (window.HUDSystem) {
        console.warn('[HUDSystem] Already initialized');
        return;
    }

    let initialized = false;
    let isDragging = false;
    let dragOffsetX, dragOffsetY;
    
    // Cache DOM element references (avoid repeated getElementById calls)
    let hudElement = null;
    let geocodeEl = null;
    let elevEl = null;
    let slopeEl = null;
    let aspectEl = null;
    
    // Throttle HUD updates to avoid excessive raycasting
    let lastUpdateTime = 0;
    const UPDATE_THROTTLE_MS = 16; // ~60fps max update rate

    /**
     * Initialize HUD system
     * Sets up dragging, position loading, settings, and event handlers
     */
    function init() {
        if (initialized) {
            console.warn('[HUDSystem] init() called multiple times - skipping');
            return;
        }

        // Cache DOM element references
        hudElement = document.getElementById('info');
        geocodeEl = document.getElementById('hud-geocode');
        elevEl = document.getElementById('hud-elev');
        slopeEl = document.getElementById('hud-slope');
        aspectEl = document.getElementById('hud-aspect');
        
        if (!hudElement) {
            console.warn('[HUDSystem] HUD element #info not found');
            return;
        }

        // Load settings
        loadSettings();

        // Setup dragging
        initDragging();

        // Setup show/hide toggle
        setupShowHideToggle();

        // Setup minimize/expand buttons
        setupMinimizeExpand();

        // Setup settings panel
        setupSettingsPanel();

        // Load saved position
        loadPosition();

        // Apply settings to UI
        applySettingsToUI();

        // Bind settings handlers
        bindSettingsHandlers();

        initialized = true;
        console.log('[HUDSystem] Initialized successfully');
    }

    /**
     * Setup HUD dragging functionality
     */
    function initDragging() {
        if (!hudElement) return;

        hudElement.addEventListener('mousedown', (e) => {
            // Don't start drag if clicking on buttons or inputs
            if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT') {
                return;
            }

            isDragging = true;
            const rect = hudElement.getBoundingClientRect();
            dragOffsetX = e.clientX - rect.left;
            dragOffsetY = e.clientY - rect.top;
            e.preventDefault();
            e.stopPropagation();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;

            // Calculate new position instantly
            let newLeft = e.clientX - dragOffsetX;
            let newTop = e.clientY - dragOffsetY;

            // Keep HUD within viewport bounds
            const maxLeft = window.innerWidth - hudElement.offsetWidth - 10;
            const maxTop = window.innerHeight - hudElement.offsetHeight - 10;
            newLeft = Math.max(10, Math.min(newLeft, maxLeft));
            newTop = Math.max(10, Math.min(newTop, maxTop));

            // Apply instantly without any delay
            hudElement.style.left = newLeft + 'px';
            hudElement.style.top = newTop + 'px';
        }, { passive: false });

        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                savePosition();
            }
        });
    }

    /**
     * Setup show/hide toggle
     */
    function setupShowHideToggle() {
        const showHUDCheckbox = document.getElementById('showHUD');
        if (showHUDCheckbox && hudElement) {
            showHUDCheckbox.addEventListener('change', () => {
                hudElement.style.display = showHUDCheckbox.checked ? 'block' : 'none';
            });
        }
    }

    /**
     * Setup minimize/expand buttons
     */
    function setupMinimizeExpand() {
        const hudMin = document.getElementById('hud-minimize');
        const hudExp = document.getElementById('hud-expand');
        if (hudMin && hudExp && hudElement) {
            hudMin.addEventListener('click', () => {
                hudElement.style.display = 'none';
                hudExp.style.display = 'block';
                // Uncheck showHUD checkbox
                const showHUDCheckbox = document.getElementById('showHUD');
                if (showHUDCheckbox) showHUDCheckbox.checked = false;
            });
            hudExp.addEventListener('click', () => {
                hudElement.style.display = '';
                hudExp.style.display = 'none';
                // Check showHUD checkbox
                const showHUDCheckbox = document.getElementById('showHUD');
                if (showHUDCheckbox) showHUDCheckbox.checked = true;
            });
        }
    }

    /**
     * Setup settings panel toggle
     */
    function setupSettingsPanel() {
        const hudConfigBtn = document.getElementById('hud-config');
        const hudConfigPanel = document.getElementById('hud-config-panel');
        if (hudConfigBtn && hudConfigPanel) {
            hudConfigBtn.addEventListener('click', () => {
                const visible = hudConfigPanel.style.display !== 'none';
                hudConfigPanel.style.display = visible ? 'none' : 'block';
            });
        }
    }

    function savePosition() {
        if (!hudElement) return;
        try {
            const position = {
                left: hudElement.style.left,
                top: hudElement.style.top
            };
            localStorage.setItem('hudPosition', JSON.stringify(position));
        } catch (_) { }
    }

    /**
     * Load HUD position from localStorage
     */
    function loadPosition() {
        if (!hudElement) return;
        try {
            const saved = localStorage.getItem('hudPosition');
            if (saved) {
                const position = JSON.parse(saved);
                if (position.left) hudElement.style.left = position.left;
                if (position.top) hudElement.style.top = position.top;
            }
        } catch (_) { }
    }

    /**
     * Load HUD settings from localStorage
     */
    function loadSettings() {
        try {
            const raw = localStorage.getItem('hudSettings');
            const parsed = raw ? JSON.parse(raw) : null;
            window.hudSettings = parsed || {
                units: 'metric', // 'metric'|'imperial'|'both'
                show: { geocode: true, elevation: true, slope: true, aspect: true, distance: false }
            };
        } catch (_) {
            window.hudSettings = { units: 'metric', show: { geocode: true, elevation: true, slope: true, aspect: true, distance: false } };
        }
    }

    /**
     * Save HUD settings to localStorage
     */
    function saveSettings() {
        try {
            localStorage.setItem('hudSettings', JSON.stringify(window.hudSettings));
        } catch (_) { }
    }

    /**
     * Apply HUD settings to UI elements
     */
    function applySettingsToUI() {
        if (!window.hudSettings) return;
        const u = window.hudSettings.units;
        const unitsRadios = document.querySelectorAll('input[name="hud-units"]');
        unitsRadios.forEach(r => { r.checked = (r.value === u); });

        const rowGeocode = document.getElementById('hud-row-geocode');
        const rowElev = document.getElementById('hud-row-elev');
        const rowSlope = document.getElementById('hud-row-slope');
        const rowAspect = document.getElementById('hud-row-aspect');
        const rowRelief = document.getElementById('hud-row-relief');
        if (rowGeocode) rowGeocode.style.display = window.hudSettings.show.geocode ? '' : 'none';
        if (rowElev) rowElev.style.display = window.hudSettings.show.elevation ? '' : 'none';
        if (rowSlope) rowSlope.style.display = window.hudSettings.show.slope ? '' : 'none';
        if (rowAspect) rowAspect.style.display = window.hudSettings.show.aspect ? '' : 'none';
        if (rowRelief) rowRelief.style.display = window.hudSettings.show.relief ? '' : 'none';

        const chkGeocode = document.getElementById('hud-show-geocode');
        const chkElev = document.getElementById('hud-show-elev');
        const chkSlope = document.getElementById('hud-show-slope');
        const chkAspect = document.getElementById('hud-show-aspect');
        const chkRelief = document.getElementById('hud-show-relief');
        if (chkGeocode) chkGeocode.checked = !!window.hudSettings.show.geocode;
        if (chkElev) chkElev.checked = !!window.hudSettings.show.elevation;
        if (chkSlope) chkSlope.checked = !!window.hudSettings.show.slope;
        if (chkAspect) chkAspect.checked = !!window.hudSettings.show.aspect;
        if (chkRelief) chkRelief.checked = !!window.hudSettings.show.relief;
    }

    /**
     * Bind settings panel event handlers
     */
    function bindSettingsHandlers() {
        // Units
        document.querySelectorAll('input[name="hud-units"]').forEach(r => {
            r.addEventListener('change', (e) => {
                if (e.target.checked) {
                    window.hudSettings.units = e.target.value;
                    saveSettings();
                    // Refresh current HUD display
                    if (typeof window.currentMouseX === 'number' && typeof window.currentMouseY === 'number') {
                        update(window.currentMouseX, window.currentMouseY);
                    }
                }
            });
        });

        // Visibility
        const vis = [
            { id: 'hud-show-geocode', key: 'geocode' },
            { id: 'hud-show-elev', key: 'elevation' },
            { id: 'hud-show-slope', key: 'slope' },
            { id: 'hud-show-aspect', key: 'aspect' },
            { id: 'hud-show-relief', key: 'relief' }
        ];
        vis.forEach(({ id, key }) => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('change', () => {
                    window.hudSettings.show[key] = !!el.checked;
                    saveSettings();
                    applySettingsToUI();
                });
            }
        });
    }

    /**
     * Update HUD content with elevation, slope, and aspect data
     * PERFORMANCE OPTIMIZED:
     * - Early exit if HUD not visible
     * - Throttled updates (~60fps max)
     * - Cached DOM element references
     * - Skip expensive raycasting when not needed
     * @param {number} clientX - Mouse X position
     * @param {number} clientY - Mouse Y position
     */
    function update(clientX, clientY) {
        // Early exit if HUD not visible or elements not cached
        if (!hudElement || !elevEl || hudElement.style.display === 'none') {
            return;
        }
        
        if (!window.processedData) {
            if (elevEl) elevEl.textContent = '--';
            if (geocodeEl) geocodeEl.textContent = '--';
            if (slopeEl) slopeEl.textContent = '--';
            if (aspectEl) aspectEl.textContent = '--';
            return;
        }

        // Throttle updates to avoid excessive raycasting
        const now = performance.now();
        if (now - lastUpdateTime < UPDATE_THROTTLE_MS) {
            return;
        }
        lastUpdateTime = now;

        // Raycast to get world position
        if (typeof window.GeometryUtils === 'undefined' || typeof window.GeometryUtils.raycastToWorld !== 'function') {
            return;
        }
        const world = window.GeometryUtils.raycastToWorld(clientX, clientY);
        if (!world) {
            if (geocodeEl) geocodeEl.textContent = '--';
            elevEl.textContent = '--';
            if (slopeEl) slopeEl.textContent = '--';
            if (aspectEl) aspectEl.textContent = '--';
            return;
        }

        // Ignore when cursor is outside data footprint
        if (typeof window.GeometryUtils.isWorldInsideData === 'function') {
            if (!window.GeometryUtils.isWorldInsideData(world.x, world.z)) {
                if (geocodeEl) geocodeEl.textContent = '--';
                elevEl.textContent = '--';
                if (slopeEl) slopeEl.textContent = '--';
                if (aspectEl) aspectEl.textContent = '--';
                return;
            }
        }

        // Get grid index
        if (typeof window.GeometryUtils.worldToGridIndex !== 'function') {
            return;
        }
        const idx = window.GeometryUtils.worldToGridIndex(world.x, world.z);
        if (!idx) return;

        const zCell = (window.processedData.elevation[idx.i] && window.processedData.elevation[idx.i][idx.j]);
        const hasData = (zCell != null) && isFinite(zCell);
        if (!hasData) {
            if (geocodeEl) geocodeEl.textContent = '--';
            elevEl.textContent = '--';
            if (slopeEl) slopeEl.textContent = '--';
            if (aspectEl) aspectEl.textContent = '--';
            return;
        }

        // Update geocode (lat/lon) - only if geocode row is visible
        if (geocodeEl && typeof window.GeometryUtils.worldToLonLat === 'function') {
            // Check if geocode should be shown (from settings)
            const showGeocode = window.hudSettings && window.hudSettings.show && window.hudSettings.show.geocode !== false;
            if (showGeocode) {
                const geo = window.GeometryUtils.worldToLonLat(world.x, world.z);
                if (geo && geo.lat != null && geo.lon != null) {
                    const latStr = geo.lat >= 0 ? `${geo.lat.toFixed(4)}°N` : `${Math.abs(geo.lat).toFixed(4)}°S`;
                    const lonStr = geo.lon >= 0 ? `${geo.lon.toFixed(4)}°E` : `${Math.abs(geo.lon).toFixed(4)}°W`;
                    geocodeEl.textContent = `${latStr}, ${lonStr}`;
                } else {
                    geocodeEl.textContent = '--';
                }
            }
        }

        const zMeters = zCell;
        
        // Get slope and aspect (these functions are in viewer-advanced.js)
        let s = null;
        let a = null;
        if (typeof getSlopeDegrees === 'function') {
            s = getSlopeDegrees(idx.i, idx.j);
        }
        if (typeof getAspectDegrees === 'function') {
            a = getAspectDegrees(idx.i, idx.j);
        }

        const units = (window.hudSettings && window.hudSettings.units) || 'metric';
        
        // Format elevation
        let elevText = '--';
        if (typeof window.FormatUtils !== 'undefined' && typeof window.FormatUtils.formatElevation === 'function') {
            elevText = window.FormatUtils.formatElevation(zMeters, units);
        } else {
            elevText = `${zMeters.toFixed(0)}m`;
        }

        elevEl.textContent = elevText;
        if (slopeEl) slopeEl.textContent = (s != null && isFinite(s)) ? `${s.toFixed(1)}deg` : '--';
        if (aspectEl) aspectEl.textContent = (a != null && isFinite(a)) ? `${Math.round(a)}deg` : '--';
    }

    function show() {
        if (hudElement) {
            hudElement.style.display = 'block';
            const showHUDCheckbox = document.getElementById('showHUD');
            if (showHUDCheckbox) showHUDCheckbox.checked = true;
        }
    }

    /**
     * Hide HUD
     */
    function hide() {
        if (hudElement) {
            hudElement.style.display = 'none';
            const showHUDCheckbox = document.getElementById('showHUD');
            if (showHUDCheckbox) showHUDCheckbox.checked = false;
        }
    }

    /**
     * Check if HUD is visible
     * @returns {boolean}
     */
    function isVisible() {
        return hudElement && hudElement.style.display !== 'none';
    }

    // Export module
    window.HUDSystem = {
        init: init,
        update: update,
        show: show,
        hide: hide,
        isVisible: isVisible,
        loadSettings: loadSettings,
        saveSettings: saveSettings
    };

})();

