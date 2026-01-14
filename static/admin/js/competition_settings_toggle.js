document.addEventListener("DOMContentLoaded", function () {
    const gradingSelect = document.querySelector("select[name='grading_system']");
    if (!gradingSelect) return;

    // Fields shown only for point_based mode
    const pointBasedOnlyFields = ["top_points"];

    // Fields shown only for dynamic modes (both with and without attempts)
    const dynamicOnlyFields = [
        "top_points_10", "top_points_20", "top_points_30", "top_points_40",
        "top_points_50", "top_points_60", "top_points_70", "top_points_80",
        "top_points_90", "top_points_100"
    ];

    // Fields shown for modes with attempt penalty (point_based and dynamic_attempts)
    const attemptPenaltyFields = ["attempt_penalty"];
    const minPointsFields = ["min_top_points", "min_zone_points", "min_zone1_points", "min_zone2_points"];

    // Fields shown for all point-based modes
    const sharedPointFields = [
        "flash_points",
        "zone_points", "zone1_points", "zone2_points"
    ];

    // Helper to get row element for a field
    function getFieldRow(name) {
        const input = document.querySelector(`#id_${name}`);
        return (
            document.querySelector(`.form-row.field-${name}`) ||
            input?.closest(".form-row") ||
            input?.closest(".field-box")
        );
    }

    // Helper to get fieldset and header for rows
    function getFieldsetAndHeader(row) {
        if (!row) return { fieldset: null, header: null };
        const fieldset = row.closest("fieldset");
        const header = fieldset?.previousElementSibling;
        return {
            fieldset,
            header: header?.tagName === "H2" ? header : null
        };
    }

    // Collect all elements
    const pointBasedOnlyRows = pointBasedOnlyFields.map(getFieldRow).filter(Boolean);
    const dynamicOnlyRows = dynamicOnlyFields.map(getFieldRow).filter(Boolean);
    const attemptPenaltyRows = attemptPenaltyFields.map(getFieldRow).filter(Boolean);
    const minPointsRows = minPointsFields.map(getFieldRow).filter(Boolean);
    const sharedRows = sharedPointFields.map(getFieldRow).filter(Boolean);

    // Get unique fieldsets for each category
    const pointBasedOnlyFieldsets = [...new Set(pointBasedOnlyRows.map(r => getFieldsetAndHeader(r).fieldset).filter(Boolean))];
    const dynamicOnlyFieldsets = [...new Set(dynamicOnlyRows.map(r => getFieldsetAndHeader(r).fieldset).filter(Boolean))];
    const attemptPenaltyFieldsets = [...new Set(attemptPenaltyRows.map(r => getFieldsetAndHeader(r).fieldset).filter(Boolean))];
    const minPointsFieldsets = [...new Set(minPointsRows.map(r => getFieldsetAndHeader(r).fieldset).filter(Boolean))];
    const sharedFieldsets = [...new Set(sharedRows.map(r => getFieldsetAndHeader(r).fieldset).filter(Boolean))];

    function toggleFields() {
        const mode = gradingSelect.value;
        const isPointBased = mode === "point_based";
        const isDynamic = mode === "point_based_dynamic";
        const isDynamicAttempts = mode === "point_based_dynamic_attempts";
        const showPointFields = isPointBased || isDynamic || isDynamicAttempts;
        const showDynamicFields = isDynamic || isDynamicAttempts;
        const showAttemptPenalty = isPointBased || isDynamicAttempts;

        // Toggle point_based only fieldsets (Top-Punkte)
        pointBasedOnlyFieldsets.forEach((fs) => {
            fs.style.display = isPointBased ? "" : "none";
            const header = fs.previousElementSibling;
            if (header?.tagName === "H2") header.style.display = isPointBased ? "" : "none";
        });

        // Toggle dynamic only fieldsets (Percentage tiers)
        dynamicOnlyFieldsets.forEach((fs) => {
            fs.style.display = showDynamicFields ? "" : "none";
            const header = fs.previousElementSibling;
            if (header?.tagName === "H2") header.style.display = showDynamicFields ? "" : "none";
        });

        // Toggle attempt penalty fieldsets (Strafen)
        attemptPenaltyFieldsets.forEach((fs) => {
            fs.style.display = showAttemptPenalty ? "" : "none";
            const header = fs.previousElementSibling;
            if (header?.tagName === "H2") header.style.display = showAttemptPenalty ? "" : "none";
        });

        // Toggle min points fieldsets (shown when attempt penalty is active)
        minPointsFieldsets.forEach((fs) => {
            fs.style.display = showAttemptPenalty ? "" : "none";
            const header = fs.previousElementSibling;
            if (header?.tagName === "H2") header.style.display = showAttemptPenalty ? "" : "none";
        });

        // Toggle shared fieldsets (Flash, Zones)
        sharedFieldsets.forEach((fs) => {
            fs.style.display = showPointFields ? "" : "none";
            const header = fs.previousElementSibling;
            if (header?.tagName === "H2") header.style.display = showPointFields ? "" : "none";
        });
    }

    gradingSelect.addEventListener("change", toggleFields);
    toggleFields();
});
