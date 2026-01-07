/**
 * D&D Combat Engine - Error Handler
 * Centralized error handling with recovery and user feedback.
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';

/**
 * Error severity levels
 */
export const ErrorSeverity = {
    INFO: 'info',
    WARNING: 'warning',
    ERROR: 'error',
    CRITICAL: 'critical'
};

/**
 * Error categories for different handling strategies
 */
export const ErrorCategory = {
    NETWORK: 'network',
    AUTH: 'auth',
    VALIDATION: 'validation',
    COMBAT: 'combat',
    CAMPAIGN: 'campaign',
    AI: 'ai',
    UNKNOWN: 'unknown'
};

/**
 * Custom error class for game errors
 */
export class GameError extends Error {
    constructor(code, message, options = {}) {
        super(message);
        this.name = 'GameError';
        this.code = code;
        this.details = options.details || {};
        this.recoverable = options.recoverable !== false;
        this.recoveryHint = options.recoveryHint || null;
        this.severity = options.severity || ErrorSeverity.ERROR;
        this.category = options.category || ErrorCategory.UNKNOWN;
        this.timestamp = new Date().toISOString();
        this.errorId = options.errorId || this._generateId();
    }

    _generateId() {
        return Math.random().toString(36).substring(2, 10);
    }

    toJSON() {
        return {
            code: this.code,
            message: this.message,
            details: this.details,
            recoverable: this.recoverable,
            recoveryHint: this.recoveryHint,
            severity: this.severity,
            category: this.category,
            timestamp: this.timestamp,
            errorId: this.errorId
        };
    }
}

/**
 * Error Handler - Singleton class for centralized error management
 */
class ErrorHandler {
    constructor() {
        this.errorLog = [];
        this.maxLogSize = 100;
        this.retryAttempts = new Map();
        this.maxRetries = 3;
        this.retryDelays = [1000, 3000, 5000]; // Exponential backoff

        // Bind global error handlers
        this._setupGlobalHandlers();
    }

    /**
     * Setup global error handlers
     */
    _setupGlobalHandlers() {
        // Handle uncaught errors
        window.onerror = (message, source, lineno, colno, error) => {
            this.handle(error || new Error(message), {
                source,
                lineno,
                colno,
                global: true
            });
            return false; // Let default handler also run
        };

        // Handle unhandled promise rejections
        window.onunhandledrejection = (event) => {
            const error = event.reason instanceof Error
                ? event.reason
                : new Error(String(event.reason));
            this.handle(error, { unhandledRejection: true });
        };
    }

    /**
     * Main error handling method
     * @param {Error|GameError} error - The error to handle
     * @param {Object} context - Additional context about where the error occurred
     * @returns {boolean} Whether the error was handled successfully
     */
    handle(error, context = {}) {
        // Convert to GameError if needed
        const gameError = this._normalizeError(error, context);

        // Log the error
        this._logError(gameError, context);

        // Emit error event for other components
        eventBus.emit(EVENTS.ERROR_OCCURRED, {
            error: gameError.toJSON(),
            context
        });

        // Determine handling strategy based on category
        switch (gameError.category) {
            case ErrorCategory.NETWORK:
                return this._handleNetworkError(gameError, context);
            case ErrorCategory.AUTH:
                return this._handleAuthError(gameError, context);
            case ErrorCategory.VALIDATION:
                return this._handleValidationError(gameError, context);
            case ErrorCategory.COMBAT:
                return this._handleCombatError(gameError, context);
            case ErrorCategory.AI:
                return this._handleAIError(gameError, context);
            default:
                return this._handleGenericError(gameError, context);
        }
    }

    /**
     * Normalize any error into a GameError
     */
    _normalizeError(error, context) {
        if (error instanceof GameError) {
            return error;
        }

        // Parse API error response
        if (error.response?.error) {
            const apiError = error.response.error;
            return new GameError(
                apiError.code || 'UNKNOWN',
                apiError.message || error.message,
                {
                    details: apiError.details || {},
                    recoverable: apiError.recoverable,
                    recoveryHint: apiError.recovery_hint,
                    errorId: apiError.error_id,
                    category: this._categorizeErrorCode(apiError.code)
                }
            );
        }

        // Handle fetch errors
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            return new GameError('NETWORK_ERROR', 'Unable to connect to server', {
                category: ErrorCategory.NETWORK,
                recoverable: true,
                recoveryHint: 'Check your internet connection'
            });
        }

        // Handle timeout errors
        if (error.name === 'AbortError') {
            return new GameError('TIMEOUT', 'Request timed out', {
                category: ErrorCategory.NETWORK,
                recoverable: true,
                recoveryHint: 'The server took too long to respond. Try again.'
            });
        }

