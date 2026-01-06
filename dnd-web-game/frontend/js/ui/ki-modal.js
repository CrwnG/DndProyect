/**
 * D&D Combat Engine - Ki Powers Modal
 * Monk Ki point spending UI
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';

class KiModal {
    constructor() {
        this.kiRemaining = 0;
        this.maxKi = 0;
        this.selectedPower = null;
        this.monkLevel = 0;
        this.createModal();
        this.subscribeToEvents();
    }

    createModal() {
        const modal = document.createElement('div');
        modal.id = 'ki-modal';
        modal.className = 'ki-modal hidden';
        modal.innerHTML = `
            <div class="modal-overlay" id="ki-overlay"></div>
            <div class="modal-content ki-content">
                <div class="modal-header">
                    <h2><span class="header-icon">&#9775;</span> Ki Powers</h2>
                    <button class="modal-close" id="ki-close">&times;</button>
                </div>

                <div class="ki-pool-display">
                    <div class="pool-label">Ki Points</div>
                    <div class="pool-bar">
                        <div class="pool-fill" id="ki-pool-fill"></div>
                    </div>
                    <div class="pool-text"><span id="ki-pool-current">0</span> / <span id="ki-pool-max">0</span></div>
                </div>

                <div class="ki-powers-grid" id="ki-powers-grid">
                    <!-- Populated dynamically -->
                </div>

                <div class="ki-power-info" id="ki-power-info">
                    <p class="info-placeholder">Select a Ki power to see details</p>
                </div>

                <button class="btn-use-ki" id="btn-use-ki" disabled>Select a Power</button>
            </div>
        `;
        document.body.appendChild(modal);
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Close button
        document.getElementById('ki-close')?.addEventListener('click', () => this.hide());
        document.getElementById('ki-overlay')?.addEventListener('click', () => this.hide());

        // Use Ki button
        document.getElementById('btn-use-ki')?.addEventListener('click', () => this.useSelectedPower());

        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible()) {
                this.hide();
            }
        });
    }

    subscribeToEvents() {
        eventBus.on(EVENTS.KI_POWERS_REQUESTED, () => {
            this.show();
        });
    }

    isVisible() {
        return !document.getElementById('ki-modal')?.classList.contains('hidden');
    }

    async show() {
        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const playerStats = gameState.combatant_stats?.[gameState.playerId] || {};

        // Get monk level and Ki points
        this.monkLevel = player?.stats?.level || playerStats.level || 1;
        this.maxKi = this.monkLevel; // Ki points = Monk level
        this.kiRemaining = playerStats.ki_points ?? this.maxKi;

        // Reset selection
        this.selectedPower = null;

        this.render();
        document.getElementById('ki-modal')?.classList.remove('hidden');
    }

    hide() {
        document.getElementById('ki-modal')?.classList.add('hidden');
        this.selectedPower = null;
    }

    render() {
        // Update Ki pool display
        document.getElementById('ki-pool-current').textContent = this.kiRemaining;
        document.getElementById('ki-pool-max').textContent = this.maxKi;

        const poolPercent = (this.kiRemaining / this.maxKi) * 100;
        document.getElementById('ki-pool-fill').style.width = `${poolPercent}%`;

        // Render Ki powers grid
        this.renderPowersGrid();

        // Reset info panel
        document.getElementById('ki-power-info').innerHTML =
            '<p class="info-placeholder">Select a Ki power to see details</p>';

        // Reset button
        const btn = document.getElementById('btn-use-ki');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Select a Power';
        }
    }

    renderPowersGrid() {
        const grid = document.getElementById('ki-powers-grid');
        if (!grid) return;

        const gameState = state.getState();
        const turn = gameState.turn || {};
        const bonusUsed = turn.bonusActionUsed;

        // Define Ki powers
        const powers = [
            {
                id: 'flurry_of_blows',
                name: 'Flurry of Blows',
                cost: 1,
                type: 'bonus',
                icon: '&#128074;&#128074;',
                minLevel: 2,
                description: 'Immediately after taking the Attack action, make two unarmed strikes as a bonus action.',
                requirement: 'Must have attacked this turn',
                effect: '+2 unarmed strikes'
            },
            {
                id: 'patient_defense',
                name: 'Patient Defense',
                cost: 1,
                type: 'bonus',
                icon: '&#128737;',
                minLevel: 2,
                description: 'Take the Dodge action as a bonus action. Attacks against you have disadvantage until your next turn.',
                requirement: 'Bonus action',
                effect: 'Dodge as bonus action'
            },
            {
                id: 'step_of_the_wind',
                name: 'Step of the Wind',
                cost: 1,
                type: 'bonus',
                icon: '&#128168;',
                minLevel: 2,
                description: 'Take the Dash or Disengage action as a bonus action, and your jump distance is doubled.',
                requirement: 'Bonus action',
                effect: 'Dash/Disengage + double jump'
            },
            {
                id: 'stunning_strike',
                name: 'Stunning Strike',
                cost: 1,
                type: 'on_hit',
                icon: '&#11088;',
                minLevel: 5,
                description: 'When you hit with a melee weapon attack, force the target to make a Constitution save or be stunned until the end of your next turn.',
                requirement: 'On melee hit',
                effect: 'Target stunned (CON save)'
            },
            {
                id: 'deflect_missiles',
                name: 'Deflect Missiles',
                cost: 1,
                type: 'reaction',
                icon: '&#127993;',
                minLevel: 3,
                description: 'Use your reaction to deflect a missile. If you reduce damage to 0, spend 1 Ki to throw it back.',
                requirement: 'Reaction to ranged attack',
                effect: 'Reduce damage / throw back'
            },
            {
                id: 'slow_fall',
                name: 'Slow Fall',
                cost: 0,
                type: 'reaction',
                icon: '&#129666;',
                minLevel: 4,
                description: 'Use your reaction to reduce falling damage by 5 times your monk level.',
                requirement: 'Reaction when falling',
                effect: `Reduce damage by ${this.monkLevel * 5}`
            }
        ];

        let html = '';

        for (const power of powers) {
            // Check if available at current level
            const available = this.monkLevel >= power.minLevel;
            // Check if can afford
            const canAfford = this.kiRemaining >= power.cost;
            // Check if bonus action available (for bonus action powers)
            const bonusAvailable = power.type !== 'bonus' || !bonusUsed;
            // Is this power usable right now?
            const usable = available && canAfford && bonusAvailable;

            html += `
                <div class="ki-power-card ${!usable ? 'disabled' : ''} ${!available ? 'locked' : ''}"
                     data-power-id="${power.id}"
                     data-cost="${power.cost}">
                    <div class="power-icon">${power.icon}</div>
                    <div class="power-name">${power.name}</div>
                    <div class="power-cost">${power.cost > 0 ? power.cost + ' Ki' : 'Free'}</div>
                    <div class="power-type">${this.formatType(power.type)}</div>
                    ${!available ? `<div class="level-lock">Lvl ${power.minLevel}</div>` : ''}
                </div>
            `;
        }

        grid.innerHTML = html;

        // Store powers for reference
        this.powers = powers;

        // Add click handlers
        grid.querySelectorAll('.ki-power-card:not(.disabled)').forEach(card => {
            card.addEventListener('click', () => {
                const powerId = card.dataset.powerId;
                this.selectPower(powerId);
            });
        });
    }

    formatType(type) {
        switch (type) {
            case 'bonus': return 'Bonus Action';
            case 'action': return 'Action';
            case 'reaction': return 'Reaction';
            case 'on_hit': return 'On Hit';
            default: return type;
        }
    }

    selectPower(powerId) {
        const power = this.powers.find(p => p.id === powerId);
        if (!power) return;

        this.selectedPower = power;

        // Update visual selection
        document.querySelectorAll('.ki-power-card').forEach(c => c.classList.remove('selected'));
        document.querySelector(`[data-power-id="${powerId}"]`)?.classList.add('selected');

        // Show power info
        const infoPanel = document.getElementById('ki-power-info');
        if (infoPanel) {
            infoPanel.innerHTML = `
                <h4>${power.name}</h4>
                <p class="power-description">${power.description}</p>
                <div class="power-details">
                    <span class="detail"><strong>Cost:</strong> ${power.cost > 0 ? power.cost + ' Ki' : 'Free'}</span>
                    <span class="detail"><strong>Type:</strong> ${this.formatType(power.type)}</span>
                    <span class="detail"><strong>Effect:</strong> ${power.effect}</span>
                </div>
            `;
        }

        // Update button
        const btn = document.getElementById('btn-use-ki');
        if (btn) {
            btn.disabled = false;
            btn.textContent = `Use ${power.name} (${power.cost} Ki)`;
        }
    }

    async useSelectedPower() {
        if (!this.selectedPower) return;

        const power = this.selectedPower;

        try {
            const gameState = state.getState();
            const response = await api.useKiPower(
                gameState.combatId,
                gameState.playerId,
                power.id
            );

            if (response.success) {
                eventBus.emit(EVENTS.UI_LOG_ENTRY, {
                    type: 'class_feature',
                    message: response.description || `Used ${power.name}`
                });

                eventBus.emit(EVENTS.CLASS_FEATURE_USED, {
                    feature: 'ki_power',
                    power: power.id,
                    ki_spent: power.cost
                });

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                // Handle special cases
                if (power.id === 'patient_defense') {
                    state.useBonusAction();
                } else if (power.id === 'step_of_the_wind') {
                    state.useBonusAction();
                    // Movement is doubled - handled by backend
                } else if (power.id === 'flurry_of_blows') {
                    state.useBonusAction();
                    // Extra attacks are added by backend
                } else if (power.id === 'stunning_strike') {
                    // Applied on next hit - just mark as pending
                    state.set('turn.stunningStrikePending', true);
                }

                this.hide();
            } else {
                eventBus.emit(EVENTS.UI_NOTIFICATION, {
                    type: 'error',
                    message: response.description || 'Failed to use Ki power'
                });
            }
        } catch (error) {
            console.error('[KiModal] Use Ki power error:', error);
            eventBus.emit(EVENTS.UI_NOTIFICATION, {
                type: 'error',
                message: 'Failed to use Ki power'
            });
        }
    }
}

export const kiModal = new KiModal();
export default kiModal;
