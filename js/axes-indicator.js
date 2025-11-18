/**
 * Axes Indicator - Visual 3D axes helper
 * Industry standard: X=Red, Y=Green, Z=Blue (RGB=XYZ)
 * Rotates with world/terrain to show world orientation
 */

class AxesIndicator {
    constructor() {
        this.group = null;
        this.labels = [];
    }

    /**
     * Create the axes indicator group
     * @param {THREE.Scene} scene - The Three.js scene to add to
     * @param {Object} options - Configuration options
     * @param {number} options.size - Size of axes (default: 0.3)
     * @param {number} options.viewportX - Horizontal position in viewport (0-1, default: 0.5 = center)
     * @param {number} options.viewportY - Vertical position in viewport (0-1, default: 0.08 = bottom middle)
     * @param {number} options.distance - Distance from camera (default: 3)
     */
    create(scene, options = {}) {
        const size = options.size || 0.3; // 20% of original 1.5
        this.viewportX = options.viewportX !== undefined ? options.viewportX : 0.5; // Center horizontally
        this.viewportY = options.viewportY !== undefined ? options.viewportY : 0.08; // Bottom middle (8% from bottom)
        this.distance = options.distance !== undefined ? options.distance : 3;

        this.group = new THREE.Group();
        this.scene = scene;

        // Industry standard colors: X=Red, Y=Green, Z=Blue (RGB=XYZ)
        const xColor = 0xff0000; // Red
        const yColor = 0x00ff00; // Green
        const zColor = 0x0088ff; // Blue

        // Create origin sphere for 3D feel
        const sphereGeometry = new THREE.SphereGeometry(size * 0.15, 16, 16);
        const sphereMaterial = new THREE.MeshStandardMaterial({
            color: 0xffffff,
            metalness: 0.3,
            roughness: 0.7
        });
        const originSphere = new THREE.Mesh(sphereGeometry, sphereMaterial);
        this.group.add(originSphere);

        // Create thicker axes lines with 3D appearance
        const lineWidth = size * 0.08;
        const arrowLength = size * 0.4;
        const arrowRadius = size * 0.06;

        // X axis (Red) - positive direction only
        const xArrow = new THREE.ArrowHelper(
            new THREE.Vector3(1, 0, 0),
            new THREE.Vector3(0, 0, 0),
            size,
            xColor,
            arrowLength,
            arrowRadius
        );
        this.group.add(xArrow);

        // Y axis (Green) - positive direction only
        const yArrow = new THREE.ArrowHelper(
            new THREE.Vector3(0, 1, 0),
            new THREE.Vector3(0, 0, 0),
            size,
            yColor,
            arrowLength,
            arrowRadius
        );
        this.group.add(yArrow);

        // Z axis (Blue) - positive direction only
        const zArrow = new THREE.ArrowHelper(
            new THREE.Vector3(0, 0, 1),
            new THREE.Vector3(0, 0, 0),
            size,
            zColor,
            arrowLength,
            arrowRadius
        );
        this.group.add(zArrow);

        // Create negative direction lines (dashed, thinner, gray)
        const negLineLength = size * 0.85;
        const negLineMaterial = new THREE.LineBasicMaterial({
            color: 0x666666,
            linewidth: 1,
            transparent: true,
            opacity: 0.5
        });

        // X negative
        const xNegGeometry = new THREE.BufferGeometry();
        xNegGeometry.setAttribute('position', new THREE.Float32BufferAttribute([
            0, 0, 0,
            -negLineLength, 0, 0
        ], 3));
        const xNegLine = new THREE.Line(xNegGeometry, negLineMaterial);
        this.group.add(xNegLine);

        // Y negative
        const yNegGeometry = new THREE.BufferGeometry();
        yNegGeometry.setAttribute('position', new THREE.Float32BufferAttribute([
            0, 0, 0,
            0, -negLineLength, 0
        ], 3));
        const yNegLine = new THREE.Line(yNegGeometry, negLineMaterial);
        this.group.add(yNegLine);

        // Z negative
        const zNegGeometry = new THREE.BufferGeometry();
        zNegGeometry.setAttribute('position', new THREE.Float32BufferAttribute([
            0, 0, 0,
            0, 0, -negLineLength
        ], 3));
        const zNegLine = new THREE.Line(zNegGeometry, negLineMaterial);
        this.group.add(zNegLine);

        // Industry standard labels: X, Y, Z closer to arrow tips
        const labelDistance = size * 1.15; // Closer to arrows
        const labelSize = size * 0.3;

        // X label (Red) - positioned at arrow tip
        const xLabel = this.createLabel('X', xColor, labelSize);
        xLabel.position.set(size, 0, 0);
        this.group.add(xLabel);
        this.labels.push(xLabel);

        // Y label (Green) - positioned at arrow tip
        const yLabel = this.createLabel('Y', yColor, labelSize);
        yLabel.position.set(0, size, 0);
        this.group.add(yLabel);
        this.labels.push(yLabel);

        // Z label (Blue) - positioned at arrow tip
        const zLabel = this.createLabel('Z', zColor, labelSize);
        zLabel.position.set(0, 0, size);
        this.group.add(zLabel);
        this.labels.push(zLabel);

        // Rotation labels: Pitch (X-axis), Yaw (Y-axis), Roll (Z-axis)
        const rotationLabelDistance = size * 1.35;
        const rotationLabelSize = size * 0.25;

        // Pitch label (rotation around X axis) - positioned near X axis
        const pitchLabel = this.createLabel('Pitch', 0xffaa00, rotationLabelSize);
        pitchLabel.position.set(rotationLabelDistance * 0.7, rotationLabelDistance * 0.3, 0);
        this.group.add(pitchLabel);
        this.labels.push(pitchLabel);

        // Yaw label (rotation around Y axis) - positioned near Y axis
        const yawLabel = this.createLabel('Yaw', 0xaa00ff, rotationLabelSize);
        yawLabel.position.set(rotationLabelDistance * 0.3, rotationLabelDistance * 0.7, rotationLabelDistance * 0.3);
        this.group.add(yawLabel);
        this.labels.push(yawLabel);

        // Roll label (rotation around Z axis) - positioned near Z axis
        const rollLabel = this.createLabel('Roll', 0x00ffaa, rotationLabelSize);
        rollLabel.position.set(rotationLabelDistance * 0.3, rotationLabelDistance * 0.3, rotationLabelDistance * 0.7);
        this.group.add(rollLabel);
        this.labels.push(rollLabel);

        // Add to scene
        scene.add(this.group);

        // Position relative to camera viewport
        this.updatePosition = () => {
            if (!this.group || !window.camera || !window.renderer) return;

            // Convert viewport coordinates (0-1) to normalized device coordinates (-1 to +1)
            const ndcX = (this.viewportX * 2) - 1; // 0.5 -> 0 (center)
            const ndcY = -((this.viewportY * 2) - 1); // 0.08 -> 0.84 (bottom, flipped)

            // Create a raycaster from camera through the viewport point
            const raycaster = new THREE.Raycaster();
            raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), window.camera);

