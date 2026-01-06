"""
Subclass System for D&D 5e 2024

Comprehensive subclass architecture supporting:
- Subclass definitions with level-gated features
- Subclass selection at appropriate levels per class
- Subclass feature registration and lookup
- Feature prerequisites and resource costs
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum


# Level at which each class gains their subclass (D&D 5e 2024)
SUBCLASS_LEVELS: Dict[str, int] = {
    "barbarian": 3,
    "bard": 3,
    "cleric": 1,  # Domain at level 1
    "druid": 2,   # Circle at level 2
    "fighter": 3,
    "monk": 3,
    "paladin": 3,
    "ranger": 3,
    "rogue": 3,
    "sorcerer": 1,  # Origin at level 1
    "warlock": 1,   # Patron at level 1
    "wizard": 2,    # School at level 2
}


class FeatureType(str, Enum):
    """Types of subclass features."""
    PASSIVE = "passive"  # Always active
    ACTION = "action"  # Requires action to use
    BONUS_ACTION = "bonus_action"
    REACTION = "reaction"
    FREE = "free"  # No action cost
    RITUAL = "ritual"  # Can be cast as ritual
    CHANNEL_DIVINITY = "channel_divinity"  # Cleric/Paladin
    WILD_SHAPE = "wild_shape"  # Druid
    METAMAGIC = "metamagic"  # Sorcerer
    INVOCATION = "invocation"  # Warlock


@dataclass
class SubclassFeature:
    """A single feature granted by a subclass."""
    id: str
    name: str
    level: int  # Level when feature is gained
    description: str
    feature_type: FeatureType = FeatureType.PASSIVE

    # Resource costs
    uses_per_rest: Optional[int] = None  # None = unlimited
    resource_type: Optional[str] = None  # "channel_divinity", "ki", "sorcery_points", etc.
    resource_cost: int = 0

    # Prerequisites
    requires_concentration: bool = False
    requires_spell_slot: bool = False
    spell_slot_level: int = 0

    # Effects
    grants_proficiency: List[str] = field(default_factory=list)
    grants_resistance: List[str] = field(default_factory=list)
    grants_immunity: List[str] = field(default_factory=list)
    grants_spells: List[str] = field(default_factory=list)  # Always prepared spells
    modifies_ability: Optional[str] = None  # e.g., "rage", "sneak_attack"

    # For features that have variable effects by level
    scaling: Optional[Dict[int, Any]] = None  # {level: effect_value}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level,
            "description": self.description,
            "feature_type": self.feature_type.value,
            "uses_per_rest": self.uses_per_rest,
            "resource_type": self.resource_type,
            "resource_cost": self.resource_cost,
            "requires_concentration": self.requires_concentration,
            "grants_proficiency": self.grants_proficiency,
            "grants_resistance": self.grants_resistance,
            "grants_immunity": self.grants_immunity,
            "grants_spells": self.grants_spells,
        }


@dataclass
class Subclass:
    """A complete subclass definition."""
    id: str
    name: str
    class_id: str  # Parent class (e.g., "fighter", "cleric")
    description: str
    features: List[SubclassFeature] = field(default_factory=list)

    # Subclass-specific resources
    bonus_proficiencies: List[str] = field(default_factory=list)
    bonus_languages: List[str] = field(default_factory=list)

    # Spellcasting modifications (for half-caster subclasses like Eldritch Knight)
    grants_spellcasting: bool = False
    spellcasting_ability: Optional[str] = None  # "intelligence", "wisdom", "charisma"

    def get_features_at_level(self, level: int) -> List[SubclassFeature]:
        """Get all features available at or before a given level."""
        return [f for f in self.features if f.level <= level]

    def get_new_features_at_level(self, level: int) -> List[SubclassFeature]:
        """Get features gained exactly at a given level."""
        return [f for f in self.features if f.level == level]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "class_id": self.class_id,
            "description": self.description,
            "features": [f.to_dict() for f in self.features],
            "bonus_proficiencies": self.bonus_proficiencies,
            "grants_spellcasting": self.grants_spellcasting,
            "spellcasting_ability": self.spellcasting_ability,
        }


# =============================================================================
# SUBCLASS DEFINITIONS
# =============================================================================

# -----------------------------------------------------------------------------
# BARBARIAN SUBCLASSES
# -----------------------------------------------------------------------------

BERSERKER = Subclass(
    id="berserker",
    name="Path of the Berserker",
    class_id="barbarian",
    description="Violence is both a means and an end. You follow a path of untrammeled fury.",
    features=[
        SubclassFeature(
            id="frenzy",
            name="Frenzy",
            level=3,
            description="When you enter rage, you can choose to frenzy. While frenzied, you can make a single melee weapon attack as a bonus action on each of your turns. When your rage ends, you gain one level of exhaustion.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="mindless_rage",
            name="Mindless Rage",
            level=6,
            description="You can't be charmed or frightened while raging. If you are charmed or frightened when you enter rage, the effect is suspended for the duration.",
            feature_type=FeatureType.PASSIVE,
            grants_immunity=["charmed", "frightened"],  # While raging
        ),
        SubclassFeature(
            id="intimidating_presence",
            name="Intimidating Presence",
            level=10,
            description="You can use your action to frighten someone with your menacing presence.",
            feature_type=FeatureType.ACTION,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="retaliation",
            name="Retaliation",
            level=14,
            description="When you take damage from a creature within 5 feet, you can use your reaction to make a melee weapon attack against that creature.",
            feature_type=FeatureType.REACTION,
        ),
    ]
)

TOTEM_WARRIOR = Subclass(
    id="totem_warrior",
    name="Path of the Totem Warrior",
    class_id="barbarian",
    description="You make a spiritual journey to find a spirit animal companion.",
    features=[
        SubclassFeature(
            id="spirit_seeker",
            name="Spirit Seeker",
            level=3,
            description="You can cast Beast Sense and Speak with Animals as rituals.",
            feature_type=FeatureType.RITUAL,
            grants_spells=["beast_sense", "speak_with_animals"],
        ),
        SubclassFeature(
            id="totem_spirit",
            name="Totem Spirit",
            level=3,
            description="Choose a totem animal: Bear (resistance to all damage except psychic while raging), Eagle (opportunity attacks against you have disadvantage, Dash as bonus action), Wolf (allies have advantage on melee attacks against enemies within 5ft of you while you're raging).",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="aspect_of_the_beast",
            name="Aspect of the Beast",
            level=6,
            description="Gain a magical benefit based on your totem animal.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="spirit_walker",
            name="Spirit Walker",
            level=10,
            description="You can cast Commune with Nature as a ritual.",
            feature_type=FeatureType.RITUAL,
            grants_spells=["commune_with_nature"],
        ),
        SubclassFeature(
            id="totemic_attunement",
            name="Totemic Attunement",
            level=14,
            description="Gain the final totem benefit based on your chosen animal.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)

# -----------------------------------------------------------------------------
# FIGHTER SUBCLASSES
# -----------------------------------------------------------------------------

CHAMPION = Subclass(
    id="champion",
    name="Champion",
    class_id="fighter",
    description="You focus on raw physical power, honed to deadly perfection.",
    features=[
        SubclassFeature(
            id="improved_critical",
            name="Improved Critical",
            level=3,
            description="Your weapon attacks score a critical hit on a roll of 19 or 20.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="remarkable_athlete",
            name="Remarkable Athlete",
            level=7,
            description="Add half your proficiency bonus (rounded up) to any Strength, Dexterity, or Constitution check that doesn't already use your proficiency bonus. Your running long jump increases by feet equal to your Strength modifier.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="additional_fighting_style",
            name="Additional Fighting Style",
            level=10,
            description="You can choose a second option from the Fighting Style class feature.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="superior_critical",
            name="Superior Critical",
            level=15,
            description="Your weapon attacks score a critical hit on a roll of 18-20.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="survivor",
            name="Survivor",
            level=18,
            description="At the start of each of your turns, you regain hit points equal to 5 + your Constitution modifier if you have no more than half of your hit points left. You don't gain this benefit if you have 0 hit points.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)

BATTLE_MASTER = Subclass(
    id="battle_master",
    name="Battle Master",
    class_id="fighter",
    description="You employ martial techniques passed down through generations.",
    features=[
        SubclassFeature(
            id="combat_superiority",
            name="Combat Superiority",
            level=3,
            description="You learn maneuvers that are fueled by superiority dice. You have 4 superiority dice (d8s) and learn 3 maneuvers. You regain all superiority dice on a short or long rest.",
            feature_type=FeatureType.PASSIVE,
            scaling={3: {"dice": 4, "die_size": 8, "maneuvers": 3},
                    7: {"dice": 5, "die_size": 8, "maneuvers": 5},
                    10: {"dice": 5, "die_size": 10, "maneuvers": 7},
                    15: {"dice": 6, "die_size": 10, "maneuvers": 9},
                    18: {"dice": 6, "die_size": 12, "maneuvers": 9}},
        ),
        SubclassFeature(
            id="student_of_war",
            name="Student of War",
            level=3,
            description="You gain proficiency with one type of artisan's tools of your choice.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="know_your_enemy",
            name="Know Your Enemy",
            level=7,
            description="If you spend at least 1 minute observing or interacting with another creature, you can learn information about its capabilities.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="relentless",
            name="Relentless",
            level=15,
            description="When you roll initiative and have no superiority dice remaining, you regain 1 superiority die.",
            feature_type=FeatureType.PASSIVE,
        ),
    ],
    bonus_proficiencies=["artisan_tools"],
)

ELDRITCH_KNIGHT = Subclass(
    id="eldritch_knight",
    name="Eldritch Knight",
    class_id="fighter",
    description="You combine martial prowess with magical study.",
    grants_spellcasting=True,
    spellcasting_ability="intelligence",
    features=[
        SubclassFeature(
            id="spellcasting",
            name="Spellcasting",
            level=3,
            description="You learn to cast wizard spells. Intelligence is your spellcasting ability.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="weapon_bond",
            name="Weapon Bond",
            level=3,
            description="You can bond with up to two weapons. You can summon a bonded weapon as a bonus action.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="war_magic",
            name="War Magic",
            level=7,
            description="When you cast a cantrip, you can make one weapon attack as a bonus action.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="eldritch_strike",
            name="Eldritch Strike",
            level=10,
            description="When you hit with a weapon attack, the creature has disadvantage on its next saving throw against a spell you cast before the end of your next turn.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="arcane_charge",
            name="Arcane Charge",
            level=15,
            description="When you use Action Surge, you can teleport up to 30 feet to an unoccupied space you can see.",
            feature_type=FeatureType.FREE,
        ),
        SubclassFeature(
            id="improved_war_magic",
            name="Improved War Magic",
            level=18,
            description="When you cast a spell, you can make one weapon attack as a bonus action.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
    ]
)

# -----------------------------------------------------------------------------
# ROGUE SUBCLASSES
# -----------------------------------------------------------------------------

THIEF = Subclass(
    id="thief",
    name="Thief",
    class_id="rogue",
    description="You hone your skills in the larcenous arts.",
    features=[
        SubclassFeature(
            id="fast_hands",
            name="Fast Hands",
            level=3,
            description="You can use Cunning Action to make a Sleight of Hand check, use thieves' tools, or take the Use an Object action.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="second_story_work",
            name="Second-Story Work",
            level=3,
            description="You gain a climbing speed equal to your walking speed. You can jump extra distance equal to your Dexterity modifier in feet.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="supreme_sneak",
            name="Supreme Sneak",
            level=9,
            description="You have advantage on Stealth checks if you move no more than half your speed on the same turn.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="use_magic_device",
            name="Use Magic Device",
            level=13,
            description="You can use any magic item, ignoring class, race, and level requirements.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="thiefs_reflexes",
            name="Thief's Reflexes",
            level=17,
            description="You can take two turns during the first round of combat.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)

ASSASSIN = Subclass(
    id="assassin",
    name="Assassin",
    class_id="rogue",
    description="You focus your training on the grim art of death.",
    features=[
        SubclassFeature(
            id="bonus_proficiencies",
            name="Bonus Proficiencies",
            level=3,
            description="You gain proficiency with the disguise kit and poisoner's kit.",
            feature_type=FeatureType.PASSIVE,
            grants_proficiency=["disguise_kit", "poisoners_kit"],
        ),
        SubclassFeature(
            id="assassinate",
            name="Assassinate",
            level=3,
            description="You have advantage on attack rolls against creatures that haven't taken a turn yet. Any hit you score against a surprised creature is a critical hit.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="infiltration_expertise",
            name="Infiltration Expertise",
            level=9,
            description="You can create false identities with flawless documentation.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="impostor",
            name="Impostor",
            level=13,
            description="You can unerringly mimic another person's speech, writing, and behavior.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="death_strike",
            name="Death Strike",
            level=17,
            description="When you hit a surprised creature, it must make a Constitution save or take double damage.",
            feature_type=FeatureType.PASSIVE,
        ),
    ],
    bonus_proficiencies=["disguise_kit", "poisoners_kit"],
)

# -----------------------------------------------------------------------------
# CLERIC SUBCLASSES (DOMAINS)
# -----------------------------------------------------------------------------

LIFE_DOMAIN = Subclass(
    id="life_domain",
    name="Life Domain",
    class_id="cleric",
    description="Gods of life promote vitality through healing the sick and wounded.",
    features=[
        SubclassFeature(
            id="bonus_proficiency",
            name="Bonus Proficiency",
            level=1,
            description="You gain proficiency with heavy armor.",
            feature_type=FeatureType.PASSIVE,
            grants_proficiency=["heavy_armor"],
        ),
        SubclassFeature(
            id="disciple_of_life",
            name="Disciple of Life",
            level=1,
            description="When you cast a spell that restores hit points, the creature regains additional hit points equal to 2 + the spell's level.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="channel_divinity_preserve_life",
            name="Channel Divinity: Preserve Life",
            level=2,
            description="As an action, restore hit points equal to 5 times your cleric level, divided among any creatures within 30 feet. Can't restore more than half a creature's max HP.",
            feature_type=FeatureType.CHANNEL_DIVINITY,
            uses_per_rest=1,  # Scales with cleric CD uses
        ),
        SubclassFeature(
            id="blessed_healer",
            name="Blessed Healer",
            level=6,
            description="When you cast a spell that restores hit points to another creature, you also regain hit points equal to 2 + the spell's level.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="divine_strike_life",
            name="Divine Strike",
            level=8,
            description="Once on each of your turns when you hit with a weapon attack, you deal an extra 1d8 radiant damage (2d8 at level 14).",
            feature_type=FeatureType.PASSIVE,
            scaling={8: {"dice": 1, "damage_type": "radiant"},
                    14: {"dice": 2, "damage_type": "radiant"}},
        ),
        SubclassFeature(
            id="supreme_healing",
            name="Supreme Healing",
            level=17,
            description="When you roll dice to restore hit points with a spell, you can use the maximum number instead of rolling.",
            feature_type=FeatureType.PASSIVE,
        ),
    ],
    bonus_proficiencies=["heavy_armor"],
)

WAR_DOMAIN = Subclass(
    id="war_domain",
    name="War Domain",
    class_id="cleric",
    description="Gods of war inspire great courage and valor in warriors.",
    features=[
        SubclassFeature(
            id="bonus_proficiencies_war",
            name="Bonus Proficiencies",
            level=1,
            description="You gain proficiency with martial weapons and heavy armor.",
            feature_type=FeatureType.PASSIVE,
            grants_proficiency=["martial_weapons", "heavy_armor"],
        ),
        SubclassFeature(
            id="war_priest",
            name="War Priest",
            level=1,
            description="When you take the Attack action, you can make one weapon attack as a bonus action. You can use this a number of times equal to your Wisdom modifier.",
            feature_type=FeatureType.BONUS_ACTION,
            uses_per_rest=5,  # Wisdom modifier, typically
        ),
        SubclassFeature(
            id="channel_divinity_guided_strike",
            name="Channel Divinity: Guided Strike",
            level=2,
            description="When you make an attack roll, you can use your Channel Divinity to gain a +10 bonus to the roll.",
            feature_type=FeatureType.CHANNEL_DIVINITY,
        ),
        SubclassFeature(
            id="channel_divinity_war_gods_blessing",
            name="Channel Divinity: War God's Blessing",
            level=6,
            description="When a creature within 30 feet makes an attack roll, you can use your reaction to grant that creature a +10 bonus to the roll.",
            feature_type=FeatureType.REACTION,
            resource_type="channel_divinity",
        ),
        SubclassFeature(
            id="divine_strike_war",
            name="Divine Strike",
            level=8,
            description="Once on each of your turns when you hit with a weapon attack, you deal an extra 1d8 damage of the same type (2d8 at level 14).",
            feature_type=FeatureType.PASSIVE,
            scaling={8: {"dice": 1}, 14: {"dice": 2}},
        ),
        SubclassFeature(
            id="avatar_of_battle",
            name="Avatar of Battle",
            level=17,
            description="You have resistance to bludgeoning, piercing, and slashing damage from nonmagical attacks.",
            feature_type=FeatureType.PASSIVE,
            grants_resistance=["bludgeoning", "piercing", "slashing"],
        ),
    ],
    bonus_proficiencies=["martial_weapons", "heavy_armor"],
)

LIGHT_DOMAIN = Subclass(
    id="light_domain",
    name="Light Domain",
    class_id="cleric",
    description="Gods of light promote ideals of rebirth and renewal, truth, vigilance, and beauty.",
    features=[
        SubclassFeature(
            id="bonus_cantrip_light",
            name="Bonus Cantrip",
            level=1,
            description="You gain the Light cantrip if you don't already know it.",
            feature_type=FeatureType.PASSIVE,
            grants_spells=["light"],
        ),
        SubclassFeature(
            id="warding_flare",
            name="Warding Flare",
            level=1,
            description="When you are attacked by a creature within 30 feet that you can see, you can use your reaction to impose disadvantage on the attack roll, causing light to flare before the attacker. You can use this a number of times equal to your Wisdom modifier (min 1).",
            feature_type=FeatureType.REACTION,
            uses_per_rest=5,  # Wisdom modifier
        ),
        SubclassFeature(
            id="channel_divinity_radiance_of_the_dawn",
            name="Channel Divinity: Radiance of the Dawn",
            level=2,
            description="As an action, you present your holy symbol and any magical darkness within 30 feet is dispelled. Each hostile creature within 30 feet must make a Constitution saving throw. A creature takes radiant damage equal to 2d10 + your cleric level on a failed save, or half on success.",
            feature_type=FeatureType.CHANNEL_DIVINITY,
        ),
        SubclassFeature(
            id="improved_flare",
            name="Improved Flare",
            level=6,
            description="You can use your Warding Flare when a creature you can see within 30 feet attacks a creature other than you.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="potent_spellcasting_light",
            name="Potent Spellcasting",
            level=8,
            description="You add your Wisdom modifier to the damage you deal with any cleric cantrip.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="corona_of_light",
            name="Corona of Light",
            level=17,
            description="You can use your action to activate an aura of sunlight lasting 1 minute. You emit bright light in a 60-foot radius and dim light 30 feet beyond that. Your enemies in the bright light have disadvantage on saving throws against spells that deal fire or radiant damage.",
            feature_type=FeatureType.ACTION,
            uses_per_rest=1,
        ),
    ],
    # Domain Spells: burning hands, faerie fire (1), flaming sphere, scorching ray (3),
    # daylight, fireball (5), guardian of faith, wall of fire (7), flame strike, scrying (9)
)

TEMPEST_DOMAIN = Subclass(
    id="tempest_domain",
    name="Tempest Domain",
    class_id="cleric",
    description="Gods of tempests govern storms, sea, and sky, sending their clerics to spread awe of their power.",
    features=[
        SubclassFeature(
            id="bonus_proficiencies_tempest",
            name="Bonus Proficiencies",
            level=1,
            description="You gain proficiency with martial weapons and heavy armor.",
            feature_type=FeatureType.PASSIVE,
            grants_proficiency=["martial_weapons", "heavy_armor"],
        ),
        SubclassFeature(
            id="wrath_of_the_storm",
            name="Wrath of the Storm",
            level=1,
            description="When a creature within 5 feet hits you with an attack, you can use your reaction to cause the creature to make a Dexterity saving throw. On a failed save, it takes 2d8 lightning or thunder damage (your choice), or half on success. You can use this a number of times equal to your Wisdom modifier.",
            feature_type=FeatureType.REACTION,
            uses_per_rest=5,  # Wisdom modifier
        ),
        SubclassFeature(
            id="channel_divinity_destructive_wrath",
            name="Channel Divinity: Destructive Wrath",
            level=2,
            description="When you roll lightning or thunder damage, you can use your Channel Divinity to deal maximum damage instead of rolling.",
            feature_type=FeatureType.CHANNEL_DIVINITY,
        ),
        SubclassFeature(
            id="thunderbolt_strike",
            name="Thunderbolt Strike",
            level=6,
            description="When you deal lightning damage to a Large or smaller creature, you can also push it up to 10 feet away from you.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="divine_strike_tempest",
            name="Divine Strike",
            level=8,
            description="Once on each of your turns when you hit with a weapon attack, you deal an extra 1d8 thunder damage (2d8 at level 14).",
            feature_type=FeatureType.PASSIVE,
            scaling={8: {"dice": 1, "damage_type": "thunder"},
                    14: {"dice": 2, "damage_type": "thunder"}},
        ),
        SubclassFeature(
            id="stormborn",
            name="Stormborn",
            level=17,
            description="You have a flying speed equal to your walking speed whenever you are outdoors, in natural weather conditions such as rain or wind.",
            feature_type=FeatureType.PASSIVE,
        ),
    ],
    bonus_proficiencies=["martial_weapons", "heavy_armor"],
    # Domain Spells: fog cloud, thunderwave (1), gust of wind, shatter (3),
    # call lightning, sleet storm (5), control water, ice storm (7), destructive wave, insect plague (9)
)

KNOWLEDGE_DOMAIN = Subclass(
    id="knowledge_domain",
    name="Knowledge Domain",
    class_id="cleric",
    description="Gods of knowledge value learning and understanding above all.",
    features=[
        SubclassFeature(
            id="blessings_of_knowledge",
            name="Blessings of Knowledge",
            level=1,
            description="You learn two languages of your choice. You also become proficient in two of the following skills: Arcana, History, Nature, or Religion. Your proficiency bonus is doubled for any ability check you make using either of those skills.",
            feature_type=FeatureType.PASSIVE,
            grants_proficiency=["arcana", "history"],  # Default, player chooses
        ),
        SubclassFeature(
            id="channel_divinity_knowledge_of_the_ages",
            name="Channel Divinity: Knowledge of the Ages",
            level=2,
            description="As an action, you can choose one skill or tool. For 10 minutes, you have proficiency with the chosen skill or tool.",
            feature_type=FeatureType.CHANNEL_DIVINITY,
        ),
        SubclassFeature(
            id="channel_divinity_read_thoughts",
            name="Channel Divinity: Read Thoughts",
            level=6,
            description="As an action, choose a creature you can see within 60 feet. That creature must make a Wisdom saving throw. If it fails, you can read its surface thoughts for 1 minute. You can also cast Suggestion on it without expending a spell slot.",
            feature_type=FeatureType.CHANNEL_DIVINITY,
        ),
        SubclassFeature(
            id="potent_spellcasting_knowledge",
            name="Potent Spellcasting",
            level=8,
            description="You add your Wisdom modifier to the damage you deal with any cleric cantrip.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="visions_of_the_past",
            name="Visions of the Past",
            level=17,
            description="You can spend at least 1 minute in meditation to receive dreamlike visions about an object you're holding or your immediate surroundings. Object Reading reveals events within the last 24 hours per Wisdom modifier. Area Reading reveals significant events within the last 10 days per Wisdom modifier.",
            feature_type=FeatureType.ACTION,
            uses_per_rest=1,
        ),
    ],
    # Domain Spells: command, identify (1), augury, suggestion (3),
    # nondetection, speak with dead (5), arcane eye, confusion (7), legend lore, scrying (9)
)

TRICKERY_DOMAIN = Subclass(
    id="trickery_domain",
    name="Trickery Domain",
    class_id="cleric",
    description="Gods of trickery are mischief-makers and instigators who use deception and treachery.",
    features=[
        SubclassFeature(
            id="blessing_of_the_trickster",
            name="Blessing of the Trickster",
            level=1,
            description="You can use your action to touch a willing creature other than yourself to give it advantage on Dexterity (Stealth) checks. This blessing lasts for 1 hour or until you use this feature again.",
            feature_type=FeatureType.ACTION,
        ),
        SubclassFeature(
            id="channel_divinity_invoke_duplicity",
            name="Channel Divinity: Invoke Duplicity",
            level=2,
            description="As an action, you create a perfect illusion of yourself that lasts for 1 minute. As a bonus action, you can move it up to 30 feet. You can cast spells as though you were in the illusion's space. When both you and your illusion are within 5 feet of a creature, you have advantage on attack rolls against that creature.",
            feature_type=FeatureType.CHANNEL_DIVINITY,
        ),
        SubclassFeature(
            id="channel_divinity_cloak_of_shadows",
            name="Channel Divinity: Cloak of Shadows",
            level=6,
            description="As an action, you can use your Channel Divinity to become invisible until the end of your next turn. You become visible if you attack or cast a spell.",
            feature_type=FeatureType.CHANNEL_DIVINITY,
        ),
        SubclassFeature(
            id="divine_strike_trickery",
            name="Divine Strike",
            level=8,
            description="Once on each of your turns when you hit with a weapon attack, you deal an extra 1d8 poison damage (2d8 at level 14).",
            feature_type=FeatureType.PASSIVE,
            scaling={8: {"dice": 1, "damage_type": "poison"},
                    14: {"dice": 2, "damage_type": "poison"}},
        ),
        SubclassFeature(
            id="improved_duplicity",
            name="Improved Duplicity",
            level=17,
            description="You can create up to four duplicates of yourself with Invoke Duplicity, instead of one. As a bonus action, you can move any number of them up to 30 feet (max range 120 feet).",
            feature_type=FeatureType.PASSIVE,
        ),
    ],
    # Domain Spells: charm person, disguise self (1), mirror image, pass without trace (3),
    # blink, dispel magic (5), dimension door, polymorph (7), dominate person, modify memory (9)
)

# -----------------------------------------------------------------------------
# WIZARD SUBCLASSES (SCHOOLS)
# -----------------------------------------------------------------------------

SCHOOL_OF_EVOCATION = Subclass(
    id="evocation",
    name="School of Evocation",
    class_id="wizard",
    description="You focus your study on magic that creates powerful elemental effects.",
    features=[
        SubclassFeature(
            id="evocation_savant",
            name="Evocation Savant",
            level=2,
            description="Gold and time you spend to copy evocation spells is halved.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="sculpt_spells",
            name="Sculpt Spells",
            level=2,
            description="When you cast an evocation spell, you can choose a number of creatures equal to 1 + the spell's level. Those creatures automatically succeed on their saving throws and take no damage.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="potent_cantrip",
            name="Potent Cantrip",
            level=6,
            description="Your damaging cantrips deal half damage on a successful saving throw.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="empowered_evocation",
            name="Empowered Evocation",
            level=10,
            description="Add your Intelligence modifier to one damage roll of any wizard evocation spell you cast.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="overchannel",
            name="Overchannel",
            level=14,
            description="When you cast a wizard spell of 5th level or lower that deals damage, you can deal maximum damage. If you use this again before a long rest, you take necrotic damage.",
            feature_type=FeatureType.FREE,
            uses_per_rest=1,  # Free first use, then damage
        ),
    ]
)

SCHOOL_OF_ABJURATION = Subclass(
    id="abjuration",
    name="School of Abjuration",
    class_id="wizard",
    description="You focus on magic that blocks, banishes, or protects.",
    features=[
        SubclassFeature(
            id="abjuration_savant",
            name="Abjuration Savant",
            level=2,
            description="Gold and time you spend to copy abjuration spells is halved.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="arcane_ward",
            name="Arcane Ward",
            level=2,
            description="When you cast an abjuration spell, you create a magical ward with hit points equal to twice your wizard level + your Intelligence modifier. When you take damage, the ward takes it instead.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="projected_ward",
            name="Projected Ward",
            level=6,
            description="When a creature within 30 feet takes damage, you can use your reaction to have your Arcane Ward take the damage instead.",
            feature_type=FeatureType.REACTION,
        ),
        SubclassFeature(
            id="improved_abjuration",
            name="Improved Abjuration",
            level=10,
            description="When you cast an abjuration spell that requires an ability check (like Counterspell), add your proficiency bonus to that check.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="spell_resistance",
            name="Spell Resistance",
            level=14,
            description="You have advantage on saving throws against spells. You have resistance against the damage of spells.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)

SCHOOL_OF_NECROMANCY = Subclass(
    id="necromancy",
    name="School of Necromancy",
    class_id="wizard",
    description="You focus your studies on the magic that manipulates the forces of life and death.",
    features=[
        SubclassFeature(
            id="necromancy_savant",
            name="Necromancy Savant",
            level=2,
            description="Gold and time you spend to copy necromancy spells is halved.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="grim_harvest",
            name="Grim Harvest",
            level=2,
            description="When you kill a creature with a spell of 1st level or higher, you regain HP equal to twice the spell's level, or three times if it's a necromancy spell. You can't regain HP this way from constructs or undead.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="undead_thralls",
            name="Undead Thralls",
            level=6,
            description="You add the Animate Dead spell to your spellbook. When you cast Animate Dead, you can target one additional corpse or pile of bones. Undead you create with necromancy spells have additional benefits: their HP maximum increases by your wizard level, and they add your proficiency bonus to their weapon damage rolls.",
            feature_type=FeatureType.PASSIVE,
            grants_spells=["animate dead"],
        ),
        SubclassFeature(
            id="inured_to_undeath",
            name="Inured to Undeath",
            level=10,
            description="You have resistance to necrotic damage. Your hit point maximum can't be reduced.",
            feature_type=FeatureType.PASSIVE,
            grants_resistance=["necrotic"],
        ),
        SubclassFeature(
            id="command_undead",
            name="Command Undead",
            level=14,
            description="You can use your action to bring an undead under your control. The target must make a Charisma saving throw against your spell save DC. On a failure, it becomes friendly to you and obeys your commands. If the target has an Intelligence of 8 or higher, it has advantage on the save. If it has Intelligence of 12 or higher, it can repeat the save every hour.",
            feature_type=FeatureType.ACTION,
        ),
    ]
)

SCHOOL_OF_DIVINATION = Subclass(
    id="divination",
    name="School of Divination",
    class_id="wizard",
    description="You focus your studies on magic that reveals information otherwise hidden from the senses.",
    features=[
        SubclassFeature(
            id="divination_savant",
            name="Divination Savant",
            level=2,
            description="Gold and time you spend to copy divination spells is halved.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="portent",
            name="Portent",
            level=2,
            description="When you finish a long rest, roll two d20s and record the numbers. You can replace any attack roll, saving throw, or ability check made by you or a creature you can see with one of these foretelling rolls. You must choose to do so before the roll, and you can replace a roll in this way only once per turn. Each foretelling roll can be used only once.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="expert_divination",
            name="Expert Divination",
            level=6,
            description="When you cast a divination spell of 2nd level or higher using a spell slot, you regain one expended spell slot. The slot you regain must be of a level lower than the spell you cast and can't be higher than 5th level.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="the_third_eye",
            name="The Third Eye",
            level=10,
            description="You can use your action to increase your powers of perception. Choose one benefit: Darkvision (60 ft), Ethereal Sight (see into Ethereal Plane 60 ft), Greater Comprehension (read any language), or See Invisibility (see invisible creatures). This lasts until you are incapacitated or take a short/long rest.",
            feature_type=FeatureType.ACTION,
        ),
        SubclassFeature(
            id="greater_portent",
            name="Greater Portent",
            level=14,
            description="You roll three d20s for your Portent feature instead of two.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)

SCHOOL_OF_ILLUSION = Subclass(
    id="illusion",
    name="School of Illusion",
    class_id="wizard",
    description="You focus your studies on magic that dazzles the senses, befuddles the mind, and deceives even the wisest folk.",
    features=[
        SubclassFeature(
            id="illusion_savant",
            name="Illusion Savant",
            level=2,
            description="Gold and time you spend to copy illusion spells is halved.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="improved_minor_illusion",
            name="Improved Minor Illusion",
            level=2,
            description="You learn the Minor Illusion cantrip. When you cast it, you can create both a sound and an image with a single casting of the spell.",
            feature_type=FeatureType.PASSIVE,
            grants_spells=["minor illusion"],
        ),
        SubclassFeature(
            id="malleable_illusions",
            name="Malleable Illusions",
            level=6,
            description="When you cast an illusion spell that has a duration of 1 minute or longer, you can use your action to change the nature of that illusion (using the spell's normal parameters for the illusion), provided you can see the illusion.",
            feature_type=FeatureType.ACTION,
        ),
        SubclassFeature(
            id="illusory_self",
            name="Illusory Self",
            level=10,
            description="When a creature makes an attack roll against you, you can use your reaction to create an illusory duplicate. The attack automatically misses you, then the illusion dissipates. You regain the use of this feature after a short or long rest.",
            feature_type=FeatureType.REACTION,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="illusory_reality",
            name="Illusory Reality",
            level=14,
            description="When you cast an illusion spell of 1st level or higher, you can choose one inanimate, nonmagical object that is part of the illusion and make that object real. The object can't deal damage or directly harm anyone. The object remains real for 1 minute.",
            feature_type=FeatureType.FREE,
        ),
    ]
)

SCHOOL_OF_CONJURATION = Subclass(
    id="conjuration",
    name="School of Conjuration",
    class_id="wizard",
    description="You focus your studies on magic that produces objects and creatures out of thin air.",
    features=[
        SubclassFeature(
            id="conjuration_savant",
            name="Conjuration Savant",
            level=2,
            description="Gold and time you spend to copy conjuration spells is halved.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="minor_conjuration",
            name="Minor Conjuration",
            level=2,
            description="You can use your action to conjure up an inanimate object in your hand or on the ground in an unoccupied space within 10 feet. It must be no larger than 3 feet on a side and weigh no more than 10 pounds, and its form must be a nonmagical object you have seen. The object is visibly magical, radiating dim light out to 5 feet. It disappears after 1 hour, when you use this feature again, or if it takes or deals any damage.",
            feature_type=FeatureType.ACTION,
        ),
        SubclassFeature(
            id="benign_transposition",
            name="Benign Transposition",
            level=6,
            description="You can use your action to teleport up to 30 feet to an unoccupied space you can see. Alternatively, you can choose a space within range that is occupied by a Small or Medium creature. If that creature is willing, you both teleport, swapping places. You regain this ability after a long rest or when you cast a conjuration spell of 1st level or higher.",
            feature_type=FeatureType.ACTION,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="focused_conjuration",
            name="Focused Conjuration",
            level=10,
            description="While you are concentrating on a conjuration spell, your concentration can't be broken as a result of taking damage.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="durable_summons",
            name="Durable Summons",
            level=14,
            description="Any creature you summon or create with a conjuration spell has 30 temporary hit points.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)

# -----------------------------------------------------------------------------
# DRUID SUBCLASSES (CIRCLES)
# -----------------------------------------------------------------------------

CIRCLE_OF_THE_MOON = Subclass(
    id="circle_moon",
    name="Circle of the Moon",
    class_id="druid",
    description="You draw power from the moon, gaining the ability to transform into more powerful beasts.",
    features=[
        SubclassFeature(
            id="combat_wild_shape",
            name="Combat Wild Shape",
            level=2,
            description="You can use Wild Shape as a bonus action. When you transform, you gain temporary HP equal to 3 × your druid level. Your AC while transformed can be 13 + your Wisdom modifier if higher than the beast's AC.",
            feature_type=FeatureType.WILD_SHAPE,
        ),
        SubclassFeature(
            id="circle_forms_moon",
            name="Circle Forms",
            level=2,
            description="You can transform into beasts with CR 1 at level 2, and CR equal to your druid level / 3 (rounded down) at level 6+.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="moonlight_step",
            name="Moonlight Step",
            level=10,
            description="While in Wild Shape, you can teleport up to 30 feet as a bonus action. You can use this a number of times equal to your proficiency bonus per long rest.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="lunar_form",
            name="Lunar Form",
            level=14,
            description="While in Wild Shape, you have resistance to bludgeoning, piercing, and slashing damage. Your beast attacks deal an additional 2d10 radiant damage.",
            feature_type=FeatureType.PASSIVE,
            grants_resistance=["bludgeoning", "piercing", "slashing"],
        ),
    ]
)

CIRCLE_OF_THE_LAND = Subclass(
    id="circle_land",
    name="Circle of the Land",
    class_id="druid",
    description="You draw power from the land itself, gaining terrain-specific spells.",
    features=[
        SubclassFeature(
            id="bonus_cantrip",
            name="Bonus Cantrip",
            level=2,
            description="You learn one additional druid cantrip of your choice.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="natural_recovery",
            name="Natural Recovery",
            level=2,
            description="During a short rest, you can recover expended spell slots with a combined level equal to or less than half your druid level (rounded up). Slots must be 5th level or lower. Once used, you can't use this feature again until you finish a long rest.",
            feature_type=FeatureType.PASSIVE,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="circle_spells_land",
            name="Circle Spells",
            level=2,
            description="Your connection to a specific land grants you access to certain spells at druid levels 3, 5, 7, and 9. These spells are always prepared and don't count against your prepared spells.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="lands_stride",
            name="Land's Stride",
            level=6,
            description="Moving through nonmagical difficult terrain costs no extra movement. You can pass through nonmagical plants without being slowed or taking damage. You have advantage on saves against plants that are magically created or manipulated to impede movement.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="natures_ward",
            name="Nature's Ward",
            level=10,
            description="You can't be charmed or frightened by elementals or fey, and you are immune to poison and disease.",
            feature_type=FeatureType.PASSIVE,
            grants_immunity=["poison", "disease"],
        ),
        SubclassFeature(
            id="natures_sanctuary",
            name="Nature's Sanctuary",
            level=14,
            description="Beasts and plant creatures must make a Wisdom save to attack you. On a failed save, they must choose a different target or lose the attack.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)

CIRCLE_OF_THE_SEA = Subclass(
    id="circle_sea",
    name="Circle of the Sea",
    class_id="druid",
    description="You draw power from ocean depths, commanding the might of storms and tides.",
    features=[
        SubclassFeature(
            id="wrath_of_the_sea",
            name="Wrath of the Sea",
            level=2,
            description="As a bonus action, you create a churning aura of water around you. Hostile creatures that end their turn within 10 feet take cold damage. Uses equal to your Wisdom modifier per long rest.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="aquatic_affinity",
            name="Aquatic Affinity",
            level=2,
            description="You gain a swimming speed equal to your walking speed.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="aquatic_gifts",
            name="Aquatic Gifts",
            level=6,
            description="You can breathe underwater, and you can cast spells underwater without disadvantage on attack rolls.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="stormborn",
            name="Stormborn",
            level=10,
            description="When outdoors, you gain a flying speed of 60 feet. You have resistance to lightning and thunder damage.",
            feature_type=FeatureType.PASSIVE,
            grants_resistance=["lightning", "thunder"],
        ),
        SubclassFeature(
            id="oceanic_gift",
            name="Oceanic Gift",
            level=14,
            description="When you activate Wrath of the Sea, you can teleport up to 30 feet as part of the same bonus action.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)

CIRCLE_OF_THE_STARS = Subclass(
    id="circle_stars",
    name="Circle of the Stars",
    class_id="druid",
    description="You have traced your connection to the cosmos through starlight and ancient constellations.",
    features=[
        SubclassFeature(
            id="star_map",
            name="Star Map",
            level=2,
            description="You learn the Guidance cantrip if you don't already know it, and you always have Guiding Bolt prepared. You can cast Guiding Bolt without expending a spell slot once per long rest.",
            feature_type=FeatureType.PASSIVE,
            grants_spells=["guidance", "guiding_bolt"],
        ),
        SubclassFeature(
            id="starry_form",
            name="Starry Form",
            level=2,
            description="As a bonus action, you can expend a Wild Shape use to assume a starry form for 10 minutes. Choose a constellation: Archer (bonus action ranged spell attack for 1d8+WIS radiant), Chalice (bonus healing when you cast healing spell), or Dragon (minimum 10 on concentration checks).",
            feature_type=FeatureType.WILD_SHAPE,
        ),
        SubclassFeature(
            id="cosmic_omen",
            name="Cosmic Omen",
            level=6,
            description="When you finish a long rest, roll a die. On even (Weal), as a reaction you can add 1d6 to an ally's attack, save, or ability check within 30 feet. On odd (Woe), you can subtract 1d6 from an enemy's roll. Uses equal to proficiency bonus per long rest.",
            feature_type=FeatureType.REACTION,
        ),
        SubclassFeature(
            id="twinkling_constellations",
            name="Twinkling Constellations",
            level=10,
            description="You can change your Starry Form constellation at the start of each of your turns. While in Dragon constellation, you gain a 20-foot fly speed (hover).",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="full_of_stars",
            name="Full of Stars",
            level=14,
            description="While in Starry Form, you have resistance to bludgeoning, piercing, and slashing damage.",
            feature_type=FeatureType.PASSIVE,
            grants_resistance=["bludgeoning", "piercing", "slashing"],
        ),
    ]
)

# -----------------------------------------------------------------------------
# WARLOCK SUBCLASSES (PATRONS)
# -----------------------------------------------------------------------------

THE_FIEND = Subclass(
    id="fiend",
    name="The Fiend",
    class_id="warlock",
    description="You have made a pact with a fiend from the lower planes of existence, a being whose aims are evil.",
    features=[
        SubclassFeature(
            id="dark_ones_blessing",
            name="Dark One's Blessing",
            level=1,
            description="When you reduce a hostile creature to 0 HP, gain temporary HP equal to your Charisma modifier + your warlock level (minimum of 1).",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="dark_ones_own_luck",
            name="Dark One's Own Luck",
            level=6,
            description="When you make an ability check or saving throw, you can add 1d10 to the roll. You can use this feature once per short or long rest.",
            feature_type=FeatureType.FREE,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="fiendish_resilience",
            name="Fiendish Resilience",
            level=10,
            description="When you finish a short or long rest, choose one damage type. You have resistance to that damage type until you choose a different one.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="hurl_through_hell",
            name="Hurl Through Hell",
            level=14,
            description="When you hit a creature with an attack, you can banish it to the lower planes. It takes 10d10 psychic damage when it returns. Once per long rest.",
            feature_type=FeatureType.PASSIVE,
            uses_per_rest=1,
        ),
    ]
)

THE_ARCHFEY = Subclass(
    id="archfey",
    name="The Archfey",
    class_id="warlock",
    description="Your patron is a lord or lady of the fey, a creature of legend who holds secrets from before mortal races were born.",
    features=[
        SubclassFeature(
            id="fey_presence",
            name="Fey Presence",
            level=1,
            description="As an action, cause creatures in a 10-foot cube to make a Wisdom save or become charmed or frightened until the end of your next turn. Once per short or long rest.",
            feature_type=FeatureType.ACTION,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="misty_escape",
            name="Misty Escape",
            level=6,
            description="When you take damage, you can use your reaction to turn invisible and teleport up to 60 feet. Once per short or long rest.",
            feature_type=FeatureType.REACTION,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="beguiling_defenses",
            name="Beguiling Defenses",
            level=10,
            description="You are immune to being charmed, and when another creature attempts to charm you, you can turn the charm back on it.",
            feature_type=FeatureType.PASSIVE,
            grants_immunity=["charmed"],
        ),
        SubclassFeature(
            id="dark_delirium",
            name="Dark Delirium",
            level=14,
            description="As an action, choose a creature within 60 feet. It must make a Wisdom save or be charmed or frightened for 1 minute. Once per short or long rest.",
            feature_type=FeatureType.ACTION,
            uses_per_rest=1,
        ),
    ]
)

THE_GREAT_OLD_ONE = Subclass(
    id="great_old_one",
    name="The Great Old One",
    class_id="warlock",
    description="Your patron is a mysterious entity whose nature is utterly foreign to the fabric of reality.",
    features=[
        SubclassFeature(
            id="awakened_mind",
            name="Awakened Mind",
            level=1,
            description="You can telepathically speak to any creature you can see within 30 feet. The creature understands you if it knows at least one language.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="entropic_ward",
            name="Entropic Ward",
            level=6,
            description="When a creature makes an attack roll against you, use your reaction to impose disadvantage. If the attack misses, gain advantage on your next attack against it.",
            feature_type=FeatureType.REACTION,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="thought_shield",
            name="Thought Shield",
            level=10,
            description="Your thoughts can't be read by telepathy or other means. You have resistance to psychic damage.",
            feature_type=FeatureType.PASSIVE,
            grants_resistance=["psychic"],
        ),
        SubclassFeature(
            id="create_thrall",
            name="Create Thrall",
            level=14,
            description="Touch an incapacitated humanoid to charm it. It is charmed by you until Remove Curse is cast on it or you use this feature again.",
            feature_type=FeatureType.ACTION,
        ),
    ]
)

THE_CELESTIAL = Subclass(
    id="celestial",
    name="The Celestial",
    class_id="warlock",
    description="Your patron is a powerful being of the Upper Planes, such as a solar, an empyrean, or an archon.",
    features=[
        SubclassFeature(
            id="healing_light",
            name="Healing Light",
            level=1,
            description="You have a pool of d6s equal to 1 + your warlock level. As a bonus action, heal a creature within 60 feet by spending dice from the pool.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="radiant_soul",
            name="Radiant Soul",
            level=6,
            description="You have resistance to radiant damage. When you cast a spell that deals fire or radiant damage, add your Charisma modifier to one damage roll.",
            feature_type=FeatureType.PASSIVE,
            grants_resistance=["radiant"],
        ),
        SubclassFeature(
            id="celestial_resilience",
            name="Celestial Resilience",
            level=10,
            description="When you finish a short or long rest, you and up to five creatures gain temporary HP equal to your warlock level + Charisma modifier.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="searing_vengeance",
            name="Searing Vengeance",
            level=14,
            description="When you make a death saving throw at the start of your turn, you can instead regain HP equal to half your HP maximum and stand up. Creatures within 30 feet take radiant damage and are blinded. Once per long rest.",
            feature_type=FeatureType.PASSIVE,
            uses_per_rest=1,
        ),
    ]
)

THE_HEXBLADE = Subclass(
    id="hexblade",
    name="The Hexblade",
    class_id="warlock",
    description="You have made your pact with a mysterious entity from the Shadowfell, a force that manifests in sentient magic weapons.",
    bonus_proficiencies=["medium_armor", "shields", "martial_weapons"],
    features=[
        SubclassFeature(
            id="hexblades_curse",
            name="Hexblade's Curse",
            level=1,
            description="As a bonus action, curse a creature within 30 feet. Gain bonus damage equal to proficiency, crit on 19-20, regain HP equal to warlock level + CHA mod on its death.",
            feature_type=FeatureType.BONUS_ACTION,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="hex_warrior",
            name="Hex Warrior",
            level=1,
            description="Gain proficiency with medium armor, shields, and martial weapons. You can use Charisma for attack and damage with one weapon you touch (or your pact weapon).",
            feature_type=FeatureType.PASSIVE,
            grants_proficiency=["medium_armor", "shields", "martial_weapons"],
        ),
        SubclassFeature(
            id="accursed_specter",
            name="Accursed Specter",
            level=6,
            description="When you slay a humanoid, raise it as a specter that serves you until your next long rest. It gains bonus HP equal to half your warlock level.",
            feature_type=FeatureType.PASSIVE,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="armor_of_hexes",
            name="Armor of Hexes",
            level=10,
            description="If the target of your Hexblade's Curse hits you with an attack, roll a d6. On a 4 or higher, the attack instead misses.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="master_of_hexes",
            name="Master of Hexes",
            level=14,
            description="When a creature cursed by your Hexblade's Curse dies, you can apply the curse to a different creature within 30 feet without expending a use.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)

THE_FATHOMLESS = Subclass(
    id="fathomless",
    name="The Fathomless",
    class_id="warlock",
    description="You have plunged into a pact with the deeps. An entity of the ocean has granted you access to abyssal power.",
    features=[
        SubclassFeature(
            id="tentacle_of_the_deeps",
            name="Tentacle of the Deeps",
            level=1,
            description="As a bonus action, summon a spectral tentacle within 60 feet. It can make melee spell attacks for 1d8 cold damage and reduce target's speed by 10 feet.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="gift_of_the_sea",
            name="Gift of the Sea",
            level=1,
            description="You gain a swimming speed of 40 feet, and you can breathe underwater.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="oceanic_soul",
            name="Oceanic Soul",
            level=6,
            description="You gain resistance to cold damage. When fully submerged, you and creatures you choose within 30 feet can speak underwater.",
            feature_type=FeatureType.PASSIVE,
            grants_resistance=["cold"],
        ),
        SubclassFeature(
            id="guardian_coil",
            name="Guardian Coil",
            level=6,
            description="When you or a creature you can see within 10 feet of your tentacle takes damage, use your reaction to have the tentacle absorb the damage (reduces by 1d8).",
            feature_type=FeatureType.REACTION,
        ),
        SubclassFeature(
            id="grasping_tentacles",
            name="Grasping Tentacles",
            level=10,
            description="You can cast Evard's Black Tentacles once without a spell slot. When you cast it this way, you can concentrate on it and another spell simultaneously.",
            feature_type=FeatureType.PASSIVE,
            uses_per_rest=1,
            grants_spells=["evards_black_tentacles"],
        ),
        SubclassFeature(
            id="fathomless_plunge",
            name="Fathomless Plunge",
            level=14,
            description="As an action, teleport yourself and up to 5 willing creatures within 30 feet to a body of water you've seen (within 1 mile). Once per short or long rest.",
            feature_type=FeatureType.ACTION,
            uses_per_rest=1,
        ),
    ]
)

THE_GENIE = Subclass(
    id="genie",
    name="The Genie",
    class_id="warlock",
    description="You have made a pact with one of the rarest kinds of genie, a noble genie. Such entities rule vast fiefs and command great respect.",
    features=[
        SubclassFeature(
            id="genies_vessel",
            name="Genie's Vessel",
            level=1,
            description="Your patron gives you a magical vessel. As an action, you can vanish into your vessel for hours equal to twice your proficiency bonus.",
            feature_type=FeatureType.ACTION,
        ),
        SubclassFeature(
            id="bottled_respite",
            name="Bottled Respite",
            level=1,
            description="While inside your vessel, you can hear the area around it. Your vessel has AC equal to your spell save DC. If destroyed, you appear in the nearest space.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="genies_wrath",
            name="Genie's Wrath",
            level=1,
            description="Once during each of your turns when you hit with an attack, deal extra damage equal to your proficiency bonus. Damage type depends on your genie kind.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="elemental_gift",
            name="Elemental Gift",
            level=6,
            description="You gain resistance to a damage type based on your genie's kind. As a bonus action, gain a flying speed of 30 feet for 10 minutes. Uses equal to proficiency bonus per long rest.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="sanctuary_vessel",
            name="Sanctuary Vessel",
            level=10,
            description="Up to 5 creatures can enter your vessel with you. When you exit, everyone exits. Creatures inside gain the benefits of a short rest.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="limited_wish",
            name="Limited Wish",
            level=14,
            description="As an action, speak to your patron for a limited wish: cast any spell of 6th level or lower with a casting time of 1 action without material components. Once per 1d4 long rests.",
            feature_type=FeatureType.ACTION,
            uses_per_rest=1,
        ),
    ]
)

THE_UNDEAD = Subclass(
    id="undead",
    name="The Undead",
    class_id="warlock",
    description="You have made a pact with a deathless being, a creature that defies the cycle of life and death.",
    features=[
        SubclassFeature(
            id="form_of_dread",
            name="Form of Dread",
            level=1,
            description="As a bonus action, transform for 1 minute: gain temp HP equal to 1d10 + warlock level, once per turn when you hit, target must make WIS save or be frightened until end of your next turn, you are immune to the frightened condition.",
            feature_type=FeatureType.BONUS_ACTION,
            grants_immunity=["frightened"],
        ),
        SubclassFeature(
            id="grave_touched",
            name="Grave Touched",
            level=6,
            description="You don't need to eat, drink, or breathe. Once per turn, you can change the damage type of an attack to necrotic, and roll one additional damage die.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="necrotic_husk",
            name="Necrotic Husk",
            level=10,
            description="You have resistance to necrotic damage. If you're reduced to 0 HP, you can drop to 1 HP instead and each creature within 30 feet takes necrotic damage. Once per long rest.",
            feature_type=FeatureType.PASSIVE,
            uses_per_rest=1,
            grants_resistance=["necrotic"],
        ),
        SubclassFeature(
            id="spirit_projection",
            name="Spirit Projection",
            level=14,
            description="As an action, project your spirit from your body for up to 1 hour. Your body is unconscious. Your spirit has resistance to bludgeoning, piercing, and slashing damage. Once per long rest.",
            feature_type=FeatureType.ACTION,
            uses_per_rest=1,
        ),
    ]
)

# -----------------------------------------------------------------------------
# SORCERER SUBCLASSES (ORIGINS)
# -----------------------------------------------------------------------------

DRACONIC_BLOODLINE = Subclass(
    id="draconic_bloodline",
    name="Draconic Bloodline",
    class_id="sorcerer",
    description="Your innate magic comes from draconic magic that was mingled with your blood or that of your ancestors.",
    features=[
        SubclassFeature(
            id="dragon_ancestor",
            name="Dragon Ancestor",
            level=1,
            description="Choose a dragon type (black, blue, brass, bronze, copper, gold, green, red, silver, white). You learn Draconic and have advantage on Charisma checks with dragons.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="draconic_resilience",
            name="Draconic Resilience",
            level=1,
            description="Your HP maximum increases by 1 for each sorcerer level. When unarmored, your AC equals 13 + your Dexterity modifier.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="elemental_affinity",
            name="Elemental Affinity",
            level=6,
            description="Add your Charisma modifier to damage of spells matching your dragon's damage type. Spend 1 sorcery point to gain resistance to that damage type for 1 hour.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="dragon_wings",
            name="Dragon Wings",
            level=14,
            description="As a bonus action, sprout dragon wings gaining a flying speed equal to your walking speed.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="draconic_presence",
            name="Draconic Presence",
            level=18,
            description="Spend 5 sorcery points to emanate an aura of awe or fear (60 feet) for 1 minute. Creatures must save or be charmed/frightened.",
            feature_type=FeatureType.ACTION,
            resource_type="sorcery_points",
            resource_cost=5,
        ),
    ]
)

WILD_MAGIC_ORIGIN = Subclass(
    id="wild_magic",
    name="Wild Magic",
    class_id="sorcerer",
    description="Your innate magic comes from the wild forces of chaos that underlie the order of creation.",
    features=[
        SubclassFeature(
            id="wild_magic_surge",
            name="Wild Magic Surge",
            level=1,
            description="After casting a sorcerer spell of 1st level or higher, DM can have you roll d20. On 1, roll on the Wild Magic Surge table for a random magical effect.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="tides_of_chaos",
            name="Tides of Chaos",
            level=1,
            description="Gain advantage on one attack roll, ability check, or saving throw. Regain use after long rest or when DM triggers a Wild Magic Surge.",
            feature_type=FeatureType.FREE,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="bend_luck",
            name="Bend Luck",
            level=6,
            description="When a creature you see makes an attack roll, ability check, or saving throw, spend 2 sorcery points as a reaction to roll 1d4 and add or subtract from their roll.",
            feature_type=FeatureType.REACTION,
            resource_type="sorcery_points",
            resource_cost=2,
        ),
        SubclassFeature(
            id="controlled_chaos",
            name="Controlled Chaos",
            level=14,
            description="When you roll on the Wild Magic Surge table, roll twice and use either number.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="spell_bombardment",
            name="Spell Bombardment",
            level=18,
            description="When you roll maximum on a damage die for a spell, roll that die again and add the extra damage once per turn.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)

DIVINE_SOUL_ORIGIN = Subclass(
    id="divine_soul",
    name="Divine Soul",
    class_id="sorcerer",
    description="Your link to the divine allows your magic to touch the celestial or fiendish realms.",
    features=[
        SubclassFeature(
            id="divine_magic",
            name="Divine Magic",
            level=1,
            description="You can learn spells from the cleric spell list in addition to sorcerer spells. Choose an affinity (Good/Evil/Law/Chaos/Neutrality) for a bonus spell.",
            feature_type=FeatureType.PASSIVE,
            grants_spells=["cure_wounds"],
        ),
        SubclassFeature(
            id="favored_by_the_gods",
            name="Favored by the Gods",
            level=1,
            description="When you fail a saving throw or miss with an attack roll, add 2d4 to the total. Once per short or long rest.",
            feature_type=FeatureType.FREE,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="empowered_healing",
            name="Empowered Healing",
            level=6,
            description="When you or an ally within 5 feet rolls dice to heal, spend 1 sorcery point to reroll any number of those dice once.",
            feature_type=FeatureType.FREE,
            resource_type="sorcery_points",
            resource_cost=1,
        ),
        SubclassFeature(
            id="otherworldly_wings",
            name="Otherworldly Wings",
            level=14,
            description="As a bonus action, manifest spectral wings gaining a flying speed of 30 feet.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="unearthly_recovery",
            name="Unearthly Recovery",
            level=18,
            description="As a bonus action when you have fewer than half your hit points, regain HP equal to half your maximum. Once per long rest.",
            feature_type=FeatureType.BONUS_ACTION,
            uses_per_rest=1,
        ),
    ]
)

SHADOW_MAGIC_ORIGIN = Subclass(
    id="shadow_magic",
    name="Shadow Magic",
    class_id="sorcerer",
    description="You are a creature of shadow, and your magic draws from the cold darkness of the Shadowfell.",
    features=[
        SubclassFeature(
            id="eyes_of_the_dark",
            name="Eyes of the Dark",
            level=1,
            description="You have darkvision 120 feet. At 3rd level, learn Darkness (doesn't count against spells known). Cast it with 2 sorcery points and see through it.",
            feature_type=FeatureType.PASSIVE,
            grants_spells=["darkness"],
        ),
        SubclassFeature(
            id="strength_of_the_grave",
            name="Strength of the Grave",
            level=1,
            description="When damage reduces you to 0 HP, make a CHA save (DC 5 + damage). On success, drop to 1 HP instead. Doesn't work against radiant or critical hits.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="hound_of_ill_omen",
            name="Hound of Ill Omen",
            level=6,
            description="Spend 3 sorcery points as a bonus action to summon a dire wolf that hunts a target within 120 feet.",
            feature_type=FeatureType.BONUS_ACTION,
            resource_type="sorcery_points",
            resource_cost=3,
        ),
        SubclassFeature(
            id="shadow_walk",
            name="Shadow Walk",
            level=14,
            description="As a bonus action when in dim light or darkness, teleport up to 120 feet to another space in dim light or darkness.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="umbral_form",
            name="Umbral Form",
            level=18,
            description="Spend 6 sorcery points to become a shadow for 1 minute: resistance to all damage except force and radiant, and can move through creatures/objects.",
            feature_type=FeatureType.BONUS_ACTION,
            resource_type="sorcery_points",
            resource_cost=6,
        ),
    ]
)

STORM_SORCERY_ORIGIN = Subclass(
    id="storm_sorcery",
    name="Storm Sorcery",
    class_id="sorcerer",
    description="Your innate magic comes from the power of elemental air and storm.",
    features=[
        SubclassFeature(
            id="wind_speaker",
            name="Wind Speaker",
            level=1,
            description="You can speak, read, and write Primordial and its dialects (Aquan, Auran, Ignan, Terran).",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="tempestuous_magic",
            name="Tempestuous Magic",
            level=1,
            description="After casting a spell of 1st level or higher, use a bonus action to fly up to 10 feet without provoking opportunity attacks.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="heart_of_the_storm",
            name="Heart of the Storm",
            level=6,
            description="Gain resistance to lightning and thunder damage. When you cast a lightning/thunder spell, deal half your sorcerer level as damage to creatures within 10 feet.",
            feature_type=FeatureType.PASSIVE,
            grants_resistance=["lightning", "thunder"],
        ),
        SubclassFeature(
            id="storm_guide",
            name="Storm Guide",
            level=6,
            description="If it's raining, use an action to stop rain in a 20-foot radius. You can also create calm winds around yourself.",
            feature_type=FeatureType.ACTION,
        ),
        SubclassFeature(
            id="storms_fury",
            name="Storm's Fury",
            level=14,
            description="When hit by a melee attack, use your reaction to deal lightning damage equal to your sorcerer level and force a STR save or be pushed 20 feet.",
            feature_type=FeatureType.REACTION,
        ),
        SubclassFeature(
            id="wind_soul",
            name="Wind Soul",
            level=18,
            description="Gain immunity to lightning and thunder damage and a 60-foot flying speed. Can reduce to 30 feet to grant 30-foot flight to 3+CHA creatures for 1 hour.",
            feature_type=FeatureType.PASSIVE,
            grants_immunity=["lightning", "thunder"],
        ),
    ]
)

ABERRANT_MIND_ORIGIN = Subclass(
    id="aberrant_mind",
    name="Aberrant Mind",
    class_id="sorcerer",
    description="An alien influence has wrapped its tendrils around your mind, giving you psionic power.",
    features=[
        SubclassFeature(
            id="psionic_spells",
            name="Psionic Spells",
            level=1,
            description="You learn additional spells that don't count against your spells known: Arms of Hadar, Dissonant Whispers (1st), Calm Emotions, Detect Thoughts (3rd), and more.",
            feature_type=FeatureType.PASSIVE,
            grants_spells=["arms_of_hadar", "dissonant_whispers"],
        ),
        SubclassFeature(
            id="telepathic_speech",
            name="Telepathic Speech",
            level=1,
            description="As a bonus action, establish telepathy with a creature within 30 feet. You can communicate for a number of miles equal to your Charisma modifier.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="psionic_sorcery",
            name="Psionic Sorcery",
            level=6,
            description="Cast Psionic Spells using sorcery points equal to the spell's level instead of a spell slot. No verbal or somatic components needed.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="psychic_defenses",
            name="Psychic Defenses",
            level=6,
            description="You gain resistance to psychic damage and advantage on saves against being charmed or frightened.",
            feature_type=FeatureType.PASSIVE,
            grants_resistance=["psychic"],
        ),
        SubclassFeature(
            id="revelation_in_flesh",
            name="Revelation in Flesh",
            level=14,
            description="Spend 1+ sorcery points as a bonus action to transform for 10 minutes: see invisible, swim + breathe water, squeeze through 1-inch spaces, or hover.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="warping_implosion",
            name="Warping Implosion",
            level=18,
            description="As an action, teleport 120 feet. Creatures within 30 feet of your origin must save or take 3d10 force damage and be pulled toward the space. Once per long rest.",
            feature_type=FeatureType.ACTION,
            uses_per_rest=1,
        ),
    ]
)

CLOCKWORK_SOUL_ORIGIN = Subclass(
    id="clockwork_soul",
    name="Clockwork Soul",
    class_id="sorcerer",
    description="The cosmic force of order has suffused you with magic from the plane of Mechanus.",
    features=[
        SubclassFeature(
            id="clockwork_magic",
            name="Clockwork Magic",
            level=1,
            description="You learn additional spells that don't count against your spells known: Alarm, Protection from Evil and Good (1st), Aid, Lesser Restoration (3rd), and more.",
            feature_type=FeatureType.PASSIVE,
            grants_spells=["alarm", "protection_from_evil_and_good"],
        ),
        SubclassFeature(
            id="restore_balance",
            name="Restore Balance",
            level=1,
            description="When a creature within 60 feet rolls with advantage or disadvantage, use your reaction to cancel it. Uses equal to proficiency bonus per long rest.",
            feature_type=FeatureType.REACTION,
        ),
        SubclassFeature(
            id="bastion_of_law",
            name="Bastion of Law",
            level=6,
            description="As an action, spend 1-5 sorcery points to create a ward on a creature with that many d8s. Expend dice to reduce damage taken.",
            feature_type=FeatureType.ACTION,
            resource_type="sorcery_points",
        ),
        SubclassFeature(
            id="trance_of_order",
            name="Trance of Order",
            level=14,
            description="As a bonus action, enter a trance for 1 minute: attacks can't benefit from advantage against you, and you treat rolls of 9 or lower as 10.",
            feature_type=FeatureType.BONUS_ACTION,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="clockwork_cavalcade",
            name="Clockwork Cavalcade",
            level=18,
            description="As an action, summon spirits of order in a 30-foot cube. Each creature of your choice takes 100 damage, and you can restore HP or repair objects.",
            feature_type=FeatureType.ACTION,
            uses_per_rest=1,
        ),
    ]
)


# =============================================================================
# RANGER SUBCLASSES
# =============================================================================

BEAST_MASTER = Subclass(
    id="beast_master",
    name="Beast Master",
    class_id="ranger",
    description="You form a mystical bond with a beast companion that fights alongside you.",
    features=[
        SubclassFeature(
            id="primal_companion",
            name="Primal Companion",
            level=3,
            description="You magically summon a primal beast (Beast of the Land, Sea, or Sky). It obeys your commands and acts on your turn. It gains proficiency bonus to AC, attacks, damage, saves, and skills.",
            feature_type=FeatureType.ACTION,
        ),
        SubclassFeature(
            id="exceptional_training",
            name="Exceptional Training",
            level=7,
            description="On your turn, you can command your beast to take the Dash, Disengage, or Help action as a bonus action. When you cast a spell with a range of self, it can also affect your beast.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="bestial_fury",
            name="Bestial Fury",
            level=11,
            description="Your companion can make two attacks when you command it to attack. When you command it to take the Attack action, you can also make one weapon attack yourself.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="share_spells",
            name="Share Spells",
            level=15,
            description="When you cast a spell targeting yourself, you can also affect your beast companion if it is within 30 feet of you.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)

HUNTER = Subclass(
    id="hunter",
    name="Hunter",
    class_id="ranger",
    description="You excel at the deadly art of hunting monsters and foes.",
    features=[
        SubclassFeature(
            id="hunters_prey",
            name="Hunter's Prey",
            level=3,
            description="Choose one: Colossus Slayer (extra 1d8 damage to wounded targets), Giant Killer (reaction attack when Large+ misses you), or Horde Breaker (extra attack against adjacent enemy).",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="defensive_tactics",
            name="Defensive Tactics",
            level=7,
            description="Choose one: Escape the Horde (disadvantage on opportunity attacks against you), Multiattack Defense (+4 AC after being hit), or Steel Will (advantage vs frightened).",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="multiattack",
            name="Multiattack",
            level=11,
            description="Choose one: Volley (ranged attack against all creatures in 10-foot radius) or Whirlwind Attack (melee attack against all creatures in reach).",
            feature_type=FeatureType.ACTION,
        ),
        SubclassFeature(
            id="superior_hunters_defense",
            name="Superior Hunter's Defense",
            level=15,
            description="Choose one: Evasion, Stand Against the Tide (redirect attack to another creature), or Uncanny Dodge.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)

GLOOM_STALKER = Subclass(
    id="gloom_stalker",
    name="Gloom Stalker",
    class_id="ranger",
    description="You are at home in the darkest places, using shadows and fear as your weapons.",
    features=[
        SubclassFeature(
            id="dread_ambusher",
            name="Dread Ambusher",
            level=3,
            description="Add WIS modifier to initiative. On the first turn of combat, your speed increases by 10 feet and you can make one extra attack that deals an additional 1d8 damage.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="umbral_sight",
            name="Umbral Sight",
            level=3,
            description="You gain darkvision 60 feet, or add 30 feet if you already have it. While in darkness, you are invisible to creatures relying on darkvision.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="iron_mind",
            name="Iron Mind",
            level=7,
            description="You gain proficiency in Wisdom saving throws. If you already have it, gain Intelligence or Charisma saves instead.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="stalkers_flurry",
            name="Stalker's Flurry",
            level=11,
            description="Once per turn, when you miss with a weapon attack, you can make another weapon attack as part of the same action.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="shadowy_dodge",
            name="Shadowy Dodge",
            level=15,
            description="When a creature attacks you without advantage, use your reaction to impose disadvantage on the attack roll.",
            feature_type=FeatureType.REACTION,
        ),
    ]
)

FEY_WANDERER = Subclass(
    id="fey_wanderer",
    name="Fey Wanderer",
    class_id="ranger",
    description="A mystical bond to the Feywild grants you beguiling powers and fey magic.",
    features=[
        SubclassFeature(
            id="dreadful_strikes",
            name="Dreadful Strikes",
            level=3,
            description="Once per turn, when you hit a creature, you can deal an extra 1d4 psychic damage. This increases to 1d6 at level 11.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="otherworldly_glamour",
            name="Otherworldly Glamour",
            level=3,
            description="Add your WIS modifier to Charisma checks. You gain proficiency in Deception, Performance, or Persuasion.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="beguiling_twist",
            name="Beguiling Twist",
            level=7,
            description="When you or an ally within 120 feet succeeds on a save against charmed or frightened, use your reaction to force another creature to make a WIS save or be charmed/frightened.",
            feature_type=FeatureType.REACTION,
        ),
        SubclassFeature(
            id="fey_reinforcements",
            name="Fey Reinforcements",
            level=11,
            description="You learn Summon Fey. You can cast it once without a spell slot per long rest, and fey summoned are immune to charm.",
            feature_type=FeatureType.PASSIVE,
            grants_spells=["summon_fey"],
        ),
        SubclassFeature(
            id="misty_wanderer",
            name="Misty Wanderer",
            level=15,
            description="You can cast Misty Step without expending a spell slot a number of times equal to your WIS modifier. When you do, you can bring one willing creature within 5 feet.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
    ]
)


# =============================================================================
# MONK SUBCLASSES
# =============================================================================

WAY_OF_THE_OPEN_HAND = Subclass(
    id="open_hand",
    name="Way of the Open Hand",
    class_id="monk",
    description="You master the art of unarmed combat, manipulating your foe's ki against them.",
    features=[
        SubclassFeature(
            id="open_hand_technique",
            name="Open Hand Technique",
            level=3,
            description="When you hit with a Flurry of Blows attack, you can impose one effect: knock prone (DEX save), push 15 feet (STR save), or prevent reactions until end of your next turn.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="wholeness_of_body",
            name="Wholeness of Body",
            level=6,
            description="As an action, regain HP equal to 3 times your monk level. Once per long rest.",
            feature_type=FeatureType.ACTION,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="tranquility",
            name="Tranquility",
            level=11,
            description="At the end of a long rest, you gain the effect of Sanctuary until the start of your next long rest or until you attack/cast a spell.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="quivering_palm",
            name="Quivering Palm",
            level=17,
            description="When you hit with an unarmed strike, spend 3 ki points to set up lethal vibrations. Within 17 days, use an action to end them: CON save or reduced to 0 HP, or 10d10 necrotic on success.",
            feature_type=FeatureType.ACTION,
            resource_type="ki_points",
            resource_cost=3,
        ),
    ]
)

WAY_OF_SHADOW = Subclass(
    id="shadow",
    name="Way of Shadow",
    class_id="monk",
    description="You follow a tradition that values stealth, subterfuge, and the arts of the ninja.",
    features=[
        SubclassFeature(
            id="shadow_arts",
            name="Shadow Arts",
            level=3,
            description="Spend 2 ki points to cast Darkness, Darkvision, Pass without Trace, or Silence. You can also cast Minor Illusion as a cantrip.",
            feature_type=FeatureType.ACTION,
            resource_type="ki_points",
            resource_cost=2,
            grants_spells=["minor_illusion", "darkness", "darkvision", "pass_without_trace", "silence"],
        ),
        SubclassFeature(
            id="shadow_step",
            name="Shadow Step",
            level=6,
            description="As a bonus action, teleport up to 60 feet from one dim light/darkness to another. You have advantage on the first melee attack you make before the end of the turn.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="cloak_of_shadows",
            name="Cloak of Shadows",
            level=11,
            description="As an action when in dim light or darkness, become invisible until you attack, cast a spell, or enter bright light.",
            feature_type=FeatureType.ACTION,
        ),
        SubclassFeature(
            id="opportunist",
            name="Opportunist",
            level=17,
            description="When a creature within 5 feet is hit by an attack from someone other than you, you can use your reaction to make a melee attack against that creature.",
            feature_type=FeatureType.REACTION,
        ),
    ]
)

WAY_OF_MERCY = Subclass(
    id="mercy",
    name="Way of Mercy",
    class_id="monk",
    description="You learn to manipulate the life force of others to bring relief or suffering.",
    features=[
        SubclassFeature(
            id="implements_of_mercy",
            name="Implements of Mercy",
            level=3,
            description="You gain proficiency in Insight and Medicine, and with the herbalism kit. You also gain a special mercy mask.",
            feature_type=FeatureType.PASSIVE,
            grants_proficiency=["insight", "medicine", "herbalism_kit"],
        ),
        SubclassFeature(
            id="hand_of_healing",
            name="Hand of Healing",
            level=3,
            description="As an action, spend 1 ki point to touch a creature and restore HP equal to martial arts die + WIS modifier. Can replace one Flurry of Blows attack with this.",
            feature_type=FeatureType.ACTION,
            resource_type="ki_points",
            resource_cost=1,
        ),
        SubclassFeature(
            id="hand_of_harm",
            name="Hand of Harm",
            level=3,
            description="When you hit with an unarmed strike, spend 1 ki point to deal extra necrotic damage equal to martial arts die + WIS modifier. Can poison the target (CON save).",
            feature_type=FeatureType.PASSIVE,
            resource_type="ki_points",
            resource_cost=1,
        ),
        SubclassFeature(
            id="physicians_touch",
            name="Physician's Touch",
            level=6,
            description="Hand of Healing can also end one disease or condition (blinded, deafened, paralyzed, poisoned, stunned). Hand of Harm can also poison without extra ki.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="flurry_of_healing_and_harm",
            name="Flurry of Healing and Harm",
            level=11,
            description="When you use Flurry of Blows, you can replace each attack with Hand of Healing (no ki cost). Hand of Harm can be used on each Flurry attack.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="hand_of_ultimate_mercy",
            name="Hand of Ultimate Mercy",
            level=17,
            description="As an action, touch a creature that died within 24 hours and spend 5 ki points to return it to life with 4d10 + WIS modifier HP. Once per long rest.",
            feature_type=FeatureType.ACTION,
            resource_type="ki_points",
            resource_cost=5,
            uses_per_rest=1,
        ),
    ]
)

WAY_OF_FOUR_ELEMENTS = Subclass(
    id="four_elements",
    name="Way of the Four Elements",
    class_id="monk",
    description="You harness the power of the elements through your ki, casting elemental spells.",
    features=[
        SubclassFeature(
            id="disciple_of_the_elements",
            name="Disciple of the Elements",
            level=3,
            description="You learn Elemental Attunement and one elemental discipline. You gain more at levels 6, 11, and 17. Use ki points to fuel them.",
            feature_type=FeatureType.ACTION,
            resource_type="ki_points",
        ),
        SubclassFeature(
            id="elemental_disciplines_6",
            name="Additional Discipline",
            level=6,
            description="Learn one additional elemental discipline and can replace one known discipline.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="elemental_disciplines_11",
            name="Advanced Discipline",
            level=11,
            description="Learn one additional elemental discipline. Can replace one known.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="elemental_disciplines_17",
            name="Master Discipline",
            level=17,
            description="Learn one additional elemental discipline. Can replace one known.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)


# =============================================================================
# BARD SUBCLASSES
# =============================================================================

COLLEGE_OF_LORE = Subclass(
    id="lore",
    name="College of Lore",
    class_id="bard",
    description="You collect knowledge from every source, weaving magic with words and secrets.",
    features=[
        SubclassFeature(
            id="bonus_proficiencies_lore",
            name="Bonus Proficiencies",
            level=3,
            description="You gain proficiency in three skills of your choice.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="cutting_words",
            name="Cutting Words",
            level=3,
            description="As a reaction when a creature within 60 feet makes an attack roll, ability check, or damage roll, expend a Bardic Inspiration to subtract the die from their roll.",
            feature_type=FeatureType.REACTION,
        ),
        SubclassFeature(
            id="additional_magical_secrets",
            name="Additional Magical Secrets",
            level=6,
            description="Learn two spells from any class. They count as bard spells and don't count against spells known.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="peerless_skill",
            name="Peerless Skill",
            level=14,
            description="When you make an ability check, you can expend a Bardic Inspiration die and add it to the roll. You can do this after seeing the roll but before knowing the result.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)

COLLEGE_OF_VALOR = Subclass(
    id="valor",
    name="College of Valor",
    class_id="bard",
    description="You are a warrior-poet who inspires others in battle with deeds and words.",
    bonus_proficiencies=["medium_armor", "shields", "martial_weapons"],
    features=[
        SubclassFeature(
            id="combat_inspiration",
            name="Combat Inspiration",
            level=3,
            description="A creature with your Bardic Inspiration can add it to a weapon damage roll or AC against one attack (after the attack roll is made).",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="extra_attack_valor",
            name="Extra Attack",
            level=6,
            description="You can attack twice instead of once when you take the Attack action on your turn.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="battle_magic",
            name="Battle Magic",
            level=14,
            description="When you use your action to cast a bard spell, you can make one weapon attack as a bonus action.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
    ]
)

COLLEGE_OF_GLAMOUR = Subclass(
    id="glamour",
    name="College of Glamour",
    class_id="bard",
    description="You have learned to weave fey magic into your performance, beguiling all who hear.",
    features=[
        SubclassFeature(
            id="mantle_of_inspiration",
            name="Mantle of Inspiration",
            level=3,
            description="As a bonus action, expend a Bardic Inspiration to grant up to 5 creatures temporary HP equal to 2 times your bard level. They can immediately move up to their speed without provoking opportunity attacks.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="enthralling_performance",
            name="Enthralling Performance",
            level=3,
            description="After performing for at least 1 minute, choose up to your CHA modifier humanoids who watched. They must make WIS saves or be charmed for 1 hour.",
            feature_type=FeatureType.ACTION,
        ),
        SubclassFeature(
            id="mantle_of_majesty",
            name="Mantle of Majesty",
            level=6,
            description="As a bonus action, take on an unearthly appearance for 1 minute. During this time, cast Command as a bonus action without using a spell slot. Creatures charmed by you auto-fail.",
            feature_type=FeatureType.BONUS_ACTION,
            uses_per_rest=1,
        ),
        SubclassFeature(
            id="unbreakable_majesty",
            name="Unbreakable Majesty",
            level=14,
            description="As a bonus action, assume a magisterial presence for 1 minute. First time each creature attacks you, they must make CHA save or target someone else, and have disadvantage on saves against your spells that turn.",
            feature_type=FeatureType.BONUS_ACTION,
            uses_per_rest=1,
        ),
    ]
)

COLLEGE_OF_DANCE = Subclass(
    id="dance",
    name="College of Dance",
    class_id="bard",
    description="You have trained in dances passed down from satyr revelries, using graceful moves to control the battlefield.",
    features=[
        SubclassFeature(
            id="dazzling_footwork",
            name="Dazzling Footwork",
            level=3,
            description="While not wearing armor or using a shield, AC equals 10 + DEX + CHA. When you take the Attack action, you can make one extra unarmed strike (1d4 + DEX bludgeoning). Your speed increases by 10 feet.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="inspiring_movement",
            name="Inspiring Movement",
            level=3,
            description="When an enemy ends its turn within 5 feet of you, you can use a reaction to expend a Bardic Inspiration, moving up to half your speed and giving the die to an ally within 60 feet.",
            feature_type=FeatureType.REACTION,
        ),
        SubclassFeature(
            id="tandem_footwork",
            name="Tandem Footwork",
            level=6,
            description="When you roll initiative and aren't surprised, choose up to your proficiency bonus allies who can see you. They each gain a Bardic Inspiration die and can immediately move up to half their speed.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="leading_evasion",
            name="Leading Evasion",
            level=14,
            description="When you are subjected to an effect that allows a DEX save for half damage, you and allies within 5 feet take no damage on success and half on failure.",
            feature_type=FeatureType.PASSIVE,
        ),
    ]
)


# =============================================================================
# PALADIN SUBCLASSES
# =============================================================================

OATH_OF_DEVOTION = Subclass(
    id="devotion",
    name="Oath of Devotion",
    class_id="paladin",
    description="The Oath of Devotion binds a paladin to the loftiest ideals of justice, virtue, and order.",
    features=[
        SubclassFeature(
            id="oath_spells_devotion",
            name="Oath Spells",
            level=3,
            description="You gain oath spells at specified levels: Protection from Evil and Good, Sanctuary (3rd), Lesser Restoration, Zone of Truth (5th), and more.",
            feature_type=FeatureType.PASSIVE,
            grants_spells=["protection_from_evil_and_good", "sanctuary"],
        ),
        SubclassFeature(
            id="sacred_weapon",
            name="Sacred Weapon",
            level=3,
            description="As an action, imbue a weapon with positive energy. For 1 minute, add CHA modifier to attack rolls, it emits bright light 20ft/dim 20ft, and counts as magical.",
            feature_type=FeatureType.ACTION,
        ),
        SubclassFeature(
            id="turn_the_unholy",
            name="Turn the Unholy",
            level=3,
            description="As an action, each fiend or undead within 30 feet must make WIS save or be turned for 1 minute.",
            feature_type=FeatureType.ACTION,
        ),
        SubclassFeature(
            id="aura_of_devotion",
            name="Aura of Devotion",
            level=7,
            description="You and friendly creatures within 10 feet can't be charmed while you're conscious. Range increases to 30 feet at level 18.",
            feature_type=FeatureType.PASSIVE,
            grants_immunity=["charmed"],
        ),
        SubclassFeature(
            id="purity_of_spirit",
            name="Purity of Spirit",
            level=15,
            description="You are always under the effects of Protection from Evil and Good.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="holy_nimbus",
            name="Holy Nimbus",
            level=20,
            description="As an action, emanate an aura of sunlight for 1 minute. Enemies within 30 feet take 10 radiant damage at start of their turns. You and allies have advantage on saves against spells of fiends and undead.",
            feature_type=FeatureType.ACTION,
            uses_per_rest=1,
        ),
    ]
)

OATH_OF_VENGEANCE = Subclass(
    id="vengeance",
    name="Oath of Vengeance",
    class_id="paladin",
    description="The Oath of Vengeance is a solemn commitment to punish those who have committed grievous sins.",
    features=[
        SubclassFeature(
            id="oath_spells_vengeance",
            name="Oath Spells",
            level=3,
            description="You gain oath spells: Bane, Hunter's Mark (3rd), Hold Person, Misty Step (5th), and more.",
            feature_type=FeatureType.PASSIVE,
            grants_spells=["bane", "hunters_mark"],
        ),
        SubclassFeature(
            id="abjure_enemy",
            name="Abjure Enemy",
            level=3,
            description="As an action, one creature within 60 feet must make WIS save or be frightened and have speed 0. Fiends and undead have disadvantage.",
            feature_type=FeatureType.ACTION,
        ),
        SubclassFeature(
            id="vow_of_enmity",
            name="Vow of Enmity",
            level=3,
            description="As a bonus action, choose a creature within 10 feet. You have advantage on attack rolls against it for 1 minute.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="relentless_avenger",
            name="Relentless Avenger",
            level=7,
            description="When you hit with an opportunity attack, you can move up to half your speed immediately after as part of the reaction without provoking.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="soul_of_vengeance",
            name="Soul of Vengeance",
            level=15,
            description="When a creature under your Vow of Enmity makes an attack, you can use your reaction to make a melee weapon attack against it.",
            feature_type=FeatureType.REACTION,
        ),
        SubclassFeature(
            id="avenging_angel",
            name="Avenging Angel",
            level=20,
            description="As an action, transform for 1 hour: gain flying speed 60ft, emanate a 30-foot aura causing WIS saves or frightened. Once per long rest.",
            feature_type=FeatureType.ACTION,
            uses_per_rest=1,
        ),
    ]
)

OATH_OF_GLORY = Subclass(
    id="glory",
    name="Oath of Glory",
    class_id="paladin",
    description="The Oath of Glory calls paladins to feats of heroism and athletic excellence.",
    features=[
        SubclassFeature(
            id="oath_spells_glory",
            name="Oath Spells",
            level=3,
            description="You gain oath spells: Guiding Bolt, Heroism (3rd), Enhance Ability, Magic Weapon (5th), and more.",
            feature_type=FeatureType.PASSIVE,
            grants_spells=["guiding_bolt", "heroism"],
        ),
        SubclassFeature(
            id="peerless_athlete",
            name="Peerless Athlete",
            level=3,
            description="As a bonus action, for 10 minutes: advantage on Athletics and Acrobatics, carry/push/drag/lift double, jump distance increases by 10 feet.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="inspiring_smite",
            name="Inspiring Smite",
            level=3,
            description="After using Divine Smite, you can distribute temporary HP equal to 2d8 + your level among creatures within 30 feet as a bonus action.",
            feature_type=FeatureType.BONUS_ACTION,
        ),
        SubclassFeature(
            id="aura_of_alacrity",
            name="Aura of Alacrity",
            level=7,
            description="Your walking speed increases by 10 feet. Allies within 5 feet also gain this bonus. Range increases to 10 feet at level 18.",
            feature_type=FeatureType.PASSIVE,
        ),
        SubclassFeature(
            id="glorious_defense",
            name="Glorious Defense",
            level=15,
            description="When a creature hits you or an ally within 10 feet, use your reaction to add your CHA modifier to AC, potentially causing a miss. If it misses, you can make one attack against it.",
            feature_type=FeatureType.REACTION,
        ),
        SubclassFeature(
            id="living_legend",
            name="Living Legend",
            level=20,
            description="As a bonus action, gain benefits for 1 minute: advantage on CHA checks, turn a missed attack into a hit once per turn, reroll a failed save once. Once per long rest or restore with 5th-level slot.",
            feature_type=FeatureType.BONUS_ACTION,
            uses_per_rest=1,
        ),
    ]
)


# =============================================================================
# SUBCLASS REGISTRY
# =============================================================================

# All registered subclasses
SUBCLASS_REGISTRY: Dict[str, Dict[str, Subclass]] = {
    "barbarian": {
        "berserker": BERSERKER,
        "totem_warrior": TOTEM_WARRIOR,
    },
    "fighter": {
        "champion": CHAMPION,
        "battle_master": BATTLE_MASTER,
        "eldritch_knight": ELDRITCH_KNIGHT,
    },
    "rogue": {
        "thief": THIEF,
        "assassin": ASSASSIN,
    },
    "cleric": {
        "life_domain": LIFE_DOMAIN,
        "war_domain": WAR_DOMAIN,
        "light_domain": LIGHT_DOMAIN,
        "tempest_domain": TEMPEST_DOMAIN,
        "knowledge_domain": KNOWLEDGE_DOMAIN,
        "trickery_domain": TRICKERY_DOMAIN,
    },
    "wizard": {
        "evocation": SCHOOL_OF_EVOCATION,
        "abjuration": SCHOOL_OF_ABJURATION,
        "necromancy": SCHOOL_OF_NECROMANCY,
        "divination": SCHOOL_OF_DIVINATION,
        "illusion": SCHOOL_OF_ILLUSION,
        "conjuration": SCHOOL_OF_CONJURATION,
    },
    "druid": {
        "circle_moon": CIRCLE_OF_THE_MOON,
        "circle_land": CIRCLE_OF_THE_LAND,
        "circle_sea": CIRCLE_OF_THE_SEA,
        "circle_stars": CIRCLE_OF_THE_STARS,
    },
    "warlock": {
        "fiend": THE_FIEND,
        "archfey": THE_ARCHFEY,
        "great_old_one": THE_GREAT_OLD_ONE,
        "celestial": THE_CELESTIAL,
        "hexblade": THE_HEXBLADE,
        "fathomless": THE_FATHOMLESS,
        "genie": THE_GENIE,
        "undead": THE_UNDEAD,
    },
    "sorcerer": {
        "draconic_bloodline": DRACONIC_BLOODLINE,
        "wild_magic": WILD_MAGIC_ORIGIN,
        "divine_soul": DIVINE_SOUL_ORIGIN,
        "shadow_magic": SHADOW_MAGIC_ORIGIN,
        "storm_sorcery": STORM_SORCERY_ORIGIN,
        "aberrant_mind": ABERRANT_MIND_ORIGIN,
        "clockwork_soul": CLOCKWORK_SOUL_ORIGIN,
    },
    "ranger": {
        "beast_master": BEAST_MASTER,
        "hunter": HUNTER,
        "gloom_stalker": GLOOM_STALKER,
        "fey_wanderer": FEY_WANDERER,
    },
    "monk": {
        "open_hand": WAY_OF_THE_OPEN_HAND,
        "shadow": WAY_OF_SHADOW,
        "mercy": WAY_OF_MERCY,
        "four_elements": WAY_OF_FOUR_ELEMENTS,
    },
    "bard": {
        "lore": COLLEGE_OF_LORE,
        "valor": COLLEGE_OF_VALOR,
        "glamour": COLLEGE_OF_GLAMOUR,
        "dance": COLLEGE_OF_DANCE,
    },
    "paladin": {
        "devotion": OATH_OF_DEVOTION,
        "vengeance": OATH_OF_VENGEANCE,
        "glory": OATH_OF_GLORY,
    },
}


def get_subclasses_for_class(class_id: str) -> List[Subclass]:
    """Get all available subclasses for a class."""
    class_id = class_id.lower()
    subclasses = SUBCLASS_REGISTRY.get(class_id, {})
    return list(subclasses.values())


def get_subclass(class_id: str, subclass_id: str) -> Optional[Subclass]:
    """Get a specific subclass by class and subclass ID."""
    class_id = class_id.lower()
    subclass_id = subclass_id.lower()
    return SUBCLASS_REGISTRY.get(class_id, {}).get(subclass_id)


def get_subclass_level(class_id: str) -> int:
    """Get the level at which a class gains their subclass."""
    return SUBCLASS_LEVELS.get(class_id.lower(), 3)


def get_subclass_features_at_level(
    class_id: str,
    subclass_id: str,
    level: int
) -> List[SubclassFeature]:
    """Get all subclass features available at a given level."""
    subclass = get_subclass(class_id, subclass_id)
    if not subclass:
        return []
    return subclass.get_features_at_level(level)


def get_new_subclass_features_at_level(
    class_id: str,
    subclass_id: str,
    level: int
) -> List[SubclassFeature]:
    """Get subclass features gained exactly at a given level."""
    subclass = get_subclass(class_id, subclass_id)
    if not subclass:
        return []
    return subclass.get_new_features_at_level(level)


def needs_subclass_selection(class_id: str, current_level: int, has_subclass: bool) -> bool:
    """Check if a character needs to select a subclass."""
    if has_subclass:
        return False
    subclass_level = get_subclass_level(class_id)
    return current_level >= subclass_level


def get_subclass_choices(class_id: str) -> List[Dict[str, Any]]:
    """Get subclass options for character creation/level-up UI."""
    subclasses = get_subclasses_for_class(class_id)
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "grants_spellcasting": s.grants_spellcasting,
            "bonus_proficiencies": s.bonus_proficiencies,
        }
        for s in subclasses
    ]
