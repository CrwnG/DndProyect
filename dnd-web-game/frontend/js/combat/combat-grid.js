/**
 * D&D Combat Engine - Combat Grid
 * Canvas-based 8x8 grid rendering for tactical combat
 */

import { CONFIG } from '../config.js';
import { eventBus, EVENTS } from '../engine/event-bus.js';
import state, { GameMode } from '../engine/state-manager.js';
import api from '../api/api-client.js';
import toast from '../ui/toast-notification.js';

class CombatGrid {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');

        // Grid dimensions
        this.gridSize = CONFIG.GRID.SIZE;
        this.cellSize = CONFIG.GRID.CELL_SIZE;

        // Animation state
        this.animations = [];
        this.animationFrame = null;

        // Movement animation tracking
        this.animatingPositions = new Map(); // combatantId -> {x, y} animated position
        this.isAnimating = false;

        // Stacking detection
        this.stackedCells = new Map(); // "x,y" -> [{id, combatant}, ...]

        // Ground items tracking (dropped items on the grid)
        this.groundItems = new Map(); // "x,y" -> [items]

        // Create stacking tooltip element
        this.stackTooltip = document.createElement('div');
        this.stackTooltip.className = 'stack-tooltip hidden';
        this.canvas.parentElement.appendChild(this.stackTooltip);

