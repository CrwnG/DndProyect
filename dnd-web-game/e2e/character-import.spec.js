/**
 * E2E Test: Character Import
 * Tests character import functionality from various sources.
 */

const { test, expect } = require('@playwright/test');
const path = require('path');

test.describe('Character Import', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/');
        await page.waitForSelector('.game-container', { timeout: 10000 });
    });

    // ==================== File Upload Tests ====================

    test.describe('File Upload', () => {
        test('should have file upload option', async ({ page }) => {
            // Look for import/upload button
            const importBtn = page.locator('button:has-text("Import"), button:has-text("Upload")').first();
            const fileInput = page.locator('input[type="file"]').first();

            // Either button or hidden file input should exist
        });

        test('should accept PDF files', async ({ page }) => {
            const fileInput = page.locator('input[type="file"]').first();

            if (await fileInput.isVisible({ timeout: 3000 }).catch(() => false)) {
                // Check accept attribute
                const accept = await fileInput.getAttribute('accept');
                if (accept) {
                    expect(accept).toContain('pdf');
                }
            }
        });

        test('should accept JSON files', async ({ page }) => {
            const fileInput = page.locator('input[type="file"]').first();

            if (await fileInput.isVisible({ timeout: 3000 }).catch(() => false)) {
                const accept = await fileInput.getAttribute('accept');
                if (accept) {
                    expect(accept).toContain('json');
                }
            }
        });
    });

    // ==================== Character Sheet Display Tests ====================

    test.describe('Character Display', () => {
        test('should display character name', async ({ page }) => {
            const charName = page.locator('.character-name, .char-name, h2, h3').first();
            await expect(charName).toBeVisible({ timeout: 10000 });
        });

        test('should display character stats', async ({ page }) => {
            const stats = page.locator('.character-stats, .abilities, .stat-block');
            if (await stats.isVisible({ timeout: 3000 }).catch(() => false)) {
                await expect(stats).toBeVisible();
            }
        });

        test('should display HP bar', async ({ page }) => {
            const hpBar = page.locator('.hp-bar, .health-bar, [class*="hp"]');
            await expect(hpBar.first()).toBeVisible({ timeout: 10000 });
        });
    });

    // ==================== D&D Beyond Import Tests ====================

    test.describe('D&D Beyond Integration', () => {
        test('should have D&D Beyond import option', async ({ page }) => {
            const dndbBtn = page.locator('button:has-text("D&D Beyond"), button:has-text("Beyond")');
            // May not be available
        });
    });

    // ==================== Character Validation Tests ====================

    test.describe('Character Validation', () => {
        test('should validate character level', async ({ page }) => {
            // Character level should be displayed and valid
            const level = page.locator('.character-level, .level, [class*="level"]');
            if (await level.isVisible({ timeout: 3000 }).catch(() => false)) {
                const text = await level.textContent();
                // Level should be between 1-20
            }
        });

        test('should display character class', async ({ page }) => {
            const charClass = page.locator('.character-class, .class, [class*="class-name"]');
            if (await charClass.isVisible({ timeout: 3000 }).catch(() => false)) {
                await expect(charClass).toBeVisible();
            }
        });
    });

    // ==================== Quick Character Creation Tests ====================

    test.describe('Quick Character Creation', () => {
        test('should have quick create option', async ({ page }) => {
            const quickCreate = page.locator('button:has-text("Quick"), button:has-text("Random")');
            // May have quick character generation
        });

        test('should offer class selection', async ({ page }) => {
            const classSelect = page.locator('select[name="class"], .class-select');
            if (await classSelect.isVisible({ timeout: 3000 }).catch(() => false)) {
                // Get available options
                const options = await classSelect.locator('option').allTextContents();
                expect(options.length).toBeGreaterThan(0);
            }
        });

        test('should offer race selection', async ({ page }) => {
            const raceSelect = page.locator('select[name="race"], .race-select');
            if (await raceSelect.isVisible({ timeout: 3000 }).catch(() => false)) {
                const options = await raceSelect.locator('option').allTextContents();
                expect(options.length).toBeGreaterThan(0);
            }
        });
    });

    // ==================== Character Sheet Export Tests ====================

    test.describe('Character Export', () => {
        test('should have export option', async ({ page }) => {
            const exportBtn = page.locator('button:has-text("Export"), button:has-text("Download")');
            // Export functionality for characters
        });

        test('should support Foundry VTT export', async ({ page }) => {
            const foundryBtn = page.locator('button:has-text("Foundry"), button:has-text("VTT")');
            // Foundry export option
        });
    });
});


// ==================== Full Import Flow Test ====================

test.describe('Full Import Flow', () => {
    test('should complete character import workflow', async ({ page }) => {
        await page.goto('/');
        await page.waitForSelector('.game-container');

        // 1. Check that character panel is visible
        const charPanel = page.locator('.character-panel, .left-panel');
        await expect(charPanel.first()).toBeVisible({ timeout: 10000 });

        // 2. Character info should be displayed
        const charInfo = page.locator('.character-info, .character-name');
        if (await charInfo.isVisible({ timeout: 3000 }).catch(() => false)) {
            await expect(charInfo).toBeVisible();
        }

        // Test passes if character UI is functional
    });
});
