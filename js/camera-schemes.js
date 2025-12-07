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

    cleanup() { }
    onMouseDown(event) { }
    onMouseMove(event) { }
    onMouseUp(event) { }
    onWheel(event) { }
    update() { }
    // Cancel all active drag operations (called when mouse leaves canvas or on cleanup)
    cancelAllDrags() {
        this.state = {};
    }
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

// ==================== FLYING MODE (Space Simulator Style) ====================
class FlyingScheme extends CameraScheme {
    constructor() {
        super('Flying', 'Mouse = look around, WASD = move, QE = up/down, Shift = speed boost');
        this.keys = {};
        this.mouseSensitivity = 0.002;
        this.moveSpeed = 5.0;
        this.fastMoveSpeed = 15.0;
        this.euler = new THREE.Euler(0, 0, 0, 'YXZ');
    }

    activate(camera, controls, renderer) {
        super.activate(camera, controls, renderer);

        // Store initial camera orientation
        this.euler.setFromQuaternion(camera.quaternion);

        // Set up event listeners
        this.keydownHandler = (e) => this.onKeyDown(e);
        this.keyupHandler = (e) => this.onKeyUp(e);
        this.mouseMoveHandler = (e) => this.onMouseMoveFlying(e);
        this.clickHandler = (e) => this.onClickFlying(e);

        window.addEventListener('keydown', this.keydownHandler);
        window.addEventListener('keyup', this.keyupHandler);
        renderer.domElement.addEventListener('mousemove', this.mouseMoveHandler);
        renderer.domElement.addEventListener('click', this.clickHandler);

        // Disable OrbitControls
        if (controls) {
            this._controlsPrev = {
                enabled: controls.enabled,
                enableRotate: controls.enableRotate,
                enablePan: controls.enablePan,
                enableZoom: controls.enableZoom
            };
            controls.enabled = false;
        }

        // Instructions for pointer lock
        appendActivityLog('Flying mode: Click canvas to look around with mouse. ESC to release.');
    }

    cleanup() {
        window.removeEventListener('keydown', this.keydownHandler);
        window.removeEventListener('keyup', this.keyupHandler);
        this.renderer.domElement.removeEventListener('mousemove', this.mouseMoveHandler);
        this.renderer.domElement.removeEventListener('click', this.clickHandler);

        // Restore controls
        if (this.controls && this._controlsPrev) {
            this.controls.enabled = this._controlsPrev.enabled;
            this.controls.enableRotate = this._controlsPrev.enableRotate;
            this.controls.enablePan = this._controlsPrev.enablePan;
            this.controls.enableZoom = this._controlsPrev.enableZoom;
        }

        // Exit pointer lock if active
        if (document.pointerLockElement === this.renderer.domElement) {
            document.exitPointerLock();
        }
    }

    onKeyDown(event) {
        // Don't process keys if user is typing
        const activeElement = document.activeElement;
        const isTyping = activeElement && (
            activeElement.tagName === 'INPUT' ||
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.tagName === 'SELECT' ||
            activeElement.isContentEditable
        );
        if (isTyping) return;

        this.keys[event.key.toLowerCase()] = true;
    }

    onKeyUp(event) {
        this.keys[event.key.toLowerCase()] = false;
    }

    onClickFlying(event) {
        // Request pointer lock for smooth mouse look
        if (document.pointerLockElement !== this.renderer.domElement) {
            this.renderer.domElement.requestPointerLock();
        }
    }

