/**
 * Keyboard Shortcuts Module
 * 
 * PURPOSE:
 * Centralized keyboard shortcut handling for the viewer.
 * Manages global shortcuts that work across all camera schemes.
 * 
 * FEATURES:
 * - Global shortcuts (R for reset, +/- for resolution)
 * - Respects input field focus (doesn't interfere with typing)
 * - Integrates with camera schemes (camera handles movement keys)
 * - Tracks movement keys (WASD/QE) for camera schemes
 * 
 * SHORTCUTS:
 * - R: Reset camera
 * - + or =: Increase sharpness (decrease bucket size by 1)
 * - - or _: Decrease sharpness / blur (increase bucket size by 1)
 * - Shift + +: Zoom in (simulates mouse wheel scroll up)
 * - Shift + -: Zoom out (simulates mouse wheel scroll down)
 * - ? or /: Toggle keyboard shortcuts help overlay
 * - V: Overhead camera view (same as "Overhead" button)
 * - F: Reset camera (same as "Reset Camera" button)
 * - WASD/QE: Movement (handled by camera scheme, but tracked here)
 * 
 * USAGE:
 * This module provides handler functions that are called from viewer-advanced.js.
 * The handlers are called BEFORE camera scheme handlers, allowing global shortcuts
 * to take precedence when needed.
 * 
 * DEPENDS ON:
 * - Global: keyboard object (for movement key tracking)
 * - Functions: resetCamera() (from viewer-advanced.js)
 * - Module: ResolutionControls.adjust() (from resolution-controls.js)
 */

/**
 * Check if user is currently typing in an input field
 * @param {KeyboardEvent} event - Keyboard event
 * @returns {boolean} True if user is typing
 */
function isUserTyping(event) {
    const activeElement = document.activeElement;
    return activeElement && (
        activeElement.tagName === 'INPUT' ||
        activeElement.tagName === 'TEXTAREA' ||
        activeElement.tagName === 'SELECT' ||
        activeElement.isContentEditable
    );
}

/**
 * Handle global keyboard shortcuts
 * @param {KeyboardEvent} event - Keyboard event
 * @param {Object} keyboard - Keyboard state object (for movement key tracking)
 */
function handleGlobalShortcuts(event, keyboard) {
    // Don't process keyboard shortcuts if user is typing in an input field
    if (isUserTyping(event)) {
        return;
    }

    const key = event.key.toLowerCase();

    // Movement keys (tracked but not used since camera scheme handles movement)
    if (key === 'w') keyboard.w = true;
    if (key === 'a') keyboard.a = true;
    if (key === 's') keyboard.s = true;
    if (key === 'd') keyboard.d = true;
    if (key === 'q') keyboard.q = true;
    if (key === 'e') keyboard.e = true;

    // Modifier keys
    if (event.shiftKey) keyboard.shift = true;
    if (event.ctrlKey) keyboard.ctrl = true;
    if (event.altKey) keyboard.alt = true;

    // Global shortcuts (only handle keys NOT handled by camera scheme)
    
    // R key: Reset camera (fallback if camera scheme doesn't handle it)
    if (event.key === 'r' || event.key === 'R') {
        if (typeof resetCamera === 'function') {
            resetCamera();
        }
        return;
    }

    // Shift + + key: Zoom in (simulates mouse wheel scroll up)
    if (event.shiftKey && (event.key === '+' || event.key === '=')) {
        event.preventDefault();
        if (typeof keyboardZoom === 'function') {
            keyboardZoom(-1); // Negative = zoom in
        }
        return;
    }

    // Shift + - key: Zoom out (simulates mouse wheel scroll down)
    if (event.shiftKey && (event.key === '-' || event.key === '_')) {
        event.preventDefault();
        if (typeof keyboardZoom === 'function') {
            keyboardZoom(1); // Positive = zoom out
        }
        return;
    }

    // + key: Increase sharpness (decrease bucket size by 1) - ONLY without Shift
    if (!event.shiftKey && (event.key === '+' || event.key === '=')) {
        event.preventDefault();
        if (window.ResolutionControls && typeof window.ResolutionControls.adjust === 'function') {
            window.ResolutionControls.adjust(-1);
        }
        return;
    }

    // - key: Decrease sharpness / blur (increase bucket size by 1) - ONLY without Shift
    if (!event.shiftKey && (event.key === '-' || event.key === '_')) {
        event.preventDefault();
        if (window.ResolutionControls && typeof window.ResolutionControls.adjust === 'function') {
            window.ResolutionControls.adjust(1);
        }
        return;
    }

    // ? or / key: Toggle shortcuts help overlay
    if (event.key === '?' || event.key === '/') {
        event.preventDefault();
        if (typeof toggleShortcutsOverlay === 'function') {
            toggleShortcutsOverlay();
        }
        return;
    }

    // V key: Overhead camera view (same as "Overhead" button)
    if (event.key === 'v' || event.key === 'V') {
        event.preventDefault();
        if (typeof triggerOverheadView === 'function') {
            triggerOverheadView();
        }
        return;
    }

    // F key: Reset camera (same as "Reset Camera" button)
    if (event.key === 'f' || event.key === 'F') {
        event.preventDefault();
        if (typeof resetCamera === 'function') {
            resetCamera();
        }
        return;
    }
    // Arrow keys: Disabled for now
    // if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    //     event.preventDefault(); // Prevent page scrolling
    //     navigateRegions(event.key === 'ArrowDown' ? 1 : -1);
    // }
}

/**
 * Handle keyboard key release
 * @param {KeyboardEvent} event - Keyboard event
 * @param {Object} keyboard - Keyboard state object
 */
function handleGlobalKeyUp(event, keyboard) {
    const key = event.key.toLowerCase();

    // Release movement keys
    if (key === 'w') keyboard.w = false;
    if (key === 'a') keyboard.a = false;
    if (key === 's') keyboard.s = false;
    if (key === 'd') keyboard.d = false;
    if (key === 'q') keyboard.q = false;
    if (key === 'e') keyboard.e = false;

    // Release modifier keys
    if (!event.shiftKey) keyboard.shift = false;
    if (!event.ctrlKey) keyboard.ctrl = false;
    if (!event.altKey) keyboard.alt = false;
}

/**
 * Initialize keyboard shortcuts system
 * This is a no-op now - handlers are called directly from viewer-advanced.js
 * Kept for backward compatibility
 * @param {Object} keyboard - Keyboard state object (from viewer-advanced.js)
 */
function initKeyboardShortcuts(keyboard) {
    // Module is now passive - handlers are called directly
    // This function exists for backward compatibility
}

/**
 * Cleanup keyboard shortcuts system
 * This is a no-op now - no cleanup needed
 */
function cleanupKeyboardShortcuts() {
    // Module is now passive - no cleanup needed
}

// Export module
window.KeyboardShortcuts = {
    init: initKeyboardShortcuts,
    cleanup: cleanupKeyboardShortcuts,
    handleGlobalShortcuts: handleGlobalShortcuts,
    handleGlobalKeyUp: handleGlobalKeyUp,
    isUserTyping: isUserTyping
};