            // Position the group at a fixed distance along the ray
            const direction = raycaster.ray.direction;
            const position = raycaster.ray.origin.clone();
            position.addScaledVector(direction, this.distance);

            this.group.position.copy(position);

            // Rotate axes indicator to match world/terrain orientation (shows world axes)
            // This makes it rotate with the terrain as the user rotates the map
            if (window.terrainGroup && window.terrainGroup.quaternion) {
                this.group.quaternion.copy(window.terrainGroup.quaternion);
            } else {
                // Default to identity (no rotation) if terrainGroup not available
                this.group.quaternion.set(0, 0, 0, 1);
            }
        };

        // Make labels always face camera
        this.updateLabels = () => {
            if (!this.group || !window.camera) return;
            this.labels.forEach(label => {
                label.lookAt(window.camera.position);
            });
        };
    }

    /**
     * Create a text label sprite
     */
    createLabel(text, color, size) {
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.width = 128;
        canvas.height = 32;

        // Semi-transparent dark background for readability
        context.fillStyle = 'rgba(0, 0, 0, 0.6)';
        context.fillRect(0, 0, canvas.width, canvas.height);

        // Text
        context.font = 'Bold 24px Arial';
        context.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        context.fillText(text, canvas.width / 2, canvas.height / 2);

        // Create sprite
        const texture = new THREE.CanvasTexture(canvas);
        texture.needsUpdate = true;
        const spriteMaterial = new THREE.SpriteMaterial({
            map: texture,
            transparent: true,
            depthTest: false,
            depthWrite: false
        });
        const sprite = new THREE.Sprite(spriteMaterial);
        sprite.scale.set(size, size * 0.25, 1);

        return sprite;
    }

    /**
     * Update position relative to camera viewport, rotation, and label orientations
     * Call this in the render loop
     */
    update() {
        if (this.updatePosition) {
            this.updatePosition();
        }
        if (this.updateLabels) {
            this.updateLabels();
        }
    }

    /**
     * Show/hide the axes indicator
     */
    setVisible(visible) {
        if (this.group) {
            this.group.visible = visible;
        }
    }

    /**
     * Remove from scene
     */
    dispose() {
        if (this.group && this.group.parent) {
            this.group.parent.remove(this.group);
        }
        this.labels.forEach(label => {
            if (label.material && label.material.map) {
                label.material.map.dispose();
            }
            if (label.material) {
                label.material.dispose();
            }
        });
        this.group = null;
        this.labels = [];
    }
}

// Export singleton instance
window.AxesIndicator = window.AxesIndicator || new AxesIndicator();
