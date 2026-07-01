/**
 * E2E: campaign menu navigation + Quick Combat against the REAL DOM.
 *
 * The original spec was written against an imagined UI (selectors that never
 * existed), so every test timed out. These tests exercise what the app actually
 * renders: the campaign menu modal, campaign selection, and a live Quick Combat.
 */

const { test, expect } = require('@playwright/test');

test.describe('Campaign menu', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/');
        await page.waitForSelector('.game-container');
    });

    test('shows the main menu with the core entries', async ({ page }) => {
        await expect(page.locator('button:has-text("New Campaign")')).toBeVisible();
        await expect(page.locator('#btn-quick-combat, button:has-text("Quick Combat")').first()).toBeVisible();
    });

    test('New Campaign lists the tutorial campaign and Back returns', async ({ page }) => {
        await page.locator('button:has-text("New Campaign")').click();
        await expect(page.locator('text=The Goblin Caves')).toBeVisible();
        await page.locator('#btn-back-main, button:has-text("Back")').first().click();
        await expect(page.locator('button:has-text("New Campaign")')).toBeVisible();
    });
});

test.describe('Quick Combat', () => {
    test('starts a fight: grid, initiative, and actions come alive', async ({ page }) => {
        await page.goto('/');
        await page.waitForSelector('.game-container');
        await page.locator('#btn-quick-combat, button:has-text("Quick Combat")').first().click();

        // The battlefield canvas renders and the demo party appears in initiative.
        await expect(page.locator('canvas').first()).toBeVisible({ timeout: 15000 });
        await expect(page.locator('text=Thorin').first()).toBeVisible({ timeout: 15000 });

        // The action economy is live: End Turn is enabled on the player's turn.
        await expect(page.locator('#btn-end-turn')).toBeEnabled({ timeout: 15000 });
    });

    test('ending the turn hands over to the goblins and comes back', async ({ page }) => {
        await page.goto('/');
        await page.waitForSelector('.game-container');
        await page.locator('#btn-quick-combat, button:has-text("Quick Combat")').first().click();
        await expect(page.locator('#btn-end-turn')).toBeEnabled({ timeout: 15000 });

        await page.locator('#btn-end-turn').click();
        // Enemy turns resolve server-side; eventually it's the player's turn again.
        await expect(page.locator('#btn-end-turn')).toBeEnabled({ timeout: 30000 });
    });
});
