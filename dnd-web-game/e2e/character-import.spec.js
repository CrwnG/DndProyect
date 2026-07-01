/**
 * E2E: character import UI against the REAL DOM (header #btn-import-character
 * opens #character-import-modal with a #character-file input).
 */

const { test, expect } = require('@playwright/test');

test.describe('Character import', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/');
        await page.waitForSelector('.game-container');
        // The campaign menu modal opens on load and its overlay covers the header —
        // wait for it, close it, and wait for it to be gone before clicking.
        const menu = page.locator('button:has-text("New Campaign")');
        await menu.waitFor({ state: 'visible' });
        await page.keyboard.press('Escape');
        await menu.waitFor({ state: 'hidden' });
    });

    test('the header button opens the import modal', async ({ page }) => {
        await page.locator('#btn-import-character').click();
        await expect(page.locator('#character-import-modal')).toBeVisible();
        await expect(page.locator('#character-file')).toBeAttached();
    });

    test('the file input accepts character files', async ({ page }) => {
        await page.locator('#btn-import-character').click();
        const accept = await page.locator('#character-file').getAttribute('accept');
        expect(accept).toBeTruthy();   // wired to real file types, not a dead input
    });
});
