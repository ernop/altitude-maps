// Camera Control Schemes - Multiple proven implementations
// Each scheme is self-contained and can be switched dynamically

class CameraScheme {
    constructor(name, description) {
        this.name = name;
        this.description = description;
        this.enabled = false;
        this.state = {};
    }
    
    activate(camera, controls, renderer) {
        this.camera = camera;
        this.controls = controls;
        this.renderer = renderer;
        this.enabled = true;
        this.reset();
    }
    
    deactivate() {
        this.enabled = false;
        this.cleanup();
    }
    
    reset() {
        this.state = {};
    }
    
    cleanup() {}
    onMouseDown(event) {}
    onMouseMove(event) {}
    onMouseUp(event) {}
    onWheel(event) {}
    update() {}
}

// ==================== GOOGLE MAPS STYLE ====================
class GoogleMapsScheme extends CameraScheme {
    constructor() {
        super('Google Maps', 'Left drag = pan, Scroll = zoom to cursor, Right drag = rotate');
        this.groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
        this.raycaster = new THREE.Raycaster();
    }
    
    raycast(x, y) {
        const rect = this.renderer.domElement.getBoundingClientRect();
        const ndcX = ((x - rect.left) / rect.width) * 2 - 1;
        const ndcY = -((y - rect.top) / rect.height) * 2 + 1;
        
        this.raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), this.camera);
        const point = new THREE.Vector3();
        this.raycaster.ray.intersectPlane(this.groundPlane, point);
        return point;
    }
    
    onMouseDown(event) {
        if (event.button === 0) { // Left = pan
            this.state.panning = true;
            this.state.panStart = { x: event.clientX, y: event.clientY }; // Use screen coords for smooth panning
            this.state.cameraStart = this.camera.position.clone();
            this.state.targetStart = this.controls.target.clone();
        } else if (event.button === 2) { // Right = rotate
            this.state.rotating = true;
            this.state.rotateStart = { x: event.clientX, y: event.clientY };
            this.state.cameraStart = this.camera.position.clone();
            this.state.targetStart = this.controls.target.clone();
        }
    }
    
    onMouseMove(event) {
        if (this.state.panning && this.state.panStart) {
            const current = this.raycast(event.clientX, event.clientY);
            if (current) {
                const delta = new THREE.Vector3().subVectors(this.state.panStart, current);
                this.camera.position.copy(this.state.cameraStart).add(delta);
                this.controls.target.copy(this.state.targetStart).add(delta);
            }
        }
        
        if (this.state.rotating && this.state.rotateStart) {
            const deltaX = event.clientX - this.state.rotateStart.x;
            const deltaY = event.clientY - this.state.rotateStart.y;
            
            const offset = new THREE.Vector3().subVectors(this.state.cameraStart, this.state.targetStart);
            const radius = offset.length();
            
            // Horizontal rotation
            const theta = -deltaX * 0.005;
            const phi = -deltaY * 0.005;
            
            const spherical = new THREE.Spherical().setFromVector3(offset);
            spherical.theta += theta;
            spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi + phi));
            
            offset.setFromSpherical(spherical);
            this.camera.position.copy(this.state.targetStart).add(offset);
            this.camera.lookAt(this.controls.target);
        }
    }
    
    onMouseUp(event) {
        this.state.panning = false;
        this.state.rotating = false;
    }
    
    onWheel(event) {
        // Zoom to cursor
        const point = this.raycast(event.clientX, event.clientY);
        if (!point) return;
        
        const distance = this.camera.position.distanceTo(point);
        const zoomSpeed = 0.1;
        // STANDARD: Scroll UP (negative delta) = zoom IN, Scroll DOWN (positive) = zoom OUT
        const factor = event.deltaY > 0 ? 1 + zoomSpeed : 1 - zoomSpeed;
        
        const newDist = distance * factor;
        if (newDist < 1) return;
        
        const direction = new THREE.Vector3().subVectors(point, this.camera.position).normalize();
        const move = distance * (1 - factor);
        this.camera.position.addScaledVector(direction, move);
    }
}

// ==================== GOOGLE EARTH STYLE ====================
class GoogleEarthScheme extends CameraScheme {
    constructor() {
        super('Google Earth', 'Left drag = rotate around point, Scroll = zoom to cursor, Ctrl = pan');
        this.groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
        this.raycaster = new THREE.Raycaster();
    }
    
