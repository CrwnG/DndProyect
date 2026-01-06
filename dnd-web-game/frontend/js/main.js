/**
 * D&D Combat Engine - Main Entry Point
 * Initializes all game components and starts the application
 */

import { CONFIG } from './config.js';
import { eventBus, EVENTS } from './engine/event-bus.js';
import state from './engine/state-manager.js';
import api from './api/api-client.js';
import CombatGrid from './combat/combat-grid.js';
import MovementHandler from './combat/movement-handler.js';
import CharacterPanel from './ui/character-panel.js';
import InitiativeTracker from './ui/initiative-tracker.js';
import ActionBar from './ui/action-bar.js';
import { characterImportUI } from './ui/character-import.js';
import { campaignMenu } from './ui/campaign-menu.js';
import { storyDisplay } from './ui/story-display.js';
import { choiceDisplay } from './ui/choice-display.js';
import { inventoryModal } from './ui/inventory-modal.js';
import lootModal from './ui/loot-modal.js';
import { victoryScreen } from './ui/victory-screen.js';
import characterCreationWizard from './ui/character-creation/creation-wizard.js';
import { equipmentManager } from './equipment/equipment-manager.js';
import { legendaryActionsPanel } from './ui/legendary-actions.js';
import { wildShapeModal } from './ui/wild-shape-modal.js';
import { layOnHandsModal } from './ui/lay-on-hands-modal.js';
import { kiModal } from './ui/ki-modal.js';
import { channelDivinityModal } from './ui/channel-divinity-modal.js';
import { bardicInspirationModal } from './ui/bardic-inspiration-modal.js';
import { metamagicModal } from './ui/metamagic-modal.js';
import { reactionPrompt } from './ui/reaction-prompt.js';

class Game {
    constructor() {
        this.combatGrid = null;
        this.movementHandler = null;
        this.characterPanel = null;
        this.initiativeTracker = null;
        this.actionBar = null;

        // Campaign components
        this.campaignMenu = campaignMenu;
        this.storyDisplay = storyDisplay;
        this.choiceDisplay = choiceDisplay;
        this.currentSessionId = null;

        // Equipment/Inventory
        this.inventoryModal = inventoryModal;

        // Loot/Treasure
        this.lootModal = lootModal;

        // Victory Screen
        this.victoryScreen = victoryScreen;

        // Legendary Actions Panel
        this.legendaryActionsPanel = legendaryActionsPanel;

        // Wild Shape Modal
        this.wildShapeModal = wildShapeModal;

        // Lay on Hands Modal
        this.layOnHandsModal = layOnHandsModal;

        // Ki Powers Modal
        this.kiModal = kiModal;

        // Channel Divinity Modal
        this.channelDivinityModal = channelDivinityModal;

        // Bardic Inspiration Modal
        this.bardicInspirationModal = bardicInspirationModal;

        // Metamagic Modal
        this.metamagicModal = metamagicModal;

        // Reaction Prompt
        this.reactionPrompt = reactionPrompt;

        // Duplicate event prevention flags
        this._combatEndHandled = false;

        this.initialized = false;
        this.importedCharacter = null;  // Store imported character for combat
    }

    /**
     * Initialize the game
     */
    async init() {
        console.log('[Game] Initializing D&D Combat Engine...');

        try {
            // Check API health
            await this.checkAPIHealth();

            // Initialize components
            this.initComponents();

            // Set up global event handlers
            this.setupGlobalEvents();

            // Set up campaign event handlers
            this.setupCampaignEvents();

            // Show campaign menu on startup
            this.campaignMenu.show();

            this.initialized = true;
            console.log('[Game] Initialization complete!');
        } catch (error) {
            console.error('[Game] Initialization failed:', error);
            this.showError('Failed to initialize game. Is the server running?');
        }
    }

    /**
     * Check API health
     */
    async checkAPIHealth() {
        try {
            const health = await api.healthCheck();
            console.log('[Game] API Health:', health);

            if (!health || health.status !== 'healthy') {
                throw new Error('API not healthy');
            }
        } catch (error) {
            console.warn('[Game] API health check failed, continuing in offline mode');
            // Continue anyway for offline testing
        }
    }

    /**
     * Initialize game components
     */
    initComponents() {
        console.log('[Game] Initializing components...');

        // Combat grid (canvas)
        this.combatGrid = new CombatGrid('combat-grid');

        // Movement handler
        this.movementHandler = new MovementHandler();

        // UI components
        this.characterPanel = new CharacterPanel();
        this.initiativeTracker = new InitiativeTracker();
        this.actionBar = new ActionBar();

        console.log('[Game] Components initialized');
    }

