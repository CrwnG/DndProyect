/**
 * D&D Combat Engine - Legendary Actions Panel
 * Displays and manages legendary actions for boss creatures
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';

class LegendaryActionsPanel {
    constructor() {
        this.container = document.getElementById('legendary-actions-panel');
        this.visible = false;
        this.legendaryCreatures = [];

        this.subscribeToState();
        this.subscribeToEvents();
    }

    /**
     * Subscribe to state changes
     */
    subscribeToState() {
        state.subscribe((newState) => {
            this.update(newState);
        });
    }

    /**
     * Subscribe to relevant events
     */
    subscribeToEvents() {
        // Refresh after turn ends (legendary actions can be used then)
        eventBus.on(EVENTS.TURN_ENDED, () => {
            this.render();
        });
    }

    /**
     * Update the panel based on game state
     */
    update(gameState) {
        // Get legendary creatures from combat state
        const combat = gameState.combat || {};
        this.legendaryCreatures = combat.legendary_creatures || [];

        // Show panel only if there are legendary creatures
        if (this.legendaryCreatures.length > 0) {
            this.show();
            this.render();
        } else {
            this.hide();
        }
    }

    /**
     * Show the panel
     */
    show() {
        if (this.container) {
            this.container.style.display = 'block';
            this.visible = true;
        }
    }

    /**
     * Hide the panel
     */
    hide() {
        if (this.container) {
            this.container.style.display = 'none';
            this.visible = false;
        }
    }

    /**
     * Render the legendary actions panel
     */
    render() {
        if (!this.container || this.legendaryCreatures.length === 0) return;

        this.container.innerHTML = '';

        // Create header
        const header = document.createElement('div');
        header.className = 'legendary-header';
        header.innerHTML = '<span class="legendary-icon">👑</span> Legendary Actions';
        this.container.appendChild(header);

        // Create a section for each legendary creature
        for (const creature of this.legendaryCreatures) {
            const creatureSection = this.createCreatureSection(creature);
            this.container.appendChild(creatureSection);
        }
    }

    /**
     * Create a section for a legendary creature
     */
    createCreatureSection(creature) {
        const section = document.createElement('div');
        section.className = 'legendary-creature';
        section.dataset.creatureId = creature.id;

        // Creature name and action count
        const nameRow = document.createElement('div');
        nameRow.className = 'legendary-name-row';
        nameRow.innerHTML = `
            <span class="creature-name">${creature.name}</span>
            <span class="action-dots">${this.renderActionDots(creature.actions_remaining, creature.actions_per_round)}</span>
        `;
        section.appendChild(nameRow);

        // Available actions
        const actionsContainer = document.createElement('div');
        actionsContainer.className = 'legendary-actions-list';

        for (const action of creature.available_actions) {
            const actionBtn = this.createActionButton(creature, action);
            actionsContainer.appendChild(actionBtn);
        }

        section.appendChild(actionsContainer);
        return section;
    }

    /**
     * Render action dots showing remaining/total
     */
    renderActionDots(remaining, total) {
        let dots = '';
        for (let i = 0; i < total; i++) {
            const filled = i < remaining;
            dots += `<span class="action-dot ${filled ? 'filled' : 'empty'}">●</span>`;
        }
        return dots;
    }

    /**
     * Create a button for a legendary action
     */
    createActionButton(creature, action) {
        const btn = document.createElement('button');
        btn.className = 'legendary-action-btn';
        btn.disabled = action.cost > creature.actions_remaining;

        // Cost indicator
        const costStr = action.cost > 1 ? ` (${action.cost})` : '';

        btn.innerHTML = `
            <span class="action-name">${action.name}${costStr}</span>
            <span class="action-desc">${this.truncateDescription(action.description, 60)}</span>
        `;

        btn.title = action.description;

        btn.addEventListener('click', () => {
            this.handleActionClick(creature, action);
        });

        return btn;
    }

    /**
     * Truncate description for display
     */
    truncateDescription(desc, maxLen) {
        if (!desc) return '';
        if (desc.length <= maxLen) return desc;
        return desc.substring(0, maxLen - 3) + '...';
    }

    /**
     * Handle clicking on a legendary action
     */
    async handleActionClick(creature, action) {
        // Check if it's a valid time to use legendary action
        // (Not on the legendary creature's own turn)
        const gameState = state.getState();
        const currentTurnId = gameState.initiative[gameState.combat.currentTurnIndex];

        if (currentTurnId === creature.id) {
            eventBus.emit(EVENTS.UI_NOTIFICATION, {
                type: 'warning',
                message: `${creature.name} cannot use legendary actions on its own turn`
            });
            return;
        }

        // Check if action requires a target
        const needsTarget = this.actionNeedsTarget(action);

        if (needsTarget) {
            // Enter targeting mode
            this.startTargeting(creature, action);
        } else {
            // Execute immediately
            await this.executeLegendaryAction(creature.id, action.id, null);
        }
    }

    /**
     * Determine if an action needs a target
     */
    actionNeedsTarget(action) {
        const name = action.name.toLowerCase();
        const desc = (action.description || '').toLowerCase();

        // Actions that typically need targets
        if (name.includes('attack') || name.includes('bite') ||
            name.includes('claw') || name.includes('tail')) {
            return true;
        }

        // Check description for targeting language
        if (desc.includes('one target') || desc.includes('one creature') ||
            desc.includes('melee weapon attack') || desc.includes('ranged weapon attack')) {
            return true;
        }

        return false;
    }

    /**
     * Start targeting mode for a legendary action
     */
    startTargeting(creature, action) {
        eventBus.emit(EVENTS.TARGETING_STARTED, {
            actionType: 'legendary',
            source: creature,
            action: action,
            callback: async (targetId) => {
                await this.executeLegendaryAction(creature.id, action.id, targetId);
            }
        });

        eventBus.emit(EVENTS.UI_NOTIFICATION, {
            type: 'info',
            message: `Select a target for ${action.name}`
        });
    }

    /**
     * Execute a legendary action
     */
    async executeLegendaryAction(monsterId, actionId, targetId) {
        try {
            const gameState = state.getState();
            const result = await api.useLegendaryAction(
                gameState.combatId,
                monsterId,
                actionId,
                targetId
            );

            if (result.success) {
                // Log the action
                eventBus.emit(EVENTS.UI_LOG_ENTRY, {
                    type: 'legendary',
                    message: result.description
                });

                // Update state with new combat state
                if (result.combat_state) {
                    state.updateCombatState(result.combat_state);
                }

                // Update local state for immediate UI feedback
                const creature = this.legendaryCreatures.find(c => c.id === monsterId);
                if (creature) {
                    creature.actions_remaining = result.actions_remaining;
                    this.render();
                }
            } else {
                eventBus.emit(EVENTS.UI_NOTIFICATION, {
                    type: 'error',
                    message: result.description
                });
            }
        } catch (error) {
            console.error('[LegendaryActions] Error:', error);
            eventBus.emit(EVENTS.UI_NOTIFICATION, {
                type: 'error',
                message: `Failed to use legendary action: ${error.message}`
            });
        }
    }
}

// Export singleton instance
export const legendaryActionsPanel = new LegendaryActionsPanel();
export default legendaryActionsPanel;
