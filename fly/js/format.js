//-------FORMATTING-------

export function formatDistance(meters) {
    if (meters == null || !isFinite(meters)) return '-';
    return meters >= 1000 ? `${(meters / 1000).toFixed(meters >= 100000 ? 0 : 2)} km` : `${Math.round(meters)} m`;
}

export function formatElevation(meters) {
    if (meters == null || !isFinite(meters)) return '-';
    return `${Math.round(meters).toLocaleString('en-US')} m`;
}

export function formatDuration(seconds) {
    if (seconds == null || !isFinite(seconds)) return '-';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return h > 0 ? `${h}h ${String(m).padStart(2, '0')}m` : `${m}m`;
}

export function formatDate(epochSeconds) {
    if (!epochSeconds) return '';
    return new Date(epochSeconds * 1000).toISOString().slice(0, 10);
}

export function formatGrade(percent) {
    if (percent == null || !isFinite(percent)) return '-';
    return `${percent > 0 ? '+' : ''}${percent.toFixed(0)}%`;
}

export function formatCompact(value) {
    return value >= 1000 ? `${value / 1000}k` : String(value);
}
