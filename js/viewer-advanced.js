// Global variables
let scene, camera, renderer, controls;
let terrainMesh, wireframeMesh, gridHelper;
let rawElevationData; // Original full-resolution data
let processedData; // Bucketed/aggregated data
let stats = {};
let borderMeshes = [];
let borderData = null;
let frameCount = 0;
let lastTime = performance.now();

// Directional edge markers (N, E, S, W)
// PRODUCT REQUIREMENT: These markers must NOT move when user adjusts vertical exaggeration slider
// Implementation: Create once at current exaggeration, don't recreate on exaggeration changes
let edgeMarkers = [];

// Parameters
let params = {
    bucketSize: 4,  // Integer multiplier of pixel spacing (1×, 2×, 3×, etc.)
    tileGap: 1,     // Gap between tiles as percentage (0-99%, where 1% = 0.99 tile size)
    aggregation: 'max',
    renderMode: 'bars',
    verticalExaggeration: 0.01311,  // Default: good balance of detail and scale
    colorScheme: 'terrain',
    wireframeOverlay: false,
    showGrid: false,
    showBorders: false,
    flatShading: true,
    autoRotate: false
};

// Initialize
async function init() {
    try {
        setupScene();
        setupEventListeners();
        
        // Populate region selector and load first region
        const firstRegionId = await populateRegionSelector();
        
        // Load the initial region data
        let dataUrl;
        if (firstRegionId === 'default') {
            dataUrl = 'generated/elevation_data.json';
        } else {
            // Use the file path from manifest (handles version suffixes like _srtm_30m_v2)
            const filename = regionsManifest?.regions[firstRegionId]?.file || `${firstRegionId}.json`;
            dataUrl = `generated/regions/${filename}`;
        }
        
        rawElevationData = await loadElevationData(dataUrl);
        
        hideLoading();
        setupControls();
        
        // Sync UI to match params (ensures no mismatch on initial load)
        syncUIControls();
        
        // Auto-adjust bucket size to meet complexity constraints
        autoAdjustBucketSize();
        
        // updateStats() is called by autoAdjustBucketSize(), no need to call again
        
        // Reset camera to appropriate distance for this terrain size
        resetCamera();
        
        animate();
    } catch (error) {
        document.getElementById('loading').innerHTML = `
            <div style="text-align: center;">
                âŒ Error loading data<br><br>
                <div style="font-size: 13px; color: #ff6666; max-width: 400px;">${error.message}</div>
                <br>
                <div style="font-size: 12px; color: #888;">
                    Make sure to run:<br>
                    <code style="color: #5588cc; background: #1a1a1a; padding: 8px; border-radius: 4px; display: inline-block; margin-top: 10px;">
                        python export_for_web_viewer.py
                    </code>
                    <br>or<br>
                    <code style="color: #5588cc; background: #1a1a1a; padding: 8px; border-radius: 4px; display: inline-block; margin-top: 10px;">
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

async function loadElevationData(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Failed to load elevation data. HTTP ${response.status}`);
    }
    const data = await response.json();
    
    // Validate format version
    if (data.format_version && data.format_version !== EXPECTED_FORMAT_VERSION) {
        console.error(`[!!] FORMAT VERSION MISMATCH!`);
        console.error(`    Expected: v${EXPECTED_FORMAT_VERSION}`);
        console.error(`    Got: v${data.format_version}`);
        console.error(`    File may have outdated transformations!`);
        throw new Error(
            `Data format version mismatch!\n` +
            `Expected v${EXPECTED_FORMAT_VERSION}, got v${data.format_version}\n\n` +
            `This data was exported with an older format.\n` +
            `Please re-export: python export_for_web_viewer.py`
        );
    } else if (!data.format_version) {
        console.warn(`[!!] No format version in data file - may be legacy format!`);
        console.warn(`    Consider re-exporting: python export_for_web_viewer.py`);
    } else {
        console.log(`[OK] Data format v${data.format_version} (exported: ${data.exported_at || 'unknown'})`);
    }
    
    return data;
}

async function loadBorderData(elevationUrl) {
    // Try to load borders from the same location with _borders suffix
    const borderUrl = elevationUrl.replace('.json', '_borders.json');
    try {
        const response = await fetch(borderUrl);
        if (!response.ok) {
            console.log(`[INFO] No border data found at ${borderUrl}`);
            return null;
        }
        const data = await response.json();
        const borderCount = (data.countries?.length || 0) + (data.states?.length || 0);
        const borderType = data.states ? 'states' : 'countries';
        console.log(`[OK] Loaded border data: ${borderCount} ${borderType}`);
        return data;
    } catch (error) {
        console.log(`[INFO] Border data not available: ${error.message}`);
        return null;
    }
}

async function loadRegionsManifest() {
    try {
        const response = await fetch('generated/regions/regions_manifest.json');
        if (!response.ok) {
            console.warn('Regions manifest not found, using default single region');
            return null;
        }
        return await response.json();
    } catch (error) {
        console.warn('Could not load regions manifest:', error);
        return null;
    }
}

async function populateRegionSelector() {
    const selectElement = document.getElementById('regionSelect');
    
    regionsManifest = await loadRegionsManifest();
    
    if (!regionsManifest || !regionsManifest.regions || Object.keys(regionsManifest.regions).length === 0) {
        // No manifest, use default single region
        selectElement.innerHTML = '<option value="default">USA (Default)</option>';
        document.getElementById('currentRegion').textContent = 'USA';
        currentRegionId = 'default';
        return 'default';
    }
    
    // Populate dropdown with available regions
    selectElement.innerHTML = '';
    
    // Group regions by continent/category
    const grouped = {};
    for (const [regionId, regionInfo] of Object.entries(regionsManifest.regions)) {
        // Determine group based on region name/id
        let group = 'Other';
        if (regionId.includes('usa_') || ['california', 'texas', 'colorado', 'washington', 'new_york', 'florida', 'arizona', 'alaska', 'hawaii', 'oregon', 'nevada', 'utah', 'idaho', 'montana', 'wyoming', 'new_mexico', 'north_dakota', 'south_dakota', 'nebraska', 'kansas', 'oklahoma', 'minnesota', 'iowa', 'missouri', 'arkansas', 'louisiana', 'wisconsin', 'illinois', 'michigan', 'indiana', 'ohio', 'mississippi', 'alabama', 'tennessee', 'kentucky', 'georgia', 'south_carolina', 'north_carolina', 'virginia', 'west_virginia', 'maryland', 'delaware', 'new_jersey', 'pennsylvania', 'connecticut', 'rhode_island', 'massachusetts', 'vermont', 'new_hampshire', 'maine'].includes(regionId)) {
            group = 'USA';
        } else if (['canada', 'mexico'].includes(regionId)) {
            group = 'North America';
        } else if (['japan', 'china', 'south_korea', 'india', 'thailand', 'vietnam', 'nepal', 'shikoku', 'hokkaido', 'honshu', 'kyushu', 'kochi'].includes(regionId)) {
            group = 'Asia';
        } else if (['germany', 'france', 'italy', 'spain', 'uk', 'poland', 'norway', 'sweden', 'switzerland', 'austria', 'greece', 'netherlands', 'iceland'].includes(regionId)) {
            group = 'Europe';
        } else if (['brazil', 'argentina', 'chile', 'peru'].includes(regionId)) {
            group = 'South America';
        } else if (['australia', 'new_zealand'].includes(regionId)) {
            group = 'Oceania';
        } else if (['south_africa', 'egypt', 'kenya'].includes(regionId)) {
            group = 'Africa';
        } else if (['israel', 'saudi_arabia'].includes(regionId)) {
            group = 'Middle East';
        } else if (['alps', 'rockies'].includes(regionId)) {
            group = 'Mountain Ranges';
        }
        
        if (!grouped[group]) grouped[group] = [];
        grouped[group].push({ id: regionId, info: regionInfo });
    }
    
    // Add grouped options
    const groupOrder = ['USA', 'North America', 'Europe', 'Asia', 'South America', 'Oceania', 'Africa', 'Middle East', 'Mountain Ranges', 'Other'];
    for (const groupName of groupOrder) {
        if (!grouped[groupName]) continue;
        
        const optgroup = document.createElement('optgroup');
        optgroup.label = groupName;
        
        grouped[groupName].sort((a, b) => a.info.name.localeCompare(b.info.name));
        
        for (const { id, info } of grouped[groupName]) {
            const option = document.createElement('option');
            option.value = id;
            option.textContent = info.name;
            option.title = info.description;
            optgroup.appendChild(option);
        }
        
        selectElement.appendChild(optgroup);
    }
    
    // Select USA as default if available, otherwise first region
    let firstRegionId;
    if (regionsManifest.regions['usa_full']) {
        firstRegionId = 'usa_full';
    } else {
        firstRegionId = Object.keys(regionsManifest.regions)[0];
    }
    selectElement.value = firstRegionId;
    currentRegionId = firstRegionId;
    updateRegionInfo(firstRegionId);
    
    // NOTE: Select2 initialization happens in setupControls(), not here
    return firstRegionId;
}

