/**
 * D&D Combat Engine - Playwright Configuration
 * End-to-end testing setup.
 */

const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
    // Test directory
    testDir: './e2e',

    // Test match patterns
    testMatch: '**/*.spec.js',

    // Parallel execution
    fullyParallel: true,

    // Fail the build on CI if you accidentally left test.only in the source code
    forbidOnly: !!process.env.CI,

    // Retry on CI only
    retries: process.env.CI ? 2 : 0,

    // Workers for parallel execution
    workers: process.env.CI ? 1 : undefined,

    // Reporter
    reporter: [
        ['html', { outputFolder: 'playwright-report' }],
        ['list']
    ],

    // Shared settings for all tests
    use: {
        // Base URL for navigation
        baseURL: 'http://localhost:8000',

        // Collect trace when retrying the failed test
        trace: 'on-first-retry',

        // Screenshot on failure
        screenshot: 'only-on-failure',

        // Video recording
        video: 'retain-on-failure',

        // Viewport size
        viewport: { width: 1280, height: 720 },

        // Action timeout
        actionTimeout: 10000,

        // Navigation timeout
        navigationTimeout: 30000,
    },

    // Test timeout
    timeout: 60000,

    // Expect timeout
    expect: {
        timeout: 5000
    },

    // Projects for different browsers
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
        {
            name: 'firefox',
            use: { ...devices['Desktop Firefox'] },
        },
        {
            name: 'webkit',
            use: { ...devices['Desktop Safari'] },
        },
        // Mobile testing
        {
            name: 'mobile-chrome',
            use: { ...devices['Pixel 5'] },
        },
        {
            name: 'mobile-safari',
            use: { ...devices['iPhone 12'] },
        },
    ],

    // Run local dev server before starting tests
    webServer: {
        command: 'cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000',
        port: 8000,
        timeout: 120000,
        reuseExistingServer: !process.env.CI,
    },
});
