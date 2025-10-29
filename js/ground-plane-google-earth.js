// Ground Plane Google Earth Camera
// Based on how Google Earth actually works with a ground plane
//
// Controls:
// - Left drag: Rotate/orbit around clicked point on plane
// - Right drag: Adjust height (altitude) only - move perpendicular to plane
// - Ctrl+Left: Pan along plane
// - Scroll: Zoom to cursor

class GroundPlaneGoogleEarth extends CameraScheme {
    constructor() {
        super('Google Earth (Ground Plane)', 'Left = orbit, Right = height, Ctrl+Left = pan, Middle = look around, Scroll = zoom');
        this.groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
        this.focusPoint = new THREE.Vector3(0, 0, 0); // Point ON the ground plane
        this.raycaster = new THREE.Raycaster();
    }
    
    activate(camera, controls, renderer) {
        super.activate(camera, controls, renderer);
        // Prevent OrbitControls from fighting with this scheme
        this._controlsPrev = this._controlsPrev || {};
        if (this.controls) {
            this._controlsPrev.enabled = typeof this.controls.enabled !== 'undefined' ? this.controls.enabled : undefined;
            this._controlsPrev.enableRotate = this.controls.enableRotate;
            this._controlsPrev.enablePan = this.controls.enablePan;
            this._controlsPrev.enableZoom = this.controls.enableZoom;
            if (typeof this.controls.enabled !== 'undefined') this.controls.enabled = false;
            if (typeof this.controls.enableRotate !== 'undefined') this.controls.enableRotate = false;
            if (typeof this.controls.enablePan !== 'undefined') this.controls.enablePan = false;
            if (typeof this.controls.enableZoom !== 'undefined') this.controls.enableZoom = false;
        }
        
        // Initialize focus point - raycast from camera to ground plane
        const cameraDir = new THREE.Vector3();
        camera.getWorldDirection(cameraDir);
        const ray = new THREE.Ray(camera.position, cameraDir);
        const focusPoint = new THREE.Vector3();
        ray.intersectPlane(this.groundPlane, focusPoint);
        
        if (focusPoint) {
            this.focusPoint.copy(focusPoint);
        }
        
        // Make sure controls.target is on the plane
        this.controls.target.copy(this.focusPoint);
        
        
    }

    cleanup() {
        // Restore OrbitControls configuration
        if (this.controls && this._controlsPrev) {
            if (typeof this._controlsPrev.enabled !== 'undefined' && typeof this.controls.enabled !== 'undefined') {
                this.controls.enabled = this._controlsPrev.enabled;
            }
            if (typeof this.controls.enableRotate !== 'undefined') this.controls.enableRotate = this._controlsPrev.enableRotate;
            if (typeof this.controls.enablePan !== 'undefined') this.controls.enablePan = this._controlsPrev.enablePan;
            if (typeof this.controls.enableZoom !== 'undefined') this.controls.enableZoom = this._controlsPrev.enableZoom;
        }
        this._controlsPrev = undefined;
    }
    
