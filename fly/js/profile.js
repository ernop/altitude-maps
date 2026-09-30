//-------ELEVATION PROFILE-------
// Distance vs DEM elevation, filled by walking-grade band. Click or drag to seek; hover to preview on the map.

import { GRADE_BANDS, gradeBandIndex } from './style.js';
import { formatDistance, formatElevation } from './format.js';

const PAD = { left: 64, right: 16, top: 12, bottom: 28 };
const NICE_STEPS = [1, 2, 2.5, 5, 10];
const AXIS_FONT = '600 13px system-ui, sans-serif';

function niceStep(range, targetCount) {
    const raw = range / Math.max(targetCount, 1);
    const magnitude = 10 ** Math.floor(Math.log10(raw));
    return NICE_STEPS.map((s) => s * magnitude).find((s) => s >= raw) || 10 * magnitude;
}

export class ProfileChart {
    constructor(canvas, { onSeek, onHover }) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.onSeek = onSeek;
        this.onHover = onHover;
        this.profile = null;
        this.playhead = 0;
        this.hover = null;
        new ResizeObserver(() => this.draw()).observe(canvas);
        this.bindPointer();
    }

    setProfile(profile) {
        this.profile = profile;
        this.playhead = 0;
        this.hover = null;
        const low = profile.stats.min_ele_m;
        const high = profile.stats.max_ele_m;
        const margin = Math.max((high - low) * 0.08, 5);
        this.yMin = low - margin;
        this.yMax = high + margin;
        this.draw();
    }

    setPlayhead(distance) {
        this.playhead = distance;
        this.draw();
    }

    //-------GEOMETRY-------
    plotWidth() { return this.canvas.clientWidth - PAD.left - PAD.right; }
    plotHeight() { return this.canvas.clientHeight - PAD.top - PAD.bottom; }
    xFor(distance) { return PAD.left + (distance / this.profile.stats.distance_m) * this.plotWidth(); }
    yFor(elevation) { return PAD.top + (1 - (elevation - this.yMin) / (this.yMax - this.yMin)) * this.plotHeight(); }
    distanceAt(clientX) {
        const x = clientX - this.canvas.getBoundingClientRect().left;
        return Math.min(Math.max((x - PAD.left) / this.plotWidth(), 0), 1) * this.profile.stats.distance_m;
    }

    //-------DRAWING-------
    draw() {
        const { canvas, ctx } = this;
        const dpr = window.devicePixelRatio || 1;
        const width = canvas.clientWidth;
        const height = canvas.clientHeight;
        if (width === 0 || height === 0) return;
        if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
            canvas.width = Math.round(width * dpr);
            canvas.height = Math.round(height * dpr);
        }
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, width, height);
        if (!this.profile) return;
        const p = this.profile;
        const plotW = this.plotWidth();
        const bottom = PAD.top + this.plotHeight();

        // Grade fill: one column per pixel, colored by the steepest sample in that column.
        let sample = 0;
        for (let px = 0; px < plotW; px++) {
            const dEnd = ((px + 1) / plotW) * p.stats.distance_m;
            let steepest = 0;
            let elevation = p.ele[sample];
            while (sample < p.dist.length - 1 && p.dist[sample] <= dEnd) {
                steepest = Math.max(steepest, Math.abs(p.grade[sample]));
                elevation = Math.max(elevation, p.ele[sample]);
                sample++;
            }
            ctx.fillStyle = GRADE_BANDS[gradeBandIndex(steepest)].color;
            const top = this.yFor(elevation);
            ctx.fillRect(PAD.left + px, top, 1.2, bottom - top);
        }

        ctx.strokeStyle = 'rgba(255,255,255,0.35)';
        ctx.lineWidth = 1;
        ctx.fillStyle = '#ffffff';
        ctx.font = AXIS_FONT;
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        const yStep = niceStep(this.yMax - this.yMin, Math.max(2, Math.floor(this.plotHeight() / 36)));
        for (let v = Math.ceil(this.yMin / yStep) * yStep; v <= this.yMax; v += yStep) {
            const y = this.yFor(v);
            ctx.beginPath();
            ctx.moveTo(PAD.left, y);
            ctx.lineTo(PAD.left + plotW, y);
            ctx.stroke();
            ctx.fillText(formatElevation(v), PAD.left - 8, y);
        }
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        const xStep = niceStep(p.stats.distance_m, Math.max(2, Math.floor(plotW / 90)));
        for (let d = 0; d <= p.stats.distance_m; d += xStep) {
            ctx.fillText(formatDistance(d), this.xFor(d), bottom + 6);
        }

        ctx.beginPath();
        p.dist.forEach((d, i) => {
            const x = this.xFor(d);
            const y = this.yFor(p.ele[i]);
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = '#000000';
        ctx.lineWidth = 4;
        ctx.stroke();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();

        this.drawMarker(this.hover, 'rgba(255,255,255,0.8)', 1);
        this.drawMarker(this.playhead, '#ffd400', 3);
    }

    drawMarker(distance, color, width) {
        if (distance == null) return;
        const { ctx } = this;
        const x = this.xFor(distance);
        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.beginPath();
        ctx.moveTo(x, PAD.top);
        ctx.lineTo(x, PAD.top + this.plotHeight());
        ctx.stroke();
    }

    //-------INTERACTION-------
    bindPointer() {
        let dragging = false;
        this.canvas.addEventListener('pointerdown', (event) => {
            if (!this.profile) return;
            dragging = true;
            this.canvas.setPointerCapture(event.pointerId);
            this.onSeek(this.distanceAt(event.clientX));
        });
        this.canvas.addEventListener('pointermove', (event) => {
            if (!this.profile) return;
            const distance = this.distanceAt(event.clientX);
            if (dragging) this.onSeek(distance);
            this.hover = distance;
            this.onHover(distance);
            this.draw();
        });
        const end = () => { dragging = false; };
        this.canvas.addEventListener('pointerup', end);
        this.canvas.addEventListener('pointercancel', end);
        this.canvas.addEventListener('pointerleave', () => {
            this.hover = null;
            this.onHover(null);
            this.draw();
        });
    }
}
