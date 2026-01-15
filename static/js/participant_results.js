// Read configuration from data attributes
const config = {
    autosaveDelay: parseInt(document.body.dataset.autosaveDelay) || 5000,
    pollInterval: parseInt(document.body.dataset.pollInterval) || 15000,
    pollJitterMin: parseInt(document.body.dataset.pollJitterMin) || 5000,
    pollJitterMax: parseInt(document.body.dataset.pollJitterMax) || 10000,
    reloadBaseDelay: parseInt(document.body.dataset.reloadBaseDelay) || 500,
    reloadBaseDelayEnd: parseInt(document.body.dataset.reloadBaseDelayEnd) || 1500,
    reloadJitter: parseInt(document.body.dataset.reloadJitter) || 5000,
    warningCountdownSeconds: parseInt(document.body.dataset.warningCountdownSeconds) || 300,
    toastErrorDuration: parseInt(document.body.dataset.toastErrorDuration) || 3000,
    toastSuccessDuration: parseInt(document.body.dataset.toastSuccessDuration) || 1500,
};

const form = document.querySelector("form");
let canSubmit = document.body.dataset.canSubmit === "true";
const nextWindowTimestamp = parseFloat(document.body.dataset.nextWindowTimestamp) || null;
const activeWindowEndTimestamp = parseFloat(document.body.dataset.activeWindowEndTimestamp) || null;
let toast = document.getElementById("autosave-toast");
if (!toast) {
    toast = document.createElement("div");
    toast.id = "autosave-toast";
    toast.classList.add("toast");
    document.body.appendChild(toast);
}
let submitTimer;
let hideToastTimer;
let pending = false;
let dirty = false;
let countdownInterval = null;
let endingCountdownInterval = null;
const csrfToken = () => document.querySelector("input[name='csrfmiddlewaretoken']").value;

// Countdown and unlock functionality
const formatCountdown = (seconds) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) {
        return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }
    return `${m}:${String(s).padStart(2, "0")}`;
};

