/**
 * D&D Combat Engine - Error Display UI
 * Visual components for displaying errors to users.
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import { errorHandler, ErrorSeverity } from '../core/error-handler.js';

/**
 * Error Modal Component
 * Full-screen modal for critical errors requiring user attention.
 */
class ErrorModal {
    constructor() {
        this.container = null;
        this.isVisible = false;
        this.currentData = null;

        this.init();
    }

    init() {
        this.createContainer();
        this.setupEventListeners();
    }

    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'error-modal';
        this.container.className = 'error-modal hidden';
        this.container.innerHTML = `
            <div class="error-modal-backdrop"></div>
            <div class="error-modal-content">
                <div class="error-modal-header">
                    <span class="error-icon">!</span>
                    <h3 class="error-title">Error</h3>
                </div>
                <div class="error-modal-body">
                    <p class="error-message"></p>
                    <p class="error-details"></p>
                    <div class="error-id"></div>
                </div>
                <div class="error-modal-actions"></div>
            </div>
        `;

        document.body.appendChild(this.container);

        // Close on backdrop click if dismissable
        this.container.querySelector('.error-modal-backdrop').addEventListener('click', () => {
            if (this.currentData?.dismissable) {
                this.hide();
            }
        });
    }

    setupEventListeners() {
        eventBus.on(EVENTS.UI_MODAL_OPENED, ({ modal, data }) => {
            if (modal === 'error') {
                this.show(data);
            }
        });

        eventBus.on(EVENTS.UI_MODAL_CLOSED, ({ modal }) => {
            if (modal === 'error') {
                this.hide();
            }
        });
    }

    show(data) {
        this.currentData = data;

        // Update content
        this.container.querySelector('.error-title').textContent = data.title || 'Error';
        this.container.querySelector('.error-message').textContent = data.message || 'An error occurred';

        const detailsEl = this.container.querySelector('.error-details');
        if (data.details) {
            detailsEl.textContent = data.details;
            detailsEl.classList.remove('hidden');
        } else {
            detailsEl.classList.add('hidden');
        }

        const errorIdEl = this.container.querySelector('.error-id');
        if (data.errorId) {
            errorIdEl.textContent = `Error ID: ${data.errorId}`;
            errorIdEl.classList.remove('hidden');
        } else {
            errorIdEl.classList.add('hidden');
        }

        // Create action buttons
        const actionsContainer = this.container.querySelector('.error-modal-actions');
        actionsContainer.innerHTML = '';

        const actions = data.actions || [{ label: 'OK', action: () => {} }];
        actions.forEach((action, index) => {
            const button = document.createElement('button');
            button.className = index === 0 ? 'error-btn primary' : 'error-btn secondary';
            button.textContent = action.label;
            button.addEventListener('click', () => {
                if (action.action) action.action();
                this.hide();
            });
            actionsContainer.appendChild(button);
        });

        // Show modal
        this.container.classList.remove('hidden');
        this.isVisible = true;

        // Focus first button
        const firstButton = actionsContainer.querySelector('button');
        if (firstButton) firstButton.focus();
    }

    hide() {
        this.container.classList.add('hidden');
        this.isVisible = false;
        this.currentData = null;

        eventBus.emit(EVENTS.UI_MODAL_CLOSED, { modal: 'error' });
    }
}

/**
 * Network Status Indicator
 * Shows connection status in the UI.
 */
class NetworkStatusIndicator {
    constructor() {
        this.container = null;
        this.isOnline = navigator.onLine;
        this.reconnectAttempts = 0;

        this.init();
    }

    init() {
        this.createContainer();
        this.setupEventListeners();
        this.updateStatus(this.isOnline);
    }

    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'network-status';
        this.container.className = 'network-status hidden';
        this.container.innerHTML = `
            <span class="status-icon"></span>
            <span class="status-text"></span>
            <button class="retry-btn hidden">Retry</button>
        `;

        document.body.appendChild(this.container);

