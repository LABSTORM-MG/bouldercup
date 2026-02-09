/**
 * Window poller module for detecting submission window changes.
 *
 * Polls the server periodically to detect when admin creates/modifies
 * submission windows, triggering page reload when state changes.
 */

/**
 * Check window state with server and reload if changed.
 *
 * Detects changes in:
 * - Submission allowance (can_submit)
 * - Window configuration (has_windows)
 * - Next window appearance
 * - Active window start/end
 *
 * @param {Object} state - Global state object
 * @param {Function} applyServerResults - Function to apply server result data
 */
export const checkWindowState = (state, applyServerResults) => {
    fetch(window.location.href, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
    })
        .then((res) => {
            if (!res.ok) throw new Error("HTTP " + res.status);
            return res.json();
        })
        .then((data) => {
            if (!data) return;

            const serverCanSubmit = data.can_submit;
            const serverHasWindows = data.has_windows;
            const serverNextWindowTimestamp = data.next_window_timestamp;
            const serverActiveWindowEndTimestamp = data.active_window_end_timestamp;

            const localHasWindows = document.body.dataset.hasWindows === "true";

            // Check if submission state changed
            const stateChanged = serverCanSubmit !== state.canSubmit;

            // Check if windows were added/removed
            const windowsChanged = serverHasWindows !== localHasWindows;

            // Check if a new next window appeared (wasn't there before)
            const newNextWindow = serverNextWindowTimestamp && !state.nextWindowTimestamp;

            // Check if active window appeared or disappeared
            const newActiveWindow = serverActiveWindowEndTimestamp && !state.activeWindowEndTimestamp;
            const activeWindowEnded = !serverActiveWindowEndTimestamp && state.activeWindowEndTimestamp;

            // Reload if any significant change detected
            if (stateChanged || windowsChanged || newNextWindow || newActiveWindow || activeWindowEnded) {
                window.location.reload();
            }

            // Update results if provided
            if (data.results) {
                applyServerResults(data.results);
            }
        })
        .catch(() => {
            // Silently ignore polling errors
        });
};

/**
 * Initialize window state polling with jitter.
 *
 * Adds random jitter to prevent thundering herd when many clients
 * are viewing the same page.
 *
 * @param {Object} config - Configuration object with polling settings
 * @param {Object} state - Global state object
 * @param {Function} applyServerResults - Function to apply server result data
 */
export const initializeWindowPolling = (config, state, applyServerResults) => {
    // Start polling with jitter to prevent thundering herd
    const pollJitter =
        Math.random() * (config.pollJitterMax - config.pollJitterMin) + config.pollJitterMin;

    setTimeout(() => {
        setInterval(() => checkWindowState(state, applyServerResults), config.pollInterval);
    }, pollJitter);
};
