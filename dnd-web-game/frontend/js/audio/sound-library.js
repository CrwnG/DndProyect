/**
 * D&D Combat Engine - Sound Library
 * Defines all available sounds with their file paths.
 *
 * Sound files are organized by category:
 * - sfx/combat/ - Combat-related sound effects
 * - sfx/ui/ - User interface sounds
 * - sfx/magic/ - Spell and magic effects
 * - music/ - Background music tracks
 * - ambient/ - Environmental ambient loops
 * - voice/ - Voice lines and narration
 */

// Base path for audio assets
const AUDIO_BASE = './assets/audio';

/**
 * Sound library mapping IDs to file paths.
 *
 * Note: These are placeholder paths. Replace with actual audio files.
 * Recommended formats: MP3 for music/ambient, WAV/OGG for short SFX.
 */
export const SOUNDS = {
    // ==================== Combat SFX ====================
    // Attacks
    attack_sword_swing: `${AUDIO_BASE}/sfx/combat/sword_swing.mp3`,
    attack_sword_hit: `${AUDIO_BASE}/sfx/combat/sword_hit.mp3`,
    attack_axe_swing: `${AUDIO_BASE}/sfx/combat/axe_swing.mp3`,
    attack_axe_hit: `${AUDIO_BASE}/sfx/combat/axe_hit.mp3`,
    attack_dagger: `${AUDIO_BASE}/sfx/combat/dagger.mp3`,
    attack_bow_draw: `${AUDIO_BASE}/sfx/combat/bow_draw.mp3`,
    attack_bow_release: `${AUDIO_BASE}/sfx/combat/bow_release.mp3`,
    attack_arrow_hit: `${AUDIO_BASE}/sfx/combat/arrow_hit.mp3`,
    attack_crossbow: `${AUDIO_BASE}/sfx/combat/crossbow.mp3`,
    attack_unarmed: `${AUDIO_BASE}/sfx/combat/punch.mp3`,
    attack_miss: `${AUDIO_BASE}/sfx/combat/whoosh.mp3`,
    attack_critical: `${AUDIO_BASE}/sfx/combat/critical_hit.mp3`,

    // Damage
    damage_physical: `${AUDIO_BASE}/sfx/combat/impact.mp3`,
    damage_slash: `${AUDIO_BASE}/sfx/combat/slash.mp3`,
    damage_pierce: `${AUDIO_BASE}/sfx/combat/pierce.mp3`,
    damage_bludgeon: `${AUDIO_BASE}/sfx/combat/thud.mp3`,
    damage_blocked: `${AUDIO_BASE}/sfx/combat/block.mp3`,
    damage_armor: `${AUDIO_BASE}/sfx/combat/armor_hit.mp3`,

    // Combat events
    combat_start: `${AUDIO_BASE}/sfx/combat/combat_start.mp3`,
    combat_victory: `${AUDIO_BASE}/sfx/combat/victory_fanfare.mp3`,
    combat_defeat: `${AUDIO_BASE}/sfx/combat/defeat.mp3`,
    death_enemy: `${AUDIO_BASE}/sfx/combat/death.mp3`,
    death_player: `${AUDIO_BASE}/sfx/combat/player_death.mp3`,
    initiative_roll: `${AUDIO_BASE}/sfx/combat/initiative.mp3`,

    // Movement
    footstep_stone: `${AUDIO_BASE}/sfx/combat/footstep_stone.mp3`,
    footstep_wood: `${AUDIO_BASE}/sfx/combat/footstep_wood.mp3`,
    footstep_grass: `${AUDIO_BASE}/sfx/combat/footstep_grass.mp3`,
    dodge: `${AUDIO_BASE}/sfx/combat/dodge.mp3`,

    // ==================== Magic SFX ====================
    // Spell casting
    spell_cast_generic: `${AUDIO_BASE}/sfx/magic/cast_generic.mp3`,
    spell_cast_fire: `${AUDIO_BASE}/sfx/magic/cast_fire.mp3`,
    spell_cast_ice: `${AUDIO_BASE}/sfx/magic/cast_ice.mp3`,
    spell_cast_lightning: `${AUDIO_BASE}/sfx/magic/cast_lightning.mp3`,
    spell_cast_holy: `${AUDIO_BASE}/sfx/magic/cast_holy.mp3`,
    spell_cast_dark: `${AUDIO_BASE}/sfx/magic/cast_dark.mp3`,
    spell_cast_nature: `${AUDIO_BASE}/sfx/magic/cast_nature.mp3`,
    spell_fizzle: `${AUDIO_BASE}/sfx/magic/fizzle.mp3`,

    // Spell effects
    spell_fireball_impact: `${AUDIO_BASE}/sfx/magic/fireball_impact.mp3`,
    spell_lightning_bolt: `${AUDIO_BASE}/sfx/magic/lightning.mp3`,
    spell_ice_shard: `${AUDIO_BASE}/sfx/magic/ice_shard.mp3`,
    spell_heal: `${AUDIO_BASE}/sfx/magic/heal.mp3`,
    spell_buff: `${AUDIO_BASE}/sfx/magic/buff.mp3`,
    spell_debuff: `${AUDIO_BASE}/sfx/magic/debuff.mp3`,
    spell_shield: `${AUDIO_BASE}/sfx/magic/shield.mp3`,
    spell_teleport: `${AUDIO_BASE}/sfx/magic/teleport.mp3`,
    spell_summon: `${AUDIO_BASE}/sfx/magic/summon.mp3`,

    // Class-specific
    rage_activate: `${AUDIO_BASE}/sfx/magic/rage.mp3`,
    sneak_attack: `${AUDIO_BASE}/sfx/magic/sneak_attack.mp3`,
    smite: `${AUDIO_BASE}/sfx/magic/smite.mp3`,
    wild_shape: `${AUDIO_BASE}/sfx/magic/wild_shape.mp3`,
    bardic_inspiration: `${AUDIO_BASE}/sfx/magic/inspiration.mp3`,
    ki_power: `${AUDIO_BASE}/sfx/magic/ki.mp3`,
    channel_divinity: `${AUDIO_BASE}/sfx/magic/divine.mp3`,

    // ==================== UI SFX ====================
    // Buttons and menus
    ui_click: `${AUDIO_BASE}/sfx/ui/click.mp3`,
    ui_hover: `${AUDIO_BASE}/sfx/ui/hover.mp3`,
    ui_open: `${AUDIO_BASE}/sfx/ui/open.mp3`,
    ui_close: `${AUDIO_BASE}/sfx/ui/close.mp3`,
    ui_confirm: `${AUDIO_BASE}/sfx/ui/confirm.mp3`,
    ui_cancel: `${AUDIO_BASE}/sfx/ui/cancel.mp3`,
    ui_error: `${AUDIO_BASE}/sfx/ui/error.mp3`,

    // Notifications
    notification_info: `${AUDIO_BASE}/sfx/ui/notification.mp3`,
    notification_success: `${AUDIO_BASE}/sfx/ui/success.mp3`,
    notification_warning: `${AUDIO_BASE}/sfx/ui/warning.mp3`,
    notification_error: `${AUDIO_BASE}/sfx/ui/alert.mp3`,

    // Turn/combat UI
    turn_start_player: `${AUDIO_BASE}/sfx/ui/turn_player.mp3`,
    turn_start_enemy: `${AUDIO_BASE}/sfx/ui/turn_enemy.mp3`,
    turn_end: `${AUDIO_BASE}/sfx/ui/turn_end.mp3`,

    // Progression
    level_up: `${AUDIO_BASE}/sfx/ui/level_up.mp3`,
    xp_gain: `${AUDIO_BASE}/sfx/ui/xp_gain.mp3`,
    gold_coin: `${AUDIO_BASE}/sfx/ui/coin.mp3`,
    gold_coins: `${AUDIO_BASE}/sfx/ui/coins.mp3`,
    item_pickup: `${AUDIO_BASE}/sfx/ui/pickup.mp3`,
    item_equip: `${AUDIO_BASE}/sfx/ui/equip.mp3`,
    item_unequip: `${AUDIO_BASE}/sfx/ui/unequip.mp3`,
    item_drop: `${AUDIO_BASE}/sfx/ui/drop.mp3`,

    // Dice
    dice_roll: `${AUDIO_BASE}/sfx/ui/dice_roll.mp3`,
    dice_natural_20: `${AUDIO_BASE}/sfx/ui/nat20.mp3`,
    dice_natural_1: `${AUDIO_BASE}/sfx/ui/nat1.mp3`,

    // ==================== Music ====================
    // Combat music
    music_combat_standard: `${AUDIO_BASE}/music/combat_standard.mp3`,
    music_combat_intense: `${AUDIO_BASE}/music/combat_intense.mp3`,
    music_combat_boss: `${AUDIO_BASE}/music/combat_boss.mp3`,
    music_combat_victory: `${AUDIO_BASE}/music/victory.mp3`,
    music_combat_defeat: `${AUDIO_BASE}/music/defeat.mp3`,

    // Exploration music
    music_exploration_calm: `${AUDIO_BASE}/music/exploration_calm.mp3`,
    music_exploration_mysterious: `${AUDIO_BASE}/music/exploration_mysterious.mp3`,
    music_exploration_tense: `${AUDIO_BASE}/music/exploration_tense.mp3`,

    // Location themes
    music_tavern: `${AUDIO_BASE}/music/tavern.mp3`,
    music_dungeon: `${AUDIO_BASE}/music/dungeon.mp3`,
    music_forest: `${AUDIO_BASE}/music/forest.mp3`,
    music_castle: `${AUDIO_BASE}/music/castle.mp3`,
    music_town: `${AUDIO_BASE}/music/town.mp3`,

    // Story/cutscene
    music_story_heroic: `${AUDIO_BASE}/music/story_heroic.mp3`,
    music_story_sad: `${AUDIO_BASE}/music/story_sad.mp3`,
    music_story_mystery: `${AUDIO_BASE}/music/story_mystery.mp3`,

    // Menu
    music_main_menu: `${AUDIO_BASE}/music/main_menu.mp3`,
    music_character_select: `${AUDIO_BASE}/music/character_select.mp3`,

    // ==================== Ambient ====================
    // Environment loops
    ambient_dungeon: `${AUDIO_BASE}/ambient/dungeon.mp3`,
    ambient_forest: `${AUDIO_BASE}/ambient/forest.mp3`,
    ambient_cave: `${AUDIO_BASE}/ambient/cave.mp3`,
    ambient_tavern: `${AUDIO_BASE}/ambient/tavern_interior.mp3`,
    ambient_town: `${AUDIO_BASE}/ambient/town.mp3`,
    ambient_rain: `${AUDIO_BASE}/ambient/rain.mp3`,
    ambient_wind: `${AUDIO_BASE}/ambient/wind.mp3`,
    ambient_fire: `${AUDIO_BASE}/ambient/fire_crackling.mp3`,
    ambient_water: `${AUDIO_BASE}/ambient/water.mp3`,
    ambient_crowd: `${AUDIO_BASE}/ambient/crowd.mp3`,
    ambient_night: `${AUDIO_BASE}/ambient/night.mp3`,

    // Combat ambience
    ambient_battle: `${AUDIO_BASE}/ambient/battle.mp3`,
};

