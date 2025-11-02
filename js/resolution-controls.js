/**
 * Resolution Controls Module
 * 
 * PURPOSE:
 * Manages the resolution slider UI and bucket size adjustments.
 * Provides user controls for terrain detail level (bucket size = pixel grouping).
 * 
 * FEATURES:
 * - Logarithmic slider for intuitive resolution control (1x to 500x)
 * - One-click presets: MAX (1x), DEFAULT (auto-calculated)
 * - Granular adjust buttons (+/-1, +/-5, +/-10)
 * - Press-and-hold repeat for buttons
 * - Visual loading overlay during resolution changes
 * - Snap-to-tick behavior for precise control
 * 
 * DESIGN NOTES:
 * - Bucket size = how many pixels to group together
 * - Lower bucket size = higher resolution (more detail, slower)
 * - Higher bucket size = lower resolution (less detail, faster)
 * - Logarithmic mapping makes the slider feel natural across huge range
 * 
 * DEPENDS ON:
 * - Global: params, rawElevationData, processedData, scene, edgeMarkers, pendingBucketTimeout
 * - Functions: rebucketData(), recreateTerrain(), updateStats(), updateURLParameter(), appendActivityLog()
 */

/**
 * Show the resolution loading overlay
 */
function showResolutionLoading() {
    const overlay = document.getElementById('resolution-loading-overlay');
    if (overlay) {
        overlay.classList.add('active');
    }
}

/**
 * Hide the resolution loading overlay
 */
function hideResolutionLoading() {
    const overlay = document.getElementById('resolution-loading-overlay');
    if (overlay) {
        overlay.classList.remove('active');
    }
}

// ===== COMPACT RESOLUTION SCALE (logarithmic mapping) =====
/**
 * Convert bucket size to slider percent (logarithmic)
 * @param {number} size - Bucket size (1-500)
 * @returns {number} Slider percentage (0-100)
 */
function bucketSizeToPercent(size) {
    const clamped = Math.max(1, Math.min(500, parseInt(size)));
    const maxLog = Math.log(500);
    const valLog = Math.log(clamped);
    return (valLog / maxLog) * 100; // 1..500 -> 0..100% in log domain
}

/**
 * Convert slider percent to bucket size (logarithmic)
 * @param {number} percent - Slider percentage (0-100)
 * @returns {number} Bucket size (1-500)
 */
function percentToBucketSize(percent) {
    const p = Math.max(0, Math.min(100, percent));
    const maxLog = Math.log(500);
    const logVal = (p / 100) * maxLog;
    const size = Math.round(Math.exp(logVal));
    return Math.max(1, Math.min(500, size));
}

/**
 * Update the visual position of the resolution slider handle
 * @param {number} size - Current bucket size
 */
function updateResolutionScaleUI(size) {
    const track = document.querySelector('#resolution-scale .resolution-scale-track');
    const handle = document.getElementById('resolutionScaleHandle');
    const fill = document.getElementById('resolutionScaleFill');
    const tag = document.getElementById('resolutionScaleTag');
    if (!track || !handle || !fill) return;
    const pct = bucketSizeToPercent(size);
    const rect = track.getBoundingClientRect();
    const x = (pct / 100) * rect.width;
    handle.style.left = `${x}px`;
    fill.style.width = `${Math.max(0, Math.min(100, (x / rect.width) * 100))}%`;
    if (tag) { tag.style.left = `${x}px`; tag.textContent = `${size}\u00D7`; }
}

/**
 * Initialize the resolution scale slider with drag, click, and preset controls
 * @global params - Parameters object
 * @global scene - Three.js scene
 * @global edgeMarkers - Array of edge marker sprites
 * @global pendingBucketTimeout - Timeout handle for debounced bucket updates
 */
