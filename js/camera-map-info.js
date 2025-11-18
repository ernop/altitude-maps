/**
 * Camera and Map Info Display Module
 * 
 * PURPOSE:
 * Live display of camera position/direction and map position/orientation
 * Updates continuously in the lower-left corner
 * 
 * DEPENDS ON:
 * - Global: window.camera (Three.js Camera)
 * - Global: window.terrainGroup (Three.js Group)
 */

(function() {
    'use strict';

    // Prevent duplicate initialization
    if (window.CameraMapInfo) {
        console.warn('[CameraMapInfo] Already initialized');
        return;
    }

    let initialized = false;
    let cameraPosEl = null;
    let cameraDirEl = null;
    let mapPosEl = null;
    let mapOrientEl = null;

    /**
     * Format a number to 2 decimal places
     */
    function formatNumber(num) {
        return num.toFixed(2);
    }

    /**
     * Format position vector as (x, y, z)
     */
    function formatPosition(pos) {
        if (!pos) return '--';
        return `(${formatNumber(pos.x)}, ${formatNumber(pos.y)}, ${formatNumber(pos.z)})`;
    }

    /**
     * Get camera direction from quaternion
     * Returns forward direction vector
     */
    function getCameraDirection(camera) {
        if (!camera) return null;
        const direction = new THREE.Vector3(0, 0, -1);
        direction.applyQuaternion(camera.quaternion);
        return direction;
    }

    /**
     * Format direction vector as (x, y, z)
     */
    function formatDirection(dir) {
        if (!dir) return '--';
        return `(${formatNumber(dir.x)}, ${formatNumber(dir.y)}, ${formatNumber(dir.z)})`;
    }

    /**
     * Get Euler angles from quaternion (for orientation display)
     * Returns yaw, pitch, roll in degrees
     */
    function getEulerAngles(quaternion) {
        if (!quaternion) return null;
        const euler = new THREE.Euler();
        euler.setFromQuaternion(quaternion, 'YXZ');
        return {
            yaw: THREE.MathUtils.radToDeg(euler.y),
            pitch: THREE.MathUtils.radToDeg(euler.x),
            roll: THREE.MathUtils.radToDeg(euler.z)
        };
    }

    /**
     * Format orientation as yaw/pitch/roll in degrees
     */
    function formatOrientation(quaternion) {
        if (!quaternion) return '--';
        const angles = getEulerAngles(quaternion);
        if (!angles) return '--';
        return `Y:${formatNumber(angles.yaw)}° P:${formatNumber(angles.pitch)}° R:${formatNumber(angles.roll)}°`;
    }

    /**
     * Update the display with current camera and map values
     */
    function update() {
        if (!initialized || !cameraPosEl || !cameraDirEl || !mapPosEl || !mapOrientEl) {
            return;
        }

        // Update camera position
        if (window.camera && window.camera.position) {
            cameraPosEl.textContent = formatPosition(window.camera.position);
        } else {
            cameraPosEl.textContent = '--';
        }

        // Update camera direction
        if (window.camera) {
            const direction = getCameraDirection(window.camera);
            cameraDirEl.textContent = formatDirection(direction);
        } else {
            cameraDirEl.textContent = '--';
        }

        // Update map position
        if (window.terrainGroup && window.terrainGroup.position) {
            mapPosEl.textContent = formatPosition(window.terrainGroup.position);
        } else {
            mapPosEl.textContent = '--';
        }

        // Update map orientation
        if (window.terrainGroup && window.terrainGroup.quaternion) {
            mapOrientEl.textContent = formatOrientation(window.terrainGroup.quaternion);
        } else {
            mapOrientEl.textContent = '--';
        }
    }

    /**
     * Initialize the module
     */
    function init() {
        if (initialized) {
            console.warn('[CameraMapInfo] init() called multiple times - skipping');
            return;
        }

        // Cache DOM element references
        cameraPosEl = document.getElementById('camera-position');
        cameraDirEl = document.getElementById('camera-direction');
        mapPosEl = document.getElementById('map-position');
        mapOrientEl = document.getElementById('map-orientation');

        if (!cameraPosEl || !cameraDirEl || !mapPosEl || !mapOrientEl) {
            console.warn('[CameraMapInfo] Required DOM elements not found');
            return;
        }

        initialized = true;
        console.log('[CameraMapInfo] Initialized');
    }

    // Expose public API
    window.CameraMapInfo = {
        init: init,
        update: update
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

