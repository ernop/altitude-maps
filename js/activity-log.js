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

// Export module
window.ActivityLog = {
    append: appendActivityLog,
    logSignificant: window.logSignificant,
    copyAll: window.copyActivityLogs
};

