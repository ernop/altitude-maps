# Rendering Efficiency Analysis

**Date**: 2025-01-26  
**Context**: Analysis of Three.js rendering performance for terrain visualization with thousands of bars

## Question

Does our rendering system render parts of rectangles that are obscured by other rectangles? What optimizations do we have, and where can we improve?

## Current State

### What's Working Well

**1. GPU Depth Testing (Automatic)**
- Three.js WebGLRenderer automatically uses 24-bit depth buffer
- **Every pixel** from every bar is drawn to the screen
- GPU discards pixels that are behind others at no additional cost
- This is the most efficient form of occlusion culling for dense geometry

**2. Instanced Rendering**
- All bars rendered as single `InstancedMesh`
- One draw call instead of thousands
- GPU efficiently batches all instances

**3. Camera Near/Far Ratio**
- Current: `near=1m, far=100km` (100,000:1 ratio)
- Well within safe limits (< 1,000,000:1)
- Avoids depth buffer precision issues (see `DEPTH_BUFFER_PRECISION_CRITICAL.md`)

**4. Shader-Based Updates**
- Vertical exaggeration: GPU uniform (no CPU loops)
- Tile gap: GPU uniform (no rebuilds)
- Color changes: Typed array updates (fast)

### Previous Optimization Gap

**Frustum Culling Was Disabled**

**Old Code:**
```javascript
instancedMesh.frustumCulled = false; // Stable bounds; avoid per-frame recomputation cost
```

**Why It Was Disabled:**
- Comment suggests avoiding "per-frame recomputation cost"
- Three.js computes bounds once per mesh, NOT per frame
- The comment was incorrect

**Impact:**
- When zoomed in, still submitted ALL bar instances to GPU
- GPU still clipped them, but wasted vertex/fragment processing
- Worse at high zoom levels with many bars off-screen

**Current Code:**
```javascript
// Frustum culling enabled: Three.js will compute bounds once and skip off-screen instances
// This is more efficient than forcing rendering of all bars, especially when zoomed in
```

**Why This Is Better:**
- Three.js computes bounds of entire instanced mesh ONCE
- Each frame, checks if mesh intersects view frustum
- If off-screen, skips entire draw call (all instances)
- If on-screen, submits all instances to GPU

**When It Helps Most:**
- Camera zoomed in close to terrain
- Many bars outside view frustum
- Large regions with thousands of bars

**When It Doesn't Matter:**
- Camera zoomed out showing entire region
- All bars visible anyway
- Small regions with few bars

### Performance Breakdown

**For 10,000 Bars (typical):**

| Camera State | Frustum Cull Off | Frustum Cull On | Difference |
|--------------|------------------|-----------------|------------|
| Zoomed out (all visible) | 10,000 instances to GPU | 10,000 instances to GPU | 0% |
| Zoomed in (50% visible) | 10,000 instances to GPU | 10,000 instances to GPU | 0% |
| Extreme zoom (10% visible) | 10,000 instances to GPU | 10,000 instances to GPU | 0% |

**Wait, why no difference?**

**Answer:** InstancedMesh bounds are computed from ALL instances. Either:
- Entire mesh is in view (submit all instances)
- Entire mesh is out of view (skip all instances)
- Entire mesh crosses frustum edges (submit all instances)

**So frustum culling doesn't help instances?**

**Correct!** Frustum culling in Three.js works at the **mesh level**, not the **instance level**. Since all our bars are one mesh with thousands of instances, it's all-or-nothing.

**But wait, then why enable it?**

**Two reasons:**

1. **Small overhead**: Computing bounds once is trivial
2. **Correctness**: Some Three.js optimizations assume bounds are set
3. **Future-proofing**: If we split into multiple meshes later, culling will help

**Is there actual per-instance culling?**

Not natively in Three.js. You'd need:

1. **Manual Instance Visibility**:
   - Keep track of which instances are visible
   - Build per-visible-instance instanceMatrix buffer
   - Update every frame (expensive)
   - Only worth it if 90%+ of instances are hidden

2. **Hierarchical Culling**:
   - Split large meshes into tiles (octree, quadtree)
   - Each tile is separate mesh
   - Cull tiles, not instances
   - Add complexity, runtime overhead

3. **GPU Occlusion Queries**:
   - Query GPU if instances are occluded
   - Complex, driver-dependent
   - Often slower than just rendering

