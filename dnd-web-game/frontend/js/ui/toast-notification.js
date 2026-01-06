/**
 * D&D Combat Engine - Toast Notification System
 * Provides user-facing feedback for errors and success messages
 */

class ToastNotification {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // Create container on DOM ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.createContainer());
        } else {
            this.createContainer();
        }
        this.injectStyles();
    }

    createContainer() {
        if (this.container) return;

        this.container = document.createElement('div');
        this.container.id = 'toast-container';
        document.body.appendChild(this.container);
    }

    injectStyles() {
        if (document.getElementById('toast-notification-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'toast-notification-styles';
        styles.textContent = `
            #toast-container {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: 10px;
                pointer-events: none;
            }

            .toast {
                padding: 12px 20px;
                border-radius: 6px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 14px;
                max-width: 350px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                pointer-events: auto;
                animation: toastSlideIn 0.3s ease-out;
                display: flex;
                align-items: center;
                gap: 10px;
            }

            .toast.toast-exit {
                animation: toastSlideOut 0.3s ease-in forwards;
            }

            .toast-error {
                background: linear-gradient(135deg, #8b0000, #a02020);
                color: #fff;
                border-left: 4px solid #ff4444;
            }

            .toast-success {
                background: linear-gradient(135deg, #1a472a, #2d5a3d);
                color: #fff;
                border-left: 4px solid #4caf50;
            }

            .toast-warning {
                background: linear-gradient(135deg, #5c4a1f, #7a6428);
                color: #fff;
                border-left: 4px solid #ffc107;
            }

            .toast-info {
                background: linear-gradient(135deg, #1a3a5c, #2a4a7c);
                color: #fff;
                border-left: 4px solid #2196f3;
            }

            .toast-icon {
                font-size: 18px;
            }

            .toast-close {
                margin-left: auto;
                background: none;
                border: none;
                color: rgba(255, 255, 255, 0.7);
                cursor: pointer;
                font-size: 18px;
                padding: 0 4px;
            }

            .toast-close:hover {
                color: #fff;
            }

            @keyframes toastSlideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }

            @keyframes toastSlideOut {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(100%);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(styles);
    }

    /**
     * Show a toast notification
     * @param {string} message - Message to display
     * @param {string} type - Type: 'error', 'success', 'warning', 'info'
     * @param {number} duration - Duration in ms (0 for persistent)
     */
    show(message, type = 'info', duration = 4000) {
        if (!this.container) {
            this.createContainer();
        }

        const icons = {
            error: '⚠️',
            success: '✓',
            warning: '⚡',
            info: 'ℹ️'
        };

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
            <span class="toast-message">${this.escapeHtml(message)}</span>
            <button class="toast-close" aria-label="Close notification">&times;</button>
        `;

        // Close button handler
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => this.dismiss(toast));

        this.container.appendChild(toast);

        // Auto-dismiss after duration
        if (duration > 0) {
            setTimeout(() => this.dismiss(toast), duration);
        }

        return toast;
    }

    dismiss(toast) {
        if (!toast || toast.classList.contains('toast-exit')) return;

        toast.classList.add('toast-exit');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300); // Match animation duration
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Convenience methods
    error(message, duration = 6000) {
        return this.show(message, 'error', duration);
    }

    success(message, duration = 3000) {
        return this.show(message, 'success', duration);
    }

    warning(message, duration = 5000) {
        return this.show(message, 'warning', duration);
    }

    info(message, duration = 4000) {
        return this.show(message, 'info', duration);
    }
}

// Export singleton instance
export const toast = new ToastNotification();
export default toast;
