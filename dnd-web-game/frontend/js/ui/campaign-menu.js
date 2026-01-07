/**
 * D&D Combat Engine - Campaign Menu
 * Main menu for selecting campaigns and managing game sessions
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';
import { toast } from './toast-notification.js';

/**
 * Escape HTML special characters to prevent XSS
 * @param {string} str - String to escape
 * @returns {string} Escaped string safe for innerHTML
 */
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

class CampaignMenu {
    constructor() {
        this.container = null;
        this.campaigns = [];
        this.selectedCampaign = null;
        this.characters = [];
        this.selectedCharacters = [];
        this.isVisible = false;

        this.init();
    }

    init() {
        this.createMenuContainer();
        this.setupEventListeners();
    }

    createMenuContainer() {
        // Create main container
        this.container = document.createElement('div');
        this.container.id = 'campaign-menu';
        this.container.className = 'campaign-menu hidden';
        this.container.innerHTML = `
            <div class="campaign-menu-backdrop"></div>
            <div class="campaign-menu-content">
                <div class="campaign-menu-header">
                    <h1>D&D Combat Engine</h1>
                    <p class="subtitle">BG3-Inspired Tactical Combat</p>
                </div>

                <div class="campaign-menu-body">
                    <!-- Main Menu Buttons -->
                    <div id="main-menu-view" class="menu-view">
                        <button class="menu-btn primary" id="btn-new-game">New Campaign</button>
                        <button class="menu-btn" id="btn-continue">Continue</button>
                        <button class="menu-btn" id="btn-load-game">Load Game</button>
                        <button class="menu-btn" id="btn-quick-combat">Quick Combat</button>
                    </div>

                    <!-- Campaign Selection View -->
                    <div id="campaign-select-view" class="menu-view hidden">
                        <h2>Select Campaign</h2>
                        <div id="campaign-list" class="campaign-list">
                            <div class="loading">Loading campaigns...</div>
                        </div>
                        <div class="menu-actions">
                            <button class="menu-btn secondary" id="btn-back-main">Back</button>
                            <button class="menu-btn" id="btn-create-campaign">Create Campaign</button>
                            <button class="menu-btn" id="btn-import-campaign">Import JSON</button>
                            <button class="menu-btn primary" id="btn-select-campaign" disabled>Select</button>
                        </div>
                    </div>

                    <!-- Campaign Import View -->
                    <div id="campaign-import-view" class="menu-view hidden">
                        <h2>Import Campaign</h2>
                        <p class="hint-text">Import a campaign from JSON file or paste campaign text</p>

                        <div class="import-tabs">
                            <button class="tab active" data-tab="json-import">JSON File</button>
                            <button class="tab" data-tab="text-import">Paste Text</button>
                        </div>

                        <div id="json-import-tab" class="tab-content">
                            <div id="campaign-drop-zone" class="drop-zone">
                                <div class="drop-zone-content">
                                    <span class="drop-icon">📁</span>
                                    <p>Drag & drop a campaign JSON file</p>
                                    <p class="drop-hint">or click to browse</p>
                                    <input type="file" id="campaign-file" accept=".json" hidden>
                                </div>
                            </div>
                        </div>

                        <div id="text-import-tab" class="tab-content hidden">
                            <textarea id="campaign-text-input" class="campaign-text-input" placeholder="Paste your campaign text here..."></textarea>
                            <input type="text" id="campaign-name-input" class="campaign-name-input" placeholder="Campaign Name">
                        </div>

                        <div id="campaign-import-error" class="import-error hidden"></div>
                        <div id="campaign-import-loading" class="import-loading hidden">
                            <div class="spinner"></div>
                            <span>Importing campaign...</span>
                        </div>

                        <div class="menu-actions">
                            <button class="menu-btn secondary" id="btn-back-from-import">Back</button>
                            <button class="menu-btn primary" id="btn-confirm-campaign-import">Import</button>
                        </div>
                    </div>

                    <!-- Party Setup View -->
                    <div id="party-setup-view" class="menu-view hidden">
                        <h2>Party Setup</h2>
                        <p class="campaign-title" id="selected-campaign-name"></p>

                        <div class="party-section">
                            <h3>Available Characters</h3>
                            <div id="character-list" class="character-list">
                                <div class="loading">Loading characters...</div>
                            </div>
                            <button class="menu-btn small" id="btn-import-character-menu">Import Character</button>
                        </div>

                        <div class="party-section">
                            <h3>Your Party</h3>
                            <div id="party-list" class="party-list">
                                <p class="empty-text">Select characters above to add to party</p>
                            </div>
                        </div>

                        <div class="menu-actions">
                            <button class="menu-btn secondary" id="btn-back-campaigns">Back</button>
                            <button class="menu-btn primary" id="btn-start-campaign" disabled>Start Adventure</button>
                        </div>
                    </div>

                    <!-- Load Game View -->
                    <div id="load-game-view" class="menu-view hidden">
                        <h2>Load Game</h2>
                        <div id="save-list" class="save-list">
                            <div class="loading">Loading saves...</div>
                        </div>
                        <div class="menu-actions">
                            <button class="menu-btn secondary" id="btn-back-from-load">Back</button>
                            <button class="menu-btn primary" id="btn-load-save" disabled>Load</button>
                        </div>
                    </div>
                </div>

                <div class="campaign-menu-footer">
                    <p>Press ESC to close</p>
                </div>
            </div>
        `;

        document.body.appendChild(this.container);
    }

