/**
 * Character Creation Wizard - D&D 2024 Rules
 *
 * Full character creation wizard with step-by-step process:
 * 1. Species - Choose race/species with traits
 * 2. Class - Choose class with features
 * 3. Background - Choose background (gives ability bonuses + origin feat)
 * 4. Abilities - Point buy or standard array
 * 5. Feat - Choose origin feat
 * 6. Equipment - Choose starting equipment
 * 7. Details - Name and optional description
 * 8. Review - Final summary and create
 */

import { eventBus, EVENTS } from '../../engine/event-bus.js';
import state from '../../engine/state-manager.js';
import api from '../../api/api-client.js';

const CREATION_STEPS = [
    { id: 'species', name: 'Species', icon: '🧝' },
    { id: 'class', name: 'Class', icon: '⚔️' },
    { id: 'background', name: 'Background', icon: '📜' },
    { id: 'abilities', name: 'Abilities', icon: '💪' },
    { id: 'feat', name: 'Feat', icon: '✨' },
    { id: 'equipment', name: 'Equipment', icon: '🎒' },
    { id: 'details', name: 'Details', icon: '📝' },
    { id: 'review', name: 'Review', icon: '✅' }
];

const POINT_BUY_COSTS = { 8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9 };
const STANDARD_ARRAY = [15, 14, 13, 12, 10, 8];
const ABILITIES = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'];
const ABILITY_LABELS = {
    strength: 'STR', dexterity: 'DEX', constitution: 'CON',
    intelligence: 'INT', wisdom: 'WIS', charisma: 'CHA'
};

class CharacterCreationWizard {
    constructor() {
        this.isOpen = false;
        this.element = null;
        this.buildId = null;
        this.currentStep = 0;

        // Cached data from API
        this.speciesData = [];
        this.classData = [];
        this.backgroundData = [];
        this.originFeats = [];

        // Current build state
        this.build = {
            species_id: null,
            class_id: null,
            background_id: null,
            ability_scores: { strength: 8, dexterity: 8, constitution: 8, intelligence: 8, wisdom: 8, charisma: 8 },
            ability_method: 'point_buy',
            ability_bonuses: {},
            origin_feat_id: null,
            skill_choices: [],
            equipment_choices: [],
            fighting_style: null,
            weapon_masteries: [],
            name: '',
            size: null
        };

        // Selected data for display
        this.selectedSpecies = null;
        this.selectedClass = null;
        this.selectedBackground = null;
        this.selectedFeat = null;

        this.createModal();
        this.setupKeyboardShortcut();
    }

