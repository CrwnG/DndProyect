/**
 * D&D Combat Engine - Channel Divinity Modal
 * Cleric/Paladin Channel Divinity selection UI
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';
import { toast } from './toast-notification.js';

class ChannelDivinityModal {
    constructor() {
        this.usesRemaining = 0;
        this.maxUses = 1;
        this.selectedOption = null;
        this.playerClass = '';
        this.subclass = '';
        this.level = 1;
        this.createModal();
        this.subscribeToEvents();
    }

    createModal() {
        const modal = document.createElement('div');
        modal.id = 'channel-divinity-modal';
        modal.className = 'channel-divinity-modal hidden';
        modal.innerHTML = `
            <div class="modal-overlay" id="channel-divinity-overlay"></div>
            <div class="modal-content channel-divinity-content">
                <div class="modal-header">
                    <h2><span class="header-icon">&#9768;</span> Channel Divinity</h2>
                    <button class="modal-close" id="channel-divinity-close">&times;</button>
                </div>

                <div class="uses-display">
                    <div class="uses-label">Uses Remaining</div>
                    <div class="uses-icons" id="channel-divinity-uses">
                        <!-- Populated dynamically -->
                    </div>
                    <div class="uses-text"><span id="cd-uses-current">1</span> / <span id="cd-uses-max">1</span></div>
                </div>

                <div class="channel-options-grid" id="channel-options-grid">
                    <!-- Populated dynamically -->
                </div>

                <div class="option-info" id="channel-option-info">
                    <p class="info-placeholder">Select a Channel Divinity option to see details</p>
                </div>

                <button class="btn-use-channel" id="btn-use-channel" disabled>Select an Option</button>
            </div>
        `;
        document.body.appendChild(modal);
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Close button
        document.getElementById('channel-divinity-close')?.addEventListener('click', () => this.hide());
        document.getElementById('channel-divinity-overlay')?.addEventListener('click', () => this.hide());

        // Use button
        document.getElementById('btn-use-channel')?.addEventListener('click', () => this.useSelectedOption());

        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible()) {
                this.hide();
            }
        });
    }

    subscribeToEvents() {
        eventBus.on(EVENTS.CHANNEL_DIVINITY_REQUESTED, (data) => {
            this.show(data);
        });
    }

    isVisible() {
        return !document.getElementById('channel-divinity-modal')?.classList.contains('hidden');
    }

    show(data = {}) {
        const gameState = state.getState();
        const player = data.player || gameState.combatants[gameState.playerId];

        // Get class info
        this.playerClass = (player?.stats?.class || player?.character_class || '').toLowerCase();
        this.subclass = (player?.stats?.subclass || player?.subclass || '').toLowerCase();
        this.level = player?.stats?.level || player?.level || 1;

        // Get uses remaining
        this.maxUses = this.level >= 18 ? 3 : (this.level >= 6 ? 2 : 1);
        this.usesRemaining = player?.resources?.channel_divinity_uses ?? this.maxUses;

        // Reset selection
        this.selectedOption = null;

        this.render();
        document.getElementById('channel-divinity-modal')?.classList.remove('hidden');
    }

    hide() {
        document.getElementById('channel-divinity-modal')?.classList.add('hidden');
        this.selectedOption = null;
    }

    render() {
        // Update uses display
        document.getElementById('cd-uses-current').textContent = this.usesRemaining;
        document.getElementById('cd-uses-max').textContent = this.maxUses;

        // Render uses icons
        const usesContainer = document.getElementById('channel-divinity-uses');
        if (usesContainer) {
            let html = '';
            for (let i = 0; i < this.maxUses; i++) {
                const filled = i < this.usesRemaining;
                html += `<span class="use-icon ${filled ? 'filled' : 'empty'}">&#9768;</span>`;
            }
            usesContainer.innerHTML = html;
        }

        // Render options grid
        this.renderOptionsGrid();

        // Reset info panel
        document.getElementById('channel-option-info').innerHTML =
            '<p class="info-placeholder">Select a Channel Divinity option to see details</p>';

        // Reset button
        const btn = document.getElementById('btn-use-channel');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Select an Option';
        }
    }

    getClericDomainOptions() {
        const baseOptions = [
            {
                id: 'turn_undead',
                name: 'Turn Undead',
                icon: '&#128128;',
                description: 'As an action, you present your holy symbol. Each undead within 30 feet must make a Wisdom saving throw or be turned for 1 minute.',
                effect: 'Undead flee (WIS save)',
                type: 'action',
                available: true
            }
        ];

        // Add Destroy Undead if level 5+
        if (this.level >= 5) {
            const destroyCR = this.level >= 17 ? 4 : (this.level >= 14 ? 3 : (this.level >= 11 ? 2 : (this.level >= 8 ? 1 : 0.5)));
            baseOptions.push({
                id: 'destroy_undead',
                name: 'Destroy Undead',
                icon: '&#128165;',
                description: `When an undead fails its save against Turn Undead and is CR ${destroyCR} or lower, it is instantly destroyed.`,
                effect: `Destroy CR ${destroyCR} or lower`,
                type: 'passive',
                available: true
            });
        }

        // Add domain-specific options
        const domainOptions = this.getDomainSpecificOptions();
        return [...baseOptions, ...domainOptions];
    }

    getDomainSpecificOptions() {
        switch (this.subclass) {
            case 'life':
            case 'life_domain':
                return [{
                    id: 'preserve_life',
                    name: 'Preserve Life',
                    icon: '&#10084;',
                    description: 'Heal allies within 30 feet, distributing up to 5x your cleric level in HP. Cannot heal above half max HP.',
                    effect: `Heal up to ${this.level * 5} HP total`,
                    type: 'action',
                    available: true
                }];

            case 'light':
            case 'light_domain':
                return [{
                    id: 'radiance_of_the_dawn',
                    name: 'Radiance of the Dawn',
                    icon: '&#9728;',
                    description: 'Dispel magical darkness within 30 feet. Hostile creatures in range take 2d10 + cleric level radiant damage (CON save for half).',
                    effect: `2d10+${this.level} radiant (CON save)`,
                    type: 'action',
                    available: true
                }];

            case 'war':
            case 'war_domain':
                return [{
                    id: 'guided_strike',
                    name: 'Guided Strike',
                    icon: '&#9876;',
                    description: 'When you make an attack roll, you can use Channel Divinity to gain a +10 bonus to the roll.',
                    effect: '+10 to attack roll',
                    type: 'reaction',
                    available: true
                }, {
                    id: 'war_gods_blessing',
                    name: "War God's Blessing",
                    icon: '&#128737;',
                    description: 'When an ally within 30 feet makes an attack roll, you can grant them a +10 bonus.',
                    effect: '+10 to ally attack',
                    type: 'reaction',
                    available: this.level >= 6
                }];

            case 'trickery':
            case 'trickery_domain':
                return [{
                    id: 'invoke_duplicity',
                    name: 'Invoke Duplicity',
                    icon: '&#128100;',
                    description: 'Create an illusory duplicate of yourself within 30 feet. You can cast spells as if you were in its space, and you have advantage on attacks when both you and the duplicate are within 5 feet of the target.',
                    effect: 'Create illusion duplicate',
                    type: 'action',
                    available: true
                }];

            default:
                return [];
        }
    }

    getPaladinOathOptions() {
        const oathOptions = {
            'devotion': [
                {
                    id: 'sacred_weapon',
                    name: 'Sacred Weapon',
                    icon: '&#9876;',
                    description: 'Imbue your weapon with holy energy for 1 minute. Add your Charisma modifier to attack rolls, weapon emits bright light.',
                    effect: '+CHA to attacks, magic weapon',
                    type: 'action',
                    available: true
                },
                {
                    id: 'turn_the_unholy',
                    name: 'Turn the Unholy',
                    icon: '&#128128;',
                    description: 'Fiends and undead within 30 feet must make a Wisdom save or be turned for 1 minute.',
                    effect: 'Turn fiends/undead',
                    type: 'action',
                    available: true
                }
            ],
            'vengeance': [
                {
                    id: 'abjure_enemy',
                    name: 'Abjure Enemy',
                    icon: '&#128065;',
                    description: 'One creature within 60 feet must make a Wisdom save or be frightened and its speed is 0 for 1 minute.',
                    effect: 'Frighten + immobilize',
                    type: 'action',
                    available: true
                },
                {
                    id: 'vow_of_enmity',
                    name: 'Vow of Enmity',
                    icon: '&#128544;',
                    description: 'Gain advantage on attack rolls against one creature within 10 feet for 1 minute.',
                    effect: 'Advantage on attacks',
                    type: 'bonus',
                    available: true
                }
            ],
            'ancients': [
                {
                    id: 'natures_wrath',
                    name: "Nature's Wrath",
                    icon: '&#127807;',
                    description: 'Spectral vines spring up and restrain a creature within 10 feet (STR/DEX save).',
                    effect: 'Restrain target',
                    type: 'action',
                    available: true
                },
                {
                    id: 'turn_the_faithless',
                    name: 'Turn the Faithless',
                    icon: '&#129412;',
                    description: 'Fey and fiends within 30 feet must make a Wisdom save or be turned for 1 minute.',
                    effect: 'Turn fey/fiends',
                    type: 'action',
                    available: true
                }
            ],
            'glory': [
                {
                    id: 'peerless_athlete',
                    name: 'Peerless Athlete',
                    icon: '&#127939;',
                    description: 'For 10 minutes, you have advantage on Athletics and Acrobatics checks, and your carrying/push/drag/lift capacity doubles.',
                    effect: 'Advantage on Athletics/Acrobatics',
                    type: 'bonus',
                    available: true
                },
                {
                    id: 'inspiring_smite',
                    name: 'Inspiring Smite',
                    icon: '&#10024;',
                    description: 'After you deal damage with Divine Smite, distribute temporary HP equal to 2d8 + level among allies within 30 feet.',
                    effect: 'Temp HP to allies after smite',
                    type: 'reaction',
                    available: true
                }
            ]
        };

        // Normalize subclass name
        const normalizedSubclass = this.subclass.replace(/_/g, '').replace(/oath of /i, '').replace(/oath/i, '').trim();

        // Find matching oath
        for (const [oathName, options] of Object.entries(oathOptions)) {
            if (normalizedSubclass.includes(oathName) || oathName.includes(normalizedSubclass)) {
                return options;
            }
        }

        // Default to Devotion if no match
        return oathOptions['devotion'] || [];
    }

    getOptions() {
        if (this.playerClass === 'cleric') {
            return this.getClericDomainOptions();
        } else if (this.playerClass === 'paladin') {
            return this.getPaladinOathOptions();
        }
        return [];
    }

    renderOptionsGrid() {
        const grid = document.getElementById('channel-options-grid');
        if (!grid) return;

        const gameState = state.getState();
        const turn = gameState.turn || {};
        const actionUsed = turn.actionUsed;
        const bonusUsed = turn.bonusActionUsed;
        const reactionUsed = turn.reactionUsed;

        const options = this.getOptions();
        this.options = options;

        let html = '';

        for (const option of options) {
            // Check if can use based on action type
            let canUse = option.available && this.usesRemaining > 0;
            if (option.type === 'action' && actionUsed) canUse = false;
            if (option.type === 'bonus' && bonusUsed) canUse = false;
            if (option.type === 'reaction' && reactionUsed) canUse = false;
            if (option.type === 'passive') canUse = false; // Passive abilities aren't activated

            html += `
                <div class="channel-option-card ${!canUse ? 'disabled' : ''}"
                     data-option-id="${option.id}">
                    <div class="option-icon">${option.icon}</div>
                    <div class="option-name">${option.name}</div>
                    <div class="option-type">${this.formatType(option.type)}</div>
                    ${!option.available ? '<div class="level-lock">Not Available</div>' : ''}
                </div>
            `;
        }

        if (options.length === 0) {
            html = '<div class="no-options">No Channel Divinity options available for your class/subclass.</div>';
        }

        grid.innerHTML = html;

        // Add click handlers
        grid.querySelectorAll('.channel-option-card:not(.disabled)').forEach(card => {
            card.addEventListener('click', () => {
                const optionId = card.dataset.optionId;
                this.selectOption(optionId);
            });
        });
    }

    formatType(type) {
        switch (type) {
            case 'bonus': return 'Bonus Action';
            case 'action': return 'Action';
            case 'reaction': return 'Reaction';
            case 'passive': return 'Passive';
            default: return type;
        }
    }

    selectOption(optionId) {
        const option = this.options.find(o => o.id === optionId);
        if (!option) return;

        this.selectedOption = option;

        // Update visual selection
        document.querySelectorAll('.channel-option-card').forEach(c => c.classList.remove('selected'));
        document.querySelector(`[data-option-id="${optionId}"]`)?.classList.add('selected');

        // Show option info
        const infoPanel = document.getElementById('channel-option-info');
        if (infoPanel) {
            infoPanel.innerHTML = `
                <h4>${option.name}</h4>
                <p class="option-description">${option.description}</p>
                <div class="option-details">
                    <span class="detail"><strong>Type:</strong> ${this.formatType(option.type)}</span>
                    <span class="detail"><strong>Effect:</strong> ${option.effect}</span>
                </div>
            `;
        }

        // Update button
        const btn = document.getElementById('btn-use-channel');
        if (btn) {
            btn.disabled = false;
            btn.textContent = `Use ${option.name}`;
        }
    }

    async useSelectedOption() {
        if (!this.selectedOption) return;

        const option = this.selectedOption;

        try {
            const gameState = state.getState();
            const combatId = gameState.combat?.id;
            const playerId = gameState.playerId;

            const response = await api.useClassFeature(combatId, 'channel_divinity', {
                combatant_id: playerId,
                option: option.id
            });

            if (response.success) {
                // Update action economy based on type
                if (option.type === 'action') {
                    state.set('turn.actionUsed', true);
                } else if (option.type === 'bonus') {
                    state.set('turn.bonusActionUsed', true);
                } else if (option.type === 'reaction') {
                    state.set('turn.reactionUsed', true);
                }

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                const player = gameState.combatants[playerId];
                state.addLogEntry({
                    type: 'class_feature',
                    actor: player?.name,
                    message: `${player?.name} uses Channel Divinity: ${option.name}!`,
                });

                toast.success(`Channel Divinity: ${option.name}!`);
                eventBus.emit(EVENTS.CLASS_FEATURE_USED, {
                    feature: 'channel_divinity',
                    option: option.id
                });

                this.hide();
            } else {
                toast.error(response.message || 'Failed to use Channel Divinity');
            }
        } catch (error) {
            console.error('[ChannelDivinityModal] Use error:', error);
            toast.error('Failed to use Channel Divinity');
        }
    }
}

export const channelDivinityModal = new ChannelDivinityModal();
export default channelDivinityModal;
