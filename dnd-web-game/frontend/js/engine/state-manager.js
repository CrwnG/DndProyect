/**
 * D&D Combat Engine - State Manager
 * Centralized state management for the game
 */

import { eventBus, EVENTS } from './event-bus.js';

/**
 * Game modes
 */
export const GameMode = {
    IDLE: 'idle',
    COMBAT: 'combat',
    TARGETING: 'targeting',
    AREA_TARGETING: 'area_targeting',
    MOVING: 'moving',
};

/**
 * Initial state
 */
const initialState = {
    // Game mode
    mode: GameMode.IDLE,

    // Combat state
    combat: {
        id: null,
        round: 1,
        phase: 'not_in_combat',
        currentTurnIndex: 0,
        legendary_creatures: [], // Legendary creatures with their actions
    },

    // Initiative order
    initiative: [],

    // Combatants (keyed by ID)
    combatants: {},

    // Grid state
    grid: {
        cells: [],          // 2D array of cell data
        positions: {},      // combatant_id -> {x, y}
        reachableCells: [], // List of {x, y} for current combatant
        attackTargets: [],  // List of combatant IDs that can be attacked
        selectedCell: null, // {x, y} or null
        hoveredCell: null,  // {x, y} or null
        pathPreview: [],    // List of {x, y} for movement path
        // Area targeting state
        areaTargeting: {
            active: false,
            shape: null,        // 'sphere', 'cone', 'line', 'cube', 'cylinder'
            radius: 0,          // Size of the area in feet
            range: 0,           // Max range from caster
            previewCells: [],   // Cells in the area preview
            spell: null,        // Current spell being cast
            slotLevel: null,    // Spell slot level
        },
        // Threat zone state (opportunity attack areas)
        threatZones: {},        // enemy_id -> {name, reach, cells: [{x,y}]}
        showThreatZones: false, // Toggle for displaying threat zones
    },

    // Current turn state
    turn: {
        combatantId: null,
        actionUsed: false,
        bonusActionUsed: false,
        reactionUsed: false,
        movementRemaining: 30,
        movementUsed: 0,
        // Extra Attack tracking (D&D 5e)
        attacksRemaining: 1,
        maxAttacks: 1,
        // Two-Weapon Fighting tracking (D&D 5e)
        canOffhandAttack: false,
        mainHandWeapon: null,
        // Object Interaction (for weapon switching, D&D 5e)
        objectInteractionUsed: false,
    },

    // UI state
    ui: {
        selectedAction: null,
        targetingMode: false,
        targetType: null,   // 'melee', 'ranged', 'spell'
        movementModeActive: false,  // Must click Move button to enable movement
        showingModal: null,
        combatLog: [],
    },

    // Player's controlled combatants (array for multi-character parties)
    playerIds: [],
};

class StateManager {
    constructor() {
        this.state = JSON.parse(JSON.stringify(initialState));
        this.subscribers = new Set();
    }

    /**
     * Get current state (read-only copy)
     */
    getState() {
        const stateCopy = JSON.parse(JSON.stringify(this.state));
        // Add backwards-compatible playerId property
        // Returns current combatant ID if they're a player, otherwise first player ID
        const playerIds = this.state.playerIds || [];
        const currentCombatant = this.getCurrentCombatant();
        if (currentCombatant && playerIds.includes(currentCombatant.id)) {
            stateCopy.playerId = currentCombatant.id;
        } else {
            stateCopy.playerId = playerIds[0] || null;
        }
        return stateCopy;
    }

    /**
     * Get a specific part of state
     */
    get(path) {
        const parts = path.split('.');
        let value = this.state;
        for (const part of parts) {
            if (value === undefined) return undefined;
            value = value[part];
        }
        return value;
    }

    /**
     * Set a specific part of state
     */
    set(path, value) {
        const parts = path.split('.');
        let target = this.state;
        for (let i = 0; i < parts.length - 1; i++) {
            if (target[parts[i]] === undefined) {
                target[parts[i]] = {};
            }
            target = target[parts[i]];
        }
        target[parts[parts.length - 1]] = value;
        this.notifySubscribers();
    }