/**
 * Sound categories for organized access
 */
export const SoundCategories = {
    COMBAT_ATTACKS: [
        'attack_sword_swing', 'attack_sword_hit', 'attack_axe_swing', 'attack_axe_hit',
        'attack_dagger', 'attack_bow_draw', 'attack_bow_release', 'attack_arrow_hit',
        'attack_crossbow', 'attack_unarmed', 'attack_miss', 'attack_critical'
    ],
    COMBAT_DAMAGE: [
        'damage_physical', 'damage_slash', 'damage_pierce', 'damage_bludgeon',
        'damage_blocked', 'damage_armor'
    ],
    COMBAT_EVENTS: [
        'combat_start', 'combat_victory', 'combat_defeat', 'death_enemy',
        'death_player', 'initiative_roll'
    ],
    SPELLS: [
        'spell_cast_generic', 'spell_cast_fire', 'spell_cast_ice', 'spell_cast_lightning',
        'spell_cast_holy', 'spell_cast_dark', 'spell_cast_nature', 'spell_fizzle',
        'spell_fireball_impact', 'spell_lightning_bolt', 'spell_ice_shard', 'spell_heal',
        'spell_buff', 'spell_debuff', 'spell_shield', 'spell_teleport', 'spell_summon'
    ],
    UI: [
        'ui_click', 'ui_hover', 'ui_open', 'ui_close', 'ui_confirm', 'ui_cancel',
        'ui_error', 'notification_info', 'notification_success', 'notification_warning',
        'notification_error'
    ],
    DICE: [
        'dice_roll', 'dice_natural_20', 'dice_natural_1'
    ]
};

