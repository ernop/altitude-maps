// Ground Plane Camera System
// Console sanitizer: strip non-ASCII (e.g., emojis) from log output
(() => {
    const sanitize = (v) => typeof v === 'string' ? v.replace(/[^\x00-\x7F]/g, '') : v;
    const wrap = (fn) => (...args) => {
        return fn.apply(console, args.map(sanitize));
    };
    console.log = wrap(console.log);
    console.info = wrap(console.info);
    // Do not wrap warn/error so critical issues are never suppressed or altered
    // Note: Message filtering now handled by viewer-advanced.js to allow UI log mirroring
})();
// Custom ground plane camera system (project default)
// 
// Core concept:
// - Fixed ground plane at y=0 (the map surface)
// - Focus point ON the plane (where camera looks)
// - All operations relative to this plane

class GroundPlaneCamera extends CameraScheme {
    constructor() {
        super('Custom (Default)', 'Left = pan, Right = rotate map (board game physics), Middle = rotate head (look around), Shift+Left = tilt, Alt+Left = rotate, Scroll = zoom, WASD/QE = fly, F = reframe');
        this.groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
        this.focusPoint = new THREE.Vector3(0, 0, 0); // Point ON the ground plane
        this.raycaster = new THREE.Raycaster();

        // WASD keyboard movement state
        this.keysPressed = {};
        this.baseMoveSpeed = 4.0; // Base movement speed (doubled from 2.0)
        this.currentMoveSpeed = 4.0; // Current speed with acceleration
        this.maxMoveSpeed = 8.0; // Maximum speed (2x base)
        this.acceleration = 0.05; // Speed increase per frame (gradual)

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

        } else if (event.button === 0) { // Left = Pan (standard map grab and drag)
            this.state.panning = true;
            this.state.panStart = { x: event.clientX, y: event.clientY };
            this.state.focusStart = this.focusPoint.clone();
            this.state.cameraStart = this.camera.position.clone();

        } else if (event.button === 1) { // Middle = Rotate Head (your head moves, camera position fixed)
            this.state.rotatingCamera = true;
            this.state.rotateCameraStart = { x: event.clientX, y: event.clientY };

            // Store initial camera orientation as Euler angles (YXZ order)
            const euler = new THREE.Euler(0, 0, 0, 'YXZ');
            euler.setFromQuaternion(this.camera.quaternion);
            this.state.startYaw = euler.y;
            this.state.startPitch = euler.x;

        } else if (event.button === 2) { // Right = Rotate Map (steering wheel / roll physics)
            this.state.rotatingTerrain = true;
            this.state.rotateTerrainStart = { x: event.clientX, y: event.clientY };

            // Store initial terrain group rotation as quaternion
            if (window.terrainGroup) {
                this.state.terrainStartRotationQuaternion = window.terrainGroup.quaternion.clone();
            }

        }
    }

    onMouseMove(event) {
        if (this.state.panning && this.state.panStart) {
            // Pan: Camera moves incrementally with mouse
            // Calculate delta from LAST position (not initial click)
            const deltaX = event.clientX - this.state.panStart.x;
            const deltaY = event.clientY - this.state.panStart.y;

            // Natural head movement: only pitch and yaw, NO ROLL
            // Use world up vector (0,1,0) to ensure no roll is introduced
            const worldUp = new THREE.Vector3(0, 1, 0);

            // Get camera forward direction (view direction)
            const forward = new THREE.Vector3();
            this.camera.getWorldDirection(forward);

            // Calculate right vector using world up (prevents roll)
            // Match existing codebase pattern: crossVectors(forward, up) gives left vector
            // We'll use it as-is for consistency with existing code
            const right = new THREE.Vector3();
            right.crossVectors(forward, worldUp).normalize();

            // Recalculate forward as horizontal projection (for ground plane movement)
            const forwardHorizontal = new THREE.Vector3();
            forwardHorizontal.copy(forward);
            forwardHorizontal.y = 0; // Project onto ground plane
            forwardHorizontal.normalize();

            // Calculate movement speed based on distance from focus point
            const distance = this.camera.position.distanceTo(this.focusPoint);
            const moveSpeed = distance * 0.0005; // Adaptive speed (50% slower than before)

            // Calculate incremental movement
            // Mouse left → camera moves right (reversed sense)
            // Mouse up → camera moves up (already working correctly)
            const movement = new THREE.Vector3();
            movement.addScaledVector(right, -deltaX * moveSpeed);      // Mouse left = camera right (reversed)
            movement.addScaledVector(forwardHorizontal, deltaY * moveSpeed);    // Mouse down = camera back (was already correct)
            movement.y = 0; // Keep movement on ground plane

            // Apply incremental movement
            this.focusPoint.add(movement);
            this.focusPoint.y = 0; // Keep on plane

            this.camera.position.add(movement);

            // Update controls target
            this.controls.target.copy(this.focusPoint);

            // Ensure camera up vector stays aligned with world up (prevents roll accumulation)
            // This maintains natural head orientation (no tilt/roll)
            this.camera.up.copy(worldUp);

            // Update pan start to current position for next frame (incremental)
            this.state.panStart.x = event.clientX;
            this.state.panStart.y = event.clientY;
        }

        if (this.state.tilting) {
            // If Shift key is released mid-drag, cancel tilt operation smoothly
            if (!event.shiftKey) {

                this.state.tilting = false;
                return;
            }

            const deltaY = event.clientY - this.state.tiltStart.y;

            // Only apply tilt if mouse has actually moved (prevents initial jump)
            if (Math.abs(deltaY) > 0) {
                // Get vector from pivot point to camera
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
                // Use the LOCKED pivot point (focusStart)
                offset.setFromSpherical(spherical);
                this.camera.position.copy(this.state.focusStart).add(offset);
                this.camera.lookAt(this.state.focusStart);
                this.controls.target.copy(this.state.focusStart);
            }
        }

        if (this.state.rotating) {
            // If Alt was used to start rotation and Alt is released, cancel smoothly
            if (this.state.rotatingWithAlt && !event.altKey) {

                this.state.rotating = false;
                this.state.rotatingWithAlt = false;
                return;
            }

            const deltaX = event.clientX - this.state.rotateStart.x;
            const deltaY = event.clientY - this.state.rotateStart.y;

            // Calculate rotation angles from mouse movement
            const rotationSpeed = 0.005;
            const horizontalAngle = -deltaX * rotationSpeed;
            const verticalAngle = -deltaY * rotationSpeed;

            // Rotate camera position around pivot point
            // Start from initial camera position, translate to pivot origin
            const pos = this.state.cameraStart.clone().sub(this.state.focusStart);

            // Horizontal rotation (around Y axis through pivot)
            pos.applyAxisAngle(new THREE.Vector3(0, 1, 0), horizontalAngle);

            // Vertical rotation (around right/horizontal axis through pivot)
            // First check current angle to prevent flipping
            const currentAngle = Math.acos(pos.y / pos.length());
            const right = new THREE.Vector3(1, 0, 0);
            right.applyAxisAngle(new THREE.Vector3(0, 1, 0), horizontalAngle);

            // Clamp vertical angle to prevent flipping (keep between 0.1 and 179.9 degrees)
            const newAngle = currentAngle + verticalAngle;
            const minAngle = 0.1; // Almost straight up
            const maxAngle = Math.PI - 0.1; // Almost straight down

            if (newAngle > minAngle && newAngle < maxAngle) {
                pos.applyAxisAngle(right, verticalAngle);
            }

            // Translate back from pivot origin
            pos.add(this.state.focusStart);

            // Update camera position
            this.camera.position.copy(pos);

            // Look at pivot
            this.camera.lookAt(this.state.focusStart);
        }

        if (this.state.rotatingCamera) {
            // MMB: Rotate Head (egocentric - you turn your head)
            // Camera position stays completely fixed, only orientation changes
            // This is PURE HEAD MOVEMENT - nothing else changes
            const deltaX = event.clientX - this.state.rotateCameraStart.x;
            const deltaY = event.clientY - this.state.rotateCameraStart.y;

            // Rotation sensitivity
            const sensitivity = 0.005;

            // Calculate new yaw and pitch from initial values
            // Mouse left (negative deltaX) → positive yaw (turn left)
            // Mouse up (negative deltaY) → positive pitch (look up)
            // Negate deltaX so mouse left = turn left (positive yaw)
            const yaw = this.state.startYaw + (-deltaX * sensitivity);
            let pitch = this.state.startPitch + (-deltaY * sensitivity);

            // Clamp pitch to prevent gimbal lock (don't look straight up/down)
            const maxPitch = Math.PI / 2 - 0.01;
            pitch = Math.max(-maxPitch, Math.min(maxPitch, pitch));

            // Apply rotation using Euler angles (YXZ order prevents roll)
            const euler = new THREE.Euler(pitch, yaw, 0, 'YXZ');
            this.camera.quaternion.setFromEuler(euler);
            this.camera.up.set(0, 1, 0); // Maintain world up

            // Focus point stays locked - don't recalculate it
            // This prevents exponential drift where each rotation recalculates
            // focus point based on current orientation, causing distance to grow
        }

        if (this.state.rotatingTerrain) {
            // RMB: Rotate Terrain (turntable + tilt)
            // Horizontal mouse = spin around Y axis (turntable)
            // Vertical mouse = tilt around screen-horizontal axis (camera-relative)
            if (!window.terrainGroup) return;

            const deltaX = event.clientX - this.state.rotateTerrainStart.x;
            const deltaY = event.clientY - this.state.rotateTerrainStart.y;

            // Rotation speed
            const rotationSpeed = 0.005;

            // Start from initial rotation
            let newRotation = this.state.terrainStartRotationQuaternion.clone();

            // HORIZONTAL MOVEMENT: Rotate around axis parallel to camera up (screen vertical)
            if (Math.abs(deltaX) > 0) {
                const cameraUpAxis = this.camera.up.clone().applyQuaternion(this.camera.quaternion).normalize();
                if (cameraUpAxis.lengthSq() < 1e-6) {
                    cameraUpAxis.set(0, 1, 0);
                }
                const angleUp = deltaX * rotationSpeed;
                const rotationUp = new THREE.Quaternion();
                rotationUp.setFromAxisAngle(cameraUpAxis, angleUp);
                newRotation = new THREE.Quaternion().multiplyQuaternions(rotationUp, newRotation);
            }

            // VERTICAL MOVEMENT: Rotate around camera's horizontal axis (screen-relative tilt)
            if (Math.abs(deltaY) > 0) {
                // Calculate camera view direction (from camera toward terrain center)
                const terrainCenter = window.terrainGroup.position;
                const viewDir = new THREE.Vector3();
                viewDir.subVectors(terrainCenter, this.camera.position).normalize();

                // Calculate horizontal axis = perpendicular to both Y-axis and view direction
                // This is the axis that's horizontal in screen space
                const yAxis = new THREE.Vector3(0, 1, 0);
                const horizontalAxis = new THREE.Vector3();
                horizontalAxis.crossVectors(viewDir, yAxis).normalize();

                // Mouse DOWN = positive deltaY = terrain tilts forward (near edge up)
                // Mouse UP = negative deltaY = terrain tilts backward (far edge up)
                const angleH = deltaY * rotationSpeed;
                const rotationH = new THREE.Quaternion();
                rotationH.setFromAxisAngle(horizontalAxis, angleH);
                newRotation = new THREE.Quaternion().multiplyQuaternions(rotationH, newRotation);
            }

            // Apply combined rotation
            window.terrainGroup.quaternion.copy(newRotation);
        }
    }

    onMouseUp(event) {
        if (event.button === 0) {
            if (this.state.tilting) {
                this.state.tilting = false;
            }
            if (this.state.rotating && this.state.rotatingWithAlt) {
                this.state.rotating = false;
                this.state.rotatingWithAlt = false;
            }
            this.state.panning = false;
        } else if (event.button === 1) {
            this.state.rotatingCamera = false;
        } else if (event.button === 2) {
            this.state.rotatingTerrain = false;
        }
    }

    // Cancel all active drag operations (called when mouse leaves canvas or on cleanup)
    cancelAllDrags() {
        this.state.panning = false;
        this.state.tilting = false;
        this.state.rotating = false;
        this.state.rotatingWithAlt = false;
        this.state.rotatingCamera = false;
        this.state.rotatingTerrain = false;
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
        if (newDistance > 50000) return; // Don't zoom out too far (prevents raycast failures)

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
        // 15deg from straight-down: z offset = y * tan(15deg)
        const tiltDeg = 45;
        const zOffset = fixedHeight * Math.tan(THREE.MathUtils.degToRad(tiltDeg));
        this.camera.position.set(0, fixedHeight, zOffset);

        // Look at center of terrain
        this.focusPoint.set(0, 0, 0);
        this.controls.target.copy(this.focusPoint);

        // Standard up vector for normal camera controls
        this.camera.up.set(0, 1, 0);

        // Reset camera quaternion to identity (clear any rotation state)
        this.camera.quaternion.set(0, 0, 0, 1);

        // Apply lookAt AFTER quaternion reset
        this.camera.lookAt(this.focusPoint);

        // Reset terrain group rotation (the map itself can be rotated via RMB drag)
        if (window.terrainGroup) {
            window.terrainGroup.rotation.set(0, 0, 0);
            console.log('Terrain rotation reset to (0, 0, 0)');
        }

        // Clear all keyboard state (stop any in-progress movement)
        this.keysPressed = {};

        // Reset movement speed to base speed
        this.currentMoveSpeed = this.baseMoveSpeed;

        // Clear touch/gesture state
        this.touches = {};
        this.lastPinchDistance = 0;
        this.lastTouchCenter = null;
        this.lastTouchAngle = null;
        this.touchStartPositions = null;

        // Update OrbitControls to sync with new camera state
        this.controls.update();

        console.log('Camera fully reset: position, orientation, focus, terrain rotation, and all internal state cleared');
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
                    if (newDistance > 5 && newDistance < 50000) {
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

            // Two-finger twist = rotate around vertical axis
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
        // WASD/QE keyboard movement (always active - Roblox Studio style)
        if (this.enabled) {
            // Get camera vectors
            const forward = new THREE.Vector3();
            this.camera.getWorldDirection(forward);

            const right = new THREE.Vector3();
            right.crossVectors(forward, this.camera.up).normalize();

            const movement = new THREE.Vector3();

            // Check if any movement keys are pressed
            const isMoving = this.keysPressed['w'] || this.keysPressed['s'] ||
                this.keysPressed['a'] || this.keysPressed['d'] ||
                this.keysPressed['q'] || this.keysPressed['e'];

            if (isMoving) {
                // Gradually increase speed while moving
                this.currentMoveSpeed = Math.min(this.currentMoveSpeed + this.acceleration, this.maxMoveSpeed);

                // WASD/QE movement - pure free flight, no constraints
                if (this.keysPressed['w']) movement.addScaledVector(forward, this.currentMoveSpeed);
                if (this.keysPressed['s']) movement.addScaledVector(forward, -this.currentMoveSpeed);
                if (this.keysPressed['a']) movement.addScaledVector(right, -this.currentMoveSpeed);
                if (this.keysPressed['d']) movement.addScaledVector(right, this.currentMoveSpeed);
                if (this.keysPressed['q']) movement.y -= this.currentMoveSpeed;  // Down
                if (this.keysPressed['e']) movement.y += this.currentMoveSpeed;  // Up

                // Move camera in pure space
                if (movement.length() > 0) {
                    this.camera.position.add(movement);

                    // Update focus point to stay ahead of camera for mouse controls
                    const cameraDir = new THREE.Vector3();
                    this.camera.getWorldDirection(cameraDir);
                    this.focusPoint.copy(this.camera.position).addScaledVector(cameraDir, 1000);
                    this.controls.target.copy(this.focusPoint);
                }
            } else {
                // Immediately reset speed when movement stops
                this.currentMoveSpeed = this.baseMoveSpeed;
            }
        }

        // Only update camera orientation during active mouse operations
        // Mouse operations handle lookAt themselves
        // Keyboard movement maintains camera orientation (no auto-lookAt)
    }
}

// Add to schemes
window.CameraSchemes = window.CameraSchemes || {};
window.CameraSchemes['ground-plane'] = new GroundPlaneCamera();

