// Ground Plane Camera System
// The fundamental model used by Google Maps, Mapbox, etc.
// 
// Core concept:
// - Fixed ground plane at y=0 (the map surface)
// - Focus point ON the plane (where camera looks)
// - All operations relative to this plane

class GroundPlaneCamera extends CameraScheme {
    constructor() {
        super('Ground Plane (Google Maps)', 'Left drag = pan, Shift+Left = tilt, Scroll = zoom, Right = rotate');
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
        
        console.log(`📍 Ground plane camera initialized. Focus point: (${this.focusPoint.x.toFixed(1)}, ${this.focusPoint.y.toFixed(1)}, ${this.focusPoint.z.toFixed(1)})`);
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
        if (event.button === 0 && event.shiftKey) { // Shift+Left = Tilt (adjust viewing angle)
            this.state.tilting = true;
            this.state.tiltStart = { x: event.clientX, y: event.clientY };
            this.state.cameraStart = this.camera.position.clone();
            this.state.focusStart = this.focusPoint.clone();
            console.log('🔽 Tilt started (Shift+Left)');
        } else if (event.button === 0) { // Left = Pan along plane
            this.state.panning = true;
            this.state.panStart = { x: event.clientX, y: event.clientY }; // Use screen coords for smooth panning
            this.state.focusStart = this.focusPoint.clone();
            this.state.cameraStart = this.camera.position.clone();
            console.log('🖱️ Pan started on plane');
        } else if (event.button === 2) { // Right = Rotate around focus point
            this.state.rotating = true;
            this.state.rotateStart = { x: event.clientX, y: event.clientY };
            this.state.cameraStart = this.camera.position.clone();
            this.state.focusStart = this.focusPoint.clone();
            console.log('🔄 Rotation started around focus point');
        }
    }
    
    onMouseMove(event) {
        if (this.state.panning && this.state.panStart) {
            // Pan: Use screen-space movement for smooth dragging
            // This is much smoother than continuous raycasting
            const deltaX = event.clientX - this.state.panStart.x;
            const deltaY = event.clientY - this.state.panStart.y;
            
            // Get camera's right and forward vectors (projected onto ground plane)
            const right = new THREE.Vector3();
            this.camera.getWorldDirection(right);
            right.cross(this.camera.up).normalize();
            
            const forward = new THREE.Vector3();
            this.camera.getWorldDirection(forward);
            forward.y = 0; // Project onto ground plane
            forward.normalize();
            
            // Calculate movement speed based on distance from focus point
            const distance = this.camera.position.distanceTo(this.focusPoint);
            const moveSpeed = distance * 0.001; // Adaptive speed
            
            // Calculate world-space movement for "grab and drag" behavior
            // When you drag mouse DOWN, grab the map and pull it DOWN (camera moves back)
            // When you drag mouse LEFT, grab the map and pull it LEFT (camera moves left)
            const movement = new THREE.Vector3();
            movement.addScaledVector(right, -deltaX * moveSpeed);  // Drag left → map left, drag right → map right
            movement.addScaledVector(forward, deltaY * moveSpeed); // Drag down → map down, drag up → map up
            movement.y = 0; // Keep movement on ground plane
            
            // Move focus point and camera together
            this.focusPoint.copy(this.state.focusStart).add(movement);
            this.focusPoint.y = 0; // Keep on plane
            
            this.camera.position.copy(this.state.cameraStart).add(movement);
            
            // Update controls target
            this.controls.target.copy(this.focusPoint);
        }
        
        if (this.state.tilting) {
            // If Shift key is released mid-drag, cancel tilt operation smoothly
            if (!event.shiftKey) {
                console.log('🔽 Tilt cancelled (Shift released)');
                this.state.tilting = false;
                return;
            }
            
            // Tilt: Adjust viewing angle (phi) - drag down = tilt down (see more land), drag up = tilt up (overhead)
            const deltaY = event.clientY - this.state.tiltStart.y;
            
            // Get vector from focus point to camera
            const offset = new THREE.Vector3();
            offset.subVectors(this.state.cameraStart, this.state.focusStart);
            
            // Convert to spherical coordinates
            const spherical = new THREE.Spherical();
            spherical.setFromVector3(offset);
            
            // Adjust vertical angle (phi) based on mouse movement
            // Drag DOWN = positive deltaY = increase phi = tilt down (see more terrain)
            // Drag UP = negative deltaY = decrease phi = tilt up (more overhead)
            const tiltSpeed = 0.005;
            spherical.phi = Math.max(0.1, Math.min(Math.PI / 2 - 0.01, spherical.phi + deltaY * tiltSpeed));
            
            // Convert back to Cartesian and apply
            offset.setFromSpherical(spherical);
            this.camera.position.copy(this.focusPoint).add(offset);
            
            // Update controls target (lookAt will be handled by update() loop for smoothness)
            this.controls.target.copy(this.focusPoint);
        }
        
        if (this.state.rotating) {
            // Rotate: Orbit camera around focus point, maintaining distance from plane
            const deltaX = event.clientX - this.state.rotateStart.x;
            const deltaY = event.clientY - this.state.rotateStart.y;
            
            // Get vector from focus point to camera
            const offset = new THREE.Vector3();
            offset.subVectors(this.state.cameraStart, this.state.focusStart);
            
            // Convert to spherical coordinates for rotation
            const spherical = new THREE.Spherical();
            spherical.setFromVector3(offset);
            
            // Rotate horizontally (theta)
            spherical.theta -= deltaX * 0.005;
            
            // Rotate vertically (phi) - limit to prevent flipping
            spherical.phi = Math.max(0.1, Math.min(Math.PI / 2 - 0.01, spherical.phi - deltaY * 0.005));
            
            // Convert back to Cartesian and apply
            offset.setFromSpherical(spherical);
            this.camera.position.copy(this.focusPoint).add(offset);
            
            // Update controls target (lookAt will be handled by update() loop for smoothness)
            this.controls.target.copy(this.focusPoint);
        }
    }
    
