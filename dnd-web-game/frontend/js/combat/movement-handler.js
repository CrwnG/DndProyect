/**
 * D&D Combat Engine - Movement Handler
 * Handles grid-based movement, pathfinding preview, and movement execution
 */

import { CONFIG } from '../config.js';
import { eventBus, EVENTS } from '../engine/event-bus.js';
import state, { GameMode } from '../engine/state-manager.js';
import api from '../api/api-client.js';

class MovementHandler {
    constructor() {
        this.isMoving = false;
        this.setupEventListeners();
    }

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Listen for cell clicks
        eventBus.on(EVENTS.CELL_CLICKED, this.handleCellClick.bind(this));

        // Listen for cell hover (for path preview)
        eventBus.on(EVENTS.CELL_HOVERED, this.handleCellHover.bind(this));

        // Listen for turn start to fetch reachable cells
        eventBus.on(EVENTS.TURN_STARTED, this.handleTurnStart.bind(this));
    }

    /**
     * Handle turn start - fetch reachable cells
     */
    async handleTurnStart(data) {
        if (state.isPlayerTurn()) {
            await this.fetchReachableCells();
        }
    }

    /**
     * Fetch reachable cells from the server
     */
    async fetchReachableCells() {
        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const currentCombatant = state.getCurrentCombatant();

        if (!combatId || !currentCombatant) return;

        try {
            const response = await api.getReachableCells(combatId, currentCombatant.id);
            if (response.reachable) {
                state.setReachableCells(response.reachable);
            }
        } catch (error) {
            console.error('[MovementHandler] Failed to fetch reachable cells:', error);
            eventBus.emit(EVENTS.ERROR_OCCURRED, { message: 'Failed to fetch movement options' });
        }
    }

    /**
     * Handle cell click
     */
    async handleCellClick(cell) {
        const gameState = state.getState();

        // Only handle movement if it's the player's turn and in combat mode
        if (!state.isPlayerTurn()) return;
        if (gameState.mode === GameMode.TARGETING) return;
        if (this.isMoving) return;

        // IMPORTANT: Only allow movement if movement mode is active (Move button clicked)
        // This prevents accidental movement when clicking on the grid
        if (!gameState.ui.movementModeActive) {
            // Check if clicked on a combatant (selection still works without movement mode)
            const combatant = state.getCombatantAtPosition(cell.x, cell.y);
            if (combatant) {
                eventBus.emit(EVENTS.COMBATANT_SELECTED, combatant);
            }
            return;
        }

        // Check if clicked cell is reachable
        const isReachable = gameState.grid.reachableCells.some(
            c => c.x === cell.x && c.y === cell.y
        );

        if (isReachable) {
            await this.moveToCell(cell);
            // Disable movement mode after moving (one-shot action)
            state.setMovementModeActive(false);
        } else {
            // Check if clicked on a combatant
            const combatant = state.getCombatantAtPosition(cell.x, cell.y);
            if (combatant) {
                eventBus.emit(EVENTS.COMBATANT_SELECTED, combatant);
            }
        }
    }

    /**
     * Handle cell hover - show path preview
     */
    handleCellHover(cell) {
        const gameState = state.getState();

        // Only show path preview in combat mode on player's turn
        if (!state.isPlayerTurn()) return;
        if (gameState.mode !== GameMode.COMBAT) return;

        // Only show path preview when movement mode is active
        if (!gameState.ui.movementModeActive) {
            state.setPathPreview([]);
            return;
        }

        // Check if hovered cell is reachable
        const isReachable = gameState.grid.reachableCells.some(
            c => c.x === cell.x && c.y === cell.y
        );

        if (isReachable) {
            const path = this.calculatePathPreview(cell);
            state.setPathPreview(path);
        } else {
            state.setPathPreview([]);
        }
    }

    /**
     * Calculate path preview from current position to target
     * Simple implementation - for actual pathfinding, use A* from backend
     */
    calculatePathPreview(target) {
        const currentCombatant = state.getCurrentCombatant();
        if (!currentCombatant) return [];

        const gameState = state.getState();
        const startPos = gameState.grid.positions[currentCombatant.id];
        if (!startPos) return [];

        // Simple straight line path (the backend handles actual pathfinding)
        const path = [];
        let x = startPos.x;
        let y = startPos.y;

        while (x !== target.x || y !== target.y) {
            if (x < target.x) x++;
            else if (x > target.x) x--;

            if (y < target.y) y++;
            else if (y > target.y) y--;

            path.push({ x, y });
        }

        return path;
    }

    /**
     * Move to a cell
     */
    async moveToCell(targetCell) {
        this.isMoving = true;
        state.enterMovementMode();

        const gameState = state.getState();
        const combatId = gameState.combat.id;
        const currentCombatant = state.getCurrentCombatant();

        // Save starting position BEFORE API call for animation
        const startPos = { ...gameState.grid.positions[currentCombatant.id] };
        const path = this.calculatePathPreview(targetCell);

        try {
            const response = await api.moveCombatant(
                combatId,
                currentCombatant.id,
                targetCell.x,
                targetCell.y
            );

            if (response.success) {
                // Emit event for animation BEFORE updating state
                // This allows the grid to animate the token smoothly
                eventBus.emit(EVENTS.MOVEMENT_STARTED, {
                    combatantId: currentCombatant.id,
                    from: startPos,
                    to: targetCell,
                    path: path,
                });

                // Small delay for animation to start before state updates
                // The grid will animate using animatingPositions map
                await new Promise(resolve => setTimeout(resolve, path.length * CONFIG.ANIMATION.MOVE_DURATION));

                // Update position in state (after animation)
                state.updatePosition(currentCombatant.id, targetCell.x, targetCell.y);

                // Update movement used
                if (response.distance) {
                    state.useMovement(response.distance);
                }

                // Add log entry
                state.addLogEntry({
                    type: 'movement',
                    actor: currentCombatant.name,
                    message: `moved to (${targetCell.x + 1}, ${targetCell.y + 1})`,
                });

                // Handle Opportunity Attacks (D&D 5e rule)
                // When moving away from hostile creatures, they may attack
                if (response.opportunity_attacks && response.opportunity_attacks.length > 0) {
                    await this.handleOpportunityAttacks(response.opportunity_attacks, currentCombatant);
                }

                // Refresh reachable cells
                await this.fetchReachableCells();

                eventBus.emit(EVENTS.MOVEMENT_COMPLETED, {
                    combatantId: currentCombatant.id,
                    from: startPos,
                    to: targetCell,
                });
            } else {
                state.addLogEntry({
                    type: 'error',
                    message: response.description || 'Movement failed',
                });
            }
        } catch (error) {
            console.error('[MovementHandler] Movement failed:', error);
            state.addLogEntry({
                type: 'error',
                message: 'Movement failed: ' + error.message,
            });
        } finally {
            this.isMoving = false;
            state.exitMovementMode();
            state.setPathPreview([]);
        }
    }

    /**
     * Handle opportunity attacks triggered by movement (D&D 5e)
     * @param {Array} attackerIds - List of enemy IDs that can make opportunity attacks
     * @param {Object} target - The combatant being attacked (the mover)
     */
    async handleOpportunityAttacks(attackerIds, target) {
        const gameState = state.getState();
        const combatId = gameState.combat?.id;

        // Validate required data before attempting opportunity attacks
        if (!combatId) {
            console.error('[MovementHandler] Cannot process opportunity attacks: no combat ID');
            return;
        }
        if (!target?.id) {
            console.error('[MovementHandler] Cannot process opportunity attacks: no target ID');
            return;
        }
        if (!attackerIds || attackerIds.length === 0) {
            return;
        }

        for (const attackerId of attackerIds) {
            // Validate attackerId
            if (!attackerId) {
                console.warn('[MovementHandler] Skipping opportunity attack: invalid attacker ID');
                continue;
            }

            // Try to find attacker in combatants map (may use different key format)
            let attacker = gameState.combatants[attackerId];

            // If not found directly, search by ID
            if (!attacker) {
                attacker = Object.values(gameState.combatants || {}).find(c => c.id === attackerId);
            }

            // Get attacker name for logging (even if we don't have full data)
            const attackerName = attacker?.name || attackerId;

            // Skip if attacker is not active (but still allow if we don't have the full object)
            if (attacker && !attacker.isActive) {
                console.log(`[MovementHandler] Skipping OA from ${attackerName}: not active`);
                continue;
            }

            // Log the opportunity attack
            state.addLogEntry({
                type: 'enemy_action',
                message: `${attackerName} makes an opportunity attack against ${target.name}!`,
            });

            // Call the reaction API to resolve the opportunity attack
            try {
                console.log('[MovementHandler] Attempting opportunity attack:', {
                    combatId,
                    attackerId,
                    targetId: target.id,
                    attackerName,
                    targetName: target?.name
                });

                const response = await api.useReaction(
                    combatId,
                    attackerId,           // reactor_id (enemy making the attack)
                    'opportunity_attack', // reaction_type
                    target.id             // trigger_source_id (player who moved)
                );

                if (response.success) {
                    const wasHit = response.damage_dealt > 0;

                    // Log the result
                    state.addLogEntry({
                        type: wasHit ? 'enemy_hit' : 'enemy_action',
                        message: response.description,
                    });

                    // Emit event for attack animation
                    eventBus.emit(EVENTS.OPPORTUNITY_ATTACK, {
                        attackerId: attackerId,
                        targetId: target.id,
                        hit: wasHit,
                        damage: response.damage_dealt,
                        description: response.description,
                    });

                    // Update combat state from response
                    if (response.combat_state) {
                        state.updateCombatState(response.combat_state);
                    }

                    // Small delay for attack animation
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
            } catch (error) {
                console.error('[MovementHandler] Opportunity attack failed:', error);
                // Log the error but continue with other opportunity attacks
                state.addLogEntry({
                    type: 'error',
                    message: `Opportunity attack from ${attackerName} failed`,
                });
            }
        }
    }

    /**
     * Calculate movement cost between two cells
     */
    calculateMovementCost(from, to, cells) {
        // Diagonal movement costs the same in 5e (optional: use 5-10-5 rule)
        const dx = Math.abs(to.x - from.x);
        const dy = Math.abs(to.y - from.y);

        // Get terrain at destination
        const destCell = cells?.[to.y]?.[to.x];
        const isDifficult = destCell?.terrain === 'difficult';

        const baseCost = Math.max(dx, dy) * CONFIG.RULES.MOVEMENT_COST_NORMAL;
        return isDifficult ? baseCost * 2 : baseCost;
    }

    /**
     * Check if movement is available
     */
    canMove() {
        const gameState = state.getState();
        return (
            state.isPlayerTurn() &&
            gameState.turn.movementRemaining > 0 &&
            gameState.mode === GameMode.COMBAT &&
            !this.isMoving
        );
    }

    /**
     * Get remaining movement display string
     */
    getRemainingMovementDisplay() {
        const gameState = state.getState();
        return `${gameState.turn.movementRemaining} ft`;
    }
}

export default MovementHandler;