    /**
     * Set up global event handlers
     */
    setupGlobalEvents() {
        // Combat events
        eventBus.on(EVENTS.COMBAT_STARTED, (data) => {
            console.log('[Game] Combat started:', data);
            this.updateCombatLog('Combat has begun!');
            // Reset duplicate prevention flag for new combat
            this._combatEndHandled = false;
        });

        eventBus.on(EVENTS.COMBAT_ENDED, async (data) => {
            console.log('[Game] Combat ended:', data);

            // Prevent duplicate handling (can be triggered by both checkCombatOver and handleEndTurn)
            if (this._combatEndHandled) {
                console.log('[Game] Combat end already handled, skipping duplicate');
                return;
            }
            this._combatEndHandled = true;

            this.updateCombatLog('Combat ended!');

            // If this was a campaign combat, handle victory/defeat
            if (this.currentSessionId) {
                const isVictory = data.result === 'victory';

                try {
                    // Call endSessionCombat to trigger XP/loot calculation and get combat summary
                    console.log('[Game] Calling endSessionCombat to get combat summary...');
                    const response = await api.endSessionCombat(this.currentSessionId, isVictory);
                    console.log('[Game] Combat end response:', response);

                    if (isVictory && response.combat_summary) {
                        // Show victory screen with combat summary
                        console.log('[Game] Showing victory screen with summary:', response.combat_summary);

                        // Get player character data for XP display
                        const currentState = state.getState();
                        const playerData = currentState.combatants ?
                            Object.values(currentState.combatants).find(c => c.isPlayer) : null;

                        this.victoryScreen.show(response.combat_summary, playerData);

                        // Listen for victory screen dismiss to continue campaign
                        const handleDismiss = async () => {
                            eventBus.off(EVENTS.VICTORY_DISMISSED, handleDismiss);

                            // Auto-collect loot for party before advancing
                            const combatId = response.combat_summary?.combat_id || state.get('combat.id');
                            const playerIds = state.getState().playerIds || [];
                            const firstPlayerId = playerIds[0];

                            if (combatId && firstPlayerId && response.combat_summary?.loot) {
                                try {
                                    console.log('[Game] Auto-collecting loot for party...');
                                    // Pass all party member IDs for gold division
                                    await api.collectLoot(combatId, firstPlayerId, [], true, playerIds);
                                    console.log('[Game] Loot collected successfully');
                                } catch (e) {
                                    console.warn('[Game] Loot collection failed (may already be collected):', e);
                                }
                            }

                            console.log('[Game] Victory screen dismissed, advancing campaign...');
                            await this.advanceCampaign('continue');
                        };
                        eventBus.on(EVENTS.VICTORY_DISMISSED, handleDismiss);

                    } else if (data.result === 'defeat') {
                        this.showNotification('Defeat...', 'error');
                        setTimeout(async () => {
                            console.log('[Game] Advancing campaign after defeat...');
                            await this.advanceCampaign('continue');
                        }, 1500);
                    } else {
                        // Fallback: just advance
                        await this.advanceCampaign('continue');
                    }
                } catch (error) {
                    console.error('[Game] Failed to end combat:', error);
                    this.showError('Failed to process combat end');
                    // Try to advance anyway
                    await this.advanceCampaign('continue');
                }
            }
            // Quick Combat (no session) - show victory screen with real loot from API
            else if (data.result === 'victory') {
                console.log('[Game] Quick Combat victory - generating real loot');

                // Build combat summary from combat state
                const currentState = state.getState();
                const combatants = currentState.combatants ? Object.values(currentState.combatants) : [];

                // Get defeated enemies with CR data
                const defeatedEnemies = combatants
                    .filter(c => !c.isPlayer && !c.isActive)
                    .map(c => ({
                        name: c.name,
                        cr: c.stats?.cr || c.stats?.challenge_rating || 0.25,
                    }));

                // Calculate XP
                const totalXP = defeatedEnemies.reduce((sum, e) => sum + this.getXPForCR(e.cr), 0);

                // Call loot API for real treasure generation (DMG tables)
                let loot = { coins: {}, gems: [], art_objects: [], magic_items: [], mundane_items: [] };
                try {
                    const isBossEncounter = defeatedEnemies.length === 1 && defeatedEnemies[0].cr >= 5;
                    const result = await api.generateLoot(defeatedEnemies, 'medium', isBossEncounter);
                    loot = result.loot || loot;
                    console.log('[Game] Generated loot from DMG tables:', loot);
                } catch (e) {
                    console.warn('[Game] Loot API failed, using empty loot:', e);
                }

                const combatSummary = {
                    combat_id: currentState.combat?.id || 'quick-combat',
                    enemies_defeated: defeatedEnemies.map(e => ({
                        ...e,
                        xp: this.getXPForCR(e.cr)
                    })),
                    xp_earned: totalXP,
                    xp_per_player: totalXP,
                    level_ups: [],
                    loot: loot
                };

                const playerData = combatants.find(c => c.isPlayer);
                this.victoryScreen.show(combatSummary, playerData);
            }
        });

        // Turn events
        eventBus.on(EVENTS.TURN_STARTED, (data) => {
            const combatant = state.getState().combatants[data.combatantId];
            if (combatant) {
                this.updateCombatLog(`${combatant.name}'s turn`);
            }
        });

        // Attack events
        eventBus.on(EVENTS.ATTACK_RESOLVED, (data) => {
            if (data.hit) {
                const target = state.getState().combatants[data.targetId];
                if (target) {
                    const pos = state.getState().grid.positions[data.targetId];
                    if (pos) {
                        this.combatGrid.showDamageNumber(pos.x, pos.y, data.damage, data.critical);
                        this.combatGrid.showAttackFlash(pos.x, pos.y);
                    }
                }
            }
        });

        // Error events
        eventBus.on(EVENTS.ERROR_OCCURRED, (error) => {
            console.error('[Game] Error:', error);
            this.showError(error.message || 'An error occurred');
        });

        // Log entries
        eventBus.on(EVENTS.UI_LOG_ENTRY, (entry) => {
            this.updateCombatLog(entry.message, entry.type);
        });

        // Character import events
        eventBus.on(EVENTS.CHARACTER_IMPORTED, (data) => {
            console.log('[Game] Character imported:', data);
            this.importedCharacter = data;

            // Show success notification
            this.showNotification(`Imported: ${data.character.name} (${data.character.class || 'Unknown'} ${data.character.level || 1})`, 'success');
            this.updateCombatLog(`Imported character: ${data.character.name}`);

            // Update start combat button to show imported character
            const startBtn = document.getElementById('btn-start-combat');
            if (startBtn) {
                startBtn.innerHTML = `<span class="action-icon">⚔️</span><span class="action-label">Start Combat with ${data.character.name}</span>`;
                startBtn.classList.add('has-import');
            }
        });

        // Import button click
        const importBtn = document.getElementById('btn-import-character');
        if (importBtn) {
            importBtn.addEventListener('click', () => {
                characterImportUI.show();
            });
        }

        // Inventory button click
        const inventoryBtn = document.getElementById('btn-inventory');
        if (inventoryBtn) {
            inventoryBtn.addEventListener('click', () => {
                this.inventoryModal.toggle();
            });
        }

        // Create Character button click
        const createBtn = document.getElementById('btn-create-character');
        if (createBtn) {
            createBtn.addEventListener('click', () => {
                characterCreationWizard.show();
            });
        }

        // Import modal close button
        const importClose = document.getElementById('import-close');
        if (importClose) {
            importClose.addEventListener('click', () => {
                characterImportUI.hide();
            });
        }

        // Drop zone click to trigger file input
        const dropZone = document.getElementById('file-drop-zone');
        const fileInput = document.getElementById('character-file');
        if (dropZone && fileInput) {
            dropZone.addEventListener('click', () => {
                fileInput.click();
            });
        }
    }

