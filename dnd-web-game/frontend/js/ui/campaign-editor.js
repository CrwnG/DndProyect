/**
 * D&D Combat Engine - Campaign Editor
 * Visual campaign modification interface with drag-and-drop.
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import api from '../api/api-client.js';
import { errorHandler } from '../core/error-handler.js';

/**
 * Campaign Editor Component
 */
class CampaignEditor {
    constructor() {
        this.container = null;
        this.campaign = null;
        this.isVisible = false;
        this.isDirty = false;
        this.selectedChapter = null;
        this.selectedEncounter = null;
        this.draggedItem = null;

        this.init();
    }

    init() {
        this.createContainer();
        this.setupEventListeners();
    }

    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'campaign-editor';
        this.container.className = 'campaign-editor hidden';
        this.container.innerHTML = `
            <div class="editor-backdrop"></div>
            <div class="editor-content">
                <header class="editor-header">
                    <div class="editor-title-section">
                        <h2 class="editor-title">Campaign Editor</h2>
                        <span class="editor-campaign-name"></span>
                    </div>
                    <div class="editor-actions">
                        <button class="editor-btn btn-undo" title="Undo">↶</button>
                        <button class="editor-btn btn-save" title="Save Changes">💾 Save</button>
                        <button class="editor-btn btn-close" title="Close">&times;</button>
                    </div>
                </header>

                <div class="editor-body">
                    <!-- Left Sidebar: Chapter/Encounter Tree -->
                    <aside class="editor-sidebar">
                        <div class="sidebar-header">
                            <h3>Structure</h3>
                            <button class="btn-add-chapter" title="Add Chapter">+ Chapter</button>
                        </div>
                        <div class="chapter-tree"></div>
                    </aside>

                    <!-- Main Editor Area -->
                    <main class="editor-main">
                        <!-- Campaign Metadata Panel (default view) -->
                        <div class="edit-panel panel-campaign">
                            <h3>Campaign Settings</h3>
                            <div class="form-group">
                                <label for="campaign-name">Name</label>
                                <input type="text" id="campaign-name" class="form-input">
                            </div>
                            <div class="form-group">
                                <label for="campaign-desc">Description</label>
                                <textarea id="campaign-desc" class="form-textarea" rows="4"></textarea>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label for="campaign-theme">Theme</label>
                                    <select id="campaign-theme" class="form-select">
                                        <option value="adventure">Adventure</option>
                                        <option value="dark">Dark Fantasy</option>
                                        <option value="heroic">Heroic</option>
                                        <option value="mystery">Mystery</option>
                                        <option value="horror">Horror</option>
                                        <option value="comedy">Comedy</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label for="campaign-difficulty">Difficulty</label>
                                    <select id="campaign-difficulty" class="form-select">
                                        <option value="easy">Easy</option>
                                        <option value="medium">Medium</option>
                                        <option value="hard">Hard</option>
                                        <option value="deadly">Deadly</option>
                                    </select>
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Party Level Range</label>
                                    <div class="level-range">
                                        <input type="number" id="level-min" min="1" max="20" value="1" class="form-input-small">
                                        <span>to</span>
                                        <input type="number" id="level-max" min="1" max="20" value="5" class="form-input-small">
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Encounter Edit Panel -->
                        <div class="edit-panel panel-encounter hidden">
                            <h3>Edit Encounter</h3>
                            <div class="form-group">
                                <label for="encounter-name">Name</label>
                                <input type="text" id="encounter-name" class="form-input">
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label for="encounter-type">Type</label>
                                    <select id="encounter-type" class="form-select">
                                        <option value="combat">Combat</option>
                                        <option value="social">Social</option>
                                        <option value="exploration">Exploration</option>
                                        <option value="puzzle">Puzzle</option>
                                        <option value="choice">Choice</option>
                                        <option value="rest">Rest</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label for="encounter-difficulty">Difficulty</label>
                                    <select id="encounter-difficulty" class="form-select">
                                        <option value="easy">Easy</option>
                                        <option value="medium">Medium</option>
                                        <option value="hard">Hard</option>
                                        <option value="deadly">Deadly</option>
                                    </select>
                                </div>
                            </div>
                            <div class="form-group">
                                <label for="encounter-story">Story Introduction</label>
                                <textarea id="encounter-story" class="form-textarea" rows="4" placeholder="The text shown before the encounter begins..."></textarea>
                            </div>
                            <div class="form-group">
                                <label for="encounter-outcome">Outcome Text</label>
                                <textarea id="encounter-outcome" class="form-textarea" rows="3" placeholder="The text shown after the encounter ends..."></textarea>
                            </div>

                            <!-- Combat-specific: Enemies -->
                            <div class="encounter-enemies">
                                <div class="section-header">
                                    <h4>Enemies</h4>
                                    <button class="btn-add-enemy">+ Add Enemy</button>
                                </div>
                                <div class="enemy-list"></div>
                            </div>

                            <!-- Choice-specific: Options -->
                            <div class="encounter-choices hidden">
                                <div class="section-header">
                                    <h4>Choices</h4>
                                    <button class="btn-add-choice">+ Add Choice</button>
                                </div>
                                <div class="choice-list"></div>
                            </div>

                            <div class="panel-actions">
                                <button class="btn-delete-encounter">Delete Encounter</button>
                            </div>
                        </div>

                        <!-- NPC Edit Panel -->
                        <div class="edit-panel panel-npc hidden">
                            <h3>Edit NPC</h3>
                            <div class="form-group">
                                <label for="npc-name">Name</label>
                                <input type="text" id="npc-name" class="form-input">
                            </div>
                            <div class="form-group">
                                <label for="npc-role">Role</label>
                                <select id="npc-role" class="form-select">
                                    <option value="companion">Companion</option>
                                    <option value="villain">Villain</option>
                                    <option value="quest_giver">Quest Giver</option>
                                    <option value="merchant">Merchant</option>
                                    <option value="neutral">Neutral</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="npc-disposition">Disposition (-100 to 100)</label>
                                <input type="range" id="npc-disposition" min="-100" max="100" value="0" class="form-range">
                                <span class="disposition-value">Neutral (0)</span>
                            </div>
                            <div class="form-group">
                                <label for="npc-traits">Personality Traits</label>
                                <input type="text" id="npc-traits" class="form-input" placeholder="cynical, loyal, brave...">
                            </div>
                            <div class="form-group">
                                <label for="npc-motivation">Motivation</label>
                                <input type="text" id="npc-motivation" class="form-input">
                            </div>
                            <div class="form-group">
                                <label for="npc-secret">Secret (optional)</label>
                                <textarea id="npc-secret" class="form-textarea" rows="2" placeholder="A hidden truth players can discover..."></textarea>
                            </div>
                        </div>
                    </main>

                    <!-- Right Sidebar: Quick Actions / Preview -->
                    <aside class="editor-preview">
                        <h3>Preview</h3>
                        <div class="preview-content">
                            <p class="preview-hint">Select an encounter to preview how it will appear to players.</p>
                        </div>
                        <div class="quick-actions">
                            <button class="btn-duplicate">Duplicate Campaign</button>
                            <button class="btn-export">Export JSON</button>
                        </div>
                    </aside>
                </div>

                <!-- Unsaved Changes Warning -->
                <div class="unsaved-warning hidden">
                    <span>You have unsaved changes</span>
                </div>
            </div>
        `;

