/**
 * Inventory Grid Component
 *
 * Grid-based backpack display with:
 * - Grid layout (6 columns)
 * - Item icons with quantity badges
 * - Drag and drop to equipment slots
 * - Click to quick-equip
 * - Hover for item tooltip
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import { equipmentManager, RARITY_COLORS } from '../equipment/equipment-manager.js';
import itemTooltip from './item-tooltip.js';
import api from '../api/api-client.js';
import state from '../engine/state-manager.js';
import toast from './toast-notification.js';

class InventoryGrid {
    constructor(container, paperDoll = null) {
        this.container = container;
        this.paperDoll = paperDoll;  // Reference to paper doll for highlighting
        this.gridColumns = 6;
        this.items = [];
        this.selectedItem = null;
        // Search and sort state
        this.searchFilter = '';
        this.currentSort = 'name';
        this.typeFilter = 'all';
    }

    /**
     * Initialize the inventory grid.
     */
    init() {
        this.render();
        this.setupEventListeners();
    }

    /**
     * Render the inventory grid.
     */
    render() {
        if (!this.container) return;

        // Get all items and apply filters
        let allItems = equipmentManager.getInventory();

        // Apply type filter
        if (this.typeFilter && this.typeFilter !== 'all') {
            allItems = allItems.filter(item =>
                item.item_type?.toLowerCase() === this.typeFilter.toLowerCase()
            );
        }

        // Apply search filter
        if (this.searchFilter) {
            const searchLower = this.searchFilter.toLowerCase();
            allItems = allItems.filter(item =>
                item.name?.toLowerCase().includes(searchLower) ||
                item.description?.toLowerCase().includes(searchLower)
            );
        }

        // Apply sort
        this.items = this.applySorting(allItems);

        // Calculate grid rows needed (minimum 3 rows)
        const minRows = 3;
        const rowsNeeded = Math.max(minRows, Math.ceil(this.items.length / this.gridColumns) + 1);
        const totalCells = rowsNeeded * this.gridColumns;

        let cellsHtml = '';
        for (let i = 0; i < totalCells; i++) {
            const item = this.items[i];
            cellsHtml += this.renderCell(i, item);
        }

        this.container.innerHTML = `
            <div class="inventory-grid-header">
                <span class="inventory-title">Inventory</span>
                <span class="inventory-count">${this.items.length} items</span>
            </div>
            <div class="inventory-grid" style="grid-template-columns: repeat(${this.gridColumns}, 1fr);">
                ${cellsHtml}
            </div>
        `;
    }

    /**
     * Apply sorting to items array.
     */
    applySorting(items) {
        const sortFunctions = {
            name: (a, b) => (a.name || '').localeCompare(b.name || ''),
            type: (a, b) => (a.item_type || '').localeCompare(b.item_type || ''),
            rarity: (a, b) => {
                const rarityOrder = ['common', 'uncommon', 'rare', 'very_rare', 'legendary', 'artifact'];
                return rarityOrder.indexOf(b.rarity || 'common') - rarityOrder.indexOf(a.rarity || 'common');
            },
            weight: (a, b) => (a.weight || 0) - (b.weight || 0),
            value: (a, b) => (b.value || 0) - (a.value || 0),
        };

        const sortFn = sortFunctions[this.currentSort];
        if (sortFn) {
            return [...items].sort(sortFn);
        }
        return items;
    }

    /**
     * Render a single inventory cell.
     */
    renderCell(index, item) {
        const isEmpty = !item;
        const rarityColor = item ? RARITY_COLORS[item.rarity || 'common'] : '';

        return `
            <div class="inventory-cell ${isEmpty ? 'empty' : 'has-item'}"
                 data-index="${index}"
                 ${item ? `data-item-id="${item.id}"` : ''}
                 draggable="${!isEmpty}"
                 ${item ? `style="--rarity-color: ${rarityColor}"` : ''}>
                ${item ? `
                    <div class="inventory-item">
                        <span class="item-icon">${item.icon || '📦'}</span>
                        ${item.quantity > 1 ? `<span class="item-quantity">${item.quantity}</span>` : ''}
                    </div>
                    <div class="item-rarity-indicator"></div>
                ` : ''}
            </div>
        `;
    }

    /**
     * Set up event listeners.
     */
    setupEventListeners() {
        this.container.addEventListener('click', (e) => this.handleCellClick(e));
        this.container.addEventListener('contextmenu', (e) => this.handleContextMenu(e));
        this.container.addEventListener('mouseenter', (e) => this.handleMouseEnter(e), true);
        this.container.addEventListener('mouseleave', (e) => this.handleMouseLeave(e), true);
        this.container.addEventListener('mousemove', (e) => this.handleMouseMove(e));

        // Drag and drop
        this.container.addEventListener('dragstart', (e) => this.handleDragStart(e));
        this.container.addEventListener('dragend', (e) => this.handleDragEnd(e));
        this.container.addEventListener('dragover', (e) => this.handleDragOver(e));
        this.container.addEventListener('drop', (e) => this.handleDrop(e));

        // Listen for equipment changes
        eventBus.on(EVENTS.EQUIPMENT_CHANGED, () => this.render());
        eventBus.on(EVENTS.ITEM_EQUIPPED, () => this.render());
        eventBus.on(EVENTS.ITEM_UNEQUIPPED, () => this.render());
    }

    /**
     * Handle cell click - select item or quick-equip.
     */
    handleCellClick(e) {
        const cell = e.target.closest('.inventory-cell');
        if (!cell || cell.classList.contains('empty')) return;

        const itemId = cell.dataset.itemId;
        const item = this.items.find(i => i.id === itemId);

        if (!item) return;

        // Double-click to quick-equip
        if (e.detail === 2) {
            this.quickEquip(item);
        } else {
            // Single click to select
            this.selectItem(cell, item);
        }
    }

    /**
     * Handle right-click context menu.
     */
    handleContextMenu(e) {
        e.preventDefault();

        const cell = e.target.closest('.inventory-cell');
        if (!cell || cell.classList.contains('empty')) return;

        const itemId = cell.dataset.itemId;
        const item = this.items.find(i => i.id === itemId);

        if (item) {
            this.showContextMenu(item, e.clientX, e.clientY);
        }
    }

    /**
     * Handle mouse enter - show tooltip.
     */
    handleMouseEnter(e) {
        const cell = e.target.closest('.inventory-cell');
        if (!cell || cell.classList.contains('empty')) return;

        const itemId = cell.dataset.itemId;
        const item = this.items.find(i => i.id === itemId);

        if (item) {
            itemTooltip.show(item, e.clientX, e.clientY);
        }
    }

    /**
     * Handle mouse leave - hide tooltip.
     */
    handleMouseLeave(e) {
        const cell = e.target.closest('.inventory-cell');
        if (!cell) return;

        const relatedTarget = e.relatedTarget;
        if (!cell.contains(relatedTarget)) {
            itemTooltip.hide();
        }
    }

    /**
     * Handle mouse move - update tooltip position.
     */
    handleMouseMove(e) {
        itemTooltip.updatePosition(e.clientX, e.clientY);
    }

    /**
     * Handle drag start.
     */
    handleDragStart(e) {
        const cell = e.target.closest('.inventory-cell');
        if (!cell || cell.classList.contains('empty')) {
            e.preventDefault();
            return;
        }

        const itemId = cell.dataset.itemId;
        const item = this.items.find(i => i.id === itemId);

        if (item) {
            e.dataTransfer.setData('text/plain', JSON.stringify({
                itemId: item.id,
                source: 'inventory',
            }));
            e.dataTransfer.effectAllowed = 'move';

            cell.classList.add('dragging');
            itemTooltip.hide();

            // Highlight valid equipment slots in paper doll
            if (this.paperDoll) {
                this.paperDoll.highlightSlotsForItem(item);
            }
        }
    }

    /**
     * Handle drag end.
     */
    handleDragEnd(e) {
        const cell = e.target.closest('.inventory-cell');
        if (cell) {
            cell.classList.remove('dragging');
        }

        // Clear paper doll highlights
        if (this.paperDoll) {
            this.paperDoll.clearHighlights();
        }
    }

    /**
     * Handle drag over.
     */
    handleDragOver(e) {
        const cell = e.target.closest('.inventory-cell');
        if (cell && cell.classList.contains('empty')) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        }
    }

    /**
     * Handle drop.
     */
    async handleDrop(e) {
        e.preventDefault();

        const cell = e.target.closest('.inventory-cell');
        if (!cell) return;

        try {
            const data = JSON.parse(e.dataTransfer.getData('text/plain'));

            if (data.source === 'paper-doll') {
                // Unequip from paper doll to inventory
                await equipmentManager.unequipItem(data.fromSlot);
            }
            // Inventory-to-inventory rearrangement could be added here
        } catch (error) {
            console.error('[InventoryGrid] Drop error:', error);
        }
    }

    /**
     * Select an item (visual selection).
     */
    selectItem(cell, item) {
        // Clear previous selection
        this.container.querySelectorAll('.inventory-cell.selected').forEach(el => {
            el.classList.remove('selected');
        });

        cell.classList.add('selected');
        this.selectedItem = item;

        eventBus.emit(EVENTS.ITEM_SELECTED, { item, source: 'inventory' });
    }

    /**
     * Quick-equip item to best slot.
     */
    async quickEquip(item) {
        const validSlots = equipmentManager.getValidSlotsForItem(item);

        if (validSlots.length === 0) {
            console.log('[InventoryGrid] No valid slots for item:', item.name);
            return;
        }

        // Try to equip to first empty valid slot
        const equipped = equipmentManager.getEquippedItems();
        const emptySlot = validSlots.find(slot => !equipped[slot]);

        const targetSlot = emptySlot || validSlots[0];

        const result = await equipmentManager.equipItem(item.id, targetSlot);
        if (result.success) {
            console.log('[InventoryGrid] Quick-equipped', item.name, 'to', targetSlot);
        }
    }

    /**
     * Check if an item is a consumable (potion, scroll, etc.)
     */
    isConsumable(item) {
        if (!item) return false;
        // Check by type
        if (item.type === 'consumable' || item.item_type === 'consumable') return true;
        // Check by ID patterns
        if (item.id?.includes('potion') || item.id?.includes('scroll')) return true;
        // Check by name patterns
        const name = (item.name || '').toLowerCase();
        if (name.includes('potion') || name.includes('scroll') || name.includes('elixir')) return true;
        return false;
    }

    /**
     * Use a consumable item in combat
     */
    async useConsumable(item) {
        const gameState = state.getState();
        const combatId = gameState.combat?.id;
        const playerId = gameState.playerId;

        // Check if in combat
        if (!combatId) {
            toast.warning('Can only use items during combat');
            return;
        }

        // Check if bonus action is available (D&D 2024: potions are bonus action)
        if (gameState.turn?.bonusActionUsed) {
            toast.warning('Bonus action already used this turn');
            return;
        }

        if (!state.isPlayerTurn()) {
            toast.warning('Can only use items on your turn');
            return;
        }

        try {
            const response = await api.useItem(combatId, playerId, item.id);

            if (response.success) {
                // Mark bonus action as used
                state.set('turn.bonusActionUsed', true);

                // Show success message - backend returns 'effect' (singular), not 'effects'
                const effect = response.effect || {};
                const healAmount = effect.healing || effect.rolled || 0;
                if (healAmount > 0) {
                    toast.success(`Used ${item.name}: Healed ${healAmount} HP!`);

                    // Emit healing event for animation
                    eventBus.emit(EVENTS.HEALING_RECEIVED, {
                        combatantId: playerId,
                        amount: healAmount,
                        newHp: effect.new_hp,
                        maxHp: effect.max_hp,
                    });
                } else {
                    toast.success(`Used ${item.name}`);
                }

                // Update combat state
                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                // Refresh inventory display
                this.render();

                // Log the action
                state.addLogEntry({
                    type: 'player_action',
                    actor: gameState.combatants?.[playerId]?.name || 'Player',
                    message: `used ${item.name}`,
                });
            } else {
                toast.error(response.message || `Failed to use ${item.name}`);
            }
        } catch (error) {
            console.error('[InventoryGrid] Use consumable failed:', error);
            toast.error(`Failed to use ${item.name}: ${error.message}`);
        }
    }

    /**
     * Drop an item on the ground at the player's position
     */
    async dropItem(item) {
        const gameState = state.getState();
        const combatId = gameState.combat?.id;
        const playerId = gameState.playerId;

        if (!combatId) {
            toast.warning('Can only drop items during combat');
            return;
        }

        // Get player's current position
        const position = gameState.grid?.positions?.[playerId];
        const posArray = position ? [position.x, position.y] : null;

        try {
            const response = await api.dropItem(combatId, playerId, item.id, posArray);

            if (response.success) {
                toast.success(`Dropped ${item.name}`);

                // FIX: Update ALL possible item locations in local state
                // 1. combatant_stats.inventory (picked up items, potions)
                const currentStats = state.get(`combatant_stats.${playerId}`) || {};
                if (currentStats.inventory) {
                    const newInventory = currentStats.inventory.filter(i => i.id !== item.id);
                    state.set(`combatant_stats.${playerId}.inventory`, newInventory);
                }

                // 2. combatants.${playerId}.inventory (player's direct inventory)
                const player = state.get(`combatants.${playerId}`);
                if (player?.inventory) {
                    const newInv = player.inventory.filter(i => i.id !== item.id);
                    state.set(`combatants.${playerId}.inventory`, newInv);
                }

                // 3. combatants.${playerId}.equipment.inventory (unequipped items from slots)
                if (player?.equipment?.inventory) {
                    const newEquipInv = player.equipment.inventory.filter(i => i.id !== item.id);
                    state.set(`combatants.${playerId}.equipment.inventory`, newEquipInv);
                }

                // 4. If item was equipped, clear the slot (check all weapon/gear slots)
                if (player?.equipment) {
                    const slots = ['main_hand', 'off_hand', 'ranged', 'armor', 'head', 'cloak', 'gloves', 'boots', 'amulet', 'belt', 'ring_1', 'ring_2'];
                    for (const slot of slots) {
                        const equipped = player.equipment[slot];
                        if (equipped && equipped.id === item.id) {
                            state.set(`combatants.${playerId}.equipment.${slot}`, null);
                            break;
                        }
                    }
                }

                // Emit event for UI updates (grid can show dropped items)
                eventBus.emit(EVENTS.ITEM_DROPPED, {
                    item,
                    position: posArray,
                    groundItems: response.ground_items,
                });

                // Refresh inventory display
                this.render();

                // Log the action
                state.addLogEntry({
                    type: 'player_action',
                    actor: gameState.combatants?.[playerId]?.name || 'Player',
                    message: `dropped ${item.name}`,
                });
            } else {
                toast.error(response.message || `Failed to drop ${item.name}`);
            }
        } catch (error) {
            console.error('[InventoryGrid] Drop item failed:', error);
            toast.error(`Failed to drop ${item.name}: ${error.message}`);
        }
    }

    /**
     * Show context menu for an item.
     */
    showContextMenu(item, x, y) {
        // Remove any existing context menu
        const existing = document.querySelector('.inventory-context-menu');
        if (existing) existing.remove();

        const validSlots = equipmentManager.getValidSlotsForItem(item);
        const isConsumable = this.isConsumable(item);

        const menu = document.createElement('div');
        menu.className = 'inventory-context-menu';
        menu.style.left = `${x}px`;
        menu.style.top = `${y}px`;

        let menuHtml = `
            <div class="context-menu-header">${item.name}</div>
        `;

        // Use option for consumables (potions, scrolls)
        if (isConsumable) {
            const gameState = state.getState();
            const inCombat = !!gameState.combat?.id;
            const canUse = inCombat && state.isPlayerTurn() && !gameState.turn?.bonusActionUsed;

            menuHtml += `
                <button class="context-menu-item use-item ${!canUse ? 'disabled' : ''}"
                        data-action="use" ${!canUse ? 'disabled' : ''}>
                    🧪 Use${!inCombat ? ' (combat only)' : ''}
                </button>
            `;
        }

        // Equip options
        if (validSlots.length > 0) {
            validSlots.forEach(slot => {
                const slotName = slot.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                menuHtml += `
                    <button class="context-menu-item" data-action="equip" data-slot="${slot}">
                        Equip to ${slotName}
                    </button>
                `;
            });
        }

        // Drop option
        menuHtml += `
            <button class="context-menu-item danger" data-action="drop">
                Drop Item
            </button>
        `;

        menu.innerHTML = menuHtml;
        document.body.appendChild(menu);

        // Handle menu clicks
        menu.addEventListener('click', async (e) => {
            const button = e.target.closest('.context-menu-item');
            if (!button || button.disabled) return;

            const action = button.dataset.action;

            if (action === 'use') {
                await this.useConsumable(item);
            } else if (action === 'equip') {
                const slot = button.dataset.slot;
                await equipmentManager.equipItem(item.id, slot);
            } else if (action === 'drop') {
                await this.dropItem(item);
            }

            menu.remove();
        });

        // Close on click outside
        const closeHandler = (e) => {
            if (!menu.contains(e.target)) {
                menu.remove();
                document.removeEventListener('click', closeHandler);
            }
        };
        setTimeout(() => document.addEventListener('click', closeHandler), 0);
    }

    /**
     * Filter inventory by item type.
     */
    filterByType(type) {
        this.typeFilter = type || 'all';
        this.render();
    }

    /**
     * Set search filter text.
     */
    setSearchFilter(searchText) {
        this.searchFilter = searchText || '';
        this.render();
    }

    /**
     * Set sort order.
     */
    setSortBy(property) {
        this.currentSort = property || 'name';
        this.render();
    }

    /**
     * Sort inventory by a property (legacy method).
     */
    sortBy(property) {
        this.setSortBy(property);
    }

    /**
     * Get total count of items.
     */
    getItemCount() {
        return this.items.length;
    }

    /**
     * Connect to paper doll for highlighting.
     */
    setPaperDoll(paperDoll) {
        this.paperDoll = paperDoll;
    }
}

export { InventoryGrid };
export default InventoryGrid;
