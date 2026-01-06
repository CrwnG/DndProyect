/**
 * D&D Combat Engine - Wild Shape Modal
 * Druid beast form selection UI
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';

class WildShapeModal {
    constructor() {
        this.selectedForm = null;
        this.availableForms = [];
        this.usesRemaining = 0;
        this.maxUses = 2;
        this.isActive = false;
        this.currentFormId = null;
        this.createModal();
        this.subscribeToEvents();
    }

    createModal() {
        const modal = document.createElement('div');
        modal.id = 'wild-shape-modal';
        modal.className = 'wild-shape-modal hidden';
        modal.innerHTML = `
            <div class="modal-overlay" id="wild-shape-overlay"></div>
            <div class="modal-content wild-shape-content">
                <div class="modal-header">
                    <h2><span class="header-icon">🐺</span> Wild Shape</h2>
                    <button class="modal-close" id="wild-shape-close">&times;</button>
                </div>

                <div class="wild-shape-info">
                    <div class="uses-display">
                        <span class="uses-label">Uses Remaining:</span>
                        <span class="uses-count" id="wild-shape-uses">2/2</span>
                    </div>
                    <div class="current-form hidden" id="current-form-display">
                        <span class="form-label">Current Form:</span>
                        <span class="form-name" id="current-form-name">-</span>
                        <button class="btn-revert" id="btn-revert-form">Revert</button>
                    </div>
                </div>

                <div class="form-grid" id="beast-form-grid">
                    <!-- Populated dynamically -->
                </div>

                <div class="form-details hidden" id="form-details">
                    <h3 id="form-name"></h3>
                    <div class="form-stats">
                        <div class="stat"><span class="stat-label">CR</span><span id="form-cr">-</span></div>
                        <div class="stat"><span class="stat-label">HP</span><span id="form-hp">-</span></div>
                        <div class="stat"><span class="stat-label">AC</span><span id="form-ac">-</span></div>
                        <div class="stat"><span class="stat-label">Speed</span><span id="form-speed">-</span></div>
                    </div>
                    <div class="form-abilities">
                        <h4>Abilities</h4>
                        <div class="ability-scores" id="form-abilities">
                            <!-- STR, DEX, CON, INT, WIS, CHA -->
                        </div>
                    </div>
                    <div class="form-attacks">
                        <h4>Attacks</h4>
                        <div id="form-attacks-list">
                            <!-- Beast attacks -->
                        </div>
                    </div>
                    <div class="form-traits" id="form-traits">
                        <!-- Special traits like Pack Tactics, Keen Senses, etc. -->
                    </div>
                    <button class="btn-transform" id="btn-transform" disabled>Select a Form</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Close button
        document.getElementById('wild-shape-close')?.addEventListener('click', () => this.hide());
        document.getElementById('wild-shape-overlay')?.addEventListener('click', () => this.hide());

        // Transform button
        document.getElementById('btn-transform')?.addEventListener('click', () => this.transform());

        // Revert button
        document.getElementById('btn-revert-form')?.addEventListener('click', () => this.revert());

        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible()) {
                this.hide();
            }
        });
    }

    subscribeToEvents() {
        eventBus.on(EVENTS.WILD_SHAPE_REQUESTED, () => {
            this.show();
        });
    }

    isVisible() {
        return !document.getElementById('wild-shape-modal')?.classList.contains('hidden');
    }

    async show() {
        try {
            const gameState = state.getState();
            const playerId = gameState.playerId;

            // Fetch available forms from API
            const response = await api.get(`/class-features/${gameState.combatId}/wild-shape/available-forms/${playerId}`);

            this.availableForms = response.available_forms || [];
            this.usesRemaining = response.uses_remaining || 0;
            this.maxUses = response.max_uses || 2;
            this.isActive = response.is_active || false;
            this.currentFormId = response.current_form || null;

            this.render();
            document.getElementById('wild-shape-modal')?.classList.remove('hidden');
        } catch (error) {
            console.error('[WildShapeModal] Error fetching forms:', error);
            eventBus.emit(EVENTS.UI_NOTIFICATION, {
                type: 'error',
                message: 'Failed to load Wild Shape forms'
            });
        }
    }

    hide() {
        document.getElementById('wild-shape-modal')?.classList.add('hidden');
        this.selectedForm = null;
    }

    render() {
        // Update uses display
        document.getElementById('wild-shape-uses').textContent = `${this.usesRemaining}/${this.maxUses}`;

        // Show current form if active
        const currentFormDisplay = document.getElementById('current-form-display');
        if (this.isActive && this.currentFormId) {
            const currentForm = this.availableForms.find(f => f.id === this.currentFormId);
            document.getElementById('current-form-name').textContent = currentForm?.name || this.currentFormId;
            currentFormDisplay?.classList.remove('hidden');
        } else {
            currentFormDisplay?.classList.add('hidden');
        }

        // Render form grid
        this.renderFormGrid();

        // Reset details panel
        document.getElementById('form-details')?.classList.add('hidden');
    }

    renderFormGrid() {
        const grid = document.getElementById('beast-form-grid');
        if (!grid) return;

        if (this.availableForms.length === 0) {
            grid.innerHTML = '<div class="no-forms">No beast forms available at your level</div>';
            return;
        }

        // Group forms by CR
        const formsByCR = {};
        this.availableForms.forEach(form => {
            const cr = form.cr || 0;
            if (!formsByCR[cr]) formsByCR[cr] = [];
            formsByCR[cr].push(form);
        });

        let html = '';

        // Sort CR values
        const crValues = Object.keys(formsByCR).map(Number).sort((a, b) => a - b);

        for (const cr of crValues) {
            const forms = formsByCR[cr];
            html += `<div class="cr-section">
                <h4 class="cr-header">CR ${cr === 0 ? '0' : cr}</h4>
                <div class="form-cards">`;

            for (const form of forms) {
                const disabled = this.usesRemaining <= 0 || this.isActive;
                const speedIcons = this.getSpeedIcons(form);

                html += `
                    <div class="form-card ${disabled ? 'disabled' : ''}"
                         data-form-id="${form.id}">
                        <div class="form-icon">${this.getFormIcon(form)}</div>
                        <div class="form-name">${form.name}</div>
                        <div class="form-quick-stats">
                            <span class="hp-badge">HP ${form.hp}</span>
                            <span class="ac-badge">AC ${form.ac}</span>
                        </div>
                        <div class="form-speeds">${speedIcons}</div>
                    </div>
                `;
            }

            html += '</div></div>';
        }

        grid.innerHTML = html;

        // Add click handlers
        grid.querySelectorAll('.form-card:not(.disabled)').forEach(card => {
            card.addEventListener('click', () => {
                this.selectForm(card.dataset.formId);
            });
        });
    }

    getFormIcon(form) {
        // Map common beast types to emojis
        const name = form.name?.toLowerCase() || '';

        if (name.includes('wolf') || name.includes('dire wolf')) return '🐺';
        if (name.includes('bear')) return '🐻';
        if (name.includes('cat') || name.includes('panther') || name.includes('lion') || name.includes('tiger')) return '🐱';
        if (name.includes('spider')) return '🕷️';
        if (name.includes('snake') || name.includes('constrictor') || name.includes('viper')) return '🐍';
        if (name.includes('rat')) return '🐀';
        if (name.includes('bat')) return '🦇';
        if (name.includes('hawk') || name.includes('eagle') || name.includes('owl')) return '🦅';
        if (name.includes('crocodile') || name.includes('alligator')) return '🐊';
        if (name.includes('shark')) return '🦈';
        if (name.includes('octopus')) return '🐙';
        if (name.includes('boar')) return '🐗';
        if (name.includes('horse') || name.includes('riding')) return '🐴';
        if (name.includes('ape') || name.includes('gorilla')) return '🦍';
        if (name.includes('elephant') || name.includes('mammoth')) return '🐘';
        if (name.includes('frog') || name.includes('toad')) return '🐸';

        return '🦎'; // Default
    }

    getSpeedIcons(form) {
        let icons = [];
        const speed = form.speed || {};

        if (speed.walk || typeof form.speed === 'number') {
            icons.push('🚶');
        }
        if (speed.swim) {
            icons.push('🏊');
        }
        if (speed.fly) {
            icons.push('🦅');
        }
        if (speed.climb) {
            icons.push('🧗');
        }
        if (speed.burrow) {
            icons.push('🕳️');
        }

        return icons.join(' ');
    }

    selectForm(formId) {
        const form = this.availableForms.find(f => f.id === formId);
        if (!form) return;

        this.selectedForm = form;

        // Update card selection
        document.querySelectorAll('.form-card').forEach(c => c.classList.remove('selected'));
        document.querySelector(`[data-form-id="${formId}"]`)?.classList.add('selected');

        // Show details
        this.showFormDetails(form);
    }

    showFormDetails(form) {
        const panel = document.getElementById('form-details');
        if (!panel) return;

        document.getElementById('form-name').textContent = form.name;
        document.getElementById('form-cr').textContent = form.cr;
        document.getElementById('form-hp').textContent = form.hp;
        document.getElementById('form-ac').textContent = form.ac;

        // Speed
        let speedText = '';
        if (typeof form.speed === 'object') {
            const speeds = [];
            if (form.speed.walk) speeds.push(`${form.speed.walk} ft.`);
            if (form.speed.swim) speeds.push(`swim ${form.speed.swim} ft.`);
            if (form.speed.fly) speeds.push(`fly ${form.speed.fly} ft.`);
            if (form.speed.climb) speeds.push(`climb ${form.speed.climb} ft.`);
            if (form.speed.burrow) speeds.push(`burrow ${form.speed.burrow} ft.`);
            speedText = speeds.join(', ');
        } else {
            speedText = `${form.speed || 30} ft.`;
        }
        document.getElementById('form-speed').textContent = speedText;

        // Abilities
        const abilities = form.abilities || {};
        document.getElementById('form-abilities').innerHTML = `
            <div class="ability"><span>STR</span><span>${abilities.strength || 10}</span></div>
            <div class="ability"><span>DEX</span><span>${abilities.dexterity || 10}</span></div>
            <div class="ability"><span>CON</span><span>${abilities.constitution || 10}</span></div>
            <div class="ability"><span>INT</span><span>${abilities.intelligence || 10}</span></div>
            <div class="ability"><span>WIS</span><span>${abilities.wisdom || 10}</span></div>
            <div class="ability"><span>CHA</span><span>${abilities.charisma || 10}</span></div>
        `;

        // Attacks
        const attacks = form.attacks || [];
        let attacksHtml = '';
        for (const attack of attacks) {
            attacksHtml += `
                <div class="attack-item">
                    <strong>${attack.name}</strong>: +${attack.attack_bonus || 0} to hit,
                    ${attack.damage_dice || '1d4'}${attack.damage_bonus ? ` + ${attack.damage_bonus}` : ''} ${attack.damage_type || ''} damage
                </div>
            `;
        }
        document.getElementById('form-attacks-list').innerHTML = attacksHtml || '<em>No attacks</em>';

        // Traits
        const traits = form.traits || [];
        let traitsHtml = '';
        if (traits.length > 0) {
            traitsHtml = '<h4>Special Traits</h4>';
            for (const trait of traits) {
                traitsHtml += `<div class="trait-item"><strong>${trait.name}:</strong> ${trait.description}</div>`;
            }
        }
        document.getElementById('form-traits').innerHTML = traitsHtml;

        // Update transform button
        const btn = document.getElementById('btn-transform');
        if (btn) {
            btn.disabled = false;
            btn.textContent = `Transform into ${form.name}`;
        }

        panel.classList.remove('hidden');
    }

    async transform() {
        if (!this.selectedForm) return;

        try {
            const gameState = state.getState();
            const response = await api.useWildShape(
                gameState.combatId,
                gameState.playerId,
                this.selectedForm.id
            );

            if (response.success) {
                eventBus.emit(EVENTS.WILD_SHAPE_TRANSFORMED, {
                    formId: this.selectedForm.id,
                    formName: this.selectedForm.name,
                    formStats: response.form_stats
                });

                eventBus.emit(EVENTS.UI_LOG_ENTRY, {
                    type: 'class_feature',
                    message: response.description
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
            console.error('[WildShapeModal] Transform error:', error);
            eventBus.emit(EVENTS.UI_NOTIFICATION, {
                type: 'error',
                message: 'Failed to transform'
            });
        }
    }

    async revert() {
        try {
            const gameState = state.getState();
            const response = await api.revertWildShape(
                gameState.combatId,
                gameState.playerId
            );

            if (response.success) {
                eventBus.emit(EVENTS.WILD_SHAPE_REVERTED, {});

                eventBus.emit(EVENTS.UI_LOG_ENTRY, {
                    type: 'class_feature',
                    message: response.description
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
            console.error('[WildShapeModal] Revert error:', error);
            eventBus.emit(EVENTS.UI_NOTIFICATION, {
                type: 'error',
                message: 'Failed to revert form'
            });
        }
    }
}

export const wildShapeModal = new WildShapeModal();
export default wildShapeModal;
