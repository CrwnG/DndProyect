/**
 * Shop Modal - Buy and sell items from vendors
 *
 * Features:
 * - Split view: Shop inventory | Player inventory
 * - Item cards with price, rarity, stats preview
 * - Buy/Sell buttons with confirmation
 * - Gold display with transaction preview
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';
import toast from './toast-notification.js';
import { RARITY_COLORS } from '../equipment/equipment-manager.js';

class ShopModal {
    constructor() {
        this.isOpen = false;
        this.element = null;
        this.currentShop = null;
        this.playerInventory = [];
        this.createModal();
    }

    createModal() {
        this.element = document.createElement('div');
        this.element.id = 'shop-modal';
        this.element.className = 'shop-modal hidden';

        this.element.innerHTML = `
            <div class="shop-modal-overlay" id="shop-overlay"></div>
            <div class="shop-modal-content">
                <div class="shop-header">
                    <h2 class="shop-title" id="shop-title">Shop</h2>
                    <div class="shop-gold">
                        <span class="gold-icon">&#x1F4B0;</span>
                        <span class="gold-amount" id="shop-gold-amount">0</span>
                        <span class="gold-label">gp</span>
                    </div>
                    <button class="shop-close-btn" id="shop-close-btn">&times;</button>
                </div>

                <div class="shop-body">
                    <div class="shop-panel shop-inventory-panel">
                        <h3 class="panel-title">Shop Inventory</h3>
                        <div class="shop-items" id="shop-items"></div>
                    </div>

                    <div class="shop-panel player-inventory-panel">
                        <h3 class="panel-title">Your Items</h3>
                        <div class="player-items" id="player-items"></div>
                    </div>
                </div>

                <div class="shop-footer">
                    <span class="shop-owner" id="shop-owner"></span>
                    <span class="shop-description" id="shop-description"></span>
                </div>
            </div>
        `;

        document.body.appendChild(this.element);
        this.setupEventListeners();
    }

    setupEventListeners() {
        document.getElementById('shop-close-btn')?.addEventListener('click', () => {
            this.hide();
        });

        document.getElementById('shop-overlay')?.addEventListener('click', () => {
            this.hide();
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.hide();
            }
        });
    }

    async show(shopId) {
        try {
            // Load shop data
            const response = await api.getShop(shopId);
            if (!response.success) {
                toast.error('Failed to load shop');
                return;
            }

            this.currentShop = response.shop;
            this.loadPlayerInventory();

            // Update UI
            document.getElementById('shop-title').textContent = this.currentShop.name;
            document.getElementById('shop-owner').textContent = `Proprietor: ${this.currentShop.owner_name}`;
            document.getElementById('shop-description').textContent = this.currentShop.description;

            this.updateGoldDisplay();
            this.renderShopItems();
            this.renderPlayerItems();

            this.element.classList.remove('hidden');
            this.isOpen = true;

            eventBus.emit(EVENTS.UI_MODAL_OPENED, { modal: 'shop' });
        } catch (error) {
            console.error('[ShopModal] Error loading shop:', error);
            toast.error('Failed to open shop');
        }
    }

    hide() {
        this.element.classList.add('hidden');
        this.isOpen = false;
        this.currentShop = null;

        eventBus.emit(EVENTS.UI_MODAL_CLOSED, { modal: 'shop' });
    }

    loadPlayerInventory() {
        const gameState = state.getState();
        const playerId = gameState.playerId;
        const player = playerId ? gameState.combatants?.[playerId] : null;
        this.playerInventory = player?.inventory || [];
    }

    updateGoldDisplay() {
        const gameState = state.getState();
        const playerId = gameState.playerId;
        const combatantStats = gameState.combatant_stats?.[playerId] || {};
        const gold = combatantStats.gold || 0;

        document.getElementById('shop-gold-amount').textContent = gold.toLocaleString();
    }

    renderShopItems() {
        const container = document.getElementById('shop-items');
        if (!container || !this.currentShop) return;

        if (this.currentShop.inventory.length === 0) {
            container.innerHTML = '<div class="no-items">Shop is empty</div>';
            return;
        }

        container.innerHTML = this.currentShop.inventory.map(shopItem => {
            const item = shopItem.item_data;
            const price = Math.floor(shopItem.price * this.currentShop.buy_rate);
            const rarityColor = RARITY_COLORS[item.rarity || 'common'] || RARITY_COLORS.common;
            const stockText = shopItem.quantity === -1 ? '' : `(${shopItem.quantity} left)`;

            return `
                <div class="shop-item" data-item-id="${shopItem.item_id}" style="--rarity-color: ${rarityColor}">
                    <div class="item-icon">${item.icon || '&#x1F4E6;'}</div>
                    <div class="item-info">
                        <span class="item-name">${item.name}</span>
                        <span class="item-desc">${item.description || ''}</span>
                    </div>
                    <div class="item-price">
                        <span class="price-amount">${price}</span>
                        <span class="price-currency">gp</span>
                    </div>
                    <button class="buy-btn" data-item-id="${shopItem.item_id}" data-price="${price}">
                        Buy
                    </button>
                    <span class="stock-info">${stockText}</span>
                </div>
            `;
        }).join('');

        // Add buy button listeners
        container.querySelectorAll('.buy-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const itemId = e.target.dataset.itemId;
                const price = parseInt(e.target.dataset.price);
                this.buyItem(itemId, price);
            });
        });
    }

    renderPlayerItems() {
        const container = document.getElementById('player-items');
        if (!container) return;

        this.loadPlayerInventory();

        if (this.playerInventory.length === 0) {
            container.innerHTML = '<div class="no-items">No items to sell</div>';
            return;
        }

        container.innerHTML = this.playerInventory.map(item => {
            const sellPrice = Math.floor((item.value || 0) * this.currentShop.sell_rate);
            const rarityColor = RARITY_COLORS[item.rarity || 'common'] || RARITY_COLORS.common;

            return `
                <div class="shop-item player-item" data-item-id="${item.id}" style="--rarity-color: ${rarityColor}">
                    <div class="item-icon">${item.icon || '&#x1F4E6;'}</div>
                    <div class="item-info">
                        <span class="item-name">${item.name}</span>
                        <span class="item-desc">${item.description || ''}</span>
                    </div>
                    <div class="item-price sell-price">
                        <span class="price-amount">${sellPrice}</span>
                        <span class="price-currency">gp</span>
                    </div>
                    <button class="sell-btn" data-item-id="${item.id}" data-price="${sellPrice}">
                        Sell
                    </button>
                </div>
            `;
        }).join('');

        // Add sell button listeners
        container.querySelectorAll('.sell-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const itemId = e.target.dataset.itemId;
                const price = parseInt(e.target.dataset.price);
                this.sellItem(itemId, price);
            });
        });
    }

    async buyItem(itemId, price) {
        const gameState = state.getState();
        const combatId = gameState.combat?.id;
        const playerId = gameState.playerId;

        if (!combatId || !playerId) {
            toast.error('Cannot buy items outside of combat');
            return;
        }

        try {
            const response = await api.buyItem(
                this.currentShop.id,
                itemId,
                combatId,
                playerId
            );

            if (response.success) {
                toast.success(response.message);
                this.updateGoldDisplay();
                this.renderPlayerItems();

                // Update local state
                const player = gameState.combatants?.[playerId];
                if (player && response.item) {
                    const newItem = { ...response.item, id: `${itemId}_${Date.now()}` };
                    state.set(`combatants.${playerId}.inventory`, [...(player.inventory || []), newItem]);
                }

                eventBus.emit(EVENTS.GOLD_CHANGED, { gold: response.new_gold });
            } else {
                toast.error(response.message || 'Purchase failed');
            }
        } catch (error) {
            console.error('[ShopModal] Buy error:', error);
            toast.error(error.message || 'Failed to buy item');
        }
    }

    async sellItem(itemId, price) {
        const gameState = state.getState();
        const combatId = gameState.combat?.id;
        const playerId = gameState.playerId;

        if (!combatId || !playerId) {
            toast.error('Cannot sell items outside of combat');
            return;
        }

        try {
            const response = await api.sellItem(
                this.currentShop.id,
                itemId,
                combatId,
                playerId
            );

            if (response.success) {
                toast.success(response.message);
                this.updateGoldDisplay();

                // Update local state - remove item from inventory
                const player = gameState.combatants?.[playerId];
                if (player) {
                    const newInventory = player.inventory.filter(i => i.id !== itemId);
                    state.set(`combatants.${playerId}.inventory`, newInventory);
                }

                this.renderPlayerItems();

                eventBus.emit(EVENTS.GOLD_CHANGED, { gold: response.new_gold });
            } else {
                toast.error(response.message || 'Sale failed');
            }
        } catch (error) {
            console.error('[ShopModal] Sell error:', error);
            toast.error(error.message || 'Failed to sell item');
        }
    }
}

// Export singleton
export const shopModal = new ShopModal();
export default shopModal;
