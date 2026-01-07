/**
 * D&D Combat Engine - Mobile Navigation
 * Bottom navigation bar and floating action button for mobile.
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';

/**
 * Mobile Navigation Component
 */
class MobileNav {
    constructor() {
        this.container = null;
        this.fab = null;
        this.activeTab = 'combat';
        this.isVisible = false;

        // Only initialize on mobile
        if (this.isMobile()) {
            this.init();
        }
    }

    /**
     * Check if on mobile device
     */
    isMobile() {
        return window.innerWidth <= 768 ||
            ('ontouchstart' in window) ||
            (navigator.maxTouchPoints > 0);
    }

    init() {
        this.createNavBar();
        this.createFAB();
        this.setupEventListeners();
        this.show();
    }

    createNavBar() {
        this.container = document.createElement('nav');
        this.container.className = 'mobile-nav';
        this.container.innerHTML = `
            <button class="mobile-nav-btn active" data-tab="combat" title="Combat">
                <span class="nav-icon">⚔️</span>
                <span class="nav-label">Combat</span>
            </button>
            <button class="mobile-nav-btn" data-tab="character" title="Character">
                <span class="nav-icon">👤</span>
                <span class="nav-label">Character</span>
            </button>
            <button class="mobile-nav-btn" data-tab="inventory" title="Inventory">
                <span class="nav-icon">🎒</span>
                <span class="nav-label">Inventory</span>
            </button>
            <button class="mobile-nav-btn" data-tab="log" title="Combat Log">
                <span class="nav-icon">📜</span>
                <span class="nav-label">Log</span>
            </button>
            <button class="mobile-nav-btn" data-tab="menu" title="Menu">
                <span class="nav-icon">☰</span>
                <span class="nav-label">Menu</span>
            </button>
        `;

        document.body.appendChild(this.container);
    }

    createFAB() {
        this.fab = document.createElement('button');
        this.fab.className = 'fab';
        this.fab.innerHTML = '⚡';
        this.fab.title = 'Quick Action';

        document.body.appendChild(this.fab);
    }

