/**
 * Character Sheet Modal - BG3-Style
 * Comprehensive character information display
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';

// Skill to ability mapping (D&D 5e 2024)
const SKILLS = {
    'acrobatics': { ability: 'dexterity', name: 'Acrobatics' },
    'animal_handling': { ability: 'wisdom', name: 'Animal Handling' },
    'arcana': { ability: 'intelligence', name: 'Arcana' },
    'athletics': { ability: 'strength', name: 'Athletics' },
    'deception': { ability: 'charisma', name: 'Deception' },
    'history': { ability: 'intelligence', name: 'History' },
    'insight': { ability: 'wisdom', name: 'Insight' },
    'intimidation': { ability: 'charisma', name: 'Intimidation' },
    'investigation': { ability: 'intelligence', name: 'Investigation' },
    'medicine': { ability: 'wisdom', name: 'Medicine' },
    'nature': { ability: 'intelligence', name: 'Nature' },
    'perception': { ability: 'wisdom', name: 'Perception' },
    'performance': { ability: 'charisma', name: 'Performance' },
    'persuasion': { ability: 'charisma', name: 'Persuasion' },
    'religion': { ability: 'intelligence', name: 'Religion' },
    'sleight_of_hand': { ability: 'dexterity', name: 'Sleight of Hand' },
    'stealth': { ability: 'dexterity', name: 'Stealth' },
    'survival': { ability: 'wisdom', name: 'Survival' }
};

const ABILITIES = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'];
const ABILITY_ABBREV = {
    strength: 'STR',
    dexterity: 'DEX',
    constitution: 'CON',
    intelligence: 'INT',
    wisdom: 'WIS',
    charisma: 'CHA'
};

// Class icons for portrait
const CLASS_ICONS = {
    fighter: '⚔️',
    wizard: '🧙',
    rogue: '🗡️',
    cleric: '✝️',
    ranger: '🏹',
    paladin: '🛡️',
    barbarian: '💪',
    bard: '🎵',
    druid: '🌿',
    monk: '👊',
    sorcerer: '✨',
    warlock: '👁️',
    default: '👤'
};

// Hit die by class
const HIT_DICE = {
    barbarian: 12,
    fighter: 10,
    paladin: 10,
    ranger: 10,
    bard: 8,
    cleric: 8,
    druid: 8,
    monk: 8,
    rogue: 8,
    warlock: 8,
    sorcerer: 6,
    wizard: 6,
    default: 8
};

// XP thresholds by level
const XP_THRESHOLDS = [0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000, 85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000];

class CharacterSheetModal {
    constructor() {
        this.isOpen = false;
        this.element = null;
        this.characterData = null;
        this.combatantData = null;
        this.createModal();
        this.setupKeyboardShortcut();
        this.setupEventListeners();
    }

    createModal() {
        // Create modal container
        this.element = document.createElement('div');
        this.element.className = 'character-sheet-modal hidden';
        this.element.innerHTML = `
            <div class="character-sheet-overlay"></div>
            <div class="character-sheet-content">
                <div class="character-sheet-header">
                    <span class="character-sheet-title">Character Sheet</span>
                    <button class="character-sheet-close" aria-label="Close">&times;</button>
                </div>

                <div class="character-info-header">
                    <div class="character-portrait" id="sheet-portrait">👤</div>
                    <div class="character-details">
                        <div class="character-name" id="sheet-name">Character Name</div>
                        <div class="character-class-info" id="sheet-class">Human Fighter - Level 1</div>
                        <div class="character-background" id="sheet-background">Background</div>
                        <div class="xp-container">
                            <div class="xp-label" id="sheet-xp-label">XP: 0 / 300</div>
                            <div class="xp-bar">
                                <div class="xp-fill" id="sheet-xp-fill" style="width: 0%"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="character-sheet-body">
                    <!-- Left Column: Abilities & Combat -->
                    <div class="sheet-column-left">
                        <div class="ability-scores-section">
                            <div class="section-title">Ability Scores</div>
                            <div class="ability-scores-grid" id="sheet-abilities"></div>
                        </div>

                        <div class="combat-stats-section">
                            <div class="section-title">Combat</div>
                            <div class="combat-stats-grid" id="sheet-combat-stats"></div>
                        </div>

                        <div class="hp-section">
                            <div class="section-title">Hit Points</div>
                            <div class="hp-display">
                                <div class="hp-values">
                                    <span class="hp-current" id="sheet-hp-current">10</span>
                                    <span class="hp-separator">/</span>
                                    <span class="hp-max" id="sheet-hp-max">10</span>
                                </div>
                                <span class="hp-temp" id="sheet-hp-temp"></span>
                            </div>
                            <div class="hp-bar">
                                <div class="hp-fill healthy" id="sheet-hp-fill" style="width: 100%"></div>
                            </div>
                            <div class="hit-dice-row">
                                <span class="hit-dice-label">Hit Dice</span>
                                <span class="hit-dice-value" id="sheet-hit-dice">1d8 (1/1)</span>
                            </div>
                        </div>
                    </div>

                    <!-- Center Column: Skills & Saves -->
                    <div class="sheet-column-center">
                        <div class="saving-throws-section">
                            <div class="section-title">Saving Throws</div>
                            <div class="saves-grid" id="sheet-saves"></div>
                        </div>

                        <div class="skills-section">
                            <div class="section-title">Skills</div>
                            <div class="skills-list" id="sheet-skills"></div>
                        </div>

                        <div class="passive-scores-section">
                            <div class="section-title">Passive Scores</div>
                            <div class="passive-scores-grid" id="sheet-passives"></div>
                        </div>
                    </div>

                    <!-- Right Column: Proficiencies & Features -->
                    <div class="sheet-column-right">
                        <div class="proficiencies-section">
                            <div class="section-title">Proficiencies</div>
                            <div id="sheet-proficiencies"></div>
                        </div>

                        <div class="features-section">
                            <div class="section-title">Class Features</div>
                            <div class="features-list" id="sheet-features"></div>
                        </div>

                        <div class="spellcasting-section hidden" id="sheet-spellcasting">
                            <div class="section-title">Spellcasting</div>
                            <div class="spellcasting-stats" id="sheet-spell-stats"></div>
                            <div class="spell-slots-row" id="sheet-spell-slots"></div>
                        </div>
                    </div>
                </div>

                <div class="character-sheet-footer">
                    <div class="conditions-section">
                        <span class="conditions-label">Conditions:</span>
                        <div class="conditions-list" id="sheet-conditions">
                            <span class="no-conditions">None</span>
                        </div>
                    </div>

                    <div class="death-saves-section">
                        <div class="death-save-group">
                            <span class="death-save-label">Successes</span>
                            <div class="death-save-pips" id="sheet-death-successes">
                                <div class="death-save-pip"></div>
                                <div class="death-save-pip"></div>
                                <div class="death-save-pip"></div>
                            </div>
                        </div>
                        <div class="death-save-group">
                            <span class="death-save-label">Failures</span>
                            <div class="death-save-pips" id="sheet-death-failures">
                                <div class="death-save-pip"></div>
                                <div class="death-save-pip"></div>
                                <div class="death-save-pip"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(this.element);

        // Wire up close button and overlay
        const closeBtn = this.element.querySelector('.character-sheet-close');
        const overlay = this.element.querySelector('.character-sheet-overlay');

        closeBtn.addEventListener('click', () => this.hide());
        overlay.addEventListener('click', () => this.hide());
    }

    setupKeyboardShortcut() {
        document.addEventListener('keydown', (e) => {
            // Ignore if typing in input
            if (e.target.matches('input, textarea, select')) return;

            // Toggle on 'C' key
            if (e.key.toLowerCase() === 'c' && !e.ctrlKey && !e.altKey && !e.metaKey) {
                e.preventDefault();
                this.toggle();
            }

            // Close on Escape
            if (e.key === 'Escape' && this.isOpen) {
                e.preventDefault();
                this.hide();
            }
        });
    }

    setupEventListeners() {
        // Update when character changes
        eventBus.on(EVENTS.CHARACTER_UPDATED, () => {
            if (this.isOpen) {
                this.loadCharacterData();
            }
        });

        eventBus.on(EVENTS.COMBAT_STATE_UPDATED, () => {
            if (this.isOpen) {
                this.updateFromCombatState();
            }
        });
    }

    async show() {
        this.isOpen = true;
        this.element.classList.remove('hidden');
        await this.loadCharacterData();
        eventBus.emit(EVENTS.UI_MODAL_OPENED, { modal: 'character-sheet' });
    }

    hide() {
        this.isOpen = false;
        this.element.classList.add('hidden');
        eventBus.emit(EVENTS.UI_MODAL_CLOSED, { modal: 'character-sheet' });
    }

    toggle() {
        if (this.isOpen) {
            this.hide();
        } else {
            this.show();
        }
    }

    async loadCharacterData() {
        try {
            const gameState = state.getState();
            const playerId = gameState.playerId;

            // Get combatant data from state
            this.combatantData = gameState.combatants?.[playerId];

            // Try to get full character data from API if we have a character_id
            const characterId = this.combatantData?.character_id;
            if (characterId) {
                try {
                    const response = await api.getCharacter(characterId);
                    this.characterData = response.character || response;
                } catch (err) {
                    console.log('[CharacterSheet] Could not load full character data:', err.message);
                    this.characterData = null;
                }
            }

            this.updateDisplay();
        } catch (err) {
            console.error('[CharacterSheet] Error loading character data:', err);
        }
    }

    updateFromCombatState() {
        const gameState = state.getState();
        const playerId = gameState.playerId;
        this.combatantData = gameState.combatants?.[playerId];
        this.updateDisplay();
    }

    updateDisplay() {
        const char = this.characterData || {};
        const combat = this.combatantData || {};

        // Merge data sources
        const data = {
            name: char.name || combat.name || 'Unknown',
            species: char.species || combat.species || 'Human',
            characterClass: char.character_class || combat.character_class || combat.class || 'Fighter',
            subclass: char.subclass || combat.subclass || '',
            level: char.level || combat.level || 1,
            background: char.background || 'Adventurer',
            experience: char.experience || 0,
            abilities: char.abilities || combat.abilities || this.extractAbilities(combat),
            maxHp: char.max_hp || combat.maxHp || combat.max_hp || 10,
            currentHp: char.current_hp || combat.hp || combat.current_hp || 10,
            tempHp: char.temp_hp || combat.temp_hp || 0,
            ac: combat.ac || char.ac || 10,
            speed: combat.speed || char.speed || 30,
            proficiencyBonus: char.proficiency_bonus || this.calculateProficiencyBonus(char.level || combat.level || 1),
            skillProficiencies: char.skill_proficiencies || [],
            savingThrowProficiencies: char.saving_throw_proficiencies || [],
            weaponProficiencies: char.weapon_proficiencies || [],
            armorProficiencies: char.armor_proficiencies || [],
            toolProficiencies: char.tool_proficiencies || [],
            classFeatures: char.class_features || [],
            conditions: char.conditions || combat.conditions || [],
            deathSaves: char.death_saves || combat.death_saves || { successes: 0, failures: 0 },
            spellcasting: char.spellcasting || combat.spellcasting || null
        };

        this.updateHeader(data);
        this.updateAbilityScores(data);
        this.updateCombatStats(data);
        this.updateHP(data);
        this.updateSavingThrows(data);
        this.updateSkills(data);
        this.updatePassiveScores(data);
        this.updateProficiencies(data);
        this.updateFeatures(data);
        this.updateSpellcasting(data);
        this.updateConditions(data);
        this.updateDeathSaves(data);
    }

    extractAbilities(combat) {
        // Extract ability scores from combatant data
        return {
            strength: combat.strength || combat.str || 10,
            dexterity: combat.dexterity || combat.dex || 10,
            constitution: combat.constitution || combat.con || 10,
            intelligence: combat.intelligence || combat.int || 10,
            wisdom: combat.wisdom || combat.wis || 10,
            charisma: combat.charisma || combat.cha || 10
        };
    }

    calculateProficiencyBonus(level) {
        return Math.floor((level - 1) / 4) + 2;
    }

    calculateModifier(score) {
        return Math.floor((score - 10) / 2);
    }

    formatModifier(mod) {
        return mod >= 0 ? `+${mod}` : `${mod}`;
    }

    updateHeader(data) {
        const classLower = data.characterClass.toLowerCase();
        const icon = CLASS_ICONS[classLower] || CLASS_ICONS.default;

        document.getElementById('sheet-portrait').textContent = icon;
        document.getElementById('sheet-name').textContent = data.name;

        let classInfo = `${data.species} ${data.characterClass}`;
        if (data.subclass) {
            classInfo += ` (${data.subclass})`;
        }
        classInfo += ` - Level ${data.level}`;
        document.getElementById('sheet-class').textContent = classInfo;

        document.getElementById('sheet-background').textContent = data.background;

        // XP progress
        const currentXP = data.experience;
        const currentLevelXP = XP_THRESHOLDS[data.level - 1] || 0;
        const nextLevelXP = XP_THRESHOLDS[data.level] || XP_THRESHOLDS[19];
        const xpProgress = ((currentXP - currentLevelXP) / (nextLevelXP - currentLevelXP)) * 100;

        document.getElementById('sheet-xp-label').textContent = `XP: ${currentXP.toLocaleString()} / ${nextLevelXP.toLocaleString()}`;
        document.getElementById('sheet-xp-fill').style.width = `${Math.min(100, Math.max(0, xpProgress))}%`;
    }

    updateAbilityScores(data) {
        const container = document.getElementById('sheet-abilities');
        container.innerHTML = '';

        ABILITIES.forEach(ability => {
            const score = data.abilities[ability] || 10;
            const mod = this.calculateModifier(score);
            const modClass = mod > 0 ? 'positive' : (mod < 0 ? 'negative' : '');

            const box = document.createElement('div');
            box.className = 'ability-box';
            box.innerHTML = `
                <div class="ability-name">${ABILITY_ABBREV[ability]}</div>
                <div class="ability-score">${score}</div>
                <div class="ability-modifier ${modClass}">${this.formatModifier(mod)}</div>
            `;
            container.appendChild(box);
        });
    }

    updateCombatStats(data) {
        const container = document.getElementById('sheet-combat-stats');
        container.innerHTML = `
            <div class="combat-stat">
                <div class="combat-stat-label">AC</div>
                <div class="combat-stat-value ac">${data.ac}</div>
            </div>
            <div class="combat-stat">
                <div class="combat-stat-label">Initiative</div>
                <div class="combat-stat-value">${this.formatModifier(this.calculateModifier(data.abilities.dexterity || 10))}</div>
            </div>
            <div class="combat-stat">
                <div class="combat-stat-label">Speed</div>
                <div class="combat-stat-value speed">${data.speed}ft</div>
            </div>
            <div class="combat-stat">
                <div class="combat-stat-label">Prof. Bonus</div>
                <div class="combat-stat-value">+${data.proficiencyBonus}</div>
            </div>
        `;
    }

    updateHP(data) {
        document.getElementById('sheet-hp-current').textContent = data.currentHp;
        document.getElementById('sheet-hp-max').textContent = data.maxHp;

        const tempElement = document.getElementById('sheet-hp-temp');
        if (data.tempHp > 0) {
            tempElement.textContent = `+${data.tempHp} temp`;
        } else {
            tempElement.textContent = '';
        }

        const hpPercent = (data.currentHp / data.maxHp) * 100;
        const hpFill = document.getElementById('sheet-hp-fill');
        hpFill.style.width = `${Math.max(0, hpPercent)}%`;

        hpFill.classList.remove('healthy', 'injured', 'critical');
        if (hpPercent > 50) {
            hpFill.classList.add('healthy');
        } else if (hpPercent > 25) {
            hpFill.classList.add('injured');
        } else {
            hpFill.classList.add('critical');
        }

        // Hit dice
        const classLower = data.characterClass.toLowerCase();
        const hitDie = HIT_DICE[classLower] || HIT_DICE.default;
        document.getElementById('sheet-hit-dice').textContent = `${data.level}d${hitDie} (${data.level}/${data.level})`;
    }

    updateSavingThrows(data) {
        const container = document.getElementById('sheet-saves');
        container.innerHTML = '';

        ABILITIES.forEach(ability => {
            const mod = this.calculateModifier(data.abilities[ability] || 10);
            const isProficient = data.savingThrowProficiencies.includes(ability);
            const bonus = isProficient ? mod + data.proficiencyBonus : mod;

            const row = document.createElement('div');
            row.className = `save-row ${isProficient ? 'proficient' : ''}`;
            row.innerHTML = `
                <div class="proficiency-dot ${isProficient ? 'filled' : ''}"></div>
                <span class="save-name">${ABILITY_ABBREV[ability]}</span>
                <span class="save-bonus">${this.formatModifier(bonus)}</span>
            `;
            container.appendChild(row);
        });
    }

    updateSkills(data) {
        const container = document.getElementById('sheet-skills');
        container.innerHTML = '';

        // Sort skills alphabetically
        const sortedSkills = Object.entries(SKILLS).sort((a, b) => a[1].name.localeCompare(b[1].name));

        sortedSkills.forEach(([skillId, skillInfo]) => {
            const abilityMod = this.calculateModifier(data.abilities[skillInfo.ability] || 10);
            const isProficient = data.skillProficiencies.includes(skillId);
            // Check for expertise (double proficiency)
            const hasExpertise = data.skillProficiencies.filter(s => s === skillId).length > 1;

            let bonus = abilityMod;
            if (isProficient) bonus += data.proficiencyBonus;
            if (hasExpertise) bonus += data.proficiencyBonus;

            const row = document.createElement('div');
            row.className = `skill-row ${isProficient ? 'proficient' : ''} ${hasExpertise ? 'expertise' : ''}`;
            row.innerHTML = `
                <div class="proficiency-dot ${isProficient ? 'filled' : ''}"></div>
                <span class="skill-name">${skillInfo.name}</span>
                <span class="skill-ability">${ABILITY_ABBREV[skillInfo.ability]}</span>
                <span class="skill-bonus">${this.formatModifier(bonus)}</span>
            `;
            container.appendChild(row);
        });
    }

    updatePassiveScores(data) {
        const container = document.getElementById('sheet-passives');

        const getPassive = (skill) => {
            const skillInfo = SKILLS[skill];
            const abilityMod = this.calculateModifier(data.abilities[skillInfo.ability] || 10);
            const isProficient = data.skillProficiencies.includes(skill);
            return 10 + abilityMod + (isProficient ? data.proficiencyBonus : 0);
        };

        container.innerHTML = `
            <div class="passive-score">
                <div class="passive-label">Perception</div>
                <div class="passive-value">${getPassive('perception')}</div>
            </div>
            <div class="passive-score">
                <div class="passive-label">Investigation</div>
                <div class="passive-value">${getPassive('investigation')}</div>
            </div>
            <div class="passive-score">
                <div class="passive-label">Insight</div>
                <div class="passive-value">${getPassive('insight')}</div>
            </div>
        `;
    }

    updateProficiencies(data) {
        const container = document.getElementById('sheet-proficiencies');

        const formatList = (arr) => {
            if (!arr || arr.length === 0) return 'None';
            return arr.map(p => this.formatProficiencyName(p)).join(', ');
        };

        container.innerHTML = `
            <div class="proficiency-group">
                <div class="proficiency-group-title">Weapons</div>
                <div class="proficiency-list">${formatList(data.weaponProficiencies)}</div>
            </div>
            <div class="proficiency-group">
                <div class="proficiency-group-title">Armor</div>
                <div class="proficiency-list">${formatList(data.armorProficiencies)}</div>
            </div>
            <div class="proficiency-group">
                <div class="proficiency-group-title">Tools</div>
                <div class="proficiency-list">${formatList(data.toolProficiencies)}</div>
            </div>
            <div class="proficiency-group">
                <div class="proficiency-group-title">Languages</div>
                <div class="proficiency-list">Common</div>
            </div>
        `;
    }

    formatProficiencyName(name) {
        if (!name) return '';
        return name.split('_').map(word =>
            word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');
    }

    updateFeatures(data) {
        const container = document.getElementById('sheet-features');
        container.innerHTML = '';

        if (!data.classFeatures || data.classFeatures.length === 0) {
            // Default features based on class
            const defaultFeatures = this.getDefaultFeatures(data.characterClass, data.level);
            defaultFeatures.forEach(feature => {
                const item = document.createElement('div');
                item.className = 'feature-item';
                item.innerHTML = `
                    <div class="feature-name">${feature.name}</div>
                    <div class="feature-source">${feature.source}</div>
                `;
                container.appendChild(item);
            });
        } else {
            data.classFeatures.forEach(feature => {
                const item = document.createElement('div');
                item.className = 'feature-item';
                item.innerHTML = `
                    <div class="feature-name">${typeof feature === 'string' ? feature : feature.name || feature}</div>
                    <div class="feature-source">${data.characterClass} Feature</div>
                `;
                container.appendChild(item);
            });
        }
    }

    getDefaultFeatures(characterClass, level) {
        const features = [];
        const classLower = characterClass.toLowerCase();

        // Fighter features
        if (classLower === 'fighter') {
            if (level >= 1) features.push({ name: 'Fighting Style', source: 'Fighter 1' });
            if (level >= 1) features.push({ name: 'Second Wind', source: 'Fighter 1' });
            if (level >= 2) features.push({ name: 'Action Surge', source: 'Fighter 2' });
            if (level >= 3) features.push({ name: 'Martial Archetype', source: 'Fighter 3' });
            if (level >= 5) features.push({ name: 'Extra Attack', source: 'Fighter 5' });
            if (level >= 9) features.push({ name: 'Indomitable', source: 'Fighter 9' });
        }
        // Wizard features
        else if (classLower === 'wizard') {
            if (level >= 1) features.push({ name: 'Spellcasting', source: 'Wizard 1' });
            if (level >= 1) features.push({ name: 'Arcane Recovery', source: 'Wizard 1' });
            if (level >= 2) features.push({ name: 'Arcane Tradition', source: 'Wizard 2' });
        }
        // Rogue features
        else if (classLower === 'rogue') {
            if (level >= 1) features.push({ name: 'Expertise', source: 'Rogue 1' });
            if (level >= 1) features.push({ name: 'Sneak Attack', source: 'Rogue 1' });
            if (level >= 1) features.push({ name: "Thieves' Cant", source: 'Rogue 1' });
            if (level >= 2) features.push({ name: 'Cunning Action', source: 'Rogue 2' });
            if (level >= 3) features.push({ name: 'Roguish Archetype', source: 'Rogue 3' });
            if (level >= 5) features.push({ name: 'Uncanny Dodge', source: 'Rogue 5' });
        }
        // Cleric features
        else if (classLower === 'cleric') {
            if (level >= 1) features.push({ name: 'Spellcasting', source: 'Cleric 1' });
            if (level >= 1) features.push({ name: 'Divine Domain', source: 'Cleric 1' });
            if (level >= 2) features.push({ name: 'Channel Divinity', source: 'Cleric 2' });
            if (level >= 5) features.push({ name: 'Destroy Undead', source: 'Cleric 5' });
        }
        // Add more classes as needed...

        if (features.length === 0) {
            features.push({ name: 'Class Features', source: `${characterClass} 1` });
        }

        return features;
    }

    updateSpellcasting(data) {
        const section = document.getElementById('sheet-spellcasting');

        if (!data.spellcasting) {
            section.classList.add('hidden');
            return;
        }

        section.classList.remove('hidden');

        const statsContainer = document.getElementById('sheet-spell-stats');
        const slotsContainer = document.getElementById('sheet-spell-slots');

        const spellAbility = data.spellcasting.ability || 'intelligence';
        const abilityMod = this.calculateModifier(data.abilities[spellAbility] || 10);
        const spellDC = 8 + data.proficiencyBonus + abilityMod;
        const spellAttack = data.proficiencyBonus + abilityMod;

        statsContainer.innerHTML = `
            <div class="spell-stat">
                <div class="spell-stat-label">Spell Ability</div>
                <div class="spell-stat-value">${ABILITY_ABBREV[spellAbility]}</div>
            </div>
            <div class="spell-stat">
                <div class="spell-stat-label">Spell DC</div>
                <div class="spell-stat-value">${spellDC}</div>
            </div>
            <div class="spell-stat">
                <div class="spell-stat-label">Spell Attack</div>
                <div class="spell-stat-value">${this.formatModifier(spellAttack)}</div>
            </div>
        `;

        // Spell slots
        const slotsMax = data.spellcasting.spell_slots_max || {};
        const slotsUsed = data.spellcasting.spell_slots_used || {};

        slotsContainer.innerHTML = '';
        for (let level = 1; level <= 9; level++) {
            const max = slotsMax[level] || 0;
            if (max === 0) continue;

            const used = slotsUsed[level] || 0;
            const remaining = max - used;

            const slotDiv = document.createElement('div');
            slotDiv.className = 'spell-slot-level';

            let pips = '';
            for (let i = 0; i < max; i++) {
                pips += `<div class="slot-pip ${i >= remaining ? 'used' : ''}"></div>`;
            }

            slotDiv.innerHTML = `
                <span class="slot-level-label">${level}${this.getOrdinalSuffix(level)}</span>
                <div class="slot-pips">${pips}</div>
            `;
            slotsContainer.appendChild(slotDiv);
        }
    }

    getOrdinalSuffix(n) {
        const s = ['th', 'st', 'nd', 'rd'];
        const v = n % 100;
        return s[(v - 20) % 10] || s[v] || s[0];
    }

    updateConditions(data) {
        const container = document.getElementById('sheet-conditions');

        if (!data.conditions || data.conditions.length === 0) {
            container.innerHTML = '<span class="no-conditions">None</span>';
            return;
        }

        container.innerHTML = data.conditions.map(condition =>
            `<span class="condition-tag">${this.formatProficiencyName(condition)}</span>`
        ).join('');
    }

    updateDeathSaves(data) {
        const successPips = document.querySelectorAll('#sheet-death-successes .death-save-pip');
        const failurePips = document.querySelectorAll('#sheet-death-failures .death-save-pip');

        const successes = data.deathSaves?.successes || 0;
        const failures = data.deathSaves?.failures || 0;

        successPips.forEach((pip, i) => {
            pip.classList.toggle('success', i < successes);
        });

        failurePips.forEach((pip, i) => {
            pip.classList.toggle('failure', i < failures);
        });
    }
}

// Create singleton instance
export const characterSheetModal = new CharacterSheetModal();
export default characterSheetModal;
