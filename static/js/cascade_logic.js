/**
 * Cascade logic module for attempt validation and checkbox hierarchy.
 *
 * Semantics:
 *   top_attempts  = total attempts on the boulder
 *   zone_attempts = attempt number on which that zone was FIRST reached;
 *                   if the zone is unreached, zone_attempts mirrors top_attempts
 *
 * Invariant: zone1_att <= zone2_att <= top_att (for reached zones)
 *
 * When top_att changes:
 *   - top_att is constrained to >= any reached zone_att (zones are authoritative)
 *   - Unreached zones mirror the (possibly clamped) top_att
 *   - Top checkbox is not affected
 *
 * When a zone attempt input is adjusted while that zone is unchecked:
 *   - Treated as adjusting top_att (since unchecked zone_att == top_att)
 *
 * When zone_att is adjusted while the zone is checked:
 *   - Higher zone_atts and top_att are pushed UP if the value increases past them
 *   - Lower zone_atts are pulled DOWN if the value decreases below them
 *   - Minimum att = 1 for reached zones
 *
 * Checkbox cascade:
 *   - Checking a harder milestone checks all easier ones
 *   - Unchecking an easier milestone unchecks all harder ones
 *   - Unchecking top leaves zone checkboxes unchanged
 */

const clampValue = (inputEl) => {
    if (!inputEl) return 0;
    let val = Number(inputEl.value || 0);
    if (Number.isNaN(val) || val < 0) val = 0;
    inputEl.value = val;
    return val;
};

const isFlashState = (checkboxes, inputs) => {
    if (!checkboxes.top || !checkboxes.top.checked) return false;
    const candidates = [inputs.top, inputs.z2, inputs.z1].filter(Boolean);
    if (!candidates.length) return false;
    return candidates.every((el) => Number(el.value || 0) === 1);
};

