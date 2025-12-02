document.addEventListener("DOMContentLoaded", function () {
    const gradingSelect = document.querySelector("select[name='grading_system']");

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