/**
 * Get appropriate attack sound based on weapon type
 */
export function getAttackSound(weaponType, hit = true) {
    const weaponSounds = {
        sword: hit ? 'attack_sword_hit' : 'attack_sword_swing',
        longsword: hit ? 'attack_sword_hit' : 'attack_sword_swing',
        shortsword: hit ? 'attack_sword_hit' : 'attack_sword_swing',
        greatsword: hit ? 'attack_sword_hit' : 'attack_sword_swing',
        axe: hit ? 'attack_axe_hit' : 'attack_axe_swing',
        battleaxe: hit ? 'attack_axe_hit' : 'attack_axe_swing',
        greataxe: hit ? 'attack_axe_hit' : 'attack_axe_swing',
        handaxe: hit ? 'attack_axe_hit' : 'attack_axe_swing',
        dagger: 'attack_dagger',
        bow: hit ? 'attack_arrow_hit' : 'attack_bow_release',
        longbow: hit ? 'attack_arrow_hit' : 'attack_bow_release',
        shortbow: hit ? 'attack_arrow_hit' : 'attack_bow_release',
        crossbow: hit ? 'attack_arrow_hit' : 'attack_crossbow',
        unarmed: 'attack_unarmed',
        fist: 'attack_unarmed'
    };

    return weaponSounds[weaponType?.toLowerCase()] || (hit ? 'damage_physical' : 'attack_miss');
}

