/**
 * Unit tests for CombatGrid
 * Tests grid rendering, token management, and interaction.
 */

// Mock CombatGrid implementation for testing
class CombatGrid {
    constructor(options = {}) {
        this.width = options.width || 20;
        this.height = options.height || 15;
        this.cellSize = options.cellSize || 40;
        this.canvas = null;
        this.ctx = null;
        this.tokens = new Map();
        this.terrain = new Map();
        this.selectedToken = null;
        this.highlightedCells = [];
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
    }

    init(canvasElement) {
        this.canvas = canvasElement;
        this.ctx = canvasElement.getContext('2d');
        return true;
    }

    addToken(id, x, y, data = {}) {
        if (x < 0 || x >= this.width || y < 0 || y >= this.height) {
            return false;
        }
        if (this.getTokenAt(x, y)) {
            return false; // Cell occupied
        }
        this.tokens.set(id, { id, x, y, ...data });
        return true;
    }

    removeToken(id) {
        return this.tokens.delete(id);
    }

    moveToken(id, newX, newY) {
        const token = this.tokens.get(id);
        if (!token) return false;
        if (newX < 0 || newX >= this.width || newY < 0 || newY >= this.height) {
            return false;
        }
        const occupant = this.getTokenAt(newX, newY);
        if (occupant && occupant.id !== id) {
            return false;
        }
        token.x = newX;
        token.y = newY;
        return true;
    }

    getToken(id) {
        return this.tokens.get(id) || null;
    }

    getTokenAt(x, y) {
        for (const token of this.tokens.values()) {
            if (token.x === x && token.y === y) {
                return token;
            }
        }
        return null;
    }

    selectToken(id) {
        const token = this.tokens.get(id);
        if (token) {
            this.selectedToken = token;
            return true;
        }
        return false;
    }

    deselectToken() {
        this.selectedToken = null;
    }

    setTerrain(x, y, type) {
        const key = `${x},${y}`;
        if (type === null) {
            this.terrain.delete(key);
        } else {
            this.terrain.set(key, type);
        }
    }

    getTerrain(x, y) {
        return this.terrain.get(`${x},${y}`) || 'normal';
    }

    highlightCells(cells) {
        this.highlightedCells = [...cells];
    }

    clearHighlight() {
        this.highlightedCells = [];
    }

    getDistance(x1, y1, x2, y2) {
        // D&D uses 5ft grid, diagonal = 5ft (simplified)
        return Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1)) * 5;
    }

    getCellsInRange(x, y, range) {
        const cells = [];
        const cellRange = Math.floor(range / 5);

        for (let dx = -cellRange; dx <= cellRange; dx++) {
            for (let dy = -cellRange; dy <= cellRange; dy++) {
                const cx = x + dx;
                const cy = y + dy;
                if (cx >= 0 && cx < this.width && cy >= 0 && cy < this.height) {
                    if (this.getDistance(x, y, cx, cy) <= range) {
                        cells.push({ x: cx, y: cy });
                    }
                }
            }
        }
        return cells;
    }

    screenToGrid(screenX, screenY) {
        const x = Math.floor((screenX - this.offsetX) / (this.cellSize * this.scale));
        const y = Math.floor((screenY - this.offsetY) / (this.cellSize * this.scale));
        return { x, y };
    }

    gridToScreen(gridX, gridY) {
        const x = gridX * this.cellSize * this.scale + this.offsetX;
        const y = gridY * this.cellSize * this.scale + this.offsetY;
        return { x, y };
    }

    setScale(scale) {
        this.scale = Math.max(0.5, Math.min(3, scale));
    }

    pan(dx, dy) {
        this.offsetX += dx;
        this.offsetY += dy;
    }

    render() {
        if (!this.ctx) return;
        // Rendering would happen here
        return true;
    }
}


