/**
 * Altitude Maps - Advanced 3D Elevation Viewer
 * Main application orchestrator
 * 
 * MODULAR ARCHITECTURE:
 * This file coordinates between specialized modules, each handling a specific domain:
 * 
 * - activity-log.js              → UI activity log (timestamped events, copy to clipboard)
 * - bucketing.js                 → Data aggregation and downsampling
 * - camera-schemes.js            → Camera control implementations (Google Maps, Blender, etc.)
 * - color-legend.js              → Color scale legend UI component
 * - color-schemes.js             → Color palettes and descriptions
 * - edge-markers.js              → Directional markers (N/E/S/W labels at terrain edges)
 * - format-utils.js              → Data formatting (units, distances, file sizes)
 * - geometry-utils.js            → Spatial calculations and coordinate conversions
 * - ground-plane-camera.js       → Ground plane camera system (default)
 * - ground-plane-google-earth.js → Google Earth camera variant
 * - resolution-controls.js       → Resolution slider, bucket size presets (MAX/DEFAULT)
 * - state-connectivity.js        → Region adjacency and connectivity visualization
 * - ui-loading.js                → Loading screen and progress bar management
 * 
 * This main file handles:
 * - Application initialization and lifecycle
 * - Scene setup (Three.js renderer, camera, lights)
 * - Terrain rendering (bars, surface, points)
 * - UI event handling and state management
 * - Region loading and data processing
 * - HUD updates and user interactions
 * 
 * Design principle: Keep thin wrapper functions here that delegate to modules.
 * Avoid duplication - each function should have a single source of truth.
 */

// Version tracking
const VIEWER_VERSION = '1.362';

// All console logs use plain ASCII - no sanitizer needed

//-------CORE THREE.JS STATE-------
let scene, camera, renderer, controls;
let terrainMesh, terrainGroup, gridHelper;
let raycaster;
let groundPlane;
let edgeMarkers = []; // N/E/S/W markers (must not move with vertical exaggeration changes)
const __tmpColor = new THREE.Color(); // Reused to avoid per-vertex allocations

//-------DATA STATE-------
let rawElevationData;
let processedData;
let derivedSlopeDeg = null;
let derivedAspectDeg = null;
let trueScaleValue = null;

//-------REGION STATE-------
const MAX_RECENT_REGIONS = 10;
let recentRegions = [];
let regionAdjacency = null;

//-------UI STATE-------
let currentMouseX, currentMouseY;
let hudSettings = null;
let isCurrentlyLoading = false;

//-------PERFORMANCE TRACKING-------
let terrainStats = {};
let frameCount = 0;
let lastFpsUpdateTime = performance.now();

// Helper functions to convert between UI (multiplier) and internal (absolute) values
function multiplierToInternal(multiplier) {
    if (trueScaleValue === null) {
        // Fallback if true scale not calculated yet
        if (rawElevationData) {
            const scale = calculateRealWorldScale();
            trueScaleValue = 1.0 / scale.metersPerPixelX;
        } else {
            return 0.03; // Default fallback
        }
    }
    return trueScaleValue * multiplier;
}

function internalToMultiplier(internalValue) {
    if (trueScaleValue === null) {
        return 1; // Default to 1x
    }
    return Math.round(internalValue / trueScaleValue);
}

function appendActivityLog(message) {
    return window.ActivityLog.append(message);
}

//-------RENDER MODE STATE-------
let barsInstancedMesh = null;
let barsIndexToRow = null;
let barsIndexToCol = null;
let barsTileSize = 0;
const barsDummy = new THREE.Object3D();
let pendingVertExagRaf = null;
let pendingTileGapRaf = null;
let pendingBucketTimeout = null;
let lastBarsExaggerationInternal = null;
let lastPointsExaggerationInternal = null;
let lastBarsTileSize = 1.0;
let lastAutoResolutionAdjustTime = 0;

//-------PARAMETERS-------
let params = {
    bucketSize: 4, // Integer multiplier of pixel spacing (1x, 2x, 3x, etc.)
    tileGap: 0, // Gap between tiles as percentage (0-99%)
    aggregation: 'max',
    renderMode: 'bars',
    verticalExaggeration: 0.04, // Default: good balance of detail and scale
    colorScheme: 'high-contrast',
    showGrid: false,
    autoRotate: false,
    // Shading: Always use Natural (Lambert) - no UI control needed
    colorGamma: 1.0
};

// Read and apply modifiable params from URL so links are shareable and stateful
function applyParamsFromURL() {
    const sp = new URLSearchParams(window.location.search);
    const getInt = (k, min, max) => {
        if (!sp.has(k)) return null;
        const v = parseInt(sp.get(k), 10);
        if (Number.isNaN(v)) return null;
        if (typeof min === 'number') return Math.max(min, typeof max === 'number' ? Math.min(max, v) : v);
        return v;
    };
    const getFloat = (k, min, max) => {
        if (!sp.has(k)) return null;
        const v = parseFloat(sp.get(k));
        if (Number.isNaN(v)) return null;
        let n = v;
        if (typeof min === 'number') n = Math.max(min, n);
        if (typeof max === 'number') n = Math.min(max, n);
        return n;
    };
    const getBool = (k) => {
        if (!sp.has(k)) return null;
        const v = sp.get(k).toLowerCase();
        return v === '1' || v === 'true' || v === 'yes';
    };
    const getStr = (k, allowed) => {
        if (!sp.has(k)) return null;
        const v = sp.get(k);
        if (Array.isArray(allowed) && allowed.length) return allowed.includes(v) ? v : null;
        return v;
    };

    const bs = getInt('bucketSize', 1, 500);
    if (bs !== null) params.bucketSize = bs;

    const tg = getInt('tileGap', 0, 99);
    if (tg !== null) params.tileGap = tg;

    const agg = getStr('aggregation', ['max', 'mean', 'min']);
    if (agg) params.aggregation = agg;

    const rm = getStr('renderMode', ['bars', 'points', 'surface']);
    if (rm) params.renderMode = rm;

    const ex = getFloat('exag', 1, 100);
    if (ex !== null) params.verticalExaggeration = multiplierToInternal(ex);

    const cs = getStr('colorScheme');
    if (cs) params.colorScheme = cs;

    const gamma = getFloat('gamma', 0.5, 2.0);
    if (gamma !== null) params.colorGamma = gamma;
}

// Initialize
async function init() {
    try {
        setupScene();
        setupEventListeners();

        // Initialize color scale legend
        if (typeof initColorLegend === 'function') {
            initColorLegend();
            console.log('Color legend initialized');
        } else {
            console.warn('initColorLegend function not found');
        }

        // Ensure activity log is visible by adding an initial entry
        appendActivityLog('Viewer initialized');
        // Mirror warnings/errors and significant console.log messages into activity log
        if (!window.__consolePatched) {
            const origLog = console.log.bind(console);
            const origWarn = console.warn.bind(console);
            const origError = console.error.bind(console);

            console.log = (...args) => {
                origLog(...args);
                const msg = args.join(' ');
                const first = msg.split(' ')[0];
                if (first === '[OK]' || first === '[INFO]' || first === '[JSON]' ||
                    msg.startsWith('Bucket size') || msg.startsWith('Resolution set') ||
                    msg.startsWith('Setting TRUE') || msg.startsWith('Setting ') && msg.includes('x exaggeration') ||
                    msg.startsWith('Camera reset') || msg.startsWith('True scale') ||
                    msg.startsWith('Loading region') || msg.startsWith('Loading JSON') ||
                    msg.startsWith('Aggregation:') || msg.startsWith('Already at') ||
                    msg.startsWith('Switching to') || msg.startsWith('Pivot marker') ||
                    msg.startsWith('Bars centered') || msg.startsWith('Points centered') ||
                    msg.startsWith('PURE 2D') || msg.startsWith('Created') && msg.includes('instanced bars')) {
                    try { appendActivityLog(msg); } catch (_) { }
                }
            };
            console.warn = (...args) => { try { appendActivityLog(args.join(' ')); } catch (_) { } origWarn(...args); };
            console.error = (...args) => { try { appendActivityLog(args.join(' ')); } catch (_) { } origError(...args); };
            window.__consolePatched = true;
        }

        // Display version number
        document.getElementById('version-display').textContent = `v${VIEWER_VERSION}`;
        appendActivityLog(`Altitude Maps Viewer v${VIEWER_VERSION}`);

        // Populate region selector (loads manifest and populates dropdown)
        const firstRegionId = await populateRegionSelector();

        // Load state adjacency data (US states only)
        if (typeof loadStateAdjacency === 'function') {
            await loadStateAdjacency();
        }

        // Initialize Select2 and all UI controls BEFORE loading any region data
        // This ensures the region selector is completely loaded and interactive
        setupControls();

        // Apply any parameters from URL before first load so initial render matches query
        applyParamsFromURL();

        // Load the initial region data first so the UI never shows a different name than what's rendered
        await loadRegion(firstRegionId);

        // After load completes, update the input to reflect the currently shown region
        const regionInput = document.getElementById('regionSelect');
        if (regionInput) {
            suppressRegionChange = true;
            regionInput.value = regionIdToName[firstRegionId] || firstRegionId;
            suppressRegionChange = false;
            console.log(`Region input synced to shown region: ${firstRegionId}`);
        }

        // Set default vertical exaggeration to 6x ONLY if not specified in URL
        // URL params are the source of truth on initial load, then UI takes over
        const urlParams = new URLSearchParams(window.location.search);
        if (!urlParams.has('exag')) {
            try {
                if (typeof setVertExagMultiplier === 'function') {
                    setVertExagMultiplier(6);
                    console.log('Set default vertical exaggeration to 6x (no URL param)');
                }
            } catch (e) {
                console.warn('Could not set default vertical exaggeration to 6x:', e);
            }
        } else {
            console.log('Keeping vertical exaggeration from URL parameter');
        }
        // Initialize HUD toggle
        const hudMin = document.getElementById('hud-minimize');
        const hudExp = document.getElementById('hud-expand');
        const hud = document.getElementById('info');
        if (hudMin && hudExp && hud) {
            hudMin.addEventListener('click', () => { hud.style.display = 'none'; hudExp.style.display = 'block'; });
            hudExp.addEventListener('click', () => { hud.style.display = ''; hudExp.style.display = 'none'; });
        }
        // Rebuild dropdown for initial interaction (uses rebuildRegionDropdown function)
        rebuildRegionDropdown();

        // Update navigation hints for initial region
        updateRegionNavHints();

        // Calculate true scale for this data
        const scale = calculateRealWorldScale();
        trueScaleValue = 1.0 / scale.metersPerPixelX;
        console.log(`True scale for this region: ${trueScaleValue.toFixed(6)}x`);

        hideLoading();

        // Sync UI to match params (ensures no mismatch on initial load)
        syncUIControls();

        // NOTE: autoAdjustBucketSize() was already called by loadRegion() above
        // No need to call it again here - that would create terrain twice!

        // Animate loop starts
        animate();
    } catch (error) {
        document.getElementById('loading').innerHTML = `
 <div style="text-align: center;">
 Error loading data<br><br>
 <div style="font-size: 13px; color:#ff6666; max-width: 400px;">${error.message}</div>
 <br>
 <div style="font-size: 12px; color:#888;">
 Make sure to run:<br>
 <code style="color:#5588cc; background:#1a1a1a; padding: 8px; border-radius: 4px; display: inline-block; margin-top: 10px;">
 python export_for_web_viewer.py
 </code>
 <br>or<br>
 <code style="color:#5588cc; background:#1a1a1a; padding: 8px; border-radius: 4px; display: inline-block; margin-top: 10px;">
 python download_regions.py
 </code>
 </div>
 </div>
 `;
        console.error('Error:', error);
    }
}

let regionsManifest = null;
let currentRegionId = null;

// Data caching toggle: when true (default), do NOT add cache-busting params
// Enable dev busting with URL: ?useCache=0 (or useCache=false)
const USE_CACHE = (() => {
    try {
        const params = new URLSearchParams(window.location.search);
        if (params.has('useCache')) {
            const v = params.get('useCache')?.toLowerCase();
            return !(v === '0' || v === 'false' || v === 'off' || v === 'no');
        }
    } catch (e) { }
    return true; // default on (production-friendly)
})();

async function loadElevationData(url) {
    // Always use gzipped version (smaller, faster)
    const gzUrl = url.endsWith('.json') ? url + '.gz' : url;
    if (!gzUrl.endsWith('.gz')) {
        throw new Error(`Elevation data URL must end with .json or .gz, got: ${url}`);
    }
    const gzUrlWithBuster = USE_CACHE ? gzUrl : (gzUrl.includes('?') ? `${gzUrl}&_t=${Date.now()}` : `${gzUrl}?_t=${Date.now()}`);
    const tStart = performance.now();
    const response = await fetch(gzUrlWithBuster);
    const finalUrl = gzUrl;

    if (!response.ok) {
        throw new Error(`Failed to load elevation data. HTTP ${response.status} ${response.statusText} for ${gzUrl}`);
    }

    // Extract filename from URL
    const filename = finalUrl.split('/').pop();

    // Log response details for debugging
    console.log(`Loading JSON file: ${filename}`);
    console.log(` Full URL: ${finalUrl}`);
    console.log(` HTTP Status: ${response.status} ${response.statusText}`);
    console.log(` Content-Type: ${response.headers.get('content-type')}`);
    console.log(` Content-Encoding: ${response.headers.get('content-encoding')}`);
    console.log(` Content-Length: ${response.headers.get('content-length')}`);

    if (!response.ok) {
        throw new Error(`Failed to load elevation data. HTTP ${response.status} ${response.statusCode} for ${finalUrl}`);
    }

    // Detect cache hit using Performance API
    const actualUrl = finalUrl === gzUrl ? gzUrlWithBuster : (USE_CACHE ? url : (url.includes('?') ? `${url}&_t=${Date.now()}` : `${url}?_t=${Date.now()}`));
    const perfEntries = performance.getEntriesByName(actualUrl, 'resource');
    const isCacheHit = perfEntries.length > 0 && perfEntries[0].transferSize === 0;

    if (isCacheHit) {
        console.log(` Cache hit! Loading from browser cache.`);
        appendActivityLog(`Loading ${filename} from cache`);
        updateLoadingProgress(0, 0, 1, 'Loading from cache...');
    }

    // Get content length for progress tracking
    const contentLength = response.headers.get('content-length');
    const totalBytes = contentLength ? parseInt(contentLength) : 0;

    // Check if file is gzipped and server didn't decompress it
    const contentEncoding = response.headers.get('content-encoding');
    const serverDecompressed = contentEncoding && contentEncoding.includes('gzip');
    const isGzipped = finalUrl.endsWith('.gz') && !serverDecompressed;

    let data;

    if (isCacheHit || !totalBytes || !response.body) {
        // Cache hit or no content length - just parse directly (fast)
        console.log(` Parsing JSON...`);
        if (isGzipped) {
            // Need to decompress gzipped data
            const arrayBuffer = await response.arrayBuffer();
            const stream = new DecompressionStream('gzip');
            const writer = stream.writable.getWriter();
            writer.write(new Uint8Array(arrayBuffer));
            writer.close();
            const decompressedResponse = new Response(stream.readable);
            const text = await decompressedResponse.text();
            data = JSON.parse(text);
        } else {
            data = await response.json();
        }
    } else {
        // Real download - stream with progress tracking
        console.log(` Downloading with progress tracking...`);
        const reader = response.body.getReader();
        const chunks = [];
        let receivedBytes = 0;
        let lastProgressUpdate = 0;

        while (true) {
            const { done, value } = await reader.read();

            if (done) break;

            chunks.push(value);
            receivedBytes += value.length;

            // Update progress (throttle to every 100ms to avoid UI spam)
            const now = performance.now();
            if (now - lastProgressUpdate > 100) {
                const percent = Math.floor((receivedBytes / totalBytes) * 100);
                updateLoadingProgress(percent, receivedBytes, totalBytes, 'Downloading...');
                lastProgressUpdate = now;
            }
        }

        // Combine chunks
        const blob = new Blob(chunks);

        if (isGzipped) {
            // Decompress gzipped data
            console.log(` Decompressing gzipped data...`);
            const arrayBuffer = await blob.arrayBuffer();
            const stream = new DecompressionStream('gzip');
            const writer = stream.writable.getWriter();
            writer.write(new Uint8Array(arrayBuffer));
            writer.close();
            const decompressedResponse = new Response(stream.readable);
            const text = await decompressedResponse.text();
            console.log(` Parsing JSON...`);
            data = JSON.parse(text);
        } else {
            // Parse uncompressed JSON
            const text = await blob.text();
            console.log(` Parsing JSON...`);
            data = JSON.parse(text);
        }
    }

    // Log final size
    const sizeMB = totalBytes ? (totalBytes / 1024 / 1024).toFixed(2) : '?';
    appendActivityLog(`Loaded ${filename}: ${sizeMB} MB`);

    // Extract version from filename for logging (e.g., ohio_srtm_30m_2048px_v2.json -> v2)
    const versionMatch = filename.match(/_v(\d+)\.json/);
    const fileVersion = versionMatch ? versionMatch[1] : 'unknown';
    appendActivityLog(`[OK] Data format v${fileVersion} from filename`);

    try { window.ActivityLog.logResourceTiming(actualUrl, 'Loaded JSON', tStart, performance.now()); } catch (e) { }
    return data;
}