    /**
     * Update multiple state values
     */
    update(updates) {
        for (const [path, value] of Object.entries(updates)) {
            this.set(path, value);
        }
    }

    /**
     * Subscribe to state changes
     */
    subscribe(callback) {
        this.subscribers.add(callback);
        return () => this.subscribers.delete(callback);
    }

    /**
     * Notify all subscribers of state change
     */
    notifySubscribers() {
        this.subscribers.forEach(callback => {
            try {
                callback(this.getState());
            } catch (error) {
                console.error('[StateManager] Error in subscriber:', error);
            }
        });
    }

    /**
     * Reset to initial state
     */
    reset() {
        this.state = JSON.parse(JSON.stringify(initialState));
        this.notifySubscribers();
    }

    // ==================== Combat State Methods ====================

    /**
     * Initialize combat state
     */
    initCombat(combatData) {
        console.log('[StateManager] initCombat called with:', {
            combat_id: combatData.combat_id,
            current_turn_index: combatData.current_turn_index,
            initiative_order: combatData.initiative_order,
            combatants: combatData.combatants?.map(c => ({ id: c.id, name: c.name, type: c.type })),
            playerIds_before: this.state.playerIds,
        });

        this.state.mode = GameMode.COMBAT;
        this.state.combat = {
            id: combatData.combat_id,
            round: combatData.round || 1,
            phase: combatData.phase || 'in_combat',
            currentTurnIndex: combatData.current_turn_index || 0,
        };

        // Set up combatants
        this.state.combatants = {};
        if (combatData.combatants) {
            for (const c of combatData.combatants) {
                this.state.combatants[c.id] = {
                    id: c.id,
                    name: c.name,
                    type: c.type || c.combatant_type || 'enemy', // Handle both field names
                    hp: c.current_hp,
                    maxHp: c.max_hp,
                    ac: c.ac,
                    speed: c.speed || 30,
                    initiativeRoll: c.initiative_roll,
                    isActive: c.is_active !== false,
                    conditions: c.conditions || [],
                    stats: c.stats || {},
                    // BG3-style equipment system
                    equipment: c.equipment || null,
                    abilities: c.abilities || {},
                    // Spellcasting data for caster classes (D&D 5e)
                    spellcasting: c.spellcasting || null,
                    // Inventory for consumables (potions, scrolls, etc.)
                    inventory: c.inventory || [],
                };
            }
        }

        // Set up initiative order - extract IDs if objects are provided
        const rawInitiative = combatData.initiative_order || [];
        this.state.initiative = rawInitiative.map(entry => {
            // Handle both string IDs and objects with 'id' property
            if (typeof entry === 'string') {
                return entry;
            }
            return entry.id || entry;
        });

        console.log('[StateManager] After setting up combatants:', {
            combatantKeys: Object.keys(this.state.combatants),
            combatantTypes: Object.fromEntries(
                Object.entries(this.state.combatants).map(([id, c]) => [id, c.type])
            ),
            initiative: this.state.initiative,
            currentTurnIndex: this.state.combat.currentTurnIndex,
            playerIds: this.state.playerIds,
        });

        // Set up positions
        console.log('[StateManager] Positions from combatData:', combatData.positions);
        this.state.grid.positions = combatData.positions || {};

        // Set up grid cells
        if (combatData.grid) {
            this.state.grid.cells = combatData.grid;
        }

        this.notifySubscribers();
        eventBus.emit(EVENTS.COMBAT_STARTED, this.getState());
    }

