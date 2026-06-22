/**
 * Unit tests for the REAL CombatGrid (js/combat/combat-grid.js).
 *
 * The previous file defined a fictional CombatGrid with a token-map API
 * (addToken/removeToken/getTokenAt) that the shipped module does NOT have — the
 * real grid is a canvas renderer driven by the StateManager. jsdom has no canvas,
 * so we stub a 2D context and assert what's testable WITHOUT pixel rendering:
 * that the real constructor wires up against CONFIG and the canvas cleanly.
 */
import { CONFIG } from '../../js/config.js';

// Stub the 2D context jsdom doesn't provide. Every method the renderer calls is a
// no-op; we only care that construction + setup run against the real class.
function stubCanvasContext() {
    const noop = () => {};
    const ctx = new Proxy({}, {
        get: (_t, prop) => {
            if (prop === 'canvas') return null;
            if (prop === 'measureText') return () => ({ width: 0 });
            if (prop === 'createLinearGradient' || prop === 'createRadialGradient')
                return () => ({ addColorStop: noop });
            return noop;
        },
    });
    HTMLCanvasElement.prototype.getContext = jest.fn(() => ctx);
    return ctx;
}

describe('CombatGrid (real module)', () => {
    let CombatGrid;

    beforeAll(async () => {
        jest.spyOn(console, 'log').mockImplementation(() => {});
        stubCanvasContext();
        // Imported after the canvas stub so module-level use is safe.
        CombatGrid = (await import('../../js/combat/combat-grid.js')).default;
    });

    afterAll(() => console.log.mockRestore && console.log.mockRestore());

    function mountCanvas(id = 'grid') {
        document.body.innerHTML = `<div class="grid-wrap"><canvas id="${id}"></canvas></div>`;
        return document.getElementById(id);
    }

    test('constructs against CONFIG grid dimensions and obtains a context', () => {
        mountCanvas();
        const grid = new CombatGrid('grid');
        expect(grid.gridSize).toBe(CONFIG.GRID.SIZE);
        expect(grid.cellSize).toBe(CONFIG.GRID.CELL_SIZE);
        expect(grid.ctx).toBeTruthy();
        expect(grid.canvas).toBe(document.getElementById('grid'));
    });

    test('initializes empty animation/stacking/ground-item state', () => {
        mountCanvas();
        const grid = new CombatGrid('grid');
        expect(Array.isArray(grid.animations)).toBe(true);
        expect(grid.animations).toHaveLength(0);
        expect(grid.isAnimating).toBe(false);
        expect(grid.animatingPositions instanceof Map).toBe(true);
        expect(grid.stackedCells instanceof Map).toBe(true);
        expect(grid.groundItems instanceof Map).toBe(true);
    });

    test('creates and attaches a stacking tooltip to the canvas parent', () => {
        const canvas = mountCanvas();
        const grid = new CombatGrid('grid');
        expect(grid.stackTooltip).toBeTruthy();
        expect(grid.stackTooltip.classList.contains('stack-tooltip')).toBe(true);
        expect(canvas.parentElement.contains(grid.stackTooltip)).toBe(true);
    });
});