    /**
     * Set up campaign event handlers
     */
    setupCampaignEvents() {
        // Campaign started - load story intro
        eventBus.on(EVENTS.CAMPAIGN_STARTED, async (data) => {
            console.log('[Game] Campaign started:', data);
            this.currentSessionId = data.sessionId;
            state.set('session.id', data.sessionId);

            // Verify session.id was set
            console.log('[Game] Session ID set to:', data.sessionId);
            console.log('[Game] Verifying state.get("session.id"):', state.get('session.id'));
            console.log('[Game] Full session object:', state.get('session'));

            // Advance to start and show first encounter
            await this.advanceCampaign('start_campaign');
        });

        // Campaign continued from save
        eventBus.on(EVENTS.CAMPAIGN_CONTINUED, async (data) => {
            console.log('[Game] Campaign continued:', data);
            this.currentSessionId = data.sessionId;
            state.set('session.id', data.sessionId);
            await this.refreshCampaignState();
        });

        // Campaign loaded from save
        eventBus.on(EVENTS.CAMPAIGN_LOADED, async (data) => {
            console.log('[Game] Campaign loaded:', data);
            this.currentSessionId = data.sessionId;
            state.set('session.id', data.sessionId);
            await this.handleCampaignState(data.state);
        });

        // Quick combat requested (skip campaign, go straight to demo)
        eventBus.on(EVENTS.QUICK_COMBAT_REQUESTED, async () => {
            console.log('[Game] Quick combat requested');
            await this.loadDemoCombat();
        });

        // Open character import from campaign menu
        eventBus.on(EVENTS.OPEN_CHARACTER_IMPORT, () => {
            characterImportUI.show();
        });

        // Campaign state changed (from choice-display, etc.)
        eventBus.on(EVENTS.CAMPAIGN_STATE_CHANGED, async (campaignState) => {
            console.log('[Game] Campaign state changed:', campaignState);
            await this.handleCampaignState(campaignState);
        });
    }

