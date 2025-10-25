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
        super('Google Earth (Ground Plane)', 'Left = orbit, Right = height adjust, Ctrl+Left = pan, Scroll = zoom');
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
            const currentPoint = this.raycastToPlane(event.clientX, event.clientY);
            
            if (currentPoint) {
                const delta = new THREE.Vector3();
                delta.subVectors(this.state.panStartWorld, currentPoint);
                
                // Move focus point and camera together along plane
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
            
        } else if (event.button === 2) {
            if (this.state.adjustingHeight) {
                console.log(`⬆️ Height adjustment ended. New height: ${this.camera.position.y.toFixed(1)}`);
            }
            this.state.adjustingHeight = false;
        }
    }
    
    onWheel(event) {
        // Zoom: Move camera away/toward focus point, with smart cursor tracking
        const cursorPoint = this.raycastToPlane(event.clientX, event.clientY);
        
        if (!cursorPoint) return;
        
        // Calculate how far cursor is from screen center (normalized 0-1)
        const rect = this.renderer.domElement.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        const distFromCenterX = Math.abs(event.clientX - centerX) / (rect.width / 2);
        const distFromCenterY = Math.abs(event.clientY - centerY) / (rect.height / 2);
        const distFromCenter = Math.max(distFromCenterX, distFromCenterY); // 0 = center, 1 = edge
        
        // Adjust focus point toward cursor
        // Key: Reduce adjustment when cursor is at edge (prevents spinning!)
        const towardsCursor = new THREE.Vector3(
            cursorPoint.x - this.focusPoint.x,
            0,
            cursorPoint.z - this.focusPoint.z
        );
        
        const zoomingIn = event.deltaY < 0;
        
        if (zoomingIn) {
            // Zoom IN: Move focus aggressively toward cursor (safe because we're getting closer)
            // Even at edges, this feels good
            const focusAdjust = 0.25;
            this.focusPoint.addScaledVector(towardsCursor, focusAdjust);
        } else {
            // Zoom OUT: Only adjust focus when cursor is near center
            // At edges, barely adjust to prevent spinning
            const centerBias = Math.max(0, 1.0 - distFromCenter); // 1 at center, 0 at edge
            const focusAdjust = 0.15 * centerBias; // Scales down to 0 at edges
            this.focusPoint.addScaledVector(towardsCursor, focusAdjust);
        }
        
        this.focusPoint.y = 0; // Keep on plane
        
        // Now zoom: Move camera along the line from focus point to camera
        const cameraToFocus = new THREE.Vector3();
        cameraToFocus.subVectors(this.camera.position, this.focusPoint);
        
        const currentDistance = cameraToFocus.length();
        
        // Zoom speed
        const zoomSpeed = 0.1;
        const factor = event.deltaY > 0 ? 1 + zoomSpeed : 1 - zoomSpeed;
        
        const newDistance = currentDistance * factor;
        if (newDistance < 5 || newDistance > 50000) return;
        
        // Move camera to new distance from focus point
        cameraToFocus.normalize();
        cameraToFocus.multiplyScalar(newDistance);
        this.camera.position.copy(this.focusPoint).add(cameraToFocus);
        
        // Update controls target
        this.controls.target.copy(this.focusPoint);
        
        // Don't call lookAt here - let update() handle it
    }
    
    update() {
        // Only update camera orientation if we're NOT actively dragging
        // This prevents "fighting" during pan/orbit operations
        if (this.enabled && this.focusPoint) {
            const isActiveDragging = this.state.panning || this.state.orbiting || this.state.adjustingHeight;
            if (!isActiveDragging) {
                this.camera.lookAt(this.focusPoint);
            }
        }
    }
}

// Add to schemes
window.CameraSchemes = window.CameraSchemes || {};
window.CameraSchemes['google-earth-plane'] = new GroundPlaneGoogleEarth();

