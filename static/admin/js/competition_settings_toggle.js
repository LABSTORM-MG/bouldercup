document.addEventListener("DOMContentLoaded", function () {
    const gradingSelect = document.querySelector("select[name='grading_system']");
    const rows = [
        "div.field-top_points",
        "div.field-zone_points",
        "div.field-flash_points",
        "div.field-attempt_penalty",
    ].map((sel) => document.querySelector(sel));

    const toggleFields = () => {
        const isCustom = gradingSelect && gradingSelect.value === "custom";
        rows.forEach((row) => {
            if (!row) return;
            row.style.display = isCustom ? "" : "none";
        });
    };

    if (gradingSelect) {
        gradingSelect.addEventListener("change", toggleFields);
        toggleFields();
    }
});