function updateRegionInfo(regionId) {
    if (regionId === 'default' || !regionsManifest || !regionsManifest.regions[regionId]) {
        document.getElementById('currentRegion').textContent = 'USA';
        document.getElementById('regionInfo').textContent = 'Continental United States';
        return;
    }
    
    const regionInfo = regionsManifest.regions[regionId];
    document.getElementById('currentRegion').textContent = regionInfo.name;
    document.getElementById('regionInfo').textContent = regionInfo.description;
}

async function loadRegion(regionId) {
    console.log(`ðŸŒ Loading region: ${regionId}`);
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
        
        rawElevationData = await loadElevationData(dataUrl);
        borderData = await loadBorderData(dataUrl);
        currentRegionId = regionId;
        updateRegionInfo(regionId);
        
        // Update Select2 dropdown to show the loaded region
        const $regionSelect = $('#regionSelect');
        if ($regionSelect.length && $regionSelect.hasClass('select2-hidden-accessible')) {
            // Use val() and trigger('change') to update the UI properly
            $regionSelect.val(regionId).trigger('change');
        }
        
        // Clear edge markers so they get recreated for new region
        edgeMarkers.forEach(marker => scene.remove(marker));
        edgeMarkers = [];
        
        // Reprocess and recreate terrain
        rebucketData();
        recreateTerrain();
        recreateBorders();
        updateStats();
        
        // Sync UI controls with current params
        syncUIControls();
        
        // Reset camera for new terrain size
        resetCamera();
        
        hideLoading();
        console.log(`âœ… Loaded ${regionId}`);
    } catch (error) {
        console.error(`âŒ Failed to load region ${regionId}:`, error);
        alert(`Failed to load region: ${error.message}`);
        hideLoading();
        
        // On error, revert Select2 dropdown to previous region
        const $regionSelect = $('#regionSelect');
        if ($regionSelect.length && $regionSelect.hasClass('select2-hidden-accessible')) {
            $regionSelect.val(currentRegionId).trigger('change');
        }
    }
}

function showLoading(message = 'Loading elevation data...') {
    const loadingDiv = document.getElementById('loading');
    loadingDiv.textContent = message;
    loadingDiv.style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

// Sync UI controls with current params
function syncUIControls() {
    // Bucket size - sync both slider and input
    document.getElementById('bucketSize').value = params.bucketSize;
    document.getElementById('bucketSizeInput').value = params.bucketSize;
    
    // Tile gap - sync both slider and input
    document.getElementById('tileGap').value = params.tileGap;
    document.getElementById('tileGapInput').value = params.tileGap;
    
    // Vertical exaggeration - sync both slider and input
    document.getElementById('vertExag').value = params.verticalExaggeration;
    document.getElementById('vertExagInput').value = params.verticalExaggeration.toFixed(5);
    
    // Render mode
    document.getElementById('renderMode').value = params.renderMode;
    
    // Aggregation method
    document.getElementById('aggregation').value = params.aggregation;
    
    // Color scheme (using jQuery/Select2)
    // Note: terrain is already created with correct colors before this function is called
    // We just need to update the UI dropdown to match without triggering recreation
    const $colorScheme = $('#colorScheme');
    $colorScheme.val(params.colorScheme);
    // Update Select2 UI without triggering change handlers
    if ($colorScheme.hasClass('select2-hidden-accessible')) {
        $colorScheme.trigger('change.select2');
    }
    
    // Checkboxes
    document.getElementById('flatShading').checked = params.flatShading;
    document.getElementById('wireframeOverlay').checked = params.wireframeOverlay;
    document.getElementById('showGrid').checked = params.showGrid;
    document.getElementById('showBorders').checked = params.showBorders;
    document.getElementById('autoRotate').checked = params.autoRotate;
    
    // Apply visual settings to scene objects
    if (wireframeMesh) {
        wireframeMesh.visible = params.wireframeOverlay;
    }
    if (gridHelper) {
        gridHelper.visible = params.showGrid;
    }
    if (borderMeshes && borderMeshes.length > 0) {
        borderMeshes.forEach(mesh => mesh.visible = params.showBorders);
    }
    if (controls) {
        controls.autoRotate = params.autoRotate;
    }
}

// CLIENT-SIDE BUCKETING ALGORITHMS
function rebucketData() {
    const startTime = performance.now();
    console.log(`ðŸ”² Bucketing with multiplier ${params.bucketSize}Ã—, method: ${params.aggregation}`);
    
    const { width, height, elevation, bounds } = rawElevationData;
    
    // Calculate real-world scale
    const scale = calculateRealWorldScale();
    
    // CORRECT APPROACH: Bucket size MUST be an integer multiple of pixel spacing
    // This ensures buckets align perfectly with the data grid
    const bucketSize = params.bucketSize;  // Integer multiple (1, 2, 3, 4, ...)
    
    // Calculate bucketed dimensions (simple integer division)
    const bucketedWidth = Math.floor(width / bucketSize);
    const bucketedHeight = Math.floor(height / bucketSize);
    
    // Bucket physical size = pixel spacing Ã— multiplier
    const bucketSizeMetersX = scale.metersPerPixelX * bucketSize;
    const bucketSizeMetersY = scale.metersPerPixelY * bucketSize;
    
    console.log(`ðŸ“ Raw data: ${width}Ã—${height} pixels @ ${scale.metersPerPixelX.toFixed(0)}Ã—${scale.metersPerPixelY.toFixed(0)}m/pixel`);
    console.log(`ðŸ“ Bucket multiplier: ${bucketSize}Ã— â†’ ${bucketedWidth}Ã—${bucketedHeight} buckets`);
    console.log(`ðŸ“ Bucket size: ${(bucketSizeMetersX/1000).toFixed(2)}km Ã— ${(bucketSizeMetersY/1000).toFixed(2)}km`);
    
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
            
            // Collect all values in this bucket (bucketSize Ã— bucketSize pixels)
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
                        console.error(`âŒ Unknown aggregation method: ${params.aggregation}`);
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
        bucketSizeMetersX: bucketSizeMetersX,  // Actual size to tile perfectly
        bucketSizeMetersY: bucketSizeMetersY
    };
    
    const duration = (performance.now() - startTime).toFixed(2);
    const reduction = (100 * (1 - (bucketedWidth * bucketedHeight) / (width * height))).toFixed(1);
    console.log(`âœ… Bucketed to ${bucketedWidth}Ã—${bucketedHeight} (${reduction}% reduction) in ${duration}ms`);
}

