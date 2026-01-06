/**
 * Paper Doll Component
 *
 * Visual equipment slot display in BG3-style layout:
 *
 * ┌─────────────────────────────────────┐
 * │             [Head/Helm]             │
 * │    [Cloak]   [Armor]    [Amulet]    │
 * │    [Gloves]  [Belt]     [Ring 1]    │
 * │    [Boots]   [Main]     [Ring 2]    │
 * │              [Off]      [Ranged]    │
 * └─────────────────────────────────────┘
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import { equipmentManager, EQUIPMENT_SLOTS, RARITY_COLORS } from '../equipment/equipment-manager.js';
import itemTooltip from './item-tooltip.js';

// Slots that cannot be changed during combat (armor takes minutes to don/doff)
const COMBAT_LOCKED_SLOTS = ['armor', 'head', 'cloak', 'gloves', 'boots', 'belt'];

class PaperDoll {
    constructor(container) {
        this.container = container;
        this.slots = {};
        this.draggedItem = null;
        this.highlightedSlots = [];
        this.inCombat = false;
    }

    /**
     * Initialize the paper doll UI.
     */
    init() {
        this.render();
        this.setupEventListeners();
        this.setupCombatListeners();
    }

    /**
     * Set up combat state listeners.
     */
    setupCombatListeners() {
        // Listen for combat start/end to lock/unlock armor slots
        eventBus.on(EVENTS.COMBAT_STARTED, () => {
            this.inCombat = true;
            this.updateCombatLockState();
        });

        eventBus.on(EVENTS.COMBAT_ENDED, () => {
            this.inCombat = false;
            this.updateCombatLockState();
        });

        // Also check initial state from window.state if available
        if (window.state?.getState) {
            const gameState = window.state.getState();
            this.inCombat = gameState.inCombat === true;
        }
    }

    /**
     * Update visual state of combat-locked slots.
     */
    updateCombatLockState() {
        COMBAT_LOCKED_SLOTS.forEach(slotId => {
            const slotElement = this.slots[slotId];
            if (slotElement) {
                if (this.inCombat) {
                    slotElement.classList.add('combat-locked');
                    slotElement.setAttribute('title', 'Cannot change armor during combat');
                } else {
                    slotElement.classList.remove('combat-locked');
                    slotElement.removeAttribute('title');
                }
            }
        });
    }

    /**
     * Check if a slot is locked due to combat.
     * @param {string} slotId - The slot to check
     * @returns {boolean} True if the slot is locked
     */
    isSlotCombatLocked(slotId) {
        return this.inCombat && COMBAT_LOCKED_SLOTS.includes(slotId);
    }

    /**
     * Render the paper doll layout.
     */
    render() {
        if (!this.container) return;

        const equipment = equipmentManager.getEquippedItems();

        this.container.innerHTML = `
            <div class="paper-doll-grid">
                <!-- Row 1: Head -->
                <div class="paper-doll-row">
                    <div class="slot-spacer"></div>
                    ${this.renderSlot('head', equipment.head)}
                    <div class="slot-spacer"></div>
                </div>

                <!-- Row 2: Cloak, Armor, Amulet -->
                <div class="paper-doll-row">
                    ${this.renderSlot('cloak', equipment.cloak)}
                    ${this.renderSlot('armor', equipment.armor)}
                    ${this.renderSlot('amulet', equipment.amulet)}
                </div>

                <!-- Row 3: Gloves, Belt, Ring 1 -->
                <div class="paper-doll-row">
                    ${this.renderSlot('gloves', equipment.gloves)}
                    ${this.renderSlot('belt', equipment.belt)}
                    ${this.renderSlot('ring_1', equipment.ring_1)}
                </div>

                <!-- Row 4: Boots, Main Hand, Ring 2 -->
                <div class="paper-doll-row">
                    ${this.renderSlot('boots', equipment.boots)}
                    ${this.renderSlot('main_hand', equipment.main_hand)}
                    ${this.renderSlot('ring_2', equipment.ring_2)}
                </div>

                <!-- Row 5: Off Hand, Ranged -->
                <div class="paper-doll-row">
                    <div class="slot-spacer"></div>
                    ${this.renderSlot('off_hand', equipment.off_hand)}
                    ${this.renderSlot('ranged', equipment.ranged)}
                </div>
            </div>
        `;

        this.cacheSlotElements();
    }

    /**
     * Render a single equipment slot.
     */
    renderSlot(slotId, item) {
        const slotDef = Object.values(EQUIPMENT_SLOTS).find(s => s.id === slotId) || {};
        const isEmpty = !item;
        const rarityColor = item ? RARITY_COLORS[item.rarity || 'common'] : '';
        const isCombatLocked = this.isSlotCombatLocked(slotId);
        const lockedClass = isCombatLocked ? 'combat-locked' : '';
        const lockedTitle = isCombatLocked ? 'title="Cannot change armor during combat"' : '';

        return `
            <div class="equipment-slot ${isEmpty ? 'empty' : 'equipped'} ${lockedClass}"
                 data-slot="${slotId}"
                 draggable="${!isEmpty && !isCombatLocked}"
                 ${lockedTitle}
                 ${item ? `style="--rarity-color: ${rarityColor}"` : ''}>
                <div class="slot-background">
                    <span class="slot-icon">${slotDef.icon || '?'}</span>
                </div>
                ${item ? `
                    <div class="slot-item" data-item-id="${item.id}">
                        <span class="item-icon">${item.icon || slotDef.icon || '?'}</span>
                        ${item.quantity > 1 ? `<span class="item-quantity">${item.quantity}</span>` : ''}
                    </div>
                    <div class="slot-rarity-border"></div>
                ` : ''}
                <div class="slot-label">${slotDef.name || slotId}</div>
            </div>
        `;
    }

    /**
     * Cache slot element references for quick access.
     */
    cacheSlotElements() {
        this.slots = {};
        const slotElements = this.container.querySelectorAll('.equipment-slot');
        slotElements.forEach(el => {
            const slotId = el.dataset.slot;
            this.slots[slotId] = el;
        });
    }

    /**
     * Set up event listeners for slots.
     */
    setupEventListeners() {
        this.container.addEventListener('click', (e) => this.handleSlotClick(e));
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
     * Handle right-click context menu on equipment slot.
     */
    handleContextMenu(e) {
        e.preventDefault();
        console.log('[PaperDoll] Right-click detected on paper doll');

        const slot = e.target.closest('.equipment-slot');
        if (!slot) {
            console.log('[PaperDoll] No slot found at click target');
            return;
        }

        const slotId = slot.dataset.slot;
        const isEquipped = slot.classList.contains('equipped');
        console.log('[PaperDoll] Right-click on slot:', slotId, 'isEquipped:', isEquipped);

        if (!isEquipped) {
            // Empty slot - nothing to unequip
            console.log('[PaperDoll] Slot is empty, nothing to unequip');
            return;
        }

        // Check for combat lock
        if (this.isSlotCombatLocked(slotId)) {
            console.log('[PaperDoll] Slot is combat-locked');
            this.showCombatLockWarning(slotId);
            return;
        }

        const item = equipmentManager.getEquippedItems()[slotId];
        console.log('[PaperDoll] Item in slot:', item?.name);
        if (item) {
            this.showContextMenu(slotId, item, e.clientX, e.clientY);
        }
    }

    /**
     * Show context menu for equipment slot.
     */
    showContextMenu(slotId, item, x, y) {
        // Remove any existing context menu
        const existing = document.querySelector('.equipment-context-menu');
        if (existing) existing.remove();

        const slotDef = Object.values(EQUIPMENT_SLOTS).find(s => s.id === slotId) || {};

        const menu = document.createElement('div');
        menu.className = 'equipment-context-menu';
        menu.style.left = `${x}px`;
        menu.style.top = `${y}px`;

        menu.innerHTML = `
            <div class="context-menu-header">${item.name}</div>
            <button class="context-menu-item" data-action="unequip">
                Unequip to Inventory
            </button>
        `;

        document.body.appendChild(menu);

        // Handle menu clicks
        menu.addEventListener('click', async (e) => {
            const button = e.target.closest('.context-menu-item');
            if (!button) return;

            const action = button.dataset.action;

            if (action === 'unequip') {
                const result = await equipmentManager.unequipItem(slotId);
                if (!result.success) {
                    console.error('[PaperDoll] Unequip failed:', result.error);
                }
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
     * Handle slot click - unequip item.
     */
    handleSlotClick(e) {
        const slot = e.target.closest('.equipment-slot');
        if (!slot) return;

        const slotId = slot.dataset.slot;
        const isEquipped = slot.classList.contains('equipped');

        // Check for combat lock
        if (this.isSlotCombatLocked(slotId)) {
            this.showCombatLockWarning(slotId);
            return;
        }

        if (isEquipped) {
            // Right-click to unequip (handled by context menu)
            // Left-click could show item details or do nothing
            eventBus.emit(EVENTS.ITEM_SELECTED, {
                slot: slotId,
                item: equipmentManager.getEquippedItems()[slotId],
            });
        }
    }

    /**
     * Show a warning when trying to change combat-locked equipment.
     * @param {string} slotId - The slot that is locked
     */
    showCombatLockWarning(slotId) {
        const slotDef = Object.values(EQUIPMENT_SLOTS).find(s => s.id === slotId) || {};
        const slotName = slotDef.name || slotId;

        // Show a toast notification
        const warning = document.createElement('div');
        warning.className = 'armor-change-warning';
        warning.innerHTML = `
            <span class="warning-icon">⚔️</span>
            <span class="warning-text">Cannot change ${slotName} during combat!</span>
        `;
        document.body.appendChild(warning);

        // Animate in
        requestAnimationFrame(() => {
            warning.classList.add('show');
        });

        // Remove after animation
        setTimeout(() => {
            warning.classList.remove('show');
            setTimeout(() => warning.remove(), 300);
        }, 2000);
    }

    /**
     * Handle mouse enter on slot - show tooltip.
     */
    handleMouseEnter(e) {
        const slot = e.target.closest('.equipment-slot');
        if (!slot || slot.classList.contains('empty')) return;

        const slotId = slot.dataset.slot;
        const item = equipmentManager.getEquippedItems()[slotId];

        if (item) {
            itemTooltip.show(item, e.clientX, e.clientY);
        }
    }

    /**
     * Handle mouse leave - hide tooltip.
     */
    handleMouseLeave(e) {
        const slot = e.target.closest('.equipment-slot');
        if (!slot) return;

        // Only hide if we're actually leaving the slot (not entering a child)
        const relatedTarget = e.relatedTarget;
        if (!slot.contains(relatedTarget)) {
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
     * Handle drag start - start dragging an equipped item.
     */
    handleDragStart(e) {
        const slot = e.target.closest('.equipment-slot');
        if (!slot || slot.classList.contains('empty')) {
            e.preventDefault();
            return;
        }

        const slotId = slot.dataset.slot;

        // Block dragging from combat-locked slots
        if (this.isSlotCombatLocked(slotId)) {
            e.preventDefault();
            this.showCombatLockWarning(slotId);
            return;
        }

        const item = equipmentManager.getEquippedItems()[slotId];

        if (item) {
            this.draggedItem = { item, fromSlot: slotId };
            e.dataTransfer.setData('text/plain', JSON.stringify({
                itemId: item.id,
                fromSlot: slotId,
                source: 'paper-doll',
            }));
            e.dataTransfer.effectAllowed = 'move';

            slot.classList.add('dragging');
            itemTooltip.hide();

            // Highlight valid drop targets (excluding combat-locked slots)
            this.highlightValidSlots(item);
        }
    }

    /**
     * Handle drag end - cleanup.
     */
    handleDragEnd(e) {
        const slot = e.target.closest('.equipment-slot');
        if (slot) {
            slot.classList.remove('dragging');
        }

        this.clearHighlights();
        this.draggedItem = null;
    }

    /**
     * Handle drag over - allow drop on valid slots.
     */
    handleDragOver(e) {
        const slot = e.target.closest('.equipment-slot');
        if (!slot) return;

        // Check if this is a valid drop target
        if (slot.classList.contains('highlight-valid')) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        }
    }

    /**
     * Handle drop - swap items between slots.
     */
    async handleDrop(e) {
        e.preventDefault();

        const slot = e.target.closest('.equipment-slot');
        if (!slot) return;

        const toSlot = slot.dataset.slot;

        // Block drops on combat-locked slots
        if (this.isSlotCombatLocked(toSlot)) {
            this.showCombatLockWarning(toSlot);
            this.clearHighlights();
            return;
        }

        try {
            const data = JSON.parse(e.dataTransfer.getData('text/plain'));

            if (data.source === 'paper-doll') {
                // Swap between paper doll slots
                const fromSlot = data.fromSlot;
                if (fromSlot !== toSlot) {
                    await equipmentManager.swapSlots(fromSlot, toSlot);
                }
            } else if (data.source === 'inventory') {
                // Equip from inventory
                await equipmentManager.equipItem(data.itemId, toSlot);
            }
        } catch (error) {
            console.error('[PaperDoll] Drop error:', error);
        }

        this.clearHighlights();
    }

    /**
     * Highlight valid slots for an item.
     * Excludes combat-locked slots during combat.
     */
    highlightValidSlots(item) {
        const validSlots = equipmentManager.getValidSlotsForItem(item);

        Object.entries(this.slots).forEach(([slotId, element]) => {
            // Skip combat-locked slots during combat
            if (this.isSlotCombatLocked(slotId)) {
                return;
            }

            if (validSlots.includes(slotId)) {
                element.classList.add('highlight-valid');
                this.highlightedSlots.push(element);
            }
        });
    }

    /**
     * Highlight specific slots during drag from inventory.
     */
    highlightSlotsForItem(item) {
        this.highlightValidSlots(item);
    }

    /**
     * Clear all slot highlights.
     */
    clearHighlights() {
        this.highlightedSlots.forEach(el => {
            el.classList.remove('highlight-valid');
        });
        this.highlightedSlots = [];
    }

    /**
     * Update a specific slot without full re-render.
     */
    updateSlot(slotId) {
        const slotElement = this.slots[slotId];
        if (!slotElement) return;

        const equipment = equipmentManager.getEquippedItems();
        const item = equipment[slotId];

        // Replace slot HTML
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = this.renderSlot(slotId, item);
        const newSlot = tempDiv.firstElementChild;

        slotElement.replaceWith(newSlot);
        this.slots[slotId] = newSlot;
    }

    /**
     * Get current equipment state for display.
     */
    getEquipmentSummary() {
        const equipment = equipmentManager.getEquippedItems();
        const summary = {};

        Object.entries(equipment).forEach(([slot, item]) => {
            summary[slot] = item ? {
                name: item.name,
                rarity: item.rarity || 'common',
            } : null;
        });

        return summary;
    }
}

export { PaperDoll };
export default PaperDoll;