const syncFlash = (flashBadge, checkboxes, inputs) => {
    if (!flashBadge || !inputs.top || !checkboxes.top) return;
    flashBadge.classList.toggle("show", isFlashState(checkboxes, inputs));
};

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

    // ------------------------------------------------------------------
    // Normalizers — called after their specific input changes.
    // All assume the zone IS checked (unchecked zones redirect to top).
    // ------------------------------------------------------------------

    // Called when zone1_att changes while zone1 is checked.
    // Enforces minimum 1; pushes z2 and top UP if z1 increased past them.
    const normalizeAfterZ1 = () => {
        let z1 = clampValue(inputs.z1);
        if (z1 < 1) { inputs.z1.value = 1; z1 = 1; }

        if (inputs.z2 && checkboxes.z2?.checked && Number(inputs.z2.value || 0) < z1) {
            inputs.z2.value = z1;
        }
        const z2v = inputs.z2 ? Number(inputs.z2.value || 0) : 0;
        let tp = Number(inputs.top?.value || 0);
        const needed = Math.max(z1, z2v);
        if (inputs.top && tp < needed) { inputs.top.value = needed; tp = needed; }

        // Keep unreached z2 mirror in sync if top changed
        if (inputs.z2 && !checkboxes.z2?.checked) inputs.z2.value = tp;
    };

    // Called when zone2_att changes while zone2 is checked.
    // Enforces minimum 1; pushes top UP if z2 increased; pulls z1 DOWN if z2 decreased below z1.
    const normalizeAfterZ2 = () => {
        if (!inputs.z2) return;
        let z2 = clampValue(inputs.z2);
        if (z2 < 1) { inputs.z2.value = 1; z2 = 1; }

        let tp = Number(inputs.top?.value || 0);
        if (tp < z2) { inputs.top.value = z2; tp = z2; }

        if (inputs.z1 && checkboxes.z1?.checked && Number(inputs.z1.value || 0) > z2) {
            inputs.z1.value = z2;
        }

        // Keep unreached z1 mirror in sync if top changed
        if (inputs.z1 && !checkboxes.z1?.checked) inputs.z1.value = tp;
    };

    // Called when top_att changes.
    // Zones are authoritative: top_att cannot go below any reached zone_att.
    // Unreached zones mirror the (possibly clamped) top_att.
    // Top checkbox is not affected.
    const normalizeAfterTop = () => {
        let tp = clampValue(inputs.top);

        if (inputs.z2 && checkboxes.z2?.checked) {
            const z2 = Number(inputs.z2.value || 0);
            if (z2 > tp) { inputs.top.value = z2; tp = z2; }
        }
        if (inputs.z1 && checkboxes.z1?.checked) {
            const z1 = Number(inputs.z1.value || 0);
            if (z1 > tp) { inputs.top.value = z1; tp = z1; }
        }

        if (inputs.z2 && !checkboxes.z2?.checked) inputs.z2.value = tp;
        if (inputs.z1 && !checkboxes.z1?.checked) inputs.z1.value = tp;
    };

    // One-time init: apply invariants to whatever state is loaded from the server.
    const initNormalize = () => {
        let tp = clampValue(inputs.top);

        // Mirror unreached zones first
        if (inputs.z1 && !checkboxes.z1?.checked) inputs.z1.value = tp;
        if (inputs.z2 && !checkboxes.z2?.checked) inputs.z2.value = tp;

        // Enforce minimum att=1 for reached zones
        if (inputs.z1 && checkboxes.z1?.checked && Number(inputs.z1.value || 0) < 1) {
            inputs.z1.value = 1;
        }
        if (inputs.z2 && checkboxes.z2?.checked && Number(inputs.z2.value || 0) < 1) {
            inputs.z2.value = 1;
        }

        // Ensure z1_att <= z2_att (only when both are reached)
        if (inputs.z1 && inputs.z2 && checkboxes.z1?.checked && checkboxes.z2?.checked) {
            const z1 = Number(inputs.z1.value || 0);
            if (Number(inputs.z2.value || 0) < z1) inputs.z2.value = z1;
        }

        // Ensure top_att >= all reached zone_atts
        const z1v = inputs.z1 && checkboxes.z1?.checked ? Number(inputs.z1.value || 0) : 0;
        const z2v = inputs.z2 && checkboxes.z2?.checked ? Number(inputs.z2.value || 0) : 0;
        const needed = Math.max(z1v, z2v);
        if (inputs.top && tp < needed) {
            inputs.top.value = needed;
            tp = needed;
        }

        // Re-mirror unreached zones in case top changed
        if (inputs.z2 && !checkboxes.z2?.checked) inputs.z2.value = tp;
        if (inputs.z1 && !checkboxes.z1?.checked) inputs.z1.value = tp;
    };

    // ------------------------------------------------------------------
    // Checkbox handler
    // ------------------------------------------------------------------

    const onCheckChange = (changedCb) => {
        const tp = () => Number(inputs.top?.value || 0);

        if (changedCb.checked) {
            // Ensure total attempts >= 1 when any milestone is first reached
            if (inputs.top && tp() < 1) inputs.top.value = 1;

            // Cascade DOWN: checking a harder milestone checks all easier ones
            if (changedCb === checkboxes.top) {
                if (checkboxes.z2) checkboxes.z2.checked = true;
                if (checkboxes.z1) checkboxes.z1.checked = true;
            } else if (changedCb === checkboxes.z2) {
                if (checkboxes.z1) checkboxes.z1.checked = true;
            }

            // Ensure all now-checked zones have att >= 1
            const curTp = tp();
            if (checkboxes.z1?.checked && inputs.z1 && Number(inputs.z1.value || 0) < 1) {
                inputs.z1.value = curTp || 1;
            }
            if (checkboxes.z2?.checked && inputs.z2 && Number(inputs.z2.value || 0) < 1) {
                inputs.z2.value = curTp || 1;
            }
        } else {
            const curTp = tp();
            if (changedCb === checkboxes.z1) {
                // Cascade UP: unchecking zone1 also unchecks zone2 and top
                if (checkboxes.z2) checkboxes.z2.checked = false;
                if (checkboxes.top) checkboxes.top.checked = false;
                if (inputs.z1) inputs.z1.value = curTp;
                if (inputs.z2) inputs.z2.value = curTp;
            } else if (changedCb === checkboxes.z2) {
                // Cascade UP: unchecking zone2 also unchecks top
                if (checkboxes.top) checkboxes.top.checked = false;
                if (inputs.z2) inputs.z2.value = curTp;
            }
            // Unchecking top: zone checkboxes and their atts are unchanged
        }

        syncFlash(flashBadge, checkboxes, inputs);
    };

    // ------------------------------------------------------------------
    // Wire up events
    // ------------------------------------------------------------------

    // Returns whether this input belongs to an unchecked zone.
    // Unchecked zone inputs redirect their +/- to top_att.
    const isUncheckedZone = (inputEl) => {
        if (inputEl === inputs.z1 && !checkboxes.z1?.checked) return true;
        if (inputEl === inputs.z2 && !checkboxes.z2?.checked) return true;
        return false;
    };

    card.querySelectorAll(".attempt-controls").forEach((controls) => {
        const inputEl = controls.querySelector("input[type='number']");
        const dec = controls.querySelector(".dec");
        const inc = controls.querySelector(".inc");
        if (!inputEl) return;

        dec?.addEventListener("click", () => {
            if (isUncheckedZone(inputEl)) {
                // Redirect to top_att: unchecked zone_att == top_att
                inputs.top.value = Math.max(0, Number(inputs.top.value || 0) - 1);
                normalizeAfterTop();
            } else {
                inputEl.value = Math.max(0, Number(inputEl.value || 0) - 1);
                if (inputEl === inputs.top) normalizeAfterTop();
                else if (inputEl === inputs.z1) normalizeAfterZ1();
                else if (inputEl === inputs.z2) normalizeAfterZ2();
            }
            syncFlash(flashBadge, checkboxes, inputs);
            queueSubmit();
        });

        inc?.addEventListener("click", () => {
            if (isUncheckedZone(inputEl)) {
                inputs.top.value = Number(inputs.top.value || 0) + 1;
                normalizeAfterTop();
            } else {
                inputEl.value = Number(inputEl.value || 0) + 1;
                if (inputEl === inputs.top) normalizeAfterTop();
                else if (inputEl === inputs.z1) normalizeAfterZ1();
                else if (inputEl === inputs.z2) normalizeAfterZ2();
            }
            syncFlash(flashBadge, checkboxes, inputs);
            queueSubmit();
        });

        inputEl.addEventListener("input", () => {
            clampValue(inputEl);
            if (isUncheckedZone(inputEl)) {
                inputs.top.value = inputEl.value;
                normalizeAfterTop();
            } else {
                if (inputEl === inputs.top) normalizeAfterTop();
                else if (inputEl === inputs.z1) normalizeAfterZ1();
                else if (inputEl === inputs.z2) normalizeAfterZ2();
            }
            syncFlash(flashBadge, checkboxes, inputs);
            queueSubmit();
        });
    });

    card.querySelectorAll("input[type='checkbox']").forEach((cb) => {
        cb.addEventListener("change", () => {
            onCheckChange(cb);
            queueSubmit();
        });
    });

    initNormalize();
    syncFlash(flashBadge, checkboxes, inputs);
};