function createEdgeMarkers() {
    // Remove old markers
    edgeMarkers.forEach(marker => scene.remove(marker));
    edgeMarkers = [];
    
    if (!rawElevationData || !processedData) return;
    
    const gridWidth = processedData.width;
    const gridHeight = processedData.height;
    
    // Position markers at a height using CURRENT exaggeration
    // This ensures they're visible at the right height when created
    // They won't move because they're only created once (not recreated on exaggeration changes)
    const markerHeight = rawElevationData.stats.max * params.verticalExaggeration * 1.2;
    
    // Calculate actual coordinate extents based on render mode
    let xExtent, zExtent, avgSize;
    if (params.renderMode === 'bars') {
        // Bars use UNIFORM 2D grid - same spacing in X and Z (no aspect ratio)
        const bucketMultiplier = params.bucketSize;
        xExtent = (gridWidth - 1) * bucketMultiplier / 2;
        zExtent = (gridHeight - 1) * bucketMultiplier / 2;  // NO aspect ratio scaling!
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
        { text: 'N', x: 0, z: -zExtent, color: 0xff4444 },      // North edge
        { text: 'S', x: 0, z: zExtent, color: 0x4488ff },       // South edge
        { text: 'E', x: xExtent, z: 0, color: 0x44ff44 },        // East edge
        { text: 'W', x: -xExtent, z: 0, color: 0xffff44 }        // West edge
    ];
    
    markers.forEach(markerData => {
        const sprite = createTextSprite(markerData.text, markerData.color);
        sprite.position.set(markerData.x, markerHeight, markerData.z);
        
        // Scale based on terrain size
        const baseScale = avgSize * 0.06;  // 6% of average dimension (tripled from original 2%)
        sprite.scale.set(baseScale, baseScale, baseScale);
        
        scene.add(sprite);
        edgeMarkers.push(sprite);
    });
    
    console.log(`âœ… Created edge markers (N, E, S, W) at fixed height ${markerHeight}m`);
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
        depthTest: false,  // Always visible
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
    //   Near: 1 meter (close enough for detail)
    //   Far: 100,000 meters = 100km (enough for large terrains)
    //   Ratio: 100,000:1 (good depth precision)
    //
    // NEVER use values like:
    //   - near < 0.1 (too close, wastes precision on unused range)
    //   - far > 1,000,000 (too far, spreads precision too thin)
    //   - ratio > 1,000,000:1 (depth buffer will fail)
    //
    // If you need larger view distances, implement a logarithmic depth buffer
    // or frustum-based dynamic near/far adjustment. DO NOT just increase far plane.
    // ============================================================================
    const aspect = window.innerWidth / window.innerHeight;
    camera = new THREE.PerspectiveCamera(60, aspect, 1, 100000);  // 1m to 100km
    camera.position.set(50, 50, 80);  // Will be reset after data loads
    
    // SAFETY CHECK: Validate near/far ratio to prevent depth buffer artifacts
    const nearFarRatio = camera.far / camera.near;
    if (nearFarRatio > 1000000) {
        console.error('ðŸš¨ CRITICAL: Camera near/far ratio is TOO EXTREME!');
        console.error(`   Current ratio: ${nearFarRatio.toLocaleString()}:1`);
        console.error(`   Near: ${camera.near}, Far: ${camera.far}`);
        console.error(`   This WILL cause depth buffer artifacts (geometry bleeding through).`);
        console.error(`   See learnings/DEPTH_BUFFER_PRECISION_CRITICAL.md`);
        console.error(`   Recommended: Keep ratio under 1,000,000:1`);
    } else {
        console.log(`âœ… Camera near/far ratio: ${nearFarRatio.toLocaleString()}:1 (good)`);
    }
    
    // Renderer
    renderer = new THREE.WebGLRenderer({ 
        antialias: true,  // ENABLED: Prevents edge aliasing artifacts that can look like overlapping
        preserveDrawingBuffer: true,
        alpha: false,
        powerPreference: "high-performance"
    });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    document.getElementById('canvas-container').appendChild(renderer.domElement);
    
    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);
    
    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.7);
    dirLight1.position.set(100, 200, 100);
    dirLight1.castShadow = false;
    scene.add(dirLight1);
    
    const dirLight2 = new THREE.DirectionalLight(0x6688ff, 0.4);
    dirLight2.position.set(-100, 100, -100);
    scene.add(dirLight2);
    
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
        update: function() {
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
}

// Optimized rendering for Select2 options
function formatRegionOption(option) {
    if (!option.id) return option.text;
    // Simple text rendering without extra DOM manipulation
    return $('<span>').text(option.text);
}

function formatRegionSelection(option) {
    if (!option.id) return option.text;
    // Simple text rendering for selected item
    return option.text;
}

// Track if controls have been set up to prevent duplicate initialization
let controlsInitialized = false;

