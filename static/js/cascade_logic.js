/**
 * Cascade logic module for attempt validation and checkbox hierarchy.
 *
 * Enforces rules:
 * - Higher achievements (top > zone2 > zone1) imply lower achievements
 * - Attempt counts must cascade: top_attempts >= zone2_attempts >= zone1_attempts
 * - Checked achievements require non-zero attempt counts
 */

/**
 * Clamp input value to non-negative integer.
 *
 * @param {HTMLInputElement} inputEl - Number input element
 * @returns {number} Clamped value
 */
const clampValue = (inputEl) => {
    if (!inputEl) return 0;
    let val = Number(inputEl.value || 0);
    if (Number.isNaN(val) || val < 0) val = 0;
    inputEl.value = val;
    return val;
};

/**
 * Check if current state is a flash (top in 1 attempt).
 *
 * @param {Object} checkboxes - Object with checkbox elements
 * @param {Object} inputs - Object with attempt input elements
 * @returns {boolean} True if flash state
 */
const isFlashState = (checkboxes, inputs) => {
    if (!checkboxes.top || !checkboxes.top.checked) return false;
    const candidates = [inputs.top, inputs.z2, inputs.z1].filter(Boolean);
    if (!candidates.length) return false;
    return candidates.every((el) => Number(el.value || 0) === 1);
};

/**
 * Sync flash badge visibility.
 *
 * @param {HTMLElement} flashBadge - Flash badge element
 * @param {Object} checkboxes - Object with checkbox elements
 * @param {Object} inputs - Object with attempt input elements
 */
const syncFlash = (flashBadge, checkboxes, inputs) => {
    if (!flashBadge || !inputs.top || !checkboxes.top) return;
    const flash = isFlashState(checkboxes, inputs);
    flashBadge.classList.toggle("show", flash);
};

/**
 * Enforce attempt count rules and cascading.
 *
 * Rules:
 * - Checked achievements require at least 1 attempt
 * - Attempt counts cascade upward (z1 <= z2 <= top)
 * - Auto-fill zero values when checkboxes are checked
 *
 * @param {Object} inputs - Object with attempt input elements
 * @param {Object} checkboxes - Object with checkbox elements
 * @param {HTMLElement} flashBadge - Flash badge element
 */
const enforceAttempts = (inputs, checkboxes, flashBadge) => {
    const state = {
        z1: checkboxes.z1 ? checkboxes.z1.checked : false,
        z2: checkboxes.z2 ? checkboxes.z2.checked : false,
        top: checkboxes.top ? checkboxes.top.checked : false,
    };

    // Clamp all values first
    clampValue(inputs.z1);
    clampValue(inputs.z2);
    clampValue(inputs.top);

    // Ensure minimum attempts of 1 when checked
    if (state.z1 && inputs.z1 && Number(inputs.z1.value || 0) < 1) inputs.z1.value = 1;
    if (state.z2 && inputs.z2 && Number(inputs.z2.value || 0) < 1) inputs.z2.value = 1;
    if (state.top && inputs.top && Number(inputs.top.value || 0) < 1) inputs.top.value = 1;

    // Auto-fill zeros when checkboxes are checked
    const valTop = Number(inputs.top?.value || 0);
    const valZ2 = Number(inputs.z2?.value || 0);
    if (state.top && inputs.z2 && valZ2 === 0) inputs.z2.value = valTop || 1;
    if ((state.top || state.z2) && inputs.z1 && Number(inputs.z1.value || 0) === 0) {
        inputs.z1.value = inputs.z2 ? Number(inputs.z2.value || 0) || valTop || 1 : valTop || 1;
    }

    // CRITICAL: Enforce hierarchical cascade - higher achievements ALWAYS need at least as many attempts
    // Read final values after all auto-fills
    let z1Val = Number(inputs.z1?.value || 0);
    let z2Val = Number(inputs.z2?.value || 0);
    let topVal = Number(inputs.top?.value || 0);

    // ALWAYS cascade upward: if Zone 1 has attempts, Zone 2 and Top must have at least that many
    if (z1Val > 0) {
        // Zone 2 must have at least Zone 1 attempts
        if (inputs.z2 && z2Val < z1Val) {
            inputs.z2.value = z1Val;
            z2Val = z1Val;
        }
        // Top must have at least Zone 1 attempts
        if (inputs.top && topVal < z1Val) {
            inputs.top.value = z1Val;
            topVal = z1Val;
        }
    }

    // If Zone 2 has attempts, Top must have at least Zone 2 attempts
    if (z2Val > 0 && inputs.top && topVal < z2Val) {
        inputs.top.value = z2Val;
    }

    syncFlash(flashBadge, checkboxes, inputs);
};

/**
 * Handle checkbox cascade logic.
 *
 * Rules:
 * - Checking a higher achievement checks all lower ones
 * - Unchecking a lower achievement unchecks all higher ones
 * - Top always requires all lower achievements
 *
 * @param {HTMLInputElement} changed - The checkbox that changed
 * @param {Object} checkboxes - Object with checkbox elements
 * @param {Object} inputs - Object with attempt input elements
 * @param {HTMLElement} flashBadge - Flash badge element
 */
const cascade = (changed, checkboxes, inputs, flashBadge) => {
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

    // Ensure no gaps in the hierarchy
    for (let i = levels.length - 1; i > 0; i--) {
        if (levels[i].checked && !levels[i - 1].checked) {
            levels[i].checked = false;
        }
    }

    // Top always requires all lower achievements
    const topIdx = checkboxes.top ? levels.findIndex((el) => el === checkboxes.top) : -1;
    if (topIdx >= 0 && levels[topIdx].checked) {
        for (let i = 0; i < topIdx; i++) {
            levels[i].checked = true;
        }
    }

    enforceAttempts(inputs, checkboxes, flashBadge);
    syncFlash(flashBadge, checkboxes, inputs);
};

/**
 * Initialize cascade logic for a boulder card.
 *
 * @param {HTMLElement} card - Boulder card element
 * @param {Function} queueSubmit - Function to queue form submission
 */
export const initializeCascadeLogic = (card, queueSubmit) => {
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

    // Set up increment/decrement buttons
    card.querySelectorAll(".attempt-controls").forEach((controls) => {
        const inputEl = controls.querySelector("input[type='number']");
        const dec = controls.querySelector(".dec");
        const inc = controls.querySelector(".inc");
        if (!inputEl) return;

        dec?.addEventListener("click", () => {
            inputEl.value = Math.max(0, Number(inputEl.value || 0) - 1);
            enforceAttempts(inputs, checkboxes, flashBadge);
            syncFlash(flashBadge, checkboxes, inputs);
            queueSubmit();
        });

        inc?.addEventListener("click", () => {
            inputEl.value = Number(inputEl.value || 0) + 1;
            enforceAttempts(inputs, checkboxes, flashBadge);
            syncFlash(flashBadge, checkboxes, inputs);
            queueSubmit();
        });

        inputEl.addEventListener("input", () => {
            clampValue(inputEl);
            enforceAttempts(inputs, checkboxes, flashBadge);
            syncFlash(flashBadge, checkboxes, inputs);
            queueSubmit();
        });
    });

    // Set up checkbox cascade
    card.querySelectorAll("input[type='checkbox']").forEach((cb) => {
        cb.addEventListener("change", () => {
            cascade(cb, checkboxes, inputs, flashBadge);
            queueSubmit();
        });
    });

    // Initialize state
    enforceAttempts(inputs, checkboxes, flashBadge);
    syncFlash(flashBadge, checkboxes, inputs);
};
