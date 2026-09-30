//-------MAP STYLE-------
// Sources and layers for terrain, basemaps, overlays, and tracks. See PRODUCT.md for the policies behind them.

export const BASEMAPS = [
    { id: 'relief', label: 'Relief (elevation colors)' },
    {
        id: 'satellite', label: 'Satellite (Esri)', maxzoom: 19,
        tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
        attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics',
    },
    {
        id: 'usgs-imagery', label: 'USGS Imagery (US)', maxzoom: 16,
        tiles: ['https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}'],
        attribution: 'USGS The National Map',
    },
    {
        id: 'usgs-topo', label: 'USGS Topo (US)', maxzoom: 16,
        tiles: ['https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}'],
        attribution: 'USGS The National Map',
    },
    {
        id: 'opentopomap', label: 'OpenTopoMap', maxzoom: 17,
        tiles: ['https://tile.opentopomap.org/{z}/{x}/{y}.png'],
        attribution: '&copy; OpenTopoMap (CC-BY-SA), &copy; OpenStreetMap contributors',
    },
    {
        id: 'osm', label: 'OpenStreetMap', maxzoom: 19,
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        attribution: '&copy; OpenStreetMap contributors',
    },
];

// Walking-grade bands shared by the slope overlay legend, the track coloring, and the profile.
export const GRADE_BANDS = [
    { upTo: 5, color: '#ffffff', label: '<5%' },
    { upTo: 10, color: '#2ecc40', label: '5-10' },
    { upTo: 15, color: '#aadc1e', label: '10-15' },
    { upTo: 20, color: '#ffdc00', label: '15-20' },
    { upTo: 30, color: '#ff851b', label: '20-30' },
    { upTo: 45, color: '#e61414', label: '30-45' },
    { upTo: 70, color: '#dc00c8', label: '45-70' },
    { upTo: 100, color: '#8c3cff', label: '70-100' },
    { upTo: Infinity, color: '#3c0a64', label: '>100%' },
];

export function gradeBandIndex(absGrade) {
    for (let i = 0; i < GRADE_BANDS.length; i++) {
        if (absGrade < GRADE_BANDS[i].upTo) return i;
    }
    return GRADE_BANDS.length - 1;
}

export const TRACK_COLORS = { walked: '#ff3b30', planned: '#00d5ff' };

// Hypsometric palette stretched between the low and high elevations in view.
const RELIEF_PALETTE = [
    [0.00, '#12502f'], [0.14, '#2f7d32'], [0.28, '#7fb342'], [0.42, '#d9d27a'],
    [0.56, '#d1a55a'], [0.70, '#a8703c'], [0.84, '#8a6a58'], [0.93, '#c9bdb4'], [1.00, '#ffffff'],
];

export function reliefColorExpression(low, high) {
    const span = Math.max(high - low, 20);
    const stops = RELIEF_PALETTE.flatMap(([f, color]) => [low + f * span, color]);
    return ['interpolate', ['linear'], ['elevation'], ...stops];
}

const SKY = {
    'sky-color': '#4f86d0',
    'horizon-color': '#d6e4f2',
    'fog-color': '#d6e4f2',
    'sky-horizon-blend': 0.6,
    'horizon-fog-blend': 0.6,
    'fog-ground-blend': 0.85,
    'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 10, 1, 12, 0],
};

const EMPTY = { type: 'FeatureCollection', features: [] };

function lineWidth(base) {
    return ['interpolate', ['exponential', 1.6], ['zoom'], 6, base * 0.5, 12, base, 16, base * 2.2];
}