function setupControls() {
    if (controlsInitialized) {
        console.warn('⚠️ setupControls() called multiple times - skipping to prevent memory leak');
        return;
    }
    
    // Initialize Select2 for region selector (typeahead with autocomplete)
    $('#regionSelect').select2({
        placeholder: 'Select a region...',
        allowClear: false,
        width: '100%',
        dropdownAutoWidth: true,
        minimumResultsForSearch: 5, // Show search box only when scrolling is needed
        closeOnSelect: true,
        templateResult: formatRegionOption,
        templateSelection: formatRegionSelection
    });
    
    // Initialize Select2 for color scheme (typeahead with autocomplete)
    $('#colorScheme').select2({
        placeholder: 'Select a color scheme...',
        allowClear: false,
        width: '100%',
        minimumResultsForSearch: Infinity, // Disable search for short lists
        dropdownAutoWidth: true,
        closeOnSelect: true
    });
    
    // Region selector - use .off() first to prevent duplicate handlers
    // Use a flag to prevent recursion when programmatically updating the value
    let isLoadingRegion = false;
    $('#regionSelect').off('change').on('change', function(e) {
        if (isLoadingRegion) return; // Prevent recursion
        
        const regionId = $(this).val();
        if (regionId && regionId !== currentRegionId) {
            isLoadingRegion = true;
            loadRegion(regionId).finally(() => {
                isLoadingRegion = false;
            });
        }
    });
    
    // Update bucket size range label
    function updateBucketSizeLabel(value) {
        const label = document.getElementById('bucketSizeRangeLabel');
        if (value === 1) {
            label.textContent = 'Full resolution (1 pixel = 1 bar)';
        } else if (value <= 5) {
            label.textContent = `Low reduction (${value}Ã—${value} pixels per bar)`;
        } else if (value <= 15) {
            label.textContent = `Medium reduction (${value}Ã—${value} pixels per bar)`;
        } else if (value <= 30) {
            label.textContent = `High reduction (${value}Ã—${value} pixels per bar)`;
        } else {
            label.textContent = `Very high reduction (${value}Ã—${value} pixels per bar)`;
        }
    }
    
    // Bucket size - immediate updates
    
    // Sync slider -> input
    document.getElementById('bucketSize').addEventListener('input', (e) => {
        params.bucketSize = parseInt(e.target.value);
        document.getElementById('bucketSizeInput').value = params.bucketSize;
        
        // Update immediately for responsive feedback
        // Clear edge markers so they get recreated at new positions
        edgeMarkers.forEach(marker => scene.remove(marker));
        edgeMarkers = [];
        rebucketData();
        recreateTerrain();
    });
    
    // Sync input -> slider
    document.getElementById('bucketSizeInput').addEventListener('change', (e) => {
        let value = parseInt(e.target.value);
        // Clamp to valid range
        value = Math.max(1, Math.min(500, value));
        params.bucketSize = value;
        document.getElementById('bucketSize').value = value;
        document.getElementById('bucketSizeInput').value = value;
        
        // Clear edge markers so they get recreated at new positions
        edgeMarkers.forEach(marker => scene.remove(marker));
        edgeMarkers = [];
        rebucketData();
        recreateTerrain();
    });
    
    // Tile gap - immediate updates
    
    // Sync slider -> input
    document.getElementById('tileGap').addEventListener('input', (e) => {
        params.tileGap = parseInt(e.target.value);
        document.getElementById('tileGapInput').value = params.tileGap;
        
        // Update immediately for responsive feedback
        recreateTerrain();  // Only recreate terrain, no need to rebucket
    });
    
    // Sync input -> slider
    document.getElementById('tileGapInput').addEventListener('change', (e) => {
        let value = parseInt(e.target.value);
        // Clamp to valid range
        value = Math.max(0, Math.min(99, value));
        params.tileGap = value;
        document.getElementById('tileGap').value = value;
        document.getElementById('tileGapInput').value = value;
        recreateTerrain();
    });
    
    // Aggregation method
    document.getElementById('aggregation').addEventListener('change', (e) => {
        console.log(`ðŸ”„ Aggregation changed from ${params.aggregation} to ${e.target.value}`);
        params.aggregation = e.target.value;
        // Clear edge markers so they get recreated at new positions
        edgeMarkers.forEach(marker => scene.remove(marker));
        edgeMarkers = [];
        rebucketData();
        recreateTerrain();
        // Remove focus from dropdown so keyboard navigation works
        e.target.blur();
    });
    
    // Render mode
    document.getElementById('renderMode').addEventListener('change', (e) => {
        params.renderMode = e.target.value;
        // Clear edge markers so they get recreated at new positions for new render mode
        edgeMarkers.forEach(marker => scene.remove(marker));
        edgeMarkers = [];
        recreateTerrain();
        // Remove focus from dropdown so keyboard navigation works
        e.target.blur();
    });
    
    // Vertical exaggeration - immediate updates while dragging
    
    // Sync slider -> input (update immediately)
    document.getElementById('vertExag').addEventListener('input', (e) => {
        params.verticalExaggeration = parseFloat(e.target.value);
        document.getElementById('vertExagInput').value = params.verticalExaggeration.toFixed(5);
        
        // Update terrain immediately for responsive feedback
        updateTerrainHeight();
    });
    
    // Sync input -> slider
    document.getElementById('vertExagInput').addEventListener('change', (e) => {
        let value = parseFloat(e.target.value);
        // Clamp to valid range
        value = Math.max(0.00001, Math.min(0.3, value));
        params.verticalExaggeration = value;
        document.getElementById('vertExag').value = value;
        document.getElementById('vertExagInput').value = value.toFixed(5);
        updateTerrainHeight();
    });
    
    // Color scheme
    $('#colorScheme').on('change', function(e) {
        params.colorScheme = $(this).val();
        updateColors();
    });
    
    // Wireframe overlay
    document.getElementById('wireframeOverlay').addEventListener('change', (e) => {
        params.wireframeOverlay = e.target.checked;
        if (wireframeMesh) wireframeMesh.visible = params.wireframeOverlay;
    });
    
    // Grid
    document.getElementById('showGrid').addEventListener('change', (e) => {
        params.showGrid = e.target.checked;
        gridHelper.visible = params.showGrid;
    });
    
    // Borders
    document.getElementById('showBorders').addEventListener('change', (e) => {
        params.showBorders = e.target.checked;
        borderMeshes.forEach(mesh => mesh.visible = params.showBorders);
    });
    
    // Flat shading toggle
    document.getElementById('flatShading').addEventListener('change', (e) => {
        params.flatShading = e.target.checked;
        recreateTerrain();
    });
    
    // Auto-rotate
    document.getElementById('autoRotate').addEventListener('change', (e) => {
        params.autoRotate = e.target.checked;
        controls.autoRotate = params.autoRotate;
    });
    
    // Mark controls as initialized to prevent duplicate setup
    controlsInitialized = true;
    console.log('✅ Controls initialized successfully');
}

function adjustBucketSize(delta) {
    if (!rawElevationData) {
        console.warn('⚠️ No data loaded, cannot adjust bucket size');
        return;
    }
    
    // Calculate new bucket size with clamping to valid range [1, 500]
    let newSize = params.bucketSize + delta;
    newSize = Math.max(1, Math.min(500, newSize));
    
    // Update params and UI
    params.bucketSize = newSize;
    document.getElementById('bucketSize').value = newSize;
    document.getElementById('bucketSizeInput').value = newSize;
    
    // Clear edge markers so they get recreated at new positions
    edgeMarkers.forEach(marker => scene.remove(marker));
    edgeMarkers = [];
    
    // Rebucket and recreate terrain
    rebucketData();
    recreateTerrain();
    updateStats();
    
    console.log(`🎯 Bucket size adjusted by ${delta > 0 ? '+' : ''}${delta} → ${newSize}×`);
}