    setupEventListeners() {
        // Main menu buttons
        document.getElementById('btn-new-game')?.addEventListener('click', () => this.showCampaignSelect());
        document.getElementById('btn-continue')?.addEventListener('click', () => this.handleContinue());
        document.getElementById('btn-load-game')?.addEventListener('click', () => this.showLoadGame());
        document.getElementById('btn-quick-combat')?.addEventListener('click', () => this.startQuickCombat());

        // Campaign selection
        document.getElementById('btn-back-main')?.addEventListener('click', () => this.showMainMenu());
        document.getElementById('btn-select-campaign')?.addEventListener('click', () => this.showPartySetup());
        document.getElementById('btn-create-campaign')?.addEventListener('click', () => this.openCampaignCreator());
        document.getElementById('btn-import-campaign')?.addEventListener('click', () => this.showCampaignImport());

        // Campaign import
        document.getElementById('btn-back-from-import')?.addEventListener('click', () => this.showCampaignSelect());
        document.getElementById('btn-confirm-campaign-import')?.addEventListener('click', () => this.confirmCampaignImport());

        // Campaign import tabs
        this.container.querySelectorAll('#campaign-import-view .tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchCampaignImportTab(tab.dataset.tab));
        });

        // Campaign file input and drop zone
        const campaignDropZone = document.getElementById('campaign-drop-zone');
        const campaignFileInput = document.getElementById('campaign-file');
        if (campaignDropZone && campaignFileInput) {
            campaignDropZone.addEventListener('click', () => campaignFileInput.click());
            campaignDropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                campaignDropZone.classList.add('drag-over');
            });
            campaignDropZone.addEventListener('dragleave', () => {
                campaignDropZone.classList.remove('drag-over');
            });
            campaignDropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                campaignDropZone.classList.remove('drag-over');
                const file = e.dataTransfer.files[0];
                if (file) this.handleCampaignFile(file);
            });
            campaignFileInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) this.handleCampaignFile(file);
            });
        }

        // Party setup
        document.getElementById('btn-back-campaigns')?.addEventListener('click', () => this.showCampaignSelect());
        document.getElementById('btn-import-character-menu')?.addEventListener('click', () => this.openCharacterImport());
        document.getElementById('btn-start-campaign')?.addEventListener('click', () => this.startCampaign());

        // Load game
        document.getElementById('btn-back-from-load')?.addEventListener('click', () => this.showMainMenu());
        document.getElementById('btn-load-save')?.addEventListener('click', () => this.loadSelectedSave());

        // Backdrop click to close (when allowed)
        this.container.querySelector('.campaign-menu-backdrop')?.addEventListener('click', () => {
            // Only close if not in initial state
            if (state.get('combat.id')) {
                this.hide();
            }
        });

        // ESC key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible && state.get('combat.id')) {
                this.hide();
            }
        });

        // Listen for campaign events
        eventBus.on(EVENTS.CAMPAIGN_STARTED, () => this.hide());

        // Listen for character imports to refresh the list
        eventBus.on(EVENTS.CHARACTER_IMPORTED, async (data) => {
            console.log('[CampaignMenu] Character imported:', data);
            // Refresh character list if in party setup view
            if (this.isVisible) {
                await this.loadCharacters();
            }
        });
    }

    // =============================================================================
    // View Management
    // =============================================================================

    showView(viewId) {
        // Hide all views
        this.container.querySelectorAll('.menu-view').forEach(view => {
            view.classList.add('hidden');
        });

        // Show requested view
        const view = document.getElementById(viewId);
        if (view) {
            view.classList.remove('hidden');
        }
    }

    show() {
        this.container.classList.remove('hidden');
        this.isVisible = true;
        this.showMainMenu();
    }

    hide() {
        this.container.classList.add('hidden');
        this.isVisible = false;
    }

    showMainMenu() {
        this.showView('main-menu-view');

        // Update continue button state
        const continueBtn = document.getElementById('btn-continue');
        const hasSession = !!state.get('session.id');
        if (continueBtn) {
            continueBtn.disabled = !hasSession;
            continueBtn.classList.toggle('disabled', !hasSession);
        }
    }

    // =============================================================================
    // Campaign Selection
    // =============================================================================

    async showCampaignSelect() {
        this.showView('campaign-select-view');
        await this.loadCampaigns();
    }

    async loadCampaigns() {
        const listEl = document.getElementById('campaign-list');
        listEl.innerHTML = '<div class="loading">Loading campaigns...</div>';

        try {
            const response = await api.listCampaigns();
            this.campaigns = response.campaigns || [];

            if (this.campaigns.length === 0) {
                listEl.innerHTML = '<p class="empty-text">No campaigns available</p>';
                return;
            }

            listEl.innerHTML = '';
            for (const campaign of this.campaigns) {
                const card = this.createCampaignCard(campaign);
                listEl.appendChild(card);
            }
        } catch (error) {
            console.error('[CampaignMenu] Failed to load campaigns:', error);
            toast.error('Failed to load campaigns');
            listEl.innerHTML = '<p class="error-text">Failed to load campaigns</p>';
        }
    }

    createCampaignCard(campaign) {
        const card = document.createElement('div');
        card.className = 'campaign-card';
        card.dataset.campaignId = campaign.id;

        card.innerHTML = `
            <h3 class="campaign-name">${escapeHtml(campaign.name)}</h3>
            <p class="campaign-author">by ${escapeHtml(campaign.author || 'Unknown')}</p>
            <p class="campaign-desc">${escapeHtml(campaign.description || 'No description')}</p>
        `;

        card.addEventListener('click', () => {
            // Deselect others
            this.container.querySelectorAll('.campaign-card').forEach(c => {
                c.classList.remove('selected');
            });

            // Select this one
            card.classList.add('selected');
            this.selectedCampaign = campaign;

            // Enable select button
            document.getElementById('btn-select-campaign').disabled = false;
        });

        return card;
    }

    // =============================================================================
    // Campaign Import
    // =============================================================================

    showCampaignImport() {
        this.showView('campaign-import-view');
        this.pendingCampaignData = null;
        this.clearCampaignImportError();

        // Reset form
        const textInput = document.getElementById('campaign-text-input');
        const nameInput = document.getElementById('campaign-name-input');
        const fileInput = document.getElementById('campaign-file');
        if (textInput) textInput.value = '';
        if (nameInput) nameInput.value = '';
        if (fileInput) fileInput.value = '';
    }

    openCampaignCreator() {
        // Emit event to open the campaign creator modal
        eventBus.emit(EVENTS.OPEN_CAMPAIGN_CREATOR);
    }

    switchCampaignImportTab(tabId) {
        // Update tab buttons
        this.container.querySelectorAll('#campaign-import-view .tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabId);
        });

        // Update tab content
        const jsonTab = document.getElementById('json-import-tab');
        const textTab = document.getElementById('text-import-tab');
        if (jsonTab) jsonTab.classList.toggle('hidden', tabId !== 'json-import');
        if (textTab) textTab.classList.toggle('hidden', tabId !== 'text-import');
    }

    async handleCampaignFile(file) {
        if (!file.name.toLowerCase().endsWith('.json')) {
            this.showCampaignImportError('Please upload a JSON file');
            return;
        }

        try {
            const text = await file.text();
            this.pendingCampaignData = JSON.parse(text);
            console.log('[CampaignMenu] Campaign file loaded:', this.pendingCampaignData);

            // Show success indicator
            const dropZone = document.getElementById('campaign-drop-zone');
            if (dropZone) {
                dropZone.innerHTML = `
                    <div class="drop-zone-content success">
                        <span class="drop-icon">✅</span>
                        <p>${file.name}</p>
                        <p class="drop-hint">Ready to import</p>
                    </div>
                `;
            }
        } catch (error) {
            console.error('[CampaignMenu] Failed to parse campaign file:', error);
            toast.error('Invalid campaign file');
            this.showCampaignImportError('Invalid JSON file: ' + error.message);
        }
    }

    async confirmCampaignImport() {
        const activeTab = this.container.querySelector('#campaign-import-view .tab.active')?.dataset.tab;

        if (activeTab === 'text-import') {
            // Handle text import
            const textInput = document.getElementById('campaign-text-input');
            const nameInput = document.getElementById('campaign-name-input');
            const text = textInput?.value?.trim();
            const name = nameInput?.value?.trim();

            if (!text) {
                this.showCampaignImportError('Please paste your campaign text');
                return;
            }

            if (!name) {
                this.showCampaignImportError('Please enter a campaign name');
                return;
            }

            // Convert text to campaign structure
            this.pendingCampaignData = this.parseTextCampaign(text, name);
        } else {
            // JSON import
            if (!this.pendingCampaignData) {
                this.showCampaignImportError('Please select a campaign file');
                return;
            }
        }

        // Show loading
        const loadingEl = document.getElementById('campaign-import-loading');
        if (loadingEl) loadingEl.classList.remove('hidden');

        try {
            const response = await api.importCampaign(this.pendingCampaignData);
            console.log('[CampaignMenu] Campaign imported:', response);

            if (response.success || response.campaign_id) {
                // Success! Go back to campaign list
                this.pendingCampaignData = null;
                await this.showCampaignSelect();
            } else {
                this.showCampaignImportError('Import failed: ' + (response.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('[CampaignMenu] Campaign import failed:', error);
            toast.error('Campaign import failed');
            this.showCampaignImportError('Import failed: ' + error.message);
        } finally {
            if (loadingEl) loadingEl.classList.add('hidden');
        }
    }

    /**
     * Parse a text-based campaign into the JSON structure
     */
    parseTextCampaign(text, name) {
        // Extract title from first line if present
        const lines = text.split('\n');
        const title = name || lines[0]?.trim() || 'Imported Campaign';

        // Try to extract chapters/parts
        const chapters = [];
        const encounters = {};

        // Look for chapter markers (CHAPTER X, Part X, etc.)
        const chapterRegex = /^(?:CHAPTER|PART|ACT)\s*(\d+|[IVX]+)[:\s]*(.*)/im;
        const partRegex = /^(?:Part\s*\d+|Scene)[:\s]*(.*)/im;

        let currentChapter = null;
        let currentEncounterId = 0;
        let storyBuffer = [];

        for (const line of lines) {
            const chapterMatch = line.match(chapterRegex);
            const partMatch = line.match(partRegex);

            if (chapterMatch) {
                // Save previous chapter
                if (currentChapter && storyBuffer.length > 0) {
                    const encId = `enc-${currentEncounterId++}`;
                    encounters[encId] = {
                        type: 'story',
                        story: {
                            intro_text: storyBuffer.join('\n\n')
                        }
                    };
                    currentChapter.encounters.push(encId);
                    storyBuffer = [];
                }

                // Start new chapter
                currentChapter = {
                    id: `ch-${chapters.length + 1}`,
                    name: chapterMatch[2] || `Chapter ${chapterMatch[1]}`,
                    encounters: []
                };
                chapters.push(currentChapter);
            } else if (partMatch && currentChapter) {
                // Save story buffer as encounter
                if (storyBuffer.length > 0) {
                    const encId = `enc-${currentEncounterId++}`;
                    encounters[encId] = {
                        type: 'story',
                        story: {
                            intro_text: storyBuffer.join('\n\n')
                        }
                    };
                    currentChapter.encounters.push(encId);
                    storyBuffer = [];
                }
            } else if (line.trim()) {
                storyBuffer.push(line.trim());
            }
        }

        // Save any remaining content
        if (storyBuffer.length > 0) {
            if (!currentChapter) {
                currentChapter = {
                    id: 'ch-1',
                    name: 'Introduction',
                    encounters: []
                };
                chapters.push(currentChapter);
            }
            const encId = `enc-${currentEncounterId++}`;
            encounters[encId] = {
                type: 'story',
                story: {
                    intro_text: storyBuffer.join('\n\n')
                }
            };
            currentChapter.encounters.push(encId);
        }

        // If no chapters found, create a single chapter with the whole text
        if (chapters.length === 0) {
            chapters.push({
                id: 'ch-1',
                name: 'The Adventure',
                encounters: ['enc-0']
            });
            encounters['enc-0'] = {
                type: 'story',
                story: {
                    intro_text: text
                }
            };
        }

        return {
            id: `imported-${Date.now()}`,
            name: title,
            author: 'Imported',
            description: `Imported campaign: ${title}`,
            settings: {
                difficulty: 'normal',
                ruleset: '5e_2024'
            },
            chapters,
            encounters
        };
    }

    showCampaignImportError(message) {
        const errorEl = document.getElementById('campaign-import-error');
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.classList.remove('hidden');
        }
    }

    clearCampaignImportError() {
        const errorEl = document.getElementById('campaign-import-error');
        if (errorEl) {
            errorEl.classList.add('hidden');
        }
    }

    // =============================================================================
    // Party Setup
    // =============================================================================

    async showPartySetup() {
        if (!this.selectedCampaign) return;

        this.showView('party-setup-view');

        // Update campaign name
        document.getElementById('selected-campaign-name').textContent = this.selectedCampaign.name;

        // Load available characters
        await this.loadCharacters();
        this.updatePartyList();
    }

    async loadCharacters() {
        const listEl = document.getElementById('character-list');
        listEl.innerHTML = '<div class="loading">Loading characters...</div>';

        try {
            const response = await api.listCharacters();
            this.characters = response.characters || [];

            if (this.characters.length === 0) {
                listEl.innerHTML = `
                    <p class="empty-text">No characters imported yet</p>
                    <p class="hint-text">Import a character or use a demo character</p>
                `;

                // Add demo character button
                const demoBtn = document.createElement('button');
                demoBtn.className = 'menu-btn small';
                demoBtn.textContent = 'Create Demo Character';
                demoBtn.addEventListener('click', () => this.createDemoCharacter());
                listEl.appendChild(demoBtn);
                return;
            }

            listEl.innerHTML = '';
            for (const char of this.characters) {
                const card = this.createCharacterCard(char);
                listEl.appendChild(card);
            }
        } catch (error) {
            console.error('[CampaignMenu] Failed to load characters:', error);
            toast.error('Failed to load characters');
            listEl.innerHTML = '<p class="error-text">Failed to load characters</p>';
        }
    }

    createCharacterCard(character) {
        const card = document.createElement('div');
        card.className = 'character-card';
        card.dataset.characterId = character.id;

        const isSelected = this.selectedCharacters.some(c => c.id === character.id);
        if (isSelected) {
            card.classList.add('selected');
        }

        card.innerHTML = `
            <div class="char-info">
                <span class="char-name">${escapeHtml(character.name)}</span>
                <span class="char-class">Level ${character.level || 1} ${escapeHtml(character.class || 'Fighter')}</span>
            </div>
            <div class="char-stats">
                <span>HP: ${character.max_hp || 10}</span>
                <span>AC: ${character.ac || 10}</span>
            </div>
            <button class="delete-char-btn" title="Delete Character">×</button>
        `;

        // Click on card to select
        card.addEventListener('click', (e) => {
            // Don't select if clicking delete button
            if (e.target.classList.contains('delete-char-btn')) return;
            this.toggleCharacterSelection(character, card);
        });

        // Delete button handler
        const deleteBtn = card.querySelector('.delete-char-btn');
        deleteBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            if (confirm(`Delete "${character.name}"? This cannot be undone.`)) {
                await this.deleteCharacter(character.id);
            }
        });

        return card;
    }

    toggleCharacterSelection(character, card) {
        const index = this.selectedCharacters.findIndex(c => c.id === character.id);

        if (index >= 0) {
            // Remove from selection
            this.selectedCharacters.splice(index, 1);
            card.classList.remove('selected');
        } else {
            // Add to selection (max 4)
            if (this.selectedCharacters.length < 4) {
                this.selectedCharacters.push(character);
                card.classList.add('selected');
            }
        }

        this.updatePartyList();
    }

    updatePartyList() {
        const listEl = document.getElementById('party-list');
        const startBtn = document.getElementById('btn-start-campaign');

        if (this.selectedCharacters.length === 0) {
            listEl.innerHTML = '<p class="empty-text">Select characters above to add to party</p>';
            startBtn.disabled = true;
            return;
        }

        listEl.innerHTML = '';
        for (const char of this.selectedCharacters) {
            const item = document.createElement('div');
            item.className = 'party-member';
            item.innerHTML = `
                <span class="member-name">${escapeHtml(char.name)}</span>
                <span class="member-class">${escapeHtml(char.class || 'Fighter')} ${char.level || 1}</span>
                <button class="remove-btn" data-id="${escapeHtml(char.id)}">X</button>
            `;

            item.querySelector('.remove-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeFromParty(char.id);
            });

            listEl.appendChild(item);
        }

        startBtn.disabled = false;
    }

    removeFromParty(characterId) {
        const index = this.selectedCharacters.findIndex(c => c.id === characterId);
        if (index >= 0) {
            this.selectedCharacters.splice(index, 1);

            // Update card state
            const card = this.container.querySelector(`.character-card[data-character-id="${characterId}"]`);
            if (card) {
                card.classList.remove('selected');
            }

            this.updatePartyList();
        }
    }

    async deleteCharacter(characterId) {
        try {
            const response = await api.deleteCharacter(characterId);
            if (response.success) {
                // Remove from selected if it was selected
                this.removeFromParty(characterId);
                // Remove from character list
                this.characters = this.characters.filter(c => c.id !== characterId);
                // Re-render the character list
                await this.loadCharacters();
            } else {
                console.error('[CampaignMenu] Failed to delete character:', response.error);
            }
        } catch (error) {
            console.error('[CampaignMenu] Error deleting character:', error);
        }
    }

    async createDemoCharacter() {
        try {
            const response = await api.createDemoCharacter();
            if (response.character) {
                this.characters.push(response.character);
                await this.loadCharacters();
            }
        } catch (error) {
            console.error('[CampaignMenu] Failed to create demo character:', error);
            toast.error('Failed to create demo character');
        }
    }

    openCharacterImport() {
        // Trigger the existing character import modal
        eventBus.emit(EVENTS.OPEN_CHARACTER_IMPORT);
    }

    // =============================================================================
    // Campaign Start
    // =============================================================================

    async startCampaign() {
        if (!this.selectedCampaign || this.selectedCharacters.length === 0) {
            return;
        }

        try {
            // Fetch full character data for each selected character
            // The list endpoint only returns minimal data, so we need full stats
            const fullCharacters = await Promise.all(
                this.selectedCharacters.map(async char => {
                    try {
                        const response = await api.getCharacter(char.id);
                        if (response.success && response.combatant) {
                            // Use combatant format which has all combat stats
                            return {
                                id: char.id,
                                ...response.combatant,
                                // Ensure we have the raw character data for abilities
                                raw: response.character,
                            };
                        }
                    } catch (err) {
                        console.warn(`[CampaignMenu] Failed to fetch character ${char.id}, using list data`);
                    }
                    // Fallback to the minimal list data if fetch fails
                    return char;
                })
            );

            // DEBUG: Log the full character data received from API
            console.log('[CampaignMenu] Full characters from API:', fullCharacters);
            fullCharacters.forEach((char, i) => {
                console.log(`[CampaignMenu] Character ${i} class fields:`, {
                    'char.class': char.class,
                    'char.character_class': char.character_class,
                    'char.abilities?.class': char.abilities?.class,
                    'char.equipment': char.equipment,
                    'char.weapons': char.weapons,
                });
            });

            // Convert characters to party member format using full data
            const party = fullCharacters.map(char => {
                // Get ability scores from various possible locations
                const abilities = char.raw?.abilities || char.abilities || {};
                const combatantAbilities = char.abilities || {};
                // Stats object from backend (character_service.py)
                const stats = char.stats || {};

                // Helper to get score from nested object or direct value
                const getScore = (key, fullKey) => {
                    // Try stats object first (from character_service.py)
                    if (typeof stats[fullKey] === 'number') return stats[fullKey];
                    // Try nested object format: { str: { score: 16, mod: 3 } }
                    if (abilities[key]?.score) return abilities[key].score;
                    // Try direct value format: { str: 16 }
                    if (typeof abilities[key] === 'number') return abilities[key];
                    // Try full name format: { strength: 16 }
                    if (typeof abilities[fullKey] === 'number') return abilities[fullKey];
                    // Try combatant format: { str_score: 16 }
                    if (combatantAbilities[`${key}_score`]) return combatantAbilities[`${key}_score`];
                    // Default
                    return 10;
                };

                // Get class from multiple possible locations (filter out empty strings)
                const characterClass =
                    (stats.class && stats.class.trim()) ||
                    (char.class && String(char.class).trim()) ||
                    (char.character_class && String(char.character_class).trim()) ||
                    (char.abilities?.class && String(char.abilities.class).trim()) ||
                    'Fighter';

                // Get level from multiple possible locations
                const level =
                    stats.level ||
                    char.level ||
                    char.abilities?.level ||
                    1;

                // DEBUG: Log extracted values
                console.log(`[CampaignMenu] Character extraction: name='${char.name}', class='${characterClass}', level=${level}, str=${getScore('str', 'strength')}`);

                return {
                    name: char.name,
                    character_class: characterClass,
                    level: level,
                    max_hp: char.max_hp || char.hp || 10,
                    ac: char.ac || char.armor_class || 10,
                    speed: char.speed || 30,
                    strength: getScore('str', 'strength'),
                    dexterity: getScore('dex', 'dexterity'),
                    constitution: getScore('con', 'constitution'),
                    intelligence: getScore('int', 'intelligence'),
                    wisdom: getScore('wis', 'wisdom'),
                    charisma: getScore('cha', 'charisma'),
                    // Send weapons list for combat display
                    weapons: char.weapons || char.raw?.weapons || char.abilities?.weapons || [],
                    // Send equipment structure if available
                    equipment_data: char.equipment_data || null,
                    // Send spellcasting data if available (for Paladin, Cleric, etc.)
                    spellcasting: char.spellcasting || char.raw?.spellcasting || null,
                    // Database link for syncing progress back to Character table
                    character_id: char.id || null,
                    // Individual gold (from character database)
                    gold: char.raw?.gold || char.gold || 0,
                };
            });

            console.log('[CampaignMenu] Party created with full stats:', party);
            // Log first party member in detail
            if (party.length > 0) {
                console.log('[CampaignMenu] First party member:', JSON.stringify(party[0], null, 2));
            }

            // Create session
            const response = await api.createSession(this.selectedCampaign.id, party);

            if (response.success) {
                // Store session info in state
                state.set('session.id', response.session_id);
                state.set('session.campaignId', this.selectedCampaign.id);
                state.set('session.state', response.state);

                // Emit event
                eventBus.emit(EVENTS.CAMPAIGN_STARTED, {
                    sessionId: response.session_id,
                    campaignId: this.selectedCampaign.id,
                    state: response.state,
                });

                this.hide();
            }
        } catch (error) {
            console.error('[CampaignMenu] Failed to start campaign:', error);
            toast.error('Failed to start campaign');
        }
    }

    // =============================================================================
    // Continue & Load
    // =============================================================================

    handleContinue() {
        const sessionId = state.get('session.id');
        if (sessionId) {
            this.hide();
            eventBus.emit(EVENTS.CAMPAIGN_CONTINUED, { sessionId });
        }
    }

    async showLoadGame() {
        this.showView('load-game-view');
        await this.loadSaves();
    }

    async loadSaves() {
        const listEl = document.getElementById('save-list');
        listEl.innerHTML = '<div class="loading">Loading saves...</div>';

        try {
            const response = await api.listSaves();
            const saves = response.saves || [];

            if (saves.length === 0) {
                listEl.innerHTML = '<p class="empty-text">No saved games</p>';
                return;
            }

            listEl.innerHTML = '';
            for (const save of saves) {
                const card = this.createSaveCard(save);
                listEl.appendChild(card);
            }
        } catch (error) {
            console.error('[CampaignMenu] Failed to load saves:', error);
            toast.error('Failed to load saved games');
            listEl.innerHTML = '<p class="error-text">Failed to load saves</p>';
        }
    }

    createSaveCard(save) {
        const card = document.createElement('div');
        card.className = 'save-card';
        card.dataset.saveId = save.id;

        const date = new Date(save.created_at).toLocaleString();

        card.innerHTML = `
            <div class="save-info">
                <span class="save-name">${escapeHtml(save.name)}</span>
                <span class="save-campaign">${escapeHtml(save.campaign_name)}</span>
            </div>
            <div class="save-details">
                <span class="save-encounter">${escapeHtml(save.encounter_name)}</span>
                <span class="save-party">${escapeHtml(save.party_summary)}</span>
                <span class="save-date">${escapeHtml(date)}</span>
            </div>
        `;

        card.addEventListener('click', () => {
            this.container.querySelectorAll('.save-card').forEach(c => {
                c.classList.remove('selected');
            });
            card.classList.add('selected');
            this.selectedSave = save;
            document.getElementById('btn-load-save').disabled = false;
        });

        return card;
    }

    async loadSelectedSave() {
        if (!this.selectedSave) return;

        try {
            const response = await api.loadSave(this.selectedSave.id);

            if (response.success) {
                state.set('session.id', response.session_id);
                state.set('session.state', response.state);

                eventBus.emit(EVENTS.CAMPAIGN_LOADED, {
                    sessionId: response.session_id,
                    state: response.state,
                });

                this.hide();
            }
        } catch (error) {
            console.error('[CampaignMenu] Failed to load save:', error);
            toast.error('Failed to load saved game');
        }
    }

    // =============================================================================
    // Quick Combat (Demo Mode)
    // =============================================================================

    startQuickCombat() {
        this.hide();
        eventBus.emit(EVENTS.QUICK_COMBAT_REQUESTED);
    }
}

// Export singleton
export const campaignMenu = new CampaignMenu();
export default campaignMenu;
