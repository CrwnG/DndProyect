/**
 * D&D Combat Engine - Authentication Modal
 * Login and registration UI.
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import { authService } from '../services/auth.js';
import { errorHandler } from '../core/error-handler.js';

/**
 * Authentication Modal
 */
class AuthModal {
    constructor() {
        this.container = null;
        this.isVisible = false;
        this.mode = 'login'; // 'login' or 'register'
        this.onSuccess = null;

        this.init();
    }

    init() {
        this.createContainer();
        this.setupEventListeners();
    }

    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'auth-modal';
        this.container.className = 'auth-modal hidden';
        this.container.innerHTML = `
            <div class="auth-backdrop"></div>
            <div class="auth-content">
                <button class="auth-close">&times;</button>

                <div class="auth-header">
                    <h2 class="auth-title">Welcome, Adventurer</h2>
                    <p class="auth-subtitle">Sign in to save your progress and join multiplayer sessions</p>
                </div>

                <div class="auth-tabs">
                    <button class="auth-tab active" data-tab="login">Sign In</button>
                    <button class="auth-tab" data-tab="register">Create Account</button>
                </div>

                <!-- Login Form -->
                <form id="login-form" class="auth-form">
                    <div class="form-group">
                        <label for="login-username">Username or Email</label>
                        <input type="text" id="login-username" name="username" required autocomplete="username">
                    </div>
                    <div class="form-group">
                        <label for="login-password">Password</label>
                        <input type="password" id="login-password" name="password" required autocomplete="current-password">
                    </div>
                    <div class="form-error hidden"></div>
                    <button type="submit" class="auth-submit">Sign In</button>
                </form>

                <!-- Register Form -->
                <form id="register-form" class="auth-form hidden">
                    <div class="form-group">
                        <label for="register-username">Username</label>
                        <input type="text" id="register-username" name="username" required minlength="3" maxlength="32" autocomplete="username">
                        <span class="form-hint">3-32 characters, letters, numbers, underscores</span>
                    </div>
                    <div class="form-group">
                        <label for="register-email">Email</label>
                        <input type="email" id="register-email" name="email" required autocomplete="email">
                    </div>
                    <div class="form-group">
                        <label for="register-display-name">Display Name (optional)</label>
                        <input type="text" id="register-display-name" name="display_name" maxlength="64">
                    </div>
                    <div class="form-group">
                        <label for="register-password">Password</label>
                        <input type="password" id="register-password" name="password" required minlength="8" autocomplete="new-password">
                        <span class="form-hint">At least 8 characters</span>
                    </div>
                    <div class="form-group">
                        <label for="register-confirm">Confirm Password</label>
                        <input type="password" id="register-confirm" name="confirm" required autocomplete="new-password">
                    </div>
                    <div class="form-error hidden"></div>
                    <button type="submit" class="auth-submit">Create Account</button>
                </form>

                <div class="auth-footer">
                    <p class="auth-skip">
                        <button class="skip-link">Continue as Guest</button>
                    </p>
                </div>
            </div>
        `;

