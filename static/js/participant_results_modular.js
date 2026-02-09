/**
 * Main participant results script - modular version.
 *
 * Coordinates:
 * - Autosave functionality
 * - Countdown timers for submission windows
 * - Window state polling
 * - Cascade logic for attempt validation
 */

import { initializeAutosave } from "./result_autosave.js";
import { initializeCountdowns } from "./countdown_timer.js";
import { initializeWindowPolling } from "./window_poller.js";
import { initializeCascadeLogic } from "./cascade_logic.js";

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

// Global state
const state = {
    form: document.querySelector("form"),
    canSubmit: document.body.dataset.canSubmit === "true",
    nextWindowTimestamp: parseFloat(document.body.dataset.nextWindowTimestamp) || null,
    activeWindowEndTimestamp: parseFloat(document.body.dataset.activeWindowEndTimestamp) || null,
    pending: false,
    dirty: false,
};

// Create or get toast element
let toast = document.getElementById("autosave-toast");
if (!toast) {
    toast = document.createElement("div");
    toast.id = "autosave-toast";
    toast.classList.add("toast");
    document.body.appendChild(toast);
}

// Initialize autosave
const { queueSubmit, flushBeforeUnload, showStatus, applyServerResults } = initializeAutosave(
    state,
    config,
    toast
);

// Initialize countdowns
initializeCountdowns(state, showStatus, flushBeforeUnload, config);

// Initialize window polling
initializeWindowPolling(config, state, applyServerResults);

// Initialize cascade logic for each boulder card
document.querySelectorAll(".boulder-card").forEach((card) => {
    initializeCascadeLogic(card, queueSubmit);
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