async function loadRegionsManifest() {
    const timestamp = Date.now();
    const gzUrl = `generated/regions/regions_manifest.json.gz?_t=${timestamp}`;
    const tStart = performance.now();
    const response = await fetch(gzUrl, { cache: 'no-store' });

    if (!response.ok) {
        throw new Error(`Failed to load regions manifest. HTTP ${response.status} ${response.statusText} for ${gzUrl}`);
    }

    // Check if response is already decompressed by server (Content-Encoding header)
    const contentEncoding = response.headers.get('content-encoding');
    const serverDecompressed = contentEncoding && contentEncoding.includes('gzip');

    if (serverDecompressed) {
        // Server already decompressed it (Content-Encoding header set)
        const json = await response.json();
        try { window.ActivityLog.logResourceTiming(gzUrl, 'Loaded manifest', tStart, performance.now()); } catch (e) { }
        return json;
    } else {
        // Server is serving raw compressed bytes, we need to decompress
        const arrayBuffer = await response.arrayBuffer();
        const stream = new DecompressionStream('gzip');
        const writer = stream.writable.getWriter();

        // Write compressed data to decompression stream
        writer.write(new Uint8Array(arrayBuffer));
        writer.close();

        // Read decompressed data from the readable side
        const decompressedResponse = new Response(stream.readable);
        const text = await decompressedResponse.text();
        const json = JSON.parse(text);
        try { window.ActivityLog.logResourceTiming(gzUrl, 'Loaded manifest (gzipped)', tStart, performance.now()); } catch (e) { }
        return json;
    }
}

async function loadAdjacencyData() {
    const gzUrl = 'generated/regions/region_adjacency.json.gz';
    const response = await fetch(gzUrl);

    if (!response.ok) {
        throw new Error(`Failed to load region adjacency data. HTTP ${response.status} ${response.statusText} for ${gzUrl}`);
    }

    // Check if response is already decompressed by server (Content-Encoding header)
    const contentEncoding = response.headers.get('content-encoding');
    const serverDecompressed = contentEncoding && contentEncoding.includes('gzip');

    if (serverDecompressed) {
        // Server already decompressed it (Content-Encoding header set)
        return await response.json();
    } else {
        // Server is serving raw compressed bytes, we need to decompress
        const arrayBuffer = await response.arrayBuffer();
        const stream = new DecompressionStream('gzip');
        const writer = stream.writable.getWriter();

        // Write compressed data to decompression stream
        writer.write(new Uint8Array(arrayBuffer));
        writer.close();

        // Read decompressed data from the readable side
        const decompressedResponse = new Response(stream.readable);
        const text = await decompressedResponse.text();
        return JSON.parse(text);
    }
}

// Recent regions management
function loadRecentRegions() {
    try {
        const stored = localStorage.getItem('recentRegions');
        if (stored) {
            const parsed = JSON.parse(stored);
            if (Array.isArray(parsed)) {
                recentRegions = parsed.slice(0, MAX_RECENT_REGIONS);
                return;
            }
        }
    } catch (e) {
        console.warn('Could not load recent regions:', e);
    }
    recentRegions = [];

    // If no recent regions, populate with default personal history
    if (recentRegions.length === 0) {
        recentRegions = ['new_mexico', 'san_francisco', 'faroe_islands'];
        saveRecentRegions();
    }
}

function saveRecentRegions() {
    try {
        localStorage.setItem('recentRegions', JSON.stringify(recentRegions));
    } catch (e) {
        console.warn('Could not save recent regions:', e);
    }
}

function addToRecentRegions(regionId) {
    if (!regionId) return;

    // Remove if already in list
    recentRegions = recentRegions.filter(id => id !== regionId);

    // Add to front
    recentRegions.unshift(regionId);

    // Trim to max size
    if (recentRegions.length > MAX_RECENT_REGIONS) {
        recentRegions = recentRegions.slice(0, MAX_RECENT_REGIONS);
    }

    saveRecentRegions();
}

function getValidRecentRegions() {
    // Filter recent regions to only include those that still exist in manifest
    if (!regionsManifest || !regionsManifest.regions) return [];
    return recentRegions.filter(id => regionsManifest.regions[id]);
}

function rebuildRegionDropdown() {
    // Rebuild regionOptions array with current recent regions
    if (!regionsManifest || !regionsManifest.regions) return;

    regionOptions = [];

    // Build groups again
    const internationalCountries = [];
    const nonCountryRegions = [];
    const unitedStates = [];

    for (const [regionId, regionInfo] of Object.entries(regionsManifest.regions)) {
        const id = regionId;
        const region_type = (regionInfo && regionInfo.region_type) ? String(regionInfo.region_type).toLowerCase() : null;
        if (region_type === 'usa_state') {
            unitedStates.push({ id, info: regionInfo });
        } else if (region_type === 'country') {
            internationalCountries.push({ id, info: regionInfo });
        } else if (region_type === 'region') {
            nonCountryRegions.push({ id, info: regionInfo });
        } else {
            nonCountryRegions.push({ id, info: regionInfo });
        }
    }

    // Recent regions are shown separately above the dropdown, not in the dropdown list

    // 1) Countries (alpha)
    if (internationalCountries.length > 0) {
        regionOptions.push({ id: '__header__', name: 'COUNTRIES' });
        internationalCountries.sort((a, b) => a.info.name.localeCompare(b.info.name));
        for (const { id, info } of internationalCountries) {
            regionOptions.push({ id, name: info.name });
        }
        if (nonCountryRegions.length || unitedStates.length) {
            regionOptions.push({ id: '__divider__', name: '' });
        }
    }

    // 2) Regions (alpha)
    if (nonCountryRegions.length > 0) {
        regionOptions.push({ id: '__header__', name: 'REGIONS' });
        nonCountryRegions.sort((a, b) => a.info.name.localeCompare(b.info.name));
        for (const { id, info } of nonCountryRegions) {
            regionOptions.push({ id, name: info.name });
        }
        if (unitedStates.length) {
            regionOptions.push({ id: '__divider__', name: '' });
        }
    }

    // 3) US states (alpha)
    if (unitedStates.length > 0) {
        regionOptions.push({ id: '__header__', name: 'US STATES' });
        unitedStates.sort((a, b) => a.info.name.localeCompare(b.info.name));
        for (const { id, info } of unitedStates) {
            regionOptions.push({ id, name: info.name });
        }
    }

    // Rebuild the DOM dropdown
    const dropdown = document.getElementById('regionDropdown');
    if (dropdown) {
        dropdown.innerHTML = '';
        regionOptions.forEach((opt) => {
            if (opt.id === '__divider__') {
                const div = document.createElement('div');
                div.setAttribute('data-divider', 'true');
                div.style.margin = '6px 0';
                div.style.borderTop = '1px solid rgba(85,136,204,0.35)';
                div.style.opacity = '0.8';
                dropdown.appendChild(div);
                return;
            }
            if (opt.id === '__header__') {
                const header = document.createElement('div');
                header.setAttribute('data-header', 'true');
                header.textContent = opt.name;
                header.style.padding = '8px 10px';
                header.style.fontSize = '11px';
                header.style.fontWeight = '700';
                header.style.color = '#888';
                header.style.textTransform = 'uppercase';
                header.style.letterSpacing = '0.5px';
                header.style.backgroundColor = 'rgba(85,136,204,0.08)';
                header.style.cursor = 'default';
                header.style.userSelect = 'none';
                dropdown.appendChild(header);
                return;
            }
            const row = document.createElement('div');
            row.textContent = opt.name;
            row.setAttribute('data-id', opt.id);
            row.style.padding = '8px 10px';
            row.style.cursor = 'pointer';
            row.style.fontSize = '12px';
            row.style.borderBottom = '1px solid rgba(85,136,204,0.12)';

            row.addEventListener('mousedown', (e) => {
                e.preventDefault();
                if (opt.id && opt.id !== currentRegionId) {
                    loadRegion(opt.id);
                }
                const input = document.getElementById('regionSelect');
                if (input) input.value = opt.name;
                dropdown.style.display = 'none';
            });
            dropdown.appendChild(row);
        });
    }
}

async function populateRegionSelector() {
    const inputEl = document.getElementById('regionSelect');
    const listEl = document.getElementById('regionList');

    regionsManifest = await loadRegionsManifest();
    regionAdjacency = await loadAdjacencyData();

    if (!regionsManifest.regions || Object.keys(regionsManifest.regions).length === 0) {
        throw new Error('Regions manifest is empty. Cannot load elevation data.');
    }

    // Check for URL parameter to specify initial region (e.g., ?region=ohio)
    const urlParams = new URLSearchParams(window.location.search);
    const urlRegion = urlParams.get('region');

    // Check localStorage for last viewed region
    const lastRegion = localStorage.getItem('lastViewedRegion');

    // Load recent regions from localStorage
    loadRecentRegions();

    // Build maps first (needed for all regions)
    regionIdToName = {};
    regionNameToId = {};
    for (const [regionId, regionInfo] of Object.entries(regionsManifest.regions)) {
        regionIdToName[regionId] = regionInfo.name;
        regionNameToId[regionInfo.name.toLowerCase()] = regionId;
    }

    // Build options for custom dropdown
    regionOptions = [];

    // Build groups using manifest-provided region_type:
    // Desired order in dropdown: 0) Recent, 1) Countries (international), 2) Regions (non-country), 3) US states
    const internationalCountries = [];
    const nonCountryRegions = [];
    const unitedStates = [];

    for (const [regionId, regionInfo] of Object.entries(regionsManifest.regions)) {
        const id = regionId;
        const region_type = (regionInfo && regionInfo.region_type) ? String(regionInfo.region_type).toLowerCase() : null;
        if (region_type === 'usa_state') {
            unitedStates.push({ id, info: regionInfo });
        } else if (region_type === 'country') {
            internationalCountries.push({ id, info: regionInfo });
        } else if (region_type === 'region') {
            nonCountryRegions.push({ id, info: regionInfo });
        } else {
            // Fallback: treat unknown region_type as generic regions
            nonCountryRegions.push({ id, info: regionInfo });
        }
    }

    // Recent regions are shown separately above the dropdown, not in the dropdown list

    // 1) Countries (alpha)
    if (internationalCountries.length > 0) {
        regionOptions.push({ id: '__header__', name: 'COUNTRIES' });
        internationalCountries.sort((a, b) => a.info.name.localeCompare(b.info.name));
        for (const { id, info } of internationalCountries) {
            regionOptions.push({ id, name: info.name });
        }
        if (nonCountryRegions.length || unitedStates.length) {
            regionOptions.push({ id: '__divider__', name: '' });
        }
    }

    // 2) Regions (alpha)
    if (nonCountryRegions.length > 0) {
        regionOptions.push({ id: '__header__', name: 'REGIONS' });
        nonCountryRegions.sort((a, b) => a.info.name.localeCompare(b.info.name));
        for (const { id, info } of nonCountryRegions) {
            regionOptions.push({ id, name: info.name });
        }
        if (unitedStates.length) {
            regionOptions.push({ id: '__divider__', name: '' });
        }
    }

    // 3) US states (alpha)
    if (unitedStates.length > 0) {
        regionOptions.push({ id: '__header__', name: 'US STATES' });
        unitedStates.sort((a, b) => a.info.name.localeCompare(b.info.name));
        for (const { id, info } of unitedStates) {
            regionOptions.push({ id, name: info.name });
        }
    }

    // Determine which region to load initially
    // Priority: URL parameter > California > localStorage > first region
    let firstRegionId;

    if (urlRegion && regionsManifest.regions[urlRegion]) {
        // URL parameter takes highest priority (e.g., ?region=ohio)
        firstRegionId = urlRegion;
        console.log(` Loading region from URL: ${urlRegion}`);
    } else if (regionsManifest.regions['california']) {
        // Default to California if available
        firstRegionId = 'california';
        console.log(` Loading default region: california`);
    } else if (lastRegion && regionsManifest.regions[lastRegion]) {
        // Remember last viewed region from localStorage
        firstRegionId = lastRegion;
        console.log(` Loading last viewed region: ${lastRegion}`);
    } else {
        // Fallback to first available region
        firstRegionId = Object.keys(regionsManifest.regions)[0];
        console.log(` Loading first available region: ${firstRegionId}`);
    }

    if (inputEl) {
        inputEl.value = regionIdToName[firstRegionId] || firstRegionId;
    }
    currentRegionId = firstRegionId;
    updateRegionInfo(firstRegionId);

    // NOTE: Select2 initialization happens in setupControls(), not here
    return firstRegionId;
}

function resolveRegionIdFromInput(inputValue) {
    if (!inputValue) return null;
    const trimmed = inputValue.trim();
    // Exact id match
    if (regionsManifest && regionsManifest.regions && regionsManifest.regions[trimmed]) {
        return trimmed;
    }
    // Exact name match (case-insensitive)
    const byName = regionNameToId[trimmed.toLowerCase()];
    if (byName) return byName;
    return null;
}

function updateRegionInfo(regionId) {
    const currentRegionEl = document.getElementById('currentRegion');
    const regionInfoEl = document.getElementById('regionInfo');

    if (!regionsManifest || !regionsManifest.regions[regionId]) {
        if (currentRegionEl) currentRegionEl.textContent = 'Unknown Region';
        if (regionInfoEl) regionInfoEl.textContent = 'No region data available';
        return;
    }

    const regionInfo = regionsManifest.regions[regionId];
    if (currentRegionEl) currentRegionEl.textContent = regionInfo.name;
    if (regionInfoEl) regionInfoEl.textContent = regionInfo.description;
}

async function loadRegion(regionId) {
    // Fallback to california if no region specified or invalid
    if (!regionId || !regionsManifest?.regions[regionId]) {
        regionId = 'california';
    }

    appendActivityLog(`Loading region: ${regionId}`);

    const regionName = regionsManifest?.regions[regionId]?.name || regionId;
    showLoading(`Loading ${regionName}...`);

    try {
        // ALWAYS use manifest file path (no fallback)
        const filename = regionsManifest.regions[regionId].file;
        if (!filename) {
            throw new Error(`No file path in manifest for region: ${regionId}`);
        }
        const dataUrl = `generated/regions/${filename}`;

        // loadElevationData now handles progress updates intelligently
        // (shows "Loading from cache..." for cached data or "Downloading..." with progress for real downloads)
        rawElevationData = await loadElevationData(dataUrl);
        currentRegionId = regionId;
        updateRegionInfo(regionId);

        // Calculate true scale for this data
        const scale = calculateRealWorldScale();
        trueScaleValue = 1.0 / scale.metersPerPixelX;
        console.log(`True scale for this region: ${trueScaleValue.toFixed(6)}x`);

        // Update button highlighting now that trueScaleValue is known
        updateVertExagButtons(params.verticalExaggeration);

        // Save to localStorage so we remember this region next time
        localStorage.setItem('lastViewedRegion', regionId);

        // Add to recent regions list
        addToRecentRegions(regionId);

        // Rebuild dropdown to reflect updated recent regions
        rebuildRegionDropdown();

        // Update navigation hints
        updateRegionNavHints();

        // Update URL parameter so the link is shareable
        updateURLParameter('region', regionId);

        // Update native input to show the loaded region without triggering load
        const regionInput = document.getElementById('regionSelect');
        if (regionInput) {
            suppressRegionChange = true;
            regionInput.value = regionIdToName[regionId] || regionId;
            suppressRegionChange = false;
        }

        // Clear edge markers so they get recreated for new region
        if (terrainGroup) {
            edgeMarkers.forEach(marker => terrainGroup.remove(marker));
        }
        edgeMarkers = [];

        // Processing steps with detailed progress tracking
        let stepStart;

        updateLoadingProgress(20, 1, 1, 'Auto-adjusting resolution...');
        stepStart = performance.now();
        // autoAdjustBucketSize() calls rebucketData() + recreateTerrain() internally
        // No need to call them again after this
        autoAdjustBucketSize();
        console.log(`autoAdjustBucketSize: ${(performance.now() - stepStart).toFixed(1)}ms (includes rebucket + terrain creation)`);

        updateLoadingProgress(70, 1, 1, 'Applying colors...');
        stepStart = performance.now();
        if (!params.colorScheme) params.colorScheme = 'high-contrast';
        updateColors();
        console.log(`updateColors: ${(performance.now() - stepStart).toFixed(1)}ms`);


        updateLoadingProgress(95, 1, 1, 'Finalizing...');
        updateStats();

        // Update color legend with loaded data
        if (typeof updateColorLegend === 'function') {
            updateColorLegend();
        }

        // Sync UI controls with current params
        syncUIControls();

        // Reset camera for new terrain size
        resetCamera();

        // Automatically reframe view (equivalent to F key) if camera scheme supports it
        if (activeScheme && activeScheme.reframeView) {
            activeScheme.reframeView();
        }

        hideLoading();
        appendActivityLog(`Loaded ${regionId}`);
        try { logSignificant(`Region loaded: ${regionId}`); } catch (_) { }

        // Create connectivity labels for US states
        if (typeof createConnectivityLabels === 'function') {
            createConnectivityLabels();
        }
    } catch (error) {
        console.error(`Failed to load region ${regionId}:`, error);
        try { logSignificant(`Region load failed: ${regionId}`); } catch (_) { }
        alert(`Failed to load region: ${error.message}`);
        hideLoading();

        // On error, revert input to previous region name
        const regionInput = document.getElementById('regionSelect');
        if (regionInput) {
            regionInput.value = regionIdToName[currentRegionId] || currentRegionId || '';
        }
    }
}

// UI loading states now in ui-loading.js
function showLoading(message) {
    return window.UILoading.show(message);
}

function updateLoadingProgress(percent, loaded, total, message) {
    return window.UILoading.updateProgress(percent, loaded, total, message);
}

function hideLoading() {
    return window.UILoading.hide();
}

// Data formatting utilities now in js/format-utils.js
function formatFileSize(bytes) {
    return window.FormatUtils.formatFileSize(bytes);
}

