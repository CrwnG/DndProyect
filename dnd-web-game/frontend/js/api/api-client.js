/**
 * D&D Combat Engine - API Client
 * Handles all HTTP communication with the backend
 */

import { CONFIG } from '../config.js';

class APIClient {
    constructor(baseUrl = CONFIG.API_BASE_URL) {
        this.baseUrl = baseUrl;
    }

    /**
     * Make an HTTP request
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;

        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };

        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers,
            },
        };

        if (CONFIG.DEBUG) {
            console.log(`[API] ${options.method || 'GET'} ${url}`, options.body ? JSON.parse(options.body) : '');
        }

        try {
            const response = await fetch(url, mergedOptions);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new APIError(
                    errorData.detail || `HTTP ${response.status}`,
                    response.status,
                    errorData
                );
            }

            const data = await response.json();

            if (CONFIG.DEBUG) {
                console.log(`[API] Response:`, data);
            }

            return data;
        } catch (error) {
            if (error instanceof APIError) {
                throw error;
            }
            throw new APIError(`Network error: ${error.message}`, 0, null);
        }
    }

    /**
     * GET request
     */
    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }

    /**
     * POST request
     */
    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    /**
     * PUT request
     */
    async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    /**
     * DELETE request
     */
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    // ==================== Combat Endpoints ====================

    /**
     * Start a new combat encounter
     * @param {Array} players - Array of player combatant data
     * @param {Array} enemies - Array of enemy combatant data
     * @param {Object} options - Grid options (width, height, obstacles, positions)
     */
    async startCombat(players, enemies, options = {}) {
        return this.post('/combat/start', {
            players,
            enemies,
            grid_width: options.gridWidth || 8,
            grid_height: options.gridHeight || 8,
            obstacles: options.obstacles || [],
            difficult_terrain: options.difficultTerrain || [],
            initial_positions: options.initialPositions || null,
        });
    }

    /**
     * End combat
     */
    async endCombat(combatId) {
        return this.post(`/combat/${combatId}/end`, {});
    }

    /**
     * Get current combat state
     */
    async getCombatState(combatId) {
        return this.get(`/combat/${combatId}/state`);
    }

    /**
     * Perform an action (attack, dash, dodge, etc.)
     */
    async performAction(combatId, actionType, targetId = null, options = {}) {
        return this.post('/combat/action', {
            combat_id: combatId,
            action_type: actionType,
            target_id: targetId,
            weapon_name: options.weaponName || null,
            spell_name: options.spellName || null,
            extra_data: options.extraData || {},
        });
    }

    /**
     * Move a combatant to a target position
     * @param {string} combatId - The combat session ID
     * @param {string} combatantId - The ID of the combatant to move
     * @param {number} targetX - Target X coordinate
     * @param {number} targetY - Target Y coordinate
     */
    async moveCombatant(combatId, combatantId, targetX, targetY) {
        return this.post('/combat/move', {
            combat_id: combatId,
            combatant_id: combatantId,
            target_x: targetX,
            target_y: targetY,
        });
    }

    /**
     * Use a reaction (opportunity attack, Shield spell, etc.)
     * @param {string} combatId - Combat session ID
     * @param {string} reactorId - ID of the combatant using their reaction
     * @param {string} reactionType - Type of reaction (opportunity_attack, shield, uncanny_dodge)
     * @param {string} triggerSourceId - ID of the combatant that triggered the reaction
     */
    async useReaction(combatId, reactorId, reactionType, triggerSourceId) {
        // Validate all required parameters to prevent 422 errors
        if (!combatId || typeof combatId !== 'string') {
            throw new APIError(`useReaction: Invalid combat_id: ${combatId}`, 400, null);
        }
        if (!reactorId || typeof reactorId !== 'string') {
            throw new APIError(`useReaction: Invalid reactor_id: ${reactorId}`, 400, null);
        }
        if (!reactionType || typeof reactionType !== 'string') {
            throw new APIError(`useReaction: Invalid reaction_type: ${reactionType}`, 400, null);
        }
        if (!triggerSourceId || typeof triggerSourceId !== 'string') {
            throw new APIError(`useReaction: Invalid trigger_source_id: ${triggerSourceId}`, 400, null);
        }

        const requestBody = {
            combat_id: combatId,
            reaction_type: reactionType,
            trigger_source_id: triggerSourceId,
            extra_data: {
                reactor_id: reactorId
            }
        };
        console.log('[API] useReaction request:', requestBody);
        return this.post('/combat/reaction', requestBody);
    }

    /**
     * Perform a bonus action (off-hand attack, second wind, etc.)
     * @param {string} combatId - The combat session ID
     * @param {string} bonusActionType - Type of bonus action (offhand_attack, second_wind)
     * @param {string} targetId - Target of the bonus action (if applicable)
     * @param {Object} options - Additional options (weaponName, extraData)
     */
    async performBonusAction(combatId, bonusActionType, targetId = null, options = {}) {
        return this.post('/combat/bonus-action', {
            combat_id: combatId,
            bonus_action_type: bonusActionType,
            target_id: targetId,
            weapon_name: options.weaponName || null,
            extra_data: options.extraData || {},
        });
    }

    /**
     * End current turn
     */
    async endTurn(combatId) {
        return this.post(`/combat/${combatId}/end-turn`, {});
    }

    // ==================== Class Feature Endpoints ====================

    /**
     * Use Divine Smite (Paladin)
     * @param {string} combatId - Combat session ID
     * @param {number} slotLevel - Spell slot level to expend (1-5)
     * @param {string} targetId - ID of the target to damage
     */
    async applyDivineSmite(combatId, slotLevel, targetId) {
        return this.post(`/combat/${combatId}/divine-smite?slot_level=${slotLevel}&target_id=${targetId}`, {});
    }

    /**
     * Use Action Surge (Fighter)
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Fighter's combatant ID
     */
    async useActionSurge(combatId, combatantId) {
        return this.post(`/combat/${combatId}/action-surge?combatant_id=${combatantId}`, {});
    }

    /**
     * Use a class feature (generic router to specific endpoints)
     * @param {string} combatId - Combat session ID
     * @param {string} featureType - Feature type (action_surge, rage, wild_shape, lay_on_hands, cunning_action, revert_wild_shape, reckless_attack, channel_divinity, bardic_inspiration)
     * @param {Object} options - Additional options (target_id, amount, action_type for cunning action, combatant_id)
     */
    async useClassFeature(combatId, featureType, options = {}) {
        // Route to specific endpoints based on feature type
        switch (featureType) {
            case 'action_surge':
                return this.useActionSurge(combatId, options.combatant_id);
            case 'rage':
                return this.enterRage(combatId, options.combatant_id);
            case 'wild_shape':
                return this.useWildShape(combatId, options.combatant_id, options.beast_form);
            case 'revert_wild_shape':
                return this.revertWildShape(combatId, options.combatant_id);
            case 'lay_on_hands':
                return this.useLayOnHands(combatId, options.combatant_id, options.target_id, options.amount);
            case 'cunning_action':
                return this.useCunningAction(combatId, options.combatant_id, options.action_type);
            case 'reckless_attack':
                return this.useRecklessAttack(combatId, options.combatant_id);
            case 'channel_divinity':
                return this.useChannelDivinity(combatId, options.combatant_id, options.option);
            case 'bardic_inspiration':
                return this.useBardicInspiration(combatId, options.combatant_id, options.target_id);
            default:
                throw new APIError(`Unknown class feature: ${featureType}`, 400, null);
        }
    }

    /**
     * Enter Barbarian Rage
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Barbarian's combatant ID
     */
    async enterRage(combatId, combatantId) {
        return this.post(`/class-features/${combatId}/barbarian/rage`, {
            combatant_id: combatantId
        });
    }

    /**
     * Use Druid Wild Shape
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Druid's combatant ID
     * @param {string} beastForm - Name of the beast form
     */
    async useWildShape(combatId, combatantId, beastForm) {
        return this.post(`/class-features/${combatId}/druid/wild-shape`, {
            combatant_id: combatantId,
            beast_form: beastForm
        });
    }

    /**
     * Revert from Wild Shape
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Druid's combatant ID
     */
    async revertWildShape(combatId, combatantId) {
        return this.post(`/class-features/${combatId}/druid/revert`, {
            combatant_id: combatantId
        });
    }

    /**
     * Use Paladin Lay on Hands
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Paladin's combatant ID
     * @param {string} targetId - Target to heal
     * @param {number} amount - HP to heal
     * @param {boolean} cureDisease - Whether to cure a disease (5 HP cost)
     * @param {boolean} curePoison - Whether to cure poison (5 HP cost)
     */
    async useLayOnHands(combatId, combatantId, targetId, amount, cureDisease = false, curePoison = false) {
        return this.post(`/class-features/${combatId}/paladin/lay-on-hands`, {
            combatant_id: combatantId,
            target_id: targetId,
            points_to_spend: amount,
            cure_disease: cureDisease,
            cure_poison: curePoison
        });
    }

    /**
     * Use Rogue Cunning Action
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Rogue's combatant ID
     * @param {string} actionType - 'dash', 'disengage', or 'hide'
     */
    async useCunningAction(combatId, combatantId, actionType) {
        return this.post(`/class-features/${combatId}/rogue/cunning-action`, {
            combatant_id: combatantId,
            action_type: actionType
        });
    }

    /**
     * Use Barbarian Reckless Attack
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Barbarian's combatant ID
     */
    async useRecklessAttack(combatId, combatantId) {
        return this.post(`/class-features/${combatId}/barbarian/reckless-attack`, {
            combatant_id: combatantId
        });
    }

    /**
     * Use Cleric/Paladin Channel Divinity
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Cleric or Paladin's combatant ID
     * @param {string} option - Channel Divinity option (e.g., 'turn_undead', 'sacred_weapon')
     */
    async useChannelDivinity(combatId, combatantId, option) {
        return this.post(`/class-features/${combatId}/channel-divinity`, {
            combatant_id: combatantId,
            option: option
        });
    }

    /**
     * Use Bard Bardic Inspiration
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Bard's combatant ID
     * @param {string} targetId - ID of the ally to inspire
     */
    async useBardicInspiration(combatId, combatantId, targetId) {
        return this.post(`/class-features/${combatId}/bard/bardic-inspiration`, {
            combatant_id: combatantId,
            target_id: targetId
        });
    }

    // ==================== Monk Ki Endpoints ====================

    /**
     * Use a Monk Ki power
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Monk's combatant ID
     * @param {string} powerId - Ki power to use (flurry_of_blows, patient_defense, step_of_the_wind, stunning_strike)
     */
    async useKiPower(combatId, combatantId, powerId) {
        // Route to specific Ki ability endpoints
        const endpoints = {
            'flurry_of_blows': 'flurry-of-blows',
            'patient_defense': 'patient-defense',
            'step_of_the_wind': 'step-of-the-wind',
            'stunning_strike': 'stunning-strike'
        };
        const endpoint = endpoints[powerId] || powerId.replace(/_/g, '-');
        return this.post(`/class-features/${combatId}/ki/${endpoint}`, {
            combatant_id: combatantId
        });
    }

    /**
     * Get current Ki points for a Monk
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Monk's combatant ID
     */
    async getKiPoints(combatId, combatantId) {
        return this.get(`/class-features/${combatId}/monk/ki-points/${combatantId}`);
    }

    // ==================== Rest Endpoints ====================

    /**
     * Take a short rest to recover hit dice and some class resources
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Combatant ID
     * @param {number} hitDiceToSpend - Number of hit dice to spend for healing (optional)
     */
    async shortRest(combatId, combatantId, hitDiceToSpend = 0) {
        return this.post(`/class-features/${combatId}/rest/short`, {
            combatant_id: combatantId,
            hit_dice_to_spend: hitDiceToSpend
        });
    }

    /**
     * Take a long rest to fully recover HP, spell slots, and all class resources
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Combatant ID
     */
    async longRest(combatId, combatantId) {
        return this.post(`/class-features/${combatId}/rest/long`, {
            combatant_id: combatantId
        });
    }

    // ==================== Death Saves ====================

    /**
     * Roll a death saving throw for an unconscious character
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Combatant ID
     */
    async rollDeathSave(combatId, combatantId) {
        return this.post(`/combat/${combatId}/death-save`, {
            combatant_id: combatantId
        });
    }

    // ==================== Legendary Actions ====================

    /**
     * Use a legendary action for a legendary creature
     * @param {string} combatId - Combat session ID
     * @param {string} monsterId - ID of the legendary creature
     * @param {string} actionId - ID of the legendary action to use
     * @param {string|null} targetId - Optional target for the action
     */
    async useLegendaryAction(combatId, monsterId, actionId, targetId = null) {
        return this.post('/combat/legendary-action', {
            combat_id: combatId,
            monster_id: monsterId,
            action_id: actionId,
            target_id: targetId
        });
    }

    // ==================== Equipment Endpoints ====================

    /**
     * Get all available items from rules data
     */
    async getAllItems() {
        return this.get('/equipment/items');
    }

    /**
     * Get all weapons
     */
    async getWeapons() {
        return this.get('/equipment/items/weapons');
    }

    /**
     * Get all armor
     */
    async getArmor() {
        return this.get('/equipment/items/armor');
    }

    /**
     * Get all adventuring gear
     */
    async getGear() {
        return this.get('/equipment/items/gear');
    }

    /**
     * Get equipment state for a combatant
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Combatant ID
     */
    async getEquipment(combatId, combatantId) {
        return this.get(`/equipment/${combatId}/${combatantId}`);
    }

    /**
     * Equip an item to a slot
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Combatant ID
     * @param {string} itemId - Item ID to equip
     * @param {string} slot - Target slot
     */
    async equipItem(combatId, combatantId, itemId, slot) {
        return this.post(`/equipment/${combatId}/${combatantId}/equip`, {
            item_id: itemId,
            slot: slot,
        });
    }

    /**
     * Unequip an item from a slot
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Combatant ID
     * @param {string} slot - Slot to unequip
     */
    async unequipItem(combatId, combatantId, slot) {
        return this.post(`/equipment/${combatId}/${combatantId}/unequip`, {
            slot: slot,
        });
    }

    /**
     * Swap items between two slots
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Combatant ID
     * @param {string} fromSlot - Source slot
     * @param {string} toSlot - Target slot
     */
    async swapEquipmentSlots(combatId, combatantId, fromSlot, toSlot) {
        return this.post(`/equipment/${combatId}/${combatantId}/swap`, {
            from_slot: fromSlot,
            to_slot: toSlot,
        });
    }

    /**
     * Get available equipment slots
     */
    async getEquipmentSlots() {
        return this.get('/equipment/slots');
    }

    /**
     * Get item rarities with colors
     */
    async getItemRarities() {
        return this.get('/equipment/rarities');
    }

    /**
     * Get reachable cells for movement
     */
    async getReachableCells(combatId, combatantId) {
        return this.get(`/combat/${combatId}/reachable?combatant_id=${combatantId}`);
    }

    /**
     * Get threat zones for enemies (opportunity attack areas)
     * @param {string} combatId - Combat session ID
     * @param {string|null} combatantId - Optional specific enemy ID
     * @returns {Promise<{threat_zones: Object}>} Threat zones by enemy ID
     */
    async getThreatZones(combatId, combatantId = null) {
        let url = `/combat/${combatId}/threat-zones`;
        if (combatantId) {
            url += `?combatant_id=${combatantId}`;
        }
        return this.get(url);
    }

    /**
     * Get valid attack targets
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Attacker's ID
     * @param {string|null} weaponId - Optional weapon ID to determine range from weapon data
     * @param {number} rangeFt - Fallback range in feet (default 5 for melee)
     */
    async getValidTargets(combatId, combatantId, weaponId = null, rangeFt = 5) {
        // FIXED: Now includes combatant_id in URL so backend knows who is attacking
        let url = `/combat/${combatId}/targets?combatant_id=${combatantId}&range_ft=${rangeFt}`;
        if (weaponId) {
            url += `&weapon_id=${weaponId}`;
        }
        console.log('[API] getValidTargets:', { combatId, combatantId, weaponId, rangeFt, url });
        return this.get(url);
    }

    /**
     * Get initiative order
     */
    async getInitiativeOrder(combatId) {
        return this.get(`/combat/${combatId}/initiative`);
    }

    /**
     * Get combat events/log
     */
    async getCombatEvents(combatId, limit = 20) {
        return this.get(`/combat/${combatId}/events?limit=${limit}`);
    }

    // ==================== Character Import Endpoints ====================

    /**
     * Upload a file to a specific endpoint
     * @param {string} endpoint - API endpoint
     * @param {File} file - File to upload
     */
    async uploadFile(endpoint, file) {
        const formData = new FormData();
        formData.append('file', file);

        const url = `${this.baseUrl}${endpoint}`;

        if (CONFIG.DEBUG) {
            console.log(`[API] Uploading file to ${url}:`, file.name);
        }

        try {
            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                // Don't set Content-Type - browser will set it with boundary
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new APIError(
                    errorData.detail || `HTTP ${response.status}`,
                    response.status,
                    errorData
                );
            }

            const data = await response.json();

            if (CONFIG.DEBUG) {
                console.log(`[API] Upload response:`, data);
            }

            return data;
        } catch (error) {
            if (error instanceof APIError) {
                throw error;
            }
            throw new APIError(`Upload error: ${error.message}`, 0, null);
        }
    }

    /**
     * Import character from PDF file
     * @param {File} file - PDF file containing D&D Beyond character sheet
     */
    async importCharacterPDF(file) {
        return this.uploadFile('/character/import/pdf', file);
    }

    /**
     * Import character from JSON file
     * @param {File} file - JSON file with character data
     */
    async importCharacterJSON(file) {
        return this.uploadFile('/character/import/json', file);
    }

    /**
     * List all imported characters
     */
    async listCharacters() {
        return this.get('/character/list');
    }

    /**
     * Get a specific imported character
     * @param {string} characterId - UUID of the character
     */
    async getCharacter(characterId) {
        return this.get(`/character/${characterId}`);
    }

    /**
     * Get combatant format for a character
     * @param {string} characterId - UUID of the character
     */
    async getCharacterCombatant(characterId) {
        return this.get(`/character/${characterId}/combatant`);
    }

    /**
     * Delete an imported character
     * @param {string} characterId - UUID of the character
     */
    async deleteCharacter(characterId) {
        return this.delete(`/character/${characterId}`);
    }

    /**
     * Create a demo character for testing
     */
    async createDemoCharacter() {
        return this.post('/character/demo', {});
    }

    // ==================== Campaign Endpoints ====================

    /**
     * Get list of available campaigns
     */
    async listCampaigns() {
        return this.get('/campaign/list');
    }

    /**
     * Get campaign details
     * @param {string} campaignId - Campaign ID
     */
    async getCampaign(campaignId) {
        return this.get(`/campaign/${campaignId}`);
    }

    /**
     * Import a campaign from JSON data
     * @param {Object} campaignData - Campaign JSON data
     */
    async importCampaign(campaignData) {
        return this.post('/campaign/import', campaignData);
    }

    /**
     * Create a new game session
     * @param {string} campaignId - Campaign to play
     * @param {Array} party - Array of party member data
     */
    async createSession(campaignId, party) {
        return this.post('/campaign/session/create', {
            campaign_id: campaignId,
            party: party,
        });
    }

    /**
     * Get current session state
     * @param {string} sessionId - Session ID
     */
    async getSessionState(sessionId) {
        return this.get(`/campaign/session/${sessionId}/state`);
    }

    /**
     * Advance the campaign state
     * @param {string} sessionId - Session ID
     * @param {string} action - Action to take (start_campaign, continue, etc.)
     * @param {Object} data - Optional action data
     */
    async advanceSession(sessionId, action, data = null) {
        return this.post(`/campaign/session/${sessionId}/advance`, {
            action: action,
            data: data,
        });
    }

    /**
     * Take a rest (short or long)
     * @param {string} sessionId - Session ID
     * @param {string} restType - "short" or "long"
     */
    async takeRest(sessionId, restType = 'short') {
        return this.post(`/campaign/session/${sessionId}/rest?rest_type=${restType}`, {});
    }

    /**
     * Save the current game
     * @param {string} sessionId - Session ID
     * @param {number} slot - Save slot (0-9)
     * @param {string} name - Save name
     */
    async saveGame(sessionId, slot, name) {
        return this.post(`/campaign/session/${sessionId}/save`, {
            slot: slot,
            name: name,
        });
    }

    /**
     * List saved games
     */
    async listSaves() {
        return this.get('/campaign/saves');
    }

    /**
     * Load a saved game
     * @param {string} saveId - Save ID
     */
    async loadSave(saveId) {
        return this.post('/campaign/saves/load', {
            save_id: saveId,
        });
    }

    /**
     * Delete a saved game
     * @param {string} saveId - Save ID
     */
    async deleteSave(saveId) {
        return this.delete(`/campaign/saves/${saveId}`);
    }

    /**
     * Get combat state for current session
     * @param {string} sessionId - Session ID
     */
    async getSessionCombat(sessionId) {
        return this.get(`/campaign/session/${sessionId}/combat`);
    }

    /**
     * End combat and return to campaign flow
     * @param {string} sessionId - Session ID
     * @param {boolean} victory - Whether the player won
     */
    async endSessionCombat(sessionId, victory) {
        return this.post(`/campaign/session/${sessionId}/combat/end?victory=${victory}`, {});
    }

    // ==================== Spell Endpoints ====================

    /**
     * Get list of spells with optional filtering
     * @param {Object} filters - Filter options (level, school, className, ritual, concentration, search)
     */
    async getSpells(filters = {}) {
        const params = new URLSearchParams();
        if (filters.level !== undefined) params.append('level', filters.level);
        if (filters.school) params.append('school', filters.school);
        if (filters.className) params.append('class_name', filters.className);
        if (filters.ritual !== undefined) params.append('ritual', filters.ritual);
        if (filters.concentration !== undefined) params.append('concentration', filters.concentration);
        if (filters.search) params.append('search', filters.search);

        const queryString = params.toString();
        return this.get(`/spells${queryString ? `?${queryString}` : ''}`);
    }

    /**
     * Get a specific spell by ID
     * @param {string} spellId - Spell ID
     */
    async getSpell(spellId) {
        return this.get(`/spells/${spellId}`);
    }

    /**
     * Get spells available to a specific class
     * @param {string} className - Class name (wizard, cleric, etc.)
     * @param {number} maxLevel - Maximum spell level to include
     */
    async getClassSpells(className, maxLevel = 9) {
        return this.get(`/spells/class/${className}?max_level=${maxLevel}`);
    }

    /**
     * Get character's spell information (cantrips, prepared, slots)
     * @param {string} characterId - Character ID
     * @param {string} combatId - Optional combat ID for current slot usage
     */
    async getCharacterSpells(characterId, combatId = null) {
        let url = `/spells/character/${characterId}/spells`;
        if (combatId) {
            url += `?combat_id=${combatId}`;
        }
        return this.get(url);
    }

    /**
     * Get spells the character can currently cast (has slots, prepared, etc.)
     * @param {string} characterId - Character ID
     * @param {string} combatId - Optional combat ID for current state
     */
    async getAvailableSpells(characterId, combatId = null) {
        let url = `/spells/character/${characterId}/available`;
        if (combatId) {
            url += `?combat_id=${combatId}`;
        }
        return this.get(url);
    }

    /**
     * Prepare spells for a character (for prepared casters like Wizard, Cleric)
     * @param {string} characterId - Character ID
     * @param {Array<string>} spellIds - Array of spell IDs to prepare
     */
    async prepareSpells(characterId, spellIds) {
        return this.post(`/spells/character/${characterId}/prepare`, {
            spell_ids: spellIds,
        });
    }

    /**
     * Cast a spell in combat
     * @param {string} combatId - Combat session ID
     * @param {string} casterId - ID of the caster
     * @param {string} spellId - ID of the spell to cast
     * @param {number} slotLevel - Spell slot level to use (null for cantrips)
     * @param {Array<string>} targetIds - Array of target IDs
     * @param {Object} targetPoint - Optional {x, y} for area spells
     */
    async castSpell(combatId, casterId, spellId, slotLevel = null, targetIds = [], targetPoint = null) {
        return this.post(`/spells/combat/${combatId}/cast`, {
            caster_id: casterId,
            spell_id: spellId,
            slot_level: slotLevel,
            target_ids: targetIds,
            target_point: targetPoint,
        });
    }

    /**
     * Get valid targets for a spell
     * @param {string} combatId - Combat session ID
     * @param {string} spellId - Spell ID
     * @param {string} casterId - Caster ID
     */
    async getSpellTargets(combatId, spellId, casterId) {
        return this.get(`/spells/combat/${combatId}/valid-targets/${spellId}?caster_id=${casterId}`);
    }

    /**
     * Make a concentration check after taking damage
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - ID of the combatant concentrating
     * @param {number} damage - Damage taken
     */
    async concentrationCheck(combatId, combatantId, damage) {
        return this.post(`/spells/combat/${combatId}/concentration-check`, {
            combatant_id: combatantId,
            damage: damage,
        });
    }

    // ==================== Character Creation Endpoints ====================

    /**
     * Get all available species for character creation
     */
    async getCreationSpecies() {
        return this.get('/creation/species');
    }

    /**
     * Get details for a specific species
     * @param {string} speciesId - Species ID
     */
    async getCreationSpeciesDetails(speciesId) {
        return this.get(`/creation/species/${speciesId}`);
    }

    /**
     * Get all available classes for character creation
     */
    async getCreationClasses() {
        return this.get('/creation/classes');
    }

    /**
     * Get details for a specific class
     * @param {string} classId - Class ID
     */
    async getCreationClassDetails(classId) {
        return this.get(`/creation/classes/${classId}`);
    }

    /**
     * Get class features at a specific level
     * @param {string} classId - Class ID
     * @param {number} level - Character level (1-20)
     */
    async getCreationClassFeatures(classId, level = 1) {
        return this.get(`/creation/classes/${classId}/features?level=${level}`);
    }

    /**
     * Get starting equipment choices for a class
     * @param {string} classId - Class ID
     */
    async getCreationClassEquipment(classId) {
        return this.get(`/creation/classes/${classId}/equipment`);
    }

    /**
     * Get all available backgrounds for character creation
     */
    async getCreationBackgrounds() {
        return this.get('/creation/backgrounds');
    }

    /**
     * Get details for a specific background
     * @param {string} backgroundId - Background ID
     */
    async getCreationBackgroundDetails(backgroundId) {
        return this.get(`/creation/backgrounds/${backgroundId}`);
    }

    /**
     * Get all origin feats
     */
    async getCreationOriginFeats() {
        return this.get('/creation/feats/origin');
    }

    /**
     * Get all general feats
     */
    async getCreationGeneralFeats() {
        return this.get('/creation/feats/general');
    }

    /**
     * Get details for a specific feat
     * @param {string} featId - Feat ID
     */
    async getCreationFeatDetails(featId) {
        return this.get(`/creation/feats/${featId}`);
    }

    /**
     * Get point buy rules and costs
     */
    async getCreationPointBuyInfo() {
        return this.get('/creation/ability-scores/point-buy');
    }

    /**
     * Get standard array values
     */
    async getCreationStandardArray() {
        return this.get('/creation/ability-scores/standard-array');
    }

    /**
     * Start a new character build
     */
    async createNewBuild() {
        return this.post('/creation/build/new', {});
    }

    /**
     * Get current state of a build
     * @param {string} buildId - Build ID
     */
    async getBuild(buildId) {
        return this.get(`/creation/build/${buildId}`);
    }

    /**
     * Delete a character build
     * @param {string} buildId - Build ID
     */
    async deleteBuild(buildId) {
        return this.delete(`/creation/build/${buildId}`);
    }

    /**
     * Set species for a character build
     * @param {string} buildId - Build ID
     * @param {string} speciesId - Species ID
     * @param {string} size - Optional size choice for species with size options
     */
    async setBuildSpecies(buildId, speciesId, size = null) {
        const data = { build_id: buildId, species_id: speciesId };
        if (size) data.size = size;
        return this.post('/creation/build/species', data);
    }

    /**
     * Set class for a character build
     * @param {string} buildId - Build ID
     * @param {string} classId - Class ID
     * @param {Array<string>} skillChoices - Optional skill proficiency choices
     */
    async setBuildClass(buildId, classId, skillChoices = null) {
        const data = { build_id: buildId, class_id: classId };
        if (skillChoices) data.skill_choices = skillChoices;
        return this.post('/creation/build/class', data);
    }

    /**
     * Set background for a character build
     * @param {string} buildId - Build ID
     * @param {string} backgroundId - Background ID
     */
    async setBuildBackground(buildId, backgroundId) {
        return this.post('/creation/build/background', {
            build_id: buildId,
            background_id: backgroundId,
        });
    }

    /**
     * Set ability scores and background bonuses
     * @param {string} buildId - Build ID
     * @param {Object} scores - Base ability scores {strength: 10, dexterity: 14, ...}
     * @param {string} method - "point_buy" or "standard_array"
     * @param {Object} bonuses - Background bonuses {strength: 2, dexterity: 1, ...}
     */
    async setBuildAbilities(buildId, scores, method, bonuses) {
        return this.post('/creation/build/abilities', {
            build_id: buildId,
            scores: scores,
            method: method,
            bonuses: bonuses,
        });
    }

    /**
     * Set origin feat for a character build
     * @param {string} buildId - Build ID
     * @param {string} featId - Feat ID
     */
    async setBuildFeat(buildId, featId) {
        return this.post('/creation/build/feat', {
            build_id: buildId,
            feat_id: featId,
        });
    }

    /**
     * Set equipment choices for a character build
     * @param {string} buildId - Build ID
     * @param {Array} choices - Equipment choice selections
     */
    async setBuildEquipment(buildId, choices) {
        return this.post('/creation/build/equipment', {
            build_id: buildId,
            choices: choices,
        });
    }

    /**
     * Set fighting style for applicable classes
     * @param {string} buildId - Build ID
     * @param {string} styleId - Fighting style ID
     */
    async setBuildFightingStyle(buildId, styleId) {
        return this.post('/creation/build/fighting-style', {
            build_id: buildId,
            style_id: styleId,
        });
    }

    /**
     * Set weapon mastery choices
     * @param {string} buildId - Build ID
     * @param {Array<string>} weapons - Weapon IDs for mastery
     */
    async setBuildWeaponMasteries(buildId, weapons) {
        return this.post('/creation/build/weapon-masteries', {
            build_id: buildId,
            weapons: weapons,
        });
    }

    /**
     * Set character details (name, appearance, etc.)
     * @param {string} buildId - Build ID
     * @param {string} name - Character name
     * @param {string} appearance - Optional appearance description
     * @param {string} personality - Optional personality description
     * @param {string} backstory - Optional backstory
     */
    async setBuildDetails(buildId, name, appearance = null, personality = null, backstory = null) {
        const data = { build_id: buildId, name: name };
        if (appearance) data.appearance = appearance;
        if (personality) data.personality = personality;
        if (backstory) data.backstory = backstory;
        return this.post('/creation/build/details', data);
    }

    /**
     * Validate the current build state
     * @param {string} buildId - Build ID
     */
    async validateBuild(buildId) {
        return this.get(`/creation/build/${buildId}/validate`);
    }

    /**
     * Preview what the finalized character would look like
     * @param {string} buildId - Build ID
     */
    async previewBuild(buildId) {
        return this.get(`/creation/build/${buildId}/preview`);
    }

    /**
     * Finalize the build and create the character
     * @param {string} buildId - Build ID
     */
    async finalizeBuild(buildId) {
        return this.post(`/creation/build/${buildId}/finalize`, {});
    }

    // ==================== Loot Endpoints ====================

    /**
     * Generate loot for defeated enemies
     * @param {Array} enemies - Array of defeated enemies with {name, cr}
     * @param {string} difficulty - Encounter difficulty: easy, medium, hard, deadly
     * @param {boolean} isBoss - Whether this is a boss encounter (generates hoard treasure)
     * @returns {Promise<Object>} Generated loot with coins, gems, art_objects, magic_items
     */
    async generateLoot(enemies, difficulty = 'medium', isBoss = false) {
        return this.post('/loot/generate', {
            enemies: enemies,
            difficulty: difficulty,
            is_boss: isBoss,
        });
    }

    /**
     * Get loot from a completed combat
     * @param {string} combatId - Combat ID
     */
    async getCombatLoot(combatId) {
        return this.get(`/loot/combat/${combatId}`);
    }

    /**
     * Collect loot from a combat
     * @param {string} combatId - Combat ID
     * @param {string} characterId - Character collecting the loot
     * @param {Array} itemIds - Specific item IDs to collect (empty = all)
     * @param {boolean} takeCoins - Whether to take coins
     */
    async collectLoot(combatId, characterId, itemIds = [], takeCoins = true) {
        return this.post(`/loot/combat/${combatId}/collect`, {
            character_id: characterId,
            item_ids: itemIds,
            take_coins: takeCoins,
        });
    }

    /**
     * Distribute loot among party members
     * @param {string} combatId - Combat ID
     * @param {Object} distribution - Map of character_id -> item IDs
     * @param {Object} coinSplit - Map of character_id -> percentage
     */
    async distributeLoot(combatId, distribution, coinSplit = {}) {
        return this.post(`/loot/combat/${combatId}/distribute`, {
            distribution,
            coin_split: coinSplit,
        });
    }

    /**
     * Preview possible loot for a CR
     * @param {number} cr - Challenge Rating
     * @param {string} treasureType - 'individual' or 'hoard'
     */
    async previewLoot(cr, treasureType = 'individual') {
        return this.get(`/loot/preview/${cr}?treasure_type=${treasureType}`);
    }

    // ==================== Items & Consumables ====================

    /**
     * Give an item to a character
     * @param {string} characterId - Character ID
     * @param {string} itemId - Item ID (e.g., 'potion_of_healing')
     * @param {number} quantity - Number of items to give
     */
    async giveItem(characterId, itemId, quantity = 1) {
        return this.post('/loot/give-item', {
            character_id: characterId,
            item_id: itemId,
            quantity: quantity,
        });
    }

    /**
     * Use a consumable item in combat
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Combatant using the item
     * @param {string} itemId - Item ID to use
     * @param {string} targetId - Optional target ID
     */
    async useItem(combatId, combatantId, itemId, targetId = null) {
        return this.post('/loot/use-item', {
            combat_id: combatId,
            combatant_id: combatantId,
            item_id: itemId,
            target_id: targetId,
        });
    }

    /**
     * Drop an item on the ground
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Combatant dropping the item
     * @param {string} itemId - Item ID to drop
     * @param {Array} position - Optional [x, y] position to drop at
     */
    async dropItem(combatId, combatantId, itemId, position = null) {
        return this.post(`/loot/${combatId}/drop`, {
            combatant_id: combatantId,
            item_id: itemId,
            position: position,
        });
    }

    /**
     * Pick up item(s) from the ground
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Combatant picking up items
     * @param {Array} position - Optional [x, y] position to pick up from
     * @param {string} itemId - Optional specific item ID to pick up
     */
    async pickupItem(combatId, combatantId, position = null, itemId = null) {
        return this.post(`/loot/${combatId}/pickup`, {
            combatant_id: combatantId,
            position: position,
            item_id: itemId,
        });
    }

    /**
     * Get all ground items for a combat
     * @param {string} combatId - Combat session ID
     */
    async getGroundItems(combatId) {
        return this.get(`/loot/${combatId}/ground-items`);
    }

    // ==================== Shop ====================

    /**
     * Get list of available shops
     */
    async getShops() {
        return this.get('/shop/');
    }

    /**
     * Get a specific shop's inventory
     * @param {string} shopId - Shop ID
     */
    async getShop(shopId) {
        return this.get(`/shop/${shopId}`);
    }

    /**
     * Buy an item from a shop
     * @param {string} shopId - Shop ID
     * @param {string} itemId - Item to buy
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Buyer's combatant ID
     * @param {number} quantity - Number to buy
     */
    async buyItem(shopId, itemId, combatId, combatantId, quantity = 1) {
        return this.post('/shop/buy', {
            shop_id: shopId,
            item_id: itemId,
            combat_id: combatId,
            combatant_id: combatantId,
            quantity,
        });
    }

    /**
     * Sell an item to a shop
     * @param {string} shopId - Shop ID
     * @param {string} itemId - Item to sell
     * @param {string} combatId - Combat session ID
     * @param {string} combatantId - Seller's combatant ID
     * @param {number} quantity - Number to sell
     */
    async sellItem(shopId, itemId, combatId, combatantId, quantity = 1) {
        return this.post('/shop/sell', {
            shop_id: shopId,
            item_id: itemId,
            combat_id: combatId,
            combatant_id: combatantId,
            quantity,
        });
    }

    // ==================== Health Check ====================

    /**
     * Check API health
     */
    async healthCheck() {
        return this.get('/health');
    }
}

/**
 * Custom error class for API errors
 */
class APIError extends Error {
    constructor(message, status, data) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.data = data;
    }
}

// Export singleton instance
export const api = new APIClient();
export { APIClient, APIError };
export default api;
