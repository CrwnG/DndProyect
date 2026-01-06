/**
 * D&D Combat Engine - Targeting System
 * Handles target selection for attacks and spells
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state, { GameMode } from '../engine/state-manager.js';
import api from '../api/api-client.js';

class TargetingSystem {
    constructor() {
        this.targetingCallback = null;
        this.setupEventListeners();
    }

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        eventBus.on(EVENTS.CELL_CLICKED, this.handleCellClick.bind(this));
        // Note: We don't listen to TARGETING_CANCELLED to avoid infinite loop
        // The cancelTargeting method is called directly from the cancel button
    }

    /**
     * Start targeting mode
     * @param {string} targetType - 'melee', 'ranged', or 'spell'
     * @param {Function} callback - Called when target is selected
     * @param {Object|null} weapon - Optional weapon object with id, range, etc.
     */
    async startTargeting(targetType, callback, weapon = null) {
        this.targetingCallback = callback;
        this.currentWeapon = weapon;
        state.enterTargetingMode(targetType);

        // Fetch valid targets from server
        await this.fetchValidTargets(weapon);

        // Show targeting modal
        this.showTargetingModal(targetType);
    }

    /**
     * Fetch valid targets from server
     * @param {Object|null} weapon - Weapon object with id for range calculation
     */
    async fetchValidTargets(weapon = null) {
        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const currentCombatant = state.getCurrentCombatant();

        if (!combatId || !currentCombatant) return;

        try {
            // Pass weapon ID so backend can use weapon's range
            const weaponId = weapon?.id || null;
            const fallbackRange = weapon?.range || 5;
            const response = await api.getValidTargets(combatId, currentCombatant.id, weaponId, fallbackRange);
            if (response.targets) {
                // Extract just the IDs - backend returns [{id, name, ...}, ...]
                // but combat-grid.js expects an array of IDs for highlighting
                const targetIds = response.targets.map(t => t.id);
                console.log('[TargetingSystem] Valid targets:', targetIds);
                state.setAttackTargets(targetIds);
            }
        } catch (error) {
            console.error('[TargetingSystem] Failed to fetch targets:', error);
            state.setAttackTargets([]);
        }
    }

    /**
     * Handle cell click during targeting
     */
    handleCellClick(cell) {
        const gameState = state.getState();

        console.log('[TargetingSystem] Cell clicked:', { x: cell.x, y: cell.y });
        console.log('[TargetingSystem] Current mode:', gameState.mode);
        console.log('[TargetingSystem] Attack targets:', gameState.grid.attackTargets);
        console.log('[TargetingSystem] All positions:', gameState.grid.positions);

        // Only handle if in targeting mode
        if (gameState.mode !== GameMode.TARGETING) {
            console.log('[TargetingSystem] Not in targeting mode, ignoring click');
            return;
        }

        // Check if clicked on a valid target
        const combatant = state.getCombatantAtPosition(cell.x, cell.y);
        console.log('[TargetingSystem] Combatant at position:', combatant);

        if (combatant && gameState.grid.attackTargets.includes(combatant.id)) {
            console.log('[TargetingSystem] Valid target selected:', combatant.id);
            this.selectTarget(combatant);
        } else {
            console.log('[TargetingSystem] Not a valid target:', {
                hasCombatant: !!combatant,
                combatantId: combatant?.id,
                isInTargetList: combatant ? gameState.grid.attackTargets.includes(combatant.id) : false
            });
        }
    }

    /**
     * Select a target
     */
    selectTarget(target) {
        this.hideTargetingModal();
        state.exitTargetingMode();

        eventBus.emit(EVENTS.TARGET_SELECTED, target);

        if (this.targetingCallback) {
            this.targetingCallback(target);
            this.targetingCallback = null;
        }
    }

    /**
     * Cancel targeting mode
     */
    cancelTargeting() {
        this.hideTargetingModal();
        state.exitTargetingMode();
        this.targetingCallback = null;

        eventBus.emit(EVENTS.ACTION_CANCELLED);
    }

    /**
     * Show targeting panel (BG3 style - compact, doesn't block grid)
     */
    showTargetingModal(targetType) {
        const panel = document.getElementById('targeting-panel');
        const title = document.getElementById('targeting-title');
        const description = document.getElementById('targeting-description');

        if (panel) {
            let titleText = 'Select Target';
            let descText = 'Click on a highlighted enemy to attack.';

            switch (targetType) {
                case 'melee':
                    titleText = 'Melee Attack';
                    descText = 'Click on an adjacent enemy (red glow) to attack.';
                    break;
                case 'ranged':
                    titleText = 'Ranged Attack';
                    descText = 'Click on an enemy within range to attack.';
                    break;
                case 'spell':
                    titleText = 'Cast Spell';
                    descText = 'Click on a valid target for this spell.';
                    break;
            }

            if (title) title.textContent = titleText;
            if (description) description.textContent = descText;

            panel.classList.remove('hidden');

            // Set up cancel button
            const cancelBtn = document.getElementById('targeting-cancel');
            if (cancelBtn) {
                cancelBtn.onclick = () => this.cancelTargeting();
            }

            // Set up ESC key to cancel
            this.escHandler = (e) => {
                if (e.key === 'Escape') {
                    this.cancelTargeting();
                }
            };
            document.addEventListener('keydown', this.escHandler);
        }

        // Add targeting class to body for cursor change
        document.body.classList.add('targeting-active');
    }

    /**
     * Hide targeting panel
     */
    hideTargetingModal() {
        const panel = document.getElementById('targeting-panel');
        if (panel) {
            panel.classList.add('hidden');
        }
        document.body.classList.remove('targeting-active');

        // Remove ESC key handler
        if (this.escHandler) {
            document.removeEventListener('keydown', this.escHandler);
            this.escHandler = null;
        }
    }

    /**
     * Check if a combatant is a valid target
     */
    isValidTarget(combatantId) {
        const gameState = state.getState();
        return gameState.grid.attackTargets.includes(combatantId);
    }

    /**
     * Get list of valid targets
     */
    getValidTargets() {
        const gameState = state.getState();
        return gameState.grid.attackTargets.map(id => gameState.combatants[id]).filter(Boolean);
    }
}

export default TargetingSystem;
