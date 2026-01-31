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

    // Inject CSS animations
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: scale(0.95) translateY(-20px);
            }
            to {
                opacity: 1;
                transform: scale(1) translateY(0);
            }
        }
        @keyframes fadeOut {
            from { opacity: 1; }
            to { opacity: 0; }
        }
        @keyframes slideOut {
            from {
                opacity: 1;
                transform: scale(1) translateY(0);
            }
            to {
                opacity: 0;
                transform: scale(0.95) translateY(-20px);
            }
        }
    `;
    document.head.appendChild(style);

    /**
     * Adjust color brightness
     */
    function adjustBrightness(color, percent) {
        // Simple brightness adjustment for hex colors
        const num = parseInt(color.replace('#', ''), 16);
        const r = Math.max(0, Math.min(255, ((num >> 16) & 0xff) + percent));
        const g = Math.max(0, Math.min(255, ((num >> 8) & 0xff) + percent));
        const b = Math.max(0, Math.min(255, (num & 0xff) + percent));
        return '#' + ((r << 16) | (g << 8) | b).toString(16).padStart(6, '0');
    }

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
            background-color: rgba(0, 0, 0, 0.75);
            z-index: 9998;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            animation: fadeIn 0.2s ease-out;
        `;

        // Create modal box
        const modal = document.createElement('div');
        modal.style.cssText = `
            background: linear-gradient(135deg, ${message.background_color} 0%, ${adjustBrightness(message.background_color, -15)} 100%);
            max-width: 90%;
            width: 600px;
            max-height: 85vh;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.1);
            padding: 0;
            position: relative;
            z-index: 9999;
            overflow: hidden;
            color: #fff;
            animation: slideIn 0.3s ease-out;
        `;

        // Create header section
        const header = document.createElement('div');
        header.style.cssText = `
            padding: 28px 32px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.15);
            background: rgba(0, 0, 0, 0.1);
        `;

        // Create close button
        const closeButton = document.createElement('button');
        closeButton.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
            </svg>
        `;
        closeButton.style.cssText = `
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.2);
            border: none;
            color: #fff;
            cursor: pointer;
            padding: 8px;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            transition: all 0.2s;
            backdrop-filter: blur(10px);
        `;
        closeButton.onmouseover = function() {
            this.style.background = 'rgba(255, 255, 255, 0.2)';
            this.style.transform = 'scale(1.1)';
        };
        closeButton.onmouseout = function() {
            this.style.background = 'rgba(0, 0, 0, 0.2)';
            this.style.transform = 'scale(1)';
        };

        // Create heading (if exists)
        if (message.heading) {
            const heading = document.createElement('h2');
            heading.textContent = message.heading;
            heading.style.cssText = `
                margin: 0;
                font-size: 28px;
                font-weight: 700;
                color: #fff;
                letter-spacing: -0.5px;
                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            `;
            header.appendChild(heading);
        }

        modal.appendChild(header);

        // Create content section (if exists)
        if (message.content) {
            const contentWrapper = document.createElement('div');
            contentWrapper.style.cssText = `
                padding: 32px;
                overflow-y: auto;
                max-height: calc(85vh - 120px);
            `;

            const content = document.createElement('div');
            content.textContent = message.content;
            content.style.cssText = `
                white-space: pre-wrap;
                font-size: 17px;
                line-height: 1.6;
                color: rgba(255, 255, 255, 0.95);
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
            `;
            contentWrapper.appendChild(content);
            modal.appendChild(contentWrapper);
        } else {
            // If no content, adjust header padding
            header.style.borderBottom = 'none';
        }

        modal.appendChild(closeButton);

        // Prevent clicks on modal from closing it
        modal.addEventListener('click', function(e) {
            e.stopPropagation();
        });

        // Close handlers
        function closeModal() {
            backdrop.style.animation = 'fadeOut 0.2s ease-out';
            modal.style.animation = 'slideOut 0.2s ease-out';
            setTimeout(() => {
                backdrop.remove();
                updateLastSeenTimestamp(message.updated_at);
            }, 200);
        }

        closeButton.addEventListener('click', closeModal);

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
