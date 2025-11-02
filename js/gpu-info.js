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
 * Run GPU performance benchmark
 * @param {THREE.WebGLRenderer} testRenderer - Three.js renderer to test
 * @param {WebGLRenderingContext} testGL - WebGL context to test
 * @returns {Object} Benchmark results
 */
function benchmarkGPU(testRenderer, testGL) {
    const results = {
        triangleTest: null,
        fillRateTest: null,
        textureTest: null,
        overallScore: null
    };

    try {
        // Test 1: Triangle rendering performance
        const triangleScene = new THREE.Scene();
        const triangleCamera = new THREE.PerspectiveCamera(60, 1, 0.1, 1000);
        triangleCamera.position.z = 50;

        // Create many small triangles
        const triangleCount = 10000;
        const triangleGeometry = new THREE.BufferGeometry();
        const vertices = new Float32Array(triangleCount * 9); // 3 vertices * 3 components

        for (let i = 0; i < triangleCount * 9; i += 9) {
            const x = Math.random() * 100 - 50;
            const y = Math.random() * 100 - 50;
            const z = Math.random() * 100 - 50;

            vertices[i] = x;
            vertices[i + 1] = y;
            vertices[i + 2] = z;

            vertices[i + 3] = x + Math.random() * 2;
            vertices[i + 4] = y + Math.random() * 2;
            vertices[i + 5] = z;

            vertices[i + 6] = x;
            vertices[i + 7] = y + Math.random() * 2;
            vertices[i + 8] = z;
        }

        triangleGeometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
        const triangleMaterial = new THREE.MeshBasicMaterial({ color: 0xff0000 });
        const triangleMesh = new THREE.Mesh(triangleGeometry, triangleMaterial);
        triangleScene.add(triangleMesh);

        // Measure triangle rendering time
        const triangleStart = performance.now();
        const triangleFrames = 60;
        for (let i = 0; i < triangleFrames; i++) {
            triangleMesh.rotation.y += 0.01;
            testRenderer.render(triangleScene, triangleCamera);
        }
        const triangleTime = performance.now() - triangleStart;
        const triangleFPS = (triangleFrames / triangleTime) * 1000;

        results.triangleTest = {
            fps: triangleFPS.toFixed(1),
            avgFrameTime: (triangleTime / triangleFrames).toFixed(2),
            triangleCount
        };

        // Test 2: Fill rate (large textured quad)
        const fillScene = new THREE.Scene();
        const fillCamera = new THREE.PerspectiveCamera(60, 1, 0.1, 1000);
        fillCamera.position.z = 2;

        const fillGeometry = new THREE.PlaneGeometry(10, 10);
        const canvas = document.createElement('canvas');
        canvas.width = 2048;
        canvas.height = 2048;
        const ctx = canvas.getContext('2d');
        const imageData = ctx.createImageData(2048, 2048);
        for (let i = 0; i < imageData.data.length; i += 4) {
            imageData.data[i] = Math.random() * 255;
            imageData.data[i + 1] = Math.random() * 255;
            imageData.data[i + 2] = Math.random() * 255;
            imageData.data[i + 3] = 255;
        }
        ctx.putImageData(imageData, 0, 0);

        const fillTexture = new THREE.CanvasTexture(canvas);
        const fillMaterial = new THREE.MeshBasicMaterial({ map: fillTexture });
        const fillMesh = new THREE.Mesh(fillGeometry, fillMaterial);
        fillScene.add(fillMesh);

        const fillStart = performance.now();
        const fillFrames = 60;
        for (let i = 0; i < fillFrames; i++) {
            fillMesh.rotation.z += 0.01;
            testRenderer.render(fillScene, fillCamera);
        }
        const fillTime = performance.now() - fillStart;
        const fillFPS = (fillFrames / fillTime) * 1000;

        results.fillRateTest = {
            fps: fillFPS.toFixed(1),
            avgFrameTime: (fillTime / fillFrames).toFixed(2),
            textureSize: '2048x2048'
        };

        // Test 3: Texture sampling
        const textureStart = performance.now();
        const maxTextureSize = testGL.getParameter(testGL.MAX_TEXTURE_SIZE);
        const textureTime = performance.now() - textureStart;

        results.textureTest = {
            maxSize: maxTextureSize,
            queryTime: textureTime.toFixed(2)
        };

        // Calculate overall score (normalized)
        const triangleScore = Math.min(triangleFPS / 60, 1) * 100;
        const fillScore = Math.min(fillFPS / 60, 1) * 100;
        const textureScore = Math.min(maxTextureSize / 16384, 1) * 100;

        results.overallScore = ((triangleScore + fillScore + textureScore) / 3).toFixed(1);

        // Cleanup
        triangleGeometry.dispose();
        triangleMaterial.dispose();
        fillGeometry.dispose();
        fillMaterial.dispose();
        fillTexture.dispose();

    } catch (error) {
        results.error = error.message;
    }

    return results;
}

// Export to window for global access
window.GPUInfo = {
    detectGPU,
    benchmarkGPU
};

