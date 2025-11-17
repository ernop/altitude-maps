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
 * - terrain-renderer.js          → Terrain geometry creation (bars mode only)
 * - map-shading.js              → Visual appearance (colors, materials, lighting)
 * - compass-rose.js            → Edge markers + click handling (extends edge-markers.js)
 * - edge-markers.js              → Directional markers (N/E/S/W labels at terrain edges) - marker creation only
 * - format-utils.js              → Data formatting (units, distances, file sizes)
 * - geometry-utils.js            → Spatial calculations and coordinate conversions
 * - ground-plane-camera.js       → Ground plane camera system (default)
 * - ground-plane-google-earth.js → Google Earth camera variant
 * - keyboard-shortcuts.js        → Global keyboard shortcuts (R for reset, +/- for resolution)
 * - resolution-controls.js       → Resolution slider, bucket size presets (MAX/DEFAULT)
 * - state-connectivity.js        → Region adjacency and connectivity visualization
 * - hud-system.js                 → HUD overlay system (dragging, position, settings, content updates)
 * - ui-controls-manager.js       → UI control setup and event binding (region selector, render mode, vertical exaggeration, color scheme)
 * - ui-loading.js                → Loading screen and progress bar management
 * 
 * This main file handles:
 * - Application initialization and lifecycle
 * - Scene setup (Three.js renderer, camera, lights)
 * - Terrain rendering (bars mode only)
 * - UI event handling and state management
 * - Region loading and data processing
 * - HUD updates and user interactions
 * 
 * Design principle: Keep thin wrapper functions here that delegate to modules.
 * Avoid duplication - each function should have a single source of truth.
 */

// Version tracking
const VIEWER_VERSION = '1.369';

// RegionType enum is defined in state-connectivity.js (loaded before this file)
// Values: RegionType.USA_STATE, RegionType.COUNTRY, RegionType.AREA

// All console logs use plain ASCII - no sanitizer needed

//-------CORE THREE.JS STATE-------
let scene, camera, renderer, controls;
let terrainMesh, terrainGroup, gridHelper;
let raycaster;
let groundPlane;
let edgeMarkers = []; // N/E/S/W markers (must not move with vertical exaggeration changes)
const __tmpColor = new THREE.Color(); // Reused to avoid per-vertex allocations

// Expose core Three.js state on window for modules
window.scene = null; // Will be set in setupScene()
window.camera = null; // Will be set in setupScene()
window.renderer = null; // Will be set in setupScene()
window.controls = null; // Will be set in setupScene()
window.terrainMesh = null;
window.terrainGroup = null;
window.edgeMarkers = edgeMarkers;
window.raycaster = null; // Will be set in setupScene()

//-------DATA STATE-------
let rawElevationData;
let processedData;
let derivedSlopeDeg = null;
let derivedAspectDeg = null;
let trueScaleValue = null;
// Cache for bucketed data by bucket size (key: bucketSize, value: processedData object)
// This allows instant bucket size changes without recomputation
let bucketedDataCache = {};

// Expose data state on window for modules
window.processedData = null; // Will be set when data loads
window.rawElevationData = null; // Will be set when data loads
window.derivedSlopeDeg = null;
window.derivedAspectDeg = null;

//-------REGION STATE-------
const MAX_RECENT_REGIONS = 12;
const DEFAULT_REGION = 'california';
let recentRegions = [];
let regionsManifest = null;
let currentRegionId = null;
let regionAdjacency = null;
let globalElevationStats = null; // Global min/max for global scale mode

// Expose global stats on window for modules
window.globalElevationStats = null;

//-------UI STATE-------
let currentMouseX, currentMouseY;
let hudSettings = null;
let isCurrentlyLoading = false;

//-------PERFORMANCE TRACKING-------
let terrainStats = {};
let frameCount = 0;
let lastFpsUpdateTime = performance.now();

// Expose performance tracking on window for modules
window.terrainStats = terrainStats;

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

//-------TERRAIN STATE-------
let barsInstancedMesh = null;
let barsIndexToRow = null;
let barsIndexToCol = null;
let barsTileSize = 0;
const barsDummy = new THREE.Object3D();
let pendingVertExagRaf = null;
let pendingBucketTimeout = null;
let lastBarsExaggerationInternal = null;
let lastAutoResolutionAdjustTime = 0;

// Expose terrain state on window for modules
window.barsInstancedMesh = null;
window.barsIndexToRow = null;
window.barsIndexToCol = null;
window.barsTileSize = 0;
window.barsDummy = barsDummy;
window.lastBarsExaggerationInternal = null;
window.lastBarsTileSize = null;

//-------PARAMETERS-------
let     params = {
    bucketSize: 4, // Integer multiplier of pixel spacing (1x, 2x, 3x, etc.)
    aggregation: 'max', // Always 'max' - highest point in each bucket
    renderMode: 'bars',
    verticalExaggeration: 0.04, // Default: good balance of detail and scale
    colorScheme: 'high-contrast',
    showGrid: false,
    autoRotate: false,
    // Shading: Always use Natural (Lambert) - no UI control needed
    colorGamma: 1.0,
    useGlobalScale: false // Default: per-region auto-scaling
};

// Expose params on window for modules
window.params = params;

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

    // Tile gap always 0%, aggregation always 'max' - no URL params needed

    // Only bars mode is supported - ignore renderMode URL param
    params.renderMode = 'bars';

    const ex = getFloat('exag', 1, 100);
    if (ex !== null) params.verticalExaggeration = multiplierToInternal(ex);

    const cs = getStr('colorScheme');
    if (cs) params.colorScheme = cs;

    const gamma = getFloat('gamma', 0.5, 2.0);
    if (gamma !== null) params.colorGamma = gamma;

    // Camera state parameters
    const cx = getFloat('cx');
    const cy = getFloat('cy');
    const cz = getFloat('cz');
    const fx = getFloat('fx');
    const fy = getFloat('fy');
    const fz = getFloat('fz');
    const rx = getFloat('rx');
    const ry = getFloat('ry');
    const rz = getFloat('rz');

    // Store camera state from URL (will be applied after scene setup)
    if (cx !== null && cy !== null && cz !== null) {
        window.urlCameraState = {
            position: { x: cx, y: cy, z: cz },
            focus: {
                x: fx !== null ? fx : 0,
                y: fy !== null ? fy : 0,
                z: fz !== null ? fz : 0
            },
            terrainRotation: {
                x: rx !== null ? rx : 0,
                y: ry !== null ? ry : 0,
                z: rz !== null ? rz : 0
            }
        };
        console.log('[applyParamsFromURL] Camera state found in URL:', window.urlCameraState);
    }
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
                try { appendActivityLog(args.join(' ')); } catch (_) { }
            };
            console.warn = (...args) => { try { appendActivityLog(args.join(' ')); } catch (_) { } origWarn(...args); };
            console.error = (...args) => { try { appendActivityLog(args.join(' ')); } catch (_) { } origError(...args); };
            window.__consolePatched = true;
        }

        document.getElementById('version-display').textContent = `v${VIEWER_VERSION}`;
        appendActivityLog(`Altitude Maps Viewer v${VIEWER_VERSION}`);

        const firstRegionId = await populateRegionSelector();

        await loadStateAdjacency();

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
        
        // Initialize shortcuts overlay
        initShortcutsOverlay();
        
        // Rebuild dropdown for initial interaction (uses rebuildRegionDropdown function)
        rebuildRegionDropdown();

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

