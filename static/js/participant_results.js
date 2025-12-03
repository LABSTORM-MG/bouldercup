const form = document.querySelector("form");
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
const csrfToken = () => document.querySelector("input[name='csrfmiddlewaretoken']").value;

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
    const timeout = state === "error" ? 3000 : 1500;
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
    clearTimeout(submitTimer);
    dirty = true;
    submitTimer = setTimeout(submitAjax, 2000);
};

const flushBeforeUnload = () => {
    if (!form) return;
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

// Periodic polling to pick up remote changes when multiple devices are active.
const pollIntervalMs = 5000;
setInterval(() => {
    if (!form || pending || dirty) return;
    fetch(window.location.href, {
        method: "GET",
        credentials: "same-origin",
        headers: {
            "X-Requested-With": "XMLHttpRequest",
        },
    })
        .then((res) => {
            if (!res.ok) throw new Error("HTTP " + res.status);
            return res.json();
        })
        .then((data) => {
            applyServerResults(data.results || {});
        })
        .catch(() => {
            /* ignore poll errors */
        });
}, pollIntervalMs);

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
