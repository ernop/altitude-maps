// Ground Plane Camera System
// Console sanitizer: strip non-ASCII (e.g., emojis) from log output
(() => {
    const sanitize = (v) => typeof v === 'string' ? v.replace(/[^\x00-\x7F]/g, '') : v;
    const wrap = (fn) => (...args) => fn.apply(console, args.map(sanitize));
    console.log = wrap(console.log);
    console.info = wrap(console.info);
    console.warn = wrap(console.warn);
    console.error = wrap(console.error);
})();
// The fundamental model used by Google Maps, Mapbox, etc.
// 
// Core concept:
// - Fixed ground plane at y=0 (the map surface)
// - Focus point ON the plane (where camera looks)
// - All operations relative to this plane

class GroundPlaneCamera extends CameraScheme {
    constructor() {
        super('Ground Plane (Google Earth)', 'Left = pan, Shift+Left = tilt, Alt+Left/Right = rotate, Scroll = zoom, WASD/QE = fly, F = reframe');
        this.groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
        this.focusPoint = new THREE.Vector3(0, 0, 0); // Point ON the ground plane
        this.raycaster = new THREE.Raycaster();
        
        // WASD keyboard movement state
        this.keysPressed = {};
        
        // Touch/trackpad gesture state
        this.touches = {};
        this.lastPinchDistance = 0;
        this.lastTouchCenter = null;
        this.lastTouchAngle = null; // For two-finger twist rotation
        this.touchStartPositions = null;
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
        
        // Setup keyboard event listeners for WASD flythrough
        this.keyDownHandler = this.onKeyDown.bind(this);
        this.keyUpHandler = this.onKeyUp.bind(this);
        window.addEventListener('keydown', this.keyDownHandler);
        window.addEventListener('keyup', this.keyUpHandler);
        
        // Setup touch/trackpad gesture listeners
        this.touchStartHandler = this.onTouchStart.bind(this);
        this.touchMoveHandler = this.onTouchMove.bind(this);
        this.touchEndHandler = this.onTouchEnd.bind(this);
        this.renderer.domElement.addEventListener('touchstart', this.touchStartHandler, { passive: false });
        this.renderer.domElement.addEventListener('touchmove', this.touchMoveHandler, { passive: false });
        this.renderer.domElement.addEventListener('touchend', this.touchEndHandler, { passive: false });
        this.renderer.domElement.addEventListener('touchcancel', this.touchEndHandler, { passive: false });
        
        // Initialized
    }
    
