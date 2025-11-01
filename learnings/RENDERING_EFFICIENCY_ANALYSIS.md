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

## References

- `learnings/DEPTH_BUFFER_PRECISION_CRITICAL.md` - Camera near/far limits
- `tech/TECHNICAL_REFERENCE.md` - Performance guidelines
- [Three.js Frustum Culling](https://threejs.org/docs/#api/en/core/Object3D.frustumCulled)
- [Three.js InstancedMesh](https://threejs.org/docs/#api/en/objects/InstancedMesh)