// Sync UI controls with current params
function syncUIControls() {
    // Bucket size - sync compact scale and numeric value (elements may differ)
    try { updateResolutionScaleUI(params.bucketSize); } catch (_) { }
    const valEl = document.getElementById('bucketSizeValue');
    if (valEl) valEl.textContent = `${params.bucketSize}\u00D7`;
    const legacySlider = document.getElementById('bucketSize');
    if (legacySlider) legacySlider.value = params.bucketSize;
    const legacyInput = document.getElementById('bucketSizeInput');
    if (legacyInput) legacyInput.value = params.bucketSize;

    // Tile gap UI removed; keep param but skip DOM sync
    const tileGapEl = document.getElementById('tileGap');
    const tileGapInputEl = document.getElementById('tileGapInput');
    if (tileGapEl) tileGapEl.value = params.tileGap;
    if (tileGapInputEl) tileGapInputEl.value = params.tileGap;

    // Vertical exaggeration - sync both slider and input (convert to multiplier for display)
    const multiplier = internalToMultiplier(params.verticalExaggeration);
    document.getElementById('vertExag').value = multiplier;
    document.getElementById('vertExagInput').value = multiplier;

    // Update button highlighting
    updateVertExagButtons(params.verticalExaggeration);

    // Render mode
    document.getElementById('renderMode').value = params.renderMode;

    // Aggregation method (element may not be present)
    const aggregationEl = document.getElementById('aggregation');
    if (aggregationEl) {
        aggregationEl.value = params.aggregation;
    }

    // Color scheme (native select with jQuery helper)
    const $colorScheme = $('#colorScheme');
    $colorScheme.val(params.colorScheme);

    // Shading: Always Natural (Lambert) - no UI element

    // Apply visual settings to scene objects
    if (gridHelper) {
        gridHelper.visible = params.showGrid;
    }
    if (controls) {
        controls.autoRotate = params.autoRotate;
    }

    // Shading: Always Natural (Lambert) - no controls needed
}

// Compute percentile-based auto stretch bounds from current bucketed elevation
function computeAutoStretchStats() {
    if (!processedData || !processedData.elevation) return;
    if (!params.autoStretchEnabled) { if (processedData.stats) { delete processedData.stats.autoLow; delete processedData.stats.autoHigh; } return; }
    const lowPct = Math.max(0, Math.min(100, params.autoStretchLowPct || 2));
    const highPct = Math.max(0, Math.min(100, params.autoStretchHighPct || 98));
    const values = [];
    const elev = processedData.elevation;
    for (let i = 0; i < elev.length; i++) {
        const row = elev[i];
        for (let j = 0; j < row.length; j++) {
            const v = row[j];
            if (v !== null && v !== undefined && isFinite(v)) values.push(v);
        }
    }
    if (!processedData.stats) processedData.stats = {};
    if (values.length < 10) { delete processedData.stats.autoLow; delete processedData.stats.autoHigh; return; }
    values.sort((a, b) => a - b);
    const p = (q) => {
        const idx = Math.max(0, Math.min(values.length - 1, Math.round((q / 100) * (values.length - 1))));
        return values[idx];
    };
    processedData.stats.autoLow = p(lowPct);
    processedData.stats.autoHigh = p(highPct);
}

// CLIENT-SIDE BUCKETING ALGORITHMS
function rebucketData() {
    const startTime = performance.now();
    const stack = new Error().stack;
    const caller = stack.split('\n')[2]?.trim() || 'unknown';
    console.log(`[BUCKETING] rebucketData() called from: ${caller}`);
    appendActivityLog(`Bucketing with multiplier ${params.bucketSize}x, method: ${params.aggregation}`);

    const { width, height, elevation, bounds } = rawElevationData;

    // Calculate real-world scale
    const scale = calculateRealWorldScale();

    // CORRECT APPROACH: Bucket size MUST be an integer multiple of pixel spacing
    // This ensures buckets align perfectly with the data grid
    const bucketSize = params.bucketSize; // Integer multiple (1, 2, 3, 4, ...)

    // Calculate bucketed dimensions (simple integer division)
    const bucketedWidth = Math.floor(width / bucketSize);
    const bucketedHeight = Math.floor(height / bucketSize);

    // Bucket physical size = pixel spacing x multiplier
    const bucketSizeMetersX = scale.metersPerPixelX * bucketSize;
    const bucketSizeMetersY = scale.metersPerPixelY * bucketSize;

    // Pre-allocate array for better performance
    const bucketedElevation = new Array(bucketedHeight);

    // Pixels per bucket (always an integer now)
    const pxPerBucketX = bucketSize;
    const pxPerBucketY = bucketSize;

    // Pre-allocate buffer for collecting values
    const maxBucketPixels = Math.ceil(pxPerBucketX * pxPerBucketY * 1.5); // 1.5x safety margin
    const buffer = new Float32Array(maxBucketPixels);

    for (let by = 0; by < bucketedHeight; by++) {
        const row = new Array(bucketedWidth);

        for (let bx = 0; bx < bucketedWidth; bx++) {
            // Calculate pixel range for this bucket (now always integer aligned)
            const pixelX0 = bx * bucketSize;
            const pixelX1 = (bx + 1) * bucketSize;
            const pixelY0 = by * bucketSize;
            const pixelY1 = (by + 1) * bucketSize;

            // Collect all values in this bucket (bucketSize x bucketSize pixels)
            let count = 0;
            for (let py = pixelY0; py < pixelY1 && py < height; py++) {
                for (let px = pixelX0; px < pixelX1 && px < width; px++) {
                    const val = elevation[py] && elevation[py][px];
                    if (val !== null && val !== undefined) {
                        buffer[count++] = val;
                    }
                }
            }

            // Aggregate based on method
            let value = null;
            if (count > 0) {
                switch (params.aggregation) {
                    case 'max':
                        value = buffer[0];
                        for (let i = 1; i < count; i++) {
                            if (buffer[i] > value) value = buffer[i];
                        }
                        break;
                    case 'min':
                        value = buffer[0];
                        for (let i = 1; i < count; i++) {
                            if (buffer[i] < value) value = buffer[i];
                        }
                        break;
                    case 'average':
                        value = 0;
                        for (let i = 0; i < count; i++) {
                            value += buffer[i];
                        }
                        value /= count;
                        break;
                    case 'median':
                        const sortedSlice = Array.from(buffer.slice(0, count)).sort((a, b) => a - b);
                        const mid = Math.floor(count / 2);
                        value = count % 2 === 0
                            ? (sortedSlice[mid - 1] + sortedSlice[mid]) / 2
                            : sortedSlice[mid];
                        break;
                    default:
                        console.error(`Unknown aggregation method: ${params.aggregation}`);
                        value = buffer[0]; // Fallback to first value
                        break;
                }
            }

            row[bx] = value;
        }
        bucketedElevation[by] = row;
    }

    processedData = {
        width: bucketedWidth,
        height: bucketedHeight,
        elevation: bucketedElevation,
        stats: rawElevationData.stats,
        bucketSizeMetersX: bucketSizeMetersX, // Actual size to tile perfectly
        bucketSizeMetersY: bucketSizeMetersY
    };

    computeDerivedGrids();
    computeAutoStretchStats();

    const duration = (performance.now() - startTime).toFixed(2);
    const reduction = (100 * (1 - (bucketedWidth * bucketedHeight) / (width * height))).toFixed(1);
    appendActivityLog(`Bucketed to ${bucketedWidth}x${bucketedHeight} (${reduction}% reduction) in ${duration}ms`);

    // Update Resolution header with footprint and rectangle count
    updateResolutionInfo();
}

// Edge markers now in edge-markers.js
function createEdgeMarkers() {
    return window.EdgeMarkers.create();
}

function createTextSprite(text, color) {
    return window.EdgeMarkers.createTextSprite(text, color);
}

function updateEdgeMarkers() {
    return window.EdgeMarkers.update();
}

/**
 * Dynamically test if frustum culling helps performance
 * Disables culling, measures FPS, re-enables, measures again
 * @returns {Promise<Object>} Performance comparison
 */
async function testFrustumCulling() {
    if (!barsInstancedMesh || terrainStats.bars === 0) {
        console.warn('Cannot test frustum culling: no bars loaded');
        return null;
    }

    console.log('Testing frustum culling effectiveness...');

    // Measure current FPS with culling on
    const fpsWithCulling = await measureFPS(100); // 100 frames
    console.log(`FPS with frustum culling: ${fpsWithCulling.toFixed(1)}`);

    // Disable culling and measure again
    barsInstancedMesh.frustumCulled = false;
    const fpsWithoutCulling = await measureFPS(100);
    console.log(`FPS without frustum culling: ${fpsWithoutCulling.toFixed(1)}`);

    // Re-enable culling
    barsInstancedMesh.frustumCulled = true;

    const result = {
        withCulling: fpsWithCulling,
        withoutCulling: fpsWithoutCulling,
        improvement: ((fpsWithCulling - fpsWithoutCulling) / fpsWithoutCulling * 100).toFixed(1),
        recommendation: fpsWithCulling > fpsWithoutCulling * 1.05 ? 'keep enabled' : 'minimal benefit'
    };

    console.log(`Frustum culling test: ${result.improvement}% improvement (${result.recommendation})`);
    return result;
}

/**
 * Measure average FPS over N frames
 * @param {number} frames - Number of frames to measure
 * @returns {Promise<number>} Average FPS
 */
async function measureFPS(frames) {
    return new Promise((resolve) => {
        let frameCount = 0;
        const startTime = performance.now();

        function countFrame() {
            frameCount++;
            if (frameCount >= frames) {
                const duration = (performance.now() - startTime) / 1000;
                const avgFPS = frames / duration;
                resolve(avgFPS);
            } else {
                requestAnimationFrame(countFrame);
            }
        }

        requestAnimationFrame(countFrame);
    });
}

// Expose performance testing functions for console use
window.testFrustumCulling = testFrustumCulling;
window.measureFPS = measureFPS;

function setupScene() {
    // Scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a0a);
    // Fog disabled - colors stay vibrant at all zoom levels
    // scene.fog = new THREE.Fog(0x0a0a0a, 100, 800);

    // ============================================================================
    // CRITICAL: CAMERA NEAR/FAR PLANE RATIO - DO NOT MODIFY WITHOUT READING THIS
    // ============================================================================
    // The near/far plane ratio directly affects depth buffer precision.
    //
    // PROBLEM: With extreme ratios (e.g., 0.001 to 50,000,000 = 50 billion:1),
    // the 24-bit depth buffer cannot distinguish between nearby and distant geometry
    // at oblique viewing angles. This causes DISTANT GEOMETRY TO BLEED THROUGH
    // NEARBY GEOMETRY, creating jagged artifacts that vary with camera angle.
    //
    // SYMPTOMS:
    // - Jagged "bleeding" of distant bars through nearby bars
    // - Artifacts appear/disappear as camera rotates
    // - Worse at oblique/grazing angles, better at perpendicular views
    // - Persists even with tile gaps between geometry
    //
    // SOLUTION: Keep near/far ratio reasonable. Current values:
    // Near: 1 meter (close enough for detail)
    // Far: 100,000 meters = 100km (enough for large terrains)
    // Ratio: 100,000:1 (good depth precision)
    //
    // NEVER use values like:
    // - near < 0.1 (too close, wastes precision on unused range)
    // - far > 1,000,000 (too far, spreads precision too thin)
    // - ratio > 1,000,000:1 (depth buffer will fail)
    //
    // If you need larger view distances, implement a logarithmic depth buffer
    // or frustum-based dynamic near/far adjustment. DO NOT just increase far plane.
    // ============================================================================
    const aspect = window.innerWidth / window.innerHeight;
    camera = new THREE.PerspectiveCamera(60, aspect, 1, 100000); // 1m to 100km
    camera.position.set(50, 50, 80); // Will be reset after data loads

    // SAFETY CHECK: Validate near/far ratio to prevent depth buffer artifacts
    const nearFarRatio = camera.far / camera.near;
    if (nearFarRatio > 1000000) {
        console.error('CRITICAL: Camera near/far ratio is TOO EXTREME!');
        console.error(` Current ratio: ${nearFarRatio.toLocaleString()}:1`);
        console.error(` Near: ${camera.near}, Far: ${camera.far}`);
        console.error(` This WILL cause depth buffer artifacts (geometry bleeding through).`);
        console.error(` See learnings/DEPTH_BUFFER_PRECISION_CRITICAL.md`);
        console.error(` Recommended: Keep ratio under 1,000,000:1`);
    } else {
        // Good near/far ratio; no log needed
    }

    // Renderer with fallback for Mac/Chrome compatibility
    // Try high-performance first, fall back to default if it fails
    try {
        renderer = new THREE.WebGLRenderer({
            antialias: true,
            preserveDrawingBuffer: true,
            alpha: false,
            powerPreference: "high-performance"
        });

        // Check if renderer actually initialized properly
        const gl = renderer.getContext();
        if (!gl || gl.isContextLost()) {
            throw new Error('Renderer context check failed or lost');
        }
    } catch (e) {
        console.warn('Failed to create WebGL renderer with high-performance, trying fallback:', e);
        // Fallback: try without powerPreference (some older Macs have GPU switching issues)
        try {
            renderer = new THREE.WebGLRenderer({
                antialias: true,
                preserveDrawingBuffer: true,
                alpha: false
                // No powerPreference - let the system decide
            });

            const gl = renderer.getContext();
            if (!gl || gl.isContextLost()) {
                throw new Error('Fallback renderer context check failed or lost');
            }
            console.log('[OK] Using fallback renderer (no powerPreference) for compatibility');
        } catch (e2) {
            // Last resort: minimal renderer settings
            console.error('All WebGL renderer initialization attempts failed:', e2);
            renderer = new THREE.WebGLRenderer({
                antialias: false,
                preserveDrawingBuffer: false,
                alpha: false
            });
            console.warn('[WARN] Using minimal renderer settings - some features may be degraded');
        }
    }

    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    document.getElementById('canvas-container').appendChild(renderer.domElement);

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);
    window.__ambientLight = ambientLight;

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.7);
    dirLight1.position.set(100, 200, 100);
    dirLight1.castShadow = false;
    scene.add(dirLight1);
    window.__dirLight1 = dirLight1;

    const dirLight2 = new THREE.DirectionalLight(0x6688ff, 0.4);
    dirLight2.position.set(-100, 100, -100);
    scene.add(dirLight2);
    window.__dirLight2 = dirLight2;

    // Initialize lighting intensities for Natural (Lambert) shading
    updateLightingForShading();

    // Grid helper
    gridHelper = new THREE.GridHelper(200, 40, 0x555555, 0x222222);
    gridHelper.position.y = -0.1;
    gridHelper.visible = false;
    scene.add(gridHelper);

    // Simple orbit target for rotation - no OrbitControls library needed
    controls = {
        target: new THREE.Vector3(0, 0, 0),
        enabled: true,
        autoRotate: false,
        autoRotateSpeed: 2.0,
        update: function () {
            // Auto-rotate if enabled
            if (this.autoRotate && this.enabled) {
                const angle = this.autoRotateSpeed * 0.01;
                const x = camera.position.x;
                const z = camera.position.z;
                camera.position.x = x * Math.cos(angle) - z * Math.sin(angle);
                camera.position.z = x * Math.sin(angle) + z * Math.cos(angle);
                camera.lookAt(this.target);
            }
        }
    };

    // Initialize raycaster and ground plane for cursor picking and HUD
    // Ground plane is y=0 (map surface) for stable interactions
    raycaster = new THREE.Raycaster();
    groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);

    // Initialize Natural (Lambert) lighting
    try { updateLightingForShading(); } catch (_) { }
}

// (Removed Select2 formatters; using native datalist)

// Track if controls have been set up to prevent duplicate initialization
let controlsInitialized = false;
let suppressRegionChange = false; // Prevent change handler during programmatic updates
let regionIdToName = {};
let regionNameToId = {};
let regionOptions = []; // [{id, name}]

