/**
 * D&D Combat Engine - Event Bus
 * Pub/Sub system for decoupled communication between components
 */

class EventBus {
    constructor() {
        this.listeners = new Map();
        this.onceListeners = new Map();
    }

    /**
     * Subscribe to an event
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     * @returns {Function} Unsubscribe function
     */
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }
        this.listeners.get(event).add(callback);

        // Return unsubscribe function
        return () => this.off(event, callback);
    }

    /**
     * Subscribe to an event once
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     */
    once(event, callback) {
        if (!this.onceListeners.has(event)) {
            this.onceListeners.set(event, new Set());
        }
        this.onceListeners.get(event).add(callback);
    }

    /**
     * Unsubscribe from an event
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     */
    off(event, callback) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).delete(callback);
        }
        if (this.onceListeners.has(event)) {
            this.onceListeners.get(event).delete(callback);
        }
    }

    /**
     * Emit an event
     * @param {string} event - Event name
     * @param {*} data - Event data
     */
    emit(event, data) {
        // Call regular listeners
        if (this.listeners.has(event)) {
            this.listeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`[EventBus] Error in listener for "${event}":`, error);
                }
            });
        }

        // Call and remove once listeners
        if (this.onceListeners.has(event)) {
            this.onceListeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`[EventBus] Error in once listener for "${event}":`, error);
                }
            });
            this.onceListeners.delete(event);
        }
    }

    /**
     * Remove all listeners for an event
     * @param {string} event - Event name (optional, removes all if not provided)
     */
    clear(event = null) {
        if (event) {
            this.listeners.delete(event);
            this.onceListeners.delete(event);
        } else {
            this.listeners.clear();
            this.onceListeners.clear();
        }
    }

    /**
     * Check if event has listeners
     * @param {string} event - Event name
     * @returns {boolean}
     */
    hasListeners(event) {
        return (
            (this.listeners.has(event) && this.listeners.get(event).size > 0) ||
            (this.onceListeners.has(event) && this.onceListeners.get(event).size > 0)
        );
    }
}

