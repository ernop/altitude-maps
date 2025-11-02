/**
 * UI Loading States Module
 * 
 * PURPOSE:
 * Manages the loading screen and progress bar displayed during data loading.
 * Simple show/hide/update operations for loading overlay.
 * 
 * FEATURES:
 * - Show loading screen with custom message
 * - Update progress bar with percentage and file size
 * - Hide loading screen
 * - Uses animated gradient progress bar
 * 
 * DESIGN:
 * - Pure DOM manipulation (no Three.js)
 * - Updates global isCurrentlyLoading flag
 * - Uses formatFileSize() from format-utils.js
 * 
 * DEPENDS ON:
 * - Global: isCurrentlyLoading (flag)
 * - DOM: #loading, #progress-bar-fill, #progress-text
 * - window.FormatUtils.formatFileSize()
 */

/**
 * Show loading screen with optional custom message
 * Creates progress bar elements and displays spinner
 * 
 * @param {string} message - Loading message to display (default: 'Loading elevation data...')
 * @global isCurrentlyLoading - Sets to true
 */
function showLoading(message = 'Loading elevation data...') {
    isCurrentlyLoading = true;
    const loadingDiv = document.getElementById('loading');
    loadingDiv.innerHTML = `
        <div style="text-align: center;">
            ${message}
            <div class="spinner"></div>
            <div id="progress-container" style="margin-top: 15px; width: 300px;">
                <div id="progress-bar-bg" style="width: 100%; height: 20px; background: rgba(255,255,255,0.1); border-radius: 10px; overflow: hidden;">
                    <div id="progress-bar-fill" style="width: 0%; height: 100%; background: linear-gradient(90deg,#4488cc,#5599dd); transition: width 0.3s ease;"></div>
                </div>
                <div id="progress-text" style="margin-top: 8px; font-size: 13px; color:#aaa;">Initializing...</div>
            </div>
        </div>
    `;
    loadingDiv.style.display = 'flex';
}

/**
 * Update loading progress bar
 * Shows percentage and file sizes (loaded/total)
 * 
 * @param {number} percent - Progress percentage (0-100)
 * @param {number} loaded - Bytes loaded so far
 * @param {number} total - Total bytes to load
 */
function updateLoadingProgress(percent, loaded, total) {
    const progressFill = document.getElementById('progress-bar-fill');
    const progressText = document.getElementById('progress-text');

    if (!progressFill || !progressText) return;

    progressFill.style.width = `${Math.min(100, percent)}%`;
    progressText.textContent = `${percent}% (${window.FormatUtils.formatFileSize(loaded)} / ${window.FormatUtils.formatFileSize(total)})`;
}

/**
 * Hide loading screen
 * Sets loading div display to none and clears loading flag
 * 
 * @global isCurrentlyLoading - Sets to false
 */
function hideLoading() {
    isCurrentlyLoading = false;
    document.getElementById('loading').style.display = 'none';
}

// Export module
window.UILoading = {
    show: showLoading,
    updateProgress: updateLoadingProgress,
    hide: hideLoading
};

