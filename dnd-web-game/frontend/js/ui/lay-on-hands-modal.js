/**
 * D&D Combat Engine - Lay on Hands Modal
 * Paladin healing pool allocation UI
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';

class LayOnHandsModal {
    constructor() {
        this.poolRemaining = 0;
        this.maxPool = 0;
        this.selectedTarget = null;
        this.healAmount = 0;
        this.cureDisease = false;
        this.curePoison = false;
        this.createModal();
        this.subscribeToEvents();
    }

    createModal() {
        const modal = document.createElement('div');
        modal.id = 'lay-on-hands-modal';
        modal.className = 'lay-on-hands-modal hidden';
        modal.innerHTML = `
            <div class="modal-overlay" id="loh-overlay"></div>
            <div class="modal-content loh-content">
                <div class="modal-header">
                    <h2><span class="header-icon">✋</span> Lay on Hands</h2>
                    <button class="modal-close" id="loh-close">&times;</button>
                </div>

                <div class="loh-pool-display">
                    <div class="pool-label">Healing Pool</div>
                    <div class="pool-bar">
                        <div class="pool-fill" id="loh-pool-fill"></div>
                    </div>
                    <div class="pool-text"><span id="loh-pool-current">0</span> / <span id="loh-pool-max">0</span> HP</div>
                </div>

                <div class="loh-section">
                    <h3>Select Target</h3>
                    <div class="target-grid" id="loh-target-grid">
                        <!-- Populated dynamically -->
                    </div>
                </div>

                <div class="loh-section">
                    <h3>Healing Amount</h3>
                    <div class="heal-controls">
                        <input type="range" id="loh-heal-slider" min="1" max="100" value="1" disabled>
                        <div class="heal-display">
                            <span id="loh-heal-amount">0</span> HP
                        </div>
                    </div>
                    <div class="quick-buttons" id="loh-quick-buttons">
                        <!-- Quick heal buttons -->
                    </div>
                </div>

                <div class="loh-section conditions-section">
                    <h3>Cure Conditions (5 HP each)</h3>
                    <div class="condition-toggles">
                        <label class="condition-toggle">
                            <input type="checkbox" id="loh-cure-disease">
                            <span class="toggle-label">🦠 Cure Disease</span>
                        </label>
                        <label class="condition-toggle">
                            <input type="checkbox" id="loh-cure-poison">
                            <span class="toggle-label">☠️ Cure Poison</span>
                        </label>
                    </div>
                </div>

                <div class="loh-cost-summary" id="loh-cost-summary">
                    <!-- Shows total cost calculation -->
                </div>

                <button class="btn-heal" id="btn-loh-heal" disabled>Select a Target</button>
            </div>
        `;
        document.body.appendChild(modal);
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Close button
        document.getElementById('loh-close')?.addEventListener('click', () => this.hide());
        document.getElementById('loh-overlay')?.addEventListener('click', () => this.hide());

        // Heal slider
        const slider = document.getElementById('loh-heal-slider');
        slider?.addEventListener('input', (e) => {
            this.healAmount = parseInt(e.target.value);
            this.updateHealDisplay();
            this.updateCostSummary();
        });

        // Condition checkboxes
        document.getElementById('loh-cure-disease')?.addEventListener('change', (e) => {
            this.cureDisease = e.target.checked;
            this.updateCostSummary();
        });

        document.getElementById('loh-cure-poison')?.addEventListener('change', (e) => {
            this.curePoison = e.target.checked;
            this.updateCostSummary();
        });

        // Heal button
        document.getElementById('btn-loh-heal')?.addEventListener('click', () => this.heal());

        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible()) {
                this.hide();
            }
        });
    }

    subscribeToEvents() {
        eventBus.on(EVENTS.LAY_ON_HANDS_REQUESTED, () => {
            this.show();
        });
    }

    isVisible() {
        return !document.getElementById('lay-on-hands-modal')?.classList.contains('hidden');
    }

    async show() {
        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const playerStats = gameState.combatant_stats?.[gameState.playerId] || {};

        // Calculate pool based on paladin level
        const level = player?.stats?.level || playerStats.level || 1;
        this.maxPool = level * 5; // 5 HP per paladin level
        this.poolRemaining = playerStats.lay_on_hands_pool ?? this.maxPool;

        // Reset state
        this.selectedTarget = null;
        this.healAmount = 1;
        this.cureDisease = false;
        this.curePoison = false;

        document.getElementById('loh-cure-disease').checked = false;
        document.getElementById('loh-cure-poison').checked = false;

        this.render();
        document.getElementById('lay-on-hands-modal')?.classList.remove('hidden');
    }

    hide() {
        document.getElementById('lay-on-hands-modal')?.classList.add('hidden');
        this.selectedTarget = null;
    }

    render() {
        // Update pool display
        document.getElementById('loh-pool-current').textContent = this.poolRemaining;
        document.getElementById('loh-pool-max').textContent = this.maxPool;

        const poolPercent = (this.poolRemaining / this.maxPool) * 100;
        document.getElementById('loh-pool-fill').style.width = `${poolPercent}%`;

        // Render target grid
        this.renderTargetGrid();

        // Update slider max
        const slider = document.getElementById('loh-heal-slider');
        if (slider) {
            slider.max = this.poolRemaining;
            slider.value = Math.min(this.healAmount, this.poolRemaining);
        }

        // Render quick buttons
        this.renderQuickButtons();

        // Update cost summary
        this.updateCostSummary();

        // Update button state
        this.updateHealButton();
    }

    renderTargetGrid() {
        const grid = document.getElementById('loh-target-grid');
        if (!grid) return;

        const gameState = state.getState();
        const combatants = gameState.combatants;

        // Get all allies (players)
        const allies = Object.values(combatants).filter(c =>
            c.type === 'player' && c.isActive !== false && (c.hp > 0 || c.current_hp > 0)
        );

        let html = '';

        for (const ally of allies) {
            const hp = ally.hp ?? ally.current_hp ?? 0;
            const maxHp = ally.max_hp ?? ally.maxHp ?? hp;
            const hpPercent = (hp / maxHp) * 100;
            const needsHealing = hp < maxHp;
            const selected = this.selectedTarget?.id === ally.id;

            html += `
                <div class="target-card ${selected ? 'selected' : ''} ${!needsHealing ? 'full-hp' : ''}"
                     data-target-id="${ally.id}">
                    <div class="target-name">${ally.name}</div>
                    <div class="target-hp-bar">
                        <div class="hp-fill" style="width: ${hpPercent}%"></div>
                    </div>
                    <div class="target-hp-text">${hp} / ${maxHp}</div>
                    ${!needsHealing ? '<span class="full-badge">Full HP</span>' : ''}
                </div>
            `;
        }

        grid.innerHTML = html;

        // Add click handlers
        grid.querySelectorAll('.target-card').forEach(card => {
            card.addEventListener('click', () => {
                const targetId = card.dataset.targetId;
                const target = combatants[targetId];
                if (target) {
                    this.selectTarget(target);
                }
            });
        });
    }

    selectTarget(target) {
        this.selectedTarget = target;

        // Update visual selection
        document.querySelectorAll('.target-card').forEach(c => c.classList.remove('selected'));
        document.querySelector(`[data-target-id="${target.id}"]`)?.classList.add('selected');

        // Enable slider
        const slider = document.getElementById('loh-heal-slider');
        if (slider) {
            slider.disabled = false;

            // Set slider to heal to full HP by default
            const hp = target.hp ?? target.current_hp ?? 0;
            const maxHp = target.max_hp ?? target.maxHp ?? hp;
            const healNeeded = maxHp - hp;
            const maxHeal = Math.min(healNeeded, this.poolRemaining);

            slider.value = maxHeal;
            this.healAmount = maxHeal;
        }

        this.updateHealDisplay();
        this.updateCostSummary();
        this.updateHealButton();
    }

    renderQuickButtons() {
        const container = document.getElementById('loh-quick-buttons');
        if (!container) return;

        const quickAmounts = [5, 10, 15, 20, 'Max'];
        let html = '';

        for (const amount of quickAmounts) {
            const value = amount === 'Max' ? this.poolRemaining : amount;
            const disabled = !this.selectedTarget || value > this.poolRemaining;

            html += `
                <button class="quick-btn ${disabled ? 'disabled' : ''}"
                        data-amount="${value}"
                        ${disabled ? 'disabled' : ''}>
                    ${amount === 'Max' ? 'Max' : `+${amount}`}
                </button>
            `;
        }

        container.innerHTML = html;

        // Add click handlers
        container.querySelectorAll('.quick-btn:not(.disabled)').forEach(btn => {
            btn.addEventListener('click', () => {
                const amount = parseInt(btn.dataset.amount);
                this.healAmount = amount;
                document.getElementById('loh-heal-slider').value = amount;
                this.updateHealDisplay();
                this.updateCostSummary();
            });
        });
    }

    updateHealDisplay() {
        document.getElementById('loh-heal-amount').textContent = this.healAmount;
    }

    updateCostSummary() {
        const summary = document.getElementById('loh-cost-summary');
        if (!summary) return;

        let totalCost = this.healAmount || 0;
        let items = [];

        if (this.healAmount > 0) {
            items.push(`Healing: ${this.healAmount} HP`);
        }

        if (this.cureDisease) {
            totalCost += 5;
            items.push('Cure Disease: 5 HP');
        }

        if (this.curePoison) {
            totalCost += 5;
            items.push('Cure Poison: 5 HP');
        }

        const canAfford = totalCost <= this.poolRemaining;

        summary.innerHTML = `
            <div class="cost-items">${items.join(' + ')}</div>
            <div class="cost-total ${canAfford ? '' : 'insufficient'}">
                Total Cost: ${totalCost} HP
                ${!canAfford ? '<span class="warning">(Insufficient pool)</span>' : ''}
            </div>
        `;
    }

    updateHealButton() {
        const btn = document.getElementById('btn-loh-heal');
        if (!btn) return;

        const totalCost = this.calculateTotalCost();
        const canHeal = this.selectedTarget && totalCost > 0 && totalCost <= this.poolRemaining;

        btn.disabled = !canHeal;
        btn.textContent = this.selectedTarget
            ? `Heal ${this.selectedTarget.name} (${totalCost} HP)`
            : 'Select a Target';
    }

    calculateTotalCost() {
        let cost = this.healAmount || 0;
        if (this.cureDisease) cost += 5;
        if (this.curePoison) cost += 5;
        return cost;
    }

    async heal() {
        if (!this.selectedTarget) return;

        const totalCost = this.calculateTotalCost();
        if (totalCost <= 0 || totalCost > this.poolRemaining) return;

        try {
            const gameState = state.getState();
            const response = await api.useLayOnHands(
                gameState.combatId,
                gameState.playerId,
                this.selectedTarget.id,
                this.healAmount,
                this.cureDisease,
                this.curePoison
            );

            if (response.success) {
                eventBus.emit(EVENTS.UI_LOG_ENTRY, {
                    type: 'healing',
                    message: response.description
                });

                eventBus.emit(EVENTS.CLASS_FEATURE_USED, {
                    feature: 'lay_on_hands',
                    healing: response.healing_done
                });

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                this.hide();
            } else {
                eventBus.emit(EVENTS.UI_NOTIFICATION, {
                    type: 'error',
                    message: response.description
                });
            }
        } catch (error) {
            console.error('[LayOnHandsModal] Heal error:', error);
            eventBus.emit(EVENTS.UI_NOTIFICATION, {
                type: 'error',
                message: 'Failed to use Lay on Hands'
            });
        }
    }
}

export const layOnHandsModal = new LayOnHandsModal();
export default layOnHandsModal;
