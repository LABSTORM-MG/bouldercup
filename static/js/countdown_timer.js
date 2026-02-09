/**
 * Countdown timer module for submission windows.
 *
 * Manages countdown displays for:
 * - Next window start time (when submission is locked)
 * - Active window end time (when submission is about to close)
 */

/**
 * Format seconds into human-readable countdown (H:MM:SS or M:SS).
 *
 * @param {number} seconds - Total seconds remaining
 * @returns {string} Formatted time string
 */
export const formatCountdown = (seconds) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) {
        return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }
    return `${m}:${String(s).padStart(2, "0")}`;
};

/**
 * Enable submission when countdown reaches zero.
 * If transitioning from a locked state with a next window, reloads the page.
 *
 * @param {Object} state - Global state object
 * @param {Function} showStatus - Toast notification function
 * @param {Object} config - Configuration object
 */
export const enableSubmission = (state, showStatus, config) => {
    // When transitioning from one window to another, reload to get new window data
    // This ensures we have the correct active_window_end_timestamp
    if (!state.canSubmit && state.nextWindowTimestamp) {
        // We're transitioning from a locked state to unlocked
        // Reload the page to get fresh data including the new active window end time
        showStatus("Abgabe gestartet - Seite wird aktualisiert...", "ok");
        // Add random jitter to prevent all clients refreshing simultaneously
        const jitter = Math.random() * config.reloadJitter;
        setTimeout(() => {
            window.location.reload();
        }, config.reloadBaseDelay + jitter);
        return;
    }

    state.canSubmit = true;
    document.body.dataset.canSubmit = "true";

    // Hide the locked notice
    const notice = document.getElementById("locked-notice");
    if (notice) {
        notice.style.display = "none";
    }

    // Enable all form inputs
    const boulderList = document.querySelector(".boulder-list");
    if (boulderList) {
        boulderList.classList.remove("readonly");
    }

    document.querySelectorAll("input[disabled], button[disabled]").forEach((el) => {
        el.disabled = false;
    });

    // Show success toast
    showStatus("Eintragung freigeschaltet!", "ok");
};

/**
 * Update countdown display for next window start.
 *
 * @param {Object} state - Global state object
 * @param {Function} showStatus - Toast notification function
 * @param {Object} config - Configuration object
 * @param {number|null} intervalId - Interval ID to clear when done
 * @returns {number|null} Updated interval ID (null if cleared)
 */
export const updateCountdown = (state, showStatus, config, intervalId) => {
    if (!state.nextWindowTimestamp) return intervalId;

    const now = Date.now() / 1000;
    const remaining = Math.max(0, Math.floor(state.nextWindowTimestamp - now));
    const countdownEl = document.getElementById("countdown");

    if (remaining <= 0) {
        if (intervalId) {
            clearInterval(intervalId);
            intervalId = null;
        }
        enableSubmission(state, showStatus, config);
        return null;
    }

    if (countdownEl) {
        countdownEl.textContent = formatCountdown(remaining);
    }

    return intervalId;
};

/**
 * Disable submission when window ends.
 * Flushes any pending changes before disabling.
 *
 * @param {Object} state - Global state object
 * @param {Function} flushBeforeUnload - Function to flush pending changes
 * @param {Function} showStatus - Toast notification function
 * @param {Object} config - Configuration object
 */
export const disableSubmission = (state, flushBeforeUnload, showStatus, config) => {
    // Flush any pending changes before disabling
    if (state.dirty && state.form) {
        flushBeforeUnload();
    }

    state.canSubmit = false;
    document.body.dataset.canSubmit = "false";

    // Hide the ending notice
    const endingNotice = document.getElementById("ending-notice");
    if (endingNotice) {
        endingNotice.style.display = "none";
    }

    // Disable all form inputs
    const boulderList = document.querySelector(".boulder-list");
    if (boulderList) {
        boulderList.classList.add("readonly");
    }

    document.querySelectorAll(".boulder-card input:not([type='hidden']), .boulder-card button").forEach((el) => {
        el.disabled = true;
    });

    // Reload the page to get fresh data (next window info, updated state, etc.)
    // Add random jitter to prevent all clients refreshing simultaneously
    showStatus("Abgabe beendet - Seite wird aktualisiert...", "pending");
    const jitter = Math.random() * config.reloadJitter;
    setTimeout(() => {
        window.location.reload();
    }, config.reloadBaseDelayEnd + jitter);
};

/**
 * Update ending countdown display (last N minutes warning).
 *
 * @param {Object} state - Global state object
 * @param {Object} config - Configuration object
 * @param {Function} flushBeforeUnload - Function to flush pending changes
 * @param {Function} showStatus - Toast notification function
 * @param {number|null} intervalId - Interval ID to clear when done
 * @returns {number|null} Updated interval ID (null if cleared)
 */
export const updateEndingCountdown = (state, config, flushBeforeUnload, showStatus, intervalId) => {
    if (!state.activeWindowEndTimestamp || !state.canSubmit) return intervalId;

    const now = Date.now() / 1000;
    const remaining = Math.max(0, Math.floor(state.activeWindowEndTimestamp - now));
    const endingNotice = document.getElementById("ending-notice");
    const endingCountdownEl = document.getElementById("ending-countdown");

    if (remaining <= 0) {
        // Window has ended
        if (intervalId) {
            clearInterval(intervalId);
            intervalId = null;
        }
        disableSubmission(state, flushBeforeUnload, showStatus, config);
        return null;
    }

    // Show/hide the ending notice based on remaining time
    if (remaining <= config.warningCountdownSeconds) {
        if (endingNotice) {
            endingNotice.style.display = "";
        }
        if (endingCountdownEl) {
            endingCountdownEl.textContent = formatCountdown(remaining);
        }
    } else {
        if (endingNotice) {
            endingNotice.style.display = "none";
        }
    }

    return intervalId;
};

/**
 * Initialize countdown timers.
 *
 * @param {Object} state - Global state object
 * @param {Function} showStatus - Toast notification function
 * @param {Function} flushBeforeUnload - Function to flush pending changes
 * @param {Object} config - Configuration object
 * @returns {Object} Object containing interval IDs for cleanup
 */
export const initializeCountdowns = (state, showStatus, flushBeforeUnload, config) => {
    let countdownInterval = null;
    let endingCountdownInterval = null;

    // Start countdown for next window if submission is locked
    if (state.nextWindowTimestamp && !state.canSubmit) {
        countdownInterval = updateCountdown(state, showStatus, config, null);
        if (countdownInterval === null) {
            // Already enabled, don't set interval
        } else {
            countdownInterval = setInterval(() => {
                countdownInterval = updateCountdown(state, showStatus, config, countdownInterval);
            }, 1000);
        }
    }

    // Start ending countdown if there's an active window
    if (state.activeWindowEndTimestamp && state.canSubmit) {
        endingCountdownInterval = updateEndingCountdown(state, config, flushBeforeUnload, showStatus, null);
        if (endingCountdownInterval === null) {
            // Already disabled, don't set interval
        } else {
            endingCountdownInterval = setInterval(() => {
                endingCountdownInterval = updateEndingCountdown(
                    state,
                    config,
                    flushBeforeUnload,
                    showStatus,
                    endingCountdownInterval
                );
            }, 1000);
        }
    }

    return { countdownInterval, endingCountdownInterval };
};
