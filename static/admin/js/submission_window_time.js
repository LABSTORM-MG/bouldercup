/**
 * Override Django admin's "Now" button behavior for time fields
 * to only fill hours and minutes (no seconds).
 */
document.addEventListener("DOMContentLoaded", function () {
    // Override DateTimeShortcuts.handleClockQuicklink if it exists
    if (typeof DateTimeShortcuts !== "undefined") {
        const originalHandleClockQuicklink = DateTimeShortcuts.handleClockQuicklink;
        DateTimeShortcuts.handleClockQuicklink = function (num, mode) {
            if (mode === "now") {
                // Custom "Now" handling without seconds
                const d = new Date();
                const hours = String(d.getHours()).padStart(2, "0");
                const minutes = String(d.getMinutes()).padStart(2, "0");
                DateTimeShortcuts.clockInputs[num].value = hours + ":" + minutes;
                DateTimeShortcuts.dismissClock(num);
                return;
            }
            // For other modes (like specific times), use original behavior
            if (originalHandleClockQuicklink) {
                originalHandleClockQuicklink.call(DateTimeShortcuts, num, mode);
            }
        };
    }

    // Also handle direct clicks on "Now" links that may bypass DateTimeShortcuts
    document.addEventListener("click", function (e) {
        const link = e.target.closest("a");
        if (!link) return;

        // Check if this is a "Now" or "Jetzt" link (German translation)
        const text = link.textContent.trim().toLowerCase();
        if (text === "now" || text === "jetzt") {
            // Find the closest datetime shortcuts container
            const shortcuts = link.closest(".datetimeshortcuts, .timezonewarning");
            if (!shortcuts) return;

            // Look for the time input specifically - it's the second input in a datetime pair
            // Find the parent field container
            const fieldBox = shortcuts.closest(".field-submission_start, .field-submission_end") ||
                           shortcuts.closest(".form-row");

            if (fieldBox) {
                // Get all text inputs in this field - date is first, time is second
                const inputs = fieldBox.querySelectorAll("input[type='text']");
                const timeInput = inputs.length >= 2 ? inputs[1] : null;

                if (timeInput) {
                    e.preventDefault();
                    e.stopPropagation();

                    const d = new Date();
                    const hours = String(d.getHours()).padStart(2, "0");
                    const minutes = String(d.getMinutes()).padStart(2, "0");
                    timeInput.value = hours + ":" + minutes;

                    // Trigger change event for form validation
                    timeInput.dispatchEvent(new Event("change", { bubbles: true }));
                }
            }
        }
    }, true);
});
