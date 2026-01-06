/**
 * D&D 2024 Divine Smite Modal
 * Appears when a Paladin hits with an attack and has spell slots available
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';

class DivineSmiteModal {
    constructor() {
        this.resolveCallback = null;
        this.attackData = null;
        this.availableSlots = {};
        this.createModal();
    }

    createModal() {
        const modal = document.createElement('div');
        modal.id = 'divine-smite-modal';
        modal.className = 'divine-smite-modal hidden';
        modal.innerHTML = `
            <div class="smite-modal-overlay" id="smite-modal-overlay"></div>
            <div class="divine-smite-content">
                <div class="smite-header">
                    <div class="smite-icon">&#9876;</div>
                    <h2>Divine Smite</h2>
                </div>

                <div class="smite-body">
                    <p class="smite-prompt">Your attack hit! Channel divine energy?</p>

                    <div class="smite-target-info" id="smite-target-info">
                        <!-- Dynamically populated -->
                    </div>

                    <div class="smite-options" id="smite-options">
                        <!-- Dynamically populated spell slot options -->
                    </div>

                    <div class="smite-damage-preview" id="smite-damage-preview">
                        <!-- Shows damage preview for selected slot -->
                    </div>
                </div>

                <div class="smite-footer">
                    <button class="btn-smite-skip" id="btn-smite-skip">Skip Smite</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Skip button
        document.getElementById('btn-smite-skip')?.addEventListener('click', () => {
            this.resolve({ use: false, slotLevel: null });
        });

        // Overlay click to skip
        document.getElementById('smite-modal-overlay')?.addEventListener('click', () => {
            this.resolve({ use: false, slotLevel: null });
        });

        // ESC to skip
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !this.isHidden()) {
                this.resolve({ use: false, slotLevel: null });
            }
        });
    }

    /**
     * Show the Divine Smite modal
     * @param {Object} attackResult - The attack result from the backend
     * @returns {Promise<{use: boolean, slotLevel: number|null}>}
     */
    show(attackResult) {
        return new Promise((resolve) => {
            this.resolveCallback = resolve;
            this.attackData = attackResult;
            this.availableSlots = attackResult.extra_data?.available_spell_slots || {};

            // Populate the modal
            this.renderTargetInfo(attackResult);
            this.renderSlotOptions();

            // Show modal
            const modal = document.getElementById('divine-smite-modal');
            modal?.classList.remove('hidden');

            // Play a subtle sound or animation here if desired
        });
    }

    hide() {
        const modal = document.getElementById('divine-smite-modal');
        modal?.classList.add('hidden');
        this.resolveCallback = null;
        this.attackData = null;
        this.availableSlots = {};
    }

    isHidden() {
        return document.getElementById('divine-smite-modal')?.classList.contains('hidden');
    }

    resolve(result) {
        if (this.resolveCallback) {
            this.resolveCallback(result);
        }
        this.hide();
    }

    renderTargetInfo(attackResult) {
        const container = document.getElementById('smite-target-info');
        if (!container) return;

        const targetName = attackResult.target_name || 'Target';
        const damageDealt = attackResult.damage_dealt || 0;
        const isUndead = attackResult.extra_data?.target_is_undead_or_fiend || false;

        container.innerHTML = `
            <div class="target-summary">
                <span class="target-name">${targetName}</span>
                <span class="base-damage">Base damage: ${damageDealt}</span>
                ${isUndead ? '<span class="undead-bonus">+1d8 vs Undead/Fiend!</span>' : ''}
            </div>
        `;
    }

    renderSlotOptions() {
        const container = document.getElementById('smite-options');
        if (!container) return;

        let html = '';

        // Generate options for each available spell slot level
        for (let level = 1; level <= 5; level++) {
            const slotsAvailable = this.availableSlots[level] || 0;

            if (slotsAvailable > 0) {
                const damage = this.calculateSmiteDamage(level);
                const diceCount = this.getSmiteDice(level);

                html += `
                    <button class="smite-slot-option" data-level="${level}">
                        <div class="slot-level">${this.getOrdinalLevel(level)} Level</div>
                        <div class="slot-damage">${diceCount}d8 Force</div>
                        <div class="slot-avg">(avg ${damage})</div>
                        <div class="slot-count">${slotsAvailable} slot${slotsAvailable > 1 ? 's' : ''}</div>
                    </button>
                `;
            }
        }

        if (!html) {
            html = '<div class="no-slots">No spell slots available</div>';
        }

        container.innerHTML = html;

        // Add click handlers to slot options
        container.querySelectorAll('.smite-slot-option').forEach(btn => {
            btn.addEventListener('click', () => {
                const level = parseInt(btn.dataset.level);
                this.selectSlot(level);
            });
        });
    }

    selectSlot(level) {
        // Highlight selected option briefly
        const options = document.querySelectorAll('.smite-slot-option');
        options.forEach(opt => opt.classList.remove('selected'));

        const selected = document.querySelector(`[data-level="${level}"]`);
        selected?.classList.add('selected');

        // Resolve with the selected slot
        setTimeout(() => {
            this.resolve({ use: true, slotLevel: level });
        }, 200); // Brief delay for visual feedback
    }

    getSmiteDice(slotLevel) {
        // Base: 2d8, +1d8 per level above 1st (max 5d8)
        const baseDice = 2;
        const extraDice = Math.min(slotLevel - 1, 3);
        return baseDice + extraDice;
    }

    calculateSmiteDamage(slotLevel) {
        const dice = this.getSmiteDice(slotLevel);
        // Average of d8 is 4.5, rounded
        return Math.floor(dice * 4.5);
    }

    getOrdinalLevel(n) {
        const suffixes = ['th', 'st', 'nd', 'rd'];
        const v = n % 100;
        return n + (suffixes[(v - 20) % 10] || suffixes[v] || suffixes[0]);
    }
}

// Export singleton instance
const divineSmiteModal = new DivineSmiteModal();
export default divineSmiteModal;
