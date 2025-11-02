/**
 * GPU Detection and Benchmarking Module
 * Detects GPU information and runs performance benchmarks
 */

/**
 * Detect GPU information from WebGL context with tier classification
 * @param {THREE.WebGLRenderer} [renderer] - Optional Three.js renderer (uses its GL context)
 * @returns {Object} GPU information object with tier classification
 */
function detectGPU(renderer) {
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

    // Detect vendor and tier
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
 * Detect GPU vendor from renderer string
 * @param {string} renderer - GPU renderer string
 * @returns {string} Detected vendor name
 */
function detectVendorFromRenderer(renderer) {
    const r = renderer.toLowerCase();
    if (r.includes('nvidia') || r.includes('geforce') || r.includes('quadro') || r.includes('tesla')) {
        return 'NVIDIA';
    } else if (r.includes('amd') || r.includes('radeon') || r.includes('ati')) {
        return 'AMD';
    } else if (r.includes('intel')) {
        return 'Intel';
    } else if (r.includes('apple') || r.includes('m1') || r.includes('m2') || r.includes('m3')) {
        return 'Apple';
    } else if (r.includes('mali')) {
        return 'ARM Mali';
    } else if (r.includes('adreno')) {
        return 'Qualcomm Adreno';
    } else if (r.includes('powervr')) {
        return 'PowerVR';
    } else {
        return 'Unknown';
    }
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

// Export to window for global access
window.GPUInfo = {
    detectGPU,
    benchmarkGPU
};