/**
 * Get damage sound based on damage type
 */
export function getDamageSound(damageType) {
    const damageSounds = {
        slashing: 'damage_slash',
        piercing: 'damage_pierce',
        bludgeoning: 'damage_bludgeon',
        fire: 'spell_fireball_impact',
        cold: 'spell_ice_shard',
        lightning: 'spell_lightning_bolt',
        thunder: 'spell_lightning_bolt',
        acid: 'spell_debuff',
        poison: 'spell_debuff',
        necrotic: 'spell_cast_dark',
        radiant: 'spell_cast_holy',
        force: 'spell_cast_generic',
        psychic: 'spell_debuff'
    };

    return damageSounds[damageType?.toLowerCase()] || 'damage_physical';
}

/**
 * Get spell casting sound based on school
 */
export function getSpellCastSound(school) {
    const schoolSounds = {
        evocation: 'spell_cast_fire',
        abjuration: 'spell_shield',
        conjuration: 'spell_summon',
        divination: 'spell_cast_holy',
        enchantment: 'spell_buff',
        illusion: 'spell_cast_dark',
        necromancy: 'spell_cast_dark',
        transmutation: 'spell_cast_nature'
    };

    return schoolSounds[school?.toLowerCase()] || 'spell_cast_generic';
}

/**
 * Get music track based on combat difficulty
 */
export function getCombatMusic(difficulty, isBoss = false) {
    if (isBoss) return 'music_combat_boss';

    const difficultyMusic = {
        easy: 'music_combat_standard',
        medium: 'music_combat_standard',
        hard: 'music_combat_intense',
        deadly: 'music_combat_intense'
    };

    return difficultyMusic[difficulty?.toLowerCase()] || 'music_combat_standard';
}

/**
 * Get ambient sound for a scene type
 */
export function getAmbientForScene(sceneType) {
    const sceneAmbient = {
        dungeon: 'ambient_dungeon',
        cave: 'ambient_cave',
        forest: 'ambient_forest',
        tavern: 'ambient_tavern',
        town: 'ambient_town',
        castle: 'ambient_dungeon',
        outdoor: 'ambient_forest',
        rain: 'ambient_rain',
        night: 'ambient_night'
    };

    return sceneAmbient[sceneType?.toLowerCase()] || 'ambient_dungeon';
}

export default SOUNDS;
