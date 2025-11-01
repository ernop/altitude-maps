// Version tracking
const VIEWER_VERSION = '1.339';

// All console logs use plain ASCII - no sanitizer needed

// Global variables
let scene, camera, renderer, controls;
let terrainMesh, gridHelper;
let rawElevationData; // Original full-resolution data
let processedData; // Bucketed/aggregated data
let derivedSlopeDeg = null; // 2D array of slope (degrees)
let derivedAspectDeg = null; // 2D array of aspect (0-360 degrees)
let raycaster; // Three.js raycaster for HUD and camera interactions
let groundPlane; // Ground plane at y=0 used for consistent ray intersections
let currentMouseX, currentMouseY; // Tracked mouse position for HUD updates
let hudSettings = null; // HUD configuration (units/visibility)
let borderSegmentsMeters = []; // Flattened list of border line segments in meters space
let borderSegmentsGeo = []; // [{axLon, axLat, bxLon, bxLat}]
let borderGeoIndex = null; // Map of cellKey -> array of segment indices
let borderGeoCellSizeDeg = 0.25; // spatial hash cell size in degrees

// Temporary color reused to avoid per-vertex allocations
const __tmpColor = new THREE.Color();
let stats = {};
let borderMeshes = [];
let borderData = null;
let frameCount = 0;
let lastTime = performance.now();
let isCurrentlyLoading = false; // Track if region is being loaded/reloaded

// Directional edge markers (N, E, S, W)
// PRODUCT REQUIREMENT: These markers must NOT move when user adjusts vertical exaggeration slider
// Implementation: Create once at current exaggeration, don't recreate on exaggeration changes
let edgeMarkers = [];

// True scale value for current data (calculated after data loads)
let trueScaleValue = null;


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

// Simple debounce utility for coalescing rapid UI events
function debounce(func, wait) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), wait);
    };
}

// UI activity log utilities
function appendActivityLog(message) {
    const logEls = document.querySelectorAll('#activityLog');
    if (!logEls || logEls.length === 0) return;
    const time = new Date().toLocaleTimeString();
    const text = `[${time}] ${message}`;
    logEls.forEach((logEl) => {
        const row = document.createElement('div');
        row.textContent = text;
        logEl.appendChild(row);
        // Natural auto-scroll to bottom
        logEl.scrollTop = logEl.scrollHeight;
    });
}

// Significant event helper (policy: add genuinely meaningful events)
window.logSignificant = function (message) {
    try { appendActivityLog(`[IMPORTANT] ${message}`); } catch (_) { }
};

// Copy all log text from all activityLog containers to clipboard
window.copyActivityLogs = async function () {
    try {
        const logEls = Array.from(document.querySelectorAll('#activityLog'));
        const texts = logEls.map(el => el.innerText.trim()).filter(Boolean);
        const combined = texts.join('\n');
        await navigator.clipboard.writeText(combined);
        appendActivityLog('Logs copied to clipboard.');
    } catch (e) {
        appendActivityLog(`Failed to copy logs: ${e && e.message ? e.message : e}`);
    }
};

function logResourceTiming(resourceUrl, label, startTimeMs, endTimeMs) {
    let entry = null;
    try {
        const entries = performance.getEntriesByName(resourceUrl);
        if (entries && entries.length) {
            entry = entries[entries.length - 1];
        }
    } catch (e) {
        // Ignore
    }
    const encodedKb = entry && typeof entry.encodedBodySize === 'number' ? (entry.encodedBodySize / 1024) : null;
    const decodedKb = entry && typeof entry.decodedBodySize === 'number' ? (entry.decodedBodySize / 1024) : null;
    const transferKb = entry && typeof entry.transferSize === 'number' ? (entry.transferSize / 1024) : null;
    const compressed = (encodedKb !== null && decodedKb !== null) ? (decodedKb > encodedKb) : null;
    const parts = [];
    if (decodedKb !== null) parts.push(`${decodedKb.toFixed(1)} KB decoded`);
    if (encodedKb !== null) parts.push(`${encodedKb.toFixed(1)} KB encoded`);
    if (transferKb !== null) parts.push(`${transferKb.toFixed(1)} KB transfer`);
    if (compressed !== null) parts.push(compressed ? 'compressed' : 'uncompressed');
    const duration = Math.max(0, Math.round((endTimeMs ?? performance.now()) - (startTimeMs ?? performance.now())));
    parts.push(`${duration} ms`);
    appendActivityLog(`${label}: ${resourceUrl} | ${parts.join(' | ')}`);
}

// Bars/Points fast-update state
let barsInstancedMesh = null;
let barsIndexToRow = null; // Int32Array mapping: instanceIndex -> row
let barsIndexToCol = null; // Int32Array mapping: instanceIndex -> col
let barsTileSize = 0;
const barsDummy = new THREE.Object3D();
let pendingVertExagRaf = null; // Coalesce rapid exaggeration updates to the latest frame
let lastBarsExaggerationInternal = null; // Internal value used when bars were last (re)built
let lastPointsExaggerationInternal = null; // Internal value used when points were last (re)built
let lastBarsTileSize = 1.0; // Tile size used when bars were last (re)built
let pendingTileGapRaf = null; // Coalesce tile gap updates to latest frame
let pendingBucketTimeout = null; // Debounce for bucket size rebuilds
let lastAutoResolutionAdjustTime = 0; // Track last auto-resolution adjustment to debounce

// Parameters
let params = {
    bucketSize: 4, // Integer multiplier of pixel spacing (1x, 2x, 3x, etc.)
    tileGap: 0, // Gap between tiles as percentage (0-99%)
    aggregation: 'max',
    renderMode: 'bars',
    verticalExaggeration: 0.03, // Default: good balance of detail and scale
    colorScheme: 'terrain',
    showGrid: false,
    showBorders: false,
    autoRotate: false,
    flatLightingEnabled: false,
    hillshadeEnabled: false,
    sunAzimuthDeg: 315,
    sunAltitudeDeg: 45,
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

    // Resolution (bucket size)
    const bs = getInt('bucketSize', 1, 500);
    if (bs !== null) params.bucketSize = bs;

    // Tile gap percentage
    const tg = getInt('tileGap', 0, 99);
    if (tg !== null) params.tileGap = tg;

    // Aggregation
    const agg = getStr('aggregation', ['max', 'mean', 'min']);
    if (agg) params.aggregation = agg;

    // Render mode
    const rm = getStr('renderMode', ['bars', 'points', 'surface']);
    if (rm) params.renderMode = rm;

    // Vertical exaggeration as user-facing multiplier (exag=6 => 6x)
    const ex = getFloat('exag', 1, 100);
    if (ex !== null) params.verticalExaggeration = multiplierToInternal(ex);

    // Color scheme
    const cs = getStr('colorScheme');
    if (cs) params.colorScheme = cs;

    // Shading / lighting
    const flat = getBool('flat');
    if (flat !== null) params.flatLightingEnabled = !!flat;
    const hs = getBool('hillshade');
    if (hs !== null) params.hillshadeEnabled = !!hs;
    const saz = getInt('sunAz', 0, 360);
    if (saz !== null) params.sunAzimuthDeg = saz;
    const sal = getInt('sunAlt', 0, 90);
    if (sal !== null) params.sunAltitudeDeg = sal;
    const gamma = getFloat('gamma', 0.5, 2.0);
    if (gamma !== null) params.colorGamma = gamma;

    // Camera scheme (if exists in UI)
    const scheme = getStr('camera');
    const schemeEl = document.getElementById('cameraScheme');
    if (scheme && schemeEl) {
        schemeEl.value = scheme;
        try { switchCameraScheme(scheme); } catch (_) { }
    }
}

