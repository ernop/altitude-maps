//-------FLIGHT CONTROLLER-------
// Keyboard flight works in both modes. Orbit: MapLibre mouse handlers. Fly: drag to look around in place.
// Camera changes go through calculateCameraOptionsFromCameraLngLatAltRotation so the camera position is the source of truth.

const EARTH_CIRCUMFERENCE_M = 2 * Math.PI * 6371008.8;
const METERS_PER_DEGREE = EARTH_CIRCUMFERENCE_M / 360;
const WORLD_TILE_SIZE = 512;
const ORBIT_MAX_PITCH = 85;
const FLY_MAX_PITCH = 130;
const TURN_DEG_PER_S = 70;
const LOOK_DEG_PER_PX = 0.18;
const MIN_CLEARANCE_M = 4;
const BOOST = 5;
const SPEED_FACTOR_MIN = 0.1;
const SPEED_FACTOR_MAX = 20;
const WHEEL_SPEED_STEP = 1.2;
const WHEEL_NOTCH_PX = 100;
const WHEEL_LINE_PX = 33;
const MOVE_KEYS = new Set(['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyQ', 'KeyE', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight']);

export function isTypingTarget(target) {
    return target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));
}

export class FlightController {
    constructor(map, { onModeChange, onUserMove }) {
        this.map = map;
        this.mode = 'orbit';
        this.pressed = new Set();
        this.speedFactor = 1;
        this.boost = false;
        this.lastFrame = null;
        this.frameRequested = false;
        this.drag = null;
        this.onModeChange = onModeChange;
        this.onUserMove = onUserMove;
        map.keyboard.disable();
        this.bindKeys();
        this.bindMouse();
    }

    //-------MODE-------
    setMode(mode) {
        if (mode === this.mode) return;
        this.mode = mode;
        const handlers = ['dragPan', 'dragRotate', 'scrollZoom', 'touchZoomRotate', 'doubleClickZoom', 'boxZoom'];
        if (mode === 'fly') {
            handlers.forEach((h) => this.map[h].disable());
            this.map.setCenterClampedToGround(false);
            this.map.setMaxPitch(FLY_MAX_PITCH);
        } else {
            handlers.forEach((h) => this.map[h].enable());
            this.map.setCenterClampedToGround(true);
            this.map.setMaxPitch(ORBIT_MAX_PITCH);
        }
        this.map.getCanvas().classList.toggle('fly-cursor', mode === 'fly');
        this.onModeChange(mode);
    }

    //-------CAMERA STATE-------
    // Mirrors MapLibre's internal getCameraAltitude/getCameraLngLat; the transform is not public in the production build.
    cameraState() {
        const map = this.map;
        const center = map.getCenter();
        const pitch = map.getPitch();
        const bearing = map.getBearing();
        const halfFov = (map.getVerticalFieldOfView() * Math.PI / 180) / 2;
        const cameraToCenterPx = 0.5 / Math.tan(halfFov) * map.getCanvas().clientHeight;
        const metersPerPixel = EARTH_CIRCUMFERENCE_M * Math.cos(center.lat * Math.PI / 180) / (WORLD_TILE_SIZE * 2 ** map.getZoom());
        const distance = cameraToCenterPx * metersPerPixel;
        const pitchRad = pitch * Math.PI / 180;
        const bearingRad = bearing * Math.PI / 180;
        const ground = Math.sin(pitchRad) * distance;
        const lat = center.lat - (Math.cos(bearingRad) * ground) / METERS_PER_DEGREE;
        const lng = center.lng - (Math.sin(bearingRad) * ground) / (METERS_PER_DEGREE * Math.cos(center.lat * Math.PI / 180));
        return { lng, lat, alt: map.getCenterElevation() + Math.cos(pitchRad) * distance, bearing, pitch };
    }

    groundAltitude(lng, lat) {
        return this.map.queryTerrainElevation([lng, lat]) ?? 0;
    }

    heightAboveGround() {
        const state = this.cameraState();
        return state.alt - this.groundAltitude(state.lng, state.lat);
    }

    applyCamera(state) {
        const maxPitch = this.mode === 'fly' ? FLY_MAX_PITCH : ORBIT_MAX_PITCH;
        const pitch = Math.min(Math.max(state.pitch, 0), maxPitch);
        const alt = Math.max(state.alt, this.groundAltitude(state.lng, state.lat) + MIN_CLEARANCE_M);
        const options = this.map.calculateCameraOptionsFromCameraLngLatAltRotation([state.lng, state.lat], alt, state.bearing, pitch);
        this.map.jumpTo(options);
    }

