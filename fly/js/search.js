//-------PLACE SEARCH-------
// Place names through Nominatim (light personal use fits its usage policy), or "lat, lon" coordinates.

const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search';
const COORDINATE_PATTERN = /^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/;
const RESULT_LIMIT = 8;
const PLACE_PITCH = 60;

export class PlaceSearch {
    constructor(map, { form, input, results }, { onStatus }) {
        this.map = map;
        this.input = input;
        this.results = results;
        this.onStatus = onStatus;
        form.addEventListener('submit', (event) => {
            event.preventDefault();
            this.search(input.value);
        });
        results.addEventListener('click', (event) => {
            const row = event.target.closest('.place-row');
            if (row) this.go(JSON.parse(row.dataset.place));
        });
    }

    async search(query) {
        const match = query.match(COORDINATE_PATTERN);
        if (match) {
            const lat = Number(match[1]);
            const lng = Number(match[2]);
            this.results.replaceChildren();
            this.map.flyTo({ center: [lng, lat], zoom: 14, pitch: PLACE_PITCH, duration: 2500 });
            return;
        }
        if (!query.trim()) return;
        this.onStatus('Searching...');
        const url = `${NOMINATIM_URL}?${new URLSearchParams({ q: query, format: 'jsonv2', limit: RESULT_LIMIT })}`;
        const response = await fetch(url, { headers: { 'Accept-Language': 'en' } });
        const places = await response.json();
        this.onStatus(places.length ? '' : `No places found for "${query}"`);
        this.results.replaceChildren(...places.map((place) => {
            const row = document.createElement('li');
            row.className = 'place-row';
            row.dataset.place = JSON.stringify({ bbox: place.boundingbox.map(Number), lat: Number(place.lat), lon: Number(place.lon) });
            row.textContent = place.display_name;
            row.title = place.display_name;
            return row;
        }));
        if (places.length === 1) this.go(JSON.parse(this.results.firstChild.dataset.place));
    }

    go(place) {
        const [south, north, west, east] = place.bbox;
        this.map.fitBounds([[west, south], [east, north]], { pitch: PLACE_PITCH, duration: 2500, maxZoom: 15, padding: 40 });
    }
}
