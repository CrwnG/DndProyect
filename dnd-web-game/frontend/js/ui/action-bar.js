/**
 * D&D Combat Engine - Action Bar
 * Handles action button clicks and action execution
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state, { GameMode } from '../engine/state-manager.js';
import api from '../api/api-client.js';
import TargetingSystem from '../combat/targeting-system.js';
import { diceRoller } from './dice-roller.js';
import spellModal from './spell-modal.js';
import divineSmiteModal from './divine-smite-modal.js';
import { toast } from './toast-notification.js';

/**
 * Escape HTML special characters to prevent XSS
 * @param {string} str - String to escape
 * @returns {string} Escaped string safe for innerHTML
 */
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

class ActionBar {
    constructor() {
        this.targetingSystem = new TargetingSystem();

        // Action buttons
        this.buttons = {
            attack: document.getElementById('btn-attack'),
            spell: document.getElementById('btn-spell'),
            dash: document.getElementById('btn-dash'),
            dodge: document.getElementById('btn-dodge'),
            disengage: document.getElementById('btn-disengage'),
            ready: document.getElementById('btn-ready'),
            // Additional standard actions
            help: document.getElementById('btn-help'),
            hide: document.getElementById('btn-hide'),
            grapple: document.getElementById('btn-grapple'),
            shove: document.getElementById('btn-shove'),
            // Bonus action buttons
            useItem: document.getElementById('btn-use-item'),
            secondWind: document.getElementById('btn-second-wind'),
            offhand: document.getElementById('btn-offhand'),
            // Class feature buttons
            actionSurge: document.getElementById('btn-action-surge'),
            rage: document.getElementById('btn-rage'),
            wildShape: document.getElementById('btn-wild-shape'),
            layOnHands: document.getElementById('btn-lay-on-hands'),
            cunningAction: document.getElementById('btn-cunning-action'),
            kiPowers: document.getElementById('btn-ki-powers'),
            recklessAttack: document.getElementById('btn-reckless-attack'),
            channelDivinity: document.getElementById('btn-channel-divinity'),
            bardicInspiration: document.getElementById('btn-bardic-inspiration'),
            metamagic: document.getElementById('btn-metamagic'),
            // Ranger feature buttons
            huntersMark: document.getElementById('btn-hunters-mark'),
            favoredFoe: document.getElementById('btn-favored-foe'),
            // Warlock feature buttons
            eldritchBlast: document.getElementById('btn-eldritch-blast'),
            invocations: document.getElementById('btn-invocations'),
            hex: document.getElementById('btn-hex'),
            // Rest buttons
            shortRest: document.getElementById('btn-short-rest'),
            longRest: document.getElementById('btn-long-rest'),
            // Other buttons
            threatZones: document.getElementById('btn-threat-zones'),
            move: document.getElementById('btn-move'),
            endTurn: document.getElementById('btn-end-turn'),
        };

        this.setupEventListeners();
        this.subscribeToState();
    }

    /**
     * Set up button click handlers
     */
    setupEventListeners() {
        // Action buttons
        this.buttons.attack?.addEventListener('click', () => this.handleAttack());
        this.buttons.spell?.addEventListener('click', () => this.handleSpell());
        this.buttons.dash?.addEventListener('click', () => this.handleDash());
        this.buttons.dodge?.addEventListener('click', () => this.handleDodge());
        this.buttons.disengage?.addEventListener('click', () => this.handleDisengage());
        this.buttons.ready?.addEventListener('click', () => this.handleReady());

        // Additional standard actions
        this.buttons.help?.addEventListener('click', () => this.handleHelp());
        this.buttons.hide?.addEventListener('click', () => this.handleHide());
        this.buttons.grapple?.addEventListener('click', () => this.handleGrapple());
        this.buttons.shove?.addEventListener('click', () => this.handleShove());

        // Bonus action buttons
        this.buttons.useItem?.addEventListener('click', () => this.handleUseItem());
        this.buttons.secondWind?.addEventListener('click', () => this.handleSecondWind());
        this.buttons.offhand?.addEventListener('click', () => this.handleOffhandAttack());

        // Class feature buttons
        this.buttons.actionSurge?.addEventListener('click', () => this.handleActionSurge());
        this.buttons.rage?.addEventListener('click', () => this.handleRage());
        this.buttons.wildShape?.addEventListener('click', () => this.handleWildShape());
        this.buttons.layOnHands?.addEventListener('click', () => this.handleLayOnHands());
        this.buttons.cunningAction?.addEventListener('click', () => this.handleCunningAction());
        this.buttons.kiPowers?.addEventListener('click', () => this.handleKiPowers());
        this.buttons.recklessAttack?.addEventListener('click', () => this.handleRecklessAttack());
        this.buttons.channelDivinity?.addEventListener('click', () => this.handleChannelDivinity());
        this.buttons.bardicInspiration?.addEventListener('click', () => this.handleBardicInspiration());
        this.buttons.metamagic?.addEventListener('click', () => this.handleMetamagic());

        // Ranger feature buttons
        this.buttons.huntersMark?.addEventListener('click', () => this.handleHuntersMark());
        this.buttons.favoredFoe?.addEventListener('click', () => this.handleFavoredFoe());

        // Warlock feature buttons
        this.buttons.eldritchBlast?.addEventListener('click', () => this.handleEldritchBlast());
        this.buttons.invocations?.addEventListener('click', () => this.handleInvocations());
        this.buttons.hex?.addEventListener('click', () => this.handleHex());

        // Rest buttons
        this.buttons.shortRest?.addEventListener('click', () => this.handleShortRest());
        this.buttons.longRest?.addEventListener('click', () => this.handleLongRest());

        // Threat zones toggle button
        this.buttons.threatZones?.addEventListener('click', () => this.handleThreatZoneToggle());

        // Move button
        this.buttons.move?.addEventListener('click', () => this.handleMove());

        // End turn
        this.buttons.endTurn?.addEventListener('click', () => this.handleEndTurn());

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
    }

    /**
     * Subscribe to state changes
     */
    subscribeToState() {
        state.subscribe((newState) => {
            this.updateButtonStates(newState);
        });
    }

    /**
     * Update button enabled/disabled states
     */
    updateButtonStates(gameState) {
        const isPlayerTurn = state.isPlayerTurn();
        const turn = gameState.turn;
        const mode = gameState.mode;

        // Disable all if not player's turn or in targeting mode
        const canAct = isPlayerTurn && mode === GameMode.COMBAT;
        // Extra Attack: Check attacks remaining AND actionUsed (Dash/Dodge consume action)
        const attacksRemaining = turn.attacksRemaining ?? 1;
        const canAttack = canAct && attacksRemaining > 0 && !turn.actionUsed;
        const canUseAction = canAct && !turn.actionUsed;
        const canUseBonusAction = canAct && !turn.bonusActionUsed;

        // Get player data for feature checks
        const player = gameState.combatants[gameState.playerId];

        // Update action buttons
        this.setButtonEnabled(this.buttons.attack, canAttack);
        // Spell button: enabled if player has spells and can use action (or has cantrips for bonus actions)
        const canCastSpell = canUseAction && this.playerHasSpells(player);
        this.setButtonEnabled(this.buttons.spell, canCastSpell);
        this.setButtonEnabled(this.buttons.dash, canUseAction);
        this.setButtonEnabled(this.buttons.dodge, canUseAction);
        this.setButtonEnabled(this.buttons.disengage, canUseAction);
        this.setButtonEnabled(this.buttons.ready, canUseAction);

        // Standard actions that use the action
        this.setButtonEnabled(this.buttons.help, canUseAction);
        this.setButtonEnabled(this.buttons.hide, canUseAction);

        // Grapple/Shove replace one attack (like Extra Attack)
        this.setButtonEnabled(this.buttons.grapple, canAttack);
        this.setButtonEnabled(this.buttons.shove, canAttack);

        // Update attack button text for Extra Attack
        if (this.buttons.attack) {
            const maxAttacks = turn.maxAttacks || 1;
            const attackLabel = this.buttons.attack.querySelector('.action-label');
            if (attackLabel && maxAttacks > 1) {
                attackLabel.textContent = `Attack (${attacksRemaining}/${maxAttacks})`;
            } else if (attackLabel) {
                attackLabel.textContent = 'Attack';
            }
        }

        // Update bonus action buttons
        // Use Item: Available if bonus action not used (for potions, scrolls, etc.)
        const hasConsumables = player?.inventory?.some(item =>
            item.type === 'consumable' || item.item_type === 'consumable'
        );
        this.setButtonEnabled(this.buttons.useItem, canUseBonusAction && hasConsumables);

        // Second Wind: Fighter only, once per short rest
        const canSecondWind = canUseBonusAction && player?.stats?.class?.toLowerCase() === 'fighter';
        this.setButtonEnabled(this.buttons.secondWind, canSecondWind);
        // Show/hide second wind based on class
        if (this.buttons.secondWind) {
            this.buttons.secondWind.style.display = player?.stats?.class?.toLowerCase() === 'fighter' ? 'flex' : 'none';
        }

        // Off-hand Attack: Available if attacked with light melee weapon this turn
        const canOffhandAttack = canUseBonusAction && turn.canOffhandAttack;
        this.setButtonEnabled(this.buttons.offhand, canOffhandAttack);
        // Show/hide off-hand button based on availability
        if (this.buttons.offhand) {
            this.buttons.offhand.style.display = turn.canOffhandAttack ? 'flex' : 'none';
        }

        // Class feature buttons - show/hide and enable based on class and level
        this.updateClassFeatureButtons(player, canAct, canUseBonusAction, turn);

        // Move button: available if there's movement remaining
        const canMove = isPlayerTurn && turn.movementRemaining > 0 && mode === GameMode.COMBAT;
        this.setButtonEnabled(this.buttons.move, canMove);

        // Update Move button selected state when movement mode is active
        if (this.buttons.move) {
            if (gameState.ui.movementModeActive) {
                this.buttons.move.classList.add('active');
            } else {
                this.buttons.move.classList.remove('active');
            }
        }

        // End turn always available on player's turn
        this.setButtonEnabled(this.buttons.endTurn, isPlayerTurn);

        // Update selected state
        this.updateSelectedAction(gameState.ui.selectedAction);

        // Update action economy bar
        this.updateActionEconomyBar(gameState, isPlayerTurn);
    }

    /**
     * Update the action economy status bar
     */
    updateActionEconomyBar(gameState, isPlayerTurn) {
        const turn = gameState.turn;

        // Action resource
        const actionEl = document.getElementById('resource-action');
        if (actionEl) {
            if (!isPlayerTurn) {
                actionEl.className = 'resource';
                actionEl.textContent = 'Not Your Turn';
            } else if (turn.actionUsed) {
                actionEl.className = 'resource used';
                actionEl.textContent = 'Action Used';
            } else {
                actionEl.className = 'resource available';
                actionEl.textContent = 'Action';
            }
        }

        // Bonus Action resource
        const bonusEl = document.getElementById('resource-bonus');
        if (bonusEl) {
            if (!isPlayerTurn) {
                bonusEl.className = 'resource';
                bonusEl.textContent = 'Bonus';
            } else if (turn.bonusActionUsed) {
                bonusEl.className = 'resource used';
                bonusEl.textContent = 'Bonus Used';
            } else {
                bonusEl.className = 'resource available';
                bonusEl.textContent = 'Bonus';
            }
        }

        // Reaction resource
        const reactionEl = document.getElementById('resource-reaction');
        if (reactionEl) {
            if (turn.reactionUsed) {
                reactionEl.className = 'resource used';
                reactionEl.textContent = 'Reaction Used';
            } else {
                reactionEl.className = 'resource available';
                reactionEl.textContent = 'Reaction';
            }
        }

        // Movement resource
        const movementEl = document.getElementById('resource-movement');
        if (movementEl) {
            const remaining = turn.movementRemaining || 0;
            movementEl.textContent = `${remaining} ft`;
            if (remaining === 0) {
                movementEl.className = 'resource used';
            } else {
                movementEl.className = 'resource movement';
            }
        }

        // Object Interaction resource (for weapon switching)
        const interactionEl = document.getElementById('resource-interaction');
        if (interactionEl) {
            if (turn.objectInteractionUsed) {
                interactionEl.className = 'resource-interaction used';
                interactionEl.textContent = 'Object Used';
            } else {
                interactionEl.className = 'resource-interaction available';
                interactionEl.textContent = 'Object';
            }
        }
    }

    /**
     * Set button enabled state
     */
    setButtonEnabled(button, enabled) {
        if (button) {
            button.disabled = !enabled;
        }
    }

    /**
     * Update which action is selected
     */
    updateSelectedAction(actionType) {
        Object.values(this.buttons).forEach(btn => {
            btn?.classList.remove('selected');
        });

        if (actionType && this.buttons[actionType]) {
            this.buttons[actionType].classList.add('selected');
        }
    }

    /**
     * Handle keyboard shortcuts
     */
    handleKeyboard(event) {
        if (!state.isPlayerTurn()) return;

        switch (event.key.toLowerCase()) {
            case 'a':
                this.handleAttack();
                break;
            case 's':
                this.handleSpell();
                break;
            case 'd':
                if (event.shiftKey) {
                    this.handleDisengage();
                } else {
                    this.handleDash();
                }
                break;
            case 'o':
                this.handleDodge();
                break;
            case 'r':
                this.handleReady();
                break;
            case 'm':
                this.handleMove();
                break;
            case 't':
                this.handleThreatZoneToggle();
                break;
            case 'e':
            case 'enter':
                this.handleEndTurn();
                break;
            case 'escape':
                this.cancelCurrentAction();
                // Also disable movement mode on ESC
                if (state.isMovementModeActive()) {
                    state.setMovementModeActive(false);
                }
                // Also close spell modal if open
                if (!spellModal.isHidden()) {
                    spellModal.hide();
                }
                break;
        }
    }

    /**
     * Cancel current action
     */
    cancelCurrentAction() {
        state.setSelectedAction(null);
        state.exitTargetingMode();
        this.hideWeaponSelection();
        this.selectedWeapon = null;
        eventBus.emit(EVENTS.ACTION_CANCELLED);
    }

    // ==================== Combat End Detection ====================

    /**
     * Check if combat has ended after an action (attack, spell, etc.)
     * Emits COMBAT_ENDED event if all enemies or all players are defeated.
     * @param {Object} response - API response that may contain combat_over flag
     * @returns {boolean} True if combat ended
     */
    checkCombatOver(response = {}) {
        // First check if backend explicitly says combat is over
        if (response.combat_over) {
            console.log('[ActionBar] Combat ended (from response):', response.combat_result);
            state.addLogEntry({
                type: 'combat_end',
                message: `Combat ended: ${response.combat_result || 'unknown outcome'}`,
            });
            eventBus.emit(EVENTS.COMBAT_ENDED, {
                result: response.combat_result,
            });
            return true;
        }

        // Otherwise check combat state - all enemies dead = victory, all players dead = defeat
        const gameState = state.getState();
        const combatants = gameState.combatants ? Object.values(gameState.combatants) : [];

        // Use correct field names: type='player'/'enemy', hp (not current_hp), isActive
        const isEnemy = (c) => c.type === 'enemy' || (!c.isPlayer && c.type !== 'player');
        const isPlayer = (c) => c.isPlayer || c.type === 'player';
        const isAlive = (c) => c.isActive && (c.hp > 0 || c.current_hp > 0);

        const activeEnemies = combatants.filter(c => isEnemy(c) && isAlive(c));
        const activePlayers = combatants.filter(c => isPlayer(c) && isAlive(c));
        const totalEnemies = combatants.filter(c => isEnemy(c));
        const totalPlayers = combatants.filter(c => isPlayer(c));

        console.log('[ActionBar] Combat state check:', {
            totalCombatants: combatants.length,
            activeEnemies: activeEnemies.length,
            activePlayers: activePlayers.length,
            totalEnemies: totalEnemies.length,
            totalPlayers: totalPlayers.length
        });

        if (activeEnemies.length === 0 && totalEnemies.length > 0) {
            // All enemies defeated = victory
            console.log('[ActionBar] Combat ended - all enemies defeated');
            state.addLogEntry({
                type: 'combat_end',
                message: 'Combat ended: victory',
            });
            eventBus.emit(EVENTS.COMBAT_ENDED, {
                result: 'victory',
            });
            return true;
        }

        if (activePlayers.length === 0 && totalPlayers.length > 0) {
            // All players defeated = defeat
            console.log('[ActionBar] Combat ended - all players defeated');
            state.addLogEntry({
                type: 'combat_end',
                message: 'Combat ended: defeat',
            });
            eventBus.emit(EVENTS.COMBAT_ENDED, {
                result: 'defeat',
            });
            return true;
        }

        return false;
    }

    // ==================== Action Handlers ====================

