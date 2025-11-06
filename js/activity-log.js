/**
 * Activity Log Utilities
 * 
 * PURPOSE:
 * Manages the activity log displayed in the UI, which records significant events
 * during data loading and processing. Useful for debugging and understanding
 * what the viewer is doing.
 * 
 * FEATURES:
 * - Timestamped log entries
 * - Auto-scroll to latest entry
 * - Copy all logs to clipboard
 * - Supports multiple log containers (loading screen + controls panel)
 * 
 * USAGE:
 * - appendActivityLog(message) - Add any message
 * - window.logSignificant(message) - Add important event (marked [IMPORTANT])
 * - window.copyActivityLogs() - Copy all logs to clipboard (called by buttons)
 */

/**
 * Append a message to all activity log containers
 * Automatically adds timestamp and scrolls to bottom
 * 
 * @param {string} message - Message to log
 */
function appendActivityLog(message) {
    const logEls = document.querySelectorAll('#activityLog');
    if (!logEls || logEls.length === 0) return;

    const time = new Date().toLocaleTimeString();
    const text = `[${time}] ${message}`;

    logEls.forEach((logEl) => {
        const row = document.createElement('div');
        row.textContent = text;
        logEl.appendChild(row);
        // Natural auto-scroll to bottom
        logEl.scrollTop = logEl.scrollHeight;
    });
}

/**
 * Log a significant event (marked [IMPORTANT] for easy identification)
 * Exposed globally for easy access from any code
 * 
 * @param {string} message - Important message to log
 */
window.logSignificant = function (message) {
    try {
        appendActivityLog(`[IMPORTANT] ${message}`);
    } catch (_) {
        // Silently fail - don't break if logging fails
    }
};

/**
 * Copy all log text from all activityLog containers to clipboard
 * Combines text from multiple log panels (loading screen + controls)
 * Called by "Copy all logs" buttons in the UI
 * 
 * @returns {Promise<void>}
 */
window.copyActivityLogs = async function () {
    try {
        const logEls = Array.from(document.querySelectorAll('#activityLog'));
        const texts = logEls.map(el => el.innerText.trim()).filter(Boolean);
        const combined = texts.join('\n');
        await navigator.clipboard.writeText(combined);
        appendActivityLog('Logs copied to clipboard.');
    } catch (e) {
        appendActivityLog(`Failed to copy logs: ${e && e.message ? e.message : e}`);
    }
};

/**
 * Log resource loading timing with performance metrics
 * Uses Performance API to extract file size, compression, and timing data
 * 
 * @param {string} resourceUrl - URL of the resource that was loaded
 * @param {string} label - Label for the log entry (e.g., "Loaded JSON")
 * @param {number} startTimeMs - Start time in milliseconds (from performance.now())
 * @param {number} endTimeMs - End time in milliseconds (from performance.now())
 */
function logResourceTiming(resourceUrl, label, startTimeMs, endTimeMs) {
    let entry = null;
    try {
        const entries = performance.getEntriesByName(resourceUrl);
        if (entries && entries.length) {
            entry = entries[entries.length - 1];
        }
    } catch (e) {
        // Ignore - performance API might not be available
    }
    const encodedKb = entry && typeof entry.encodedBodySize === 'number' ? (entry.encodedBodySize / 1024) : null;
    const decodedKb = entry && typeof entry.decodedBodySize === 'number' ? (entry.decodedBodySize / 1024) : null;
    const transferKb = entry && typeof entry.transferSize === 'number' ? (entry.transferSize / 1024) : null;
    const compressed = (encodedKb !== null && decodedKb !== null) ? (decodedKb > encodedKb) : null;
    const parts = [];
    if (decodedKb !== null) parts.push(`${decodedKb.toFixed(1)} KB decoded`);
    if (encodedKb !== null) parts.push(`${encodedKb.toFixed(1)} KB encoded`);
    if (transferKb !== null) parts.push(`${transferKb.toFixed(1)} KB transfer`);
    if (compressed !== null) parts.push(compressed ? 'compressed' : 'uncompressed');
    const duration = Math.max(0, Math.round((endTimeMs ?? performance.now()) - (startTimeMs ?? performance.now())));
    parts.push(`${duration} ms`);
    appendActivityLog(`${label}: ${resourceUrl} | ${parts.join(' | ')}`);
}

// Export module
window.ActivityLog = {
    append: appendActivityLog,
    logSignificant: window.logSignificant,
    copyAll: window.copyActivityLogs,
    logResourceTiming: logResourceTiming
};

