/**
 * D&D Combat Engine - Encounter Panel
 * Form-based editor for individual encounter properties.
 */

/**
 * Encounter property editor panel
 */
export class EncounterPanel {
    constructor(container, callbacks = {}) {
        this.container = container;
        this.callbacks = callbacks;
        this.encounter = null;
        this.enemyTemplates = [
            'goblin', 'goblin_boss', 'skeleton', 'zombie', 'orc', 'orc_war_chief',
            'giant_rat', 'wolf', 'bugbear', 'mimic', 'owlbear', 'bandit',
            'bandit_captain', 'giant_spider', 'ogre', 'cultist', 'thug',
        ];
    }

    loadEncounter(encounter) {
        this.encounter = encounter;
        this.render();
    }

    clear() {
        this.encounter = null;
        this.container.innerHTML = `
            <h3>Selected Encounter</h3>
            <div class="no-selection">
                <p>Select an encounter node to edit</p>
            </div>
        `;
    }

    render() {
        if (!this.encounter) {
            this.clear();
            return;
        }

        const enc = this.encounter;
        this.container.innerHTML = `
            <h3>Encounter Properties</h3>

            <div class="form-group">
                <label for="enc-name">Name</label>
                <input type="text" id="enc-name" value="${this.escapeHtml(enc.name || '')}" placeholder="Encounter name">
            </div>

            <div class="form-group">
                <label for="enc-type">Type</label>
                <select id="enc-type">
                    <option value="combat" ${enc.type === 'combat' ? 'selected' : ''}>Combat</option>
                    <option value="rest" ${enc.type === 'rest' ? 'selected' : ''}>Rest</option>
                    <option value="choice" ${enc.type === 'choice' ? 'selected' : ''}>Choice</option>
                    <option value="cutscene" ${enc.type === 'cutscene' ? 'selected' : ''}>Cutscene</option>
                    <option value="social" ${enc.type === 'social' ? 'selected' : ''}>Social</option>
                    <option value="exploration" ${enc.type === 'exploration' ? 'selected' : ''}>Exploration</option>
                </select>
            </div>

            <div class="form-group">
                <label for="enc-intro">Intro Text</label>
                <textarea id="enc-intro" rows="3" placeholder="Scene description...">${this.escapeHtml(enc.story?.intro_text || '')}</textarea>
            </div>

            ${this.renderTypeSpecificFields(enc)}

            <div class="form-group">
                <label>Transitions (${(enc.transitions || []).length})</label>
                <div id="transitions-list" class="transitions-list">
                    ${this.renderTransitions(enc)}
                </div>
            </div>

            <div class="panel-actions">
                <button class="panel-btn danger" id="btn-delete-encounter">Delete Encounter</button>
            </div>
        `;

        this.setupEventListeners();
    }

    renderTypeSpecificFields(enc) {
        switch (enc.type) {
            case 'combat':
                return this.renderCombatFields(enc);
            case 'choice':
                return this.renderChoiceFields(enc);
            case 'rest':
                return this.renderRestFields(enc);
            default:
                return '';
        }
    }

    renderCombatFields(enc) {
        const enemies = enc.enemies || [];
        return `
            <div class="form-group">
                <label>Enemies</label>
                <div id="enemies-list" class="enemies-list">
                    ${enemies.map((e, i) => this.renderEnemyRow(e, i)).join('')}
                </div>
                <button class="panel-btn small" id="btn-add-enemy">+ Add Enemy</button>
            </div>

            <div class="form-group">
                <label for="enc-difficulty">Difficulty Override</label>
                <select id="enc-difficulty">
                    <option value="" ${!enc.difficulty_override ? 'selected' : ''}>Use Campaign Default</option>
                    <option value="easy" ${enc.difficulty_override === 'easy' ? 'selected' : ''}>Easy</option>
                    <option value="medium" ${enc.difficulty_override === 'medium' ? 'selected' : ''}>Medium</option>
                    <option value="hard" ${enc.difficulty_override === 'hard' ? 'selected' : ''}>Hard</option>
                    <option value="deadly" ${enc.difficulty_override === 'deadly' ? 'selected' : ''}>Deadly</option>
                </select>
            </div>
        `;
    }

    renderEnemyRow(enemy, index) {
        return `
            <div class="enemy-row" data-index="${index}">
                <select class="enemy-template" data-index="${index}">
                    ${this.enemyTemplates.map(t => `
                        <option value="${t}" ${enemy.template === t ? 'selected' : ''}>${t}</option>
                    `).join('')}
                </select>
                <input type="number" class="enemy-count" data-index="${index}" value="${enemy.count || 1}" min="1" max="20">
                <button class="remove-btn" data-index="${index}">×</button>
            </div>
        `;
    }

