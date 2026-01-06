/**
 * Inventory Modal - BG3-style equipment and inventory panel
 *
 * Combines:
 * - Paper Doll (equipment slots)
 * - Inventory Grid (backpack items)
 * - Encumbrance Bar
 * - Character stats summary
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import { equipmentManager } from '../equipment/equipment-manager.js';
import PaperDoll from './paper-doll.js';
import InventoryGrid from './inventory-grid.js';

class InventoryModal {
    constructor() {
        this.isOpen = false;
        this.element = null;
        this.paperDoll = null;
        this.inventoryGrid = null;
        this.createModal();
        this.setupKeyboardShortcut();
    }

    /**
     * Create the modal DOM element.
     */
    createModal() {
        this.element = document.createElement('div');
        this.element.id = 'inventory-modal';
        this.element.className = 'inventory-modal hidden';

        this.element.innerHTML = `
            <div class="inventory-modal-overlay" id="inventory-overlay"></div>
            <div class="inventory-modal-content">
                <div class="inventory-header">
                    <h2 class="inventory-title">Equipment & Inventory</h2>
                    <button class="inventory-close-btn" id="inventory-close-btn" title="Close (I)">&times;</button>
                </div>

                <div class="inventory-body">
                    <div class="inventory-left-panel">
                        <div class="character-summary" id="character-summary">
                            <!-- Character stats -->
                        </div>
                        <div class="paper-doll-container" id="paper-doll-container">
                            <!-- Paper doll renders here -->
                        </div>
                    </div>

                    <div class="inventory-right-panel">
                        <div class="inventory-search-sort">
                            <input type="text" id="inventory-search" class="inventory-search" placeholder="Search items..." />
                            <select id="inventory-sort" class="inventory-sort">
                                <option value="name">Name</option>
                                <option value="rarity">Rarity</option>
                                <option value="value">Value</option>
                                <option value="weight">Weight</option>
                                <option value="type">Type</option>
                            </select>
                        </div>
                        <div class="inventory-filters" id="inventory-filters">
                            <button class="filter-btn active" data-filter="all">All</button>
                            <button class="filter-btn" data-filter="weapon">Weapons</button>
                            <button class="filter-btn" data-filter="armor">Armor</button>
                            <button class="filter-btn" data-filter="consumable">Items</button>
                        </div>
                        <div class="inventory-grid-container" id="inventory-grid-container">
                            <!-- Inventory grid renders here -->
                        </div>
                    </div>
                </div>

                <div class="inventory-footer">
                    <div class="encumbrance-section" id="encumbrance-section">
                        <!-- Encumbrance bar -->
                    </div>
                    <div class="gold-section" id="gold-section">
                        <!-- Gold display -->
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(this.element);
        this.setupEventListeners();
    }

    /**
     * Set up event listeners.
     */
    setupEventListeners() {
        // Close button
        document.getElementById('inventory-close-btn')?.addEventListener('click', () => {
            this.hide();
        });

        // Overlay click to close
        document.getElementById('inventory-overlay')?.addEventListener('click', () => {
            this.hide();
        });

        // Search input
        document.getElementById('inventory-search')?.addEventListener('input', (e) => {
            if (this.inventoryGrid) {
                this.inventoryGrid.setSearchFilter(e.target.value);
            }
        });

        // Sort dropdown
        document.getElementById('inventory-sort')?.addEventListener('change', (e) => {
            if (this.inventoryGrid) {
                this.inventoryGrid.setSortBy(e.target.value);
            }
        });

        // Filter buttons
        document.getElementById('inventory-filters')?.addEventListener('click', (e) => {
            const btn = e.target.closest('.filter-btn');
            if (!btn) return;

            // Update active state
            document.querySelectorAll('#inventory-filters .filter-btn').forEach(b => {
                b.classList.remove('active');
            });
            btn.classList.add('active');

            // Apply filter
            const filter = btn.dataset.filter;
            if (this.inventoryGrid) {
                this.inventoryGrid.filterByType(filter);
            }
        });

        // Listen for equipment changes
        eventBus.on(EVENTS.EQUIPMENT_CHANGED, () => this.updateDisplay());
        eventBus.on(EVENTS.ITEM_EQUIPPED, () => this.updateDisplay());
        eventBus.on(EVENTS.ITEM_UNEQUIPPED, () => this.updateDisplay());
    }

    /**
     * Set up keyboard shortcut (I key).
     */
    setupKeyboardShortcut() {
        document.addEventListener('keydown', (e) => {
            // Ignore if typing in an input
            if (e.target.matches('input, textarea')) return;

            // Toggle on 'I' key
            if (e.key.toLowerCase() === 'i' && !e.ctrlKey && !e.altKey && !e.metaKey) {
                e.preventDefault();
                this.toggle();
            }

            // Close on Escape
            if (e.key === 'Escape' && this.isOpen) {
                this.hide();
            }
        });
    }

    /**
     * Show the inventory modal.
     */
    show() {
        console.log('[InventoryModal] show() called');
        try {
            // Set context for equipment manager - use getState() to get full state
            const gameState = state.getState();
            const combatState = gameState.combat;
            const playerId = gameState.playerId;
            const player = playerId ? gameState.combatants?.[playerId] : null;
            console.log('[InventoryModal] combatState:', combatState, 'player:', player, 'playerId:', playerId);

            // Set equipment context if in combat
            if (combatState?.combat_id && playerId) {
                equipmentManager.setContext(combatState.combat_id, playerId);
            } else if (combatState?.id && playerId) {
                equipmentManager.setContext(combatState.id, playerId);
            }

            // Initialize components
            this.initComponents();

            // Show modal
            this.element.classList.remove('hidden');
            this.isOpen = true;
            console.log('[InventoryModal] Modal shown, isOpen:', this.isOpen);

            // Update display
            this.updateDisplay();

            eventBus.emit(EVENTS.INVENTORY_OPENED);
            eventBus.emit(EVENTS.UI_MODAL_OPENED, { modal: 'inventory' });
        } catch (error) {
            console.error('[InventoryModal] Error in show():', error);
        }
    }

    /**
     * Hide the inventory modal.
     */
    hide() {
        this.element.classList.add('hidden');
        this.isOpen = false;

        eventBus.emit(EVENTS.INVENTORY_CLOSED);
        eventBus.emit(EVENTS.UI_MODAL_CLOSED, { modal: 'inventory' });
    }

    /**
     * Toggle the inventory modal.
     */
    toggle() {
        console.log('[InventoryModal] toggle() called, isOpen:', this.isOpen);
        if (this.isOpen) {
            this.hide();
        } else {
            this.show();
        }
    }

    /**
     * Initialize paper doll and inventory grid components.
     */
    initComponents() {
        const paperDollContainer = document.getElementById('paper-doll-container');
        const inventoryGridContainer = document.getElementById('inventory-grid-container');

        if (paperDollContainer && !this.paperDoll) {
            this.paperDoll = new PaperDoll(paperDollContainer);
            this.paperDoll.init();
        }

        if (inventoryGridContainer && !this.inventoryGrid) {
            this.inventoryGrid = new InventoryGrid(inventoryGridContainer, this.paperDoll);
            this.inventoryGrid.init();
        }
    }

    /**
     * Update the entire display.
     */
    updateDisplay() {
        this.updateCharacterSummary();
        this.updateEncumbrance();
        this.updateGold();

        if (this.paperDoll) {
            this.paperDoll.render();
        }
        if (this.inventoryGrid) {
            this.inventoryGrid.render();
        }
    }

    /**
     * Update character summary section.
     */
    updateCharacterSummary() {
        const container = document.getElementById('character-summary');
        if (!container) return;

        // Get player from state using correct API
        const gameState = state.getState();
        const playerId = gameState.playerId;
        const player = playerId ? gameState.combatants?.[playerId] : null;

        if (!player) {
            container.innerHTML = '<div class="no-character">No character loaded</div>';
            return;
        }

        const stats = player.stats || {};

        // Note: state-manager uses hp/maxHp (camelCase), not current_hp/max_hp (snake_case)
        const currentHp = player.hp ?? player.current_hp ?? '?';
        const maxHp = player.maxHp ?? player.max_hp ?? '?';
        // AC can come from top-level player.ac, stats.ac, or abilities
        const playerAc = player.ac ?? stats.ac ?? player.abilities?.ac ?? 10;
        const playerSpeed = player.speed ?? stats.speed ?? 30;

        // Debug: Log AC sources
        console.log('[InventoryModal] AC Debug:', {
            'player.ac': player.ac,
            'stats.ac': stats.ac,
            'player.abilities?.ac': player.abilities?.ac,
            'final playerAc': playerAc,
            'player keys': Object.keys(player)
        });

        container.innerHTML = `
            <div class="char-name">${player.name || 'Unknown'}</div>
            <div class="char-class">${stats.class || 'Adventurer'} Level ${stats.level || 1}</div>
            <div class="char-stats">
                <div class="stat-item">
                    <span class="stat-label">HP</span>
                    <span class="stat-value">${currentHp}/${maxHp}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">AC</span>
                    <span class="stat-value">${playerAc}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Speed</span>
                    <span class="stat-value">${playerSpeed} ft</span>
                </div>
            </div>
        `;
    }

    /**
     * Update encumbrance bar.
     */
    updateEncumbrance() {
        const container = document.getElementById('encumbrance-section');
        if (!container) return;

        const equipment = equipmentManager.getEquipment();
        // Get player from state using correct API
        const gameState = state.getState();
        const playerId = gameState.playerId;
        const player = playerId ? gameState.combatants?.[playerId] : null;
        const strength = player?.stats?.strength || player?.stats?.str || 10;

        const currentWeight = equipment?.current_weight || equipmentManager.calculateWeight();
        const maxCapacity = strength * 15;
        const normalLimit = strength * 5;
        const encumberedLimit = strength * 10;

        const percentage = Math.min(100, (currentWeight / maxCapacity) * 100);

        // Determine status
        let status = 'normal';
        let statusText = '';
        if (currentWeight > maxCapacity) {
            status = 'over-capacity';
            statusText = 'Over Capacity!';
        } else if (currentWeight > encumberedLimit) {
            status = 'heavily-encumbered';
            statusText = 'Heavily Encumbered (-20 speed)';
        } else if (currentWeight > normalLimit) {
            status = 'encumbered';
            statusText = 'Encumbered (-10 speed)';
        }

        container.innerHTML = `
            <div class="encumbrance-bar ${status}">
                <div class="encumbrance-fill" style="width: ${percentage}%"></div>
                <div class="encumbrance-markers">
                    <div class="marker normal" style="left: ${(normalLimit / maxCapacity) * 100}%"></div>
                    <div class="marker encumbered" style="left: ${(encumberedLimit / maxCapacity) * 100}%"></div>
                </div>
            </div>
            <div class="encumbrance-text">
                <span class="weight-value">${currentWeight.toFixed(1)} / ${maxCapacity} lb.</span>
                ${statusText ? `<span class="encumbrance-status">${statusText}</span>` : ''}
            </div>
        `;
    }

    /**
     * Update gold display.
     */
    updateGold() {
        const container = document.getElementById('gold-section');
        if (!container) return;

        const gameState = state.getState();
        const playerId = gameState.playerId;
        const player = playerId ? gameState.combatants?.[playerId] : null;
        const gold = player?.gold || player?.stats?.gold || 0;

        container.innerHTML = `
            <div class="gold-display">
                <span class="gold-icon">G</span>
                <span class="gold-amount">${gold.toLocaleString()}</span>
            </div>
        `;
    }

    /**
     * Check if modal is currently open.
     */
    isVisible() {
        return this.isOpen;
    }

    /**
     * Refresh equipment from API.
     */
    async refresh() {
        await equipmentManager.refreshEquipment();
        this.updateDisplay();
    }
}

// Export singleton instance
export const inventoryModal = new InventoryModal();
export default inventoryModal;