        // Initialize
        this.setupEventListeners();
        this.subscribeToState();
    }

    /**
     * Set up mouse event listeners
     */
    setupEventListeners() {
        this.canvas.addEventListener('click', this.handleClick.bind(this));
        this.canvas.addEventListener('mousemove', this.handleMouseMove.bind(this));
        this.canvas.addEventListener('mouseleave', this.handleMouseLeave.bind(this));

        // Listen for movement animation events
        eventBus.on(EVENTS.MOVEMENT_STARTED, this.handleMovementStarted.bind(this));

        // Listen for attack animation events
        eventBus.on(EVENTS.ATTACK_RESOLVED, this.handleAttackResolved.bind(this));

        // Listen for opportunity attack events
        eventBus.on(EVENTS.OPPORTUNITY_ATTACK, this.handleOpportunityAttack.bind(this));

        // Listen for combatant defeated events
        eventBus.on(EVENTS.COMBATANT_DEFEATED, this.handleCombatantDefeated.bind(this));

        // Listen for item dropped events
        eventBus.on(EVENTS.ITEM_DROPPED, this.handleItemDropped.bind(this));
    }

    /**
     * Handle item dropped event - update ground items display
     */
    handleItemDropped(data) {
        console.log('[CombatGrid] Item dropped:', data);
        if (data && data.groundItems) {
            // Convert object to Map
            this.groundItems = new Map(Object.entries(data.groundItems));
            this.render();
        }
    }

    /**
     * Handle combatant defeated event - play death animation
     */
    async handleCombatantDefeated(data) {
        if (!data || !data.combatantId) return;

        const gameState = state.getState();
        const positions = gameState.grid.positions || {};
        const position = positions[data.combatantId];

        if (position) {
            await this.playDeathAnimation(position.x, position.y, data.name);
        }
    }

    /**
     * Handle opportunity attack event - show slash animation
     */
    async handleOpportunityAttack(data) {
        if (!data) return;

        const { attackerId, targetId, hit, damage, description } = data;
        const gameState = state.getState();
        const positions = gameState.grid.positions || {};

        // Get attacker and target positions
        const attackerPos = positions[attackerId];
        const targetPos = positions[targetId];

        if (!attackerPos || !targetPos) {
            console.warn('[CombatGrid] Cannot play OA animation - missing positions');
            return;
        }

        // Play the opportunity attack animation sequence
        await this.playOpportunityAttackAnimation(attackerPos, targetPos, hit, damage);
    }

    /**
     * Play opportunity attack animation sequence
     * @param {Object} attackerPos - Attacker grid position {x, y}
     * @param {Object} targetPos - Target grid position {x, y}
     * @param {boolean} hit - Whether the attack hit
     * @param {number} damage - Damage dealt (if hit)
     */
    async playOpportunityAttackAnimation(attackerPos, targetPos, hit, damage) {
        const attackerCanvas = this.gridToCanvas(attackerPos.x, attackerPos.y);
        const targetCanvas = this.gridToCanvas(targetPos.x, targetPos.y);
        const container = this.canvas.parentElement;

        // 1. Show warning pulse on attacker
        this.showOpportunityWarning(attackerPos.x, attackerPos.y);

        // 2. Show "OPPORTUNITY!" label
        const label = document.createElement('div');
        label.className = 'opportunity-label';
        label.textContent = 'OPPORTUNITY!';
        label.style.left = `${attackerCanvas.x}px`;
        label.style.top = `${attackerCanvas.y - 35}px`;
        container.appendChild(label);

        await new Promise(resolve => setTimeout(resolve, 200));

        // 3. Show slash effect on target
        this.showOpportunitySlash(targetPos.x, targetPos.y);

        await new Promise(resolve => setTimeout(resolve, 150));

        // 4. Show hit/miss result
        if (hit && damage > 0) {
            // Show impact and damage number
            this.showImpactEffect(targetPos.x, targetPos.y, false);
            this.showDamageNumber(targetPos.x, targetPos.y, damage, false, false);
        } else {
            // Show miss effect
            this.showMissEffect(targetPos.x, targetPos.y);
        }

        // 5. Clean up label after animation
        setTimeout(() => label.remove(), 1000);
    }

    /**
     * Show opportunity attack warning pulse on attacker
     * @param {number} gridX - Grid X coordinate
     * @param {number} gridY - Grid Y coordinate
     */
    showOpportunityWarning(gridX, gridY) {
        const center = this.gridToCanvas(gridX, gridY);
        const element = document.createElement('div');
        element.className = 'opportunity-warning';
        element.style.left = `${center.x - 25}px`;
        element.style.top = `${center.y - 25}px`;

        const container = this.canvas.parentElement;
        container.appendChild(element);

        setTimeout(() => element.remove(), 500);
    }

    /**
     * Show opportunity attack slash effect on target
     * @param {number} gridX - Grid X coordinate
     * @param {number} gridY - Grid Y coordinate
     */
    showOpportunitySlash(gridX, gridY) {
        const center = this.gridToCanvas(gridX, gridY);
        const element = document.createElement('div');
        element.className = 'opportunity-slash';
        element.style.left = `${center.x}px`;
        element.style.top = `${center.y}px`;

        const container = this.canvas.parentElement;
        container.appendChild(element);

        setTimeout(() => element.remove(), 400);
    }

    /**
     * Handle attack resolved event - trigger attack animation
     */
    async handleAttackResolved(data) {
        const gameState = state.getState();
        const positions = gameState.grid.positions || {};

        // Get attacker and target positions
        const attackerId = gameState.playerId; // Player attacked
        const targetId = data.target_id;

        const attackerPos = positions[attackerId];
        const targetPos = positions[targetId];

        if (attackerPos && targetPos) {
            // Play attack animation sequence
            await this.playAttackAnimation(attackerPos, targetPos, data);
        }
    }

    /**
     * Handle movement started event - trigger animation
     */
    handleMovementStarted(data) {
        // Null check for data object
        if (!data) {
            console.warn('[CombatGrid] Movement started with no data');
            return;
        }

        const { combatantId, from, path } = data;

        // Validate all required properties
        if (!combatantId) {
            console.warn('[CombatGrid] Movement started with no combatantId');
            return;
        }

        if (!from || typeof from.x !== 'number' || typeof from.y !== 'number') {
            console.warn('[CombatGrid] Movement started with invalid from position:', from);
            return;
        }

        if (!path || !Array.isArray(path) || path.length === 0) {
            console.warn('[CombatGrid] Movement started with invalid path:', path);
            return;
        }

        this.animateMovement(combatantId, from, path);
    }

    /**
     * Subscribe to state changes
     */
    subscribeToState() {
        state.subscribe(() => {
            this.render();
        });
    }

    /**
     * Convert canvas coordinates to grid coordinates
     */
    canvasToGrid(canvasX, canvasY) {
        const rect = this.canvas.getBoundingClientRect();
        const x = Math.floor((canvasX - rect.left) / this.cellSize);
        const y = Math.floor((canvasY - rect.top) / this.cellSize);

        if (x >= 0 && x < this.gridSize && y >= 0 && y < this.gridSize) {
            return { x, y };
        }
        return null;
    }

    /**
     * Convert grid coordinates to canvas center point
     */
    gridToCanvas(gridX, gridY) {
        return {
            x: gridX * this.cellSize + this.cellSize / 2,
            y: gridY * this.cellSize + this.cellSize / 2,
        };
    }

    /**
     * Handle canvas click
     */
    handleClick(event) {
        const gridPos = this.canvasToGrid(event.clientX, event.clientY);
        if (!gridPos) return;

        // Check for ground items at clicked position
        const key = `${gridPos.x},${gridPos.y}`;
        const items = this.groundItems.get(key);

        if (items && items.length > 0) {
            // Check if player is at or adjacent to this position
            const gameState = state.getState();
            const playerPos = gameState.grid?.positions?.[gameState.playerId];

            if (playerPos) {
                const distance = Math.max(
                    Math.abs(playerPos.x - gridPos.x),
                    Math.abs(playerPos.y - gridPos.y)
                );

                // Can pick up if standing on or adjacent (within 1 cell)
                if (distance <= 1) {
                    this.pickupGroundItems(gridPos, items);
                    return;
                } else {
                    toast.info('Move closer to pick up items');
                }
            }
        }

        // Default behavior - emit cell clicked event
        eventBus.emit(EVENTS.CELL_CLICKED, gridPos);
    }

    /**
     * Pick up items from the ground at a position
     * @param {Object} pos - Grid position {x, y}
     * @param {Array} items - Items at that position
     */
    async pickupGroundItems(pos, items) {
        const gameState = state.getState();
        const combatId = gameState.combat?.id;
        const playerId = gameState.playerId;

        if (!combatId || !playerId) {
            toast.error('Cannot pick up items - invalid game state');
            return;
        }

        try {
            const result = await api.pickupItem(
                combatId,
                playerId,
                [pos.x, pos.y]
            );

            if (result.success) {
                const pickedCount = result.items_picked_up?.length || items.length;
                toast.success(`Picked up ${pickedCount} item(s)`);

                // Update local ground items from response
                if (result.ground_items) {
                    this.groundItems = new Map(Object.entries(result.ground_items));
                } else {
                    // Remove items from this position locally
                    this.groundItems.delete(`${pos.x},${pos.y}`);
                }

                this.render();

                // FIX: Update local state with picked up items
                if (playerId && result.items_picked_up?.length > 0) {
                    const currentStats = state.get(`combatant_stats.${playerId}`) || {};
                    const currentInventory = currentStats.inventory || [];
                    const updatedInventory = [...currentInventory, ...result.items_picked_up];
                    state.set(`combatant_stats.${playerId}.inventory`, updatedInventory);

                    // Also update combatants.playerId.inventory
                    const player = state.get(`combatants.${playerId}`);
                    if (player) {
                        const playerInventory = player.inventory || [];
                        state.set(`combatants.${playerId}.inventory`, [...playerInventory, ...result.items_picked_up]);
                    }
                }

                // Notify other systems that equipment changed
                eventBus.emit(EVENTS.EQUIPMENT_CHANGED);
            } else {
                toast.error(result.message || 'Failed to pick up items');
            }
        } catch (error) {
            console.error('[CombatGrid] Pickup failed:', error);
            toast.error(`Failed to pick up items: ${error.message}`);
        }
    }

    /**
     * Handle mouse move
     */
    handleMouseMove(event) {
        const gridPos = this.canvasToGrid(event.clientX, event.clientY);
        const currentHovered = state.get('grid.hoveredCell');

        if (gridPos) {
            if (!currentHovered || currentHovered.x !== gridPos.x || currentHovered.y !== gridPos.y) {
                state.setHoveredCell(gridPos);
                eventBus.emit(EVENTS.CELL_HOVERED, gridPos);
            }

            // Show stacking tooltip if hovering over stacked cell
            this.updateStackTooltip(gridPos, event.clientX, event.clientY);
        } else {
            this.hideStackTooltip();
        }
    }

    /**
     * Update the stacking tooltip for hovered cell
     */
    updateStackTooltip(gridPos, mouseX, mouseY) {
        const key = `${gridPos.x},${gridPos.y}`;
        const occupants = this.stackedCells.get(key);
        const groundItems = this.groundItems.get(key);

        let tooltipContent = '';

        // Show stacked combatants
        if (occupants && occupants.length > 1) {
            const names = occupants.map(o => {
                const type = o.combatant.type === 'player' ? '🛡️' : '👹';
                return `${type} ${o.combatant.name}`;
            }).join('<br>');
            tooltipContent += `<strong>Stacked (${occupants.length}):</strong><br>${names}`;
        }

        // Show ground items
        if (groundItems && groundItems.length > 0) {
            if (tooltipContent) tooltipContent += '<br><br>';
            const itemNames = groundItems.map(item => {
                const icon = item.type === 'potion' ? '🧪' : item.type === 'weapon' ? '⚔️' : '📦';
                return `${icon} ${item.name}`;
            }).join('<br>');
            tooltipContent += `<strong>💰 Ground Items (${groundItems.length}):</strong><br>${itemNames}<br><em style="color: #2ecc71;">Click to pick up</em>`;
        }

        if (tooltipContent) {
            this.stackTooltip.innerHTML = tooltipContent;
            this.stackTooltip.classList.remove('hidden');

            // Position tooltip near cursor
            const rect = this.canvas.getBoundingClientRect();
            this.stackTooltip.style.left = `${mouseX - rect.left + 15}px`;
            this.stackTooltip.style.top = `${mouseY - rect.top - 10}px`;
        } else {
            this.hideStackTooltip();
        }
    }

    /**
     * Hide the stacking tooltip
     */
    hideStackTooltip() {
        this.stackTooltip.classList.add('hidden');
    }

    /**
     * Handle mouse leave
     */
    handleMouseLeave() {
        state.setHoveredCell(null);
        eventBus.emit(EVENTS.CELL_UNHOVERED);
        this.hideStackTooltip();
    }

    /**
     * Main render method
     */
    render() {
        const currentState = state.getState();

        // Clear canvas
        this.ctx.fillStyle = CONFIG.COLORS.GRID_BG;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw grid cells
        this.drawGridCells(currentState);

        // Draw elevation indicators (visual height differentiation)
        this.drawElevationIndicators(currentState);

        // Draw cover indicators (half/three-quarters cover)
        this.drawCoverIndicators(currentState);

        // Draw grid lines
        this.drawGridLines();

        // Draw highlights (reachable, attack range, selected)
        this.drawHighlights(currentState);

        // Draw threat zones (enemy opportunity attack areas)
        this.drawThreatZones(currentState);

        // Draw path preview (with OA warnings)
        this.drawPathPreview(currentState);

        // Draw combatants (tokens)
        this.drawCombatants(currentState);

        // Draw ground items (dropped loot)
        this.drawGroundItems();

        // Draw hover highlight
        this.drawHoverHighlight(currentState);

        // Draw coordinates
        this.drawCoordinates();

        eventBus.emit(EVENTS.GRID_RENDERED);
    }

    /**
     * Draw grid cells (terrain)
     */
    drawGridCells(gameState) {
        const cells = gameState.grid.cells;
        if (!cells || cells.length === 0) return;

        for (let y = 0; y < this.gridSize; y++) {
            for (let x = 0; x < this.gridSize; x++) {
                const cell = cells[y]?.[x];
                if (cell) {
                    const posX = x * this.cellSize;
                    const posY = y * this.cellSize;

                    // Draw based on terrain type
                    if (cell.blocked || cell.terrain === 'wall') {
                        this.ctx.fillStyle = CONFIG.COLORS.CELL_WALL;
                        this.ctx.fillRect(posX, posY, this.cellSize, this.cellSize);
                    } else if (cell.terrain === 'difficult') {
                        this.ctx.fillStyle = CONFIG.COLORS.CELL_DIFFICULT;
                        this.ctx.fillRect(posX, posY, this.cellSize, this.cellSize);
                        // Draw hatching pattern
                        this.drawDifficultTerrainPattern(posX, posY);
                    }
                }
            }
        }
    }

    /**
     * Draw hatching pattern for difficult terrain
     */
    drawDifficultTerrainPattern(x, y) {
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        this.ctx.lineWidth = 1;

        const step = 8;
        for (let i = step; i < this.cellSize * 2; i += step) {
            this.ctx.beginPath();
            this.ctx.moveTo(x + Math.max(0, i - this.cellSize), y + Math.min(i, this.cellSize));
            this.ctx.lineTo(x + Math.min(i, this.cellSize), y + Math.max(0, i - this.cellSize));
            this.ctx.stroke();
        }
    }

    /**
     * Draw elevation indicators on cells with elevation > 0
     * Higher cells appear raised with shadow effects and height labels
     */
    drawElevationIndicators(gameState) {
        const cells = gameState.grid.cells;
        if (!cells || cells.length === 0) return;

        for (let y = 0; y < this.gridSize; y++) {
            for (let x = 0; x < this.gridSize; x++) {
                const cell = cells[y]?.[x];
                if (!cell || !cell.elevation || cell.elevation === 0) continue;

                const posX = x * this.cellSize;
                const posY = y * this.cellSize;
                const elevation = cell.elevation;

                // Draw elevation tint (intensity based on height)
                const alpha = Math.min(0.1 + elevation * 0.08, 0.4);
                this.ctx.fillStyle = `rgba(139, 119, 101, ${alpha})`;
                this.ctx.fillRect(posX + 1, posY + 1, this.cellSize - 2, this.cellSize - 2);

                // Draw 3D shadow on bottom-right edges
                this.ctx.fillStyle = CONFIG.COLORS.ELEVATION_SHADOW;
                this.ctx.fillRect(posX + this.cellSize - 3, posY + 1, 3, this.cellSize - 1);
                this.ctx.fillRect(posX + 1, posY + this.cellSize - 3, this.cellSize - 1, 3);

                // Draw height label in bottom-left corner
                this.ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
                this.ctx.font = 'bold 9px Arial';
                this.ctx.textAlign = 'left';
                this.ctx.textBaseline = 'bottom';
                this.ctx.fillText(`${elevation * 5}ft`, posX + 3, posY + this.cellSize - 2);
            }
        }
    }

    /**
     * Draw cover indicators on cells with cover
     * D&D 5e: Half cover (+2 AC), Three-quarters cover (+5 AC)
     */
    drawCoverIndicators(gameState) {
        const cells = gameState.grid.cells;
        if (!cells || cells.length === 0) return;

        for (let y = 0; y < this.gridSize; y++) {
            for (let x = 0; x < this.gridSize; x++) {
                const cell = cells[y]?.[x];
                if (!cell || !cell.cover_value || cell.cover_value === 0) continue;

                const posX = x * this.cellSize;
                const posY = y * this.cellSize;

                // Determine cover type and colors
                let fillColor, borderColor, label;
                if (cell.cover_value === 2) {
                    // Half cover (+2 AC) - Blue
                    fillColor = CONFIG.COLORS.COVER_HALF;
                    borderColor = CONFIG.COLORS.COVER_HALF_BORDER;
                    label = '+2';
                } else if (cell.cover_value >= 5) {
                    // Three-quarters cover (+5 AC) - Purple
                    fillColor = CONFIG.COLORS.COVER_THREE_QUARTERS;
                    borderColor = CONFIG.COLORS.COVER_THREE_QUARTERS_BORDER;
                    label = '+5';
                } else {
                    continue; // Unknown cover value
                }

                // Draw cover indicator as corner triangle (top-right)
                this.ctx.fillStyle = fillColor;
                this.ctx.beginPath();
                this.ctx.moveTo(posX + this.cellSize, posY);
                this.ctx.lineTo(posX + this.cellSize, posY + 20);
                this.ctx.lineTo(posX + this.cellSize - 20, posY);
                this.ctx.closePath();
                this.ctx.fill();

                // Draw border
                this.ctx.strokeStyle = borderColor;
                this.ctx.lineWidth = 2;
                this.ctx.stroke();

                // Draw AC bonus label
                this.ctx.fillStyle = '#ffffff';
                this.ctx.font = 'bold 10px Arial';
                this.ctx.textAlign = 'center';
                this.ctx.textBaseline = 'middle';
                this.ctx.fillText(label, posX + this.cellSize - 10, posY + 8);
            }
        }
    }

    /**
     * Draw threat zones (enemy opportunity attack areas)
     * Shows cells where movement could trigger opportunity attacks
     */
    drawThreatZones(gameState) {
        // Only draw if threat zones display is enabled
        if (!gameState.grid.showThreatZones) return;

        const threatZones = gameState.grid.threatZones || {};
        if (Object.keys(threatZones).length === 0) return;

        // Aggregate all threat cells into a Set for efficient lookup
        const threatCells = new Set();
        for (const [enemyId, zone] of Object.entries(threatZones)) {
            for (const cell of zone.cells || []) {
                threatCells.add(`${cell.x},${cell.y}`);
            }
        }

        // Draw threat zone overlay on each threatened cell
        for (const key of threatCells) {
            const [x, y] = key.split(',').map(Number);
            const posX = x * this.cellSize;
            const posY = y * this.cellSize;

            // Fill with threat color
            this.ctx.fillStyle = CONFIG.COLORS.THREAT_ZONE;
            this.ctx.fillRect(posX + 1, posY + 1, this.cellSize - 2, this.cellSize - 2);

            // Draw dashed border
            this.ctx.strokeStyle = CONFIG.COLORS.THREAT_ZONE_BORDER;
            this.ctx.lineWidth = 1;
            this.ctx.setLineDash([4, 4]);
            this.ctx.strokeRect(posX + 2, posY + 2, this.cellSize - 4, this.cellSize - 4);
            this.ctx.setLineDash([]); // Reset dash pattern
        }
    }

    /**
     * Check if a path would trigger opportunity attacks
     * Returns cells in path that would trigger OA when leaving
     */
    checkPathThreatWarnings(path, gameState) {
        const threatZones = gameState.grid.threatZones || {};
        if (Object.keys(threatZones).length === 0 || !path || path.length < 2) {
            return [];
        }

        // Build set of all threat cells
        const threatCells = new Set();
        for (const [enemyId, zone] of Object.entries(threatZones)) {
            for (const cell of zone.cells || []) {
                threatCells.add(`${cell.x},${cell.y}`);
            }
        }

        const warnings = [];

        // Check each step in path
        for (let i = 0; i < path.length - 1; i++) {
            const from = path[i];
            const to = path[i + 1];
            const fromKey = `${from.x},${from.y}`;
            const toKey = `${to.x},${to.y}`;

            // Leaving a threat zone triggers OA
            if (threatCells.has(fromKey) && !threatCells.has(toKey)) {
                warnings.push({ x: from.x, y: from.y, type: 'leaving_threat' });
            }
        }

        return warnings;
    }

    /**
     * Draw grid lines
     */
    drawGridLines() {
        this.ctx.strokeStyle = CONFIG.COLORS.GRID_LINE;
        this.ctx.lineWidth = 1;

        // Vertical lines
        for (let x = 0; x <= this.gridSize; x++) {
            this.ctx.beginPath();
            this.ctx.moveTo(x * this.cellSize, 0);
            this.ctx.lineTo(x * this.cellSize, this.canvas.height);
            this.ctx.stroke();
        }

        // Horizontal lines
        for (let y = 0; y <= this.gridSize; y++) {
            this.ctx.beginPath();
            this.ctx.moveTo(0, y * this.cellSize);
            this.ctx.lineTo(this.canvas.width, y * this.cellSize);
            this.ctx.stroke();
        }
    }

    /**
     * Draw cell highlights (reachable, attack range)
     */
    drawHighlights(gameState) {
        const mode = gameState.mode;
        const reachable = gameState.grid.reachableCells || [];
        const attackTargets = gameState.grid.attackTargets || [];
        const positions = gameState.grid.positions || {};

        // Draw reachable cells (movement mode)
        if (mode === GameMode.MOVING || mode === GameMode.COMBAT) {
            for (const cell of reachable) {
                this.drawCellHighlight(cell.x, cell.y, 'reachable');
            }
        }

        // Draw attack range (targeting mode)
        if (mode === GameMode.TARGETING) {
            for (const targetId of attackTargets) {
                const pos = positions[targetId];
                if (pos) {
                    this.drawCellHighlight(pos.x, pos.y, 'attack');
                }
            }
        }

        // Draw area targeting preview
        if (mode === GameMode.AREA_TARGETING) {
            const areaTargeting = gameState.grid.areaTargeting || {};
            const previewCells = areaTargeting.previewCells || [];

            for (const cell of previewCells) {
                this.drawCellHighlight(cell.x, cell.y, 'area');
            }
        }

        // Draw selected cell
        const selected = gameState.grid.selectedCell;
        if (selected) {
            this.drawCellHighlight(selected.x, selected.y, 'selected');
        }
    }

    /**
     * Draw a cell highlight
     */
    drawCellHighlight(x, y, type) {
        const posX = x * this.cellSize;
        const posY = y * this.cellSize;

        let fillColor, borderColor;
        switch (type) {
            case 'reachable':
                fillColor = CONFIG.COLORS.HIGHLIGHT_REACHABLE;
                borderColor = CONFIG.COLORS.HIGHLIGHT_REACHABLE_BORDER;
                break;
            case 'attack':
                fillColor = CONFIG.COLORS.HIGHLIGHT_ATTACK;
                borderColor = CONFIG.COLORS.HIGHLIGHT_ATTACK_BORDER;
                break;
            case 'selected':
                fillColor = CONFIG.COLORS.HIGHLIGHT_SELECTED;
                borderColor = CONFIG.COLORS.HIGHLIGHT_SELECTED_BORDER;
                break;
            case 'path':
                fillColor = CONFIG.COLORS.HIGHLIGHT_PATH;
                borderColor = CONFIG.COLORS.HIGHLIGHT_PATH_BORDER;
                break;
            case 'area':
                // Orange highlight for area spell targeting
                fillColor = 'rgba(255, 140, 0, 0.4)';
                borderColor = 'rgba(255, 165, 0, 0.9)';
                break;
            default:
                fillColor = CONFIG.COLORS.HIGHLIGHT_HOVER;
                borderColor = 'transparent';
        }

        // Fill
        this.ctx.fillStyle = fillColor;
        this.ctx.fillRect(posX + 1, posY + 1, this.cellSize - 2, this.cellSize - 2);

        // Border
        if (borderColor !== 'transparent') {
            this.ctx.strokeStyle = borderColor;
            this.ctx.lineWidth = 2;
            this.ctx.strokeRect(posX + 2, posY + 2, this.cellSize - 4, this.cellSize - 4);
        }
    }

    /**
     * Draw path preview for movement
     */
    drawPathPreview(gameState) {
        const path = gameState.grid.pathPreview || [];
        if (path.length === 0) return;

        // Check for opportunity attack warnings
        const oaWarnings = this.checkPathThreatWarnings(path, gameState);
        const warningCells = new Set(oaWarnings.map(w => `${w.x},${w.y}`));

        // Draw path cells
        for (const cell of path) {
            this.drawCellHighlight(cell.x, cell.y, 'path');
        }

        // Draw OA warning indicators on cells that trigger opportunity attacks
        for (const warning of oaWarnings) {
            const posX = warning.x * this.cellSize;
            const posY = warning.y * this.cellSize;

            // Draw warning background
            this.ctx.fillStyle = CONFIG.COLORS.THREAT_WARNING;
            this.ctx.fillRect(posX + 1, posY + 1, this.cellSize - 2, this.cellSize - 2);

            // Draw warning icon (exclamation mark)
            this.ctx.fillStyle = '#f39c12';
            this.ctx.font = 'bold 14px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            this.ctx.fillText('!', posX + this.cellSize - 12, posY + 12);

            // Draw "OA" text in center
            this.ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
            this.ctx.font = 'bold 10px Arial';
            this.ctx.fillText('OA', posX + this.cellSize / 2, posY + this.cellSize / 2);
        }

        // Draw arrows between cells
        this.ctx.strokeStyle = CONFIG.COLORS.HIGHLIGHT_PATH_BORDER;
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();

        for (let i = 0; i < path.length - 1; i++) {
            const from = this.gridToCanvas(path[i].x, path[i].y);
            const to = this.gridToCanvas(path[i + 1].x, path[i + 1].y);

            if (i === 0) {
                this.ctx.moveTo(from.x, from.y);
            }
            this.ctx.lineTo(to.x, to.y);
        }
        this.ctx.stroke();
    }

    /**
     * Draw all combatants as tokens
     */
    drawCombatants(gameState) {
        const combatants = gameState.combatants || {};
        const positions = gameState.grid.positions || {};
        const currentCombatant = gameState.initiative[gameState.combat.currentTurnIndex];

        // First pass: count entities per cell to detect stacking
        const cellOccupants = new Map(); // "x,y" -> [{id, combatant}, ...]

        for (const [id, combatant] of Object.entries(combatants)) {
            if (!combatant.isActive) continue;

            let pos = this.animatingPositions.get(id) || positions[id];
            if (!pos) continue;

            const key = `${pos.x},${pos.y}`;
            if (!cellOccupants.has(key)) {
                cellOccupants.set(key, []);
            }
            cellOccupants.get(key).push({ id, combatant, pos });
        }

        // Second pass: draw tokens
        for (const [id, combatant] of Object.entries(combatants)) {
            if (!combatant.isActive) continue;

            let pos = this.animatingPositions.get(id) || positions[id];
            if (!pos) continue;

            const isCurrentTurn = id === currentCombatant;
            this.drawToken(pos.x, pos.y, combatant, isCurrentTurn);
        }

        // Store stacked cells for hover tooltip access
        this.stackedCells = cellOccupants;

        // Third pass: draw stacking indicators for cells with multiple entities
        for (const [key, occupants] of cellOccupants) {
            if (occupants.length > 1) {
                const [x, y] = key.split(',').map(Number);
                this.drawStackingIndicator(x, y, occupants);
            }
        }
    }

    /**
     * Draw ground items (dropped loot) on the grid
     */
    drawGroundItems() {
        if (this.groundItems.size === 0) return;

        for (const [key, items] of this.groundItems) {
            if (!items || items.length === 0) continue;

            const [x, y] = key.split(',').map(Number);
            const center = this.gridToCanvas(x, y);

            // Draw loot bag background circle
            this.ctx.beginPath();
            this.ctx.arc(center.x, center.y + 15, 12, 0, Math.PI * 2);
            this.ctx.fillStyle = 'rgba(218, 165, 32, 0.8)'; // Gold color
            this.ctx.fill();
            this.ctx.strokeStyle = '#8B4513'; // Brown border
            this.ctx.lineWidth = 2;
            this.ctx.stroke();

            // Draw loot bag icon (emoji)
            this.ctx.font = '16px sans-serif';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            this.ctx.fillText('💰', center.x, center.y + 15);

            // Draw item count badge if multiple items
            if (items.length > 1) {
                const badgeX = center.x + 10;
                const badgeY = center.y + 5;
                const badgeRadius = 8;

                // Badge background
                this.ctx.beginPath();
                this.ctx.arc(badgeX, badgeY, badgeRadius, 0, Math.PI * 2);
                this.ctx.fillStyle = '#2ecc71'; // Green
                this.ctx.fill();
                this.ctx.strokeStyle = '#fff';
                this.ctx.lineWidth = 1;
                this.ctx.stroke();

                // Badge count
                this.ctx.fillStyle = '#fff';
                this.ctx.font = 'bold 10px Arial';
                this.ctx.fillText(items.length.toString(), badgeX, badgeY);
            }
        }
    }

    /**
     * Draw stacking indicator badge when multiple entities occupy same cell
     */
    drawStackingIndicator(gridX, gridY, occupants) {
        const center = this.gridToCanvas(gridX, gridY);
        const count = occupants.length;

        // Draw badge in top-right corner of cell
        const badgeX = center.x + CONFIG.TOKEN.RADIUS - 2;
        const badgeY = center.y - CONFIG.TOKEN.RADIUS + 2;
        const badgeRadius = 10;

        // Badge background (red for warning)
        this.ctx.beginPath();
        this.ctx.arc(badgeX, badgeY, badgeRadius, 0, Math.PI * 2);
        this.ctx.fillStyle = '#e74c3c';
        this.ctx.fill();

        // Badge border
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();

        // Badge text (count)
        this.ctx.fillStyle = '#ffffff';
        this.ctx.font = 'bold 11px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(count.toString(), badgeX, badgeY);
    }

    /**
     * Draw a combatant token
     */
    drawToken(gridX, gridY, combatant, isCurrentTurn) {
        const center = this.gridToCanvas(gridX, gridY);
        const radius = CONFIG.TOKEN.RADIUS;

        // Draw glow for current turn
        if (isCurrentTurn) {
            this.ctx.beginPath();
            this.ctx.arc(center.x, center.y, radius + 5, 0, Math.PI * 2);
            this.ctx.fillStyle = 'rgba(212, 175, 55, 0.3)';
            this.ctx.fill();
        }

        // Token circle
        this.ctx.beginPath();
        this.ctx.arc(center.x, center.y, radius, 0, Math.PI * 2);

        // Fill color based on type
        const isPlayer = combatant.type === 'player';
        this.ctx.fillStyle = isPlayer ? CONFIG.COLORS.TOKEN_PLAYER : CONFIG.COLORS.TOKEN_ENEMY;
        this.ctx.fill();

        // Border
        this.ctx.strokeStyle = isPlayer ? CONFIG.COLORS.TOKEN_PLAYER_BORDER : CONFIG.COLORS.TOKEN_ENEMY_BORDER;
        this.ctx.lineWidth = CONFIG.TOKEN.BORDER_WIDTH;
        this.ctx.stroke();

        // Draw initial or symbol
        this.ctx.fillStyle = CONFIG.COLORS.TEXT_DARK;
        this.ctx.font = `bold ${CONFIG.TOKEN.FONT_SIZE}px Arial`;
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';

        const initial = combatant.name ? combatant.name[0].toUpperCase() : '?';
        this.ctx.fillText(initial, center.x, center.y);

        // HP bar under token
        this.drawTokenHPBar(center.x, center.y + radius + 4, combatant.hp, combatant.maxHp);

        // Draw condition icons (D&D 2024 weapon mastery effects)
        this.drawConditionIcons(center.x, center.y, radius, combatant.conditions || []);
    }

    /**
     * Draw condition icons around a token
     * @param {number} centerX - Token center X
     * @param {number} centerY - Token center Y
     * @param {number} radius - Token radius
     * @param {Array<string>} conditions - Array of active conditions
     */
    drawConditionIcons(centerX, centerY, radius, conditions) {
        if (!conditions || conditions.length === 0) return;

        // Condition colors and abbreviations
        const conditionStyles = {
            vexed: { color: '#f1c40f', abbr: 'V' },      // Gold - advantage marker
            sapped: { color: '#9b59b6', abbr: 'S' },     // Purple - disadvantage
            slowed: { color: '#3498db', abbr: 'SL' },    // Blue - slow
            prone: { color: '#e74c3c', abbr: 'P' },      // Red - prone
            frightened: { color: '#f39c12', abbr: 'F' }, // Orange - frightened
            poisoned: { color: '#27ae60', abbr: 'PO' },  // Green - poisoned
            stunned: { color: '#e67e22', abbr: 'ST' },   // Dark orange - stunned
            steady_aim: { color: '#2ecc71', abbr: 'A' }, // Light green - aiming
        };

        // Position icons at top-right of token
        const iconSize = 8;
        const startX = centerX + radius - 4;
        const startY = centerY - radius - 4;

        let iconIndex = 0;
        for (const condition of conditions) {
            const style = conditionStyles[condition.toLowerCase()];
            if (!style) continue;

            const iconX = startX - (iconIndex * (iconSize + 2));
            const iconY = startY;

            // Draw icon background
            this.ctx.beginPath();
            this.ctx.arc(iconX, iconY, iconSize, 0, Math.PI * 2);
            this.ctx.fillStyle = style.color;
            this.ctx.fill();
            this.ctx.strokeStyle = 'rgba(0, 0, 0, 0.5)';
            this.ctx.lineWidth = 1;
            this.ctx.stroke();

            // Draw abbreviation
            this.ctx.fillStyle = '#fff';
            this.ctx.font = `bold ${iconSize}px Arial`;
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            this.ctx.fillText(style.abbr, iconX, iconY);

            iconIndex++;
            if (iconIndex >= 3) break; // Max 3 icons visible
        }
    }

    /**
     * Draw HP bar under a token
     */
    drawTokenHPBar(centerX, y, hp, maxHp) {
        const barWidth = 30;
        const barHeight = 4;
        const x = centerX - barWidth / 2;

        // Background
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        this.ctx.fillRect(x, y, barWidth, barHeight);

        // HP fill
        const hpPercent = Math.max(0, Math.min(1, hp / maxHp));
        let hpColor = CONFIG.COLORS.HP_FULL;
        if (hpPercent <= 0.25) {
            hpColor = CONFIG.COLORS.HP_LOW;
        } else if (hpPercent <= 0.5) {
            hpColor = CONFIG.COLORS.HP_MID;
        }

        this.ctx.fillStyle = hpColor;
        this.ctx.fillRect(x, y, barWidth * hpPercent, barHeight);

        // Border
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
        this.ctx.lineWidth = 1;
        this.ctx.strokeRect(x, y, barWidth, barHeight);
    }

    /**
     * Draw hover highlight
     */
    drawHoverHighlight(gameState) {
        const hovered = gameState.grid.hoveredCell;
        if (!hovered) return;

        const posX = hovered.x * this.cellSize;
        const posY = hovered.y * this.cellSize;

        this.ctx.fillStyle = CONFIG.COLORS.HIGHLIGHT_HOVER;
        this.ctx.fillRect(posX + 1, posY + 1, this.cellSize - 2, this.cellSize - 2);
    }

    /**
     * Draw grid coordinates
     */
    drawCoordinates() {
        this.ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
        this.ctx.font = '10px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';

        // Column numbers (x-axis)
        for (let x = 0; x < this.gridSize; x++) {
            this.ctx.fillText(
                String(x + 1),
                x * this.cellSize + this.cellSize / 2,
                this.canvas.height - 5
            );
        }

        // Row numbers (y-axis)
        for (let y = 0; y < this.gridSize; y++) {
            this.ctx.fillText(
                String(y + 1),
                8,
                y * this.cellSize + this.cellSize / 2
            );
        }
    }

    // ==================== Animation Methods ====================

    /**
     * Animate damage number floating up
     */
    showDamageNumber(gridX, gridY, damage, isCrit = false, isHeal = false) {
        const center = this.gridToCanvas(gridX, gridY);
        const element = document.createElement('div');
        element.className = `damage-number${isCrit ? ' crit' : ''}${isHeal ? ' heal' : ''}`;
        element.textContent = isHeal ? `+${damage}` : `-${damage}`;
        element.style.left = `${center.x}px`;
        element.style.top = `${center.y - 20}px`;

        const container = this.canvas.parentElement;
        container.appendChild(element);

        // Remove after animation
        setTimeout(() => element.remove(), CONFIG.ANIMATION.DAMAGE_FLOAT_DURATION);
    }

    /**
     * Show attack flash effect
     */
    showAttackFlash(gridX, gridY) {
        const center = this.gridToCanvas(gridX, gridY);
        const element = document.createElement('div');
        element.className = 'attack-flash';
        element.style.left = `${center.x - 30}px`;
        element.style.top = `${center.y - 30}px`;
        element.style.width = '60px';
        element.style.height = '60px';
        element.style.borderRadius = '50%';

        const container = this.canvas.parentElement;
        container.appendChild(element);

        setTimeout(() => element.remove(), CONFIG.ANIMATION.ATTACK_DURATION);
    }

    // ==================== Movement Animation ====================

    /**
     * Animate a combatant moving along a path
     * @param {string} combatantId - ID of the combatant to animate
     * @param {Object} fromPos - Starting position {x, y}
     * @param {Array} path - Array of cells to move through [{x, y}, ...]
     * @returns {Promise} Resolves when animation completes
     */
    async animateMovement(combatantId, fromPos, path) {
        // Safety validation
        if (!combatantId || !fromPos || !path || path.length === 0) {
            console.warn('[CombatGrid] animateMovement called with invalid params:', { combatantId, fromPos, path });
            return;
        }

        this.isAnimating = true;
        const duration = CONFIG.ANIMATION.MOVE_DURATION;

        let currentPos = { x: fromPos.x ?? 0, y: fromPos.y ?? 0 };

        // Animate through each cell in the path
        for (const targetCell of path) {
            await this.interpolatePosition(combatantId, currentPos, targetCell, duration);

            // Show trail at previous position
            this.showMovementTrail(currentPos.x, currentPos.y);

            currentPos = { x: targetCell.x, y: targetCell.y };
        }

        // Animation complete - clean up
        this.animatingPositions.delete(combatantId);
        this.isAnimating = false;

        // Force final render
        this.render();
    }

    /**
     * Interpolate position between two cells over time
     * @param {string} combatantId - ID of the combatant
     * @param {Object} from - Starting position {x, y}
     * @param {Object} to - Target position {x, y}
     * @param {number} duration - Animation duration in ms
     * @returns {Promise} Resolves when interpolation completes
     */
    interpolatePosition(combatantId, from, to, duration) {
        return new Promise(resolve => {
            const startTime = performance.now();

            const animate = (currentTime) => {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const eased = this.easeOutQuad(progress);

                // Calculate interpolated position
                const interpolatedX = from.x + (to.x - from.x) * eased;
                const interpolatedY = from.y + (to.y - from.y) * eased;

                // Update animated position
                this.animatingPositions.set(combatantId, {
                    x: interpolatedX,
                    y: interpolatedY
                });

                // Re-render
                this.render();

                if (progress < 1) {
                    requestAnimationFrame(animate);
                } else {
                    // Snap to final position
                    this.animatingPositions.set(combatantId, { x: to.x, y: to.y });
                    resolve();
                }
            };

            requestAnimationFrame(animate);
        });
    }

    /**
     * Easing function for smooth animation
     * @param {number} t - Progress from 0 to 1
     * @returns {number} Eased value
     */
    easeOutQuad(t) {
        return t * (2 - t);
    }

    /**
     * Show a movement trail dot at a position
     * @param {number} gridX - Grid X coordinate
     * @param {number} gridY - Grid Y coordinate
     */
    showMovementTrail(gridX, gridY) {
        const center = this.gridToCanvas(gridX, gridY);
        const element = document.createElement('div');
        element.className = 'movement-trail';
        element.style.left = `${center.x - 5}px`;
        element.style.top = `${center.y - 5}px`;
        // The .movement-trail class in CSS already defines size, shape, color, and animation

        const container = this.canvas.parentElement;
        container.appendChild(element);

        // Remove after animation completes
        setTimeout(() => element.remove(), 500);
    }

    /**
     * Check if any animation is in progress
     * @returns {boolean}
     */
    isMovementAnimating() {
        return this.isAnimating || this.animatingPositions.size > 0;
    }

    // ==================== Attack Animation Methods ====================

    /**
     * Play full attack animation sequence
     * @param {Object} attackerPos - Attacker grid position {x, y}
     * @param {Object} targetPos - Target grid position {x, y}
     * @param {Object} attackData - Attack result data
     */
    async playAttackAnimation(attackerPos, targetPos, attackData) {
        const attackerCanvas = this.gridToCanvas(attackerPos.x, attackerPos.y);
        const targetCanvas = this.gridToCanvas(targetPos.x, targetPos.y);

        // 1. Show attacker wind-up (glow effect)
        this.showAttackerGlow(attackerPos.x, attackerPos.y);

        // 2. Draw attack arc/line
        await this.animateAttackArc(attackerCanvas, targetCanvas, attackData.hit);

        // 3. Show impact effect on target
        if (attackData.hit) {
            this.showImpactEffect(targetPos.x, targetPos.y, attackData.critical);

            // 4. Show damage number
            if (attackData.damage_dealt || attackData.damage) {
                const damage = attackData.damage_dealt || attackData.damage;
                this.showDamageNumber(targetPos.x, targetPos.y, damage, attackData.critical, false);
            }
        } else {
            // Miss effect
            this.showMissEffect(targetPos.x, targetPos.y);
        }
    }

    /**
     * Show glow effect on attacker token
     * @param {number} gridX - Grid X coordinate
     * @param {number} gridY - Grid Y coordinate
     */
    showAttackerGlow(gridX, gridY) {
        const center = this.gridToCanvas(gridX, gridY);
        const element = document.createElement('div');
        element.className = 'attacker-glow';
        element.style.left = `${center.x - 35}px`;
        element.style.top = `${center.y - 35}px`;
        element.style.width = '70px';
        element.style.height = '70px';

        const container = this.canvas.parentElement;
        container.appendChild(element);

        setTimeout(() => element.remove(), 400);
    }

    /**
     * Animate attack arc from attacker to target
     * @param {Object} from - Canvas position {x, y}
     * @param {Object} to - Canvas position {x, y}
     * @param {boolean} hit - Whether the attack hit
     * @returns {Promise} Resolves when animation completes
     */
    animateAttackArc(from, to, hit) {
        return new Promise(resolve => {
            const duration = 250; // ms
            const startTime = performance.now();

            // Create a temporary canvas for the attack line
            const overlay = this.canvas.parentElement.querySelector('.grid-overlay');

            const animate = (currentTime) => {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const eased = this.easeOutQuad(progress);

                // Calculate current endpoint of the line
                const currentX = from.x + (to.x - from.x) * eased;
                const currentY = from.y + (to.y - from.y) * eased;

                // Draw on canvas
                this.ctx.save();

                // Draw attack line
                this.ctx.beginPath();
                this.ctx.moveTo(from.x, from.y);
                this.ctx.lineTo(currentX, currentY);

                // Line style
                this.ctx.strokeStyle = hit ? '#e74c3c' : '#888888';
                this.ctx.lineWidth = 3;
                this.ctx.lineCap = 'round';

                // Glow effect
                this.ctx.shadowColor = hit ? '#e74c3c' : '#888888';
                this.ctx.shadowBlur = 10;

                this.ctx.stroke();
                this.ctx.restore();

                // Re-render to clear and redraw
                if (progress < 1) {
                    requestAnimationFrame(animate);
                } else {
                    // Clear the attack line after a brief moment
                    setTimeout(() => {
                        this.render();
                        resolve();
                    }, 100);
                }
            };

            requestAnimationFrame(animate);
        });
    }

    /**
     * Show impact effect when attack hits
     * @param {number} gridX - Grid X coordinate
     * @param {number} gridY - Grid Y coordinate
     * @param {boolean} isCritical - Whether it was a critical hit
     */
    showImpactEffect(gridX, gridY, isCritical) {
        const center = this.gridToCanvas(gridX, gridY);

        // Create impact burst element
        const element = document.createElement('div');
        element.className = `impact-burst${isCritical ? ' critical' : ''}`;
        element.style.left = `${center.x}px`;
        element.style.top = `${center.y}px`;

        const container = this.canvas.parentElement;
        container.appendChild(element);

        // Also show attack flash
        this.showAttackFlash(gridX, gridY);

        setTimeout(() => element.remove(), 400);
    }

    /**
     * Show miss swoosh effect
     * @param {number} gridX - Grid X coordinate
     * @param {number} gridY - Grid Y coordinate
     */
    showMissEffect(gridX, gridY) {
        const center = this.gridToCanvas(gridX, gridY);

        const element = document.createElement('div');
        element.className = 'miss-swoosh';
        element.textContent = 'MISS';
        element.style.left = `${center.x}px`;
        element.style.top = `${center.y}px`;

        const container = this.canvas.parentElement;
        container.appendChild(element);

        setTimeout(() => element.remove(), 800);
    }

    /**
     * Show weapon mastery effect indicator
     * @param {number} gridX - Grid X coordinate
     * @param {number} gridY - Grid Y coordinate
     * @param {string} masteryType - Type of mastery (cleave, graze, push, etc.)
     */
    showMasteryEffect(gridX, gridY, masteryType) {
        const center = this.gridToCanvas(gridX, gridY);

        const element = document.createElement('div');
        element.className = 'mastery-indicator active';
        element.textContent = masteryType.toUpperCase();
        element.style.left = `${center.x - 30}px`;
        element.style.top = `${center.y + 25}px`;

        const container = this.canvas.parentElement;
        container.appendChild(element);

        setTimeout(() => element.remove(), 1500);
    }

    /**
     * Show condition applied indicator (for weapon mastery effects like Sap, Slow, etc.)
     * @param {number} gridX - Grid X coordinate
     * @param {number} gridY - Grid Y coordinate
     * @param {string} condition - Condition name
     */
    showConditionApplied(gridX, gridY, condition) {
        const center = this.gridToCanvas(gridX, gridY);

        const element = document.createElement('div');
        element.className = 'damage-number';
        element.style.color = '#9b59b6'; // Purple for conditions
        element.textContent = condition.toUpperCase();
        element.style.left = `${center.x}px`;
        element.style.top = `${center.y - 40}px`;

        const container = this.canvas.parentElement;
        container.appendChild(element);

        setTimeout(() => element.remove(), 1000);
    }

    /**
     * Show healing number floating up
     * @param {number} gridX - Grid X coordinate
     * @param {number} gridY - Grid Y coordinate
     * @param {number} amount - Healing amount
     */
    showHealingNumber(gridX, gridY, amount) {
        this.showDamageNumber(gridX, gridY, amount, false, true);
    }

    /**
     * Play death animation when a combatant is defeated
     * @param {number} gridX - Grid X coordinate
     * @param {number} gridY - Grid Y coordinate
     * @param {string} name - Name of defeated combatant
     */
    async playDeathAnimation(gridX, gridY, name = 'Enemy') {
        const center = this.gridToCanvas(gridX, gridY);
        const container = this.canvas.parentElement;

        // 1. Flash effect - bright white/red flash
        const flash = document.createElement('div');
        flash.className = 'death-flash';
        flash.style.left = `${center.x}px`;
        flash.style.top = `${center.y}px`;
        container.appendChild(flash);

        // 2. Skull/death icon rising up
        const skull = document.createElement('div');
        skull.className = 'death-skull';
        skull.textContent = '💀';
        skull.style.left = `${center.x}px`;
        skull.style.top = `${center.y}px`;
        container.appendChild(skull);

        // 3. "DEFEATED!" text
        const text = document.createElement('div');
        text.className = 'death-text';
        text.textContent = 'DEFEATED!';
        text.style.left = `${center.x}px`;
        text.style.top = `${center.y + 30}px`;
        container.appendChild(text);

        // 4. Particle effect (blood splatter / sparks)
        for (let i = 0; i < 8; i++) {
            const particle = document.createElement('div');
            particle.className = 'death-particle';
            const angle = (i / 8) * Math.PI * 2;
            const distance = 30 + Math.random() * 20;
            particle.style.left = `${center.x}px`;
            particle.style.top = `${center.y}px`;
            particle.style.setProperty('--dx', `${Math.cos(angle) * distance}px`);
            particle.style.setProperty('--dy', `${Math.sin(angle) * distance}px`);
            container.appendChild(particle);
            setTimeout(() => particle.remove(), 600);
        }

        // Clean up after animation
        setTimeout(() => flash.remove(), 300);
        setTimeout(() => skull.remove(), 1200);
        setTimeout(() => text.remove(), 1500);

        // Wait for animation to complete
        await new Promise(resolve => setTimeout(resolve, 800));
    }
}

export default CombatGrid;