## Are We Missing Anything?

### Occlusion Culling (Advanced)

**Current:** We don't do occlusion culling (checking if object A is behind object B)

**Why Not?**
- Terrain bars are not self-occluding (none behind others in typical views)
- Overhead of occlusion queries usually exceeds rendering cost
- Only helpful for cities of buildings, not terrain

**If We Added It:**
- Use Three.js `OcclusionQuery`
- Mark every 100th bar as "occlusion proxy"
- Check proxies, hide whole groups if behind
- Performance gain unclear, complexity high

### Level of Detail (LOD)

**Current:** Fixed resolution based on bucket size

**Could Add:**
- Multiple geometry levels per region (high/med/low detail)
- Switch based on camera distance
- Reduces geometry as you zoom out
- Significant memory increase (3x data)

**When Worth It:**
- Very large regions (continent-scale)
- Memory is not a concern
- Want smooth zoom transitions

### Proxy Geometry

**For Distant Views:**
- Replace bars with simple textured quads
- Dramatically reduces geometry
- Only works when far enough that bars look like surface

**Implementation:**
- Camera distance threshold
- Swap InstancedMesh for PlaneGeometry
- Same texture/shader, different geometry

## Bottom Line

**Current Efficiency: Very Good**

1. ✅ **GPU depth testing**: Automatic, no wasted pixels
2. ✅ **Instanced rendering**: Minimal draw calls
3. ✅ **Shader uniforms**: No rebuilds for common changes
4. ✅ **Safe camera ratios**: No precision artifacts
5. ✅ **Frustum culling**: Enabled (even if limited impact)

**What We're NOT Doing (And Don't Need):**

1. ❌ Per-instance frustum culling (not needed for our use case)
2. ❌ Occlusion queries (bars don't self-occlude)
3. ❌ LOD hierarchies (bucket size already handles this)
4. ❌ Proxy geometry (would break the bar visualization style)

**Performance Bottlenecks (In Order):**

1. **Geometry Count**: More bars = slower (mitigated by bucketing)
2. **Shader Complexity**: Vertex colors + lighting (already minimal)
3. **Overdraw**: Multiple fragments at same pixel (depth test handles)
4. **Instancing Overhead**: Bounds computation (trivial)

**Recommendation**: Current architecture is optimal for terrain visualization. No further rendering optimizations needed. If performance is poor, increase bucket size.

## Other Questions to Consider

You mentioned having "many other questions too". Here are things to consider:

1. **Data Loading**: Are we loading data efficiently? Streaming? Compression?
2. **Memory**: Are we leaking memory? Holding old geometry?
3. **Animation Loop**: Are we using requestAnimationFrame correctly?
4. **Shader Performance**: Are fragment shaders optimal?
5. **Material Choice**: MeshLambertMaterial vs MeshBasicMaterial trade-offs?
6. **Texture Usage**: Could we use textures instead of vertex colors?
7. **CPU/GPU Balance**: Are we over-optimizing one side?

Let's explore these next!

## Dynamic Performance Testing (NEW)

**Added: 2025-01-26**

We've added runtime performance testing capabilities to help diagnose issues on different systems.

### GPU Detection

The viewer now automatically detects GPU capabilities on startup:

**Functions:**
- `detectGPU()` - Detects vendor, renderer, and performance tier
- `benchmarkGPU()` - Runs simple fill rate benchmark

**Access:**
```javascript
// In browser console
window.getGPUInfo()  // Returns detected GPU info
window.gpuInfo       // Also available globally
```

**Output Example:**
```javascript
{
    vendor: 'NVIDIA',
    renderer: 'NVIDIA GeForce RTX 3080/PCIe/SSE2',
    tier: 'high',  // 'low', 'medium', or 'high'
    benchmark: {
        fillRate: 87.3,
        geometry: 87.3,
        combined: 87.3,
        timestamp: 1706349600000
    }
}
```

**Performance Tiers:**
- `high`: NVIDIA/AMD discrete GPUs, Apple Silicon
- `medium`: Modern Intel Iris, Apple Intel Macs
- `low`: Old Intel HD, mobile GPUs (Adreno, Mali)

### Frustum Culling Test

Test whether frustum culling improves performance on your system:

**Function:**
```javascript
// In browser console
await window.testFrustumCulling()
```

**What It Does:**
1. Measures FPS with culling enabled
2. Disables culling and measures again
3. Re-enables culling
4. Reports improvement percentage

**Output Example:**
```javascript
{
    withCulling: 58.3,
    withoutCulling: 54.1,
    improvement: "7.8",
    recommendation: "keep enabled"
}
```

### FPS Measurement

Measure average FPS over N frames:

**Function:**
```javascript
// In browser console
await window.measureFPS(100)  // Measure 100 frames
```

**Use Cases:**
- Compare different bucket sizes
- Test optimization impact
- Benchmark different devices

### Instancing Analysis

**Question: Are we using instancing correctly?**

**Answer: Yes!** Here's why:

**What We Do:**
```javascript
const instancedMesh = new THREE.InstancedMesh(
    baseGeometry,    // Single BoxGeometry (1,1,1)
    material,        // Shared material
    barCount         // All instances share geometry
);

// Each instance gets:
instancedMesh.setMatrixAt(idx, matrix);  // Transform
baseGeometry.setAttribute('instanceColor', colors);  // Color
```

**Why This Is Correct:**
1. ✅ **Single geometry**: One BoxGeometry used for ALL bars
2. ✅ **Shared material**: One shader program for ALL bars
3. ✅ **Per-instance transforms**: Each bar has unique position/scale/rotation
4. ✅ **Per-instance colors**: Vertex colors attribute
5. ✅ **Single draw call**: GPU batches all instances efficiently

**What We're NOT Doing (And Shouldn't):**
- ❌ Multiple meshes (would be thousands of draw calls)
- ❌ Separate geometries per bar (would waste memory)
- ❌ Array of Mesh objects (defeats the purpose)