    deactivate() {
        // Clean up keyboard listeners
        if (this.keyDownHandler) {
            window.removeEventListener('keydown', this.keyDownHandler);
            window.removeEventListener('keyup', this.keyUpHandler);
        }
        
        // Clean up touch listeners
        if (this.touchStartHandler) {
            this.renderer.domElement.removeEventListener('touchstart', this.touchStartHandler);
            this.renderer.domElement.removeEventListener('touchmove', this.touchMoveHandler);
            this.renderer.domElement.removeEventListener('touchend', this.touchEndHandler);
            this.renderer.domElement.removeEventListener('touchcancel', this.touchEndHandler);
        }
        
        super.deactivate();
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
            
        } else if (event.button === 0 && event.altKey) { // Alt+Left = Tumble/Rotate (Maya style)
            this.state.rotating = true;
            this.state.rotatingWithAlt = true; // Track that Alt was used
            this.state.rotateStart = { x: event.clientX, y: event.clientY };
            this.state.cameraStart = this.camera.position.clone();
            this.state.focusStart = this.focusPoint.clone();
            
        } else if (event.button === 0) { // Left = Pan along plane
            this.state.panning = true;
            this.state.panStart = { x: event.clientX, y: event.clientY }; // Use screen coords for smooth panning
            this.state.focusStart = this.focusPoint.clone();
            this.state.cameraStart = this.camera.position.clone();
            
        } else if (event.button === 2) { // Right = Rotate around focus point
            this.state.rotating = true;
            this.state.rotatingWithAlt = false; // Right button, not Alt
            this.state.rotateStart = { x: event.clientX, y: event.clientY };
            this.state.cameraStart = this.camera.position.clone();
            this.state.focusStart = this.focusPoint.clone();
            
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
            // If Alt was used to start rotation and Alt is released, cancel smoothly
            if (this.state.rotatingWithAlt && !event.altKey) {
                
                this.state.rotating = false;
                this.state.rotatingWithAlt = false;
                return;
            }
            
            // Google Earth style rotation: rotate view around focus point
            // Horizontal drag = rotate around vertical axis (turn left/right)
            // Vertical drag = tilt view up/down
            const deltaX = event.clientX - this.state.rotateStart.x;
            const deltaY = event.clientY - this.state.rotateStart.y;
            
            // Get current offset from focus to camera
            const offset = new THREE.Vector3();
            offset.subVectors(this.state.cameraStart, this.state.focusStart);
            
            // Convert to spherical coordinates
            const spherical = new THREE.Spherical();
            spherical.setFromVector3(offset);
            
            // Apply rotation
            // Horizontal: rotate around vertical axis (theta)
            spherical.theta -= deltaX * 0.005;
            
            // Vertical: tilt (phi) - drag right to tilt down (see more ground)
            spherical.phi = Math.max(0.1, Math.min(Math.PI / 2 - 0.01, spherical.phi - deltaY * 0.005));
            
            // Convert back and update camera position
            offset.setFromSpherical(spherical);
            this.camera.position.copy(this.focusPoint).add(offset);
            
            // Update controls target
            this.controls.target.copy(this.focusPoint);
        }
    }
    
    onMouseUp(event) {
        if (event.button === 0) {
            if (this.state.tilting) {
                
                this.state.tilting = false;
            }
            if (this.state.panning) {
                
            }
            if (this.state.rotating) {
                
                this.state.rotating = false;
                this.state.rotatingWithAlt = false;
            }
            this.state.panning = false;
        } else if (event.button === 2) {
            this.state.rotating = false;
            this.state.rotatingWithAlt = false;
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
    
    // Keyboard handlers for WASD flythrough
    onKeyDown(event) {
        // Don't process keyboard shortcuts if user is typing in an input field
        const activeElement = document.activeElement;
        const isTyping = activeElement && (
            activeElement.tagName === 'INPUT' ||
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.tagName === 'SELECT' ||
            activeElement.isContentEditable ||
            activeElement.classList.contains('select2-search__field') // Select2 search box
        );
        
        if (isTyping) {
            return; // User is typing, don't process camera controls
        }
        
        const key = event.key.toLowerCase();
        
        // F key = reframe view to center of terrain
        if (key === 'f') {
            this.reframeView();
            return;
        }
        
        // Track which keys are pressed for continuous movement
        this.keysPressed[key] = true;
    }
    
    onKeyUp(event) {
        this.keysPressed[event.key.toLowerCase()] = false;
    }
    
    // Reframe view to center of terrain (F key)
    // Fixed camera position: directly above center, looking straight down
    // This gives a consistent map view every time
    reframeView() {
		// Standard fixed height (reduced by ~40% to move closer)
		const fixedHeight = 1320;
		
		// Slight tilt around X axis (east-west) so we see some relief
		// 15° from straight-down: z offset = y * tan(15°)
		const tiltDeg = 45;
		const zOffset = fixedHeight * Math.tan(THREE.MathUtils.degToRad(tiltDeg));
		this.camera.position.set(0, fixedHeight, zOffset);
        
        // Look at center of terrain
        this.focusPoint.set(0, 0, 0);
        this.controls.target.copy(this.focusPoint);
        
        // Standard up vector for normal camera controls
        this.camera.up.set(0, 1, 0);
        this.camera.lookAt(this.focusPoint);
		
    }
    
    // Set terrain bounds (called externally by viewer)
    setTerrainBounds(minX, maxX, minZ, maxZ) {
        this.terrainBounds = { minX, maxX, minZ, maxZ };
    }
    
    // Touch/trackpad gesture handlers
    onTouchStart(event) {
        event.preventDefault();
        
        // Store touch positions
        this.touches = {};
        for (let i = 0; i < event.touches.length; i++) {
            const touch = event.touches[i];
            this.touches[touch.identifier] = {
                x: touch.clientX,
                y: touch.clientY,
                startX: touch.clientX,
                startY: touch.clientY
            };
        }
        
        // Two-finger gestures
        if (event.touches.length === 2) {
            const touch1 = event.touches[0];
            const touch2 = event.touches[1];
            
            // Calculate initial pinch distance
            const dx = touch2.clientX - touch1.clientX;
            const dy = touch2.clientY - touch1.clientY;
            this.lastPinchDistance = Math.sqrt(dx * dx + dy * dy);
            
            // Calculate initial touch center
            this.lastTouchCenter = {
                x: (touch1.clientX + touch2.clientX) / 2,
                y: (touch1.clientY + touch2.clientY) / 2
            };

            // Initial angle between touches for twist rotation
            this.lastTouchAngle = Math.atan2(dy, dx);
            
            // Store starting camera position for gestures
            this.touchStartPositions = {
                camera: this.camera.position.clone(),
                focus: this.focusPoint.clone()
            };
            
        }
    }
    
    onTouchMove(event) {
        event.preventDefault();
        
        if (event.touches.length === 1) {
            // Single finger = pan (like mouse drag)
            const touch = event.touches[0];
            const prevTouch = this.touches[touch.identifier];
            
            if (prevTouch) {
                const deltaX = touch.clientX - prevTouch.x;
                const deltaY = touch.clientY - prevTouch.y;
                
                // Get camera vectors
                const right = new THREE.Vector3();
                this.camera.getWorldDirection(right);
                right.cross(this.camera.up).normalize();
                
                const forward = new THREE.Vector3();
                this.camera.getWorldDirection(forward);
                forward.y = 0;
                forward.normalize();
                
                // Calculate movement
                const distance = this.camera.position.distanceTo(this.focusPoint);
                const moveSpeed = distance * 0.002; // Slightly faster than mouse for touch
                
                const movement = new THREE.Vector3();
                movement.addScaledVector(right, -deltaX * moveSpeed);
                movement.addScaledVector(forward, deltaY * moveSpeed);
                movement.y = 0;
                
                // Move camera and focus
                this.camera.position.add(movement);
                this.focusPoint.add(movement);
                this.focusPoint.y = 0;
                
                this.controls.target.copy(this.focusPoint);
                
                // Update stored position
                prevTouch.x = touch.clientX;
                prevTouch.y = touch.clientY;
            }
        } else if (event.touches.length === 2) {
            // Two fingers = pinch zoom + pan
            const touch1 = event.touches[0];
            const touch2 = event.touches[1];
            
            // Calculate current pinch distance
            const dx = touch2.clientX - touch1.clientX;
            const dy = touch2.clientY - touch1.clientY;
            const currentDistance = Math.sqrt(dx * dx + dy * dy);
            const currentAngle = Math.atan2(dy, dx);
            
            // Calculate current center
            const currentCenter = {
                x: (touch1.clientX + touch2.clientX) / 2,
                y: (touch1.clientY + touch2.clientY) / 2
            };
            
            // Pinch zoom
            if (this.lastPinchDistance > 0) {
                const pinchDelta = currentDistance - this.lastPinchDistance;
                const zoomFactor = 1 - (pinchDelta * 0.01); // Sensitivity
                
                // Get center point on ground plane
                const centerPoint = this.raycastToPlane(currentCenter.x, currentCenter.y);
                
                if (centerPoint) {
                    // Move camera toward/away from center point
                    const direction = new THREE.Vector3();
                    direction.subVectors(centerPoint, this.camera.position);
                    const distance = direction.length();
                    direction.normalize();
                    
                    const newDistance = distance * zoomFactor;
                    if (newDistance > 5 && newDistance < 100000) {
                        const moveAmount = distance - newDistance;
                        this.camera.position.addScaledVector(direction, moveAmount);
                        
                        // Adjust focus point slightly
                        const towardsCursor = new THREE.Vector3();
                        towardsCursor.subVectors(centerPoint, this.focusPoint);
                        this.focusPoint.addScaledVector(towardsCursor, pinchDelta > 0 ? 0.05 : -0.05);
                        this.focusPoint.y = 0;
                        
                        this.controls.target.copy(this.focusPoint);
                    }
                }
            }
            
            // Two-finger pan
            if (this.lastTouchCenter) {
                const panDeltaX = currentCenter.x - this.lastTouchCenter.x;
                const panDeltaY = currentCenter.y - this.lastTouchCenter.y;
                
                const right = new THREE.Vector3();
                this.camera.getWorldDirection(right);
                right.cross(this.camera.up).normalize();
                
                const forward = new THREE.Vector3();
                this.camera.getWorldDirection(forward);
                forward.y = 0;
                forward.normalize();
                
                const distance = this.camera.position.distanceTo(this.focusPoint);
                const moveSpeed = distance * 0.002;
                
                const movement = new THREE.Vector3();
                movement.addScaledVector(right, -panDeltaX * moveSpeed);
                movement.addScaledVector(forward, panDeltaY * moveSpeed);
                movement.y = 0;
                
                this.camera.position.add(movement);
                this.focusPoint.add(movement);
                this.focusPoint.y = 0;
                
                this.controls.target.copy(this.focusPoint);
            }

            // Two-finger twist = rotate around vertical axis (like Google Earth)
            if (this.lastTouchAngle !== null) {
                const deltaAngle = currentAngle - this.lastTouchAngle;
                if (Math.abs(deltaAngle) > 0.001) {
                    // Rotate camera position around focus point by deltaAngle
                    const offset = new THREE.Vector3();
                    offset.subVectors(this.camera.position, this.focusPoint);
                    const spherical = new THREE.Spherical();
                    spherical.setFromVector3(offset);
                    // Horizontal rotation
                    spherical.theta -= deltaAngle; // match mouse: left drag increases theta negatively
                    // Constrain tilt angle a bit to avoid flipping
                    spherical.phi = Math.max(0.1, Math.min(Math.PI / 2 - 0.01, spherical.phi));
                    offset.setFromSpherical(spherical);
                    this.camera.position.copy(this.focusPoint).add(offset);
                    this.controls.target.copy(this.focusPoint);
                }
            }
            
            // Update for next frame
            this.lastPinchDistance = currentDistance;
            this.lastTouchCenter = currentCenter;
            this.lastTouchAngle = currentAngle;
        }
    }
    
    onTouchEnd(event) {
        event.preventDefault();
        
        // Remove ended touches
        const activeTouchIds = new Set();
        for (let i = 0; i < event.touches.length; i++) {
            activeTouchIds.add(event.touches[i].identifier);
        }
        
        // Clean up touches that ended
        for (const id in this.touches) {
            if (!activeTouchIds.has(parseInt(id))) {
                delete this.touches[id];
            }
        }
        
        // Reset gesture state if no touches left
        if (event.touches.length < 2) {
            this.lastPinchDistance = 0;
            this.lastTouchCenter = null;
            this.lastTouchAngle = null;
            this.touchStartPositions = null;
        }
    }
    
    update() {
        // WASD/QE keyboard movement (always active)
        if (this.enabled) {
            const moveSpeed = 2.0; // Units per frame
            
            // Get camera vectors
            const forward = new THREE.Vector3();
            this.camera.getWorldDirection(forward);
            
            const right = new THREE.Vector3();
            right.crossVectors(forward, this.camera.up).normalize();
            
            const movement = new THREE.Vector3();
            
            // WASD/QE movement
            if (this.keysPressed['w']) movement.addScaledVector(forward, moveSpeed);
            if (this.keysPressed['s']) movement.addScaledVector(forward, -moveSpeed);
            if (this.keysPressed['a']) movement.addScaledVector(right, -moveSpeed);
            if (this.keysPressed['d']) movement.addScaledVector(right, moveSpeed);
            if (this.keysPressed['q']) movement.y -= moveSpeed;  // Down
            if (this.keysPressed['e']) movement.y += moveSpeed;  // Up
            
            // Apply movement
            if (movement.length() > 0) {
                this.camera.position.add(movement);
                this.focusPoint.add(movement);
                this.focusPoint.y = 0; // Keep focus on ground plane
                this.controls.target.copy(this.focusPoint);
            }
        }
        
        // Ensure camera always looks at focus point
        if (this.enabled && this.focusPoint) {
            this.camera.lookAt(this.focusPoint);
        }
    }
}

// Add to schemes
window.CameraSchemes = window.CameraSchemes || {};
window.CameraSchemes['ground-plane'] = new GroundPlaneCamera();