    onMouseMoveFlying(event) {
        // Only handle mouse movement when pointer is locked
        if (document.pointerLockElement !== this.renderer.domElement) return;

        const movementX = event.movementX || 0;
        const movementY = event.movementY || 0;

        // Update euler angles for smooth FPS-style look
        this.euler.setFromQuaternion(this.camera.quaternion);
        this.euler.y -= movementX * this.mouseSensitivity;
        this.euler.x -= movementY * this.mouseSensitivity;

        // Clamp vertical rotation to prevent flipping
        this.euler.x = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, this.euler.x));

        this.camera.quaternion.setFromEuler(this.euler);
    }

    update() {
        if (!this.enabled) return;

        const speed = this.keys['shift'] ? this.fastMoveSpeed : this.moveSpeed;

        const forward = new THREE.Vector3();
        this.camera.getWorldDirection(forward);
        forward.normalize();

        const right = new THREE.Vector3();
        right.crossVectors(forward, this.camera.up).normalize();

        const delta = new THREE.Vector3();

        if (this.keys['w']) delta.addScaledVector(forward, speed);
        if (this.keys['s']) delta.addScaledVector(forward, -speed);
        if (this.keys['a']) delta.addScaledVector(right, -speed);
        if (this.keys['d']) delta.addScaledVector(right, speed);
        if (this.keys['e']) delta.y += speed;
        if (this.keys['q']) delta.y -= speed;

        if (delta.lengthSq() > 0) {
            this.camera.position.add(delta);
        }

        // Update controls target to be in front of camera
        if (this.controls) {
            this.controls.target.copy(this.camera.position).add(forward.multiplyScalar(100));
        }
    }
}

// ==================== JUMPING MODE (Third-Person Character) ====================
class JumpingScheme extends CameraScheme {
    constructor() {
        super('Jumping (Map-Grandpa)', 'WASD = move, Space = jump, Mouse = look around, Shift = run');
        this.keys = {};
        this.character = {
            position: new THREE.Vector3(0, 50, 0),
            velocity: new THREE.Vector3(0, 0, 0),
            onGround: false,
            radius: 0.5,  // 1/10th size (was 5)
            height: 1.0   // 1/10th size (was 10)
        };
        this.mouseSensitivity = 0.003;
        this.walkSpeed = 15.0;   // 5x faster (was 3.0)
        this.runSpeed = 40.0;    // 5x faster (was 8.0)
        this.jumpForce = 25.0;   // Stronger jump (was 15.0)
        this.gravity = -60.0;    // 2x stronger gravity for less floaty feel (was -30.0)

        // Camera offset from character (third-person view)
        this.cameraDistance = 30;
        this.cameraHeight = 15;
        this.cameraAngle = { theta: 0, phi: Math.PI / 6 }; // Horizontal and vertical angles

        this.terrainData = null; // Will be set by viewer
    }

    activate(camera, controls, renderer) {
        super.activate(camera, controls, renderer);

        // Find a valid spawn position (non-null elevation tile)
        let spawnX = 0, spawnZ = 0;
        let terrainHeight = this.getTerrainHeight(0, 0);
        
        // If center is null/water, search for valid land in a spiral pattern
        if (terrainHeight <= 0 && typeof processedData !== 'undefined' && processedData) {
            let found = false;
            const maxSearch = 50;
            for (let radius = 1; radius < maxSearch && !found; radius++) {
                for (let angle = 0; angle < Math.PI * 2; angle += Math.PI / 8) {
                    const testX = Math.cos(angle) * radius * (params.bucketSize || 1);
                    const testZ = Math.sin(angle) * radius * (params.bucketSize || 1);
                    const testHeight = this.getTerrainHeight(testX, testZ);
                    if (testHeight > 0) {
                        spawnX = testX;
                        spawnZ = testZ;
                        terrainHeight = testHeight;
                        found = true;
                        break;
                    }
                }
            }
        }
        
        // Position character 10 body-units above the terrain top
        this.character.position.set(spawnX, terrainHeight + (this.character.height * 10), spawnZ);

        // Set up event listeners
        this.keydownHandler = (e) => this.onKeyDown(e);
        this.keyupHandler = (e) => this.onKeyUp(e);
        this.mouseMoveHandler = (e) => this.onMouseMoveJumping(e);
        this.mouseDownHandler = (e) => this.onMouseDownJumping(e);

        window.addEventListener('keydown', this.keydownHandler);
        window.addEventListener('keyup', this.keyupHandler);
        renderer.domElement.addEventListener('mousemove', this.mouseMoveHandler);
        renderer.domElement.addEventListener('mousedown', this.mouseDownHandler);

        // Disable OrbitControls
        if (controls) {
            this._controlsPrev = {
                enabled: controls.enabled,
                enableRotate: controls.enableRotate,
                enablePan: controls.enablePan,
                enableZoom: controls.enableZoom
            };
            controls.enabled = false;
        }

        // Create character mesh (simple cube for Map-Grandpa)
        this.createCharacterMesh();

        appendActivityLog('Jumping mode: Meet Map-Grandpa! WASD to move, Space to jump, right-click drag to look around.');
    }