const enableSubmission = () => {
    // When transitioning from one window to another, reload to get new window data
    // This ensures we have the correct active_window_end_timestamp
    if (!canSubmit && nextWindowTimestamp) {
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

    canSubmit = true;
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

const updateCountdown = () => {
    if (!nextWindowTimestamp) return;

    const now = Date.now() / 1000;
    const remaining = Math.max(0, Math.floor(nextWindowTimestamp - now));
    const countdownEl = document.getElementById("countdown");

    if (remaining <= 0) {
        if (countdownInterval) {
            clearInterval(countdownInterval);
            countdownInterval = null;
        }
        enableSubmission();
        return;
    }

    if (countdownEl) {
        countdownEl.textContent = formatCountdown(remaining);
    }
};

// Start countdown if there's a next window
if (nextWindowTimestamp && !canSubmit) {
    updateCountdown();
    countdownInterval = setInterval(updateCountdown, 1000);
}

// Disable submission when window ends
const disableSubmission = () => {
    // Flush any pending changes before disabling
    if (dirty && form) {
        flushBeforeUnload();
    }

    canSubmit = false;
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

// Update ending countdown (last 5 minutes)
const updateEndingCountdown = () => {
    if (!activeWindowEndTimestamp || !canSubmit) return;

    const now = Date.now() / 1000;
    const remaining = Math.max(0, Math.floor(activeWindowEndTimestamp - now));
    const endingNotice = document.getElementById("ending-notice");
    const endingCountdownEl = document.getElementById("ending-countdown");

    if (remaining <= 0) {
        // Window has ended
        if (endingCountdownInterval) {
            clearInterval(endingCountdownInterval);
            endingCountdownInterval = null;
        }
        disableSubmission();
        return;
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
};

// Start ending countdown if there's an active window
if (activeWindowEndTimestamp && canSubmit) {
    updateEndingCountdown();
    endingCountdownInterval = setInterval(updateEndingCountdown, 1000);
}

// Poll server to detect submission window changes (e.g., admin creates new window)
const checkWindowState = () => {
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
            const stateChanged = serverCanSubmit !== canSubmit;

            // Check if windows were added/removed
            const windowsChanged = serverHasWindows !== localHasWindows;

            // Check if a new next window appeared (wasn't there before)
            const newNextWindow = serverNextWindowTimestamp && !nextWindowTimestamp;

            // Check if active window appeared or disappeared
            const newActiveWindow = serverActiveWindowEndTimestamp && !activeWindowEndTimestamp;
            const activeWindowEnded = !serverActiveWindowEndTimestamp && activeWindowEndTimestamp;

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

// Start polling with jitter to prevent thundering herd
const pollJitter = Math.random() * (config.pollJitterMax - config.pollJitterMin) + config.pollJitterMin;
setTimeout(() => {
    setInterval(checkWindowState, config.pollInterval);
}, pollJitter);

const isFlashState = (checkboxes, inputs) => {
    if (!checkboxes.top || !checkboxes.top.checked) return false;
    const candidates = [inputs.top, inputs.z2, inputs.z1].filter(Boolean);
    if (!candidates.length) return false;
    return candidates.every((el) => Number(el.value || 0) === 1);
};

const applyServerResults = (results) => {
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
        const ts = card.querySelector(`input[name='ts_${bid}']`);
        const badge = card.querySelector(".flash-badge");
        const incomingTs = typeof vals.updated_at === "number" ? vals.updated_at : null;
        const localTs = ts ? parseFloat(ts.value || "0") : 0;
        if (incomingTs && incomingTs <= localTs + 1e-4) return;
        if (inputs.z1 && typeof vals.attempts_zone1 === "number") inputs.z1.value = vals.attempts_zone1;
        if (inputs.z2 && typeof vals.attempts_zone2 === "number") inputs.z2.value = vals.attempts_zone2;
        if (inputs.top && typeof vals.attempts_top === "number") inputs.top.value = vals.attempts_top;
        if (checkboxes.z1 && typeof vals.zone1 === "boolean") checkboxes.z1.checked = vals.zone1;
        if (checkboxes.z2 && typeof vals.zone2 === "boolean") checkboxes.z2.checked = vals.zone2;
        if (checkboxes.top && typeof vals.top === "boolean") checkboxes.top.checked = vals.top;
        if (ts && incomingTs !== null) ts.value = incomingTs;
        if (badge) {
            const flash = isFlashState(checkboxes, inputs);
            badge.classList.toggle("show", flash);
        }
    });
};

const showStatus = (text, state = "ok") => {
    if (!toast) return;
    toast.textContent = text;
    toast.classList.remove("error", "pending", "show");
    if (state === "error") toast.classList.add("error");
    if (state === "pending") toast.classList.add("pending");
    requestAnimationFrame(() => toast.classList.add("show"));
    clearTimeout(hideToastTimer);
    const timeout = state === "error" ? config.toastErrorDuration : config.toastSuccessDuration;
    hideToastTimer = setTimeout(() => {
        toast.classList.remove("show");
    }, timeout);
};

const submitAjax = () => {
    if (!form || pending) {
        return;
    }
    const data = new FormData(form);
    dirty = false;
    pending = true;
    showStatus("Speichere ...", "pending");
    fetch(window.location.href, {
        method: "POST",
        credentials: "same-origin",
        headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": csrfToken(),
        },
        body: data,
    })
        .then((res) => {
            if (!res.ok) throw new Error("HTTP " + res.status);
            return res.json();
        })
        .then((data) => {
            showStatus("Gespeichert", "ok");
            applyServerResults(data.results || {});
        })
        .catch(() => {
            showStatus("Fehler beim Speichern", "error");
            dirty = true; // retry next change if we hit an error
        })
        .finally(() => {
            pending = false;
            if (dirty) {
                queueSubmit();
            }
        });
};

const queueSubmit = () => {
    if (!canSubmit) return; // Don't save when submission is locked
    clearTimeout(submitTimer);
    dirty = true;
    // Save after the configured delay following the last detected change
    submitTimer = setTimeout(submitAjax, config.autosaveDelay);
};

const flushBeforeUnload = () => {
    if (!form || !canSubmit) return;
    // If nothing changed and nothing is in flight, skip.
    if (!dirty && !pending) return;
    const data = new FormData(form);
    const targetUrl = form.getAttribute("action") || window.location.href;
    // Try to persist even during page unload; sendBeacon is the most reliable option.
    if (navigator.sendBeacon) {
        navigator.sendBeacon(targetUrl, data);
        dirty = false;
    } else {
        submitAjax();
    }
};

if (form) {
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        queueSubmit();
    });
}

// Save on tab/window close or navigation away.
window.addEventListener("pagehide", flushBeforeUnload);
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
        flushBeforeUnload();
    }
});
window.addEventListener("beforeunload", flushBeforeUnload);
window.addEventListener("unload", flushBeforeUnload);