    onMouseUp(event) {
        if (event.button === 0) {
            if (this.state.tilting) {
                console.log('🔽 Tilt ended');
                this.state.tilting = false;
            }
            if (this.state.panning) {
                console.log(`📍 Pan ended. Focus point: (${this.focusPoint.x.toFixed(1)}, ${this.focusPoint.y.toFixed(1)}, ${this.focusPoint.z.toFixed(1)})`);
            }
            this.state.panning = false;
        } else if (event.button === 2) {
            this.state.rotating = false;
        }
    }
    
    onWheel(event) {
        // Zoom: Move camera perpendicular to plane, toward cursor point
        const cursorPoint = this.raycastToPlane(event.clientX, event.clientY);
        
        if (!cursorPoint) return;
        
        // Get distance from camera to the cursor point on the plane
        const distance = this.camera.position.distanceTo(cursorPoint);
        
        // Zoom speed based on distance
        const zoomSpeed = 0.1;
        // STANDARD: Scroll UP (negative delta) = zoom IN = get closer
        const factor = event.deltaY > 0 ? 1 + zoomSpeed : 1 - zoomSpeed;
        
        const newDistance = distance * factor;
        if (newDistance < 5) return; // Don't get too close
        
        // Calculate direction from camera to cursor point
        const direction = new THREE.Vector3();
        direction.subVectors(cursorPoint, this.camera.position);
        direction.normalize();
        
        // Move camera toward/away from cursor point
        const moveAmount = distance * (1 - factor);
        this.camera.position.addScaledVector(direction, moveAmount);
        
        // Adjust focus point slightly toward/away from cursor point for natural feel
        // Zoom IN (scroll up): focus moves toward cursor
        // Zoom OUT (scroll down): focus moves away from cursor
        const towardsCursor = new THREE.Vector3();
        towardsCursor.subVectors(cursorPoint, this.focusPoint);
        const focusShift = event.deltaY > 0 ? -0.1 : 0.1;  // Zoom out = move away, Zoom in = move toward
        this.focusPoint.addScaledVector(towardsCursor, focusShift);
        this.focusPoint.y = 0; // Keep on plane
        
        this.controls.target.copy(this.focusPoint);
        
        // Note: camera.lookAt() is handled by update() loop, not here
        // This prevents jitter from multiple lookAt calls per frame
    }
    
    update() {
        // Ensure camera always looks at focus point
        if (this.enabled && this.focusPoint) {
            this.camera.lookAt(this.focusPoint);
        }
    }
}

// Add to schemes
window.CameraSchemes = window.CameraSchemes || {};
window.CameraSchemes['ground-plane'] = new GroundPlaneCamera();

