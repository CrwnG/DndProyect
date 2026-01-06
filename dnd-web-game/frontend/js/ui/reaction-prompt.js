/**
 * D&D Combat Engine - Reaction Prompt
 * UI for player reactions (Shield, Uncanny Dodge, Counterspell, etc.)
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';

class ReactionPrompt {
    constructor() {
        this.isVisible = false;
        this.currentTrigger = null;
        this.availableReactions = [];
        this.timeoutId = null;
        this.timeRemaining = 0;
        this.createPrompt();
        this.subscribeToEvents();
    }

    createPrompt() {
        const prompt = document.createElement('div');
        prompt.id = 'reaction-prompt';
        prompt.className = 'reaction-prompt hidden';
        prompt.innerHTML = `
            <div class="reaction-prompt-overlay" id="reaction-overlay"></div>
            <div class="reaction-prompt-content">
                <div class="reaction-header">
                    <div class="reaction-title">
                        <span class="reaction-icon">&#9889;</span>
                        <h3>Reaction Available!</h3>
                    </div>
                    <div class="reaction-timer" id="reaction-timer">
                        <div class="timer-bar" id="timer-bar"></div>
                    </div>
                </div>

                <div class="reaction-trigger" id="reaction-trigger">
                    <!-- Trigger description goes here -->
                </div>

                <div class="reaction-options" id="reaction-options">
                    <!-- Available reactions go here -->
                </div>

                <div class="reaction-actions">
                    <button class="btn-decline" id="btn-decline-reaction">
                        <span class="btn-icon">&#10060;</span>
                        <span class="btn-text">Decline</span>
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(prompt);
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Decline button
        document.getElementById('btn-decline-reaction')?.addEventListener('click', () => {
            this.decline();
        });

        // Clicking overlay also declines (convenient for fast gameplay)
        document.getElementById('reaction-overlay')?.addEventListener('click', () => {
            this.decline();
        });

        // Escape key to decline
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible) {
                this.decline();
            }
        });

        // Number keys for quick selection (1, 2, 3, etc.)
        document.addEventListener('keydown', (e) => {
            if (!this.isVisible) return;
            const num = parseInt(e.key);
            if (num >= 1 && num <= this.availableReactions.length) {
                const reaction = this.availableReactions[num - 1];
                if (reaction && !reaction.disabled) {
                    this.useReaction(reaction);
                }
            }
        });
    }

    subscribeToEvents() {
        // Listen for reaction opportunities from backend
        eventBus.on(EVENTS.REACTION_AVAILABLE, (data) => {
            this.show(data);
        });

        // Hide prompt when combat ends
        eventBus.on(EVENTS.COMBAT_ENDED, () => {
            this.hide();
        });

        // Hide prompt when turn changes (shouldn't happen but safety)
        eventBus.on(EVENTS.TURN_STARTED, () => {
            // Don't hide on turn start - reactions can happen any time
        });
    }

    /**
     * Show the reaction prompt
     * @param {Object} data - Reaction trigger data
     * @param {string} data.trigger_type - Type of trigger (attack, spell, movement)
     * @param {string} data.trigger_source_id - ID of combatant that triggered
     * @param {string} data.target_id - ID of the player being targeted (if applicable)
     * @param {Array} data.available_reactions - List of reactions player can use
     * @param {number} data.incoming_damage - Damage amount (for damage reactions)
     * @param {Object} data.spell - Spell being cast (for Counterspell)
     */
    show(data) {
        console.log('[ReactionPrompt] Show with data:', data);

        const gameState = state.getState();
        const turn = gameState.turn || {};

        // Check if reaction already used
        if (turn.reactionUsed) {
            console.log('[ReactionPrompt] Reaction already used this round');
            return;
        }

        this.currentTrigger = data;
        this.availableReactions = this.determineAvailableReactions(data);

        if (this.availableReactions.length === 0) {
            console.log('[ReactionPrompt] No valid reactions available');
            return;
        }

        // Build trigger description
        this.renderTriggerDescription(data);

        // Build reaction options
        this.renderReactionOptions();

        // Show the prompt
        document.getElementById('reaction-prompt')?.classList.remove('hidden');
        this.isVisible = true;

        // Start countdown timer (default 10 seconds, can be configured)
        this.startTimer(data.timeout || 10000);

        // Emit event that prompt is shown
        eventBus.emit(EVENTS.UI_MODAL_OPENED, { modal: 'reaction-prompt' });
    }

    hide() {
        document.getElementById('reaction-prompt')?.classList.add('hidden');
        this.isVisible = false;
        this.currentTrigger = null;
        this.availableReactions = [];

        if (this.timeoutId) {
            clearInterval(this.timeoutId);
            this.timeoutId = null;
        }

        eventBus.emit(EVENTS.UI_MODAL_CLOSED, { modal: 'reaction-prompt' });
    }

    /**
     * Determine which reactions are available based on trigger and player abilities
     */
    determineAvailableReactions(triggerData) {
        const reactions = [];
        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const playerStats = gameState.combatant_stats?.[gameState.playerId] || {};
        const playerClass = (player?.stats?.class || playerStats.class || '').toLowerCase();
        const playerLevel = player?.stats?.level || playerStats.level || 1;
        const spellSlots = playerStats.spell_slots || player?.resources?.spell_slots || {};

        const triggerType = triggerData.trigger_type;

        // Shield spell (Wizard, Sorcerer, or anyone with Shield prepared)
        if (triggerType === 'attack' && this.hasSpellPrepared('shield')) {
            const has1stSlot = (spellSlots['1'] || 0) > 0;
            reactions.push({
                id: 'shield',
                name: 'Shield',
                icon: '&#128737;',
                description: '+5 AC until start of next turn. Blocks this attack if it makes the attack miss.',
                type: 'spell',
                cost: '1st-level slot',
                disabled: !has1stSlot,
                disabledReason: !has1stSlot ? 'No spell slots' : null
            });
        }

        // Absorb Elements (reaction to elemental damage)
        if (triggerType === 'elemental_damage' && this.hasSpellPrepared('absorb_elements')) {
            const has1stSlot = (spellSlots['1'] || 0) > 0;
            reactions.push({
                id: 'absorb_elements',
                name: 'Absorb Elements',
                icon: '&#127775;',
                description: 'Gain resistance to triggering damage type. Your next melee attack deals +1d6 of that type.',
                type: 'spell',
                cost: '1st-level slot',
                disabled: !has1stSlot,
                disabledReason: !has1stSlot ? 'No spell slots' : null
            });
        }

        // Counterspell (reaction to spell being cast)
        if (triggerType === 'spell_cast' && this.hasSpellPrepared('counterspell')) {
            const has3rdSlot = (spellSlots['3'] || 0) > 0;
            const spellLevel = triggerData.spell?.level || 0;
            reactions.push({
                id: 'counterspell',
                name: 'Counterspell',
                icon: '&#128683;',
                description: `Counter the ${triggerData.spell?.name || 'spell'} (level ${spellLevel}). Auto-success if cast at same level or higher.`,
                type: 'spell',
                cost: '3rd-level slot',
                disabled: !has3rdSlot,
                disabledReason: !has3rdSlot ? 'No 3rd+ level slots' : null
            });
        }

        // Uncanny Dodge (Rogue 5+)
        if (triggerType === 'attack' && playerClass === 'rogue' && playerLevel >= 5) {
            reactions.push({
                id: 'uncanny_dodge',
                name: 'Uncanny Dodge',
                icon: '&#128168;',
                description: 'Halve the damage from this attack.',
                type: 'class_feature',
                cost: 'Reaction',
                disabled: false
            });
        }

        // Defensive Duelist (feat, requires finesse weapon)
        if (triggerType === 'attack' && this.hasFeat('defensive_duelist')) {
            const profBonus = Math.floor((playerLevel - 1) / 4) + 2;
            reactions.push({
                id: 'defensive_duelist',
                name: 'Defensive Duelist',
                icon: '&#9876;',
                description: `Add +${profBonus} (proficiency) to AC against this attack.`,
                type: 'feat',
                cost: 'Reaction',
                disabled: false
            });
        }

        // Sentinel (feat, reaction to attack on ally)
        if (triggerType === 'ally_attacked' && this.hasFeat('sentinel')) {
            reactions.push({
                id: 'sentinel',
                name: 'Sentinel',
                icon: '&#128737;',
                description: 'Make a melee attack against the attacker.',
                type: 'feat',
                cost: 'Reaction',
                disabled: false
            });
        }

        // Parry (Battle Master maneuver)
        if (triggerType === 'attack' && this.hasManeuver('parry')) {
            const superiorityDice = playerStats.superiority_dice || 0;
            reactions.push({
                id: 'parry',
                name: 'Parry',
                icon: '&#9876;',
                description: 'Add superiority die + DEX mod to AC against this attack.',
                type: 'maneuver',
                cost: '1 Superiority Die',
                disabled: superiorityDice === 0,
                disabledReason: superiorityDice === 0 ? 'No superiority dice' : null
            });
        }

        // Hellish Rebuke (Tiefling racial or Warlock)
        if (triggerType === 'damage_taken' && this.hasSpellPrepared('hellish_rebuke')) {
            const has1stSlot = (spellSlots['1'] || 0) > 0;
            reactions.push({
                id: 'hellish_rebuke',
                name: 'Hellish Rebuke',
                icon: '&#128293;',
                description: 'Deal 2d10 fire damage to the attacker (DEX save for half).',
                type: 'spell',
                cost: '1st-level slot',
                disabled: !has1stSlot,
                disabledReason: !has1stSlot ? 'No spell slots' : null
            });
        }

        // Opportunity Attack (always available when enemy leaves reach)
        if (triggerType === 'enemy_leaving_reach') {
            reactions.push({
                id: 'opportunity_attack',
                name: 'Opportunity Attack',
                icon: '&#9876;',
                description: `Make a melee attack against ${triggerData.enemy_name || 'the enemy'} as they flee.`,
                type: 'standard',
                cost: 'Reaction',
                disabled: false
            });
        }

        return reactions;
    }

    /**
     * Check if player has a spell prepared
     */
    hasSpellPrepared(spellId) {
        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const preparedSpells = player?.spells?.prepared || player?.prepared_spells || [];
        const knownSpells = player?.spells?.known || player?.known_spells || [];

        return preparedSpells.includes(spellId) ||
               knownSpells.includes(spellId) ||
               preparedSpells.some(s => s.id === spellId || s.name?.toLowerCase().replace(/\s/g, '_') === spellId) ||
               knownSpells.some(s => s.id === spellId || s.name?.toLowerCase().replace(/\s/g, '_') === spellId);
    }

    /**
     * Check if player has a feat
     */
    hasFeat(featId) {
        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const feats = player?.feats || player?.stats?.feats || [];
        return feats.includes(featId) || feats.some(f => f.id === featId || f.name?.toLowerCase().replace(/\s/g, '_') === featId);
    }

    /**
     * Check if player has a maneuver (Battle Master)
     */
    hasManeuver(maneuverId) {
        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const maneuvers = player?.maneuvers || player?.stats?.maneuvers || [];
        return maneuvers.includes(maneuverId) || maneuvers.some(m => m.id === maneuverId);
    }

    renderTriggerDescription(data) {
        const triggerEl = document.getElementById('reaction-trigger');
        if (!triggerEl) return;

        const gameState = state.getState();
        const sourceName = gameState.combatants[data.trigger_source_id]?.name || 'An enemy';

        let description = '';
        let icon = '&#9888;';

        switch (data.trigger_type) {
            case 'attack':
                icon = '&#9876;';
                description = `<strong>${sourceName}</strong> is attacking you!`;
                if (data.attack_roll) {
                    description += ` <span class="attack-roll">(Roll: ${data.attack_roll})</span>`;
                }
                if (data.incoming_damage) {
                    description += ` <span class="damage-preview">Potential damage: ${data.incoming_damage}</span>`;
                }
                break;
            case 'spell_cast':
                icon = '&#10024;';
                const spellName = data.spell?.name || 'a spell';
                description = `<strong>${sourceName}</strong> is casting <strong>${spellName}</strong>!`;
                break;
            case 'elemental_damage':
                icon = '&#127775;';
                description = `You're taking <strong>${data.damage_type || 'elemental'}</strong> damage!`;
                break;
            case 'enemy_leaving_reach':
                icon = '&#128099;';
                description = `<strong>${data.enemy_name || sourceName}</strong> is moving out of your reach!`;
                break;
            case 'ally_attacked':
                icon = '&#128737;';
                const allyName = gameState.combatants[data.target_id]?.name || 'Your ally';
                description = `<strong>${sourceName}</strong> is attacking <strong>${allyName}</strong>!`;
                break;
            case 'damage_taken':
                icon = '&#128165;';
                description = `You just took <strong>${data.incoming_damage || '?'}</strong> damage from <strong>${sourceName}</strong>!`;
                break;
            default:
                description = 'You can use a reaction!';
        }

        triggerEl.innerHTML = `
            <span class="trigger-icon">${icon}</span>
            <p class="trigger-description">${description}</p>
        `;
    }

    renderReactionOptions() {
        const optionsEl = document.getElementById('reaction-options');
        if (!optionsEl) return;

        let html = '';

        this.availableReactions.forEach((reaction, index) => {
            const disabledClass = reaction.disabled ? 'disabled' : '';
            const shortcutKey = index + 1;

            html += `
                <div class="reaction-option ${disabledClass}"
                     data-reaction-id="${reaction.id}"
                     ${reaction.disabled ? 'title="' + reaction.disabledReason + '"' : ''}>
                    <div class="reaction-option-icon">${reaction.icon}</div>
                    <div class="reaction-option-info">
                        <div class="reaction-option-name">${reaction.name}</div>
                        <div class="reaction-option-desc">${reaction.description}</div>
                        <div class="reaction-option-cost">${reaction.cost}</div>
                    </div>
                    <div class="reaction-option-shortcut">${shortcutKey}</div>
                </div>
            `;
        });

        optionsEl.innerHTML = html;

        // Add click handlers
        optionsEl.querySelectorAll('.reaction-option:not(.disabled)').forEach(el => {
            el.addEventListener('click', () => {
                const reactionId = el.dataset.reactionId;
                const reaction = this.availableReactions.find(r => r.id === reactionId);
                if (reaction) {
                    this.useReaction(reaction);
                }
            });
        });
    }

    startTimer(duration) {
        this.timeRemaining = duration;
        const timerBar = document.getElementById('timer-bar');
        if (!timerBar) return;

        // Reset timer bar
        timerBar.style.width = '100%';
        timerBar.style.transition = `width ${duration}ms linear`;

        // Trigger reflow then animate
        timerBar.offsetHeight;
        timerBar.style.width = '0%';

        // Set timeout to auto-decline
        this.timeoutId = setTimeout(() => {
            if (this.isVisible) {
                console.log('[ReactionPrompt] Timer expired, auto-declining');
                this.decline();
            }
        }, duration);
    }

    async useReaction(reaction) {
        if (!this.currentTrigger) return;

        console.log('[ReactionPrompt] Using reaction:', reaction.id);

        try {
            const gameState = state.getState();
            const response = await api.useReaction(
                gameState.combat?.id,
                gameState.playerId,
                reaction.id,
                this.currentTrigger.trigger_source_id
            );

            if (response.success) {
                // Log the reaction use
                eventBus.emit(EVENTS.UI_LOG_ENTRY, {
                    type: 'reaction',
                    message: response.description || `Used ${reaction.name}!`
                });

                // Emit reaction used event
                eventBus.emit(EVENTS.REACTION_USED, {
                    reaction: reaction.id,
                    reactor: gameState.playerId,
                    trigger: this.currentTrigger
                });

                // Mark reaction as used
                state.set('turn.reactionUsed', true);

                // Update combat state if provided
                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }
            } else {
                eventBus.emit(EVENTS.UI_NOTIFICATION, {
                    type: 'error',
                    message: response.description || 'Failed to use reaction'
                });
            }
        } catch (error) {
            console.error('[ReactionPrompt] Use reaction error:', error);
            eventBus.emit(EVENTS.UI_NOTIFICATION, {
                type: 'error',
                message: 'Failed to use reaction'
            });
        }

        this.hide();
    }

    decline() {
        console.log('[ReactionPrompt] Declined reaction');

        eventBus.emit(EVENTS.UI_LOG_ENTRY, {
            type: 'info',
            message: 'Declined to use reaction'
        });

        this.hide();
    }
}

export const reactionPrompt = new ReactionPrompt();
export default reactionPrompt;