    /**
     * Update combat state from server response
     */
    updateCombatState(data) {
        if (data.round !== undefined) {
            this.state.combat.round = data.round;
        }
        if (data.current_turn_index !== undefined) {
            this.state.combat.currentTurnIndex = data.current_turn_index;
        }
        if (data.phase !== undefined) {
            this.state.combat.phase = data.phase;
        }
        if (data.legendary_creatures !== undefined) {
            this.state.combat.legendary_creatures = data.legendary_creatures;
        }
        if (data.positions) {
            this.state.grid.positions = data.positions;
        }

        // Update combatants
        if (data.combatants) {
            for (const c of data.combatants) {
                if (this.state.combatants[c.id]) {
                    const oldIsActive = this.state.combatants[c.id].isActive;
                    const newIsActive = c.is_active ?? oldIsActive;

                    Object.assign(this.state.combatants[c.id], {
                        hp: c.current_hp ?? this.state.combatants[c.id].hp,
                        isActive: newIsActive,
                        conditions: c.conditions ?? this.state.combatants[c.id].conditions,
                        // Update spellcasting if provided (spell slots may change)
                        spellcasting: c.spellcasting ?? this.state.combatants[c.id].spellcasting,
                        // Update AC if provided (in case equipment changed)
                        ac: c.ac ?? this.state.combatants[c.id].ac,
                        // Update inventory if provided (potions may be used)
                        inventory: c.inventory ?? this.state.combatants[c.id].inventory,
                    });

                    // Check if combatant was just defeated
                    if (oldIsActive && !newIsActive) {
                        eventBus.emit(EVENTS.COMBATANT_DEFEATED, {
                            combatantId: c.id,
                            name: this.state.combatants[c.id].name,
                        });
                    }
                }
            }
        }

        // Update turn state - PRESERVE existing fields like attacksRemaining, maxAttacks
        if (data.turn_state) {
            this.state.turn = {
                ...this.state.turn,  // Preserve attacksRemaining, maxAttacks, objectInteractionUsed, etc.
                combatantId: data.turn_state.combatant_id,
                actionUsed: data.turn_state.action_used || false,
                bonusActionUsed: data.turn_state.bonus_action_used || false,
                reactionUsed: data.turn_state.reaction_used || false,
                movementRemaining: data.turn_state.movement_remaining ?? this.state.turn.movementRemaining,
                movementUsed: data.turn_state.movement_used || 0,
            };
        }

        this.notifySubscribers();
        eventBus.emit(EVENTS.COMBAT_STATE_UPDATED, this.getState());
    }

    /**
     * Get current combatant
     */
    getCurrentCombatant() {
        const index = this.state.combat.currentTurnIndex;
        const initiativeLength = this.state.initiative.length;

        console.log('[StateManager] getCurrentCombatant:', {
            index,
            initiativeLength,
            initiative: this.state.initiative,
            combatantKeys: Object.keys(this.state.combatants),
        });

        if (index >= 0 && index < initiativeLength) {
            const id = this.state.initiative[index];
            const combatant = this.state.combatants[id];
            console.log('[StateManager] getCurrentCombatant found:', { id, combatant: combatant ? { id: combatant.id, name: combatant.name } : null });
            return combatant || null;  // Return null if combatant not found, not undefined
        }
        return null;
    }

    /**
     * Check if it's a player-controlled combatant's turn
     * Supports multiple player characters in the party
     */
    isPlayerTurn() {
        const current = this.getCurrentCombatant();
        const playerIds = this.state.playerIds || [];

        // Explicit boolean result
        if (!current || playerIds.length === 0) {
            console.log('[StateManager] isPlayerTurn: false (missing current or playerIds)', { current: !!current, playerIds });
            return false;
        }

        // Check if current combatant is one of the player-controlled characters
        const result = playerIds.includes(current.id);
        console.log('[StateManager] isPlayerTurn:', {
            currentId: current.id,
            currentName: current.name,
            playerIds,
            result,
        });

        return result;
    }

    /**
     * Get combatant at position
     * Handles both array [x,y] and object {x,y} position formats
     */
    getCombatantAtPosition(x, y) {
        for (const [id, pos] of Object.entries(this.state.grid.positions)) {
            // Handle both array [x,y] and object {x,y} formats
            const px = Array.isArray(pos) ? pos[0] : pos.x;
            const py = Array.isArray(pos) ? pos[1] : pos.y;
            if (px === x && py === y) {
                return this.state.combatants[id];
            }
        }
        return null;
    }

    // ==================== Grid State Methods ====================

    /**
     * Set reachable cells
     */
    setReachableCells(cells) {
        this.state.grid.reachableCells = cells;
        this.notifySubscribers();
        eventBus.emit(EVENTS.REACHABLE_CELLS_UPDATED, cells);
    }

    /**
     * Set attack targets
     */
    setAttackTargets(targetIds) {
        this.state.grid.attackTargets = targetIds;
        this.notifySubscribers();
    }

