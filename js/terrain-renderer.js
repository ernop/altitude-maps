/**
 * Terrain Renderer Module
 * 
 * PURPOSE:
 * Create and manage terrain geometry (bars, points, surface modes).
 * Handles all terrain mesh creation, updates, and positioning.
 * 
 * FEATURES:
 * - Create terrain in three modes: bars, points, surface
 * - Update terrain height (vertical exaggeration)
 * - Recreate terrain (bucket size changes, etc.)
 * - Center terrain based on render mode
 * - Manage terrain statistics
 * - Coordinate with camera schemes for bounds
 * 
 * DESIGN NOTES:
 * - Single place for all terrain geometry creation
 * - Clear separation from visual appearance (MapShading handles colors)
 * - Accesses shared state via window globals (scene, terrainGroup, etc.)
 * - Follows LLM-friendly pattern: explicit over implicit
 * 
 * RELATIONSHIP TO MAP SHADING:
 * - Terrain Renderer: Creates geometry (mesh structure, vertices, instanced meshes)
 * - Map Shading: Applies visual appearance (colors, materials, lighting)
 * - Clear separation: Geometry vs. Appearance
 * - Terrain Renderer calls Map Shading during creation to apply initial colors
 * 
 * DEPENDS ON:
 * - Global: window.scene, window.terrainGroup, window.terrainMesh
 * - Global: window.barsInstancedMesh, window.barsIndexToRow, window.barsIndexToCol, window.barsTileSize, window.barsDummy
 * - Global: window.lastBarsExaggerationInternal, window.lastPointsExaggerationInternal, window.lastBarsTileSize
 * - Global: window.terrainStats, window.processedData, window.params
 * - Global: window.edgeMarkers, window.controls
 * - Functions: getColorForElevation(), setLastColorIndex() (from viewer-advanced wrappers)
 * - Functions: calculateRealWorldScale() (from geometry-utils)
 * - Functions: createEdgeMarkers(), createConnectivityLabels(), updateStats(), appendActivityLog()
 */

