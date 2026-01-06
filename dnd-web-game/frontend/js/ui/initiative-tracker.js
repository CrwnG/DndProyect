/**
 * D&D Combat Engine - Initiative Tracker
 * Displays turn order and highlights current combatant
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';

class InitiativeTracker {
    constructor() {
        this.listElement = document.getElementById('initiative-list');
        this.roundCounter = document.getElementById('round-counter');
        this.currentTurnDisplay = document.getElementById('current-turn');

        this.subscribeToState();
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
     * Update the initiative display
     */
    update(gameState) {
        this.updateRoundCounter(gameState);
        this.updateCurrentTurn(gameState);
        this.updateInitiativeList(gameState);
    }

    /**
     * Update round counter
     */
    updateRoundCounter(gameState) {
        if (this.roundCounter) {
            this.roundCounter.textContent = `Round ${gameState.combat.round || 1}`;
        }
    }

    /**
     * Update current turn display in header
     */
    updateCurrentTurn(gameState) {
        if (!this.currentTurnDisplay) return;

        const currentId = gameState.initiative[gameState.combat.currentTurnIndex];
        const current = gameState.combatants[currentId];

        if (current) {
            const isPlayer = current.type === 'player';
            this.currentTurnDisplay.textContent = `${current.name}'s Turn`;
            this.currentTurnDisplay.className = isPlayer ? 'text-green' : 'text-red';
        } else {
            this.currentTurnDisplay.textContent = '-';
        }
    }

    /**
     * Update the initiative list
     */
    updateInitiativeList(gameState) {
        if (!this.listElement) return;

        const initiative = gameState.initiative || [];
        const currentIndex = gameState.combat.currentTurnIndex;

        console.log('[InitiativeTracker] Updating with:', {
            initiative,
            currentIndex,
            combatantsKeys: Object.keys(gameState.combatants || {}),
        });

        if (initiative.length === 0) {
            this.listElement.innerHTML = '<li class="text-muted">No combatants</li>';
            return;
        }

        this.listElement.innerHTML = initiative
            .map((id, index) => {
                const combatant = gameState.combatants[id];
                if (!combatant) return '';

                const isActive = index === currentIndex;
                const isPlayer = combatant.type === 'player';
                const isDefeated = !combatant.isActive;

                let classes = 'initiative-item';
                if (isActive) classes += ' active';
                if (isPlayer) classes += ' player';
                else classes += ' enemy';
                if (isDefeated) classes += ' defeated';

                const hpPercent = Math.round((combatant.hp / combatant.maxHp) * 100);
                const hpClass = hpPercent <= 25 ? 'text-red' : hpPercent <= 50 ? 'text-gold' : '';

                return `
                    <li class="${classes}" data-combatant-id="${id}">
                        <span class="initiative-name">${combatant.name}</span>
                        <span class="initiative-roll">[${combatant.initiativeRoll || '?'}]</span>
                        <span class="initiative-hp ${hpClass}">${combatant.hp}/${combatant.maxHp}</span>
                    </li>
                `;
            })
            .join('');

        // Add click handlers for combatant selection
        this.listElement.querySelectorAll('.initiative-item').forEach(item => {
            item.addEventListener('click', () => {
                const id = item.dataset.combatantId;
                const combatant = gameState.combatants[id];
                if (combatant) {
                    eventBus.emit(EVENTS.COMBATANT_SELECTED, combatant);
                }
            });
        });
    }

    /**
     * Highlight next turn preview
     */
    showNextTurnPreview() {
        const gameState = state.getState();
        const nextIndex = (gameState.combat.currentTurnIndex + 1) % gameState.initiative.length;
        const nextId = gameState.initiative[nextIndex];

        const items = this.listElement?.querySelectorAll('.initiative-item');
        items?.forEach((item, index) => {
            if (index === nextIndex) {
                item.classList.add('next-turn');
            } else {
                item.classList.remove('next-turn');
            }
        });
    }

    /**
     * Scroll to current combatant in list
     */
    scrollToCurrent() {
        const activeItem = this.listElement?.querySelector('.initiative-item.active');
        if (activeItem) {
            activeItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
}

export default InitiativeTracker;
