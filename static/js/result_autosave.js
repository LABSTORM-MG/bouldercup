/**
 * Result autosave module for handling form submission and persistence.
 *
 * Features:
 * - Debounced autosave after user input
 * - Optimistic locking with timestamp-based conflict detection
 * - sendBeacon for reliable save-on-unload
 * - Toast notifications for save status
 */

/**
 * Check if current state represents a flash (top in 1 attempt).
 *
 * @param {Object} checkboxes - Object with checkbox elements (top, z1, z2)
 * @param {Object} inputs - Object with attempt input elements (top, z1, z2)
 * @returns {boolean} True if this is a flash state
 */
export const isFlashState = (checkboxes, inputs) => {
    if (!checkboxes.top || !checkboxes.top.checked) return false;
    const candidates = [inputs.top, inputs.z2, inputs.z1].filter(Boolean);
    if (!candidates.length) return false;
    return candidates.every((el) => Number(el.value || 0) === 1);
};

/**
 * Apply server results to form inputs.
 * Uses version-based optimistic locking to prevent overwriting newer local changes.
 *
 * @param {Object} results - Server results object (boulder_id -> result data)
 */
export const applyServerResults = (results) => {
    if (!results) return;

    Object.entries(results).forEach(([bid, vals]) => {
        const card = document.querySelector(`.boulder-card[data-boulder='${bid}']`);
        if (!card) return;

        const inputs = {
            z1: card.querySelector(`input[name='attempts_zone1_${bid}']`),
            z2: card.querySelector(`input[name='attempts_zone2_${bid}']`),
            top: card.querySelector(`input[name='attempts_top_${bid}']`),
        };
        const checkboxes = {
            z1: card.querySelector(`input[name='zone1_${bid}']`),
            z2: card.querySelector(`input[name='zone2_${bid}']`),
            top: card.querySelector(`input[name='sent_${bid}']`),
        };
        const ver = card.querySelector(`input[name='ver_${bid}']`);
        const badge = card.querySelector(".flash-badge");

        // Version-based optimistic locking: only apply if server version is newer
        const incomingVersion = typeof vals.version === "number" ? vals.version : null;
        const localVersion = ver ? parseInt(ver.value || "0") : 0;
        if (incomingVersion !== null && incomingVersion <= localVersion) return;

        // Apply server values
        if (inputs.z1 && typeof vals.attempts_zone1 === "number") inputs.z1.value = vals.attempts_zone1;
        if (inputs.z2 && typeof vals.attempts_zone2 === "number") inputs.z2.value = vals.attempts_zone2;
        if (inputs.top && typeof vals.attempts_top === "number") inputs.top.value = vals.attempts_top;
        if (checkboxes.z1 && typeof vals.zone1 === "boolean") checkboxes.z1.checked = vals.zone1;
        if (checkboxes.z2 && typeof vals.zone2 === "boolean") checkboxes.z2.checked = vals.zone2;
        if (checkboxes.top && typeof vals.top === "boolean") checkboxes.top.checked = vals.top;
        if (ver && incomingVersion !== null) ver.value = incomingVersion;

        // Update flash badge
        if (badge) {
            const flash = isFlashState(checkboxes, inputs);
            badge.classList.toggle("show", flash);
        }
    });
};

/**
 * Show toast notification.
 *
 * @param {HTMLElement} toast - Toast element
 * @param {string} text - Message to display
 * @param {string} state - Toast state: "ok", "error", or "pending"
 * @param {Object} config - Configuration object
 * @param {Object} timers - Object to store hideToastTimer
 */
export const showStatus = (toast, text, state, config, timers) => {
    if (!toast) return;

    toast.textContent = text;
    toast.classList.remove("error", "pending", "show");
    if (state === "error") toast.classList.add("error");
    if (state === "pending") toast.classList.add("pending");

    requestAnimationFrame(() => toast.classList.add("show"));

    clearTimeout(timers.hideToastTimer);
    const timeout = state === "error" ? config.toastErrorDuration : config.toastSuccessDuration;
    timers.hideToastTimer = setTimeout(() => {
        toast.classList.remove("show");
    }, timeout);
};

