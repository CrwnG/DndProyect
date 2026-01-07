/**
 * D&D Combat Engine - Authentication Service
 * Handles user authentication, token management, and session persistence.
 */

import { eventBus } from '../engine/event-bus.js';
import { CONFIG } from '../config.js';

// Token storage keys
const ACCESS_TOKEN_KEY = 'dnd_access_token';
const REFRESH_TOKEN_KEY = 'dnd_refresh_token';
const USER_KEY = 'dnd_user';

/**
 * Authentication Service
 * Manages user sessions, tokens, and auth state.
 */
class AuthService {
    constructor() {
        this.user = null;
        this.accessToken = null;
        this.refreshToken = null;
        this.refreshPromise = null;

        // Load stored auth state
        this.loadStoredAuth();

        // Setup auto-refresh
        this.setupAutoRefresh();
    }

    // =========================================================================
    // STORAGE MANAGEMENT
    // =========================================================================

    /**
     * Load authentication state from localStorage
     */
    loadStoredAuth() {
        try {
            const storedUser = localStorage.getItem(USER_KEY);
            const storedAccessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
            const storedRefreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);

            if (storedUser && storedAccessToken) {
                this.user = JSON.parse(storedUser);
                this.accessToken = storedAccessToken;
                this.refreshToken = storedRefreshToken;

                console.log('[AuthService] Loaded stored auth for:', this.user.username);
            }
        } catch (error) {
            console.error('[AuthService] Failed to load stored auth:', error);
            this.clearStoredAuth();
        }
    }

    /**
     * Save authentication state to localStorage
     */
    saveAuth(user, tokens) {
        this.user = user;
        this.accessToken = tokens.access_token;
        this.refreshToken = tokens.refresh_token;

        localStorage.setItem(USER_KEY, JSON.stringify(user));
        localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
        localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
    }

    /**
     * Clear all stored authentication data
     */
    clearStoredAuth() {
        this.user = null;
        this.accessToken = null;
        this.refreshToken = null;

        localStorage.removeItem(USER_KEY);
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
    }

    // =========================================================================
    // AUTH STATE
    // =========================================================================

    /**
     * Check if user is currently authenticated
     */
    isAuthenticated() {
        return !!this.accessToken && !!this.user;
    }

    /**
     * Get current user
     */
    getUser() {
        return this.user;
    }

    /**
     * Get access token for API requests
     */
    getAccessToken() {
        return this.accessToken;
    }

    // =========================================================================
    // API METHODS
    // =========================================================================

    /**
     * Register a new user
     */
    async register(username, email, password, displayName = null) {
        const response = await this._request('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify({
                username,
                email,
                password,
                display_name: displayName,
            }),
        });

        this.saveAuth(response.user, response.tokens);
        eventBus.emit('auth:login', { user: this.user });

        return response;
    }

    /**
     * Login with username/email and password
     */
    async login(username, password) {
        const response = await this._request('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password }),
        });

        this.saveAuth(response.user, response.tokens);
        eventBus.emit('auth:login', { user: this.user });

        return response;
    }

    /**
     * Logout current user
     */
    async logout() {
        try {
            await this._request('/api/auth/logout', {
                method: 'POST',
            });
        } catch (error) {
            console.warn('[AuthService] Logout API call failed:', error);
        }

        const username = this.user?.username;
        this.clearStoredAuth();
        eventBus.emit('auth:logout', { username });
    }

    /**
     * Refresh access token
     */
    async refreshAccessToken() {
        // Prevent multiple simultaneous refresh attempts
        if (this.refreshPromise) {
            return this.refreshPromise;
        }

        if (!this.refreshToken) {
            throw new Error('No refresh token available');
        }

        this.refreshPromise = this._doRefresh();

        try {
            const result = await this.refreshPromise;
            return result;
        } finally {
            this.refreshPromise = null;
        }
    }

    async _doRefresh() {
        try {
            const response = await this._request('/api/auth/refresh', {
                method: 'POST',
                body: JSON.stringify({ refresh_token: this.refreshToken }),
                skipAuth: true, // Don't use access token for refresh
            });

            this.accessToken = response.access_token;
            this.refreshToken = response.refresh_token;

            localStorage.setItem(ACCESS_TOKEN_KEY, response.access_token);
            localStorage.setItem(REFRESH_TOKEN_KEY, response.refresh_token);

            eventBus.emit('auth:tokenRefreshed');

            return response;
        } catch (error) {
            console.error('[AuthService] Token refresh failed:', error);
            this.clearStoredAuth();
            eventBus.emit('auth:sessionExpired', { error });
            throw error;
        }
    }

    /**
     * Verify current token is still valid
     */
    async verifyToken() {
        if (!this.accessToken) {
            return false;
        }

        try {
            const response = await this._request('/api/auth/verify');
            this.user = response.user;
            localStorage.setItem(USER_KEY, JSON.stringify(response.user));
            return true;
        } catch (error) {
            console.warn('[AuthService] Token verification failed:', error);
            return false;
        }
    }

    /**
     * Get current user profile
     */
    async getProfile() {
        const response = await this._request('/api/auth/me');
        this.user = response;
        localStorage.setItem(USER_KEY, JSON.stringify(response));
        return response;
    }

    /**
     * Update user profile
     */
    async updateProfile(updates) {
        const response = await this._request('/api/auth/profile', {
            method: 'PUT',
            body: JSON.stringify(updates),
        });

        this.user = response;
        localStorage.setItem(USER_KEY, JSON.stringify(response));
        eventBus.emit('auth:profileUpdated', { user: this.user });

        return response;
    }

    /**
     * Change password
     */
    async changePassword(oldPassword, newPassword) {
        const response = await this._request('/api/auth/change-password', {
            method: 'POST',
            body: JSON.stringify({
                old_password: oldPassword,
                new_password: newPassword,
            }),
        });

        // Password change invalidates tokens, need to re-login
        this.clearStoredAuth();
        eventBus.emit('auth:passwordChanged');

        return response;
    }

    // =========================================================================
    // HTTP HELPERS
    // =========================================================================

    /**
     * Make an authenticated API request
     */
    async _request(url, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        // Add auth header unless explicitly skipped
        if (!options.skipAuth && this.accessToken) {
            headers['Authorization'] = `Bearer ${this.accessToken}`;
        }

        const response = await fetch(`${CONFIG.API_BASE_URL}${url}`, {
            ...options,
            headers,
        });

        const data = await response.json();

        if (!response.ok) {
            // Handle token expiration
            if (response.status === 401 && !options.skipAuth && !options.isRetry) {
                try {
                    await this.refreshAccessToken();
                    // Retry the request
                    return this._request(url, { ...options, isRetry: true });
                } catch (refreshError) {
                    throw data.error || { message: 'Session expired' };
                }
            }

            throw data.error || { message: data.detail || 'Request failed' };
        }

        return data;
    }

    // =========================================================================
    // AUTO-REFRESH
    // =========================================================================

    /**
     * Setup automatic token refresh before expiration
     */
    setupAutoRefresh() {
        // Refresh token 5 minutes before expiration
        const refreshInterval = (60 - 5) * 60 * 1000; // 55 minutes

        setInterval(() => {
            if (this.isAuthenticated()) {
                this.refreshAccessToken().catch(err => {
                    console.warn('[AuthService] Auto-refresh failed:', err);
                });
            }
        }, refreshInterval);

        // Listen for session expiration events
        eventBus.on('auth:sessionExpired', () => {
            this.clearStoredAuth();
        });
    }
}

// Export singleton instance
export const authService = new AuthService();
export default authService;
