/**
 * Admin Message Polling Module
 *
 * Polls the server for admin broadcast messages and displays them as modal overlays.
 * Messages are shown once per update based on localStorage tracking.
 */
(function() {
    'use strict';

    // Read configuration from body data attributes
    const pollInterval = parseInt(document.body.getAttribute('data-admin-message-poll-interval')) || 30000;
    const jitterMin = parseInt(document.body.getAttribute('data-admin-message-poll-jitter-min')) || 5000;
    const jitterMax = parseInt(document.body.getAttribute('data-admin-message-poll-jitter-max')) || 10000;

    const STORAGE_KEY = 'admin_message_seen_timestamp';
    const API_URL = '/api/admin-message/';

    let pollTimer = null;

    /**
     * Get random jitter value between min and max
     */
    function getJitter(min, max) {
        return Math.random() * (max - min) + min;
    }

    /**
     * Get the last seen message timestamp from localStorage
     */
    function getLastSeenTimestamp() {
        const stored = localStorage.getItem(STORAGE_KEY);
        return stored ? parseFloat(stored) : 0;
    }

    /**
     * Update the last seen message timestamp in localStorage
     */
    function updateLastSeenTimestamp(timestamp) {
        localStorage.setItem(STORAGE_KEY, timestamp.toString());
    }

    /**
     * Create and show the modal overlay
     */
    function showModal(message) {
        // Create backdrop
        const backdrop = document.createElement('div');
        backdrop.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(0, 0, 0, 0.6);
            z-index: 9998;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        `;

        // Create modal box
        const modal = document.createElement('div');
        modal.style.cssText = `
            background-color: ${message.background_color};
            max-width: 90%;
            width: 500px;
            max-height: 80vh;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            padding: 24px;
            position: relative;
            z-index: 9999;
            overflow-y: auto;
            color: #fff;
        `;

        // Create close button
        const closeButton = document.createElement('button');
        closeButton.textContent = '×';
        closeButton.style.cssText = `
            position: absolute;
            top: 8px;
            right: 12px;
            background: none;
            border: none;
            color: #fff;
            font-size: 32px;
            line-height: 1;
            cursor: pointer;
            padding: 0;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0.8;
            transition: opacity 0.2s;
        `;
        closeButton.onmouseover = function() { this.style.opacity = '1'; };
        closeButton.onmouseout = function() { this.style.opacity = '0.8'; };

        // Create heading (if exists)
        if (message.heading) {
            const heading = document.createElement('h2');
            heading.textContent = message.heading;
            heading.style.cssText = `
                margin: 0 0 16px 0;
                font-size: 24px;
                font-weight: bold;
                padding-right: 32px;
                color: #fff;
            `;
            modal.appendChild(heading);
        }

        // Create content (if exists)
        if (message.content) {
            const content = document.createElement('div');
            content.textContent = message.content;
            content.style.cssText = `
                white-space: pre-wrap;
                font-size: 16px;
                line-height: 1.5;
                color: #fff;
                margin-top: ${message.heading ? '0' : '20px'};
            `;
            modal.appendChild(content);
        }

        modal.appendChild(closeButton);

        // Close handlers
        function closeModal() {
            backdrop.remove();
            updateLastSeenTimestamp(message.updated_at);
        }

        closeButton.addEventListener('click', closeModal);
        backdrop.addEventListener('click', function(e) {
            if (e.target === backdrop) {
                closeModal();
            }
        });

        // Add to page
        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);
    }

    /**
     * Fetch admin message from server
     */
    function fetchAdminMessage() {
        fetch(API_URL, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.ok && data.message) {
                const lastSeen = getLastSeenTimestamp();
                if (data.message.updated_at > lastSeen) {
                    showModal(data.message);
                }
            }
        })
        .catch(error => {
            // Silently ignore errors - next poll will retry
            console.debug('Admin message poll error:', error);
        });
    }

    /**
     * Start polling with jitter
     */
    function startPolling() {
        // Initial poll with jitter
        const initialDelay = getJitter(jitterMin, jitterMax);
        setTimeout(() => {
            fetchAdminMessage();
            // Schedule regular polling
            pollTimer = setInterval(fetchAdminMessage, pollInterval);
        }, initialDelay);
    }

    /**
     * Stop polling (for cleanup)
     */
    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    // Initialize on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startPolling);
    } else {
        startPolling();
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', stopPolling);

})();