    cleanup() {
        window.removeEventListener('keydown', this.keydownHandler);
        window.removeEventListener('keyup', this.keyupHandler);
        this.renderer.domElement.removeEventListener('mousemove', this.mouseMoveHandler);
        this.renderer.domElement.removeEventListener('mousedown', this.mouseDownHandler);

        // Remove character mesh
        if (this.characterMesh && scene) {
            scene.remove(this.characterMesh);
            this.characterMesh.geometry.dispose();
            this.characterMesh.material.dispose();
            this.characterMesh = null;
        }

        // Restore controls
        if (this.controls && this._controlsPrev) {
            this.controls.enabled = this._controlsPrev.enabled;
            this.controls.enableRotate = this._controlsPrev.enableRotate;
            this.controls.enablePan = this._controlsPrev.enablePan;
            this.controls.enableZoom = this._controlsPrev.enableZoom;
        }

        if (document.pointerLockElement === this.renderer.domElement) {
            document.exitPointerLock();
        }
    }

    createCharacterMesh() {
        // Simple cube representing Map-Grandpa
        const geometry = new THREE.BoxGeometry(
            this.character.radius * 2,
            this.character.height,
            this.character.radius * 2
        );
        const material = new THREE.MeshStandardMaterial({
            color: 0xff6600,
            metalness: 0.2,
            roughness: 0.7
        });
        this.characterMesh = new THREE.Mesh(geometry, material);

        // Add to scene (need to access global scene)
        if (typeof scene !== 'undefined' && scene) {
            scene.add(this.characterMesh);
        }
    }

    onKeyDown(event) {
        // Don't process keys if user is typing
        const activeElement = document.activeElement;
        const isTyping = activeElement && (
            activeElement.tagName === 'INPUT' ||
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.tagName === 'SELECT' ||
            activeElement.isContentEditable
        );
        if (isTyping) return;

        this.keys[event.key.toLowerCase()] = true;

        // Jump
        if (event.key === ' ' && this.character.onGround) {
            this.character.velocity.y = this.jumpForce;
            this.character.onGround = false;
        }
    }

    onKeyUp(event) {
        this.keys[event.key.toLowerCase()] = false;
    }

    onMouseDownJumping(event) {
        if (event.button === 2) { // Right click
            this.state.rotating = true;
            this.state.rotateStart = { x: event.clientX, y: event.clientY };
        }
    }

    onMouseMoveJumping(event) {
        if (this.state.rotating && this.state.rotateStart) {
            const deltaX = event.clientX - this.state.rotateStart.x;
            const deltaY = event.clientY - this.state.rotateStart.y;

            this.cameraAngle.theta -= deltaX * this.mouseSensitivity;
            this.cameraAngle.phi += deltaY * this.mouseSensitivity;

            // Clamp vertical angle
            this.cameraAngle.phi = Math.max(0.1, Math.min(Math.PI / 2, this.cameraAngle.phi));

            this.state.rotateStart = { x: event.clientX, y: event.clientY };
        }
    }

    onMouseUp(event) {
        if (event.button === 2) {
            this.state.rotating = false;
        }
    }