(function() {
    'use strict';

    // Prevent duplicate initialization
    if (window.TerrainRenderer) {
        console.warn('[TerrainRenderer] Already initialized');
        return;
    }

    /**
     * Create terrain based on current render mode
     */
    function create() {
        const t0 = performance.now();

        // Remove old terrain and DISPOSE geometry/materials
        if (window.terrainGroup) {
            window.scene.remove(window.terrainGroup);
        }

        // Create new terrain group (centered at world origin for rotation)
        window.terrainGroup = new THREE.Group();
        window.terrainGroup.position.set(0, 0, 0);
        window.scene.add(window.terrainGroup);
        // Expose for camera controls
        if (typeof window !== 'undefined') {
            window.terrainGroup = window.terrainGroup;
        }

        const { width, height, elevation } = window.processedData;

        // Calculate real-world scale
        let scale;
        if (typeof calculateRealWorldScale === 'function') {
            scale = calculateRealWorldScale();
        } else if (window.GeometryUtils && typeof window.GeometryUtils.calculateRealWorldScale === 'function') {
            scale = window.GeometryUtils.calculateRealWorldScale();
        } else {
            scale = { widthMeters: 1000, heightMeters: 1000 };
        }

        if (window.params.renderMode === 'bars') {
            createBars(width, height, elevation, scale);
        } else if (window.params.renderMode === 'points') {
            createPoints(width, height, elevation, scale);
        } else {
            // Fallback to bars if unknown render mode (surface/wireframe removed)
            console.warn(`Unknown render mode '${window.params.renderMode}', falling back to 'bars'`);
            window.params.renderMode = 'bars';
            createBars(width, height, elevation, scale);
        }

        // Center terrain - different centering for different modes
        // Note: Position is preserved in recreate() to keep map fixed when bucket size changes
        if (window.terrainMesh) {
            if (window.params.renderMode === 'bars') {
                // Bars use UNIFORM 2D grid - same spacing in X and Z (no aspect ratio)
                const bucketMultiplier = window.params.bucketSize;
                window.terrainMesh.position.x = -(width - 1) * bucketMultiplier / 2;
                window.terrainMesh.position.z = -(height - 1) * bucketMultiplier / 2; // NO aspect ratio scaling!
                console.log(`Bars centered: uniform grid ${width}x${height}, tile size ${bucketMultiplier}, offset (${window.terrainMesh.position.x.toFixed(1)}, ${window.terrainMesh.position.z.toFixed(1)})`);
            } else if (window.params.renderMode === 'points') {
                // Points use uniform grid positioning, scaled by bucketSize
                const bucketSize = window.params.bucketSize;
                window.terrainMesh.position.x = -(width - 1) * bucketSize / 2;
                window.terrainMesh.position.z = -(height - 1) * bucketSize / 2;
                console.log(`Points centered: uniform grid ${width}x${height}, bucket size ${bucketSize}, offset (${window.terrainMesh.position.x.toFixed(1)}, ${window.terrainMesh.position.z.toFixed(1)})`);
            }
        }

        const t1 = performance.now();
        if (typeof appendActivityLog === 'function') {
            appendActivityLog(`Terrain created in ${(t1 - t0).toFixed(1)}ms`);
        }

        if (window.terrainStats) {
            window.terrainStats.vertices = width * height;
            window.terrainStats.bucketedVertices = width * height;
        }

        // Update camera scheme with terrain bounds for F key reframing
        if (window.controls && window.controls.activeScheme && window.controls.activeScheme.setTerrainBounds) {
            // Calculate bounds based on render mode
            if (window.params.renderMode === 'bars') {
                const bucketMultiplier = window.params.bucketSize;
                const halfWidth = (width - 1) * bucketMultiplier / 2;
                const halfDepth = (height - 1) * bucketMultiplier / 2;
                window.controls.activeScheme.setTerrainBounds(-halfWidth, halfWidth, -halfDepth, halfDepth);
            } else if (window.params.renderMode === 'points') {
                const bucketSize = window.params.bucketSize;
                const halfWidth = (width - 1) * bucketSize / 2;
                const halfDepth = (height - 1) * bucketSize / 2;
                window.controls.activeScheme.setTerrainBounds(-halfWidth, halfWidth, -halfDepth, halfDepth);
            }
        }

        // PRODUCT REQUIREMENT: Edge markers must stay fixed when vertical exaggeration changes
        // Only create edge markers if they don't exist yet (prevents movement on exaggeration change)
        if (window.edgeMarkers && window.edgeMarkers.length === 0) {
            if (typeof createEdgeMarkers === 'function') {
                createEdgeMarkers();
            }
            // Update compass rose when markers are recreated
            if (window.CompassRose && typeof window.CompassRose.update === 'function') {
                window.CompassRose.update();
            }
            // Create connectivity labels alongside edge markers
            if (typeof createConnectivityLabels === 'function') {
                createConnectivityLabels();
            }
        }

        if (typeof updateStats === 'function') {
            updateStats();
        }
    }

    /**
     * Create bars terrain (instanced meshes)
     */
    function createBars(width, height, elevation, scale) {
        // PURE 2D GRID APPROACH:
        // Treat the input data as a perfect 2D grid with uniform square tiles.
        // This is the correct approach because:
        // 1. The input data IS a perfect 2D array - no gaps, overlaps, or irregularities
        // 2. Each data point [i,j] should map to one uniform tile in 3D space
        // 3. Bucket size just creates larger square tiles (more chunky/blurred), not stretching
        // 4. This avoids distortion from real-world projections and maintains data integrity
        // Use shared dummy object for instancing transforms to avoid reallocations

        // Bucket multiplier determines tile size (larger = more chunky visualization)
        const bucketMultiplier = window.params.bucketSize;

        // Create SQUARE bars for uniform 2D grid (no stretching or distortion)
        // Tile gap always 0% (tiles touching)
        const tileSize = bucketMultiplier;
        // Base unit cube (1x1x1)
        const baseGeometry = new THREE.BoxGeometry(1, 1, 1, 1, 1, 1);

        console.log(`PURE 2D GRID: ${width} x ${height} bars (spacing: ${bucketMultiplier}x, no gap)`);
        console.log(`Tile XZ footprint: ${tileSize.toFixed(2)} x ${tileSize.toFixed(2)} (uniform squares, NEVER changes with Y scale)`);
        console.log(`Grid spacing: X=${bucketMultiplier}, Z=${bucketMultiplier} (uniform, INDEPENDENT of height)`);
        console.log(`Vertical exaggeration: ${window.params.verticalExaggeration.toFixed(5)}x (affects ONLY Y-axis)`);
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
        window.barsIndexToRow = new Int32Array(barCount);
        window.barsIndexToCol = new Int32Array(barCount);

        let idx = 0;
        for (let i = 0; i < height; i++) {
            const row = elevation[i];
            if (!row) continue;
            for (let j = 0; j < width; j++) {
                let z = row[j];
                if (z === null || z === undefined) continue;

                const elev = Math.max(z * window.params.verticalExaggeration, 0.1);
                const xPos = j * bucketMultiplier;
                const zPos = i * bucketMultiplier;
                const yPos = elev * 0.5;

                window.barsDummy.rotation.set(0, 0, 0);
                window.barsDummy.position.set(xPos, yPos, zPos);
                window.barsDummy.scale.set(tileSize, elev, tileSize);
                window.barsDummy.updateMatrix();
                instancedMesh.setMatrixAt(idx, window.barsDummy.matrix);

                const c = typeof getColorForElevation === 'function' ? getColorForElevation(z) : new THREE.Color(0x808080);
                colorArray[idx * 3] = c.r;
                colorArray[idx * 3 + 1] = c.g;
                colorArray[idx * 3 + 2] = c.b;

                window.barsIndexToRow[idx] = i;
                window.barsIndexToCol[idx] = j;
                idx++;
            }
        }

        // Persist references for fast, in-place updates (no rebuilds)
        window.barsInstancedMesh = instancedMesh;
        window.barsTileSize = tileSize;

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

        window.terrainMesh = instancedMesh;
        window.terrainGroup.add(window.terrainMesh); // Add to group instead of scene directly
        // Expose for camera controls
        if (typeof window !== 'undefined') {
            window.terrainMesh = window.terrainMesh;
        }
        if (window.terrainStats) {
            window.terrainStats.bars = barCount;
        }
        // Record the internal exaggeration used when building bars and reset uniform to 1.0
        window.lastBarsExaggerationInternal = window.params.verticalExaggeration;
        window.lastBarsTileSize = tileSize;
        if (window.terrainMesh.material && window.terrainMesh.material.userData && window.terrainMesh.material.userData.uExaggerationUniform) {
            window.terrainMesh.material.userData.uExaggerationUniform.value = 1.0;
        }
        if (window.terrainMesh.material && window.terrainMesh.material.userData && window.terrainMesh.material.userData.uTileScaleUniform) {
            window.terrainMesh.material.userData.uTileScaleUniform.value = 1.0;
        }
        console.log(`Created ${barCount.toLocaleString()} instanced bars (OPTIMIZED)`);
        console.log(`Scene now has ${window.scene.children.length} total objects`);

        // DEBUG: List all meshes in scene
        let meshCount = 0;
        let instancedMeshCount = 0;
        window.scene.traverse((obj) => {
            if (obj instanceof THREE.Mesh) meshCount++;
            if (obj instanceof THREE.InstancedMesh) {
                instancedMeshCount++;
            }
        });
        console.log(`Total meshes: ${meshCount}, InstancedMeshes: ${instancedMeshCount}`);

        // Performance warning and suggestion
        if (barCount > 15000) {
            console.warn(`Very high bar count (${barCount.toLocaleString()})! Consider:
 - Increase bucket multiplier to ${Math.ceil(window.params.bucketSize * 1.5)}x+
 - Switch to 'Points' render mode for better performance
 - Current: ${Math.floor(100 * barCount / (width * height))}% of bucketed grid has data`);
        } else if (barCount > 8000) {
            console.warn(`High bar count (${barCount.toLocaleString()}). Increase bucket multiplier if laggy.`);
        }
    }

    /**
     * Create points terrain (point cloud)
     */
    function createPoints(width, height, elevation, scale) {
        const geometry = new THREE.BufferGeometry();
        const positions = [];
        const colors = [];

        // Uniform grid spacing - treat as simple 2D grid, scaled by bucketSize
        const bucketSize = window.params.bucketSize; // Match bars mode spacing

        // GeoTIFF: elevation[row][col] where row=North->South (i), col=West->East (j)
        for (let i = 0; i < height; i++) { // row (North to South)
            for (let j = 0; j < width; j++) { // column (West to East)
                let z = elevation[i] && elevation[i][j];
                if (z === null || z === undefined) z = 0;

                // Uniform 2D grid positioning
                const xPos = j * bucketSize;
                const zPos = i * bucketSize;
                positions.push(xPos, z * window.params.verticalExaggeration, zPos);

                const color = typeof getColorForElevation === 'function' ? getColorForElevation(z) : new THREE.Color(0x808080);
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

        window.terrainMesh = points;
        window.terrainGroup.add(window.terrainMesh); // Add to group instead of scene directly
        // Expose for camera controls
        if (typeof window !== 'undefined') {
            window.terrainMesh = window.terrainMesh;
        }
        window.lastPointsExaggerationInternal = window.params.verticalExaggeration;
        if (window.terrainMesh.material && window.terrainMesh.material.userData && window.terrainMesh.material.userData.uExaggerationUniform) {
            window.terrainMesh.material.userData.uExaggerationUniform.value = 1.0;
        }
    }

    /**
     * Create surface terrain (mesh)
     */
    function createSurface(width, height, elevation, scale) {
        // Create uniform 2D grid - no geographic corrections
        // Treat data as simple evenly-spaced grid points
        // Scale by bucketSize to match bars mode extent
        const bucketMultiplier = window.params.bucketSize;
        const geometry = new THREE.PlaneGeometry(
            width * bucketMultiplier, height * bucketMultiplier, width - 1, height - 1
        );

        const isWireframe = (window.params.renderMode === 'wireframe');
        const colors = isWireframe ? null : [];
        const positions = geometry.attributes.position;

        // GeoTIFF: elevation[row][col] where row=North->South, col=West->East
        for (let i = 0; i < height; i++) { // row (North to South)
            for (let j = 0; j < width; j++) { // column (West to East)
                const idx = i * width + j;
                let z = elevation[i] && elevation[i][j];
                if (z === null || z === undefined) z = 0;

                positions.setZ(idx, z * window.params.verticalExaggeration);

                if (!isWireframe) {
                    if (typeof setLastColorIndex === 'function') {
                        setLastColorIndex(i, j);
                    }
                    const color = typeof getColorForElevation === 'function' ? getColorForElevation(z) : new THREE.Color(0x808080);
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

        window.terrainMesh = new THREE.Mesh(geometry, material);
        window.terrainMesh.rotation.x = -Math.PI / 2;
        window.terrainGroup.add(window.terrainMesh); // Add to group instead of scene directly
        // Expose for camera controls
        if (typeof window !== 'undefined') {
            window.terrainMesh = window.terrainMesh;
        }
    }

    /**
     * Update terrain height (vertical exaggeration)
     */
    function updateHeight() {
        if (!window.terrainMesh) return;

        if (window.params.renderMode === 'bars') {
            if (!window.barsInstancedMesh) {
                if (typeof recreate === 'function') {
                    recreate();
                }
                return;
            }
            // Instant update: update shader uniform to ratio of new/internal used value
            const u = window.barsInstancedMesh.material && window.barsInstancedMesh.material.userData && window.barsInstancedMesh.material.userData.uExaggerationUniform;
            if (u) {
                const base = (window.lastBarsExaggerationInternal && window.lastBarsExaggerationInternal > 0) ? window.lastBarsExaggerationInternal : window.params.verticalExaggeration;
                u.value = window.params.verticalExaggeration / base;
            }
            // Note: bucket changes handled via recreate()
        } else if (window.params.renderMode === 'points') {
            // Instant update for points via uniform ratio (no CPU loops)
            const u = window.terrainMesh.material && window.terrainMesh.material.userData && window.terrainMesh.material.userData.uExaggerationUniform;
            if (u) {
                const base = (window.lastPointsExaggerationInternal && window.lastPointsExaggerationInternal > 0) ? window.lastPointsExaggerationInternal : window.params.verticalExaggeration;
                u.value = window.params.verticalExaggeration / base;
            }
        } else {
            // Unknown render mode - fallback to bars
            console.warn(`Unknown render mode '${window.params.renderMode}' in updateHeight, falling back to bars`);
            window.params.renderMode = 'bars';
            if (typeof recreate === 'function') {
                recreate();
            }
        }
    }

    /**
     * Recreate terrain (preserves position and rotation)
     */
    function recreate() {
        const startTime = performance.now();

        // Log call stack to understand where recreations are coming from
        const stack = new Error().stack;
        const caller = stack.split('\n')[2]?.trim() || 'unknown';
        console.log(`[TERRAIN] recreateTerrain() called from: ${caller}`);

        // Preserve terrain position and rotation before recreating
        let oldTerrainPos = null;
        let oldTerrainGroupRotation = null;

        if (window.terrainMesh) {
            oldTerrainPos = window.terrainMesh.position.clone();
        }
        if (window.terrainGroup) {
            oldTerrainGroupRotation = window.terrainGroup.rotation.clone();
        }

        create();

        // Restore terrain position if it existed before (keeps map in same place when bucket size changes)
        if (oldTerrainPos && window.terrainMesh) {
            window.terrainMesh.position.copy(oldTerrainPos);
        }

        // Restore terrain group rotation if it was rotated
        if (oldTerrainGroupRotation && window.terrainGroup) {
            window.terrainGroup.rotation.copy(oldTerrainGroupRotation);
        }

        const duration = performance.now() - startTime;
        console.log(`[PERF] recreateTerrain() completed in ${duration.toFixed(1)}ms`);
        return duration;
    }

    // Export module
    window.TerrainRenderer = {
        create: create,
        recreate: recreate,
        updateHeight: updateHeight
    };

})();