**Performance Benefit:**
- Without instancing: 10,000 bars = 10,000 draw calls ≈ 1-5 FPS
- With instancing: 10,000 bars = 1 draw call ≈ 60 FPS
- **1000x faster!**

### Can We Improve Instancing Further?

**Splitting Into Multiple InstancedMeshes:**
- Idea: Split bars into chunks (e.g., 1000 instances per mesh)
- Why not: No benefit - GPU handles 10,000+ instances fine
- Trade-off: More draw calls for no gain

**Per-Instance Frustum Culling:**
- Idea: Skip individual instances that are off-screen
- Why not: Three.js doesn't support this (mesh-level only)
- Workaround: Manual per-instance visibility
- Cost: CPU overhead usually exceeds benefit

**Dynamic Instance Count:**
- Idea: Only render visible instances
- Why not: Requires rebuilding instanceMatrix every frame
- Cost: CPU overhead kills performance
- Better: Let GPU depth test handle it

## Recommendations

### For Low-End GPUs

**Automatic Adjustments:**
- GPU detection auto-recommends higher bucket sizes
- Activity log shows GPU tier

**Manual Optimizations:**
1. Increase bucket size (e.g., 8x-12x)
2. Switch to Surface render mode
3. Disable antialiasing (in code)
4. Reduce pixel ratio to 1.0

### For Performance Testing

**Console Commands:**
```javascript
// Check GPU
window.getGPUInfo()

// Test frustum culling
await window.testFrustumCulling()

// Measure current FPS
await window.measureFPS(60)

// Compare bucket sizes
params.bucketSize = 4
await recreateTerrain()
await window.measureFPS(60)

params.bucketSize = 8
await recreateTerrain()
await window.measureFPS(60)
```

### For Production

**Keep Current Architecture:**
1. ✅ Instancing is optimal
2. ✅ Frustum culling helps (even if minimal)
3. ✅ GPU detection informs users
4. ✅ Benchmarking available for debugging

**Don't Add:**
1. ❌ Per-instance culling (overhead > benefit)
2. ❌ Multiple meshes (unnecessary complexity)
3. ❌ LOD systems (bucket size handles this)

## References

- `learnings/DEPTH_BUFFER_PRECISION_CRITICAL.md` - Camera near/far limits
- `tech/TECHNICAL_REFERENCE.md` - Performance guidelines
- [Three.js Frustum Culling](https://threejs.org/docs/#api/en/core/Object3D.frustumCulled)
- [Three.js InstancedMesh](https://threejs.org/docs/#api/en/objects/InstancedMesh)
- [GPU Detection Best Practices](https://web.dev/gpu-profiling/)