    /**
     * Handle Attack action - show weapon selection first
     */
    async handleAttack() {
        // Check attacksRemaining instead of actionUsed for Extra Attack support
        const turn = state.getState().turn;
        const attacksRemaining = turn.attacksRemaining ?? (turn.actionUsed ? 0 : 1);
        if (!state.isPlayerTurn() || attacksRemaining <= 0) return;

        state.setSelectedAction('attack');

        // Get available weapons for the player
        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const weapons = this.getPlayerWeapons(player);

        if (weapons.length <= 1) {
            // Only one weapon (or none) - skip selection
            this.selectedWeapon = weapons[0] || null;
            this.startTargetingWithWeapon(this.selectedWeapon);
        } else {
            // Show weapon selection modal
            this.showWeaponSelection(weapons);
        }
    }

    /**
     * Get available weapons for a player using BG3-style equipment system.
     * Shows equipped weapons (instant use) and inventory weapons (require object interaction).
     * @param {Object} player - Player combatant data
     * @returns {Array} Array of weapon objects with status indicators
     */
    getPlayerWeapons(player) {
        const equipment = player?.equipment;
        const gameState = state.getState();
        const turn = gameState.turn || {};

        // If no equipment system, fall back to legacy
        if (!equipment) {
            return this.getDefaultWeapons();
        }

        const weapons = [];

        // Currently equipped weapons (instant use, no cost)
        if (equipment.main_hand && equipment.main_hand.damage) {
            weapons.push({
                ...equipment.main_hand,
                type: equipment.main_hand.damage_type,
                status: 'equipped',
                slot: 'main_hand'
            });
        }

        if (equipment.off_hand && equipment.off_hand.damage) {
            weapons.push({
                ...equipment.off_hand,
                type: equipment.off_hand.damage_type,
                status: 'equipped',
                slot: 'off_hand'
            });
        }

        if (equipment.ranged && equipment.ranged.damage) {
            weapons.push({
                ...equipment.ranged,
                type: equipment.ranged.damage_type,
                status: 'equipped',
                slot: 'ranged',
                isRanged: true
            });
        }

        // Check if object interaction is available for weapon switching
        const canSwitch = !turn.objectInteractionUsed;

        // Inventory weapons (require object interaction to draw)
        if (canSwitch && equipment.inventory) {
            for (const item of equipment.inventory) {
                if (item.damage) {
                    weapons.push({
                        ...item,
                        type: item.damage_type,
                        status: 'inventory',
                        switchCost: true
                    });
                }
            }
        }

        // Always have unarmed strike available
        weapons.push({
            id: 'unarmed',
            name: 'Unarmed Strike',
            damage: '1 + STR',
            type: 'bludgeoning',
            range: 5,
            properties: [],
            icon: '✊',
            status: 'always'
        });

        return weapons;
    }

    /**
     * Get default weapons when no equipment system is present (legacy fallback)
     * @returns {Array} Array of default weapon objects
     */
    getDefaultWeapons() {
        return [
            {
                id: 'longsword',
                name: 'Longsword',
                damage: '1d8',
                type: 'slashing',
                range: 5,
                properties: ['versatile'],
                icon: '⚔️',
                status: 'equipped'
            },
            {
                id: 'unarmed',
                name: 'Unarmed Strike',
                damage: '1 + STR',
                type: 'bludgeoning',
                range: 5,
                properties: [],
                icon: '✊',
                status: 'always'
            }
        ];
    }

    /**
     * Get light weapons for off-hand attack
     * @param {Object} player - Player combatant data
     * @returns {Array} Array of light weapon objects
     */
    getLightWeapons(player) {
        const allWeapons = this.getPlayerWeapons(player);
        return allWeapons.filter(w =>
            w.properties?.includes('light') &&
            !w.properties?.includes('ammunition')
        );
    }

    /**
     * Show weapon selection modal with BG3-style equipment status badges.
     * @param {Array} weapons - Available weapons
     * @param {boolean} isOffhand - Whether this is for off-hand attack
     */
    showWeaponSelection(weapons, isOffhand = false) {
        const modal = document.getElementById('weapon-select-modal');
        const grid = document.getElementById('weapon-grid');
        const closeBtn = document.getElementById('weapon-close-btn');
        const title = modal?.querySelector('h2');

        if (!modal || !grid) return;

        // Update title for off-hand
        if (title) {
            title.textContent = isOffhand ? 'Choose Off-Hand Weapon' : 'Choose Weapon';
        }

        // Clear existing content
        grid.innerHTML = '';

        // Create weapon cards
        weapons.forEach(weapon => {
            const card = document.createElement('div');
            const isRanged = weapon.isRanged || weapon.properties?.includes('ammunition');
            const isLight = weapon.properties?.includes('light');
            const statusClass = weapon.status || 'equipped';
            card.className = `weapon-card ${statusClass}${weapon.id === 'unarmed' ? ' unarmed' : ''}${weapon.thrown || isRanged ? ' ranged' : ''}${isLight ? ' light' : ''}`;

            // Build range display
            let rangeText = '';
            if (weapon.range && weapon.range > 5) {
                if (weapon.long_range || weapon.longRange) {
                    rangeText = `${weapon.range}/${weapon.long_range || weapon.longRange} ft`;
                } else {
                    rangeText = `${weapon.range} ft`;
                }
            }

            // Status badge based on equipment status
            let statusBadge = '';
            if (weapon.status === 'equipped') {
                statusBadge = '<span class="badge equipped">Equipped</span>';
            } else if (weapon.status === 'inventory') {
                statusBadge = '<span class="badge inventory">Draw</span>';
            }

            card.innerHTML = `
                <span class="weapon-icon">${escapeHtml(weapon.icon) || '⚔️'}</span>
                <span class="weapon-name">${escapeHtml(weapon.name)}</span>
                ${statusBadge}
                <span class="weapon-damage">${escapeHtml(weapon.damage)}</span>
                <span class="weapon-type">${escapeHtml(weapon.type)}</span>
                ${rangeText ? `<span class="weapon-range">${escapeHtml(rangeText)}</span>` : ''}
                ${weapon.mastery ? `<span class="weapon-mastery">${escapeHtml(weapon.mastery)}</span>` : ''}
                ${isLight ? `<span class="weapon-property">Light</span>` : ''}
            `;

            card.addEventListener('click', () => {
                this.selectedWeapon = weapon;

                // If drawing from inventory, mark object interaction as used AND swap equipment
                if (weapon.status === 'inventory') {
                    state.set('turn.objectInteractionUsed', true);
                    console.log('[ActionBar] Object interaction used to draw', weapon.name);

                    // Actually move weapon from inventory to main_hand slot
                    const gameState = state.getState();
                    const playerId = gameState.playerId;
                    const combatant = gameState.combatants[playerId];
                    if (combatant?.equipment) {
                        const equipment = JSON.parse(JSON.stringify(combatant.equipment)); // Deep copy

                        // Find and remove weapon from inventory
                        const weaponIndex = equipment.inventory.findIndex(w => w.id === weapon.id);
                        if (weaponIndex >= 0) {
                            const drawnWeapon = equipment.inventory.splice(weaponIndex, 1)[0];

                            // Put current main_hand into inventory (if any)
                            if (equipment.main_hand) {
                                equipment.inventory.push(equipment.main_hand);
                                console.log('[ActionBar] Stowed', equipment.main_hand.name, 'to inventory');
                            }

                            // Equip the drawn weapon
                            equipment.main_hand = drawnWeapon;
                            console.log('[ActionBar] Equipped', drawnWeapon.name, 'to main hand');

                            // Update state with new equipment
                            state.set(`combatants.${playerId}.equipment`, equipment);
                        }
                    }
                }

                this.hideWeaponSelection();
                if (isOffhand) {
                    this.startOffhandTargeting(weapon);
                } else {
                    this.startTargetingWithWeapon(weapon);
                }
            });

            grid.appendChild(card);
        });

        // Setup close button
        closeBtn?.addEventListener('click', () => {
            this.hideWeaponSelection();
            this.cancelCurrentAction();
        });

        // Show modal
        modal.classList.remove('hidden');
    }

