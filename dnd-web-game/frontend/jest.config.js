/**
 * D&D Combat Engine - Jest Configuration
 * Frontend JavaScript testing setup.
 */

module.exports = {
    // Test environment
    testEnvironment: 'jsdom',

    // Root directory for tests
    roots: ['<rootDir>/tests'],

    // Test file patterns
    testMatch: [
        '**/*.test.js',
        '**/*.spec.js'
    ],

    // Module file extensions
    moduleFileExtensions: ['js', 'json'],

    // Setup files to run before each test
    setupFilesAfterEnv: ['<rootDir>/tests/setup.js'],

    // Module name mapping for imports
    moduleNameMapper: {
        // Map CSS imports to empty module
        '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
        // Map asset imports to mock
        '\\.(jpg|jpeg|png|gif|svg|mp3|wav|ogg)$': '<rootDir>/tests/__mocks__/fileMock.js',
        // Map module paths
        '^@/(.*)$': '<rootDir>/js/$1',
        '^@engine/(.*)$': '<rootDir>/js/engine/$1',
        '^@ui/(.*)$': '<rootDir>/js/ui/$1',
        '^@audio/(.*)$': '<rootDir>/js/audio/$1',
        '^@core/(.*)$': '<rootDir>/js/core/$1'
    },

    // Transform settings
    transform: {
        '^.+\\.js$': 'babel-jest'
    },

    // Ignore patterns
    transformIgnorePatterns: [
        '/node_modules/',
        '\\.pnp\\.[^\\/]+$'
    ],

    // Coverage settings
    collectCoverage: false,
    collectCoverageFrom: [
        'js/**/*.js',
        '!js/**/*.test.js',
        '!js/vendor/**'
    ],
    coverageDirectory: 'coverage',
    coverageReporters: ['text', 'lcov', 'html'],
    coverageThreshold: {
        global: {
            branches: 50,
            functions: 50,
            lines: 50,
            statements: 50
        }
    },

    // Verbose output
    verbose: true,

    // Test timeout
    testTimeout: 10000,

    // Clear mocks between tests
    clearMocks: true,

    // Globals for browser APIs
    globals: {
        'window': {},
        'document': {},
        'navigator': {},
        'localStorage': {},
        'sessionStorage': {}
    }
};
