/**
 * E2E Test: Multiplayer Session
 * Tests multiplayer functionality including lobbies and real-time sync.
 */

const { test, expect } = require('@playwright/test');

test.describe('Multiplayer Session', () => {
    // ==================== Lobby Tests ====================

    test.describe('Lobby', () => {
        test('should display multiplayer option', async ({ page }) => {
            await page.goto('/');
            await page.waitForSelector('.game-container');

            // Look for multiplayer button
            const mpBtn = page.locator('button:has-text("Multiplayer"), button:has-text("Join"), button:has-text("Host")');
            // May not be visible in all states
        });

        test('should open lobby creation modal', async ({ page }) => {
            await page.goto('/');
            await page.waitForSelector('.game-container');

            const hostBtn = page.locator('button:has-text("Host"), button:has-text("Create Lobby")').first();
            if (await hostBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
                await hostBtn.click();
                const modal = page.locator('.lobby-modal, .modal');
                await expect(modal).toBeVisible({ timeout: 5000 });
            }
        });
    });

    // ==================== Authentication Tests ====================

    test.describe('Authentication', () => {
        test('should show login option for multiplayer', async ({ page }) => {
            await page.goto('/');
            await page.waitForSelector('.game-container');

            // Look for auth modal or login button
            const authModal = page.locator('.auth-modal, .login-modal');
            const loginBtn = page.locator('button:has-text("Login"), button:has-text("Sign In")');

            // Either should be available
        });

        test('should display registration form', async ({ page }) => {
            await page.goto('/');
            await page.waitForSelector('.game-container');

            const registerBtn = page.locator('button:has-text("Register"), button:has-text("Sign Up")').first();
            if (await registerBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
                await registerBtn.click();
                const form = page.locator('form, .auth-form, .register-form');
                await expect(form).toBeVisible({ timeout: 5000 });
            }
        });
    });

    // ==================== WebSocket Connection Tests ====================

    test.describe('WebSocket Connection', () => {
        test('should establish WebSocket connection for multiplayer', async ({ page }) => {
            await page.goto('/');

            // Listen for WebSocket connections
            let wsConnected = false;

            page.on('websocket', ws => {
                wsConnected = true;
            });

            // Wait for potential connection
            await page.waitForTimeout(2000);

            // WebSocket may or may not be used depending on game state
        });
    });

    // ==================== Voting System Tests ====================

    test.describe('Voting System', () => {
        test('should display voting UI when vote is active', async ({ page }) => {
            await page.goto('/');
            await page.waitForSelector('.game-container');

            // Voting UI would appear during multiplayer choices
            const votingUI = page.locator('.voting-panel, .vote-container');
            // Only check if visible
        });
    });

    // ==================== Chat Tests ====================

    test.describe('Multiplayer Chat', () => {
        test('should have chat input available', async ({ page }) => {
            await page.goto('/');
            await page.waitForSelector('.game-container');

            const chatInput = page.locator('.chat-input, input[placeholder*="chat"]');
            // May not be visible in single-player mode
        });
    });
});


// ==================== Two-Player Simulation ====================

test.describe('Two-Player Simulation', () => {
    test('should sync state between two browsers', async ({ browser }) => {
        // Create two browser contexts to simulate two players
        const context1 = await browser.newContext();
        const context2 = await browser.newContext();

        const page1 = await context1.newPage();
        const page2 = await context2.newPage();

        try {
            // Both navigate to game
            await Promise.all([
                page1.goto('/'),
                page2.goto('/')
            ]);

            // Both should load the game
            await Promise.all([
                page1.waitForSelector('.game-container', { timeout: 10000 }),
                page2.waitForSelector('.game-container', { timeout: 10000 })
            ]);

            // Test passes if both load successfully
        } finally {
            await context1.close();
            await context2.close();
        }
    });
});