async function loadElevationData(url) {
    const gzUrl = url.endsWith('.json') ? url + '.gz' : url;
    if (!gzUrl.endsWith('.gz')) {
        throw new Error(`Elevation data URL must end with .json or .gz, got: ${url}`);
    }
    const tStart = performance.now();
    
    // Force fresh fetch - no browser caching allowed
    const response = await fetch(gzUrl, {
        cache: 'no-store',
        headers: {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    });

    if (!response.ok) {
        throw new Error(`Failed to load elevation data. HTTP ${response.status} ${response.statusText} for ${gzUrl}`);
    }

    const filename = gzUrl.split('/').pop();
    const arrayBuffer = await response.arrayBuffer();
    const stream = new DecompressionStream('gzip');
    const writer = stream.writable.getWriter();
    writer.write(new Uint8Array(arrayBuffer));
    writer.close();
    const decompressedResponse = new Response(stream.readable);
    const text = await decompressedResponse.text();
    const data = JSON.parse(text);

    const versionMatch = filename.match(/_v(\d+)\.json/);
    const fileVersion = versionMatch ? versionMatch[1] : 'unknown';
    appendActivityLog(`[OK] Data format v${fileVersion} from filename`);

    try { window.ActivityLog.logResourceTiming(gzUrl, 'Loaded JSON', tStart, performance.now()); } catch (e) { }
    return data;
}

/**
 * Compute global elevation statistics across all regions
 * Used for global scale mode to ensure consistent color mapping
 * @param {Object} manifest - Regions manifest object
 */
function computeGlobalElevationStats(manifest) {
    if (!manifest || !manifest.regions) {
        console.warn('[computeGlobalElevationStats] No regions in manifest');
        return;
    }

    let globalMin = Infinity;
    let globalMax = -Infinity;
    let globalAutoLow = Infinity;
    let globalAutoHigh = -Infinity;
    let regionsProcessed = 0;
    let regionsWithAutoStats = 0;

    for (const [regionId, regionInfo] of Object.entries(manifest.regions)) {
        if (regionInfo.stats) {
            regionsProcessed++;
            
            // Track min/max
            if (typeof regionInfo.stats.min === 'number') {
                globalMin = Math.min(globalMin, regionInfo.stats.min);
            }
            if (typeof regionInfo.stats.max === 'number') {
                globalMax = Math.max(globalMax, regionInfo.stats.max);
            }
            
            // Track auto-stretch percentiles if available
            if (typeof regionInfo.stats.autoLow === 'number' && typeof regionInfo.stats.autoHigh === 'number') {
                regionsWithAutoStats++;
                globalAutoLow = Math.min(globalAutoLow, regionInfo.stats.autoLow);
                globalAutoHigh = Math.max(globalAutoHigh, regionInfo.stats.autoHigh);
            }
        }
    }

    // Only set if we found valid data
    if (regionsProcessed > 0 && isFinite(globalMin) && isFinite(globalMax)) {
        globalElevationStats = {
            min: globalMin,
            max: globalMax,
            autoLow: isFinite(globalAutoLow) ? globalAutoLow : globalMin,
            autoHigh: isFinite(globalAutoHigh) ? globalAutoHigh : globalMax,
            regionsProcessed,
            regionsWithAutoStats
        };
        
        // Expose on window for modules
        window.globalElevationStats = globalElevationStats;
        
        console.log('[computeGlobalElevationStats] ======== GLOBAL ELEVATION STATS ========');
        console.log(`  Min elevation: ${globalMin.toFixed(1)}m`);
        console.log(`  Max elevation: ${globalMax.toFixed(1)}m`);
        console.log(`  Auto-stretch low: ${globalElevationStats.autoLow.toFixed(1)}m`);
        console.log(`  Auto-stretch high: ${globalElevationStats.autoHigh.toFixed(1)}m`);
        console.log(`  Regions processed: ${regionsProcessed}`);
        console.log(`  Regions with auto-stretch: ${regionsWithAutoStats}`);
    } else {
        console.warn('[computeGlobalElevationStats] Failed to compute valid global stats');
    }
}

async function loadRegionsManifest() {
    const manifestUrl = `generated/regions/regions_manifest.json.gz?v=${VIEWER_VERSION}`;
    const tStart = performance.now();
    
    console.log(`[loadRegionsManifest] ======== LOADING MANIFEST ========`);
    console.log(`[loadRegionsManifest] URL: ${manifestUrl}`);
    
    // Force fresh fetch - no browser caching allowed
    const response = await fetch(manifestUrl, {
        cache: 'no-store',
        headers: {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    });

    if (!response.ok) {
        throw new Error(`Failed to load regions manifest. HTTP ${response.status} ${response.statusText} for ${manifestUrl}`);
    }

    const arrayBuffer = await response.arrayBuffer();
    const stream = new DecompressionStream('gzip');
    const writer = stream.writable.getWriter();
    writer.write(new Uint8Array(arrayBuffer));
    writer.close();
    const decompressedResponse = new Response(stream.readable);
    const text = await decompressedResponse.text();
    const json = JSON.parse(text);

    console.log(`[loadRegionsManifest] Successfully loaded from: ${manifestUrl}`);
    try { window.ActivityLog.logResourceTiming(manifestUrl, 'Loaded manifest', tStart, performance.now()); } catch (e) { }
    
    // Log detailed manifest statistics
    const totalRegions = Object.keys(json?.regions || {}).length;
    console.log(`[loadRegionsManifest] ======== MANIFEST LOADED ========`);
    console.log(`[loadRegionsManifest] Total regions in manifest: ${totalRegions}`);
    console.log(`[loadRegionsManifest] Manifest version: ${json?.version || 'unknown'}`);
    
    // Count by regionType
    const typeCounts = {};
    const samplesByType = {};
    
    for (const [regionId, regionInfo] of Object.entries(json?.regions || {})) {
        const regionType = regionInfo.regionType || 'undefined';
        typeCounts[regionType] = (typeCounts[regionType] || 0) + 1;
        
        if (!samplesByType[regionType]) {
            samplesByType[regionType] = [];
        }
        if (samplesByType[regionType].length < 3) {
            samplesByType[regionType].push({ id: regionId, name: regionInfo.name });
        }
    }
    
    console.log(`[loadRegionsManifest] ======== REGION TYPE COUNTS ========`);
    Object.entries(typeCounts).sort((a, b) => b[1] - a[1]).forEach(([type, count]) => {
        console.log(`  ${type}: ${count} regions`);
        console.log(`    Samples: ${samplesByType[type].map(r => r.name).join(', ')}`);
    });
    
    // Check for any regions without files
    const missingFiles = [];
    for (const [regionId, regionInfo] of Object.entries(json?.regions || {})) {
        if (!regionInfo.file) {
            missingFiles.push(regionId);
        }
    }
    
    if (missingFiles.length > 0) {
        console.warn(`[loadRegionsManifest] ${missingFiles.length} regions without file paths:`, missingFiles);
    } else {
        console.log(`[loadRegionsManifest] All regions have file paths`);
    }
    
    console.log(`[loadRegionsManifest] ======== MANIFEST READY ========`);
    
    // Compute global elevation statistics for global scale mode
    computeGlobalElevationStats(json);
    
    return json;
}

async function loadAdjacencyData() {
    const gzUrl = `generated/regions/region_adjacency.json.gz?v=${VIEWER_VERSION}`;
    console.log(`[loadAdjacencyData] Loading from: ${gzUrl}`);
    
    // Force fresh fetch - no browser caching allowed
    const response = await fetch(gzUrl, {
        cache: 'no-store',
        headers: {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    });

    if (!response.ok) {
        throw new Error(`Failed to load region adjacency data. HTTP ${response.status} ${response.statusText} for ${gzUrl}`);
    }

    const arrayBuffer = await response.arrayBuffer();
    const stream = new DecompressionStream('gzip');
    const writer = stream.writable.getWriter();
    writer.write(new Uint8Array(arrayBuffer));
    writer.close();
    const decompressedResponse = new Response(stream.readable);
    const text = await decompressedResponse.text();
    console.log(`[loadAdjacencyData] Successfully loaded from: ${gzUrl}`);
    return JSON.parse(text);
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

function buildRegionOptions() {
    // Use window.regionsManifest if available (for ui-controls-manager.js), otherwise fall back to local variable
    const manifest = window.regionsManifest || regionsManifest;
    if (!manifest || !manifest.regions) {
        console.warn('[buildRegionOptions] No manifest available');
        return [];
    }

    const totalRegions = Object.keys(manifest.regions).length;
    console.log(`[buildRegionOptions] ======== STARTING REGION GROUPING ========`);
    console.log(`[buildRegionOptions] Total regions in manifest: ${totalRegions}`);

    // Group regions by their RegionType enum value
    const regionTypeGroups = {
        [RegionType.COUNTRY]: { header: 'COUNTRIES', regions: [] },
        [RegionType.AREA]: { header: 'AREAS', regions: [] },
        [RegionType.USA_STATE]: { header: 'US STATES', regions: [] }
    };

    // Track for detailed logging
    const classificationLog = [];

    for (const [regionId, regionInfo] of Object.entries(manifest.regions)) {
        let regionType = regionInfo.regionType;
        
        // Validate regionType is one of the enum values
        if (regionType !== RegionType.USA_STATE && 
            regionType !== RegionType.COUNTRY && 
            regionType !== RegionType.AREA) {
            console.error(`[buildRegionOptions] Invalid regionType for ${regionId}: "${regionType}". Must be one of: ${Object.values(RegionType).join(', ')}`);
            // Default to AREA for invalid values
            regionType = RegionType.AREA;
        }
        
        regionTypeGroups[regionType].regions.push({ id: regionId, name: regionInfo.name });
        
        // Log every single region
        classificationLog.push({
            id: regionId,
            name: regionInfo.name,
            regionType: regionType,
            hasFile: !!regionInfo.file
        });
    }

    // Log detailed classification info
    console.log(`[buildRegionOptions] ======== REGION CLASSIFICATION DETAILS ========`);
    console.table(classificationLog);
    
    console.log(`[buildRegionOptions] ======== GROUP COUNTS ========`);
    console.log(`  COUNTRIES: ${regionTypeGroups[RegionType.COUNTRY].regions.length} regions`);
    console.log(`  AREAS: ${regionTypeGroups[RegionType.AREA].regions.length} regions`);
    console.log(`  USA STATES: ${regionTypeGroups[RegionType.USA_STATE].regions.length} regions`);
    
    // Log sample regions from each group
    console.log(`[buildRegionOptions] ======== SAMPLE REGIONS PER GROUP ========`);
    Object.values(RegionType).forEach(regionType => {
        const samples = regionTypeGroups[regionType].regions.slice(0, 3);
        console.log(`  ${regionType.toUpperCase()}: ${samples.map(r => r.name).join(', ')}${regionTypeGroups[regionType].regions.length > 3 ? '...' : ''}`);
    });

    const options = [];
    // Order: COUNTRY, AREA, USA_STATE
    const typeOrder = [RegionType.COUNTRY, RegionType.AREA, RegionType.USA_STATE];
    const groups = typeOrder.map(type => regionTypeGroups[type]).filter(g => g.regions.length > 0);

    console.log(`[buildRegionOptions] ======== BUILDING DROPDOWN OPTIONS ========`);
    console.log(`  Number of groups (should be 3): ${groups.length}`);
    console.log(`  Groups that will be shown: ${groups.map(g => g.header).join(', ')}`);

    groups.forEach((group, index) => {
        group.regions.sort((a, b) => a.name.localeCompare(b.name));
        options.push({ id: '__header__', name: group.header });
        group.regions.forEach(({ id, name }) => {
            options.push({ id, name });
        });
        if (index < groups.length - 1) {
            options.push({ id: '__divider__', name: '' });
        }
    });

    console.log(`[buildRegionOptions] Total dropdown options created: ${options.length} (includes headers, dividers, regions)`);
    console.log(`[buildRegionOptions] ======== REGION GROUPING COMPLETE ========`);

    return options;
}

// Expose buildRegionOptions on window for ui-controls-manager.js
window.buildRegionOptions = buildRegionOptions;

function rebuildRegionDropdown() {
    if (!regionsManifest || !regionsManifest.regions) return;

    regionOptions = buildRegionOptions();
    window.regionOptions = regionOptions;

    // Rebuild the DOM dropdown
    const dropdown = document.getElementById('regionDropdown');
    if (dropdown) {
        dropdown.innerHTML = '';
        regionOptions.forEach((opt) => {
            if (opt.id === '__divider__') {
                const div = document.createElement('div');
                div.setAttribute('data-divider', 'true');
                div.className = 'region-dropdown-divider';
                dropdown.appendChild(div);
                return;
            }
            if (opt.id === '__header__') {
                const header = document.createElement('div');
                header.setAttribute('data-header', 'true');
                header.textContent = opt.name;
                header.className = 'region-dropdown-header';
                dropdown.appendChild(header);
                return;
            }
            const row = document.createElement('div');
            row.textContent = opt.name;
            row.setAttribute('data-id', opt.id);
            row.className = 'region-dropdown-item';

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

    console.log('[populateRegionSelector] ======== POPULATING REGION SELECTOR ========');
    
    regionsManifest = await loadRegionsManifest();
    window.regionsManifest = regionsManifest; // Expose for ui-controls-manager.js
    
    console.log('[populateRegionSelector] Loading adjacency data...');
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

    console.log('[populateRegionSelector] Building region name maps...');
    // Build maps first (needed for all regions)
    regionIdToName = {};
    regionNameToId = {};
    for (const [regionId, regionInfo] of Object.entries(regionsManifest.regions)) {
        regionIdToName[regionId] = regionInfo.name;
        regionNameToId[regionInfo.name.toLowerCase()] = regionId;
    }

    console.log('[populateRegionSelector] Building region options for dropdown...');
    regionOptions = buildRegionOptions();
    window.regionOptions = regionOptions;

    // Update recent regions UI now that manifest and maps are ready
    updateRecentRegionsList();

    console.log('[populateRegionSelector] ======== DETERMINING INITIAL REGION ========');
    // Determine which region to load initially
    // Priority: URL parameter > DEFAULT_REGION > localStorage > first region
    let firstRegionId;

    if (urlRegion && regionsManifest.regions[urlRegion]) {
        // URL parameter takes highest priority (e.g., ?region=ohio)
        firstRegionId = urlRegion;
        console.log(`[populateRegionSelector] Loading region from URL: ${urlRegion}`);
    } else if (regionsManifest.regions[DEFAULT_REGION]) {
        firstRegionId = DEFAULT_REGION;
        console.log(`[populateRegionSelector] Loading default region: ${DEFAULT_REGION}`);
    } else if (lastRegion && regionsManifest.regions[lastRegion]) {
        // Remember last viewed region from localStorage
        firstRegionId = lastRegion;
        console.log(`[populateRegionSelector] Loading last viewed region: ${lastRegion}`);
    } else {
        // Fallback to first available region
        firstRegionId = Object.keys(regionsManifest.regions)[0];
        console.log(`[populateRegionSelector] Loading first available region: ${firstRegionId}`);
    }

    if (inputEl) {
        inputEl.value = regionIdToName[firstRegionId] || firstRegionId;
    }
    currentRegionId = firstRegionId;
    updateRegionInfo(firstRegionId);

    console.log('[populateRegionSelector] ======== REGION SELECTOR READY ========');
    console.log(`[populateRegionSelector] Initial region: ${firstRegionId} (${regionIdToName[firstRegionId]})`);

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
    if (!regionId || !regionsManifest?.regions[regionId]) {
        regionId = regionsManifest?.regions[DEFAULT_REGION] ? DEFAULT_REGION : Object.keys(regionsManifest?.regions || {})[0];
        if (!regionId) {
            throw new Error('No regions available');
        }
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

        rawElevationData = await loadElevationData(dataUrl);
        window.rawElevationData = rawElevationData; // Sync to window
        currentRegionId = regionId;
        updateRegionInfo(regionId);

        // Clear bucketed data cache when loading new region
        bucketedDataCache = {};
        console.log('[BUCKETING] Cleared cache for new region');

        // Calculate true scale for this data
        // CRITICAL: Preserve the user's multiplier choice across region changes
        // Store the current multiplier before recalculating trueScaleValue
        const oldTrueScale = trueScaleValue;
        const currentMultiplier = oldTrueScale !== null ? params.verticalExaggeration / oldTrueScale : null;
        
        const scale = calculateRealWorldScale();
        trueScaleValue = 1.0 / scale.metersPerPixelX;
        console.log(`True scale for this region: ${trueScaleValue.toFixed(6)}x`);
        
        // If we had a previous multiplier, apply it to the new trueScaleValue
        // This keeps the user's chosen "10x" at 10x even when switching regions
        if (currentMultiplier !== null && currentMultiplier > 0) {
            params.verticalExaggeration = trueScaleValue * currentMultiplier;
            console.log(`Preserved vertical exaggeration multiplier: ${currentMultiplier.toFixed(1)}x`);
            
            // Update URL to reflect preserved multiplier
            try { 
                updateURLParameter('exag', currentMultiplier); 
            } catch (_) { }
        }

        // Update button highlighting now that trueScaleValue is known
        updateVertExagButtons(params.verticalExaggeration);

        // Save to localStorage so we remember this region next time
        localStorage.setItem('lastViewedRegion', regionId);

        // Add to recent regions list
        addToRecentRegions(regionId);

        // Update recent regions UI to reflect new order
        updateRecentRegionsList();

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
        window.edgeMarkers = edgeMarkers; // Sync to window

        // Processing steps with detailed progress tracking
        let stepStart;

        updateLoadingProgress(20, 1, 1, 'Auto-adjusting resolution...');
        stepStart = performance.now();
        // autoAdjustBucketSize() calls rebucketData() + recreateTerrain() internally
        // No need to call them again after this
        // Pass false to NOT preserve old rotation when loading new region
        autoAdjustBucketSize(false);
        console.log(`autoAdjustBucketSize: ${(performance.now() - stepStart).toFixed(1)}ms (includes rebucket + terrain creation)`);

        // Pregenerate common bucket sizes for instant switching (after initial bucketing)
        // Do this asynchronously so it doesn't block the UI
        setTimeout(() => {
            pregenerateCommonBucketSizes();
        }, 100);

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

        // Apply camera state from URL if present, otherwise reframe to default view
        if (window.urlCameraState) {
            console.log('[loadRegionData] Applying camera state from URL');
            applyCameraStateFromURL();
        } else {
            // Reset camera for new terrain size
            resetCamera();

            // Automatically reframe view (equivalent to F key) if camera scheme supports it
            if (activeScheme && activeScheme.reframeView) {
                activeScheme.reframeView();
            }
        }

        hideLoading();
        
        // Verify HUD visibility state after region loads
        if (window.HUDSystem && typeof window.HUDSystem.verifyState === 'function') {
            setTimeout(() => {
                window.HUDSystem.verifyState();
            }, 100);
        }
        appendActivityLog(`Loaded ${regionId}`);
        try { logSignificant(`Region loaded: ${regionId}`); } catch (_) { }

        // Create connectivity labels for US states
        // This is called AFTER camera setup so labels are positioned correctly
        if (typeof createConnectivityLabels === 'function') {
            console.log('[Connectivity] Calling createConnectivityLabels() after camera setup');
            if (window.terrainGroup) {
                console.log(`[Connectivity] terrainGroup rotation: (${window.terrainGroup.rotation.x.toFixed(3)}, ${window.terrainGroup.rotation.y.toFixed(3)}, ${window.terrainGroup.rotation.z.toFixed(3)})`);
            }
            console.log(`[Connectivity] processedData dimensions: ${processedData.width}x${processedData.height}`);
            try {
                createConnectivityLabels();
            } catch (error) {
                console.error('[Connectivity] Error creating labels:', error);
            }
        } else {
            console.warn('[Connectivity] createConnectivityLabels function not available');
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

    // Tile gap always 0% - no UI needed

    // Vertical exaggeration - sync both slider and input (convert to multiplier for display)
    const multiplier = internalToMultiplier(params.verticalExaggeration);
    document.getElementById('vertExag').value = multiplier;
    document.getElementById('vertExagInput').value = multiplier;

    // Update button highlighting
    updateVertExagButtons(params.verticalExaggeration);

    // Render mode (always bars)
    const renderModeSelect = document.getElementById('renderMode');
    if (renderModeSelect) renderModeSelect.value = 'bars';

    // Aggregation always 'max' - no UI needed

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

/**
 * Compute bucketed data for a specific bucket size (internal function)
 * Always uses 'max' aggregation (highest point in each bucket)
 * @param {number} bucketSize - Bucket size multiplier
 * @returns {Object} Processed data with bucketed elevation grid
 */
function computeBucketedData(bucketSize) {
    const { width, height, elevation } = rawElevationData;

    // Calculate real-world scale
    const scale = calculateRealWorldScale();

    // Calculate bucketed dimensions (simple integer division)
    const bucketedWidth = Math.floor(width / bucketSize);
    const bucketedHeight = Math.floor(height / bucketSize);

    // Bucket physical size = pixel spacing x multiplier
    const bucketSizeMetersX = scale.metersPerPixelX * bucketSize;
    const bucketSizeMetersY = scale.metersPerPixelY * bucketSize;

    // Pre-allocate array for better performance
    const bucketedElevation = new Array(bucketedHeight);

    // Pre-allocate buffer for collecting values
    const maxBucketPixels = Math.ceil(bucketSize * bucketSize * 1.5); // 1.5x safety margin
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

            // Always use 'max' aggregation (highest point in bucket)
            // BOUNDARY PRESERVATION: Only create a bar if enough pixels in the bucket are valid
            // This preserves clipped state/country boundaries during bucketing
            let value = null;
            const maxPossiblePixels = bucketSize * bucketSize;
            const validPixelRatio = count / maxPossiblePixels;
            
            // Require at least 50% of bucket pixels to be valid (not None/nodata)
            // This prevents "healing" of clipped boundaries where edge buckets
            // would otherwise fill in with aggregated values from sparse valid pixels
            if (validPixelRatio >= 0.5) {
                value = buffer[0];
                for (let i = 1; i < count; i++) {
                    if (buffer[i] > value) value = buffer[i];
                }
            }

            row[bx] = value;
        }
        bucketedElevation[by] = row;
    }

    // Count None values to verify boundary preservation
    let noneCount = 0;
    let validCount = 0;
    for (let by = 0; by < bucketedHeight; by++) {
        for (let bx = 0; bx < bucketedWidth; bx++) {
            if (bucketedElevation[by][bx] === null || bucketedElevation[by][bx] === undefined) {
                noneCount++;
            } else {
                validCount++;
            }
        }
    }
    const totalBuckets = bucketedWidth * bucketedHeight;
    const nonePercentage = (100 * noneCount / totalBuckets).toFixed(2);
    
    console.log(`[BUCKETING] Boundary preservation: ${noneCount.toLocaleString()} None buckets (${nonePercentage}% of ${totalBuckets.toLocaleString()} total)`);

    return {
        width: bucketedWidth,
        height: bucketedHeight,
        elevation: bucketedElevation,
        stats: rawElevationData.stats,
        bucketSizeMetersX: bucketSizeMetersX,
        bucketSizeMetersY: bucketSizeMetersY
    };
}

/**
 * Rebucket data using cache for instant bucket size changes
 * Checks cache first, computes if needed, stores result for future use
 */
function rebucketData() {
    const startTime = performance.now();
    const stack = new Error().stack;
    const caller = stack.split('\n')[2]?.trim() || 'unknown';
    console.log(`[BUCKETING] rebucketData() called from: ${caller}`);

    if (!rawElevationData) {
        console.warn('[BUCKETING] No raw elevation data available');
        return;
    }

    const bucketSize = params.bucketSize;
    const cacheKey = `${bucketSize}`; // No aggregation in key since always 'max'

    // Check cache first
    if (bucketedDataCache[cacheKey]) {
        processedData = bucketedDataCache[cacheKey];
        window.processedData = processedData; // Sync to window
        computeDerivedGrids();
        computeAutoStretchStats();
        
        // Update color legend if using derived color schemes (aspect/slope)
        if (params.colorScheme === 'aspect' || params.colorScheme === 'slope') {
            if (typeof updateColorLegend === 'function') {
                updateColorLegend();
            }
        }
        
        const duration = (performance.now() - startTime).toFixed(2);
        appendActivityLog(`Bucketing ${bucketSize}x (cached) in ${duration}ms`);
        updateResolutionInfo();
        return;
    }

    // Not in cache - compute it
    appendActivityLog(`Bucketing with multiplier ${bucketSize}x (max aggregation)`);
    const { width, height } = rawElevationData;

    processedData = computeBucketedData(bucketSize);
    window.processedData = processedData; // Sync to window

    // Store in cache for future use
    bucketedDataCache[cacheKey] = processedData;

    computeDerivedGrids();
    computeAutoStretchStats();

    // Update color legend if using derived color schemes (aspect/slope)
    if (params.colorScheme === 'aspect' || params.colorScheme === 'slope') {
        if (typeof updateColorLegend === 'function') {
            updateColorLegend();
        }
    }

    const duration = (performance.now() - startTime).toFixed(2);
    const bucketedWidth = processedData.width;
    const bucketedHeight = processedData.height;
    const reduction = (100 * (1 - (bucketedWidth * bucketedHeight) / (width * height))).toFixed(1);
    appendActivityLog(`Bucketed to ${bucketedWidth}x${bucketedHeight} (${reduction}% reduction) in ${duration}ms`);

    // Update Resolution header with footprint and rectangle count
    updateResolutionInfo();
}

/**
 * Pregenerate common bucket sizes for instant switching
 * Common sizes: 1, 2, 3, 4, 5, 6, 7, 8, 16, 32
 * Also generates current optimal size if not in common list
 */
function pregenerateCommonBucketSizes() {
    if (!rawElevationData) {
        console.warn('[BUCKETING] Cannot pregenerate: no raw elevation data');
        return;
    }

    const commonSizes = [1, 2, 3, 4, 5, 6, 7, 8, 16, 32];
    const currentSize = params.bucketSize;

    // Add current size if not in common list
    const sizesToGenerate = [...new Set([...commonSizes, currentSize])].sort((a, b) => a - b);

    console.log(`[BUCKETING] Pregenerating ${sizesToGenerate.length} bucket sizes...`);
    const pregenStart = performance.now();

    let generated = 0;
    for (const size of sizesToGenerate) {
        const cacheKey = `${size}`; // No aggregation in key since always 'max'
        if (!bucketedDataCache[cacheKey]) {
            bucketedDataCache[cacheKey] = computeBucketedData(size);
            generated++;
        }
    }

    const pregenDuration = (performance.now() - pregenStart).toFixed(2);
    const cacheSize = Object.keys(bucketedDataCache).length;
    console.log(`[BUCKETING] Pregenerated ${generated} bucket sizes (${cacheSize} total cached) in ${pregenDuration}ms`);

    // Estimate memory usage
    const { width, height } = rawElevationData;
    const rawSizeMB = (width * height * 8) / (1024 * 1024); // Approximate
    let cachedSizeMB = rawSizeMB; // Start with raw data
    for (const size of sizesToGenerate) {
        const bucketedWidth = Math.floor(width / size);
        const bucketedHeight = Math.floor(height / size);
        cachedSizeMB += (bucketedWidth * bucketedHeight * 8) / (1024 * 1024);
    }
    console.log(`[BUCKETING] Estimated cache memory: ~${cachedSizeMB.toFixed(2)} MB`);
}

// Edge markers now in edge-markers.js
function createEdgeMarkers() {
    return window.EdgeMarkers.create();
}

function createTextSprite(text, color) {
    return window.EdgeMarkers.createTextSprite(text, color);
}

// Update 3D connectivity label hover state
// Uses dynamic width based on text measurement (matches createNeighborLabel)
function updateLabelHoverState(label, isHovered) {
    if (!label || !label.userData.neighborName) return;
    
    const neighborName = label.userData.neighborName;
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    
    const fontSize = 28;
    const padding = 8; // Minimal padding - matches createNeighborLabel
    
    // Measure text to determine canvas width (same as createNeighborLabel)
    context.font = `Bold ${fontSize}px Arial`;
    const textMetrics = context.measureText(neighborName);
    const textWidth = textMetrics.width;
    
    // Canvas size based on text width + minimal padding (matches createNeighborLabel)
    canvas.width = Math.ceil(textWidth + padding * 2);
    canvas.height = 64;

    // Bluish background - brighter when hovered
    if (isHovered) {
        context.fillStyle = 'rgba(40, 70, 100, 0.95)'; // Brighter
    } else {
        context.fillStyle = 'rgba(20, 40, 60, 0.85)'; // Normal
    }
    context.fillRect(0, 0, canvas.width, canvas.height);

    // Subtle border
    context.strokeStyle = 'rgba(255, 255, 255, 0.3)';
    context.lineWidth = 1;
    context.strokeRect(0, 0, canvas.width, canvas.height);

    // Text - need to set font again after canvas resize
    context.font = `Bold ${fontSize}px Arial`;
    context.fillStyle = '#ffffff';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(neighborName, canvas.width / 2, canvas.height / 2);

    // Update texture
    const texture = new THREE.CanvasTexture(canvas);
    if (label.material.map) {
        label.material.map.dispose();
    }
    label.material.map = texture;
    label.material.needsUpdate = true;
}

function updateEdgeMarkers() {
    return window.EdgeMarkers.update();
}

function setupScene() {
    // Scene
    scene = new THREE.Scene();
    window.scene = scene; // Expose for modules
    scene.background = new THREE.Color(0x0a0a0a);
    // Fog disabled - colors stay vibrant at all zoom levels

    // CRITICAL: Camera near/far plane ratio affects depth buffer precision
    // See .cursorrules "3D Rendering" section for full details
    // Current: near=1m, far=100km (100,000:1 ratio - safe)
    // NEVER exceed 1,000,000:1 ratio or depth buffer artifacts will occur
    const aspect = window.innerWidth / window.innerHeight;
    camera = new THREE.PerspectiveCamera(60, aspect, 1, 100000); // 1m to 100km
    window.camera = camera; // Expose for modules
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
    window.renderer = renderer; // Expose for modules
    const pixelRatio = Math.min(window.devicePixelRatio, 2);
    renderer.setPixelRatio(pixelRatio);
    console.log(`[RENDERER] Device pixel ratio: ${window.devicePixelRatio.toFixed(2)}x (capped at ${pixelRatio.toFixed(2)}x)`);
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
    window.controls = controls; // Expose for modules

    // Initialize raycaster and ground plane for cursor picking and HUD
    // Ground plane is y=0 (map surface) for stable interactions
    raycaster = new THREE.Raycaster();
    window.raycaster = raycaster; // Expose for modules
    groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);

    // Initialize Natural (Lambert) lighting
    try { updateLightingForShading(); } catch (_) { }
}

// Track if controls have been set up to prevent duplicate initialization
let controlsInitialized = false;
let suppressRegionChange = false; // Prevent change handler during programmatic updates
let regionIdToName = {};
let regionNameToId = {};
let regionOptions = []; // [{id, name}]

function setupControls() {
    // Delegate to UIControlsManager module
    if (window.UIControlsManager && typeof window.UIControlsManager.init === 'function') {
        window.UIControlsManager.init();
        controlsInitialized = true;
    } else {
        console.error('[setupControls] UIControlsManager not available');
    }
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

function autoAdjustBucketSize(preserveTransform = true) {
    return window.ResolutionControls.autoAdjust(preserveTransform);
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
        // Track which mouse button is pressed (for URL update deferral)
        activeMouseButtons |= (1 << e.button);
        if (activeScheme) activeScheme.onMouseDown(e);
    });

    // Handle clicks on connectivity labels (US state neighbors)
    renderer.domElement.addEventListener('click', (e) => {
        // Only process if connectivity labels exist (US states only)
        if (!window.connectivityLabels || window.connectivityLabels.length === 0) {
            return;
        }

        // Use raycaster to check for sprite clicks
        const rect = renderer.domElement.getBoundingClientRect();
        const mouse = new THREE.Vector2();
        mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        raycaster.setFromCamera(mouse, camera);
        // Raycast specifically against connectivity labels (like compass rose does with edgeMarkers)
        const intersects = raycaster.intersectObjects(window.connectivityLabels, false);
        
        console.log('[Connectivity] Click detected:', {
            mouseNDC: { x: mouse.x.toFixed(3), y: mouse.y.toFixed(3) },
            labelCount: window.connectivityLabels.length,
            intersects: intersects.length,
            labels: window.connectivityLabels.map(l => ({ 
                name: l.userData.neighborName, 
                position: l.position.toArray(),
                scale: l.scale.toArray()
            }))
        });

        for (const intersect of intersects) {
            console.log('[Connectivity] Intersection found:', {
                object: intersect.object,
                userData: intersect.object.userData,
                distance: intersect.distance
            });
            // handleConnectivityClick is defined in state-connectivity.js (required module)
            if (handleConnectivityClick(intersect.object)) {
                e.preventDefault();
                e.stopPropagation();
                return; // Stop after first handled click
            }
        }
    });

    renderer.domElement.addEventListener('mousemove', (e) => {
        // Track mouse for HUD and zoom-to-cursor
        currentMouseX = e.clientX;
        currentMouseY = e.clientY;
        if (activeScheme) activeScheme.onMouseMove(e);
        // Update HUD live
        if (window.HUDSystem && typeof window.HUDSystem.update === 'function') {
            window.HUDSystem.update(e.clientX, e.clientY);
        }

        // Check if hovering over connectivity label
        if (window.connectivityLabels && window.connectivityLabels.length > 0) {
            const rect = renderer.domElement.getBoundingClientRect();
            const mouse = new THREE.Vector2();
            mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);
            // Raycast specifically against connectivity labels
            const intersects = raycaster.intersectObjects(window.connectivityLabels, false);

            // Update hover state for all labels
            window.connectivityLabels.forEach(label => {
                const wasHovered = label.userData.isHovered;
                const isHovered = intersects.length > 0 && intersects[0].object === label;
                
                if (isHovered !== wasHovered) {
                    label.userData.isHovered = isHovered;
                    updateLabelHoverState(label, isHovered);
                }
            });

            let overLabel = intersects.length > 0;
            renderer.domElement.style.cursor = overLabel ? 'pointer' : 'default';
        }
    });

    renderer.domElement.addEventListener('mouseup', (e) => {
        // Track which mouse button is released (for URL update deferral)
        activeMouseButtons &= ~(1 << e.button);
        if (activeScheme) activeScheme.onMouseUp(e);
    });

    // Window-level mouseup listener: catches mouseup events even when mouse is outside canvas
    // This prevents drag state from getting stuck if user releases mouse button outside the canvas
    window.addEventListener('mouseup', (e) => {
        // Track which mouse button is released (for URL update deferral)
        activeMouseButtons &= ~(1 << e.button);
        if (activeScheme && typeof activeScheme.onMouseUp === 'function') {
            activeScheme.onMouseUp(e);
        }
    });

    // Cancel drags when mouse leaves canvas (safety measure)
    renderer.domElement.addEventListener('mouseleave', (e) => {
        // Clear all mouse button state (prevents stuck buttons)
        activeMouseButtons = 0;
        if (activeScheme && typeof activeScheme.cancelAllDrags === 'function') {
            activeScheme.cancelAllDrags();
        }
    });

    // Compass rose initialization (delegated to CompassRose module)
    if (window.CompassRose && typeof window.CompassRose.init === 'function') {
        window.CompassRose.init(raycaster, camera, renderer);
    } else {
        console.error('[setupEventListeners] CompassRose not available');
    }

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

    // HUD system initialization (delegated to HUDSystem module)
    if (window.HUDSystem && typeof window.HUDSystem.init === 'function') {
        window.HUDSystem.init();
    } else {
        console.error('[setupEventListeners] HUDSystem not available');
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

    // Global Scale toggle - use consistent elevation range across all regions
    const useGlobalScaleCheckbox = document.getElementById('useGlobalScale');
    if (useGlobalScaleCheckbox) {
        // Load saved preference from localStorage (default: false)
        const savedGlobalScale = localStorage.getItem('useGlobalScale');
        if (savedGlobalScale !== null) {
            useGlobalScaleCheckbox.checked = savedGlobalScale === 'true';
            params.useGlobalScale = useGlobalScaleCheckbox.checked;
        }

        // Add change listener
        useGlobalScaleCheckbox.addEventListener('change', () => {
            params.useGlobalScale = useGlobalScaleCheckbox.checked;
            // Update all terrain colors to apply new scale
            if (typeof updateColors === 'function') {
                updateColors();
            }
            // Update color legend to show new scale range
            if (typeof updateColorLegend === 'function') {
                updateColorLegend();
            }
            // Save preference to localStorage
            localStorage.setItem('useGlobalScale', String(params.useGlobalScale));
            console.log(`[Global Scale] ${params.useGlobalScale ? 'Enabled' : 'Disabled'} - using ${params.useGlobalScale ? 'global' : 'per-region'} scale`);
        });
    }

    // Edge Markers show/hide toggle handled by CompassRose module (called above)

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

    // HUD initialization handled by HUDSystem module (called above)
}

// HUD functions moved to hud-system.js module
// Keeping thin wrappers for backward compatibility
function initHudDragging() {
    // Delegated to HUDSystem module
    if (window.HUDSystem && typeof window.HUDSystem.init === 'function') {
        window.HUDSystem.init();
    }
}

function saveHudPosition() {
    // Delegated to HUDSystem module (called internally)
}

function loadHudPosition() {
    // Delegated to HUDSystem module (called internally)
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

// Terrain renderer functions moved to terrain-renderer.js module
// Keeping thin wrappers for backward compatibility
function createTerrain() {
    if (window.TerrainRenderer && typeof window.TerrainRenderer.create === 'function') {
        window.TerrainRenderer.create();
    } else {
        console.error('[createTerrain] TerrainRenderer not available');
    }
}

function recreateTerrain(preserveTransform = true) {
    if (window.TerrainRenderer && typeof window.TerrainRenderer.recreate === 'function') {
        return window.TerrainRenderer.recreate(preserveTransform);
    } else {
        console.error('[recreateTerrain] TerrainRenderer not available');
        return 0;
    }
}

function updateTerrainHeight() {
    if (window.TerrainRenderer && typeof window.TerrainRenderer.updateHeight === 'function') {
        window.TerrainRenderer.updateHeight();
    } else {
        console.error('[updateTerrainHeight] TerrainRenderer not available');
    }
}

// Terrain creation functions moved to TerrainRenderer module
// Keeping thin wrappers for backward compatibility
function createBarsTerrain(width, height, elevation, scale) {
    // Delegated to TerrainRenderer.create() which calls createBars internally
    console.warn('[createBarsTerrain] This function is deprecated - use TerrainRenderer.create()');
    if (window.TerrainRenderer && typeof window.TerrainRenderer.create === 'function') {
        window.TerrainRenderer.create();
    }
}


// Old terrain creation implementations removed - now in terrain-renderer.js module

// Helpers for per-cell derived values during colorization
// Delegated to MapShading module, keeping wrappers for backward compatibility
let __lastColorRow = 0, __lastColorCol = 0;
function setLastColorIndex(i, j) {
    __lastColorRow = i;
    __lastColorCol = j;
    // Also update in MapShading if available
    if (window.MapShading && typeof window.MapShading.setLastColorIndex === 'function') {
        window.MapShading.setLastColorIndex(i, j);
    }
}
function deriveCurrentSlope() {
    if (typeof getSlopeDegrees === 'function') {
        return getSlopeDegrees(__lastColorRow, __lastColorCol) ?? 0;
    }
    return 0;
}
function deriveCurrentAspect() {
    if (typeof getAspectDegrees === 'function') {
        return getAspectDegrees(__lastColorRow, __lastColorCol) ?? 0;
    }
    return 0;
}

// Old updateTerrainHeight implementation removed - now in terrain-renderer.js module

// Map shading functions moved to map-shading.js module
// Keeping thin wrappers for backward compatibility
function getColorForElevation(elevation) {
    if (window.MapShading && typeof window.MapShading.getColor === 'function') {
        return window.MapShading.getColor(elevation);
    }
    // Fallback
    return __tmpColor.set(0x808080);
}

function updateColors() {
    if (window.MapShading && typeof window.MapShading.updateAll === 'function') {
        window.MapShading.updateAll();
    } else {
        // Fallback if not ready yet
        if (typeof recreateTerrain === 'function') {
            recreateTerrain();
        }
    }
}

// Store original terrain position to keep it fixed when bucket size changes
let originalTerrainPosition = null;

// Old recreateTerrain implementation removed - now in terrain-renderer.js module

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
    window.derivedSlopeDeg = null; // Sync to window
    window.derivedAspectDeg = null; // Sync to window
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
    window.derivedSlopeDeg = derivedSlopeDeg; // Sync to window
    window.derivedAspectDeg = derivedAspectDeg; // Sync to window
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

    // Use pixel-grid extents to preserve proportions established by the pipeline
    const bucketMultiplier = params.bucketSize;
    const xExtent = (gridWidth - 1) * bucketMultiplier;
    const zExtent = (gridHeight - 1) * bucketMultiplier;

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

function setFlat() {
    console.log(`Setting FLAT view (no height variation)`);
    
    // Use minimum possible value to create flat appearance
    const flatValue = 0.00001;
    
    setVertExag(flatValue);
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

    // Special handling for flat button
    const flatBtn = document.getElementById('vertExagBtnFlat');
    if (flatBtn) {
        const flatValue = 0.00001;
        const tolerance = 0.000001;
        if (Math.abs(activeValue - flatValue) < tolerance) {
            flatBtn.classList.add('active');
            flatBtn.style.outline = '2px solid#ffaa00';
            activeVertExagButton = flatBtn;
        }
    }

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

// Apply camera state from URL parameters
function applyCameraStateFromURL() {
    if (!window.urlCameraState) return;

    const state = window.urlCameraState;
    
    // Apply camera position
    if (camera && state.position) {
        camera.position.set(state.position.x, state.position.y, state.position.z);
        console.log(`Camera position set from URL: (${state.position.x.toFixed(1)}, ${state.position.y.toFixed(1)}, ${state.position.z.toFixed(1)})`);
    }

    // Apply focus point (controls target)
    if (controls && state.focus) {
        controls.target.set(state.focus.x, state.focus.y, state.focus.z);
        console.log(`Camera focus set from URL: (${state.focus.x.toFixed(1)}, ${state.focus.y.toFixed(1)}, ${state.focus.z.toFixed(1)})`);
    }

    // Apply terrain rotation
    if (window.terrainGroup && state.terrainRotation) {
        window.terrainGroup.rotation.set(state.terrainRotation.x, state.terrainRotation.y, state.terrainRotation.z);
        console.log(`Terrain rotation set from URL: (${state.terrainRotation.x.toFixed(3)}, ${state.terrainRotation.y.toFixed(3)}, ${state.terrainRotation.z.toFixed(3)})`);
    }

    // Update camera orientation and controls
    if (camera && controls) {
        camera.lookAt(controls.target);
        controls.update();
    }

    // Update active camera scheme's focus point if it has one
    if (activeScheme && activeScheme.focusPoint && state.focus) {
        activeScheme.focusPoint.set(state.focus.x, state.focus.y, state.focus.z);
    }

    // Clear the URL state after applying (so switching regions uses default view)
    delete window.urlCameraState;
}

// Update camera state in URL (when camera stops moving AND no mouse buttons are held)
let lastCameraState = null;
let lastUrlUpdateState = null;
let cameraIsMoving = false;
let activeMouseButtons = 0; // Bitmask of currently pressed mouse buttons

function updateCameraStateInURL() {
    // Skip if no camera or controls
    if (!camera || !controls) return;

    // Capture current state
    const currentState = {
        cx: camera.position.x,
        cy: camera.position.y,
        cz: camera.position.z,
        fx: controls.target.x,
        fy: controls.target.y,
        fz: controls.target.z,
        rx: window.terrainGroup ? window.terrainGroup.rotation.x : 0,
        ry: window.terrainGroup ? window.terrainGroup.rotation.y : 0,
        rz: window.terrainGroup ? window.terrainGroup.rotation.z : 0
    };

    // Check if state has changed from previous frame (with small threshold to avoid floating point noise)
    const threshold = 0.01;
    let stateChanged = false;
    
    if (lastCameraState) {
        stateChanged = Object.keys(currentState).some(key => {
            return Math.abs(currentState[key] - lastCameraState[key]) > threshold;
        });
    } else {
        // First frame, initialize
        lastCameraState = currentState;
        return;
    }

    if (stateChanged) {
        // Camera is moving - mark as moving and defer URL update
        cameraIsMoving = true;
    } else if (cameraIsMoving && activeMouseButtons === 0) {
        // Camera stopped moving AND no mouse buttons held - update URL immediately
        cameraIsMoving = false;
        
        // Check if state is different from last URL update (avoid redundant updates)
        let needsUpdate = !lastUrlUpdateState;
        if (lastUrlUpdateState) {
            needsUpdate = Object.keys(currentState).some(key => {
                return Math.abs(currentState[key] - lastUrlUpdateState[key]) > threshold;
            });
        }
        
        if (needsUpdate) {
            // Update URL with current camera state
            const url = new URL(window.location);
            
            // Round to 2 decimal places for cleaner URLs
            url.searchParams.set('cx', currentState.cx.toFixed(2));
            url.searchParams.set('cy', currentState.cy.toFixed(2));
            url.searchParams.set('cz', currentState.cz.toFixed(2));
            
            // Only include focus if not at origin
            if (Math.abs(currentState.fx) > threshold || Math.abs(currentState.fy) > threshold || Math.abs(currentState.fz) > threshold) {
                url.searchParams.set('fx', currentState.fx.toFixed(2));
                url.searchParams.set('fy', currentState.fy.toFixed(2));
                url.searchParams.set('fz', currentState.fz.toFixed(2));
            } else {
                url.searchParams.delete('fx');
                url.searchParams.delete('fy');
                url.searchParams.delete('fz');
            }
            
            // Only include rotation if not zero
            if (Math.abs(currentState.rx) > threshold || Math.abs(currentState.ry) > threshold || Math.abs(currentState.rz) > threshold) {
                url.searchParams.set('rx', currentState.rx.toFixed(3));
                url.searchParams.set('ry', currentState.ry.toFixed(3));
                url.searchParams.set('rz', currentState.rz.toFixed(3));
            } else {
                url.searchParams.delete('rx');
                url.searchParams.delete('ry');
                url.searchParams.delete('rz');
            }

            // Use replaceState instead of pushState to avoid cluttering history
            window.history.replaceState({}, '', url);
            
            // Update last URL update state
            lastUrlUpdateState = { ...currentState };
        }
    }
    
    // Update last state for next frame
    lastCameraState = { ...currentState };
}

function exportImage() {
    // Temporarily enable preserveDrawingBuffer for screenshot
    const prevPDB = renderer.getContext().getContextAttributes && renderer.getContext().getContextAttributes().preserveDrawingBuffer;
    // Some drivers may not allow toggling at runtime; we emulate by rendering once then reading
    renderer.render(scene, camera);
    const dataURL = renderer.domElement.toDataURL('image/png');
    const link = document.createElement('a');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    link.download = `terrain_bucket${params.bucketSize}_max_${timestamp}.png`;
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

// Keyboard shortcuts are now handled by keyboard-shortcuts.js module
// These functions are kept for backward compatibility but delegate to the module
function onKeyDown(event) {
    // Delegate to keyboard shortcuts module
    if (window.KeyboardShortcuts && window.KeyboardShortcuts.handleGlobalShortcuts) {
        window.KeyboardShortcuts.handleGlobalShortcuts(event, keyboard);
    }
    
    // Camera schemes handle their own keys (WASD, F, etc.)
    if (activeScheme && typeof activeScheme.onKeyDown === 'function') {
        activeScheme.onKeyDown(event);
    }
}

function onKeyUp(event) {
    // Delegate to keyboard shortcuts module
    if (window.KeyboardShortcuts && window.KeyboardShortcuts.handleGlobalKeyUp) {
        window.KeyboardShortcuts.handleGlobalKeyUp(event, keyboard);
    }
    
    // Camera schemes handle their own keys
    if (activeScheme && typeof activeScheme.onKeyUp === 'function') {
        activeScheme.onKeyUp(event);
    }
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

// HUD functions moved to hud-system.js module
// Keeping thin wrappers for backward compatibility
function updateCursorHUD(clientX, clientY) {
    if (window.HUDSystem && typeof window.HUDSystem.update === 'function') {
        window.HUDSystem.update(clientX, clientY);
    }
}

function loadHudSettings() {
    if (window.HUDSystem && typeof window.HUDSystem.loadSettings === 'function') {
        window.HUDSystem.loadSettings();
    }
}

function saveHudSettings() {
    if (window.HUDSystem && typeof window.HUDSystem.saveSettings === 'function') {
        window.HUDSystem.saveSettings();
    }
}

function applyHudSettingsToUI() {
    // Delegated to HUDSystem module (called internally during init)
}

function bindHudSettingsHandlers() {
    // Delegated to HUDSystem module (called internally during init)
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
    const bucket = params.bucketSize;
    xMin = -(w - 1) * bucket / 2; xMax = (w - 1) * bucket / 2;
    zMin = -(h - 1) * bucket / 2; zMax = (h - 1) * bucket / 2;
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
    if (window.HUDSystem && typeof window.HUDSystem.update === 'function') {
        window.HUDSystem.update(event.clientX, event.clientY);
    }
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
    
    // Update camera state in URL (debounced to avoid excessive updates)
    updateCameraStateInURL();
    
    // HUD update moved to mousemove handler only (removed duplicate call from animate loop)
    // This prevents double-updates and improves performance
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

// Toggle keyboard shortcuts overlay
function toggleShortcutsOverlay() {
    const overlay = document.getElementById('shortcuts-overlay');
    if (!overlay) return;
    
    if (overlay.style.display === 'none' || !overlay.style.display) {
        overlay.style.display = 'flex';
    } else {
        overlay.style.display = 'none';
    }
}

// Keyboard zoom (Shift + +/-) - simulates mouse wheel scroll
function keyboardZoom(direction) {
    // direction: -1 = zoom in (like scroll up), 1 = zoom out (like scroll down)
    if (!activeScheme || !activeScheme.enabled) return;
    
    // Create fake wheel event at screen center
    const centerX = window.innerWidth / 2;
    const centerY = window.innerHeight / 2;
    
    // Standard wheel deltaY: positive = scroll down (zoom out), negative = scroll up (zoom in)
    // We use 100 as a typical deltaY value (matches standard mouse wheel)
    const fakeWheelEvent = {
        clientX: centerX,
        clientY: centerY,
        deltaY: direction * 100, // -100 for zoom in, +100 for zoom out
        preventDefault: () => {}
    };
    
    // Delegate to active camera scheme's wheel handler
    if (typeof activeScheme.onWheel === 'function') {
        activeScheme.onWheel(fakeWheelEvent);
    }
}

// Initialize shortcuts overlay event handlers
function initShortcutsOverlay() {
    const overlay = document.getElementById('shortcuts-overlay');
    const closeBtn = document.getElementById('shortcuts-close');
    
    if (!overlay || !closeBtn) return;
    
    // Close button
    closeBtn.addEventListener('click', () => {
        overlay.style.display = 'none';
    });
    
    // Click outside modal to close
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            overlay.style.display = 'none';
        }
    });
    
    // ESC key to close
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && overlay.style.display !== 'none') {
            e.preventDefault();
            overlay.style.display = 'none';
        }
    });
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