        document.body.appendChild(this.container);
    }

    setupEventListeners() {
        // Close button
        this.container.querySelector('.btn-close').addEventListener('click', () => {
            this.handleClose();
        });

        // Backdrop click
        this.container.querySelector('.editor-backdrop').addEventListener('click', () => {
            this.handleClose();
        });

        // Save button
        this.container.querySelector('.btn-save').addEventListener('click', () => {
            this.saveCampaign();
        });

        // Undo button
        this.container.querySelector('.btn-undo').addEventListener('click', () => {
            this.undoLastChange();
        });

        // Campaign metadata changes
        const campaignInputs = ['campaign-name', 'campaign-desc', 'campaign-theme', 'campaign-difficulty', 'level-min', 'level-max'];
        campaignInputs.forEach(id => {
            const el = this.container.querySelector(`#${id}`);
            if (el) {
                el.addEventListener('change', () => this.handleCampaignMetadataChange());
            }
        });

        // Encounter type change (show/hide relevant sections)
        this.container.querySelector('#encounter-type').addEventListener('change', (e) => {
            this.updateEncounterTypeUI(e.target.value);
        });

        // NPC disposition slider
        const dispositionSlider = this.container.querySelector('#npc-disposition');
        if (dispositionSlider) {
            dispositionSlider.addEventListener('input', (e) => {
                const value = parseInt(e.target.value);
                const label = this.getDispositionLabel(value);
                this.container.querySelector('.disposition-value').textContent = `${label} (${value})`;
            });
        }

        // Quick actions
        this.container.querySelector('.btn-duplicate').addEventListener('click', () => {
            this.duplicateCampaign();
        });

        this.container.querySelector('.btn-export').addEventListener('click', () => {
            this.exportCampaign();
        });

        // Add chapter button
        this.container.querySelector('.btn-add-chapter').addEventListener('click', () => {
            this.addChapter();
        });

        // Delete encounter button
        this.container.querySelector('.btn-delete-encounter').addEventListener('click', () => {
            this.deleteSelectedEncounter();
        });

        // Add enemy button
        this.container.querySelector('.btn-add-enemy').addEventListener('click', () => {
            this.addEnemy();
        });

        // Add choice button
        this.container.querySelector('.btn-add-choice').addEventListener('click', () => {
            this.addChoice();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (!this.isVisible) return;

            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                this.saveCampaign();
            } else if (e.ctrlKey && e.key === 'z') {
                e.preventDefault();
                this.undoLastChange();
            } else if (e.key === 'Escape') {
                this.handleClose();
            }
        });
    }

    // ==================== Show/Hide ====================

    async show(campaignId) {
        try {
            // Load campaign for editing
            const response = await api.post(`/api/campaign/${campaignId}/edit`);

            if (!response.success) {
                throw new Error(response.message || 'Failed to load campaign');
            }

            this.campaign = response.campaign;
            this.isDirty = false;
            this.selectedChapter = null;
            this.selectedEncounter = null;

            // Render the editor
            this.renderCampaign();

            // Show modal
            this.container.classList.remove('hidden');
            this.isVisible = true;

            console.log('[CampaignEditor] Opened for campaign:', campaignId);

        } catch (error) {
            errorHandler.handle(error, { component: 'CampaignEditor', action: 'show' });
        }
    }

    hide() {
        this.container.classList.add('hidden');
        this.isVisible = false;
    }

    handleClose() {
        if (this.isDirty) {
            if (confirm('You have unsaved changes. Discard them?')) {
                this.discardChanges();
                this.hide();
            }
        } else {
            this.hide();
        }
    }

    // ==================== Rendering ====================

    renderCampaign() {
        if (!this.campaign) return;

        // Update title
        this.container.querySelector('.editor-campaign-name').textContent = this.campaign.name;

        // Render campaign metadata
        this.container.querySelector('#campaign-name').value = this.campaign.name || '';
        this.container.querySelector('#campaign-desc').value = this.campaign.description || '';
        this.container.querySelector('#campaign-theme').value = this.campaign.theme || 'adventure';
        this.container.querySelector('#campaign-difficulty').value = this.campaign.difficulty || 'medium';

        const levelRange = this.campaign.party_level_range || [1, 5];
        this.container.querySelector('#level-min').value = levelRange[0];
        this.container.querySelector('#level-max').value = levelRange[1];

        // Render chapter tree
        this.renderChapterTree();

        // Show campaign panel by default
        this.showPanel('campaign');
    }

    renderChapterTree() {
        const treeContainer = this.container.querySelector('.chapter-tree');
        treeContainer.innerHTML = '';

        if (!this.campaign.chapters || this.campaign.chapters.length === 0) {
            treeContainer.innerHTML = '<p class="empty-message">No chapters yet. Add one to get started.</p>';
            return;
        }

        this.campaign.chapters.forEach((chapter, chapterIndex) => {
            const chapterEl = document.createElement('div');
            chapterEl.className = 'chapter-item';
            chapterEl.dataset.chapterId = chapter.id;

            chapterEl.innerHTML = `
                <div class="chapter-header">
                    <span class="chapter-toggle">▶</span>
                    <span class="chapter-name">${chapter.name || `Chapter ${chapterIndex + 1}`}</span>
                    <button class="btn-add-encounter" title="Add Encounter">+</button>
                </div>
                <div class="encounter-list collapsed"></div>
            `;

            // Chapter toggle
            const header = chapterEl.querySelector('.chapter-header');
            header.addEventListener('click', (e) => {
                if (e.target.classList.contains('btn-add-encounter')) return;
                this.toggleChapter(chapterEl);
            });

            // Add encounter button
            chapterEl.querySelector('.btn-add-encounter').addEventListener('click', (e) => {
                e.stopPropagation();
                this.addEncounter(chapter.id);
            });

            // Render encounters
            const encounterList = chapterEl.querySelector('.encounter-list');
            if (chapter.encounters) {
                chapter.encounters.forEach((encounter, encIndex) => {
                    const encEl = this.createEncounterElement(encounter, chapter.id);
                    encounterList.appendChild(encEl);
                });
            }

            treeContainer.appendChild(chapterEl);
        });
    }

    createEncounterElement(encounter, chapterId) {
        const encEl = document.createElement('div');
        encEl.className = 'encounter-item';
        encEl.dataset.encounterId = encounter.id;
        encEl.dataset.chapterId = chapterId;
        encEl.draggable = true;

        const typeIcon = this.getEncounterTypeIcon(encounter.type);

        encEl.innerHTML = `
            <span class="encounter-icon">${typeIcon}</span>
            <span class="encounter-name">${encounter.name || 'Unnamed'}</span>
            <span class="encounter-type-badge">${encounter.type}</span>
        `;

        // Click to edit
        encEl.addEventListener('click', () => {
            this.selectEncounter(encounter.id, chapterId);
        });

        // Drag and drop
        encEl.addEventListener('dragstart', (e) => {
            this.handleDragStart(e, encounter, chapterId);
        });
        encEl.addEventListener('dragend', () => {
            this.handleDragEnd();
        });
        encEl.addEventListener('dragover', (e) => {
            this.handleDragOver(e);
        });
        encEl.addEventListener('drop', (e) => {
            this.handleDrop(e, encounter, chapterId);
        });

        return encEl;
    }

    getEncounterTypeIcon(type) {
        const icons = {
            combat: '⚔️',
            social: '💬',
            exploration: '🔍',
            puzzle: '🧩',
            choice: '❓',
            rest: '⛺',
        };
        return icons[type] || '📜';
    }

    toggleChapter(chapterEl) {
        const list = chapterEl.querySelector('.encounter-list');
        const toggle = chapterEl.querySelector('.chapter-toggle');

        list.classList.toggle('collapsed');
        toggle.textContent = list.classList.contains('collapsed') ? '▶' : '▼';
    }

    showPanel(panelType) {
        // Hide all panels
        this.container.querySelectorAll('.edit-panel').forEach(panel => {
            panel.classList.add('hidden');
        });

        // Show requested panel
        const panel = this.container.querySelector(`.panel-${panelType}`);
        if (panel) {
            panel.classList.remove('hidden');
        }
    }

    // ==================== Selection ====================

    selectEncounter(encounterId, chapterId) {
        // Update selection state
        this.selectedChapter = chapterId;
        this.selectedEncounter = encounterId;

        // Highlight in tree
        this.container.querySelectorAll('.encounter-item').forEach(el => {
            el.classList.toggle('selected', el.dataset.encounterId === encounterId);
        });

        // Find encounter data
        const chapter = this.campaign.chapters.find(ch => ch.id === chapterId);
        const encounter = chapter?.encounters.find(enc => enc.id === encounterId);

        if (!encounter) return;

        // Populate encounter panel
        this.container.querySelector('#encounter-name').value = encounter.name || '';
        this.container.querySelector('#encounter-type').value = encounter.type || 'combat';
        this.container.querySelector('#encounter-difficulty').value = encounter.difficulty || 'medium';
        this.container.querySelector('#encounter-story').value = encounter.story_text || '';
        this.container.querySelector('#encounter-outcome').value = encounter.outcome_text || '';

        // Update type-specific UI
        this.updateEncounterTypeUI(encounter.type);

        // Render enemies if combat
        if (encounter.type === 'combat') {
            this.renderEnemyList(encounter.enemies || []);
        }

        // Render choices if choice encounter
        if (encounter.type === 'choice') {
            this.renderChoiceList(encounter.choices || []);
        }

        // Show encounter panel
        this.showPanel('encounter');

        // Update preview
        this.updatePreview(encounter);
    }

    updateEncounterTypeUI(type) {
        const enemiesSection = this.container.querySelector('.encounter-enemies');
        const choicesSection = this.container.querySelector('.encounter-choices');

        enemiesSection.classList.toggle('hidden', type !== 'combat');
        choicesSection.classList.toggle('hidden', type !== 'choice');
    }

    // ==================== Editing Operations ====================

    async handleCampaignMetadataChange() {
        if (!this.campaign) return;

        const data = {
            name: this.container.querySelector('#campaign-name').value,
            description: this.container.querySelector('#campaign-desc').value,
            theme: this.container.querySelector('#campaign-theme').value,
            difficulty: this.container.querySelector('#campaign-difficulty').value,
            party_level_range: [
                parseInt(this.container.querySelector('#level-min').value) || 1,
                parseInt(this.container.querySelector('#level-max').value) || 5,
            ]
        };

        try {
            await api.put(`/api/campaign/${this.campaign.id}/metadata`, data);
            Object.assign(this.campaign, data);
            this.markDirty();
        } catch (error) {
            console.error('[CampaignEditor] Failed to update metadata:', error);
        }
    }

    async updateEncounter(encounterId, data) {
        if (!this.campaign) return;

        try {
            const response = await api.put(`/api/campaign/${this.campaign.id}/encounter/${encounterId}`, data);

            if (response.success) {
                // Update local data
                for (const chapter of this.campaign.chapters) {
                    const encIndex = chapter.encounters.findIndex(e => e.id === encounterId);
                    if (encIndex >= 0) {
                        chapter.encounters[encIndex] = response.encounter;
                        break;
                    }
                }
                this.markDirty();
            }
        } catch (error) {
            errorHandler.handle(error, { component: 'CampaignEditor', action: 'updateEncounter' });
        }
    }

    async addEncounter(chapterId) {
        try {
            const response = await api.post(`/api/campaign/${this.campaign.id}/chapter/${chapterId}/encounter`, {
                name: 'New Encounter',
                type: 'combat',
                difficulty: 'medium',
            });

            if (response.success) {
                // Add to local data
                const chapter = this.campaign.chapters.find(ch => ch.id === chapterId);
                if (chapter) {
                    chapter.encounters.push(response.encounter);
                }
                this.renderChapterTree();
                this.markDirty();

                // Select the new encounter
                this.selectEncounter(response.encounter.id, chapterId);
            }
        } catch (error) {
            errorHandler.handle(error, { component: 'CampaignEditor', action: 'addEncounter' });
        }
    }

    async deleteSelectedEncounter() {
        if (!this.selectedEncounter || !this.selectedChapter) return;

        if (!confirm('Delete this encounter? This cannot be undone.')) return;

        try {
            const response = await api.delete(`/api/campaign/${this.campaign.id}/chapter/${this.selectedChapter}/encounter/${this.selectedEncounter}`);

            if (response.success) {
                // Remove from local data
                const chapter = this.campaign.chapters.find(ch => ch.id === this.selectedChapter);
                if (chapter) {
                    chapter.encounters = chapter.encounters.filter(e => e.id !== this.selectedEncounter);
                }

                this.selectedEncounter = null;
                this.renderChapterTree();
                this.showPanel('campaign');
                this.markDirty();
            }
        } catch (error) {
            errorHandler.handle(error, { component: 'CampaignEditor', action: 'deleteEncounter' });
        }
    }

    addChapter() {
        // For now, show an alert. In a full implementation, this would call the API.
        alert('Add Chapter feature coming soon. For now, chapters are created with the campaign.');
    }

    // ==================== Drag and Drop ====================

    handleDragStart(e, encounter, chapterId) {
        this.draggedItem = { encounter, chapterId };
        e.target.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
    }

    handleDragEnd() {
        this.draggedItem = null;
        this.container.querySelectorAll('.encounter-item').forEach(el => {
            el.classList.remove('dragging', 'drag-over');
        });
    }

    handleDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        e.currentTarget.classList.add('drag-over');
    }

    async handleDrop(e, targetEncounter, targetChapterId) {
        e.preventDefault();
        e.currentTarget.classList.remove('drag-over');

        if (!this.draggedItem) return;
        if (this.draggedItem.encounter.id === targetEncounter.id) return;

        // Only support reordering within the same chapter for now
        if (this.draggedItem.chapterId !== targetChapterId) {
            alert('Moving encounters between chapters is not yet supported.');
            return;
        }

        try {
            // Get current order
            const chapter = this.campaign.chapters.find(ch => ch.id === targetChapterId);
            const currentOrder = chapter.encounters.map(e => e.id);

            // Calculate new order
            const draggedIndex = currentOrder.indexOf(this.draggedItem.encounter.id);
            const targetIndex = currentOrder.indexOf(targetEncounter.id);

            // Remove dragged item
            currentOrder.splice(draggedIndex, 1);
            // Insert at target position
            currentOrder.splice(targetIndex, 0, this.draggedItem.encounter.id);

            // Call API
            const response = await api.put(`/api/campaign/${this.campaign.id}/chapter/${targetChapterId}/reorder`, {
                encounter_ids: currentOrder
            });

            if (response.success) {
                // Update local data
                chapter.encounters = currentOrder.map(id =>
                    chapter.encounters.find(e => e.id === id)
                );
                this.renderChapterTree();
                this.markDirty();
            }
        } catch (error) {
            errorHandler.handle(error, { component: 'CampaignEditor', action: 'reorderEncounters' });
        }
    }

    // ==================== Enemy/Choice Lists ====================

    renderEnemyList(enemies) {
        const list = this.container.querySelector('.enemy-list');
        list.innerHTML = '';

        if (!enemies.length) {
            list.innerHTML = '<p class="empty-message">No enemies. Add some!</p>';
            return;
        }

        enemies.forEach((enemy, index) => {
            const el = document.createElement('div');
            el.className = 'enemy-item';
            el.innerHTML = `
                <span class="enemy-name">${enemy.name || 'Unknown'}</span>
                <span class="enemy-cr">CR ${enemy.cr || '?'}</span>
                <button class="btn-remove-enemy" data-index="${index}">×</button>
            `;

            el.querySelector('.btn-remove-enemy').addEventListener('click', () => {
                this.removeEnemy(index);
            });

            list.appendChild(el);
        });
    }

    renderChoiceList(choices) {
        const list = this.container.querySelector('.choice-list');
        list.innerHTML = '';

        if (!choices.length) {
            list.innerHTML = '<p class="empty-message">No choices defined.</p>';
            return;
        }

        choices.forEach((choice, index) => {
            const el = document.createElement('div');
            el.className = 'choice-item';
            el.innerHTML = `
                <input type="text" class="choice-text" value="${choice.text || ''}" placeholder="Choice text...">
                <button class="btn-remove-choice" data-index="${index}">×</button>
            `;

            el.querySelector('.btn-remove-choice').addEventListener('click', () => {
                this.removeChoice(index);
            });

            list.appendChild(el);
        });
    }

    addEnemy() {
        // Simple prompt for now - could be a proper modal
        const name = prompt('Enemy name:');
        if (!name) return;

        const cr = prompt('Challenge Rating (0.25, 0.5, 1, 2, etc.):', '1');

        // Update the encounter
        // For now, just add to UI - full implementation would call API
        console.log('[CampaignEditor] Would add enemy:', { name, cr });
    }

    removeEnemy(index) {
        console.log('[CampaignEditor] Would remove enemy at index:', index);
    }

    addChoice() {
        console.log('[CampaignEditor] Would add choice');
    }

    removeChoice(index) {
        console.log('[CampaignEditor] Would remove choice at index:', index);
    }

    // ==================== Preview ====================

    updatePreview(encounter) {
        const previewContent = this.container.querySelector('.preview-content');

        previewContent.innerHTML = `
            <div class="preview-encounter">
                <h4>${encounter.name || 'Unnamed Encounter'}</h4>
                <p class="preview-type">${this.getEncounterTypeIcon(encounter.type)} ${encounter.type}</p>
                ${encounter.story_text ? `<p class="preview-story">${encounter.story_text}</p>` : ''}
                ${encounter.type === 'combat' && encounter.enemies?.length ?
                    `<p class="preview-enemies">Enemies: ${encounter.enemies.map(e => e.name).join(', ')}</p>` : ''
                }
            </div>
        `;
    }

    // ==================== Save/Discard ====================

    markDirty() {
        this.isDirty = true;
        this.container.querySelector('.unsaved-warning').classList.remove('hidden');
        this.container.querySelector('.editor-campaign-name').textContent = `${this.campaign.name} *`;
    }

    async saveCampaign() {
        if (!this.campaign) return;

        try {
            const response = await api.post(`/api/campaign/${this.campaign.id}/save`);

            if (response.success) {
                this.isDirty = false;
                this.container.querySelector('.unsaved-warning').classList.add('hidden');
                this.container.querySelector('.editor-campaign-name').textContent = this.campaign.name;

                eventBus.emit(EVENTS.UI_NOTIFICATION, {
                    type: 'success',
                    message: 'Campaign saved successfully!',
                    duration: 3000
                });
            }
        } catch (error) {
            errorHandler.handle(error, { component: 'CampaignEditor', action: 'save' });
        }
    }

    async discardChanges() {
        if (!this.campaign) return;

        try {
            await api.post(`/api/campaign/${this.campaign.id}/discard`);
            this.isDirty = false;
        } catch (error) {
            console.error('[CampaignEditor] Failed to discard changes:', error);
        }
    }

    async undoLastChange() {
        if (!this.campaign) return;

        try {
            const response = await api.post(`/api/campaign/${this.campaign.id}/undo`);

            if (response.success && response.campaign) {
                this.campaign = response.campaign;
                this.renderCampaign();

                eventBus.emit(EVENTS.UI_NOTIFICATION, {
                    type: 'info',
                    message: 'Change undone',
                    duration: 2000
                });
            }
        } catch (error) {
            console.error('[CampaignEditor] Failed to undo:', error);
        }
    }

    // ==================== Quick Actions ====================

    async duplicateCampaign() {
        if (!this.campaign) return;

        const newName = prompt('Name for the copy:', `Copy of ${this.campaign.name}`);
        if (!newName) return;

        try {
            const response = await api.post(`/api/campaign/${this.campaign.id}/duplicate`, {
                new_name: newName
            });

            if (response.success) {
                eventBus.emit(EVENTS.UI_NOTIFICATION, {
                    type: 'success',
                    message: 'Campaign duplicated!',
                    duration: 3000
                });

                // Optionally switch to editing the new campaign
                if (confirm('Edit the new campaign now?')) {
                    this.campaign = response.campaign;
                    this.isDirty = false;
                    this.renderCampaign();
                }
            }
        } catch (error) {
            errorHandler.handle(error, { component: 'CampaignEditor', action: 'duplicate' });
        }
    }

    exportCampaign() {
        if (!this.campaign) return;

        const json = JSON.stringify(this.campaign, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = `${this.campaign.name.replace(/\s+/g, '_')}.json`;
        a.click();

        URL.revokeObjectURL(url);
    }

    // ==================== Helpers ====================

    getDispositionLabel(value) {
        if (value <= -75) return 'Hostile';
        if (value <= -25) return 'Unfriendly';
        if (value < 25) return 'Neutral';
        if (value < 75) return 'Friendly';
        return 'Allied';
    }
}