// Event Names Constants
export const EVENTS = {
    // Combat Events
    COMBAT_STARTED: 'combat:started',
    COMBAT_ENDED: 'combat:ended',
    COMBAT_STATE_UPDATED: 'combat:stateUpdated',

    // Turn Events
    TURN_STARTED: 'turn:started',
    TURN_ENDED: 'turn:ended',
    ROUND_STARTED: 'round:started',

    // Action Events
    ACTION_SELECTED: 'action:selected',
    ACTION_PERFORMED: 'action:performed',
    ACTION_CANCELLED: 'action:cancelled',

    // Movement Events
    MOVEMENT_STARTED: 'movement:started',
    MOVEMENT_COMPLETED: 'movement:completed',
    MOVEMENT_CANCELLED: 'movement:cancelled',
    MOVEMENT_MODE_ENABLED: 'movement:modeEnabled',
    MOVEMENT_MODE_DISABLED: 'movement:modeDisabled',
    REACHABLE_CELLS_UPDATED: 'movement:reachableCellsUpdated',
    THREAT_ZONES_UPDATED: 'movement:threatZonesUpdated',

    // Attack Events
    ATTACK_STARTED: 'attack:started',
    ATTACK_RESOLVED: 'attack:resolved',
    TARGET_SELECTED: 'attack:targetSelected',
    TARGETING_STARTED: 'targeting:started',
    TARGETING_CANCELLED: 'targeting:cancelled',
    AREA_TARGETING_STARTED: 'targeting:areaStarted',
    AREA_TARGET_SELECTED: 'targeting:areaSelected',

    // Spell Events
    SPELL_CAST: 'spell:cast',
    SPELL_EFFECT_APPLIED: 'spell:effectApplied',
    CONCENTRATION_STARTED: 'spell:concentrationStarted',
    CONCENTRATION_ENDED: 'spell:concentrationEnded',
    CONCENTRATION_CHECK: 'spell:concentrationCheck',

    // Enemy Turn Events
    ENEMY_ACTION: 'enemy:action',
    ENEMY_TURN_STARTED: 'enemy:turnStarted',
    ENEMY_TURN_ENDED: 'enemy:turnEnded',

    // Grid Events
    CELL_CLICKED: 'grid:cellClicked',
    CELL_HOVERED: 'grid:cellHovered',
    CELL_UNHOVERED: 'grid:cellUnhovered',
    GRID_RENDERED: 'grid:rendered',

    // Combatant Events
    COMBATANT_DAMAGED: 'combatant:damaged',
    COMBATANT_HEALED: 'combatant:healed',
    COMBATANT_DEFEATED: 'combatant:defeated',
    COMBATANT_SELECTED: 'combatant:selected',
    COMBATANT_MOVED: 'combatant:moved',

    // Reaction Events
    REACTION_AVAILABLE: 'reaction:available',
    REACTION_USED: 'reaction:used',
    OPPORTUNITY_ATTACK_TRIGGERED: 'reaction:opportunityAttack',
    OPPORTUNITY_ATTACK: 'reaction:opportunityAttackResolved',

    // Class Feature Events
    CLASS_FEATURE_USED: 'classFeature:used',
    WILD_SHAPE_REQUESTED: 'classFeature:wildShapeRequested',
    WILD_SHAPE_TRANSFORMED: 'classFeature:wildShapeTransformed',
    WILD_SHAPE_REVERTED: 'classFeature:wildShapeReverted',
    RAGE_STARTED: 'classFeature:rageStarted',
    RAGE_ENDED: 'classFeature:rageEnded',
    LAY_ON_HANDS_REQUESTED: 'classFeature:layOnHandsRequested',
    KI_POWERS_REQUESTED: 'classFeature:kiPowersRequested',
    CHANNEL_DIVINITY_REQUESTED: 'classFeature:channelDivinityRequested',
    METAMAGIC_REQUESTED: 'classFeature:metamagicRequested',
    INVOCATIONS_REQUESTED: 'classFeature:invocationsRequested',
    HUNTERS_MARK_APPLIED: 'classFeature:huntersMarkApplied',
    FAVORED_FOE_APPLIED: 'classFeature:favoredFoeApplied',
    HEX_APPLIED: 'classFeature:hexApplied',
    RECKLESS_ATTACK_ACTIVATED: 'classFeature:recklessAttackActivated',
    BARDIC_INSPIRATION_REQUESTED: 'classFeature:bardicInspirationRequested',
    BARDIC_INSPIRATION_GRANTED: 'classFeature:bardicInspirationGranted',

    // Rest Events
    REST_COMPLETED: 'rest:completed',
    SHORT_REST_STARTED: 'rest:shortStarted',
    LONG_REST_STARTED: 'rest:longStarted',

    // UI Events
    UI_MODAL_OPENED: 'ui:modalOpened',
    UI_MODAL_CLOSED: 'ui:modalClosed',
    UI_LOG_ENTRY: 'ui:logEntry',
    UI_NOTIFICATION: 'ui:notification',

    // Equipment Events
    INVENTORY_OPENED: 'inventory:opened',
    INVENTORY_CLOSED: 'inventory:closed',
    ITEM_EQUIPPED: 'equipment:itemEquipped',
    ITEM_UNEQUIPPED: 'equipment:itemUnequipped',
    EQUIPMENT_CHANGED: 'equipment:changed',
    ITEM_SELECTED: 'equipment:itemSelected',
    ITEM_DROPPED: 'equipment:itemDropped',
    WEIGHT_CHANGED: 'equipment:weightChanged',

    // Weapon Mastery Events
    MASTERY_TRIGGERED: 'mastery:triggered',
    MASTERY_EFFECT_APPLIED: 'mastery:effectApplied',

    // Loot Events
    LOOT_GENERATED: 'loot:generated',
    LOOT_COLLECTED: 'loot:collected',
    LOOT_DISTRIBUTED: 'loot:distributed',

    // Victory Events
    VICTORY_DISMISSED: 'victory:dismissed',

    // Error Events
    ERROR_OCCURRED: 'error:occurred',
    API_ERROR: 'error:api',

    // Character Import Events
    CHARACTER_IMPORTED: 'character:imported',
    CHARACTER_IMPORT_CANCELLED: 'character:importCancelled',
    OPEN_CHARACTER_IMPORT: 'character:openImport',

    // Campaign Events
    CAMPAIGN_STARTED: 'campaign:started',
    CAMPAIGN_CONTINUED: 'campaign:continued',
    CAMPAIGN_LOADED: 'campaign:loaded',
    CAMPAIGN_ENDED: 'campaign:ended',
    CAMPAIGN_STATE_CHANGED: 'campaign:stateChanged',
    ENCOUNTER_STARTED: 'encounter:started',
    ENCOUNTER_ENDED: 'encounter:ended',
    STORY_DISPLAYED: 'story:displayed',
    STORY_CONTINUED: 'story:continued',
    REST_STARTED: 'rest:started',
    REST_COMPLETED: 'rest:completed',

    // Choice Events (skill checks and branching)
    CHOICE_DISPLAYED: 'choice:displayed',
    CHOICE_SELECTED: 'choice:selected',
    CHOICE_RESULT: 'choice:result',
    SKILL_CHECK_PERFORMED: 'skillCheck:performed',

    // Menu Events
    OPEN_CAMPAIGN_MENU: 'menu:openCampaign',
    QUICK_COMBAT_REQUESTED: 'menu:quickCombat',
};

// Export singleton instance
export const eventBus = new EventBus();
export default eventBus;
