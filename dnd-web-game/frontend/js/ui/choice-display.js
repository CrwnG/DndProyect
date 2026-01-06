/**
 * D&D Combat Engine - Choice Display
 * Interactive choice UI with skill check badges and dice animations
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import apiClient from '../api/api-client.js';

// Skill to ability mapping for icons
const SKILL_ABILITIES = {
    athletics: { ability: 'str', icon: '💪' },
    acrobatics: { ability: 'dex', icon: '🤸' },
    sleight_of_hand: { ability: 'dex', icon: '🤏' },
    stealth: { ability: 'dex', icon: '🥷' },
    arcana: { ability: 'int', icon: '✨' },
    history: { ability: 'int', icon: '📜' },
    investigation: { ability: 'int', icon: '🔍' },
    nature: { ability: 'int', icon: '🌿' },
    religion: { ability: 'int', icon: '⛪' },
    animal_handling: { ability: 'wis', icon: '🐾' },
    insight: { ability: 'wis', icon: '👁️' },
    medicine: { ability: 'wis', icon: '💊' },
    perception: { ability: 'wis', icon: '👀' },
    survival: { ability: 'wis', icon: '🏕️' },
    deception: { ability: 'cha', icon: '🎭' },
    intimidation: { ability: 'cha', icon: '😠' },
    performance: { ability: 'cha', icon: '🎭' },
    persuasion: { ability: 'cha', icon: '💬' },
    // Raw ability checks
    str: { ability: 'str', icon: '💪' },
    dex: { ability: 'dex', icon: '🏃' },
    con: { ability: 'con', icon: '❤️' },
    int: { ability: 'int', icon: '🧠' },
    wis: { ability: 'wis', icon: '🦉' },
    cha: { ability: 'cha', icon: '⭐' },
};

class ChoiceDisplay {
    constructor() {
        this.container = null;
        this.choices = [];
        this.sessionId = null;  // Store session ID directly
        this.isVisible = false;
        this.isRolling = false;

        // Click-to-roll state
        this.pendingChoice = null;      // Choice waiting for roll
        this.selectedPlayerId = null;   // Selected player for player_choice
        this.awaitingPlayerSelection = false;

        this.init();
    }

    init() {
        this.createContainer();
        this.setupEventListeners();
    }

    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'choice-display';
        this.container.className = 'choice-display hidden';
        this.container.innerHTML = `
            <div class="choice-backdrop"></div>
            <div class="choice-content">
                <div class="choice-header">
                    <h2 class="choice-title">Make Your Choice</h2>
                </div>
                <div class="choice-options" id="choice-options">
                    <!-- Populated dynamically -->
                </div>
                <!-- Player Selection for player_choice checks -->
                <div class="player-selection hidden" id="player-selection">
                    <div class="player-selection-header">
                        <h3 class="player-selection-title">Who will attempt this?</h3>
                        <p class="player-selection-skill" id="player-selection-skill"></p>
                    </div>
                    <div class="player-options" id="player-options">
                        <!-- Populated dynamically -->
                    </div>
                </div>
                <!-- Click to Roll phase -->
                <div class="click-to-roll hidden" id="click-to-roll">
                    <div class="click-to-roll-info">
                        <p class="roller-name" id="roller-name"></p>
                        <p class="skill-info" id="skill-info"></p>
                    </div>
                    <button class="roll-button" id="roll-button">
                        <span class="roll-icon">🎲</span>
                        <span class="roll-text">Click to Roll</span>
                    </button>
                </div>
                <div class="choice-result hidden" id="choice-result">
                    <div class="dice-roll-display">
                        <div class="dice-container" id="dice-container">
                            <div class="die d20 choice-die">
                                <div class="die-face" id="choice-die-value">20</div>
                            </div>
                        </div>
                        <div class="roll-details" id="roll-details">
                            <!-- Roll breakdown shown here -->
                        </div>
                    </div>
                    <div class="result-message" id="result-message"></div>
                    <button class="choice-continue-btn" id="choice-continue-btn">Continue</button>
                </div>
            </div>
        `;

        document.body.appendChild(this.container);
    }

    setupEventListeners() {
        // Continue button after seeing result
        document.getElementById('choice-continue-btn')?.addEventListener('click', () => {
            this.handleContinue();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (!this.isVisible || this.isRolling) return;

            // Number keys 1-9 to select choices
            if (e.key >= '1' && e.key <= '9') {
                const index = parseInt(e.key) - 1;
                if (index < this.choices.length) {
                    this.selectChoice(this.choices[index].id);
                }
            }

            // Space/Enter to continue after result
            if (e.key === ' ' || e.key === 'Enter') {
                const resultPanel = document.getElementById('choice-result');
                if (!resultPanel?.classList.contains('hidden')) {
                    this.handleContinue();
                }
            }
        });
    }

    /**
     * Show choices for a choice encounter
     * @param {Object} options - Display options
     * @param {Array} options.choices - Array of choice objects
     * @param {string} options.title - Optional title
     * @param {string} options.sessionId - Session ID for API calls
     */
    show(options) {
        const { choices, title = 'Make Your Choice', sessionId } = options;
        this.choices = choices || [];
        this.sessionId = sessionId;  // Store the session ID
        console.log('[ChoiceDisplay] show() called with sessionId:', sessionId);

        // Set title
        const titleEl = this.container.querySelector('.choice-title');
        if (titleEl) {
            titleEl.textContent = title;
        }

        // Render choices
        this.renderChoices();

        // Show container, hide result panel
        const resultPanel = document.getElementById('choice-result');
        resultPanel?.classList.add('hidden');

        const optionsPanel = document.getElementById('choice-options');
        optionsPanel?.classList.remove('hidden');

        this.container.classList.remove('hidden');
        this.isVisible = true;

        eventBus.emit(EVENTS.CHOICE_DISPLAYED, { choices });
    }

    hide() {
        this.container.classList.add('hidden');
        this.isVisible = false;
        this.isRolling = false;
        this.pendingChoice = null;
        this.selectedPlayerId = null;
        this.awaitingPlayerSelection = false;

        // Reset all panels to default state
        document.getElementById('choice-options')?.classList.remove('hidden');
        document.getElementById('player-selection')?.classList.add('hidden');
        document.getElementById('click-to-roll')?.classList.add('hidden');
        document.getElementById('choice-result')?.classList.add('hidden');
    }

    renderChoices() {
        const optionsEl = document.getElementById('choice-options');
        if (!optionsEl) return;

        optionsEl.innerHTML = this.choices.map((choice, index) => {
            const skillInfo = choice.skill_check ? this.getSkillInfo(choice.skill_check) : null;

            return `
                <button class="choice-option" data-choice-id="${choice.id}">
                    <span class="choice-number">${index + 1}</span>
                    <div class="choice-text-content">
                        <span class="choice-text">${choice.text}</span>
                        ${choice.description ? `<span class="choice-description">${choice.description}</span>` : ''}
                    </div>
                    ${skillInfo ? `
                        <div class="skill-check-badge ${skillInfo.difficultyClass}">
                            <span class="skill-icon">${skillInfo.icon}</span>
                            <span class="skill-name">${skillInfo.displayName}</span>
                            <span class="skill-difficulty">${skillInfo.difficultyText}</span>
                        </div>
                    ` : ''}
                </button>
            `;
        }).join('');

        // Add click handlers
        optionsEl.querySelectorAll('.choice-option').forEach(btn => {
            btn.addEventListener('click', () => {
                const choiceId = btn.dataset.choiceId;
                this.selectChoice(choiceId);
            });
        });
    }

    getSkillInfo(skillCheck) {
        const skill = skillCheck.skill.toLowerCase();
        const info = SKILL_ABILITIES[skill] || { ability: 'dex', icon: '🎲' };

        // Capitalize skill name
        const displayName = skill.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

        // Map DC to difficulty class and text
        const dc = skillCheck.dc;
        let difficultyClass = 'medium';
        let difficultyText = 'Medium';
        if (dc <= 10) {
            difficultyClass = 'easy';
            difficultyText = 'Easy';
        } else if (dc <= 15) {
            difficultyClass = 'medium';
            difficultyText = 'Medium';
        } else if (dc <= 20) {
            difficultyClass = 'hard';
            difficultyText = 'Hard';
        } else {
            difficultyClass = 'very-hard';
            difficultyText = 'Very Hard';
        }

        return {
            ...info,
            displayName,
            difficultyClass,
            difficultyText,
            dc,
        };
    }

    async selectChoice(choiceId) {
        if (this.isRolling || this.awaitingPlayerSelection) return;

        const choice = this.choices.find(c => c.id === choiceId);
        if (!choice) return;

        // Highlight selected choice
        const buttons = document.querySelectorAll('.choice-option');
        buttons.forEach(btn => {
            btn.classList.remove('selected');
            if (btn.dataset.choiceId === choiceId) {
                btn.classList.add('selected');
            }
            btn.disabled = true;
        });

        // If skill check with click-to-roll, show appropriate UI
        if (choice.skill_check) {
            const checkType = choice.skill_check.check_type || 'individual';
            this.pendingChoice = choice;

            if (checkType === 'player_choice') {
                // First, call API to get party options for selection
                await this.requestPlayerSelection(choiceId, choice);
            } else if (checkType === 'group') {
                // Group check - show click to roll for everyone
                this.showClickToRoll(choice, 'Everyone', true);
            } else {
                // Individual check - show click to roll for party leader
                this.showClickToRoll(choice, 'Party Leader', false);
            }
        } else {
            // No skill check - just advance
            await this.makeChoice(choiceId);
        }
    }

    async requestPlayerSelection(choiceId, choice) {
        try {
            const sessionId = this.sessionId || state.get('session.id');
            if (!sessionId) return;

            // Call API without player_id to get party options
            const result = await apiClient.advanceSession(sessionId, 'make_choice', {
                choice_id: choiceId
            });

            const choiceResult = result.extra || result.choice_result;

            if (choiceResult && choiceResult.awaiting_player_selection) {
                // Show player selection UI
                this.showPlayerSelection(choice, choiceResult);
            } else if (choiceResult && choiceResult.skill_check) {
                // Backend already rolled (shouldn't happen for player_choice)
                this.showResult(choiceResult);
            }
        } catch (error) {
            console.error('[ChoiceDisplay] Error requesting player selection:', error);
        }
    }

    showPlayerSelection(choice, selectionData) {
        this.awaitingPlayerSelection = true;

        // Hide options, show player selection
        document.getElementById('choice-options')?.classList.add('hidden');
        document.getElementById('player-selection')?.classList.remove('hidden');

        const skillDisplay = choice.skill_check.skill.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        document.getElementById('player-selection-skill').textContent =
            `${skillDisplay} Check (DC ${selectionData.dc})`;

        const playerOptions = document.getElementById('player-options');
        if (playerOptions && selectionData.party_options) {
            playerOptions.innerHTML = selectionData.party_options.map(player => `
                <button class="player-option" data-player-id="${player.id}">
                    <span class="player-name">${player.name}</span>
                    <span class="player-modifier ${player.modifier >= 0 ? 'positive' : 'negative'}">
                        ${player.modifier_display}
                    </span>
                </button>
            `).join('');

            // Add click handlers
            playerOptions.querySelectorAll('.player-option').forEach(btn => {
                btn.addEventListener('click', () => {
                    this.selectPlayer(btn.dataset.playerId, choice);
                });
            });
        }
    }

    selectPlayer(playerId, choice) {
        this.selectedPlayerId = playerId;
        this.awaitingPlayerSelection = false;

        // Hide player selection, show click to roll
        document.getElementById('player-selection')?.classList.add('hidden');

        // Find the player name from stored choice data
        const playerName = this.pendingChoice?.skill_check?.player_name || 'Selected Character';
        this.showClickToRoll(choice, playerName, false);
    }

    showClickToRoll(choice, rollerName, isGroup) {
        document.getElementById('choice-options')?.classList.add('hidden');
        document.getElementById('player-selection')?.classList.add('hidden');
        document.getElementById('click-to-roll')?.classList.remove('hidden');

        const skillName = choice.skill_check.skill.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

        document.getElementById('roller-name').textContent = isGroup ? 'Group Check' : rollerName;
        document.getElementById('skill-info').textContent =
            `${skillName} (DC ${choice.skill_check.dc})`;

        const rollButton = document.getElementById('roll-button');
        if (rollButton) {
            // Remove old listeners
            const newButton = rollButton.cloneNode(true);
            rollButton.parentNode.replaceChild(newButton, rollButton);

            newButton.addEventListener('click', () => {
                this.executeRoll(choice, isGroup);
            });
        }
    }

    async executeRoll(choice, isGroup) {
        this.isRolling = true;

        // Hide click-to-roll, show result panel with rolling dice
        document.getElementById('click-to-roll')?.classList.add('hidden');
        document.getElementById('choice-result')?.classList.remove('hidden');

        // Start dice animation
        const dieElement = document.querySelector('.choice-die');
        const dieValue = document.getElementById('choice-die-value');
        dieElement?.classList.add('rolling');

        // Animate random values
        const animationDuration = 1500;
        const intervalTime = 50;
        let elapsed = 0;

        const animInterval = setInterval(() => {
            const randomValue = Math.floor(Math.random() * 20) + 1;
            if (dieValue) dieValue.textContent = randomValue;
            elapsed += intervalTime;

            if (elapsed >= animationDuration) {
                clearInterval(animInterval);
            }
        }, intervalTime);

        // Wait for animation to finish
        await new Promise(resolve => setTimeout(resolve, animationDuration));

        // Now make the actual API call with player_id if applicable
        await this.makeChoice(choice.id, this.selectedPlayerId);
    }

    async animateSkillCheck(choice) {
        // Hide options, show result panel
        const optionsPanel = document.getElementById('choice-options');
        const resultPanel = document.getElementById('choice-result');

        optionsPanel?.classList.add('hidden');
        resultPanel?.classList.remove('hidden');

        // Start dice animation
        const dieElement = document.querySelector('.choice-die');
        const dieValue = document.getElementById('choice-die-value');

        dieElement?.classList.add('rolling');

        // Animate random values
        const animationDuration = 1500;
        const intervalTime = 50;
        let elapsed = 0;

        const animInterval = setInterval(() => {
            const randomValue = Math.floor(Math.random() * 20) + 1;
            if (dieValue) dieValue.textContent = randomValue;
            elapsed += intervalTime;

            if (elapsed >= animationDuration) {
                clearInterval(animInterval);
            }
        }, intervalTime);

        // Wait for animation, then make the actual choice
        await new Promise(resolve => setTimeout(resolve, animationDuration));

        // Make the API call to perform the skill check
        await this.makeChoice(choice.id);
    }

    async makeChoice(choiceId, playerId = null) {
        try {
            // Use stored sessionId first, then try state as fallback
            const sessionId = this.sessionId || state.get('session.id');
            console.log('[ChoiceDisplay] makeChoice - using sessionId:', sessionId,
                '(from this.sessionId:', this.sessionId, ', state:', state.get('session.id'), ')');

            if (!sessionId) {
                console.error('[ChoiceDisplay] No session ID available');
                return;
            }

            // Call the campaign advance API with the choice and optional player_id
            const data = { choice_id: choiceId };
            if (playerId) {
                data.player_id = playerId;
            }

            const result = await apiClient.advanceSession(sessionId, 'make_choice', data);

            // Choice result is in result.extra from the API
            const choiceResult = result.extra || result.choice_result;
            console.log('[ChoiceDisplay] makeChoice result:', result);
            console.log('[ChoiceDisplay] choiceResult:', choiceResult);

            if (choiceResult && choiceResult.skill_check) {
                // Skill check was performed - show the result
                console.log('[ChoiceDisplay] Showing skill check result');
                this.showResult(choiceResult);
                return; // IMPORTANT: Don't continue yet - wait for user to click Continue
            } else if (choiceResult && choiceResult.next_encounter) {
                // No skill check, direct transition - hide and emit state change
                this.hide();
                if (result.state) {
                    eventBus.emit(EVENTS.CAMPAIGN_STATE_CHANGED, result.state);
                }
            } else if (result.state) {
                // Fallback: campaign state advanced
                state.update('campaign.phase', result.state.phase);
                this.hide();
                eventBus.emit(EVENTS.CAMPAIGN_STATE_CHANGED, result.state);
            }
        } catch (error) {
            console.error('[ChoiceDisplay] Error making choice:', error);
            this.isRolling = false;
        }
    }

    showResult(result) {
        const diceContainer = document.getElementById('dice-container');
        const dieElement = document.querySelector('.choice-die');
        const dieValue = document.getElementById('choice-die-value');
        const rollDetails = document.getElementById('roll-details');
        const resultMessage = document.getElementById('result-message');

        // Stop rolling animation
        dieElement?.classList.remove('rolling');
        this.isRolling = false;

        if (result.skill_check) {
            const check = result.skill_check;

            // Check if this is a group check
            if (check.check_type === 'group' && check.individual_results) {
                this.showGroupResult(result);
                return;
            }

            // Show final die value for individual check
            if (dieValue) dieValue.textContent = check.roll;

            // Color the die based on result
            dieElement?.classList.remove('success', 'failure', 'critical-success', 'critical-failure');
            if (check.critical_success) {
                dieElement?.classList.add('critical-success');
            } else if (check.critical_failure) {
                dieElement?.classList.add('critical-failure');
            } else if (check.success) {
                dieElement?.classList.add('success');
            } else {
                dieElement?.classList.add('failure');
            }

            // Show roll breakdown
            const skillName = check.skill.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            if (rollDetails) {
                rollDetails.innerHTML = `
                    <div class="roll-breakdown">
                        <span class="character-name">${check.character_name}</span>
                        <span class="skill-label">${skillName} Check</span>
                    </div>
                    <div class="roll-math">
                        <span class="roll-value">${check.roll}</span>
                        <span class="modifier">${check.modifier >= 0 ? '+' : ''}${check.modifier}</span>
                        <span class="equals">=</span>
                        <span class="total ${check.success ? 'success' : 'failure'}">${check.total}</span>
                        <span class="vs">vs DC ${check.dc}</span>
                    </div>
                `;
            }

            // Show result message
            if (resultMessage) {
                const statusClass = check.success ? 'success' : 'failure';
                const statusText = check.critical_success ? 'Critical Success!' :
                    check.critical_failure ? 'Critical Failure!' :
                        check.success ? 'Success!' : 'Failed!';

                resultMessage.innerHTML = `
                    <div class="result-status ${statusClass}">${statusText}</div>
                    <div class="result-text">${result.outcome_text || ''}</div>
                `;
            }
        }
    }

    showGroupResult(result) {
        const diceContainer = document.getElementById('dice-container');
        const rollDetails = document.getElementById('roll-details');
        const resultMessage = document.getElementById('result-message');

        const check = result.skill_check;
        const skillName = check.skill.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

        // Replace single die with multiple dice for group check
        if (diceContainer) {
            diceContainer.innerHTML = check.individual_results.map(r => `
                <div class="group-roll ${r.success ? 'success' : 'failure'}">
                    <div class="mini-die ${r.critical_success ? 'critical-success' : r.critical_failure ? 'critical-failure' : ''}">${r.roll}</div>
                    <div class="group-roll-name">${r.character_name}</div>
                    <div class="group-roll-total">${r.total} ${r.success ? '✓' : '✗'}</div>
                </div>
            `).join('');
        }

        // Show group summary
        if (rollDetails) {
            rollDetails.innerHTML = `
                <div class="group-summary">
                    <span class="skill-label">${skillName} Group Check (DC ${check.dc})</span>
                    <div class="group-tally">
                        <span class="successes">${check.successes} Succeeded</span>
                        <span class="divider">|</span>
                        <span class="failures">${check.failures} Failed</span>
                        <span class="divider">|</span>
                        <span class="needed">Need ${check.needed_successes}</span>
                    </div>
                </div>
            `;
        }

        // Show result message
        if (resultMessage) {
            const statusClass = check.success ? 'success' : 'failure';
            const statusText = check.success ? 'Group Success!' : 'Group Failed!';

            resultMessage.innerHTML = `
                <div class="result-status ${statusClass}">${statusText}</div>
                <div class="result-text">${result.outcome_text || ''}</div>
            `;
        }
    }

    async handleContinue() {
        try {
            // Use stored sessionId first, then try state as fallback
            const sessionId = this.sessionId || state.get('session.id');
            console.log('[ChoiceDisplay] handleContinue - using sessionId:', sessionId);
            if (!sessionId) return;

            // Continue the campaign after seeing the result
            const result = await apiClient.advanceSession(sessionId, 'continue', {});

            this.hide();

            if (result.state) {
                state.update('campaign', result.state);
                eventBus.emit(EVENTS.CAMPAIGN_STATE_CHANGED, result.state);
            }
        } catch (error) {
            console.error('[ChoiceDisplay] Error continuing:', error);
        }
    }

    isShowing() {
        return this.isVisible;
    }
}

