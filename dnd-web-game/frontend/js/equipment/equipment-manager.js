/**
 * Equipment Manager - Central logic for equipment operations
 *
 * Handles:
 * - Equipment state management
 * - Equip/unequip operations with API sync
 * - Weight calculation and encumbrance
 * - Slot validation
 * - Event emission for UI updates
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';

// Equipment slot definitions matching BG3-style paper doll layout
export const EQUIPMENT_SLOTS = {
    // Weapons
    MAIN_HAND: {
        id: 'main_hand',
        name: 'Main Hand',
        icon: '🗡️',
        accepts: ['weapon'],
        position: { row: 4, col: 2 }
    },
    OFF_HAND: {
        id: 'off_hand',
        name: 'Off Hand',
        icon: '🛡️',
        accepts: ['weapon', 'shield'],
        position: { row: 5, col: 2 }
    },
    RANGED: {
        id: 'ranged',
        name: 'Ranged',
        icon: '🏹',
        accepts: ['weapon'],
        position: { row: 5, col: 3 }
    },

    // Protection
    HEAD: {
        id: 'head',
        name: 'Head',
        icon: '🪖',
        accepts: ['helmet', 'circlet', 'hat', 'head'],
        position: { row: 1, col: 2 }
    },
    ARMOR: {
        id: 'armor',
        name: 'Armor',
        icon: '🎽',
        accepts: ['armor'],
        position: { row: 2, col: 2 }
    },
    CLOAK: {
        id: 'cloak',
        name: 'Cloak',
        icon: '🧥',
        accepts: ['cloak', 'cape'],
        position: { row: 2, col: 1 }
    },
    GLOVES: {
        id: 'gloves',
        name: 'Gloves',
        icon: '🧤',
        accepts: ['gloves', 'gauntlets'],
        position: { row: 3, col: 1 }
    },
    BOOTS: {
        id: 'boots',
        name: 'Boots',
        icon: '👢',
        accepts: ['boots', 'shoes'],
        position: { row: 4, col: 1 }
    },

    // Accessories
    AMULET: {
        id: 'amulet',
        name: 'Amulet',
        icon: '📿',
        accepts: ['amulet', 'necklace'],
        position: { row: 2, col: 3 }
    },
    BELT: {
        id: 'belt',
        name: 'Belt',
        icon: '🎀',
        accepts: ['belt', 'girdle'],
        position: { row: 3, col: 2 }
    },
    RING_1: {
        id: 'ring_1',
        name: 'Ring',
        icon: '💍',
        accepts: ['ring'],
        position: { row: 3, col: 3 }
    },
    RING_2: {
        id: 'ring_2',
        name: 'Ring',
        icon: '💍',
        accepts: ['ring'],
        position: { row: 4, col: 3 }
    },
};

// Rarity colors for item display
export const RARITY_COLORS = {
    common: '#9d9d9d',
    uncommon: '#1eff00',
    rare: '#0070dd',
    very_rare: '#a335ee',
    legendary: '#ff8000',
    artifact: '#e6cc80',
};

// Weapon mastery descriptions
export const MASTERY_DESCRIPTIONS = {
    cleave: 'Hit another creature in reach with the same attack roll',
    graze: 'Deal ability modifier damage on a miss',
    push: 'Push target 10 feet away on hit',
    topple: 'Target must save or fall prone',
    nick: 'Make an extra attack with light weapon as bonus action',
    vex: 'Gain advantage on next attack against this target',
    sap: 'Target has disadvantage on next attack',
    slow: 'Reduce target speed by 10 feet',
};

class EquipmentManager {
    constructor() {
        this.selectedItem = null;
        this.draggedItem = null;
        this.currentCombatId = null;
        this.currentCombatantId = null;
        this.cachedItems = null;
    }

    /**
     * Set the current combat context for equipment operations.
     */
    setContext(combatId, combatantId) {
        this.currentCombatId = combatId;
        this.currentCombatantId = combatantId;
    }

    /**
     * Get equipment for the current player from state.
     */
    getEquipment() {
        const gameState = state.getState();
        const playerId = gameState.playerId;
        const player = playerId ? gameState.combatants?.[playerId] : null;
        if (!player) return null;

        return player.equipment || {
            main_hand: null,
            off_hand: null,
            ranged: null,
            armor: null,
            head: null,
            cloak: null,
            gloves: null,
            boots: null,
            amulet: null,
            belt: null,
            ring_1: null,
            ring_2: null,
            inventory: [],
            carrying_capacity: 150,
            current_weight: 0,
        };
    }

    /**
     * Get all equipped items as a flat object.
     */
    getEquippedItems() {
        const equipment = this.getEquipment();
        if (!equipment) return {};

        return {
            main_hand: equipment.main_hand,
            off_hand: equipment.off_hand,
            ranged: equipment.ranged,
            armor: equipment.armor,
            head: equipment.head,
            cloak: equipment.cloak,
            gloves: equipment.gloves,
            boots: equipment.boots,
            amulet: equipment.amulet,
            belt: equipment.belt,
            ring_1: equipment.ring_1,
            ring_2: equipment.ring_2,
        };
    }

    /**
     * Get inventory items.
     * Merges items from equipment.inventory and combatant_stats.inventory (for combat items like potions)
     */
    getInventory() {
        const gameState = state.getState();
        const playerId = gameState.playerId;

        // Get inventory from equipment state
        const equipment = this.getEquipment();
        const equipmentInventory = equipment?.inventory || [];

        // Also check combatant_stats.inventory (where combat items like potions are stored)
        const combatStats = gameState.combatant_stats?.[playerId] || {};
        const combatInventory = combatStats.inventory || [];

        // Also check player.inventory directly
        const player = playerId ? gameState.combatants?.[playerId] : null;
        const playerInventory = player?.inventory || [];

        // Merge all sources, avoiding duplicates by ID
        const itemMap = new Map();

        // Add items from all sources
        [...equipmentInventory, ...combatInventory, ...playerInventory].forEach(item => {
            if (item && item.id) {
                // If item already exists, update quantity
                if (itemMap.has(item.id)) {
                    const existing = itemMap.get(item.id);
                    existing.quantity = (existing.quantity || 1) + (item.quantity || 1) - 1;
                } else {
                    itemMap.set(item.id, { ...item });
                }
            }
        });

        return Array.from(itemMap.values());
    }

    /**
     * Check if an item can be equipped to a specific slot.
     */
    canEquipToSlot(item, slotId) {
        const slot = Object.values(EQUIPMENT_SLOTS).find(s => s.id === slotId);
        if (!slot) return false;
        if (!item) return true; // Empty slot accepts anything

        // Check item type against slot's accepted types
        const itemType = item.item_type?.toLowerCase() || '';
        const validSlots = item.valid_slots || [];

        // If item has explicit valid_slots, check that first
        if (validSlots.length > 0) {
            return validSlots.includes(slotId);
        }

        // Otherwise check by item type
        return slot.accepts.some(accepted =>
            itemType.includes(accepted) || accepted.includes(itemType)
        );
    }

    /**
     * Get valid slots for an item.
     */
    getValidSlotsForItem(item) {
        if (!item) return [];

        return Object.values(EQUIPMENT_SLOTS)
            .filter(slot => this.canEquipToSlot(item, slot.id))
            .map(slot => slot.id);
    }

    /**
     * Equip an item from inventory to a slot.
     */
    async equipItem(itemId, slotId) {
        if (!this.currentCombatId || !this.currentCombatantId) {
            console.error('[EquipmentManager] No combat context set');
            return { success: false, error: 'No combat context' };
        }

        try {
            const result = await api.equipItem(
                this.currentCombatId,
                this.currentCombatantId,
                itemId,
                slotId
            );

            if (result.success) {
                // Update combatant_stats.inventory if returned (item was picked up from ground)
                const gameState = state.getState();
                const playerId = gameState.playerId;
                if (playerId && result.combat_inventory !== undefined) {
                    state.set(`combatant_stats.${playerId}.inventory`, result.combat_inventory);
                }

                // ALSO remove the equipped item from combatants.${playerId}.inventory
                // (pickup adds to both locations, so we need to clean up both)
                if (playerId) {
                    const player = gameState.combatants?.[playerId];
                    if (player?.inventory) {
                        const updatedPlayerInv = player.inventory.filter(i => i.id !== itemId);
                        state.set(`combatants.${playerId}.inventory`, updatedPlayerInv);
                    }
                }

                // Refresh equipment state
                await this.refreshEquipment();

                // Emit event for UI update
                eventBus.emit(EVENTS.ITEM_EQUIPPED, {
                    itemId,
                    slot: slotId,
                    item: result.equipped,
                });

                return { success: true, item: result.equipped };
            }

            return { success: false, error: result.message || 'Failed to equip' };
        } catch (error) {
            console.error('[EquipmentManager] Equip error:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Unequip an item from a slot to inventory.
     */
    async unequipItem(slotId) {
        console.log('[EquipmentManager] unequipItem called for slot:', slotId);
        console.log('[EquipmentManager] Combat context:', {
            combatId: this.currentCombatId,
            combatantId: this.currentCombatantId,
        });

        if (!this.currentCombatId || !this.currentCombatantId) {
            console.error('[EquipmentManager] No combat context set - cannot unequip');
            // Import toast dynamically to show error to user
            import('../ui/toast-notification.js').then(({ default: toast }) => {
                toast.error('Cannot unequip: no active combat');
            });
            return { success: false, error: 'No combat context' };
        }

        try {
            console.log('[EquipmentManager] Calling API to unequip from slot:', slotId);
            const result = await api.unequipItem(
                this.currentCombatId,
                this.currentCombatantId,
                slotId
            );
            console.log('[EquipmentManager] Unequip API result:', result);

            if (result.success) {
                // Refresh equipment state
                await this.refreshEquipment();

                // Emit event for UI update
                eventBus.emit(EVENTS.ITEM_UNEQUIPPED, {
                    slot: slotId,
                });

                return { success: true };
            }

            console.error('[EquipmentManager] Unequip failed:', result.message);
            return { success: false, error: result.message || 'Failed to unequip' };
        } catch (error) {
            console.error('[EquipmentManager] Unequip error:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Swap items between two slots.
     */
    async swapSlots(fromSlot, toSlot) {
        if (!this.currentCombatId || !this.currentCombatantId) {
            console.error('[EquipmentManager] No combat context set');
            return { success: false, error: 'No combat context' };
        }

        try {
            const result = await api.swapEquipmentSlots(
                this.currentCombatId,
                this.currentCombatantId,
                fromSlot,
                toSlot
            );

            if (result.success) {
                await this.refreshEquipment();
                return { success: true };
            }

            return { success: false, error: result.message };
        } catch (error) {
            console.error('[EquipmentManager] Swap error:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Refresh equipment from API and update state.
     */
    async refreshEquipment() {
        if (!this.currentCombatId || !this.currentCombatantId) {
            return;
        }

        try {
            const equipment = await api.getEquipment(
                this.currentCombatId,
                this.currentCombatantId
            );

            // FIX: Use state.set() instead of direct mutation to trigger UI updates
            const gameState = state.getState();
            const playerId = gameState.playerId;

            if (playerId) {
                const newEquipment = {
                    ...equipment.equipped,
                    inventory: equipment.inventory,
                    carrying_capacity: equipment.carrying_capacity,
                    current_weight: equipment.current_weight,
                };

                // Update state properly - triggers subscribers
                state.set(`combatants.${playerId}.equipment`, newEquipment);
                state.set(`combatants.${playerId}.encumbrance_status`, equipment.encumbrance_status);

                // Emit event for components not subscribed to state
                eventBus.emit(EVENTS.EQUIPMENT_CHANGED, newEquipment);
            }
        } catch (error) {
            console.error('[EquipmentManager] Refresh error:', error);
        }
    }

    /**
     * Calculate total weight of equipment and inventory.
     */
    calculateWeight() {
        const equipment = this.getEquipment();
        if (!equipment) return 0;

        let total = 0;

        // Equipped items
        const equipped = this.getEquippedItems();
        for (const item of Object.values(equipped)) {
            if (item) {
                total += (item.weight || 0) * (item.quantity || 1);
            }
        }

        // Inventory items
        for (const item of equipment.inventory || []) {
            total += (item.weight || 0) * (item.quantity || 1);
        }

        return total;
    }

    /**
     * Get encumbrance status based on D&D 5e rules.
     */
    getEncumbranceStatus(strength = 10) {
        const weight = this.calculateWeight();
        const normalLimit = strength * 5;
        const encumberedLimit = strength * 10;
        const maxCapacity = strength * 15;

        if (weight <= normalLimit) {
            return { status: 'normal', penalty: null };
        } else if (weight <= encumberedLimit) {
            return { status: 'encumbered', penalty: '-10 speed' };
        } else if (weight <= maxCapacity) {
            return { status: 'heavily_encumbered', penalty: '-20 speed, disadvantage on ability checks' };
        } else {
            return { status: 'over_capacity', penalty: 'Cannot move' };
        }
    }

    /**
     * Load all available items from rules data.
     */
    async loadItemData() {
        if (this.cachedItems) {
            return this.cachedItems;
        }

        try {
            const items = await api.getAllItems();
            this.cachedItems = items;
            return items;
        } catch (error) {
            console.error('[EquipmentManager] Failed to load items:', error);
            return { weapons: [], armor: [], gear: [] };
        }
    }

    /**
     * Get rarity color for an item.
     */
    getRarityColor(rarity) {
        return RARITY_COLORS[rarity?.toLowerCase()] || RARITY_COLORS.common;
    }

    /**
     * Get mastery description for a weapon.
     */
    getMasteryDescription(masteryType) {
        return MASTERY_DESCRIPTIONS[masteryType?.toLowerCase()] || '';
    }

    /**
     * Format item tooltip data.
     */
    getTooltipData(item) {
        if (!item) return null;

        return {
            name: item.name,
            type: item.item_type,
            rarity: item.rarity || 'common',
            rarityColor: this.getRarityColor(item.rarity),
            damage: item.damage,
            damageType: item.damage_type,
            acBonus: item.ac_bonus,
            maxDexBonus: item.max_dex_bonus,
            properties: item.properties || [],
            mastery: item.mastery,
            masteryDescription: this.getMasteryDescription(item.mastery),
            weight: item.weight,
            value: item.value,
            description: item.description,
            requiresAttunement: item.requires_attunement,
            isAttuned: item.is_attuned,
        };
    }

    /**
     * Check if combat is in progress (restricts armor changes).
     */
    isInCombat() {
        return state.getCombatState()?.phase === 'combat';
    }

    /**
     * Check if an item change is allowed based on combat restrictions.
     */
    canChangeItem(slotId) {
        // Armor can't be changed during combat (takes 1-10 minutes)
        if (slotId === 'armor' && this.isInCombat()) {
            return { allowed: false, reason: 'Cannot change armor during combat' };
        }

        return { allowed: true };
    }
}

// Export singleton instance
export const equipmentManager = new EquipmentManager();
export default equipmentManager;