    /**
     * Advance campaign state
     */
    async advanceCampaign(action, data = null) {
        if (!this.currentSessionId) return;

        try {
            const response = await api.advanceSession(this.currentSessionId, action, data);
            if (response.success) {
                await this.handleCampaignState(response.state);

                // Handle extra data (combat state, etc.)
                if (response.extra) {
                    if (response.extra.combat_state) {
                        await this.handleCombatStart(response.extra);
                    }
                }
            }
        } catch (error) {
            console.error('[Game] Failed to advance campaign:', error);
            this.showError('Failed to advance campaign');
        }
    }

    /**
     * Refresh campaign state from server
     */
    async refreshCampaignState() {
        if (!this.currentSessionId) return;

        try {
            const response = await api.getSessionState(this.currentSessionId);
            await this.handleCampaignState(response.state);
        } catch (error) {
            console.error('[Game] Failed to refresh campaign state:', error);
        }
    }

    /**
     * Handle campaign state changes
     */
    async handleCampaignState(campaignState) {
        console.log('[Game] Handling campaign state:', campaignState);

        const phase = campaignState.phase;

        switch (phase) {
            case 'story_intro':
            case 'story_outcome':
                // Show story display
                this.storyDisplay.show({
                    title: campaignState.encounter_name,
                    text: campaignState.story_text || 'The adventure continues...',
                    buttonText: phase === 'story_intro' ? 'Begin' : 'Continue',
                    onContinue: async () => {
                        this.storyDisplay.hide();
                        if (phase === 'story_intro' && campaignState.encounter_type === 'combat') {
                            await this.advanceCampaign('start_combat');
                        } else if (phase === 'story_intro' && campaignState.encounter_type === 'choice') {
                            // Advance to show choices
                            await this.advanceCampaign('continue');
                        } else {
                            await this.advanceCampaign('continue');
                        }
                    },
                });
                break;

            case 'choice':
                // Show choice display with options - pass session ID directly
                this.choiceDisplay.show({
                    title: campaignState.encounter_name || 'Make Your Choice',
                    choices: campaignState.choices || [],
                    sessionId: this.currentSessionId,  // Pass explicitly
                });
                break;

            case 'choice_result':
                // Choice display handles its own result display
                // The choiceDisplay will call continue when ready
                break;

            case 'combat':
                // Combat is handled separately
                break;

            case 'combat_resolution':
                // Show victory summary then continue
                this.showNotification('Victory!', 'success');
                await this.advanceCampaign('continue');
                break;

            case 'rest':
                // Show rest options
                this.showRestOptions(campaignState);
                break;

            case 'game_over':
                this.storyDisplay.show({
                    title: 'Defeat',
                    text: campaignState.story_text || 'Your adventure ends here...',
                    buttonText: 'Return to Menu',
                    onContinue: () => {
                        this.storyDisplay.hide();
                        this.campaignMenu.show();
                    },
                });
                break;

            case 'victory':
                this.storyDisplay.show({
                    title: 'Campaign Complete!',
                    text: campaignState.story_text || 'Congratulations! You have completed the campaign.',
                    buttonText: 'Return to Menu',
                    onContinue: () => {
                        this.storyDisplay.hide();
                        this.campaignMenu.show();
                    },
                });
                break;

            case 'menu':
                this.campaignMenu.show();
                break;
        }
    }