// Add CSS for choice display
const choiceCSS = `
/* =============================================================================
   Choice Display Styles - D&D Decision Making UI
   ============================================================================= */

.choice-display {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 900;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    animation: choiceFadeIn 0.4s ease forwards;
}

@keyframes choiceFadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.choice-display.hidden {
    display: none;
}

.choice-backdrop {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: linear-gradient(180deg, rgba(15, 10, 25, 0.95) 0%, rgba(20, 25, 40, 0.97) 100%);
}

.choice-content {
    position: relative;
    width: 90%;
    max-width: 700px;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    padding: var(--spacing-lg);
    background: linear-gradient(180deg, rgba(25, 20, 40, 0.98) 0%, rgba(20, 25, 45, 0.98) 100%);
    border: 2px solid var(--accent-gold);
    border-radius: 8px;
    box-shadow: 0 0 40px rgba(212, 175, 55, 0.25);
    animation: choiceSlideIn 0.5s ease forwards;
}

@keyframes choiceSlideIn {
    from {
        opacity: 0;
        transform: translateY(30px) scale(0.95);
    }
    to {
        opacity: 1;
        transform: translateY(0) scale(1);
    }
}

.choice-header {
    text-align: center;
    padding-bottom: var(--spacing-md);
    border-bottom: 1px solid rgba(212, 175, 55, 0.3);
    margin-bottom: var(--spacing-lg);
}

.choice-title {
    margin: 0;
    font-family: 'Cinzel', 'Times New Roman', serif;
    font-size: 1.8rem;
    font-weight: 600;
    color: var(--accent-gold);
    text-shadow: 0 0 15px rgba(212, 175, 55, 0.5);
    letter-spacing: 0.05em;
}

.choice-options {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
}

.choice-option {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    padding: var(--spacing-md) var(--spacing-lg);
    background: linear-gradient(135deg, rgba(40, 35, 60, 0.8) 0%, rgba(30, 35, 55, 0.8) 100%);
    border: 1px solid rgba(212, 175, 55, 0.3);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.3s ease;
    text-align: left;
}

.choice-option:hover {
    background: linear-gradient(135deg, rgba(50, 45, 75, 0.9) 0%, rgba(40, 45, 70, 0.9) 100%);
    border-color: var(--accent-gold);
    transform: translateX(5px);
    box-shadow: 0 0 20px rgba(212, 175, 55, 0.2);
}

.choice-option.selected {
    background: linear-gradient(135deg, rgba(60, 55, 90, 0.95) 0%, rgba(50, 55, 85, 0.95) 100%);
    border-color: var(--accent-gold);
}

.choice-option:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.choice-number {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    background: rgba(212, 175, 55, 0.2);
    border: 1px solid var(--accent-gold);
    border-radius: 50%;
    font-family: 'Cinzel', serif;
    font-weight: 600;
    color: var(--accent-gold);
    flex-shrink: 0;
}

.choice-text-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.choice-text {
    font-family: 'Georgia', serif;
    font-size: 1.1rem;
    color: #e8e4dc;
}

.choice-description {
    font-size: 0.85rem;
    color: rgba(232, 228, 220, 0.6);
    font-style: italic;
}

/* Skill Check Badge */
.skill-check-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 20px;
    font-size: 0.85rem;
    flex-shrink: 0;
}

.skill-check-badge.easy {
    border: 1px solid #4CAF50;
    color: #4CAF50;
}

.skill-check-badge.medium {
    border: 1px solid #FFC107;
    color: #FFC107;
}

.skill-check-badge.hard {
    border: 1px solid #FF9800;
    color: #FF9800;
}

.skill-check-badge.very-hard {
    border: 1px solid #F44336;
    color: #F44336;
}

.skill-icon {
    font-size: 1rem;
}

.skill-name {
    font-weight: 500;
}

.skill-difficulty {
    opacity: 0.8;
    font-size: 0.75rem;
}

/* Choice Result Panel */
.choice-result {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-lg);
    padding: var(--spacing-lg);
}

.dice-roll-display {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-md);
}

.choice-die {
    width: 80px;
    height: 80px;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 3px solid var(--accent-gold);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Cinzel', serif;
    font-size: 2rem;
    font-weight: 700;
    color: #fff;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}

.choice-die.rolling {
    animation: diceRoll 0.1s infinite;
}

@keyframes diceRoll {
    0%, 100% { transform: rotate(-5deg) scale(1); }
    25% { transform: rotate(5deg) scale(1.05); }
    50% { transform: rotate(-3deg) scale(1); }
    75% { transform: rotate(3deg) scale(1.02); }
}

.choice-die.success {
    border-color: #4CAF50;
    box-shadow: 0 0 30px rgba(76, 175, 80, 0.5);
}

.choice-die.failure {
    border-color: #F44336;
    box-shadow: 0 0 30px rgba(244, 67, 54, 0.5);
}

.choice-die.critical-success {
    border-color: #FFD700;
    box-shadow: 0 0 40px rgba(255, 215, 0, 0.7);
    animation: criticalGlow 1s ease-in-out infinite alternate;
}

.choice-die.critical-failure {
    border-color: #8B0000;
    box-shadow: 0 0 40px rgba(139, 0, 0, 0.7);
}

@keyframes criticalGlow {
    from { box-shadow: 0 0 30px rgba(255, 215, 0, 0.5); }
    to { box-shadow: 0 0 50px rgba(255, 215, 0, 0.9); }
}

.roll-details {
    text-align: center;
}

.roll-breakdown {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: var(--spacing-sm);
}

.character-name {
    font-family: 'Cinzel', serif;
    color: var(--accent-gold);
    font-weight: 600;
}

.skill-label {
    color: rgba(232, 228, 220, 0.8);
    font-size: 0.9rem;
}

.roll-math {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    font-family: 'Cinzel', serif;
    font-size: 1.2rem;
}

.roll-value {
    color: #fff;
}

.modifier {
    color: rgba(232, 228, 220, 0.7);
}

.equals {
    color: rgba(232, 228, 220, 0.5);
}

.total {
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
}

.total.success {
    color: #4CAF50;
    background: rgba(76, 175, 80, 0.2);
}

.total.failure {
    color: #F44336;
    background: rgba(244, 67, 54, 0.2);
}

.vs {
    color: rgba(232, 228, 220, 0.6);
    font-size: 0.9rem;
}

.result-message {
    text-align: center;
    margin-top: var(--spacing-md);
}

.result-status {
    font-family: 'Cinzel', serif;
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: var(--spacing-sm);
}

.result-status.success {
    color: #4CAF50;
    text-shadow: 0 0 15px rgba(76, 175, 80, 0.5);
}

.result-status.failure {
    color: #F44336;
    text-shadow: 0 0 15px rgba(244, 67, 54, 0.5);
}

.result-text {
    font-family: 'Georgia', serif;
    font-size: 1rem;
    color: #e8e4dc;
    max-width: 500px;
    line-height: 1.6;
}

.choice-continue-btn {
    padding: var(--spacing-md) var(--spacing-xl);
    min-width: 180px;
    background: linear-gradient(135deg, var(--accent-gold) 0%, #a08030 100%);
    border: 2px solid var(--accent-gold);
    border-radius: 4px;
    color: #1a1520;
    font-family: 'Cinzel', serif;
    font-size: 1rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    cursor: pointer;
    transition: all 0.3s ease;
    margin-top: var(--spacing-md);
}

.choice-continue-btn:hover {
    background: linear-gradient(135deg, #e5c04a 0%, #c9a030 100%);
    transform: translateY(-2px);
    box-shadow: 0 4px 15px rgba(212, 175, 55, 0.4);
}

/* Player Selection UI */
.player-selection {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-lg);
}

.player-selection-header {
    text-align: center;
}

.player-selection-title {
    font-family: 'Cinzel', serif;
    font-size: 1.4rem;
    color: var(--accent-gold);
    margin: 0 0 var(--spacing-sm) 0;
}

.player-selection-skill {
    color: rgba(232, 228, 220, 0.8);
    font-size: 1rem;
    margin: 0;
}

.player-options {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: var(--spacing-md);
}

.player-option {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: var(--spacing-md) var(--spacing-lg);
    min-width: 120px;
    background: linear-gradient(135deg, rgba(40, 35, 60, 0.8) 0%, rgba(30, 35, 55, 0.8) 100%);
    border: 2px solid rgba(212, 175, 55, 0.3);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.3s ease;
}

.player-option:hover {
    background: linear-gradient(135deg, rgba(50, 45, 75, 0.9) 0%, rgba(40, 45, 70, 0.9) 100%);
    border-color: var(--accent-gold);
    transform: translateY(-3px);
    box-shadow: 0 4px 20px rgba(212, 175, 55, 0.3);
}

.player-name {
    font-family: 'Cinzel', serif;
    font-size: 1.1rem;
    color: #e8e4dc;
}

.player-modifier {
    font-family: 'Cinzel', serif;
    font-size: 1.3rem;
    font-weight: 700;
}

.player-modifier.positive {
    color: #4CAF50;
}

.player-modifier.negative {
    color: #F44336;
}

/* Click to Roll UI */
.click-to-roll {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-lg);
    padding: var(--spacing-xl);
}

.click-to-roll-info {
    text-align: center;
}

.roller-name {
    font-family: 'Cinzel', serif;
    font-size: 1.4rem;
    color: var(--accent-gold);
    margin: 0 0 var(--spacing-sm) 0;
}

.skill-info {
    color: rgba(232, 228, 220, 0.8);
    font-size: 1rem;
    margin: 0;
}

.roll-button {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-lg) var(--spacing-xl);
    min-width: 200px;
    background: linear-gradient(135deg, rgba(60, 50, 100, 0.9) 0%, rgba(40, 50, 90, 0.9) 100%);
    border: 3px solid var(--accent-gold);
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.3s ease;
    animation: rollButtonPulse 2s ease-in-out infinite;
}

@keyframes rollButtonPulse {
    0%, 100% { box-shadow: 0 0 20px rgba(212, 175, 55, 0.3); }
    50% { box-shadow: 0 0 40px rgba(212, 175, 55, 0.6); }
}

.roll-button:hover {
    background: linear-gradient(135deg, rgba(80, 70, 130, 0.95) 0%, rgba(60, 70, 120, 0.95) 100%);
    transform: scale(1.05);
    animation: none;
    box-shadow: 0 0 50px rgba(212, 175, 55, 0.7);
}

.roll-icon {
    font-size: 2rem;
}

.roll-text {
    font-family: 'Cinzel', serif;
    font-size: 1.3rem;
    font-weight: 600;
    color: var(--accent-gold);
    letter-spacing: 0.05em;
}

/* Group Check Result Display */
.group-roll {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: var(--spacing-sm);
    min-width: 80px;
}

.group-roll.success .mini-die {
    border-color: #4CAF50;
    box-shadow: 0 0 15px rgba(76, 175, 80, 0.5);
}

.group-roll.failure .mini-die {
    border-color: #F44336;
    box-shadow: 0 0 15px rgba(244, 67, 54, 0.5);
}

.mini-die {
    width: 50px;
    height: 50px;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 2px solid var(--accent-gold);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Cinzel', serif;
    font-size: 1.3rem;
    font-weight: 700;
    color: #fff;
}

.mini-die.critical-success {
    border-color: #FFD700;
    box-shadow: 0 0 20px rgba(255, 215, 0, 0.7);
}

.mini-die.critical-failure {
    border-color: #8B0000;
    box-shadow: 0 0 20px rgba(139, 0, 0, 0.7);
}

.group-roll-name {
    font-size: 0.75rem;
    color: rgba(232, 228, 220, 0.8);
    max-width: 80px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.group-roll-total {
    font-family: 'Cinzel', serif;
    font-size: 0.9rem;
    font-weight: 600;
}

.group-roll.success .group-roll-total {
    color: #4CAF50;
}

.group-roll.failure .group-roll-total {
    color: #F44336;
}

#dice-container {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: var(--spacing-md);
}

.group-summary {
    text-align: center;
}

.group-tally {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-md);
    margin-top: var(--spacing-sm);
    font-family: 'Cinzel', serif;
}

.group-tally .successes {
    color: #4CAF50;
}

.group-tally .failures {
    color: #F44336;
}

.group-tally .needed {
    color: var(--accent-gold);
}

.group-tally .divider {
    color: rgba(232, 228, 220, 0.3);
}
`;

// Inject CSS
const styleSheet = document.createElement('style');
styleSheet.textContent = choiceCSS;
document.head.appendChild(styleSheet);

// Export singleton
export const choiceDisplay = new ChoiceDisplay();
export default choiceDisplay;