    getTerrainHeight(x, z) {
        // Get terrain height at character position
        // In bars mode, this returns the TOP of the bar (solid collision)
        if (typeof processedData === 'undefined' || !processedData) return 0;
        if (typeof params === 'undefined' || !params) return 0;

        // Use worldToGridIndex to convert world position to grid indices
        const idx = worldToGridIndex(x, z);
        if (!idx) return 0;

        const { i, j } = idx;
        const elevation = processedData.elevation[i] && processedData.elevation[i][j];
        if (elevation === null || elevation === undefined) return 0;

        // Return TOP of terrain/bar (elevation * vertical exaggeration)
        // This is the top surface of the bar (solid collision)
        return elevation * (params.verticalExaggeration || 1.0);
    }

    update() {
        if (!this.enabled) return;

        const deltaTime = 1 / 60; // Assume 60fps for physics

        // Movement input
        const speed = this.keys['shift'] ? this.runSpeed : this.walkSpeed;

        // Get camera-relative movement direction
        const forward = new THREE.Vector3(
            Math.sin(this.cameraAngle.theta),
            0,
            Math.cos(this.cameraAngle.theta)
        ).normalize();

        const right = new THREE.Vector3(
            Math.cos(this.cameraAngle.theta),
            0,
            -Math.sin(this.cameraAngle.theta)
        ).normalize();

        const movement = new THREE.Vector3();
        if (this.keys['w']) movement.addScaledVector(forward, speed);
        if (this.keys['s']) movement.addScaledVector(forward, -speed);
        if (this.keys['a']) movement.addScaledVector(right, -speed);
        if (this.keys['d']) movement.addScaledVector(right, speed);

        // Apply movement
        this.character.position.x += movement.x * deltaTime;
        this.character.position.z += movement.z * deltaTime;

        // Apply gravity
        this.character.velocity.y += this.gravity * deltaTime;
        this.character.position.y += this.character.velocity.y * deltaTime;

        // Terrain collision
        const terrainHeight = this.getTerrainHeight(this.character.position.x, this.character.position.z);
        const groundLevel = terrainHeight + this.character.height / 2;

        if (this.character.position.y <= groundLevel) {
            this.character.position.y = groundLevel;
            this.character.velocity.y = 0;
            this.character.onGround = true;
        } else {
            this.character.onGround = false;
        }

        // Update character mesh
        if (this.characterMesh) {
            this.characterMesh.position.copy(this.character.position);
        }

        // Update camera position (third-person)
        const camX = this.character.position.x - Math.sin(this.cameraAngle.theta) * this.cameraDistance * Math.cos(this.cameraAngle.phi);
        const camY = this.character.position.y + this.cameraDistance * Math.sin(this.cameraAngle.phi) + this.cameraHeight;
        const camZ = this.character.position.z - Math.cos(this.cameraAngle.theta) * this.cameraDistance * Math.cos(this.cameraAngle.phi);

        this.camera.position.set(camX, camY, camZ);
        this.camera.lookAt(this.character.position);

        // Update controls target
        if (this.controls) {
            this.controls.target.copy(this.character.position);
        }
    }
}

