/**
 * Offline sync: triggers retry when connection is restored.
 *
 * The form DOM is the queue — it always holds the user's current intended state.
 * When the network returns, if state.dirty is true (unsaved changes exist), we
 * trigger queueSubmitFn() which debounces and then calls submitAjax().
 *
 * @param {Object} state - Global state (state.dirty, state.canSubmit)
 * @param {Function} queueSubmitFn - Schedules a save attempt
 * @param {Function} showStatusFn - Shows a toast notification
 */
export const initOfflineSync = (state, queueSubmitFn, showStatusFn) => {
    window.addEventListener('online', () => {
        if (state.dirty && state.canSubmit) {
            showStatusFn("Verbindung wiederhergestellt – speichert ...", "pending");
            queueSubmitFn();
        }
    });

    window.addEventListener('offline', () => {
        if (state.dirty) {
            showStatusFn(
                "Offline \u2013 wird gesendet sobald Verbindung besteht",
                "offline"
            );
        }
    });
};