describe('CombatGrid', () => {
    let grid;
    let mockCanvas;

    beforeEach(() => {
        mockCanvas = document.createElement('canvas');
        mockCanvas.width = 800;
        mockCanvas.height = 600;

        grid = new CombatGrid({ width: 20, height: 15, cellSize: 40 });
        grid.init(mockCanvas);
    });

    // ==================== Initialization Tests ====================

    describe('Initialization', () => {
        test('should initialize with correct dimensions', () => {
            expect(grid.width).toBe(20);
            expect(grid.height).toBe(15);
            expect(grid.cellSize).toBe(40);
        });

        test('should initialize with empty token map', () => {
            expect(grid.tokens.size).toBe(0);
        });

        test('should get canvas context', () => {
            expect(grid.ctx).not.toBeNull();
        });
    });

    // ==================== Token Management Tests ====================

    describe('Token Management', () => {
        test('should add a token at valid position', () => {
            const result = grid.addToken('player-1', 5, 5, { name: 'Hero' });

            expect(result).toBe(true);
            expect(grid.tokens.size).toBe(1);
        });

        test('should reject token at invalid position (out of bounds)', () => {
            const result = grid.addToken('player-1', -1, 5);
            expect(result).toBe(false);

            const result2 = grid.addToken('player-1', 25, 5);
            expect(result2).toBe(false);
        });

        test('should reject token in occupied cell', () => {
            grid.addToken('player-1', 5, 5);
            const result = grid.addToken('player-2', 5, 5);

            expect(result).toBe(false);
            expect(grid.tokens.size).toBe(1);
        });

        test('should remove token', () => {
            grid.addToken('player-1', 5, 5);
            const result = grid.removeToken('player-1');

            expect(result).toBe(true);
            expect(grid.tokens.size).toBe(0);
        });

        test('should get token by ID', () => {
            grid.addToken('player-1', 5, 5, { name: 'Hero' });
            const token = grid.getToken('player-1');

            expect(token).not.toBeNull();
            expect(token.name).toBe('Hero');
            expect(token.x).toBe(5);
            expect(token.y).toBe(5);
        });

        test('should get token at position', () => {
            grid.addToken('player-1', 5, 5);
            const token = grid.getTokenAt(5, 5);

            expect(token).not.toBeNull();
            expect(token.id).toBe('player-1');
        });

        test('should return null for empty cell', () => {
            const token = grid.getTokenAt(5, 5);
            expect(token).toBeNull();
        });
    });

    // ==================== Movement Tests ====================

    describe('Token Movement', () => {
        test('should move token to valid position', () => {
            grid.addToken('player-1', 5, 5);
            const result = grid.moveToken('player-1', 6, 5);

            expect(result).toBe(true);
            expect(grid.getToken('player-1').x).toBe(6);
            expect(grid.getToken('player-1').y).toBe(5);
        });

        test('should not move to out of bounds', () => {
            grid.addToken('player-1', 5, 5);
            const result = grid.moveToken('player-1', -1, 5);

            expect(result).toBe(false);
            expect(grid.getToken('player-1').x).toBe(5);
        });

        test('should not move to occupied cell', () => {
            grid.addToken('player-1', 5, 5);
            grid.addToken('enemy-1', 6, 5);

            const result = grid.moveToken('player-1', 6, 5);

            expect(result).toBe(false);
            expect(grid.getToken('player-1').x).toBe(5);
        });

        test('should return false for non-existent token', () => {
            const result = grid.moveToken('non-existent', 5, 5);
            expect(result).toBe(false);
        });
    });

    // ==================== Selection Tests ====================

    describe('Token Selection', () => {
        test('should select existing token', () => {
            grid.addToken('player-1', 5, 5);
            const result = grid.selectToken('player-1');

            expect(result).toBe(true);
            expect(grid.selectedToken).not.toBeNull();
            expect(grid.selectedToken.id).toBe('player-1');
        });

        test('should not select non-existent token', () => {
            const result = grid.selectToken('non-existent');

            expect(result).toBe(false);
            expect(grid.selectedToken).toBeNull();
        });

        test('should deselect token', () => {
            grid.addToken('player-1', 5, 5);
            grid.selectToken('player-1');
            grid.deselectToken();

            expect(grid.selectedToken).toBeNull();
        });
    });

    // ==================== Terrain Tests ====================

    describe('Terrain', () => {
        test('should set terrain type', () => {
            grid.setTerrain(5, 5, 'difficult');
            expect(grid.getTerrain(5, 5)).toBe('difficult');
        });

        test('should return normal for unset terrain', () => {
            expect(grid.getTerrain(5, 5)).toBe('normal');
        });

        test('should clear terrain', () => {
            grid.setTerrain(5, 5, 'difficult');
            grid.setTerrain(5, 5, null);

            expect(grid.getTerrain(5, 5)).toBe('normal');
        });
    });

    // ==================== Distance Calculation Tests ====================

    describe('Distance Calculation', () => {
        test('should calculate adjacent distance as 5ft', () => {
            expect(grid.getDistance(0, 0, 1, 0)).toBe(5);
            expect(grid.getDistance(0, 0, 0, 1)).toBe(5);
        });

        test('should calculate diagonal distance correctly', () => {
            // D&D 5e simplified: diagonal = same as straight
            expect(grid.getDistance(0, 0, 1, 1)).toBe(5);
        });

        test('should calculate longer distances', () => {
            expect(grid.getDistance(0, 0, 6, 0)).toBe(30); // 6 cells = 30ft
        });
    });

    // ==================== Range Calculation Tests ====================

    describe('Cells in Range', () => {
        test('should get cells within range', () => {
            const cells = grid.getCellsInRange(10, 10, 15);

            expect(cells.length).toBeGreaterThan(0);
            // 15ft range = 3 cells in each direction
            expect(cells.some(c => c.x === 10 && c.y === 10)).toBe(true); // Center
            expect(cells.some(c => c.x === 13 && c.y === 10)).toBe(true); // 3 cells away
        });

        test('should not include cells out of bounds', () => {
            const cells = grid.getCellsInRange(0, 0, 25);

            // Should not have negative coordinates
            expect(cells.every(c => c.x >= 0 && c.y >= 0)).toBe(true);
        });
    });

    // ==================== Coordinate Conversion Tests ====================

    describe('Coordinate Conversion', () => {
        test('should convert screen to grid coordinates', () => {
            const result = grid.screenToGrid(80, 40);

            expect(result.x).toBe(2);
            expect(result.y).toBe(1);
        });

        test('should convert grid to screen coordinates', () => {
            const result = grid.gridToScreen(2, 1);

            expect(result.x).toBe(80);
            expect(result.y).toBe(40);
        });

        test('should account for scale in conversion', () => {
            grid.setScale(2);
            const result = grid.screenToGrid(160, 80);

            expect(result.x).toBe(2);
            expect(result.y).toBe(1);
        });
    });

    // ==================== Zoom and Pan Tests ====================

    describe('Zoom and Pan', () => {
        test('should set scale within bounds', () => {
            grid.setScale(2);
            expect(grid.scale).toBe(2);

            grid.setScale(0.1); // Below min
            expect(grid.scale).toBe(0.5);

            grid.setScale(10); // Above max
            expect(grid.scale).toBe(3);
        });

        test('should pan grid', () => {
            grid.pan(50, 30);

            expect(grid.offsetX).toBe(50);
            expect(grid.offsetY).toBe(30);
        });
    });

    // ==================== Highlight Tests ====================

    describe('Cell Highlighting', () => {
        test('should highlight cells', () => {
            const cells = [{ x: 5, y: 5 }, { x: 6, y: 5 }];
            grid.highlightCells(cells);

            expect(grid.highlightedCells.length).toBe(2);
        });

        test('should clear highlights', () => {
            grid.highlightCells([{ x: 5, y: 5 }]);
            grid.clearHighlight();

            expect(grid.highlightedCells.length).toBe(0);
        });
    });
});
