/**
 * Item Tooltip Component
 *
 * Displays detailed item information on hover with:
 * - Name (color-coded by rarity)
 * - Item type
 * - Damage/AC values
 * - Properties (light, heavy, versatile, etc.)
 * - Weapon Mastery (2024 rules)
 * - Weight and value
 * - Description
 */

import { RARITY_COLORS, MASTERY_DESCRIPTIONS } from '../equipment/equipment-manager.js';

class ItemTooltip {
    constructor() {
        this.element = null;
        this.visible = false;
        this.currentItem = null;
        this.createTooltipElement();
    }

    /**
     * Create the tooltip DOM element.
     */
    createTooltipElement() {
        this.element = document.createElement('div');
        this.element.className = 'item-tooltip hidden';
        this.element.id = 'item-tooltip';
        document.body.appendChild(this.element);
    }

    /**
     * Show the tooltip for an item at a position.
     * @param {Object} item - Item data
     * @param {number} x - X position (mouse)
     * @param {number} y - Y position (mouse)
     */
    show(item, x, y) {
        if (!item) {
            this.hide();
            return;
        }

        this.currentItem = item;
        this.element.innerHTML = this.renderContent(item);
        this.positionTooltip(x, y);
        this.element.classList.remove('hidden');
        this.visible = true;
    }

    /**
     * Hide the tooltip.
     */
    hide() {
        this.element.classList.add('hidden');
        this.visible = false;
        this.currentItem = null;
    }

