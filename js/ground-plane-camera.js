// Ground Plane Camera System
// The fundamental model used by Google Maps, Mapbox, etc.
// 
// Core concept:
// - Fixed ground plane at y=0 (the map surface)
// - Focus point ON the plane (where camera looks)
// - All operations relative to this plane

class GroundPlaneCamera extends CameraScheme {
    constructor() {
        super('Ground Plane (Google Maps)', 'Left drag = pan on plane, Scroll = zoom perpendicular, Right = rotate');
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
        if (event.button === 0) { // Left = Pan along plane
            this.state.panning = true;
            this.state.panStart = this.raycastToPlane(event.clientX, event.clientY);
            if (this.state.panStart) {
                this.state.focusStart = this.focusPoint.clone();
                this.state.cameraStart = this.camera.position.clone();
                console.log('🖱️ Pan started on plane');
            } else {
                this.state.panning = false;
            }
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
            // Pan: Slide the focus point along the ground plane
            const currentPoint = this.raycastToPlane(event.clientX, event.clientY);
            
            if (currentPoint) {
                // Calculate how much the plane point moved
                const delta = new THREE.Vector3();
                delta.subVectors(this.state.panStart, currentPoint);
                
                // Move focus point on the plane (only XZ, Y stays 0)
                this.focusPoint.copy(this.state.focusStart).add(delta);
                this.focusPoint.y = 0; // Keep on plane
                
                // Move camera by the same amount (parallel to plane)
                this.camera.position.copy(this.state.cameraStart).add(delta);
                
                // Update controls target
                this.controls.target.copy(this.focusPoint);
            }
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
            
            // Always look at focus point
            this.camera.lookAt(this.focusPoint);
            this.controls.target.copy(this.focusPoint);
        }
    }
    
    onMouseUp(event) {
        if (event.button === 0) {
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
        
        // Adjust focus point slightly toward cursor point for natural feel
        const towardsCursor = new THREE.Vector3();
        towardsCursor.subVectors(cursorPoint, this.focusPoint);
        this.focusPoint.addScaledVector(towardsCursor, 0.1);
        this.focusPoint.y = 0; // Keep on plane
        
        this.controls.target.copy(this.focusPoint);
        
        // Make sure camera still looks at focus point
        this.camera.lookAt(this.focusPoint);
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