    /**
     * Handle combat start from campaign
     */
    async handleCombatStart(combatData) {
        console.log('[Game] Starting combat from campaign:', combatData);

        if (combatData.combat_state) {
            // Find ALL player IDs from combatants (check both type and combatant_type)
            const combatants = combatData.combat_state.combatants || [];
            console.log('[Game] Combat combatants:', combatants.map(c => ({
                id: c.id, name: c.name, type: c.type, combatant_type: c.combatant_type
            })));

            // Get ALL player-controlled characters, not just the first one
            const players = combatants.filter(c => c.type === 'player' || c.combatant_type === 'player');
            const playerIds = players.map(p => p.id);

            if (playerIds.length > 0) {
                // CRITICAL: Set playerIds BEFORE initCombat so isPlayerTurn() works
                state.set('playerIds', playerIds);
                console.log('[Game] Set playerIds to:', playerIds);
            } else {
                console.warn('[Game] No players found in combatants!', combatants);
            }

            // Add combat_id to combat_state if provided at top level
            if (combatData.combat_id && !combatData.combat_state.combat_id) {
                combatData.combat_state.combat_id = combatData.combat_id;
            }

            // Initialize combat state
            state.initCombat(combatData.combat_state);
            this.updateCombatLog('Combat has begun!');

            // Show dramatic combat announcement
            this.showCombatAnnouncement('COMBAT!');

            // If it's not the player's turn, process enemy turns until it is
            if (!state.isPlayerTurn()) {
                console.log('[Game] Not player turn - processing initial enemy turns...');
                await this.processInitialEnemyTurns();
            }

            // CRITICAL: Emit TURN_STARTED for the current player so movement handler
            // fetches reachable cells and enables first-turn movement
            if (state.isPlayerTurn()) {
                const currentCombatant = state.getCurrentCombatant();
                console.log('[Game] Emitting TURN_STARTED for player:', currentCombatant?.id);
                eventBus.emit(EVENTS.TURN_STARTED, { combatantId: currentCombatant?.id });
            }
        }
    }

    /**
     * Show rest options dialog
     */
    showRestOptions(campaignState) {
        // Simple rest UI - could be enhanced with a proper component
        this.storyDisplay.show({
            title: campaignState.encounter_name || 'Rest',
            text: campaignState.story_text || 'You find a moment to rest and recover.\n\nWould you like to take a short rest (1 hour) to recover some hit points, or skip and continue your journey?',
            buttonText: 'Short Rest',
            onContinue: async () => {
                this.storyDisplay.hide();
                try {
                    const response = await api.takeRest(this.currentSessionId, 'short');
                    if (response.success) {
                        this.showRestResults(response.rest_results);
                        await this.handleCampaignState(response.state);
                    }
                } catch (error) {
                    console.error('[Game] Rest failed:', error);
                }
            },
        });
    }

    /**
     * Show rest results notification
     */
    showRestResults(results) {
        if (!results || !results.members) return;

        for (const member of results.members) {
            const healed = member.restored?.hp_healed || 0;
            if (healed > 0) {
                this.showNotification(`${member.name} healed ${healed} HP`, 'success');
            }
        }
    }

