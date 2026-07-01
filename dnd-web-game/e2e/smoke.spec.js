/**
 * E2E smoke test: the backend serves the game and the API answers.
 * This is the minimal end-to-end proof that page.goto('/') works — the
 * blocker that made every other spec time out (batch 58 / C3).
 */

const { test, expect } = require('@playwright/test');

test.describe('Smoke', () => {
    test('serves the game page at /', async ({ page }) => {
        await page.goto('/');
        await expect(page.locator('.game-container')).toBeVisible({ timeout: 10000 });
    });

    test('loads the frontend modules without console errors', async ({ page }) => {
        const errors = [];
        page.on('pageerror', (e) => errors.push(String(e)));
        await page.goto('/');
        await page.waitForSelector('.game-container');
        expect(errors).toEqual([]);
    });

    test('API health responds through the same origin', async ({ request }) => {
        const res = await request.get('/api/health');
        expect(res.ok()).toBeTruthy();
        const body = await res.json();
        expect(body.status).toBe('healthy');
    });
});