    speedMetersPerSecond() {
        const height = Math.max(this.heightAboveGround(), 1);
        return Math.min(Math.max(height * 0.8, 15), 20000) * this.speedFactor * (this.boost ? BOOST : 1);
    }

    //-------KEYBOARD-------
    bindKeys() {
        window.addEventListener('keydown', (event) => {
            if (isTypingTarget(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
            this.boost = event.shiftKey;
            if (MOVE_KEYS.has(event.code)) {
                event.preventDefault();
                this.pressed.add(event.code);
                this.onUserMove();
                this.requestFrame();
            } else if (event.code === 'Escape' && this.mode === 'fly') {
                this.setMode('orbit');
            }
        });
        window.addEventListener('keyup', (event) => {
            this.boost = event.shiftKey;
            this.pressed.delete(event.code);
        });
        window.addEventListener('blur', () => this.pressed.clear());
    }

    requestFrame() {
        if (this.frameRequested) return;
        this.frameRequested = true;
        requestAnimationFrame((time) => this.frame(time));
    }

    frame(time) {
        this.frameRequested = false;
        if (this.pressed.size === 0) {
            this.lastFrame = null;
            return;
        }
        const dt = this.lastFrame == null ? 1 / 60 : Math.min((time - this.lastFrame) / 1000, 0.1);
        this.lastFrame = time;
        const state = this.cameraState();
        const p = this.pressed;
        const turn = (p.has('ArrowRight') ? 1 : 0) - (p.has('ArrowLeft') ? 1 : 0);
        const tilt = (p.has('ArrowUp') ? 1 : 0) - (p.has('ArrowDown') ? 1 : 0);
        const forward = (p.has('KeyW') ? 1 : 0) - (p.has('KeyS') ? 1 : 0);
        const strafe = (p.has('KeyD') ? 1 : 0) - (p.has('KeyA') ? 1 : 0);
        const climb = (p.has('KeyE') ? 1 : 0) - (p.has('KeyQ') ? 1 : 0);
        state.bearing += turn * TURN_DEG_PER_S * dt;
        state.pitch += tilt * TURN_DEG_PER_S * 0.6 * dt;
        const step = this.speedMetersPerSecond() * dt;
        const heading = state.bearing * Math.PI / 180;
        const north = (forward * Math.cos(heading) - strafe * Math.sin(heading)) * step;
        const east = (forward * Math.sin(heading) + strafe * Math.cos(heading)) * step;
        state.lat += north / METERS_PER_DEGREE;
        state.lng += east / (METERS_PER_DEGREE * Math.cos(state.lat * Math.PI / 180));
        state.alt += climb * step;
        this.applyCamera(state);
        this.requestFrame();
    }

    //-------MOUSE (FLY MODE)-------
    bindMouse() {
        const canvas = this.map.getCanvasContainer();
        canvas.addEventListener('pointerdown', (event) => {
            if (this.mode !== 'fly' || event.button !== 0) return;
            this.drag = { x: event.clientX, y: event.clientY };
            canvas.setPointerCapture(event.pointerId);
            this.onUserMove();
        });
        canvas.addEventListener('pointermove', (event) => {
            if (!this.drag) return;
            const state = this.cameraState();
            state.bearing += (event.clientX - this.drag.x) * LOOK_DEG_PER_PX;
            state.pitch -= (event.clientY - this.drag.y) * LOOK_DEG_PER_PX;
            this.drag = { x: event.clientX, y: event.clientY };
            this.applyCamera(state);
        });
        const endDrag = () => { this.drag = null; };
        canvas.addEventListener('pointerup', endDrag);
        canvas.addEventListener('pointercancel', endDrag);
        canvas.addEventListener('wheel', (event) => {
            if (this.mode !== 'fly') return;
            event.preventDefault();
            // Trackpads send many small deltas; scale by distance so one mouse notch (~100 px) is one step.
            const pixels = event.deltaY * (event.deltaMode === WheelEvent.DOM_DELTA_LINE ? WHEEL_LINE_PX : 1);
            const factor = Math.pow(WHEEL_SPEED_STEP, -pixels / WHEEL_NOTCH_PX);
            this.speedFactor = Math.min(Math.max(this.speedFactor * factor, SPEED_FACTOR_MIN), SPEED_FACTOR_MAX);
            this.onModeChange(this.mode);
        }, { passive: false });
    }
}