    setupEventListeners() {
        // Nav button clicks
        this.container.querySelectorAll('.mobile-nav-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.dataset.tab;
                this.setActiveTab(tab);
                this.handleTabAction(tab);
            });
        });

        // FAB click
        this.fab.addEventListener('click', () => {
            this.handleFABClick();
        });

        // Window resize to show/hide nav
        window.addEventListener('resize', () => {
            if (this.isMobile()) {
                this.show();
            } else {
                this.hide();
            }
        });

        // Listen for combat state changes to update FAB
        eventBus.on(EVENTS.COMBAT_STARTED, () => {
            this.updateFABState('combat');
        });

        eventBus.on(EVENTS.COMBAT_ENDED, () => {
            this.updateFABState('idle');
        });

        eventBus.on(EVENTS.TURN_STARTED, (data) => {
            if (data.isPlayer) {
                this.updateFABState('player_turn');
            } else {
                this.updateFABState('enemy_turn');
            }
        });
    }

    // ==================== Tab Navigation ====================

    setActiveTab(tab) {
        this.activeTab = tab;

        // Update button states
        this.container.querySelectorAll('.mobile-nav-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });
    }

    handleTabAction(tab) {
        switch (tab) {
            case 'combat':
                this.scrollToSection('.center-panel');
                eventBus.emit('mobile:showCombat');
                break;

            case 'character':
                this.scrollToSection('.left-panel');
                eventBus.emit('mobile:showCharacter');
                break;

            case 'inventory':
                eventBus.emit(EVENTS.UI_MODAL_OPENED, { modal: 'inventory' });
                // Try to open inventory modal
                import('./inventory-modal.js').then(({ inventoryModal }) => {
                    inventoryModal.show();
                }).catch(() => {});
                break;

            case 'log':
                this.scrollToSection('.right-panel');
                this.toggleCombatLog();
                eventBus.emit('mobile:showLog');
                break;

            case 'menu':
                this.showMobileMenu();
                break;
        }
    }

    scrollToSection(selector) {
        const section = document.querySelector(selector);
        if (section) {
            section.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    toggleCombatLog() {
        const log = document.querySelector('.combat-log');
        if (log) {
            log.classList.toggle('collapsed');
        }
    }

    showMobileMenu() {
        // Create quick menu popup
        const existingMenu = document.querySelector('.mobile-quick-menu');
        if (existingMenu) {
            existingMenu.remove();
            return;
        }

        const menu = document.createElement('div');
        menu.className = 'mobile-quick-menu';
        menu.innerHTML = `
            <div class="quick-menu-backdrop"></div>
            <div class="quick-menu-content">
                <button class="quick-menu-item" data-action="settings">
                    <span>⚙️</span> Settings
                </button>
                <button class="quick-menu-item" data-action="audio">
                    <span>🔊</span> Audio Settings
                </button>
                <button class="quick-menu-item" data-action="narration">
                    <span>🎙️</span> Narration Settings
                </button>
                <button class="quick-menu-item" data-action="fullscreen">
                    <span>⛶</span> Fullscreen
                </button>
                <button class="quick-menu-item" data-action="campaign-menu">
                    <span>📋</span> Campaign Menu
                </button>
                <button class="quick-menu-item close-btn" data-action="close">
                    <span>&times;</span> Close
                </button>
            </div>
        `;

        document.body.appendChild(menu);

        // Event listeners
        menu.querySelector('.quick-menu-backdrop').addEventListener('click', () => {
            menu.remove();
        });

        menu.querySelectorAll('.quick-menu-item').forEach(item => {
            item.addEventListener('click', () => {
                const action = item.dataset.action;
                this.handleMenuAction(action);
                menu.remove();
            });
        });
    }

    handleMenuAction(action) {
        switch (action) {
            case 'settings':
                eventBus.emit('mobile:openSettings');
                break;

            case 'audio':
                import('./settings-audio.js').then(({ audioSettings }) => {
                    audioSettings.show();
                }).catch(() => {});
                break;

            case 'narration':
                import('./settings-narration.js').then(({ narrationSettings }) => {
                    narrationSettings.show();
                }).catch(() => {});
                break;

            case 'fullscreen':
                this.toggleFullscreen();
                break;

            case 'campaign-menu':
                import('./campaign-menu.js').then(({ campaignMenu }) => {
                    campaignMenu.show();
                }).catch(() => {});
                break;

            case 'close':
                // Just close the menu
                break;
        }
    }

    toggleFullscreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().catch(() => {});
        } else {
            document.exitFullscreen().catch(() => {});
        }
    }

    // ==================== FAB (Floating Action Button) ====================

    updateFABState(state) {
        switch (state) {
            case 'combat':
                this.fab.innerHTML = '⚔️';
                this.fab.title = 'Combat Actions';
                break;

            case 'player_turn':
                this.fab.innerHTML = '⚡';
                this.fab.title = 'Your Turn - Attack';
                this.fab.classList.add('pulse');
                break;

            case 'enemy_turn':
                this.fab.innerHTML = '⏳';
                this.fab.title = 'Enemy Turn';
                this.fab.classList.remove('pulse');
                break;

            case 'idle':
            default:
                this.fab.innerHTML = '⚡';
                this.fab.title = 'Quick Action';
                this.fab.classList.remove('pulse');
                break;
        }
    }

    handleFABClick() {
        // Show quick actions menu
        const existingMenu = document.querySelector('.fab-menu');
        if (existingMenu) {
            existingMenu.remove();
            return;
        }

        const menu = document.createElement('div');
        menu.className = 'fab-menu';
        menu.innerHTML = `
            <button class="fab-menu-item" data-action="attack" title="Attack">⚔️</button>
            <button class="fab-menu-item" data-action="spell" title="Cast Spell">✨</button>
            <button class="fab-menu-item" data-action="item" title="Use Item">🧪</button>
            <button class="fab-menu-item" data-action="end-turn" title="End Turn">⏭️</button>
        `;

        document.body.appendChild(menu);

        // Position relative to FAB
        const fabRect = this.fab.getBoundingClientRect();
        menu.style.position = 'fixed';
        menu.style.bottom = `${window.innerHeight - fabRect.top + 10}px`;
        menu.style.right = `${window.innerWidth - fabRect.right}px`;

        // Event listeners
        menu.querySelectorAll('.fab-menu-item').forEach(item => {
            item.addEventListener('click', () => {
                const action = item.dataset.action;
                this.handleFABAction(action);
                menu.remove();
            });
        });

        // Close on outside click
        setTimeout(() => {
            document.addEventListener('click', function closeMenu(e) {
                if (!menu.contains(e.target) && e.target !== this.fab) {
                    menu.remove();
                    document.removeEventListener('click', closeMenu);
                }
            }.bind(this), { once: true });
        }, 100);
    }

    handleFABAction(action) {
        switch (action) {
            case 'attack':
                eventBus.emit('mobile:quickAttack');
                break;

            case 'spell':
                eventBus.emit('mobile:openSpells');
                break;

            case 'item':
                eventBus.emit('mobile:useItem');
                break;

            case 'end-turn':
                eventBus.emit('mobile:endTurn');
                break;
        }
    }

    // ==================== Show/Hide ====================

    show() {
        if (this.container) {
            this.container.style.display = 'flex';
        }
        if (this.fab) {
            this.fab.style.display = 'flex';
        }
        this.isVisible = true;
    }

    hide() {
        if (this.container) {
            this.container.style.display = 'none';
        }
        if (this.fab) {
            this.fab.style.display = 'none';
        }
        this.isVisible = false;
    }
}