    raycast(x, y) {
        const rect = this.renderer.domElement.getBoundingClientRect();
        const ndcX = ((x - rect.left) / rect.width) * 2 - 1;
        const ndcY = -((y - rect.top) / rect.height) * 2 + 1;
        
        this.raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), this.camera);
        const point = new THREE.Vector3();
        this.raycaster.ray.intersectPlane(this.groundPlane, point);
        return point;
    }
    
    onMouseDown(event) {
        if (event.button === 0 && event.ctrlKey) { // Ctrl+Left = pan
            this.state.panning = true;
            this.state.panStart = { x: event.clientX, y: event.clientY }; // Use screen coords for smooth panning
            this.state.cameraStart = this.camera.position.clone();
            this.state.targetStart = this.controls.target.clone();
        } else if (event.button === 0) { // Left = rotate around clicked point
            const point = this.raycast(event.clientX, event.clientY);
            if (point) {
                this.state.rotating = true;
                this.state.rotateStart = { x: event.clientX, y: event.clientY };
                this.state.pivot = point;
                this.state.cameraStart = this.camera.position.clone();
            }
        }
    }
    
    onMouseMove(event) {
        if (this.state.panning && this.state.panStart) {
            // Use screen-space panning (smooth like Roblox)
            const deltaX = event.clientX - this.state.panStart.x;
            const deltaY = event.clientY - this.state.panStart.y;
            
            const right = new THREE.Vector3();
            this.camera.getWorldDirection(right);
            right.cross(this.camera.up).normalize();
            
            const up = new THREE.Vector3(0, 1, 0);
            
            const distance = this.camera.position.distanceTo(this.controls.target);
            const moveSpeed = distance * 0.001;
            
            const movement = new THREE.Vector3();
            movement.addScaledVector(right, -deltaX * moveSpeed);
            movement.addScaledVector(up, deltaY * moveSpeed);
            
            this.camera.position.copy(this.state.cameraStart).add(movement);
            this.controls.target.copy(this.state.targetStart).add(movement);
        }
        
        if (this.state.rotating && this.state.pivot) {
            const deltaX = event.clientX - this.state.rotateStart.x;
            const deltaY = event.clientY - this.state.rotateStart.y;
            
            const offset = new THREE.Vector3().subVectors(this.state.cameraStart, this.state.pivot);
            
            const theta = -deltaX * 0.005;
            const phi = -deltaY * 0.005;
            
            const spherical = new THREE.Spherical().setFromVector3(offset);
            spherical.theta += theta;
            spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi + phi));
            
            offset.setFromSpherical(spherical);
            this.camera.position.copy(this.state.pivot).add(offset);
            this.camera.lookAt(this.state.pivot);
            this.controls.target.copy(this.state.pivot);
        }
    }
    
    onMouseUp(event) {
        this.state.panning = false;
        this.state.rotating = false;
    }
    
    onWheel(event) {
        const point = this.raycast(event.clientX, event.clientY);
        if (!point) return;
        
        const distance = this.camera.position.distanceTo(point);
        const zoomSpeed = 0.1;
        // STANDARD: Scroll UP (negative delta) = zoom IN
        const factor = event.deltaY > 0 ? 1 + zoomSpeed : 1 - zoomSpeed;
        
        const direction = new THREE.Vector3().subVectors(point, this.camera.position).normalize();
        const move = distance * (1 - factor);
        this.camera.position.addScaledVector(direction, move);
    }
}

// ==================== BLENDER STYLE ====================
class BlenderScheme extends CameraScheme {
    constructor() {
        super('Blender', 'Middle drag = rotate, Shift+Middle = pan, Scroll = zoom');
        this.groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
        this.raycaster = new THREE.Raycaster();
    }
    
