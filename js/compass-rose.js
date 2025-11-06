/**
 * Compass Rose Module
 * 
 * PURPOSE:
 * Edge markers with click handling for region navigation.
 * Extends edge-markers.js functionality with interactive click/hover behavior.
 * 
 * FEATURES:
 * - Click detection on edge markers
 * - Raycasting to detect marker clicks
 * - Button boundary detection (UV coordinate mapping)
 * - Hover state management (cursor changes, visual feedback)
 * - Region loading on click
 * - Show/hide toggle for edge markers
 * 
 * DESIGN NOTES:
 * - Complete compass rose feature in one module
 * - Easy to experiment with different click/hover behaviors
 * - Clear separation from main viewer event handling
 * - Follows LLM-friendly pattern: explicit over implicit
 * 
 * DEPENDS ON:
 * - edge-markers.js (marker creation via window.EdgeMarkers)
 * - Global: window.edgeMarkers, window.regionAdjacency, window.currentRegionId
 * - Global: window.camera, window.renderer, window.raycaster
 * - Functions: loadRegion() (from viewer-advanced)
 * - Functions: updateHoverState() (from edge-markers.js)
 */

(function() {
    'use strict';

    // Prevent duplicate initialization
    if (window.CompassRose) {
        console.warn('[CompassRose] Already initialized');
        return;
    }

    let initialized = false;
    let currentHoveredMarker = null;
    let currentHoveredButtonIndex = -1;

    /**
     * Initialize compass rose system
     * Sets up click and hover event listeners
     * @param {THREE.Raycaster} raycaster - Raycaster for intersection tests
     * @param {THREE.Camera} camera - Camera for raycasting
     * @param {THREE.WebGLRenderer} renderer - Renderer for DOM element access
     */
    function init(raycaster, camera, renderer) {
        if (initialized) {
            console.warn('[CompassRose] init() called multiple times - skipping');
            return;
        }

        if (!raycaster || !camera || !renderer) {
            console.error('[CompassRose] Missing required parameters (raycaster, camera, renderer)');
            return;
        }

        // Store references
        window.__compassRoseRaycaster = raycaster;
        window.__compassRoseCamera = camera;
        window.__compassRoseRenderer = renderer;

        // Setup click handler
        setupClickHandler(renderer);

        // Setup hover handler
        setupHoverHandler(renderer);

        // Setup show/hide toggle
        setupShowHideToggle();

        initialized = true;
        console.log('[CompassRose] Initialized successfully');
    }

    /**
     * Setup click handler for edge markers
     */
    function setupClickHandler(renderer) {
        renderer.domElement.addEventListener('click', (e) => {
            if (e.button !== 0) return; // Only left click

            const mouse = new THREE.Vector2();
            mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;

            const raycaster = window.__compassRoseRaycaster;
            const camera = window.__compassRoseCamera;
            if (!raycaster || !camera) return;

            raycaster.setFromCamera(mouse, camera);

            if (window.edgeMarkers && window.edgeMarkers.length > 0) {
                const intersects = raycaster.intersectObjects(window.edgeMarkers);
                if (intersects.length > 0) {
                    handleClick(intersects[0]);
                }
            }
        });
    }

    /**
     * Handle click on edge marker
     * @param {Object} intersection - Raycaster intersection result
     */
    function handleClick(intersection) {
        const marker = intersection.object;

        // Check if this marker has clickable neighbors
        if (!marker.userData.isClickable || !marker.userData.neighborIds || marker.userData.neighborIds.length === 0) {
            return;
        }

        // Use EXACT button bounds calculated during canvas drawing
        const uv = intersection.uv;
        const buttonBounds = marker.userData.buttonBounds || [];

        // Find which button was clicked by checking UV.y against exact bounds
        let clickedButton = null;
        for (const bounds of buttonBounds) {
            // bounds.uvTop is higher (closer to 1)
            // bounds.uvBottom is lower (closer to 0)
            if (uv.y >= bounds.uvBottom && uv.y <= bounds.uvTop) {
                clickedButton = bounds;
                break;
            }
        }

        if (clickedButton) {
            // Clicked on a specific button - load that neighbor
            const neighborId = marker.userData.neighborIds[clickedButton.index];
            const neighborName = marker.userData.neighborNames[clickedButton.index];
            console.log(`[CompassRose] Clicked button ${clickedButton.index + 1}/${buttonBounds.length}: ${neighborName} (UV.y=${uv.y.toFixed(3)}, bounds=[${clickedButton.uvBottom.toFixed(3)}, ${clickedButton.uvTop.toFixed(3)}])`);
            
            if (typeof loadRegion === 'function') {
                loadRegion(neighborId);
            } else {
                console.error('[CompassRose] loadRegion function not available');
            }
        } else {
            // Clicked on compass letter area or outside buttons - load first neighbor
            const neighborId = marker.userData.neighborIds[0];
            const neighborName = marker.userData.neighborNames[0];
            console.log(`[CompassRose] Clicked outside buttons (UV.y=${uv.y.toFixed(3)}) -> loading ${neighborName}`);
            
            if (typeof loadRegion === 'function') {
                loadRegion(neighborId);
            } else {
                console.error('[CompassRose] loadRegion function not available');
            }
        }
    }

    /**
     * Setup hover handler for edge markers
     */
    function setupHoverHandler(renderer) {
        renderer.domElement.addEventListener('mousemove', (e) => {
            const mouse = new THREE.Vector2();
            mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;

            const raycaster = window.__compassRoseRaycaster;
            const camera = window.__compassRoseCamera;
            if (!raycaster || !camera) return;

            raycaster.setFromCamera(mouse, camera);

            if (window.edgeMarkers && window.edgeMarkers.length > 0) {
                const intersects = raycaster.intersectObjects(window.edgeMarkers);
                handleHover(intersects);
            } else {
                // No markers - reset cursor
                renderer.domElement.style.cursor = 'default';
                clearHoverState();
            }
        });
    }

    /**
     * Handle hover on edge markers
     * @param {Array} intersects - Array of raycaster intersection results
     */
    function handleHover(intersects) {
        const renderer = window.__compassRoseRenderer;
        if (!renderer) return;

        // Check if hovering over a clickable marker
        let isHoveringClickable = false;
        let hoveredMarker = null;
        let hoveredButtonIndex = -1;

        if (intersects.length > 0) {
            const marker = intersects[0].object;
            if (marker.userData.isClickable) {
                isHoveringClickable = true;
                hoveredMarker = marker;

                // Check which button is being hovered (if any)
                const uv = intersects[0].uv;
                const buttonBounds = marker.userData.buttonBounds || [];
                for (const bounds of buttonBounds) {
                    if (uv.y >= bounds.uvBottom && uv.y <= bounds.uvTop) {
                        hoveredButtonIndex = bounds.index;
                        break;
                    }
                }
            }
        }

        // Update cursor
        renderer.domElement.style.cursor = isHoveringClickable ? 'pointer' : 'default';

        // Update hover visual state
        if (hoveredMarker !== currentHoveredMarker || hoveredButtonIndex !== currentHoveredButtonIndex) {
            // Clear previous hover state
            clearHoverState();

            // Set new hover state
            if (hoveredMarker && hoveredButtonIndex >= 0) {
                // Hovering over a specific button
                if (window.EdgeMarkers && typeof window.EdgeMarkers.updateHoverState === 'function') {
                    window.EdgeMarkers.updateHoverState(hoveredMarker, hoveredButtonIndex);
                }
                currentHoveredMarker = hoveredMarker;
                currentHoveredButtonIndex = hoveredButtonIndex;
            } else if (hoveredMarker) {
                // Hovering over marker but not a specific button
                if (window.EdgeMarkers && typeof window.EdgeMarkers.updateHoverState === 'function') {
                    window.EdgeMarkers.updateHoverState(hoveredMarker, -1);
                }
                currentHoveredMarker = hoveredMarker;
                currentHoveredButtonIndex = -1;
            }
        }
    }

    /**
     * Clear hover state
     */
    function clearHoverState() {
        if (currentHoveredMarker && window.EdgeMarkers && typeof window.EdgeMarkers.updateHoverState === 'function') {
            window.EdgeMarkers.updateHoverState(currentHoveredMarker, -1);
        }
        currentHoveredMarker = null;
        currentHoveredButtonIndex = -1;
    }

    /**
     * Setup show/hide toggle for edge markers
     */
    function setupShowHideToggle() {
        const showEdgeMarkersCheckbox = document.getElementById('showEdgeMarkers');
        if (!showEdgeMarkersCheckbox) return;

        // Load saved preference from localStorage (default: true)
        const savedEdgeMarkersVisible = localStorage.getItem('edgeMarkersVisible');
        if (savedEdgeMarkersVisible !== null) {
            showEdgeMarkersCheckbox.checked = savedEdgeMarkersVisible === 'true';
        }

        // Apply initial visibility state
        updateMarkersVisibility(showEdgeMarkersCheckbox.checked);

        // Add change listener
        showEdgeMarkersCheckbox.addEventListener('change', () => {
            const visible = showEdgeMarkersCheckbox.checked;
            updateMarkersVisibility(visible);
            // Save preference to localStorage
            localStorage.setItem('edgeMarkersVisible', String(visible));
        });
    }

    /**
     * Update edge markers visibility
     * @param {boolean} visible - Whether markers should be visible
     */
    function updateMarkersVisibility(visible) {
        if (window.edgeMarkers) {
            window.edgeMarkers.forEach(marker => {
                marker.visible = visible;
            });
        }
    }

    /**
     * Update compass rose (called when markers are recreated)
     */
    function update() {
        // Reapply visibility state if checkbox exists
        const showEdgeMarkersCheckbox = document.getElementById('showEdgeMarkers');
        if (showEdgeMarkersCheckbox && window.edgeMarkers) {
            updateMarkersVisibility(showEdgeMarkersCheckbox.checked);
        }
    }

    // Export module
    window.CompassRose = {
        init: init,
        update: update,
        handleClick: handleClick,
        handleHover: handleHover
    };

})();

