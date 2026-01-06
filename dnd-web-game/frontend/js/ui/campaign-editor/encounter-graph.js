/**
 * D&D Combat Engine - Encounter Graph
 * Canvas-based visual node editor for campaign encounters.
 */

/**
 * Visual encounter graph with drag-and-drop nodes and connections
 */
export class EncounterGraph {
    constructor(canvas, callbacks = {}) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.callbacks = callbacks;

        this.encounters = [];
        this.connections = [];
        this.selectedId = null;

        // Viewport state
        this.scale = 1;
        this.panX = 0;
        this.panY = 0;

        // Interaction state
        this.isDragging = false;
        this.isPanning = false;
        this.isConnecting = false;
        this.dragTarget = null;
        this.dragOffset = { x: 0, y: 0 };
        this.connectFrom = null;
        this.mousePos = { x: 0, y: 0 };

        // Node appearance
        this.nodeWidth = 160;
        this.nodeHeight = 60;
        this.nodeRadius = 8;

        // Colors by encounter type
        this.typeColors = {
            combat: '#dc3545',
            rest: '#28a745',
            choice: '#ffc107',
            cutscene: '#6f42c1',
            social: '#17a2b8',
            exploration: '#20c997',
            default: '#6c757d',
        };

        this.init();
    }

    init() {
        this.resize();
        this.setupEventListeners();
        this.render();
    }

    resize() {
        const parent = this.canvas.parentElement;
        this.canvas.width = parent.clientWidth;
        this.canvas.height = parent.clientHeight;
        this.render();
    }

    setupEventListeners() {
        // Mouse events
        this.canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.handleMouseUp(e));
        this.canvas.addEventListener('dblclick', (e) => this.handleDoubleClick(e));
        this.canvas.addEventListener('wheel', (e) => this.handleWheel(e));
        this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());

        // Window resize
        window.addEventListener('resize', () => this.resize());
    }

    // ==========================================================================
    // PUBLIC API
    // ==========================================================================

    loadCampaign(campaign) {
        this.encounters = campaign.encounters || [];
        this.buildConnections();
        this.fitView();
        this.render();
    }

    addEncounter(encounter) {
        this.encounters.push(encounter);
        this.buildConnections();
        this.render();
    }

    updateEncounter(encounter) {
        const index = this.encounters.findIndex(e => e.id === encounter.id);
        if (index !== -1) {
            this.encounters[index] = encounter;
            this.buildConnections();
            this.render();
        }
    }

    removeEncounter(id) {
        this.encounters = this.encounters.filter(e => e.id !== id);
        this.buildConnections();
        if (this.selectedId === id) {
            this.selectedId = null;
        }
        this.render();
    }

    setSelectedEncounter(id) {
        this.selectedId = id;
        this.render();
    }

    zoomIn() {
        this.scale = Math.min(2, this.scale * 1.2);
        this.render();
    }

    zoomOut() {
        this.scale = Math.max(0.25, this.scale / 1.2);
        this.render();
    }

    fitView() {
        if (this.encounters.length === 0) {
            this.scale = 1;
            this.panX = 0;
            this.panY = 0;
            return;
        }

        // Find bounds
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        this.encounters.forEach(e => {
            const pos = e.position || { x: 0, y: 0 };
            minX = Math.min(minX, pos.x);
            minY = Math.min(minY, pos.y);
            maxX = Math.max(maxX, pos.x + this.nodeWidth);
            maxY = Math.max(maxY, pos.y + this.nodeHeight);
        });

        const width = maxX - minX + 100;
        const height = maxY - minY + 100;
        const scaleX = this.canvas.width / width;
        const scaleY = this.canvas.height / height;

        this.scale = Math.min(1.5, Math.min(scaleX, scaleY) * 0.9);
        this.panX = -minX * this.scale + 50;
        this.panY = -minY * this.scale + 50;

        this.render();
    }

    // ==========================================================================
    // RENDERING
    // ==========================================================================

    render() {
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Background grid
        this.drawGrid();

        // Apply transform
        ctx.save();
        ctx.translate(this.panX, this.panY);
        ctx.scale(this.scale, this.scale);

        // Draw connections first (behind nodes)
        this.drawConnections();

        // Draw connection in progress
        if (this.isConnecting && this.connectFrom) {
            const fromEnc = this.encounters.find(e => e.id === this.connectFrom);
            if (fromEnc) {
                const startX = fromEnc.position.x + this.nodeWidth;
                const startY = fromEnc.position.y + this.nodeHeight / 2;
                const endX = (this.mousePos.x - this.panX) / this.scale;
                const endY = (this.mousePos.y - this.panY) / this.scale;

                ctx.beginPath();
                ctx.strokeStyle = '#17a2b8';
                ctx.lineWidth = 2;
                ctx.setLineDash([5, 5]);
                ctx.moveTo(startX, startY);
                ctx.lineTo(endX, endY);
                ctx.stroke();
                ctx.setLineDash([]);
            }
        }

        // Draw nodes
        this.encounters.forEach(encounter => {
            this.drawNode(encounter);
        });

        ctx.restore();
    }

    drawGrid() {
        const ctx = this.ctx;
        const gridSize = 50 * this.scale;

        ctx.strokeStyle = '#2a2a2a';
        ctx.lineWidth = 1;

        const offsetX = this.panX % gridSize;
        const offsetY = this.panY % gridSize;

        for (let x = offsetX; x < this.canvas.width; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, this.canvas.height);
            ctx.stroke();
        }

        for (let y = offsetY; y < this.canvas.height; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(this.canvas.width, y);
            ctx.stroke();
        }
    }

    drawConnections() {
        const ctx = this.ctx;

        this.connections.forEach(conn => {
            const from = this.encounters.find(e => e.id === conn.fromId);
            const to = this.encounters.find(e => e.id === conn.toId);

            if (!from || !to) return;

            const startX = from.position.x + this.nodeWidth;
            const startY = from.position.y + this.nodeHeight / 2;
            const endX = to.position.x;
            const endY = to.position.y + this.nodeHeight / 2;

            // Draw curved line
            ctx.beginPath();
            ctx.strokeStyle = '#888';
            ctx.lineWidth = 2;

            const midX = (startX + endX) / 2;
            ctx.moveTo(startX, startY);
            ctx.bezierCurveTo(midX, startY, midX, endY, endX, endY);
            ctx.stroke();

            // Draw arrow
            const angle = Math.atan2(endY - startY, endX - midX);
            const arrowSize = 10;
            ctx.beginPath();
            ctx.fillStyle = '#888';
            ctx.moveTo(endX, endY);
            ctx.lineTo(endX - arrowSize * Math.cos(angle - Math.PI / 6), endY - arrowSize * Math.sin(angle - Math.PI / 6));
            ctx.lineTo(endX - arrowSize * Math.cos(angle + Math.PI / 6), endY - arrowSize * Math.sin(angle + Math.PI / 6));
            ctx.closePath();
            ctx.fill();
        });
    }

    drawNode(encounter) {
        const ctx = this.ctx;
        const pos = encounter.position || { x: 0, y: 0 };
        const isSelected = encounter.id === this.selectedId;
        const color = this.typeColors[encounter.type] || this.typeColors.default;

        // Shadow
        ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
        ctx.shadowBlur = isSelected ? 15 : 8;
        ctx.shadowOffsetX = 2;
        ctx.shadowOffsetY = 2;

        // Node background
        ctx.beginPath();
        this.roundRect(ctx, pos.x, pos.y, this.nodeWidth, this.nodeHeight, this.nodeRadius);
        ctx.fillStyle = isSelected ? '#3a3a3a' : '#2a2a2a';
        ctx.fill();

        // Reset shadow
        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = 0;

        // Selection border
        if (isSelected) {
            ctx.strokeStyle = '#4dabf7';
            ctx.lineWidth = 3;
            ctx.stroke();
        }

        // Type indicator bar
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(pos.x + this.nodeRadius, pos.y);
        ctx.lineTo(pos.x + this.nodeWidth - this.nodeRadius, pos.y);
        ctx.arcTo(pos.x + this.nodeWidth, pos.y, pos.x + this.nodeWidth, pos.y + this.nodeRadius, this.nodeRadius);
        ctx.lineTo(pos.x + this.nodeWidth, pos.y + 6);
        ctx.lineTo(pos.x, pos.y + 6);
        ctx.lineTo(pos.x, pos.y + this.nodeRadius);
        ctx.arcTo(pos.x, pos.y, pos.x + this.nodeRadius, pos.y, this.nodeRadius);
        ctx.fill();

        // Title text
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 12px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const title = encounter.name || 'Unnamed';
        const truncatedTitle = title.length > 18 ? title.substring(0, 16) + '...' : title;
        ctx.fillText(truncatedTitle, pos.x + this.nodeWidth / 2, pos.y + 25);

        // Type label
        ctx.font = '10px Arial';
        ctx.fillStyle = '#aaa';
        ctx.fillText(encounter.type || 'unknown', pos.x + this.nodeWidth / 2, pos.y + 45);

        // Connection points
        this.drawConnectionPoint(pos.x, pos.y + this.nodeHeight / 2, 'input');
        this.drawConnectionPoint(pos.x + this.nodeWidth, pos.y + this.nodeHeight / 2, 'output');
    }

    drawConnectionPoint(x, y, type) {
        const ctx = this.ctx;
        ctx.beginPath();
        ctx.arc(x, y, 5, 0, Math.PI * 2);
        ctx.fillStyle = type === 'output' ? '#4dabf7' : '#aaa';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1;
        ctx.stroke();
    }

    roundRect(ctx, x, y, width, height, radius) {
        ctx.moveTo(x + radius, y);
        ctx.lineTo(x + width - radius, y);
        ctx.arcTo(x + width, y, x + width, y + radius, radius);
        ctx.lineTo(x + width, y + height - radius);
        ctx.arcTo(x + width, y + height, x + width - radius, y + height, radius);
        ctx.lineTo(x + radius, y + height);
        ctx.arcTo(x, y + height, x, y + height - radius, radius);
        ctx.lineTo(x, y + radius);
        ctx.arcTo(x, y, x + radius, y, radius);
    }

    // ==========================================================================
    // EVENT HANDLING
    // ==========================================================================

    handleMouseDown(e) {
        const pos = this.getMousePos(e);
        this.mousePos = { x: e.offsetX, y: e.offsetY };

        // Check if clicking on output connection point
        const outputHit = this.hitTestOutput(pos);
        if (outputHit) {
            this.isConnecting = true;
            this.connectFrom = outputHit.id;
            return;
        }

        // Check if clicking on node
        const hitNode = this.hitTestNode(pos);
        if (hitNode) {
            if (e.button === 0) { // Left click
                this.isDragging = true;
                this.dragTarget = hitNode;
                this.dragOffset = {
                    x: pos.x - hitNode.position.x,
                    y: pos.y - hitNode.position.y,
                };

                // Select node
                this.selectedId = hitNode.id;
                this.callbacks.onSelectEncounter?.(hitNode);
                this.render();
            }
            return;
        }

        // Start panning
        if (e.button === 0 || e.button === 1) {
            this.isPanning = true;
            this.dragOffset = { x: e.offsetX, y: e.offsetY };
        }
    }

    handleMouseMove(e) {
        this.mousePos = { x: e.offsetX, y: e.offsetY };
        const pos = this.getMousePos(e);

        if (this.isDragging && this.dragTarget) {
            this.dragTarget.position = {
                x: pos.x - this.dragOffset.x,
                y: pos.y - this.dragOffset.y,
            };
            this.callbacks.onMoveEncounter?.(this.dragTarget.id, this.dragTarget.position.x, this.dragTarget.position.y);
            this.render();
        } else if (this.isPanning) {
            const dx = e.offsetX - this.dragOffset.x;
            const dy = e.offsetY - this.dragOffset.y;
            this.panX += dx;
            this.panY += dy;
            this.dragOffset = { x: e.offsetX, y: e.offsetY };
            this.render();
        } else if (this.isConnecting) {
            this.render();
        }
    }

    handleMouseUp(e) {
        if (this.isConnecting) {
            const pos = this.getMousePos(e);
            const inputHit = this.hitTestInput(pos);

            if (inputHit && inputHit.id !== this.connectFrom) {
                this.callbacks.onCreateConnection?.(this.connectFrom, inputHit.id);
            }

            this.isConnecting = false;
            this.connectFrom = null;
            this.render();
        }

        this.isDragging = false;
        this.isPanning = false;
        this.dragTarget = null;
    }

    handleDoubleClick(e) {
        const pos = this.getMousePos(e);
        const hitNode = this.hitTestNode(pos);

        if (hitNode) {
            this.callbacks.onSelectEncounter?.(hitNode);
        }
    }

    handleWheel(e) {
        e.preventDefault();

        const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
        const oldScale = this.scale;
        this.scale = Math.max(0.25, Math.min(2, this.scale * zoomFactor));

        // Zoom toward mouse position
        const mouseX = e.offsetX;
        const mouseY = e.offsetY;
        this.panX = mouseX - (mouseX - this.panX) * (this.scale / oldScale);
        this.panY = mouseY - (mouseY - this.panY) * (this.scale / oldScale);

        this.render();
    }

    // ==========================================================================
    // HIT TESTING
    // ==========================================================================

    getMousePos(e) {
        return {
            x: (e.offsetX - this.panX) / this.scale,
            y: (e.offsetY - this.panY) / this.scale,
        };
    }

    hitTestNode(pos) {
        return this.encounters.find(e => {
            const nodePos = e.position || { x: 0, y: 0 };
            return pos.x >= nodePos.x && pos.x <= nodePos.x + this.nodeWidth &&
                   pos.y >= nodePos.y && pos.y <= nodePos.y + this.nodeHeight;
        });
    }

    hitTestOutput(pos) {
        return this.encounters.find(e => {
            const nodePos = e.position || { x: 0, y: 0 };
            const cx = nodePos.x + this.nodeWidth;
            const cy = nodePos.y + this.nodeHeight / 2;
            const dist = Math.sqrt((pos.x - cx) ** 2 + (pos.y - cy) ** 2);
            return dist <= 10;
        });
    }

    hitTestInput(pos) {
        return this.encounters.find(e => {
            const nodePos = e.position || { x: 0, y: 0 };
            const cx = nodePos.x;
            const cy = nodePos.y + this.nodeHeight / 2;
            const dist = Math.sqrt((pos.x - cx) ** 2 + (pos.y - cy) ** 2);
            return dist <= 10;
        });
    }

    // ==========================================================================
    // HELPERS
    // ==========================================================================

    buildConnections() {
        this.connections = [];
        this.encounters.forEach(e => {
            (e.transitions || []).forEach(t => {
                this.connections.push({
                    fromId: e.id,
                    toId: t.target_id,
                    condition: t.condition,
                });
            });
        });
    }
}

export default EncounterGraph;
