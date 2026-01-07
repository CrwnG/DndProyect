/**
 * D&D Combat Engine - Touch Handler
 * Mobile touch gestures for grid interaction and navigation.
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';

/**
 * Gesture types
 */
export const GestureType = {
    TAP: 'tap',
    DOUBLE_TAP: 'double_tap',
    LONG_PRESS: 'long_press',
    SWIPE_LEFT: 'swipe_left',
    SWIPE_RIGHT: 'swipe_right',
    SWIPE_UP: 'swipe_up',
    SWIPE_DOWN: 'swipe_down',
    PINCH: 'pinch',
    PAN: 'pan'
};

/**
 * Touch Handler - Mobile gesture detection and handling
 */
class TouchHandler {
    constructor() {
        // Touch state
        this.touches = [];
        this.startTime = 0;
        this.startX = 0;
        this.startY = 0;
        this.lastTapTime = 0;

        // Gesture thresholds
        this.tapThreshold = 10;           // Max movement for tap
        this.swipeThreshold = 50;         // Min distance for swipe
        this.swipeVelocityThreshold = 0.3; // Min velocity for swipe
        this.longPressDelay = 500;        // Ms for long press
        this.doubleTapDelay = 300;        // Max ms between taps

        // Pinch zoom state
        this.initialPinchDistance = 0;
        this.currentScale = 1;
        this.minScale = 0.5;
        this.maxScale = 3;

        // Pan state
        this.isPanning = false;
        this.panStartX = 0;
        this.panStartY = 0;
        this.offsetX = 0;
        this.offsetY = 0;

        // Long press timer
        this.longPressTimer = null;

        // Enabled state
        this.enabled = true;

        // Target element
        this.target = null;

        this.init();
    }

    /**
     * Initialize touch handling
     */
    init() {
        // Detect if touch is available
        this.isTouchDevice = 'ontouchstart' in window ||
            navigator.maxTouchPoints > 0 ||
            navigator.msMaxTouchPoints > 0;

        if (this.isTouchDevice) {
            console.log('[TouchHandler] Touch device detected');
        }
    }

    /**
     * Attach touch handlers to an element
     * @param {HTMLElement} element - Target element
     */
    attach(element) {
        if (!element) return;

        this.target = element;

        // Touch events
        element.addEventListener('touchstart', (e) => this.handleTouchStart(e), { passive: false });
        element.addEventListener('touchmove', (e) => this.handleTouchMove(e), { passive: false });
        element.addEventListener('touchend', (e) => this.handleTouchEnd(e));
        element.addEventListener('touchcancel', (e) => this.handleTouchCancel(e));

        // Prevent default context menu on long press
        element.addEventListener('contextmenu', (e) => {
            if (this.isTouchDevice) {
                e.preventDefault();
            }
        });

        console.log('[TouchHandler] Attached to element');
    }

    /**
     * Detach touch handlers
     */
    detach() {
        if (this.target) {
            this.target.removeEventListener('touchstart', this.handleTouchStart);
            this.target.removeEventListener('touchmove', this.handleTouchMove);
            this.target.removeEventListener('touchend', this.handleTouchEnd);
            this.target.removeEventListener('touchcancel', this.handleTouchCancel);
            this.target = null;
        }
    }

    // ==================== Touch Event Handlers ====================

    handleTouchStart(event) {
        if (!this.enabled) return;

        this.touches = Array.from(event.touches);
        this.startTime = Date.now();

        if (this.touches.length === 1) {
            // Single touch
            const touch = this.touches[0];
            this.startX = touch.clientX;
            this.startY = touch.clientY;

            // Start long press timer
            this.longPressTimer = setTimeout(() => {
                this.handleLongPress(touch);
            }, this.longPressDelay);

        } else if (this.touches.length === 2) {
            // Two finger touch - prepare for pinch/pan
            this.cancelLongPress();
            this.initialPinchDistance = this.getDistance(this.touches[0], this.touches[1]);
            this.panStartX = (this.touches[0].clientX + this.touches[1].clientX) / 2;
            this.panStartY = (this.touches[0].clientY + this.touches[1].clientY) / 2;
        }
    }

    handleTouchMove(event) {
        if (!this.enabled) return;

        const currentTouches = Array.from(event.touches);

        if (currentTouches.length === 1) {
            // Check if moved beyond tap threshold
            const touch = currentTouches[0];
            const deltaX = touch.clientX - this.startX;
            const deltaY = touch.clientY - this.startY;
            const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

            if (distance > this.tapThreshold) {
                this.cancelLongPress();
                this.isPanning = true;

                // Emit pan event
                eventBus.emit('touch:pan', {
                    deltaX,
                    deltaY,
                    x: touch.clientX,
                    y: touch.clientY
                });
            }

        } else if (currentTouches.length === 2) {
            // Pinch zoom
            event.preventDefault(); // Prevent page zoom

            const currentDistance = this.getDistance(currentTouches[0], currentTouches[1]);
            const scale = currentDistance / this.initialPinchDistance;

            // Clamp scale
            const newScale = Math.max(this.minScale, Math.min(this.maxScale, this.currentScale * scale));

            // Get center point
            const centerX = (currentTouches[0].clientX + currentTouches[1].clientX) / 2;
            const centerY = (currentTouches[0].clientY + currentTouches[1].clientY) / 2;

            eventBus.emit('touch:pinch', {
                scale: newScale,
                centerX,
                centerY,
                deltaScale: scale
            });

            // Two-finger pan
            const panDeltaX = centerX - this.panStartX;
            const panDeltaY = centerY - this.panStartY;

            if (Math.abs(panDeltaX) > 5 || Math.abs(panDeltaY) > 5) {
                eventBus.emit('touch:pan', {
                    deltaX: panDeltaX,
                    deltaY: panDeltaY,
                    x: centerX,
                    y: centerY,
                    twoFinger: true
                });
            }

            this.panStartX = centerX;
            this.panStartY = centerY;
            this.initialPinchDistance = currentDistance;
        }
    }