    /**
     * Load a demo combat for testing
     */
    async loadDemoCombat() {
        console.log('[Game] Loading demo combat...');

        // Create demo players (using backend CombatantData format)
        // Phase 9 Test: Fighter Level 5 for Extra Attack, with multiple weapon options
        const demoPlayers = [
            {
                id: 'player-1',
                name: 'Thorin',
                hp: 44,
                max_hp: 44,
                ac: 18,
                dex_mod: 2,
                str_mod: 3,
                attack_bonus: 7,  // +3 STR + 3 Prof + 1 magic
                damage_dice: '1d8',
                damage_type: 'slashing',
                speed: 30,
                abilities: {
                    class: 'fighter',
                    level: 5,  // Level 5 = Extra Attack (2 attacks per action)
                    proficiency_bonus: 3,
                    weapon: { name: 'Longsword', mastery: 'Sap' },
                },
                // BG3-style equipment system with slots
                equipment: {
                    // Currently equipped (instant use)
                    main_hand: {
                        id: 'longsword', name: 'Longsword', damage: '1d8',
                        damage_type: 'slashing', weight: 3, properties: ['versatile'], icon: '⚔️'
                    },
                    off_hand: null,  // Empty for versatile grip or shield
                    ranged: {
                        id: 'longbow', name: 'Longbow', damage: '1d8',
                        damage_type: 'piercing', weight: 2, range: 150, long_range: 600,
                        properties: ['ammunition', 'heavy', 'two_handed'], icon: '🏹'
                    },
                    armor: {
                        id: 'chain_mail', name: 'Chain Mail', ac_bonus: 16, weight: 55, icon: '🛡️'
                    },
                    // Backpack inventory (requires object interaction to draw)
                    inventory: [
                        {
                            id: 'shortsword', name: 'Shortsword', damage: '1d6',
                            damage_type: 'piercing', weight: 2, properties: ['finesse', 'light'], icon: '🗡️'
                        },
                        {
                            id: 'dagger', name: 'Dagger', damage: '1d4',
                            damage_type: 'piercing', weight: 1, range: 20, long_range: 60,
                            properties: ['finesse', 'light', 'thrown'], icon: '🔪'
                        },
                        {
                            id: 'handaxe', name: 'Handaxe', damage: '1d6',
                            damage_type: 'slashing', weight: 2, range: 20, long_range: 60,
                            properties: ['light', 'thrown'], icon: '🪓'
                        },
                    ],
                    carrying_capacity: 195,  // STR 13 × 15
                    current_weight: 65,
                },
                stats: {
                    class: 'Fighter',
                    level: 5,
                    weapon: { name: 'Longsword', mastery: 'Sap' },
                },
            },
        ];

        // Create demo enemies
        const demoEnemies = [
            {
                id: 'enemy-1',
                name: 'Goblin A',
                hp: 7,
                max_hp: 7,
                ac: 15,
                dex_mod: 2,
                str_mod: -1,
                attack_bonus: 4,
                damage_dice: '1d6',
                damage_type: 'slashing',
                speed: 30,
            },
            {
                id: 'enemy-2',
                name: 'Goblin B',
                hp: 7,
                max_hp: 7,
                ac: 15,
                dex_mod: 2,
                str_mod: -1,
                attack_bonus: 4,
                damage_dice: '1d6',
                damage_type: 'slashing',
                speed: 30,
            },
            {
                id: 'enemy-3',
                name: 'Goblin C',
                hp: 7,
                max_hp: 7,
                ac: 15,
                dex_mod: 2,
                str_mod: -1,
                attack_bonus: 4,
                damage_dice: '1d6',
                damage_type: 'slashing',
                speed: 30,
            },
        ];

        // Obstacles as array of [x, y] coordinates
        const demoObstacles = [
            [0, 0], [0, 1], [0, 2], [0, 3], [0, 4],  // Left wall column
            [1, 0],                                    // Extra wall
            [1, 4], [2, 4],                            // Interior walls
        ];

        // Initial positions as {id: [x, y]}
        // Phase 9 Test positions:
        // - enemy-1: Far away (good for ranged attack test)
        // - enemy-2: Adjacent to player (opportunity attack test when moving away)
        // - enemy-3: Medium distance
        const demoPositions = {
            'player-1': [2, 2],
            'enemy-1': [7, 1],  // Far - ranged attack test
            'enemy-2': [3, 2],  // Adjacent - opportunity attack test
            'enemy-3': [5, 4],  // Medium distance
        };

        // Create demo grid for local state (8x8 with walls)
        const demoGrid = [];
        for (let y = 0; y < 8; y++) {
            const row = [];
            for (let x = 0; x < 8; x++) {
                const isWall = demoObstacles.some(obs => obs[0] === x && obs[1] === y);
                row.push({
                    blocked: isWall,
                    terrain: isWall ? 'wall' : 'normal',
                });
            }
            demoGrid.push(row);
        }

        // Combine all combatants for local state
        const allCombatants = [
            ...demoPlayers.map(p => ({ ...p, type: 'player', current_hp: p.hp, maxHp: p.max_hp })),
            ...demoEnemies.map(e => ({ ...e, type: 'enemy', current_hp: e.hp, maxHp: e.max_hp })),
        ];

        // Demo initiative order (pre-rolled)
        const demoInitiative = ['enemy-1', 'player-1', 'enemy-2', 'enemy-3'];

        // Set player IDs FIRST - BEFORE initCombat() so isPlayerTurn() works when subscribers are notified
        const demoPlayerIds = demoPlayers.map(p => p.id);
        state.set('playerIds', demoPlayerIds);
        console.log('[Game] playerIds set to:', demoPlayerIds);

        // Try to start combat via API
        try {
            const response = await api.startCombat(demoPlayers, demoEnemies, {
                gridWidth: 8,
                gridHeight: 8,
                obstacles: demoObstacles,
                initialPositions: demoPositions,
            });

            console.log('[Game] Combat started via API:', response);

            // Convert positions to {x, y} format for local state
            const positionsXY = {};
            for (const [id, pos] of Object.entries(demoPositions)) {
                positionsXY[id] = { x: pos[0], y: pos[1] };
            }

            // Initialize state from server response
            // Backend returns combatant_id, not id
            const initiativeOrder = response.initiative_order?.map(c => c.combatant_id) || demoInitiative;
            console.log('[Game] API response initiative_order:', response.initiative_order);
            console.log('[Game] Using initiative order:', initiativeOrder);

            // Use the server's current combatant to determine the actual turn index
            const serverCurrentId = response.current_combatant?.id;
            const serverTurnIndex = serverCurrentId
                ? initiativeOrder.indexOf(serverCurrentId)
                : 0;
            console.log('[Game] Server current combatant:', serverCurrentId);
            console.log('[Game] Server turn index:', serverTurnIndex);

            state.initCombat({
                combat_id: response.combat_id,
                round: 1,
                phase: 'in_combat',
                current_turn_index: serverTurnIndex >= 0 ? serverTurnIndex : 0, // Use SERVER's turn
                combatants: allCombatants,
                initiative_order: initiativeOrder,
                positions: positionsXY,
                grid: demoGrid,
            });

        } catch (error) {
            console.warn('[Game] API not available, using offline demo:', error.message);

            // Convert positions to {x, y} format for local state
            const positionsXY = {};
            for (const [id, pos] of Object.entries(demoPositions)) {
                positionsXY[id] = { x: pos[0], y: pos[1] };
            }

            console.log('[Game] Offline mode - using demoInitiative:', demoInitiative);

            // Find the player's position in the demo initiative order
            const playerTurnIndex = demoInitiative.indexOf('player-1');
            console.log('[Game] Player is at initiative index:', playerTurnIndex);

            // Offline mode - initialize state directly
            state.initCombat({
                combat_id: 'demo-offline',
                round: 1,
                phase: 'in_combat',
                current_turn_index: playerTurnIndex >= 0 ? playerTurnIndex : 0, // Start on player's turn
                combatants: allCombatants,
                initiative_order: demoInitiative,
                positions: positionsXY,
                grid: demoGrid,
            });
        }

        // Debug: Check state after initCombat
        console.log('[Game] After initCombat - state.initiative:', state.get('initiative'));
        console.log('[Game] After initCombat - isPlayerTurn:', state.isPlayerTurn());

        // Set equipment manager context for inventory/equipment operations
        // Use the current combatant if it's a player, otherwise the first player ID
        const currentCombatId = state.get('combat.id');
        const playerIds = state.get('playerIds') || [];
        const currentPlayerId = state.isPlayerTurn()
            ? state.getCurrentCombatant()?.id
            : playerIds[0];
        if (currentCombatId && currentPlayerId) {
            equipmentManager.setContext(currentCombatId, currentPlayerId);
            console.log('[Game] Set equipment context:', currentCombatId, currentPlayerId);
        }

        // If it's not the player's turn, process enemy turns until it is
        // Skip in offline mode since there's no backend to process enemy AI
        const combatId = currentCombatId;
        if (!state.isPlayerTurn() && combatId !== 'demo-offline') {
            console.log('[Game] Not player turn - processing initial enemy turns...');
            await this.processInitialEnemyTurns();
        }

        // Set up turn state
        state.set('turn', {
            combatantId: 'player-1',
            actionUsed: false,
            bonusActionUsed: false,
            reactionUsed: false,
            movementRemaining: 30,
            movementUsed: 0,
            // BG3-style equipment system
            objectInteractionUsed: false,  // For weapon switching
            attacksRemaining: 2,  // Fighter level 5 gets 2 attacks
            maxAttacks: 2,
        });

        // Calculate reachable cells for movement
        const playerPos = demoPositions['player-1'];
        const reachableCells = [];
        for (let y = 0; y < 8; y++) {
            for (let x = 0; x < 8; x++) {
                if (!demoGrid[y][x].blocked) {
                    // Simple distance check from player position
                    const dx = Math.abs(x - playerPos[0]);
                    const dy = Math.abs(y - playerPos[1]);
                    const distance = Math.max(dx, dy) * 5; // 5ft per cell
                    if (distance <= 30) { // 30ft movement
                        reachableCells.push({ x, y });
                    }
                }
            }
        }
        state.setReachableCells(reachableCells);

        // Force a state update to refresh all UI components
        console.log('[Game] Forcing final state update, current mode:', state.get('mode'));
        console.log('[Game] Final isPlayerTurn check:', state.isPlayerTurn());
        state.notifySubscribers();

        // Emit turn started
        eventBus.emit(EVENTS.TURN_STARTED, { combatantId: 'player-1' });

        console.log('[Game] Demo combat loaded');
        this.updateCombatLog('Demo combat loaded. It\'s your turn!');
    }