export function buildStyle(config, { basemap, exaggeration, hillshade, slope }) {
    const demSource = {
        type: 'raster-dem', tiles: config.terrain.tiles, tileSize: config.terrain.tileSize,
        maxzoom: config.terrain.maxzoom, encoding: config.terrain.encoding,
    };
    const sources = {
        // Separate DEM sources for the mesh and the hillshade render better (MapLibre recommendation); HTTP caching makes the second one free.
        'terrain-dem': { ...demSource, attribution: config.terrain.attribution },
        'shade-dem': demSource,
        slope: { type: 'raster', tiles: config.slope.tiles, tileSize: config.slope.tileSize, minzoom: config.slope.minzoom, maxzoom: config.slope.maxzoom },
        'tracks-overview': { type: 'geojson', data: EMPTY },
        'track-selected': { type: 'geojson', data: EMPTY },
        'track-hover': { type: 'geojson', data: EMPTY },
        playhead: { type: 'geojson', data: EMPTY },
    };
    const layers = [{ id: 'background', type: 'background', paint: { 'background-color': '#10202a' } }];

    for (const map of BASEMAPS.filter((b) => b.tiles)) {
        sources[`basemap-${map.id}`] = { type: 'raster', tiles: map.tiles, tileSize: 256, maxzoom: map.maxzoom, attribution: map.attribution };
        layers.push({
            id: `basemap-${map.id}`, type: 'raster', source: `basemap-${map.id}`,
            layout: { visibility: basemap === map.id ? 'visible' : 'none' },
        });
    }
    layers.push(
        {
            id: 'relief', type: 'color-relief', source: 'shade-dem',
            layout: { visibility: basemap === 'relief' ? 'visible' : 'none' },
            paint: { 'color-relief-color': reliefColorExpression(0, 3000) },
        },
        {
            id: 'hillshade', type: 'hillshade', source: 'shade-dem',
            layout: { visibility: hillshade ? 'visible' : 'none' },
            paint: {
                'hillshade-method': 'igor',
                'hillshade-exaggeration': basemap === 'relief' ? 0.55 : 0.3,
                'hillshade-shadow-color': '#1b1408',
                'hillshade-highlight-color': '#ffffff',
            },
        },
        {
            id: 'slope', type: 'raster', source: 'slope',
            layout: { visibility: slope ? 'visible' : 'none' },
            paint: { 'raster-opacity': 0.75, 'raster-resampling': 'nearest' },
        },
        {
            id: 'tracks-overview-casing', type: 'line', source: 'tracks-overview',
            layout: { 'line-join': 'round', 'line-cap': 'round' },
            paint: { 'line-color': '#000000', 'line-width': lineWidth(4.5), 'line-opacity': 0.7 },
        },
        {
            id: 'tracks-overview', type: 'line', source: 'tracks-overview',
            layout: { 'line-join': 'round', 'line-cap': 'round' },
            paint: {
                'line-color': ['match', ['get', 'kind'], 'planned', TRACK_COLORS.planned, TRACK_COLORS.walked],
                'line-width': lineWidth(2.5),
            },
        },
        {
            id: 'track-selected-casing', type: 'line', source: 'track-selected',
            layout: { 'line-join': 'round', 'line-cap': 'round' },
            paint: { 'line-color': '#000000', 'line-width': lineWidth(7) },
        },
        {
            id: 'track-selected', type: 'line', source: 'track-selected',
            layout: { 'line-join': 'round', 'line-cap': 'round' },
            paint: {
                'line-color': ['step', ['get', 'g'], ...GRADE_BANDS.slice(0, -1).flatMap((b, i) => [b.color, b.upTo]), GRADE_BANDS.at(-1).color],
                'line-width': lineWidth(4.5),
            },
        },
        {
            id: 'track-hover', type: 'circle', source: 'track-hover',
            paint: { 'circle-radius': 6, 'circle-color': '#ffffff', 'circle-stroke-color': '#000000', 'circle-stroke-width': 2 },
        },
        {
            id: 'playhead', type: 'circle', source: 'playhead',
            paint: { 'circle-radius': 8, 'circle-color': '#ffd400', 'circle-stroke-color': '#000000', 'circle-stroke-width': 3 },
        },
    );

    return {
        version: 8,
        sources,
        layers,
        terrain: { source: 'terrain-dem', exaggeration },
        sky: SKY,
    };
}

export function setBasemap(map, basemap) {
    for (const b of BASEMAPS.filter((m) => m.tiles)) {
        map.setLayoutProperty(`basemap-${b.id}`, 'visibility', basemap === b.id ? 'visible' : 'none');
    }
    map.setLayoutProperty('relief', 'visibility', basemap === 'relief' ? 'visible' : 'none');
    map.setPaintProperty('hillshade', 'hillshade-exaggeration', basemap === 'relief' ? 0.55 : 0.3);
}
