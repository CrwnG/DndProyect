/**
 * D&D Combat Engine - Audio Triggers
 * Automatically plays sounds based on game events via EventBus.
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import { audioManager, AudioCategory } from './audio-manager.js';
import {
    getAttackSound,
    getDamageSound,
    getSpellCastSound,
    getCombatMusic
} from './sound-library.js';

/**
 * Audio Trigger System
 * Listens to game events and plays appropriate sounds.
 */
class AudioTriggers {
    constructor() {
        this.enabled = true;
        this.currentCombatMusic = null;

        this.init();
    }

    /**
     * Initialize event listeners
     */
    init() {
        // Combat lifecycle events
        eventBus.on(EVENTS.COMBAT_STARTED, (data) => this.onCombatStarted(data));
        eventBus.on(EVENTS.COMBAT_ENDED, (data) => this.onCombatEnded(data));

        // Turn events
        eventBus.on(EVENTS.TURN_STARTED, (data) => this.onTurnStarted(data));
        eventBus.on(EVENTS.TURN_ENDED, (data) => this.onTurnEnded(data));

        // Attack events
        eventBus.on(EVENTS.ATTACK_RESOLVED, (data) => this.onAttackResolved(data));

        // Spell events
        eventBus.on(EVENTS.SPELL_CAST, (data) => this.onSpellCast(data));

        // Damage/healing events
        eventBus.on(EVENTS.COMBATANT_DAMAGED, (data) => this.onCombatantDamaged(data));
        eventBus.on(EVENTS.COMBATANT_HEALED, (data) => this.onCombatantHealed(data));

        // Death events
        eventBus.on(EVENTS.COMBATANT_DEFEATED, (data) => this.onCombatantDefeated(data));

        // Movement events
        eventBus.on(EVENTS.COMBATANT_MOVED, (data) => this.onCombatantMoved(data));

        // UI events
        eventBus.on(EVENTS.UI_NOTIFICATION, (data) => this.onNotification(data));
        eventBus.on(EVENTS.UI_MODAL_OPENED, (data) => this.onModalOpened(data));
        eventBus.on(EVENTS.UI_MODAL_CLOSED, (data) => this.onModalClosed(data));

        // Progression events
        eventBus.on(EVENTS.LEVEL_UP, (data) => this.onLevelUp(data));
        eventBus.on(EVENTS.XP_GAINED, (data) => this.onXPGained(data));
        eventBus.on(EVENTS.LOOT_COLLECTED, (data) => this.onLootCollected(data));

        // Victory events
        eventBus.on(EVENTS.VICTORY_DISMISSED, () => this.onVictoryDismissed());

        // Dice roll events
        eventBus.on('dice:rolled', (data) => this.onDiceRolled(data));

        // Class feature events
        eventBus.on('feature:rage', () => this.onRage());
        eventBus.on('feature:smite', () => this.onSmite());
        eventBus.on('feature:sneak_attack', () => this.onSneakAttack());
        eventBus.on('feature:wild_shape', () => this.onWildShape());
        eventBus.on('feature:bardic_inspiration', () => this.onBardicInspiration());
        eventBus.on('feature:channel_divinity', () => this.onChannelDivinity());
        eventBus.on('feature:ki', () => this.onKiPower());

        console.log('[AudioTriggers] Event listeners initialized');
    }

    /**
     * Enable or disable audio triggers
     */
    setEnabled(enabled) {
        this.enabled = enabled;
    }

    // ==================== Combat Events ====================

    onCombatStarted(data) {
        if (!this.enabled) return;

        // Play combat start sound
        audioManager.playSFX('combat_start');

        // Start combat music
        const musicTrack = getCombatMusic(
            data?.difficulty || 'medium',
            data?.isBoss || false
        );
        audioManager.playMusic(musicTrack, { fadeIn: 1500 });
        this.currentCombatMusic = musicTrack;

        // Start battle ambient
        audioManager.playAmbient('ambient_battle', { fadeIn: 2000 });
    }