    raycast(x, y) {
        const rect = this.renderer.domElement.getBoundingClientRect();
        const ndcX = ((x - rect.left) / rect.width) * 2 - 1;
        const ndcY = -((y - rect.top) / rect.height) * 2 + 1;
        
        this.raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), this.camera);
        const point = new THREE.Vector3();
        this.raycaster.ray.intersectPlane(this.groundPlane, point);
        return point;
    }
    
    onMouseDown(event) {
        if (event.button === 1 && event.shiftKey) { // Shift+Middle = pan
            this.state.panning = true;
            this.state.panStart = { x: event.clientX, y: event.clientY }; // Use screen coords for smooth panning
            this.state.cameraStart = this.camera.position.clone();
            this.state.targetStart = this.controls.target.clone();
        } else if (event.button === 1) { // Middle = rotate
            this.state.rotating = true;
            this.state.rotateStart = { x: event.clientX, y: event.clientY };
            this.state.cameraStart = this.camera.position.clone();
        }
    }
    
    onMouseMove(event) {
        if (this.state.panning && this.state.panStart) {
            // Use screen-space panning (smooth like Roblox)
            const deltaX = event.clientX - this.state.panStart.x;
            const deltaY = event.clientY - this.state.panStart.y;
            
            const right = new THREE.Vector3();
            this.camera.getWorldDirection(right);
            right.cross(this.camera.up).normalize();
            
            const up = new THREE.Vector3(0, 1, 0);
            
            const distance = this.camera.position.distanceTo(this.controls.target);
            const moveSpeed = distance * 0.001;
            
            const movement = new THREE.Vector3();
            movement.addScaledVector(right, -deltaX * moveSpeed);
            movement.addScaledVector(up, deltaY * moveSpeed);
            
            this.camera.position.copy(this.state.cameraStart).add(movement);
            this.controls.target.copy(this.state.targetStart).add(movement);
        }
        
        if (this.state.rotating) {
            const deltaX = event.clientX - this.state.rotateStart.x;
            const deltaY = event.clientY - this.state.rotateStart.y;
            
            const offset = new THREE.Vector3().subVectors(this.state.cameraStart, this.controls.target);
            
            const theta = -deltaX * 0.005;
            const phi = -deltaY * 0.005;
            
            const spherical = new THREE.Spherical().setFromVector3(offset);
            spherical.theta += theta;
            spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi + phi));
            
            offset.setFromSpherical(spherical);
            this.camera.position.copy(this.controls.target).add(offset);
            this.camera.lookAt(this.controls.target);
        }
    }
    
    onMouseUp(event) {
        this.state.panning = false;
        this.state.rotating = false;
    }
    
    onWheel(event) {
        const forward = new THREE.Vector3();
        this.camera.getWorldDirection(forward);
        const distance = this.camera.position.distanceTo(this.controls.target);
        // STANDARD: Scroll UP (negative delta) = zoom IN = move forward (negative moveAmount)
        const moveAmount = (event.deltaY > 0 ? -1 : 1) * distance * 0.1;
        this.camera.position.addScaledVector(forward, moveAmount);
    }
}

// ==================== ROBLOX STUDIO STYLE ====================
class RobloxScheme extends CameraScheme {
    constructor() {
        super('Roblox Studio', 'Right drag = rotate, Middle drag = pan, WASD = move, QE = up/down');
        this.keys = {};
    }
    
    activate(camera, controls, renderer) {
        super.activate(camera, controls, renderer);
        this.keydownHandler = (e) => this.onKeyDown(e);
        this.keyupHandler = (e) => this.onKeyUp(e);
        window.addEventListener('keydown', this.keydownHandler);
        window.addEventListener('keyup', this.keyupHandler);
    }
    
    cleanup() {
        window.removeEventListener('keydown', this.keydownHandler);
        window.removeEventListener('keyup', this.keyupHandler);
    }
    
    onKeyDown(event) {
        this.keys[event.key.toLowerCase()] = true;
    }
    
    onKeyUp(event) {
        this.keys[event.key.toLowerCase()] = false;
    }
    
    onMouseDown(event) {
        if (event.button === 2) { // Right = rotate
            this.state.rotating = true;
            this.state.rotateStart = { x: event.clientX, y: event.clientY };
            this.state.cameraStart = this.camera.position.clone();
        } else if (event.button === 1) { // Middle = pan
            this.state.panning = true;
            this.state.panStart = { x: event.clientX, y: event.clientY };
            this.state.cameraStart = this.camera.position.clone();
            this.state.targetStart = this.controls.target.clone();
        }
    }
    
    onMouseMove(event) {
        if (this.state.rotating) {
            const deltaX = event.clientX - this.state.rotateStart.x;
            const deltaY = event.clientY - this.state.rotateStart.y;
            
            const offset = new THREE.Vector3().subVectors(this.state.cameraStart, this.controls.target);
            
            const theta = -deltaX * 0.005;
            const phi = -deltaY * 0.005;
            
            const spherical = new THREE.Spherical().setFromVector3(offset);
            spherical.theta += theta;
            spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi + phi));
            