    // Raycast from screen position to ground plane
    raycastToPlane(screenX, screenY) {
        const rect = this.renderer.domElement.getBoundingClientRect();
        const ndcX = ((screenX - rect.left) / rect.width) * 2 - 1;
        const ndcY = -((screenY - rect.top) / rect.height) * 2 + 1;
        
        this.raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), this.camera);
        
        const point = new THREE.Vector3();
        const intersected = this.raycaster.ray.intersectPlane(this.groundPlane, point);
        
        return intersected ? point : null;
    }
    
    onMouseDown(event) {
        if (event.button === 0 && event.ctrlKey) {
            // Ctrl+Left = Pan along plane
            // Raycast to the FIXED ground plane (Y=0) to get starting world point
            const startWorldPoint = this.raycastToPlane(event.clientX, event.clientY);
            
            if (startWorldPoint) {
                this.state.panning = true;
                this.state.panStartWorld = startWorldPoint.clone();
                this.state.cameraStart = this.camera.position.clone();
                // DON'T modify focus yet - just store current focus
                this.state.focusStart = this.focusPoint.clone();
                
            }
            
        } else if (event.button === 0) {
            // Left = Orbit/rotate around clicked point on plane
            const clickedPoint = this.raycastToPlane(event.clientX, event.clientY);
            if (clickedPoint) {
                this.state.orbiting = true;
                this.state.orbitStart = { x: event.clientX, y: event.clientY };
                this.state.orbitPivot = clickedPoint; // The point on plane we orbit around
                this.state.cameraStart = this.camera.position.clone();
                // DON'T modify focus yet - just store current focus
                this.state.focusStart = this.focusPoint.clone();
                
            }
            
        } else if (event.button === 1) {
            // Middle = Look around (rotate camera view direction ONLY, position stays fixed)
            this.state.lookingAround = true;
            this.state.lookStart = { x: event.clientX, y: event.clientY };
            
            // Store camera orientation (quaternion for proper local-axis rotation)
            this.state.quaternionStart = this.camera.quaternion.clone();
            
            // Store the initial focus point - we'll keep it stable during look-around
            this.state.focusStart = this.focusPoint.clone();
            
            
        } else if (event.button === 2) {
            // Right = Adjust height (altitude) only
            this.state.adjustingHeight = true;
            this.state.heightStart = event.clientY;
            this.state.cameraStart = this.camera.position.clone();
            this.state.focusStart = this.focusPoint.clone();
            this.state.initialHeight = this.camera.position.y;
            
        }
    }
    
    onMouseMove(event) {
        if (this.state.panning && this.state.panStartWorld) {
            // Pan: Slide along the ground plane
            // Raycast current mouse position to the FIXED ground plane
            const currentWorldPoint = this.raycastToPlane(event.clientX, event.clientY);
            
            if (currentWorldPoint) {
                // Calculate delta: how far the cursor moved in world space
                const delta = new THREE.Vector3();
                delta.subVectors(this.state.panStartWorld, currentWorldPoint);
                delta.y = 0; // Ensure we stay on ground plane
                
                // Move focus point and camera together by this delta
                this.focusPoint.copy(this.state.focusStart).add(delta);
                this.focusPoint.y = 0;
                
                this.camera.position.copy(this.state.cameraStart).add(delta);
                this.controls.target.copy(this.focusPoint);
            }
        }
        
        if (this.state.orbiting && this.state.orbitPivot) {
            // Orbit: Rotate camera around the clicked point on the plane
            const deltaX = event.clientX - this.state.orbitStart.x;
            const deltaY = event.clientY - this.state.orbitStart.y;
            
            // Calculate the offset from the INITIAL FOCUS (not clicked pivot) to camera
            // This prevents jumping when the clicked point is far from current focus
            const offset = new THREE.Vector3();
            offset.subVectors(this.state.cameraStart, this.state.focusStart);
            
            // Convert to spherical coordinates
            const spherical = new THREE.Spherical();
            spherical.setFromVector3(offset);
            
            // Rotate horizontally (around Y axis / around the pivot)
            spherical.theta -= deltaX * 0.005;
            
            // Rotate vertically (tilt) - limit to prevent flipping
            spherical.phi = Math.max(0.1, Math.min(Math.PI / 2 - 0.01, spherical.phi - deltaY * 0.005));
            
            // Convert back and apply - orbit around INITIAL FOCUS
            offset.setFromSpherical(spherical);
            this.camera.position.copy(this.state.focusStart).add(offset);
            
            // Look at the INITIAL FOCUS (not the clicked point)
            this.camera.lookAt(this.state.focusStart);
            
            // Keep focus stable during orbit
            this.focusPoint.copy(this.state.focusStart);
            this.controls.target.copy(this.focusPoint);
        }
        
        if (this.state.lookingAround) {
            // Look around: Rotate camera around its LOCAL axes (position stays fixed)
            const deltaX = event.clientX - this.state.lookStart.x;
            const deltaY = event.clientY - this.state.lookStart.y;
            
            // Calculate rotation angles
            // Left/Right = rotate around camera's local Y axis (yaw)
            const yawAngle = -deltaX * 0.005;
            
            // Forward/Back = rotate around camera's local X axis (pitch)
            // Forward (negative deltaY) = look down (positive rotation around X)
            // Back (positive deltaY) = look up (negative rotation around X)
            const pitchAngle = -deltaY * 0.003;
            
            // Start from initial orientation
            this.camera.quaternion.copy(this.state.quaternionStart);
            
            // Apply yaw rotation around camera's local Y axis
            const yawQuat = new THREE.Quaternion();
            yawQuat.setFromAxisAngle(new THREE.Vector3(0, 1, 0), yawAngle);
            this.camera.quaternion.multiply(yawQuat);
            
            // Apply pitch rotation around camera's local X axis
            const localXAxis = new THREE.Vector3(1, 0, 0);
            localXAxis.applyQuaternion(this.camera.quaternion);
            const pitchQuat = new THREE.Quaternion();
            pitchQuat.setFromAxisAngle(localXAxis, pitchAngle);
            this.camera.quaternion.multiply(pitchQuat);
            
            // Keep focus point stable during look-around operation
            // (avoiding feedback loops from continuous raycasting)
            this.focusPoint.copy(this.state.focusStart);
            this.controls.target.copy(this.focusPoint);
        }
        
        if (this.state.adjustingHeight) {
            // Height adjustment: Move camera perpendicular to plane (Y-axis only)
            const deltaY = event.clientY - this.state.heightStart;
            
            // Convert mouse movement to height change
            // Positive deltaY (mouse down) = move up
            // Negative deltaY (mouse up) = move down
            const heightChange = -deltaY * 2.0; // Scale factor for sensitivity
            
            // Only change Y position, keep XZ the same
            const newHeight = this.state.initialHeight + heightChange;
            
            // Clamp to reasonable bounds
            if (newHeight > 5 && newHeight < 50000) {
                this.camera.position.y = newHeight;
                
                // Keep looking at the same focus point on the plane
                this.camera.lookAt(this.focusPoint);
            }
        }
    }
    
    onMouseUp(event) {
        if (event.button === 0) {
            
            this.state.panning = false;
            this.state.orbiting = false;
            
        } else if (event.button === 1) {
            
            this.state.lookingAround = false;
            
        } else if (event.button === 2) {
            
            this.state.adjustingHeight = false;
        }
    }
    
    onWheel(event) {
        // Stable zoom with gentle cursor bias via per-gesture anchor.
        // 1) Primary: change camera distance only (no spin)
        // 2) Secondary: apply small lateral shift of BOTH camera and focus toward anchor
        //    to get the "smart" feel without introducing rotation or drift.

        const now = performance.now();
        const anchorExpiryMs = 250; // anchor persists briefly across a wheel burst
        if (!this.state.zoomAnchor || !this.state.zoomAnchorTs || (now - this.state.zoomAnchorTs) > anchorExpiryMs) {
            // Establish new anchor at cursor
            const anchor = this.raycastToPlane(event.clientX, event.clientY);
            if (anchor) {
                this.state.zoomAnchor = anchor.clone();
                this.state.zoomAnchorTs = now;
            }
        } else {
            // Refresh timestamp to keep current anchor during rapid wheel
            this.state.zoomAnchorTs = now;
        }

        const zoomSpeed = 0.1;

        // Current camera-to-focus vector
        const cameraToFocus = new THREE.Vector3();
        cameraToFocus.subVectors(this.camera.position, this.focusPoint);
        const currentDistance = cameraToFocus.length();

        // Calculate new distance
        const factor = event.deltaY > 0 ? 1 + zoomSpeed : 1 - zoomSpeed;
        const newDistance = currentDistance * factor;
        if (newDistance < 5 || newDistance > 50000) return;

        // Compute lateral bias toward anchor (if any)
        if (this.state.zoomAnchor) {
            const focusToAnchor = new THREE.Vector3().subVectors(this.state.zoomAnchor, this.focusPoint);
            focusToAnchor.y = 0; // plane-only shift
            const lateralDistance = focusToAnchor.length();
            if (lateralDistance > 0.01) {
                const lateralDir = focusToAnchor.clone().normalize();
                const relative = lateralDistance / Math.max(currentDistance, 1e-6);
                // Suppress bias when cursor is too far from focus (edge of screen)
                if (relative < 0.75) {
                    // Mild bias amount: scale with distance but keep small
                    const base = currentDistance * (event.deltaY > 0 ? 0.02 : 0.01); // smaller when zooming out
                    const magnitude = Math.min(lateralDistance * 0.15, base);
                    const lateralShift = lateralDir.multiplyScalar(magnitude);
                    // Shift BOTH camera and focus together to avoid rotation/spin
                    this.focusPoint.add(lateralShift);
                    this.focusPoint.y = 0;
                    this.camera.position.add(lateralShift);
                }
            }
        }

        // Now change camera distance along current view vector (no change to direction)
        cameraToFocus.subVectors(this.camera.position, this.focusPoint);
        cameraToFocus.normalize();
        cameraToFocus.multiplyScalar(newDistance);
        this.camera.position.copy(this.focusPoint).add(cameraToFocus);
        this.controls.target.copy(this.focusPoint);
    }
    
    update() {
        // Only update camera orientation if we're NOT actively dragging
        // This prevents "fighting" during pan/orbit operations
        if (this.enabled && this.focusPoint) {
            const isActiveDragging = this.state.panning || this.state.orbiting || this.state.adjustingHeight || this.state.lookingAround;
            if (!isActiveDragging) {
                this.camera.lookAt(this.focusPoint);
            }
        }
    }
}

// Add to schemes
window.CameraSchemes = window.CameraSchemes || {};
window.CameraSchemes['google-earth-plane'] = new GroundPlaneGoogleEarth();

