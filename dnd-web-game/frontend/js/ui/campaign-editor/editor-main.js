/**
 * D&D Combat Engine - Campaign Editor
 * Main editor controller for creating and editing campaigns.
 * Features visual node-based encounter editing.
 */

import { eventBus, EVENTS } from '../../engine/event-bus.js';
import state from '../../engine/state-manager.js';
import api from '../../api/api-client.js';
import { toast } from '../toast-notification.js';
import { EncounterGraph } from './encounter-graph.js';
import { EncounterPanel } from './encounter-panel.js';
import { ValidationPanel } from './validation-panel.js';

/**
 * Campaign Editor - Main controller for campaign creation/editing
 */
export class CampaignEditor {
    constructor() {
        this.container = null;
        this.campaign = null;
        this.selectedEncounter = null;
        this.isDirty = false;
        this.isVisible = false;

        // Child components
        this.graph = null;
        this.encounterPanel = null;
        this.validationPanel = null;

        this.init();
    }

    init() {
        this.createEditorContainer();
        this.setupEventListeners();
    }

    createEditorContainer() {
        this.container = document.createElement('div');
        this.container.id = 'campaign-editor';
        this.container.className = 'campaign-editor hidden';
        this.container.innerHTML = `
            <div class="editor-header">
                <div class="editor-title">
                    <h2>Campaign Editor</h2>
                    <span class="campaign-name" id="editor-campaign-name">Untitled Campaign</span>
                    <span class="dirty-indicator hidden" id="dirty-indicator">*</span>
                </div>
                <div class="editor-actions">
                    <button class="editor-btn" id="btn-new-encounter" title="Add Encounter">
                        <span>+ Encounter</span>
                    </button>
                    <button class="editor-btn" id="btn-validate" title="Validate Campaign">
                        <span>Validate</span>
                    </button>
                    <button class="editor-btn" id="btn-test-play" title="Test Play">
                        <span>Test Play</span>
                    </button>
                    <button class="editor-btn secondary" id="btn-export" title="Export JSON">
                        <span>Export</span>
                    </button>
                    <button class="editor-btn primary" id="btn-save-campaign" title="Save Campaign">
                        <span>Save</span>
                    </button>
                    <button class="editor-btn close" id="btn-close-editor" title="Close Editor">
                        <span>&times;</span>
                    </button>
                </div>
            </div>

            <div class="editor-body">
                <div class="editor-sidebar" id="editor-sidebar">
                    <div class="sidebar-section">
                        <h3>Campaign Info</h3>
                        <div class="form-group">
                            <label for="campaign-name-input">Name</label>
                            <input type="text" id="campaign-name-input" placeholder="Campaign name">
                        </div>
                        <div class="form-group">
                            <label for="campaign-description">Description</label>
                            <textarea id="campaign-description" placeholder="Campaign description"></textarea>
                        </div>
                        <div class="form-group">
                            <label for="campaign-difficulty">Difficulty</label>
                            <select id="campaign-difficulty">
                                <option value="easy">Easy</option>
                                <option value="medium" selected>Medium</option>
                                <option value="hard">Hard</option>
                                <option value="deadly">Deadly</option>
                            </select>
                        </div>
                    </div>

                    <div class="sidebar-section" id="encounter-properties">
                        <h3>Selected Encounter</h3>
                        <div class="no-selection">
                            <p>Select an encounter node to edit</p>
                        </div>
                    </div>

                    <div class="sidebar-section" id="validation-results">
                        <h3>Validation</h3>
                        <div class="validation-placeholder">
                            <p>Click "Validate" to check campaign</p>
                        </div>
                    </div>
                </div>

                <div class="editor-canvas" id="editor-canvas">
                    <canvas id="encounter-graph-canvas"></canvas>
                    <div id="graph-controls" class="graph-controls">
                        <button class="graph-btn" id="btn-zoom-in" title="Zoom In">+</button>
                        <button class="graph-btn" id="btn-zoom-out" title="Zoom Out">-</button>
                        <button class="graph-btn" id="btn-fit-view" title="Fit View">Fit</button>
                        <button class="graph-btn" id="btn-auto-layout" title="Auto Layout">Auto</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(this.container);

        // Initialize child components
        this.initializeComponents();
    }

    initializeComponents() {
        const canvas = this.container.querySelector('#encounter-graph-canvas');
        const propertiesContainer = this.container.querySelector('#encounter-properties');
        const validationContainer = this.container.querySelector('#validation-results');

        this.graph = new EncounterGraph(canvas, {
            onSelectEncounter: (encounter) => this.handleEncounterSelect(encounter),
            onCreateConnection: (from, to) => this.handleCreateConnection(from, to),
            onDeleteEncounter: (id) => this.handleDeleteEncounter(id),
            onMoveEncounter: (id, x, y) => this.handleMoveEncounter(id, x, y),
        });

        this.encounterPanel = new EncounterPanel(propertiesContainer, {
            onUpdate: (data) => this.handleEncounterUpdate(data),
        });

        this.validationPanel = new ValidationPanel(validationContainer);
    }

    setupEventListeners() {
        // Header buttons
        this.container.querySelector('#btn-new-encounter').addEventListener('click', () => this.addNewEncounter());
        this.container.querySelector('#btn-validate').addEventListener('click', () => this.validateCampaign());
        this.container.querySelector('#btn-test-play').addEventListener('click', () => this.testPlay());
        this.container.querySelector('#btn-export').addEventListener('click', () => this.exportCampaign());
        this.container.querySelector('#btn-save-campaign').addEventListener('click', () => this.saveCampaign());
        this.container.querySelector('#btn-close-editor').addEventListener('click', () => this.close());

        // Graph controls
        this.container.querySelector('#btn-zoom-in').addEventListener('click', () => this.graph?.zoomIn());
        this.container.querySelector('#btn-zoom-out').addEventListener('click', () => this.graph?.zoomOut());
        this.container.querySelector('#btn-fit-view').addEventListener('click', () => this.graph?.fitView());
        this.container.querySelector('#btn-auto-layout').addEventListener('click', () => this.autoLayoutEncounters());

        // Campaign info changes
        this.container.querySelector('#campaign-name-input').addEventListener('input', (e) => {
            if (this.campaign) {
                this.campaign.name = e.target.value;
                this.container.querySelector('#editor-campaign-name').textContent = e.target.value || 'Untitled Campaign';
                this.markDirty();
            }
        });

        this.container.querySelector('#campaign-description').addEventListener('input', (e) => {
            if (this.campaign) {
                this.campaign.description = e.target.value;
                this.markDirty();
            }
        });

        this.container.querySelector('#campaign-difficulty').addEventListener('change', (e) => {
            if (this.campaign) {
                this.campaign.default_difficulty = e.target.value;
                this.markDirty();
            }
        });

        // Close on backdrop click
        this.container.addEventListener('click', (e) => {
            if (e.target === this.container) {
                this.close();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (!this.isVisible) return;

            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                this.saveCampaign();
            } else if (e.key === 'Delete' && this.selectedEncounter) {
                this.handleDeleteEncounter(this.selectedEncounter.id);
            } else if (e.key === 'Escape') {
                this.close();
            }
        });

        // Event bus subscriptions
        eventBus.on('campaign:open-editor', (campaign) => this.open(campaign));
    }

    // ==========================================================================
    // PUBLIC API
    // ==========================================================================

    open(campaign = null) {
        if (campaign) {
            this.loadCampaign(campaign);
        } else {
            this.newCampaign();
        }

        this.container.classList.remove('hidden');
        this.isVisible = true;

        // Render after showing to get correct canvas size
        requestAnimationFrame(() => {
            this.graph?.resize();
            this.graph?.render();
        });
    }

    close() {
        if (this.isDirty) {
            if (!confirm('You have unsaved changes. Close anyway?')) {
                return;
            }
        }

        this.container.classList.add('hidden');
        this.isVisible = false;
        this.campaign = null;
        this.selectedEncounter = null;
        this.isDirty = false;
    }

    newCampaign() {
        this.campaign = {
            id: this.generateId(),
            name: 'New Campaign',
            description: '',
            default_difficulty: 'medium',
            encounters: [
                {
                    id: 'start',
                    name: 'Campaign Start',
                    type: 'cutscene',
                    position: { x: 100, y: 200 },
                    story: {
                        intro_text: 'Your adventure begins...',
                    },
                    transitions: [],
                },
            ],
            starting_encounter_id: 'start',
        };

        this.updateFormFromCampaign();
        this.graph?.loadCampaign(this.campaign);
        this.clearDirty();
    }

    loadCampaign(campaign) {
        this.campaign = JSON.parse(JSON.stringify(campaign)); // Deep clone

        // Ensure encounters have positions
        this.ensureEncounterPositions();

        this.updateFormFromCampaign();
        this.graph?.loadCampaign(this.campaign);
        this.clearDirty();
    }

    // ==========================================================================
    // ENCOUNTER MANAGEMENT
    // ==========================================================================

    addNewEncounter() {
        if (!this.campaign) return;

        const newEncounter = {
            id: this.generateId(),
            name: 'New Encounter',
            type: 'combat',
            position: this.getNewEncounterPosition(),
            enemies: [],
            story: {
                intro_text: '',
            },
            transitions: [],
        };

        this.campaign.encounters.push(newEncounter);
        this.graph?.addEncounter(newEncounter);
        this.markDirty();

        // Select the new encounter
        this.handleEncounterSelect(newEncounter);
    }

    handleEncounterSelect(encounter) {
        this.selectedEncounter = encounter;
        this.encounterPanel?.loadEncounter(encounter);
        this.graph?.setSelectedEncounter(encounter?.id);
    }

    handleEncounterUpdate(data) {
        if (!this.selectedEncounter || !this.campaign) return;

        // Update encounter in campaign
        const index = this.campaign.encounters.findIndex(e => e.id === this.selectedEncounter.id);
        if (index !== -1) {
            Object.assign(this.campaign.encounters[index], data);
            this.selectedEncounter = this.campaign.encounters[index];
            this.graph?.updateEncounter(this.selectedEncounter);
            this.markDirty();
        }
    }

    handleDeleteEncounter(id) {
        if (!this.campaign) return;

        if (id === this.campaign.starting_encounter_id) {
            toast.show('Cannot delete the starting encounter', 'error');
            return;
        }

        if (!confirm('Delete this encounter?')) return;

        // Remove encounter
        this.campaign.encounters = this.campaign.encounters.filter(e => e.id !== id);

        // Remove transitions pointing to this encounter
        this.campaign.encounters.forEach(e => {
            e.transitions = (e.transitions || []).filter(t => t.target_id !== id);
        });

        this.graph?.removeEncounter(id);

        if (this.selectedEncounter?.id === id) {
            this.selectedEncounter = null;
            this.encounterPanel?.clear();
        }

        this.markDirty();
    }

    handleMoveEncounter(id, x, y) {
        if (!this.campaign) return;

        const encounter = this.campaign.encounters.find(e => e.id === id);
        if (encounter) {
            encounter.position = { x, y };
            this.markDirty();
        }
    }

    handleCreateConnection(fromId, toId) {
        if (!this.campaign) return;

        const fromEncounter = this.campaign.encounters.find(e => e.id === fromId);
        if (!fromEncounter) return;

        if (!fromEncounter.transitions) {
            fromEncounter.transitions = [];
        }

        // Check if connection already exists
        if (fromEncounter.transitions.some(t => t.target_id === toId)) {
            toast.show('Connection already exists', 'warning');
            return;
        }

        fromEncounter.transitions.push({
            target_id: toId,
            condition: 'default',
        });

        this.graph?.render();
        this.markDirty();
    }

    // ==========================================================================
    // VALIDATION & EXPORT
    // ==========================================================================

    async validateCampaign() {
        if (!this.campaign) return;

        const errors = [];
        const warnings = [];

        // Check for starting encounter
        if (!this.campaign.starting_encounter_id) {
            errors.push('No starting encounter defined');
        }

        // Check for orphan encounters (no incoming connections)
        const targetIds = new Set();
        targetIds.add(this.campaign.starting_encounter_id);
        this.campaign.encounters.forEach(e => {
            (e.transitions || []).forEach(t => targetIds.add(t.target_id));
        });

        this.campaign.encounters.forEach(e => {
            if (!targetIds.has(e.id) && e.id !== this.campaign.starting_encounter_id) {
                warnings.push(`Encounter "${e.name}" is unreachable`);
            }
        });

        // Check for dead ends (no outgoing connections)
        this.campaign.encounters.forEach(e => {
            if (!e.transitions || e.transitions.length === 0) {
                if (e.type !== 'cutscene') {
                    warnings.push(`Encounter "${e.name}" has no transitions (dead end)`);
                }
            }
        });

        // Check combat encounters for enemies
        this.campaign.encounters.forEach(e => {
            if (e.type === 'combat' && (!e.enemies || e.enemies.length === 0)) {
                warnings.push(`Combat encounter "${e.name}" has no enemies`);
            }
        });

        // Check choice encounters for choices
        this.campaign.encounters.forEach(e => {
            if (e.type === 'choice' && (!e.choices || e.choices.length === 0)) {
                warnings.push(`Choice encounter "${e.name}" has no choices`);
            }
        });

        this.validationPanel?.showResults({ errors, warnings });

        if (errors.length === 0 && warnings.length === 0) {
            toast.show('Campaign is valid!', 'success');
        } else if (errors.length > 0) {
            toast.show(`${errors.length} errors found`, 'error');
        } else {
            toast.show(`${warnings.length} warnings found`, 'warning');
        }
    }

    exportCampaign() {
        if (!this.campaign) return;

        const json = JSON.stringify(this.campaign, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = `${this.campaign.name || 'campaign'}.json`;
        a.click();

        URL.revokeObjectURL(url);
        toast.show('Campaign exported', 'success');
    }

    async saveCampaign() {
        if (!this.campaign) return;

        try {
            // For now, just export to local storage
            const key = `campaign_${this.campaign.id}`;
            localStorage.setItem(key, JSON.stringify(this.campaign));

            this.clearDirty();
            toast.show('Campaign saved', 'success');
        } catch (error) {
            console.error('Failed to save campaign:', error);
            toast.show('Failed to save campaign', 'error');
        }
    }

    testPlay() {
        if (!this.campaign) return;

        // Validate first
        this.validateCampaign();

        // Emit event to start test play
        eventBus.emit('campaign:test-play', this.campaign);
        this.close();
    }

    // ==========================================================================
    // LAYOUT
    // ==========================================================================

    autoLayoutEncounters() {
        if (!this.campaign || !this.campaign.encounters.length) return;

        // Simple tree layout
        const startId = this.campaign.starting_encounter_id;
        const visited = new Set();
        const levels = new Map();

        // BFS to assign levels
        const queue = [{ id: startId, level: 0 }];
        while (queue.length > 0) {
            const { id, level } = queue.shift();
            if (visited.has(id)) continue;
            visited.add(id);
            levels.set(id, level);

            const encounter = this.campaign.encounters.find(e => e.id === id);
            if (encounter?.transitions) {
                encounter.transitions.forEach(t => {
                    if (!visited.has(t.target_id)) {
                        queue.push({ id: t.target_id, level: level + 1 });
                    }
                });
            }
        }

        // Group by level
        const byLevel = new Map();
        levels.forEach((level, id) => {
            if (!byLevel.has(level)) byLevel.set(level, []);
            byLevel.get(level).push(id);
        });

        // Position encounters
        const xSpacing = 200;
        const ySpacing = 150;

        byLevel.forEach((ids, level) => {
            const startY = (this.graph?.canvas?.height || 400) / 2 - (ids.length - 1) * ySpacing / 2;
            ids.forEach((id, index) => {
                const encounter = this.campaign.encounters.find(e => e.id === id);
                if (encounter) {
                    encounter.position = {
                        x: 100 + level * xSpacing,
                        y: startY + index * ySpacing,
                    };
                }
            });
        });

        // Position orphans
        let orphanY = 50;
        this.campaign.encounters.forEach(e => {
            if (!levels.has(e.id)) {
                e.position = { x: 50, y: orphanY };
                orphanY += 100;
            }
        });

        this.graph?.loadCampaign(this.campaign);
        this.markDirty();
    }

    // ==========================================================================
    // HELPERS
    // ==========================================================================

    updateFormFromCampaign() {
        if (!this.campaign) return;

        this.container.querySelector('#campaign-name-input').value = this.campaign.name || '';
        this.container.querySelector('#campaign-description').value = this.campaign.description || '';
        this.container.querySelector('#campaign-difficulty').value = this.campaign.default_difficulty || 'medium';
        this.container.querySelector('#editor-campaign-name').textContent = this.campaign.name || 'Untitled Campaign';
    }

    ensureEncounterPositions() {
        if (!this.campaign?.encounters) return;

        let x = 100;
        let y = 100;

        this.campaign.encounters.forEach(e => {
            if (!e.position) {
                e.position = { x, y };
                y += 150;
                if (y > 600) {
                    y = 100;
                    x += 200;
                }
            }
        });
    }

    getNewEncounterPosition() {
        if (!this.campaign?.encounters?.length) {
            return { x: 100, y: 100 };
        }

        // Find rightmost encounter and add to the right
        let maxX = 0;
        let avgY = 0;
        this.campaign.encounters.forEach(e => {
            if (e.position?.x > maxX) maxX = e.position.x;
            avgY += e.position?.y || 0;
        });
        avgY /= this.campaign.encounters.length;

        return { x: maxX + 200, y: avgY };
    }

    generateId() {
        return 'enc_' + Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
    }

    markDirty() {
        this.isDirty = true;
        this.container.querySelector('#dirty-indicator').classList.remove('hidden');
    }

    clearDirty() {
        this.isDirty = false;
        this.container.querySelector('#dirty-indicator').classList.add('hidden');
    }
}

// Export singleton
export const campaignEditor = new CampaignEditor();
export default campaignEditor;
