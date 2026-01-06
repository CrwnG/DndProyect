/**
 * D&D 5e Loot Modal
 * BG3-style loot display and collection interface
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';

class LootModal {
    constructor() {
        this.loot = null;
        this.combatId = null;
        this.selectedItems = new Set();
        this.resolveCallback = null;
        this.createModal();
    }

    createModal() {
        const modal = document.createElement('div');
        modal.id = 'loot-modal';
        modal.className = 'modal loot-modal hidden';
        modal.innerHTML = `
            <div class="modal-overlay" id="loot-modal-overlay"></div>
            <div class="modal-content loot-content">
                <div class="loot-header">
                    <div class="loot-icon">&#128176;</div>
                    <h2>Victory Spoils</h2>
                    <div class="loot-value" id="loot-total-value">Total: 0 gp</div>
                </div>

                <div class="loot-body">
                    <!-- Coins Section -->
                    <div class="loot-section coins-section">
                        <h3>&#129689; Coins</h3>
                        <div class="coins-grid" id="loot-coins">
                            <!-- Dynamically populated -->
                        </div>
                    </div>

                    <!-- Gems & Art Section -->
                    <div class="loot-section valuables-section" id="valuables-section" style="display: none;">
                        <h3>&#128142; Gems & Art Objects</h3>
                        <div class="valuables-grid" id="loot-valuables">
                            <!-- Dynamically populated -->
                        </div>
                    </div>

                    <!-- Magic Items Section -->
                    <div class="loot-section magic-items-section" id="magic-items-section" style="display: none;">
                        <h3>&#10024; Magic Items</h3>
                        <div class="magic-items-grid" id="loot-magic-items">
                            <!-- Dynamically populated -->
                        </div>
                    </div>
                </div>

                <div class="loot-footer">
                    <button class="btn-loot-take-all" id="btn-loot-take-all">Take All</button>
                    <button class="btn-loot-take-selected" id="btn-loot-take-selected" disabled>Take Selected</button>
                    <button class="btn-loot-leave" id="btn-loot-leave">Leave</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        this.setupEventListeners();
        this.injectStyles();
    }

    setupEventListeners() {
        // Take all button
        document.getElementById('btn-loot-take-all')?.addEventListener('click', () => {
            this.collectAll();
        });

        // Take selected button
        document.getElementById('btn-loot-take-selected')?.addEventListener('click', () => {
            this.collectSelected();
        });

        // Leave button
        document.getElementById('btn-loot-leave')?.addEventListener('click', () => {
            this.hide();
        });

        // Overlay click to close
        document.getElementById('loot-modal-overlay')?.addEventListener('click', () => {
            this.hide();
        });

        // ESC to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !this.isHidden()) {
                this.hide();
            }
        });

        // Victory screen now handles loot display on combat end
        // Listen for user clicking "View Loot" from victory screen if needed
        eventBus.on(EVENTS.LOOT_COLLECTED, (data) => {
            if (data.combatId) {
                this.showFromCombat(data.combatId);
            }
        });
    }

    /**
     * Show loot modal with data from a combat encounter
     * @param {string} combatId - Combat ID
     */
    async showFromCombat(combatId) {
        this.combatId = combatId;

        try {
            const response = await api.getCombatLoot(combatId);
            if (response.success && response.loot) {
                this.show(response.loot);
            } else {
                console.log('[LootModal] No loot available for this combat');
            }
        } catch (error) {
            // 404 means no loot available - this is normal for some combats
            if (error.message?.includes('Not Found') || error.message?.includes('404')) {
                console.log('[LootModal] No loot generated for this combat (404)');
            } else {
                console.error('[LootModal] Failed to fetch loot:', error);
            }
            // Don't block campaign progression - loot is optional
        }
    }

    /**
     * Show the loot modal with given loot data
     * @param {Object} lootData - Loot data from backend
     */
    show(lootData) {
        this.loot = lootData;
        this.selectedItems.clear();
        this.render();

        const modal = document.getElementById('loot-modal');
        modal?.classList.remove('hidden');

        // Play loot sound if available
        this.playLootSound();
    }

    hide() {
        const modal = document.getElementById('loot-modal');
        modal?.classList.add('hidden');
        this.loot = null;
        this.combatId = null;
        this.selectedItems.clear();

        if (this.resolveCallback) {
            this.resolveCallback({ collected: false });
            this.resolveCallback = null;
        }
    }

    isHidden() {
        return document.getElementById('loot-modal')?.classList.contains('hidden');
    }

    render() {
        if (!this.loot) return;

        // Render coins
        this.renderCoins();

        // Render gems and art
        this.renderValuables();

        // Render magic items
        this.renderMagicItems();

        // Update total value
        const totalValue = document.getElementById('loot-total-value');
        if (totalValue) {
            totalValue.textContent = `Total: ${Math.round(this.loot.total_gold_value || 0)} gp`;
        }
    }

    renderCoins() {
        const container = document.getElementById('loot-coins');
        if (!container || !this.loot.coins) return;

        const coins = this.loot.coins;
        const coinTypes = [
            { key: 'pp', name: 'Platinum', icon: '&#9899;', color: '#E5E4E2' },
            { key: 'gp', name: 'Gold', icon: '&#128309;', color: '#FFD700' },
            { key: 'ep', name: 'Electrum', icon: '&#128309;', color: '#C0C0C0' },
            { key: 'sp', name: 'Silver', icon: '&#9898;', color: '#C0C0C0' },
            { key: 'cp', name: 'Copper', icon: '&#128308;', color: '#B87333' },
        ];

        let html = '';
        for (const coinType of coinTypes) {
            const amount = coins[coinType.key] || 0;
            if (amount > 0) {
                html += `
                    <div class="coin-item" style="border-color: ${coinType.color}">
                        <span class="coin-icon" style="color: ${coinType.color}">${coinType.icon}</span>
                        <span class="coin-amount">${amount.toLocaleString()}</span>
                        <span class="coin-name">${coinType.name}</span>
                    </div>
                `;
            }
        }

        if (!html) {
            html = '<div class="no-coins">No coins found</div>';
        }

        container.innerHTML = html;
    }

    renderValuables() {
        const container = document.getElementById('loot-valuables');
        const section = document.getElementById('valuables-section');
        if (!container || !section) return;

        const gems = this.loot.gems || [];
        const artObjects = this.loot.art_objects || [];
        const allValuables = [...gems, ...artObjects];

        if (allValuables.length === 0) {
            section.style.display = 'none';
            return;
        }

        section.style.display = 'block';

        let html = '';
        for (const item of allValuables) {
            const itemId = `valuable-${item.name.replace(/\s+/g, '-').toLowerCase()}`;
            const isSelected = this.selectedItems.has(itemId);
            const isGem = gems.includes(item);

            html += `
                <div class="valuable-item ${isSelected ? 'selected' : ''}"
                     data-item-id="${itemId}"
                     data-type="${isGem ? 'gem' : 'art'}"
                     title="${item.description || ''}">
                    <div class="valuable-icon">${isGem ? '&#128142;' : '&#127912;'}</div>
                    <div class="valuable-info">
                        <div class="valuable-name">${item.name}</div>
                        <div class="valuable-value">${item.value} gp</div>
                    </div>
                </div>
            `;
        }

        container.innerHTML = html;

        // Add click handlers
        container.querySelectorAll('.valuable-item').forEach(el => {
            el.addEventListener('click', () => {
                const itemId = el.dataset.itemId;
                this.toggleItemSelection(itemId, el);
            });
        });
    }

    renderMagicItems() {
        const container = document.getElementById('loot-magic-items');
        const section = document.getElementById('magic-items-section');
        if (!container || !section) return;

        const magicItems = this.loot.magic_items || [];

        if (magicItems.length === 0) {
            section.style.display = 'none';
            return;
        }

        section.style.display = 'block';

        const rarityColors = {
            'common': '#9d9d9d',
            'uncommon': '#1eff00',
            'rare': '#0070dd',
            'very_rare': '#a335ee',
            'legendary': '#ff8000',
            'artifact': '#e6cc80',
        };

        let html = '';
        for (const item of magicItems) {
            const itemId = item.id;
            const isSelected = this.selectedItems.has(itemId);
            const rarityColor = rarityColors[item.rarity] || '#ffffff';

            html += `
                <div class="magic-item ${isSelected ? 'selected' : ''}"
                     data-item-id="${itemId}"
                     data-rarity="${item.rarity}"
                     style="border-color: ${rarityColor}">
                    <div class="magic-item-header">
                        <span class="magic-item-name" style="color: ${rarityColor}">${item.name}</span>
                        ${item.requires_attunement ? '<span class="attunement-badge">Attunement</span>' : ''}
                    </div>
                    <div class="magic-item-meta">
                        <span class="magic-item-type">${item.type}</span>
                        <span class="magic-item-rarity">${this.formatRarity(item.rarity)}</span>
                    </div>
                    ${item.description ? `<div class="magic-item-desc">${item.description}</div>` : ''}
                </div>
            `;
        }

        container.innerHTML = html;

        // Add click handlers
        container.querySelectorAll('.magic-item').forEach(el => {
            el.addEventListener('click', () => {
                const itemId = el.dataset.itemId;
                this.toggleItemSelection(itemId, el);
            });
        });
    }

    toggleItemSelection(itemId, element) {
        if (this.selectedItems.has(itemId)) {
            this.selectedItems.delete(itemId);
            element.classList.remove('selected');
        } else {
            this.selectedItems.add(itemId);
            element.classList.add('selected');
        }

        // Update take selected button
        const takeSelectedBtn = document.getElementById('btn-loot-take-selected');
        if (takeSelectedBtn) {
            takeSelectedBtn.disabled = this.selectedItems.size === 0;
        }
    }

    formatRarity(rarity) {
        if (!rarity) return '';
        return rarity.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    async collectAll() {
        if (!this.combatId) {
            this.hide();
            return;
        }

        try {
            const gameState = state.getState();
            const characterId = gameState.playerId;

            const response = await api.collectLoot(this.combatId, characterId, [], true);

            if (response.success) {
                // Show collection notification
                state.addLogEntry({
                    type: 'loot',
                    message: `Collected ${Math.round(this.loot.total_gold_value || 0)} gp worth of treasure!`,
                });

                eventBus.emit(EVENTS.LOOT_COLLECTED, response.loot);
            }
        } catch (error) {
            console.error('[LootModal] Failed to collect loot:', error);
        }

        this.hide();
    }

    async collectSelected() {
        if (!this.combatId || this.selectedItems.size === 0) {
            return;
        }

        try {
            const gameState = state.getState();
            const characterId = gameState.playerId;
            const itemIds = Array.from(this.selectedItems);

            const response = await api.collectLoot(this.combatId, characterId, itemIds, true);

            if (response.success) {
                state.addLogEntry({
                    type: 'loot',
                    message: `Collected ${itemIds.length} items from the treasure.`,
                });

                eventBus.emit(EVENTS.LOOT_COLLECTED, response.loot);
            }
        } catch (error) {
            console.error('[LootModal] Failed to collect selected loot:', error);
        }

        this.hide();
    }

    playLootSound() {
        try {
            // Try to play loot collection sound
            const audio = new Audio('/sounds/loot-collect.mp3');
            audio.volume = 0.4;
            audio.play().catch(() => {
                // Ignore autoplay restrictions - sound is optional UX enhancement
            });
        } catch (e) {
            // Audio API not supported or file not found - silently continue
        }
    }

    injectStyles() {
        if (document.getElementById('loot-modal-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'loot-modal-styles';
        styles.textContent = `
            .loot-modal .modal-content.loot-content {
                max-width: 600px;
                background: linear-gradient(180deg, rgba(30, 25, 45, 0.98) 0%, rgba(20, 30, 50, 0.98) 100%);
                border: 2px solid var(--accent-gold, #d4af37);
                border-radius: 12px;
                box-shadow: 0 0 40px rgba(212, 175, 55, 0.3);
            }

            .loot-header {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 20px;
                border-bottom: 1px solid rgba(212, 175, 55, 0.3);
            }

            .loot-icon {
                font-size: 2rem;
            }

            .loot-header h2 {
                flex: 1;
                margin: 0;
                font-family: 'Cinzel', serif;
                color: var(--accent-gold, #d4af37);
            }

            .loot-value {
                font-size: 1.1rem;
                color: #ffd700;
                font-weight: bold;
            }

            .loot-body {
                padding: 16px 20px;
                max-height: 400px;
                overflow-y: auto;
            }

            .loot-section {
                margin-bottom: 20px;
            }

            .loot-section h3 {
                font-size: 1rem;
                color: #ffffff;
                margin: 0 0 12px 0;
                padding-bottom: 6px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }

            /* Coins Grid */
            .coins-grid {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
            }

            .coin-item {
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 10px 16px;
                background: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                min-width: 80px;
            }

            .coin-icon {
                font-size: 1.5rem;
            }

            .coin-amount {
                font-size: 1.2rem;
                font-weight: bold;
                color: #ffffff;
            }

            .coin-name {
                font-size: 0.75rem;
                color: #aaaaaa;
                text-transform: uppercase;
            }

            /* Valuables Grid */
            .valuables-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
                gap: 10px;
            }

            .valuable-item {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 10px;
                background: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.2s ease;
            }

            .valuable-item:hover {
                background: rgba(255, 255, 255, 0.05);
                border-color: rgba(255, 255, 255, 0.2);
            }

            .valuable-item.selected {
                border-color: var(--accent-gold, #d4af37);
                background: rgba(212, 175, 55, 0.1);
            }

            .valuable-icon {
                font-size: 1.5rem;
            }

            .valuable-name {
                font-size: 0.9rem;
                color: #ffffff;
            }

            .valuable-value {
                font-size: 0.8rem;
                color: #ffd700;
            }

            /* Magic Items Grid */
            .magic-items-grid {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }

            .magic-item {
                padding: 12px;
                background: rgba(0, 0, 0, 0.4);
                border: 2px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.2s ease;
            }

            .magic-item:hover {
                background: rgba(255, 255, 255, 0.05);
            }

            .magic-item.selected {
                box-shadow: 0 0 10px currentColor;
            }

            .magic-item-header {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 6px;
            }

            .magic-item-name {
                font-size: 1rem;
                font-weight: bold;
            }

            .attunement-badge {
                font-size: 0.65rem;
                padding: 2px 6px;
                background: rgba(163, 53, 238, 0.3);
                border: 1px solid #a335ee;
                border-radius: 4px;
                color: #a335ee;
            }

            .magic-item-meta {
                display: flex;
                gap: 12px;
                font-size: 0.8rem;
                color: #aaaaaa;
            }

            .magic-item-type {
                text-transform: capitalize;
            }

            .magic-item-rarity {
                text-transform: capitalize;
            }

            .magic-item-desc {
                margin-top: 8px;
                font-size: 0.85rem;
                color: #cccccc;
                line-height: 1.4;
            }

            /* Footer */
            .loot-footer {
                display: flex;
                gap: 10px;
                padding: 16px 20px;
                border-top: 1px solid rgba(212, 175, 55, 0.3);
            }

            .loot-footer button {
                flex: 1;
                padding: 12px 20px;
                border: none;
                border-radius: 6px;
                font-size: 1rem;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.2s ease;
            }

            .btn-loot-take-all {
                background: linear-gradient(180deg, #d4af37, #b8960c);
                color: #000;
            }

            .btn-loot-take-all:hover {
                background: linear-gradient(180deg, #e5c048, #c9a71d);
            }

            .btn-loot-take-selected {
                background: rgba(212, 175, 55, 0.2);
                color: #d4af37;
                border: 1px solid #d4af37;
            }

            .btn-loot-take-selected:hover:not(:disabled) {
                background: rgba(212, 175, 55, 0.3);
            }

            .btn-loot-take-selected:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }

            .btn-loot-leave {
                background: rgba(255, 255, 255, 0.1);
                color: #ffffff;
            }

            .btn-loot-leave:hover {
                background: rgba(255, 255, 255, 0.2);
            }

            .no-coins {
                color: #888;
                font-style: italic;
            }
        `;
        document.head.appendChild(styles);
    }
}

// Export singleton instance
const lootModal = new LootModal();
export default lootModal;