            offset.setFromSpherical(spherical);
            this.camera.position.copy(this.controls.target).add(offset);
            this.camera.lookAt(this.controls.target);
        }
        
        if (this.state.panning) {
            const deltaX = event.clientX - this.state.panStart.x;
            const deltaY = event.clientY - this.state.panStart.y;
            
            const right = new THREE.Vector3();
            this.camera.getWorldDirection(right);
            right.cross(this.camera.up).normalize();
            
            const up = new THREE.Vector3(0, 1, 0);
            
            const moveSpeed = 0.5;
            const movement = new THREE.Vector3();
            movement.addScaledVector(right, -deltaX * moveSpeed);
            movement.addScaledVector(up, deltaY * moveSpeed);
            
            this.camera.position.copy(this.state.cameraStart).add(movement);
            this.controls.target.copy(this.state.targetStart).add(movement);
        }
    }
    
    onMouseUp(event) {
        this.state.rotating = false;
        this.state.panning = false;
    }
    
    onWheel(event) {
        const forward = new THREE.Vector3();
        this.camera.getWorldDirection(forward);
        // STANDARD: Scroll UP (negative delta) = zoom IN = move forward (negative moveAmount)
        const moveAmount = (event.deltaY > 0 ? -1 : 1) * 20;
        this.camera.position.addScaledVector(forward, moveAmount);
        this.controls.target.addScaledVector(forward, moveAmount);
    }
    
    update() {
        if (!this.enabled) return;
        
        const moveSpeed = 2.0;
        const forward = new THREE.Vector3();
        this.camera.getWorldDirection(forward);
        forward.normalize();
        
        const right = new THREE.Vector3();
        right.crossVectors(forward, this.camera.up).normalize();
        
        const delta = new THREE.Vector3();
        
        if (this.keys['w']) delta.addScaledVector(forward, moveSpeed);
        if (this.keys['s']) delta.addScaledVector(forward, -moveSpeed);
        if (this.keys['a']) delta.addScaledVector(right, -moveSpeed);
        if (this.keys['d']) delta.addScaledVector(right, moveSpeed);
        if (this.keys['e']) delta.y += moveSpeed;
        if (this.keys['q']) delta.y -= moveSpeed;
        
        if (delta.lengthSq() > 0) {
            this.camera.position.add(delta);
            this.controls.target.add(delta);
        }
    }
}

// ==================== UNITY/UNREAL STYLE ====================
class UnityScheme extends CameraScheme {
    constructor() {
        super('Unity Editor', 'Alt+Left = orbit, Alt+Middle = pan, Alt+Right = zoom, Scroll = zoom');
    }
    
    onMouseDown(event) {
        if (event.altKey && event.button === 0) { // Alt+Left = orbit
            this.state.orbiting = true;
            this.state.orbitStart = { x: event.clientX, y: event.clientY };
            this.state.cameraStart = this.camera.position.clone();
        } else if (event.altKey && event.button === 1) { // Alt+Middle = pan
            this.state.panning = true;
            this.state.panStart = { x: event.clientX, y: event.clientY };
            this.state.cameraStart = this.camera.position.clone();
            this.state.targetStart = this.controls.target.clone();
        } else if (event.altKey && event.button === 2) { // Alt+Right = zoom
            this.state.zooming = true;
            this.state.zoomStart = event.clientY;
            this.state.cameraStart = this.camera.position.clone();
        }
    }
    
    onMouseMove(event) {
        if (this.state.orbiting) {
            const deltaX = event.clientX - this.state.orbitStart.x;
            const deltaY = event.clientY - this.state.orbitStart.y;
            
            const offset = new THREE.Vector3().subVectors(this.state.cameraStart, this.controls.target);
            
            const theta = -deltaX * 0.005;
            const phi = -deltaY * 0.005;
            
            const spherical = new THREE.Spherical().setFromVector3(offset);
            spherical.theta += theta;
            spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi + phi));
            
            offset.setFromSpherical(spherical);
            this.camera.position.copy(this.controls.target).add(offset);
            this.camera.lookAt(this.controls.target);
        }
        
        if (this.state.panning) {
            const deltaX = event.clientX - this.state.panStart.x;
            const deltaY = event.clientY - this.state.panStart.y;
            
            const right = new THREE.Vector3();
            this.camera.getWorldDirection(right);
            right.cross(this.camera.up).normalize();
            
            const up = new THREE.Vector3(0, 1, 0);
            
            const moveSpeed = 0.5;
            const movement = new THREE.Vector3();
            movement.addScaledVector(right, -deltaX * moveSpeed);
            movement.addScaledVector(up, deltaY * moveSpeed);
            
            this.camera.position.copy(this.state.cameraStart).add(movement);
            this.controls.target.copy(this.state.targetStart).add(movement);
        }
        
        if (this.state.zooming) {
            const deltaY = event.clientY - this.state.zoomStart;
            const forward = new THREE.Vector3();
            this.camera.getWorldDirection(forward);
            this.camera.position.copy(this.state.cameraStart).addScaledVector(forward, -deltaY * 0.5);
        }
    }
    
    onMouseUp(event) {
        this.state.orbiting = false;
        this.state.panning = false;
        this.state.zooming = false;
    }
    
    onWheel(event) {
        const forward = new THREE.Vector3();
        this.camera.getWorldDirection(forward);
        const distance = this.camera.position.distanceTo(this.controls.target);
        // STANDARD: Scroll UP (negative delta) = zoom IN = move forward (negative moveAmount)
        const moveAmount = (event.deltaY > 0 ? -1 : 1) * distance * 0.1;
        this.camera.position.addScaledVector(forward, moveAmount);
    }
}

// Export schemes
window.CameraSchemes = {
    'google-maps': new GoogleMapsScheme(),
    'google-earth': new GoogleEarthScheme(),
    'blender': new BlenderScheme(),
    'roblox': new RobloxScheme(),
    'unity': new UnityScheme()
};