        // Generic error
        return new GameError('UNKNOWN', error.message || 'An unexpected error occurred', {
            details: { originalError: error.name },
            category: ErrorCategory.UNKNOWN,
            recoverable: false
        });
    }

    /**
     * Categorize error based on error code
     */
    _categorizeErrorCode(code) {
        if (!code) return ErrorCategory.UNKNOWN;

        if (code.startsWith('AUTH_')) return ErrorCategory.AUTH;
        if (code.startsWith('COMBAT_')) return ErrorCategory.COMBAT;
        if (code.startsWith('CAMPAIGN_')) return ErrorCategory.CAMPAIGN;
        if (code.startsWith('AI_')) return ErrorCategory.AI;
        if (code === 'VALIDATION_ERROR') return ErrorCategory.VALIDATION;
        if (code.includes('CONNECTION') || code.includes('NETWORK')) return ErrorCategory.NETWORK;

        return ErrorCategory.UNKNOWN;
    }

    /**
     * Log error to internal log
     */
    _logError(error, context) {
        const logEntry = {
            error: error.toJSON(),
            context,
            timestamp: new Date().toISOString()
        };

        // Console logging
        if (error.severity === ErrorSeverity.CRITICAL) {
            console.error('[CRITICAL ERROR]', error.message, logEntry);
        } else if (error.severity === ErrorSeverity.ERROR) {
            console.error('[ERROR]', error.message, logEntry);
        } else if (error.severity === ErrorSeverity.WARNING) {
            console.warn('[WARNING]', error.message, logEntry);
        } else {
            console.info('[INFO]', error.message, logEntry);
        }

        // Add to log
        this.errorLog.unshift(logEntry);
        if (this.errorLog.length > this.maxLogSize) {
            this.errorLog.pop();
        }
    }

    /**
     * Handle network errors with retry logic
     */
    _handleNetworkError(error, context) {
        this.showToast(error, 'warning');

        // Offer retry if there's a retry function
        if (context.retry && typeof context.retry === 'function') {
            const key = context.operationId || 'default';
            const attempts = this.retryAttempts.get(key) || 0;

            if (attempts < this.maxRetries) {
                this.retryAttempts.set(key, attempts + 1);
                const delay = this.retryDelays[attempts] || 5000;

                console.log(`[ErrorHandler] Retrying in ${delay}ms (attempt ${attempts + 1}/${this.maxRetries})`);

                setTimeout(() => {
                    context.retry();
                }, delay);

                return true;
            } else {
                this.retryAttempts.delete(key);
                this.showModal(error, {
                    title: 'Connection Failed',
                    actions: [
                        { label: 'Retry', action: () => context.retry() },
                        { label: 'Continue Offline', action: () => this._enableOfflineMode() }
                    ]
                });
            }
        }

        return false;
    }

    /**
     * Handle authentication errors
     */
    _handleAuthError(error, context) {
        if (error.code === 'AUTH_TOKEN_EXPIRED' || error.code === 'AUTH_TOKEN_INVALID') {
            // Clear auth state and redirect to login
            eventBus.emit('auth:sessionExpired', { error });
            this.showToast(new GameError(
                error.code,
                'Your session has expired. Please log in again.',
                { severity: ErrorSeverity.WARNING }
            ));
            return true;
        }

        if (error.code === 'AUTH_FORBIDDEN') {
            this.showToast(error, 'error');
            return true;
        }

        this.showToast(error, 'error');
        return false;
    }

    /**
     * Handle validation errors
     */
    _handleValidationError(error, context) {
        // Validation errors are usually handled inline by forms
        // But we still emit an event for components that want to know
        eventBus.emit('validation:error', {
            errors: error.details?.errors || [],
            field: error.details?.field
        });

        this.showToast(error, 'warning');
        return true;
    }

    /**
     * Handle combat-specific errors
     */
    _handleCombatError(error, context) {
        // Combat errors are usually recoverable
        if (error.code === 'COMBAT_NOT_YOUR_TURN') {
            this.showToast(new GameError(
                error.code,
                "It's not your turn yet!",
                { severity: ErrorSeverity.INFO }
            ), 'info');
            return true;
        }

        if (error.code === 'COMBAT_OUT_OF_RANGE') {
            this.showToast(error, 'warning');
            return true;
        }

        this.showToast(error, 'error');
        return true;
    }

    /**
     * Handle AI service errors
     */
    _handleAIError(error, context) {
        if (error.code === 'AI_RATE_LIMITED') {
            const retryAfter = error.details?.retry_after_seconds || 60;
            this.showModal(error, {
                title: 'AI Service Busy',
                message: `The AI service is temporarily busy. Please wait ${retryAfter} seconds before trying again.`,
                actions: [
                    { label: 'OK', action: () => {} }
                ]
            });
            return true;
        }

        if (error.code === 'AI_SERVICE_UNAVAILABLE') {
            this.showToast(new GameError(
                error.code,
                'AI features are temporarily unavailable',
                { severity: ErrorSeverity.WARNING, recoveryHint: 'Try again in a moment' }
            ), 'warning');
            return true;
        }

        this.showToast(error, 'error');
        return false;
    }

    /**
     * Handle generic/unknown errors
     */
    _handleGenericError(error, context) {
        if (error.severity === ErrorSeverity.CRITICAL) {
            this.showModal(error, {
                title: 'Critical Error',
                message: error.message,
                actions: [
                    { label: 'Reload Page', action: () => window.location.reload() },
                    { label: 'Continue', action: () => {} }
                ]
            });
        } else {
            this.showToast(error);
        }

        return false;
    }

    /**
     * Show toast notification for error
     * @param {GameError} error - The error to display
     * @param {string} type - Toast type override (info, warning, error, success)
     */
    showToast(error, type = null) {
        const toastType = type || this._severityToToastType(error.severity);

        eventBus.emit(EVENTS.UI_NOTIFICATION, {
            type: toastType,
            message: error.message,
            duration: error.severity === ErrorSeverity.CRITICAL ? 0 : 5000,
            action: error.recoveryHint ? {
                label: 'More Info',
                callback: () => this.showModal(error)
            } : null
        });
    }

    /**
     * Show modal for critical errors or errors requiring user action
     * @param {GameError} error - The error to display
     * @param {Object} options - Modal options
     */
    showModal(error, options = {}) {
        const modalData = {
            type: 'error',
            title: options.title || 'Error',
            message: options.message || error.message,
            details: error.recoveryHint ? `Hint: ${error.recoveryHint}` : null,
            errorId: error.errorId,
            actions: options.actions || [
                { label: 'OK', action: () => {} }
            ],
            dismissable: error.recoverable
        };

        eventBus.emit(EVENTS.UI_MODAL_OPENED, {
            modal: 'error',
            data: modalData
        });
    }

    /**
     * Map severity to toast type
     */
    _severityToToastType(severity) {
        const map = {
            [ErrorSeverity.INFO]: 'info',
            [ErrorSeverity.WARNING]: 'warning',
            [ErrorSeverity.ERROR]: 'error',
            [ErrorSeverity.CRITICAL]: 'error'
        };
        return map[severity] || 'error';
    }

    /**
     * Enable offline mode
     */
    _enableOfflineMode() {
        console.log('[ErrorHandler] Enabling offline mode');
        eventBus.emit('app:offlineMode', { enabled: true });
    }

    /**
     * Attempt to recover from an error
     * @param {GameError} error - The error to recover from
     * @returns {boolean} Whether recovery was successful
     */
    async recover(error) {
        if (!error.recoverable) {
            console.log('[ErrorHandler] Error is not recoverable:', error.code);
            return false;
        }

        // Implement recovery strategies based on error type
        switch (error.category) {
            case ErrorCategory.NETWORK:
                // Try to reconnect
                return await this._attemptReconnect();

            case ErrorCategory.AUTH:
                // Try to refresh token
                return await this._attemptTokenRefresh();

            case ErrorCategory.COMBAT:
                // Try to resync combat state
                return await this._attemptCombatResync();

            default:
                return false;
        }
    }

    async _attemptReconnect() {
        try {
            const response = await fetch('/api/health');
            if (response.ok) {
                eventBus.emit('app:reconnected');
                return true;
            }
        } catch (e) {
            console.log('[ErrorHandler] Reconnect failed');
        }
        return false;
    }

    async _attemptTokenRefresh() {
        eventBus.emit('auth:refreshToken');
        return false; // Let the auth module handle this
    }

    async _attemptCombatResync() {
        eventBus.emit('combat:requestResync');
        return false; // Let the combat module handle this
    }

    /**
     * Report error to analytics/error tracking service
     * @param {GameError} error - The error to report
     */
    report(error) {
        // Placeholder for error tracking integration (Sentry, etc.)
        console.log('[ErrorHandler] Would report error:', error.errorId);

        // In production, this would send to an error tracking service:
        // if (window.Sentry) {
        //     window.Sentry.captureException(error);
        // }
    }

    /**
     * Get recent error log
     * @param {number} count - Number of recent errors to return
     * @returns {Array} Recent error log entries
     */
    getRecentErrors(count = 10) {
        return this.errorLog.slice(0, count);
    }

    /**
     * Clear error log
     */
    clearLog() {
        this.errorLog = [];
    }

    /**
     * Reset retry attempts for an operation
     * @param {string} operationId - The operation ID to reset
     */
    resetRetries(operationId) {
        this.retryAttempts.delete(operationId);
    }
}

// Export singleton instance
export const errorHandler = new ErrorHandler();
export default errorHandler;
