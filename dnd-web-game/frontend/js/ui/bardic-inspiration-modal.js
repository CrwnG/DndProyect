/**
 * D&D Combat Engine - Bardic Inspiration Modal
 * Bard inspiration die granting UI
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';
import { toast } from './toast-notification.js';

class BardicInspirationModal {
    constructor() {
        this.usesRemaining = 0;
        this.maxUses = 3;
        this.selectedAlly = null;
        this.inspirationDie = 'd6';
        this.level = 1;
        this.createModal();
        this.subscribeToEvents();
    }

    createModal() {
        const modal = document.createElement('div');
        modal.id = 'bardic-inspiration-modal';
        modal.className = 'bardic-inspiration-modal hidden';
        modal.innerHTML = `
            <div class="modal-overlay" id="bardic-overlay"></div>
            <div class="modal-content bardic-content">
                <div class="modal-header">
                    <h2><span class="header-icon">&#127926;</span> Bardic Inspiration</h2>
                    <button class="modal-close" id="bardic-close">&times;</button>
                </div>

                <div class="inspiration-pool-display">
                    <div class="pool-label">Inspiration Uses</div>
                    <div class="pool-icons" id="bardic-uses">
                        <!-- Populated dynamically -->
                    </div>
                    <div class="pool-text"><span id="bardic-current">3</span> / <span id="bardic-max">3</span></div>
                    <div class="die-type">Inspiration Die: <span id="bardic-die" class="die-badge">d6</span></div>
                </div>

                <div class="ally-selection">
                    <div class="section-label">Choose an Ally to Inspire</div>
                    <div class="ally-grid" id="ally-grid">
                        <!-- Populated dynamically -->
                    </div>
                </div>

                <div class="inspiration-info" id="inspiration-info">
                    <p class="info-placeholder">Select an ally to grant them a Bardic Inspiration die</p>
                </div>

                <button class="btn-inspire" id="btn-inspire" disabled>Select an Ally</button>
            </div>
        `;
        document.body.appendChild(modal);
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Close button
        document.getElementById('bardic-close')?.addEventListener('click', () => this.hide());
        document.getElementById('bardic-overlay')?.addEventListener('click', () => this.hide());

        // Inspire button
        document.getElementById('btn-inspire')?.addEventListener('click', () => this.inspireSelectedAlly());

        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible()) {
                this.hide();
            }
        });
    }

    subscribeToEvents() {
        eventBus.on(EVENTS.BARDIC_INSPIRATION_REQUESTED, (data) => {
            this.show(data);
        });
    }

    isVisible() {
        return !document.getElementById('bardic-inspiration-modal')?.classList.contains('hidden');
    }

    show(data = {}) {
        const gameState = state.getState();
        const player = data.player || gameState.combatants[gameState.playerId];

        // Get bard level
        this.level = player?.stats?.level || player?.level || 1;

        // Determine inspiration die based on level
        if (this.level >= 15) {
            this.inspirationDie = 'd12';
        } else if (this.level >= 10) {
            this.inspirationDie = 'd10';
        } else if (this.level >= 5) {
            this.inspirationDie = 'd8';
        } else {
            this.inspirationDie = 'd6';
        }

        // Calculate max uses (CHA modifier, minimum 1)
        const charisma = player?.stats?.charisma || player?.abilities?.charisma || 10;
        const chaMod = Math.floor((charisma - 10) / 2);
        this.maxUses = Math.max(1, chaMod);
        this.usesRemaining = player?.resources?.bardic_inspiration_uses ?? this.maxUses;

        // Reset selection
        this.selectedAlly = null;

        this.render();
        document.getElementById('bardic-inspiration-modal')?.classList.remove('hidden');
    }

    hide() {
        document.getElementById('bardic-inspiration-modal')?.classList.add('hidden');
        this.selectedAlly = null;
    }

    render() {
        // Update uses display
        document.getElementById('bardic-current').textContent = this.usesRemaining;
        document.getElementById('bardic-max').textContent = this.maxUses;
        document.getElementById('bardic-die').textContent = this.inspirationDie;

        // Render uses icons
        const usesContainer = document.getElementById('bardic-uses');
        if (usesContainer) {
            let html = '';
            for (let i = 0; i < this.maxUses; i++) {
                const filled = i < this.usesRemaining;
                html += `<span class="use-icon ${filled ? 'filled' : 'empty'}">&#127926;</span>`;
            }
            usesContainer.innerHTML = html;
        }

        // Render ally grid
        this.renderAllyGrid();

        // Reset info panel
        document.getElementById('inspiration-info').innerHTML =
            '<p class="info-placeholder">Select an ally to grant them a Bardic Inspiration die</p>';

        // Reset button
        const btn = document.getElementById('btn-inspire');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Select an Ally';
        }
    }

    renderAllyGrid() {
        const grid = document.getElementById('ally-grid');
        if (!grid) return;

        const gameState = state.getState();
        const playerId = gameState.playerId;

        // Get all allied combatants (players and allies, not enemies)
        const allies = Object.values(gameState.combatants).filter(c =>
            c.isActive &&
            (c.type === 'player' || c.type === 'ally') &&
            !c.conditions?.includes('inspired') // Can't stack inspiration
        );

        if (allies.length === 0) {
            grid.innerHTML = '<div class="no-allies">No allies available to inspire</div>';
            return;
        }

        let html = '';
        for (const ally of allies) {
            const isSelf = ally.id === playerId;
            const hasInspiration = ally.conditions?.includes('inspired');
            const canInspire = !hasInspiration && this.usesRemaining > 0;

            html += `
                <div class="ally-card ${!canInspire ? 'disabled' : ''} ${isSelf ? 'self' : ''}"
                     data-ally-id="${ally.id}">
                    <div class="ally-icon">${this.getClassIcon(ally.stats?.class || ally.character_class)}</div>
                    <div class="ally-name">${ally.name}${isSelf ? ' (You)' : ''}</div>
                    <div class="ally-class">${this.formatClass(ally.stats?.class || ally.character_class)} ${ally.stats?.level || ally.level || 1}</div>
                    <div class="ally-hp">HP: ${ally.hp}/${ally.maxHp}</div>
                    ${hasInspiration ? '<div class="already-inspired">Already Inspired</div>' : ''}
                </div>
            `;
        }

        grid.innerHTML = html;

        // Add click handlers
        grid.querySelectorAll('.ally-card:not(.disabled)').forEach(card => {
            card.addEventListener('click', () => {
                const allyId = card.dataset.allyId;
                this.selectAlly(allyId);
            });
        });
    }

    getClassIcon(className) {
        const icons = {
            'fighter': '&#9876;',
            'wizard': '&#9733;',
            'cleric': '&#9768;',
            'rogue': '&#128481;',
            'paladin': '&#128737;',
            'ranger': '&#127993;',
            'barbarian': '&#128170;',
            'bard': '&#127926;',
            'druid': '&#127807;',
            'monk': '&#9775;',
            'sorcerer': '&#10024;',
            'warlock': '&#128156;'
        };
        return icons[className?.toLowerCase()] || '&#128100;';
    }

    formatClass(className) {
        if (!className) return 'Adventurer';
        return className.charAt(0).toUpperCase() + className.slice(1);
    }

    selectAlly(allyId) {
        const gameState = state.getState();
        const ally = gameState.combatants[allyId];
        if (!ally) return;

        this.selectedAlly = ally;

        // Update visual selection
        document.querySelectorAll('.ally-card').forEach(c => c.classList.remove('selected'));
        document.querySelector(`[data-ally-id="${allyId}"]`)?.classList.add('selected');

        // Show ally info
        const infoPanel = document.getElementById('inspiration-info');
        if (infoPanel) {
            const isSelf = allyId === gameState.playerId;
            infoPanel.innerHTML = `
                <h4>Inspire ${ally.name}${isSelf ? ' (Yourself)' : ''}</h4>
                <p class="inspiration-description">
                    Grant ${ally.name} a <strong class="die-highlight">${this.inspirationDie}</strong> Bardic Inspiration die.
                    Within the next 10 minutes, they can add this die to one ability check, attack roll, or saving throw.
                </p>
                <div class="inspiration-details">
                    <span class="detail"><strong>Die:</strong> ${this.inspirationDie}</span>
                    <span class="detail"><strong>Duration:</strong> 10 minutes</span>
                    <span class="detail"><strong>Uses:</strong> Once per inspiration</span>
                </div>
            `;
        }

        // Update button
        const btn = document.getElementById('btn-inspire');
        if (btn) {
            btn.disabled = false;
            btn.textContent = `Inspire ${ally.name}`;
        }
    }

    async inspireSelectedAlly() {
        if (!this.selectedAlly) return;

        const ally = this.selectedAlly;

        try {
            const gameState = state.getState();
            const combatId = gameState.combat?.id;
            const playerId = gameState.playerId;

            const response = await api.useClassFeature(combatId, 'bardic_inspiration', {
                combatant_id: playerId,
                target_id: ally.id,
                die: this.inspirationDie
            });

            if (response.success) {
                // Use bonus action
                state.set('turn.bonusActionUsed', true);

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                const player = gameState.combatants[playerId];
                state.addLogEntry({
                    type: 'class_feature',
                    actor: player?.name,
                    message: `${player?.name} inspires ${ally.name} with a ${this.inspirationDie} Bardic Inspiration die!`,
                });

                toast.success(`Inspired ${ally.name}! (${this.inspirationDie})`);
                eventBus.emit(EVENTS.BARDIC_INSPIRATION_GRANTED, {
                    source: playerId,
                    target: ally.id,
                    die: this.inspirationDie
                });

                this.hide();
            } else {
                toast.error(response.message || 'Failed to grant Bardic Inspiration');
            }
        } catch (error) {
            console.error('[BardicInspirationModal] Inspire error:', error);
            toast.error('Failed to grant Bardic Inspiration');
        }
    }
}

// Add event constant if not exists
if (!EVENTS.BARDIC_INSPIRATION_REQUESTED) {
    EVENTS.BARDIC_INSPIRATION_REQUESTED = 'classFeature:bardicInspirationRequested';
}

export const bardicInspirationModal = new BardicInspirationModal();
export default bardicInspirationModal;