    renderChoiceFields(enc) {
        const choices = enc.choices || [];
        return `
            <div class="form-group">
                <label>Choices</label>
                <div id="choices-list" class="choices-list">
                    ${choices.map((c, i) => this.renderChoiceRow(c, i)).join('')}
                </div>
                <button class="panel-btn small" id="btn-add-choice">+ Add Choice</button>
            </div>
        `;
    }

    renderChoiceRow(choice, index) {
        return `
            <div class="choice-row" data-index="${index}">
                <input type="text" class="choice-text" data-index="${index}" value="${this.escapeHtml(choice.text || '')}" placeholder="Choice text">
                <div class="choice-settings">
                    <select class="choice-skill" data-index="${index}">
                        <option value="" ${!choice.skill_check ? 'selected' : ''}>No skill check</option>
                        <option value="persuasion" ${choice.skill_check === 'persuasion' ? 'selected' : ''}>Persuasion</option>
                        <option value="intimidation" ${choice.skill_check === 'intimidation' ? 'selected' : ''}>Intimidation</option>
                        <option value="deception" ${choice.skill_check === 'deception' ? 'selected' : ''}>Deception</option>
                        <option value="insight" ${choice.skill_check === 'insight' ? 'selected' : ''}>Insight</option>
                        <option value="athletics" ${choice.skill_check === 'athletics' ? 'selected' : ''}>Athletics</option>
                        <option value="stealth" ${choice.skill_check === 'stealth' ? 'selected' : ''}>Stealth</option>
                    </select>
                    <input type="number" class="choice-dc" data-index="${index}" value="${choice.dc || 10}" min="1" max="30" title="DC" ${!choice.skill_check ? 'disabled' : ''}>
                </div>
                <button class="remove-btn" data-index="${index}">×</button>
            </div>
        `;
    }

    renderRestFields(enc) {
        return `
            <div class="form-group">
                <label for="enc-rest-type">Rest Type</label>
                <select id="enc-rest-type">
                    <option value="short" ${enc.rest_type === 'short' ? 'selected' : ''}>Short Rest</option>
                    <option value="long" ${enc.rest_type === 'long' ? 'selected' : ''}>Long Rest</option>
                </select>
            </div>

            <div class="form-group">
                <label>
                    <input type="checkbox" id="enc-shop-available" ${enc.shop_available ? 'checked' : ''}>
                    Shop Available
                </label>
            </div>
        `;
    }

    renderTransitions(enc) {
        const transitions = enc.transitions || [];
        if (transitions.length === 0) {
            return '<p class="hint">No transitions. Connect to other encounters in the graph.</p>';
        }

        return transitions.map((t, i) => `
            <div class="transition-row" data-index="${i}">
                <span class="transition-target">→ ${t.target_id}</span>
                <select class="transition-condition" data-index="${i}">
                    <option value="default" ${t.condition === 'default' ? 'selected' : ''}>Default</option>
                    <option value="victory" ${t.condition === 'victory' ? 'selected' : ''}>On Victory</option>
                    <option value="defeat" ${t.condition === 'defeat' ? 'selected' : ''}>On Defeat</option>
                    <option value="choice" ${t.condition === 'choice' ? 'selected' : ''}>On Choice</option>
                </select>
                <button class="remove-btn" data-index="${i}">×</button>
            </div>
        `).join('');
    }