function autoAdjustBucketSize() {
    if (!rawElevationData) {
        console.warn('⚠️ No data loaded, cannot auto-adjust bucket size');
        return;
    }
    
    const { width, height } = rawElevationData;
    // Reduced from 10000 to ~3900 (60% larger bucket size means ~40% of original bucket count)
    const TARGET_BUCKET_COUNT = 190000;
    
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
    
    console.log(`🎯 AUTO-ADJUST: Raw data ${width}×${height} pixels (${(width*height).toLocaleString()} total)`);
    console.log(`🎯 Optimal bucket size: ${optimalSize}× → ${bucketedWidth}×${bucketedHeight} grid (${totalBuckets.toLocaleString()} buckets)`);
    console.log(`🎯 Constraint: ${totalBuckets <= TARGET_BUCKET_COUNT ? '✅' : '❌'} ${totalBuckets} / ${TARGET_BUCKET_COUNT.toLocaleString()} buckets`);
    
    // Update params and UI
    params.bucketSize = optimalSize;
    document.getElementById('bucketSize').value = optimalSize;
    document.getElementById('bucketSizeInput').value = optimalSize;
    
    // Clear edge markers so they get recreated at new positions
    edgeMarkers.forEach(marker => scene.remove(marker));
    edgeMarkers = [];
    
    // Rebucket and recreate terrain
    rebucketData();
    recreateTerrain();
    updateStats();
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
        if (activeScheme) activeScheme.onMouseMove(e);
    });
    
    renderer.domElement.addEventListener('mouseup', (e) => {
        if (activeScheme) activeScheme.onMouseUp(e);
    });
    
    // Setup camera scheme selector
    document.getElementById('cameraScheme').addEventListener('change', (e) => {
        switchCameraScheme(e.target.value);
    });
    
    // Initialize default scheme (Google Maps Ground Plane)
    switchCameraScheme('ground-plane');
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
    let zoomSpeed = 0.15;  // 15% of distance per tick
    
    // Shift modifier for precise zoom
    if (keyboard.shift) {
        zoomSpeed = 0.03;  // 3% for precise control
    }
    
    // Scroll UP (negative delta) = zoom IN (move toward target)
    // Scroll DOWN (positive delta) = zoom OUT (move away from target)
    const zoomDirection = delta > 0 ? 1 : -1;  // positive = zoom out, negative = zoom in
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
    const markerSize = avgSize * 0.01;  // 1% of average terrain dimension
    
    // Create a bright sphere at the pivot point
    const geometry = new THREE.SphereGeometry(markerSize, 16, 16);
    const material = new THREE.MeshBasicMaterial({ 
        color: 0xff00ff,
        transparent: true,
        opacity: 0.9,
        depthTest: false  // Always visible
    });
    pivotMarker = new THREE.Mesh(geometry, material);
    pivotMarker.position.copy(position);
    scene.add(pivotMarker);
    
    console.log(`ðŸ“ Pivot marker created at (${position.x.toFixed(0)}, ${position.y.toFixed(0)}, ${position.z.toFixed(0)}) with size ${markerSize.toFixed(0)}m`);
    
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
    
    const lonSpan = Math.abs(bounds.right - bounds.left);  // degrees
    const latSpan = Math.abs(bounds.top - bounds.bottom);  // degrees
    
    // Calculate meters per degree at the center latitude
    const centerLat = (bounds.top + bounds.bottom) / 2.0;
    const metersPerDegLon = 111_320 * Math.cos(centerLat * Math.PI / 180);
    const metersPerDegLat = 111_320;  // approximately constant
    
    // Calculate real-world dimensions in meters
    const widthMeters = lonSpan * metersPerDegLon;
    const heightMeters = latSpan * metersPerDegLat;
    
    // Meters per pixel
    const metersPerPixelX = widthMeters / width;
    const metersPerPixelY = heightMeters / height;
    
    console.log(`ðŸ“ Real-world scale:`);
    console.log(`   Size: ${(widthMeters/1000).toFixed(1)} Ã— ${(heightMeters/1000).toFixed(1)} km`);
    console.log(`   Resolution: ${metersPerPixelX.toFixed(1)} Ã— ${metersPerPixelY.toFixed(1)} m/pixel`);
    console.log(`   Vertical exaggeration: ${params.verticalExaggeration}x (1.0 = true Earth scale)`);
    
    return {
        metersPerPixelX,
        metersPerPixelY,
        widthMeters,
        heightMeters
    };
}

