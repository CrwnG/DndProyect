/**
 * Batch 62 (V2): battlefield surfaces flow through the REAL StateManager.
 *
 * The backend now includes `surfaces: [{x, y, type}]` in every combat-state payload;
 * the grid renderer reads `grid.surfaces`. These tests pin the plumbing between them.
 */
import { StateManager } from '../../js/engine/state-manager.js';

beforeAll(() => jest.spyOn(console, 'log').mockImplementation(() => {}));
afterAll(() => console.log.mockRestore && console.log.mockRestore());

describe('StateManager surfaces plumbing', () => {
    let sm;
    beforeEach(() => { sm = new StateManager(); });

    test('grid state starts with no surfaces', () => {
        expect(sm.get('grid.surfaces')).toEqual([]);
    });

    test('updateCombatState stores the surfaces payload', () => {
        sm.updateCombatState({ surfaces: [{ x: 3, y: 3, type: 'grease' }] });
        expect(sm.get('grid.surfaces')).toEqual([{ x: 3, y: 3, type: 'grease' }]);
    });

    test('updateCombatState clears surfaces when the payload says so', () => {
        sm.updateCombatState({ surfaces: [{ x: 1, y: 1, type: 'fire' }] });
        sm.updateCombatState({ surfaces: [] });   // e.g. surface expired via decay
        expect(sm.get('grid.surfaces')).toEqual([]);
    });

    test('updateCombatState leaves surfaces alone when the payload omits them', () => {
        sm.updateCombatState({ surfaces: [{ x: 1, y: 1, type: 'fire' }] });
        sm.updateCombatState({ round: 2 });
        expect(sm.get('grid.surfaces')).toEqual([{ x: 1, y: 1, type: 'fire' }]);
    });
});