function setupControls() {
    if (controlsInitialized) {
        console.warn('[WARN] setupControls() called multiple times - skipping to prevent memory leak');
        return;
    }

    // Custom dropdown for region input
    const regionInput = document.getElementById('regionSelect');
    const dropdown = document.getElementById('regionDropdown');
    let highlightedIndex = -1;
    let filteredOptions = [];

    function renderDropdown(items) {
        if (!dropdown) return;
        dropdown.innerHTML = '';
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
            const row = document.createElement('div');
            row.textContent = opt.name;
            row.setAttribute('data-id', opt.id);
            row.style.padding = '8px 10px';
            row.style.cursor = 'pointer';
            row.style.fontSize = '12px';
            row.style.borderBottom = '1px solid rgba(85,136,204,0.12)';
            row.addEventListener('mouseenter', () => setHighlight(idx));
            row.addEventListener('mouseleave', () => setHighlight(-1));
            row.addEventListener('mousedown', (e) => {
                e.preventDefault();
                commitSelection(opt);
            });
            dropdown.appendChild(row);
        });
        updateHighlight();
    }

    function openDropdown() {
        if (!dropdown) return;
        filteredOptions = regionOptions.slice();
        highlightedIndex = -1;
        renderDropdown(filteredOptions);
        dropdown.style.display = 'block';
    }

    function closeDropdown() {
        if (!dropdown) return;
        dropdown.style.display = 'none';
        highlightedIndex = -1;
    }

    function setHighlight(idx) {
        highlightedIndex = idx;
        updateHighlight();
    }

    function updateHighlight() {
        if (!dropdown) return;
        const children = dropdown.children;
        for (let i = 0; i < children.length; i++) {
            const el = children[i];
            // Skip styling dividers
            if (el.getAttribute('data-divider') === 'true') {
                el.style.background = 'transparent';
                el.style.color = '#fff';
                continue;
            }
            if (i === highlightedIndex) {
                el.style.background = 'rgba(85,136,204,0.3)';
                el.style.color = '#fff'; // White text on hover
            } else {
                el.style.background = 'transparent';
                el.style.color = '#fff';
            }
        }
    }

    function filterOptions(query) {
        const q = (query || '').trim().toLowerCase();
        if (!q) return regionOptions.slice();
        return regionOptions.filter(o => o.id !== '__divider__' && o.name.toLowerCase().includes(q));
    }

    function commitSelection(opt) {
        if (!regionInput || !opt || opt.id === '__divider__') return;
        regionInput.value = opt.name;
        closeDropdown();
        if (opt.id && opt.id !== currentRegionId) {
            loadRegion(opt.id);
        }
    }

    if (regionInput && dropdown) {
        regionInput.addEventListener('focus', () => {
            openDropdown();
            regionInput.select();  // Auto-select text on focus
        });
        regionInput.addEventListener('click', () => {
            openDropdown();
            regionInput.select();  // Auto-select text on click
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
                    const id = resolveRegionIdFromInput(regionInput.value);
                    if (id) commitSelection({ id, name: regionIdToName[id] || regionInput.value });
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
                const id = resolveRegionIdFromInput(regionInput.value);
                if (!id) regionInput.value = regionIdToName[currentRegionId] || currentRegionId || '';
            }
        });
    }

    // Region navigation buttons
    const regionPrevBtn = document.getElementById('region-prev');
    const regionNextBtn = document.getElementById('region-next');
    if (regionPrevBtn) {
        regionPrevBtn.addEventListener('click', () => {
            navigateRegions(-1);
        });
    }
    if (regionNextBtn) {
        regionNextBtn.addEventListener('click', () => {
            navigateRegions(1);
        });
    }

    // Color scheme uses native select; no Select2 initialization

    // Update bucket size range label
    function updateBucketSizeLabel(value) {
        const label = document.getElementById('bucketSizeRangeLabel');
        if (value === 1) {
            label.textContent = 'Full resolution (1 pixel = 1 bar)';
        } else if (value <= 5) {
            label.textContent = `Low reduction (${value}x${value} pixels per bar)`;
        } else if (value <= 15) {
            label.textContent = `Medium reduction (${value}x${value} pixels per bar)`;
        } else if (value <= 30) {
            label.textContent = `High reduction (${value}x${value} pixels per bar)`;
        } else {
            label.textContent = `Very high reduction (${value}x${value} pixels per bar)`;
        }
    }

    // Initialize compact resolution scale control
    try { initResolutionScale(); } catch (_) { }

    // Tile gap - instant via shader uniform in bars mode; recreate only if not bars
    const updateTileGapUniform = () => {
        if (params.renderMode !== 'bars' || !terrainMesh || !terrainMesh.material) return;
        const u = terrainMesh.material.userData && terrainMesh.material.userData.uTileScaleUniform;
        if (!u) return;
        const gapMultiplier = 1 - (params.tileGap / 100);
        const bucketMultiplier = params.bucketSize;
        const newTileSize = gapMultiplier * bucketMultiplier;
        const base = (lastBarsTileSize && lastBarsTileSize > 0) ? lastBarsTileSize : newTileSize;
        u.value = newTileSize / base;
    };
    const scheduleTileGapUpdate = () => {
        if (pendingTileGapRaf !== null) cancelAnimationFrame(pendingTileGapRaf);
        pendingTileGapRaf = requestAnimationFrame(() => {
            pendingTileGapRaf = null;
            updateTileGapUniform();
        });
    };

    // Tile gap UI removed; add listeners only if elements exist
    const tileGapSliderEl = document.getElementById('tileGap');
    const tileGapNumberEl = document.getElementById('tileGapInput');
    if (tileGapSliderEl) {
        tileGapSliderEl.addEventListener('input', (e) => {
            params.tileGap = parseInt(e.target.value);
            if (tileGapNumberEl) tileGapNumberEl.value = params.tileGap;
            if (params.renderMode === 'bars') {
                scheduleTileGapUpdate();
            } else {
                recreateTerrain();
            }
            updateURLParameter('tileGap', params.tileGap);
        });
    }
    if (tileGapNumberEl) {
        tileGapNumberEl.addEventListener('change', (e) => {
            let value = parseInt(e.target.value);
            value = Math.max(0, Math.min(99, value));
            params.tileGap = value;
            if (tileGapSliderEl) tileGapSliderEl.value = value;
            tileGapNumberEl.value = value;
            if (params.renderMode === 'bars') {
                updateTileGapUniform();
            } else {
                recreateTerrain();
            }
            updateURLParameter('tileGap', params.tileGap);
        });
    }

    // Aggregation method (only if UI exists)
    const aggregationSelect = document.getElementById('aggregation');
    if (aggregationSelect) {
        aggregationSelect.addEventListener('change', (e) => {
            console.log(` Aggregation: ${params.aggregation} -> ${e.target.value}`);
            params.aggregation = e.target.value;
            // Clear edge markers so they get recreated at new positions
            if (terrainGroup) {
                edgeMarkers.forEach(marker => terrainGroup.remove(marker));
            }
            edgeMarkers = [];
            rebucketData();
            recreateTerrain();
            // Remove focus from dropdown so keyboard navigation works
            e.target.blur();
            updateURLParameter('aggregation', params.aggregation);
        });
    }

    // Render mode
    document.getElementById('renderMode').addEventListener('change', (e) => {
        let nextMode = e.target.value;
        if (nextMode === 'wireframe') {
            // Wireframe disabled: fallback to surface
            nextMode = 'surface';
            e.target.value = 'surface';
        }
        params.renderMode = nextMode;
        // Clear edge markers so they get recreated at new positions for new render mode
        if (terrainGroup) {
            edgeMarkers.forEach(marker => terrainGroup.remove(marker));
        }
        edgeMarkers = [];
        recreateTerrain();
        // Remove focus from dropdown so keyboard navigation works
        e.target.blur();
        updateURLParameter('renderMode', params.renderMode);
    });

    // Vertical exaggeration - immediate updates while dragging

    // Sync slider -> input (update immediately)
    const debouncedNormalsRecompute = window.FormatUtils.debounce(() => {
        if (terrainMesh && terrainMesh.geometry && params.renderMode === 'surface') {
            terrainMesh.geometry.computeVertexNormals();
            updateEdgeMarkers();
        }
    }, 80);

    const scheduleVertExagUpdate = () => {
        if (pendingVertExagRaf !== null) cancelAnimationFrame(pendingVertExagRaf);
        pendingVertExagRaf = requestAnimationFrame(() => {
            pendingVertExagRaf = null;
            updateTerrainHeight();
        });
    };

    document.getElementById('vertExag').addEventListener('input', (e) => {
        const multiplier = parseFloat(e.target.value);
        params.verticalExaggeration = multiplierToInternal(multiplier);
        document.getElementById('vertExagInput').value = multiplier;

        // Update button states
        updateVertExagButtons(params.verticalExaggeration);

        // Coalesce rapid updates to once-per-frame
        scheduleVertExagUpdate();
        // Defer expensive normals compute while dragging (surface)
        debouncedNormalsRecompute();
    });
    // Finalize on slider change (compute normals once promptly)
    document.getElementById('vertExag').addEventListener('change', (e) => {
        if (terrainMesh && terrainMesh.geometry && params.renderMode === 'surface') {
            terrainMesh.geometry.computeVertexNormals();
            updateEdgeMarkers();
        } else if (params.renderMode === 'bars' || params.renderMode === 'points') {
            // No recreate needed for exaggeration changes; shader/point updates already applied
        }
        // Persist user-facing multiplier
        updateURLParameter('exag', internalToMultiplier(params.verticalExaggeration));
    });

    // Sync input -> slider
    document.getElementById('vertExagInput').addEventListener('change', (e) => {
        let multiplier = parseFloat(e.target.value);
        // Clamp to valid range (1 to 100)
        multiplier = Math.max(1, Math.min(100, multiplier));
        params.verticalExaggeration = multiplierToInternal(multiplier);
        document.getElementById('vertExag').value = multiplier;
        document.getElementById('vertExagInput').value = multiplier;

        // Update button states
        updateVertExagButtons(params.verticalExaggeration);

        scheduleVertExagUpdate();
        if (terrainMesh && terrainMesh.geometry && params.renderMode === 'surface') {
            terrainMesh.geometry.computeVertexNormals();
            updateEdgeMarkers();
        }
        updateURLParameter('exag', multiplier);
    });

    // Color scheme
    $('#colorScheme').on('change', function (e) {
        params.colorScheme = $(this).val();
        if (params.colorScheme === 'auto-stretch') {
            computeAutoStretchStats();
        }
        updateColors();
        updateURLParameter('colorScheme', params.colorScheme);
        updateColorSchemeDescription();
    });

    // Color scheme quick jump buttons (move by 1 option)
    const csSelect = document.getElementById('colorScheme');
    const csUpBtn = document.getElementById('colorSchemeUp');
    const csDownBtn = document.getElementById('colorSchemeDown');
    const jumpBy = 1;
    if (csSelect && csUpBtn && csDownBtn) {
        const jumpToIndex = (delta) => {
            const total = csSelect.options.length;
            let idx = csSelect.selectedIndex;
            if (idx < 0) idx = 0;
            let next = idx + delta;
            if (next < 0) next = 0;
            if (next >= total) next = total - 1;
            if (next !== idx) {
                csSelect.selectedIndex = next;
                $('#colorScheme').trigger('change');
            }
        };
        csUpBtn.addEventListener('click', () => jumpToIndex(-jumpBy));
        csDownBtn.addEventListener('click', () => jumpToIndex(+jumpBy));
    }

    // Shading: Always Natural (Lambert) - no UI control

    // Initialize vertical exaggeration button states (highlight default active button)
    updateVertExagButtons(params.verticalExaggeration);

    // Mark controls as initialized to prevent duplicate setup
    controlsInitialized = true;
    console.log('Controls initialized successfully');
}

// ===== RESOLUTION LOADING OVERLAY =====
// Resolution controls now in resolution-controls.js
function showResolutionLoading() {
    return window.ResolutionControls.showLoading();
}

function hideResolutionLoading() {
    return window.ResolutionControls.hideLoading();
}

function bucketSizeToPercent(size) {
    return window.ResolutionControls.bucketSizeToPercent(size);
}

function percentToBucketSize(percent) {
    return window.ResolutionControls.percentToBucketSize(percent);
}

function updateResolutionScaleUI(size) {
    return window.ResolutionControls.updateUI(size);
}

function initResolutionScale() {
    return window.ResolutionControls.init();
}

function adjustBucketSize(delta) {
    return window.ResolutionControls.adjust(delta);
}

function setMaxResolution() {
    return window.ResolutionControls.setMax();
}

function setDefaultResolution() {
    return window.ResolutionControls.setDefault();
}

function autoAdjustBucketSize() {
    return window.ResolutionControls.autoAdjust();
}

function setupEventListeners() {
    window.addEventListener('resize', onWindowResize);
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);

    // Prevent context menu on right-click (so we can use right-drag for rotation)
    renderer.domElement.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        return false;
    });

    // Route events to active camera scheme
    renderer.domElement.addEventListener('wheel', (e) => {
        e.preventDefault();
        if (activeScheme) activeScheme.onWheel(e);
    }, { passive: false });

    renderer.domElement.addEventListener('mousedown', (e) => {
        if (activeScheme) activeScheme.onMouseDown(e);
    });

    // Handle clicks on connectivity labels (US state neighbors)
    renderer.domElement.addEventListener('click', (e) => {
        if (typeof handleConnectivityClick === 'function') {
            // Use raycaster to check for sprite clicks
            const mouse = new THREE.Vector2();
            mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(scene.children, true);

            for (const intersect of intersects) {
                if (handleConnectivityClick(intersect.object)) {
                    break; // Stop after first handled click
                }
            }
        }
    });

    renderer.domElement.addEventListener('mousemove', (e) => {
        // Track mouse for HUD and zoom-to-cursor
        currentMouseX = e.clientX;
        currentMouseY = e.clientY;
        if (activeScheme) activeScheme.onMouseMove(e);
        // Update HUD live
        updateCursorHUD(e.clientX, e.clientY);

        // Check if hovering over connectivity label
        if (typeof handleConnectivityClick === 'function') {
            const mouse = new THREE.Vector2();
            mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(scene.children, true);

            let overLabel = false;
            for (const intersect of intersects) {
                if (intersect.object.userData.isConnectivityLabel) {
                    overLabel = true;
                    break;
                }
            }
            renderer.domElement.style.cursor = overLabel ? 'pointer' : 'default';
        }
    });

    renderer.domElement.addEventListener('mouseup', (e) => {
        if (activeScheme) activeScheme.onMouseUp(e);
    });

    // Handle clicks on edge markers (combined compass + neighbors)
    renderer.domElement.addEventListener('click', (e) => {
        if (e.button !== 0) return; // Only left click

        const mouse = new THREE.Vector2();
        mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
        mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;

        raycaster.setFromCamera(mouse, camera);

        if (edgeMarkers && edgeMarkers.length > 0) {
            const intersects = raycaster.intersectObjects(edgeMarkers);
            if (intersects.length > 0) {
                const intersection = intersects[0];
                const marker = intersection.object;

                // Check if this marker has clickable neighbors
                if (marker.userData.isClickable && marker.userData.neighborIds && marker.userData.neighborIds.length > 0) {
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
                        console.log(`Clicked button ${clickedButton.index + 1}/${buttonBounds.length}: ${neighborName} (UV.y=${uv.y.toFixed(3)}, bounds=[${clickedButton.uvBottom.toFixed(3)}, ${clickedButton.uvTop.toFixed(3)}])`);
                        loadRegion(neighborId);
                    } else {
                        // Clicked on compass letter area or outside buttons - load first neighbor
                        const neighborId = marker.userData.neighborIds[0];
                        const neighborName = marker.userData.neighborNames[0];
                        console.log(`Clicked outside buttons (UV.y=${uv.y.toFixed(3)}) -> loading ${neighborName}`);
                        loadRegion(neighborId);
                    }
                }
            }
        }
    });

    // Handle hover effects on clickable edge markers
    renderer.domElement.addEventListener('mousemove', (e) => {
        const mouse = new THREE.Vector2();
        mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
        mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;

        raycaster.setFromCamera(mouse, camera);

        if (edgeMarkers && edgeMarkers.length > 0) {
            const intersects = raycaster.intersectObjects(edgeMarkers);

            // Check if hovering over a clickable marker
            let isHoveringClickable = false;
            if (intersects.length > 0) {
                const marker = intersects[0].object;
                if (marker.userData.isClickable) {
                    isHoveringClickable = true;
                }
            }

            renderer.domElement.style.cursor = isHoveringClickable ? 'pointer' : 'default';
        }
    });

    // Setup camera scheme selector
    document.getElementById('cameraScheme').addEventListener('change', (e) => {
        switchCameraScheme(e.target.value);
        updateURLParameter('camera', e.target.value);
    });

    // Initialize default scheme (Google Maps Ground Plane)
    switchCameraScheme('ground-plane');

    // Mobile/UI controls toggle
    const mobileToggleBtn = document.getElementById('mobile-ui-toggle');
    if (mobileToggleBtn) {
        const isSmallScreen = window.innerWidth <= 768;
        if (isSmallScreen) {
            document.body.classList.add('ui-collapsed');
            mobileToggleBtn.textContent = 'Show Controls';
        }
        const updateLabel = () => {
            const collapsed = document.body.classList.contains('ui-collapsed');
            mobileToggleBtn.textContent = collapsed ? 'Show Controls' : 'Hide Controls';
        };
        mobileToggleBtn.addEventListener('click', () => {
            document.body.classList.toggle('ui-collapsed');
            updateLabel();
        });
        // If screen resizes across breakpoint, keep sensible state
        window.addEventListener('resize', () => {
            const small = window.innerWidth <= 768;
            if (small && !document.body.classList.contains('ui-collapsed')) {
                document.body.classList.add('ui-collapsed');
                updateLabel();
            }
        });
    }

    // HUD config toggles
    const hudConfigBtn = document.getElementById('hud-config');
    const hudConfigPanel = document.getElementById('hud-config-panel');
    if (hudConfigBtn && hudConfigPanel) {
        hudConfigBtn.addEventListener('click', () => {
            const visible = hudConfigPanel.style.display !== 'none';
            hudConfigPanel.style.display = visible ? 'none' : 'block';
        });
        // Load settings and bind controls
        loadHudSettings();
        applyHudSettingsToUI();
        bindHudSettingsHandlers();
    }

    // HUD show/hide toggle
    const showHUDCheckbox = document.getElementById('showHUD');
    const hudElement = document.getElementById('info');
    if (showHUDCheckbox && hudElement) {
        showHUDCheckbox.addEventListener('change', () => {
            hudElement.style.display = showHUDCheckbox.checked ? 'block' : 'none';
        });
    }

    // Color Scale show/hide toggle
    const showColorScaleCheckbox = document.getElementById('showColorScale');
    if (showColorScaleCheckbox && typeof colorLegend !== 'undefined') {
        // Load saved preference from localStorage (default: true)
        const savedColorScaleVisible = localStorage.getItem('colorScaleVisible');
        if (savedColorScaleVisible !== null) {
            showColorScaleCheckbox.checked = savedColorScaleVisible === 'true';
        }

        // Apply initial visibility state
        if (showColorScaleCheckbox.checked) {
            if (colorLegend && typeof colorLegend.show === 'function') {
                colorLegend.show();
            }
        } else {
            if (colorLegend && typeof colorLegend.hide === 'function') {
                colorLegend.hide();
            }
        }

        // Add change listener
        showColorScaleCheckbox.addEventListener('change', () => {
            const visible = showColorScaleCheckbox.checked;
            if (visible) {
                if (colorLegend && typeof colorLegend.show === 'function') {
                    colorLegend.show();
                }
                // Update with current data if available
                if (typeof updateColorLegend === 'function') {
                    updateColorLegend();
                }
            } else {
                if (colorLegend && typeof colorLegend.hide === 'function') {
                    colorLegend.hide();
                }
            }
            // Save preference to localStorage
            localStorage.setItem('colorScaleVisible', String(visible));
        });
    }

    // Edge Markers show/hide toggle
    const showEdgeMarkersCheckbox = document.getElementById('showEdgeMarkers');
    if (showEdgeMarkersCheckbox) {
        // Load saved preference from localStorage (default: true)
        const savedEdgeMarkersVisible = localStorage.getItem('edgeMarkersVisible');
        if (savedEdgeMarkersVisible !== null) {
            showEdgeMarkersCheckbox.checked = savedEdgeMarkersVisible === 'true';
        }

        // Apply initial visibility state
        edgeMarkers.forEach(marker => {
            marker.visible = showEdgeMarkersCheckbox.checked;
        });

        // Add change listener
        showEdgeMarkersCheckbox.addEventListener('change', () => {
            const visible = showEdgeMarkersCheckbox.checked;
            edgeMarkers.forEach(marker => {
                marker.visible = visible;
            });
            // Save preference to localStorage
            localStorage.setItem('edgeMarkersVisible', String(visible));
        });
    }

    // Camera Controls show/hide toggle
    const showCameraControlsCheckbox = document.getElementById('showCameraControls');
    const cameraControlsSection = document.getElementById('camera-controls-section');
    if (showCameraControlsCheckbox && cameraControlsSection) {
        // Load saved preference from localStorage (default: false)
        const savedCameraControlsVisible = localStorage.getItem('cameraControlsVisible');
        if (savedCameraControlsVisible !== null) {
            showCameraControlsCheckbox.checked = savedCameraControlsVisible === 'true';
        }

        // Apply initial visibility state
        cameraControlsSection.style.display = showCameraControlsCheckbox.checked ? 'block' : 'none';

        // Add change listener
        showCameraControlsCheckbox.addEventListener('change', () => {
            const visible = showCameraControlsCheckbox.checked;
            cameraControlsSection.style.display = visible ? 'block' : 'none';
            // Save preference to localStorage
            localStorage.setItem('cameraControlsVisible', String(visible));
        });
    }

    // HUD dragging functionality
    initHudDragging();

    // Load saved HUD position
    loadHudPosition();
}