function createTerrain() {
    const t0 = performance.now();
    console.log(`ðŸŽ¨ Creating terrain in ${params.renderMode} mode...`);
    
    // Remove old terrain and DISPOSE geometry/materials
    if (terrainMesh) {
        console.log(`ðŸ—‘ï¸ Removing old terrainMesh...`);
        scene.remove(terrainMesh);
        if (terrainMesh.geometry) terrainMesh.geometry.dispose();
        if (terrainMesh.material) {
            if (Array.isArray(terrainMesh.material)) {
                terrainMesh.material.forEach(m => m.dispose());
            } else {
                terrainMesh.material.dispose();
            }
        }
        terrainMesh = null;
    }
    if (wireframeMesh) {
        console.log(`ðŸ—‘ï¸ Removing old wireframeMesh...`);
        scene.remove(wireframeMesh);
        if (wireframeMesh.geometry) wireframeMesh.geometry.dispose();
        if (wireframeMesh.material) wireframeMesh.material.dispose();
        wireframeMesh = null;
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
            terrainMesh.position.z = -(height - 1) * bucketMultiplier / 2;  // NO aspect ratio scaling!
            console.log(`ðŸŽ¯ Bars centered: uniform grid ${width}Ã—${height}, tile size ${bucketMultiplier}, offset (${terrainMesh.position.x.toFixed(1)}, ${terrainMesh.position.z.toFixed(1)})`);
        } else if (params.renderMode === 'points') {
            // Points use uniform grid positioning
            const bucketSize = 1;
            terrainMesh.position.x = -(width - 1) * bucketSize / 2;
            terrainMesh.position.z = -(height - 1) * bucketSize / 2;
            console.log(`ðŸŽ¯ Points centered: uniform grid ${width}Ã—${height}, offset (${terrainMesh.position.x.toFixed(1)}, ${terrainMesh.position.z.toFixed(1)})`);
        } else {
            // Surface mode: PlaneGeometry is already centered, but position it at origin
            terrainMesh.position.set(0, 0, 0);
            console.log(`ðŸŽ¯ Surface centered: geometry naturally centered`);
        }
    }
    
    const t1 = performance.now();
    console.log(`âœ… Terrain created in ${(t1-t0).toFixed(1)}ms`);
    
    stats.vertices = width * height;
    stats.bucketedVertices = width * height;
    
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
    const dummy = new THREE.Object3D();
    
    // Bucket multiplier determines tile size (larger = more chunky visualization)
    const bucketMultiplier = params.bucketSize;
    
    // Create SQUARE bars for uniform 2D grid (no stretching or distortion)
    // Gap: 0% = tiles touching (1.0), 1% = 0.99, 50% = 0.5, 99% = 0.01 (tiny tiles)
    const gapMultiplier = 1 - (params.tileGap / 100);
    const tileSize = gapMultiplier * bucketMultiplier;
    // Use minimal segments (1,1,1) - Y scaling is applied per-instance, XZ never changes
    const baseGeometry = new THREE.BoxGeometry(tileSize, 1, tileSize, 1, 1, 1);
    
    console.log(`ðŸ“¦ PURE 2D GRID: ${width} Ã— ${height} bars (spacing: ${bucketMultiplier}Ã—, gap: ${params.tileGap}%)`);
    console.log(`ðŸ“¦ Tile XZ footprint: ${tileSize.toFixed(2)} Ã— ${tileSize.toFixed(2)} (uniform squares, NEVER changes with Y scale)`);
    console.log(`ðŸ“¦ Grid spacing: X=${bucketMultiplier}, Z=${bucketMultiplier} (uniform, INDEPENDENT of height)`);
    console.log(`ðŸ“¦ Vertical exaggeration: ${params.verticalExaggeration.toFixed(5)}Ã— (affects ONLY Y-axis)`);
    console.log(`ðŸ“¦ Grid approach: Each data point [i,j] â†’ one square tile, no distortion`);
    
    // Collect bar data - uniform grid positioning with square tiles
    // IMPORTANT: width Ã— height are ALREADY BUCKETED dimensions
    // E.g., if bucket size = 2Ã—2, we've already aggregated 4 pixels into 1 value
    // So this loop creates ONE rectangle per bucket, correctly spaced
    const barData = [];
    
    for (let i = 0; i < height; i++) {  // i = row index (bucketed)
        for (let j = 0; j < width; j++) {  // j = col index (bucketed)
            let z = elevation[i] && elevation[i][j];
            
            // Skip null/undefined values entirely - don't render anything for areas outside boundaries
            if (z === null || z === undefined) continue;
            
            const elev = Math.max(z * params.verticalExaggeration, 0.1);
            const color = getColorForElevation(z);
            
            // Position on UNIFORM grid - same spacing in both X and Z directions
            const xPos = j * bucketMultiplier;  // Column Ã— tile size
            const zPos = i * bucketMultiplier;  // Row Ã— tile size (NO aspect ratio!)
            barData.push({ x: xPos, y: elev / 2, z: zPos, height: elev, color });
        }
    }
    
    const barCount = barData.length;
    const material = new THREE.MeshLambertMaterial({
        vertexColors: true,
        flatShading: params.flatShading  // Toggle via UI - affects depth buffer artifact visibility
    });
    
    const instancedMesh = new THREE.InstancedMesh(
        baseGeometry,
        material,
        barCount
    );
    
    // Set transform and color for each instance
    const colorArray = new Float32Array(barCount * 3);
    
    for (let i = 0; i < barCount; i++) {
        const bar = barData[i];
        
        // CRITICAL: Reset dummy to identity state before setting new transform
        // This ensures no rotation/skew and that scale is ONLY in Y direction
        dummy.rotation.set(0, 0, 0);
        dummy.position.set(bar.x, bar.y, bar.z);
        dummy.scale.set(1, bar.height, 1);  // Scale ONLY Y (height), NOT X or Z!
        dummy.updateMatrix();
        instancedMesh.setMatrixAt(i, dummy.matrix);
        
        // Set color
        colorArray[i * 3] = bar.color.r;
        colorArray[i * 3 + 1] = bar.color.g;
        colorArray[i * 3 + 2] = bar.color.b;
    }
    
    // Log first few bars for debugging - verify XZ footprint is consistent
    if (barCount > 0) {
        console.log(`ðŸ“¦ Sample bars (verifying XZ footprint is constant):`);
        for (let i = 0; i < Math.min(3, barCount); i++) {
            const bar = barData[i];
            const xMin = bar.x - tileSize/2;
            const xMax = bar.x + tileSize/2;
            const zMin = bar.z - tileSize/2;
            const zMax = bar.z + tileSize/2;
            console.log(`   Bar ${i}: center=(${bar.x.toFixed(1)}, ${bar.y.toFixed(1)}, ${bar.z.toFixed(1)})`);
            console.log(`          XZ extent: X[${xMin.toFixed(2)} to ${xMax.toFixed(2)}] Z[${zMin.toFixed(2)} to ${zMax.toFixed(2)}] = ${tileSize.toFixed(2)}Ã—${tileSize.toFixed(2)}`);
            console.log(`          Height: ${bar.height.toFixed(2)} (Y scale only, XZ scale = 1.0)`);
        }
    }
    
    // CRITICAL: Mark instance matrix as needing GPU update
    instancedMesh.instanceMatrix.needsUpdate = true;
    
    // Add colors as instance attribute
    baseGeometry.setAttribute('instanceColor', new THREE.InstancedBufferAttribute(colorArray, 3));
    instancedMesh.material.vertexColors = true;
    
    // Enable custom vertex colors in shader
    instancedMesh.material.onBeforeCompile = (shader) => {
        shader.vertexShader = shader.vertexShader.replace(
            '#include <color_pars_vertex>',
            `#include <color_pars_vertex>
            attribute vec3 instanceColor;`
        );
        shader.vertexShader = shader.vertexShader.replace(
            '#include <color_vertex>',
            `#include <color_vertex>
            #ifdef USE_INSTANCING
                vColor = instanceColor;
            #endif`
        );
    };
    
    terrainMesh = instancedMesh;
    scene.add(terrainMesh);
    stats.bars = barCount;
    console.log(`âœ… Created ${barCount.toLocaleString()} instanced bars (OPTIMIZED)`);
    console.log(`ðŸ“Š Scene now has ${scene.children.length} total objects`);
    
    // DEBUG: List all meshes in scene
    let meshCount = 0;
    let instancedMeshCount = 0;
    scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh) meshCount++;
        if (obj instanceof THREE.InstancedMesh) {
            instancedMeshCount++;
            console.log(`   ðŸ” InstancedMesh found with ${obj.count} instances`);
        }
    });
    console.log(`ðŸ“Š Total meshes: ${meshCount}, InstancedMeshes: ${instancedMeshCount}`);
    
    // Performance warning and suggestion
    if (barCount > 15000) {
        console.warn(`âš ï¸ Very high bar count (${barCount.toLocaleString()})! Consider:
  â€¢ Increase bucket multiplier to ${Math.ceil(params.bucketSize * 1.5)}Ã—+
  â€¢ Switch to 'Surface' render mode for better performance
  â€¢ Current: ${Math.floor(100 * barCount / (width * height))}% of bucketed grid has data`);
    } else if (barCount > 8000) {
        console.warn(`âš ï¸ High bar count (${barCount.toLocaleString()}). Increase bucket multiplier if laggy.`);
    }
}

