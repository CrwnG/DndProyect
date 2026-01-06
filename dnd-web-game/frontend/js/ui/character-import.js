/**
 * D&D Combat Engine - Character Import UI
 * Handles character import from PDF and JSON files
 */

import api from '../api/api-client.js';
import { eventBus, EVENTS } from '../engine/event-bus.js';

class CharacterImportUI {
    constructor() {
        this.modal = null;
        this.fileInput = null;
        this.previewContainer = null;
        this.importedCharacter = null;
        this.isOpen = false;

        this.setupUI();
        this.setupEventListeners();
    }

    /**
     * Set up UI elements
     */
    setupUI() {
        this.modal = document.getElementById('character-import-modal');
        this.fileInput = document.getElementById('character-file');
        this.previewContainer = document.getElementById('character-preview');

        if (!this.modal) {
            console.warn('[CharacterImport] Modal not found in DOM');
        }
    }

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // File input change
        if (this.fileInput) {
            this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        }

        // Tab switching
        const tabs = document.querySelectorAll('#character-import-modal .tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
        });

        // Import button
        const importBtn = document.getElementById('import-confirm');
        if (importBtn) {
            importBtn.addEventListener('click', () => this.confirmImport());
        }

        // Cancel button
        const cancelBtn = document.getElementById('import-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.hide());
        }

        // URL import button
        const urlImportBtn = document.getElementById('url-import-btn');
        if (urlImportBtn) {
            urlImportBtn.addEventListener('click', () => this.handleUrlImport());
        }

        // Drag and drop
        const dropZone = document.getElementById('file-drop-zone');
        if (dropZone) {
            dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropZone.classList.add('drag-over');
            });
            dropZone.addEventListener('dragleave', () => {
                dropZone.classList.remove('drag-over');
            });
            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('drag-over');
                const file = e.dataTransfer.files[0];
                if (file) {
                    this.processFile(file);
                }
            });
        }

        // ESC key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.hide();
            }
        });
    }

    /**
     * Show the import modal
     */
    show() {
        if (this.modal) {
            this.modal.classList.remove('hidden');
            this.isOpen = true;
            this.resetState();
        }
    }

    /**
     * Hide the import modal
     */
    hide() {
        if (this.modal) {
            this.modal.classList.add('hidden');
            this.isOpen = false;
            this.resetState();
        }
    }

    /**
     * Reset modal state
     */
    resetState() {
        this.importedCharacter = null;
        if (this.fileInput) {
            this.fileInput.value = '';
        }
        if (this.previewContainer) {
            this.previewContainer.classList.add('hidden');
            this.previewContainer.innerHTML = '';
        }
        const confirmBtn = document.getElementById('import-confirm');
        if (confirmBtn) {
            confirmBtn.disabled = true;
        }
        this.hideError();
        this.hideLoading();
    }

    /**
     * Switch between tabs
     */
    switchTab(tabId) {
        // Update tab buttons
        const tabs = document.querySelectorAll('#character-import-modal .tab');
        tabs.forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabId);
        });

        // Update tab content
        const fileTab = document.getElementById('file-tab');
        const urlTab = document.getElementById('url-tab');

        if (fileTab) fileTab.classList.toggle('hidden', tabId !== 'file');
        if (urlTab) urlTab.classList.toggle('hidden', tabId !== 'url');
    }

    /**
     * Handle file selection
     */
    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            this.processFile(file);
        }
    }

    /**
     * Process uploaded file
     */
    async processFile(file) {
        const isPDF = file.name.toLowerCase().endsWith('.pdf');
        const isJSON = file.name.toLowerCase().endsWith('.json');

        if (!isPDF && !isJSON) {
            this.showError('Please upload a PDF or JSON file');
            return;
        }

        this.showLoading('Parsing character sheet...');

        try {
            let result;
            if (isPDF) {
                result = await api.importCharacterPDF(file);
            } else {
                result = await api.importCharacterJSON(file);
            }

            this.hideLoading();

            if (result.success) {
                this.importedCharacter = {
                    id: result.character_id,
                    character: result.character,
                    combatant: result.combatant,
                };
                this.showPreview(result.character, result.combatant, result.warnings);
            } else {
                this.showError('Failed to parse character sheet');
            }
        } catch (error) {
            this.hideLoading();
            this.showError(`Import failed: ${error.message}`);
        }
    }

    /**
     * Handle URL import (placeholder for Phase 10B)
     */
    async handleUrlImport() {
        const urlInput = document.getElementById('character-url');
        if (!urlInput || !urlInput.value.trim()) {
            this.showError('Please enter a D&D Beyond character URL');
            return;
        }

        const url = urlInput.value.trim();

        // Validate URL format
        if (!url.includes('dndbeyond.com/characters/')) {
            this.showError('Please enter a valid D&D Beyond character URL');
            return;
        }

        this.showError('URL import coming soon! Please use PDF or JSON import for now.');
    }

    /**
     * Show character preview
     */
    showPreview(character, combatant, warnings = []) {
        if (!this.previewContainer) return;

        const weaponsList = (character.weapons || [])
            .map(w => `<li>${w.name} (${w.damage} ${w.damage_type})</li>`)
            .join('');

        const featuresList = (character.features || [])
            .slice(0, 5)
            .map(f => `<li>${f.name}</li>`)
            .join('');

        const warningsHtml = warnings.length > 0
            ? `<div class="preview-warnings">
                 <h4>Warnings</h4>
                 <ul>${warnings.map(w => `<li>${w}</li>`).join('')}</ul>
               </div>`
            : '';

        this.previewContainer.innerHTML = `
            <div class="character-preview-card">
                <div class="preview-header">
                    <h3>${character.name || 'Unknown'}</h3>
                    <span class="preview-class">${character.species || ''} ${character.class || 'Unknown'} ${character.level || 1}</span>
                </div>

                <div class="preview-stats">
                    <div class="stat-block">
                        <span class="stat-label">HP</span>
                        <span class="stat-value">${character.hp || combatant.hp || 10}</span>
                    </div>
                    <div class="stat-block">
                        <span class="stat-label">AC</span>
                        <span class="stat-value">${character.ac || combatant.ac || 10}</span>
                    </div>
                    <div class="stat-block">
                        <span class="stat-label">Speed</span>
                        <span class="stat-value">${character.speed || 30}ft</span>
                    </div>
                </div>

                <div class="preview-abilities">
                    ${this.renderAbilities(character.abilities)}
                </div>

                ${weaponsList ? `
                <div class="preview-section">
                    <h4>Weapons</h4>
                    <ul class="weapons-list">${weaponsList}</ul>
                </div>
                ` : ''}

                ${featuresList ? `
                <div class="preview-section">
                    <h4>Features</h4>
                    <ul class="features-list">${featuresList}</ul>
                </div>
                ` : ''}

                ${warningsHtml}
            </div>
        `;

        this.previewContainer.classList.remove('hidden');

        // Enable import button
        const confirmBtn = document.getElementById('import-confirm');
        if (confirmBtn) {
            confirmBtn.disabled = false;
        }
    }

    /**
     * Render ability scores
     */
    renderAbilities(abilities) {
        if (!abilities) return '';

        const abilityOrder = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
        const abilityNames = {
            str: 'STR', dex: 'DEX', con: 'CON',
            int: 'INT', wis: 'WIS', cha: 'CHA'
        };

        return abilityOrder.map(key => {
            const ability = abilities[key] || { score: 10, mod: 0 };
            const modStr = ability.mod >= 0 ? `+${ability.mod}` : `${ability.mod}`;
            return `
                <div class="ability-block">
                    <span class="ability-name">${abilityNames[key]}</span>
                    <span class="ability-score">${ability.score || 10}</span>
                    <span class="ability-mod">${modStr}</span>
                </div>
            `;
        }).join('');
    }

    /**
     * Confirm import and start combat with character
     */
    confirmImport() {
        if (!this.importedCharacter) {
            this.showError('No character to import');
            return;
        }

        // Emit event with imported character data
        eventBus.emit(EVENTS.CHARACTER_IMPORTED, {
            characterId: this.importedCharacter.id,
            character: this.importedCharacter.character,
            combatant: this.importedCharacter.combatant,
        });

        this.hide();
    }

    /**
     * Show loading indicator
     */
    showLoading(message = 'Loading...') {
        const loadingEl = document.getElementById('import-loading');
        if (loadingEl) {
            loadingEl.textContent = message;
            loadingEl.classList.remove('hidden');
        }
    }

    /**
     * Hide loading indicator
     */
    hideLoading() {
        const loadingEl = document.getElementById('import-loading');
        if (loadingEl) {
            loadingEl.classList.add('hidden');
        }
    }

    /**
     * Show error message
     */
    showError(message) {
        const errorEl = document.getElementById('import-error');
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.classList.remove('hidden');
        }
    }

    /**
     * Hide error message
     */
    hideError() {
        const errorEl = document.getElementById('import-error');
        if (errorEl) {
            errorEl.classList.add('hidden');
        }
    }
}

// Create and export singleton instance
const characterImportUI = new CharacterImportUI();
export { characterImportUI, CharacterImportUI };
export default characterImportUI;