        document.body.appendChild(this.container);
    }

    setupEventListeners() {
        // Close button
        this.container.querySelector('.auth-close').addEventListener('click', () => {
            this.hide();
        });

        // Backdrop click
        this.container.querySelector('.auth-backdrop').addEventListener('click', () => {
            this.hide();
        });

        // Skip/guest button
        this.container.querySelector('.skip-link').addEventListener('click', () => {
            this.hide();
            if (this.onSuccess) {
                this.onSuccess(null); // null indicates guest mode
            }
        });

        // Tab switching
        this.container.querySelectorAll('.auth-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.switchTab(tab.dataset.tab);
            });
        });

        // Login form
        this.container.querySelector('#login-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleLogin();
        });

        // Register form
        this.container.querySelector('#register-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleRegister();
        });

        // Listen for session expiration
        eventBus.on('auth:sessionExpired', () => {
            if (!this.isVisible) {
                this.show('login', () => {}, 'Your session has expired. Please sign in again.');
            }
        });
    }

    switchTab(tab) {
        this.mode = tab;

        // Update tab buttons
        this.container.querySelectorAll('.auth-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.tab === tab);
        });

        // Show/hide forms
        this.container.querySelector('#login-form').classList.toggle('hidden', tab !== 'login');
        this.container.querySelector('#register-form').classList.toggle('hidden', tab !== 'register');

        // Clear errors
        this.clearErrors();
    }

    async handleLogin() {
        const form = this.container.querySelector('#login-form');
        const username = form.querySelector('#login-username').value.trim();
        const password = form.querySelector('#login-password').value;

        this.clearErrors();
        this.setLoading(true);

        try {
            const response = await authService.login(username, password);

            this.hide();
            this.showSuccessToast(`Welcome back, ${response.user.display_name || response.user.username}!`);

            if (this.onSuccess) {
                this.onSuccess(response.user);
            }
        } catch (error) {
            this.showError(error.message || 'Login failed');
        } finally {
            this.setLoading(false);
        }
    }

    async handleRegister() {
        const form = this.container.querySelector('#register-form');
        const username = form.querySelector('#register-username').value.trim();
        const email = form.querySelector('#register-email').value.trim();
        const displayName = form.querySelector('#register-display-name').value.trim() || null;
        const password = form.querySelector('#register-password').value;
        const confirm = form.querySelector('#register-confirm').value;

        this.clearErrors();

        // Validate passwords match
        if (password !== confirm) {
            this.showError('Passwords do not match');
            return;
        }

        this.setLoading(true);

        try {
            const response = await authService.register(username, email, password, displayName);

            this.hide();
            this.showSuccessToast(`Welcome, ${response.user.display_name || response.user.username}! Your account has been created.`);

            if (this.onSuccess) {
                this.onSuccess(response.user);
            }
        } catch (error) {
            this.showError(error.message || 'Registration failed');
        } finally {
            this.setLoading(false);
        }
    }

    showError(message) {
        const form = this.mode === 'login'
            ? this.container.querySelector('#login-form')
            : this.container.querySelector('#register-form');

        const errorEl = form.querySelector('.form-error');
        errorEl.textContent = message;
        errorEl.classList.remove('hidden');
    }

    clearErrors() {
        this.container.querySelectorAll('.form-error').forEach(el => {
            el.textContent = '';
            el.classList.add('hidden');
        });
    }

    setLoading(loading) {
        const form = this.mode === 'login'
            ? this.container.querySelector('#login-form')
            : this.container.querySelector('#register-form');

        const button = form.querySelector('.auth-submit');
        button.disabled = loading;
        button.textContent = loading
            ? (this.mode === 'login' ? 'Signing In...' : 'Creating Account...')
            : (this.mode === 'login' ? 'Sign In' : 'Create Account');
    }

    showSuccessToast(message) {
        eventBus.emit(EVENTS.UI_NOTIFICATION, {
            type: 'success',
            message,
            duration: 4000,
        });
    }

    show(mode = 'login', onSuccess = null, message = null) {
        this.mode = mode;
        this.onSuccess = onSuccess;

        // Reset forms
        this.container.querySelector('#login-form').reset();
        this.container.querySelector('#register-form').reset();
        this.clearErrors();

        // Switch to correct tab
        this.switchTab(mode);

        // Show message if provided
        if (message) {
            setTimeout(() => this.showError(message), 100);
        }

        // Show modal
        this.container.classList.remove('hidden');
        this.isVisible = true;

        // Focus first input
        setTimeout(() => {
            const input = this.mode === 'login'
                ? this.container.querySelector('#login-username')
                : this.container.querySelector('#register-username');
            input?.focus();
        }, 100);
    }

    hide() {
        this.container.classList.add('hidden');
        this.isVisible = false;
        this.onSuccess = null;
    }
}

