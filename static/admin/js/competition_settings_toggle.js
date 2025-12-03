document.addEventListener("DOMContentLoaded", function () {
    const gradingSelect = document.querySelector("select[name='grading_system']");
    const pointFields = [
        "top_points",
        "flash_points",
        "min_top_points",
        "zone_points",
        "zone1_points",
        "zone2_points",
        "min_zone_points",
        "min_zone1_points",
        "min_zone2_points",
        "attempt_penalty",
    ];
    const rows = pointFields
        .map((name) => {
            const input = document.querySelector(`#id_${name}`);
            return (
                document.querySelector(`.form-row.field-${name}`) ||
                input?.closest(".form-row") ||
                input?.closest(".field-box")
            );
        })
        .filter(Boolean);
    const sectionFieldsets = Array.from(new Set(rows.map((row) => row.closest("fieldset")).filter(Boolean)));
    const sectionHeaders = sectionFieldsets
        .map((fs) => fs.previousElementSibling)
        .filter((el) => el && el.tagName === "H2");

    const toggleFields = () => {
        const isPointBased = gradingSelect && gradingSelect.value === "point_based";
        rows.forEach((row) => {
            if (!row) return;
            row.style.display = isPointBased ? "" : "none";
        });
        sectionFieldsets.forEach((fs) => {
            fs.style.display = isPointBased ? "" : "none";
        });
        sectionHeaders.forEach((header) => {
            header.style.display = isPointBased ? "" : "none";
        });
    };

    if (gradingSelect) {
        gradingSelect.addEventListener("change", toggleFields);
        toggleFields();
    }
});
