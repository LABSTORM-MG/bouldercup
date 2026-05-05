(function () {
    const POLL_INTERVAL_MS = 60000;
    const INITIAL_DELAY_MS = 15000;

    function applyStats(stats) {
        Object.entries(stats).forEach(([boulderId, s]) => {
            const card = document.querySelector(`.boulder-card[data-boulder="${boulderId}"]`);
            if (!card) return;
            const tried  = card.querySelector('[data-stat="tried"]');
            const topped = card.querySelector('[data-stat="topped"]');
            if (tried)  tried.textContent  = `${s.tried_pct}% versucht`;
            if (topped) topped.textContent = `${s.topped_pct}% getopped`;
        });
    }

    async function fetchStats() {
        try {
            const resp = await fetch('/api/boulder-stats/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!resp.ok) return;
            const data = await resp.json();
            if (data.stats) applyStats(data.stats);
        } catch (_) {
            // Network error — next poll will retry
        }
    }

    setTimeout(() => {
        fetchStats();
        setInterval(fetchStats, POLL_INTERVAL_MS);
    }, INITIAL_DELAY_MS);
})();
