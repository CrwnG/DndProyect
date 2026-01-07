/**
 * D&D Combat Engine - Jest Test Setup
 * Global test configuration and mocks.
 */

// ==================== Browser API Mocks ====================

// Mock localStorage
const localStorageMock = {
    store: {},
    getItem: jest.fn((key) => localStorageMock.store[key] || null),
    setItem: jest.fn((key, value) => {
        localStorageMock.store[key] = String(value);
    }),
    removeItem: jest.fn((key) => {
        delete localStorageMock.store[key];
    }),
    clear: jest.fn(() => {
        localStorageMock.store = {};
    }),
    get length() {
        return Object.keys(localStorageMock.store).length;
    },
    key: jest.fn((i) => Object.keys(localStorageMock.store)[i] || null)
};

Object.defineProperty(window, 'localStorage', {
    value: localStorageMock
});

Object.defineProperty(window, 'sessionStorage', {
    value: { ...localStorageMock, store: {} }
});

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: jest.fn().mockImplementation(query => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: jest.fn(),
        removeListener: jest.fn(),
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
        dispatchEvent: jest.fn(),
    })),
});

// Mock requestAnimationFrame
global.requestAnimationFrame = jest.fn(cb => setTimeout(cb, 16));
global.cancelAnimationFrame = jest.fn(id => clearTimeout(id));

// Mock performance.now
if (!global.performance) {
    global.performance = {};
}
global.performance.now = jest.fn(() => Date.now());

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
    constructor(callback) {
        this.callback = callback;
    }
    observe() { return null; }
    unobserve() { return null; }
    disconnect() { return null; }
};

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
    constructor(callback) {
        this.callback = callback;
    }
    observe() { return null; }
    unobserve() { return null; }
    disconnect() { return null; }
};


// ==================== Audio API Mocks ====================

class MockAudioContext {
    constructor() {
        this.state = 'running';
        this.destination = {};
    }
    createGain() {
        return {
            connect: jest.fn(),
            gain: { value: 1, setValueAtTime: jest.fn() }
        };
    }
    createBufferSource() {
        return {
            connect: jest.fn(),
            start: jest.fn(),
            stop: jest.fn(),
            buffer: null
        };
    }
    decodeAudioData() {
        return Promise.resolve({});
    }
    resume() {
        return Promise.resolve();
    }
    suspend() {
        return Promise.resolve();
    }
}

global.AudioContext = MockAudioContext;
global.webkitAudioContext = MockAudioContext;

// Mock Audio element
global.Audio = class Audio {
    constructor(src) {
        this.src = src;
        this.volume = 1;
        this.currentTime = 0;
        this.paused = true;
        this.loop = false;
    }
    play() {
        this.paused = false;
        return Promise.resolve();
    }
    pause() {
        this.paused = true;
    }
    load() {}
    addEventListener() {}
    removeEventListener() {}
};


// ==================== Fetch Mock ====================

global.fetch = jest.fn(() =>
    Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
        text: () => Promise.resolve(''),
        headers: new Map()
    })
);


// ==================== WebSocket Mock ====================

global.WebSocket = class WebSocket {
    constructor(url) {
        this.url = url;
        this.readyState = 1; // OPEN
        this.onopen = null;
        this.onmessage = null;
        this.onerror = null;
        this.onclose = null;

        setTimeout(() => {
            if (this.onopen) this.onopen({});
        }, 0);
    }
    send(data) {}
    close() {
        this.readyState = 3;
        if (this.onclose) this.onclose({});
    }
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;
};


// ==================== Canvas Mock ====================

HTMLCanvasElement.prototype.getContext = jest.fn(() => ({
    fillRect: jest.fn(),
    clearRect: jest.fn(),
    getImageData: jest.fn(() => ({
        data: new Array(4)
    })),
    putImageData: jest.fn(),
    createImageData: jest.fn(() => []),
    setTransform: jest.fn(),
    drawImage: jest.fn(),
    save: jest.fn(),
    restore: jest.fn(),
    beginPath: jest.fn(),
    moveTo: jest.fn(),
    lineTo: jest.fn(),
    closePath: jest.fn(),
    stroke: jest.fn(),
    fill: jest.fn(),
    arc: jest.fn(),
    rect: jest.fn(),
    translate: jest.fn(),
    rotate: jest.fn(),
    scale: jest.fn(),
    measureText: jest.fn(() => ({ width: 0 })),
    fillText: jest.fn(),
    strokeText: jest.fn(),
    canvas: { width: 800, height: 600 }
}));


// ==================== Speech Synthesis Mock ====================

global.speechSynthesis = {
    speak: jest.fn(),
    cancel: jest.fn(),
    pause: jest.fn(),
    resume: jest.fn(),
    getVoices: jest.fn(() => [
        { name: 'Test Voice', lang: 'en-US' }
    ]),
    speaking: false,
    pending: false,
    paused: false
};

global.SpeechSynthesisUtterance = class SpeechSynthesisUtterance {
    constructor(text) {
        this.text = text;
        this.voice = null;
        this.rate = 1;
        this.pitch = 1;
        this.volume = 1;
        this.onend = null;
        this.onerror = null;
    }
};


// ==================== Console Suppression ====================

// Suppress console output during tests (optional)
// Uncomment to reduce noise in test output
// console.log = jest.fn();
// console.warn = jest.fn();
// console.error = jest.fn();


// ==================== Test Utilities ====================

/**
 * Wait for async operations to complete
 */
global.flushPromises = () => new Promise(resolve => setImmediate(resolve));

/**
 * Create a mock event
 */
global.createMockEvent = (type, props = {}) => ({
    type,
    preventDefault: jest.fn(),
    stopPropagation: jest.fn(),
    target: document.createElement('div'),
    ...props
});

/**
 * Create a mock touch event
 */
global.createMockTouchEvent = (type, touches = []) => ({
    type,
    preventDefault: jest.fn(),
    stopPropagation: jest.fn(),
    touches: touches.map((t, i) => ({
        identifier: i,
        clientX: t.x || 0,
        clientY: t.y || 0,
        ...t
    })),
    changedTouches: touches.map((t, i) => ({
        identifier: i,
        clientX: t.x || 0,
        clientY: t.y || 0,
        ...t
    }))
});


// ==================== Cleanup ====================

beforeEach(() => {
    // Reset localStorage before each test
    localStorageMock.clear();

    // Reset fetch mock
    fetch.mockClear();

    // Clear any pending timers
    jest.clearAllTimers();
});

afterEach(() => {
    // Clean up any DOM modifications
    document.body.innerHTML = '';
});