// HUD dragging - entire HUD is grabbable, instant with zero lag
function initHudDragging() {
    const hud = document.getElementById('info');
    if (!hud) return;

    let isDragging = false;
    let offsetX, offsetY;

    hud.addEventListener('mousedown', (e) => {
        // Don't start drag if clicking on buttons or inputs
        if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT') {
            return;
        }

        isDragging = true;
        const rect = hud.getBoundingClientRect();
        offsetX = e.clientX - rect.left;
        offsetY = e.clientY - rect.top;
        e.preventDefault();
        e.stopPropagation();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;

        // Calculate new position instantly
        let newLeft = e.clientX - offsetX;
        let newTop = e.clientY - offsetY;

        // Keep HUD within viewport bounds
        const maxLeft = window.innerWidth - hud.offsetWidth - 10;
        const maxTop = window.innerHeight - hud.offsetHeight - 10;
        newLeft = Math.max(10, Math.min(newLeft, maxLeft));
        newTop = Math.max(10, Math.min(newTop, maxTop));

        // Apply instantly without any delay
        hud.style.left = newLeft + 'px';
        hud.style.top = newTop + 'px';
    }, { passive: false });

    document.addEventListener('mouseup', () => {
        if (isDragging) {
            isDragging = false;
            saveHudPosition();
        }
    });
}

function saveHudPosition() {
    const hud = document.getElementById('info');
    if (!hud) return;
    try {
        const position = {
            left: hud.style.left,
            top: hud.style.top
        };
        localStorage.setItem('hudPosition', JSON.stringify(position));
    } catch (_) { }
}

function loadHudPosition() {
    const hud = document.getElementById('info');
    if (!hud) return;
    try {
        const saved = localStorage.getItem('hudPosition');
        if (saved) {
            const position = JSON.parse(saved);
            if (position.left) hud.style.left = position.left;
            if (position.top) hud.style.top = position.top;
        }
    } catch (_) { }
}

// OLD CAMERA CONTROL CODE - REPLACED BY SCHEMES
// Keeping these functions temporarily for reference/backwards compatibility
function linearZoom_OLD(delta) {
    if (!camera) return;

    // Try to get the 3D point under the cursor
    const targetPoint = raycastToWorld(currentMouseX, currentMouseY);

    if (!targetPoint) {
        // Fallback: move in view direction if raycast fails
        const forward = new THREE.Vector3();
        camera.getWorldDirection(forward);
        forward.normalize();

        const baseSpeed = 50;
        const moveAmount = -1 * (delta > 0 ? baseSpeed : -baseSpeed);
        const movement = forward.multiplyScalar(moveAmount);

        // Move camera AND target together to maintain orientation
        camera.position.add(movement);
        controls.target.add(movement);
        return;
    }

    // Calculate zoom factor based on distance and scroll delta
    const distanceToTarget = camera.position.distanceTo(targetPoint);

    // Zoom speed: percentage of distance per scroll tick
    let zoomSpeed = 0.15; // 15% of distance per tick

    // Shift modifier for precise zoom
    if (keyboard.shift) {
        zoomSpeed = 0.03; // 3% for precise control
    }

    // Scroll UP (negative delta) = zoom IN (move toward target)
    // Scroll DOWN (positive delta) = zoom OUT (move away from target)
    const zoomDirection = delta > 0 ? 1 : -1; // positive = zoom out, negative = zoom in
    const zoomFactor = 1.0 + (zoomSpeed * zoomDirection);

    // Don't zoom too close
    const newDistance = distanceToTarget * zoomFactor;
    if (newDistance < 1.0) {
        return;
    }

    // Calculate direction from camera to target point
    const direction = new THREE.Vector3();
    direction.subVectors(targetPoint, camera.position);
    direction.normalize();

    // Move camera toward/away from target point
    const moveAmount = distanceToTarget * (1.0 - zoomFactor);
    camera.position.addScaledVector(direction, moveAmount);

    // Also move the orbit target slightly toward the cursor point
    // This keeps the view centered on what you're looking at
    controls.target.addScaledVector(direction, moveAmount * 0.05);
}

// Create a visual marker showing rotation pivot point
function createPivotMarker(position) {
    // Remove old marker
    if (pivotMarker) {
        scene.remove(pivotMarker);
    }

    // Scale marker based on terrain size
    const scale = rawElevationData ? calculateRealWorldScale() : { widthMeters: 1000, heightMeters: 1000 };
    const avgSize = (scale.widthMeters + scale.heightMeters) / 2;
    const markerSize = avgSize * 0.01; // 1% of average terrain dimension

    // Create a bright sphere at the pivot point
    const geometry = new THREE.SphereGeometry(markerSize, 16, 16);
    const material = new THREE.MeshBasicMaterial({
        color: 0xff00ff,
        transparent: true,
        opacity: 0.9,
        depthTest: false // Always visible
    });
    pivotMarker = new THREE.Mesh(geometry, material);
    pivotMarker.position.copy(position);
    scene.add(pivotMarker);

    console.log(`Pivot marker created at (${position.x.toFixed(0)}, ${position.y.toFixed(0)}, ${position.z.toFixed(0)}) with size ${markerSize.toFixed(0)}m`);

    // Auto-remove after 3 seconds
    setTimeout(() => {
        if (pivotMarker) {
            scene.remove(pivotMarker);
            pivotMarker = null;
        }
    }, 3000);
}

// Geometry utilities now in js/geometry-utils.js
function calculateRealWorldScale(data) {
    return window.GeometryUtils.calculateRealWorldScale(data);
}

function createTerrain() {
    const t0 = performance.now();

    // Remove old terrain and DISPOSE geometry/materials
    if (terrainGroup) {
        scene.remove(terrainGroup);
    }

    // Create new terrain group (centered at world origin for rotation)
    terrainGroup = new THREE.Group();
    terrainGroup.position.set(0, 0, 0);
    scene.add(terrainGroup);
    window.terrainGroup = terrainGroup; // Expose for camera controls

    const { width, height, elevation } = processedData;

    // Calculate real-world scale
    const scale = calculateRealWorldScale();

    if (params.renderMode === 'bars') {
        createBarsTerrain(width, height, elevation, scale);
    } else if (params.renderMode === 'points') {
        createPointCloudTerrain(width, height, elevation, scale);
    } else {
        createSurfaceTerrain(width, height, elevation, scale);
    }

    // Center terrain - different centering for different modes
    // Note: Position is preserved in recreateTerrain() to keep map fixed when bucket size changes
    if (terrainMesh) {
        if (params.renderMode === 'bars') {
            // Bars use UNIFORM 2D grid - same spacing in X and Z (no aspect ratio)
            const bucketMultiplier = params.bucketSize;
            terrainMesh.position.x = -(width - 1) * bucketMultiplier / 2;
            terrainMesh.position.z = -(height - 1) * bucketMultiplier / 2; // NO aspect ratio scaling!
            console.log(`Bars centered: uniform grid ${width}x${height}, tile size ${bucketMultiplier}, offset (${terrainMesh.position.x.toFixed(1)}, ${terrainMesh.position.z.toFixed(1)})`);
        } else if (params.renderMode === 'points') {
            // Points use uniform grid positioning, scaled by bucketSize
            const bucketSize = params.bucketSize;
            terrainMesh.position.x = -(width - 1) * bucketSize / 2;
            terrainMesh.position.z = -(height - 1) * bucketSize / 2;
            console.log(`Points centered: uniform grid ${width}x${height}, bucket size ${bucketSize}, offset (${terrainMesh.position.x.toFixed(1)}, ${terrainMesh.position.z.toFixed(1)})`);
        } else {
            // Surface mode: PlaneGeometry is already centered, but position it at origin
            terrainMesh.position.set(0, 0, 0);
            console.log(`Surface centered: geometry naturally centered`);
        }
    }

    const t1 = performance.now();
    appendActivityLog(`Terrain created in ${(t1 - t0).toFixed(1)}ms`);

    terrainStats.vertices = width * height;
    terrainStats.bucketedVertices = width * height;

    // Update camera scheme with terrain bounds for F key reframing
    if (controls && controls.activeScheme && controls.activeScheme.setTerrainBounds) {
        // Calculate bounds based on render mode
        if (params.renderMode === 'bars') {
            const bucketMultiplier = params.bucketSize;
            const halfWidth = (width - 1) * bucketMultiplier / 2;
            const halfDepth = (height - 1) * bucketMultiplier / 2;
            controls.activeScheme.setTerrainBounds(-halfWidth, halfWidth, -halfDepth, halfDepth);
        } else if (params.renderMode === 'points') {
            const bucketSize = params.bucketSize;
            const halfWidth = (width - 1) * bucketSize / 2;
            const halfDepth = (height - 1) * bucketSize / 2;
            controls.activeScheme.setTerrainBounds(-halfWidth, halfWidth, -halfDepth, halfDepth);
        } else {
            // Surface mode - use geometry grid extents (uniform grid, scaled by bucketSize)
            const bucketMultiplier = params.bucketSize;
            const halfWidth = (width * bucketMultiplier) / 2;
            const halfDepth = (height * bucketMultiplier) / 2;
            controls.activeScheme.setTerrainBounds(-halfWidth, halfWidth, -halfDepth, halfDepth);
        }
    }

    // PRODUCT REQUIREMENT: Edge markers must stay fixed when vertical exaggeration changes
    // Only create edge markers if they don't exist yet (prevents movement on exaggeration change)
    if (edgeMarkers.length === 0) {
        createEdgeMarkers();
        // Create connectivity labels alongside edge markers
        if (typeof createConnectivityLabels === 'function') {
            createConnectivityLabels();
        }
    }

    updateStats();
}

function createBarsTerrain(width, height, elevation, scale) {
    // PURE 2D GRID APPROACH:
    // Treat the input data as a perfect 2D grid with uniform square tiles.
    // This is the correct approach because:
    // 1. The input data IS a perfect 2D array - no gaps, overlaps, or irregularities
    // 2. Each data point [i,j] should map to one uniform tile in 3D space
    // 3. Bucket size just creates larger square tiles (more chunky/blurred), not stretching
    // 4. This avoids distortion from real-world projections and maintains data integrity
    // Use shared dummy object for instancing transforms to avoid reallocations

    // Bucket multiplier determines tile size (larger = more chunky visualization)
    const bucketMultiplier = params.bucketSize;

    // Create SQUARE bars for uniform 2D grid (no stretching or distortion)
    // Gap: 0% = tiles touching (1.0), 1% = 0.99, 50% = 0.5, 99% = 0.01 (tiny tiles)
    const gapMultiplier = 1 - (params.tileGap / 100);
    const tileSize = gapMultiplier * bucketMultiplier;
    // Base unit cube (1x1x1). We'll scale X/Z per-instance so tile gap can update without rebuilds.
    const baseGeometry = new THREE.BoxGeometry(1, 1, 1, 1, 1, 1);

    console.log(`PURE 2D GRID: ${width} x ${height} bars (spacing: ${bucketMultiplier}x, gap: ${params.tileGap}%)`);
    console.log(`Tile XZ footprint: ${tileSize.toFixed(2)} x ${tileSize.toFixed(2)} (uniform squares, NEVER changes with Y scale)`);
    console.log(`Grid spacing: X=${bucketMultiplier}, Z=${bucketMultiplier} (uniform, INDEPENDENT of height)`);
    console.log(`Vertical exaggeration: ${params.verticalExaggeration.toFixed(5)}x (affects ONLY Y-axis)`);
    console.log(`Grid approach: Each data point [i,j] -> one square tile, no distortion`);

    // First pass: count valid (non-null) samples to preallocate buffers
    let barCount = 0;
    for (let i = 0; i < height; i++) {
        const row = elevation[i];
        if (!row) continue;
        for (let j = 0; j < width; j++) {
            const z = row[j];
            if (z === null || z === undefined) continue;
            barCount++;
        }
    }
    // Always use Natural (Lambert) shading
    const material = new THREE.MeshLambertMaterial({ vertexColors: true });

    const instancedMesh = new THREE.InstancedMesh(
        baseGeometry,
        material,
        barCount
    );
    instancedMesh.frustumCulled = false; // Stable bounds; avoid per-frame recomputation cost

    // Set transform and color for each instance using typed mappings
    // Use Float32 colors for exact previous visual appearance (0..1 per channel)
    const colorArray = new Float32Array(barCount * 3);
    barsIndexToRow = new Int32Array(barCount);
    barsIndexToCol = new Int32Array(barCount);

    let idx = 0;
    for (let i = 0; i < height; i++) {
        const row = elevation[i];
        if (!row) continue;
        for (let j = 0; j < width; j++) {
            let z = row[j];
            if (z === null || z === undefined) continue;

            const elev = Math.max(z * params.verticalExaggeration, 0.1);
            const xPos = j * bucketMultiplier;
            const zPos = i * bucketMultiplier;
            const yPos = elev * 0.5;

            barsDummy.rotation.set(0, 0, 0);
            barsDummy.position.set(xPos, yPos, zPos);
            barsDummy.scale.set(tileSize, elev, tileSize);
            barsDummy.updateMatrix();
            instancedMesh.setMatrixAt(idx, barsDummy.matrix);

            const c = getColorForElevation(z);
            colorArray[idx * 3] = c.r;
            colorArray[idx * 3 + 1] = c.g;
            colorArray[idx * 3 + 2] = c.b;

            barsIndexToRow[idx] = i;
            barsIndexToCol[idx] = j;
            idx++;
        }
    }

    // Persist references for fast, in-place updates (no rebuilds)
    barsInstancedMesh = instancedMesh;
    // barData removed in favor of compact typed index maps
    barsTileSize = tileSize;
    // Remove verbose per-bar sample logging to reduce console overhead

    // CRITICAL: Mark instance matrix as needing GPU update
    instancedMesh.instanceMatrix.needsUpdate = true;

    // Add colors as instance attribute
    baseGeometry.setAttribute('instanceColor', new THREE.InstancedBufferAttribute(colorArray, 3));
    instancedMesh.material.vertexColors = true;

    // Enable custom vertex colors and add uExaggeration uniform for instant height scaling
    instancedMesh.material.onBeforeCompile = (shader) => {
        // Inject attributes/uniforms
        // IMPORTANT: Bars are created using current params.verticalExaggeration baked into instance scale.
        // The shader uniform represents the RATIO relative to that baked value.
        shader.uniforms.uExaggeration = { value: 1.0 };
        // uTileScale scales X/Z in local space relative to built tile size
        shader.uniforms.uTileScale = { value: 1.0 };
        instancedMesh.material.userData = instancedMesh.material.userData || {};
        instancedMesh.material.userData.uExaggerationUniform = shader.uniforms.uExaggeration;
        instancedMesh.material.userData.uTileScaleUniform = shader.uniforms.uTileScale;

        shader.vertexShader = shader.vertexShader.replace(
            '#include <color_pars_vertex>',
            `#include <color_pars_vertex>\nattribute vec3 instanceColor;\nuniform float uExaggeration;\nuniform float uTileScale;`
        );

        // Pass per-instance color
        shader.vertexShader = shader.vertexShader.replace(
            '#include <color_vertex>',
            `#include <color_vertex>\n#ifdef USE_INSTANCING\n vColor = instanceColor;\n#endif`
        );

        // Apply vertical exaggeration in local space BEFORE instancing transform.
        // Keep bar bottoms anchored at ground by adding (uExaggeration-1)/2 offset in local space,
        // which becomes (uExaggeration-1)*instanceHeight/2 after instance scaling.
        shader.vertexShader = shader.vertexShader.replace(
            '#include <begin_vertex>',
            `#include <begin_vertex>\ntransformed.xz*= uTileScale;\ntransformed.y = transformed.y* uExaggeration + (uExaggeration - 1.0)* 0.5;`
        );
    };

    terrainMesh = instancedMesh;
    terrainGroup.add(terrainMesh); // Add to group instead of scene directly
    window.terrainMesh = terrainMesh; // Expose for camera controls
    terrainStats.bars = barCount;
    // Record the internal exaggeration used when building bars and reset uniform to 1.0
    lastBarsExaggerationInternal = params.verticalExaggeration;
    lastBarsTileSize = tileSize;
    if (terrainMesh.material && terrainMesh.material.userData && terrainMesh.material.userData.uExaggerationUniform) {
        terrainMesh.material.userData.uExaggerationUniform.value = 1.0;
    }
    if (terrainMesh.material && terrainMesh.material.userData && terrainMesh.material.userData.uTileScaleUniform) {
        terrainMesh.material.userData.uTileScaleUniform.value = 1.0;
    }
    console.log(`Created ${barCount.toLocaleString()} instanced bars (OPTIMIZED)`);
    console.log(`Scene now has ${scene.children.length} total objects`);

    // DEBUG: List all meshes in scene
    let meshCount = 0;
    let instancedMeshCount = 0;
    scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh) meshCount++;
        if (obj instanceof THREE.InstancedMesh) {
            instancedMeshCount++;
        }
    });
    console.log(`Total meshes: ${meshCount}, InstancedMeshes: ${instancedMeshCount}`);

    // Performance warning and suggestion
    if (barCount > 15000) {
        console.warn(`Very high bar count (${barCount.toLocaleString()})! Consider:
 - Increase bucket multiplier to ${Math.ceil(params.bucketSize * 1.5)}x+
 - Switch to 'Surface' render mode for better performance
 - Current: ${Math.floor(100 * barCount / (width * height))}% of bucketed grid has data`);
    } else if (barCount > 8000) {
        console.warn(`High bar count (${barCount.toLocaleString()}). Increase bucket multiplier if laggy.`);
    }
}

