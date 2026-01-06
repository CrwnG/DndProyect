/**
 * D&D Combat Engine - Character Panel
 * Displays current character stats, HP, conditions, etc.
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';

class CharacterPanel {
    constructor() {
        // DOM elements
        this.elements = {
            charName: document.getElementById('char-name'),
            charClass: document.getElementById('char-class'),
            hpBar: document.getElementById('hp-bar'),
            hpText: document.getElementById('hp-text'),
            charAc: document.getElementById('char-ac'),
            movementRemaining: document.getElementById('movement-remaining'),
            weaponName: document.getElementById('weapon-name'),
            weaponMastery: document.getElementById('weapon-mastery'),
            conditionsList: document.getElementById('conditions-list'),
            enemyList: document.getElementById('enemy-list'),
            // Death saves
            deathSavesBlock: document.getElementById('death-saves-block'),
            deathSaveSuccesses: document.getElementById('death-save-successes'),
            deathSaveFailures: document.getElementById('death-save-failures'),
            btnRollDeathSave: document.getElementById('btn-roll-death-save'),
        };

        this.setupDeathSaveButton();
        this.subscribeToState();
    }

    /**
     * Set up death save button click handler
     */
    setupDeathSaveButton() {
        if (this.elements.btnRollDeathSave) {
            this.elements.btnRollDeathSave.addEventListener('click', () => this.rollDeathSave());
        }
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
     * Update the panel with new state
     */
    update(gameState) {
        const playerId = gameState.playerId;
        const player = gameState.combatants[playerId];

        if (player) {
            this.updatePlayerInfo(player);
            this.updateHP(player);
            this.updateConditions(player);
            this.updateDeathSaves(player, gameState);
        }

        this.updateMovement(gameState);
        this.updateEnemyList(gameState);
    }

    /**
     * Update player info section
     */
    updatePlayerInfo(player) {
        // DEBUG: Log the full player object to see what data we're receiving
        console.log('[CharacterPanel] FULL PLAYER DATA:', JSON.stringify(player, null, 2));
        console.log('[CharacterPanel] player.stats:', player.stats);
        console.log('[CharacterPanel] player.abilities:', player.abilities);
        console.log('[CharacterPanel] player.character_class:', player.character_class);

        if (this.elements.charName) {
            this.elements.charName.textContent = player.name || '-';
        }
        if (this.elements.charClass) {
            // Check multiple locations for class/level data
            const classText = player.stats?.class || player.abilities?.class || player.character_class || 'Adventurer';
            const level = player.stats?.level || player.abilities?.level || player.level || 1;
            console.log('[CharacterPanel] classText resolved to:', classText, 'level:', level);
            // Capitalize first letter of class
            const displayClass = classText.charAt(0).toUpperCase() + classText.slice(1);
            this.elements.charClass.textContent = `${displayClass} ${level}`;
        }
        if (this.elements.charAc) {
            this.elements.charAc.textContent = player.ac || '-';
        }
        // Get equipped weapon from equipment system (dynamic) or fallback to stats (static)
        const equippedWeapon = player.equipment?.main_hand || player.stats?.weapon || player.abilities?.weapons?.[0];
        if (this.elements.weaponName) {
            this.elements.weaponName.textContent = equippedWeapon?.name || 'Unarmed';
        }
        if (this.elements.weaponMastery) {
            const mastery = equippedWeapon?.mastery;
            if (mastery) {
                this.elements.weaponMastery.textContent = `(${mastery} mastery)`;
            } else {
                this.elements.weaponMastery.textContent = '';
            }
        }
    }

    /**
     * Update HP bar
     */
    updateHP(player) {
        const hp = player.hp || 0;
        const maxHp = player.maxHp || 1;
        const percent = Math.max(0, Math.min(100, (hp / maxHp) * 100));

        if (this.elements.hpBar) {
            this.elements.hpBar.style.width = `${percent}%`;

            // Update color class
            this.elements.hpBar.classList.remove('mid', 'low');
            if (percent <= 25) {
                this.elements.hpBar.classList.add('low');
            } else if (percent <= 50) {
                this.elements.hpBar.classList.add('mid');
            }
        }

        if (this.elements.hpText) {
            this.elements.hpText.textContent = `${hp} / ${maxHp}`;
        }
    }

    /**
     * Update movement remaining
     */
    updateMovement(gameState) {
        if (this.elements.movementRemaining) {
            const remaining = gameState.turn?.movementRemaining ?? 30;
            this.elements.movementRemaining.textContent = `${remaining} ft`;
        }
    }

    /**
     * Update conditions list
     */
    updateConditions(player) {
        if (!this.elements.conditionsList) return;

        const conditions = player.conditions || [];

        if (conditions.length === 0) {
            this.elements.conditionsList.innerHTML = '<span class="no-conditions">None</span>';
        } else {
            this.elements.conditionsList.innerHTML = conditions
                .map(c => `<span class="condition-tag">${c}</span>`)
                .join('');
        }
    }

    /**
     * Update enemy list
     */
    updateEnemyList(gameState) {
        if (!this.elements.enemyList) return;

        const enemies = Object.values(gameState.combatants)
            .filter(c => c.type === 'enemy' && c.isActive);

        if (enemies.length === 0) {
            this.elements.enemyList.innerHTML = '<li class="enemy-item"><span class="text-muted">No enemies</span></li>';
        } else {
            this.elements.enemyList.innerHTML = enemies
                .map(e => `
                    <li class="enemy-item">
                        <span class="enemy-name">${e.name}</span>
                        <span class="enemy-hp">${e.hp}/${e.maxHp}</span>
                    </li>
                `)
                .join('');
        }
    }

    /**
     * Set the player's combatant ID
     * Updates playerIds array for multi-character support
     */
    setPlayerId(id) {
        const currentPlayerIds = state.get('playerIds') || [];
        if (!currentPlayerIds.includes(id)) {
            state.set('playerIds', [...currentPlayerIds, id]);
        }
    }

    /**
     * Update death saves display
     */
    updateDeathSaves(player, gameState) {
        if (!this.elements.deathSavesBlock) return;

        const hp = player.hp || 0;
        const isUnconscious = hp <= 0;

        // Show/hide death saves block based on HP
        if (isUnconscious) {
            this.elements.deathSavesBlock.style.display = 'block';

            // Get death save counts from player state
            const deathSaves = player.death_saves || player.deathSaves || { successes: 0, failures: 0 };
            const successes = deathSaves.successes || 0;
            const failures = deathSaves.failures || 0;

            // Update success icons
            if (this.elements.deathSaveSuccesses) {
                const successIcons = this.elements.deathSaveSuccesses.querySelectorAll('.death-save-icon');
                successIcons.forEach((icon, index) => {
                    if (index < successes) {
                        icon.classList.add('filled');
                        icon.innerHTML = '&#9829;'; // Filled heart
                    } else {
                        icon.classList.remove('filled');
                        icon.innerHTML = '&#9825;'; // Empty heart
                    }
                });
            }

            // Update failure icons
            if (this.elements.deathSaveFailures) {
                const failureIcons = this.elements.deathSaveFailures.querySelectorAll('.death-save-icon');
                failureIcons.forEach((icon, index) => {
                    if (index < failures) {
                        icon.classList.add('filled');
                    } else {
                        icon.classList.remove('filled');
                    }
                });
            }

            // Enable/disable roll button based on turn
            const isPlayerTurn = state.isPlayerTurn();
            const currentCombatant = state.getCurrentCombatant();
            const isThisPlayerTurn = isPlayerTurn && currentCombatant?.id === gameState.playerId;

            if (this.elements.btnRollDeathSave) {
                this.elements.btnRollDeathSave.disabled = !isThisPlayerTurn;

                if (successes >= 3) {
                    this.elements.btnRollDeathSave.disabled = true;
                    this.elements.btnRollDeathSave.querySelector('.btn-text').textContent = 'Stabilized!';
                } else if (failures >= 3) {
                    this.elements.btnRollDeathSave.disabled = true;
                    this.elements.btnRollDeathSave.querySelector('.btn-text').textContent = 'Dead';
                } else {
                    this.elements.btnRollDeathSave.querySelector('.btn-text').textContent = 'Roll Death Save';
                }
            }
        } else {
            this.elements.deathSavesBlock.style.display = 'none';
        }
    }

    /**
     * Roll a death saving throw
     */
    async rollDeathSave() {
        const gameState = state.getState();
        const combatId = gameState.combat?.id;
        const playerId = gameState.playerId;

        if (!combatId || !playerId) {
            console.error('[CharacterPanel] Cannot roll death save: missing combat or player ID');
            return;
        }

        try {
            // Disable button while rolling
            if (this.elements.btnRollDeathSave) {
                this.elements.btnRollDeathSave.disabled = true;
                this.elements.btnRollDeathSave.querySelector('.btn-text').textContent = 'Rolling...';
            }

            const response = await api.rollDeathSave(combatId, playerId);

            if (response.success) {
                // Log the result
                const roll = response.roll || response.result?.roll || 0;
                const isSuccess = response.is_success || response.result?.is_success || roll >= 10;
                const isCritical = roll === 1 || roll === 20;

                let message = `Death Save: ${roll}`;
                if (roll === 20) {
                    message += ' - NATURAL 20! Regained 1 HP!';
                } else if (roll === 1) {
                    message += ' - NATURAL 1! Two failures!';
                } else if (isSuccess) {
                    message += ' - Success!';
                } else {
                    message += ' - Failure!';
                }

                eventBus.emit(EVENTS.UI_LOG_ENTRY, {
                    type: isCritical ? (roll === 20 ? 'critical' : 'fumble') : (isSuccess ? 'success' : 'failure'),
                    message: message
                });

                // Update combat state if provided
                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                // If natural 20, player regains 1 HP and is no longer dying
                if (roll === 20) {
                    eventBus.emit(EVENTS.UI_NOTIFICATION, {
                        type: 'success',
                        message: 'Natural 20! You regain consciousness with 1 HP!'
                    });
                }

                // If 3 failures, player dies
                if (response.is_dead || response.result?.is_dead) {
                    eventBus.emit(EVENTS.UI_NOTIFICATION, {
                        type: 'error',
                        message: 'You have died...'
                    });
                    eventBus.emit(EVENTS.COMBATANT_DEFEATED, { combatantId: playerId });
                }

                // If 3 successes, player stabilizes
                if (response.is_stable || response.result?.is_stable) {
                    eventBus.emit(EVENTS.UI_NOTIFICATION, {
                        type: 'success',
                        message: 'You have stabilized!'
                    });
                }
            } else {
                eventBus.emit(EVENTS.UI_NOTIFICATION, {
                    type: 'error',
                    message: response.description || 'Failed to roll death save'
                });
            }
        } catch (error) {
            console.error('[CharacterPanel] Death save error:', error);
            eventBus.emit(EVENTS.UI_NOTIFICATION, {
                type: 'error',
                message: 'Failed to roll death save'
            });
        }
    }
}

export default CharacterPanel;