// Inject styles
const styles = `
.campaign-editor {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 10000;
    display: flex;
    align-items: center;
    justify-content: center;
}

.campaign-editor.hidden {
    display: none;
}

.editor-backdrop {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.85);
}

.editor-content {
    position: relative;
    width: 95%;
    max-width: 1400px;
    height: 90vh;
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    border: 2px solid #d4af37;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    animation: editorSlideIn 0.3s ease-out;
}

@keyframes editorSlideIn {
    from {
        opacity: 0;
        transform: translateY(-20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 24px;
    border-bottom: 1px solid #3a3a5c;
    background: rgba(0, 0, 0, 0.2);
}

.editor-title-section {
    display: flex;
    align-items: baseline;
    gap: 16px;
}

.editor-title {
    margin: 0;
    color: #d4af37;
    font-family: 'Cinzel', serif;
    font-size: 1.3rem;
}

.editor-campaign-name {
    color: #888;
    font-size: 0.95rem;
}

.editor-actions {
    display: flex;
    gap: 8px;
}

.editor-btn {
    padding: 8px 16px;
    background: rgba(212, 175, 55, 0.2);
    border: 1px solid #d4af37;
    border-radius: 6px;
    color: #d4af37;
    cursor: pointer;
    transition: all 0.2s;
}

.editor-btn:hover {
    background: #d4af37;
    color: #1a1a2e;
}

.btn-close {
    font-size: 1.5rem;
    padding: 4px 12px;
}

.editor-body {
    flex: 1;
    display: flex;
    overflow: hidden;
}

/* Sidebar */
.editor-sidebar {
    width: 280px;
    border-right: 1px solid #3a3a5c;
    display: flex;
    flex-direction: column;
    background: rgba(0, 0, 0, 0.1);
}

.sidebar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid #3a3a5c;
}

.sidebar-header h3 {
    margin: 0;
    color: #c8c8c8;
    font-size: 0.9rem;
}

.btn-add-chapter {
    padding: 4px 8px;
    background: transparent;
    border: 1px solid #666;
    border-radius: 4px;
    color: #888;
    font-size: 0.8rem;
    cursor: pointer;
}

.btn-add-chapter:hover {
    border-color: #d4af37;
    color: #d4af37;
}

.chapter-tree {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
}

.chapter-item {
    margin-bottom: 4px;
}

.chapter-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: rgba(212, 175, 55, 0.1);
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.2s;
}

.chapter-header:hover {
    background: rgba(212, 175, 55, 0.2);
}

.chapter-toggle {
    font-size: 0.7rem;
    color: #888;
}

.chapter-name {
    flex: 1;
    color: #e8e8e8;
    font-size: 0.9rem;
}

.btn-add-encounter {
    padding: 2px 8px;
    background: transparent;
    border: none;
    color: #666;
    font-size: 1rem;
    cursor: pointer;
}

.btn-add-encounter:hover {
    color: #d4af37;
}

.encounter-list {
    padding-left: 16px;
    margin-top: 4px;
}

.encounter-list.collapsed {
    display: none;
}

.encounter-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    margin: 2px 0;
    background: rgba(0, 0, 0, 0.2);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
}

.encounter-item:hover {
    background: rgba(212, 175, 55, 0.15);
}

.encounter-item.selected {
    background: rgba(212, 175, 55, 0.3);
    border-left: 3px solid #d4af37;
}

.encounter-item.dragging {
    opacity: 0.5;
}

.encounter-item.drag-over {
    border-top: 2px solid #d4af37;
}

.encounter-icon {
    font-size: 1rem;
}

.encounter-name {
    flex: 1;
    color: #c8c8c8;
    font-size: 0.85rem;
}

.encounter-type-badge {
    padding: 2px 6px;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 3px;
    color: #888;
    font-size: 0.7rem;
    text-transform: uppercase;
}

/* Main Editor Area */
.editor-main {
    flex: 1;
    padding: 20px;
    overflow-y: auto;
}

.edit-panel {
    max-width: 700px;
}

.edit-panel.hidden {
    display: none;
}

.edit-panel h3 {
    margin: 0 0 20px 0;
    color: #d4af37;
    font-family: 'Cinzel', serif;
}

.form-group {
    margin-bottom: 16px;
}

.form-group label {
    display: block;
    margin-bottom: 6px;
    color: #c8c8c8;
    font-size: 0.9rem;
}

.form-input,
.form-select,
.form-textarea {
    width: 100%;
    padding: 10px 12px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid #3a3a5c;
    border-radius: 6px;
    color: #e8e8e8;
    font-size: 0.95rem;
}

.form-input:focus,
.form-select:focus,
.form-textarea:focus {
    outline: none;
    border-color: #d4af37;
}

.form-textarea {
    resize: vertical;
    min-height: 80px;
}

.form-row {
    display: flex;
    gap: 16px;
}

.form-row .form-group {
    flex: 1;
}

.form-input-small {
    width: 70px;
    padding: 8px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid #3a3a5c;
    border-radius: 4px;
    color: #e8e8e8;
    text-align: center;
}

.level-range {
    display: flex;
    align-items: center;
    gap: 10px;
    color: #888;
}

.form-range {
    width: 100%;
}

.section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 20px;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #3a3a5c;
}

.section-header h4 {
    margin: 0;
    color: #c8c8c8;
}

.enemy-list,
.choice-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.enemy-item,
.choice-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    background: rgba(0, 0, 0, 0.2);
    border-radius: 6px;
}

.enemy-name {
    flex: 1;
    color: #e8e8e8;
}

.enemy-cr {
    color: #888;
    font-size: 0.85rem;
}

.choice-text {
    flex: 1;
    padding: 6px 10px;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid #3a3a5c;
    border-radius: 4px;
    color: #e8e8e8;
}

.btn-remove-enemy,
.btn-remove-choice {
    padding: 4px 8px;
    background: transparent;
    border: none;
    color: #e74c3c;
    cursor: pointer;
    font-size: 1rem;
}

.panel-actions {
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid #3a3a5c;
}

.btn-delete-encounter {
    padding: 8px 16px;
    background: rgba(231, 76, 60, 0.2);
    border: 1px solid #e74c3c;
    border-radius: 6px;
    color: #e74c3c;
    cursor: pointer;
}

.btn-delete-encounter:hover {
    background: #e74c3c;
    color: white;
}

/* Preview Sidebar */
.editor-preview {
    width: 280px;
    border-left: 1px solid #3a3a5c;
    padding: 16px;
    display: flex;
    flex-direction: column;
    background: rgba(0, 0, 0, 0.1);
}

.editor-preview h3 {
    margin: 0 0 16px 0;
    color: #c8c8c8;
    font-size: 0.9rem;
}

.preview-content {
    flex: 1;
    overflow-y: auto;
}

.preview-hint {
    color: #666;
    font-size: 0.85rem;
    font-style: italic;
}

.preview-encounter h4 {
    margin: 0 0 8px 0;
    color: #d4af37;
}

.preview-type {
    color: #888;
    font-size: 0.85rem;
    margin-bottom: 12px;
}

.preview-story {
    color: #c8c8c8;
    font-size: 0.9rem;
    line-height: 1.5;
    font-style: italic;
}

.quick-actions {
    margin-top: auto;
    padding-top: 16px;
    border-top: 1px solid #3a3a5c;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.btn-duplicate,
.btn-export {
    padding: 10px;
    background: transparent;
    border: 1px solid #666;
    border-radius: 6px;
    color: #888;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-duplicate:hover,
.btn-export:hover {
    border-color: #d4af37;
    color: #d4af37;
}

/* Unsaved Warning */
.unsaved-warning {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 8px 16px;
    background: rgba(231, 76, 60, 0.9);
    color: white;
    text-align: center;
    font-size: 0.9rem;
}

.unsaved-warning.hidden {
    display: none;
}

.empty-message {
    color: #666;
    font-style: italic;
    font-size: 0.85rem;
    padding: 8px;
}

.btn-add-enemy,
.btn-add-choice {
    padding: 4px 10px;
    background: transparent;
    border: 1px solid #666;
    border-radius: 4px;
    color: #888;
    font-size: 0.8rem;
    cursor: pointer;
}

.btn-add-enemy:hover,
.btn-add-choice:hover {
    border-color: #d4af37;
    color: #d4af37;
}
`;

const styleSheet = document.createElement('style');
styleSheet.textContent = styles;
document.head.appendChild(styleSheet);

// Export singleton
export const campaignEditor = new CampaignEditor();
export default campaignEditor;