function createPointCloudTerrain(width, height, elevation, scale) {
    const geometry = new THREE.BufferGeometry();
    const positions = [];
    const colors = [];

    // Uniform grid spacing - treat as simple 2D grid, scaled by bucketSize
    const bucketSize = params.bucketSize; // Match bars mode spacing

    // GeoTIFF: elevation[row][col] where row=North->South (i), col=West->East (j)
    for (let i = 0; i < height; i++) { // row (North to South)
        for (let j = 0; j < width; j++) { // column (West to East)
            let z = elevation[i] && elevation[i][j];
            if (z === null || z === undefined) z = 0;

            // Uniform 2D grid positioning
            const xPos = j * bucketSize;
            const zPos = i * bucketSize;
            positions.push(xPos, z * params.verticalExaggeration, zPos);

            const color = getColorForElevation(z);
            colors.push(color.r, color.g, color.b);
        }
    }

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
        size: bucketSize * 1.5, // Point size scales with bucket size
        vertexColors: true,
        sizeAttenuation: true
    });

    // Create points mesh
    const points = new THREE.Points(geometry, material);

    // Add uExaggeration uniform to scale Y on the GPU (ratio relative to build exaggeration)
    points.material.onBeforeCompile = (shader) => {
        shader.uniforms.uExaggeration = { value: 1.0 };
        points.material.userData = points.material.userData || {};
        points.material.userData.uExaggerationUniform = shader.uniforms.uExaggeration;
        shader.vertexShader = shader.vertexShader.replace(
            'void main() {',
            'uniform float uExaggeration;\nvoid main() {'
        );
        shader.vertexShader = shader.vertexShader.replace(
            '#include <begin_vertex>',
            `#include <begin_vertex>\ntransformed.y*= uExaggeration;`
        );
    };

    terrainMesh = points;
    terrainGroup.add(terrainMesh); // Add to group instead of scene directly
    window.terrainMesh = terrainMesh; // Expose for camera controls
    lastPointsExaggerationInternal = params.verticalExaggeration;
    if (terrainMesh.material && terrainMesh.material.userData && terrainMesh.material.userData.uExaggerationUniform) {
        terrainMesh.material.userData.uExaggerationUniform.value = 1.0;
    }
}

function createSurfaceTerrain(width, height, elevation, scale) {
    // Create uniform 2D grid - no geographic corrections
    // Treat data as simple evenly-spaced grid points
    // Scale by bucketSize to match bars mode extent
    const bucketMultiplier = params.bucketSize;
    const geometry = new THREE.PlaneGeometry(
        width * bucketMultiplier, height * bucketMultiplier, width - 1, height - 1
    );

    const isWireframe = (params.renderMode === 'wireframe');
    const colors = isWireframe ? null : [];
    const positions = geometry.attributes.position;

    // GeoTIFF: elevation[row][col] where row=Northâ†'South, col=Westâ†'East
    for (let i = 0; i < height; i++) { // row (North to South)
        for (let j = 0; j < width; j++) { // column (West to East)
            const idx = i * width + j;
            let z = elevation[i] && elevation[i][j];
            if (z === null || z === undefined) z = 0;

            positions.setZ(idx, z * params.verticalExaggeration);

            if (!isWireframe) {
                setLastColorIndex(i, j);
                const color = getColorForElevation(z);
                colors.push(color.r, color.g, color.b);
            }
        }
    }

    if (!isWireframe) {
        geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
        // PERFORMANCE FIX: Defer expensive computeVertexNormals() to after first render
        // This makes the viewer interactive immediately (no 2-3 second freeze)
        // Natural (Lambert) shading always needs normals
        setTimeout(() => {
            if (geometry && !geometry.attributes.normal) {
                const t0 = performance.now();
                geometry.computeVertexNormals();
                const t1 = performance.now();
                console.log(`[Deferred] Computed vertex normals in ${(t1 - t0).toFixed(1)}ms`);
            }
        }, 0);
    }

    let material;
    if (isWireframe) {
        // Wireframe ignores vertexColors; use a bright, unlit material for visibility
        material = new THREE.MeshBasicMaterial({
            color: 0xffffff,
            wireframe: true,
            side: THREE.DoubleSide
        });
    } else {
        // Always use Natural (Lambert) shading
        material = new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: false, wireframe: false, side: THREE.DoubleSide });
    }

    terrainMesh = new THREE.Mesh(geometry, material);
    terrainMesh.rotation.x = -Math.PI / 2;
    terrainGroup.add(terrainMesh); // Add to group instead of scene directly
    window.terrainMesh = terrainMesh; // Expose for camera controls
}

function getColorForElevation(elevation) {
    // Special case: elevation at or below sea level (0m) should look like WATER
    if (elevation <= 0.5) {
        return __tmpColor.set(0x0066cc); // Ocean blue for water
    }

    // Derived map modes
    if (params.colorScheme === 'slope' && derivedSlopeDeg) {
        const deg = deriveCurrentSlope();
        const clamped = Math.max(0, Math.min(60, isFinite(deg) ? deg : 0));
        const t = clamped / 60; // 0..1
        // Blue (low) -> green -> yellow -> red (high)
        const h = (1 - t) * 0.66; // 0.66=blue to 0=red
        return __tmpColor.setHSL(h, 1.0, 0.5);
    }
    if (params.colorScheme === 'aspect' && derivedAspectDeg) {
        const deg = deriveCurrentAspect();
        const h = ((isFinite(deg) ? deg : 0) % 360) / 360; // 0..1
        return __tmpColor.setHSL(h, 1.0, 0.5);
    }

    const useAuto = (params && params.colorScheme === 'auto-stretch');
    const stats = processedData && processedData.stats ? processedData.stats : rawElevationData.stats;
    const low = useAuto && typeof stats.autoLow === 'number' ? stats.autoLow : stats.min;
    const high = useAuto && typeof stats.autoHigh === 'number' ? stats.autoHigh : stats.max;
    const denom = Math.max(1e-9, high - low);
    let normalized = Math.max(0, Math.min(1, (elevation - low) / denom));
    // Apply contrast (gamma). >1 darkens lower values, <1 brightens
    const g = (params && typeof params.colorGamma === 'number') ? Math.max(0.1, Math.min(10, params.colorGamma)) : 1.0;
    normalized = Math.pow(normalized, g);

    const scheme = COLOR_SCHEMES[params.colorScheme] || COLOR_SCHEMES['high-contrast'];
    const isBanded = params.colorScheme === 'hypsometric-banded';

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
                // Reuse temporary color to avoid allocations
                return __tmpColor.copy(a.color).lerp(b.color, localT);
            }
        }
    }

    const baseColor = __tmpColor.copy(scheme[scheme.length - 1].color);
    return baseColor;
}

// Helpers for per-cell derived values during colorization
let __lastColorRow = 0, __lastColorCol = 0;
function setLastColorIndex(i, j) { __lastColorRow = i; __lastColorCol = j; }
function deriveCurrentSlope() { return getSlopeDegrees(__lastColorRow, __lastColorCol) ?? 0; }
function deriveCurrentAspect() { return getAspectDegrees(__lastColorRow, __lastColorCol) ?? 0; }

function updateTerrainHeight() {
    if (!terrainMesh) return;

    if (params.renderMode === 'bars') {
        if (!barsInstancedMesh) { recreateTerrain(); return; }
        // Instant update: update shader uniform to ratio of new/internal used value
        const u = barsInstancedMesh.material && barsInstancedMesh.material.userData && barsInstancedMesh.material.userData.uExaggerationUniform;
        if (u) {
            const base = (lastBarsExaggerationInternal && lastBarsExaggerationInternal > 0) ? lastBarsExaggerationInternal : params.verticalExaggeration;
            u.value = params.verticalExaggeration / base;
        }
        // Note: tile gap/bucket changes are handled by their own controls via recreateTerrain()
    } else if (params.renderMode === 'points') {
        // Instant update for points via uniform ratio (no CPU loops)
        const u = terrainMesh.material && terrainMesh.material.userData && terrainMesh.material.userData.uExaggerationUniform;
        if (u) {
            const base = (lastPointsExaggerationInternal && lastPointsExaggerationInternal > 0) ? lastPointsExaggerationInternal : params.verticalExaggeration;
            u.value = params.verticalExaggeration / base;
        }
    } else {
        const positions = terrainMesh.geometry.attributes.position;
        const { width, height, elevation } = processedData;

        // Update elevation heights for existing geometry
        for (let i = 0; i < height; i++) { // row (North to South)
            for (let j = 0; j < width; j++) { // column (West to East)
                const idx = i * width + j;
                let z = elevation[i] && elevation[i][j];
                if (z === null || z === undefined) z = 0;

                positions.setZ(idx, z * params.verticalExaggeration);
            }
        }

        positions.needsUpdate = true;
    }
}

