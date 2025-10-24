# CRITICAL: Depth Buffer Precision and Camera Near/Far Planes

**⚠️ DO NOT IGNORE THIS DOCUMENT ⚠️**

This issue has caused significant debugging time in the past. Read this before modifying camera settings.

## The Problem

### Symptoms
When viewing 3D terrain, you may see **jagged "bleeding" artifacts** where distant geometry appears to render in front of nearby geometry, even when they are clearly separated. These artifacts:

- Appear/disappear as the camera rotates
- Are worse at oblique/grazing angles
- Are better when viewing perpendicular to surfaces
- Persist even with gaps between geometry (e.g., 21% tile gap still shows artifacts)
- Make it look like "z-fighting" but z-fighting is not the cause

### Visual Example
```
     Nearby green cube ───┐
                          │
    ┌─────────────┐       │
    │   GREEN     │       │
    │   CUBE      │◄──────┘
    │             │
    └─────────────┘
           │
           └── Distant brown cube "bleeds through" 
               at certain camera angles
```

### Root Cause: Depth Buffer Precision

The depth buffer (typically 24-bit) stores depth information for every pixel. When the ratio between the **camera's near plane and far plane** is too extreme, the depth buffer loses precision and cannot reliably determine which geometry is closer.

**The depth buffer precision formula:**
```
Precision loss ∝ far / near
```

With extreme ratios like `near=0.001, far=50,000,000`, you get a **50 billion:1 ratio**. The 24-bit depth buffer simply cannot maintain precision across this range.

## The Solution

### Current (Correct) Settings
```javascript
camera = new THREE.PerspectiveCamera(60, aspect, 1, 100000);
//                                              ^  ^^^^^^
//                                           near   far
//                                           1m    100km
//                                         Ratio: 100,000:1 ✅
```

### DO NOT USE (Previous Broken Settings)
```javascript
camera = new THREE.PerspectiveCamera(60, aspect, 0.001, 50000000);
//                                              ^^^^^  ^^^^^^^^
//                                              BAD     BAD
//                                         Ratio: 50,000,000,000:1 ❌
```

## Rules to Follow

### ✅ GOOD PRACTICES
1. **Near plane:** Should be as far as possible without clipping nearby objects
   - Typical range: `1` to `10` meters for terrain visualization
   - NEVER go below `0.1` unless absolutely necessary

2. **Far plane:** Should be as close as possible while showing all needed objects
   - Typical range: `10,000` to `100,000` meters for terrain
   - NEVER exceed `1,000,000` unless using logarithmic depth buffer

3. **Ratio:** Keep under `1,000,000:1`
   - Good: `100,000:1` (current settings)
   - Acceptable: `1,000,000:1` (maximum)
   - Bad: `50,000,000,000:1` (guaranteed artifacts)

### ❌ NEVER DO THIS
```javascript
// ❌ "I want to see everything from very close to very far"
camera = new THREE.PerspectiveCamera(60, aspect, 0.001, 10000000);

// ❌ "Let me just make far plane infinite to be safe"
camera = new THREE.PerspectiveCamera(60, aspect, 1, Number.MAX_VALUE);

// ❌ "This scene is huge, I need near=0.0001"
camera = new THREE.PerspectiveCamera(60, aspect, 0.0001, 100000);
```

## Advanced Solutions (If You Need Extreme View Distances)

If you genuinely need to see objects from 1mm to 1000km, don't just increase the far plane. Instead:

1. **Logarithmic Depth Buffer**
   - Requires custom shaders
   - Provides better precision across extreme ranges
   - More complex to implement

2. **Dynamic Near/Far Adjustment**
   - Calculate near/far based on current scene bounds
   - Update planes as camera moves
   - Maintains good precision at all times

3. **Multi-Pass Rendering**
   - Render near objects in one pass
   - Render far objects in another pass
   - Composite results

4. **Level of Detail (LOD)**
   - Don't render distant objects at full detail
   - Reduces far plane requirements

## Where This Is Protected in Code

### Main Scene Camera
**File:** `interactive_viewer_advanced.html`  
**Location:** `setupScene()` function, lines ~1394-1425

```javascript
// ============================================================================
// CRITICAL: CAMERA NEAR/FAR PLANE RATIO - DO NOT MODIFY WITHOUT READING THIS
// ============================================================================
const aspect = window.innerWidth / window.innerHeight;
camera = new THREE.PerspectiveCamera(60, aspect, 1, 100000);  // 1m to 100km
```

**Protection:** Large comment block explaining the issue. Read it before changing.

### Compass Camera
**File:** `interactive_viewer_advanced.html`  
**Location:** `setupCompass()` function, lines ~1126-1128

```javascript
// Note: 0.1 to 100 = 1000:1 ratio is acceptable here because compass scene
// has minimal depth (all objects within a few units). Main camera needs stricter limits.
compassCamera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
```

**Note:** Compass has different requirements (small scene, limited depth).

## Testing for This Issue

If you suspect depth buffer problems:

1. **Check the symptoms:**
   - Does the artifact vary with camera angle?
   - Does it affect separated geometry (not overlapping)?
   - Is it worse at oblique angles?

2. **Check near/far ratio:**
   ```javascript
   console.log('Near/Far ratio:', camera.far / camera.near);
   // Should be < 1,000,000
   ```

3. **Test with conservative values:**
   ```javascript
   camera.near = 1;
   camera.far = 10000;
   camera.updateProjectionMatrix();
   ```

4. **Rotate camera to different angles:**
   - If artifacts disappear at some angles, it's depth buffer precision
   - If artifacts persist at all angles identically, it's something else (z-fighting, etc.)

## Related Issues (NOT the Same Thing)

### Z-Fighting
- **Cause:** Two surfaces at exactly the same depth
- **Symptoms:** Flickering between two surfaces, always in same location
- **Solution:** Separate geometry, use depth offset
- **Not affected by camera angle**

### Near Plane Clipping
- **Cause:** Near plane too far, clips nearby geometry
- **Symptoms:** Objects disappear when camera gets close
- **Solution:** Decrease near plane (but watch the ratio!)

### Far Plane Clipping
- **Cause:** Far plane too close, clips distant geometry
- **Symptoms:** Objects disappear in the distance
- **Solution:** Increase far plane (but watch the ratio!)

## History

- **October 2025:** Issue discovered after changing camera from reasonable values to extreme values
- Symptoms: Jagged bleeding artifacts at oblique angles, even with 21% tile gaps
- Debugging time: Multiple hours across several sessions
- **Root cause:** Camera near/far ratio of 50 billion:1
- **Fix:** Changed to 100,000:1 ratio (near=1, far=100000)
- **Result:** Complete elimination of artifacts

## References

- [Three.js PerspectiveCamera Documentation](https://threejs.org/docs/#api/en/cameras/PerspectiveCamera)
- [OpenGL Depth Buffer Precision](https://www.khronos.org/opengl/wiki/Depth_Buffer_Precision)
- [Depth Buffer Precision Blog Post](https://developer.nvidia.com/content/depth-precision-visualized)

## Final Warning

**If you change the camera near/far planes and start seeing weird rendering artifacts:**

1. Check this document first
2. Calculate your near/far ratio
3. If ratio > 1,000,000:1, that's your problem
4. Don't waste hours debugging - just fix the ratio

**This has been documented so you don't have to rediscover it.**