function createPointCloudTerrain(width, height, elevation, scale) {
    const geometry = new THREE.BufferGeometry();
    const positions = [];
    const colors = [];
    
    // Uniform grid spacing - treat as simple 2D grid
    const bucketSize = 1;  // Uniform spacing
    
    // GeoTIFF: elevation[row][col] where row=Northâ†'South (i), col=Westâ†'East (j)
    for (let i = 0; i < height; i++) {  // row (North to South)
        for (let j = 0; j < width; j++) {  // column (West to East)
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
        size: bucketSize * 1.5,  // Point size scales with bucket size
        vertexColors: true,
        sizeAttenuation: true
    });
    
    terrainMesh = new THREE.Points(geometry, material);
    scene.add(terrainMesh);
}

function createSurfaceTerrain(width, height, elevation, scale) {
    // Create uniform 2D grid - no geographic corrections
    // Treat data as simple evenly-spaced grid points
    const geometry = new THREE.PlaneGeometry(
        width, height, width - 1, height - 1
    );
    
    const colors = [];
    const positions = geometry.attributes.position;
    
    // GeoTIFF: elevation[row][col] where row=Northâ†'South, col=Westâ†'East
    for (let i = 0; i < height; i++) {  // row (North to South)
        for (let j = 0; j < width; j++) {  // column (West to East)
            const idx = i * width + j;
            let z = elevation[i] && elevation[i][j];
            if (z === null || z === undefined) z = 0;
            
            positions.setZ(idx, z * params.verticalExaggeration);
            
            const color = getColorForElevation(z);
            colors.push(color.r, color.g, color.b);
        }
    }
    
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    geometry.computeVertexNormals();
    
    const material = new THREE.MeshLambertMaterial({  // Faster than MeshStandardMaterial
        vertexColors: true,
        flatShading: params.renderMode === 'wireframe' ? true : params.flatShading,
        wireframe: params.renderMode === 'wireframe',
        side: THREE.DoubleSide
    });
    
    terrainMesh = new THREE.Mesh(geometry, material);
    terrainMesh.rotation.x = -Math.PI / 2;
    scene.add(terrainMesh);
}

function getColorForElevation(elevation) {
    // Special case: elevation at or below sea level (0m) should look like WATER
    if (elevation <= 0.5) {
        return new THREE.Color(0x0066cc);  // Ocean blue for water
    }
    
    const { min, max } = rawElevationData.stats;
    const normalized = Math.max(0, Math.min(1, (elevation - min) / (max - min)));
    
    const schemes = {
        terrain: [
            { stop: 0.0, color: new THREE.Color(0x1a4f63) },
            { stop: 0.2, color: new THREE.Color(0x2d8659) },
            { stop: 0.4, color: new THREE.Color(0x5ea849) },
            { stop: 0.6, color: new THREE.Color(0xa8b840) },
            { stop: 0.8, color: new THREE.Color(0xb87333) },
            { stop: 1.0, color: new THREE.Color(0xe8e8e8) }
        ],
        elevation: [
            { stop: 0.0, color: new THREE.Color(0x0000ff) },
            { stop: 0.5, color: new THREE.Color(0x00ff00) },
            { stop: 1.0, color: new THREE.Color(0xff0000) }
        ],
        grayscale: [
            { stop: 0.0, color: new THREE.Color(0x111111) },
            { stop: 1.0, color: new THREE.Color(0xffffff) }
        ],
        rainbow: [
            { stop: 0.0, color: new THREE.Color(0x9400d3) },
            { stop: 0.2, color: new THREE.Color(0x0000ff) },
            { stop: 0.4, color: new THREE.Color(0x00ff00) },
            { stop: 0.6, color: new THREE.Color(0xffff00) },
            { stop: 0.8, color: new THREE.Color(0xff7f00) },
            { stop: 1.0, color: new THREE.Color(0xff0000) }
        ],
        earth: [
            { stop: 0.0, color: new THREE.Color(0x2C1810) },
            { stop: 0.3, color: new THREE.Color(0x6B5244) },
            { stop: 0.6, color: new THREE.Color(0x8B9A6B) },
            { stop: 1.0, color: new THREE.Color(0xC4B89C) }
        ],
        heatmap: [
            { stop: 0.0, color: new THREE.Color(0x000033) },
            { stop: 0.25, color: new THREE.Color(0x0066ff) },
            { stop: 0.5, color: new THREE.Color(0x00ff66) },
            { stop: 0.75, color: new THREE.Color(0xffff00) },
            { stop: 1.0, color: new THREE.Color(0xff0000) }
        ]
    };
    
    const scheme = schemes[params.colorScheme] || schemes.terrain;
    
    for (let i = 0; i < scheme.length - 1; i++) {
        if (normalized >= scheme[i].stop && normalized <= scheme[i + 1].stop) {
            const localT = (normalized - scheme[i].stop) / (scheme[i + 1].stop - scheme[i].stop);
            return new THREE.Color().lerpColors(scheme[i].color, scheme[i + 1].color, localT);
        }
    }
    
    return scheme[scheme.length - 1].color;
}

function updateTerrainHeight() {
    if (!terrainMesh) return;
    
    if (params.renderMode === 'bars' || params.renderMode === 'points') {
        recreateTerrain();
    } else {
        const positions = terrainMesh.geometry.attributes.position;
        const { width, height, elevation } = processedData;
        
        // Update elevation heights for existing geometry
        for (let i = 0; i < height; i++) {  // row (North to South)
            for (let j = 0; j < width; j++) {  // column (West to East)
                const idx = i * width + j;
                let z = elevation[i] && elevation[i][j];
                if (z === null || z === undefined) z = 0;
                
                positions.setZ(idx, z * params.verticalExaggeration);
            }
        }
        
        positions.needsUpdate = true;
        terrainMesh.geometry.computeVertexNormals();
        
        // Update edge markers to match new height
        updateEdgeMarkers();
    }
}

function updateColors() {
    recreateTerrain();
}

function recreateTerrain() {
    console.log(`ðŸ”„ recreateTerrain() called, render mode: ${params.renderMode}`);
    createTerrain();
}

function recreateBorders() {
    console.log('ðŸ—ºï¸ Creating borders...');
    
    // Remove old borders
    borderMeshes.forEach(mesh => scene.remove(mesh));
    borderMeshes = [];
    
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
                    color: 0xFFFF00,  // YELLOW - highly visible!
                    linewidth: 2,
                    transparent: true,
                    opacity: 0.9
                });
                const line = new THREE.Line(geometry, material);
                scene.add(line);
                borderMeshes.push(line);
                totalSegments++;
            }
        });
    });
    
    const entityCount = allBorders.length;
    const entityType = borderData.states ? 'states' : 'countries';
    console.log(`âœ… Created ${totalSegments} border segments for ${entityCount} ${entityType}`);
}