    setupEventListeners() {
        // Basic fields
        this.container.querySelector('#enc-name')?.addEventListener('input', (e) => {
            this.updateEncounter({ name: e.target.value });
        });

        this.container.querySelector('#enc-type')?.addEventListener('change', (e) => {
            this.updateEncounter({ type: e.target.value });
            this.render(); // Re-render for type-specific fields
        });

        this.container.querySelector('#enc-intro')?.addEventListener('input', (e) => {
            this.updateEncounter({ story: { ...this.encounter.story, intro_text: e.target.value } });
        });

        // Combat-specific
        this.container.querySelector('#btn-add-enemy')?.addEventListener('click', () => {
            const enemies = [...(this.encounter.enemies || []), { template: 'goblin', count: 1 }];
            this.updateEncounter({ enemies });
            this.render();
        });

        this.container.querySelectorAll('.enemy-template').forEach(el => {
            el.addEventListener('change', (e) => {
                const index = parseInt(e.target.dataset.index);
                const enemies = [...(this.encounter.enemies || [])];
                if (enemies[index]) {
                    enemies[index].template = e.target.value;
                    this.updateEncounter({ enemies });
                }
            });
        });

        this.container.querySelectorAll('.enemy-count').forEach(el => {
            el.addEventListener('change', (e) => {
                const index = parseInt(e.target.dataset.index);
                const enemies = [...(this.encounter.enemies || [])];
                if (enemies[index]) {
                    enemies[index].count = parseInt(e.target.value) || 1;
                    this.updateEncounter({ enemies });
                }
            });
        });

        this.container.querySelectorAll('.enemies-list .remove-btn').forEach(el => {
            el.addEventListener('click', (e) => {
                const index = parseInt(e.target.dataset.index);
                const enemies = (this.encounter.enemies || []).filter((_, i) => i !== index);
                this.updateEncounter({ enemies });
                this.render();
            });
        });

        this.container.querySelector('#enc-difficulty')?.addEventListener('change', (e) => {
            this.updateEncounter({ difficulty_override: e.target.value || null });
        });

        // Choice-specific
        this.container.querySelector('#btn-add-choice')?.addEventListener('click', () => {
            const choices = [...(this.encounter.choices || []), { text: 'New choice' }];
            this.updateEncounter({ choices });
            this.render();
        });

        this.container.querySelectorAll('.choice-text').forEach(el => {
            el.addEventListener('input', (e) => {
                const index = parseInt(e.target.dataset.index);
                const choices = [...(this.encounter.choices || [])];
                if (choices[index]) {
                    choices[index].text = e.target.value;
                    this.updateEncounter({ choices });
                }
            });
        });

        this.container.querySelectorAll('.choice-skill').forEach(el => {
            el.addEventListener('change', (e) => {
                const index = parseInt(e.target.dataset.index);
                const choices = [...(this.encounter.choices || [])];
                if (choices[index]) {
                    choices[index].skill_check = e.target.value || null;
                    this.updateEncounter({ choices });
                    // Enable/disable DC input
                    const dcInput = this.container.querySelector(`.choice-dc[data-index="${index}"]`);
                    if (dcInput) {
                        dcInput.disabled = !e.target.value;
                    }
                }
            });
        });

        this.container.querySelectorAll('.choice-dc').forEach(el => {
            el.addEventListener('change', (e) => {
                const index = parseInt(e.target.dataset.index);
                const choices = [...(this.encounter.choices || [])];
                if (choices[index]) {
                    choices[index].dc = parseInt(e.target.value) || 10;
                    this.updateEncounter({ choices });
                }
            });
        });

        this.container.querySelectorAll('.choices-list .remove-btn').forEach(el => {
            el.addEventListener('click', (e) => {
                const index = parseInt(e.target.dataset.index);
                const choices = (this.encounter.choices || []).filter((_, i) => i !== index);
                this.updateEncounter({ choices });
                this.render();
            });
        });

        // Rest-specific
        this.container.querySelector('#enc-rest-type')?.addEventListener('change', (e) => {
            this.updateEncounter({ rest_type: e.target.value });
        });

        this.container.querySelector('#enc-shop-available')?.addEventListener('change', (e) => {
            this.updateEncounter({ shop_available: e.target.checked });
        });

        // Transitions
        this.container.querySelectorAll('.transition-condition').forEach(el => {
            el.addEventListener('change', (e) => {
                const index = parseInt(e.target.dataset.index);
                const transitions = [...(this.encounter.transitions || [])];
                if (transitions[index]) {
                    transitions[index].condition = e.target.value;
                    this.updateEncounter({ transitions });
                }
            });
        });

        this.container.querySelectorAll('.transitions-list .remove-btn').forEach(el => {
            el.addEventListener('click', (e) => {
                const index = parseInt(e.target.dataset.index);
                const transitions = (this.encounter.transitions || []).filter((_, i) => i !== index);
                this.updateEncounter({ transitions });
                this.render();
            });
        });

        // Delete button
        this.container.querySelector('#btn-delete-encounter')?.addEventListener('click', () => {
            // Let the main editor handle this
            const event = new CustomEvent('encounter:delete', { detail: { id: this.encounter.id } });
            this.container.dispatchEvent(event);
        });
    }

    updateEncounter(updates) {
        if (!this.encounter) return;
        Object.assign(this.encounter, updates);
        this.callbacks.onUpdate?.(updates);
    }

    escapeHtml(str) {
        if (str === null || str === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(str);
        return div.innerHTML;
    }
}

export default EncounterPanel;