// Additional CSS for mobile components
const styles = `
/* Quick Menu */
.mobile-quick-menu {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 9500;
    display: flex;
    align-items: flex-end;
    justify-content: center;
}

.quick-menu-backdrop {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.6);
}

.quick-menu-content {
    position: relative;
    width: 100%;
    max-width: 400px;
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    border-top: 2px solid #d4af37;
    border-radius: 16px 16px 0 0;
    padding: 16px;
    padding-bottom: max(16px, env(safe-area-inset-bottom));
    animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
    from {
        transform: translateY(100%);
    }
    to {
        transform: translateY(0);
    }
}

.quick-menu-item {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    padding: 14px 16px;
    background: transparent;
    border: none;
    border-radius: 8px;
    color: #c8c8c8;
    font-size: 1rem;
    cursor: pointer;
    transition: all 0.2s;
}

.quick-menu-item:hover,
.quick-menu-item:active {
    background: rgba(212, 175, 55, 0.2);
    color: #d4af37;
}

.quick-menu-item.close-btn {
    margin-top: 8px;
    border-top: 1px solid #3a3a5c;
    padding-top: 16px;
    color: #888;
}

/* FAB Menu */
.fab-menu {
    display: flex;
    flex-direction: column;
    gap: 8px;
    z-index: 8998;
    animation: fabMenuIn 0.2s ease-out;
}

@keyframes fabMenuIn {
    from {
        opacity: 0;
        transform: scale(0.8);
    }
    to {
        opacity: 1;
        transform: scale(1);
    }
}

.fab-menu-item {
    width: 48px;
    height: 48px;
    background: linear-gradient(180deg, #2a2a4e 0%, #1a1a2e 100%);
    border: 1px solid #3a3a5c;
    border-radius: 50%;
    font-size: 1.2rem;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.fab-menu-item:hover,
.fab-menu-item:active {
    background: rgba(212, 175, 55, 0.3);
    border-color: #d4af37;
    transform: scale(1.1);
}

/* FAB Pulse Animation */
.fab.pulse {
    animation: fabPulse 1.5s infinite;
}

@keyframes fabPulse {
    0%, 100% {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    }
    50% {
        box-shadow: 0 4px 20px rgba(212, 175, 55, 0.6);
    }
}
`;

const styleSheet = document.createElement('style');
styleSheet.textContent = styles;
document.head.appendChild(styleSheet);

// Export singleton
export const mobileNav = new MobileNav();
export default mobileNav;
