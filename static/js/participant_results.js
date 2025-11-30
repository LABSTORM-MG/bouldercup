const form = document.querySelector("form");
const toast = document.getElementById("autosave-toast");
let submitTimer;
let hideToastTimer;
let pending = false;
let dirty = false;
const csrfToken = () => document.querySelector("input[name='csrfmiddlewaretoken']").value;

const applyServerResults = (results) => {
    if (!results) return;
    Object.entries(results).forEach(([bid, vals]) => {
        const card = document.querySelector(`.boulder-card[data-boulder='${bid}']`);
        if (!card) return;
        const input = card.querySelector(`input[name='attempts_${bid}']`);
        const zone1 = card.querySelector(`input[name='zone1_${bid}']`);
        const zone2 = card.querySelector(`input[name='zone2_${bid}']`);
        const sent = card.querySelector(`input[name='sent_${bid}']`);
        const ts = card.querySelector(`input[name='ts_${bid}']`);
        const badge = card.querySelector(".flash-badge");
        const incomingTs = typeof vals.updated_at === "number" ? vals.updated_at : null;
        const localTs = ts ? parseFloat(ts.value || "0") : 0;
        if (incomingTs && incomingTs <= localTs + 1e-4) return;
        if (typeof vals.attempts === "number" && input) input.value = vals.attempts;
        if (zone1 && typeof vals.zone1 === "boolean") zone1.checked = vals.zone1;
        if (zone2 && typeof vals.zone2 === "boolean") zone2.checked = vals.zone2;
        if (sent && typeof vals.top === "boolean") sent.checked = vals.top;
        if (ts && incomingTs !== null) ts.value = incomingTs;
        if (badge && sent && input) {
            const flash = sent.checked && Number(input.value || 0) === 1;
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

if (form) {
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        queueSubmit();
    });
}

// Periodic polling to pick up remote changes when multiple devices are active.
const pollIntervalMs = 5000;
setInterval(() => {
    if (!form || pending || dirty) return;
    fetch(window.location.href, {
        method: "GET",
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
    const input = card.querySelector("input[type='number']");
    const zone1 = card.querySelector("input[name^='zone1_']");
    const zone2 = card.querySelector("input[name^='zone2_']");
    const sent = card.querySelector("input[name^='sent_']");
    const checkboxes = card.querySelectorAll("input[type='checkbox']");
    const flashBadge = card.querySelector(".flash-badge");

    const hasResult = () => {
        return (
            (zone1 && zone1.checked) ||
            (zone2 && zone2.checked) ||
            (sent && sent.checked)
        );
    };

    const syncAttempts = () => {
        let val = Number(input.value || 0);
        if (Number.isNaN(val)) val = 0;
        if (hasResult() && val < 1) {
            val = 1;
        }
        if (val < 0) val = 0;
        input.value = val;
    };

    const syncFlash = () => {
        if (!flashBadge) return;
        const attempts = Number(input.value || 0);
        const flash = sent && sent.checked && attempts === 1;
        flashBadge.classList.toggle("show", flash);
    };

    card.querySelector(".dec").addEventListener("click", () => {
        const next = Math.max(0, Number(input.value || 0) - 1);
        input.value = next;
        syncAttempts();
        syncFlash();
        queueSubmit();
    });
    card.querySelector(".inc").addEventListener("click", () => {
        const next = Number(input.value || 0) + 1;
        input.value = next;
        syncAttempts();
        syncFlash();
        queueSubmit();
    });
    input.addEventListener("input", () => {
        let val = Number(input.value || 0);
        if (Number.isNaN(val) || val < 0) val = 0;
        input.value = val;
        syncAttempts();
        syncFlash();
        queueSubmit();
    });
    const cascade = (changed) => {
        const levels = [
            zone1 ? zone1 : null, // lowest
            zone2 ? zone2 : null,
            sent ? sent : null,   // top
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
            // Turning on: select this level and everything below; drop higher.
            selectThrough(idx);
        } else if (higherChecked) {
            // Demote to this level: keep this on, lower on, higher off.
            selectThrough(idx);
            levels[idx].checked = true;
        } else {
            // Highest selected toggled off: just uncheck it, keep lower as-is.
            levels[idx].checked = false;
        }

        // Enforce hierarchy: no higher without lower.
        for (let i = levels.length - 1; i > 0; i--) {
            if (levels[i].checked && !levels[i - 1].checked) {
                levels[i].checked = false;
            }
        }

        // If top is checked, ensure all below are on.
        const topIdx = sent ? levels.findIndex((el) => el === sent) : -1;
        if (topIdx >= 0 && levels[topIdx].checked) {
            for (let i = 0; i < topIdx; i++) {
                levels[i].checked = true;
            }
        }
        syncAttempts();
        syncFlash();
    };
    checkboxes.forEach((cb) => {
        cb.addEventListener("change", () => {
            cascade(cb);
            queueSubmit();
        });
    });
    syncAttempts();
    syncFlash();
});

// Improve text contrast based on background color of the boulder card body.
const computeTextColor = (rgbString) => {
    const match = rgbString.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
    if (!match) return "#0f172a";
    const [r, g, b] = match.slice(1).map(Number);
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminance > 0.6 ? "#0f172a" : "#ffffff";
};

document.querySelectorAll(".boulder-card-body").forEach((body) => {
    const bg = window.getComputedStyle(body).backgroundColor;
    body.style.color = computeTextColor(bg);
});