function initResolutionScale() {
    const container = document.getElementById('resolution-scale');
    const track = container && container.querySelector('.resolution-scale-track');
    const maxBtn = document.getElementById('resolutionMaxLabel');
    if (!container || !track) return;

    let isDragging = false;
    let lastSetSize = params.bucketSize;
    let startX = 0;
    let dragMoved = false;

    // Build ticks with common meaningful steps
    const ticks = [1, 2, 5, 10, 20, 50, 100, 200, 500];
    const ticksEl = document.getElementById('resolutionScaleTicks');
    if (ticksEl) {
        ticksEl.innerHTML = '';
        const trackRect = track.getBoundingClientRect();
        const width = trackRect.width > 0 ? trackRect.width : 200; // fallback before layout
        ticks.forEach((t) => {
            const p = bucketSizeToPercent(t);
            const tick = document.createElement('div');
            tick.className = 'resolution-scale-tick';
            tick.style.left = `${p}%`;
            tick.innerHTML = `<div class="line"></div><div class="label">${t}\u00D7</div>`;
            ticksEl.appendChild(tick);
        });
    }

    const setFromClientX = (clientX, commit) => {
        const rect = track.getBoundingClientRect();
        const clampedX = Math.max(rect.left, Math.min(rect.right, clientX));
        const pct = ((clampedX - rect.left) / rect.width) * 100;
        const size = percentToBucketSize(pct);
        if (size === lastSetSize && !commit) return;
        lastSetSize = size;
        params.bucketSize = size;
        updateResolutionScaleUI(size);
        // Debounced heavy work during drag
        if (!commit) {
            if (pendingBucketTimeout !== null) clearTimeout(pendingBucketTimeout);
            showResolutionLoading();
            pendingBucketTimeout = setTimeout(() => {
                pendingBucketTimeout = null;
                try {
                    edgeMarkers.forEach(marker => scene.remove(marker));
                    edgeMarkers = [];
                    rebucketData();
                    recreateTerrain();
                    updateURLParameter('bucketSize', params.bucketSize);
                } finally {
                    hideResolutionLoading();
                }
            }, 120);
        } else {
            // Commit: immediate rebuild once
            showResolutionLoading();
            if (pendingBucketTimeout !== null) { clearTimeout(pendingBucketTimeout); pendingBucketTimeout = null; }
            setTimeout(() => {
                try {
                    edgeMarkers.forEach(marker => scene.remove(marker));
                    edgeMarkers = [];
                    rebucketData();
                    recreateTerrain();
                    updateURLParameter('bucketSize', params.bucketSize);
                } finally {
                    hideResolutionLoading();
                }
            }, 0);
        }
    };

    const onPointerDown = (e) => {
        isDragging = true;
        startX = e.clientX;
        dragMoved = false;
        setFromClientX(e.clientX, false);
        window.addEventListener('pointermove', onPointerMove);
        window.addEventListener('pointerup', onPointerUp, { once: true });
    };
    const onPointerMove = (e) => {
        if (!isDragging) return;
        if (Math.abs(e.clientX - startX) > 6) dragMoved = true;
        setFromClientX(e.clientX, false);
    };
    const onPointerUp = (e) => {
        if (!isDragging) return;
        isDragging = false;
        if (!dragMoved) {
            // Snap to nearest tick on simple click
            const rect = track.getBoundingClientRect();
            const clampedX = Math.max(rect.left, Math.min(rect.right, e.clientX));
            const pct = ((clampedX - rect.left) / rect.width) * 100;
            const rawSize = percentToBucketSize(pct);
            const nearest = ticks.reduce((best, t) => Math.abs(t - rawSize) < Math.abs(best - rawSize) ? t : best, ticks[0]);
            setImmediateToSize(nearest);
        } else {
            setFromClientX(e.clientX, true);
        }
        window.removeEventListener('pointermove', onPointerMove);
    };

    // Make the entire container clickable to jump (snap to nearest tick)
    container.addEventListener('click', (e) => {
        if (e.target === track || track.contains(e.target)) return; // track click already handled via pointer handlers
        const rect = track.getBoundingClientRect();
        const clampedX = Math.max(rect.left, Math.min(rect.right, e.clientX));
        const pct = ((clampedX - rect.left) / rect.width) * 100;
        const rawSize = percentToBucketSize(pct);
        const nearest = ticks.reduce((best, t) => Math.abs(t - rawSize) < Math.abs(best - rawSize) ? t : best, ticks[0]);
        setImmediateToSize(nearest);
    });

    track.addEventListener('pointerdown', onPointerDown);

    // Helper: set immediately to a specific size (one rebuild)
    const setImmediateToSize = (size) => {
        const clamped = Math.max(1, Math.min(500, Math.round(size)));
        if (clamped === params.bucketSize) return;
        params.bucketSize = clamped;
        updateResolutionScaleUI(clamped);
        showResolutionLoading();
        if (pendingBucketTimeout !== null) { clearTimeout(pendingBucketTimeout); pendingBucketTimeout = null; }
        setTimeout(() => {
            try {
                edgeMarkers.forEach(marker => scene.remove(marker));
                edgeMarkers = [];
                rebucketData();
                recreateTerrain();
                updateURLParameter('bucketSize', params.bucketSize);
            } finally {
                hideResolutionLoading();
            }
        }, 0);
    };

    // Sharp button: move to previous smaller tick (single step per click)
    if (maxBtn) {
        const doSharpStep = () => {
            let prev = 1;
            for (let i = 0; i < ticks.length; i++) {
                if (ticks[i] >= params.bucketSize) { break; }
                prev = ticks[i];
            }
            setImmediateToSize(prev);
        };
        maxBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); doSharpStep(); });
    }

    // Helper: press-and-hold repeating for buttons
    const setupHoldRepeat = (el, stepFn) => {
        if (!el) return;
        let holdTimeout = null;
        let holdInterval = null;
        const clearTimers = () => {
            if (holdTimeout) { clearTimeout(holdTimeout); holdTimeout = null; }
            if (holdInterval) { clearInterval(holdInterval); holdInterval = null; }
        };
        const start = (ev) => {
            ev.preventDefault();
            stepFn();
            clearTimers();
            holdTimeout = setTimeout(() => {
                holdInterval = setInterval(stepFn, 100);
            }, 350);
        };
        const end = () => clearTimers();
        el.addEventListener('mousedown', start);
        el.addEventListener('touchstart', start, { passive: false });
        window.addEventListener('mouseup', end);
        window.addEventListener('touchend', end);
        el.addEventListener('mouseleave', end);
    };

    // Less/Blur button: move to next larger tick (single step per click)
    const lessBtn = document.getElementById('resolutionLessButton');
    if (lessBtn) {
        const doBlurStep = () => {
            let target = ticks.find(t => t > params.bucketSize) || 500;
            setImmediateToSize(target);
        };
        lessBtn.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); doBlurStep(); });
    }

    // Initial position
    updateResolutionScaleUI(params.bucketSize);
}

