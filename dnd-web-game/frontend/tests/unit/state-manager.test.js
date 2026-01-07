/**
 * Unit tests for StateManager
 * Tests state management, subscriptions, and persistence.
 */

// Mock StateManager implementation
class StateManager {
    constructor(initialState = {}) {
        this.state = { ...initialState };
        this.subscribers = new Map();
        this.history = [];
        this.historyIndex = -1;
        this.maxHistory = 50;
    }

    getState() {
        return { ...this.state };
    }

    setState(updates, recordHistory = true) {
        if (recordHistory) {
            this.history = this.history.slice(0, this.historyIndex + 1);
            this.history.push({ ...this.state });
            if (this.history.length > this.maxHistory) {
                this.history.shift();
            } else {
                this.historyIndex++;
            }
        }

        const oldState = { ...this.state };
        this.state = { ...this.state, ...updates };

        // Notify subscribers
        for (const [key, callbacks] of this.subscribers) {
            if (key in updates) {
                for (const callback of callbacks) {
                    callback(this.state[key], oldState[key]);
                }
            }
        }
    }

    subscribe(key, callback) {
        if (!this.subscribers.has(key)) {
            this.subscribers.set(key, new Set());
        }
        this.subscribers.get(key).add(callback);

        return () => {
            this.subscribers.get(key).delete(callback);
        };
    }

    undo() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            this.state = { ...this.history[this.historyIndex] };
            return true;
        }
        return false;
    }

    redo() {
        if (this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            this.state = { ...this.history[this.historyIndex] };
            return true;
        }
        return false;
    }

    save(key = 'dnd-engine-state') {
        try {
            localStorage.setItem(key, JSON.stringify(this.state));
            return true;
        } catch (e) {
            return false;
        }
    }

    load(key = 'dnd-engine-state') {
        try {
            const saved = localStorage.getItem(key);
            if (saved) {
                this.state = JSON.parse(saved);
                return true;
            }
        } catch (e) {}
        return false;
    }

    reset(initialState = {}) {
        this.state = { ...initialState };
        this.history = [];
        this.historyIndex = -1;
    }
}


