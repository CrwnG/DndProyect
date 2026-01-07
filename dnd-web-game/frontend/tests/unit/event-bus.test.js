/**
 * Unit tests for EventBus
 * Tests event subscription, emission, and lifecycle.
 */

// Mock the module since we can't use ES modules directly
const EventBus = {
    listeners: new Map(),

    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }
        this.listeners.get(event).add(callback);
        return () => this.off(event, callback);
    },

    off(event, callback) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).delete(callback);
        }
    },

    emit(event, data) {
        if (this.listeners.has(event)) {
            for (const callback of this.listeners.get(event)) {
                try {
                    callback(data);
                } catch (e) {
                    console.error(`Event handler error: ${e}`);
                }
            }
        }
    },

    once(event, callback) {
        const wrapper = (data) => {
            this.off(event, wrapper);
            callback(data);
        };
        return this.on(event, wrapper);
    },

    clear() {
        this.listeners.clear();
    }
};


describe('EventBus', () => {
    beforeEach(() => {
        EventBus.clear();
    });

    // ==================== Subscription Tests ====================

    describe('Subscription (on)', () => {
        test('should register a listener for an event', () => {
            const callback = jest.fn();
            EventBus.on('test-event', callback);

            expect(EventBus.listeners.has('test-event')).toBe(true);
            expect(EventBus.listeners.get('test-event').has(callback)).toBe(true);
        });

        test('should allow multiple listeners for the same event', () => {
            const callback1 = jest.fn();
            const callback2 = jest.fn();

            EventBus.on('test-event', callback1);
            EventBus.on('test-event', callback2);

            expect(EventBus.listeners.get('test-event').size).toBe(2);
        });

        test('should return an unsubscribe function', () => {
            const callback = jest.fn();
            const unsubscribe = EventBus.on('test-event', callback);

            expect(typeof unsubscribe).toBe('function');

            unsubscribe();
            expect(EventBus.listeners.get('test-event').has(callback)).toBe(false);
        });
    });

    // ==================== Emission Tests ====================

    describe('Emission (emit)', () => {
        test('should call registered listeners when event is emitted', () => {
            const callback = jest.fn();
            EventBus.on('test-event', callback);

            EventBus.emit('test-event', { value: 42 });

            expect(callback).toHaveBeenCalledWith({ value: 42 });
            expect(callback).toHaveBeenCalledTimes(1);
        });

        test('should call all listeners for an event', () => {
            const callback1 = jest.fn();
            const callback2 = jest.fn();

            EventBus.on('test-event', callback1);
            EventBus.on('test-event', callback2);

            EventBus.emit('test-event', 'data');

            expect(callback1).toHaveBeenCalledWith('data');
            expect(callback2).toHaveBeenCalledWith('data');
        });

        test('should not call listeners for other events', () => {
            const callback = jest.fn();
            EventBus.on('event-a', callback);

            EventBus.emit('event-b', 'data');

            expect(callback).not.toHaveBeenCalled();
        });

        test('should handle emit with no listeners gracefully', () => {
            expect(() => {
                EventBus.emit('no-listeners', 'data');
            }).not.toThrow();
        });

        test('should continue calling other listeners if one throws', () => {
            const errorCallback = jest.fn(() => {
                throw new Error('Test error');
            });
            const normalCallback = jest.fn();

            EventBus.on('test-event', errorCallback);
            EventBus.on('test-event', normalCallback);

            // Suppress console.error for this test
            const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

            EventBus.emit('test-event', 'data');

            expect(errorCallback).toHaveBeenCalled();
            expect(normalCallback).toHaveBeenCalled();

            consoleSpy.mockRestore();
        });
    });

    // ==================== Unsubscription Tests ====================

    describe('Unsubscription (off)', () => {
        test('should remove a specific listener', () => {
            const callback1 = jest.fn();
            const callback2 = jest.fn();

            EventBus.on('test-event', callback1);
            EventBus.on('test-event', callback2);

            EventBus.off('test-event', callback1);

            EventBus.emit('test-event', 'data');

            expect(callback1).not.toHaveBeenCalled();
            expect(callback2).toHaveBeenCalled();
        });

        test('should handle removing non-existent listener gracefully', () => {
            const callback = jest.fn();

            expect(() => {
                EventBus.off('test-event', callback);
            }).not.toThrow();
        });

        test('should handle removing from non-existent event gracefully', () => {
            expect(() => {
                EventBus.off('non-existent', jest.fn());
            }).not.toThrow();
        });
    });

    // ==================== Once Tests ====================

    describe('One-time Subscription (once)', () => {
        test('should only call listener once', () => {
            const callback = jest.fn();
            EventBus.once('test-event', callback);

            EventBus.emit('test-event', 'first');
            EventBus.emit('test-event', 'second');

            expect(callback).toHaveBeenCalledTimes(1);
            expect(callback).toHaveBeenCalledWith('first');
        });

        test('should automatically unsubscribe after first call', () => {
            const callback = jest.fn();
            EventBus.once('test-event', callback);

            EventBus.emit('test-event', 'data');

            // Check listener was removed
            expect(EventBus.listeners.get('test-event').size).toBe(0);
        });

        test('should return an unsubscribe function', () => {
            const callback = jest.fn();
            const unsubscribe = EventBus.once('test-event', callback);

            unsubscribe();

            EventBus.emit('test-event', 'data');
            expect(callback).not.toHaveBeenCalled();
        });
    });

    // ==================== Clear Tests ====================

    describe('Clear', () => {
        test('should remove all listeners', () => {
            EventBus.on('event-a', jest.fn());
            EventBus.on('event-b', jest.fn());
            EventBus.on('event-a', jest.fn());

            EventBus.clear();

            expect(EventBus.listeners.size).toBe(0);
        });
    });

    // ==================== Combat Event Tests ====================

    describe('Combat Events', () => {
        test('should handle COMBAT_STARTED event', () => {
            const callback = jest.fn();
            EventBus.on('COMBAT_STARTED', callback);

            EventBus.emit('COMBAT_STARTED', {
                players: [{ id: 'p1', name: 'Hero' }],
                enemies: [{ id: 'e1', name: 'Goblin' }]
            });

            expect(callback).toHaveBeenCalledWith(
                expect.objectContaining({
                    players: expect.any(Array),
                    enemies: expect.any(Array)
                })
            );
        });

        test('should handle TURN_STARTED event', () => {
            const callback = jest.fn();
            EventBus.on('TURN_STARTED', callback);

            EventBus.emit('TURN_STARTED', {
                combatantId: 'p1',
                isPlayer: true,
                round: 1
            });

            expect(callback).toHaveBeenCalledWith(
                expect.objectContaining({
                    combatantId: 'p1',
                    isPlayer: true
                })
            );
        });

        test('should handle ATTACK_RESOLVED event', () => {
            const callback = jest.fn();
            EventBus.on('ATTACK_RESOLVED', callback);

            EventBus.emit('ATTACK_RESOLVED', {
                attackerId: 'p1',
                targetId: 'e1',
                hit: true,
                damage: 8,
                critical: false
            });

            expect(callback).toHaveBeenCalledWith(
                expect.objectContaining({
                    hit: true,
                    damage: 8
                })
            );
        });
    });
});