/**
 * Submit form via AJAX.
 *
 * @param {Object} state - Global state object
 * @param {Function} showStatusFn - Toast notification function
 * @param {Function} applyServerResults - Function to apply server results
 * @param {Function} queueSubmit - Function to queue another submit if dirty
 */
export const submitAjax = (state, showStatusFn, applyServerResults, queueSubmit) => {
    if (!state.form || state.pending) {
        return;
    }

    const data = new FormData(state.form);
    state.dirty = false;
    state.pending = true;
    showStatusFn("Speichere ...", "pending");

    const csrfToken = document.querySelector("input[name='csrfmiddlewaretoken']").value;

    fetch(window.location.href, {
        method: "POST",
        credentials: "same-origin",
        headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": csrfToken,
        },
        body: data,
    })
        .then((res) => {
            if (!res.ok) throw new Error("HTTP " + res.status);
            return res.json();
        })
        .then((data) => {
            showStatusFn("Gespeichert", "ok");
            applyServerResults(data.results || {});
        })
        .catch(() => {
            showStatusFn("Fehler beim Speichern", "error");
            state.dirty = true; // retry next change if we hit an error
        })
        .finally(() => {
            state.pending = false;
            if (state.dirty) {
                queueSubmit();
            }
        });
};

/**
 * Queue a form submission after debounce delay.
 *
 * @param {Object} state - Global state object
 * @param {Object} config - Configuration object
 * @param {Function} submitAjax - Function to submit via AJAX
 * @param {Object} timers - Object to store submitTimer
 */
export const queueSubmit = (state, config, submitAjax, timers) => {
    if (!state.canSubmit) return; // Don't save when submission is locked

    clearTimeout(timers.submitTimer);
    state.dirty = true;

    // Save after the configured delay following the last detected change
    timers.submitTimer = setTimeout(submitAjax, config.autosaveDelay);
};

/**
 * Flush pending changes before page unload.
 * Uses sendBeacon for reliability during unload.
 *
 * @param {Object} state - Global state object
 */
export const flushBeforeUnload = (state) => {
    if (!state.form || !state.canSubmit) return;

    // If nothing changed and nothing is in flight, skip.
    if (!state.dirty && !state.pending) return;

    const data = new FormData(state.form);
    const targetUrl = state.form.getAttribute("action") || window.location.href;

    // Try to persist even during page unload; sendBeacon is the most reliable option.
    if (navigator.sendBeacon) {
        navigator.sendBeacon(targetUrl, data);
        state.dirty = false;
    }
};

/**
 * Initialize autosave functionality.
 *
 * @param {Object} state - Global state object
 * @param {Object} config - Configuration object
 * @param {HTMLElement} toast - Toast notification element
 * @returns {Object} Object containing timers and functions for external use
 */
export const initializeAutosave = (state, config, toast) => {
    const timers = {
        submitTimer: null,
        hideToastTimer: null,
    };

    const showStatusFn = (text, statusState) =>
        showStatus(toast, text, statusState, config, timers);

    const submitAjaxFn = () => submitAjax(state, showStatusFn, applyServerResults, queueSubmitFn);
    const queueSubmitFn = () => queueSubmit(state, config, submitAjaxFn, timers);
    const flushBeforeUnloadFn = () => flushBeforeUnload(state);

    // Set up form submit handler
    if (state.form) {
        state.form.addEventListener("submit", (e) => {
            e.preventDefault();
            queueSubmitFn();
        });
    }

    // Set up page unload handlers
    window.addEventListener("pagehide", flushBeforeUnloadFn);
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden") {
            flushBeforeUnloadFn();
        }
    });
    window.addEventListener("beforeunload", flushBeforeUnloadFn);
    window.addEventListener("unload", flushBeforeUnloadFn);

    return {
        queueSubmit: queueSubmitFn,
        flushBeforeUnload: flushBeforeUnloadFn,
        showStatus: showStatusFn,
        applyServerResults,
    };
};