    /**
     * Set selected cell
     */
    setSelectedCell(cell) {
        this.state.grid.selectedCell = cell;
        this.notifySubscribers();
    }

    /**
     * Set hovered cell
     */
    setHoveredCell(cell) {
        this.state.grid.hoveredCell = cell;
        this.notifySubscribers();
    }

    /**
     * Set path preview
     */
    setPathPreview(path) {
        this.state.grid.pathPreview = path;
        this.notifySubscribers();
    }

    /**
     * Set threat zones data (enemy opportunity attack areas)
     */
    setThreatZones(zones) {
        this.state.grid.threatZones = zones || {};
        this.notifySubscribers();
        eventBus.emit(EVENTS.THREAT_ZONES_UPDATED, zones);
    }

    /**
     * Toggle threat zone display on/off
     * @param {boolean|null} show - If null, toggles current state
     */
    toggleThreatZoneDisplay(show = null) {
        this.state.grid.showThreatZones = show !== null ? show : !this.state.grid.showThreatZones;
        this.notifySubscribers();
        return this.state.grid.showThreatZones;
    }

    /**
     * Update combatant position
     */
    updatePosition(combatantId, x, y) {
        this.state.grid.positions[combatantId] = { x, y };
        this.notifySubscribers();
        eventBus.emit(EVENTS.COMBATANT_MOVED, { combatantId, x, y });
    }

    // ==================== UI State Methods ====================

    /**
     * Set selected action
     */
    setSelectedAction(action) {
        this.state.ui.selectedAction = action;
        this.notifySubscribers();
        eventBus.emit(EVENTS.ACTION_SELECTED, action);
    }

    /**
     * Enter targeting mode
     */
    enterTargetingMode(targetType) {
        this.state.mode = GameMode.TARGETING;
        this.state.ui.targetingMode = true;
        this.state.ui.targetType = targetType;
        this.notifySubscribers();
        eventBus.emit(EVENTS.TARGETING_STARTED, targetType);
    }

    /**
     * Exit targeting mode
     */
    exitTargetingMode() {
        this.state.mode = GameMode.COMBAT;
        this.state.ui.targetingMode = false;
        this.state.ui.targetType = null;
        this.state.grid.attackTargets = [];
        this.notifySubscribers();
        eventBus.emit(EVENTS.TARGETING_CANCELLED);
    }

    /**
     * Enter movement mode
     */
    enterMovementMode() {
        this.state.mode = GameMode.MOVING;
        this.notifySubscribers();
        // Note: MOVEMENT_STARTED event with actual data is emitted by movement-handler.js
        // Do not emit here without data - it causes "[CombatGrid] Movement started with no data" warning
    }

    /**
     * Exit movement mode
     */
    exitMovementMode() {
        this.state.mode = GameMode.COMBAT;
        // Don't clear reachableCells here - they're refreshed after movement
        // and we want to keep showing them for the player's turn
        this.state.grid.pathPreview = [];
        this.notifySubscribers();
    }

    /**
     * Enter area targeting mode for area spells
     * @param {Object} spell - The spell being cast
     * @param {number} slotLevel - The spell slot level
     * @param {string} shape - Area shape (sphere, cone, line, cube, cylinder)
     * @param {number} radius - Area size in feet
     * @param {number} range - Max range from caster in feet
     */
    enterAreaTargetingMode(spell, slotLevel, shape, radius, range) {
        this.state.mode = GameMode.AREA_TARGETING;
        this.state.ui.targetingMode = true;
        this.state.ui.targetType = 'area';
        this.state.grid.areaTargeting = {
            active: true,
            shape: shape,
            radius: radius,
            range: range,
            previewCells: [],
            spell: spell,
            slotLevel: slotLevel,
        };
        this.notifySubscribers();
        eventBus.emit(EVENTS.AREA_TARGETING_STARTED, { spell, shape, radius, range });
    }

    /**
     * Update area targeting preview cells based on hovered position
     * @param {Array} cells - Array of {x, y} cells in the preview
     */
    updateAreaPreview(cells) {
        this.state.grid.areaTargeting.previewCells = cells;
        this.notifySubscribers();
    }