    /**
     * Process initial enemy turns when combat starts and it's not the player's turn.
     * The backend's /end-turn endpoint processes ALL enemy turns automatically
     * until it reaches a player turn, so we only need one call.
     */
    async processInitialEnemyTurns() {
        const combatId = state.get('combat.id');
        if (!combatId) {
            console.error('[Game] No combat ID for processing enemy turns');
            return;
        }

        try {
            this.updateCombatLog('Enemies are taking their turns...', 'info');

            const response = await api.endTurn(combatId);

            // Show enemy actions in the combat log
            if (response.enemy_actions && response.enemy_actions.length > 0) {
                for (const action of response.enemy_actions) {
                    const logType = action.hit ? 'enemy_hit' : 'enemy_action';
                    this.updateCombatLog(action.description, logType);
                }
            }

            // Sync state from server response
            if (response.combat_state) {
                state.updateCombatState(response.combat_state);
            }

            // Update the current turn index
            if (typeof response.current_turn_index === 'number') {
                state.set('combat.currentTurnIndex', response.current_turn_index);
            }

            console.log('[Game] Enemy turns processed, now player turn:', state.isPlayerTurn());
            state.notifySubscribers();

        } catch (error) {
            console.error('[Game] Failed to process enemy turns:', error);
            this.updateCombatLog('Error processing enemy turns: ' + error.message, 'error');
        }
    }