    onCombatEnded(data) {
        if (!this.enabled) return;

        // Stop battle ambient
        audioManager.stopAmbient(1500);

        if (data?.result === 'victory') {
            // Play victory music
            audioManager.playMusic('music_combat_victory', { fadeIn: 500, loop: false });
            audioManager.playSFX('combat_victory');
        } else if (data?.result === 'defeat') {
            // Play defeat music
            audioManager.playMusic('music_combat_defeat', { fadeIn: 500, loop: false });
            audioManager.playSFX('combat_defeat');
        } else {
            // Just stop music
            audioManager.stopMusic(2000);
        }

        this.currentCombatMusic = null;
    }

    onTurnStarted(data) {
        if (!this.enabled) return;

        if (data?.isPlayer) {
            audioManager.playSFX('turn_start_player', { volume: 0.7 });
        } else {
            audioManager.playSFX('turn_start_enemy', { volume: 0.5 });
        }
    }

    onTurnEnded(data) {
        if (!this.enabled) return;
        // Optional: subtle turn end sound
        // audioManager.playSFX('turn_end', { volume: 0.3 });
    }

    // ==================== Attack Events ====================

    onAttackResolved(data) {
        if (!this.enabled) return;

        const weaponType = data?.weapon?.type || data?.weaponType || 'sword';

        if (data?.hit) {
            // Hit sound
            const hitSound = getAttackSound(weaponType, true);
            audioManager.playSFX(hitSound);

            // Critical hit has extra flourish
            if (data?.critical) {
                audioManager.playSFX('attack_critical', { delay: 100, volume: 1.2 });
            }
        } else {
            // Miss sound
            audioManager.playSFX('attack_miss');
        }
    }

    // ==================== Spell Events ====================

    onSpellCast(data) {
        if (!this.enabled) return;

        const school = data?.school || 'evocation';
        const castSound = getSpellCastSound(school);
        audioManager.playSFX(castSound);

        // Play effect sound if specified
        if (data?.effectSound) {
            audioManager.playSFX(data.effectSound, { delay: 300 });
        }

        // Handle specific spell effects
        const spellName = data?.spellName?.toLowerCase() || '';

        if (spellName.includes('fireball')) {
            audioManager.playSFX('spell_fireball_impact', { delay: 500 });
        } else if (spellName.includes('lightning')) {
            audioManager.playSFX('spell_lightning_bolt', { delay: 200 });
        } else if (spellName.includes('heal') || spellName.includes('cure')) {
            audioManager.playSFX('spell_heal', { delay: 300 });
        }
    }

    // ==================== Damage/Healing Events ====================

    onCombatantDamaged(data) {
        if (!this.enabled) return;

        const damageType = data?.damageType || 'physical';
        const damageSound = getDamageSound(damageType);
        audioManager.playSFX(damageSound, { volume: 0.8 });
    }

    onCombatantHealed(data) {
        if (!this.enabled) return;

        audioManager.playSFX('spell_heal', { volume: 0.7 });
    }

    // ==================== Death Events ====================

    onCombatantDefeated(data) {
        if (!this.enabled) return;

        if (data?.isPlayer) {
            audioManager.playSFX('death_player');
        } else {
            audioManager.playSFX('death_enemy');
        }
    }

    // ==================== Movement Events ====================

    onCombatantMoved(data) {
        if (!this.enabled) return;

        // Get terrain type for footstep sound
        const terrain = data?.terrain || 'stone';
        const footstepSound = `footstep_${terrain}`;

        // Only play occasionally to avoid spam
        if (Math.random() < 0.3) {
            audioManager.playSFX(footstepSound, { volume: 0.3 });
        }
    }

    // ==================== UI Events ====================

    onNotification(data) {
        if (!this.enabled) return;

        const type = data?.type || 'info';
        const notificationSounds = {
            info: 'notification_info',
            success: 'notification_success',
            warning: 'notification_warning',
            error: 'notification_error'
        };

        const sound = notificationSounds[type] || 'notification_info';
        audioManager.playSFX(sound, { volume: 0.5 });
    }

    onModalOpened(data) {
        if (!this.enabled) return;
        audioManager.playSFX('ui_open', { volume: 0.4 });
    }

    onModalClosed(data) {
        if (!this.enabled) return;
        audioManager.playSFX('ui_close', { volume: 0.4 });
    }

    // ==================== Progression Events ====================

    onLevelUp(data) {
        if (!this.enabled) return;
        audioManager.playSFX('level_up', { volume: 1.0 });
    }