document.querySelectorAll(".boulder-card").forEach((card) => {
    const bid = card.dataset.boulder;
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
    const flashBadge = card.querySelector(".flash-badge");

    const clampValue = (inputEl) => {
        if (!inputEl) return 0;
        let val = Number(inputEl.value || 0);
        if (Number.isNaN(val) || val < 0) val = 0;
        inputEl.value = val;
        return val;
    };

    const syncFlash = () => {
        if (!flashBadge || !inputs.top || !checkboxes.top) return;
        const flash = isFlashState(checkboxes, inputs);
        flashBadge.classList.toggle("show", flash);
    };

    const enforceAttempts = () => {
        const state = {
            z1: checkboxes.z1 ? checkboxes.z1.checked : false,
            z2: checkboxes.z2 ? checkboxes.z2.checked : false,
            top: checkboxes.top ? checkboxes.top.checked : false,
        };

        const v1 = clampValue(inputs.z1);
        const v2 = clampValue(inputs.z2);
        const vt = clampValue(inputs.top);

        if (state.z1 && inputs.z1 && v1 < 1) inputs.z1.value = 1;
        if (state.z2 && inputs.z2 && v2 < 1) inputs.z2.value = 1;
        if (state.top && inputs.top && vt < 1) inputs.top.value = 1;

        const valTop = Number(inputs.top?.value || 0);
        const valZ2 = Number(inputs.z2?.value || 0);
        if (state.top && inputs.z2 && valZ2 === 0) inputs.z2.value = valTop || 1;
        if ((state.top || state.z2) && inputs.z1 && Number(inputs.z1.value || 0) === 0) {
            inputs.z1.value = inputs.z2 ? Number(inputs.z2.value || 0) || valTop || 1 : valTop || 1;
        }

        const z1Val = Number(inputs.z1?.value || 0);
        const z2Val = Number(inputs.z2?.value || 0);
        if (state.z2 && inputs.z2 && z2Val < z1Val) {
            inputs.z2.value = z1Val;
        }
        if (state.top && inputs.top) {
            const baseline = inputs.z2 ? Number(inputs.z2.value || 0) : z1Val;
            if (Number(inputs.top.value || 0) < baseline) {
                inputs.top.value = baseline;
            }
        }

        syncFlash();
    };

    const cascade = (changed) => {
        const levels = [
            checkboxes.z1 ? checkboxes.z1 : null, // lowest
            checkboxes.z2 ? checkboxes.z2 : null,
            checkboxes.top ? checkboxes.top : null, // highest
        ].filter(Boolean);
        if (!changed) return;
        const idx = levels.findIndex((el) => el === changed);
        if (idx === -1) return;
        const current = levels.map((el) => el.checked);
        const higherChecked = current.slice(idx + 1).some(Boolean);

        const selectThrough = (targetIdx) => {
            levels.forEach((el, i) => {
                el.checked = i <= targetIdx;
            });
        };

        if (changed.checked) {
            selectThrough(idx);
        } else if (higherChecked) {
            selectThrough(idx);
            levels[idx].checked = true;
        } else {
            levels[idx].checked = false;
        }

        for (let i = levels.length - 1; i > 0; i--) {
            if (levels[i].checked && !levels[i - 1].checked) {
                levels[i].checked = false;
            }
        }

        const topIdx = checkboxes.top ? levels.findIndex((el) => el === checkboxes.top) : -1;
        if (topIdx >= 0 && levels[topIdx].checked) {
            for (let i = 0; i < topIdx; i++) {
                levels[i].checked = true;
            }
        }
        enforceAttempts();
        syncFlash();
    };

    card.querySelectorAll(".attempt-controls").forEach((controls) => {
        const inputEl = controls.querySelector("input[type='number']");
        const dec = controls.querySelector(".dec");
        const inc = controls.querySelector(".inc");
        if (!inputEl) return;

        dec?.addEventListener("click", () => {
            inputEl.value = Math.max(0, Number(inputEl.value || 0) - 1);
            enforceAttempts();
            syncFlash();
            queueSubmit();
        });
        inc?.addEventListener("click", () => {
            inputEl.value = Number(inputEl.value || 0) + 1;
            enforceAttempts();
            syncFlash();
            queueSubmit();
        });
        inputEl.addEventListener("input", () => {
            clampValue(inputEl);
            enforceAttempts();
            syncFlash();
            queueSubmit();
        });
    });

    card.querySelectorAll("input[type='checkbox']").forEach((cb) => {
        cb.addEventListener("change", () => {
            cascade(cb);
            queueSubmit();
        });
    });

    enforceAttempts();
    syncFlash();
});

// Compute readable text color for a given rgb(...) string.
const computeTextColor = (rgbString) => {
    const match = rgbString.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
    if (!match) return "#0f172a";
    const [r, g, b] = match.slice(1).map(Number);
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminance > 0.6 ? "#0f172a" : "#ffffff";
};

// Adjust header text contrast based on its accent background.
document.querySelectorAll(".boulder-header").forEach((header) => {
    const bg = window.getComputedStyle(header).backgroundColor;
    const textColor = computeTextColor(bg);
    header.style.color = textColor;
    const flash = header.querySelector(".flash-badge");
    if (flash) flash.style.color = textColor;
});