    /**
     * Update combat log
     */
    updateCombatLog(message, type = 'info') {
        const logContent = document.getElementById('log-content');
        if (!logContent) return;

        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        entry.textContent = message;

        logContent.insertBefore(entry, logContent.firstChild);

        // Keep only last 20 entries
        while (logContent.children.length > 20) {
            logContent.removeChild(logContent.lastChild);
        }
    }

    /**
     * Show error message
     */
    showError(message) {
        console.error('[Game] Error:', message);
        this.updateCombatLog(`Error: ${message}`, 'error');
    }

    /**
     * Show toast notification
     */
    showNotification(message, type = 'info') {
        // Create or get notification container
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                display: flex;
                flex-direction: column;
                gap: 10px;
            `;
            document.body.appendChild(container);
        }

        // Create notification
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.style.cssText = `
            padding: 12px 20px;
            border-radius: 6px;
            color: white;
            font-weight: 500;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            animation: slideIn 0.3s ease;
            background: ${type === 'success' ? '#27ae60' : type === 'error' ? '#e74c3c' : '#3498db'};
        `;
        notification.textContent = message;

        container.appendChild(notification);

        // Auto-remove after 4 seconds
        setTimeout(() => {
            notification.style.animation = 'fadeOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 4000);
    }

    /**
     * Get XP value for a Challenge Rating (D&D 5e 2024)
     * @param {number|string} cr - Challenge Rating
     * @returns {number} XP value
     */
    getXPForCR(cr) {
        const XP_BY_CR = {
            0: 10, 0.125: 25, 0.25: 50, 0.5: 100,
            1: 200, 2: 450, 3: 700, 4: 1100, 5: 1800,
            6: 2300, 7: 2900, 8: 3900, 9: 5000, 10: 5900,
            11: 7200, 12: 8400, 13: 10000, 14: 11500, 15: 13000,
            16: 15000, 17: 18000, 18: 20000, 19: 22000, 20: 25000,
            21: 33000, 22: 41000, 23: 50000, 24: 62000, 25: 75000,
            26: 90000, 27: 105000, 28: 120000, 29: 135000, 30: 155000
        };
        const numCR = typeof cr === 'string' ? parseFloat(cr) : cr;
        return XP_BY_CR[numCR] || 50;
    }

    /**
     * Show dramatic combat start announcement
     */
    showCombatAnnouncement(title = 'COMBAT!') {
        // Create full-screen overlay
        const overlay = document.createElement('div');
        overlay.id = 'combat-announcement';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: radial-gradient(circle, rgba(139, 0, 0, 0.8) 0%, rgba(0, 0, 0, 0.9) 100%);
            z-index: 9000;
            opacity: 0;
            animation: combatAnnounceFadeIn 0.3s ease forwards;
            pointer-events: none;
        `;

        const text = document.createElement('div');
        text.style.cssText = `
            font-family: 'Cinzel', 'Times New Roman', serif;
            font-size: 5rem;
            font-weight: 700;
            color: #d4af37;
            text-shadow:
                0 0 20px rgba(212, 175, 55, 0.8),
                0 0 40px rgba(139, 0, 0, 0.8),
                2px 2px 4px rgba(0, 0, 0, 0.8);
            letter-spacing: 0.2em;
            transform: scale(0.5);
            animation: combatTextPop 0.5s ease 0.1s forwards;
        `;
        text.textContent = title;

        overlay.appendChild(text);
        document.body.appendChild(overlay);

        // Add keyframes if not already added
        if (!document.getElementById('combat-announce-styles')) {
            const style = document.createElement('style');
            style.id = 'combat-announce-styles';
            style.textContent = `
                @keyframes combatAnnounceFadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                @keyframes combatTextPop {
                    0% { transform: scale(0.5); }
                    50% { transform: scale(1.2); }
                    100% { transform: scale(1); }
                }
                @keyframes combatAnnounceFadeOut {
                    from { opacity: 1; }
                    to { opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }

        // Fade out and remove after delay
        setTimeout(() => {
            overlay.style.animation = 'combatAnnounceFadeOut 0.5s ease forwards';
            setTimeout(() => overlay.remove(), 500);
        }, 1500);
    }
}

// Initialize game when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const game = new Game();
    game.init();

    // Expose game instance for debugging
    if (CONFIG.DEBUG) {
        window.game = game;
        window.state = state;
        window.eventBus = eventBus;
        window.inventoryModal = inventoryModal;
    }
});

export default Game;