    /**
     * Hide weapon selection modal
     */
    hideWeaponSelection() {
        const modal = document.getElementById('weapon-select-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
    }

    /**
     * Start targeting mode with selected weapon
     * @param {Object} weapon - Selected weapon
     */
    startTargetingWithWeapon(weapon) {
        // Determine if this is a ranged weapon based on properties or range
        const isRanged = weapon?.range > 5 ||
            weapon?.properties?.includes('ammunition') ||
            weapon?.properties?.includes('thrown');
        const rangeType = isRanged ? 'ranged' : 'melee';

        // Pass weapon to targeting system for range-based target filtering
        this.targetingSystem.startTargeting(rangeType, async (target) => {
            await this.executeAttack(target, weapon);
        }, weapon);
    }

    /**
     * Execute attack on target
     * @param {Object} target - Target combatant
     * @param {Object} weapon - Selected weapon (optional)
     */
    async executeAttack(target, weapon = null) {
        const gameState = state.getState();
        const combatId = gameState.combat.id;

        try {
            // Build request options
            const options = {};
            if (weapon) {
                // Use camelCase to match api-client.js performAction() expectation
                options.weaponName = weapon.id || weapon.name;
            }

            const response = await api.performAction(
                combatId,
                'attack',
                target.id,
                options
            );

            // Update state from response
            if (response.success) {
                // Play dice roll animation BEFORE updating combat state
                // This creates a dramatic reveal effect
                // Pass the API response directly - it now contains all needed fields
                console.log('[ActionBar] Attack response:', response);
                await diceRoller.playAttackSequence(response);

                // Update combat state after animation
                state.updateCombatState(response.combat_state || {});

                // Update Extra Attack tracking from response
                const extraData = response.extra_data || {};
                if (extraData.attacks_remaining !== undefined) {
                    state.set('turn.attacksRemaining', extraData.attacks_remaining);
                    state.set('turn.maxAttacks', extraData.max_attacks || 1);
                }
                // Update Two-Weapon Fighting tracking
                if (extraData.can_offhand_attack !== undefined) {
                    state.set('turn.canOffhandAttack', extraData.can_offhand_attack);
                }
                // Mark action as used only if all attacks are used
                if (extraData.attacks_remaining === 0) {
                    state.useAction();
                }

                // Log entry for the base attack
                state.addLogEntry({
                    type: response.hit ? 'hit' : 'miss',
                    actor: state.getState().combatants[gameState.playerId]?.name,
                    target: target.name,
                    damage: response.damage_dealt,
                    message: response.description,
                });

                // Check for Weapon Mastery effects (D&D 2024)
                if (extraData.weapon_mastery_applied) {
                    const masteryType = extraData.weapon_mastery_type;
                    const masteryDamage = extraData.weapon_mastery_extra_damage || 0;
                    const masteryMessage = this.getMasteryMessage(masteryType, masteryDamage, target.name);

                    state.addLogEntry({
                        type: 'mastery',
                        message: masteryMessage,
                    });
                }

                // Check for Divine Smite opportunity (Paladin, D&D 2024)
                // Divine Smite costs a bonus action in 2024 rules - check it's available
                const currentTurn = state.getState().turn;
                if (response.hit && extraData.can_divine_smite && !currentTurn.bonusActionUsed) {
                    try {
                        // Add target info for the modal
                        response.target_name = target.name;

                        const smiteChoice = await divineSmiteModal.show(response);

                        if (smiteChoice.use && smiteChoice.slotLevel) {
                            // Apply Divine Smite via API
                            const smiteResult = await api.applyDivineSmite(
                                combatId,
                                smiteChoice.slotLevel,
                                target.id
                            );

                            if (smiteResult.success) {
                                // Update state with smite damage
                                state.updateCombatState(smiteResult.combat_state || {});

                                // D&D 2024: Divine Smite costs a bonus action
                                state.useBonusAction();

                                // Log the Divine Smite
                                state.addLogEntry({
                                    type: 'divine_smite',
                                    message: `Divine Smite deals ${smiteResult.damage_dealt} FORCE damage!`,
                                });
                            }
                        }
                    } catch (smiteError) {
                        console.error('[ActionBar] Divine Smite failed:', smiteError);
                        toast.error('Divine Smite failed');
                    }
                }

                // Emit attack resolved with target_id for animations
                eventBus.emit(EVENTS.ATTACK_RESOLVED, {
                    ...response,
                    target_id: target.id,
                    target_name: target.name,
                });

                // Check if combat ended after this attack
                this.checkCombatOver(response);
            } else {
                state.addLogEntry({
                    type: 'error',
                    message: response.description || 'Attack failed',
                });
            }
        } catch (error) {
            console.error('[ActionBar] Attack failed:', error);
            toast.error('Attack failed: ' + error.message);
            state.addLogEntry({
                type: 'error',
                message: 'Attack failed: ' + error.message,
            });
        }

        state.setSelectedAction(null);
    }

    /**
     * Show attack result modal
     */
    showAttackResult(result) {
        const modal = document.getElementById('result-modal');
        const title = document.getElementById('result-title');
        const details = document.getElementById('result-details');

        if (!modal || !details) return;

        const isHit = result.hit;
        const isCrit = result.critical;

        title.textContent = isCrit ? 'Critical Hit!' : isHit ? 'Hit!' : 'Miss!';
        title.className = isCrit ? 'text-gold' : isHit ? 'text-green' : 'text-red';

        details.innerHTML = `
            <div class="result-row">
                <span class="result-label">Attack Roll:</span>
                <span class="result-value">${escapeHtml(result.attack_roll) || '?'}</span>
            </div>
            <div class="result-row">
                <span class="result-label">vs AC:</span>
                <span class="result-value">${escapeHtml(result.target_ac) || '?'}</span>
            </div>
            ${isHit ? `
                <div class="result-row">
                    <span class="result-label">Damage:</span>
                    <span class="result-value ${isCrit ? 'crit' : 'hit'}">${escapeHtml(result.damage) || 0} ${escapeHtml(result.damage_type) || ''}</span>
                </div>
            ` : ''}
            ${result.mastery_effect ? `
                <div class="result-row">
                    <span class="result-label">Mastery:</span>
                    <span class="result-value text-purple">${escapeHtml(result.mastery_effect)}</span>
                </div>
            ` : ''}
        `;

        modal.classList.remove('hidden');

        // Set up continue button
        const continueBtn = document.getElementById('result-continue');
        if (continueBtn) {
            continueBtn.onclick = () => modal.classList.add('hidden');
        }
    }

    /**
     * Get a descriptive message for weapon mastery effects (D&D 2024)
     * @param {string} masteryType - Type of mastery (graze, push, vex, etc.)
     * @param {number} damage - Extra damage dealt (for graze)
     * @param {string} targetName - Name of the target
     * @returns {string} Formatted message
     */
    getMasteryMessage(masteryType, damage, targetName) {
        const messages = {
            graze: `Graze! ${damage} damage dealt despite missing`,
            push: `${targetName} pushed 10ft back!`,
            vex: `Vex applied - advantage on next attack vs ${targetName}`,
            topple: `${targetName} knocked prone!`,
            sap: `${targetName} sapped - disadvantage on their next attack`,
            slow: `${targetName} slowed - speed reduced by 10ft`,
            cleave: `Cleave! Additional target struck`,
            nick: `Nick allows bonus action attack`,
        };

        return messages[masteryType?.toLowerCase()] || `Weapon Mastery: ${masteryType}`;
    }

    /**
     * Handle Spell action - show spell selection modal
     */
    async handleSpell() {
        if (!state.isPlayerTurn() || state.getState().turn.actionUsed) return;

        state.setSelectedAction('spell');

        // Show spell modal and wait for selection
        spellModal.show(async (selection) => {
            if (!selection || !selection.spell) {
                state.setSelectedAction(null);
                return;
            }

            const { spell, slotLevel } = selection;
            console.log('[ActionBar] Spell selected:', spell.name, 'at level', slotLevel);

            // Determine if spell needs targeting
            if (spell.target_type === 'self') {
                // Self-targeting spell - cast immediately
                await this.executeSpell(spell, slotLevel, [state.getState().playerId]);
            } else if (spell.target_type === 'single' || spell.target_type === 'touch') {
                // Single target spell - enter targeting mode
                this.startSpellTargeting(spell, slotLevel);
            } else if (['sphere', 'cone', 'line', 'cube', 'cylinder'].includes(spell.target_type)) {
                // Area spell - need to select a point
                this.startAreaSpellTargeting(spell, slotLevel);
            } else {
                // Default: try single target
                this.startSpellTargeting(spell, slotLevel);
            }
        });
    }

    /**
     * Check if player has any spells available
     * @param {Object} player - Player combatant data
     * @returns {boolean} True if player has spells
     */
    playerHasSpells(player) {
        if (!player) return false;

        // Priority 1: Check actual spellcasting data from backend
        if (player.spellcasting) {
            const sc = player.spellcasting;

            // Has cantrips (always castable)
            if (sc.cantrips_known?.length > 0) return true;

            // Has prepared or known spells
            if (sc.prepared_spells?.length > 0) return true;
            if (sc.spells_known?.length > 0) return true;

            // Has available spell slots
            if (sc.spell_slots) {
                for (const [level, maxSlots] of Object.entries(sc.spell_slots)) {
                    const used = sc.spell_slots_used?.[level] || 0;
                    if (maxSlots - used > 0) return true;
                }
            }
        }

        // Priority 2: Fallback to class check (enables button while loading spells)
        const spellcastingClasses = [
            'wizard', 'cleric', 'druid', 'paladin', 'bard',
            'sorcerer', 'warlock', 'ranger', 'artificer'
        ];
        // Check multiple locations for class (stats, abilities, or direct)
        const playerClass = (
            player.stats?.class ||
            player.abilities?.class ||
            player.character_class ||
            ''
        ).toLowerCase();

        if (spellcastingClasses.includes(playerClass)) {
            return true;
        }

        return false;
    }

    /**
     * Start targeting mode for a spell
     * @param {Object} spell - The spell to cast
     * @param {number} slotLevel - The slot level to use
     */
    startSpellTargeting(spell, slotLevel) {
        // Determine range type based on spell range
        let rangeType = 'melee';
        const rangeFt = this.parseSpellRange(spell.range);

        if (rangeFt > 5) {
            rangeType = 'ranged';
        }

        // Start targeting with spell info
        this.targetingSystem.startTargeting(rangeType, async (target) => {
            await this.executeSpell(spell, slotLevel, [target.id]);
        }, { range: rangeFt, spell: spell });
    }

    /**
     * Start targeting mode for area spells
     * @param {Object} spell - The spell to cast
     * @param {number} slotLevel - The slot level to use
     */
    startAreaSpellTargeting(spell, slotLevel) {
        const range = this.parseSpellRange(spell.range);
        const areaSize = this.parseAreaSize(spell);
        const areaType = spell.target_type || 'sphere';

        console.log('[ActionBar] Starting area spell targeting:', {
            spell: spell.name,
            range,
            areaSize,
            areaType
        });

        // Enter area targeting mode
        state.enterAreaTargetingMode(spell, slotLevel, areaType, areaSize, range);

        // Set up hover listener for area preview
        this._areaHoverListener = (cell) => {
            if (cell) {
                const previewCells = this.calculateAreaCells(cell.x, cell.y, areaType, areaSize);
                state.updateAreaPreview(previewCells);
            }
        };
        eventBus.on(EVENTS.CELL_HOVERED, this._areaHoverListener);

        // Set up click listener for area selection
        this._areaClickListener = (cell) => {
            const gameState = state.getState();
            if (gameState.mode !== GameMode.AREA_TARGETING) return;

            // Get all targets in the area
            const areaCells = this.calculateAreaCells(cell.x, cell.y, areaType, areaSize);
            const targetIds = this.getTargetsInArea(areaCells);

            console.log('[ActionBar] Area spell targets:', targetIds);

            // Clean up listeners
            this.cleanupAreaTargeting();

            // Execute the spell with area targets
            this.executeSpell(spell, slotLevel, targetIds, { x: cell.x, y: cell.y });
        };
        eventBus.on(EVENTS.CELL_CLICKED, this._areaClickListener);

        // Set up cancel handler
        this._areaCancelListener = () => {
            this.cleanupAreaTargeting();
        };
        eventBus.on(EVENTS.TARGETING_CANCELLED, this._areaCancelListener);

        // Show targeting modal
        this.showAreaTargetingModal(spell, areaType, areaSize);
    }

    /**
     * Clean up area targeting event listeners
     */
    cleanupAreaTargeting() {
        if (this._areaHoverListener) {
            eventBus.off(EVENTS.CELL_HOVERED, this._areaHoverListener);
            this._areaHoverListener = null;
        }
        if (this._areaClickListener) {
            eventBus.off(EVENTS.CELL_CLICKED, this._areaClickListener);
            this._areaClickListener = null;
        }
        if (this._areaCancelListener) {
            eventBus.off(EVENTS.TARGETING_CANCELLED, this._areaCancelListener);
            this._areaCancelListener = null;
        }
        state.exitAreaTargetingMode();
        this.hideAreaTargetingModal();
    }

    /**
     * Parse area size from spell data
     * @param {Object} spell - Spell object
     * @returns {number} Area radius in grid cells (1 cell = 5 feet)
     */
    parseAreaSize(spell) {
        // Try to get from spell properties
        if (spell.area_size) return Math.ceil(spell.area_size / 5);
        if (spell.radius) return Math.ceil(spell.radius / 5);

        // Parse from description or default by spell type
        const desc = (spell.description || '').toLowerCase();

        // Common area spell patterns
        if (desc.includes('20-foot radius')) return 4;
        if (desc.includes('15-foot radius')) return 3;
        if (desc.includes('10-foot radius')) return 2;
        if (desc.includes('5-foot radius')) return 1;
        if (desc.includes('30-foot cone')) return 6;
        if (desc.includes('15-foot cone')) return 3;
        if (desc.includes('60-foot line')) return 12;
        if (desc.includes('30-foot line')) return 6;

        // Default based on spell type
        switch (spell.target_type) {
            case 'cone': return 3;
            case 'line': return 6;
            case 'cube': return 2;
            case 'cylinder': return 2;
            default: return 2; // 10-foot radius sphere
        }
    }

    /**
     * Calculate grid cells affected by area
     * @param {number} centerX - Center X coordinate
     * @param {number} centerY - Center Y coordinate
     * @param {string} shape - Area shape
     * @param {number} radius - Radius in grid cells
     * @returns {Array} Array of {x, y} cells
     */
    calculateAreaCells(centerX, centerY, shape, radius) {
        const cells = [];
        const gridSize = 8; // Assume 8x8 grid

        switch (shape) {
            case 'sphere':
            case 'cylinder':
                // Circular area
                for (let dy = -radius; dy <= radius; dy++) {
                    for (let dx = -radius; dx <= radius; dx++) {
                        const distance = Math.sqrt(dx * dx + dy * dy);
                        if (distance <= radius) {
                            const x = centerX + dx;
                            const y = centerY + dy;
                            if (x >= 0 && x < gridSize && y >= 0 && y < gridSize) {
                                cells.push({ x, y });
                            }
                        }
                    }
                }
                break;

            case 'cube':
                // Square area
                for (let dy = -radius; dy <= radius; dy++) {
                    for (let dx = -radius; dx <= radius; dx++) {
                        const x = centerX + dx;
                        const y = centerY + dy;
                        if (x >= 0 && x < gridSize && y >= 0 && y < gridSize) {
                            cells.push({ x, y });
                        }
                    }
                }
                break;

            case 'cone':
                // Cone shape (simplified - emanates in direction from caster)
                const gameState = state.getState();
                const casterPos = gameState.grid.positions[gameState.playerId];
                if (casterPos) {
                    const dx = centerX - casterPos.x;
                    const dy = centerY - casterPos.y;
                    const angle = Math.atan2(dy, dx);

                    for (let r = 1; r <= radius; r++) {
                        const spread = Math.ceil(r / 2);
                        for (let s = -spread; s <= spread; s++) {
                            const x = Math.round(casterPos.x + r * Math.cos(angle) + s * Math.sin(angle));
                            const y = Math.round(casterPos.y + r * Math.sin(angle) - s * Math.cos(angle));
                            if (x >= 0 && x < gridSize && y >= 0 && y < gridSize) {
                                cells.push({ x, y });
                            }
                        }
                    }
                }
                break;

            case 'line':
                // Line from caster through target point
                const gs = state.getState();
                const caster = gs.grid.positions[gs.playerId];
                if (caster) {
                    const ddx = centerX - caster.x;
                    const ddy = centerY - caster.y;
                    const length = Math.sqrt(ddx * ddx + ddy * ddy);
                    if (length > 0) {
                        const stepX = ddx / length;
                        const stepY = ddy / length;
                        for (let i = 1; i <= radius && i <= length + radius; i++) {
                            const x = Math.round(caster.x + i * stepX);
                            const y = Math.round(caster.y + i * stepY);
                            if (x >= 0 && x < gridSize && y >= 0 && y < gridSize) {
                                if (!cells.some(c => c.x === x && c.y === y)) {
                                    cells.push({ x, y });
                                }
                            }
                        }
                    }
                }
                break;

            default:
                // Default to single cell
                cells.push({ x: centerX, y: centerY });
        }

        return cells;
    }

    /**
     * Get combatant IDs in area cells
     * @param {Array} areaCells - Array of {x, y} cells
     * @returns {Array} Array of combatant IDs in the area
     */
    getTargetsInArea(areaCells) {
        const gameState = state.getState();
        const positions = gameState.grid.positions || {};
        const combatants = gameState.combatants || {};
        const targetIds = [];

        // Build position lookup
        const positionMap = {};
        for (const [id, pos] of Object.entries(positions)) {
            const key = `${pos.x},${pos.y}`;
            if (!positionMap[key]) positionMap[key] = [];
            positionMap[key].push(id);
        }

        // Find all combatants in area cells
        for (const cell of areaCells) {
            const key = `${cell.x},${cell.y}`;
            const idsAtCell = positionMap[key] || [];
            for (const id of idsAtCell) {
                const combatant = combatants[id];
                // Include enemies (and optionally allies for some spells)
                if (combatant && combatant.isActive && combatant.type === 'enemy') {
                    if (!targetIds.includes(id)) {
                        targetIds.push(id);
                    }
                }
            }
        }

        return targetIds;
    }

    /**
     * Show area targeting modal
     */
    showAreaTargetingModal(spell, areaType, areaSize) {
        const panel = document.getElementById('targeting-panel');
        const title = document.getElementById('targeting-title');
        const description = document.getElementById('targeting-description');

        if (panel) {
            if (title) title.textContent = `Cast ${spell.name}`;
            if (description) {
                description.textContent = `Click to place ${areaSize * 5}ft ${areaType} area. Enemies in the highlighted area will be affected.`;
            }

            panel.classList.remove('hidden');

            // Set up cancel button
            const cancelBtn = document.getElementById('targeting-cancel');
            if (cancelBtn) {
                cancelBtn.onclick = () => this.cleanupAreaTargeting();
            }

            // ESC key to cancel
            this._areaEscHandler = (e) => {
                if (e.key === 'Escape') {
                    this.cleanupAreaTargeting();
                }
            };
            document.addEventListener('keydown', this._areaEscHandler);
        }

        document.body.classList.add('targeting-active');
    }

    /**
     * Hide area targeting modal
     */
    hideAreaTargetingModal() {
        const panel = document.getElementById('targeting-panel');
        if (panel) {
            panel.classList.add('hidden');
        }
        document.body.classList.remove('targeting-active');

        if (this._areaEscHandler) {
            document.removeEventListener('keydown', this._areaEscHandler);
            this._areaEscHandler = null;
        }
    }

    /**
     * Parse spell range string to feet
     * @param {string} range - Range string like "60 feet" or "Touch"
     * @returns {number} Range in feet
     */
    parseSpellRange(range) {
        if (!range) return 5;

        const rangeStr = range.toLowerCase();
        if (rangeStr === 'touch' || rangeStr === 'self') {
            return 5;
        }

        // Extract number from range string
        const match = rangeStr.match(/(\d+)/);
        if (match) {
            return parseInt(match[1]);
        }

        return 60; // Default for ranged spells
    }

    /**
     * Execute a spell on targets
     * @param {Object} spell - The spell to cast
     * @param {number} slotLevel - The slot level to use (null for cantrips)
     * @param {Array<string>} targetIds - Array of target IDs
     * @param {Object} targetPoint - Optional {x, y} for area spells
     */
    async executeSpell(spell, slotLevel, targetIds = [], targetPoint = null) {
        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const casterId = gameState.playerId;

        try {
            const response = await api.castSpell(
                combatId,
                casterId,
                spell.id,
                slotLevel,
                targetIds,
                targetPoint
            );

            if (response.success) {
                // Mark action as used (spells use action unless bonus action spell)
                state.useAction();

                // IMPORTANT: Play dice animation FIRST, before updating combat state
                // Otherwise the HP update triggers death animation before dice roll shows
                if (response.attack_roll != null) {
                    // Attack spell - show dice roll (use != null to catch both null and undefined)
                    await diceRoller.playAttackSequence({
                        attack_roll: response.attack_roll,
                        attack_total: response.attack_total,
                        target_ac: response.target_ac,
                        hit: response.hit,
                        critical: response.critical,
                        damage_dealt: response.damage_dealt ? Object.values(response.damage_dealt)[0] : 0,
                        damage_type: response.damage_type,
                        description: response.description
                    });
                } else if (response.save_dc != null && response.save_results) {
                    // Saving throw spell - show enemy's save roll vs DC
                    const targetId = Object.keys(response.save_results)[0];
                    const saveResult = response.save_results[targetId];
                    if (saveResult) {
                        await diceRoller.playSavingThrowSequence({
                            save_roll: saveResult.roll,
                            save_total: saveResult.total,
                            save_dc: response.save_dc,
                            saved: saveResult.saved,
                            save_type: response.save_type || 'DEX',
                            damage: response.damage_dealt?.[targetId] || 0,
                            damage_type: response.damage_type || 'radiant',
                            spell_name: spell.name,
                            damage_dice: response.damage_dice || '1d8',
                            damage_rolls: response.damage_rolls || []
                        });
                    }
                }

                // Update combat state AFTER dice animation completes
                // This ensures death/damage animations happen in correct order
                state.updateCombatState(response.combat_state || {});

                // Log the spell cast
                state.addLogEntry({
                    type: response.damage_dealt ? 'spell_damage' : (response.healing_done ? 'heal' : 'spell'),
                    actor: gameState.combatants[casterId]?.name,
                    message: response.description,
                    spell: spell.name,
                    slotLevel: slotLevel
                });

                eventBus.emit(EVENTS.SPELL_CAST, {
                    spell: spell,
                    slotLevel: slotLevel,
                    result: response
                });

                // Check if combat ended after this spell (e.g., killed last enemy)
                this.checkCombatOver(response);
            } else {
                // Spell returned but was unsuccessful - don't consume action
                toast.error(response.description || 'Spell casting failed');
                state.addLogEntry({
                    type: 'error',
                    message: response.description || 'Spell casting failed',
                });
            }
        } catch (error) {
            console.error('[ActionBar] Spell casting failed:', error);
            toast.error('Spell casting failed: ' + (error.message || 'Unknown error'));
            state.addLogEntry({
                type: 'error',
                message: 'Failed to cast spell: ' + (error.message || 'Unknown error'),
            });
        } finally {
            // Always reset targeting and selected action, even on failure
            this.targetingSystem.cancelTargeting();
            state.setSelectedAction(null);
        }
    }

    /**
     * Handle Dash action
     */
    async handleDash() {
        await this.executeSimpleAction('dash');
    }

    /**
     * Handle Dodge action
     */
    async handleDodge() {
        await this.executeSimpleAction('dodge');
    }

    /**
     * Handle Disengage action
     */
    async handleDisengage() {
        await this.executeSimpleAction('disengage');
    }

    /**
     * Handle Ready action
     * Shows a modal to select the trigger condition for the readied action.
     */
    async handleReady() {
        const triggers = [
            { id: 'enemy_approaches', label: 'An enemy approaches me', description: 'Trigger when an enemy enters your reach' },
            { id: 'enemy_attacks', label: 'An enemy attacks an ally', description: 'Trigger when an enemy attacks a party member' },
            { id: 'enemy_casts', label: 'An enemy casts a spell', description: 'Trigger when an enemy begins spellcasting' },
            { id: 'ally_falls', label: 'An ally falls unconscious', description: 'Trigger when a party member drops to 0 HP' },
            { id: 'enemy_moves', label: 'An enemy moves away', description: 'Trigger when an enemy leaves your reach' },
        ];

        try {
            const selectedTrigger = await this.showReadyActionModal(triggers);

            if (selectedTrigger) {
                await this.executeSimpleAction('ready', {
                    trigger: selectedTrigger.id,
                    triggerText: selectedTrigger.label
                });

                // Log the ready action
                const gameState = state.getState();
                const player = gameState.combatants[gameState.playerId];
                state.addLogEntry({
                    type: 'action',
                    actor: player?.name || 'Player',
                    message: `readies an action: "${selectedTrigger.label}"`,
                });
            }
        } catch (error) {
            // User cancelled
            console.log('[ActionBar] Ready action cancelled');
        }
    }

    /**
     * Show modal for ready action trigger selection
     * @param {Array} triggers - Available trigger options
     * @returns {Promise} Resolves with selected trigger or rejects if cancelled
     */
    showReadyActionModal(triggers) {
        return new Promise((resolve, reject) => {
            // Create or get modal
            let modal = document.getElementById('ready-action-modal');
            if (!modal) {
                modal = this.createReadyActionModal();
            }

            const container = modal.querySelector('.trigger-options');
            const customInput = modal.querySelector('.custom-trigger-input');

            // Populate trigger options
            container.innerHTML = triggers.map(t => `
                <button class="trigger-btn" data-id="${escapeHtml(t.id)}" title="${escapeHtml(t.description)}">
                    <span class="trigger-label">${escapeHtml(t.label)}</span>
                    <span class="trigger-desc">${escapeHtml(t.description)}</span>
                </button>
            `).join('') + `
                <button class="trigger-btn custom-btn" data-id="custom">
                    <span class="trigger-label">Custom trigger...</span>
                    <span class="trigger-desc">Enter your own trigger condition</span>
                </button>
            `;

            // Hide custom input initially
            if (customInput) customInput.style.display = 'none';

            // Handle trigger selection
            const handleClick = (e) => {
                const btn = e.target.closest('.trigger-btn');
                if (!btn) return;

                const triggerId = btn.dataset.id;

                if (triggerId === 'custom') {
                    // Show custom input
                    if (customInput) {
                        customInput.style.display = 'flex';
                        customInput.querySelector('input').focus();
                    }
                } else {
                    const selected = triggers.find(t => t.id === triggerId);
                    cleanup();
                    modal.classList.remove('show');
                    resolve(selected);
                }
            };

            // Handle custom input submit
            const handleCustomSubmit = () => {
                const input = customInput?.querySelector('input');
                if (input && input.value.trim()) {
                    cleanup();
                    modal.classList.remove('show');
                    resolve({
                        id: 'custom',
                        label: input.value.trim(),
                        description: 'Custom trigger'
                    });
                }
            };

            // Handle cancel
            const handleCancel = () => {
                cleanup();
                modal.classList.remove('show');
                reject(new Error('Cancelled'));
            };

            // Handle ESC key
            const handleEsc = (e) => {
                if (e.key === 'Escape') {
                    handleCancel();
                }
            };

            // Cleanup function
            const cleanup = () => {
                container.removeEventListener('click', handleClick);
                document.removeEventListener('keydown', handleEsc);
                const cancelBtn = modal.querySelector('.cancel-btn');
                if (cancelBtn) cancelBtn.removeEventListener('click', handleCancel);
                const submitBtn = customInput?.querySelector('button');
                if (submitBtn) submitBtn.removeEventListener('click', handleCustomSubmit);
            };

            // Set up event listeners
            container.addEventListener('click', handleClick);
            document.addEventListener('keydown', handleEsc);

            const cancelBtn = modal.querySelector('.cancel-btn');
            if (cancelBtn) cancelBtn.addEventListener('click', handleCancel);

            const submitBtn = customInput?.querySelector('button');
            if (submitBtn) submitBtn.addEventListener('click', handleCustomSubmit);

            // Show modal
            modal.classList.add('show');
        });
    }

    /**
     * Create ready action modal element
     * @returns {HTMLElement} Modal element
     */
    createReadyActionModal() {
        const modal = document.createElement('div');
        modal.id = 'ready-action-modal';
        modal.className = 'modal ready-action-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>Ready Action</h3>
                <p class="modal-subtitle">Choose when your readied action triggers:</p>
                <div class="trigger-options"></div>
                <div class="custom-trigger-input" style="display: none;">
                    <input type="text" placeholder="Enter custom trigger condition..." maxlength="100">
                    <button class="submit-custom-btn">Ready</button>
                </div>
                <button class="cancel-btn">Cancel</button>
            </div>
        `;

        // Add styles if not present
        if (!document.getElementById('ready-action-modal-styles')) {
            const style = document.createElement('style');
            style.id = 'ready-action-modal-styles';
            style.textContent = `
                .ready-action-modal {
                    display: none;
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0, 0, 0, 0.7);
                    z-index: 1000;
                    align-items: center;
                    justify-content: center;
                }
                .ready-action-modal.show {
                    display: flex;
                }
                .ready-action-modal .modal-content {
                    background: linear-gradient(135deg, #2a1a0a, #1a0f05);
                    border: 2px solid #8b7355;
                    border-radius: 8px;
                    padding: 24px;
                    min-width: 400px;
                    max-width: 500px;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
                }
                .ready-action-modal h3 {
                    color: #d4af37;
                    margin: 0 0 8px 0;
                    text-align: center;
                    font-size: 1.5em;
                }
                .ready-action-modal .modal-subtitle {
                    color: #c9b896;
                    text-align: center;
                    margin-bottom: 16px;
                }
                .ready-action-modal .trigger-options {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                    margin-bottom: 16px;
                }
                .ready-action-modal .trigger-btn {
                    background: linear-gradient(135deg, #3d2817, #2a1a0a);
                    border: 1px solid #6b5344;
                    border-radius: 6px;
                    padding: 12px;
                    text-align: left;
                    cursor: pointer;
                    transition: all 0.2s;
                    display: flex;
                    flex-direction: column;
                    gap: 4px;
                }
                .ready-action-modal .trigger-btn:hover {
                    background: linear-gradient(135deg, #4d3827, #3a2a1a);
                    border-color: #d4af37;
                }
                .ready-action-modal .trigger-label {
                    color: #e8dcc8;
                    font-weight: bold;
                    font-size: 1em;
                }
                .ready-action-modal .trigger-desc {
                    color: #9a8873;
                    font-size: 0.85em;
                }
                .ready-action-modal .custom-btn {
                    border-style: dashed;
                }
                .ready-action-modal .custom-trigger-input {
                    display: flex;
                    gap: 8px;
                    margin-bottom: 16px;
                }
                .ready-action-modal .custom-trigger-input input {
                    flex: 1;
                    padding: 8px 12px;
                    background: #1a0f05;
                    border: 1px solid #6b5344;
                    border-radius: 4px;
                    color: #e8dcc8;
                }
                .ready-action-modal .submit-custom-btn {
                    background: linear-gradient(135deg, #4a7c2e, #2d5a1a);
                    border: 1px solid #5a9c3e;
                    border-radius: 4px;
                    padding: 8px 16px;
                    color: #e8dcc8;
                    cursor: pointer;
                }
                .ready-action-modal .cancel-btn {
                    display: block;
                    width: 100%;
                    padding: 10px;
                    background: linear-gradient(135deg, #5a3a2a, #3a1a0a);
                    border: 1px solid #6b5344;
                    border-radius: 4px;
                    color: #c9b896;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                .ready-action-modal .cancel-btn:hover {
                    background: linear-gradient(135deg, #6a4a3a, #4a2a1a);
                }
            `;
            document.head.appendChild(style);
        }

        document.body.appendChild(modal);
        return modal;
    }

    // ==================== Additional Standard Actions ====================

    /**
     * Handle Help action - give an ally advantage on their next attack or check
     * Requires selecting an adjacent ally
     */
    async handleHelp() {
        if (!state.isPlayerTurn() || state.getState().turn.actionUsed) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];

        // Find adjacent allies
        const allies = Object.values(gameState.combatants).filter(c => {
            if (c.id === gameState.playerId) return false;
            if (c.is_enemy) return false;
            if (c.hp <= 0) return false;
            // Check if adjacent (within 5ft)
            const dx = Math.abs(c.x - player.x);
            const dy = Math.abs(c.y - player.y);
            return dx <= 1 && dy <= 1;
        });

        if (allies.length === 0) {
            toast.warning('No adjacent allies to help');
            return;
        }

        // If only one ally, help them directly
        if (allies.length === 1) {
            await this.executeHelpAction(allies[0].id);
            return;
        }

        // Multiple allies - enter targeting mode
        state.setTargetingState({
            mode: 'single',
            action: 'help',
            validTargets: allies.map(a => a.id),
            callback: async (targetId) => {
                await this.executeHelpAction(targetId);
            }
        });

        toast.info('Select an ally to help');
    }

    /**
     * Execute Help action on a target ally
     * @param {string} targetId - ID of the ally to help
     */
    async executeHelpAction(targetId) {
        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const target = gameState.combatants[targetId];

        try {
            const response = await api.performAction(gameState.combat.id, 'help', targetId);

            if (response.success) {
                state.useAction();

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                state.addLogEntry({
                    type: 'action',
                    actor: player?.name,
                    message: `${player?.name} helps ${target?.name} - they have advantage on their next attack!`,
                });

                toast.success(`Helping ${target?.name}!`);
            } else {
                toast.error(response.message || 'Failed to help');
            }
        } catch (error) {
            console.error('[ActionBar] Help action failed:', error);
            toast.error('Help action failed');
        }

        state.clearTargetingState();
    }

    /**
     * Handle Hide action - attempt to become hidden with a Stealth check
     */
    async handleHide() {
        if (!state.isPlayerTurn() || state.getState().turn.actionUsed) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];

        try {
            const response = await api.performAction(gameState.combat.id, 'hide');

            if (response.success) {
                state.useAction();

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                const stealthRoll = response.extra_data?.stealth_roll || '?';
                const isHidden = response.extra_data?.is_hidden;

                state.addLogEntry({
                    type: 'action',
                    actor: player?.name,
                    message: `${player?.name} attempts to hide (Stealth: ${stealthRoll}) - ${isHidden ? 'Success!' : 'Enemies noticed!'}`,
                });

                if (isHidden) {
                    toast.success(`Hidden! Stealth: ${stealthRoll}`);
                } else {
                    toast.warning(`Failed to hide. Stealth: ${stealthRoll}`);
                }
            } else {
                toast.error(response.message || 'Failed to hide');
            }
        } catch (error) {
            console.error('[ActionBar] Hide action failed:', error);
            toast.error('Hide action failed');
        }
    }

    /**
     * Handle Grapple action - attempt to grab an enemy
     * Replaces one attack, requires a free hand
     */
    async handleGrapple() {
        if (!state.isPlayerTurn()) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];

        // Find adjacent enemies that can be grappled
        const targets = Object.values(gameState.combatants).filter(c => {
            if (!c.is_enemy) return false;
            if (c.hp <= 0) return false;
            // Check if adjacent (within 5ft reach)
            const dx = Math.abs(c.x - player.x);
            const dy = Math.abs(c.y - player.y);
            return dx <= 1 && dy <= 1;
        });

        if (targets.length === 0) {
            toast.warning('No enemies in reach to grapple');
            return;
        }

        // Enter targeting mode
        state.setTargetingState({
            mode: 'single',
            action: 'grapple',
            validTargets: targets.map(t => t.id),
            callback: async (targetId) => {
                await this.executeGrapple(targetId);
            }
        });

        toast.info('Select an enemy to grapple');
    }

    /**
     * Execute Grapple on a target
     * @param {string} targetId - ID of the enemy to grapple
     */
    async executeGrapple(targetId) {
        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const target = gameState.combatants[targetId];

        try {
            const response = await api.performAction(gameState.combat.id, 'grapple', targetId);

            if (response.success) {
                // Grapple replaces one attack, not the full action
                // If player has extra attack unused, don't mark action as fully used
                const attacksRemaining = gameState.turn.attacksRemaining || 0;
                if (attacksRemaining <= 1) {
                    state.useAction();
                } else {
                    state.set('turn.attacksRemaining', attacksRemaining - 1);
                }

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                const grappleSuccess = response.extra_data?.grapple_success;
                const playerRoll = response.extra_data?.player_roll || '?';
                const targetRoll = response.extra_data?.target_roll || '?';

                state.addLogEntry({
                    type: 'action',
                    actor: player?.name,
                    message: `${player?.name} attempts to grapple ${target?.name} (${playerRoll} vs ${targetRoll}) - ${grappleSuccess ? 'Grappled!' : 'Failed!'}`,
                });

                if (grappleSuccess) {
                    toast.success(`Grappled ${target?.name}!`);
                } else {
                    toast.warning(`Failed to grapple ${target?.name}`);
                }
            } else {
                toast.error(response.message || 'Grapple failed');
            }
        } catch (error) {
            console.error('[ActionBar] Grapple failed:', error);
            toast.error('Grapple failed');
        }

        state.clearTargetingState();
    }

    /**
     * Handle Shove action - attempt to push an enemy or knock them prone
     * Replaces one attack
     */
    async handleShove() {
        if (!state.isPlayerTurn()) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];

        // Find adjacent enemies that can be shoved
        const targets = Object.values(gameState.combatants).filter(c => {
            if (!c.is_enemy) return false;
            if (c.hp <= 0) return false;
            // Check if adjacent (within 5ft reach)
            const dx = Math.abs(c.x - player.x);
            const dy = Math.abs(c.y - player.y);
            return dx <= 1 && dy <= 1;
        });

        if (targets.length === 0) {
            toast.warning('No enemies in reach to shove');
            return;
        }

        // Enter targeting mode
        state.setTargetingState({
            mode: 'single',
            action: 'shove',
            validTargets: targets.map(t => t.id),
            callback: async (targetId) => {
                // Ask: push away or knock prone?
                const shoveType = await this.showShoveTypeModal();
                if (shoveType) {
                    await this.executeShove(targetId, shoveType);
                }
            }
        });

        toast.info('Select an enemy to shove');
    }

    /**
     * Show modal to choose shove type (push or prone)
     * @returns {Promise<string>} 'push' or 'prone'
     */
    showShoveTypeModal() {
        return new Promise((resolve) => {
            let modal = document.getElementById('shove-type-modal');
            if (!modal) {
                modal = document.createElement('div');
                modal.id = 'shove-type-modal';
                modal.className = 'modal shove-type-modal';
                modal.innerHTML = `
                    <div class="modal-content">
                        <h3>Shove Effect</h3>
                        <div class="shove-options">
                            <button class="shove-btn" data-type="push">
                                <span class="shove-icon">👐</span>
                                <span class="shove-label">Push Away</span>
                                <span class="shove-desc">Push the target 5 feet away from you</span>
                            </button>
                            <button class="shove-btn" data-type="prone">
                                <span class="shove-icon">🦵</span>
                                <span class="shove-label">Knock Prone</span>
                                <span class="shove-desc">Knock the target prone (advantage on melee attacks)</span>
                            </button>
                        </div>
                        <button class="cancel-btn">Cancel</button>
                    </div>
                `;

                const style = document.createElement('style');
                style.textContent = `
                    .shove-type-modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 1000; align-items: center; justify-content: center; }
                    .shove-type-modal.show { display: flex; }
                    .shove-type-modal .modal-content { background: linear-gradient(135deg, #2a1a0a, #1a0f05); border: 2px solid #8b7355; border-radius: 8px; padding: 24px; min-width: 300px; }
                    .shove-type-modal h3 { color: #d4af37; margin: 0 0 16px 0; text-align: center; }
                    .shove-type-modal .shove-options { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
                    .shove-type-modal .shove-btn { background: linear-gradient(135deg, #3d2817, #2a1a0a); border: 1px solid #6b5344; border-radius: 6px; padding: 12px; cursor: pointer; display: flex; flex-direction: column; align-items: center; text-align: center; transition: all 0.2s; }
                    .shove-type-modal .shove-btn:hover { background: linear-gradient(135deg, #4d3827, #3a2a1a); border-color: #d4af37; }
                    .shove-type-modal .shove-icon { font-size: 1.5em; margin-bottom: 4px; }
                    .shove-type-modal .shove-label { color: #e8dcc8; font-weight: bold; }
                    .shove-type-modal .shove-desc { color: #9a8873; font-size: 0.8em; margin-top: 4px; }
                    .shove-type-modal .cancel-btn { display: block; width: 100%; padding: 10px; background: linear-gradient(135deg, #5a3a2a, #3a1a0a); border: 1px solid #6b5344; border-radius: 4px; color: #c9b896; cursor: pointer; }
                `;
                document.head.appendChild(style);
                document.body.appendChild(modal);
            }

            const handleClick = (e) => {
                const btn = e.target.closest('.shove-btn');
                if (btn) {
                    cleanup();
                    modal.classList.remove('show');
                    resolve(btn.dataset.type);
                }
            };

            const handleCancel = () => {
                cleanup();
                modal.classList.remove('show');
                resolve(null);
            };

            const handleEsc = (e) => {
                if (e.key === 'Escape') handleCancel();
            };

            const cleanup = () => {
                modal.querySelector('.shove-options').removeEventListener('click', handleClick);
                modal.querySelector('.cancel-btn').removeEventListener('click', handleCancel);
                document.removeEventListener('keydown', handleEsc);
            };

            modal.querySelector('.shove-options').addEventListener('click', handleClick);
            modal.querySelector('.cancel-btn').addEventListener('click', handleCancel);
            document.addEventListener('keydown', handleEsc);

            modal.classList.add('show');
        });
    }

    /**
     * Execute Shove on a target
     * @param {string} targetId - ID of the enemy to shove
     * @param {string} shoveType - 'push' or 'prone'
     */
    async executeShove(targetId, shoveType) {
        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const target = gameState.combatants[targetId];

        try {
            const response = await api.performAction(gameState.combat.id, 'shove', targetId, {
                extraData: { shove_type: shoveType }
            });

            if (response.success) {
                // Shove replaces one attack
                const attacksRemaining = gameState.turn.attacksRemaining || 0;
                if (attacksRemaining <= 1) {
                    state.useAction();
                } else {
                    state.set('turn.attacksRemaining', attacksRemaining - 1);
                }

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                const shoveSuccess = response.extra_data?.shove_success;
                const playerRoll = response.extra_data?.player_roll || '?';
                const targetRoll = response.extra_data?.target_roll || '?';
                const effectText = shoveType === 'push' ? 'pushed 5ft' : 'knocked prone';

                state.addLogEntry({
                    type: 'action',
                    actor: player?.name,
                    message: `${player?.name} attempts to shove ${target?.name} (${playerRoll} vs ${targetRoll}) - ${shoveSuccess ? effectText + '!' : 'Failed!'}`,
                });

                if (shoveSuccess) {
                    toast.success(`${target?.name} ${effectText}!`);
                } else {
                    toast.warning(`Failed to shove ${target?.name}`);
                }
            } else {
                toast.error(response.message || 'Shove failed');
            }
        } catch (error) {
            console.error('[ActionBar] Shove failed:', error);
            toast.error('Shove failed');
        }

        state.clearTargetingState();
    }

    /**
     * Handle Move button - toggle movement mode
     * When movement mode is active, clicking reachable cells will move the player
     */
    handleMove() {
        if (!state.isPlayerTurn()) return;

        const gameState = state.getState();
        if (gameState.turn.movementRemaining <= 0) return;

        // Toggle movement mode
        state.toggleMovementModeActive();

        // Log feedback
        if (state.isMovementModeActive()) {
            state.addLogEntry({
                type: 'action',
                message: 'Movement mode enabled - click a highlighted cell to move',
            });
        } else {
            state.addLogEntry({
                type: 'action',
                message: 'Movement mode disabled',
            });
        }
    }

    /**
     * Handle Threat Zone Toggle - show/hide enemy threat zones on the grid
     * Threat zones indicate where enemies can make opportunity attacks
     */
    async handleThreatZoneToggle() {
        const gameState = state.getState();
        const combatId = gameState.combat?.id;

        // Toggle the display state
        const newState = state.toggleThreatZoneDisplay();

        // Update button visual state
        if (this.buttons.threatZones) {
            if (newState) {
                this.buttons.threatZones.classList.add('active');
            } else {
                this.buttons.threatZones.classList.remove('active');
            }
        }

        // If turning on, fetch threat zones from backend
        if (newState && combatId) {
            try {
                const response = await api.getThreatZones(combatId, gameState.playerId);
                if (response.threat_zones) {
                    state.setThreatZones(response.threat_zones);
                }
            } catch (error) {
                console.error('[ActionBar] Failed to fetch threat zones:', error);
                // Don't show toast - it's a UI toggle, not a critical action
            }
        }

        // Log feedback
        state.addLogEntry({
            type: 'info',
            message: newState ? 'Threat zones displayed - red areas trigger opportunity attacks' : 'Threat zones hidden',
        });

        // Emit event for grid to redraw
        eventBus.emit(EVENTS.THREAT_ZONES_UPDATED, { visible: newState });
    }

    /**
     * Update class feature buttons visibility and enabled state
     * @param {Object} player - Player combatant data
     * @param {boolean} canAct - Whether player can use actions
     * @param {boolean} canUseBonusAction - Whether player can use bonus actions
     * @param {Object} turn - Turn state
     */
    updateClassFeatureButtons(player, canAct, canUseBonusAction, turn) {
        const playerClass = (player?.stats?.class || player?.character_class || '').toLowerCase();
        const playerLevel = player?.stats?.level || player?.level || 1;

        // Action Surge: Fighter 2+, free action (doesn't use action economy)
        const isFighter = playerClass === 'fighter';
        const hasActionSurge = isFighter && playerLevel >= 2;
        const actionSurgeUsed = turn.actionSurgeUsed || player?.resources?.action_surge_used;
        if (this.buttons.actionSurge) {
            this.buttons.actionSurge.style.display = hasActionSurge ? 'flex' : 'none';
            this.setButtonEnabled(this.buttons.actionSurge, hasActionSurge && !actionSurgeUsed && canAct);
        }

        // Rage: Barbarian 1+, bonus action
        const isBarbarian = playerClass === 'barbarian';
        const isRaging = turn.isRaging || player?.conditions?.includes('raging');
        const ragesRemaining = player?.resources?.rages_remaining ?? (isBarbarian ? 2 : 0);
        if (this.buttons.rage) {
            this.buttons.rage.style.display = isBarbarian ? 'flex' : 'none';
            this.setButtonEnabled(this.buttons.rage, isBarbarian && canUseBonusAction && !isRaging && ragesRemaining > 0);
            // Update rage button visual if already raging
            if (isRaging) {
                this.buttons.rage.classList.add('active');
            } else {
                this.buttons.rage.classList.remove('active');
            }
        }

        // Wild Shape: Druid 2+, bonus action
        const isDruid = playerClass === 'druid';
        const hasWildShape = isDruid && playerLevel >= 2;
        const wildShapeUsesRemaining = player?.resources?.wild_shape_uses ?? (hasWildShape ? 2 : 0);
        const isWildShaped = turn.isWildShaped || player?.conditions?.includes('wild_shaped');
        if (this.buttons.wildShape) {
            this.buttons.wildShape.style.display = hasWildShape ? 'flex' : 'none';
            this.setButtonEnabled(this.buttons.wildShape, hasWildShape && canUseBonusAction && wildShapeUsesRemaining > 0);
            if (isWildShaped) {
                this.buttons.wildShape.classList.add('active');
                // Change label when transformed
                const label = this.buttons.wildShape.querySelector('.action-label');
                if (label) label.textContent = 'Revert';
            } else {
                this.buttons.wildShape.classList.remove('active');
                const label = this.buttons.wildShape.querySelector('.action-label');
                if (label) label.textContent = 'Wild Shape';
            }
        }

        // Lay on Hands: Paladin 1+, action
        const isPaladin = playerClass === 'paladin';
        const layOnHandsPool = player?.resources?.lay_on_hands_pool ?? (isPaladin ? playerLevel * 5 : 0);
        if (this.buttons.layOnHands) {
            this.buttons.layOnHands.style.display = isPaladin ? 'flex' : 'none';
            this.setButtonEnabled(this.buttons.layOnHands, isPaladin && canAct && layOnHandsPool > 0);
        }

        // Cunning Action: Rogue 2+, bonus action
        const isRogue = playerClass === 'rogue';
        const hasCunningAction = isRogue && playerLevel >= 2;
        if (this.buttons.cunningAction) {
            this.buttons.cunningAction.style.display = hasCunningAction ? 'flex' : 'none';
            this.setButtonEnabled(this.buttons.cunningAction, hasCunningAction && canUseBonusAction);
        }

        // Ki Powers: Monk 2+, various action types
        const isMonk = playerClass === 'monk';
        const hasKi = isMonk && playerLevel >= 2;
        const kiPointsRemaining = player?.resources?.ki_points ?? (hasKi ? playerLevel : 0);
        if (this.buttons.kiPowers) {
            this.buttons.kiPowers.style.display = hasKi ? 'flex' : 'none';
            // Ki powers have different action costs, so just check if player has Ki and can act
            this.setButtonEnabled(this.buttons.kiPowers, hasKi && kiPointsRemaining > 0 && canAct);
        }

        // Reckless Attack: Barbarian 2+, free action at start of attack
        const hasRecklessAttack = isBarbarian && playerLevel >= 2;
        const isReckless = turn.isReckless || player?.conditions?.includes('reckless');
        if (this.buttons.recklessAttack) {
            this.buttons.recklessAttack.style.display = hasRecklessAttack ? 'flex' : 'none';
            // Can only use Reckless Attack if not already active this turn
            this.setButtonEnabled(this.buttons.recklessAttack, hasRecklessAttack && canAct && !isReckless);
            if (isReckless) {
                this.buttons.recklessAttack.classList.add('active');
            } else {
                this.buttons.recklessAttack.classList.remove('active');
            }
        }

        // Channel Divinity: Cleric/Paladin 2+, action
        const isCleric = playerClass === 'cleric';
        const hasChannelDivinity = (isCleric || isPaladin) && playerLevel >= 2;
        const channelDivinityUsesRemaining = player?.resources?.channel_divinity_uses ?? (hasChannelDivinity ? 1 : 0);
        if (this.buttons.channelDivinity) {
            this.buttons.channelDivinity.style.display = hasChannelDivinity ? 'flex' : 'none';
            this.setButtonEnabled(this.buttons.channelDivinity, hasChannelDivinity && canAct && channelDivinityUsesRemaining > 0);
        }

        // Bardic Inspiration: Bard 1+, bonus action
        const isBard = playerClass === 'bard';
        // Uses equal to CHA modifier (min 1), tracked in resources
        const bardicInspirationUses = player?.resources?.bardic_inspiration_uses ?? (isBard ? 3 : 0);
        if (this.buttons.bardicInspiration) {
            this.buttons.bardicInspiration.style.display = isBard ? 'flex' : 'none';
            this.setButtonEnabled(this.buttons.bardicInspiration, isBard && canUseBonusAction && bardicInspirationUses > 0);
        }

        // Metamagic: Sorcerer 3+, various costs
        const isSorcerer = playerClass === 'sorcerer';
        const hasMetamagic = isSorcerer && playerLevel >= 3;
        const sorceryPointsRemaining = player?.resources?.sorcery_points ?? (hasMetamagic ? playerLevel : 0);
        if (this.buttons.metamagic) {
            this.buttons.metamagic.style.display = hasMetamagic ? 'flex' : 'none';
            // Metamagic is applied when casting spells, but can view available options
            this.setButtonEnabled(this.buttons.metamagic, hasMetamagic && sorceryPointsRemaining > 0 && canAct);
        }

        // Hunter's Mark: Ranger 1+, bonus action (concentration spell-like)
        const isRanger = playerClass === 'ranger';
        const hasHuntersMark = isRanger && playerLevel >= 1;
        const huntersMarkActive = player?.conditions?.includes('hunters_mark_active');
        if (this.buttons.huntersMark) {
            this.buttons.huntersMark.style.display = hasHuntersMark ? 'flex' : 'none';
            // Can cast if not already active, has bonus action, and has spell slots
            const rangerSpellSlots = player?.resources?.spell_slots_remaining ?? (isRanger ? 2 : 0);
            this.setButtonEnabled(this.buttons.huntersMark, hasHuntersMark && canUseBonusAction && !huntersMarkActive && rangerSpellSlots > 0);
            if (huntersMarkActive) {
                this.buttons.huntersMark.classList.add('active');
            } else {
                this.buttons.huntersMark.classList.remove('active');
            }
        }

        // Favored Foe: Ranger 1+, free action (replaces Favored Enemy in 2024)
        const hasFavoredFoe = isRanger && playerLevel >= 1;
        const favoredFoeUsesRemaining = player?.resources?.favored_foe_uses ?? (isRanger ? Math.max(1, Math.floor(player?.proficiency_bonus || 2)) : 0);
        if (this.buttons.favoredFoe) {
            this.buttons.favoredFoe.style.display = hasFavoredFoe ? 'flex' : 'none';
            this.setButtonEnabled(this.buttons.favoredFoe, hasFavoredFoe && canAct && favoredFoeUsesRemaining > 0);
        }

        // Eldritch Blast: Warlock cantrip, action
        const isWarlock = playerClass === 'warlock';
        if (this.buttons.eldritchBlast) {
            this.buttons.eldritchBlast.style.display = isWarlock ? 'flex' : 'none';
            this.setButtonEnabled(this.buttons.eldritchBlast, isWarlock && canAct);
        }

        // Invocations: Warlock 2+, various effects (opens modal)
        const hasInvocations = isWarlock && playerLevel >= 2;
        if (this.buttons.invocations) {
            this.buttons.invocations.style.display = hasInvocations ? 'flex' : 'none';
            this.setButtonEnabled(this.buttons.invocations, hasInvocations && canAct);
        }

        // Hex: Warlock 1+, bonus action (concentration spell)
        const hexActive = player?.conditions?.includes('hex_active');
        if (this.buttons.hex) {
            this.buttons.hex.style.display = isWarlock ? 'flex' : 'none';
            // Check Pact Magic slots
            const pactMagicSlots = player?.resources?.pact_magic_slots ?? (isWarlock ? 1 : 0);
            this.setButtonEnabled(this.buttons.hex, isWarlock && canUseBonusAction && !hexActive && pactMagicSlots > 0);
            if (hexActive) {
                this.buttons.hex.classList.add('active');
            } else {
                this.buttons.hex.classList.remove('active');
            }
        }
    }

    // ==================== Class Feature Handlers ====================

    /**
     * Handle Action Surge (Fighter feature)
     * Grants an additional action this turn (free action, once per short rest)
     */
    async handleActionSurge() {
        if (!state.isPlayerTurn()) return;

        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const player = gameState.combatants[gameState.playerId];

        // Check if already used
        if (gameState.turn.actionSurgeUsed || player?.resources?.action_surge_used) {
            toast.warning('Action Surge already used this rest');
            return;
        }

        try {
            const response = await api.useClassFeature(combatId, 'action_surge', {
                combatant_id: gameState.playerId
            });

            if (response.success) {
                // Mark Action Surge as used
                state.set('turn.actionSurgeUsed', true);

                // Reset action for this turn (Action Surge grants a new action)
                state.set('turn.actionUsed', false);

                // Reset attacks for the new action granted by Action Surge
                const currentTurn = state.getState().turn || {};
                const maxAttacks = currentTurn.maxAttacks || 2;  // Level 5+ fighters get 2
                state.set('turn.attacksRemaining', maxAttacks);
                state.set('turn.attacks_made', 0);

                // Update combat state
                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                state.addLogEntry({
                    type: 'class_feature',
                    actor: player?.name,
                    message: `${player?.name} uses Action Surge and gains an additional action!`,
                });

                toast.success('Action Surge activated!');
                eventBus.emit(EVENTS.CLASS_FEATURE_USED, { feature: 'action_surge' });
            } else {
                toast.error(response.message || 'Failed to use Action Surge');
            }
        } catch (error) {
            console.error('[ActionBar] Action Surge failed:', error);
            toast.error('Action Surge failed');
        }
    }

    /**
     * Handle Rage (Barbarian feature)
     * Enter a rage for bonus damage and resistance (bonus action)
     */
    async handleRage() {
        if (!state.isPlayerTurn() || state.getState().turn.bonusActionUsed) return;

        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const player = gameState.combatants[gameState.playerId];

        // Check if already raging
        if (gameState.turn.isRaging || player?.conditions?.includes('raging')) {
            toast.warning('Already raging!');
            return;
        }

        try {
            const response = await api.useClassFeature(combatId, 'rage', {
                combatant_id: gameState.playerId
            });

            if (response.success) {
                state.set('turn.bonusActionUsed', true);
                state.set('turn.isRaging', true);

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                state.addLogEntry({
                    type: 'class_feature',
                    actor: player?.name,
                    message: `${player?.name} enters a RAGE! (+${response.extra_data?.rage_damage || 2} damage, resistance to physical)`,
                });

                toast.success('RAGE activated!');
                eventBus.emit(EVENTS.CLASS_FEATURE_USED, { feature: 'rage' });
            } else {
                toast.error(response.message || 'Failed to enter rage');
            }
        } catch (error) {
            console.error('[ActionBar] Rage failed:', error);
            toast.error('Rage failed');
        }
    }

    /**
     * Handle Wild Shape (Druid feature)
     * Opens a modal to select beast form (bonus action)
     */
    async handleWildShape() {
        if (!state.isPlayerTurn() || state.getState().turn.bonusActionUsed) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];

        // If already in Wild Shape, revert instead
        if (gameState.turn.isWildShaped || player?.conditions?.includes('wild_shaped')) {
            await this.revertWildShape();
            return;
        }

        // Open Wild Shape modal with available beast forms
        eventBus.emit(EVENTS.WILD_SHAPE_REQUESTED, { player });
    }

    /**
     * Revert from Wild Shape back to normal form
     */
    async revertWildShape() {
        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const player = gameState.combatants[gameState.playerId];

        try {
            const response = await api.useClassFeature(combatId, 'revert_wild_shape', {
                combatant_id: gameState.playerId
            });

            if (response.success) {
                // Reverting is a bonus action in 2024 rules (or free if knocked out)
                state.set('turn.bonusActionUsed', true);
                state.set('turn.isWildShaped', false);

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                state.addLogEntry({
                    type: 'class_feature',
                    actor: player?.name,
                    message: `${player?.name} reverts from Wild Shape.`,
                });

                toast.success('Reverted to normal form');
            } else {
                toast.error(response.message || 'Failed to revert');
            }
        } catch (error) {
            console.error('[ActionBar] Revert Wild Shape failed:', error);
            toast.error('Failed to revert from Wild Shape');
        }
    }

    /**
     * Handle Lay on Hands (Paladin feature)
     * Opens a modal to select healing amount and target (action)
     */
    async handleLayOnHands() {
        if (!state.isPlayerTurn() || state.getState().turn.actionUsed) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];

        // Open Lay on Hands modal with healing slider and target selection
        eventBus.emit(EVENTS.LAY_ON_HANDS_REQUESTED, { player });
    }

    /**
     * Execute Lay on Hands healing
     * @param {string} targetId - Target combatant ID
     * @param {number} amount - Amount to heal
     */
    async executeLayOnHands(targetId, amount) {
        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const player = gameState.combatants[gameState.playerId];

        try {
            const response = await api.useClassFeature(combatId, 'lay_on_hands', {
                combatant_id: gameState.playerId,
                target_id: targetId,
                amount: amount
            });

            if (response.success) {
                state.useAction();

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                const targetName = gameState.combatants[targetId]?.name || 'target';
                state.addLogEntry({
                    type: 'heal',
                    actor: player?.name,
                    message: `${player?.name} uses Lay on Hands to heal ${targetName} for ${response.extra_data?.healing || amount} HP!`,
                });

                toast.success(`Healed ${response.extra_data?.healing || amount} HP!`);
                eventBus.emit(EVENTS.CLASS_FEATURE_USED, { feature: 'lay_on_hands', healing: response.extra_data?.healing });
            } else {
                toast.error(response.message || 'Failed to use Lay on Hands');
            }
        } catch (error) {
            console.error('[ActionBar] Lay on Hands failed:', error);
            toast.error('Lay on Hands failed');
        }
    }

    /**
     * Handle Cunning Action (Rogue feature)
     * Shows sub-menu for Dash, Disengage, or Hide as bonus action
     */
    async handleCunningAction() {
        if (!state.isPlayerTurn() || state.getState().turn.bonusActionUsed) return;

        // Show cunning action sub-menu
        const options = [
            { id: 'dash', label: 'Dash', description: 'Double your movement speed', icon: '💨' },
            { id: 'disengage', label: 'Disengage', description: 'Movement doesn\'t provoke opportunity attacks', icon: '🏃' },
            { id: 'hide', label: 'Hide', description: 'Attempt to hide (Stealth check)', icon: '🙈' },
        ];

        try {
            const selected = await this.showCunningActionMenu(options);
            if (selected) {
                await this.executeCunningAction(selected.id);
            }
        } catch (error) {
            // User cancelled
            console.log('[ActionBar] Cunning Action cancelled');
        }
    }

    /**
     * Show cunning action selection menu
     * @param {Array} options - Available cunning action options
     * @returns {Promise<Object>} Selected option
     */
    showCunningActionMenu(options) {
        return new Promise((resolve, reject) => {
            let modal = document.getElementById('cunning-action-modal');
            if (!modal) {
                modal = this.createCunningActionModal();
            }

            const container = modal.querySelector('.cunning-options');
            container.innerHTML = options.map(opt => `
                <button class="cunning-btn" data-id="${escapeHtml(opt.id)}">
                    <span class="cunning-icon">${opt.icon}</span>
                    <div class="cunning-info">
                        <span class="cunning-label">${escapeHtml(opt.label)}</span>
                        <span class="cunning-desc">${escapeHtml(opt.description)}</span>
                    </div>
                </button>
            `).join('');

            const handleClick = (e) => {
                const btn = e.target.closest('.cunning-btn');
                if (!btn) return;

                const optId = btn.dataset.id;
                const selected = options.find(o => o.id === optId);

                cleanup();
                modal.classList.remove('show');
                resolve(selected);
            };

            const handleCancel = () => {
                cleanup();
                modal.classList.remove('show');
                reject(new Error('Cancelled'));
            };

            const handleEsc = (e) => {
                if (e.key === 'Escape') handleCancel();
            };

            const cleanup = () => {
                container.removeEventListener('click', handleClick);
                document.removeEventListener('keydown', handleEsc);
                modal.querySelector('.cancel-btn')?.removeEventListener('click', handleCancel);
            };

            container.addEventListener('click', handleClick);
            document.addEventListener('keydown', handleEsc);
            modal.querySelector('.cancel-btn')?.addEventListener('click', handleCancel);

            modal.classList.add('show');
        });
    }

    /**
     * Create cunning action selection modal
     * @returns {HTMLElement} Modal element
     */
    createCunningActionModal() {
        const modal = document.createElement('div');
        modal.id = 'cunning-action-modal';
        modal.className = 'modal cunning-action-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>🏃 Cunning Action</h3>
                <p class="modal-subtitle">Choose your bonus action:</p>
                <div class="cunning-options"></div>
                <button class="cancel-btn">Cancel</button>
            </div>
        `;

        if (!document.getElementById('cunning-action-modal-styles')) {
            const style = document.createElement('style');
            style.id = 'cunning-action-modal-styles';
            style.textContent = `
                .cunning-action-modal {
                    display: none;
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0, 0, 0, 0.7);
                    z-index: 1000;
                    align-items: center;
                    justify-content: center;
                }
                .cunning-action-modal.show { display: flex; }
                .cunning-action-modal .modal-content {
                    background: linear-gradient(135deg, #2a1a0a, #1a0f05);
                    border: 2px solid #8b7355;
                    border-radius: 8px;
                    padding: 24px;
                    min-width: 350px;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
                }
                .cunning-action-modal h3 {
                    color: #d4af37;
                    margin: 0 0 8px 0;
                    text-align: center;
                }
                .cunning-action-modal .modal-subtitle {
                    color: #c9b896;
                    text-align: center;
                    margin-bottom: 16px;
                }
                .cunning-action-modal .cunning-options {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                    margin-bottom: 16px;
                }
                .cunning-action-modal .cunning-btn {
                    background: linear-gradient(135deg, #3d2817, #2a1a0a);
                    border: 1px solid #6b5344;
                    border-radius: 6px;
                    padding: 12px;
                    cursor: pointer;
                    transition: all 0.2s;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }
                .cunning-action-modal .cunning-btn:hover {
                    background: linear-gradient(135deg, #4d3827, #3a2a1a);
                    border-color: #d4af37;
                }
                .cunning-action-modal .cunning-icon { font-size: 1.5em; }
                .cunning-action-modal .cunning-info {
                    display: flex;
                    flex-direction: column;
                    text-align: left;
                }
                .cunning-action-modal .cunning-label {
                    color: #e8dcc8;
                    font-weight: bold;
                }
                .cunning-action-modal .cunning-desc {
                    color: #9a8873;
                    font-size: 0.85em;
                }
                .cunning-action-modal .cancel-btn {
                    display: block;
                    width: 100%;
                    padding: 10px;
                    background: linear-gradient(135deg, #5a3a2a, #3a1a0a);
                    border: 1px solid #6b5344;
                    border-radius: 4px;
                    color: #c9b896;
                    cursor: pointer;
                }
                .cunning-action-modal .cancel-btn:hover {
                    background: linear-gradient(135deg, #6a4a3a, #4a2a1a);
                }
            `;
            document.head.appendChild(style);
        }

        document.body.appendChild(modal);
        return modal;
    }

    /**
     * Execute cunning action (Dash/Disengage/Hide as bonus action)
     * @param {string} actionType - 'dash', 'disengage', or 'hide'
     */
    async executeCunningAction(actionType) {
        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const player = gameState.combatants[gameState.playerId];

        try {
            const response = await api.useClassFeature(combatId, 'cunning_action', {
                combatant_id: gameState.playerId,
                action_type: actionType
            });

            if (response.success) {
                state.set('turn.bonusActionUsed', true);

                // Apply action effect
                if (actionType === 'dash') {
                    // Double movement
                    const currentMovement = gameState.turn.movementRemaining || 0;
                    state.set('turn.movementRemaining', currentMovement + (player?.speed || 30));
                } else if (actionType === 'disengage') {
                    state.set('turn.disengaged', true);
                }

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                const actionNames = { dash: 'Dash', disengage: 'Disengage', hide: 'Hide' };
                state.addLogEntry({
                    type: 'class_feature',
                    actor: player?.name,
                    message: `${player?.name} uses Cunning Action to ${actionNames[actionType]}!`,
                });

                toast.success(`Cunning Action: ${actionNames[actionType]}!`);
                eventBus.emit(EVENTS.CLASS_FEATURE_USED, { feature: 'cunning_action', action: actionType });
            } else {
                toast.error(response.message || `Failed to use Cunning Action: ${actionType}`);
            }
        } catch (error) {
            console.error('[ActionBar] Cunning Action failed:', error);
            toast.error('Cunning Action failed');
        }
    }

    /**
     * Handle Ki Powers (Monk feature)
     * Opens Ki Powers modal for Flurry of Blows, Patient Defense, Step of the Wind, Stunning Strike
     */
    handleKiPowers() {
        if (!state.isPlayerTurn()) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];

        // Check Ki points available
        const kiPoints = player?.resources?.ki_points ?? player?.stats?.level ?? 0;
        if (kiPoints <= 0) {
            toast.warning('No Ki points remaining');
            return;
        }

        // Emit event to open Ki Powers modal
        eventBus.emit(EVENTS.KI_POWERS_REQUESTED);
    }

    /**
     * Handle Reckless Attack (Barbarian feature)
     * Gain advantage on melee STR attacks this turn, but enemies have advantage against you
     */
    async handleRecklessAttack() {
        if (!state.isPlayerTurn()) return;

        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const player = gameState.combatants[gameState.playerId];

        // Check if already reckless
        if (gameState.turn.isReckless || player?.conditions?.includes('reckless')) {
            toast.warning('Already using Reckless Attack!');
            return;
        }

        try {
            const response = await api.useClassFeature(combatId, 'reckless_attack', {
                combatant_id: gameState.playerId
            });

            if (response.success) {
                state.set('turn.isReckless', true);

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                state.addLogEntry({
                    type: 'class_feature',
                    actor: player?.name,
                    message: `${player?.name} attacks recklessly! Advantage on attacks, but attacks against them have advantage.`,
                });

                toast.success('Reckless Attack activated!');
                eventBus.emit(EVENTS.CLASS_FEATURE_USED, { feature: 'reckless_attack' });
            } else {
                toast.error(response.message || 'Failed to use Reckless Attack');
            }
        } catch (error) {
            console.error('[ActionBar] Reckless Attack failed:', error);
            toast.error('Reckless Attack failed');
        }
    }

    /**
     * Handle Channel Divinity (Cleric/Paladin feature)
     * Opens modal for Channel Divinity options based on class/subclass
     */
    async handleChannelDivinity() {
        if (!state.isPlayerTurn() || state.getState().turn.actionUsed) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const playerClass = (player?.stats?.class || '').toLowerCase();

        // Channel Divinity options vary by class and subclass
        // For now, emit event to open a selection modal
        eventBus.emit(EVENTS.CHANNEL_DIVINITY_REQUESTED, {
            player,
            playerClass,
            subclass: player?.stats?.subclass || player?.subclass
        });

        // If no modal system is set up, use a simple implementation
        if (!eventBus.listeners(EVENTS.CHANNEL_DIVINITY_REQUESTED)?.length) {
            // Default: Turn Undead for Clerics, basic Channel for Paladins
            await this.executeChannelDivinity(playerClass === 'cleric' ? 'turn_undead' : 'sacred_weapon');
        }
    }

    /**
     * Execute Channel Divinity with a specific option
     */
    async executeChannelDivinity(option) {
        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const player = gameState.combatants[gameState.playerId];

        try {
            const response = await api.useClassFeature(combatId, 'channel_divinity', {
                combatant_id: gameState.playerId,
                option: option
            });

            if (response.success) {
                state.set('turn.actionUsed', true);

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                state.addLogEntry({
                    type: 'class_feature',
                    actor: player?.name,
                    message: response.description || `${player?.name} channels divine energy!`,
                });

                toast.success('Channel Divinity used!');
                eventBus.emit(EVENTS.CLASS_FEATURE_USED, { feature: 'channel_divinity', option });
            } else {
                toast.error(response.message || 'Failed to use Channel Divinity');
            }
        } catch (error) {
            console.error('[ActionBar] Channel Divinity failed:', error);
            toast.error('Channel Divinity failed');
        }
    }

    /**
     * Handle Bardic Inspiration (Bard feature)
     * Grant an inspiration die to an ally (bonus action)
     */
    async handleBardicInspiration() {
        if (!state.isPlayerTurn() || state.getState().turn.bonusActionUsed) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];

        // Get list of allies to inspire
        const allies = Object.values(gameState.combatants)
            .filter(c => c.type === 'player' && c.id !== gameState.playerId && c.hp > 0);

        if (allies.length === 0) {
            toast.warning('No allies to inspire');
            return;
        }

        // If only one ally, inspire them directly
        if (allies.length === 1) {
            await this.executeBardicInspiration(allies[0].id);
            return;
        }

        // Multiple allies - enter targeting mode
        state.setSelectedAction('bardic_inspiration');
        eventBus.emit(EVENTS.TARGETING_STARTED, {
            actionType: 'bardic_inspiration',
            targetType: 'ally',
            message: 'Select an ally to inspire'
        });
    }

    /**
     * Execute Bardic Inspiration on a target
     */
    async executeBardicInspiration(targetId) {
        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const player = gameState.combatants[gameState.playerId];
        const target = gameState.combatants[targetId];

        try {
            const response = await api.useClassFeature(combatId, 'bardic_inspiration', {
                combatant_id: gameState.playerId,
                target_id: targetId
            });

            if (response.success) {
                state.set('turn.bonusActionUsed', true);

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                const dieSize = response.extra_data?.die_size || 'd6';
                state.addLogEntry({
                    type: 'class_feature',
                    actor: player?.name,
                    message: `${player?.name} inspires ${target?.name} with a ${dieSize} Bardic Inspiration die!`,
                });

                toast.success(`${target?.name} inspired!`);
                eventBus.emit(EVENTS.CLASS_FEATURE_USED, { feature: 'bardic_inspiration', target: targetId });
            } else {
                toast.error(response.message || 'Failed to use Bardic Inspiration');
            }
        } catch (error) {
            console.error('[ActionBar] Bardic Inspiration failed:', error);
            toast.error('Bardic Inspiration failed');
        } finally {
            state.setSelectedAction(null);
            state.exitTargetingMode();
        }
    }

    /**
     * Handle Metamagic (Sorcerer feature)
     * Opens modal to view/manage sorcery points and metamagic options
     */
    handleMetamagic() {
        if (!state.isPlayerTurn()) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];

        const sorceryPoints = player?.resources?.sorcery_points ?? 0;
        if (sorceryPoints <= 0) {
            toast.warning('No Sorcery Points remaining');
            return;
        }

        // Emit event to open Metamagic modal
        eventBus.emit(EVENTS.METAMAGIC_REQUESTED, {
            player,
            sorceryPoints,
            metamagicKnown: player?.resources?.metamagic_known || []
        });

        // If no modal handler, show info toast
        if (!eventBus.listeners(EVENTS.METAMAGIC_REQUESTED)?.length) {
            toast.info(`${sorceryPoints} Sorcery Points available. Metamagic is applied when casting spells.`);
        }
    }

    // ==================== Ranger Feature Handlers ====================

    /**
     * Handle Hunter's Mark (Ranger feature)
     * Mark a target for extra 1d6 damage on hits and advantage on Perception/Survival to track
     */
    async handleHuntersMark() {
        if (!state.isPlayerTurn() || state.getState().turn.bonusActionUsed) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];

        // Check if already have Hunter's Mark active
        if (player?.conditions?.includes('hunters_mark_active')) {
            toast.warning("Hunter's Mark is already active. Attack the marked target for bonus damage!");
            return;
        }

        // Start targeting mode to select a target
        this.targetingSystem.startTargeting('enemy', async (target) => {
            await this.executeHuntersMark(target);
        }, {
            range: 90, // 90ft range
            prompt: "Select a target for Hunter's Mark (1d6 bonus damage on hits)"
        });
    }

    /**
     * Execute Hunter's Mark on target
     */
    async executeHuntersMark(target) {
        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const player = gameState.combatants[gameState.playerId];

        try {
            const response = await api.useClassFeature(combatId, 'hunters_mark', {
                combatant_id: gameState.playerId,
                target_id: target.id
            });

            if (response.success) {
                state.set('turn.bonusActionUsed', true);

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                state.addLogEntry({
                    type: 'class_feature',
                    actor: player?.name,
                    message: `${player?.name} marks ${target.name} with Hunter's Mark! +1d6 damage on hits.`,
                });

                toast.success(`Hunter's Mark on ${target.name}!`);
                eventBus.emit(EVENTS.CLASS_FEATURE_USED, { feature: 'hunters_mark', target: target.id });
            } else {
                toast.error(response.message || "Failed to cast Hunter's Mark");
            }
        } catch (error) {
            console.error("[ActionBar] Hunter's Mark failed:", error);
            toast.error("Hunter's Mark failed");
        }
    }

    /**
     * Handle Favored Foe (Ranger 2024 feature)
     * Mark a creature for extra 1d4-1d6 damage on first hit per turn
     */
    async handleFavoredFoe() {
        if (!state.isPlayerTurn()) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];

        // Check uses remaining
        const usesRemaining = player?.resources?.favored_foe_uses ?? 0;
        if (usesRemaining <= 0) {
            toast.warning('No Favored Foe uses remaining');
            return;
        }

        // Start targeting mode to select a target
        this.targetingSystem.startTargeting('enemy', async (target) => {
            await this.executeFavoredFoe(target);
        }, {
            range: 90, // Same range as Hunter's Mark
            prompt: "Select a Favored Foe (bonus damage on first hit per turn)"
        });
    }

    /**
     * Execute Favored Foe on target
     */
    async executeFavoredFoe(target) {
        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const player = gameState.combatants[gameState.playerId];

        try {
            const response = await api.useClassFeature(combatId, 'favored_foe', {
                combatant_id: gameState.playerId,
                target_id: target.id
            });

            if (response.success) {
                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                const damageBonus = player?.stats?.level >= 14 ? '1d6' : (player?.stats?.level >= 6 ? '1d6' : '1d4');
                state.addLogEntry({
                    type: 'class_feature',
                    actor: player?.name,
                    message: `${player?.name} marks ${target.name} as Favored Foe! +${damageBonus} damage on first hit per turn.`,
                });

                toast.success(`${target.name} is your Favored Foe!`);
                eventBus.emit(EVENTS.CLASS_FEATURE_USED, { feature: 'favored_foe', target: target.id });
            } else {
                toast.error(response.message || 'Failed to mark Favored Foe');
            }
        } catch (error) {
            console.error('[ActionBar] Favored Foe failed:', error);
            toast.error('Favored Foe failed');
        }
    }

    // ==================== Warlock Feature Handlers ====================

    /**
     * Handle Eldritch Blast (Warlock cantrip)
     * Force damage cantrip that scales with level and can be modified by invocations
     */
    async handleEldritchBlast() {
        if (!state.isPlayerTurn() || state.getState().turn.actionUsed) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const level = player?.stats?.level || player?.level || 1;

        // Calculate number of beams (1 at level 1, 2 at 5, 3 at 11, 4 at 17)
        let beams = 1;
        if (level >= 17) beams = 4;
        else if (level >= 11) beams = 3;
        else if (level >= 5) beams = 2;

        // Check for Eldritch Invocations that modify the blast
        const invocations = player?.resources?.eldritch_invocations || [];
        const hasAgonizingBlast = invocations.includes('agonizing_blast');
        const hasRepellingBlast = invocations.includes('repelling_blast');

        // Start targeting mode
        this.targetingSystem.startTargeting('enemy', async (target) => {
            await this.executeEldritchBlast(target, beams, { hasAgonizingBlast, hasRepellingBlast });
        }, {
            range: 120, // 120ft range
            prompt: `Fire Eldritch Blast (${beams} beam${beams > 1 ? 's' : ''}, 1d10+${hasAgonizingBlast ? 'CHA' : '0'} force each)`
        });
    }

    /**
     * Execute Eldritch Blast on target
     */
    async executeEldritchBlast(target, beams, modifiers) {
        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const player = gameState.combatants[gameState.playerId];

        try {
            const response = await api.castSpell(combatId, gameState.playerId, 'eldritch_blast', {
                target_id: target.id,
                beams: beams,
                modifiers: modifiers
            });

            if (response.success) {
                state.set('turn.actionUsed', true);

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                const damage = response.extra_data?.total_damage || response.damage || 0;
                state.addLogEntry({
                    type: 'spell',
                    actor: player?.name,
                    message: `${player?.name} blasts ${target.name} with Eldritch Blast for ${damage} force damage!`,
                });

                toast.success(`Eldritch Blast hits for ${damage} damage!`);
                eventBus.emit(EVENTS.SPELL_CAST, { spell: 'eldritch_blast', target: target.id });
            } else {
                toast.error(response.message || 'Eldritch Blast missed');
            }
        } catch (error) {
            console.error('[ActionBar] Eldritch Blast failed:', error);
            toast.error('Eldritch Blast failed');
        }
    }

    /**
     * Handle Invocations (Warlock feature)
     * Opens modal to view and activate Eldritch Invocations
     */
    handleInvocations() {
        if (!state.isPlayerTurn()) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];

        const invocations = player?.resources?.eldritch_invocations || [];
        if (invocations.length === 0) {
            toast.warning('No Eldritch Invocations known');
            return;
        }

        // Emit event to open Invocations modal
        eventBus.emit(EVENTS.INVOCATIONS_REQUESTED, {
            player,
            invocations
        });

        // If no modal handler, show info toast
        if (!eventBus.listeners(EVENTS.INVOCATIONS_REQUESTED)?.length) {
            toast.info(`Active Invocations: ${invocations.join(', ')}`);
        }
    }

    /**
     * Handle Hex (Warlock spell)
     * Curse a target for 1d6 necrotic bonus damage and disadvantage on one ability
     */
    async handleHex() {
        if (!state.isPlayerTurn() || state.getState().turn.bonusActionUsed) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];

        // Check if already have Hex active
        if (player?.conditions?.includes('hex_active')) {
            toast.warning('Hex is already active. You can move it to another target when the current target dies.');
            return;
        }

        // Check Pact Magic slots
        const pactSlots = player?.resources?.pact_magic_slots ?? 0;
        if (pactSlots <= 0) {
            toast.warning('No Pact Magic slots remaining');
            return;
        }

        // Start targeting mode to select a target
        this.targetingSystem.startTargeting('enemy', async (target) => {
            await this.executeHex(target);
        }, {
            range: 90, // 90ft range
            prompt: "Select a target for Hex (1d6 necrotic bonus damage)"
        });
    }

    /**
     * Execute Hex on target
     */
    async executeHex(target) {
        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const player = gameState.combatants[gameState.playerId];

        try {
            const response = await api.castSpell(combatId, gameState.playerId, 'hex', {
                target_id: target.id
            });

            if (response.success) {
                state.set('turn.bonusActionUsed', true);

                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                state.addLogEntry({
                    type: 'spell',
                    actor: player?.name,
                    message: `${player?.name} hexes ${target.name}! +1d6 necrotic damage on hits.`,
                });

                toast.success(`Hex placed on ${target.name}!`);
                eventBus.emit(EVENTS.SPELL_CAST, { spell: 'hex', target: target.id });
            } else {
                toast.error(response.message || 'Failed to cast Hex');
            }
        } catch (error) {
            console.error('[ActionBar] Hex failed:', error);
            toast.error('Hex failed');
        }
    }

    /**
     * Execute a simple action (no target needed)
     */
    async executeSimpleAction(actionType, additionalData = {}) {
        if (!state.isPlayerTurn() || state.getState().turn.actionUsed) return;

        const gameState = state.getState();
        const combatId = gameState.combat.id;

        try {
            const response = await api.performAction(
                combatId,
                actionType,
                null,
                { extraData: additionalData }
            );

            if (response.success) {
                state.useAction();
                state.updateCombatState(response.combat_state || {});

                state.addLogEntry({
                    type: 'action',
                    actor: state.getState().combatants[gameState.playerId]?.name,
                    message: response.description,
                });

                eventBus.emit(EVENTS.ACTION_PERFORMED, { actionType, response });
            } else {
                state.addLogEntry({
                    type: 'error',
                    message: response.description || `${actionType} failed`,
                });
            }
        } catch (error) {
            console.error(`[ActionBar] ${actionType} failed:`, error);
            toast.error(`${actionType} failed`);
        }
    }

    /**
     * Handle Second Wind (Fighter bonus action)
     */
    async handleSecondWind() {
        if (!state.isPlayerTurn() || state.getState().turn.bonusActionUsed) return;

        const gameState = state.getState();
        const combatId = gameState.combat.id;

        try {
            const response = await api.performBonusAction(
                combatId,
                'second_wind'
            );

            if (response.success) {
                state.set('turn.bonusActionUsed', true);
                state.updateCombatState(response.combat_state || {});

                state.addLogEntry({
                    type: 'heal',
                    actor: state.getState().combatants[gameState.playerId]?.name,
                    message: `uses Second Wind and heals for ${response.extra_data?.healing || '?'} HP`,
                });
            }
        } catch (error) {
            console.error('[ActionBar] Second Wind failed:', error);
            toast.error('Second Wind failed');
        }
    }

    /**
     * Handle Off-Hand Attack (Two-Weapon Fighting bonus action)
     * D&D 5e: Attack with off-hand light weapon after attacking with main-hand light weapon
     */
    async handleOffhandAttack() {
        if (!state.isPlayerTurn() || state.getState().turn.bonusActionUsed) return;
        if (!state.getState().turn.canOffhandAttack) return;

        state.setSelectedAction('offhand');

        // Get light weapons for off-hand (exclude main hand weapon)
        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const lightWeapons = this.getLightWeapons(player);
        const mainHandWeapon = gameState.turn.mainHandWeapon;

        // Filter out main-hand weapon if needed
        const offhandWeapons = lightWeapons.filter(w => w.id !== mainHandWeapon);

        if (offhandWeapons.length === 0) {
            state.addLogEntry({
                type: 'error',
                message: 'No light weapons available for off-hand attack',
            });
            return;
        }

        if (offhandWeapons.length === 1) {
            // Only one weapon - skip selection
            this.selectedWeapon = offhandWeapons[0];
            this.startOffhandTargeting(this.selectedWeapon);
        } else {
            // Show weapon selection modal for off-hand
            this.showWeaponSelection(offhandWeapons, true);
        }
    }

    /**
     * Start targeting mode for off-hand attack
     * @param {Object} weapon - Selected off-hand weapon
     */
    startOffhandTargeting(weapon) {
        this.targetingSystem.startTargeting('melee', async (target) => {
            await this.executeOffhandAttack(target, weapon);
        });
    }

    /**
     * Execute off-hand attack on target
     * @param {Object} target - Target combatant
     * @param {Object} weapon - Selected off-hand weapon
     */
    async executeOffhandAttack(target, weapon) {
        const gameState = state.getState();
        const combatId = gameState.combat.id;

        try {
            const response = await api.performBonusAction(
                combatId,
                'offhand_attack',
                target.id,
                { weaponName: weapon.id || weapon.name }
            );

            if (response.success) {
                state.set('turn.bonusActionUsed', true);
                state.set('turn.canOffhandAttack', false);

                // Play dice roll animation
                console.log('[ActionBar] Off-hand attack response:', response);
                await diceRoller.playAttackSequence(response);

                // Update combat state
                state.updateCombatState(response.combat_state || {});

                // Log entry
                state.addLogEntry({
                    type: response.hit ? 'hit' : 'miss',
                    actor: state.getState().combatants[gameState.playerId]?.name,
                    target: target.name,
                    damage: response.damage_dealt,
                    message: `Off-hand: ${response.description}`,
                });

                // Emit attack resolved with target_id for animations
                eventBus.emit(EVENTS.ATTACK_RESOLVED, {
                    ...response,
                    target_id: target.id,
                    target_name: target.name,
                });
            } else {
                state.addLogEntry({
                    type: 'error',
                    message: response.description || 'Off-hand attack failed',
                });
            }
        } catch (error) {
            console.error('[ActionBar] Off-hand attack failed:', error);
            toast.error('Off-hand attack failed');
            state.addLogEntry({
                type: 'error',
                message: 'Off-hand attack failed: ' + error.message,
            });
        }

        state.setSelectedAction(null);
    }

    /**
     * Handle Use Item (Bonus Action)
     * D&D 2024: Using a consumable item (potion, scroll) is a bonus action
     * Opens a quick-use menu showing available consumables
     */
    async handleUseItem() {
        if (!state.isPlayerTurn() || state.getState().turn.bonusActionUsed) return;

        const gameState = state.getState();
        const player = gameState.combatants[gameState.playerId];
        const inventory = player?.inventory || [];

        // Get consumable items from inventory
        const consumables = inventory.filter(item =>
            item.type === 'consumable' || item.item_type === 'consumable'
        );

        if (consumables.length === 0) {
            toast.warning('No consumable items available');
            return;
        }

        // Show consumable selection modal
        try {
            const selectedItem = await this.showConsumableSelection(consumables);
            if (selectedItem) {
                await this.executeUseItem(selectedItem);
            }
        } catch (error) {
            // User cancelled selection
            console.log('[ActionBar] Use Item cancelled');
        }
    }

    /**
     * Show consumable item selection modal
     * @param {Array} consumables - Available consumable items
     * @returns {Promise<Object>} Selected item or rejects if cancelled
     */
    showConsumableSelection(consumables) {
        return new Promise((resolve, reject) => {
            // Create or get modal
            let modal = document.getElementById('consumable-select-modal');
            if (!modal) {
                modal = this.createConsumableSelectModal();
            }

            const container = modal.querySelector('.consumable-options');

            // Populate consumable options
            container.innerHTML = consumables.map(item => `
                <button class="consumable-btn" data-id="${escapeHtml(item.id || item.item_id)}">
                    <span class="consumable-icon">${escapeHtml(item.icon) || '🧪'}</span>
                    <div class="consumable-info">
                        <span class="consumable-name">${escapeHtml(item.name)}</span>
                        <span class="consumable-desc">${escapeHtml(item.description || item.effect || 'Use this item')}</span>
                    </div>
                    ${item.quantity > 1 ? `<span class="consumable-qty">x${item.quantity}</span>` : ''}
                </button>
            `).join('');

            // Handle consumable selection
            const handleClick = (e) => {
                const btn = e.target.closest('.consumable-btn');
                if (!btn) return;

                const itemId = btn.dataset.id;
                const selected = consumables.find(c => (c.id || c.item_id) === itemId);

                cleanup();
                modal.classList.remove('show');
                resolve(selected);
            };

            // Handle cancel
            const handleCancel = () => {
                cleanup();
                modal.classList.remove('show');
                reject(new Error('Cancelled'));
            };

            // Handle ESC key
            const handleEsc = (e) => {
                if (e.key === 'Escape') {
                    handleCancel();
                }
            };

            // Cleanup function
            const cleanup = () => {
                container.removeEventListener('click', handleClick);
                document.removeEventListener('keydown', handleEsc);
                const cancelBtn = modal.querySelector('.cancel-btn');
                if (cancelBtn) cancelBtn.removeEventListener('click', handleCancel);
            };

            // Set up event listeners
            container.addEventListener('click', handleClick);
            document.addEventListener('keydown', handleEsc);

            const cancelBtn = modal.querySelector('.cancel-btn');
            if (cancelBtn) cancelBtn.addEventListener('click', handleCancel);

            // Show modal
            modal.classList.add('show');
        });
    }

    /**
     * Create consumable selection modal element
     * @returns {HTMLElement} Modal element
     */
    createConsumableSelectModal() {
        const modal = document.createElement('div');
        modal.id = 'consumable-select-modal';
        modal.className = 'modal consumable-select-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>🍾 Use Item</h3>
                <p class="modal-subtitle">Select a consumable to use (Bonus Action):</p>
                <div class="consumable-options"></div>
                <button class="cancel-btn">Cancel</button>
            </div>
        `;

        // Add styles if not present
        if (!document.getElementById('consumable-select-modal-styles')) {
            const style = document.createElement('style');
            style.id = 'consumable-select-modal-styles';
            style.textContent = `
                .consumable-select-modal {
                    display: none;
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0, 0, 0, 0.7);
                    z-index: 1000;
                    align-items: center;
                    justify-content: center;
                }
                .consumable-select-modal.show {
                    display: flex;
                }
                .consumable-select-modal .modal-content {
                    background: linear-gradient(135deg, #2a1a0a, #1a0f05);
                    border: 2px solid #8b7355;
                    border-radius: 8px;
                    padding: 24px;
                    min-width: 350px;
                    max-width: 450px;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
                }
                .consumable-select-modal h3 {
                    color: #d4af37;
                    margin: 0 0 8px 0;
                    text-align: center;
                    font-size: 1.5em;
                }
                .consumable-select-modal .modal-subtitle {
                    color: #c9b896;
                    text-align: center;
                    margin-bottom: 16px;
                    font-size: 0.9em;
                }
                .consumable-select-modal .consumable-options {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                    margin-bottom: 16px;
                    max-height: 300px;
                    overflow-y: auto;
                }
                .consumable-select-modal .consumable-btn {
                    background: linear-gradient(135deg, #3d2817, #2a1a0a);
                    border: 1px solid #6b5344;
                    border-radius: 6px;
                    padding: 12px;
                    text-align: left;
                    cursor: pointer;
                    transition: all 0.2s;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }
                .consumable-select-modal .consumable-btn:hover {
                    background: linear-gradient(135deg, #4d3827, #3a2a1a);
                    border-color: #d4af37;
                    transform: translateX(4px);
                }
                .consumable-select-modal .consumable-icon {
                    font-size: 1.8em;
                    min-width: 40px;
                    text-align: center;
                }
                .consumable-select-modal .consumable-info {
                    flex: 1;
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                }
                .consumable-select-modal .consumable-name {
                    color: #e8dcc8;
                    font-weight: bold;
                    font-size: 1em;
                }
                .consumable-select-modal .consumable-desc {
                    color: #9a8873;
                    font-size: 0.85em;
                }
                .consumable-select-modal .consumable-qty {
                    color: #d4af37;
                    font-weight: bold;
                    font-size: 0.9em;
                    background: rgba(212, 175, 55, 0.2);
                    padding: 2px 8px;
                    border-radius: 4px;
                }
                .consumable-select-modal .cancel-btn {
                    display: block;
                    width: 100%;
                    padding: 10px;
                    background: linear-gradient(135deg, #5a3a2a, #3a1a0a);
                    border: 1px solid #6b5344;
                    border-radius: 4px;
                    color: #c9b896;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                .consumable-select-modal .cancel-btn:hover {
                    background: linear-gradient(135deg, #6a4a3a, #4a2a1a);
                }
            `;
            document.head.appendChild(style);
        }

        document.body.appendChild(modal);
        return modal;
    }

    /**
     * Execute using a consumable item
     * @param {Object} item - The item to use
     */
    async executeUseItem(item) {
        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const playerId = gameState.playerId;

        try {
            const response = await api.useItem(combatId, playerId, item.id || item.item_id);

            if (response.success) {
                state.set('turn.bonusActionUsed', true);

                // Update combat state
                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                // Remove item from local inventory state
                const player = gameState.combatants[playerId];
                if (player?.inventory) {
                    const itemIndex = player.inventory.findIndex(i =>
                        (i.id || i.item_id) === (item.id || item.item_id)
                    );
                    if (itemIndex >= 0) {
                        if (player.inventory[itemIndex].quantity > 1) {
                            player.inventory[itemIndex].quantity--;
                        } else {
                            player.inventory.splice(itemIndex, 1);
                        }
                        state.set(`combatants.${playerId}.inventory`, [...player.inventory]);
                    }
                }

                // Log the item use
                const effect = response.effect || {};
                const playerName = gameState.combatants[playerId]?.name || 'You';

                if (effect.healing || effect.rolled) {
                    const healAmount = effect.healing || effect.rolled || 0;
                    state.addLogEntry({
                        type: 'heal',
                        actor: playerName,
                        message: `${playerName} uses ${item.name} and recovers ${healAmount} HP!`,
                    });
                    toast.success(`Healed ${healAmount} HP!`);

                    // Emit heal event for animations
                    eventBus.emit(EVENTS.COMBATANT_HEALED, {
                        combatantId: playerId,
                        amount: healAmount,
                        newHp: effect.new_hp,
                        maxHp: effect.max_hp,
                    });
                } else {
                    state.addLogEntry({
                        type: 'action',
                        actor: playerName,
                        message: `${playerName} uses ${item.name}.`,
                    });
                    toast.success(`Used ${item.name}!`);
                }

                eventBus.emit(EVENTS.ITEM_USED, { item, effect: response.effect });
            } else {
                toast.error(response.message || `Failed to use ${item.name}`);
            }
        } catch (error) {
            console.error('[ActionBar] Use item failed:', error);
            toast.error(`Failed to use ${item.name}: ` + error.message);
        }
    }

    /**
     * Handle Use Potion (Bonus Action) - Legacy method for direct potion use
     * D&D 2024: Drinking a potion is a bonus action
     */
    async handleUsePotion() {
        if (!state.isPlayerTurn() || state.getState().turn.bonusActionUsed) return;

        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const playerId = gameState.playerId;

        try {
            const response = await api.useItem(combatId, playerId, 'potion_of_healing');

            if (response.success) {
                state.set('turn.bonusActionUsed', true);

                // Update combat state
                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                // Log the healing
                const effect = response.effect || {};
                const healAmount = effect.rolled || 0;
                const playerName = gameState.combatants[playerId]?.name || 'You';

                state.addLogEntry({
                    type: 'heal',
                    actor: playerName,
                    message: `${playerName} drinks a Potion of Healing and recovers ${healAmount} HP! (${effect.old_hp} → ${effect.new_hp})`,
                });

                toast.success(`Healed ${healAmount} HP!`);

                // Emit heal event for animations
                eventBus.emit(EVENTS.COMBATANT_HEALED, {
                    combatantId: playerId,
                    amount: healAmount,
                    newHp: effect.new_hp,
                    maxHp: effect.max_hp,
                });
            } else {
                toast.error(response.message || 'Failed to use potion');
            }
        } catch (error) {
            console.error('[ActionBar] Use potion failed:', error);
            toast.error('Failed to use potion: ' + error.message);
        }
    }

    /**
     * Handle End Turn
     */
    async handleEndTurn() {
        if (!state.isPlayerTurn()) return;

        const gameState = state.getState();
        const combatId = gameState.combat.id;

        try {
            const response = await api.endTurn(combatId);

            if (response.success) {
                eventBus.emit(EVENTS.TURN_ENDED, {
                    combatantId: gameState.playerId,
                });

                // Animate enemy actions one-by-one before updating state
                if (response.enemy_actions && response.enemy_actions.length > 0) {
                    await this.playEnemyTurns(response.enemy_actions);
                }

                // Update state with combat state from response
                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                } else {
                    // Fallback: update turn index directly
                    state.set('combat.currentTurnIndex', response.current_turn_index || 0);
                }

                // Check if combat is over
                if (response.combat_over) {
                    state.addLogEntry({
                        type: 'combat_end',
                        message: `Combat ended: ${response.combat_result || 'unknown outcome'}`,
                    });
                    eventBus.emit(EVENTS.COMBAT_ENDED, {
                        result: response.combat_result,
                    });
                } else {
                    // Emit turn started for next combatant (should be player again)
                    const newState = state.getState();
                    const nextId = newState.initiative[newState.combat.currentTurnIndex];
                    eventBus.emit(EVENTS.TURN_STARTED, {
                        combatantId: nextId,
                    });

                    // If it's back to player's turn, reset turn resources and refresh movement
                    if (state.isPlayerTurn()) {
                        state.resetTurn();  // Reset action, bonus action, movement for new turn
                        this.refreshPlayerMovement();
                    }
                }
            }
        } catch (error) {
            console.error('[ActionBar] End turn failed:', error);
            toast.error('Failed to end turn');
            state.addLogEntry({
                type: 'error',
                message: 'Failed to end turn: ' + error.message,
            });
        }
    }

    // ==================== Rest Actions ====================

    /**
     * Handle Short Rest
     * Short rests restore hit dice and some class resources (Fighter's Second Wind, Warlock spell slots, etc.)
     */
    async handleShortRest() {
        const gameState = state.getState();
        const combatId = gameState.combat?.id;
        const playerId = gameState.playerId;
        const isInCombat = gameState.mode === GameMode.COMBAT && gameState.combat?.active;

        // Check if in active combat - warn but allow
        if (isInCombat) {
            const confirm = window.confirm(
                'Taking a short rest during combat is unusual. Are you sure you want to continue?\n\n' +
                'Short rests typically happen between encounters.'
            );
            if (!confirm) return;
        }

        try {
            // For now, spend 0 hit dice - in a full implementation, we'd show a modal to choose
            const response = await api.shortRest(combatId, playerId, 0);

            if (response.success) {
                // Show what was recovered
                const recovered = response.recovered || {};
                let message = 'Short rest complete!';
                const recoveryItems = [];

                if (recovered.hit_dice_spent > 0) {
                    recoveryItems.push(`${recovered.hp_healed} HP restored (${recovered.hit_dice_spent} hit dice)`);
                }
                if (recovered.second_wind_restored) {
                    recoveryItems.push('Second Wind restored');
                }
                if (recovered.action_surge_restored) {
                    recoveryItems.push('Action Surge restored');
                }
                if (recovered.superiority_dice_restored > 0) {
                    recoveryItems.push(`${recovered.superiority_dice_restored} Superiority Dice restored`);
                }
                if (recovered.warlock_slots_restored > 0) {
                    recoveryItems.push(`${recovered.warlock_slots_restored} Pact Magic slots restored`);
                }
                if (recovered.ki_points_restored > 0) {
                    recoveryItems.push(`${recovered.ki_points_restored} Ki points restored`);
                }
                if (recovered.channel_divinity_restored > 0) {
                    recoveryItems.push('Channel Divinity restored');
                }

                if (recoveryItems.length > 0) {
                    message += '\n' + recoveryItems.join('\n');
                }

                toast.success(message);
                state.addLogEntry({
                    type: 'rest',
                    message: `Short rest: ${recoveryItems.length > 0 ? recoveryItems.join(', ') : 'No resources to restore'}`,
                });

                // Update combat state if provided
                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                eventBus.emit(EVENTS.REST_COMPLETED, { type: 'short', recovered });
            } else {
                toast.error(response.message || 'Short rest failed');
            }
        } catch (error) {
            console.error('[ActionBar] Short rest failed:', error);
            toast.error('Short rest failed: ' + error.message);
        }
    }

    /**
     * Handle Long Rest
     * Long rests fully restore HP, spell slots, and all class resources
     */
    async handleLongRest() {
        const gameState = state.getState();
        const combatId = gameState.combat?.id;
        const playerId = gameState.playerId;
        const isInCombat = gameState.mode === GameMode.COMBAT && gameState.combat?.active;

        // Check if in active combat - strongly discourage
        if (isInCombat) {
            const confirm = window.confirm(
                'You cannot take a long rest during active combat!\n\n' +
                'Long rests require 8 hours of rest in a safe location.\n\n' +
                'Continue anyway for testing purposes?'
            );
            if (!confirm) return;
        }

        try {
            const response = await api.longRest(combatId, playerId);

            if (response.success) {
                // Show what was recovered
                const recovered = response.recovered || {};
                let message = 'Long rest complete! Full recovery!';
                const recoveryItems = [];

                if (recovered.hp_healed > 0) {
                    recoveryItems.push(`${recovered.hp_healed} HP restored to full`);
                }
                if (recovered.spell_slots_restored > 0) {
                    recoveryItems.push('All spell slots restored');
                }
                if (recovered.hit_dice_restored > 0) {
                    recoveryItems.push(`${recovered.hit_dice_restored} hit dice restored`);
                }
                if (recovered.class_resources_restored) {
                    recoveryItems.push('All class resources restored');
                }

                toast.success(message);
                state.addLogEntry({
                    type: 'rest',
                    message: `Long rest: Full recovery! ${recoveryItems.join(', ')}`,
                });

                // Update combat state if provided
                if (response.combat_state) {
                    state.updateCombatState(response.combat_state);
                }

                eventBus.emit(EVENTS.REST_COMPLETED, { type: 'long', recovered });
            } else {
                toast.error(response.message || 'Long rest failed');
            }
        } catch (error) {
            console.error('[ActionBar] Long rest failed:', error);
            toast.error('Long rest failed: ' + error.message);
        }
    }

    /**
     * Play enemy turn animations one-by-one with BG3-style dice rolls
     * @param {Array} enemyActions - Array of enemy action objects
     */
    async playEnemyTurns(enemyActions) {
        const banner = document.getElementById('enemy-turn-banner');
        const nameEl = document.getElementById('enemy-turn-name');
        const actionTextEl = document.getElementById('enemy-action-text');

        if (!banner || !nameEl || !actionTextEl) {
            // Fallback: just log to combat log
            for (const action of enemyActions) {
                state.addLogEntry({
                    type: action.hit ? 'enemy_hit' : 'enemy_action',
                    message: action.description,
                });
            }
            return;
        }

        // Group actions by enemy
        const actionsByEnemy = {};
        for (const action of enemyActions) {
            const enemyId = action.enemy_id;
            if (!actionsByEnemy[enemyId]) {
                actionsByEnemy[enemyId] = {
                    name: action.enemy_name,
                    actions: []
                };
            }
            actionsByEnemy[enemyId].actions.push(action);
        }

        // Play each enemy's turn
        for (const [enemyId, enemyData] of Object.entries(actionsByEnemy)) {
            // Show the enemy turn banner
            nameEl.textContent = enemyData.name;
            actionTextEl.textContent = '';
            actionTextEl.className = 'enemy-action-text';
            banner.classList.remove('hidden', 'hiding');

            // Wait for banner entrance
            await this.delay(400);

            // Play each action for this enemy
            for (const action of enemyData.actions) {
                if (action.action_type === 'move' && action.movement_path) {
                    // ANIMATE MOVEMENT
                    actionTextEl.textContent = 'Moving...';
                    actionTextEl.className = 'enemy-action-text move';

                    // Emit movement event for grid animation
                    eventBus.emit(EVENTS.MOVEMENT_STARTED, {
                        combatantId: action.enemy_id,
                        from: { x: action.old_position[0], y: action.old_position[1] },
                        path: action.movement_path.map(p => ({ x: p[0], y: p[1] }))
                    });

                    // Wait for movement animation (150ms per step)
                    const moveTime = action.movement_path.length * 150;
                    await this.delay(moveTime + 200);

                    // FIX: Update enemy position in state AFTER animation completes
                    // This prevents the token from snapping back to old position
                    const finalPos = action.movement_path[action.movement_path.length - 1];
                    state.updatePosition(action.enemy_id, finalPos[0], finalPos[1]);

                    // Log to combat log
                    state.addLogEntry({
                        type: 'enemy_action',
                        message: action.description,
                    });

                } else if (action.action_type === 'attack') {
                    // ANIMATE ATTACK WITH DICE
                    const targetName = this.getTargetName(action.target_id);
                    actionTextEl.textContent = `Attacking ${targetName}...`;
                    actionTextEl.className = 'enemy-action-text attack';

                    // Show enemy dice roll animation
                    await diceRoller.showEnemyAttackSequence(action.enemy_name, action);

                    // Emit attack event for grid animation (projectile, damage numbers)
                    eventBus.emit(EVENTS.ATTACK_RESOLVED, {
                        attacker_id: action.enemy_id,
                        target_id: action.target_id,
                        hit: action.hit,
                        critical: action.critical,
                        damage: action.damage_dealt
                    });

                    // Update action text with result
                    actionTextEl.textContent = action.description;
                    actionTextEl.className = `enemy-action-text attack ${action.hit ? 'hit' : 'miss'}`;

                    // Log to combat log
                    state.addLogEntry({
                        type: action.hit ? 'enemy_hit' : 'enemy_action',
                        message: action.description,
                    });

                    await this.delay(500);
                } else {
                    // Other action types (none, etc.)
                    actionTextEl.textContent = action.description;
                    actionTextEl.className = 'enemy-action-text';

                    // Log to combat log
                    state.addLogEntry({
                        type: 'enemy_action',
                        message: action.description,
                    });

                    // Emit event for grid animation
                    eventBus.emit(EVENTS.ENEMY_ACTION, action);

                    await this.delay(800);
                }
            }

            // Hide banner with animation
            banner.classList.add('hiding');
            await this.delay(300);
            banner.classList.add('hidden');
            banner.classList.remove('hiding');

            // Brief pause between enemies
            await this.delay(200);
        }
    }

    /**
     * Get target name from combatant ID
     * @param {string} targetId - Target combatant ID
     * @returns {string} Target name
     */
    getTargetName(targetId) {
        if (!targetId) return 'unknown';
        const gameState = state.getState();
        const combatant = gameState.combatants[targetId];
        return combatant?.name || targetId;
    }

    /**
     * Simple delay helper
     * @param {number} ms - Milliseconds to wait
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Refresh player movement options after enemies move
     */
    async refreshPlayerMovement() {
        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const playerId = gameState.playerId;

        try {
            const response = await api.getReachableCells(combatId, playerId);
            if (response.reachable) {
                state.setReachableCells(response.reachable);
            }
        } catch (error) {
            console.error('[ActionBar] Failed to refresh movement:', error);
            // Don't show toast for movement refresh - it's a background operation
        }
    }
}

export default ActionBar;