/**
 * Adjust bucket size by a delta amount with granular control
 * @param {number} delta - Amount to adjust (+/- 1, 5, 10, etc.)
 */
function adjustBucketSize(delta) {
    if (!rawElevationData) {
        console.warn('[WARN] No data loaded, cannot adjust bucket size');
        return;
    }

    // Calculate new bucket size with clamping to valid range [1, 500]
    let newSize = params.bucketSize + delta;
    newSize = Math.max(1, Math.min(500, newSize));

    // If size didn't actually change (already at limit), don't show loading UI
    if (newSize === params.bucketSize) {
        console.log(`[INFO] Already at ${newSize === 1 ? 'minimum' : 'maximum'} resolution (${newSize}x), no change needed`);
        return;
    }

    // Show loading overlay
    showResolutionLoading();

    // Cancel any pending drag debounce and rebuild immediately
    if (pendingBucketTimeout !== null) { clearTimeout(pendingBucketTimeout); pendingBucketTimeout = null; }
    setTimeout(() => {
        try {

            // Update params and UI
            params.bucketSize = newSize;
            try { updateResolutionScaleUI(newSize); } catch (_) { }
            // tag UI updated via updateResolutionScaleUI

            // Clear edge markers so they get recreated at new positions
            edgeMarkers.forEach(marker => scene.remove(marker));
            edgeMarkers = [];

            // Rebucket and recreate terrain
            rebucketData();
            recreateTerrain();
            updateStats();

            console.log(`Bucket size adjusted by ${delta > 0 ? '+' : ''}${delta} -> ${newSize}x`);
            try { updateURLParameter('bucketSize', newSize); } catch (_) { }
        } finally {
            // Hide loading overlay
            hideResolutionLoading();
        }
    }, 50);
}

/**
 * Set resolution to maximum detail (bucket size = 1)
 */
function setMaxResolution() {
    if (!rawElevationData) {
        console.warn('[WARN] No data loaded, cannot set max resolution');
        return;
    }

    // If already at max resolution, don't show loading UI
    if (params.bucketSize === 1) {
        console.log('[INFO] Already at maximum resolution (1x), no change needed');
        return;
    }

    // Show loading overlay
    showResolutionLoading();

    // Use setTimeout to allow UI to update before heavy processing
    setTimeout(() => {
        try {
            // Max resolution = bucket size of 1 (every pixel rendered)
            params.bucketSize = 1;
            try { updateResolutionScaleUI(1); } catch (_) { }
            // tag UI updated via updateResolutionScaleUI

            // Clear edge markers so they get recreated at new positions
            edgeMarkers.forEach(marker => scene.remove(marker));
            edgeMarkers = [];

            // Rebucket and recreate terrain
            rebucketData();
            recreateTerrain();
            updateStats();

            console.log('Resolution set to MAX (bucket size = 1)');
            try { updateURLParameter('bucketSize', 1); } catch (_) { }
        } finally {
            // Hide loading overlay
            hideResolutionLoading();
        }
    }, 50);
}

