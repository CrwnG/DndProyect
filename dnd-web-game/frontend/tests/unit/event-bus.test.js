/**
 * Unit tests for the REAL EventBus (js/engine/event-bus.js).
 *
 * Previously this file redefined EventBus inline as a mock object and tested the
 * mock — so it proved nothing about the shipped module. It now imports the actual
 * class and the EVENTS catalog, exercising the real on/once/off/emit/clear/
 * hasListeners behaviour (incl. the real once-uses-a-separate-Map semantics).
 */
import { EventBus, EVENTS, eventBus } from '../../js/engine/event-bus.js';

describe('EventBus (real module)', () => {
    let bus;

    beforeEach(() => {
        bus = new EventBus();
    });

    describe('on / emit', () => {
        test('calls a registered listener with the emitted data', () => {
            const cb = jest.fn();
            bus.on('test', cb);
            bus.emit('test', { value: 42 });
            expect(cb).toHaveBeenCalledWith({ value: 42 });
            expect(cb).toHaveBeenCalledTimes(1);
        });

        test('calls every listener for an event', () => {
            const a = jest.fn();
            const b = jest.fn();
            bus.on('test', a);
            bus.on('test', b);
            bus.emit('test', 'data');
            expect(a).toHaveBeenCalledWith('data');
            expect(b).toHaveBeenCalledWith('data');
        });

        test('does not call listeners of other events', () => {
            const cb = jest.fn();
            bus.on('a', cb);
            bus.emit('b', 'data');
            expect(cb).not.toHaveBeenCalled();
        });

        test('emitting with no listeners does not throw', () => {
            expect(() => bus.emit('nobody', 'data')).not.toThrow();
        });

        test('a throwing listener does not stop the others', () => {
            const boom = jest.fn(() => { throw new Error('boom'); });
            const ok = jest.fn();
            bus.on('test', boom);
            bus.on('test', ok);
            const spy = jest.spyOn(console, 'error').mockImplementation();
            bus.emit('test', 'data');
            expect(boom).toHaveBeenCalled();
            expect(ok).toHaveBeenCalled();      // survived the throw
            spy.mockRestore();
        });

        test('on returns an unsubscribe function', () => {
            const cb = jest.fn();
            const off = bus.on('test', cb);
            expect(typeof off).toBe('function');
            off();
            bus.emit('test', 'data');
            expect(cb).not.toHaveBeenCalled();
        });
    });

    describe('off', () => {
        test('removes a specific listener, leaving others', () => {
            const a = jest.fn();
            const b = jest.fn();
            bus.on('test', a);
            bus.on('test', b);
            bus.off('test', a);
            bus.emit('test', 'data');
            expect(a).not.toHaveBeenCalled();
            expect(b).toHaveBeenCalled();
        });

        test('removing an unknown listener / event is a no-op', () => {
            expect(() => bus.off('test', jest.fn())).not.toThrow();
            expect(() => bus.off('nope', jest.fn())).not.toThrow();
        });
    });

    describe('once', () => {
        test('fires only on the first emit', () => {
            const cb = jest.fn();
            bus.once('test', cb);
            bus.emit('test', 'first');
            bus.emit('test', 'second');
            expect(cb).toHaveBeenCalledTimes(1);
            expect(cb).toHaveBeenCalledWith('first');
        });

        test('leaves no once-listener after firing', () => {
            const cb = jest.fn();
            bus.once('test', cb);
            bus.emit('test', 'data');
            expect(bus.hasListeners('test')).toBe(false);
        });

        test('once and on can coexist on the same event', () => {
            const onceCb = jest.fn();
            const onCb = jest.fn();
            bus.once('test', onceCb);
            bus.on('test', onCb);
            bus.emit('test', 1);
            bus.emit('test', 2);
            expect(onceCb).toHaveBeenCalledTimes(1);
            expect(onCb).toHaveBeenCalledTimes(2);
        });
    });

    describe('hasListeners / clear', () => {
        test('hasListeners reflects on and once registrations', () => {
            expect(bus.hasListeners('test')).toBe(false);
            bus.on('test', jest.fn());
            expect(bus.hasListeners('test')).toBe(true);
            const bus2 = new EventBus();
            bus2.once('t2', jest.fn());
            expect(bus2.hasListeners('t2')).toBe(true);
        });

        test('clear(event) drops just that event', () => {
            bus.on('a', jest.fn());
            bus.on('b', jest.fn());
            bus.clear('a');
            expect(bus.hasListeners('a')).toBe(false);
            expect(bus.hasListeners('b')).toBe(true);
        });

        test('clear() drops everything', () => {
            bus.on('a', jest.fn());
            bus.once('b', jest.fn());
            bus.clear();
            expect(bus.hasListeners('a')).toBe(false);
            expect(bus.hasListeners('b')).toBe(false);
        });
    });

    describe('EVENTS catalog + singleton', () => {
        test('exposes the documented combat event names', () => {
            expect(EVENTS.COMBAT_STARTED).toBe('combat:started');
            expect(EVENTS.TURN_STARTED).toBe('turn:started');
            expect(EVENTS.ATTACK_RESOLVED).toBe('attack:resolved');
        });

        test('the exported singleton is a usable EventBus', () => {
            const cb = jest.fn();
            const off = eventBus.on(EVENTS.UI_NOTIFICATION, cb);
            eventBus.emit(EVENTS.UI_NOTIFICATION, { msg: 'hi' });
            expect(cb).toHaveBeenCalledWith({ msg: 'hi' });
            off();
        });
    });
});
