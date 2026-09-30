//-------ALTITUDE MAPS FLYOVER-------
// Boots the map, wires panel controls, tracks, profile, playback, flight, and HUD. See PRODUCT.md.

import * as maplibregl from 'https://unpkg.com/maplibre-gl@6.11.2/dist/maplibre-gl.mjs';
import { BASEMAPS, GRADE_BANDS, buildStyle, reliefColorExpression, setBasemap } from './style.js';
import { createSlider, createStepSlider } from './slider.js';
import { FlightController, isTypingTarget } from './flight.js';
import { Playback, SPEED_MULTIPLIERS, CAMERA_HEIGHTS_M } from './playback.js';
import { ProfileChart } from './profile.js';
import { TrackPanel } from './tracks.js';
import { PlaceSearch } from './search.js';
import { formatCompact, formatDistance, formatDuration, formatElevation, formatGrade } from './format.js';

//-------CONSTANTS-------
const PREFS_KEY = 'altitude-maps-fly-prefs';
const DEFAULT_PREFS = { exaggeration: 3, basemap: 'relief', hillshade: true, slope: false, autoRelief: true };
const DEFAULT_VIEW = { center: [-119.6, 37.3], zoom: 6, pitch: 45, bearing: 0 };
const RELIEF_SAMPLE_GRID = 14;
const RELIEF_LOW_PERCENTILE = 0.02;
const RELIEF_HIGH_PERCENTILE = 0.98;
const MIN_RELIEF_SPAN_M = 30;

const $ = (id) => document.getElementById(id);

//-------PREFERENCES-------
function loadPrefs() {
    const stored = JSON.parse(localStorage.getItem(PREFS_KEY) || '{}');
    return { ...DEFAULT_PREFS, ...stored };
}
const prefs = loadPrefs();
function savePrefs() { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); }

function setStatus(message) {
    $('status').textContent = message;
    $('status').hidden = !message;
}

//-------BOOT-------
const config = await (await fetch('/api/config')).json();
const hasHashView = window.location.hash.length > 1;
const map = new maplibregl.Map({
    container: 'map',
    style: buildStyle(config, prefs),
    hash: true,
    maxPitch: 85,
    maxZoom: 19,
    attributionControl: { compact: true },
    canvasContextAttributes: { antialias: true },
    ...(hasHashView ? {} : DEFAULT_VIEW),
});
map.addControl(new maplibregl.NavigationControl({ visualizePitch: true, showZoom: true }), 'top-right');
map.addControl(new maplibregl.ScaleControl({ unit: 'metric', maxWidth: 160 }), 'bottom-right');
window.flyMap = map;
await new Promise((resolve) => map.on('load', resolve));

//-------TERRAIN CONTROLS-------
createSlider({
    container: $('exaggeration-slot'), label: 'Vertical exaggeration', min: 1, max: 10, step: 0.1, value: prefs.exaggeration,
    ticks: Array.from({ length: 10 }, (_, i) => ({ value: i + 1, label: `${i + 1}` })),
    format: (v) => `${v.toFixed(1)}x`,
    onInput: (v) => {
        prefs.exaggeration = v;
        savePrefs();
        map.setTerrain({ source: 'terrain-dem', exaggeration: v });
        if (playback.profile && !playback.playing) playback.seek(playback.distance);
    },
});

const basemapSelect = $('basemap');
basemapSelect.replaceChildren(...BASEMAPS.map((b) => new Option(b.label, b.id, false, b.id === prefs.basemap)));
basemapSelect.addEventListener('change', () => {
    prefs.basemap = basemapSelect.value;
    savePrefs();
    setBasemap(map, prefs.basemap);
    $('relief-fit-row').hidden = prefs.basemap !== 'relief';
    fitReliefColors();
});
$('relief-fit-row').hidden = prefs.basemap !== 'relief';