// Initialize
async function init() {
    try {
        setupScene();
        setupEventListeners();

        // Ensure activity log is visible by adding an initial entry
        appendActivityLog('Viewer initialized');
        // Mirror warnings/errors and significant console.log messages into activity log
        if (!window.__consolePatched) {
            const origLog = console.log.bind(console);
            const origWarn = console.warn.bind(console);
            const origError = console.error.bind(console);

            // Mirror significant console.log messages to activity log
            // Skip verbose/debug-only messages that would spam the UI
            console.log = (...args) => {
                origLog(...args);
                const msg = args.join(' ');
                // Only mirror significant messages (not verbose debug details)
                if (msg.includes('[OK]') || msg.includes('[INFO]') || msg.includes('[JSON]') ||
                    msg.includes('Bucket size adjusted') || msg.includes('Resolution set') ||
                    msg.includes('Setting TRUE SCALE') || (msg.includes('Setting ') && msg.includes('x exaggeration')) ||
                    msg.includes('Camera reset') || msg.includes('True scale for') ||
                    msg.includes('Loading region') || msg.includes('Loading JSON file') ||
                    msg.includes('Aggregation:') || msg.includes('Already at') ||
                    msg.includes('Switching to') || msg.includes('Pivot marker created') ||
                    msg.includes('Bars centered') || msg.includes('Points centered') ||
                    msg.includes('PURE 2D GRID') || (msg.includes('Created') && msg.includes('instanced bars')) ||
                    msg.includes('Creating borders') || msg.includes('border segments')) {
                    try { appendActivityLog(msg); } catch (_) { }
                }
            };
            console.warn = (...args) => { try { appendActivityLog(args.join(' ')); } catch (_) { } origWarn(...args); };
            console.error = (...args) => { try { appendActivityLog(args.join(' ')); } catch (_) { } origError(...args); };
            window.__consolePatched = true;
        }

        // Display version number
        const versionDisplay = document.getElementById('version-display');
        if (versionDisplay) {
            versionDisplay.textContent = `v${VIEWER_VERSION}`;
        }
        appendActivityLog(`Altitude Maps Viewer v${VIEWER_VERSION}`);

        // Populate region selector (loads manifest and populates dropdown)
        const firstRegionId = await populateRegionSelector();

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

        // Set default vertical exaggeration to 6x after initial data load
        try {
            if (typeof setVertExagMultiplier === 'function') {
                setVertExagMultiplier(6);
            }
        } catch (e) {
            console.warn('Could not set default vertical exaggeration to 6x:', e);
        }
        // Initialize HUD toggle
        const hudMin = document.getElementById('hud-minimize');
        const hudExp = document.getElementById('hud-expand');
        const hud = document.getElementById('info');
        if (hudMin && hudExp && hud) {
            hudMin.addEventListener('click', () => { hud.style.display = 'none'; hudExp.style.display = 'block'; });
            hudExp.addEventListener('click', () => { hud.style.display = ''; hudExp.style.display = 'none'; });
        }
        // Ensure dropdown is filled for initial interaction
        const dropdown = document.getElementById('regionDropdown');
        if (dropdown && regionOptions.length) {
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

        // Calculate true scale for this data
        const scale = calculateRealWorldScale();
        trueScaleValue = 1.0 / scale.metersPerPixelX;
        console.log(`True scale for this region: ${trueScaleValue.toFixed(6)}x`);

        hideLoading();

        // Sync UI to match params (ensures no mismatch on initial load)
        syncUIControls();

        // Auto-adjust bucket size to meet complexity constraints
        autoAdjustBucketSize();

        // updateStats() is called by autoAdjustBucketSize(), no need to call again

        // Reset camera to appropriate distance for this terrain size
        resetCamera();

        // Automatically reframe view (equivalent to F key) if camera scheme supports it
        if (activeScheme && activeScheme.reframeView) {
            activeScheme.reframeView();
        }

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

// Expected data format version - must match export script
const EXPECTED_FORMAT_VERSION = 2;

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
    // Respect caching toggle: only bust cache when USE_CACHE is false
    const urlWithBuster = USE_CACHE ? url : (url.includes('?') ? `${url}&_t=${Date.now()}` : `${url}?_t=${Date.now()}`);
    const tStart = performance.now();
    const response = await fetch(urlWithBuster);

    // Extract filename from URL
    const filename = url.split('/').pop();

    // Log response details for debugging
    console.log(`Loading JSON file: ${filename}`);
    console.log(` Full URL: ${url}`);
    console.log(` HTTP Status: ${response.status} ${response.statusText}`);
    console.log(` Content-Type: ${response.headers.get('content-type')}`);
    console.log(` Content-Encoding: ${response.headers.get('content-encoding')}`);
    console.log(` Content-Length: ${response.headers.get('content-length')}`);

    if (!response.ok) {
        throw new Error(`Failed to load elevation data. HTTP ${response.status} ${response.statusText} for ${url}`);
    }

    // HTTP/2 strips Content-Length after auto-decompression, so we load as blob to get size
    // This works with compressed data transparently
    console.log(` Loading data (HTTP/2 compatible mode)...`);
    const blob = await response.blob();
    const text = await blob.text();
    const data = JSON.parse(text);

    appendActivityLog(`Loaded ${filename}: ${(blob.size / 1024 / 1024).toFixed(2)} MB (decompressed)`);
    updateLoadingProgress(100, blob.size, blob.size);

    // Validate format version
    if (data.format_version && data.format_version !== EXPECTED_FORMAT_VERSION) {
        console.error(`[!!] FORMAT VERSION MISMATCH!`);
        console.error(` Expected: v${EXPECTED_FORMAT_VERSION}`);
        console.error(` Got: v${data.format_version}`);
        console.error(` File may have outdated transformations!`);
        throw new Error(
            `Data format version mismatch!\n` +
            `Expected v${EXPECTED_FORMAT_VERSION}, got v${data.format_version}\n\n` +
            `This data was exported with an older format.\n` +
            `Please re-export: python export_for_web_viewer.py`
        );
    } else if (!data.format_version) {
        console.warn(`[!!] No format version in data file - may be legacy format!`);
        console.warn(` Consider re-exporting: python export_for_web_viewer.py`);
    } else {
        appendActivityLog(`[OK] Data format v${data.format_version} (exported: ${data.exported_at || 'unknown'})`);
    }

    try { logResourceTiming(urlWithBuster, 'Loaded JSON', tStart, performance.now()); } catch (e) { }
    return data;
}

async function loadBorderData(elevationUrl) {
    // Try to load borders from the same location with _borders suffix
    const borderUrl = elevationUrl.replace('.json', '_borders.json');
    // Respect caching toggle
    const urlWithBuster = USE_CACHE ? borderUrl : (borderUrl.includes('?') ? `${borderUrl}&_t=${Date.now()}` : `${borderUrl}?_t=${Date.now()}`);
    try {
        const tStart = performance.now();
        const response = await fetch(urlWithBuster);
        if (!response.ok) {
            console.warn(`[INFO] No border data found at ${borderUrl}`);
            return null;
        }
        const data = await response.json();
        const borderCount = (data.countries?.length || 0) + (data.states?.length || 0);
        const borderType = data.states ? 'states' : 'countries';
        appendActivityLog(`[OK] Loaded border data: ${borderCount} ${borderType}`);
        try { logResourceTiming(urlWithBuster, 'Loaded borders', tStart, performance.now()); } catch (e) { }
        return data;
    } catch (error) {
        console.warn(`[INFO] Border data not available: ${error.message}`);
        return null;
    }
}

async function loadRegionsManifest() {
    try {
        const base = `generated/regions/regions_manifest.json`;
        // Always cache-bust manifest requests to pick up latest regions
        const url = base.includes('?') ? `${base}&_t=${Date.now()}` : `${base}?_t=${Date.now()}`;
        const tStart = performance.now();
        const response = await fetch(url, { cache: 'no-store' });
        if (!response.ok) {
            console.warn('Regions manifest not found, using default single region');
            return null;
        }
        const json = await response.json();
        try { logResourceTiming(url, 'Loaded manifest', tStart, performance.now()); } catch (e) { }
        return json;
    } catch (error) {
        console.warn('Could not load regions manifest:', error);
        return null;
    }
}

async function populateRegionSelector() {
    const inputEl = document.getElementById('regionSelect');
    const listEl = document.getElementById('regionList');

    regionsManifest = await loadRegionsManifest();

    if (!regionsManifest || !regionsManifest.regions || Object.keys(regionsManifest.regions).length === 0) {
        // No manifest, use default single region
        if (inputEl) {
            inputEl.value = 'Default Region';
        }
        currentRegionId = 'default';
        return 'default';
    }

    // Check for URL parameter to specify initial region (e.g., ?region=ohio)
    const urlParams = new URLSearchParams(window.location.search);
    const urlRegion = urlParams.get('region');

    // Check localStorage for last viewed region
    const lastRegion = localStorage.getItem('lastViewedRegion');

    // Build maps and populate options for custom dropdown
    regionIdToName = {};
    regionNameToId = {};
    regionOptions = [];

    // Build three groups using manifest-provided categories:
    // Desired order in dropdown: 1) US states, 2) Regions (non-country), 3) Countries (international)
    const internationalCountries = [];
    const nonCountryRegions = [];
    const unitedStates = [];

    for (const [regionId, regionInfo] of Object.entries(regionsManifest.regions)) {
        const id = regionId;
        const category = (regionInfo && regionInfo.category) ? String(regionInfo.category).toLowerCase() : null;
        if (category === 'usa_state') {
            unitedStates.push({ id, info: regionInfo });
        } else if (category === 'country') {
            internationalCountries.push({ id, info: regionInfo });
        } else if (category === 'region') {
            nonCountryRegions.push({ id, info: regionInfo });
        } else {
            // Fallback: treat unknown categories as generic regions
            nonCountryRegions.push({ id, info: regionInfo });
        }
    }

    // 1) US states (alpha)
    unitedStates.sort((a, b) => a.info.name.localeCompare(b.info.name));
    for (const { id, info } of unitedStates) {
        regionIdToName[id] = info.name;
        regionNameToId[info.name.toLowerCase()] = id;
        regionOptions.push({ id, name: info.name });
    }
    if (unitedStates.length && (nonCountryRegions.length || internationalCountries.length)) {
        regionOptions.push({ id: '__divider__', name: '' });
    }

    // 2) Regions (alpha)
    nonCountryRegions.sort((a, b) => a.info.name.localeCompare(b.info.name));
    for (const { id, info } of nonCountryRegions) {
        regionIdToName[id] = info.name;
        regionNameToId[info.name.toLowerCase()] = id;
        regionOptions.push({ id, name: info.name });
    }
    if (nonCountryRegions.length && internationalCountries.length) {
        regionOptions.push({ id: '__divider__', name: '' });
    }

    // 3) Countries (alpha)
    internationalCountries.sort((a, b) => a.info.name.localeCompare(b.info.name));
    for (const { id, info } of internationalCountries) {
        regionIdToName[id] = info.name;
        regionNameToId[info.name.toLowerCase()] = id;
        regionOptions.push({ id, name: info.name });
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

    if (regionId === 'default' || !regionsManifest || !regionsManifest.regions[regionId]) {
        if (currentRegionEl) currentRegionEl.textContent = 'Default Region';
        if (regionInfoEl) regionInfoEl.textContent = 'No region data available';
        return;
    }

    const regionInfo = regionsManifest.regions[regionId];
    if (currentRegionEl) currentRegionEl.textContent = regionInfo.name;
    if (regionInfoEl) regionInfoEl.textContent = regionInfo.description;
}

async function loadRegion(regionId) {
    appendActivityLog(`Loading region: ${regionId}`);
    showLoading(`Loading ${regionsManifest?.regions[regionId]?.name || regionId}...`);

    try {
        let dataUrl;
        if (regionId === 'default') {
            dataUrl = 'generated/elevation_data.json';
        } else {
            // Use the file path from manifest (handles version suffixes like _srtm_30m_v2)
            const filename = regionsManifest?.regions[regionId]?.file || `${regionId}.json`;
            dataUrl = `generated/regions/${filename}`;
        }

        // Display the full file path in the UI
        const regionInfoEl = document.getElementById('regionInfo');
        if (regionInfoEl) {
            const regionName = regionsManifest?.regions[regionId]?.name || regionId;
            regionInfoEl.innerHTML = `
 ${regionName}<br>
 <span style="font-size: 11px; color:#888; font-family: monospace;">${dataUrl}</span>
 `;
        }

        rawElevationData = await loadElevationData(dataUrl);
        borderData = await loadBorderData(dataUrl);
        currentRegionId = regionId;
        updateRegionInfo(regionId);

        // Display the full file path in the UI (after updateRegionInfo overwrites it)
        if (regionInfoEl) {
            const regionName = regionsManifest?.regions[regionId]?.name || regionId;
            regionInfoEl.innerHTML = `
 ${regionName}<br>
 <span style="font-size: 11px; color:#888; font-family: monospace;">${dataUrl}</span>
 `;
        }

        // Calculate true scale for this data
        const scale = calculateRealWorldScale();
        trueScaleValue = 1.0 / scale.metersPerPixelX;
        console.log(`True scale for this region: ${trueScaleValue.toFixed(6)}x`);

        // Save to localStorage so we remember this region next time
        localStorage.setItem('lastViewedRegion', regionId);

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
        edgeMarkers.forEach(marker => scene.remove(marker));
        edgeMarkers = [];

        // Before first build for this region, auto-increase bucket size to target count
        // (respects larger values from URL/user)
        autoAdjustBucketSize();
        // Reprocess and recreate terrain
        rebucketData();
        recreateTerrain();
        // Ensure color scheme is applied immediately on new region load
        if (!params.colorScheme) params.colorScheme = 'terrain';
        updateColors();
        recreateBorders();
        updateStats();

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

function showLoading(message = 'Loading elevation data...') {
    isCurrentlyLoading = true;
    const loadingDiv = document.getElementById('loading');
    loadingDiv.innerHTML = `
 <div style="text-align: center;">
 ${message}
 <div class="spinner"></div>
 <div id="progress-container" style="margin-top: 15px; width: 300px;">
 <div id="progress-bar-bg" style="width: 100%; height: 20px; background: rgba(255,255,255,0.1); border-radius: 10px; overflow: hidden;">
 <div id="progress-bar-fill" style="width: 0%; height: 100%; background: linear-gradient(90deg,#4488cc,#5599dd); transition: width 0.3s ease;"></div>
 </div>
 <div id="progress-text" style="margin-top: 8px; font-size: 13px; color:#aaa;">Initializing...</div>
 </div>
 </div>
 `;
    loadingDiv.style.display = 'flex';
}

function updateLoadingProgress(percent, loaded, total) {
    const progressFill = document.getElementById('progress-bar-fill');
    const progressText = document.getElementById('progress-text');

    if (!progressFill || !progressText) return;

    progressFill.style.width = `${Math.min(100, percent)}%`;
    progressText.textContent = `${percent}% (${formatFileSize(loaded)} / ${formatFileSize(total)})`;
}

function formatFileSize(bytes) {
    if (bytes < 1024) {
        return `${bytes} B`;
    } else if (bytes < 1024 * 1024) {
        return `${(bytes / 1024).toFixed(1)} KB`;
    } else {
        return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    }
}

function hideLoading() {
    isCurrentlyLoading = false;
    document.getElementById('loading').style.display = 'none';
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

    // Flat lighting toggle (if present)
    const flatChk = document.getElementById('flatLightingEnabled');
    if (flatChk) flatChk.checked = !!params.flatLightingEnabled;

    // Apply visual settings to scene objects
    if (gridHelper) {
        gridHelper.visible = params.showGrid;
    }
    if (borderMeshes && borderMeshes.length > 0) {
        borderMeshes.forEach(mesh => mesh.visible = params.showBorders);
    }
    if (controls) {
        controls.autoRotate = params.autoRotate;
    }

    // Shading controls removed from UI
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

function createEdgeMarkers() {
    // Remove old markers
    edgeMarkers.forEach(marker => scene.remove(marker));
    edgeMarkers = [];

    if (!rawElevationData || !processedData) return;

    const gridWidth = processedData.width;
    const gridHeight = processedData.height;

    // Position markers at ground level (y=0) so they sit on the terrain surface
    // They stay at this fixed height regardless of vertical exaggeration changes
    const markerHeight = 0;

    // Calculate actual coordinate extents based on render mode
    let xExtent, zExtent, avgSize;
    if (params.renderMode === 'bars') {
        // Bars use UNIFORM 2D grid - same spacing in X and Z (no aspect ratio)
        const bucketMultiplier = params.bucketSize;
        xExtent = (gridWidth - 1) * bucketMultiplier / 2;
        zExtent = (gridHeight - 1) * bucketMultiplier / 2; // NO aspect ratio scaling!
        avgSize = (xExtent + zExtent);
    } else if (params.renderMode === 'points') {
        // Points use uniform grid positioning
        const bucketSize = 1;
        xExtent = (gridWidth - 1) * bucketSize / 2;
        zExtent = (gridHeight - 1) * bucketSize / 2;
        avgSize = (xExtent + zExtent);
    } else {
        // Surface uses uniform grid positioning (centered PlaneGeometry)
        xExtent = gridWidth / 2;
        zExtent = gridHeight / 2;
        avgSize = (gridWidth + gridHeight) / 2;
    }

    // Create text sprites for N, E, S, W at appropriate edges
    const markers = [
        { text: 'N', x: 0, z: -zExtent, color: 0xff4444 }, // North edge
        { text: 'S', x: 0, z: zExtent, color: 0x4488ff }, // South edge
        { text: 'E', x: xExtent, z: 0, color: 0x44ff44 }, // East edge
        { text: 'W', x: -xExtent, z: 0, color: 0xffff44 } // West edge
    ];

    markers.forEach(markerData => {
        const sprite = createTextSprite(markerData.text, markerData.color);
        sprite.position.set(markerData.x, markerHeight, markerData.z);

        // Scale based on terrain size
        const baseScale = avgSize * 0.06; // 6% of average dimension (tripled from original 2%)
        sprite.scale.set(baseScale, baseScale, baseScale);

        scene.add(sprite);
        edgeMarkers.push(sprite);
    });

    // Removed verbose edge marker creation log
}

function createTextSprite(text, color) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    canvas.width = 256;
    canvas.height = 256;

    // Draw background circle
    context.fillStyle = 'rgba(0, 0, 0, 0.8)';
    context.beginPath();
    context.arc(128, 128, 100, 0, 2 * Math.PI);
    context.fill();

    // Draw border
    context.strokeStyle = `#${color.toString(16).padStart(6, '0')}`;
    context.lineWidth = 8;
    context.beginPath();
    context.arc(128, 128, 100, 0, 2 * Math.PI);
    context.stroke();

    // Draw text
    context.font = 'Bold 140px Arial';
    context.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(text, 128, 128);

    const texture = new THREE.CanvasTexture(canvas);
    const spriteMaterial = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthTest: false, // Always visible
        depthWrite: false
    });
    const sprite = new THREE.Sprite(spriteMaterial);

    return sprite;
}

function updateEdgeMarkers() {
    if (!rawElevationData || !processedData || edgeMarkers.length === 0) return;

    // Markers stay at fixed height - no update needed when vertical exaggeration changes
    // This function is kept for compatibility but doesn't change marker heights
    // The markers are positioned at a fixed height set in createEdgeMarkers()
}

/**
 * Detect GPU capabilities and benchmark performance tier
 * @returns {Object|null} GPU info with vendor, renderer, tier, and benchmark results
 */
function detectGPU() {
    // Use the renderer's GL context if available
    let gl = null;
    if (renderer && renderer.getContext) {
        gl = renderer.getContext();
    } else {
        // Fallback: create temporary context
        gl = document.createElement('canvas').getContext('webgl') ||
            document.createElement('canvas').getContext('experimental-webgl');
    }

    if (!gl) {
        console.error('WebGL not supported! This viewer requires WebGL.');
        return null;
    }

    const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
    const gpuInfo = {
        renderer: debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : 'Unknown',
        vendor: debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : 'Unknown',
        tier: 'medium', // Default tier
        benchmark: null
    };

    // Identify known GPU vendor strings
    const rendererLower = gpuInfo.renderer.toLowerCase();
    const vendorLower = gpuInfo.vendor.toLowerCase();

    // Detect vendor
    if (vendorLower.includes('intel') || rendererLower.includes('intel')) {
        gpuInfo.vendor = 'Intel';
        // Intel integrated graphics - tier depends on generation
        if (rendererLower.includes('iris') || rendererLower.includes('uhd 770') || rendererLower.includes('uhd 750')) {
            gpuInfo.tier = 'medium'; // Modern Intel Xe Graphics
        } else {
            gpuInfo.tier = 'low'; // Older Intel HD Graphics
        }
    } else if (vendorLower.includes('nvidia') || rendererLower.includes('nvidia')) {
        gpuInfo.vendor = 'NVIDIA';
        gpuInfo.tier = 'high'; // Most NVIDIA GPUs are discrete and powerful
    } else if (vendorLower.includes('amd') || rendererLower.includes('amd') || rendererLower.includes('radeon')) {
        gpuInfo.vendor = 'AMD';
        if (rendererLower.includes('integrated')) {
            gpuInfo.tier = 'low'; // AMD integrated graphics
        } else {
            gpuInfo.tier = 'high'; // AMD discrete GPUs
        }
    } else if (vendorLower.includes('apple') || rendererLower.includes('apple')) {
        gpuInfo.vendor = 'Apple';
        // Apple Silicon vs older Macs
        if (rendererLower.includes('apple gpu') || rendererLower.includes('apple m1') || rendererLower.includes('apple m2')) {
            gpuInfo.tier = 'high'; // Apple Silicon GPUs are powerful
        } else {
            gpuInfo.tier = 'medium'; // Older Intel Mac GPUs
        }
    } else if (vendorLower.includes('adreno') || rendererLower.includes('adreno')) {
        gpuInfo.vendor = 'Qualcomm';
        gpuInfo.tier = 'low'; // Mobile GPUs
    } else if (vendorLower.includes('mali') || rendererLower.includes('mali')) {
        gpuInfo.vendor = 'ARM';
        gpuInfo.tier = 'low'; // Mobile GPUs
    } else {
        gpuInfo.vendor = 'Unknown';
        gpuInfo.tier = 'medium'; // Conservative default
    }

    // Run simple performance benchmark if renderer is available
    if (renderer) {
        gpuInfo.benchmark = benchmarkGPU(renderer, gl);
    }

    return gpuInfo;
}

/**
 * Benchmark GPU fill rate and geometry performance
 * @param {THREE.WebGLRenderer} testRenderer - Renderer to test with
 * @param {WebGLRenderingContext} testGL - WebGL context to test with
 * @returns {Object} Benchmark results
 */
function benchmarkGPU(testRenderer, testGL) {
    const benchmark = {
        fillRate: 0,
        geometry: 0,
        combined: 0,
        timestamp: Date.now()
    };

    try {
        // Create off-screen canvas for benchmark to avoid visual interference
        const offscreenCanvas = document.createElement('canvas');
        offscreenCanvas.width = 256;
        offscreenCanvas.height = 256;
        const offscreenGL = offscreenCanvas.getContext('webgl', { preserveDrawingBuffer: false });

        if (!offscreenGL) {
            // Fallback: skip benchmark if off-screen context not available
            return benchmark;
        }

        // Create off-screen renderer for benchmark
        const offscreenRenderer = new THREE.WebGLRenderer({
            canvas: offscreenCanvas,
            context: offscreenGL,
            antialias: false,
            alpha: false
        });
        offscreenRenderer.setSize(256, 256);
        offscreenRenderer.setPixelRatio(1);

        const testScene = new THREE.Scene();
        const testCamera = new THREE.PerspectiveCamera(60, 1, 1, 1000);
        testCamera.position.set(0, 0, 100);

        // Create test geometry (1000 cubes)
        const geometry = new THREE.BoxGeometry(1, 1, 1);
        const material = new THREE.MeshLambertMaterial({ color: 0x00ff00 });
        const mesh = new THREE.InstancedMesh(geometry, material, 1000);

        // Random positions
        const dummy = new THREE.Object3D();
        for (let i = 0; i < 1000; i++) {
            dummy.position.set(
                (Math.random() - 0.5) * 50,
                (Math.random() - 0.5) * 50,
                (Math.random() - 0.5) * 50
            );
            dummy.updateMatrix();
            mesh.setMatrixAt(i, dummy.matrix);
        }
        testScene.add(mesh);

        // Add light
        const light = new THREE.DirectionalLight(0xffffff, 1);
        light.position.set(1, 1, 1);
        testScene.add(light);

        // Benchmark: 100 frames
        const startTime = performance.now();
        for (let i = 0; i < 100; i++) {
            offscreenRenderer.render(testScene, testCamera);
        }
        const endTime = performance.now();
        const avgFrameTime = (endTime - startTime) / 100;

        // Calculate scores (lower is better, normalize to 0-100 scale)
        benchmark.fillRate = Math.min(100, (1000 / avgFrameTime) * 10); // Target: 16.67ms = 60fps
        benchmark.geometry = benchmark.fillRate; // Same test for both
        benchmark.combined = benchmark.fillRate;

        // Cleanup
        geometry.dispose();
        material.dispose();
        mesh.dispose();
        light.dispose();
        offscreenRenderer.dispose();

    } catch (e) {
        console.warn('GPU benchmark failed:', e);
    }

    return benchmark;
}

/**
 * Dynamically test if frustum culling helps performance
 * Disables culling, measures FPS, re-enables, measures again
 * @returns {Promise<Object>} Performance comparison
 */
async function testFrustumCulling() {
    if (!barsInstancedMesh || stats.bars === 0) {
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
window.getGPUInfo = () => window.gpuInfo || { error: 'No GPU info available yet' };

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

    // GPU Detection and Benchmarking (async after renderer is ready)
    setTimeout(() => {
        window.gpuInfo = detectGPU();
        if (window.gpuInfo) {
            console.log('GPU Detection:', window.gpuInfo);
            // Log performance tier recommendation
            if (window.gpuInfo.tier === 'low') {
                console.warn('LOW-END GPU detected. Consider increasing bucket size for better performance.');
                appendActivityLog(`GPU: ${window.gpuInfo.vendor} ${window.gpuInfo.renderer} - ${window.gpuInfo.tier.toUpperCase()} tier`);
            } else {
                appendActivityLog(`GPU: ${window.gpuInfo.vendor} ${window.gpuInfo.renderer} - ${window.gpuInfo.tier.toUpperCase()} tier`);
            }
        }
    }, 100); // Small delay to let renderer initialize

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

    // Ensure intensities match current flat/non-flat state
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

    // Apply current shading parameters
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
        });
        regionInput.addEventListener('click', () => {
            openDropdown();
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
            edgeMarkers.forEach(marker => scene.remove(marker));
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
        edgeMarkers.forEach(marker => scene.remove(marker));
        edgeMarkers = [];
        recreateTerrain();
        // Remove focus from dropdown so keyboard navigation works
        e.target.blur();
        updateURLParameter('renderMode', params.renderMode);
    });

    // Vertical exaggeration - immediate updates while dragging

    // Sync slider -> input (update immediately)
    const debouncedNormalsRecompute = debounce(() => {
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

    // Flat lighting
    const flatToggle = document.getElementById('flatLightingEnabled');
    if (flatToggle) {
        flatToggle.addEventListener('change', (e) => {
            params.flatLightingEnabled = !!e.target.checked;
            updateLightingForShading();
            recreateTerrain();
            updateURLParameter('flat', params.flatLightingEnabled ? '1' : '0');
        });
    }

    // Initialize vertical exaggeration button states (highlight default active button)
    updateVertExagButtons(params.verticalExaggeration);

    // Mark controls as initialized to prevent duplicate setup
    controlsInitialized = true;
    console.log('Controls initialized successfully');
}

// ===== RESOLUTION LOADING OVERLAY =====
function showResolutionLoading() {
    const overlay = document.getElementById('resolution-loading-overlay');
    if (overlay) {
        overlay.classList.add('active');
    }
}

function hideResolutionLoading() {
    const overlay = document.getElementById('resolution-loading-overlay');
    if (overlay) {
        overlay.classList.remove('active');
    }
}

// ===== COMPACT RESOLUTION SCALE (logarithmic mapping) =====
function bucketSizeToPercent(size) {
    const clamped = Math.max(1, Math.min(500, parseInt(size)));
    const maxLog = Math.log(500);
    const valLog = Math.log(clamped);
    return (valLog / maxLog) * 100; // 1..500 -> 0..100% in log domain
}

function percentToBucketSize(percent) {
    const p = Math.max(0, Math.min(100, percent));
    const maxLog = Math.log(500);
    const logVal = (p / 100) * maxLog;
    const size = Math.round(Math.exp(logVal));
    return Math.max(1, Math.min(500, size));
}

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

function autoAdjustBucketSize() {
    if (!rawElevationData) {
        console.warn('[WARN] No data loaded, cannot auto-adjust bucket size');
        return;
    }

    const { width, height } = rawElevationData;
    // Reduced from 10000 to ~3900 (60% larger bucket size means ~40% of original bucket count)
    const TARGET_BUCKET_COUNT = 390000;

    // Calculate optimal bucket size to stay within TARGET_BUCKET_COUNT constraint
    // Start with direct calculation: bucketSize = ceil(sqrt(width* height / TARGET_BUCKET_COUNT))
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

    renderer.domElement.addEventListener('mousemove', (e) => {
        // Track mouse for HUD and zoom-to-cursor
        currentMouseX = e.clientX;
        currentMouseY = e.clientY;
        if (activeScheme) activeScheme.onMouseMove(e);
        // Update HUD live
        updateCursorHUD(e.clientX, e.clientY);
    });

    renderer.domElement.addEventListener('mouseup', (e) => {
        if (activeScheme) activeScheme.onMouseUp(e);
    });

    // Setup camera scheme selector
    document.getElementById('cameraScheme').addEventListener('change', (e) => {
        switchCameraScheme(e.target.value);
        updateURLParameter('camera', e.target.value);
    });

    // Initialize default scheme (Google Maps Ground Plane)
    switchCameraScheme('ground-plane');

    // GPU Info link click handler
    const gpuInfoLink = document.getElementById('gpu-info-link');
    if (gpuInfoLink) {
        gpuInfoLink.addEventListener('click', (e) => {
            e.preventDefault();
            const info = window.gpuInfo;
            if (info) {
                const tier = info.tier.toUpperCase();
                const msg = `GPU Information:\n` +
                    `Vendor: ${info.vendor}\n` +
                    `Renderer: ${info.renderer}\n` +
                    `Performance Tier: ${tier}`;
                alert(msg);
                console.log('GPU Info:', info);
            } else {
                alert('GPU information not available yet. Please wait a moment and try again.');
            }
        });
    }

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

function calculateRealWorldScale() {
    // Calculate real-world scale from geographic bounds
    // This ensures vertical_exaggeration=1.0 means "true scale like real Earth"
    const bounds = rawElevationData.bounds;
    const width = rawElevationData.width;
    const height = rawElevationData.height;

    const lonSpan = Math.abs(bounds.right - bounds.left); // degrees
    const latSpan = Math.abs(bounds.top - bounds.bottom); // degrees

    // Calculate meters per degree at the center latitude
    const centerLat = (bounds.top + bounds.bottom) / 2.0;
    const metersPerDegLon = 111_320 * Math.cos(centerLat * Math.PI / 180);
    const metersPerDegLat = 111_320; // approximately constant

    // Calculate real-world dimensions in meters
    const widthMeters = lonSpan * metersPerDegLon;
    const heightMeters = latSpan * metersPerDegLat;

    // Meters per pixel
    const metersPerPixelX = widthMeters / width;
    const metersPerPixelY = heightMeters / height;

    // Removed verbose real-world scale logs

    return {
        metersPerPixelX,
        metersPerPixelY,
        widthMeters,
        heightMeters
    };
}

function createTerrain() {
    const t0 = performance.now();

    // Remove old terrain and DISPOSE geometry/materials
    if (terrainMesh) {
        scene.remove(terrainMesh);
    }

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
    if (terrainMesh) {
        if (params.renderMode === 'bars') {
            // Bars use UNIFORM 2D grid - same spacing in X and Z (no aspect ratio)
            const bucketMultiplier = params.bucketSize;
            terrainMesh.position.x = -(width - 1) * bucketMultiplier / 2;
            terrainMesh.position.z = -(height - 1) * bucketMultiplier / 2; // NO aspect ratio scaling!
            console.log(`Bars centered: uniform grid ${width}x${height}, tile size ${bucketMultiplier}, offset (${terrainMesh.position.x.toFixed(1)}, ${terrainMesh.position.z.toFixed(1)})`);
        } else if (params.renderMode === 'points') {
            // Points use uniform grid positioning
            const bucketSize = 1;
            terrainMesh.position.x = -(width - 1) * bucketSize / 2;
            terrainMesh.position.z = -(height - 1) * bucketSize / 2;
            console.log(`Points centered: uniform grid ${width}x${height}, offset (${terrainMesh.position.x.toFixed(1)}, ${terrainMesh.position.z.toFixed(1)})`);
        } else {
            // Surface mode: PlaneGeometry is already centered, but position it at origin
            terrainMesh.position.set(0, 0, 0);
            console.log(`Surface centered: geometry naturally centered`);
        }
    }

    const t1 = performance.now();
    appendActivityLog(`Terrain created in ${(t1 - t0).toFixed(1)}ms`);

    stats.vertices = width * height;
    stats.bucketedVertices = width * height;

    // Update camera scheme with terrain bounds for F key reframing
    if (controls && controls.activeScheme && controls.activeScheme.setTerrainBounds) {
        // Calculate bounds based on render mode
        if (params.renderMode === 'bars') {
            const bucketMultiplier = params.bucketSize;
            const halfWidth = (width - 1) * bucketMultiplier / 2;
            const halfDepth = (height - 1) * bucketMultiplier / 2;
            controls.activeScheme.setTerrainBounds(-halfWidth, halfWidth, -halfDepth, halfDepth);
        } else if (params.renderMode === 'points') {
            const halfWidth = (width - 1) / 2;
            const halfDepth = (height - 1) / 2;
            controls.activeScheme.setTerrainBounds(-halfWidth, halfWidth, -halfDepth, halfDepth);
        } else {
            // Surface mode - use geometry grid extents (uniform grid)
            const halfWidth = width / 2;
            const halfDepth = height / 2;
            controls.activeScheme.setTerrainBounds(-halfWidth, halfWidth, -halfDepth, halfDepth);
        }
    }

    // PRODUCT REQUIREMENT: Edge markers must stay fixed when vertical exaggeration changes
    // Only create edge markers if they don't exist yet (prevents movement on exaggeration change)
    if (edgeMarkers.length === 0) {
        createEdgeMarkers();
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
    const material = params.flatLightingEnabled
        ? new THREE.MeshBasicMaterial({ vertexColors: true })
        : new THREE.MeshLambertMaterial({ vertexColors: true });

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
    scene.add(terrainMesh);
    stats.bars = barCount;
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

    // Uniform grid spacing - treat as simple 2D grid
    const bucketSize = 1; // Uniform spacing

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
    scene.add(terrainMesh);
    lastPointsExaggerationInternal = params.verticalExaggeration;
    if (terrainMesh.material && terrainMesh.material.userData && terrainMesh.material.userData.uExaggerationUniform) {
        terrainMesh.material.userData.uExaggerationUniform.value = 1.0;
    }
}

function createSurfaceTerrain(width, height, elevation, scale) {
    // Create uniform 2D grid - no geographic corrections
    // Treat data as simple evenly-spaced grid points
    const geometry = new THREE.PlaneGeometry(
        width, height, width - 1, height - 1
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
        geometry.computeVertexNormals();
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
        material = params.flatLightingEnabled
            ? new THREE.MeshBasicMaterial({ vertexColors: true, wireframe: false, side: THREE.DoubleSide })
            : new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: false, wireframe: false, side: THREE.DoubleSide });
    }

    terrainMesh = new THREE.Mesh(geometry, material);
    terrainMesh.rotation.x = -Math.PI / 2;
    scene.add(terrainMesh);
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

    const scheme = COLOR_SCHEMES[params.colorScheme] || COLOR_SCHEMES.terrain;

    for (let i = 0; i < scheme.length - 1; i++) {
        const a = scheme[i];
        const b = scheme[i + 1];
        if (normalized >= a.stop && normalized <= b.stop) {
            const localT = (normalized - a.stop) / (b.stop - a.stop);
            // Reuse temporary color to avoid allocations
            return __tmpColor.copy(a.color).lerp(b.color, localT);
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
        // If hillshade is enabled, vertex colors are not used; nothing to update visually
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
        return; // hillshade on: colors ignored
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

function recreateTerrain() {
    createTerrain();
}

function updateMaterialsForShading() {
    // Shading disabled for now
}

function updateSunLightDirection() {
    const light = window.__sunLight;
    if (!light) return;
    const azRad = (params.sunAzimuthDeg % 360) * Math.PI / 180;
    const altRad = (Math.max(0, Math.min(90, params.sunAltitudeDeg)) * Math.PI) / 180;
    const x = Math.cos(altRad) * Math.cos(azRad);
    const y = Math.sin(altRad);
    const z = Math.cos(altRad) * Math.sin(azRad);
    light.position.set(x * 200, y * 200, z * 200);
}

function updateLightingForShading() {
    const ambient = window.__ambientLight;
    const d1 = window.__dirLight1;
    const d2 = window.__dirLight2;
    if (!ambient || !d1 || !d2) return;
    if (params.flatLightingEnabled) {
        ambient.intensity = 1.0;
        d1.intensity = 0.0;
        d2.intensity = 0.0;
    } else {
        // Brighter ambient to avoid overly dark appearance
        ambient.intensity = 0.9;
        d1.intensity = 0.4;
        d2.intensity = 0.2;
    }
}


// ===== SUN PAD INTERACTION (mouse-driven sky control) =====
let sunPadState = { dragging: false };
function initSunPad() {
    const canvas = document.getElementById('sunPad');
    if (!canvas) return;
    const onPos = (clientX, clientY) => {
        const rect = canvas.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const dx = clientX - cx;
        const dy = clientY - cy;
        const R = Math.min(rect.width, rect.height) * 0.5 - 4;
        const r = Math.min(Math.sqrt(dx * dx + dy * dy), R);
        // Azimuth: 0deg = right (east), 90deg = up (north-ish visual), CCW
        let az = Math.atan2(-dy, dx) * 180 / Math.PI; // invert dy for canvas y
        if (az < 0) az += 360;
        // Altitude: center = 90deg, edge = 0deg
        const alt = Math.max(0, Math.min(90, (1 - (r / R)) * 90));
        params.sunAzimuthDeg = Math.round(az);
        params.sunAltitudeDeg = Math.round(alt);
        const azEl = document.getElementById('sunAzimuth');
        const azInEl = document.getElementById('sunAzimuthInput');
        const altEl = document.getElementById('sunAltitude');
        const altInEl = document.getElementById('sunAltitudeInput');
        if (azEl) azEl.value = params.sunAzimuthDeg;
        if (azInEl) azInEl.value = params.sunAzimuthDeg;
        if (altEl) altEl.value = params.sunAltitudeDeg;
        if (altInEl) altInEl.value = params.sunAltitudeDeg;
        updateSunLightDirection();
        drawSunPad();
    };
    canvas.addEventListener('mousedown', (e) => { sunPadState.dragging = true; onPos(e.clientX, e.clientY); });
    window.addEventListener('mousemove', (e) => { if (sunPadState.dragging) onPos(e.clientX, e.clientY); });
    window.addEventListener('mouseup', () => { sunPadState.dragging = false; });
    drawSunPad();
}

function drawSunPad() {
    const canvas = document.getElementById('sunPad');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    const cx = w / 2, cy = h / 2;
    const R = Math.min(w, h) * 0.5 - 4;
    // Background
    ctx.fillStyle = '#0a0a0a';
    ctx.fillRect(0, 0, w, h);
    // Horizon circle
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.strokeStyle = '#335';
    ctx.lineWidth = 1;
    ctx.stroke();
    // Altitude rings (30deg and 60deg)
    const r30 = R * (1 - 30 / 90);
    const r60 = R * (1 - 60 / 90);
    ctx.beginPath(); ctx.arc(cx, cy, r30, 0, Math.PI * 2); ctx.strokeStyle = '#233'; ctx.stroke();
    ctx.beginPath(); ctx.arc(cx, cy, r60, 0, Math.PI * 2); ctx.strokeStyle = '#233'; ctx.stroke();
    // Sun dot
    const azRad = (params.sunAzimuthDeg % 360) * Math.PI / 180;
    const altFrac = Math.max(0, Math.min(1, params.sunAltitudeDeg / 90));
    const r = R * (1 - altFrac);
    const sx = cx + Math.cos(azRad) * r;
    const sy = cy - Math.sin(azRad) * r;
    ctx.beginPath();
    ctx.arc(sx, sy, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#ffcc66';
    ctx.fill();
    ctx.strokeStyle = '#664400';
    ctx.stroke();
}

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

function recreateBorders() {
    console.log('Creating borders...');

    // Remove old borders
    borderMeshes.forEach(mesh => scene.remove(mesh));
    borderMeshes = [];
    borderSegmentsMeters = [];
    borderSegmentsGeo = [];
    borderGeoIndex = new Map();

    if (!borderData || (!borderData.countries && !borderData.states)) {
        console.log('[INFO] No border data available');
        return;
    }

    if (!params.showBorders) {
        console.log('[INFO] Borders hidden by user setting');
        return;
    }

    const { width, height, bounds: elevBounds } = rawElevationData;
    const { bounds } = borderData;

    // Calculate real-world scale
    const scale = calculateRealWorldScale();

    // Set borders at a fixed height that doesn't change with vertical exaggeration
    // Use a small constant height just above ground level
    const borderHeight = 100; // Fixed at 100 meters above ground

    let totalSegments = 0;

    // Combine countries and states into a single array for processing
    const allBorders = [
        ...(borderData.countries || []),
        ...(borderData.states || [])
    ];

    const { mx, mz } = getMetersScalePerWorldUnit();
    allBorders.forEach((entity) => {
        entity.segments.forEach((segment) => {
            const points = [];

            // Convert lon/lat to coordinates matching the render mode
            for (let i = 0; i < segment.lon.length; i++) {
                const lon = segment.lon[i];
                const lat = segment.lat[i];

                // Map geographic coords to normalized [0,1] range
                const colNormalized = (lon - elevBounds.left) / (elevBounds.right - elevBounds.left);
                const rowNormalized = (elevBounds.top - lat) / (elevBounds.top - elevBounds.bottom);

                let xCoord, zCoord;
                if (params.renderMode === 'bars') {
                    // Bars use grid-based positioning: 0 to (width-1)*bucketSize
                    const bucketMultiplier = params.bucketSize;
                    const bWidth = processedData.width;
                    const bHeight = processedData.height;
                    xCoord = colNormalized * (bWidth - 1) * bucketMultiplier;
                    zCoord = rowNormalized * (bHeight - 1) * bucketMultiplier;
                    // Apply same centering offset as terrain
                    xCoord -= (bWidth - 1) * bucketMultiplier / 2;
                    zCoord -= (bHeight - 1) * bucketMultiplier / 2;
                } else if (params.renderMode === 'points') {
                    // Points use uniform grid positioning
                    const bWidth = processedData.width;
                    const bHeight = processedData.height;
                    xCoord = colNormalized * (bWidth - 1);
                    zCoord = rowNormalized * (bHeight - 1);
                    // Apply same centering offset as terrain
                    xCoord -= (bWidth - 1) / 2;
                    zCoord -= (bHeight - 1) / 2;
                } else {
                    // Surface uses uniform grid positioning (PlaneGeometry centered at origin)
                    const bWidth = processedData.width;
                    const bHeight = processedData.height;
                    xCoord = (colNormalized - 0.5) * bWidth;
                    zCoord = (rowNormalized - 0.5) * bHeight;
                }

                // Three.js: x=East, z=South, y=elevation
                points.push(new THREE.Vector3(xCoord, borderHeight, zCoord));
            }

            if (points.length > 1) {
                const geometry = new THREE.BufferGeometry().setFromPoints(points);
                const material = new THREE.LineBasicMaterial({
                    color: 0xFFFF00, // YELLOW - highly visible!
                    linewidth: 2,
                    transparent: true,
                    opacity: 0.9
                });
                const line = new THREE.Line(geometry, material);
                scene.add(line);
                borderMeshes.push(line);
                totalSegments++;
                // Capture as meter-scaled 2D segments for HUD distance queries
                for (let p = 0; p < points.length - 1; p++) {
                    const a = points[p];
                    const b = points[p + 1];
                    borderSegmentsMeters.push({
                        ax: a.x * mx,
                        az: a.z * mz,
                        bx: b.x * mx,
                        bz: b.z * mz
                    });
                    // Also store geographic segment and index it
                    const aLon = segment.lon[p];
                    const aLat = segment.lat[p];
                    const bLon = segment.lon[p + 1];
                    const bLat = segment.lat[p + 1];
                    const geoIndex = borderSegmentsGeo.length;
                    borderSegmentsGeo.push({ axLon: aLon, axLat: aLat, bxLon: bLon, bxLat: bLat });
                    // Compute covered cells and insert id
                    const minLon = Math.min(aLon, bLon);
                    const maxLon = Math.max(aLon, bLon);
                    const minLat = Math.min(aLat, bLat);
                    const maxLat = Math.max(aLat, bLat);
                    const ix0 = Math.floor(minLon / borderGeoCellSizeDeg);
                    const ix1 = Math.floor(maxLon / borderGeoCellSizeDeg);
                    const iy0 = Math.floor(minLat / borderGeoCellSizeDeg);
                    const iy1 = Math.floor(maxLat / borderGeoCellSizeDeg);
                    for (let ix = ix0; ix <= ix1; ix++) {
                        for (let iy = iy0; iy <= iy1; iy++) {
                            const key = `${ix},${iy}`;
                            let arr = borderGeoIndex.get(key);
                            if (!arr) { arr = []; borderGeoIndex.set(key, arr); }
                            arr.push(geoIndex);
                        }
                    }
                }
            }
        });
    });

    const entityCount = allBorders.length;
    const entityType = borderData.states ? 'states' : 'countries';
    console.log(`Created ${totalSegments} border segments for ${entityCount} ${entityType}`);
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
 <span class="stat-value">${stats.bars?.toLocaleString() || 'N/A'}</span>
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
        const bucketSize = 1;
        xExtent = (gridWidth - 1) * bucketSize;
        zExtent = (gridHeight - 1) * bucketSize;
    } else {
        // Surface: PlaneGeometry is centered; treat width/height directly
        xExtent = gridWidth;
        zExtent = gridHeight;
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
    try { updateURLParameter('exag', internalToMultiplier(clampedValue)); } catch (_) { }
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
    try { updateURLParameter('exag', multiplier); } catch (_) { }
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
    camera.lookAt(0, 0, 0);

    controls.update();

    console.log(`Camera reset: fixed position (0, ${fixedHeight}, ${(fixedHeight * 0.001).toFixed(1)}) looking at origin`);
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
    // Space bar: Toggle auto-rotate
    else if (event.key === ' ') {
        event.preventDefault();
        params.autoRotate = !params.autoRotate;
        controls.autoRotate = params.autoRotate;
    }
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
        activeScheme.state.pinching
    );

    return isMovingKeyboard || isMovingMouse;
}

function updateFPS() {
    frameCount++;
    const currentTime = performance.now();
    if (currentTime >= lastTime + 1000) {
        const fps = Math.round((frameCount * 1000) / (currentTime - lastTime));
        const fpsEl = document.getElementById('fps-display');
        if (fpsEl) fpsEl.textContent = `FPS: ${fps}`;

        // Auto-reduce resolution if FPS is too low
        if (fps < 10 && fps > 0) {
            autoReduceResolution();
        }

        frameCount = 0;
        lastTime = currentTime;
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
    // Convert screen coordinates to normalized device coordinates (-1 to +1)
    const rect = renderer.domElement.getBoundingClientRect();
    const ndcX = ((screenX - rect.left) / rect.width) * 2 - 1;
    const ndcY = -((screenY - rect.top) / rect.height) * 2 + 1;

    // Set up raycaster
    raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), camera);
    // Prefer terrain intersection; fall back to ground plane
    if (terrainMesh) {
        const hits = raycaster.intersectObject(terrainMesh, true);
        if (hits && hits.length > 0) {
            const p = hits[0].point;
            return new THREE.Vector3(p.x, 0, p.z);
        }
    }
    const planeIntersect = new THREE.Vector3();
    const intersected = raycaster.ray.intersectPlane(groundPlane, planeIntersect);
    if (intersected) return planeIntersect;

    // Should never happen, but just in case
    console.warn('Raycast failed completely');
    return null;
}
function worldToLonLat(worldX, worldZ) {
    if (!rawElevationData || !processedData || !borderData) return null;
    const { bounds: elevBounds } = rawElevationData; // {left, right, top, bottom}
    const w = processedData.width;
    const h = processedData.height;
    let colNorm, rowNorm;
    if (params.renderMode === 'bars') {
        const bucket = params.bucketSize;
        const xMin = -(w - 1) * bucket / 2;
        const zMin = -(h - 1) * bucket / 2;
        const xMax = (w - 1) * bucket / 2;
        const zMax = (h - 1) * bucket / 2;
        colNorm = (worldX - xMin) / (xMax - xMin);
        rowNorm = (worldZ - zMin) / (zMax - zMin);
    } else if (params.renderMode === 'points') {
        const xMin = -(w - 1) / 2;
        const zMin = -(h - 1) / 2;
        const xMax = (w - 1) / 2;
        const zMax = (h - 1) / 2;
        colNorm = (worldX - xMin) / (xMax - xMin);
        rowNorm = (worldZ - zMin) / (zMax - zMin);
    } else {
        // surface
        colNorm = (worldX + w / 2) / (w);
        rowNorm = (worldZ + h / 2) / (h);
    }
    colNorm = Math.max(0, Math.min(1, colNorm));
    rowNorm = Math.max(0, Math.min(1, rowNorm));
    const lon = elevBounds.left + colNorm * (elevBounds.right - elevBounds.left);
    const lat = elevBounds.top - rowNorm * (elevBounds.top - elevBounds.bottom);
    return { lon, lat };
}

function worldToGridIndex(worldX, worldZ) {
    if (!processedData) return null;
    const w = processedData.width;
    const h = processedData.height;
    if (params.renderMode === 'bars') {
        const bucket = params.bucketSize;
        const originX = terrainMesh ? terrainMesh.position.x : -(w - 1) * bucket / 2;
        const originZ = terrainMesh ? terrainMesh.position.z : -(h - 1) * bucket / 2;
        let j = Math.round((worldX - originX) / bucket);
        let i = Math.round((worldZ - originZ) / bucket);
        i = Math.max(0, Math.min(h - 1, i));
        j = Math.max(0, Math.min(w - 1, j));
        return { i, j };
    } else if (params.renderMode === 'points') {
        const bucket = 1;
        const originX = terrainMesh ? terrainMesh.position.x : -(w - 1) * bucket / 2;
        const originZ = terrainMesh ? terrainMesh.position.z : -(h - 1) * bucket / 2;
        let j = Math.round((worldX - originX) / bucket);
        let i = Math.round((worldZ - originZ) / bucket);
        i = Math.max(0, Math.min(h - 1, i));
        j = Math.max(0, Math.min(w - 1, j));
        return { i, j };
    } else {
        // Surface centered at origin, each vertex spaced 1 unit
        let j = Math.round(worldX + w / 2);
        let i = Math.round(worldZ + h / 2);
        i = Math.max(0, Math.min(h - 1, i));
        j = Math.max(0, Math.min(w - 1, j));
        return { i, j };
    }
}

function updateCursorHUD(clientX, clientY) {
    const elevEl = document.getElementById('hud-elev');
    const slopeEl = document.getElementById('hud-slope');
    const aspectEl = document.getElementById('hud-aspect');
    const distEl = document.getElementById('hud-dist');
    if (!elevEl || !processedData) return;
    const world = raycastToWorld(clientX, clientY);
    if (!world) {
        elevEl.textContent = '--';
        if (slopeEl) slopeEl.textContent = '--';
        if (aspectEl) aspectEl.textContent = '--';
        if (distEl) distEl.textContent = '--';
        return;
    }
    // Ignore when cursor is outside data footprint
    if (!isWorldInsideData(world.x, world.z)) {
        elevEl.textContent = '--';
        if (slopeEl) slopeEl.textContent = '--';
        if (aspectEl) aspectEl.textContent = '--';
        if (distEl) {
            const dMetersEdge = computeDistanceToDataEdgeMeters(world.x, world.z);
            distEl.textContent = (dMetersEdge != null && isFinite(dMetersEdge)) ? formatDistance(dMetersEdge, (hudSettings && hudSettings.units) || 'metric') : '--';
        }
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
        if (distEl) {
            const dMetersEdge = computeDistanceToDataEdgeMeters(world.x, world.z);
            distEl.textContent = (dMetersEdge != null && isFinite(dMetersEdge)) ? formatDistance(dMetersEdge, (hudSettings && hudSettings.units) || 'metric') : '--';
        }
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
    if (distEl) {
        const dMeters = computeDistanceToNearestBorderMetersGeo(world.x, world.z);
        distEl.textContent = (dMeters != null && isFinite(dMeters)) ? formatDistance(dMeters, units) : '--';
    }
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
    const rowDist = document.getElementById('hud-row-dist');
    const rowRelief = document.getElementById('hud-row-relief');
    if (rowElev) rowElev.style.display = hudSettings.show.elevation ? '' : 'none';
    if (rowSlope) rowSlope.style.display = hudSettings.show.slope ? '' : 'none';
    if (rowAspect) rowAspect.style.display = hudSettings.show.aspect ? '' : 'none';
    if (rowDist) rowDist.style.display = hudSettings.show.distance ? '' : 'none';
    if (rowRelief) rowRelief.style.display = hudSettings.show.relief ? '' : 'none';
    const chkElev = document.getElementById('hud-show-elev');
    const chkSlope = document.getElementById('hud-show-slope');
    const chkAspect = document.getElementById('hud-show-aspect');
    const chkDist = document.getElementById('hud-show-dist');
    const chkRelief = document.getElementById('hud-show-relief');
    if (chkElev) chkElev.checked = !!hudSettings.show.elevation;
    if (chkSlope) chkSlope.checked = !!hudSettings.show.slope;
    if (chkAspect) chkAspect.checked = !!hudSettings.show.aspect;
    if (chkDist) chkDist.checked = !!hudSettings.show.distance;
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
        { id: 'hud-show-dist', key: 'distance' },
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
    const feet = meters * 3.280839895;
    if (units === 'metric') return `${Math.round(meters)} m`;
    if (units === 'imperial') return `${Math.round(feet)} ft`;
    return `${Math.round(meters)} m / ${Math.round(feet)} ft`;
}

function formatDistance(meters, units) {
    const miles = meters / 1609.344;
    const km = meters / 1000;
    if (units === 'metric') return km < 1 ? `${Math.round(meters)} m` : `${km.toFixed(2)} km`;
    if (units === 'imperial') return miles < 0.5 ? `${Math.round(meters * 3.280839895)} ft` : `${miles.toFixed(2)} mi`;
    const left = km < 1 ? `${Math.round(meters)} m` : `${km.toFixed(2)} km`;
    const right = miles < 0.5 ? `${Math.round(meters * 3.280839895)} ft` : `${miles.toFixed(2)} mi`;
    return `${left} / ${right}`;
}

function formatFootprint(metersX, metersY, units) {
    if (units === 'metric') {
        const kmX = metersX / 1000;
        const kmY = metersY / 1000;
        const fmtX = kmX < 1 ? `${Math.round(metersX)} m` : `${kmX.toFixed(2)} km`;
        const fmtY = kmY < 1 ? `${Math.round(metersY)} m` : `${kmY.toFixed(2)} km`;
        return `${fmtX} × ${fmtY}`;
    } else if (units === 'imperial') {
        const miX = metersX / 1609.344;
        const miY = metersY / 1609.344;
        const feetX = metersX * 3.280839895;
        const feetY = metersY * 3.280839895;
        const fmtX = miX < 0.5 ? `${Math.round(feetX)} ft` : `${miX.toFixed(2)} mi`;
        const fmtY = miY < 0.5 ? `${Math.round(feetY)} ft` : `${miY.toFixed(2)} mi`;
        return `${fmtX} × ${fmtY}`;
    } else { // 'both'
        const kmX = metersX / 1000;
        const kmY = metersY / 1000;
        const miX = metersX / 1609.344;
        const miY = metersY / 1609.344;
        const feetX = metersX * 3.280839895;
        const feetY = metersY * 3.280839895;
        const fmtXm = kmX < 1 ? `${Math.round(metersX)} m` : `${kmX.toFixed(2)} km`;
        const fmtYm = kmY < 1 ? `${Math.round(metersY)} m` : `${kmY.toFixed(2)} km`;
        const fmtXi = miX < 0.5 ? `${Math.round(feetX)} ft` : `${miX.toFixed(2)} mi`;
        const fmtYi = miY < 0.5 ? `${Math.round(feetY)} ft` : `${miY.toFixed(2)} mi`;
        return `${fmtXm} × ${fmtYm} / ${fmtXi} × ${fmtYi}`;
    }
}

function formatPixelSize(meters) {
    // Format pixel size with km if >1000m, one decimal point only
    if (meters >= 1000) {
        return `${(meters / 1000).toFixed(1)}km`;
    } else {
        return `${meters.toFixed(1)}m`;
    }
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
    if (!processedData) return { mx: 1, mz: 1 };
    if (params.renderMode === 'bars') {
        const mx = (processedData.bucketSizeMetersX || 1) / (params.bucketSize || 1);
        const mz = (processedData.bucketSizeMetersY || 1) / (params.bucketSize || 1);
        return { mx, mz };
    } else {
        const mx = processedData.bucketSizeMetersX || 1;
        const mz = processedData.bucketSizeMetersY || 1;
        return { mx, mz };
    }
}

function computeDistanceToNearestBorderMetersGeo(worldX, worldZ) {
    if (!rawElevationData) return null;
    if (!borderSegmentsGeo || borderSegmentsGeo.length === 0) {
        return computeDistanceToDataEdgeMeters(worldX, worldZ);
    }
    const ll = worldToLonLat(worldX, worldZ);
    if (!ll) return null;
    const { lon, lat } = ll;
    // Query spatial index (cell + neighbors)
    const ix = Math.floor(lon / borderGeoCellSizeDeg);
    const iy = Math.floor(lat / borderGeoCellSizeDeg);
    let candidates = new Set();
    for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
            const key = `${ix + dx},${iy + dy}`;
            const arr = borderGeoIndex && borderGeoIndex.get(key);
            if (arr) arr.forEach(id => candidates.add(id));
        }
    }
    if (candidates.size === 0) {
        // Fallback: widen search radius (two-ring)
        for (let dx = -2; dx <= 2; dx++) {
            for (let dy = -2; dy <= 2; dy++) {
                const key = `${ix + dx},${iy + dy}`;
                const arr = borderGeoIndex && borderGeoIndex.get(key);
                if (arr) arr.forEach(id => candidates.add(id));
            }
        }
    }
    if (candidates.size === 0) {
        // Fallback to data edge distance if no nearby border segments
        return computeDistanceToDataEdgeMeters(worldX, worldZ);
    }
    // Local meters per degree at this latitude (equirectangular approximation)
    const metersPerDegX = 111320 * Math.cos(lat * Math.PI / 180);
    const metersPerDegY = 110574; // average meridional
    const px = 0, py = 0; // we'll translate lon/lat to a local tangent plane centered at (lon, lat)
    let best = Infinity;
    for (const id of candidates) {
        const seg = borderSegmentsGeo[id];
        // Convert to local meters
        const ax = (seg.axLon - lon) * metersPerDegX;
        const ay = (seg.axLat - lat) * metersPerDegY;
        const bx = (seg.bxLon - lon) * metersPerDegX;
        const by = (seg.bxLat - lat) * metersPerDegY;
        const d = distancePointToSegment2D(px, py, ax, ay, bx, by);
        if (d < best) best = d;
    }
    return isFinite(best) ? best : null;
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
    const vx = bx - ax;
    const vz = bz - az;
    const wx = px - ax;
    const wz = pz - az;
    const c1 = vx * wx + vz * wz;
    if (c1 <= 0) return Math.hypot(px - ax, pz - az);
    const c2 = vx * vx + vz * vz;
    if (c2 <= c1) return Math.hypot(px - bx, pz - bz);
    const t = c1 / c2;
    const projx = ax + t * vx;
    const projz = az + t * vz;
    return Math.hypot(px - projx, pz - projz);
}

function isWorldInsideData(worldX, worldZ) {
    if (!processedData) return false;
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
    return (worldX >= xMin && worldX <= xMax && worldZ >= zMin && worldZ <= zMax);
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
    url.searchParams.set(key, value);
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