        this.container.querySelector('.retry-btn').addEventListener('click', () => {
            this.attemptReconnect();
        });
    }

    setupEventListeners() {
        // Browser online/offline events
        window.addEventListener('online', () => this.updateStatus(true));
        window.addEventListener('offline', () => this.updateStatus(false));

        // App-level connection events
        eventBus.on('app:offlineMode', ({ enabled }) => {
            this.updateStatus(!enabled);
        });

        eventBus.on('app:reconnected', () => {
            this.updateStatus(true);
            this.reconnectAttempts = 0;
        });

        eventBus.on(EVENTS.API_ERROR, () => {
            this.showTemporary('warning', 'Connection issue');
        });
    }

    updateStatus(online) {
        this.isOnline = online;

        if (online) {
            this.container.classList.add('hidden');
            this.container.classList.remove('offline', 'warning');
        } else {
            this.container.classList.remove('hidden');
            this.container.classList.add('offline');
            this.container.querySelector('.status-icon').textContent = '!';
            this.container.querySelector('.status-text').textContent = 'Offline';
            this.container.querySelector('.retry-btn').classList.remove('hidden');
        }
    }

    showTemporary(type, message, duration = 3000) {
        this.container.classList.remove('hidden', 'offline', 'warning');
        this.container.classList.add(type);
        this.container.querySelector('.status-icon').textContent = type === 'warning' ? '!' : '.';
        this.container.querySelector('.status-text').textContent = message;
        this.container.querySelector('.retry-btn').classList.add('hidden');

        setTimeout(() => {
            if (this.isOnline) {
                this.container.classList.add('hidden');
            }
        }, duration);
    }

    async attemptReconnect() {
        this.container.querySelector('.status-text').textContent = 'Reconnecting...';
        this.container.querySelector('.retry-btn').classList.add('hidden');

        this.reconnectAttempts++;

        try {
            const response = await fetch('/api/health', { timeout: 5000 });
            if (response.ok) {
                this.updateStatus(true);
                eventBus.emit('app:reconnected');
            } else {
                throw new Error('Health check failed');
            }
        } catch (e) {
            this.container.querySelector('.status-text').textContent =
                `Offline (attempt ${this.reconnectAttempts})`;
            this.container.querySelector('.retry-btn').classList.remove('hidden');
        }
    }
}

/**
 * Inline Error Display
 * For form validation errors shown next to fields.
 */
class InlineErrorDisplay {
    constructor() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        eventBus.on('validation:error', ({ errors, field }) => {
            this.showErrors(errors, field);
        });

        eventBus.on('validation:clear', ({ field }) => {
            this.clearErrors(field);
        });
    }

    showErrors(errors, targetField = null) {
        // Clear previous errors
        document.querySelectorAll('.inline-error').forEach(el => el.remove());
        document.querySelectorAll('.has-error').forEach(el => el.classList.remove('has-error'));

        errors.forEach(error => {
            if (targetField && error.field !== targetField) return;

            const fieldEl = document.querySelector(`[name="${error.field}"], #${error.field}`);
            if (fieldEl) {
                // Add error class to field
                fieldEl.classList.add('has-error');

                // Create error message
                const errorEl = document.createElement('span');
                errorEl.className = 'inline-error';
                errorEl.textContent = error.message;

                // Insert after field
                fieldEl.parentNode.insertBefore(errorEl, fieldEl.nextSibling);
            }
        });
    }

    clearErrors(field = null) {
        if (field) {
            const fieldEl = document.querySelector(`[name="${field}"], #${field}`);
            if (fieldEl) {
                fieldEl.classList.remove('has-error');
                const errorEl = fieldEl.parentNode.querySelector('.inline-error');
                if (errorEl) errorEl.remove();
            }
        } else {
            document.querySelectorAll('.inline-error').forEach(el => el.remove());
            document.querySelectorAll('.has-error').forEach(el => el.classList.remove('has-error'));
        }
    }
}

/**
 * Enhanced Toast Notification
 * Improved toast with error-specific styling.
 */
class ErrorToast {
    constructor() {
        this.container = null;
        this.queue = [];
        this.isShowing = false;

        this.init();
    }

    init() {
        this.createContainer();
        this.setupEventListeners();
    }

    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'error-toast-container';
        this.container.className = 'error-toast-container';
        document.body.appendChild(this.container);
    }

    setupEventListeners() {
        eventBus.on(EVENTS.UI_NOTIFICATION, (data) => {
            this.show(data);
        });
    }

    show(data) {
        const toast = document.createElement('div');
        toast.className = `error-toast ${data.type || 'info'}`;

        const icon = this.getIcon(data.type);
        toast.innerHTML = `
            <span class="toast-icon">${icon}</span>
            <span class="toast-message">${this.escapeHtml(data.message)}</span>
            ${data.action ? `<button class="toast-action">${this.escapeHtml(data.action.label)}</button>` : ''}
            <button class="toast-close">x</button>
        `;

        // Action button handler
        if (data.action) {
            toast.querySelector('.toast-action').addEventListener('click', () => {
                data.action.callback();
                this.dismiss(toast);
            });
        }

        // Close button handler
        toast.querySelector('.toast-close').addEventListener('click', () => {
            this.dismiss(toast);
        });

        this.container.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            toast.classList.add('show');
        });

        // Auto-dismiss
        if (data.duration !== 0) {
            setTimeout(() => {
                this.dismiss(toast);
            }, data.duration || 5000);
        }
    }

    dismiss(toast) {
        toast.classList.remove('show');
        toast.classList.add('hide');

        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }

    getIcon(type) {
        const icons = {
            info: 'i',
            success: '.',
            warning: '!',
            error: 'X'
        };
        return icons[type] || icons.info;
    }

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

