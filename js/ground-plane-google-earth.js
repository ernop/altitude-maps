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
        
        console.log(`🌍 Google Earth ground plane camera initialized`);
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
            this.state.panning = true;
            // Store BOTH mouse position and world point
            this.state.panStartMouse = { x: event.clientX, y: event.clientY };
            this.state.panStartWorld = this.raycastToPlane(event.clientX, event.clientY);
            if (this.state.panStartWorld) {
                this.state.focusStart = this.focusPoint.clone();
                this.state.cameraStart = this.camera.position.clone();
                console.log('🖱️ Pan started');
            } else {
                this.state.panning = false;
            }
            
        } else if (event.button === 0) {
            // Left = Orbit/rotate around clicked point on plane
            const clickedPoint = this.raycastToPlane(event.clientX, event.clientY);
            if (clickedPoint) {
                this.state.orbiting = true;
                this.state.orbitStart = { x: event.clientX, y: event.clientY };
                this.state.orbitPivot = clickedPoint; // The point on plane we orbit around
                this.state.cameraStart = this.camera.position.clone();
                console.log(`🔄 Orbiting around point on plane`);
            }
            
        } else if (event.button === 1) {
            // Middle = Look around (rotate camera view direction ONLY, position stays fixed)
            this.state.lookingAround = true;
            this.state.lookStart = { x: event.clientX, y: event.clientY };
            
            // Store camera orientation (quaternion for proper local-axis rotation)
            this.state.quaternionStart = this.camera.quaternion.clone();
            
            console.log('👀 Look around started (camera position fixed, local-axis rotation)');
            
        } else if (event.button === 2) {
            // Right = Adjust height (altitude) only
            this.state.adjustingHeight = true;
            this.state.heightStart = event.clientY;
            this.state.cameraStart = this.camera.position.clone();
            this.state.focusStart = this.focusPoint.clone();
            this.state.initialHeight = this.camera.position.y;
            console.log('⬆️ Height adjustment started');
        }
    }
    
    onMouseMove(event) {
        if (this.state.panning && this.state.panStartWorld && this.state.panStartMouse) {
            // Pan: Slide along the ground plane
            // Calculate delta in SCREEN SPACE to avoid feedback loops from continuous raycasting
            const mouseDeltaX = event.clientX - this.state.panStartMouse.x;
            const mouseDeltaY = event.clientY - this.state.panStartMouse.y;
            
            // Get camera's current distance to focus point (for scaling)
            const cameraToFocus = new THREE.Vector3();
            cameraToFocus.subVectors(this.state.cameraStart, this.state.focusStart);
            const distance = cameraToFocus.length();
            
            // Convert screen delta to world delta using camera's right and up vectors
            // Scale by distance to make panning speed feel natural at all zoom levels
            const scaleFactor = distance * 0.001; // Adjust sensitivity here if needed
            
            const cameraRight = new THREE.Vector3();
            const cameraUp = new THREE.Vector3();
            this.camera.getWorldDirection(cameraUp); // Get forward direction first
            cameraRight.crossVectors(cameraUp, this.camera.up).normalize();
            cameraUp.crossVectors(cameraRight, cameraUp).normalize(); // True camera up
            
            // Project onto ground plane (remove Y component from movement)
            cameraRight.y = 0;
            cameraRight.normalize();
            const cameraForward = new THREE.Vector3();
            cameraForward.crossVectors(this.camera.up, cameraRight).normalize();
            
            const delta = new THREE.Vector3();
            delta.addScaledVector(cameraRight, -mouseDeltaX * scaleFactor);
            delta.addScaledVector(cameraForward, mouseDeltaY * scaleFactor);
            delta.y = 0; // Ensure we stay on ground plane
            
            // Move focus point and camera together along plane
            this.focusPoint.copy(this.state.focusStart).add(delta);
            this.focusPoint.y = 0;
            
            this.camera.position.copy(this.state.cameraStart).add(delta);
            this.controls.target.copy(this.focusPoint);
        }
        
        if (this.state.orbiting && this.state.orbitPivot) {
            // Orbit: Rotate camera around the clicked point on the plane
            const deltaX = event.clientX - this.state.orbitStart.x;
            const deltaY = event.clientY - this.state.orbitStart.y;
            
            // Get vector from pivot point to camera
            const offset = new THREE.Vector3();
            offset.subVectors(this.state.cameraStart, this.state.orbitPivot);
            
            // Convert to spherical coordinates
            const spherical = new THREE.Spherical();
            spherical.setFromVector3(offset);
            
            // Rotate horizontally (around Y axis / around the pivot)
            spherical.theta -= deltaX * 0.005;
            
            // Rotate vertically (tilt) - limit to prevent flipping
            spherical.phi = Math.max(0.1, Math.min(Math.PI / 2 - 0.01, spherical.phi - deltaY * 0.005));
            
            // Convert back and apply
            offset.setFromSpherical(spherical);
            this.camera.position.copy(this.state.orbitPivot).add(offset);
            
            // Look at the pivot point
            this.camera.lookAt(this.state.orbitPivot);
            
            // Update focus point to the orbit pivot
            this.focusPoint.copy(this.state.orbitPivot);
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
            
            // Update focus point to where camera is now looking on the ground plane
            const cameraDir = new THREE.Vector3();
            this.camera.getWorldDirection(cameraDir);
            const ray = new THREE.Ray(this.camera.position, cameraDir);
            const newFocus = new THREE.Vector3();
            ray.intersectPlane(this.groundPlane, newFocus);
            
            if (newFocus) {
                this.focusPoint.copy(newFocus);
                this.focusPoint.y = 0;
                this.controls.target.copy(this.focusPoint);
            }
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
            if (this.state.panning) {
                console.log('📍 Pan ended');
            }
            if (this.state.orbiting) {
                console.log('🔄 Orbit ended');
            }
            this.state.panning = false;
            this.state.orbiting = false;
            
        } else if (event.button === 1) {
            if (this.state.lookingAround) {
                console.log('👀 Look around ended');
            }
            this.state.lookingAround = false;
            
        } else if (event.button === 2) {
            if (this.state.adjustingHeight) {
                console.log(`⬆️ Height adjustment ended. New height: ${this.camera.position.y.toFixed(1)}`);
            }
            this.state.adjustingHeight = false;
        }
    }
    
    onWheel(event) {
        // Proper zoom implementation: Move camera toward/away from cursor point
        // while keeping view stable (no spinning)
        
        const cursorPoint = this.raycastToPlane(event.clientX, event.clientY);
        if (!cursorPoint) return;
        
        const zoomingIn = event.deltaY < 0;
        const zoomSpeed = 0.1;
        
        // Current camera-to-focus vector
        const cameraToFocus = new THREE.Vector3();
        cameraToFocus.subVectors(this.camera.position, this.focusPoint);
        const currentDistance = cameraToFocus.length();
        
        // Calculate new distance
        const factor = event.deltaY > 0 ? 1 + zoomSpeed : 1 - zoomSpeed;
        const newDistance = currentDistance * factor;
        if (newDistance < 5 || newDistance > 50000) return;
        
        // THE KEY: Move camera toward cursor point, but constrain the movement
        // to maintain stability and prevent spinning
        
        // Vector from current focus to cursor point (on ground plane)
        const focusToCursor = new THREE.Vector3();
        focusToCursor.subVectors(cursorPoint, this.focusPoint);
        focusToCursor.y = 0; // Keep on plane
        
        const lateralDistance = focusToCursor.length();
        
        if (zoomingIn) {
            // ZOOM IN: Move focus toward cursor
            // The closer we are, the more we can safely adjust
            // Limit adjustment to prevent sudden jumps
            const maxAdjustment = Math.min(lateralDistance * 0.3, currentDistance * 0.2);
            if (lateralDistance > 0.1) {
                focusToCursor.normalize();
                this.focusPoint.addScaledVector(focusToCursor, maxAdjustment);
                this.focusPoint.y = 0;
            }
        } else {
            // ZOOM OUT: Minimal focus adjustment
            // Only adjust if cursor point is relatively close to current focus
            // This prevents spinning when cursor is at screen edges
            const relativeLateralDist = lateralDistance / currentDistance;
            
            // Only adjust if cursor is within a reasonable cone (< 0.5 means roughly within 45 degrees)
            if (relativeLateralDist < 0.5) {
                const maxAdjustment = Math.min(lateralDistance * 0.1, currentDistance * 0.05);
                if (lateralDistance > 0.1) {
                    focusToCursor.normalize();
                    this.focusPoint.addScaledVector(focusToCursor, maxAdjustment);
                    this.focusPoint.y = 0;
                }
            }
            // If cursor is far from focus (at screen edge), don't adjust focus at all
            // This eliminates spinning!
        }
        
        // Now move camera to new distance from (possibly adjusted) focus point
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