describe('StateManager', () => {
    let stateManager;

    beforeEach(() => {
        stateManager = new StateManager({
            player: null,
            combat: null,
            settings: { volume: 0.5 }
        });
    });

    // ==================== State Access Tests ====================

    describe('getState', () => {
        test('should return current state', () => {
            const state = stateManager.getState();

            expect(state).toEqual({
                player: null,
                combat: null,
                settings: { volume: 0.5 }
            });
        });

        test('should return a copy, not the reference', () => {
            const state = stateManager.getState();
            state.player = 'modified';

            expect(stateManager.getState().player).toBeNull();
        });
    });

    // ==================== State Modification Tests ====================

    describe('setState', () => {
        test('should update state with new values', () => {
            stateManager.setState({ player: { name: 'Hero' } });

            expect(stateManager.getState().player).toEqual({ name: 'Hero' });
        });

        test('should merge with existing state', () => {
            stateManager.setState({ player: { name: 'Hero' } });

            expect(stateManager.getState().settings).toEqual({ volume: 0.5 });
        });

        test('should support nested updates', () => {
            stateManager.setState({
                settings: { ...stateManager.getState().settings, volume: 0.8 }
            });

            expect(stateManager.getState().settings.volume).toBe(0.8);
        });
    });

    // ==================== Subscription Tests ====================

    describe('subscribe', () => {
        test('should notify subscriber when subscribed key changes', () => {
            const callback = jest.fn();
            stateManager.subscribe('player', callback);

            stateManager.setState({ player: { name: 'Hero' } });

            expect(callback).toHaveBeenCalledWith(
                { name: 'Hero' },
                null
            );
        });

        test('should not notify for unrelated key changes', () => {
            const callback = jest.fn();
            stateManager.subscribe('player', callback);

            stateManager.setState({ combat: { active: true } });

            expect(callback).not.toHaveBeenCalled();
        });

        test('should support multiple subscribers', () => {
            const callback1 = jest.fn();
            const callback2 = jest.fn();

            stateManager.subscribe('player', callback1);
            stateManager.subscribe('player', callback2);

            stateManager.setState({ player: { name: 'Hero' } });

            expect(callback1).toHaveBeenCalled();
            expect(callback2).toHaveBeenCalled();
        });

        test('should return unsubscribe function', () => {
            const callback = jest.fn();
            const unsubscribe = stateManager.subscribe('player', callback);

            unsubscribe();
            stateManager.setState({ player: { name: 'Hero' } });

            expect(callback).not.toHaveBeenCalled();
        });
    });

    // ==================== History Tests ====================

    describe('History (undo/redo)', () => {
        test('should record state changes in history', () => {
            stateManager.setState({ player: { hp: 100 } });
            stateManager.setState({ player: { hp: 80 } });

            expect(stateManager.history.length).toBeGreaterThan(0);
        });

        test('should undo to previous state', () => {
            stateManager.setState({ player: { hp: 100 } });
            stateManager.setState({ player: { hp: 80 } });

            stateManager.undo();

            expect(stateManager.getState().player.hp).toBe(100);
        });

        test('should redo after undo', () => {
            stateManager.setState({ player: { hp: 100 } });
            stateManager.setState({ player: { hp: 80 } });

            stateManager.undo();
            stateManager.redo();

            expect(stateManager.getState().player.hp).toBe(80);
        });

        test('should return false when nothing to undo', () => {
            const result = stateManager.undo();

            expect(result).toBe(false);
        });

        test('should return false when nothing to redo', () => {
            const result = stateManager.redo();

            expect(result).toBe(false);
        });

        test('should limit history size', () => {
            stateManager.maxHistory = 5;

            for (let i = 0; i < 10; i++) {
                stateManager.setState({ counter: i });
            }

            expect(stateManager.history.length).toBeLessThanOrEqual(5);
        });

        test('should clear redo stack on new change', () => {
            stateManager.setState({ value: 1 });
            stateManager.setState({ value: 2 });
            stateManager.setState({ value: 3 });

            stateManager.undo();
            stateManager.setState({ value: 10 });

            const canRedo = stateManager.redo();
            expect(canRedo).toBe(false);
        });
    });

    // ==================== Persistence Tests ====================

    describe('Persistence (save/load)', () => {
        test('should save state to localStorage', () => {
            stateManager.setState({ player: { name: 'Hero' } });
            stateManager.save('test-key');

            const saved = localStorage.getItem('test-key');
            expect(saved).not.toBeNull();

            const parsed = JSON.parse(saved);
            expect(parsed.player.name).toBe('Hero');
        });

        test('should load state from localStorage', () => {
            localStorage.setItem('test-key', JSON.stringify({
                player: { name: 'Loaded Hero' }
            }));

            stateManager.load('test-key');

            expect(stateManager.getState().player.name).toBe('Loaded Hero');
        });

        test('should return true on successful save', () => {
            const result = stateManager.save();

            expect(result).toBe(true);
        });

        test('should return false when nothing to load', () => {
            const result = stateManager.load('non-existent-key');

            expect(result).toBe(false);
        });
    });

    // ==================== Reset Tests ====================

    describe('reset', () => {
        test('should reset to initial state', () => {
            stateManager.setState({ player: { hp: 50 } });
            stateManager.setState({ combat: { active: true } });

            stateManager.reset({ player: null, combat: null });

            expect(stateManager.getState().player).toBeNull();
            expect(stateManager.getState().combat).toBeNull();
        });

        test('should clear history on reset', () => {
            stateManager.setState({ value: 1 });
            stateManager.setState({ value: 2 });

            stateManager.reset({});

            expect(stateManager.history.length).toBe(0);
        });
    });

    // ==================== Combat State Tests ====================

    describe('Combat State', () => {
        test('should track combat state', () => {
            stateManager.setState({
                combat: {
                    active: true,
                    round: 1,
                    currentTurn: 'player-1',
                    initiative: ['player-1', 'enemy-1']
                }
            });

            const state = stateManager.getState();
            expect(state.combat.active).toBe(true);
            expect(state.combat.round).toBe(1);
        });

        test('should update combatant HP', () => {
            stateManager.setState({
                combat: {
                    combatants: {
                        'player-1': { hp: 45, maxHp: 45 }
                    }
                }
            });

            // Simulate damage
            const combat = { ...stateManager.getState().combat };
            combat.combatants['player-1'].hp = 35;
            stateManager.setState({ combat });

            expect(stateManager.getState().combat.combatants['player-1'].hp).toBe(35);
        });
    });
});