// CSS Styles for error components
const styles = `
/* Error Modal */
.error-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 10000;
    display: flex;
    align-items: center;
    justify-content: center;
}

.error-modal.hidden {
    display: none;
}

.error-modal-backdrop {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.8);
}

.error-modal-content {
    position: relative;
    width: 90%;
    max-width: 450px;
    background: linear-gradient(180deg, #2a1a1a 0%, #1a1a2e 100%);
    border: 2px solid #e74c3c;
    border-radius: 12px;
    padding: 24px;
    animation: errorSlideIn 0.3s ease-out;
}

@keyframes errorSlideIn {
    from {
        opacity: 0;
        transform: scale(0.9) translateY(-20px);
    }
    to {
        opacity: 1;
        transform: scale(1) translateY(0);
    }
}

.error-modal-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
}

.error-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    background: #e74c3c;
    border-radius: 50%;
    color: white;
    font-size: 24px;
    font-weight: bold;
}

.error-title {
    margin: 0;
    color: #e74c3c;
    font-size: 1.3rem;
}

.error-modal-body {
    margin-bottom: 20px;
}

.error-message {
    color: #e8e8e8;
    font-size: 1rem;
    line-height: 1.5;
    margin: 0 0 12px 0;
}

.error-details {
    color: #888;
    font-size: 0.9rem;
    font-style: italic;
    margin: 0 0 12px 0;
}

.error-details.hidden {
    display: none;
}

.error-id {
    color: #555;
    font-size: 0.75rem;
    font-family: monospace;
}

.error-id.hidden {
    display: none;
}

.error-modal-actions {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
}

.error-btn {
    padding: 10px 20px;
    border-radius: 6px;
    font-size: 0.95rem;
    cursor: pointer;
    transition: all 0.2s;
    border: none;
}

.error-btn.primary {
    background: #e74c3c;
    color: white;
}

.error-btn.primary:hover {
    background: #c0392b;
}

.error-btn.secondary {
    background: transparent;
    color: #888;
    border: 1px solid #444;
}

.error-btn.secondary:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #e8e8e8;
}

/* Network Status */
.network-status {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background: #2a2a4e;
    border-radius: 20px;
    z-index: 9999;
    animation: slideUp 0.3s ease-out;
}

.network-status.hidden {
    display: none;
}

.network-status.offline {
    background: #e74c3c;
}

.network-status.warning {
    background: #f39c12;
}

@keyframes slideUp {
    from {
        opacity: 0;
        transform: translateX(-50%) translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateX(-50%) translateY(0);
    }
}

.status-icon {
    font-weight: bold;
}

.status-text {
    color: white;
    font-size: 0.9rem;
}

.retry-btn {
    background: rgba(255, 255, 255, 0.2);
    border: none;
    color: white;
    padding: 4px 12px;
    border-radius: 12px;
    cursor: pointer;
    font-size: 0.8rem;
}

.retry-btn:hover {
    background: rgba(255, 255, 255, 0.3);
}

.retry-btn.hidden {
    display: none;
}

/* Inline Errors */
.has-error {
    border-color: #e74c3c !important;
    box-shadow: 0 0 0 2px rgba(231, 76, 60, 0.2) !important;
}

.inline-error {
    display: block;
    color: #e74c3c;
    font-size: 0.8rem;
    margin-top: 4px;
}

/* Error Toast Container */
.error-toast-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9998;
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-width: 400px;
}

.error-toast {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    border-radius: 8px;
    background: #2a2a4e;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    transform: translateX(120%);
    transition: transform 0.3s ease-out, opacity 0.3s;
}

.error-toast.show {
    transform: translateX(0);
}

.error-toast.hide {
    transform: translateX(120%);
    opacity: 0;
}

.error-toast.info {
    border-left: 4px solid #3498db;
}

.error-toast.success {
    border-left: 4px solid #2ecc71;
}

.error-toast.warning {
    border-left: 4px solid #f39c12;
}

.error-toast.error {
    border-left: 4px solid #e74c3c;
}

.toast-icon {
    font-weight: bold;
    width: 20px;
    text-align: center;
}

.error-toast.info .toast-icon { color: #3498db; }
.error-toast.success .toast-icon { color: #2ecc71; }
.error-toast.warning .toast-icon { color: #f39c12; }
.error-toast.error .toast-icon { color: #e74c3c; }

.toast-message {
    flex: 1;
    color: #e8e8e8;
    font-size: 0.9rem;
}

.toast-action {
    background: rgba(255, 255, 255, 0.1);
    border: none;
    color: #888;
    padding: 4px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.8rem;
}

.toast-action:hover {
    background: rgba(255, 255, 255, 0.2);
    color: #e8e8e8;
}

.toast-close {
    background: transparent;
    border: none;
    color: #666;
    font-size: 1rem;
    cursor: pointer;
    padding: 0 4px;
}

.toast-close:hover {
    color: #888;
}
`;

// Inject styles
const styleSheet = document.createElement('style');
styleSheet.textContent = styles;
document.head.appendChild(styleSheet);

// Initialize components
export const errorModal = new ErrorModal();
export const networkStatus = new NetworkStatusIndicator();
export const inlineErrors = new InlineErrorDisplay();
export const errorToast = new ErrorToast();

// Export for use in other modules
export default {
    errorModal,
    networkStatus,
    inlineErrors,
    errorToast
};