    handleTouchEnd(event) {
        if (!this.enabled) return;

        this.cancelLongPress();

        const endTime = Date.now();
        const duration = endTime - this.startTime;

        // Get the touch that ended
        const changedTouches = Array.from(event.changedTouches);
        if (changedTouches.length === 0) return;

        const touch = changedTouches[0];
        const deltaX = touch.clientX - this.startX;
        const deltaY = touch.clientY - this.startY;
        const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
        const velocity = distance / duration;

        // Determine gesture type
        if (this.isPanning) {
            // End of pan
            this.isPanning = false;
            eventBus.emit('touch:panEnd', { deltaX, deltaY });

        } else if (distance < this.tapThreshold && duration < this.longPressDelay) {
            // It's a tap
            const now = Date.now();

            if (now - this.lastTapTime < this.doubleTapDelay) {
                // Double tap
                this.handleDoubleTap(touch);
                this.lastTapTime = 0;
            } else {
                // Single tap (with delay to check for double)
                this.lastTapTime = now;
                setTimeout(() => {
                    if (this.lastTapTime === now) {
                        this.handleTap(touch);
                    }
                }, this.doubleTapDelay);
            }

        } else if (distance >= this.swipeThreshold && velocity >= this.swipeVelocityThreshold) {
            // It's a swipe
            this.handleSwipe(deltaX, deltaY, velocity);
        }

        // Reset state
        this.touches = [];
    }

    handleTouchCancel(event) {
        this.cancelLongPress();
        this.isPanning = false;
        this.touches = [];
    }

    // ==================== Gesture Handlers ====================

    handleTap(touch) {
        const event = {
            type: GestureType.TAP,
            x: touch.clientX,
            y: touch.clientY,
            target: document.elementFromPoint(touch.clientX, touch.clientY)
        };

        eventBus.emit('touch:tap', event);
        eventBus.emit('touch:gesture', event);

        console.log('[TouchHandler] Tap at', touch.clientX, touch.clientY);
    }

    handleDoubleTap(touch) {
        const event = {
            type: GestureType.DOUBLE_TAP,
            x: touch.clientX,
            y: touch.clientY,
            target: document.elementFromPoint(touch.clientX, touch.clientY)
        };

        eventBus.emit('touch:doubleTap', event);
        eventBus.emit('touch:gesture', event);

        console.log('[TouchHandler] Double tap at', touch.clientX, touch.clientY);
    }

    handleLongPress(touch) {
        this.cancelLongPress();

        const event = {
            type: GestureType.LONG_PRESS,
            x: touch.clientX,
            y: touch.clientY,
            target: document.elementFromPoint(touch.clientX, touch.clientY)
        };

        eventBus.emit('touch:longPress', event);
        eventBus.emit('touch:gesture', event);

        // Vibrate if supported
        if (navigator.vibrate) {
            navigator.vibrate(50);
        }

        console.log('[TouchHandler] Long press at', touch.clientX, touch.clientY);
    }

    handleSwipe(deltaX, deltaY, velocity) {
        const absX = Math.abs(deltaX);
        const absY = Math.abs(deltaY);

        let type;
        if (absX > absY) {
            // Horizontal swipe
            type = deltaX > 0 ? GestureType.SWIPE_RIGHT : GestureType.SWIPE_LEFT;
        } else {
            // Vertical swipe
            type = deltaY > 0 ? GestureType.SWIPE_DOWN : GestureType.SWIPE_UP;
        }

        const event = {
            type,
            deltaX,
            deltaY,
            velocity
        };

        eventBus.emit('touch:swipe', event);
        eventBus.emit('touch:gesture', event);

        console.log('[TouchHandler] Swipe:', type);
    }

    // ==================== Utility Methods ====================

    cancelLongPress() {
        if (this.longPressTimer) {
            clearTimeout(this.longPressTimer);
            this.longPressTimer = null;
        }
    }

    getDistance(touch1, touch2) {
        const dx = touch1.clientX - touch2.clientX;
        const dy = touch1.clientY - touch2.clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }

    /**
     * Get grid cell coordinates from touch position
     * @param {number} clientX - Touch X position
     * @param {number} clientY - Touch Y position
     * @param {Object} gridInfo - Grid configuration
     */
    getCellFromTouch(clientX, clientY, gridInfo) {
        const { element, cellSize, offsetX, offsetY, scale } = gridInfo;

        if (!element) return null;

        const rect = element.getBoundingClientRect();
        const x = (clientX - rect.left - offsetX) / (cellSize * scale);
        const y = (clientY - rect.top - offsetY) / (cellSize * scale);

        return {
            x: Math.floor(x),
            y: Math.floor(y)
        };
    }

    /**
     * Enable/disable touch handling
     */
    setEnabled(enabled) {
        this.enabled = enabled;
    }

    /**
     * Set scale limits for pinch zoom
     */
    setScaleLimits(min, max) {
        this.minScale = min;
        this.maxScale = max;
    }

    /**
     * Set current scale (for external sync)
     */
    setScale(scale) {
        this.currentScale = scale;
    }

    /**
     * Check if device supports touch
     */
    isTouchSupported() {
        return this.isTouchDevice;
    }
}

// Export singleton
export const touchHandler = new TouchHandler();
export default touchHandler;
