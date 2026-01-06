/**
 * D&D Combat Engine - Metamagic Modal
 * Sorcerer Metamagic options UI
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';
import { toast } from './toast-notification.js';

class MetamagicModal {
    constructor() {
        this.sorceryPoints = 0;
        this.maxSorceryPoints = 0;
        this.selectedMetamagic = null;
        this.selectedSpell = null;
        this.level = 1;
        this.knownMetamagics = [];
        this.createModal();
        this.subscribeToEvents();
    }

    createModal() {
        const modal = document.createElement('div');
        modal.id = 'metamagic-modal';
        modal.className = 'metamagic-modal hidden';
        modal.innerHTML = `
            <div class="modal-overlay" id="metamagic-overlay"></div>
            <div class="modal-content metamagic-content">
                <div class="modal-header">
                    <h2><span class="header-icon">&#10024;</span> Metamagic</h2>
                    <button class="modal-close" id="metamagic-close">&times;</button>
                </div>

                <div class="sorcery-points-display">
                    <div class="points-label">Sorcery Points</div>
                    <div class="points-icons" id="sorcery-points-icons">
                        <!-- Populated dynamically -->
                    </div>
                    <div class="points-text"><span id="sorcery-current">0</span> / <span id="sorcery-max">0</span></div>
                </div>

                <div class="font-of-magic-section">
                    <button class="font-btn" id="btn-create-slot" title="Spend sorcery points to create spell slots">
                        <span class="font-icon">&#9733;</span> Create Slot
                    </button>
                    <button class="font-btn" id="btn-convert-slot" title="Convert spell slots to sorcery points">
                        <span class="font-icon">&#9670;</span> Convert Slot
                    </button>
                </div>

                <div class="metamagic-section">
                    <div class="section-label">Available Metamagic Options</div>
                    <div class="metamagic-grid" id="metamagic-grid">
                        <!-- Populated dynamically -->
                    </div>
                </div>

                <div class="metamagic-info" id="metamagic-info">
                    <p class="info-placeholder">Select a Metamagic option to see details</p>
                </div>

                <div class="spell-selection hidden" id="spell-selection">
                    <div class="section-label">Select Spell to Modify</div>
                    <div class="spell-grid" id="metamagic-spell-grid">
                        <!-- Populated when metamagic selected -->
                    </div>
                </div>

                <button class="btn-apply-metamagic" id="btn-apply-metamagic" disabled>Select Metamagic</button>
            </div>
        `;
        document.body.appendChild(modal);
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Close button
        document.getElementById('metamagic-close')?.addEventListener('click', () => this.hide());
        document.getElementById('metamagic-overlay')?.addEventListener('click', () => this.hide());

        // Apply button
        document.getElementById('btn-apply-metamagic')?.addEventListener('click', () => this.applyMetamagic());

        // Font of Magic buttons
        document.getElementById('btn-create-slot')?.addEventListener('click', () => this.showCreateSlotOptions());
        document.getElementById('btn-convert-slot')?.addEventListener('click', () => this.showConvertSlotOptions());

        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible()) {
                this.hide();
            }
        });
    }

    subscribeToEvents() {
        eventBus.on(EVENTS.METAMAGIC_REQUESTED, (data) => {
            this.show(data);
        });
    }

    isVisible() {
        return !document.getElementById('metamagic-modal')?.classList.contains('hidden');
    }

    show(data = {}) {
        const gameState = state.getState();
        const player = data.player || gameState.combatants[gameState.playerId];

        // Get sorcerer level
        this.level = player?.stats?.level || player?.level || 1;

        // Sorcery points = sorcerer level (starting at level 2)
        this.maxSorceryPoints = this.level >= 2 ? this.level : 0;
        this.sorceryPoints = player?.resources?.sorcery_points ?? this.maxSorceryPoints;

        // Get known metamagics (from class features or default based on level)
        this.knownMetamagics = player?.features?.metamagic || this.getDefaultMetamagics();

        // Reset selection
        this.selectedMetamagic = null;
        this.selectedSpell = null;

        this.render();
        document.getElementById('metamagic-modal')?.classList.remove('hidden');
    }

    hide() {
        document.getElementById('metamagic-modal')?.classList.add('hidden');
        this.selectedMetamagic = null;
        this.selectedSpell = null;
    }

    getDefaultMetamagics() {
        // Sorcerers learn 2 metamagic options at level 3, additional at 10 and 17
        const allMetamagics = [
            'careful', 'distant', 'empowered', 'extended',
            'heightened', 'quickened', 'subtle', 'twinned'
        ];

        if (this.level < 3) return [];

        // Default to first options available for testing
        let count = 2;
        if (this.level >= 10) count = 3;
        if (this.level >= 17) count = 4;

        return allMetamagics.slice(0, count);
    }

    getAllMetamagicOptions() {
        return {
            careful: {
                id: 'careful',
                name: 'Careful Spell',
                icon: '&#128737;',
                cost: 1,
                description: 'When you cast a spell that forces other creatures to make a saving throw, you can protect some of those creatures from the spell. Spend 1 sorcery point and choose a number of creatures up to your Charisma modifier. A chosen creature automatically succeeds on its saving throw.',
                shortEffect: 'Allies auto-save vs your AoE',
                requiresSpell: true,
                spellFilter: (spell) => spell.save_type && spell.area_of_effect
            },
            distant: {
                id: 'distant',
                name: 'Distant Spell',
                icon: '&#127919;',
                cost: 1,
                description: 'When you cast a spell that has a range of 5 feet or greater, you can spend 1 sorcery point to double the range of the spell. When you cast a spell that has a range of touch, you can spend 1 sorcery point to make the range 30 feet.',
                shortEffect: 'Double spell range',
                requiresSpell: true,
                spellFilter: (spell) => spell.range && spell.range !== 'Self'
            },
            empowered: {
                id: 'empowered',
                name: 'Empowered Spell',
                icon: '&#128165;',
                cost: 1,
                description: 'When you roll damage for a spell, you can spend 1 sorcery point to reroll a number of damage dice up to your Charisma modifier. You must use the new rolls.',
                shortEffect: 'Reroll damage dice',
                requiresSpell: true,
                spellFilter: (spell) => spell.damage || spell.damage_dice
            },
            extended: {
                id: 'extended',
                name: 'Extended Spell',
                icon: '&#8987;',
                cost: 1,
                description: 'When you cast a spell that has a duration of 1 minute or longer, you can spend 1 sorcery point to double its duration, to a maximum of 24 hours.',
                shortEffect: 'Double duration',
                requiresSpell: true,
                spellFilter: (spell) => spell.duration && !['Instantaneous', 'Until dispelled'].includes(spell.duration)
            },
            heightened: {
                id: 'heightened',
                name: 'Heightened Spell',
                icon: '&#11014;',
                cost: 3,
                description: 'When you cast a spell that forces a creature to make a saving throw, you can spend 3 sorcery points to give one target of the spell disadvantage on its first saving throw.',
                shortEffect: 'Target has disadvantage on save',
                requiresSpell: true,
                spellFilter: (spell) => spell.save_type
            },
            quickened: {
                id: 'quickened',
                name: 'Quickened Spell',
                icon: '&#9889;',
                cost: 2,
                description: 'When you cast a spell that has a casting time of 1 action, you can spend 2 sorcery points to change the casting time to 1 bonus action.',
                shortEffect: 'Cast as bonus action',
                requiresSpell: true,
                spellFilter: (spell) => spell.casting_time === '1 action' || spell.casting_time === 'Action'
            },
            subtle: {
                id: 'subtle',
                name: 'Subtle Spell',
                icon: '&#129296;',
                cost: 1,
                description: 'When you cast a spell, you can spend 1 sorcery point to cast it without any somatic or verbal components.',
                shortEffect: 'No V/S components',
                requiresSpell: true,
                spellFilter: (spell) => spell.components?.includes('V') || spell.components?.includes('S')
            },
            twinned: {
                id: 'twinned',
                name: 'Twinned Spell',
                icon: '&#9878;',
                cost: 'level',
                description: 'When you cast a spell that targets only one creature and doesn\'t have a range of self, you can spend sorcery points equal to the spell\'s level (1 for cantrips) to target a second creature.',
                shortEffect: 'Target second creature',
                requiresSpell: true,
                spellFilter: (spell) => spell.target_type === 'single' && spell.range !== 'Self'
            }
        };
    }

    render() {
        // Update sorcery points display
        document.getElementById('sorcery-current').textContent = this.sorceryPoints;
        document.getElementById('sorcery-max').textContent = this.maxSorceryPoints;

        // Render sorcery point icons
        const iconsContainer = document.getElementById('sorcery-points-icons');
        if (iconsContainer) {
            let html = '';
            for (let i = 0; i < this.maxSorceryPoints; i++) {
                const filled = i < this.sorceryPoints;
                html += `<span class="point-icon ${filled ? 'filled' : 'empty'}">&#9670;</span>`;
            }
            iconsContainer.innerHTML = html;
        }

        // Render metamagic options
        this.renderMetamagicGrid();

        // Reset spell selection
        document.getElementById('spell-selection')?.classList.add('hidden');

        // Reset info panel
        document.getElementById('metamagic-info').innerHTML =
            '<p class="info-placeholder">Select a Metamagic option to see details</p>';

        // Reset button
        const btn = document.getElementById('btn-apply-metamagic');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Select Metamagic';
        }
    }

    renderMetamagicGrid() {
        const grid = document.getElementById('metamagic-grid');
        if (!grid) return;

        const allOptions = this.getAllMetamagicOptions();
        const gameState = state.getState();
        const turn = gameState.turn || {};

        let html = '';

        for (const metamagicId of this.knownMetamagics) {
            const option = allOptions[metamagicId];
            if (!option) continue;

            const cost = option.cost === 'level' ? '1+' : option.cost;
            const canAfford = this.sorceryPoints >= (option.cost === 'level' ? 1 : option.cost);

            html += `
                <div class="metamagic-card ${!canAfford ? 'disabled' : ''}"
                     data-metamagic-id="${option.id}">
                    <div class="metamagic-icon">${option.icon}</div>
                    <div class="metamagic-name">${option.name}</div>
                    <div class="metamagic-cost">${cost} SP</div>
                </div>
            `;
        }

        if (this.knownMetamagics.length === 0) {
            html = '<div class="no-metamagic">Learn Metamagic at Sorcerer level 3</div>';
        }

        grid.innerHTML = html;

        // Add click handlers
        grid.querySelectorAll('.metamagic-card:not(.disabled)').forEach(card => {
            card.addEventListener('click', () => {
                const metamagicId = card.dataset.metamagicId;
                this.selectMetamagic(metamagicId);
            });
        });
    }

    selectMetamagic(metamagicId) {
        const allOptions = this.getAllMetamagicOptions();
        const option = allOptions[metamagicId];
        if (!option) return;

        this.selectedMetamagic = option;
        this.selectedSpell = null;

        // Update visual selection
        document.querySelectorAll('.metamagic-card').forEach(c => c.classList.remove('selected'));
        document.querySelector(`[data-metamagic-id="${metamagicId}"]`)?.classList.add('selected');

        // Show option info
        const infoPanel = document.getElementById('metamagic-info');
        if (infoPanel) {
            const costText = option.cost === 'level' ? 'Spell Level (1 min)' : `${option.cost} SP`;
            infoPanel.innerHTML = `
                <h4>${option.name}</h4>
                <p class="metamagic-description">${option.description}</p>
                <div class="metamagic-details">
                    <span class="detail"><strong>Cost:</strong> ${costText}</span>
                    <span class="detail"><strong>Effect:</strong> ${option.shortEffect}</span>
                </div>
            `;
        }

        // Show spell selection if metamagic requires a spell
        if (option.requiresSpell) {
            this.renderSpellSelection(option);
        } else {
            document.getElementById('spell-selection')?.classList.add('hidden');
            this.updateApplyButton();
        }
    }

    renderSpellSelection(metamagic) {
        const spellSection = document.getElementById('spell-selection');
        const spellGrid = document.getElementById('metamagic-spell-grid');
        if (!spellSection || !spellGrid) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];

        // Get player's known/prepared spells
        const knownSpells = player?.spells || player?.spellbook || [];

        // Filter spells based on metamagic requirements
        const filteredSpells = knownSpells.filter(spell => {
            if (metamagic.spellFilter) {
                return metamagic.spellFilter(spell);
            }
            return true;
        });

        if (filteredSpells.length === 0) {
            spellGrid.innerHTML = '<div class="no-spells">No compatible spells available</div>';
            spellSection.classList.remove('hidden');
            return;
        }

        let html = '';
        for (const spell of filteredSpells) {
            const level = spell.level || 0;
            const levelText = level === 0 ? 'Cantrip' : `Level ${level}`;

            // Calculate cost for twinned spell
            let costText = '';
            if (metamagic.id === 'twinned') {
                const cost = Math.max(1, level);
                const canAfford = this.sorceryPoints >= cost;
                if (!canAfford) {
                    continue; // Skip spells we can't afford to twin
                }
                costText = `(${cost} SP)`;
            }

            html += `
                <div class="spell-card" data-spell-id="${spell.id || spell.name}">
                    <div class="spell-name">${spell.name} ${costText}</div>
                    <div class="spell-level">${levelText}</div>
                </div>
            `;
        }

        if (html === '') {
            html = '<div class="no-spells">No affordable compatible spells</div>';
        }

        spellGrid.innerHTML = html;
        spellSection.classList.remove('hidden');

        // Add click handlers
        spellGrid.querySelectorAll('.spell-card').forEach(card => {
            card.addEventListener('click', () => {
                const spellId = card.dataset.spellId;
                this.selectSpell(spellId, filteredSpells);
            });
        });
    }

    selectSpell(spellId, spellList) {
        const spell = spellList.find(s => (s.id || s.name) === spellId);
        if (!spell) return;

        this.selectedSpell = spell;

        // Update visual selection
        document.querySelectorAll('.spell-card').forEach(c => c.classList.remove('selected'));
        document.querySelector(`[data-spell-id="${spellId}"]`)?.classList.add('selected');

        this.updateApplyButton();
    }

    updateApplyButton() {
        const btn = document.getElementById('btn-apply-metamagic');
        if (!btn) return;

        if (this.selectedMetamagic) {
            if (this.selectedMetamagic.requiresSpell) {
                if (this.selectedSpell) {
                    btn.disabled = false;
                    btn.textContent = `Apply ${this.selectedMetamagic.name} to ${this.selectedSpell.name}`;
                } else {
                    btn.disabled = true;
                    btn.textContent = 'Select a Spell';
                }
            } else {
                btn.disabled = false;
                btn.textContent = `Use ${this.selectedMetamagic.name}`;
            }
        } else {
            btn.disabled = true;
            btn.textContent = 'Select Metamagic';
        }
    }

    async applyMetamagic() {
        if (!this.selectedMetamagic) return;

        const metamagic = this.selectedMetamagic;
        const spell = this.selectedSpell;

        // Calculate cost
        let cost = metamagic.cost;
        if (cost === 'level') {
            cost = spell ? Math.max(1, spell.level || 0) : 1;
        }

        if (this.sorceryPoints < cost) {
            toast.error('Not enough sorcery points!');
            return;
        }

        try {
            const gameState = state.getState();
            const combatId = gameState.combat?.id;
            const playerId = gameState.playerId;

            const response = await api.useClassFeature(combatId, 'metamagic', {
                combatant_id: playerId,
                metamagic_id: metamagic.id,
                spell_id: spell?.id || spell?.name,
                cost: cost
            });

            if (response.success) {
                // Update sorcery points locally
                this.sorceryPoints -= cost;

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                const player = gameState.combatants[playerId];
                const message = spell
                    ? `${player?.name} applies ${metamagic.name} to ${spell.name}!`
                    : `${player?.name} uses ${metamagic.name}!`;

                state.addLogEntry({
                    type: 'class_feature',
                    actor: player?.name,
                    message: message,
                });

                toast.success(`${metamagic.name} applied! (-${cost} SP)`);
                eventBus.emit(EVENTS.CLASS_FEATURE_USED, {
                    feature: 'metamagic',
                    metamagic: metamagic.id,
                    spell: spell?.name,
                    cost: cost
                });

                this.hide();
            } else {
                toast.error(response.message || 'Failed to apply Metamagic');
            }
        } catch (error) {
            console.error('[MetamagicModal] Apply error:', error);
            toast.error('Failed to apply Metamagic');
        }
    }

    showCreateSlotOptions() {
        // Font of Magic: Create spell slots by spending sorcery points
        const costs = {
            1: 2,  // 1st level slot costs 2 SP
            2: 3,  // 2nd level slot costs 3 SP
            3: 5,  // 3rd level slot costs 5 SP
            4: 6,  // 4th level slot costs 6 SP
            5: 7   // 5th level slot costs 7 SP
        };

        const infoPanel = document.getElementById('metamagic-info');
        if (!infoPanel) return;

        let html = '<h4>Create Spell Slot</h4><p>Spend sorcery points to create spell slots:</p>';
        html += '<div class="font-options">';

        for (const [level, cost] of Object.entries(costs)) {
            const canAfford = this.sorceryPoints >= cost;
            html += `
                <button class="font-option ${!canAfford ? 'disabled' : ''}"
                        data-action="create" data-level="${level}" data-cost="${cost}"
                        ${!canAfford ? 'disabled' : ''}>
                    Level ${level} Slot (${cost} SP)
                </button>
            `;
        }

        html += '</div>';
        infoPanel.innerHTML = html;

        // Add click handlers
        infoPanel.querySelectorAll('.font-option:not(.disabled)').forEach(btn => {
            btn.addEventListener('click', () => {
                const level = parseInt(btn.dataset.level);
                const cost = parseInt(btn.dataset.cost);
                this.createSpellSlot(level, cost);
            });
        });
    }

    showConvertSlotOptions() {
        // Font of Magic: Convert spell slots to sorcery points
        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const spellSlots = player?.resources?.spell_slots || {};

        const infoPanel = document.getElementById('metamagic-info');
        if (!infoPanel) return;

        let html = '<h4>Convert Spell Slot</h4><p>Convert a spell slot to sorcery points (gain points = slot level):</p>';
        html += '<div class="font-options">';

        for (let level = 1; level <= 5; level++) {
            const available = spellSlots[level] || 0;
            const canConvert = available > 0;
            html += `
                <button class="font-option ${!canConvert ? 'disabled' : ''}"
                        data-action="convert" data-level="${level}"
                        ${!canConvert ? 'disabled' : ''}>
                    Level ${level} (${available} available) → +${level} SP
                </button>
            `;
        }

        html += '</div>';
        infoPanel.innerHTML = html;

        // Add click handlers
        infoPanel.querySelectorAll('.font-option:not(.disabled)').forEach(btn => {
            btn.addEventListener('click', () => {
                const level = parseInt(btn.dataset.level);
                this.convertSpellSlot(level);
            });
        });
    }

    async createSpellSlot(level, cost) {
        if (this.sorceryPoints < cost) {
            toast.error('Not enough sorcery points!');
            return;
        }

        try {
            const gameState = state.getState();
            const combatId = gameState.combat?.id;
            const playerId = gameState.playerId;

            const response = await api.useClassFeature(combatId, 'font_of_magic', {
                combatant_id: playerId,
                action: 'create_slot',
                slot_level: level,
                cost: cost
            });

            if (response.success) {
                this.sorceryPoints -= cost;

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                toast.success(`Created level ${level} spell slot! (-${cost} SP)`);
                this.render();
            } else {
                toast.error(response.message || 'Failed to create spell slot');
            }
        } catch (error) {
            console.error('[MetamagicModal] Create slot error:', error);
            toast.error('Failed to create spell slot');
        }
    }

    async convertSpellSlot(level) {
        try {
            const gameState = state.getState();
            const combatId = gameState.combat?.id;
            const playerId = gameState.playerId;

            const response = await api.useClassFeature(combatId, 'font_of_magic', {
                combatant_id: playerId,
                action: 'convert_slot',
                slot_level: level
            });

            if (response.success) {
                this.sorceryPoints = Math.min(this.sorceryPoints + level, this.maxSorceryPoints);

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                toast.success(`Converted spell slot to ${level} sorcery points!`);
                this.render();
            } else {
                toast.error(response.message || 'Failed to convert spell slot');
            }
        } catch (error) {
            console.error('[MetamagicModal] Convert slot error:', error);
            toast.error('Failed to convert spell slot');
        }
    }
}

export const metamagicModal = new MetamagicModal();
export default metamagicModal;