/**
 * Set resolution to calculated default (auto-adjusted for performance)
 */
function setDefaultResolution() {
    if (!rawElevationData) {
        console.warn('[WARN] No data loaded, cannot set default resolution');
        return;
    }

    // Show loading overlay
    showResolutionLoading();

    // Use setTimeout to allow UI to update before heavy processing
    setTimeout(() => {
        try {
            // Use the auto-adjust algorithm to find optimal default
            autoAdjustBucketSize();

            console.log('Resolution set to DEFAULT (auto-adjusted)');
        } finally {
            // Hide loading overlay
            hideResolutionLoading();
        }
    }, 50);
}

/**
 * Automatically calculate and set optimal bucket size for performance
 * Targets ~3,900 buckets for good balance of detail and speed
 */
function autoAdjustBucketSize() {
    if (!rawElevationData) {
        console.warn('[WARN] No data loaded, cannot auto-adjust bucket size');
        return;
    }

    const { width, height } = rawElevationData;
    // Reduced from 10000 to ~3900 (60% larger bucket size means ~40% of original bucket count)
    const TARGET_BUCKET_COUNT = 390000;

    // Calculate optimal bucket size to stay within TARGET_BUCKET_COUNT constraint
    // Start with direct calculation: bucketSize = ceil(sqrt(width * height / TARGET_BUCKET_COUNT))
    let optimalSize = Math.ceil(Math.sqrt((width * height) / TARGET_BUCKET_COUNT));

    // Verify and adjust if needed (in case of rounding edge cases)
    let bucketedWidth = Math.floor(width / optimalSize);
    let bucketedHeight = Math.floor(height / optimalSize);
    let totalBuckets = bucketedWidth * bucketedHeight;

    // If we're still over the limit, increment until we're under
    while (totalBuckets > TARGET_BUCKET_COUNT && optimalSize < 500) {
        optimalSize++;
        bucketedWidth = Math.floor(width / optimalSize);
        bucketedHeight = Math.floor(height / optimalSize);
        totalBuckets = bucketedWidth * bucketedHeight;
    }

    // Clamp to valid range [1, 500]
    optimalSize = Math.max(1, Math.min(500, optimalSize));

    // Recalculate final bucket count with clamped size
    bucketedWidth = Math.floor(width / optimalSize);
    bucketedHeight = Math.floor(height / optimalSize);
    totalBuckets = bucketedWidth * bucketedHeight;

    appendActivityLog(`Optimal bucket size: ${optimalSize}x -> ${bucketedWidth}x${bucketedHeight} grid (${totalBuckets.toLocaleString()} buckets)`);
    appendActivityLog(`Constraint: ${totalBuckets <= TARGET_BUCKET_COUNT ? '' : ''} ${totalBuckets} / ${TARGET_BUCKET_COUNT.toLocaleString()} buckets`);

    // Update params and UI (only increase small values; never reduce user-chosen larger values)
    params.bucketSize = Math.max(params.bucketSize || 1, optimalSize);
    try { updateResolutionScaleUI(optimalSize); } catch (_) { }
    // tag UI updated via updateResolutionScaleUI

    // Clear edge markers so they get recreated at new positions
    edgeMarkers.forEach(marker => scene.remove(marker));
    edgeMarkers = [];

    // Rebucket and recreate terrain
    rebucketData();
    recreateTerrain();
    updateStats();
    try { updateURLParameter('bucketSize', optimalSize); } catch (_) { }
}

// Export module
window.ResolutionControls = {
    showLoading: showResolutionLoading,
    hideLoading: hideResolutionLoading,
    bucketSizeToPercent,
    percentToBucketSize,
    updateUI: updateResolutionScaleUI,
    init: initResolutionScale,
    adjust: adjustBucketSize,
    setMax: setMaxResolution,
    setDefault: setDefaultResolution,
    autoAdjust: autoAdjustBucketSize
};

