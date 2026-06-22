/**
 * Unit tests for the REAL StateManager (js/engine/state-manager.js).
 *
 * The previous file redefined a generic StateManager (with undo/redo/save/load —
 * methods the shipped module does NOT have) inline and tested that mock. This now
 * imports the actual class and exercises the real API: path get/set/update,
 * subscriptions, combat init, current-combatant / player-turn resolution, position
 * lookup, and turn-resource tracking.
 */
import { StateManager, GameMode } from '../../js/engine/state-manager.js';

// The real StateManager logs verbosely; keep test output readable.
beforeAll(() => jest.spyOn(console, 'log').mockImplementation(() => {}));
afterAll(() => console.log.mockRestore && console.log.mockRestore());

describe('StateManager (real module)', () => {
    let sm;
    beforeEach(() => { sm = new StateManager(); });

    describe('get / set / update', () => {
        test('starts in IDLE mode', () => {
            expect(sm.get('mode')).toBe(GameMode.IDLE);
        });

        test('set writes a nested path and notifies subscribers', () => {
            const cb = jest.fn();
            sm.subscribe(cb);
            sm.set('combat.round', 3);
            expect(sm.get('combat.round')).toBe(3);
            expect(cb).toHaveBeenCalled();
        });

        test('set creates missing intermediate objects', () => {
            sm.set('ui.newThing.flag', true);
            expect(sm.get('ui.newThing.flag')).toBe(true);
        });

        test('update applies several paths at once', () => {
            sm.update({ 'combat.round': 5, 'mode': GameMode.COMBAT });
            expect(sm.get('combat.round')).toBe(5);
            expect(sm.get('mode')).toBe(GameMode.COMBAT);
        });

        test('get returns undefined for an unknown path (no throw)', () => {
            expect(sm.get('nope.not.here')).toBeUndefined();
        });

        test('getState returns a deep copy, not a live reference', () => {
            const snap = sm.getState();
            snap.combat.round = 999;
            expect(sm.get('combat.round')).toBe(1);
        });
    });

    describe('subscriptions', () => {
        test('subscribe returns an unsubscribe that stops notifications', () => {
            const cb = jest.fn();
            const off = sm.subscribe(cb);
            sm.set('combat.round', 2);
            off();
            sm.set('combat.round', 3);
            expect(cb).toHaveBeenCalledTimes(1);
        });

        test('a throwing subscriber does not break notification of others', () => {
            const boom = jest.fn(() => { throw new Error('boom'); });
            const ok = jest.fn();
            sm.subscribe(boom);
            sm.subscribe(ok);
            const spy = jest.spyOn(console, 'error').mockImplementation();
            sm.set('combat.round', 2);
            expect(ok).toHaveBeenCalled();
            spy.mockRestore();
        });
    });

    describe('combat init + current combatant', () => {
        const combatData = {
            combat_id: 'c1',
            round: 1,
            current_turn_index: 0,
            initiative_order: ['p1', 'e1'],
            combatants: [
                { id: 'p1', name: 'Hero', type: 'player', current_hp: 20, max_hp: 20, ac: 16 },
                { id: 'e1', name: 'Goblin', type: 'enemy', current_hp: 7, max_hp: 7, ac: 13 },
            ],
            positions: { p1: { x: 0, y: 0 }, e1: { x: 3, y: 3 } },
        };

        test('initCombat populates combatants, initiative and mode', () => {
            sm.initCombat(combatData);
            expect(sm.get('mode')).toBe(GameMode.COMBAT);
            expect(Object.keys(sm.get('combatants'))).toEqual(['p1', 'e1']);
            expect(sm.get('combatants').p1.hp).toBe(20);   // current_hp -> hp
            expect(sm.get('initiative')).toEqual(['p1', 'e1']);
        });

        test('getCurrentCombatant follows currentTurnIndex through initiative', () => {
            sm.initCombat(combatData);
            expect(sm.getCurrentCombatant().id).toBe('p1');
            sm.set('combat.currentTurnIndex', 1);
            expect(sm.getCurrentCombatant().id).toBe('e1');
        });

        test('getCurrentCombatant returns null when the index is out of range', () => {
            sm.initCombat(combatData);
            sm.set('combat.currentTurnIndex', 99);
            expect(sm.getCurrentCombatant()).toBeNull();
        });

        test('isPlayerTurn is true only for a player-controlled combatant', () => {
            sm.initCombat(combatData);
            sm.set('playerIds', ['p1']);
            expect(sm.isPlayerTurn()).toBe(true);
            sm.set('combat.currentTurnIndex', 1);   // the goblin
            expect(sm.isPlayerTurn()).toBe(false);
        });

        test('getCombatantAtPosition handles object and array positions', () => {
            sm.initCombat(combatData);
            expect(sm.getCombatantAtPosition(0, 0).id).toBe('p1');
            sm.set('grid.positions', { e1: [3, 3] });  // array form
            expect(sm.getCombatantAtPosition(3, 3).id).toBe('e1');
            expect(sm.getCombatantAtPosition(9, 9)).toBeNull();
        });
    });

    describe('turn resources', () => {
        test('useAction / useBonusAction flip the turn flags', () => {
            expect(sm.get('turn.actionUsed')).toBe(false);
            sm.useAction();
            sm.useBonusAction();
            expect(sm.get('turn.actionUsed')).toBe(true);
            expect(sm.get('turn.bonusActionUsed')).toBe(true);
        });

        test('useMovement decrements remaining and accrues used', () => {
            sm.set('turn.movementRemaining', 30);
            sm.useMovement(10);
            expect(sm.get('turn.movementUsed')).toBe(10);
            expect(sm.get('turn.movementRemaining')).toBe(20);
        });

        test('resetTurn restores a fresh action economy', () => {
            sm.useAction();
            sm.initCombat({
                combat_id: 'c', current_turn_index: 0, initiative_order: ['p1'],
                combatants: [{ id: 'p1', name: 'Hero', type: 'player', current_hp: 10, max_hp: 10, ac: 12,
                              stats: { class: 'fighter', level: 5, speed: 30 } }],
            });
            sm.set('playerIds', ['p1']);
            sm.resetTurn();
            expect(sm.get('turn.actionUsed')).toBe(false);
            expect(sm.get('turn.maxAttacks')).toBe(2);   // fighter 5 -> Extra Attack
        });
    });

    describe('reset', () => {
        test('reset returns to the initial state', () => {
            sm.set('combat.round', 9);
            sm.update({ mode: GameMode.COMBAT });
            sm.reset();
            expect(sm.get('combat.round')).toBe(1);
            expect(sm.get('mode')).toBe(GameMode.IDLE);
        });
    });
});