    onXPGained(data) {
        if (!this.enabled) return;
        audioManager.playSFX('xp_gain', { volume: 0.5 });
    }

    onLootCollected(data) {
        if (!this.enabled) return;

        // Coin sounds based on amount
        if (data?.gold > 100) {
            audioManager.playSFX('gold_coins', { volume: 0.6 });
        } else if (data?.gold > 0) {
            audioManager.playSFX('gold_coin', { volume: 0.5 });
        }

        // Item pickup sound
        if (data?.items?.length > 0) {
            audioManager.playSFX('item_pickup', { volume: 0.6, delay: 200 });
        }
    }

    onVictoryDismissed() {
        if (!this.enabled) return;

        // Stop victory music, return to exploration or silence
        audioManager.stopMusic(1500);
    }

    // ==================== Dice Events ====================

    onDiceRolled(data) {
        if (!this.enabled) return;

        audioManager.playSFX('dice_roll', { volume: 0.6 });

        // Special sounds for natural 20 and 1
        if (data?.natural === 20) {
            audioManager.playSFX('dice_natural_20', { delay: 400, volume: 0.8 });
        } else if (data?.natural === 1) {
            audioManager.playSFX('dice_natural_1', { delay: 400, volume: 0.8 });
        }
    }

    // ==================== Class Feature Events ====================

    onRage() {
        if (!this.enabled) return;
        audioManager.playSFX('rage_activate', { volume: 0.9 });
    }

    onSmite() {
        if (!this.enabled) return;
        audioManager.playSFX('smite', { volume: 0.9 });
    }

    onSneakAttack() {
        if (!this.enabled) return;
        audioManager.playSFX('sneak_attack', { volume: 0.8 });
    }

    onWildShape() {
        if (!this.enabled) return;
        audioManager.playSFX('wild_shape', { volume: 0.9 });
    }

    onBardicInspiration() {
        if (!this.enabled) return;
        audioManager.playSFX('bardic_inspiration', { volume: 0.7 });
    }

    onChannelDivinity() {
        if (!this.enabled) return;
        audioManager.playSFX('channel_divinity', { volume: 0.9 });
    }

    onKiPower() {
        if (!this.enabled) return;
        audioManager.playSFX('ki_power', { volume: 0.8 });
    }

    // ==================== Manual Triggers ====================

    /**
     * Play UI button click sound
     */
    playButtonClick() {
        if (!this.enabled) return;
        audioManager.playSFX('ui_click', { volume: 0.4 });
    }

    /**
     * Play item equip sound
     */
    playEquipSound() {
        if (!this.enabled) return;
        audioManager.playSFX('item_equip', { volume: 0.6 });
    }

    /**
     * Play item unequip sound
     */
    playUnequipSound() {
        if (!this.enabled) return;
        audioManager.playSFX('item_unequip', { volume: 0.5 });
    }

    /**
     * Play error sound
     */
    playErrorSound() {
        if (!this.enabled) return;
        audioManager.playSFX('ui_error', { volume: 0.6 });
    }

    /**
     * Play confirm sound
     */
    playConfirmSound() {
        if (!this.enabled) return;
        audioManager.playSFX('ui_confirm', { volume: 0.5 });
    }

    /**
     * Play scene ambient based on location
     */
    playSceneAmbient(sceneType) {
        if (!this.enabled) return;

        const ambientMap = {
            dungeon: 'ambient_dungeon',
            cave: 'ambient_cave',
            forest: 'ambient_forest',
            tavern: 'ambient_tavern',
            town: 'ambient_town',
            castle: 'ambient_dungeon'
        };

        const ambient = ambientMap[sceneType] || 'ambient_dungeon';
        audioManager.playAmbient(ambient, { fadeIn: 3000 });
    }

    /**
     * Play exploration music based on mood
     */
    playExplorationMusic(mood = 'calm') {
        if (!this.enabled) return;

        const moodMap = {
            calm: 'music_exploration_calm',
            mysterious: 'music_exploration_mysterious',
            tense: 'music_exploration_tense'
        };

        const track = moodMap[mood] || 'music_exploration_calm';
        audioManager.playMusic(track, { fadeIn: 2000 });
    }
}

// Export singleton
export const audioTriggers = new AudioTriggers();
export default audioTriggers;