function updateStats() {
    const statsDiv = document.getElementById('stats');
    const { width, height, stats: dataStats } = rawElevationData;
    const { width: bWidth, height: bHeight } = processedData;
    
    statsDiv.innerHTML = `
        <div class="stat-line">
            <span class="stat-label">Raw Data:</span> 
            <span class="stat-value">${width} Ã— ${height} pixels</span>
        </div>
        <div class="stat-line">
            <span class="stat-label">Bucket Multiplier:</span> 
            <span class="stat-value">${params.bucketSize}Ã—</span>
        </div>
        <div class="stat-line">
            <span class="stat-label">Bucketed Grid:</span> 
            <span class="stat-value">${bWidth} Ã— ${bHeight}</span>
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
    
    // Calculate distances based on actual coordinate extent
    const gridWidth = processedData.width;
    const gridHeight = processedData.height;
    const scale = calculateRealWorldScale();
    
    // Calculate actual coordinate extent (varies by render mode)
    let xExtent, zExtent;
    if (params.renderMode === 'bars') {
        // Bars use integer grid with aspect ratio scaling
        const bucketMultiplier = params.bucketSize;
        const aspectRatio = scale.metersPerPixelY / scale.metersPerPixelX;
        xExtent = (gridWidth - 1) * bucketMultiplier;
        zExtent = (gridHeight - 1) * bucketMultiplier * aspectRatio;
    } else {
        // Other modes use meter-based coordinates
        xExtent = scale.widthMeters;
        zExtent = scale.heightMeters;
    }
    
    const maxDim = Math.max(xExtent, zExtent);
    const distance = maxDim * 2.0;  // Increased from 0.8 for better overview
    const height = maxDim * 1.2;    // Increased from 0.5 for better viewing angle
    
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

function setVertExag(value) {
    params.verticalExaggeration = value;
    document.getElementById('vertExag').value = value;
    document.getElementById('vertExagInput').value = value.toFixed(5);
    
    updateTerrainHeight();
}

function resetCamera() {
    if (!rawElevationData || !processedData) {
        camera.position.set(50, 50, 80);
        controls.target.set(0, 0, 0);
        controls.update();
        return;
    }
    
    // Calculate appropriate camera distance based on actual coordinate extent
    const gridWidth = processedData.width;
    const gridHeight = processedData.height;
    const scale = calculateRealWorldScale();
    
    // Calculate actual coordinate extent (varies by render mode)
    let xExtent, zExtent;
    if (params.renderMode === 'bars') {
        // Bars use integer grid with aspect ratio scaling
        const bucketMultiplier = params.bucketSize;
        const aspectRatio = scale.metersPerPixelY / scale.metersPerPixelX;
        xExtent = (gridWidth - 1) * bucketMultiplier;
        zExtent = (gridHeight - 1) * bucketMultiplier * aspectRatio;
    } else {
        // Other modes use meter-based coordinates
        xExtent = scale.widthMeters;
        zExtent = scale.heightMeters;
    }
    
    const maxDim = Math.max(xExtent, zExtent);
    const camDistance = maxDim * 0.8;  // View from 80% of max dimension
    const camHeight = maxDim * 0.5;    // Height is 50% of max dimension
    
    camera.position.set(camDistance * 0.5, camHeight, camDistance * 0.6);
    controls.target.set(0, 0, 0);
    controls.update();
    
    console.log(`ðŸ“· Camera reset: grid ${gridWidth}Ã—${gridHeight}, extent ${xExtent.toFixed(0)}Ã—${zExtent.toFixed(0)} units`);
}

function exportImage() {
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
    console.log(`ðŸŽ® Switching to ${schemeName} camera scheme`);
    
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
    const key = event.key.toLowerCase();
    
    // Movement keys
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
    
    // Hotkeys
    if (event.key === 'r' || event.key === 'R') {
        resetCamera();
    } else if (event.key === 'f' || event.key === 'F') {
        // F key: Focus on center (Roblox Studio style)
        resetCamera();
    } else if (event.key === ' ') {
        event.preventDefault();
        params.autoRotate = !params.autoRotate;
        controls.autoRotate = params.autoRotate;
        document.getElementById('autoRotate').checked = params.autoRotate;
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
    const rotateSpeed = 0.02;  // Radians per frame for rotation
    let moveSpeed = baseSpeed;
    
    if (keyboard.shift) {
        moveSpeed *= 2.5;  // Shift = faster
    }
    if (keyboard.ctrl) {
        moveSpeed *= 0.3;  // Ctrl = slower/precise
    }
    if (keyboard.alt) {
        moveSpeed *= 4.0;  // Alt = very fast
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
    
    // Q/E: Move camera DOWN/UP (vertical, world space)
    if (keyboard.q) {
        delta.y -= moveSpeed;
    }
    if (keyboard.e) {
        delta.y += moveSpeed;
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

function updateFPS() {
    frameCount++;
    const currentTime = performance.now();
    if (currentTime >= lastTime + 1000) {
        const fps = Math.round((frameCount * 1000) / (currentTime - lastTime));
        document.getElementById('fps-display').textContent = `FPS: ${fps}`;
        frameCount = 0;
        lastTime = currentTime;
    }
}

// ===== RAYCASTING-BASED CAMERA CONTROLS =====
// This provides true "point-stays-under-cursor" dragging behavior

// Initialize ground plane for raycasting fallback (when cursor misses terrain)
// Simple horizontal plane at y=0 - provides consistent reference for dragging
groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);

function raycastToWorld(screenX, screenY) {
    // Convert screen coordinates to normalized device coordinates (-1 to +1)
    const rect = renderer.domElement.getBoundingClientRect();
    const ndcX = ((screenX - rect.left) / rect.width) * 2 - 1;
    const ndcY = -((screenY - rect.top) / rect.height) * 2 + 1;
    
    // Set up raycaster
    raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), camera);
    
    // ALWAYS use ground plane for consistency
    // This eliminates jerkiness from inconsistent terrain intersections
    const planeIntersect = new THREE.Vector3();
    const intersected = raycaster.ray.intersectPlane(groundPlane, planeIntersect);
    
    if (intersected) {
        return planeIntersect;
    }
    
    // Should never happen, but just in case
    console.warn('âš ï¸ Raycast failed completely');
    return null;
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
            console.log('ðŸ–±ï¸ Pan started');
        } else {
            console.warn('âš ï¸ Failed to raycast world point');
            isPanning = false;
        }
    }
    // Right button or Ctrl+Left = Rotate
    else if (event.button === 2 || (event.button === 0 && event.ctrlKey)) {
        isRotating = true;
        rotateStart.set(event.clientX, event.clientY);
        rotateStartCameraPos = camera.position.clone();
        rotateStartTargetPos = controls.target.clone();
        console.log('ðŸ”„ Rotation started');
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
}

function onMouseUp(event) {
    if (isPanning) {
        console.log('ðŸ–±ï¸ Pan ended');
        isPanning = false;
        panStartWorldPoint = null;
        panStartCameraPos = null;
        panStartTargetPos = null;
    }
    
    if (isRotating) {
        console.log('ðŸ”„ Rotation ended');
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
}

// Toggle controls help window
function toggleControlsHelp() {
    const window = document.getElementById('controls-help-window');
    const button = document.getElementById('controls-help-toggle');
    
    if (window.classList.contains('open')) {
        window.classList.remove('open');
        button.textContent = 'â“ Controls';
    } else {
        window.classList.add('open');
        button.textContent = 'â“ Close';
    }
}

// Start when page loads
window.addEventListener('load', init);
