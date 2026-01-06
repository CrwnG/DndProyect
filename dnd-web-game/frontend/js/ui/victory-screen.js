/**
 * D&D 5e Victory Screen
 * Full-screen BG3-style victory display with XP, loot, and level-up notifications
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';

class VictoryScreen {
    constructor() {
        this.combatSummary = null;
        this.resolveCallback = null;
        this.createScreen();
    }

    createScreen() {
        const screen = document.createElement('div');
        screen.id = 'victory-screen';
        screen.className = 'victory-screen hidden';
        screen.innerHTML = `
            <div class="victory-overlay"></div>
            <div class="victory-content">
                <div class="victory-header">
                    <div class="victory-glow"></div>
                    <h1 class="victory-title">VICTORY</h1>
                    <div class="victory-subtitle">Combat Complete</div>
                </div>

                <div class="victory-body">
                    <!-- Enemies Defeated Section -->
                    <div class="victory-section enemies-section">
                        <h3><span class="section-icon">&#9876;</span> Enemies Defeated</h3>
                        <div class="enemies-list" id="victory-enemies">
                            <!-- Dynamically populated -->
                        </div>
                    </div>

                    <!-- XP Section -->
                    <div class="victory-section xp-section">
                        <h3><span class="section-icon">&#11088;</span> Experience Gained</h3>
                        <div class="xp-display">
                            <div class="xp-amount" id="victory-xp-amount">+0 XP</div>
                            <div class="xp-progress-container">
                                <div class="xp-progress-bar" id="victory-xp-bar"></div>
                                <div class="xp-progress-text" id="victory-xp-text">0 / 300 XP to Level 3</div>
                            </div>
                        </div>
                    </div>

                    <!-- Level Up Section (hidden by default) -->
                    <div class="victory-section level-up-section hidden" id="victory-level-up-section">
                        <div class="level-up-banner">
                            <span class="level-up-icon">&#127881;</span>
                            <span class="level-up-text">LEVEL UP AVAILABLE!</span>
                            <span class="level-up-icon">&#127881;</span>
                        </div>
                    </div>

                    <!-- Loot Section -->
                    <div class="victory-section loot-section">
                        <h3><span class="section-icon">&#128176;</span> Loot Found</h3>
                        <div class="loot-preview" id="victory-loot">
                            <!-- Dynamically populated -->
                        </div>
                    </div>
                </div>

                <div class="victory-footer">
                    <button class="btn-victory-continue" id="btn-victory-continue">
                        Continue Adventure
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(screen);
        this.setupEventListeners();
        this.injectStyles();
    }

    setupEventListeners() {
        // Continue button
        document.getElementById('btn-victory-continue')?.addEventListener('click', () => {
            this.hide();
            if (this.resolveCallback) {
                this.resolveCallback();
                this.resolveCallback = null;
            }
            // Emit event that victory screen was dismissed
            eventBus.emit(EVENTS.VICTORY_DISMISSED, this.combatSummary);
        });

        // ESC to continue
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !this.isHidden()) {
                this.hide();
                if (this.resolveCallback) {
                    this.resolveCallback();
                    this.resolveCallback = null;
                }
                // Emit event that victory screen was dismissed
                eventBus.emit(EVENTS.VICTORY_DISMISSED, this.combatSummary);
            }
        });
    }

    /**
     * Show the victory screen with combat summary data
     * @param {Object} summary - Combat summary from API
     * @param {Object} playerData - Optional player character data for XP display
     * @returns {Promise} Resolves when user dismisses the screen
     */
    show(summary, playerData = null) {
        this.combatSummary = summary;
        this.populateContent(summary, playerData);

        const screen = document.getElementById('victory-screen');
        screen?.classList.remove('hidden');

        // Trigger animations
        setTimeout(() => {
            screen?.classList.add('active');
        }, 50);

        // Return promise that resolves when dismissed
        return new Promise((resolve) => {
            this.resolveCallback = resolve;
        });
    }

    hide() {
        const screen = document.getElementById('victory-screen');
        screen?.classList.remove('active');
        setTimeout(() => {
            screen?.classList.add('hidden');
        }, 300);
    }

    isHidden() {
        return document.getElementById('victory-screen')?.classList.contains('hidden');
    }

    populateContent(summary, playerData = null) {
        // Populate enemies defeated
        this.populateEnemies(summary.enemies_defeated || []);

        // Populate XP
        this.populateXP(summary, playerData);

        // Populate level-up section
        this.populateLevelUp(summary.level_ups || []);

        // Populate loot preview
        this.populateLoot(summary.loot);
    }

    populateEnemies(enemies) {
        const container = document.getElementById('victory-enemies');
        if (!container) return;

        if (enemies.length === 0) {
            container.innerHTML = '<div class="no-enemies">No enemies defeated</div>';
            return;
        }

        // Group enemies by name
        const grouped = {};
        enemies.forEach(enemy => {
            const name = enemy.name || 'Unknown';
            if (!grouped[name]) {
                grouped[name] = { count: 0, xp: 0, cr: enemy.cr };
            }
            grouped[name].count++;
            grouped[name].xp += enemy.xp || 0;
        });

        container.innerHTML = Object.entries(grouped).map(([name, data]) => `
            <div class="enemy-item">
                <span class="enemy-name">${name}${data.count > 1 ? ` x${data.count}` : ''}</span>
                <span class="enemy-cr">CR ${data.cr}</span>
                <span class="enemy-xp">${data.xp} XP</span>
            </div>
        `).join('');
    }

    populateXP(summary, playerData = null) {
        const xpAmount = document.getElementById('victory-xp-amount');
        const xpBar = document.getElementById('victory-xp-bar');
        const xpText = document.getElementById('victory-xp-text');

        if (!xpAmount || !xpBar || !xpText) return;

        const xpEarned = summary.xp_per_player || 0;
        xpAmount.textContent = `+${xpEarned} XP`;

        // Try to get current player XP for progress bar
        // First try playerData passed in, then fall back to state
        let player = playerData;
        if (!player) {
            const playerState = state.getState();
            player = playerState?.combatants ?
                Object.values(playerState.combatants).find(c => c.isPlayer || c.type === 'player') : null;
        }

        // XP thresholds by level (D&D 5e 2024)
        const XP_THRESHOLDS = {
            1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500,
            6: 14000, 7: 23000, 8: 34000, 9: 48000, 10: 64000,
            11: 85000, 12: 100000, 13: 120000, 14: 140000, 15: 165000,
            16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000
        };

        const currentLevel = player?.level || player?.stats?.level || 1;
        const currentXP = (player?.xp || 0) + xpEarned;
        const nextLevelXP = XP_THRESHOLDS[currentLevel + 1] || XP_THRESHOLDS[20];
        const currentLevelXP = XP_THRESHOLDS[currentLevel] || 0;

        const progress = Math.min(100, ((currentXP - currentLevelXP) / (nextLevelXP - currentLevelXP)) * 100);

        xpBar.style.width = `${progress}%`;
        xpText.textContent = `${currentXP} / ${nextLevelXP} XP to Level ${currentLevel + 1}`;

        // Animate XP counter
        this.animateNumber(xpAmount, 0, xpEarned, '+', ' XP');
    }

    populateLevelUp(levelUps) {
        const section = document.getElementById('victory-level-up-section');
        if (!section) return;

        if (levelUps.length > 0) {
            section.classList.remove('hidden');
            // Add pulse animation
            section.classList.add('pulse');
        } else {
            section.classList.add('hidden');
        }
    }

    populateLoot(loot) {
        const container = document.getElementById('victory-loot');
        if (!container) return;

        if (!loot) {
            container.innerHTML = '<div class="no-loot">No loot found</div>';
            return;
        }

        let html = '';

        // Coins
        const coins = loot.coins || {};
        const coinTypes = [
            { key: 'pp', name: 'Platinum', icon: '&#129689;', color: '#E5E4E2' },
            { key: 'gp', name: 'Gold', icon: '&#129689;', color: '#FFD700' },
            { key: 'ep', name: 'Electrum', icon: '&#129689;', color: '#B8B8B8' },
            { key: 'sp', name: 'Silver', icon: '&#129689;', color: '#C0C0C0' },
            { key: 'cp', name: 'Copper', icon: '&#129689;', color: '#B87333' },
        ];

        const hasCoins = Object.values(coins).some(v => v > 0);
        if (hasCoins) {
            html += '<div class="loot-coins">';
            coinTypes.forEach(coin => {
                const amount = coins[coin.key] || 0;
                if (amount > 0) {
                    html += `
                        <div class="coin-item" title="${coin.name}">
                            <span class="coin-icon" style="color: ${coin.color}">${coin.icon}</span>
                            <span class="coin-amount">${amount}</span>
                            <span class="coin-type">${coin.key}</span>
                        </div>
                    `;
                }
            });
            html += '</div>';
        }

        // Gems
        const gems = loot.gems || [];
        if (gems.length > 0) {
            html += '<div class="loot-gems">';
            gems.forEach(gem => {
                html += `
                    <div class="gem-item" title="${gem.name || gem.description}">
                        <span class="gem-icon">&#128142;</span>
                        <span class="gem-name">${gem.name || 'Gem'}</span>
                        <span class="gem-value">${gem.value || 0} gp</span>
                    </div>
                `;
            });
            html += '</div>';
        }

        // Art Objects
        const artObjects = loot.art_objects || [];
        if (artObjects.length > 0) {
            html += '<div class="loot-art">';
            artObjects.forEach(art => {
                html += `
                    <div class="art-item" title="${art.description || art.name}">
                        <span class="art-icon">&#127912;</span>
                        <span class="art-name">${art.name || 'Art Object'}</span>
                        <span class="art-value">${art.value || 0} gp</span>
                    </div>
                `;
            });
            html += '</div>';
        }

        // Magic Items
        const magicItems = loot.magic_items || [];
        if (magicItems.length > 0) {
            html += '<div class="loot-magic-items">';
            magicItems.forEach(item => {
                const rarityClass = `rarity-${item.rarity || 'common'}`;
                html += `
                    <div class="magic-item ${rarityClass}" title="${item.description || ''}">
                        <span class="item-icon">&#10024;</span>
                        <span class="item-name">${item.name}</span>
                        ${item.requires_attunement ? '<span class="attunement-badge">A</span>' : ''}
                    </div>
                `;
            });
            html += '</div>';
        }

        if (!html) {
            html = '<div class="no-loot">No treasure found</div>';
        }

        container.innerHTML = html;
    }

    animateNumber(element, start, end, prefix = '', suffix = '') {
        const duration = 1000;
        const startTime = performance.now();

        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3); // Ease out cubic
            const current = Math.round(start + (end - start) * eased);
            element.textContent = `${prefix}${current}${suffix}`;

            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };

        requestAnimationFrame(animate);
    }

    injectStyles() {
        if (document.getElementById('victory-screen-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'victory-screen-styles';
        styles.textContent = `
            .victory-screen {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
                opacity: 0;
                transition: opacity 0.3s ease;
            }

            .victory-screen.hidden {
                display: none;
            }

            .victory-screen.active {
                opacity: 1;
            }

            .victory-overlay {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: radial-gradient(ellipse at center, rgba(0,0,0,0.7) 0%, rgba(0,0,0,0.95) 100%);
            }

            .victory-content {
                position: relative;
                max-width: 600px;
                width: 90%;
                max-height: 90vh;
                overflow-y: auto;
                background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
                border: 2px solid #e6b800;
                border-radius: 12px;
                box-shadow: 0 0 50px rgba(230, 184, 0, 0.3), inset 0 0 30px rgba(0,0,0,0.5);
                animation: victorySlideIn 0.5s ease-out;
            }

            @keyframes victorySlideIn {
                from {
                    transform: scale(0.8) translateY(-30px);
                    opacity: 0;
                }
                to {
                    transform: scale(1) translateY(0);
                    opacity: 1;
                }
            }

            .victory-header {
                position: relative;
                text-align: center;
                padding: 30px 20px 20px;
                border-bottom: 1px solid rgba(230, 184, 0, 0.3);
            }

            .victory-glow {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 200px;
                height: 200px;
                background: radial-gradient(circle, rgba(230, 184, 0, 0.3) 0%, transparent 70%);
                animation: victoryPulse 2s ease-in-out infinite;
            }

            @keyframes victoryPulse {
                0%, 100% { opacity: 0.5; transform: translate(-50%, -50%) scale(1); }
                50% { opacity: 1; transform: translate(-50%, -50%) scale(1.1); }
            }

            .victory-title {
                position: relative;
                font-size: 3em;
                font-weight: bold;
                color: #ffd700;
                text-shadow: 0 0 20px rgba(255, 215, 0, 0.5), 0 2px 4px rgba(0,0,0,0.5);
                margin: 0;
                letter-spacing: 0.2em;
                animation: victoryTitleGlow 2s ease-in-out infinite;
            }

            @keyframes victoryTitleGlow {
                0%, 100% { text-shadow: 0 0 20px rgba(255, 215, 0, 0.5), 0 2px 4px rgba(0,0,0,0.5); }
                50% { text-shadow: 0 0 40px rgba(255, 215, 0, 0.8), 0 2px 4px rgba(0,0,0,0.5); }
            }

            .victory-subtitle {
                color: #b8a038;
                font-size: 1em;
                margin-top: 5px;
            }

            .victory-body {
                padding: 20px;
            }

            .victory-section {
                margin-bottom: 20px;
                padding: 15px;
                background: rgba(0,0,0,0.3);
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.1);
            }

            .victory-section h3 {
                color: #e6b800;
                margin: 0 0 12px 0;
                font-size: 1.1em;
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .section-icon {
                font-size: 1.2em;
            }

            /* Enemies Section */
            .enemies-list {
                display: flex;
                flex-direction: column;
                gap: 8px;
            }

            .enemy-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 12px;
                background: rgba(255,255,255,0.05);
                border-radius: 4px;
            }

            .enemy-name {
                color: #fff;
                flex: 1;
            }

            .enemy-cr {
                color: #888;
                margin-right: 15px;
            }

            .enemy-xp {
                color: #4CAF50;
                font-weight: bold;
            }

            /* XP Section */
            .xp-display {
                text-align: center;
            }

            .xp-amount {
                font-size: 2.5em;
                font-weight: bold;
                color: #4CAF50;
                text-shadow: 0 0 10px rgba(76, 175, 80, 0.5);
                margin-bottom: 15px;
            }

            .xp-progress-container {
                position: relative;
                height: 24px;
                background: rgba(0,0,0,0.5);
                border-radius: 12px;
                overflow: hidden;
                border: 1px solid rgba(76, 175, 80, 0.3);
            }

            .xp-progress-bar {
                height: 100%;
                background: linear-gradient(90deg, #2E7D32, #4CAF50);
                border-radius: 12px;
                transition: width 1s ease-out;
                box-shadow: 0 0 10px rgba(76, 175, 80, 0.5);
            }

            .xp-progress-text {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                color: #fff;
                font-size: 0.85em;
                text-shadow: 0 1px 2px rgba(0,0,0,0.5);
            }

            /* Level Up Section */
            .level-up-section {
                background: linear-gradient(90deg, rgba(255,215,0,0.1), rgba(255,215,0,0.2), rgba(255,215,0,0.1));
                border-color: #ffd700;
            }

            .level-up-banner {
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 15px;
                padding: 10px;
            }

            .level-up-text {
                font-size: 1.3em;
                font-weight: bold;
                color: #ffd700;
                text-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
            }

            .level-up-icon {
                font-size: 1.5em;
            }

            .level-up-section.pulse {
                animation: levelUpPulse 1s ease-in-out infinite;
            }

            @keyframes levelUpPulse {
                0%, 100% { box-shadow: 0 0 5px rgba(255, 215, 0, 0.3); }
                50% { box-shadow: 0 0 20px rgba(255, 215, 0, 0.6); }
            }

            /* Loot Section */
            .loot-preview {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }

            .loot-coins, .loot-gems, .loot-art, .loot-magic-items {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
            }

            .coin-item, .gem-item, .art-item {
                display: flex;
                align-items: center;
                gap: 5px;
                padding: 6px 10px;
                background: rgba(255,255,255,0.1);
                border-radius: 4px;
            }

            .coin-icon { font-size: 1.2em; }
            .coin-amount { color: #fff; font-weight: bold; }
            .coin-type { color: #888; text-transform: uppercase; font-size: 0.85em; }

            .gem-icon, .art-icon { font-size: 1em; }
            .gem-name, .art-name { color: #fff; }
            .gem-value, .art-value { color: #ffd700; margin-left: auto; }

            .magic-item {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 8px 12px;
                background: rgba(255,255,255,0.1);
                border-radius: 4px;
                border-left: 3px solid #9d9d9d;
            }

            .magic-item.rarity-common { border-color: #9d9d9d; }
            .magic-item.rarity-uncommon { border-color: #1eff00; }
            .magic-item.rarity-rare { border-color: #0070dd; }
            .magic-item.rarity-very_rare { border-color: #a335ee; }
            .magic-item.rarity-legendary { border-color: #ff8000; }
            .magic-item.rarity-artifact { border-color: #e6cc80; }

            .item-icon { font-size: 1.1em; }
            .item-name { color: #fff; }

            .attunement-badge {
                background: #a335ee;
                color: #fff;
                font-size: 0.7em;
                padding: 2px 5px;
                border-radius: 3px;
                margin-left: auto;
            }

            .no-loot, .no-enemies {
                color: #888;
                font-style: italic;
                text-align: center;
                padding: 10px;
            }

            /* Footer */
            .victory-footer {
                padding: 20px;
                text-align: center;
                border-top: 1px solid rgba(230, 184, 0, 0.3);
            }

            .btn-victory-continue {
                padding: 15px 40px;
                font-size: 1.2em;
                font-weight: bold;
                color: #1a1a2e;
                background: linear-gradient(180deg, #ffd700, #e6b800);
                border: none;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s ease;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                box-shadow: 0 4px 15px rgba(230, 184, 0, 0.4);
            }

            .btn-victory-continue:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(230, 184, 0, 0.6);
            }

            .btn-victory-continue:active {
                transform: translateY(0);
            }
        `;
        document.head.appendChild(styles);
    }
}

// Export singleton instance
export const victoryScreen = new VictoryScreen();
export default victoryScreen;