// CSS Styles
const styles = `
.auth-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 10001;
    display: flex;
    align-items: center;
    justify-content: center;
}

.auth-modal.hidden {
    display: none;
}

.auth-backdrop {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.8);
}

.auth-content {
    position: relative;
    width: 90%;
    max-width: 420px;
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    border: 2px solid #d4af37;
    border-radius: 12px;
    padding: 32px;
    animation: authSlideIn 0.3s ease-out;
}

@keyframes authSlideIn {
    from {
        opacity: 0;
        transform: translateY(-30px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.auth-close {
    position: absolute;
    top: 12px;
    right: 12px;
    width: 32px;
    height: 32px;
    background: transparent;
    border: none;
    color: #888;
    font-size: 24px;
    cursor: pointer;
    border-radius: 4px;
    transition: all 0.2s;
}

.auth-close:hover {
    color: #e8e8e8;
    background: rgba(255, 255, 255, 0.1);
}

.auth-header {
    text-align: center;
    margin-bottom: 24px;
}

.auth-title {
    margin: 0;
    color: #d4af37;
    font-size: 1.5rem;
    font-family: 'Cinzel', serif;
}

.auth-subtitle {
    margin: 8px 0 0 0;
    color: #888;
    font-size: 0.9rem;
}

.auth-tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 24px;
    background: rgba(0, 0, 0, 0.2);
    border-radius: 8px;
    padding: 4px;
}

.auth-tab {
    flex: 1;
    padding: 10px 16px;
    background: transparent;
    border: none;
    color: #888;
    font-size: 0.95rem;
    cursor: pointer;
    border-radius: 6px;
    transition: all 0.2s;
}

.auth-tab:hover {
    color: #c8c8c8;
}

.auth-tab.active {
    background: #d4af37;
    color: #1a1a2e;
    font-weight: 600;
}

.auth-form {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.auth-form.hidden {
    display: none;
}

.form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.form-group label {
    color: #c8c8c8;
    font-size: 0.9rem;
}

.form-group input {
    padding: 12px 14px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid #3a3a5c;
    border-radius: 6px;
    color: #e8e8e8;
    font-size: 1rem;
    transition: all 0.2s;
}

.form-group input:focus {
    outline: none;
    border-color: #d4af37;
    box-shadow: 0 0 0 2px rgba(212, 175, 55, 0.2);
}

.form-hint {
    color: #666;
    font-size: 0.8rem;
}

.form-error {
    color: #e74c3c;
    font-size: 0.9rem;
    text-align: center;
    padding: 8px;
    background: rgba(231, 76, 60, 0.1);
    border-radius: 6px;
}

.form-error.hidden {
    display: none;
}

.auth-submit {
    padding: 14px 20px;
    background: linear-gradient(180deg, #d4af37 0%, #b8972e 100%);
    border: none;
    border-radius: 6px;
    color: #1a1a2e;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    margin-top: 8px;
}

.auth-submit:hover:not(:disabled) {
    background: linear-gradient(180deg, #e4bf47 0%, #c8a73e 100%);
    transform: translateY(-1px);
}

.auth-submit:disabled {
    opacity: 0.7;
    cursor: not-allowed;
}

.auth-footer {
    margin-top: 20px;
    text-align: center;
}

.auth-skip {
    margin: 0;
    color: #666;
    font-size: 0.9rem;
}

.skip-link {
    background: transparent;
    border: none;
    color: #888;
    cursor: pointer;
    text-decoration: underline;
    font-size: 0.9rem;
}

.skip-link:hover {
    color: #c8c8c8;
}
`;

// Inject styles
const styleSheet = document.createElement('style');
styleSheet.textContent = styles;
document.head.appendChild(styleSheet);

// Export singleton
export const authModal = new AuthModal();
export default authModal;