    /**
     * Create the modal DOM element.
     */
    createModal() {
        this.element = document.createElement('div');
        this.element.id = 'character-creation-wizard';
        this.element.className = 'creation-wizard hidden';

        this.element.innerHTML = `
            <div class="creation-wizard-overlay" id="creation-overlay"></div>
            <div class="creation-wizard-content">
                <div class="creation-header">
                    <h2 class="creation-title">Create Character</h2>
                    <button class="creation-close-btn" id="creation-close-btn" title="Close">&times;</button>
                </div>

                <div class="creation-steps" id="creation-steps">
                    <!-- Step indicators rendered here -->
                </div>

                <div class="creation-body" id="creation-body">
                    <!-- Step content rendered here -->
                </div>

                <div class="creation-footer">
                    <button class="creation-btn secondary" id="creation-prev-btn">
                        <span class="btn-icon">←</span> Back
                    </button>
                    <div class="creation-progress">
                        <span id="creation-progress-text">Step 1 of 8</span>
                    </div>
                    <button class="creation-btn primary" id="creation-next-btn">
                        Next <span class="btn-icon">→</span>
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(this.element);
        this.setupEventListeners();
    }

    /**
     * Setup event listeners.
     */
    setupEventListeners() {
        document.getElementById('creation-close-btn')?.addEventListener('click', () => this.hide());
        document.getElementById('creation-overlay')?.addEventListener('click', () => this.hide());
        document.getElementById('creation-prev-btn')?.addEventListener('click', () => this.prevStep());
        document.getElementById('creation-next-btn')?.addEventListener('click', () => this.nextStep());
    }

    /**
     * Setup keyboard shortcut (C to open).
     */
    setupKeyboardShortcut() {
        document.addEventListener('keydown', (e) => {
            // Don't trigger if typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            if (e.key === 'c' && !e.ctrlKey && !e.altKey && !e.metaKey) {
                if (this.isOpen) {
                    this.hide();
                }
                // Don't auto-open with C key - require button click
            }

            if (e.key === 'Escape' && this.isOpen) {
                this.hide();
            }
        });
    }

    /**
     * Show the wizard.
     */
    async show() {
        // Load data if not cached
        if (this.speciesData.length === 0) {
            await this.loadData();
        }

        // Start a new build
        try {
            const response = await api.post('/creation/build/new', {});
            this.buildId = response.build_id;
        } catch (error) {
            console.error('Failed to start character build:', error);
        }

        this.currentStep = 0;
        this.resetBuild();
        this.renderSteps();
        this.renderCurrentStep();
        this.updateNavigationButtons();

        this.element.classList.remove('hidden');
        this.isOpen = true;

        eventBus.emit(EVENTS.UI_MODAL_OPENED, { modal: 'character-creation' });
    }

    /**
     * Hide the wizard.
     */
    hide() {
        this.element.classList.add('hidden');
        this.isOpen = false;

        eventBus.emit(EVENTS.UI_MODAL_CLOSED, { modal: 'character-creation' });
    }

    /**
     * Reset build state.
     */
    resetBuild() {
        this.build = {
            species_id: null,
            class_id: null,
            background_id: null,
            ability_scores: { strength: 8, dexterity: 8, constitution: 8, intelligence: 8, wisdom: 8, charisma: 8 },
            ability_method: 'point_buy',
            ability_bonuses: {},
            origin_feat_id: null,
            skill_choices: [],
            equipment_choices: [],
            fighting_style: null,
            weapon_masteries: [],
            name: '',
            size: null
        };
        this.selectedSpecies = null;
        this.selectedClass = null;
        this.selectedBackground = null;
        this.selectedFeat = null;
    }

    /**
     * Load all creation data from API.
     */
    async loadData() {
        try {
            const [species, classes, backgrounds, feats] = await Promise.all([
                api.get('/creation/species'),
                api.get('/creation/classes'),
                api.get('/creation/backgrounds'),
                api.get('/creation/feats/origin')
            ]);

            this.speciesData = species.species || [];
            this.classData = classes.classes || [];
            this.backgroundData = backgrounds.backgrounds || [];
            this.originFeats = feats.feats || [];

            console.log(`[Creation] Loaded: ${this.speciesData.length} species, ${this.classData.length} classes, ${this.backgroundData.length} backgrounds, ${this.originFeats.length} origin feats`);
        } catch (error) {
            console.error('Failed to load creation data:', error);
        }
    }

    /**
     * Render step indicators.
     */
    renderSteps() {
        const container = document.getElementById('creation-steps');
        if (!container) return;

        container.innerHTML = CREATION_STEPS.map((step, index) => `
            <div class="step-indicator ${index === this.currentStep ? 'active' : ''} ${index < this.currentStep ? 'completed' : ''}"
                 data-step="${index}" title="${step.name}">
                <span class="step-icon">${step.icon}</span>
                <span class="step-name">${step.name}</span>
            </div>
        `).join('');

        // Add click handlers for completed steps
        container.querySelectorAll('.step-indicator.completed').forEach(el => {
            el.addEventListener('click', () => {
                const stepIndex = parseInt(el.dataset.step);
                this.goToStep(stepIndex);
            });
        });
    }

    /**
     * Render current step content.
     */
    renderCurrentStep() {
        const step = CREATION_STEPS[this.currentStep];
        const container = document.getElementById('creation-body');
        if (!container) return;

        switch (step.id) {
            case 'species':
                this.renderSpeciesStep(container);
                break;
            case 'class':
                this.renderClassStep(container);
                break;
            case 'background':
                this.renderBackgroundStep(container);
                break;
            case 'abilities':
                this.renderAbilitiesStep(container);
                break;
            case 'feat':
                this.renderFeatStep(container);
                break;
            case 'equipment':
                this.renderEquipmentStep(container);
                break;
            case 'details':
                this.renderDetailsStep(container);
                break;
            case 'review':
                this.renderReviewStep(container);
                break;
        }

        this.renderSteps();
        this.updateNavigationButtons();
    }

    /**
     * Update navigation buttons.
     */
    updateNavigationButtons() {
        const prevBtn = document.getElementById('creation-prev-btn');
        const nextBtn = document.getElementById('creation-next-btn');
        const progressText = document.getElementById('creation-progress-text');

        if (prevBtn) {
            prevBtn.style.visibility = this.currentStep > 0 ? 'visible' : 'hidden';
        }

        if (nextBtn) {
            const isLastStep = this.currentStep === CREATION_STEPS.length - 1;
            nextBtn.innerHTML = isLastStep
                ? 'Create Character <span class="btn-icon">✓</span>'
                : 'Next <span class="btn-icon">→</span>';
        }

        if (progressText) {
            progressText.textContent = `Step ${this.currentStep + 1} of ${CREATION_STEPS.length}`;
        }
    }

    /**
     * Go to next step.
     */
    async nextStep() {
        // Validate current step
        if (!this.validateCurrentStep()) {
            return;
        }

        // Save current step to API
        await this.saveCurrentStep();

        if (this.currentStep < CREATION_STEPS.length - 1) {
            this.currentStep++;
            this.renderCurrentStep();
        } else {
            // Final step - create character
            await this.createCharacter();
        }
    }

    /**
     * Go to previous step.
     */
    prevStep() {
        if (this.currentStep > 0) {
            this.currentStep--;
            this.renderCurrentStep();
        }
    }

    /**
     * Go to specific step.
     */
    goToStep(index) {
        if (index >= 0 && index < this.currentStep) {
            this.currentStep = index;
            this.renderCurrentStep();
        }
    }

    /**
     * Validate current step.
     */
    validateCurrentStep() {
        const step = CREATION_STEPS[this.currentStep];

        switch (step.id) {
            case 'species':
                if (!this.build.species_id) {
                    this.showError('Please select a species');
                    return false;
                }
                break;
            case 'class':
                if (!this.build.class_id) {
                    this.showError('Please select a class');
                    return false;
                }
                break;
            case 'background':
                if (!this.build.background_id) {
                    this.showError('Please select a background');
                    return false;
                }
                break;
            case 'abilities':
                if (Object.keys(this.build.ability_bonuses).length === 0) {
                    this.showError('Please assign your ability score bonuses');
                    return false;
                }
                break;
            case 'feat':
                if (!this.build.origin_feat_id) {
                    this.showError('Please select an origin feat');
                    return false;
                }
                break;
            case 'details':
                if (!this.build.name.trim()) {
                    this.showError('Please enter a character name');
                    return false;
                }
                break;
        }

        return true;
    }

    /**
     * Save current step to API.
     */
    async saveCurrentStep() {
        const step = CREATION_STEPS[this.currentStep];
        if (!this.buildId) return;

        try {
            switch (step.id) {
                case 'species':
                    await api.post('/creation/build/species', {
                        build_id: this.buildId,
                        species_id: this.build.species_id,
                        size: this.build.size
                    });
                    break;
                case 'class':
                    await api.post('/creation/build/class', {
                        build_id: this.buildId,
                        class_id: this.build.class_id,
                        skill_choices: this.build.skill_choices
                    });
                    break;
                case 'background':
                    await api.post('/creation/build/background', {
                        build_id: this.buildId,
                        background_id: this.build.background_id
                    });
                    break;
                case 'abilities':
                    await api.post('/creation/build/abilities', {
                        build_id: this.buildId,
                        scores: this.build.ability_scores,
                        method: this.build.ability_method,
                        bonuses: this.build.ability_bonuses
                    });
                    break;
                case 'feat':
                    await api.post('/creation/build/feat', {
                        build_id: this.buildId,
                        feat_id: this.build.origin_feat_id
                    });
                    break;
                case 'equipment':
                    await api.post('/creation/build/equipment', {
                        build_id: this.buildId,
                        choices: this.build.equipment_choices
                    });
                    break;
                case 'details':
                    await api.post('/creation/build/details', {
                        build_id: this.buildId,
                        name: this.build.name
                    });
                    break;
            }
        } catch (error) {
            console.error(`Failed to save step ${step.id}:`, error);
        }
    }

    /**
     * Create the final character.
     */
    async createCharacter() {
        if (!this.buildId) {
            this.showError('No build in progress');
            return;
        }

        try {
            const result = await api.post(`/creation/build/${this.buildId}/finalize`, {});

            if (result.success) {
                this.hide();

                // Emit event for character created
                eventBus.emit(EVENTS.CHARACTER_IMPORTED, {
                    character: result.character,
                    source: 'creation'
                });

                this.showSuccess(`${result.character.name} created successfully!`);
            } else {
                this.showError('Failed to create character');
            }
        } catch (error) {
            console.error('Failed to create character:', error);
            this.showError(error.message || 'Failed to create character');
        }
    }

    /**
     * Show error message.
     */
    showError(message) {
        // Simple alert for now - could be improved with toast notification
        alert(message);
    }

    /**
     * Show success message.
     */
    showSuccess(message) {
        alert(message);
    }

    // ==================== Step Renderers ====================

    /**
     * Render species selection step.
     */
    renderSpeciesStep(container) {
        container.innerHTML = `
            <div class="step-content species-step">
                <h3 class="step-title">Choose Your Species</h3>
                <p class="step-description">Your species determines your size, speed, and special traits.</p>

                <div class="selection-grid species-grid">
                    ${this.speciesData.map(species => `
                        <div class="selection-card ${this.build.species_id === species.id ? 'selected' : ''}"
                             data-species-id="${species.id}">
                            <div class="card-header">
                                <h4 class="card-title">${species.name}</h4>
                                <div class="card-badges">
                                    <span class="badge">${species.size}</span>
                                    <span class="badge">${species.speed} ft</span>
                                </div>
                            </div>
                            <p class="card-description">${species.description?.substring(0, 150)}...</p>
                            <div class="card-traits">
                                ${(species.traits || []).map(t => `<span class="trait-tag">${t}</span>`).join('')}
                            </div>
                        </div>
                    `).join('')}
                </div>

                ${this.selectedSpecies ? this.renderSpeciesDetails() : ''}
            </div>
        `;

        // Add click handlers
        container.querySelectorAll('.selection-card[data-species-id]').forEach(card => {
            card.addEventListener('click', () => {
                const speciesId = card.dataset.speciesId;
                this.selectSpecies(speciesId);
            });
        });
    }

    selectSpecies(speciesId) {
        this.build.species_id = speciesId;
        this.selectedSpecies = this.speciesData.find(s => s.id === speciesId);
        this.renderCurrentStep();
    }

    renderSpeciesDetails() {
        const species = this.selectedSpecies;
        if (!species) return '';

        return `
            <div class="selection-details">
                <h4>${species.name} Traits</h4>
                <ul class="trait-list">
                    ${(species.traits || []).map(trait => `
                        <li><strong>${trait}</strong></li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    /**
     * Render class selection step.
     */
    renderClassStep(container) {
        container.innerHTML = `
            <div class="step-content class-step">
                <h3 class="step-title">Choose Your Class</h3>
                <p class="step-description">Your class determines your combat abilities, features, and playstyle.</p>

                <div class="selection-grid class-grid">
                    ${this.classData.map(cls => `
                        <div class="selection-card ${this.build.class_id === cls.id ? 'selected' : ''}"
                             data-class-id="${cls.id}">
                            <div class="card-header">
                                <h4 class="card-title">${cls.name}</h4>
                                <div class="card-badges">
                                    <span class="badge hit-die">${cls.hit_die}</span>
                                </div>
                            </div>
                            <p class="card-description">${cls.description?.substring(0, 120)}...</p>
                            <div class="card-info">
                                <span class="info-label">Primary:</span>
                                <span class="info-value">${this.formatPrimaryAbility(cls.primary_ability)}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>

                ${this.selectedClass ? this.renderClassDetails() : ''}
            </div>
        `;

        container.querySelectorAll('.selection-card[data-class-id]').forEach(card => {
            card.addEventListener('click', () => {
                const classId = card.dataset.classId;
                this.selectClass(classId);
            });
        });
    }

    selectClass(classId) {
        this.build.class_id = classId;
        this.selectedClass = this.classData.find(c => c.id === classId);
        this.renderCurrentStep();
    }

    formatPrimaryAbility(ability) {
        if (!ability) return '';
        return ability.replace(/_/g, ' ').replace(/or/g, ' or ');
    }

    renderClassDetails() {
        const cls = this.selectedClass;
        if (!cls) return '';

        return `
            <div class="selection-details">
                <h4>${cls.name} Features</h4>
                <div class="detail-row">
                    <span class="detail-label">Hit Die:</span>
                    <span class="detail-value">${cls.hit_die}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Saving Throws:</span>
                    <span class="detail-value">${(cls.saving_throws || []).map(s => s.toUpperCase()).join(', ')}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Armor:</span>
                    <span class="detail-value">${(cls.armor_proficiencies || []).join(', ') || 'None'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Weapons:</span>
                    <span class="detail-value">${(cls.weapon_proficiencies || []).join(', ')}</span>
                </div>
            </div>
        `;
    }

    /**
     * Render background selection step.
     */
    renderBackgroundStep(container) {
        container.innerHTML = `
            <div class="step-content background-step">
                <h3 class="step-title">Choose Your Background</h3>
                <p class="step-description">Your background gives you ability score bonuses, skills, and an origin feat.</p>

                <div class="selection-grid background-grid">
                    ${this.backgroundData.map(bg => `
                        <div class="selection-card ${this.build.background_id === bg.id ? 'selected' : ''}"
                             data-background-id="${bg.id}">
                            <div class="card-header">
                                <h4 class="card-title">${bg.name}</h4>
                            </div>
                            <p class="card-description">${bg.description?.substring(0, 100)}...</p>
                            <div class="card-info">
                                <span class="info-label">Skills:</span>
                                <span class="info-value">${(bg.skill_proficiencies || []).join(', ')}</span>
                            </div>
                            <div class="card-info">
                                <span class="info-label">Feat:</span>
                                <span class="info-value">${bg.origin_feat || 'Choice'}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>

                ${this.selectedBackground ? this.renderBackgroundDetails() : ''}
            </div>
        `;

        container.querySelectorAll('.selection-card[data-background-id]').forEach(card => {
            card.addEventListener('click', () => {
                const bgId = card.dataset.backgroundId;
                this.selectBackground(bgId);
            });
        });
    }

    selectBackground(backgroundId) {
        this.build.background_id = backgroundId;
        this.selectedBackground = this.backgroundData.find(b => b.id === backgroundId);
        this.renderCurrentStep();
    }

    renderBackgroundDetails() {
        const bg = this.selectedBackground;
        if (!bg) return '';

        return `
            <div class="selection-details">
                <h4>${bg.name}</h4>
                <p class="detail-description">${bg.description}</p>
                <div class="detail-row">
                    <span class="detail-label">Skills:</span>
                    <span class="detail-value">${(bg.skill_proficiencies || []).join(', ')}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Origin Feat:</span>
                    <span class="detail-value">${bg.origin_feat}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Ability Bonuses:</span>
                    <span class="detail-value">+2/+1 to two abilities of your choice</span>
                </div>
            </div>
        `;
    }

    /**
     * Render abilities step.
     */
    renderAbilitiesStep(container) {
        const pointsUsed = this.calculatePointsUsed();
        const pointsRemaining = 27 - pointsUsed;

        container.innerHTML = `
            <div class="step-content abilities-step">
                <h3 class="step-title">Set Ability Scores</h3>

                <div class="ability-method-toggle">
                    <button class="method-btn ${this.build.ability_method === 'point_buy' ? 'active' : ''}" data-method="point_buy">
                        Point Buy
                    </button>
                    <button class="method-btn ${this.build.ability_method === 'standard_array' ? 'active' : ''}" data-method="standard_array">
                        Standard Array
                    </button>
                </div>

                ${this.build.ability_method === 'point_buy' ? `
                    <div class="points-counter">
                        <span class="points-label">Points Remaining:</span>
                        <span class="points-value ${pointsRemaining < 0 ? 'over-budget' : ''}">${pointsRemaining}</span>
                        <span class="points-total">/ 27</span>
                    </div>
                ` : ''}

                <div class="ability-scores-grid">
                    ${ABILITIES.map(ability => this.renderAbilityRow(ability)).join('')}
                </div>

                <div class="ability-bonuses-section">
                    <h4>Background Bonuses</h4>
                    <p class="bonus-description">Assign +2 to one ability and +1 to another (or +1 to three abilities)</p>
                    <div class="bonus-grid">
                        ${ABILITIES.map(ability => `
                            <div class="bonus-row">
                                <span class="bonus-label">${ABILITY_LABELS[ability]}</span>
                                <select class="bonus-select" data-ability="${ability}">
                                    <option value="0" ${(this.build.ability_bonuses[ability] || 0) === 0 ? 'selected' : ''}>+0</option>
                                    <option value="1" ${this.build.ability_bonuses[ability] === 1 ? 'selected' : ''}>+1</option>
                                    <option value="2" ${this.build.ability_bonuses[ability] === 2 ? 'selected' : ''}>+2</option>
                                </select>
                            </div>
                        `).join('')}
                    </div>
                    <div class="bonus-status" id="bonus-status"></div>
                </div>

                <div class="final-scores">
                    <h4>Final Scores</h4>
                    <div class="final-scores-grid">
                        ${ABILITIES.map(ability => {
                            const base = this.build.ability_scores[ability];
                            const bonus = this.build.ability_bonuses[ability] || 0;
                            const final = Math.min(20, base + bonus);
                            const mod = Math.floor((final - 10) / 2);
                            return `
                                <div class="final-score">
                                    <span class="score-label">${ABILITY_LABELS[ability]}</span>
                                    <span class="score-value">${final}</span>
                                    <span class="score-modifier">${mod >= 0 ? '+' : ''}${mod}</span>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            </div>
        `;

        // Method toggle
        container.querySelectorAll('.method-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.build.ability_method = btn.dataset.method;
                if (this.build.ability_method === 'standard_array') {
                    this.applyStandardArray();
                }
                this.renderCurrentStep();
            });
        });

        // Point buy +/- buttons
        container.querySelectorAll('.ability-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const ability = btn.dataset.ability;
                const delta = parseInt(btn.dataset.delta);
                this.adjustAbility(ability, delta);
            });
        });

        // Bonus selects
        container.querySelectorAll('.bonus-select').forEach(select => {
            select.addEventListener('change', () => {
                this.updateAbilityBonuses();
            });
        });

        this.updateBonusStatus();
    }

    renderAbilityRow(ability) {
        const score = this.build.ability_scores[ability];
        const cost = POINT_BUY_COSTS[score] || 0;
        const canIncrease = this.build.ability_method === 'point_buy' && score < 15;
        const canDecrease = this.build.ability_method === 'point_buy' && score > 8;

        return `
            <div class="ability-row">
                <span class="ability-label">${ABILITY_LABELS[ability]}</span>
                <div class="ability-controls">
                    <button class="ability-btn ${!canDecrease ? 'disabled' : ''}"
                            data-ability="${ability}" data-delta="-1"
                            ${!canDecrease ? 'disabled' : ''}>−</button>
                    <span class="ability-value">${score}</span>
                    <button class="ability-btn ${!canIncrease ? 'disabled' : ''}"
                            data-ability="${ability}" data-delta="1"
                            ${!canIncrease ? 'disabled' : ''}>+</button>
                </div>
                <span class="ability-cost">(${cost} pts)</span>
            </div>
        `;
    }

    adjustAbility(ability, delta) {
        const current = this.build.ability_scores[ability];
        const newValue = current + delta;

        if (newValue < 8 || newValue > 15) return;

        // Check point budget
        const currentCost = this.calculatePointsUsed();
        const newCost = currentCost - POINT_BUY_COSTS[current] + POINT_BUY_COSTS[newValue];

        if (newCost > 27) return;

        this.build.ability_scores[ability] = newValue;
        this.renderCurrentStep();
    }

    calculatePointsUsed() {
        return ABILITIES.reduce((total, ability) => {
            return total + (POINT_BUY_COSTS[this.build.ability_scores[ability]] || 0);
        }, 0);
    }

    applyStandardArray() {
        // Default distribution
        this.build.ability_scores = {
            strength: 15,
            dexterity: 14,
            constitution: 13,
            intelligence: 12,
            wisdom: 10,
            charisma: 8
        };
    }

    updateAbilityBonuses() {
        this.build.ability_bonuses = {};

        document.querySelectorAll('.bonus-select').forEach(select => {
            const ability = select.dataset.ability;
            const value = parseInt(select.value);
            if (value > 0) {
                this.build.ability_bonuses[ability] = value;
            }
        });

        this.updateBonusStatus();
        this.updateFinalScores();
    }

    updateBonusStatus() {
        const status = document.getElementById('bonus-status');
        if (!status) return;

        const total = Object.values(this.build.ability_bonuses).reduce((a, b) => a + b, 0);
        const values = Object.values(this.build.ability_bonuses);

        let message = '';
        let isValid = false;

        if (total === 0) {
            message = 'Assign your background ability bonuses';
        } else if (total === 3) {
            if (values.includes(2) && values.includes(1) && values.length === 2) {
                message = '✓ Valid: +2/+1 to two abilities';
                isValid = true;
            } else if (values.every(v => v === 1) && values.length === 3) {
                message = '✓ Valid: +1 to three abilities';
                isValid = true;
            } else {
                message = '✗ Invalid pattern - use +2/+1 or +1/+1/+1';
            }
        } else {
            message = `✗ Total must be +3 (currently +${total})`;
        }

        status.textContent = message;
        status.className = `bonus-status ${isValid ? 'valid' : 'invalid'}`;
    }

    updateFinalScores() {
        const grid = document.querySelector('.final-scores-grid');
        if (!grid) return;

        grid.innerHTML = ABILITIES.map(ability => {
            const base = this.build.ability_scores[ability];
            const bonus = this.build.ability_bonuses[ability] || 0;
            const final = Math.min(20, base + bonus);
            const mod = Math.floor((final - 10) / 2);
            return `
                <div class="final-score">
                    <span class="score-label">${ABILITY_LABELS[ability]}</span>
                    <span class="score-value">${final}</span>
                    <span class="score-modifier">${mod >= 0 ? '+' : ''}${mod}</span>
                </div>
            `;
        }).join('');
    }

    /**
     * Render feat selection step.
     */
    renderFeatStep(container) {
        // Get recommended feat from background
        const recommendedFeat = this.selectedBackground?.origin_feat || null;

        container.innerHTML = `
            <div class="step-content feat-step">
                <h3 class="step-title">Choose Origin Feat</h3>
                <p class="step-description">Your background recommends ${recommendedFeat || 'an origin feat'}. You can choose any origin feat.</p>

                <div class="selection-grid feat-grid">
                    ${this.originFeats.map(feat => `
                        <div class="selection-card ${this.build.origin_feat_id === feat.id ? 'selected' : ''} ${feat.name === recommendedFeat ? 'recommended' : ''}"
                             data-feat-id="${feat.id}">
                            <div class="card-header">
                                <h4 class="card-title">${feat.name}</h4>
                                ${feat.name === recommendedFeat ? '<span class="recommended-badge">Recommended</span>' : ''}
                            </div>
                            <p class="card-description">${feat.description?.substring(0, 150)}...</p>
                        </div>
                    `).join('')}
                </div>

                ${this.selectedFeat ? this.renderFeatDetails() : ''}
            </div>
        `;

        container.querySelectorAll('.selection-card[data-feat-id]').forEach(card => {
            card.addEventListener('click', () => {
                const featId = card.dataset.featId;
                this.selectFeat(featId);
            });
        });
    }

    selectFeat(featId) {
        this.build.origin_feat_id = featId;
        this.selectedFeat = this.originFeats.find(f => f.id === featId);
        this.renderCurrentStep();
    }

    renderFeatDetails() {
        const feat = this.selectedFeat;
        if (!feat) return '';

        const benefits = feat.benefits || [];

        return `
            <div class="selection-details">
                <h4>${feat.name}</h4>
                <p class="detail-description">${feat.description}</p>
                ${benefits.length > 0 ? `
                    <ul class="benefit-list">
                        ${benefits.map(b => `<li><strong>${b.name}:</strong> ${b.description}</li>`).join('')}
                    </ul>
                ` : ''}
            </div>
        `;
    }

    /**
     * Render equipment step.
     */
    renderEquipmentStep(container) {
        container.innerHTML = `
            <div class="step-content equipment-step">
                <h3 class="step-title">Starting Equipment</h3>
                <p class="step-description">Equipment choices will be available based on your class. For now, you'll receive default starting equipment.</p>

                <div class="equipment-info">
                    <div class="equipment-note">
                        <span class="note-icon">📦</span>
                        <p>Your character will start with the default equipment for a ${this.selectedClass?.name || 'your class'}.</p>
                    </div>
                </div>
            </div>
        `;

        // Mark as done - equipment choices simplified for now
        this.build.equipment_choices = [{ type: 'default' }];
    }

    /**
     * Render details step.
     */
    renderDetailsStep(container) {
        container.innerHTML = `
            <div class="step-content details-step">
                <h3 class="step-title">Character Details</h3>
                <p class="step-description">Give your character a name and optional description.</p>

                <div class="details-form">
                    <div class="form-group">
                        <label for="character-name">Character Name *</label>
                        <input type="text" id="character-name" class="form-input"
                               value="${this.build.name}" placeholder="Enter character name" maxlength="50">
                    </div>
                </div>
            </div>
        `;

        const nameInput = document.getElementById('character-name');
        nameInput?.addEventListener('input', (e) => {
            this.build.name = e.target.value;
        });
        nameInput?.focus();
    }

    /**
     * Render review step.
     */
    renderReviewStep(container) {
        const finalScores = this.getFinalScores();
        const modifiers = this.getModifiers(finalScores);

        container.innerHTML = `
            <div class="step-content review-step">
                <h3 class="step-title">Character Summary</h3>

                <div class="review-card">
                    <div class="review-header">
                        <h2 class="character-name">${this.build.name || 'Unnamed Hero'}</h2>
                        <div class="character-subtitle">
                            ${this.selectedSpecies?.name || ''} ${this.selectedClass?.name || ''}
                        </div>
                    </div>

                    <div class="review-grid">
                        <div class="review-section">
                            <h4>Background</h4>
                            <p>${this.selectedBackground?.name || 'None'}</p>
                        </div>

                        <div class="review-section">
                            <h4>Origin Feat</h4>
                            <p>${this.selectedFeat?.name || 'None'}</p>
                        </div>
                    </div>

                    <div class="review-abilities">
                        <h4>Ability Scores</h4>
                        <div class="ability-summary">
                            ${ABILITIES.map(ability => `
                                <div class="ability-box">
                                    <span class="ability-name">${ABILITY_LABELS[ability]}</span>
                                    <span class="ability-score">${finalScores[ability]}</span>
                                    <span class="ability-mod">${modifiers[ability] >= 0 ? '+' : ''}${modifiers[ability]}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>

                    <div class="review-stats">
                        <div class="stat-box">
                            <span class="stat-label">Hit Points</span>
                            <span class="stat-value">${this.calculateHP()}</span>
                        </div>
                        <div class="stat-box">
                            <span class="stat-label">AC</span>
                            <span class="stat-value">${10 + modifiers.dexterity}</span>
                        </div>
                        <div class="stat-box">
                            <span class="stat-label">Speed</span>
                            <span class="stat-value">${this.selectedSpecies?.speed || 30} ft</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    getFinalScores() {
        const final = {};
        ABILITIES.forEach(ability => {
            const base = this.build.ability_scores[ability];
            const bonus = this.build.ability_bonuses[ability] || 0;
            final[ability] = Math.min(20, base + bonus);
        });
        return final;
    }

    getModifiers(scores) {
        const mods = {};
        ABILITIES.forEach(ability => {
            mods[ability] = Math.floor((scores[ability] - 10) / 2);
        });
        return mods;
    }

    calculateHP() {
        const hitDie = this.selectedClass?.hit_die || 'd8';
        const hitDieMax = parseInt(hitDie.substring(1));
        const conMod = Math.floor((this.getFinalScores().constitution - 10) / 2);
        return hitDieMax + conMod;
    }
}

// Create singleton instance
const characterCreationWizard = new CharacterCreationWizard();

export default characterCreationWizard;
