/**
 * D&D Spell System - Spell Selection Modal
 * BG3-style spell picker with slot selection
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';
import api from '../api/api-client.js';

class SpellModal {
    constructor() {
        this.selectedSpell = null;
        this.selectedSlotLevel = null;
        this.spellCallback = null;
        this.spellData = {
            cantrips: [],
            leveledSpells: [],
            spellSlots: {},
            spellSlotsUsed: {},
            concentratingOn: null
        };
        this.createModal();
    }

    createModal() {
        // Create modal HTML structure
        const modal = document.createElement('div');
        modal.id = 'spell-modal';
        modal.className = 'spell-modal hidden';
        modal.innerHTML = `
            <div class="spell-modal-overlay" id="spell-modal-overlay"></div>
            <div class="spell-modal-content">
                <div class="modal-header">
                    <h2>Spellbook</h2>
                    <button class="modal-close" id="spell-close-btn">&times;</button>
                </div>

                <div class="spell-modal-body">
                    <!-- Spell Slot Display -->
                    <div class="spell-slots-bar" id="spell-slots-bar">
                        <!-- Dynamically populated -->
                    </div>

                    <!-- Spell Filter Tabs -->
                    <div class="spell-tabs" id="spell-tabs">
                        <button class="spell-tab active" data-level="all">All</button>
                        <button class="spell-tab" data-level="0">Cantrips</button>
                        <button class="spell-tab" data-level="1">1st</button>
                        <button class="spell-tab" data-level="2">2nd</button>
                        <button class="spell-tab" data-level="3">3rd</button>
                        <button class="spell-tab" data-level="4">4th</button>
                        <button class="spell-tab" data-level="5">5th</button>
                    </div>

                    <!-- Main content area -->
                    <div class="spell-main-content">
                        <!-- Spell Grid -->
                        <div class="spell-grid-container">
                            <div class="spell-grid" id="spell-grid">
                                <!-- Dynamically populated spell cards -->
                            </div>
                        </div>

                        <!-- Spell Details Panel (right side) -->
                        <div class="spell-details-panel hidden" id="spell-details">
                            <h3 id="spell-detail-name"></h3>
                            <div class="spell-meta">
                                <span class="spell-school" id="spell-detail-school"></span>
                                <span class="spell-level-text" id="spell-detail-level"></span>
                            </div>
                            <div class="spell-info">
                                <div><strong>Casting Time:</strong> <span id="spell-detail-time"></span></div>
                                <div><strong>Range:</strong> <span id="spell-detail-range"></span></div>
                                <div><strong>Components:</strong> <span id="spell-detail-components"></span></div>
                                <div><strong>Duration:</strong> <span id="spell-detail-duration"></span></div>
                            </div>
                            <div class="spell-description" id="spell-detail-desc"></div>
                            <div class="spell-higher-levels hidden" id="spell-detail-higher">
                                <strong>At Higher Levels:</strong>
                                <span id="spell-detail-higher-text"></span>
                            </div>

                            <!-- Concentration Warning -->
                            <div class="concentration-warning hidden" id="concentration-warning">
                                <span class="warning-icon">⚠️</span>
                                <span class="warning-text">Casting this will end your concentration on <strong id="current-concentration-spell">-</strong></span>
                            </div>

                            <!-- Ritual Casting Info -->
                            <div class="ritual-info hidden" id="ritual-info">
                                <span class="ritual-icon">📖</span>
                                <span class="ritual-text">Can be cast as a ritual (+10 minutes, no slot required)</span>
                            </div>

                            <!-- Slot Level Selector (for leveled spells) -->
                            <div class="slot-selector hidden" id="slot-selector">
                                <label>Cast at Level:</label>
                                <select id="slot-level-select"></select>
                                <div class="upcast-preview hidden" id="upcast-preview">
                                    <!-- Shows damage/effect preview when upcasting -->
                                </div>
                            </div>

                            <button class="btn-cast" id="btn-cast-spell" disabled>Select a Spell</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Close button
        document.getElementById('spell-close-btn')?.addEventListener('click', () => this.hide());

        // Overlay click to close
        document.getElementById('spell-modal-overlay')?.addEventListener('click', () => this.hide());

        // Tab filtering
        document.getElementById('spell-tabs')?.addEventListener('click', (e) => {
            if (e.target.classList.contains('spell-tab')) {
                this.filterByLevel(e.target.dataset.level);
            }
        });

        // Cast button
        document.getElementById('btn-cast-spell')?.addEventListener('click', () => this.confirmCast());

        // ESC to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !this.isHidden()) {
                this.hide();
            }
        });
    }

    async show(callback) {
        this.spellCallback = callback;
        this.selectedSpell = null;
        this.selectedSlotLevel = null;

        const modal = document.getElementById('spell-modal');

        // Load character's spells
        await this.loadSpells();

        // Reset UI
        this.resetSelection();

        // Show modal
        modal?.classList.remove('hidden');
    }

    hide() {
        const modal = document.getElementById('spell-modal');
        modal?.classList.add('hidden');
        this.selectedSpell = null;
        this.selectedSlotLevel = null;
        this.spellCallback = null;
    }

    isHidden() {
        return document.getElementById('spell-modal')?.classList.contains('hidden');
    }

    async loadSpells() {
        const gameState = state.getState();
        const playerId = gameState.playerId;
        const combatId = gameState.combat?.id;

        try {
            console.log('[SpellModal] Loading spells for player:', playerId, 'combat:', combatId);

            // Get available spells from API
            const response = await api.getAvailableSpells(playerId, combatId);
            console.log('[SpellModal] API Response:', response);

            this.spellData = {
                cantrips: response.cantrips || [],
                leveledSpells: response.leveled_spells || [],
                spellSlots: response.spell_slots || {},
                spellSlotsUsed: response.spell_slots_used || {},
                concentratingOn: response.concentrating_on
            };
            console.log('[SpellModal] Processed spellData:', this.spellData);

            // Render spell slots bar
            console.log('[SpellModal] Rendering spell slots...');
            this.renderSpellSlots();
            console.log('[SpellModal] Spell slots rendered');

            // Render spell grid
            console.log('[SpellModal] Rendering spell grid...');
            this.renderSpellGrid();
            console.log('[SpellModal] Spell grid rendered');

        } catch (error) {
            console.error('[SpellModal] Failed to load spells:', error);
            console.error('[SpellModal] Error stack:', error.stack);
            this.showError('Failed to load spells: ' + error.message);
        }
    }

    renderSpellSlots() {
        const container = document.getElementById('spell-slots-bar');
        if (!container) return;

        const { spellSlots, spellSlotsUsed } = this.spellData;

        let html = '<span class="slots-label">Spell Slots:</span>';
        let hasSlots = false;

        for (let level = 1; level <= 9; level++) {
            const max = spellSlots[level] || 0;
            const used = spellSlotsUsed[level] || 0;
            const available = max - used;

            if (max > 0) {
                hasSlots = true;
                html += `
                    <div class="slot-group" data-level="${level}">
                        <span class="slot-label">${this.getOrdinalLevel(level)}</span>
                        <div class="slot-pips">
                            ${this.renderSlotPips(max, used)}
                        </div>
                    </div>
                `;
            }
        }

        if (!hasSlots) {
            html = '<span class="no-slots">No spell slots available</span>';
        }

        container.innerHTML = html;
    }

    renderSlotPips(max, used) {
        let pips = '';
        for (let i = 0; i < max; i++) {
            const isUsed = i < used;
            pips += `<span class="slot-pip ${isUsed ? 'used' : 'available'}"></span>`;
        }
        return pips;
    }

    getOrdinalLevel(n) {
        const suffixes = ['th', 'st', 'nd', 'rd'];
        const v = n % 100;
        return n + (suffixes[(v - 20) % 10] || suffixes[v] || suffixes[0]);
    }

    renderSpellGrid() {
        const grid = document.getElementById('spell-grid');
        if (!grid) {
            console.error('[SpellModal] spell-grid element not found!');
            return;
        }

        const { cantrips, leveledSpells } = this.spellData;
        console.log('[SpellModal] renderSpellGrid - cantrips:', cantrips?.length, 'leveledSpells:', leveledSpells?.length);

        let html = '';

        // Cantrips section - clearly marked as unlimited
        if (cantrips?.length > 0) {
            html += `<div class="spell-section cantrips-section" data-level="0">
                <h4>Cantrips <span class="unlimited-badge">(Unlimited Use)</span></h4>
                <div class="spell-cards">`;
            cantrips.forEach(spell => {
                html += this.renderSpellCard(spell);
            });
            html += '</div></div>';
        }

        // Add divider between cantrips and leveled spells
        if (cantrips?.length > 0 && leveledSpells?.length > 0) {
            html += '<div class="spell-section-divider"><span>Leveled Spells (Use Spell Slots)</span></div>';
        }

        // Group leveled spells by level
        const spellsByLevel = {};
        leveledSpells?.forEach(spell => {
            const level = spell.level || 1;
            if (!spellsByLevel[level]) spellsByLevel[level] = [];
            spellsByLevel[level].push(spell);
        });

        // Render leveled spells by level
        for (let level = 1; level <= 9; level++) {
            const spells = spellsByLevel[level];
            if (spells && spells.length > 0) {
                const hasSlot = this.hasAvailableSlot(level);
                const slotsAvailable = this.getAvailableSlotsForLevel(level);
                html += `<div class="spell-section leveled-section ${!hasSlot ? 'no-slots' : ''}" data-level="${level}">`;
                html += `<h4>${this.getOrdinalLevel(level)} Level Spells`;
                if (hasSlot) {
                    html += ` <span class="slots-available">(${slotsAvailable} slot${slotsAvailable !== 1 ? 's' : ''} available)</span>`;
                } else {
                    html += ' <span class="no-slots-badge">(No Slots)</span>';
                }
                html += '</h4>';
                html += '<div class="spell-cards">';
                spells.forEach(spell => {
                    html += this.renderSpellCard(spell, !hasSlot);
                });
                html += '</div></div>';
            }
        }

        if (!html) {
            html = '<div class="no-spells">No spells available</div>';
        }

        grid.innerHTML = html;

        // Add click handlers to spell cards
        const spellCards = grid.querySelectorAll('.spell-card');
        console.log('[SpellModal] Found', spellCards.length, 'spell cards, adding click handlers');
        spellCards.forEach(card => {
            console.log('[SpellModal] Adding click handler to card:', card.dataset.spellId, 'disabled:', card.classList.contains('disabled'));
            card.addEventListener('click', (e) => {
                console.log('[SpellModal] Card clicked:', card.dataset.spellId, 'disabled:', card.classList.contains('disabled'));
                e.stopPropagation(); // Prevent event bubbling
                if (!card.classList.contains('disabled')) {
                    this.selectSpell(card.dataset.spellId);
                } else {
                    console.log('[SpellModal] Card is disabled, ignoring click');
                }
            });
        });
    }

    hasAvailableSlot(minLevel) {
        const { spellSlots, spellSlotsUsed } = this.spellData;
        for (let level = minLevel; level <= 9; level++) {
            const max = spellSlots[level] || 0;
            const used = spellSlotsUsed[level] || 0;
            if (max - used > 0) return true;
        }
        return false;
    }

    getAvailableSlotsForLevel(minLevel) {
        const { spellSlots, spellSlotsUsed } = this.spellData;
        let total = 0;
        for (let level = minLevel; level <= 9; level++) {
            const max = spellSlots[level] || 0;
            const used = spellSlotsUsed[level] || 0;
            total += Math.max(0, max - used);
        }
        return total;
    }

    renderSpellCard(spell, disabled = false) {
        if (!spell) {
            console.error('[SpellModal] renderSpellCard received null/undefined spell');
            return '';
        }

        const schoolIcon = this.getSchoolIcon(spell.school);
        const concentrationBadge = spell.concentration ? '<span class="badge concentration" title="Concentration">C</span>' : '';
        const ritualBadge = spell.ritual ? '<span class="badge ritual" title="Ritual">R</span>' : '';
        // On-hit spells (like Divine Smite) can only be cast after hitting with a weapon
        const isOnHit = spell.trigger === 'on_hit';
        const onHitBadge = isOnHit ? '<span class="badge on-hit" title="Cast after hitting with weapon">On Hit</span>' : '';
        const levelText = spell.level === 0 ? 'Cantrip' : `${this.getOrdinalLevel(spell.level || 0)}`;

        return `
            <div class="spell-card ${disabled ? 'disabled' : ''} ${isOnHit ? 'on-hit-spell' : ''}"
                 data-spell-id="${spell.id || 'unknown'}"
                 data-level="${spell.level || 0}"
                 data-trigger="${spell.trigger || ''}">
                <div class="spell-card-header">
                    <span class="spell-icon">${schoolIcon}</span>
                    <span class="spell-name">${spell.name || 'Unknown Spell'}</span>
                    <div class="spell-badges">
                        ${concentrationBadge}${ritualBadge}${onHitBadge}
                    </div>
                </div>
                <div class="spell-card-footer">
                    <span class="spell-time">${spell.casting_time || '1 action'}</span>
                    <span class="spell-level-badge">${levelText}</span>
                </div>
            </div>
        `;
    }

    getSchoolIcon(school) {
        const icons = {
            abjuration: '🛡️',
            conjuration: '✨',
            divination: '👁️',
            enchantment: '💫',
            evocation: '🔥',
            illusion: '🌀',
            necromancy: '💀',
            transmutation: '🔄'
        };
        return icons[school?.toLowerCase()] || '📜';
    }

    async selectSpell(spellId) {
        console.log('[SpellModal] selectSpell called with:', spellId);
        // Find spell in our data
        const allSpells = [...this.spellData.cantrips, ...this.spellData.leveledSpells];
        console.log('[SpellModal] All spells:', allSpells.map(s => ({ id: s.id, name: s.name, target_type: s.target_type })));
        const spell = allSpells.find(s => s.id === spellId);

        if (!spell) {
            console.error('[SpellModal] Spell not found:', spellId);
            return;
        }

        console.log('[SpellModal] Spell found:', spell.name, 'target_type:', spell.target_type);
        this.selectedSpell = spell;

        // Highlight selected card
        document.querySelectorAll('.spell-card').forEach(c => c.classList.remove('selected'));
        document.querySelector(`[data-spell-id="${spellId}"]`)?.classList.add('selected');

        // Show details panel
        this.showSpellDetails(spell);
    }

    showSpellDetails(spell) {
        const panel = document.getElementById('spell-details');
        if (!panel) return;

        document.getElementById('spell-detail-name').textContent = spell.name;
        document.getElementById('spell-detail-school').textContent = spell.school;
        document.getElementById('spell-detail-level').textContent =
            spell.level === 0 ? 'Cantrip' : `${this.getOrdinalLevel(spell.level)} Level`;
        document.getElementById('spell-detail-time').textContent = spell.casting_time;
        document.getElementById('spell-detail-range').textContent = spell.range;
        document.getElementById('spell-detail-components').textContent = this.formatComponents(spell.components);
        document.getElementById('spell-detail-duration').textContent = spell.duration;
        document.getElementById('spell-detail-desc').textContent = spell.description;

        // Higher levels text
        const higherLevelsEl = document.getElementById('spell-detail-higher');
        if (spell.higher_levels) {
            document.getElementById('spell-detail-higher-text').textContent = spell.higher_levels;
            higherLevelsEl?.classList.remove('hidden');
        } else {
            higherLevelsEl?.classList.add('hidden');
        }

        // Concentration warning
        const concentrationWarning = document.getElementById('concentration-warning');
        if (spell.concentration && this.spellData.concentratingOn) {
            const currentSpellName = this.spellData.concentratingOn.name || this.spellData.concentratingOn;
            document.getElementById('current-concentration-spell').textContent = currentSpellName;
            concentrationWarning?.classList.remove('hidden');
        } else {
            concentrationWarning?.classList.add('hidden');
        }

        // Ritual info
        const ritualInfo = document.getElementById('ritual-info');
        if (spell.ritual) {
            ritualInfo?.classList.remove('hidden');
        } else {
            ritualInfo?.classList.add('hidden');
        }

        // Show slot selector for leveled spells (but not for on-hit spells)
        const slotSelector = document.getElementById('slot-selector');
        const isOnHit = spell.trigger === 'on_hit';

        if (spell.level > 0 && !isOnHit) {
            this.populateSlotSelector(spell.level);
            slotSelector?.classList.remove('hidden');
        } else {
            slotSelector?.classList.add('hidden');
            this.selectedSlotLevel = null;
        }

        // Enable/disable cast button based on spell type
        const castBtn = document.getElementById('btn-cast-spell');
        if (castBtn) {
            if (isOnHit) {
                // On-hit spells (like Divine Smite) can't be cast from the modal
                castBtn.disabled = true;
                castBtn.textContent = 'Cast after hitting with weapon';
                castBtn.title = 'This spell is cast as a bonus action immediately after hitting a target with a weapon attack';
            } else {
                castBtn.disabled = false;
                castBtn.textContent = `Cast ${spell.name}`;
                castBtn.title = '';
            }
        }

        panel.classList.remove('hidden');
    }

    formatComponents(components) {
        if (!components) return 'None';

        const parts = [];
        if (components.verbal) parts.push('V');
        if (components.somatic) parts.push('S');
        if (components.material) parts.push(`M (${components.material})`);
        return parts.join(', ') || 'None';
    }

    populateSlotSelector(minLevel) {
        const select = document.getElementById('slot-level-select');
        if (!select) return;

        const { spellSlots, spellSlotsUsed } = this.spellData;

        let html = '';
        let firstAvailable = null;

        for (let level = minLevel; level <= 9; level++) {
            const max = spellSlots[level] || 0;
            const used = spellSlotsUsed[level] || 0;
            const available = max - used;

            if (available > 0) {
                if (firstAvailable === null) firstAvailable = level;
                const upcastBonus = level > minLevel ? ` (+${level - minLevel} level${level - minLevel > 1 ? 's' : ''})` : '';
                html += `<option value="${level}">${this.getOrdinalLevel(level)} Level${upcastBonus} (${available} slot${available > 1 ? 's' : ''})</option>`;
            }
        }

        select.innerHTML = html;
        this.selectedSlotLevel = firstAvailable;

        select.onchange = () => {
            this.selectedSlotLevel = parseInt(select.value);
            this.updateUpcastPreview();
        };

        // Show initial upcast preview
        this.updateUpcastPreview();
    }

    /**
     * Update the upcast damage/effect preview
     */
    updateUpcastPreview() {
        const previewEl = document.getElementById('upcast-preview');
        if (!previewEl || !this.selectedSpell) {
            previewEl?.classList.add('hidden');
            return;
        }

        const baseLevel = this.selectedSpell.level;
        const castLevel = this.selectedSlotLevel;
        const upcastLevels = castLevel - baseLevel;

        if (upcastLevels <= 0) {
            previewEl.classList.add('hidden');
            return;
        }

        // Calculate upcast bonus based on spell data
        const preview = this.calculateUpcastBonus(this.selectedSpell, upcastLevels);

        if (preview) {
            previewEl.innerHTML = `<span class="upcast-label">⬆️ Upcast Bonus:</span> ${preview}`;
            previewEl.classList.remove('hidden');
        } else {
            previewEl.classList.add('hidden');
        }
    }

    /**
     * Calculate upcast bonus text based on spell properties
     */
    calculateUpcastBonus(spell, upcastLevels) {
        // Parse higher_levels text for common patterns
        const higherLevels = spell.higher_levels || '';

        // Common patterns: "additional Xd6", "one additional target", etc.
        const diceMatch = higherLevels.match(/(\d+)d(\d+)/);
        const targetMatch = higherLevels.match(/one additional (target|creature|missile)/i);

        let bonuses = [];

        // Damage dice bonus
        if (diceMatch) {
            const diceCount = parseInt(diceMatch[1]) * upcastLevels;
            const diceType = diceMatch[2];
            bonuses.push(`+${diceCount}d${diceType} damage`);
        }

        // Target bonus
        if (targetMatch) {
            bonuses.push(`+${upcastLevels} additional ${targetMatch[1]}${upcastLevels > 1 ? 's' : ''}`);
        }

        // Healing spells
        const healMatch = higherLevels.match(/heals? .*?(\d+)d(\d+)/i);
        if (healMatch && !diceMatch) {
            const diceCount = parseInt(healMatch[1]) * upcastLevels;
            const diceType = healMatch[2];
            bonuses.push(`+${diceCount}d${diceType} healing`);
        }

        // Duration increase
        const durationMatch = higherLevels.match(/duration increases by (\d+) (hour|minute|day)/i);
        if (durationMatch) {
            const amount = parseInt(durationMatch[1]) * upcastLevels;
            bonuses.push(`+${amount} ${durationMatch[2]}${amount > 1 ? 's' : ''} duration`);
        }

        if (bonuses.length > 0) {
            return bonuses.join(', ');
        }

        // Fallback: if there's higher_levels text, just note it's enhanced
        if (higherLevels) {
            return 'Enhanced effect (see description)';
        }

        return null;
    }

    filterByLevel(level) {
        // Update tab active state
        document.querySelectorAll('.spell-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.level === level);
        });

        // Show/hide spell sections
        document.querySelectorAll('.spell-section').forEach(section => {
            if (level === 'all') {
                section.classList.remove('hidden');
            } else {
                const sectionLevel = section.dataset.level;
                section.classList.toggle('hidden', sectionLevel !== level);
            }
        });
    }

    resetSelection() {
        this.selectedSpell = null;
        this.selectedSlotLevel = null;

        document.querySelectorAll('.spell-card').forEach(c => c.classList.remove('selected'));
        document.getElementById('spell-details')?.classList.add('hidden');

        const castBtn = document.getElementById('btn-cast-spell');
        if (castBtn) {
            castBtn.disabled = true;
            castBtn.textContent = 'Select a Spell';
        }

        // Reset to "All" tab
        this.filterByLevel('all');
    }

    confirmCast() {
        console.log('[SpellModal] confirmCast called, selectedSpell:', this.selectedSpell?.name);
        if (!this.selectedSpell) {
            console.log('[SpellModal] No spell selected, returning');
            return;
        }

        // Save spell data and callback BEFORE calling hide() which clears them
        const spell = this.selectedSpell;
        const slotLevel = this.selectedSlotLevel;
        const callback = this.spellCallback;

        // Hide modal (this clears selectedSpell, selectedSlotLevel, spellCallback)
        this.hide();

        // Now use the saved callback
        if (callback) {
            console.log('[SpellModal] Calling callback with spell:', spell.name, 'target_type:', spell.target_type);
            callback({
                spell: spell,
                slotLevel: slotLevel
            });
        } else {
            // Fallback: Emit event that action-bar can handle
            console.log('[SpellModal] No callback, emitting SPELL_SELECTED event');
            eventBus.emit(EVENTS.SPELL_SELECTED, { spell, slotLevel });
        }
    }

    showError(message) {
        const grid = document.getElementById('spell-grid');
        if (grid) {
            grid.innerHTML = `<div class="spell-error">${message}</div>`;
        }
    }
}

// Export singleton instance
const spellModal = new SpellModal();
export default spellModal;