function bindToggle(id, key, apply) {
    const box = $(id);
    box.checked = prefs[key];
    box.addEventListener('change', () => {
        prefs[key] = box.checked;
        savePrefs();
        apply(box.checked);
    });
}
bindToggle('toggle-hillshade', 'hillshade', (on) => map.setLayoutProperty('hillshade', 'visibility', on ? 'visible' : 'none'));
bindToggle('toggle-slope', 'slope', (on) => {
    map.setLayoutProperty('slope', 'visibility', on ? 'visible' : 'none');
    $('slope-legend').hidden = !on;
});
bindToggle('toggle-relief-fit', 'autoRelief', () => fitReliefColors());
$('slope-legend').hidden = !prefs.slope;
$('slope-legend').replaceChildren(...GRADE_BANDS.map((band) => {
    const chip = document.createElement('span');
    chip.className = 'legend-chip';
    chip.style.setProperty('--chip-color', band.color);
    chip.textContent = band.label;
    return chip;
}));

//-------RELIEF AUTO-FIT-------
// Stretch the elevation colors over what is on screen so local relief uses the whole palette.
function fitReliefColors() {
    if (prefs.basemap !== 'relief') return;
    if (!prefs.autoRelief) {
        map.setPaintProperty('relief', 'color-relief-color', reliefColorExpression(0, 3000));
        return;
    }
    const canvas = map.getCanvas();
    const exaggeration = map.getTerrain()?.exaggeration ?? 1;
    const values = [];
    for (let i = 0; i < RELIEF_SAMPLE_GRID; i++) {
        for (let j = 0; j < RELIEF_SAMPLE_GRID; j++) {
            const point = [(i + 0.5) / RELIEF_SAMPLE_GRID * canvas.clientWidth, (j + 0.5) / RELIEF_SAMPLE_GRID * canvas.clientHeight];
            const elevation = map.queryTerrainElevation(map.unproject(point));
            if (elevation != null && isFinite(elevation)) values.push(elevation / exaggeration);
        }
    }
    if (values.length < 10) return;
    values.sort((a, b) => a - b);
    let low = values[Math.floor(values.length * RELIEF_LOW_PERCENTILE)];
    let high = values[Math.floor(values.length * RELIEF_HIGH_PERCENTILE)];
    if (high - low < MIN_RELIEF_SPAN_M) {
        const mid = (high + low) / 2;
        low = mid - MIN_RELIEF_SPAN_M / 2;
        high = mid + MIN_RELIEF_SPAN_M / 2;
    }
    map.setPaintProperty('relief', 'color-relief-color', reliefColorExpression(low, high));
}
map.on('moveend', fitReliefColors);
map.once('idle', fitReliefColors);

//-------HUD-------
const hud = { cursor: $('hud-cursor'), height: $('hud-height'), scale: $('hud-scale'), mode: $('hud-mode') };
let hudFrame = false;
function updateHud() {
    hudFrame = false;
    const center = map.getCenter();
    const metersPerPixel = 40075016.686 * Math.cos(center.lat * Math.PI / 180) / (512 * 2 ** map.getZoom());
    hud.scale.textContent = metersPerPixel < 10 ? `${metersPerPixel.toFixed(1)} m/px` : `${Math.round(metersPerPixel)} m/px`;
    hud.height.textContent = formatDistance(Math.max(flight.heightAboveGround(), 0));
}
map.on('move', () => {
    if (!hudFrame) {
        hudFrame = true;
        requestAnimationFrame(updateHud);
    }
});
map.on('mousemove', (event) => {
    const elevation = map.queryTerrainElevation(event.lngLat);
    const exaggeration = map.getTerrain()?.exaggeration ?? 1;
    hud.cursor.textContent = elevation == null ? '-' : formatElevation(elevation / exaggeration);
});

//-------FLIGHT-------
const flight = new FlightController(map, {
    onModeChange: (mode) => {
        $('mode-orbit').classList.toggle('active', mode === 'orbit');
        $('mode-fly').classList.toggle('active', mode === 'fly');
        hud.mode.textContent = mode === 'fly' ? `Fly ${flight.speedFactor.toFixed(1)}x` : 'Orbit';
    },
    onUserMove: () => playback.stop(),
});
$('mode-orbit').addEventListener('click', () => flight.setMode('orbit'));
$('mode-fly').addEventListener('click', () => flight.setMode('fly'));

