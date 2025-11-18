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

        // Create origin sphere for 3D feel (slightly larger)
        const sphereGeometry = new THREE.SphereGeometry(size * 0.18, 16, 16);
        const sphereMaterial = new THREE.MeshStandardMaterial({
            color: 0xffffff,
            metalness: 0.3,
            roughness: 0.7
        });
        const originSphere = new THREE.Mesh(sphereGeometry, sphereMaterial);
        this.group.add(originSphere);

        // Create thicker axes lines with 3D appearance
        const lineWidth = size * 0.08;
        const sphereRadius = size * 0.18; // Updated to match sphere geometry
        const totalArrowLength = size * 0.333; // 2/3 of original length
        const arrowheadLength = size * 0.2; // Larger arrowhead for clearer direction (60% of total)
        const arrowheadRadius = size * 0.08; // Larger arrowhead radius for clearer direction
        const arrowStartOffset = sphereRadius * 1.2; // Start arrow just outside sphere
        const labelGap = size * 0.15; // Gap between arrow tip and X/Y/Z labels
        const rotationLabelGap = size * 0.26; // Gap between X/Y/Z labels and English labels (30% larger)

        // X axis (Red) - positive direction only
        const xArrow = new THREE.ArrowHelper(
            new THREE.Vector3(1, 0, 0),
            new THREE.Vector3(arrowStartOffset, 0, 0), // Start outside sphere
            totalArrowLength, // Total arrow length
            xColor,
            arrowheadLength, // Smaller arrowhead
            arrowheadRadius  // Smaller arrowhead radius
        );
        this.group.add(xArrow);

        // Y axis (Green) - positive direction only
        const yArrow = new THREE.ArrowHelper(
            new THREE.Vector3(0, 1, 0),
            new THREE.Vector3(0, arrowStartOffset, 0), // Start outside sphere
            totalArrowLength, // Total arrow length
            yColor,
            arrowheadLength, // Smaller arrowhead
            arrowheadRadius  // Smaller arrowhead radius
        );
        this.group.add(yArrow);

        // Z axis (Blue) - positive direction only
        const zArrow = new THREE.ArrowHelper(
            new THREE.Vector3(0, 0, 1),
            new THREE.Vector3(0, 0, arrowStartOffset), // Start outside sphere
            totalArrowLength, // Total arrow length
            zColor,
            arrowheadLength, // Smaller arrowhead
            arrowheadRadius  // Smaller arrowhead radius
        );
        this.group.add(zArrow);

        // Create negative direction lines (dashed, thinner, gray)
        const negLineLength = (arrowStartOffset + totalArrowLength) * 0.85; // Scale with arrow length
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
        const labelSize = size * 1.5; // Much larger for readability

        // X label (Red) - positioned with gap after arrow tip
        const xLabel = this.createLabel('X', xColor, labelSize);
        xLabel.position.set(arrowStartOffset + totalArrowLength + labelGap, 0, 0);
        this.group.add(xLabel);
        this.labels.push(xLabel);

        // Y label (Green) - positioned with gap after arrow tip
        const yLabel = this.createLabel('Y', yColor, labelSize);
        yLabel.position.set(0, arrowStartOffset + totalArrowLength + labelGap, 0);
        this.group.add(yLabel);
        this.labels.push(yLabel);

        // Z label (Blue) - positioned with gap after arrow tip
        const zLabel = this.createLabel('Z', zColor, labelSize);
        zLabel.position.set(0, 0, arrowStartOffset + totalArrowLength + labelGap);
        this.group.add(zLabel);
        this.labels.push(zLabel);

        // Rotation labels: Pitch (X-axis), Yaw (Y-axis), Roll (Z-axis)
        // Colors match their corresponding axes
        // Positioned further along arrow direction (after X/Y/Z labels) with gap
        const rotationLabelSize = size * 1.0; // Much larger for readability

        // Pitch label (rotation around X axis) - matches X color (red)
        // Positioned along X axis, with gap after X label
        const pitchLabel = this.createLabel('Pitch', xColor, rotationLabelSize);
        pitchLabel.position.set(arrowStartOffset + totalArrowLength + labelGap + rotationLabelGap, 0, 0);
        this.group.add(pitchLabel);
        this.labels.push(pitchLabel);

        // Yaw label (rotation around Y axis) - matches Y color (green)
        // Positioned along Y axis, with gap after Y label
        const yawLabel = this.createLabel('Yaw', yColor, rotationLabelSize);
        yawLabel.position.set(0, arrowStartOffset + totalArrowLength + labelGap + rotationLabelGap, 0);
        this.group.add(yawLabel);
        this.labels.push(yawLabel);

        // Roll label (rotation around Z axis) - matches Z color (blue)
        // Positioned along Z axis, with gap after Z label
        const rollLabel = this.createLabel('Roll', zColor, rotationLabelSize);
        rollLabel.position.set(0, 0, arrowStartOffset + totalArrowLength + labelGap + rotationLabelGap);
        this.group.add(rollLabel);
        this.labels.push(rollLabel);

        // Add to scene
        scene.add(this.group);

        // Position relative to camera viewport
        this.updatePosition = () => {
            if (!this.group || !window.camera || !window.renderer) return;

            // Convert viewport coordinates (0-1) to normalized device coordinates (-1 to +1)
            // viewportX: 0=left, 1=right -> ndcX: -1=left, +1=right
            const ndcX = (this.viewportX * 2) - 1; // 0.5 -> 0 (center)
            // viewportY: 0=top, 1=bottom -> ndcY: +1=top, -1=bottom
            // But we want viewportY to mean "distance from bottom", so flip it
            const ndcY = -1 + (this.viewportY * 2); // 0.08 -> -0.84 (8% from bottom)

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
        // Scale canvas size with label size for better quality
        const canvasScale = Math.max(1, size / 0.3); // Base scale on original size
        canvas.width = 256 * canvasScale; // Larger canvas for bigger fonts
        canvas.height = 64 * canvasScale; // Larger canvas for bigger fonts

        // No background - completely transparent (text only)

        // Text - font size scales with label size (much larger for readability)
        const fontSize = 48 * (size / 0.3); // Scale from base size 0.3, larger base font
        context.font = `Bold ${fontSize}px Arial`;
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