    /**
     * Exit area targeting mode
     */
    exitAreaTargetingMode() {
        this.state.mode = GameMode.COMBAT;
        this.state.ui.targetingMode = false;
        this.state.ui.targetType = null;
        this.state.grid.areaTargeting = {
            active: false,
            shape: null,
            radius: 0,
            range: 0,
            previewCells: [],
            spell: null,
            slotLevel: null,
        };
        this.notifySubscribers();
        eventBus.emit(EVENTS.TARGETING_CANCELLED);
    }

    /**
     * Toggle movement mode (Move button clicked)
     * When active, player can click cells to move
     */
    toggleMovementModeActive() {
        this.state.ui.movementModeActive = !this.state.ui.movementModeActive;
        this.notifySubscribers();
        if (this.state.ui.movementModeActive) {
            eventBus.emit(EVENTS.MOVEMENT_MODE_ENABLED);
        } else {
            eventBus.emit(EVENTS.MOVEMENT_MODE_DISABLED);
            this.state.grid.pathPreview = [];
        }
    }

    /**
     * Set movement mode active state
     */
    setMovementModeActive(active) {
        this.state.ui.movementModeActive = active;
        this.notifySubscribers();
        if (active) {
            eventBus.emit(EVENTS.MOVEMENT_MODE_ENABLED);
        } else {
            eventBus.emit(EVENTS.MOVEMENT_MODE_DISABLED);
            this.state.grid.pathPreview = [];
        }
    }

    /**
     * Check if movement mode is active
     */
    isMovementModeActive() {
        return this.state.ui.movementModeActive;
    }

    /**
     * Add combat log entry
     */
    addLogEntry(entry) {
        this.state.ui.combatLog.unshift({
            id: Date.now(),
            timestamp: new Date().toISOString(),
            ...entry,
        });
        // Keep only last 50 entries
        if (this.state.ui.combatLog.length > 50) {
            this.state.ui.combatLog.pop();
        }
        this.notifySubscribers();
        eventBus.emit(EVENTS.UI_LOG_ENTRY, entry);
    }

    /**
     * Update action used
     */
    useAction() {
        this.state.turn.actionUsed = true;
        this.notifySubscribers();
    }

    /**
     * Update bonus action used
     */
    useBonusAction() {
        this.state.turn.bonusActionUsed = true;
        this.notifySubscribers();
    }

    /**
     * Reset turn resources for new turn (D&D rules)
     * Called when a player-controlled combatant's turn begins
     */
    resetTurn() {
        // Get the current combatant (whoever's turn it is)
        const current = this.getCurrentCombatant();
        const currentId = current?.id;
        const player = current;
        const speed = player?.stats?.speed || player?.speed || 30;

        // Calculate max attacks from class (Extra Attack)
        const playerClass = player?.stats?.class?.toLowerCase() || '';
        const playerLevel = player?.stats?.level || 1;
        let maxAttacks = 1;
        if (playerClass === 'fighter') {
            if (playerLevel >= 20) maxAttacks = 4;
            else if (playerLevel >= 11) maxAttacks = 3;
            else if (playerLevel >= 5) maxAttacks = 2;
        } else if (['paladin', 'ranger', 'barbarian', 'monk'].includes(playerClass)) {
            if (playerLevel >= 5) maxAttacks = 2;
        }

        this.state.turn = {
            combatantId: currentId,
            actionUsed: false,
            bonusActionUsed: false,
            reactionUsed: false,
            movementRemaining: speed,
            movementUsed: 0,
            // Extra Attack tracking (D&D 5e)
            attacksRemaining: maxAttacks,
            maxAttacks: maxAttacks,
            // Two-Weapon Fighting tracking (D&D 5e)
            canOffhandAttack: false,
            mainHandWeapon: null,
            // Object Interaction (for weapon switching, D&D 5e)
            objectInteractionUsed: false,
        };
        this.notifySubscribers();
        console.log('[StateManager] Turn reset for new player turn, max attacks:', maxAttacks);
    }

    /**
     * Update movement used
     */
    useMovement(amount) {
        this.state.turn.movementUsed += amount;
        this.state.turn.movementRemaining -= amount;
        this.notifySubscribers();
    }
}

// Export singleton instance
export const state = new StateManager();
export default state;