//-------PROFILE AND PLAYBACK-------
const profileEls = {
    panel: $('profile'), name: $('profile-name'), play: $('play'),
    posDistance: $('pos-distance'), posElevation: $('pos-elevation'), posGrade: $('pos-grade'),
};
const chart = new ProfileChart($('profile-canvas'), {
    onSeek: (distance) => { playback.stop(); playback.seek(distance); },
    onHover: (distance) => {
        const source = map.getSource('track-hover');
        if (distance == null || !playback.profile) {
            source.setData({ type: 'FeatureCollection', features: [] });
            return;
        }
        const s = playback.sample(distance);
        source.setData({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [s.lng, s.lat] } });
    },
});
const playback = new Playback(map, {
    onPosition: (distance, sample) => {
        chart.setPlayhead(distance);
        profileEls.posDistance.textContent = formatDistance(distance);
        profileEls.posElevation.textContent = formatElevation(sample.ele);
        profileEls.posGrade.textContent = formatGrade(sample.grade);
        map.getSource('playhead').setData({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [sample.lng, sample.lat] } });
    },
    onStateChange: (playing) => {
        profileEls.play.textContent = playing ? 'Pause' : 'Fly along';
        profileEls.play.classList.toggle('active', playing);
    },
});
profileEls.play.addEventListener('click', () => {
    if (!playback.playing) flight.setMode('orbit');
    playback.toggle();
});
createStepSlider({
    container: $('speed-slot'), label: 'Speed', values: SPEED_MULTIPLIERS, index: SPEED_MULTIPLIERS.indexOf(playback.speedMultiplier),
    format: (v) => `${v}x`, tickFormat: (v) => `${v}`,
    onInput: (v) => { playback.speedMultiplier = v; },
});
createStepSlider({
    container: $('height-slot'), label: 'Camera height', values: CAMERA_HEIGHTS_M, index: CAMERA_HEIGHTS_M.indexOf(playback.cameraHeight),
    format: (v) => `${v} m`, tickFormat: (v) => formatCompact(v),
    onInput: (v) => {
        playback.cameraHeight = v;
        if (!playback.playing) playback.seek(playback.distance);
    },
});
$('profile-close').addEventListener('click', () => {
    playback.clear();
    tracks.clearSelection();
    map.getSource('playhead').setData({ type: 'FeatureCollection', features: [] });
    profileEls.panel.hidden = true;
    map.resize();
});

function showTrack(detail) {
    const s = detail.profile.stats;
    profileEls.name.textContent = detail.summary.name;
    $('stat-distance').textContent = formatDistance(s.distance_m);
    $('stat-gain').textContent = `+${Math.round(s.gain_m)} m`;
    $('stat-loss').textContent = `-${Math.round(s.loss_m)} m`;
    $('stat-high').textContent = formatElevation(s.max_ele_m);
    $('stat-low').textContent = formatElevation(s.min_ele_m);
    $('stat-grade').textContent = `${Math.round(s.max_grade_pct)}%`;
    $('stat-duration').textContent = formatDuration(s.duration_s);
    profileEls.panel.hidden = false;
    map.resize();
    chart.setProfile(detail.profile);
    playback.setTrack(detail);
}

//-------TRACKS AND SEARCH-------
const tracks = new TrackPanel(map, {
    list: $('track-list'), count: $('track-count'), filter: $('track-filter'), kind: $('track-kind'),
    showAll: $('tracks-show-all'), rescan: $('tracks-rescan'), importInput: $('track-import'), dropOverlay: $('drop-overlay'),
}, { onSelect: showTrack, onStatus: setStatus });
new PlaceSearch(map, { form: $('search-form'), input: $('search-input'), results: $('search-results') }, { onStatus: setStatus });

//-------GLOBAL KEYS-------
window.addEventListener('keydown', (event) => {
    if (isTypingTarget(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.code === 'Space' && playback.profile) {
        event.preventDefault();
        if (!playback.playing) flight.setMode('orbit');
        playback.toggle();
    } else if (event.code === 'KeyF') {
        flight.setMode(flight.mode === 'fly' ? 'orbit' : 'fly');
    } else if (event.code === 'KeyR') {
        const selected = tracks.tracks.find((t) => t.id === tracks.selectedId);
        const bbox = selected ? selected.bbox : tracks.bounds(tracks.tracks);
        if (bbox) tracks.fitTo(bbox);
    }
});
map.on('dragstart', () => playback.stop());
map.on('wheel', () => playback.stop());

//-------INITIAL VIEW-------
const loaded = await tracks.load();
if (!hasHashView && loaded.length) tracks.fitTo(tracks.bounds(loaded), 45);
flight.onModeChange('orbit');
updateHud();