function updateColors() {
    if (!terrainMesh || !processedData || !rawElevationData) {
        // Fallback if not ready yet
        recreateTerrain();
        return;
    }

    // Bars: update per-instance colors without rebuild
    if (params.renderMode === 'bars') {
        if (!barsInstancedMesh || !barsIndexToRow || !barsIndexToCol) { recreateTerrain(); return; }
        if (barsInstancedMesh.material && barsInstancedMesh.material.vertexColors) {
            const colorAttr = barsInstancedMesh.geometry.getAttribute('instanceColor');
            if (!colorAttr || !colorAttr.array) { recreateTerrain(); return; }

            const arr = colorAttr.array;
            const count = barsIndexToRow.length;
            for (let i = 0; i < count; i++) {
                const row = barsIndexToRow[i];
                const col = barsIndexToCol[i];
                let z = (processedData.elevation[row] && processedData.elevation[row][col]);
                if (z === null || z === undefined) z = 0;
                setLastColorIndex(row, col);
                const c = getColorForElevation(z);
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

    // Points: update color buffer in-place
    if (params.renderMode === 'points') {
        const geom = terrainMesh.geometry;
        const colorAttr = geom.getAttribute('color');
        if (!colorAttr || !colorAttr.array) { recreateTerrain(); return; }
        const width = processedData.width;
        const height = processedData.height;
        const arr = colorAttr.array;
        let k = 0;
        for (let i = 0; i < height; i++) {
            for (let j = 0; j < width; j++) {
                let z = (processedData.elevation[i] && processedData.elevation[i][j]);
                if (z === null || z === undefined) z = 0;
                setLastColorIndex(i, j);
                const c = getColorForElevation(z);
                arr[k++] = c.r;
                arr[k++] = c.g;
                arr[k++] = c.b;
            }
        }
        colorAttr.needsUpdate = true;
        return;
    }

    // Surface (and wireframe fallback): update vertex colors in-place if present
    {
        const geom = terrainMesh.geometry;
        const colorAttr = geom.getAttribute('color');
        if (!colorAttr || !colorAttr.array) { recreateTerrain(); return; }
        const width = processedData.width;
        const height = processedData.height;
        const arr = colorAttr.array;
        let k = 0;
        for (let i = 0; i < height; i++) {
            for (let j = 0; j < width; j++) {
                let z = (processedData.elevation[i] && processedData.elevation[i][j]);
                if (z === null || z === undefined) z = 0;
                const c = getColorForElevation(z);
                arr[k++] = c.r;
                arr[k++] = c.g;
                arr[k++] = c.b;
            }
        }
        colorAttr.needsUpdate = true;
        return;
    }
}

// Store original terrain position to keep it fixed when bucket size changes
let originalTerrainPosition = null;

function recreateTerrain() {
    const startTime = performance.now();

    // Log call stack to understand where recreations are coming from
    const stack = new Error().stack;
    const caller = stack.split('\n')[2]?.trim() || 'unknown';
    console.log(`[TERRAIN] recreateTerrain() called from: ${caller}`);

    // Preserve terrain position and rotation before recreating
    let oldTerrainPos = null;
    let oldTerrainGroupRotation = null;

    if (terrainMesh) {
        oldTerrainPos = terrainMesh.position.clone();
    }
    if (terrainGroup) {
        oldTerrainGroupRotation = terrainGroup.rotation.clone();
    }

    createTerrain();

    // Restore terrain position if it existed before (keeps map in same place when bucket size changes)
    if (oldTerrainPos && terrainMesh) {
        terrainMesh.position.copy(oldTerrainPos);
    } else if (terrainMesh) {
        // First time - store the original position for future recreations
        originalTerrainPosition = terrainMesh.position.clone();
    }

    // Restore terrain group rotation if it was rotated
    if (oldTerrainGroupRotation && terrainGroup) {
        terrainGroup.rotation.copy(oldTerrainGroupRotation);
    }

    const duration = performance.now() - startTime;
    console.log(`[PERF] recreateTerrain() completed in ${duration.toFixed(1)}ms`);
    return duration;
}

// Removed: updateMaterialsForShading() - always using Natural (Lambert) shading

function updateLightingForShading() {
    const ambient = window.__ambientLight;
    const d1 = window.__dirLight1;
    const d2 = window.__dirLight2;
    if (!ambient || !d1 || !d2) return;

    // Always use Natural (Lambert) - Balanced multi-directional lighting
    ambient.intensity = 0.9;
    d1.intensity = 0.4;
    d2.intensity = 0.2;
}

// Removed: Sun pad UI controls (initSunPad, drawSunPad, updateSunLightDirection) - no longer needed with Natural (Lambert) only

// ===== DERIVED GRIDS (SLOPE/ASPECT) =====
function computeDerivedGrids() {
    derivedSlopeDeg = null;
    derivedAspectDeg = null;
    if (!processedData || !processedData.elevation) return;
    const w = processedData.width;
    const h = processedData.height;
    const dx = Math.max(1e-6, processedData.bucketSizeMetersX || 1);
    const dy = Math.max(1e-6, processedData.bucketSizeMetersY || 1);
    const elev = processedData.elevation;
    const slope = new Array(h);
    const aspect = new Array(h);
    for (let i = 0; i < h; i++) {
        slope[i] = new Array(w);
        aspect[i] = new Array(w);
        for (let j = 0; j < w; j++) {
            const zc = elev[i][j] ?? 0;
            const zl = elev[i][Math.max(0, j - 1)] ?? zc;
            const zr = elev[i][Math.min(w - 1, j + 1)] ?? zc;
            const zu = elev[Math.max(0, i - 1)][j] ?? zc;
            const zd = elev[Math.min(h - 1, i + 1)][j] ?? zc;
            const dzdx = (zr - zl) / (2 * dx);
            const dzdy = (zd - zu) / (2 * dy);
            const gradMag = Math.sqrt(dzdx * dzdx + dzdy * dzdy);
            const slopeRad = Math.atan(gradMag);
            const slopeDeg = slopeRad * 180 / Math.PI;
            // Aspect: downslope direction; atan2(dzdy, dzdx) gives direction of increasing x and y.
            let asp = Math.atan2(dzdy, dzdx) * 180 / Math.PI; // -180..180
            if (asp < 0) asp += 360;
            slope[i][j] = slopeDeg;
            aspect[i][j] = asp;
        }
    }
    derivedSlopeDeg = slope;
    derivedAspectDeg = aspect;
}

function getSlopeDegrees(i, j) {
    if (!derivedSlopeDeg) return null;
    const h = derivedSlopeDeg.length;
    const w = derivedSlopeDeg[0].length;
    if (i < 0 || j < 0 || i >= h || j >= w) return null;
    return derivedSlopeDeg[i][j];
}

function getAspectDegrees(i, j) {
    if (!derivedAspectDeg) return null;
    const h = derivedAspectDeg.length;
    const w = derivedAspectDeg[0].length;
    if (i < 0 || j < 0 || i >= h || j >= w) return null;
    return derivedAspectDeg[i][j];
}

function updateStats() {
    const statsDiv = document.getElementById('stats');
    if (!statsDiv) return; // Element removed from UI

    const { width, height, stats: dataStats } = rawElevationData;
    const { width: bWidth, height: bHeight } = processedData;

    statsDiv.innerHTML = `
 <div class="stat-line">
 <span class="stat-label">Raw Data:</span>
 <span class="stat-value">${width} x ${height} pixels</span>
 </div>
 <div class="stat-line">
 <span class="stat-label">Bucket Multiplier:</span>
 <span class="stat-value">${params.bucketSize}x</span>
 </div>
 <div class="stat-line">
 <span class="stat-label">Bucketed Grid:</span>
 <span class="stat-value">${bWidth} x ${bHeight}</span>
 </div>
 <div class="stat-line">
 <span class="stat-label">Data Reduction:</span>
 <span class="stat-value">${(100 * (1 - (bWidth * bHeight) / (width * height))).toFixed(1)}%</span>
 </div>
 <div class="stat-line">
 <span class="stat-label">Elevation Range:</span>
 <span class="stat-value">${dataStats.min.toFixed(0)}m - ${dataStats.max.toFixed(0)}m</span>
 </div>
 <div class="stat-line">
 <span class="stat-label">Average Elevation:</span>
 <span class="stat-value">${dataStats.mean.toFixed(0)}m</span>
 </div>
 <div class="stat-line">
 <span class="stat-label">Bars Rendered:</span>
 <span class="stat-value">${terrainStats.bars?.toLocaleString() || 'N/A'}</span>
 </div>
 `;
}

function setView(preset) {
    if (!rawElevationData || !processedData) {
        resetCamera();
        return;
    }

    // Calculate distances based on UNIFORM GRID extents (no geographic scaling)
    const gridWidth = processedData.width;
    const gridHeight = processedData.height;

    // Use pixel-grid extents for all modes to preserve proportions established by the pipeline
    let xExtent, zExtent;
    if (params.renderMode === 'bars') {
        const bucketMultiplier = params.bucketSize;
        xExtent = (gridWidth - 1) * bucketMultiplier;
        zExtent = (gridHeight - 1) * bucketMultiplier;
    } else if (params.renderMode === 'points') {
        const bucketSize = params.bucketSize;
        xExtent = (gridWidth - 1) * bucketSize;
        zExtent = (gridHeight - 1) * bucketSize;
    } else {
        // Surface: PlaneGeometry is centered and scaled by bucketSize
        const bucketMultiplier = params.bucketSize;
        xExtent = gridWidth * bucketMultiplier;
        zExtent = gridHeight * bucketMultiplier;
    }

    const maxDim = Math.max(xExtent, zExtent);
    const distance = maxDim * 2.0; // Increased from 0.8 for better overview
    const height = maxDim * 1.2; // Increased from 0.5 for better viewing angle

    const views = {
        overhead: { x: 0, y: distance * 1.2, z: 0, target: [0, 0, 0] },
        north: { x: 0, y: height, z: distance, target: [0, 0, 0] },
        south: { x: 0, y: height, z: -distance, target: [0, 0, 0] },
        east: { x: distance, y: height, z: 0, target: [0, 0, 0] },
        west: { x: -distance, y: height, z: 0, target: [0, 0, 0] },
        isometric: { x: distance * 0.8, y: distance * 0.8, z: distance * 0.8, target: [0, maxDim * 0.01, 0] }
    };

    const view = views[preset];
    if (view) {
        camera.position.set(view.x, view.y, view.z);
        controls.target.set(...view.target);
        controls.update();
    }
}

// Track active vertical exaggeration button
let activeVertExagButton = null;

function setVertExag(value) {
    params.verticalExaggeration = value;

    // Convert to multiplier for display
    const multiplier = internalToMultiplier(value);
    document.getElementById('vertExag').value = multiplier;
    document.getElementById('vertExagInput').value = multiplier;
    // Persist to URL as user-facing multiplier
    try { updateURLParameter('exag', multiplier); } catch (_) { }

    // Update button active state
    updateVertExagButtons(value);

    // Update terrain (buttery smooth, no loading UI)
    updateTerrainHeight();
}

function setTrueScale() {
    if (trueScaleValue === null) {
        console.warn('[WARN] No data loaded, cannot set true scale');
        return;
    }

    console.log(`Setting TRUE SCALE (1:1 Earth proportions):`);
    console.log(` True scale exaggeration: ${trueScaleValue.toFixed(6)}x`);
    console.log(` Terrain slopes now have real-world steepness`);

    // Clamp to valid range
    const clampedValue = Math.max(0.00001, Math.min(0.3, trueScaleValue));
    if (clampedValue !== trueScaleValue) {
        console.warn(`[WARN] True scale ${trueScaleValue.toFixed(6)}x clamped to ${clampedValue.toFixed(6)}x (outside valid range)`);
    }

    setVertExag(clampedValue);
    // Note: setVertExag() already updates the URL
}

function setVertExagMultiplier(multiplier) {
    if (trueScaleValue === null) {
        console.warn('[WARN] True scale not calculated yet, using fallback');
        // Fallback: calculate on the fly
        if (rawElevationData) {
            const scale = calculateRealWorldScale();
            trueScaleValue = 1.0 / scale.metersPerPixelX;
        } else {
            return;
        }
    }

    const value = trueScaleValue * multiplier;
    console.log(`Setting ${multiplier}x exaggeration (${value.toFixed(6)}x)`);
    setVertExag(value);
    // Note: setVertExag() already updates the URL
}

function updateVertExagButtons(activeValue) {
    // Remove active class from all buttons
    const buttons = document.querySelectorAll('[id^="vertExagBtn"]');
    buttons.forEach(btn => {
        btn.classList.remove('active');
        btn.style.outline = '';
    });

    // Find and highlight the button matching the current value
    activeValue = parseFloat(activeValue);

    // Special handling for true scale button
    const trueScaleBtn = document.getElementById('vertExagBtnTrue');
    if (trueScaleBtn && trueScaleValue !== null) {
        const tolerance = 0.000001;
        if (Math.abs(activeValue - trueScaleValue) < tolerance) {
            trueScaleBtn.classList.add('active');
            trueScaleBtn.style.outline = '2px solid#ffaa00';
            activeVertExagButton = trueScaleBtn;
        }
    }

    // Check multiplier buttons
    buttons.forEach(btn => {
        const multiplier = btn.dataset.multiplier;
        if (multiplier && trueScaleValue !== null) {
            const btnValue = trueScaleValue * parseFloat(multiplier);
            const tolerance = Math.max(0.0001, btnValue * 0.01); // 1% tolerance
            if (Math.abs(activeValue - btnValue) < tolerance) {
                btn.classList.add('active');
                btn.style.outline = '2px solid#ffaa00';
                activeVertExagButton = btn;
            }
        }
    });
}

// Overhead view - looks directly down at terrain center
function triggerOverheadView() {
    const fixedHeight = 1320;
    const tiltDeg = 0; // Look straight down
    const zOffset = fixedHeight * Math.tan(THREE.MathUtils.degToRad(tiltDeg)); // = 0

    camera.position.set(0, fixedHeight, zOffset);

    if (activeScheme && activeScheme.focusPoint) {
        activeScheme.focusPoint.set(0, 0, 0);
        activeScheme.controls.target.copy(activeScheme.focusPoint);
    } else {
        controls.target.set(0, 0, 0);
    }

    camera.up.set(0, 1, 0);
    camera.lookAt(0, 0, 0);
}

// Trigger reframe view on active camera scheme (same as F key)
function triggerReframeView() {
    if (activeScheme && typeof activeScheme.reframeView === 'function') {
        activeScheme.reframeView();
    } else {
        // Fallback to legacy reset if scheme doesn't have reframeView
        resetCamera();
    }
}

function resetCamera() {
    // Fixed camera position: directly above center, looking straight down
    // This gives a consistent map view every time

    // Standard fixed height
    const fixedHeight = 2200;

    // Position: directly above origin at (0, 0)
    // Small Z offset toward north (+Z) - rotated 180 degrees
    camera.position.set(0, fixedHeight, fixedHeight * 0.001);

    // Look at center of terrain
    controls.target.set(0, 0, 0);

    // Standard up vector for normal camera controls
    camera.up.set(0, 1, 0);

    // Reset camera quaternion to identity (clear any rotation state)
    camera.quaternion.set(0, 0, 0, 1);

    // Apply lookAt AFTER quaternion reset
    camera.lookAt(0, 0, 0);

    // Reset terrain group rotation (the map itself can be rotated)
    if (window.terrainGroup) {
        window.terrainGroup.rotation.set(0, 0, 0);
        console.log('Terrain rotation reset to (0, 0, 0)');
    }

    // Sync OrbitControls with new camera state
    controls.update();

    console.log(`Camera fully reset: position (0, ${fixedHeight}, ${(fixedHeight * 0.001).toFixed(1)}) looking at origin, terrain rotation and all state cleared`);
}

function exportImage() {
    // Temporarily enable preserveDrawingBuffer for screenshot
    const prevPDB = renderer.getContext().getContextAttributes && renderer.getContext().getContextAttributes().preserveDrawingBuffer;
    // Some drivers may not allow toggling at runtime; we emulate by rendering once then reading
    renderer.render(scene, camera);
    const dataURL = renderer.domElement.toDataURL('image/png');
    const link = document.createElement('a');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    link.download = `terrain_bucket${params.bucketSize}_${params.aggregation}_${timestamp}.png`;
    link.href = dataURL;
    link.click();
}

function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    // Compass size stays fixed
}

// ===== CAMERA SCHEME SYSTEM =====
let activeScheme = null;

// Keyboard state tracking (used by some schemes)
const keyboard = {
    w: false, a: false, s: false, d: false,
    q: false, e: false,
    shift: false, ctrl: false, alt: false
};

function switchCameraScheme(schemeName) {
    console.log(`Switching to ${schemeName} camera scheme`);

    // Deactivate old scheme
    if (activeScheme) {
        activeScheme.deactivate();
    }

    // Activate new scheme
    activeScheme = window.CameraSchemes[schemeName];
    if (activeScheme && camera && controls && renderer) {
        activeScheme.activate(camera, controls, renderer);

        // Update UI
        const desc = document.getElementById('schemeDescription');
        if (desc) {
            desc.textContent = activeScheme.description;
        }
    }
}

// Navigate between regions using arrow keys or buttons
function navigateRegions(direction) {
    if (!regionOptions || regionOptions.length === 0 || !currentRegionId) {
        return;
    }

    // Get all non-divider regions
    const validOptions = regionOptions.filter(opt => opt.id !== '__divider__');
    if (validOptions.length === 0) return;

    // Find current region index
    const currentIndex = validOptions.findIndex(opt => opt.id === currentRegionId);
    if (currentIndex === -1) {
        // Current region not found, load first region
        loadRegion(validOptions[0].id);
        return;
    }

    // Calculate next index with wrapping
    let nextIndex = currentIndex + direction;
    if (nextIndex < 0) {
        nextIndex = validOptions.length - 1; // Wrap to end
    } else if (nextIndex >= validOptions.length) {
        nextIndex = 0; // Wrap to beginning
    }

    const nextRegion = validOptions[nextIndex];
    if (nextRegion && nextRegion.id) {
        const directionText = direction > 0 ? 'next' : 'previous';
        console.log(`Navigation: ${directionText} region → ${nextRegion.name}`);
        appendActivityLog(`Navigation: ${nextRegion.name}`);
        loadRegion(nextRegion.id);
    }
}

// Get the name of the region that would be navigated to
function getNavigationTarget(direction) {
    if (!regionOptions || regionOptions.length === 0 || !currentRegionId) {
        return null;
    }

    const validOptions = regionOptions.filter(opt => opt.id !== '__divider__');
    if (validOptions.length === 0) return null;

    const currentIndex = validOptions.findIndex(opt => opt.id === currentRegionId);
    if (currentIndex === -1) return validOptions[0]?.name || null;

    let nextIndex = currentIndex + direction;
    if (nextIndex < 0) {
        nextIndex = validOptions.length - 1;
    } else if (nextIndex >= validOptions.length) {
        nextIndex = 0;
    }

    return validOptions[nextIndex]?.name || null;
}

// Update the region navigation hints
function updateRegionNavHints() {
    const prevHint = document.getElementById('region-prev-hint');
    const nextHint = document.getElementById('region-next-hint');
    const currentDisplay = document.getElementById('region-nav-current');

    if (currentDisplay && currentRegionId) {
        const currentName = regionIdToName[currentRegionId] || currentRegionId;
        currentDisplay.textContent = currentName;
    }

    if (prevHint) {
        const prevName = getNavigationTarget(-1);
        prevHint.textContent = prevName || '';
        prevHint.title = prevName ? `Previous: ${prevName}` : '';
    }

    if (nextHint) {
        const nextName = getNavigationTarget(1);
        nextHint.textContent = nextName || '';
        nextHint.title = nextName ? `Next: ${nextName}` : '';
    }

    // Update visible recent regions list
    updateRecentRegionsList();
}

// Update the visible recent regions list in the UI
function updateRecentRegionsList() {
    const container = document.getElementById('recent-regions-container');
    const listEl = document.getElementById('recent-regions-list');

    if (!listEl) return;

    const validRecent = getValidRecentRegions();

    // Hide container if no recent regions
    if (validRecent.length === 0) {
        if (container) container.style.display = 'none';
        return;
    }

    // Show container and populate list
    if (container) container.style.display = 'block';

    listEl.innerHTML = '';
    validRecent.forEach((regionId) => {
        // Skip the current region - no need to show it in recent list
        if (regionId === currentRegionId) return;

        const regionInfo = regionsManifest?.regions[regionId];
        if (!regionInfo) return;

        const button = document.createElement('button');
        button.textContent = regionInfo.name;
        button.className = 'recent-region-btn';
        button.style.cssText = `
            display: inline-block;
            padding: 2px 6px;
            margin-right: 3px;
            margin-bottom: 3px;
            background: #1a2a3a;
            border: 1px solid #4477aa;
            border-radius: 2px;
            color: #ffffff;
            font-size: 11px;
            font-weight: normal;
            cursor: pointer;
            white-space: nowrap;
        `;

        button.addEventListener('mouseenter', () => {
            button.style.background = '#2a4a6a';
            button.style.borderColor = '#6699cc';
        });

        button.addEventListener('mouseleave', () => {
            button.style.background = '#1a2a3a';
            button.style.borderColor = '#4477aa';
        });

        button.addEventListener('click', () => {
            loadRegion(regionId);
        });

        listEl.appendChild(button);
    });
}

function onKeyDown(event) {
    // Don't process keyboard shortcuts if user is typing in an input field
    const activeElement = document.activeElement;
    const isTyping = activeElement && (
        activeElement.tagName === 'INPUT' ||
        activeElement.tagName === 'TEXTAREA' ||
        activeElement.tagName === 'SELECT' ||
        activeElement.isContentEditable ||
        activeElement.classList.contains('select2-search__field') // Select2 search box
    );

    if (isTyping) {
        return; // User is typing, don't process shortcuts
    }

    const key = event.key.toLowerCase();

    // Movement keys (tracked but not used since camera scheme handles movement)
    if (key === 'w') keyboard.w = true;
    if (key === 'a') keyboard.a = true;
    if (key === 's') keyboard.s = true;
    if (key === 'd') keyboard.d = true;
    if (key === 'q') keyboard.q = true;
    if (key === 'e') keyboard.e = true;

    // Modifier keys
    if (event.shiftKey) keyboard.shift = true;
    if (event.ctrlKey) keyboard.ctrl = true;
    if (event.altKey) keyboard.alt = true;

    // Hotkeys (only handle keys NOT handled by camera scheme)
    // R key: Reset camera (fallback if camera scheme doesn't handle it)
    if (event.key === 'r' || event.key === 'R') {
        resetCamera();
    }
    // F key: Handled by camera scheme (reframeView), don't duplicate here

    // Arrow keys: Disabled for now
    // if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    //     event.preventDefault(); // Prevent page scrolling
    //     navigateRegions(event.key === 'ArrowDown' ? 1 : -1);
    // }
}

function onKeyUp(event) {
    const key = event.key.toLowerCase();

    // Release movement keys
    if (key === 'w') keyboard.w = false;
    if (key === 'a') keyboard.a = false;
    if (key === 's') keyboard.s = false;
    if (key === 'd') keyboard.d = false;
    if (key === 'q') keyboard.q = false;
    if (key === 'e') keyboard.e = false;

    // Release modifier keys
    if (!event.shiftKey) keyboard.shift = false;
    if (!event.ctrlKey) keyboard.ctrl = false;
    if (!event.altKey) keyboard.alt = false;
}


function handleKeyboardMovement() {
    if (!camera || !controls) return;

    // Check if any key is pressed
    const isMoving = keyboard.w || keyboard.s || keyboard.a || keyboard.d || keyboard.q || keyboard.e;
    if (!isMoving) return;

    // Speed adjustments with modifiers
    const baseSpeed = 1.5;
    const rotateSpeed = 0.02; // Radians per frame for rotation
    let moveSpeed = baseSpeed;

    if (keyboard.shift) {
        moveSpeed *= 2.5; // Shift = faster
    }
    if (keyboard.ctrl) {
        moveSpeed *= 0.3; // Ctrl = slower/precise
    }
    if (keyboard.alt) {
        moveSpeed *= 4.0; // Alt = very fast
    }

    // Get camera direction vectors
    const forward = new THREE.Vector3();
    const right = new THREE.Vector3();
    camera.getWorldDirection(forward);
    forward.normalize();
    right.crossVectors(forward, camera.up).normalize();

    // Movement delta
    const delta = new THREE.Vector3();

    // W/S: Move camera FORWARD/BACKWARD (in view direction)
    if (keyboard.w) {
        delta.addScaledVector(forward, moveSpeed);
    }
    if (keyboard.s) {
        delta.addScaledVector(forward, -moveSpeed);
    }

    // Q/E: Move camera DOWN/UP (vertical relative to camera view)
    if (keyboard.q) {
        delta.addScaledVector(camera.up, -moveSpeed);
    }
    if (keyboard.e) {
        delta.addScaledVector(camera.up, moveSpeed);
    }

    // A/D: Strafe camera LEFT/RIGHT (relative to view direction)
    if (keyboard.a) {
        delta.addScaledVector(right, -moveSpeed);
    }
    if (keyboard.d) {
        delta.addScaledVector(right, moveSpeed);
    }

    // Apply positional movement
    camera.position.add(delta);
    controls.target.add(delta);

    // No rotation via A/D with new scheme
    camera.lookAt(controls.target);
}

// Check if camera is currently being moved by user
function isCameraMoving() {
    // Check keyboard movement
    const isMovingKeyboard = keyboard.w || keyboard.s || keyboard.a || keyboard.d || keyboard.q || keyboard.e;

    // Check mouse/touch movement (pan, rotate, tilt, orbit)
    const isMovingMouse = activeScheme && (
        activeScheme.state.panning ||
        activeScheme.state.rotating ||
        activeScheme.state.tilting ||
        activeScheme.state.orbiting ||
        activeScheme.state.pinching ||
        activeScheme.state.rotatingCamera ||
        activeScheme.state.rotatingTerrain
    );

    return isMovingKeyboard || isMovingMouse;
}

function updateFPS() {
    frameCount++;
    const currentTime = performance.now();
    if (currentTime >= lastFpsUpdateTime + 1000) {
        const fps = Math.round((frameCount * 1000) / (currentTime - lastFpsUpdateTime));
        const fpsEl = document.getElementById('fps-display');
        if (fpsEl) fpsEl.textContent = `FPS: ${fps}`;

        // Auto-reduce resolution if FPS is too low
        if (fps < 10 && fps > 0) {
            autoReduceResolution();
        }

        frameCount = 0;
        lastFpsUpdateTime = currentTime;
    }
}

// Automatically reduce resolution when FPS is too low
function autoReduceResolution() {
    // Don't reduce if: currently loading, camera not moving, too soon since last adjustment
    if (isCurrentlyLoading || !isCameraMoving()) {
        return;
    }

    const now = performance.now();
    const MIN_ADJUSTMENT_INTERVAL = 3000; // 3 seconds between auto-adjustments
    if (now - lastAutoResolutionAdjustTime < MIN_ADJUSTMENT_INTERVAL) {
        return;
    }

    // Increase bucket size to reduce resolution (makes rendering faster)
    const currentBucketSize = params.bucketSize;
    const newBucketSize = Math.min(500, Math.floor(currentBucketSize * 1.5));

    // Only adjust if we actually changed the bucket size
    if (newBucketSize > currentBucketSize) {
        lastAutoResolutionAdjustTime = now;
        appendActivityLog(`Low FPS detected - auto-reducing resolution: ${currentBucketSize}x -> ${newBucketSize}x`);
        adjustBucketSize(newBucketSize - currentBucketSize);
    }
}

// ===== RAYCASTING-BASED CAMERA CONTROLS =====
// This provides true "point-stays-under-cursor" dragging behavior

// Initialize ground plane for raycasting fallback (when cursor misses terrain)
// Simple horizontal plane at y=0 - provides consistent reference for dragging
if (!groundPlane) groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);

function raycastToWorld(screenX, screenY) {
    return window.GeometryUtils.raycastToWorld(screenX, screenY);
}
function worldToLonLat(worldX, worldZ) {
    return window.GeometryUtils.worldToLonLat(worldX, worldZ);
}

function worldToGridIndex(worldX, worldZ) {
    return window.GeometryUtils.worldToGridIndex(worldX, worldZ);
}

function updateCursorHUD(clientX, clientY) {
    const elevEl = document.getElementById('hud-elev');
    const slopeEl = document.getElementById('hud-slope');
    const aspectEl = document.getElementById('hud-aspect');
    if (!elevEl || !processedData) return;
    const world = raycastToWorld(clientX, clientY);
    if (!world) {
        elevEl.textContent = '--';
        if (slopeEl) slopeEl.textContent = '--';
        if (aspectEl) aspectEl.textContent = '--';
        return;
    }
    // Ignore when cursor is outside data footprint
    if (!isWorldInsideData(world.x, world.z)) {
        elevEl.textContent = '--';
        if (slopeEl) slopeEl.textContent = '--';
        if (aspectEl) aspectEl.textContent = '--';
        return;
    }

    const idx = worldToGridIndex(world.x, world.z);
    if (!idx) return;
    const zCell = (processedData.elevation[idx.i] && processedData.elevation[idx.i][idx.j]);
    const hasData = (zCell != null) && isFinite(zCell);
    if (!hasData) {
        elevEl.textContent = '--';
        if (slopeEl) slopeEl.textContent = '--';
        if (aspectEl) aspectEl.textContent = '--';
        return;
    }
    const zMeters = zCell;
    const s = getSlopeDegrees(idx.i, idx.j);
    const a = getAspectDegrees(idx.i, idx.j);
    const units = (hudSettings && hudSettings.units) || 'metric';
    const elevText = formatElevation(zMeters, units);
    elevEl.textContent = elevText;
    if (slopeEl) slopeEl.textContent = (s != null && isFinite(s)) ? `${s.toFixed(1)}deg` : '--';
    if (aspectEl) aspectEl.textContent = (a != null && isFinite(a)) ? `${Math.round(a)}deg` : '--';
}

function loadHudSettings() {
    try {
        const raw = localStorage.getItem('hudSettings');
        const parsed = raw ? JSON.parse(raw) : null;
        hudSettings = parsed || {
            units: 'metric', // 'metric'|'imperial'|'both'
            show: { elevation: true, slope: true, aspect: true, distance: false }
        };
    } catch (_) {
        hudSettings = { units: 'metric', show: { elevation: true, slope: true, aspect: true, distance: false } };
    }
}

function saveHudSettings() {
    try { localStorage.setItem('hudSettings', JSON.stringify(hudSettings)); } catch (_) { }
}

function applyHudSettingsToUI() {
    if (!hudSettings) return;
    const u = hudSettings.units;
    const unitsRadios = document.querySelectorAll('input[name="hud-units"]');
    unitsRadios.forEach(r => { r.checked = (r.value === u); });
    const rowElev = document.getElementById('hud-row-elev');
    const rowSlope = document.getElementById('hud-row-slope');
    const rowAspect = document.getElementById('hud-row-aspect');
    const rowRelief = document.getElementById('hud-row-relief');
    if (rowElev) rowElev.style.display = hudSettings.show.elevation ? '' : 'none';
    if (rowSlope) rowSlope.style.display = hudSettings.show.slope ? '' : 'none';
    if (rowAspect) rowAspect.style.display = hudSettings.show.aspect ? '' : 'none';
    if (rowRelief) rowRelief.style.display = hudSettings.show.relief ? '' : 'none';
    const chkElev = document.getElementById('hud-show-elev');
    const chkSlope = document.getElementById('hud-show-slope');
    const chkAspect = document.getElementById('hud-show-aspect');
    const chkRelief = document.getElementById('hud-show-relief');
    if (chkElev) chkElev.checked = !!hudSettings.show.elevation;
    if (chkSlope) chkSlope.checked = !!hudSettings.show.slope;
    if (chkAspect) chkAspect.checked = !!hudSettings.show.aspect;
    if (chkRelief) chkRelief.checked = !!hudSettings.show.relief;
}

function bindHudSettingsHandlers() {
    // Units
    document.querySelectorAll('input[name="hud-units"]').forEach(r => {
        r.addEventListener('change', (e) => {
            if (e.target.checked) {
                hudSettings.units = e.target.value;
                saveHudSettings();
                // Refresh current HUD display
                if (typeof currentMouseX === 'number' && typeof currentMouseY === 'number') {
                    updateCursorHUD(currentMouseX, currentMouseY);
                }
            }
        });
    });
    // Visibility
    const vis = [
        { id: 'hud-show-elev', key: 'elevation' },
        { id: 'hud-show-slope', key: 'slope' },
        { id: 'hud-show-aspect', key: 'aspect' },
        { id: 'hud-show-relief', key: 'relief' }
    ];
    vis.forEach(({ id, key }) => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', () => {
                hudSettings.show[key] = !!el.checked;
                saveHudSettings();
                applyHudSettingsToUI();
            });
        }
    });
}

