/**
 * D&D Combat Engine - Dice Roller
 * Animated dice rolling with visual feedback
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';

class DiceRoller {
    constructor() {
        this.container = null;
        this.isRolling = false;
        this.isWaitingForClick = false;
        this.clickResolver = null;
        this.pendingRollData = null;
        this.init();
    }

    /**
     * Initialize the dice roller UI
     */
    init() {
        this.container = document.getElementById('dice-roller');
        if (!this.container) {
            console.warn('[DiceRoller] Container not found');
            return;
        }

        // Subscribe to attack events
        eventBus.on(EVENTS.ATTACK_RESOLVED, this.handleAttackResult.bind(this));

        // Add click handler for click-to-roll
        this.container.addEventListener('click', this.handleContainerClick.bind(this));
    }

    /**
     * Handle click on dice container (for click-to-roll)
     */
    handleContainerClick(event) {
        if (this.isWaitingForClick && this.clickResolver) {
            this.isWaitingForClick = false;
            // Remove waiting class
            this.container.classList.remove('waiting-for-roll');
            const prompt = this.container.querySelector('.roll-prompt');
            if (prompt) prompt.remove();
            // Resolve the click promise
            this.clickResolver();
            this.clickResolver = null;
        }
    }

    /**
     * Show the dice and wait for player click
     * @returns {Promise} Resolves when player clicks
     */
    async waitForPlayerClick() {
        return new Promise(resolve => {
            this.isWaitingForClick = true;
            this.clickResolver = resolve;

            // Add waiting state
            this.container.classList.add('waiting-for-roll');

            // Add click prompt if not exists
            if (!this.container.querySelector('.roll-prompt')) {
                const prompt = document.createElement('div');
                prompt.className = 'roll-prompt';
                prompt.innerHTML = '<span class="roll-prompt-text">Click to Roll!</span>';
                this.container.appendChild(prompt);
            }
        });
    }

    /**
     * Show an animated d20 roll
     * @param {Object} options - Roll options
     * @param {number} options.finalValue - The final d20 value
     * @param {number} options.modifier - Attack modifier
     * @param {number} options.total - Total attack roll
     * @param {number} options.targetAC - Target's AC
     * @param {boolean} options.hit - Whether the attack hit
     * @param {boolean} options.critical - Whether it was a critical hit
     * @param {boolean} options.criticalMiss - Whether it was a critical miss
     * @param {boolean} options.advantage - Rolling with advantage
     * @param {boolean} options.disadvantage - Rolling with disadvantage
     * @param {number} options.secondRoll - Second die value (for adv/disadv)
     * @returns {Promise} Resolves when animation completes
     */
    async showAttackRoll(options) {
        if (this.isRolling) return;
        this.isRolling = true;

        const {
            finalValue,
            modifier,
            total,
            targetAC,
            hit,
            critical,
            criticalMiss,
            advantage,
            disadvantage,
            secondRoll
        } = options;

        // Show the container
        this.container.classList.remove('hidden');
        this.container.classList.add('active');

        // Get DOM elements
        const dieElement = this.container.querySelector('.die-face');
        const rollBreakdown = this.container.querySelector('.roll-breakdown');
        const rollResult = this.container.querySelector('.roll-result');
        const secondDieContainer = this.container.querySelector('.second-die-container');
        const secondDieElement = this.container.querySelector('.second-die-face');

        // Reset
        this.container.classList.remove('hit', 'miss', 'critical', 'critical-miss');
        if (secondDieContainer) secondDieContainer.classList.add('hidden');

        // Animate the die tumbling
        await this.animateDieTumble(dieElement, finalValue);

        // Show second die if advantage/disadvantage
        if ((advantage || disadvantage) && secondRoll !== undefined && secondDieContainer && secondDieElement) {
            secondDieContainer.classList.remove('hidden');
            secondDieElement.textContent = secondRoll;

            if (advantage) {
                // Highlight the higher die
                if (finalValue >= secondRoll) {
                    dieElement.classList.add('used');
                    secondDieElement.classList.add('unused');
                } else {
                    dieElement.classList.add('unused');
                    secondDieElement.classList.add('used');
                }
            } else if (disadvantage) {
                // Highlight the lower die
                if (finalValue <= secondRoll) {
                    dieElement.classList.add('used');
                    secondDieElement.classList.add('unused');
                } else {
                    dieElement.classList.add('unused');
                    secondDieElement.classList.add('used');
                }
            }
        }

        // Build breakdown text
        const modifierStr = modifier >= 0 ? `+${modifier}` : `${modifier}`;
        let breakdownHTML = `
            <span class="roll-dice">[d20: ${finalValue}]</span>
            <span class="roll-modifier">${modifierStr}</span>
            <span class="roll-equals">=</span>
            <span class="roll-total">${total}</span>
            <span class="roll-vs">vs AC</span>
            <span class="roll-ac">${targetAC}</span>
        `;

        if (advantage) {
            breakdownHTML = `<span class="roll-advantage">(Advantage)</span> ` + breakdownHTML;
        } else if (disadvantage) {
            breakdownHTML = `<span class="roll-disadvantage">(Disadvantage)</span> ` + breakdownHTML;
        }

        rollBreakdown.innerHTML = breakdownHTML;

        // Show result
        let resultText = '';
        let resultClass = '';

        if (critical) {
            resultText = 'CRITICAL HIT!';
            resultClass = 'critical';
            this.container.classList.add('critical');
            this.playCriticalEffect();
        } else if (criticalMiss) {
            resultText = 'CRITICAL MISS!';
            resultClass = 'critical-miss';
            this.container.classList.add('critical-miss');
        } else if (hit) {
            resultText = 'HIT!';
            resultClass = 'hit';
            this.container.classList.add('hit');
        } else {
            resultText = 'MISS';
            resultClass = 'miss';
            this.container.classList.add('miss');
        }

        rollResult.textContent = resultText;
        rollResult.className = `roll-result ${resultClass}`;

        // Show the breakdown with animation
        rollBreakdown.classList.add('visible');
        rollResult.classList.add('visible');

        this.isRolling = false;

        // Return a promise that resolves after showing the result
        return new Promise(resolve => {
            setTimeout(resolve, 500);
        });
    }

    /**
     * Animate the die tumbling through random values
     * @param {HTMLElement} dieElement - The die face element
     * @param {number} finalValue - The final value to land on
     */
    async animateDieTumble(dieElement, finalValue) {
        const tumbleDuration = 1000; // Total animation time
        const frameInterval = 50; // Time between each "frame"
        const numFrames = tumbleDuration / frameInterval;

        // Get the parent die element for 3D tumbling
        const dieContainer = dieElement.closest('.die.d20');

        dieElement.classList.add('tumbling');
        if (dieContainer) {
            dieContainer.classList.add('tumbling');
        }

        return new Promise(resolve => {
            let frame = 0;
            const tumbleInterval = setInterval(() => {
                frame++;

                // Generate random value for tumble effect
                if (frame < numFrames) {
                    const randomValue = Math.floor(Math.random() * 20) + 1;
                    dieElement.textContent = randomValue;
                } else {
                    // Final frame - show actual value
                    clearInterval(tumbleInterval);
                    dieElement.textContent = finalValue;
                    dieElement.classList.remove('tumbling');
                    if (dieContainer) {
                        dieContainer.classList.remove('tumbling');
                    }

                    // Add landing effect
                    dieElement.classList.add('landed');
                    setTimeout(() => {
                        dieElement.classList.remove('landed');
                    }, 200);

                    resolve();
                }
            }, frameInterval);
        });
    }

    /**
     * Play critical hit effect
     */
    playCriticalEffect() {
        // Screen shake effect
        document.body.classList.add('screen-shake');
        setTimeout(() => {
            document.body.classList.remove('screen-shake');
        }, 300);

        // Golden particles could be added here
        this.spawnParticles('gold');
    }

    /**
     * Spawn particle effects
     * @param {string} color - Particle color
     */
    spawnParticles(color) {
        const particleContainer = document.createElement('div');
        particleContainer.className = 'dice-particles';

        for (let i = 0; i < 12; i++) {
            const particle = document.createElement('div');
            particle.className = `particle ${color}`;
            particle.style.setProperty('--angle', `${i * 30}deg`);
            particle.style.setProperty('--delay', `${i * 30}ms`);
            particleContainer.appendChild(particle);
        }

        this.container.appendChild(particleContainer);

        setTimeout(() => {
            particleContainer.remove();
        }, 1000);
    }

    /**
     * Show animated damage dice roll
     * @param {Object} options - Damage options
     * @param {string} options.formula - Damage formula (e.g., "1d8+3" or "2d6+2")
     * @param {Array} options.rolls - Individual die results [5] or [3, 4]
     * @param {number} options.modifier - Damage modifier (+3 from STR)
     * @param {number} options.total - Total damage
     * @param {string} options.damageType - Type of damage ("slashing")
     * @param {boolean} options.critical - Whether it was a critical hit
     */
    async showDamageRoll(options) {
        const {
            formula = "1d6",
            rolls = [],
            modifier = 0,
            total,
            damageType = "damage",
            critical = false
        } = options;

        const diceContainer = this.container.querySelector('.damage-dice-container');
        const diceRow = this.container.querySelector('.damage-dice-row');
        const damageDisplay = this.container.querySelector('.damage-display');

        if (!damageDisplay) return;

        // Parse formula to get die type (d6, d8, etc.)
        const dieMatch = formula.match(/(\d+)d(\d+)/);
        let dieCount = dieMatch ? parseInt(dieMatch[1]) : 1;
        const dieType = dieMatch ? parseInt(dieMatch[2]) : 6;

        // Double dice for critical hits
        if (critical) {
            dieCount *= 2;
        }

        // Show animated dice if container exists
        if (diceContainer && diceRow) {
            // Clear and show container
            diceRow.innerHTML = '';
            diceContainer.classList.remove('hidden');

            // Create dice elements
            const diceElements = [];
            for (let i = 0; i < dieCount; i++) {
                const die = document.createElement('div');
                die.className = `die damage-die d${dieType}`;
                die.innerHTML = `<span class="die-face">${dieType}</span>`;
                diceRow.appendChild(die);
                diceElements.push(die);
            }

            // Animate each die
            for (let i = 0; i < diceElements.length; i++) {
                const die = diceElements[i];
                const face = die.querySelector('.die-face');
                const finalValue = rolls[i] || Math.floor(Math.random() * dieType) + 1;
                await this.animateDamageDie(face, finalValue, dieType);
            }
        }

        // Show damage breakdown
        damageDisplay.classList.remove('hidden');

        const rollsStr = rolls.length > 0 ? rolls.join(' + ') : '?';
        const modStr = modifier > 0 ? ` + ${modifier}` : modifier < 0 ? ` - ${Math.abs(modifier)}` : '';

        const damageHTML = `
            <span class="damage-formula">[${rollsStr}]${modStr}</span>
            <span class="damage-equals">=</span>
            <span class="damage-total ${critical ? 'critical' : ''}">${total}</span>
            <span class="damage-type">${damageType}</span>
        `;

        damageDisplay.innerHTML = damageHTML;
        damageDisplay.classList.add('visible');
    }

    /**
     * Animate a single damage die
     * @param {HTMLElement} faceElement - The die face element
     * @param {number} finalValue - The final value to land on
     * @param {number} maxValue - Maximum value for this die type
     */
    async animateDamageDie(faceElement, finalValue, maxValue) {
        const tumbleDuration = 600;
        const frameInterval = 50;
        const numFrames = tumbleDuration / frameInterval;

        const dieContainer = faceElement.closest('.die');
        if (dieContainer) {
            dieContainer.classList.add('tumbling');
        }

        return new Promise(resolve => {
            let frame = 0;
            const interval = setInterval(() => {
                frame++;
                if (frame < numFrames) {
                    faceElement.textContent = Math.floor(Math.random() * maxValue) + 1;
                } else {
                    clearInterval(interval);
                    faceElement.textContent = finalValue;
                    if (dieContainer) {
                        dieContainer.classList.remove('tumbling');
                        dieContainer.classList.add('landed');
                        setTimeout(() => dieContainer.classList.remove('landed'), 200);
                    }
                    resolve();
                }
            }, frameInterval);
        });
    }

    /**
     * Show enemy attack dice sequence (with enemy styling)
     * @param {string} enemyName - Name of attacking enemy
     * @param {Object} attackData - Attack data from EnemyAction
     */
    async showEnemyAttackSequence(enemyName, attackData) {
        const {
            attack_roll = 10,
            natural_roll = null,
            attack_modifier = 0,
            target_ac = 10,
            hit = false,
            critical = false,
            critical_miss = false,
            damage_dealt = 0,
            damage_formula = "1d6",
            damage_rolls = [],
            damage_modifier = 0,
            damage_type = "damage",
            advantage = false,
            disadvantage = false,
            second_roll = null
        } = attackData;

        // Add enemy styling
        this.container.classList.add('enemy-roll');

        // Calculate natural roll if not provided
        const finalValue = natural_roll ?? Math.max(1, Math.min(20, attack_roll - attack_modifier));

        // Show attack roll
        await this.showAttackRoll({
            finalValue,
            modifier: attack_modifier,
            total: attack_roll,
            targetAC: target_ac,
            hit,
            critical,
            criticalMiss: critical_miss,
            advantage,
            disadvantage,
            secondRoll: second_roll
        });

        // Show damage if hit
        if (hit && damage_dealt > 0) {
            await new Promise(r => setTimeout(r, 400));
            await this.showDamageRoll({
                formula: damage_formula,
                rolls: damage_rolls || [damage_dealt],
                modifier: damage_modifier,
                total: damage_dealt,
                damageType: damage_type,
                critical
            });
        }

        // Keep visible longer for enemy turns
        return new Promise(resolve => {
            setTimeout(() => {
                this.container.classList.remove('enemy-roll');
                this.hide();
                resolve();
            }, 2500);
        });
    }

    /**
     * Hide the dice roller
     */
    hide() {
        if (!this.container) return;

        this.container.classList.remove('active', 'enemy-roll');
        this.container.classList.add('hiding');

        setTimeout(() => {
            this.container.classList.add('hidden');
            this.container.classList.remove('hiding', 'hit', 'miss', 'critical', 'critical-miss');

            // Reset inner elements
            const rollBreakdown = this.container.querySelector('.roll-breakdown');
            const rollResult = this.container.querySelector('.roll-result');
            const damageDisplay = this.container.querySelector('.damage-display');
            const secondDieContainer = this.container.querySelector('.second-die-container');
            const damageDiceContainer = this.container.querySelector('.damage-dice-container');
            const damageDiceRow = this.container.querySelector('.damage-dice-row');

            if (rollBreakdown) rollBreakdown.classList.remove('visible');
            if (rollResult) rollResult.classList.remove('visible');
            if (damageDisplay) {
                damageDisplay.classList.remove('visible');
                damageDisplay.classList.add('hidden');
            }
            if (secondDieContainer) secondDieContainer.classList.add('hidden');

            // Reset damage dice container
            if (damageDiceContainer) damageDiceContainer.classList.add('hidden');
            if (damageDiceRow) damageDiceRow.innerHTML = '';

            // Reset die classes
            const dieElement = this.container.querySelector('.die-face');
            const secondDieElement = this.container.querySelector('.second-die-face');
            if (dieElement) dieElement.classList.remove('used', 'unused');
            if (secondDieElement) secondDieElement.classList.remove('used', 'unused');
        }, 300);
    }

    /**
     * Handle attack result event
     */
    handleAttackResult(result) {
        // This can be used to automatically trigger dice display on attacks
        // Currently integrated directly in action-bar.js
    }

    /**
     * Full attack roll sequence with click-to-roll option
     * @param {Object} attackData - Attack data from API
     * @param {Object} options - Display options
     * @param {boolean} options.clickToRoll - Wait for player click before rolling (default: true for player)
     */
    async playAttackSequence(attackData, options = {}) {
        const { clickToRoll = true } = options;

        // Defensive extraction with defaults
        const attack_roll = attackData.attack_roll ?? 10;
        const natural_roll = attackData.natural_roll ?? null;
        const modifier = attackData.modifier ?? 0;
        const target_ac = attackData.target_ac ?? 10;
        const hit = attackData.hit ?? false;
        const critical = attackData.critical ?? false;
        const damage = attackData.damage ?? attackData.damage_dealt ?? 0;
        const damage_type = attackData.damage_type ?? 'damage';
        const damage_formula = attackData.damage_formula ?? `${damage}`;
        const advantage = attackData.advantage ?? false;
        const disadvantage = attackData.disadvantage ?? false;
        const second_roll = attackData.second_roll ?? null;

        // Extract damage roll breakdown from backend response (new feature)
        const damage_roll = attackData.damage_roll ?? attackData.extra_data?.damage_roll ?? null;
        const damage_rolls = damage_roll?.rolls ?? [];
        const damage_modifier = damage_roll?.modifier ?? 0;

        // Calculate natural roll if not provided
        const calculatedNatural = natural_roll ?? (attack_roll - modifier);
        const finalValue = Math.max(1, Math.min(20, calculatedNatural));

        console.log('[DiceRoller] Playing attack sequence:', {
            attack_roll, natural_roll, modifier, target_ac, hit, critical, damage, clickToRoll,
            damage_roll: damage_roll  // Log full damage breakdown
        });

        // Show container first
        this.container.classList.remove('hidden');
        this.container.classList.add('active');

        // Reset die to show "?" initially for click-to-roll
        const dieElement = this.container.querySelector('.die-face');
        if (clickToRoll && dieElement) {
            dieElement.textContent = '?';
        }

        // Wait for player click if enabled
        if (clickToRoll) {
            await this.waitForPlayerClick();
        }

        // Show attack roll
        await this.showAttackRoll({
            finalValue: finalValue,
            modifier: modifier,
            total: attack_roll,
            targetAC: target_ac,
            hit: hit,
            critical: critical,
            criticalMiss: finalValue === 1,
            advantage: advantage,
            disadvantage: disadvantage,
            secondRoll: second_roll
        });

        // Wait for player click before damage roll if hit
        if (hit && damage > 0) {
            if (clickToRoll) {
                // Brief pause then wait for another click for damage
                await new Promise(resolve => setTimeout(resolve, 500));
                await this.waitForPlayerClick();
            } else {
                await new Promise(resolve => setTimeout(resolve, 300));
            }
            await this.showDamageRoll({
                formula: damage_roll?.dice_notation || damage_formula,
                rolls: damage_rolls,
                modifier: damage_modifier,
                total: damage,
                damageType: damage_type,
                critical: critical
            });
        }

        // Auto-hide after delay
        return new Promise(resolve => {
            setTimeout(() => {
                this.hide();
                resolve();
            }, 2000);
        });
    }

    /**
     * Play saving throw sequence for spells that require enemy saves (like Sacred Flame)
     * @param {Object} saveData - Saving throw data from API
     * @param {number} saveData.save_roll - The raw d20 roll
     * @param {number} saveData.save_total - Total including modifiers
     * @param {number} saveData.save_dc - Spell save DC to beat
     * @param {boolean} saveData.saved - Whether the save succeeded
     * @param {string} saveData.save_type - Type of save (DEX, WIS, etc.)
     * @param {number} saveData.damage - Damage dealt if save failed
     * @param {string} saveData.damage_type - Type of damage
     * @param {string} saveData.spell_name - Name of the spell
     * @param {string} saveData.damage_dice - Damage dice formula (e.g., "1d8")
     * @param {Array} saveData.damage_rolls - Individual die roll results
     */
    async playSavingThrowSequence(saveData) {
        const {
            save_roll = 10,
            save_total = 10,
            save_dc = 10,
            saved = false,
            save_type = 'DEX',
            damage = 0,
            damage_type = 'damage',
            spell_name = 'Spell',
            damage_dice = '1d8',
            damage_rolls = []
        } = saveData;

        console.log('[DiceRoller] Playing saving throw sequence:', saveData);

        // Show container
        this.container.classList.remove('hidden');
        this.container.classList.add('active');

        // Get DOM elements
        const dieElement = this.container.querySelector('.die-face');
        const rollBreakdown = this.container.querySelector('.roll-breakdown');
        const rollResult = this.container.querySelector('.roll-result');

        // Reset classes
        this.container.classList.remove('hit', 'miss', 'critical', 'critical-miss');

        // Animate the die tumbling to show enemy's roll
        await this.animateDieTumble(dieElement, save_roll);

        // Build breakdown text - show enemy's save vs DC
        const saveTypeUpper = save_type.toUpperCase();
        const modifierStr = save_total - save_roll >= 0 ? `+${save_total - save_roll}` : `${save_total - save_roll}`;
        const breakdownHTML = `
            <span class="roll-label">${saveTypeUpper} Save:</span>
            <span class="roll-dice">[d20: ${save_roll}]</span>
            <span class="roll-modifier">${modifierStr}</span>
            <span class="roll-equals">=</span>
            <span class="roll-total">${save_total}</span>
            <span class="roll-vs">vs DC</span>
            <span class="roll-ac">${save_dc}</span>
        `;

        rollBreakdown.innerHTML = breakdownHTML;

        // Show result based on whether they saved
        let resultText = '';
        let resultClass = '';

        if (saved) {
            resultText = 'SAVED!';
            resultClass = 'miss';  // Use miss styling for saved (spell "missed")
            this.container.classList.add('miss');
        } else {
            resultText = 'FAILED!';  // Show just FAILED, damage will be shown in dice animation
            resultClass = 'hit';  // Use hit styling for failed save (spell "hit")
            this.container.classList.add('hit');
        }

        rollResult.textContent = resultText;
        rollResult.className = `roll-result ${resultClass}`;

        // Show the breakdown with animation
        rollBreakdown.classList.add('visible');
        rollResult.classList.add('visible');

        // If save failed and there's damage, show the damage dice animation
        if (!saved && damage > 0) {
            await new Promise(r => setTimeout(r, 500)); // Brief pause before damage roll
            await this.showDamageRoll({
                formula: damage_dice,
                rolls: damage_rolls.length > 0 ? damage_rolls : [damage],
                modifier: 0,
                total: damage,
                damageType: damage_type,
                critical: false
            });
        }

        // Auto-hide after delay
        return new Promise(resolve => {
            setTimeout(() => {
                this.hide();
                resolve();
            }, 2500);  // Slightly longer delay for save results
        });
    }
}

// Export singleton instance
export const diceRoller = new DiceRoller();
export default diceRoller;