// ==================== BEYOND ALL REASON (Spring Engine RTS) STYLE ====================
// Precise replica of BAR's default "Spring Camera" mode
// Reference: Spring Engine SpringController.cpp, OverheadController.cpp
class BeyondAllReasonScheme extends CameraScheme {
    constructor() {
        super('Beyond All Reason', 'MMB = pan, Scroll = zoom to cursor, Ctrl+Scroll = tilt, Alt+Scroll = instant zoom, Arrow keys = pan, Shift = fast, Screen edge = pan');
        this.groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
        this.raycaster = new THREE.Raycaster();

        // BAR-style camera state
        this.keys = {};
        this.focusPoint = new THREE.Vector3(0, 0, 0);
        this.curDist = 1000; // Distance from focus point
        this.maxDist = 50000; // Maximum zoom out distance
        this.oldDist = 0; // For instant zoom toggle
        this.zoomBack = false; // Track if we should zoom back
        this.angle = Math.PI * 0.6; // Viewing angle (phi in spherical coords)

        // Movement speeds (matching Spring Engine defaults)
        this.scrollSpeed = 1.0; // CamSpringScrollSpeed * 0.1
        this.fastMultiplier = 3.0; // CameraMoveFastMult
        this.slowMultiplier = 0.3; // Slow movement factor
        this.edgeScrollSpeed = 0.8; // Screen edge scroll speed
        this.edgeScrollMargin = 20; // Pixels from edge to trigger

        // Screen edge state
        this.lastMouseX = 0;
        this.lastMouseY = 0;
        this.edgeScrollActive = false;
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

    activate(camera, controls, renderer) {
        super.activate(camera, controls, renderer);

        // Initialize focus point from current camera state
        const cameraDir = new THREE.Vector3();
        camera.getWorldDirection(cameraDir);
        const ray = new THREE.Ray(camera.position, cameraDir);
        const focusPoint = new THREE.Vector3();
        ray.intersectPlane(this.groundPlane, focusPoint);

        if (focusPoint) {
            this.focusPoint.copy(focusPoint);
        }
        this.curDist = camera.position.distanceTo(this.focusPoint);
        this.controls.target.copy(this.focusPoint);

        // Set up keyboard listeners
        this.keydownHandler = (e) => this.onKeyDown(e);
        this.keyupHandler = (e) => this.onKeyUp(e);
        window.addEventListener('keydown', this.keydownHandler);
        window.addEventListener('keyup', this.keyupHandler);

        // Mouse move for screen edge scrolling
        this.mouseMoveHandler = (e) => this.onMouseMoveEdge(e);
        renderer.domElement.addEventListener('mousemove', this.mouseMoveHandler);

        appendActivityLog('BAR camera: MMB=pan, Scroll=zoom (Ctrl=tilt, Alt=instant), Arrows=pan, Shift=fast');
    }

    cleanup() {
        if (this.keydownHandler) {
            window.removeEventListener('keydown', this.keydownHandler);
            window.removeEventListener('keyup', this.keyupHandler);
        }
        if (this.mouseMoveHandler && this.renderer) {
            this.renderer.domElement.removeEventListener('mousemove', this.mouseMoveHandler);
        }
    }

    onKeyDown(event) {
        // Don't process keys if user is typing
        const activeElement = document.activeElement;
        const isTyping = activeElement && (
            activeElement.tagName === 'INPUT' ||
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.tagName === 'SELECT' ||
            activeElement.isContentEditable
        );
        if (isTyping) return;

        this.keys[event.key.toLowerCase()] = true;
        this.keys[event.code] = true;

        // Track modifier states
        this.keys['shift'] = event.shiftKey;
        this.keys['ctrl'] = event.ctrlKey;
        this.keys['alt'] = event.altKey;
    }

    onKeyUp(event) {
        this.keys[event.key.toLowerCase()] = false;
        this.keys[event.code] = false;
        this.keys['shift'] = event.shiftKey;
        this.keys['ctrl'] = event.ctrlKey;
        this.keys['alt'] = event.altKey;
    }

    onMouseMoveEdge(event) {
        this.lastMouseX = event.clientX;
        this.lastMouseY = event.clientY;
    }

    onMouseDown(event) {
        if (event.button === 1) { // Middle mouse button = Pan (BAR default)
            this.state.panning = true;
            this.state.panStart = { x: event.clientX, y: event.clientY };
            this.state.cameraStart = this.camera.position.clone();
            this.state.focusStart = this.focusPoint.clone();
        } else if (event.button === 2) { // Right mouse button = alternative rotate (optional)
            // In BAR, RMB is used for unit commands, but we allow rotation here
            this.state.rotating = true;
            this.state.rotateStart = { x: event.clientX, y: event.clientY };
            this.state.cameraStart = this.camera.position.clone();
        }
    }

    onMouseMove(event) {
        // Middle mouse button pan (BAR's primary pan method)
        if (this.state.panning && this.state.panStart) {
            const deltaX = event.clientX - this.state.panStart.x;
            const deltaY = event.clientY - this.state.panStart.y;

            // Speed modifier based on current distance
            const pixelSize = (this.camera.fov * Math.PI / 180) / this.renderer.domElement.clientHeight * this.curDist * 2.0;
            let moveSpeed = pixelSize * this.scrollSpeed * 0.5;

            // Apply Shift (fast) or Ctrl (slow) modifier
            if (this.keys['shift']) {
                moveSpeed *= this.fastMultiplier;
            } else if (this.keys['ctrl']) {
                moveSpeed *= this.slowMultiplier;
            }

            // Get camera-relative directions (BAR uses flat forward direction)
            const forward = new THREE.Vector3();
            this.camera.getWorldDirection(forward);
            forward.y = 0;
            forward.normalize();

            const right = new THREE.Vector3();
            right.crossVectors(forward, new THREE.Vector3(0, 1, 0)).normalize();

            // Apply movement (inverted for natural drag feel)
            const movement = new THREE.Vector3();
            movement.addScaledVector(right, -deltaX * moveSpeed);
            movement.addScaledVector(forward, deltaY * moveSpeed);

            // Move focus point
            this.focusPoint.copy(this.state.focusStart).add(movement);
            this.focusPoint.y = 0; // Keep on ground plane

            // Update camera position to maintain distance
            this.updateCameraFromFocus();

            // Update pan start for incremental movement
            this.state.panStart.x = event.clientX;
            this.state.panStart.y = event.clientY;
            this.state.focusStart.copy(this.focusPoint);
        }

        // Optional rotation (RMB)
        if (this.state.rotating && this.state.rotateStart) {
            const deltaX = event.clientX - this.state.rotateStart.x;
            const deltaY = event.clientY - this.state.rotateStart.y;

            const offset = new THREE.Vector3().subVectors(this.state.cameraStart, this.focusPoint);
            const spherical = new THREE.Spherical().setFromVector3(offset);

            // Horizontal rotation
            spherical.theta -= deltaX * 0.005;

            // Vertical rotation with limits
            spherical.phi = Math.max(0.1, Math.min(Math.PI * 0.49, spherical.phi - deltaY * 0.005));
            this.angle = spherical.phi;

            offset.setFromSpherical(spherical);
            this.camera.position.copy(this.focusPoint).add(offset);
            this.camera.lookAt(this.focusPoint);
            this.controls.target.copy(this.focusPoint);
        }
    }

    onMouseUp(event) {
        if (event.button === 1) {
            this.state.panning = false;
        } else if (event.button === 2) {
            this.state.rotating = false;
        }
    }

    // Cancel all drag operations (called when mouse leaves canvas)
    cancelAllDrags() {
        this.state.panning = false;
        this.state.rotating = false;
    }

    // Override deactivate to ensure cleanup is called
    deactivate() {
        this.cleanup();
        super.deactivate();
    }

    onWheel(event) {
        const moveTilt = this.keys['ctrl'] || event.ctrlKey; // Ctrl+Scroll = tilt
        const moveReset = this.keys['alt'] || event.altKey; // Alt+Scroll = instant zoom
        const moveFast = this.keys['shift'] || event.shiftKey; // Shift = fast zoom

        const shiftSpeed = moveFast ? this.fastMultiplier * 0.2 : 1.0;
        // STANDARD: Scroll UP (negative delta) = zoom IN
        const move = event.deltaY > 0 ? 1 : -1; // Positive = scroll down = zoom out
        const scaledMove = 1.0 + (move * shiftSpeed * 0.1);

        if (moveTilt) {
            // Ctrl+Scroll: Tilt camera angle (BAR's movetilt behavior)
            this.angle -= (move * shiftSpeed * 0.05);
            this.angle = Math.max(0.1, Math.min(Math.PI * 0.49, this.angle));
            this.updateCameraFromFocus();
            return;
        }

        // Get cursor position for zoom-to-cursor
        const cursorPoint = this.raycast(event.clientX, event.clientY);
        if (!cursorPoint) return;

        const curDistPre = this.curDist;

        if (moveReset) {
            // Alt+Scroll: Instant zoom toggle (BAR's movereset behavior)
            if (move < 0) {
                // Zoom in with Alt = instant return to old distance
                if (this.zoomBack) {
                    this.curDist = this.oldDist;
                    this.zoomBack = false;
                }
            } else {
                // Zoom out with Alt = instant zoom to max height
                if (!this.zoomBack) {
                    this.oldDist = curDistPre;
                    this.zoomBack = true;
                }
                // Reset to overview position
                this.angle = Math.PI * 0.6;
                this.focusPoint.set(0, 0, 0);
                this.curDist = this.maxDist * 0.5;
            }
        } else if (move < 0) {
            // ZOOM IN - toward cursor position (BAR's cursorZoomIn behavior)
            const curCamPos = this.camera.position.clone();
            const newDir = new THREE.Vector3().subVectors(cursorPoint, curCamPos).normalize();

            // Calculate distance to cursor point
            const curGroundDist = curCamPos.distanceTo(cursorPoint);
            if (curGroundDist <= 0) return;

            // Move toward cursor
            const wantedPos = curCamPos.clone().addScaledVector(newDir, curGroundDist * (1 - scaledMove));

            // Calculate new distance to ground
            const newDist = wantedPos.y / Math.sin(this.angle);
            if (newDist > 5 && newDist < this.maxDist) {
                this.curDist = newDist;
                // Adjust focus point toward cursor
                this.focusPoint.lerp(cursorPoint, 0.1);
                this.focusPoint.y = 0;
            }

            this.zoomBack = false;
        } else {
            // ZOOM OUT - from center (BAR default behavior)
            this.curDist *= scaledMove;
            this.curDist = Math.min(this.curDist, this.maxDist);
            this.zoomBack = false;
        }

        this.curDist = Math.max(5, Math.min(this.maxDist, this.curDist));
        this.updateCameraFromFocus();
    }

    // Update camera position based on focus point, distance, and angle
    updateCameraFromFocus() {
        // Calculate camera position from spherical coordinates around focus
        const offset = new THREE.Vector3();
        const currentSpherical = new THREE.Spherical();

        // Get current horizontal angle from camera direction
        const currentOffset = new THREE.Vector3().subVectors(this.camera.position, this.focusPoint);
        currentSpherical.setFromVector3(currentOffset);

        // Create new position at current theta (horizontal) but with updated distance and phi (vertical)
        const spherical = new THREE.Spherical(this.curDist, this.angle, currentSpherical.theta);
        offset.setFromSpherical(spherical);

        this.camera.position.copy(this.focusPoint).add(offset);

        // Ensure minimum height above ground
        const minHeight = 5;
        if (this.camera.position.y < minHeight) {
            this.camera.position.y = minHeight;
        }

        this.camera.lookAt(this.focusPoint);
        this.controls.target.copy(this.focusPoint);
    }

    update() {
        if (!this.enabled) return;

        // Arrow key panning (BAR's primary keyboard navigation)
        const arrowUp = this.keys['arrowup'] || this.keys['ArrowUp'];
        const arrowDown = this.keys['arrowdown'] || this.keys['ArrowDown'];
        const arrowLeft = this.keys['arrowleft'] || this.keys['ArrowLeft'];
        const arrowRight = this.keys['arrowright'] || this.keys['ArrowRight'];
        const pageUp = this.keys['pageup'] || this.keys['PageUp'];
        const pageDown = this.keys['pagedown'] || this.keys['PageDown'];

        // Speed based on distance (BAR behavior)
        const pixelSize = (this.camera.fov * Math.PI / 180) / this.renderer.domElement.clientHeight * this.curDist * 2.0;
        let moveSpeed = pixelSize * this.scrollSpeed * 0.02;

        // Apply Shift (fast) or Ctrl (slow) modifier
        if (this.keys['shift']) {
            moveSpeed *= this.fastMultiplier;
        } else if (this.keys['ctrl']) {
            moveSpeed *= this.slowMultiplier;
        }

        // Get camera-relative directions
        const forward = new THREE.Vector3();
        this.camera.getWorldDirection(forward);
        forward.y = 0;
        forward.normalize();

        const right = new THREE.Vector3();
        right.crossVectors(forward, new THREE.Vector3(0, 1, 0)).normalize();

        const movement = new THREE.Vector3();

        // Arrow key movement (BAR uses arrow keys, not WASD)
        if (arrowUp) movement.addScaledVector(forward, moveSpeed);
        if (arrowDown) movement.addScaledVector(forward, -moveSpeed);
        if (arrowRight) movement.addScaledVector(right, moveSpeed);
        if (arrowLeft) movement.addScaledVector(right, -moveSpeed);

        // PageUp/PageDown for height adjustment (zoom)
        if (pageUp) {
            this.curDist *= 0.98; // Zoom in
            this.curDist = Math.max(5, this.curDist);
        }
        if (pageDown) {
            this.curDist *= 1.02; // Zoom out
            this.curDist = Math.min(this.maxDist, this.curDist);
        }

        // Screen edge scrolling (BAR feature)
        if (this.renderer) {
            const rect = this.renderer.domElement.getBoundingClientRect();
            const edgeX = this.lastMouseX - rect.left;
            const edgeY = this.lastMouseY - rect.top;
            const width = rect.width;
            const height = rect.height;

            // Check if mouse is near edges
            const margin = this.edgeScrollMargin;
            const edgeSpeed = moveSpeed * this.edgeScrollSpeed;

            if (edgeX < margin && edgeX >= 0) {
                movement.addScaledVector(right, -edgeSpeed * (1 - edgeX / margin));
            } else if (edgeX > width - margin && edgeX <= width) {
                movement.addScaledVector(right, edgeSpeed * (1 - (width - edgeX) / margin));
            }

            if (edgeY < margin && edgeY >= 0) {
                movement.addScaledVector(forward, edgeSpeed * (1 - edgeY / margin));
            } else if (edgeY > height - margin && edgeY <= height) {
                movement.addScaledVector(forward, -edgeSpeed * (1 - (height - edgeY) / margin));
            }
        }

        // Apply movement if any
        if (movement.length() > 0 || pageUp || pageDown) {
            this.focusPoint.add(movement);
            this.focusPoint.y = 0; // Keep on ground plane
            this.updateCameraFromFocus();
        }
    }

    // Reframe view (F key) - reset to default overview position
    reframeView() {
        // Reset to centered overview position (BAR-style default view)
        this.focusPoint.set(0, 0, 0);
        this.curDist = 2000; // Default viewing distance
        this.angle = Math.PI * 0.6; // Default tilt angle (about 35 degrees from vertical)
        this.zoomBack = false;

        // Reset terrain rotation if present
        if (window.terrainGroup) {
            window.terrainGroup.rotation.set(0, 0, 0);
        }

        this.updateCameraFromFocus();

        // Clear key state
        this.keys = {};

        console.log('BAR camera: View reset to default overview');
    }
}

// Export schemes
window.CameraSchemes = {
    'google-maps': new GoogleMapsScheme(),
    'google-earth': new GoogleEarthScheme(),
    'blender': new BlenderScheme(),
    'roblox': new RobloxScheme(),
    'unity': new UnityScheme(),
    'flying': new FlyingScheme(),
    'jumping': new JumpingScheme(),
    'beyond-all-reason': new BeyondAllReasonScheme()
};

