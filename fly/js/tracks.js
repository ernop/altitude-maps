//-------TRACKS-------
// Track list, overview layer, selection with grade-colored geometry, and file import (picker or drag-and-drop).

import { gradeBandIndex } from './style.js';
import { formatDate, formatDistance } from './format.js';

const FIT_PADDING_FRACTION = 0.12;
const SELECT_PITCH = 60;

async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `${response.status} ${url}`);
    return payload;
}

// Consecutive profile samples in the same grade band become one line feature.
function gradeFeatures(profile) {
    const features = [];
    let run = null;
    for (let i = 0; i < profile.dist.length; i++) {
        const band = gradeBandIndex(Math.abs(profile.grade[i]));
        const point = [profile.lon[i], profile.lat[i]];
        if (!run || run.band !== band) {
            if (run) {
                run.coords.push(point);
                features.push({ type: 'Feature', properties: { g: run.maxGrade }, geometry: { type: 'LineString', coordinates: run.coords } });
            }
            run = { band, coords: [point], maxGrade: 0 };
        } else {
            run.coords.push(point);
        }
        run.maxGrade = Math.max(run.maxGrade, Math.abs(profile.grade[i]));
    }
    if (run && run.coords.length > 1) {
        features.push({ type: 'Feature', properties: { g: run.maxGrade }, geometry: { type: 'LineString', coordinates: run.coords } });
    }
    return { type: 'FeatureCollection', features };
}

export class TrackPanel {
    constructor(map, elements, { onSelect, onStatus }) {
        this.map = map;
        this.el = elements;
        this.onSelect = onSelect;
        this.onStatus = onStatus;
        this.tracks = [];
        this.selectedId = null;
        this.kindFilter = 'all';
        this.bindUi();
        this.bindMap();
    }

    async load() {
        const [list, overview] = await Promise.all([fetchJson('/api/tracks'), fetchJson('/api/tracks/overview.geojson')]);
        this.tracks = list.tracks;
        this.map.getSource('tracks-overview').setData(overview);
        this.renderList();
        if (list.errors.length) {
            this.onStatus(`${list.errors.length} track files or folders could not be read; see the server log.`);
        }
        return this.tracks;
    }

    bounds(tracks) {
        if (!tracks.length) return null;
        return tracks.reduce((b, t) => [Math.min(b[0], t.bbox[0]), Math.min(b[1], t.bbox[1]), Math.max(b[2], t.bbox[2]), Math.max(b[3], t.bbox[3])],
            [Infinity, Infinity, -Infinity, -Infinity]);
    }

    fitTo(bbox, pitch = SELECT_PITCH) {
        const canvas = this.map.getCanvas();
        const padding = Math.round(Math.min(canvas.clientWidth, canvas.clientHeight) * FIT_PADDING_FRACTION);
        this.map.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], { padding, pitch, duration: 2000, maxZoom: 16 });
    }

    //-------LIST-------
    visibleTracks() {
        const needle = this.el.filter.value.trim().toLowerCase();
        return this.tracks.filter((t) => (this.kindFilter === 'all' || t.kind === this.kindFilter)
            && (!needle || t.name.toLowerCase().includes(needle) || t.file.toLowerCase().includes(needle)));
    }

    renderList() {
        const visible = this.visibleTracks();
        this.el.count.textContent = `${visible.length} of ${this.tracks.length}`;
        this.el.list.replaceChildren(...visible.map((track) => {
            const row = document.createElement('li');
            row.className = 'track-row';
            row.classList.toggle('selected', track.id === this.selectedId);
            row.dataset.id = track.id;
            row.title = `${track.name}\n${track.file}`;
            row.innerHTML = `<span class="swatch"></span><span class="track-name"></span><span class="track-date"></span><span class="track-distance"></span>`;
            row.querySelector('.swatch').classList.add(`swatch-${track.kind}`);
            row.querySelector('.track-name').textContent = track.name;
            row.querySelector('.track-date').textContent = formatDate(track.start_time);
            row.querySelector('.track-distance').textContent = formatDistance(track.distance_m);
            return row;
        }));
    }

    //-------SELECTION-------
    async select(trackId) {
        this.selectedId = trackId;
        this.renderList();
        this.onStatus('Loading track profile (first time samples the terrain along the track)...');
        const detail = await fetchJson(`/api/tracks/${trackId}`);
        if (this.selectedId !== trackId) return;
        this.map.getSource('track-selected').setData(gradeFeatures(detail.profile));
        this.fitTo(detail.summary.bbox);
        this.onStatus('');
        this.onSelect(detail);
    }

    clearSelection() {
        this.selectedId = null;
        this.map.getSource('track-selected').setData({ type: 'FeatureCollection', features: [] });
        this.renderList();
    }

    //-------IMPORT-------
    async importFiles(files) {
        let lastSummary = null;
        for (const file of files) {
            this.onStatus(`Importing ${file.name}...`);
            try {
                lastSummary = await fetchJson(`/api/tracks/import?name=${encodeURIComponent(file.name)}`, { method: 'POST', body: file });
            } catch (error) {
                this.onStatus(`Import failed for ${file.name}: ${error.message}`);
                return;
            }
        }
        await this.load();
        this.onStatus('');
        if (lastSummary) await this.select(lastSummary.id);
    }

    //-------BINDINGS-------
    bindUi() {
        this.el.list.addEventListener('click', (event) => {
            const row = event.target.closest('.track-row');
            if (row) this.select(row.dataset.id);
        });
        this.el.filter.addEventListener('input', () => this.renderList());
        this.el.kind.addEventListener('change', () => {
            this.kindFilter = this.el.kind.value;
            this.renderList();
        });
        this.el.showAll.addEventListener('click', () => {
            const bbox = this.bounds(this.visibleTracks());
            if (bbox) this.fitTo(bbox, 45);
        });
        this.el.rescan.addEventListener('click', async () => {
            this.onStatus('Rescanning track folders...');
            await fetchJson('/api/tracks/rescan', { method: 'POST' });
            await this.load();
            this.onStatus('');
        });
        this.el.importInput.addEventListener('change', () => {
            this.importFiles([...this.el.importInput.files]);
            this.el.importInput.value = '';
        });
        let dragDepth = 0;
        window.addEventListener('dragenter', (event) => {
            if (!event.dataTransfer?.types.includes('Files')) return;
            dragDepth++;
            this.el.dropOverlay.hidden = false;
        });
        window.addEventListener('dragleave', () => {
            dragDepth = Math.max(dragDepth - 1, 0);
            if (dragDepth === 0) this.el.dropOverlay.hidden = true;
        });
        window.addEventListener('dragover', (event) => event.preventDefault());
        window.addEventListener('drop', (event) => {
            event.preventDefault();
            dragDepth = 0;
            this.el.dropOverlay.hidden = true;
            if (event.dataTransfer?.files.length) this.importFiles([...event.dataTransfer.files]);
        });
    }

    bindMap() {
        this.map.on('click', 'tracks-overview', (event) => {
            const feature = event.features?.[0];
            if (feature) this.select(feature.properties.id);
        });
        this.map.on('mouseenter', 'tracks-overview', () => { this.map.getCanvas().classList.add('pointer-cursor'); });
        this.map.on('mouseleave', 'tracks-overview', () => { this.map.getCanvas().classList.remove('pointer-cursor'); });
    }
}