    /**
     * Position the tooltip near the cursor, keeping it in viewport.
     */
    positionTooltip(x, y) {
        const padding = 15;
        const tooltip = this.element;

        // Show temporarily to measure
        tooltip.style.visibility = 'hidden';
        tooltip.style.display = 'block';

        const rect = tooltip.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        // Default: position to the right and below cursor
        let left = x + padding;
        let top = y + padding;

        // If would overflow right, position to left of cursor
        if (left + rect.width > viewportWidth - padding) {
            left = x - rect.width - padding;
        }

        // If would overflow bottom, position above cursor
        if (top + rect.height > viewportHeight - padding) {
            top = y - rect.height - padding;
        }

        // Ensure not off left/top edge
        left = Math.max(padding, left);
        top = Math.max(padding, top);

        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${top}px`;
        tooltip.style.visibility = 'visible';
    }

    /**
     * Render the tooltip content HTML.
     */
    renderContent(item) {
        const rarity = item.rarity || 'common';
        const rarityColor = RARITY_COLORS[rarity] || RARITY_COLORS.common;
        const isWeapon = item.item_type === 'weapon' || item.damage;
        const isArmor = item.item_type === 'armor' || item.ac_bonus;

        let html = `
            <div class="tooltip-header">
                <span class="item-name" style="color: ${rarityColor}">${item.name || 'Unknown Item'}</span>
                <span class="item-type">${this.formatItemType(item)}</span>
            </div>
        `;

        // Weapon stats
        if (isWeapon) {
            html += this.renderWeaponStats(item);
        }

        // Armor stats
        if (isArmor) {
            html += this.renderArmorStats(item);
        }

        // Properties
        if (item.properties && item.properties.length > 0) {
            html += `
                <div class="tooltip-section">
                    <span class="section-label">Properties:</span>
                    <span class="property-list">${item.properties.join(', ')}</span>
                </div>
            `;
        }

        // Weapon Mastery (2024 rules)
        if (item.mastery) {
            const masteryDesc = MASTERY_DESCRIPTIONS[item.mastery.toLowerCase()] || '';
            html += `
                <div class="tooltip-section mastery-section">
                    <span class="section-label">Mastery:</span>
                    <span class="mastery-type">${this.formatMastery(item.mastery)}</span>
                    ${masteryDesc ? `<p class="mastery-desc">${masteryDesc}</p>` : ''}
                </div>
            `;
        }

        // Description
        if (item.description) {
            html += `
                <div class="tooltip-section description-section">
                    <p class="item-description">${item.description}</p>
                </div>
            `;
        }

        // Footer (weight, value, attunement)
        html += this.renderFooter(item);

        return html;
    }

    /**
     * Render weapon-specific stats.
     */
    renderWeaponStats(item) {
        let html = '<div class="tooltip-section stats-section">';

        if (item.damage) {
            const damageType = item.damage_type ? ` ${this.formatDamageType(item.damage_type)}` : '';
            html += `
                <div class="stat-row">
                    <span class="stat-icon">Damage:</span>
                    <span class="stat-value damage-value">${item.damage}${damageType}</span>
                </div>
            `;
        }

        // Versatile damage
        if (item.properties?.includes('versatile') && item.versatile_damage) {
            html += `
                <div class="stat-row">
                    <span class="stat-icon">Two-handed:</span>
                    <span class="stat-value">${item.versatile_damage}</span>
                </div>
            `;
        }

        // Range for ranged/thrown weapons
        if (item.range) {
            const longRange = item.long_range ? `/${item.long_range}` : '';
            html += `
                <div class="stat-row">
                    <span class="stat-icon">Range:</span>
                    <span class="stat-value">${item.range}${longRange} ft.</span>
                </div>
            `;
        }

        html += '</div>';
        return html;
    }

    /**
     * Render armor-specific stats.
     */
    renderArmorStats(item) {
        let html = '<div class="tooltip-section stats-section">';

        if (item.ac_bonus !== undefined && item.ac_bonus !== null) {
            let acText = item.ac_bonus.toString();

            // Show DEX bonus info
            if (item.max_dex_bonus !== undefined && item.max_dex_bonus !== null) {
                if (item.max_dex_bonus === 0) {
                    acText += ' (no DEX bonus)';
                } else {
                    acText += ` + DEX (max ${item.max_dex_bonus})`;
                }
            } else {
                acText += ' + DEX';
            }

            html += `
                <div class="stat-row">
                    <span class="stat-icon">AC:</span>
                    <span class="stat-value ac-value">${acText}</span>
                </div>
            `;
        }

        // Strength requirement with warning if player doesn't meet it
        if (item.strength_requirement) {
            // Try to get player's strength to show warning
            let strWarning = '';
            const playerStr = this.getPlayerStrength();
            if (playerStr !== null && playerStr < item.strength_requirement) {
                strWarning = ` <span class="str-warning">(Speed -10ft!)</span>`;
            }

            html += `
                <div class="stat-row">
                    <span class="stat-icon">Requires:</span>
                    <span class="stat-value">STR ${item.strength_requirement}${strWarning}</span>
                </div>
            `;
        }

        // Stealth disadvantage
        if (item.stealth_disadvantage) {
            html += `
                <div class="stat-row">
                    <span class="stat-icon stealth-penalty">Stealth:</span>
                    <span class="stat-value stealth-penalty">Disadvantage</span>
                </div>
            `;
        }

        // Don/Doff times (D&D 5e armor equipping rules)
        if (item.don_time || item.doff_time) {
            html += `<div class="armor-times">`;
            if (item.don_time) {
                html += `
                    <div class="stat-row">
                        <span class="stat-icon">Don:</span>
                        <span class="stat-value">${item.don_time}</span>
                    </div>
                `;
            }
            if (item.doff_time) {
                html += `
                    <div class="stat-row">
                        <span class="stat-icon">Doff:</span>
                        <span class="stat-value">${item.doff_time}</span>
                    </div>
                `;
            }
            html += `</div>`;
        }

        html += '</div>';
        return html;
    }

    /**
     * Get the current player's strength score.
     * @returns {number|null} Strength score or null if unavailable
     */
    getPlayerStrength() {
        try {
            // Try to get from state manager
            if (window.state && window.state.getState) {
                const gameState = window.state.getState();
                const playerId = gameState.playerId;
                if (playerId && gameState.combatants && gameState.combatants[playerId]) {
                    const player = gameState.combatants[playerId];
                    return player.stats?.strength || player.strength || null;
                }
            }
        } catch (e) {
            // Silently fail if state not available
        }
        return null;
    }

    /**
     * Render footer with weight, value, attunement.
     */
    renderFooter(item) {
        const parts = [];

        if (item.weight) {
            parts.push(`${item.weight} lb.`);
        }

        if (item.value) {
            parts.push(`${this.formatGold(item.value)}`);
        }

        let html = '';

        if (parts.length > 0) {
            html += `
                <div class="tooltip-footer">
                    <span class="footer-info">${parts.join(' | ')}</span>
                </div>
            `;
        }

        // Attunement
        if (item.requires_attunement) {
            const attuneClass = item.is_attuned ? 'attuned' : 'not-attuned';
            const attuneText = item.is_attuned ? 'Attuned' : 'Requires Attunement';
            html += `
                <div class="tooltip-attunement ${attuneClass}">
                    ${attuneText}
                </div>
            `;
        }

        return html;
    }

    /**
     * Format item type for display.
     */
    formatItemType(item) {
        const type = item.item_type || 'misc';
        const parts = [];

        // Add category based on properties
        if (item.properties?.includes('martial')) {
            parts.push('Martial');
        } else if (item.properties?.includes('simple')) {
            parts.push('Simple');
        }

        // Add range type
        if (item.range && !item.properties?.includes('thrown')) {
            parts.push('Ranged');
        } else if (item.damage && !item.range) {
            parts.push('Melee');
        }

        // Add base type
        parts.push(this.capitalize(type));

        return parts.join(' ');
    }

    /**
     * Format damage type for display.
     */
    formatDamageType(damageType) {
        const colors = {
            slashing: '#cc4444',
            piercing: '#44cc44',
            bludgeoning: '#888888',
            fire: '#ff6600',
            cold: '#66ccff',
            lightning: '#ffff00',
            thunder: '#9966ff',
            poison: '#00cc66',
            acid: '#99cc00',
            necrotic: '#663399',
            radiant: '#ffcc00',
            force: '#cc66ff',
            psychic: '#ff66cc',
        };

        const color = colors[damageType.toLowerCase()] || '#cccccc';
        return `<span style="color: ${color}">${this.capitalize(damageType)}</span>`;
    }

    /**
     * Format mastery type for display.
     */
    formatMastery(mastery) {
        return mastery.toUpperCase();
    }

    /**
     * Format gold value.
     */
    formatGold(value) {
        if (value >= 100) {
            return `${Math.floor(value / 100)} gp`;
        } else if (value >= 10) {
            return `${Math.floor(value / 10)} sp`;
        } else {
            return `${value} cp`;
        }
    }

    /**
     * Capitalize first letter.
     */
    capitalize(str) {
        if (!str) return '';
        return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
    }

    /**
     * Update tooltip position on mouse move.
     */
    updatePosition(x, y) {
        if (this.visible) {
            this.positionTooltip(x, y);
        }
    }
}

// Export singleton instance
export const itemTooltip = new ItemTooltip();
export default itemTooltip;
