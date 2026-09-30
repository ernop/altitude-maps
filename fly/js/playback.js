//-------FLY-ALONG PLAYBACK-------
// Chase camera behind the playhead, looking ahead along the track. Travel pace is the track's average speed
// (4.5 km/h without timestamps) multiplied by the chosen speed, so stops in the recording do not stall the flight.

export const SPEED_MULTIPLIERS = [1, 2, 5, 10, 25, 50, 100, 200, 500];
export const CAMERA_HEIGHTS_M = [10, 25, 50, 100, 200, 400, 800];
const DEFAULT_WALK_SPEED_MPS = 4.5 / 3.6;
const HEADING_SMOOTHING_S = 1.2;
const CAMERA_CLEARANCE_M = 8;

export class Playback {
    constructor(map, { onPosition, onStateChange }) {
        this.map = map;
        this.onPosition = onPosition;
        this.onStateChange = onStateChange;
        this.profile = null;
        this.distance = 0;
        this.playing = false;
        this.speedMultiplier = 100;
        this.cameraHeight = 100;
        this.heading = null;
        this.lastFrame = null;
    }

    setTrack(detail) {
        this.stop();
        this.profile = detail.profile;
        const stats = detail.profile.stats;
        this.baseSpeed = stats.duration_s > 60 ? stats.distance_m / stats.duration_s : DEFAULT_WALK_SPEED_MPS;
        this.distance = 0;
        this.heading = null;
        this.onPosition(this.distance, this.sample(this.distance));
    }

    clear() {
        this.stop();
        this.profile = null;
    }

    //-------SAMPLING-------
    index(distance) {
        const dist = this.profile.dist;
        let lo = 0;
        let hi = dist.length - 1;
        while (hi - lo > 1) {
            const mid = (lo + hi) >> 1;
            if (dist[mid] <= distance) lo = mid; else hi = mid;
        }
        return lo;
    }

    sample(distance) {
        const p = this.profile;
        const last = p.dist.length - 1;
        const d = Math.min(Math.max(distance, 0), p.dist[last]);
        const i = Math.min(this.index(d), Math.max(last - 1, 0));
        const span = p.dist[i + 1] - p.dist[i];
        const f = span > 0 ? (d - p.dist[i]) / span : 0;
        const lerp = (a) => a[i] + (a[i + 1] - a[i]) * f;
        return { lng: lerp(p.lon), lat: lerp(p.lat), ele: lerp(p.ele), grade: p.grade[i], distance: d };
    }

    //-------CONTROL-------
    toggle() {
        if (this.playing) this.stop(); else this.play();
    }

    play() {
        if (!this.profile) return;
        if (this.distance >= this.profile.stats.distance_m) this.distance = 0;
        this.playing = true;
        this.lastFrame = null;
        this.onStateChange(true);
        requestAnimationFrame((t) => this.frame(t));
    }

    stop() {
        if (!this.playing) return;
        this.playing = false;
        this.onStateChange(false);
    }

    seek(distance) {
        if (!this.profile) return;
        this.distance = Math.min(Math.max(distance, 0), this.profile.stats.distance_m);
        this.heading = null;
        this.placeCamera(0);
    }

    frame(time) {
        if (!this.playing) return;
        const dt = this.lastFrame == null ? 0 : Math.min((time - this.lastFrame) / 1000, 0.1);
        this.lastFrame = time;
        this.distance += this.baseSpeed * this.speedMultiplier * dt;
        if (this.distance >= this.profile.stats.distance_m) {
            this.distance = this.profile.stats.distance_m;
            this.placeCamera(dt);
            this.stop();
            return;
        }
        this.placeCamera(dt);
        requestAnimationFrame((t) => this.frame(t));
    }

    //-------CAMERA-------
    placeCamera(dt) {
        const exaggeration = this.map.getTerrain()?.exaggeration ?? 1;
        const here = this.sample(this.distance);
        const lookAhead = Math.max(60, this.cameraHeight * 1.5);
        const behind = Math.max(80, this.cameraHeight * 2);
        const ahead = this.sample(this.distance + lookAhead);
        const back = this.sample(this.distance - lookAhead * 0.5);
        const kx = 111320 * Math.cos(here.lat * Math.PI / 180);
        let hx = (ahead.lng - back.lng) * kx;
        let hy = (ahead.lat - back.lat) * 111320;
        const length = Math.hypot(hx, hy) || 1;
        hx /= length;
        hy /= length;
        if (this.heading == null || dt === 0) {
            this.heading = { x: hx, y: hy };
        } else {
            const blend = 1 - Math.exp(-dt / HEADING_SMOOTHING_S);
            this.heading.x += (hx - this.heading.x) * blend;
            this.heading.y += (hy - this.heading.y) * blend;
            const norm = Math.hypot(this.heading.x, this.heading.y) || 1;
            this.heading.x /= norm;
            this.heading.y /= norm;
        }
        const camLng = here.lng - (this.heading.x * behind) / kx;
        const camLat = here.lat - (this.heading.y * behind) / 111320;
        const groundUnderCamera = this.map.queryTerrainElevation([camLng, camLat]) ?? here.ele * exaggeration;
        const camAlt = Math.max(here.ele * exaggeration + this.cameraHeight, groundUnderCamera + CAMERA_CLEARANCE_M);
        const targetLng = here.lng + (this.heading.x * lookAhead * 0.35) / kx;
        const targetLat = here.lat + (this.heading.y * lookAhead * 0.35) / 111320;
        const target = this.sample(this.distance + lookAhead * 0.35);
        const options = this.map.calculateCameraOptionsFromTo([camLng, camLat], camAlt, [targetLng, targetLat], target.ele * exaggeration);
        this.map.jumpTo(options);
        this.onPosition(this.distance, here);
    }
}