function formatElevation(meters, units) {
    return window.FormatUtils.formatElevation(meters, units);
}

function formatDistance(meters, units) {
    return window.FormatUtils.formatDistance(meters, units);
}

function formatFootprint(metersX, metersY, units) {
    return window.FormatUtils.formatFootprint(metersX, metersY, units);
}

function formatPixelSize(meters) {
    return window.FormatUtils.formatPixelSize(meters);
}

function updateResolutionInfo() {
    const infoEl = document.getElementById('resolution-info');
    if (!infoEl || !processedData) return;

    const metersX = processedData.bucketSizeMetersX || 0;
    const metersY = processedData.bucketSizeMetersY || 0;
    const totalRectangles = processedData.width * processedData.height;

    // Format as compact "123.4m" or "1.2km", with one decimal point
    const formattedX = formatPixelSize(metersX);
    const formattedY = formatPixelSize(metersY);
    const footprintText = (metersX === metersY) ? formattedX : `${formattedX}×${formattedY}`;

    // Round total rectangles to nearest thousand
    const roundedTotal = Math.round(totalRectangles / 1000);

    infoEl.textContent = `${footprintText}, ${roundedTotal}k`;
}

function getMetersScalePerWorldUnit() {
    return window.GeometryUtils.getMetersScalePerWorldUnit();
}

function computeDistanceToDataEdgeMeters(worldX, worldZ) {
    if (!processedData) return null;
    const w = processedData.width;
    const h = processedData.height;
    let xMin, xMax, zMin, zMax;
    if (params.renderMode === 'bars') {
        const bucket = params.bucketSize;
        xMin = -(w - 1) * bucket / 2; xMax = (w - 1) * bucket / 2;
        zMin = -(h - 1) * bucket / 2; zMax = (h - 1) * bucket / 2;
    } else if (params.renderMode === 'points') {
        xMin = -(w - 1) / 2; xMax = (w - 1) / 2;
        zMin = -(h - 1) / 2; zMax = (h - 1) / 2;
    } else {
        xMin = -w / 2; xMax = w / 2;
        zMin = -h / 2; zMax = h / 2;
    }
    const { mx, mz } = getMetersScalePerWorldUnit();
    const x = worldX, z = worldZ;
    const insideX = (x >= xMin && x <= xMax);
    const insideZ = (z >= zMin && z <= zMax);
    if (insideX && insideZ) {
        const dxLeft = (x - xMin) * mx;
        const dxRight = (xMax - x) * mx;
        const dzBottom = (z - zMin) * mz;
        const dzTop = (zMax - z) * mz;
        return Math.min(dxLeft, dxRight, dzBottom, dzTop);
    }
    // Outside rectangle: distance to closest point on rect
    const clampedX = Math.max(xMin, Math.min(xMax, x));
    const clampedZ = Math.max(zMin, Math.min(zMax, z));
    const dx = (x - clampedX) * mx;
    const dz = (z - clampedZ) * mz;
    return Math.hypot(dx, dz);
}

function distancePointToSegment2D(px, pz, ax, az, bx, bz) {
    return window.GeometryUtils.distancePointToSegment2D(px, pz, ax, az, bx, bz);
}

function isWorldInsideData(worldX, worldZ) {
    return window.GeometryUtils.isWorldInsideData(worldX, worldZ);
}

function onMouseDown(event) {
    event.preventDefault();

    // Left button = Pan
    if (event.button === 0 && !event.ctrlKey) {
        isPanning = true;
        panStartMouse.set(event.clientX, event.clientY);

        // Raycast to find world point under cursor
        panStartWorldPoint = raycastToWorld(event.clientX, event.clientY);

        if (panStartWorldPoint) {
            panStartCameraPos = camera.position.clone();
            panStartTargetPos = controls.target.clone();
            console.log('Pan started');
        } else {
            console.warn('Failed to raycast world point');
            isPanning = false;
        }
    }
    // Right button or Ctrl+Left = Rotate
    else if (event.button === 2 || (event.button === 0 && event.ctrlKey)) {
        isRotating = true;
        rotateStart.set(event.clientX, event.clientY);
        rotateStartCameraPos = camera.position.clone();
        rotateStartTargetPos = controls.target.clone();
        console.log('Rotation started');
    }
}

function onMouseMove(event) {
    // Always track mouse position for zoom-to-cursor
    currentMouseX = event.clientX;
    currentMouseY = event.clientY;

    // Handle panning
    if (isPanning && panStartWorldPoint) {
        event.preventDefault();

        const currentWorldPoint = raycastToWorld(event.clientX, event.clientY);

        if (currentWorldPoint) {
            // Calculate offset: how much did the world point move?
            const worldDelta = new THREE.Vector3();
            worldDelta.subVectors(panStartWorldPoint, currentWorldPoint);

            // Apply offset to camera and target to keep picked point under cursor
            // DON'T call lookAt - just translate position and target together
            camera.position.copy(panStartCameraPos).add(worldDelta);
            controls.target.copy(panStartTargetPos).add(worldDelta);
        }
    }

    // Handle rotation
    if (isRotating) {
        event.preventDefault();

        const deltaX = event.clientX - rotateStart.x;
        const deltaY = event.clientY - rotateStart.y;

        const rotateSpeed = 0.005;

        // Get vector from target to camera
        const offset = new THREE.Vector3();
        offset.copy(rotateStartCameraPos).sub(rotateStartTargetPos);

        // Rotate horizontally (around Y axis)
        const theta = -deltaX * rotateSpeed;
        const sinTheta = Math.sin(theta);
        const cosTheta = Math.cos(theta);
        const x = offset.x * cosTheta - offset.z * sinTheta;
        const z = offset.x * sinTheta + offset.z * cosTheta;
        offset.x = x;
        offset.z = z;

        // Rotate vertically (around horizontal axis)
        const phi = -deltaY * rotateSpeed;
        const radius = Math.sqrt(offset.x * offset.x + offset.z * offset.z);
        const currentPhi = Math.atan2(offset.y, radius);
        const newPhi = Math.max(-Math.PI / 2 + 0.1, Math.min(Math.PI / 2 - 0.1, currentPhi + phi));
        offset.y = Math.sin(newPhi) * Math.sqrt(offset.x * offset.x + offset.y * offset.y + offset.z * offset.z);

        const horizontalRadius = Math.cos(newPhi) * Math.sqrt(offset.x * offset.x + offset.y * offset.y + offset.z * offset.z);
        const angle = Math.atan2(offset.z, offset.x);
        offset.x = horizontalRadius * Math.cos(angle);
        offset.z = horizontalRadius * Math.sin(angle);

        // Update camera position
        camera.position.copy(rotateStartTargetPos).add(offset);
        camera.lookAt(controls.target);
    }
    // Update HUD values at cursor
    updateCursorHUD(event.clientX, event.clientY);
}

function onMouseUp(event) {
    if (isPanning) {
        console.log('Pan ended');
        isPanning = false;
        panStartWorldPoint = null;
        panStartCameraPos = null;
        panStartTargetPos = null;
    }

    if (isRotating) {
        console.log('Rotation ended');
        isRotating = false;
        rotateStartCameraPos = null;
        rotateStartTargetPos = null;
    }
}

function animate() {
    requestAnimationFrame(animate);

    // Update active camera scheme
    if (activeScheme && activeScheme.enabled) {
        activeScheme.update();
    }

    controls.update();
    renderer.render(scene, camera);
    updateFPS();
    if (typeof currentMouseX === 'number' && typeof currentMouseY === 'number') {
        updateCursorHUD(currentMouseX, currentMouseY);
    }
}

// Toggle controls help window
function toggleControlsHelp() {
    const window = document.getElementById('controls-help-window');
    const button = document.getElementById('controls-help-toggle');

    if (window.classList.contains('open')) {
        window.classList.remove('open');
        button.textContent = 'Close';
    } else {
        window.classList.add('open');
        button.textContent = 'Close';
    }
}

// Update URL parameter without reloading page (for shareable links)
function updateURLParameter(key, value) {
    const url = new URL(window.location);
    const currentValue = url.searchParams.get(key);
    const newValue = String(value);

    // Skip update if value hasn't changed
    if (currentValue === newValue) {
        return;
    }

    url.searchParams.set(key, newValue);
    window.history.pushState({}, '', url);
    console.log(`URL updated: ${url.href}`);
}

// Copy current view URL to clipboard
function copyShareLink() {
    const url = window.location.href;
    navigator.clipboard.writeText(url).then(() => {
        // Show temporary success message
        const btn = document.getElementById('copyLinkBtn');
        const originalText = btn.textContent;
        btn.textContent = ' Copied!';
        btn.style.background = '#4CAF50';
        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.background = '';
        }, 2000);
        console.log(`Copied to clipboard: ${url}`);
    }).catch(err => {
        console.error('Failed to copy URL:', err);
        alert(`Copy this URL to share:\n${url}`);
    });
}


// Start when page loads
window.addEventListener('load', init);

