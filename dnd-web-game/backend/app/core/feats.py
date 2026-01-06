"""
Feat System for D&D 5e 2024

Comprehensive feat implementation including:
- General Feats (PHB 2024)
- Epic Boons (Level 19+)
- Prerequisites validation
- Combat and passive effects
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


class FeatCategory(str, Enum):
    """Categories of feats."""
    ORIGIN = "origin"           # Granted by background at level 1
    GENERAL = "general"         # Available at ASI levels (4, 8, 12, 16, 19)
    FIGHTING_STYLE = "fighting_style"  # Fighter/Paladin/Ranger
    EPIC_BOON = "epic_boon"     # Level 19+ only


class FeatPrerequisiteType(str, Enum):
    """Types of feat prerequisites."""
    NONE = "none"
    ABILITY_SCORE = "ability_score"
    PROFICIENCY = "proficiency"
    LEVEL = "level"
    SPELLCASTING = "spellcasting"
    CLASS = "class"


@dataclass
class FeatPrerequisite:
    """A prerequisite for taking a feat."""
    type: FeatPrerequisiteType
    value: Any  # Depends on type: int for ability/level, str for proficiency/class
    ability: Optional[str] = None  # For ability score prereqs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "value": self.value,
            "ability": self.ability,
        }


@dataclass
class FeatBenefit:
    """A benefit granted by a feat."""
    description: str

    # Ability score increase
    ability_increase: Optional[Dict[str, int]] = None  # {"strength": 1, "dexterity": 1}
    ability_choice: Optional[List[str]] = None  # Choose one from list
    ability_choice_amount: int = 1

    # Combat benefits
    attack_bonus: int = 0
    damage_bonus: int = 0
    ac_bonus: int = 0
    initiative_bonus: int = 0
    speed_bonus: int = 0
    hp_bonus_per_level: int = 0

    # Proficiencies
    grants_proficiency: List[str] = field(default_factory=list)
    grants_skill: List[str] = field(default_factory=list)
    grants_saving_throw: Optional[str] = None

    # Resistances and immunities
    grants_resistance: List[str] = field(default_factory=list)
    grants_immunity: List[str] = field(default_factory=list)

    # Combat features
    critical_range_bonus: int = 0  # Lower crit range (normally 20, becomes 19-20, etc.)
    extra_attack: bool = False
    bonus_action_attack: bool = False
    reaction_attack: bool = False

    # Special abilities (stored as flags for combat engine)
    special_abilities: List[str] = field(default_factory=list)

    # Spellcasting
    grants_cantrips: List[str] = field(default_factory=list)
    grants_spells: List[str] = field(default_factory=list)
    spell_uses_per_rest: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "ability_increase": self.ability_increase,
            "ability_choice": self.ability_choice,
            "attack_bonus": self.attack_bonus,
            "damage_bonus": self.damage_bonus,
            "ac_bonus": self.ac_bonus,
            "initiative_bonus": self.initiative_bonus,
            "speed_bonus": self.speed_bonus,
            "hp_bonus_per_level": self.hp_bonus_per_level,
            "grants_proficiency": self.grants_proficiency,
            "grants_resistance": self.grants_resistance,
            "special_abilities": self.special_abilities,
        }


@dataclass
class Feat:
    """A complete feat definition."""
    id: str
    name: str
    category: FeatCategory
    description: str
    benefits: FeatBenefit
    prerequisites: List[FeatPrerequisite] = field(default_factory=list)
    repeatable: bool = False  # Can be taken multiple times

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "benefits": self.benefits.to_dict(),
            "prerequisites": [p.to_dict() for p in self.prerequisites],
            "repeatable": self.repeatable,
        }


# =============================================================================
# GENERAL FEATS (PHB 2024)
# =============================================================================

GENERAL_FEATS: Dict[str, Feat] = {
    # Combat Feats
    "alert": Feat(
        id="alert",
        name="Alert",
        category=FeatCategory.GENERAL,
        description="Always on the lookout for danger, you gain benefits that keep you vigilant.",
        benefits=FeatBenefit(
            description="Add proficiency bonus to initiative. Can't be surprised while conscious. Other creatures don't gain advantage from being unseen.",
            initiative_bonus=0,  # Uses proficiency bonus instead
            special_abilities=["alert_initiative", "cannot_be_surprised", "no_unseen_advantage"],
        ),
    ),

    "athlete": Feat(
        id="athlete",
        name="Athlete",
        category=FeatCategory.GENERAL,
        description="You have undergone extensive physical training.",
        benefits=FeatBenefit(
            description="Increase STR or DEX by 1. Climbing doesn't cost extra movement. Standing from prone costs only 5 feet.",
            ability_choice=["strength", "dexterity"],
            ability_choice_amount=1,
            special_abilities=["climbing_no_extra_movement", "prone_stand_5ft"],
        ),
    ),

    "charger": Feat(
        id="charger",
        name="Charger",
        category=FeatCategory.GENERAL,
        description="You are especially deadly when moving before attacking.",
        benefits=FeatBenefit(
            description="When you Dash, you can make one melee attack or shove as a bonus action. If you moved at least 10 feet in a straight line, gain +5 damage or push 10 feet.",
            bonus_action_attack=True,
            special_abilities=["charger_dash_attack", "charger_bonus_damage"],
        ),
    ),

    "crossbow_expert": Feat(
        id="crossbow_expert",
        name="Crossbow Expert",
        category=FeatCategory.GENERAL,
        description="You are an expert with crossbows.",
        benefits=FeatBenefit(
            description="Ignore Loading property. No disadvantage on ranged attacks within 5 feet. When you Attack with a one-handed weapon, you can attack with a hand crossbow as a bonus action.",
            special_abilities=["ignore_loading", "no_close_range_disadvantage", "hand_crossbow_bonus_attack"],
        ),
    ),

    "defensive_duelist": Feat(
        id="defensive_duelist",
        name="Defensive Duelist",
        category=FeatCategory.GENERAL,
        description="You are skilled at protecting yourself with a finesse weapon.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.ABILITY_SCORE, 13, "dexterity"),
        ],
        benefits=FeatBenefit(
            description="When wielding a finesse weapon, you can use your reaction to add your proficiency bonus to AC against one melee attack.",
            special_abilities=["defensive_duelist_reaction"],
        ),
    ),

    "dual_wielder": Feat(
        id="dual_wielder",
        name="Dual Wielder",
        category=FeatCategory.GENERAL,
        description="You master fighting with two weapons.",
        benefits=FeatBenefit(
            description="+1 AC while wielding a melee weapon in each hand. You can two-weapon fight with non-Light weapons. You can draw or stow two weapons at once.",
            ac_bonus=1,  # When dual wielding
            special_abilities=["dual_wield_non_light", "draw_two_weapons"],
        ),
    ),

    "durable": Feat(
        id="durable",
        name="Durable",
        category=FeatCategory.GENERAL,
        description="Hardy and resilient, you gain benefits for staying power.",
        benefits=FeatBenefit(
            description="Increase CON by 1. When you roll a Hit Die to regain HP, the minimum is twice your CON modifier.",
            ability_increase={"constitution": 1},
            special_abilities=["hit_die_minimum_double_con"],
        ),
    ),

    "grappler": Feat(
        id="grappler",
        name="Grappler",
        category=FeatCategory.GENERAL,
        description="You are an expert at grabbing and holding foes.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.ABILITY_SCORE, 13, "strength"),
        ],
        benefits=FeatBenefit(
            description="Advantage on attacks against creatures you are grappling. You can use an action to pin a creature you have grappled (both restrained).",
            special_abilities=["grappler_advantage", "grappler_pin"],
        ),
    ),

    "great_weapon_master": Feat(
        id="great_weapon_master",
        name="Great Weapon Master",
        category=FeatCategory.GENERAL,
        description="You've learned to put the weight of a weapon to your advantage.",
        benefits=FeatBenefit(
            description="On a critical hit or reducing a creature to 0 HP with a melee weapon, make one melee attack as a bonus action. Before attacking with a heavy weapon, you can take -5 to hit for +10 damage.",
            special_abilities=["gwm_bonus_attack_on_crit_kill", "gwm_power_attack"],
        ),
    ),

    "heavily_armored": Feat(
        id="heavily_armored",
        name="Heavily Armored",
        category=FeatCategory.GENERAL,
        description="You have trained to master the use of heavy armor.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.PROFICIENCY, "medium_armor"),
        ],
        benefits=FeatBenefit(
            description="Increase STR by 1. Gain proficiency with heavy armor.",
            ability_increase={"strength": 1},
            grants_proficiency=["heavy_armor"],
        ),
    ),

    "heavy_armor_master": Feat(
        id="heavy_armor_master",
        name="Heavy Armor Master",
        category=FeatCategory.GENERAL,
        description="You can use your armor to deflect strikes.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.PROFICIENCY, "heavy_armor"),
        ],
        benefits=FeatBenefit(
            description="Increase STR by 1. While wearing heavy armor, reduce bludgeoning, piercing, and slashing damage from nonmagical attacks by 3.",
            ability_increase={"strength": 1},
            special_abilities=["heavy_armor_damage_reduction_3"],
        ),
    ),

    "inspiring_leader": Feat(
        id="inspiring_leader",
        name="Inspiring Leader",
        category=FeatCategory.GENERAL,
        description="You can inspire others through stirring words.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.ABILITY_SCORE, 13, "charisma"),
        ],
        benefits=FeatBenefit(
            description="You can spend 10 minutes inspiring companions. Up to 6 creatures (including yourself) within 30 feet gain temporary HP equal to your level + CHA modifier.",
            special_abilities=["inspiring_leader_temp_hp"],
        ),
    ),

    "keen_mind": Feat(
        id="keen_mind",
        name="Keen Mind",
        category=FeatCategory.GENERAL,
        description="You have a mind that can track time, direction, and detail.",
        benefits=FeatBenefit(
            description="Increase INT by 1. Always know which way is north. Always know the number of hours until sunrise or sunset. Can recall anything seen or heard within the past month.",
            ability_increase={"intelligence": 1},
            special_abilities=["keen_mind_direction", "keen_mind_time", "keen_mind_memory"],
        ),
    ),

    "lightly_armored": Feat(
        id="lightly_armored",
        name="Lightly Armored",
        category=FeatCategory.GENERAL,
        description="You have trained to master the use of light armor.",
        benefits=FeatBenefit(
            description="Increase STR or DEX by 1. Gain proficiency with light armor.",
            ability_choice=["strength", "dexterity"],
            ability_choice_amount=1,
            grants_proficiency=["light_armor"],
        ),
    ),

    "mage_slayer": Feat(
        id="mage_slayer",
        name="Mage Slayer",
        category=FeatCategory.GENERAL,
        description="You have practiced techniques useful in melee combat against spellcasters.",
        benefits=FeatBenefit(
            description="When a creature within 5 feet casts a spell, you can use your reaction to make a melee attack. When you damage a concentrating creature, it has disadvantage on the save. You have advantage on saves against spells cast within 5 feet.",
            reaction_attack=True,
            special_abilities=["mage_slayer_reaction", "mage_slayer_concentration_disadvantage", "mage_slayer_save_advantage"],
        ),
    ),

    "martial_weapon_training": Feat(
        id="martial_weapon_training",
        name="Martial Weapon Training",
        category=FeatCategory.GENERAL,
        description="You have trained with martial weapons.",
        benefits=FeatBenefit(
            description="Increase STR or DEX by 1. Gain proficiency with martial weapons. Choose one Fighting Style option from the Fighter class.",
            ability_choice=["strength", "dexterity"],
            ability_choice_amount=1,
            grants_proficiency=["martial_weapons"],
            special_abilities=["choose_fighting_style"],
        ),
    ),

    "medium_armor_master": Feat(
        id="medium_armor_master",
        name="Medium Armor Master",
        category=FeatCategory.GENERAL,
        description="You have practiced moving in medium armor.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.PROFICIENCY, "medium_armor"),
        ],
        benefits=FeatBenefit(
            description="Wearing medium armor doesn't impose disadvantage on Stealth. When wearing medium armor, you can add up to 3 (instead of 2) from DEX.",
            special_abilities=["medium_armor_no_stealth_disadvantage", "medium_armor_dex_cap_3"],
        ),
    ),

    "mobile": Feat(
        id="mobile",
        name="Mobile",
        category=FeatCategory.GENERAL,
        description="You are exceptionally speedy and agile.",
        benefits=FeatBenefit(
            description="Your speed increases by 10 feet. When you Dash, difficult terrain doesn't cost extra movement. When you make a melee attack against a creature, you don't provoke opportunity attacks from it for the rest of the turn.",
            speed_bonus=10,
            special_abilities=["dash_ignore_difficult_terrain", "no_opp_attack_after_melee"],
        ),
    ),

    "mounted_combatant": Feat(
        id="mounted_combatant",
        name="Mounted Combatant",
        category=FeatCategory.GENERAL,
        description="You are a dangerous foe to face while mounted.",
        benefits=FeatBenefit(
            description="Advantage on melee attacks against unmounted creatures smaller than your mount. Force attacks targeting your mount to target you instead. If your mount is subjected to an effect that allows a DEX save for half damage, it takes no damage on success.",
            special_abilities=["mounted_advantage_smaller", "mounted_redirect_attacks", "mounted_evasion"],
        ),
    ),

    "polearm_master": Feat(
        id="polearm_master",
        name="Polearm Master",
        category=FeatCategory.GENERAL,
        description="You can keep your enemies at bay with reach weapons.",
        benefits=FeatBenefit(
            description="When you Attack with a glaive, halberd, quarterstaff, or spear, you can use a bonus action to make a melee attack with the opposite end (1d4 bludgeoning). Creatures provoke opportunity attacks when entering your reach.",
            bonus_action_attack=True,
            special_abilities=["polearm_bonus_attack", "polearm_enter_reach_opp_attack"],
        ),
    ),

    "resilient": Feat(
        id="resilient",
        name="Resilient",
        category=FeatCategory.GENERAL,
        description="Choose one ability score. You become more resilient.",
        benefits=FeatBenefit(
            description="Increase one ability score of your choice by 1. Gain proficiency in saving throws using that ability.",
            ability_choice=["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"],
            ability_choice_amount=1,
            special_abilities=["resilient_save_proficiency"],
        ),
    ),

    "ritual_caster": Feat(
        id="ritual_caster",
        name="Ritual Caster",
        category=FeatCategory.GENERAL,
        description="You have learned a number of spells that you can cast as rituals.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.ABILITY_SCORE, 13, "intelligence"),
        ],
        benefits=FeatBenefit(
            description="Choose a class (bard, cleric, druid, sorcerer, warlock, or wizard). You gain a ritual book with two 1st-level ritual spells from that class's spell list. You can add more ritual spells you find to your book.",
            special_abilities=["ritual_caster_book"],
        ),
    ),

    "savage_attacker": Feat(
        id="savage_attacker",
        name="Savage Attacker",
        category=FeatCategory.GENERAL,
        description="Once per turn, you can reroll weapon damage.",
        benefits=FeatBenefit(
            description="Once per turn when you roll damage for a melee weapon attack, you can reroll the damage dice and use either total.",
            special_abilities=["savage_attacker_reroll"],
        ),
    ),

    "sentinel": Feat(
        id="sentinel",
        name="Sentinel",
        category=FeatCategory.GENERAL,
        description="You have mastered techniques to take advantage of every drop in any enemy's guard.",
        benefits=FeatBenefit(
            description="When you hit with an opportunity attack, the creature's speed becomes 0 for the rest of the turn. Creatures within 5 feet provoke opportunity attacks even if they Disengage. When a creature within 5 feet attacks someone other than you, you can use your reaction to attack it.",
            reaction_attack=True,
            special_abilities=["sentinel_stop_movement", "sentinel_ignore_disengage", "sentinel_reaction_attack"],
        ),
    ),

    "sharpshooter": Feat(
        id="sharpshooter",
        name="Sharpshooter",
        category=FeatCategory.GENERAL,
        description="You have mastered ranged weapons and can make shots that others find impossible.",
        benefits=FeatBenefit(
            description="Attacking at long range doesn't impose disadvantage. Ranged attacks ignore half cover and three-quarters cover. Before attacking with a ranged weapon, you can take -5 to hit for +10 damage.",
            special_abilities=["no_long_range_disadvantage", "ignore_cover", "sharpshooter_power_attack"],
        ),
    ),

    "shield_master": Feat(
        id="shield_master",
        name="Shield Master",
        category=FeatCategory.GENERAL,
        description="You use shields not just for protection but also for offense.",
        benefits=FeatBenefit(
            description="If you Attack, you can use a bonus action to shove with your shield. If not incapacitated, you can add your shield's AC bonus to DEX saves against effects that target only you. If you succeed on a DEX save for half damage, you can use your reaction to take no damage.",
            special_abilities=["shield_bonus_action_shove", "shield_dex_save_bonus", "shield_evasion"],
        ),
    ),

    "skilled": Feat(
        id="skilled",
        name="Skilled",
        category=FeatCategory.GENERAL,
        description="You gain proficiency in any combination of three skills or tools.",
        repeatable=True,
        benefits=FeatBenefit(
            description="Gain proficiency in any combination of three skills or tools of your choice.",
            special_abilities=["skilled_three_proficiencies"],
        ),
    ),

    "skulker": Feat(
        id="skulker",
        name="Skulker",
        category=FeatCategory.GENERAL,
        description="You are expert at slinking through shadows.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.ABILITY_SCORE, 13, "dexterity"),
        ],
        benefits=FeatBenefit(
            description="You can try to hide when lightly obscured. When hidden, missing a ranged attack doesn't reveal your position. Dim light doesn't impose disadvantage on Perception checks.",
            special_abilities=["hide_lightly_obscured", "miss_no_reveal", "dim_light_no_perception_penalty"],
        ),
    ),

    "speedy": Feat(
        id="speedy",
        name="Speedy",
        category=FeatCategory.GENERAL,
        description="You are faster than most.",
        benefits=FeatBenefit(
            description="Your speed increases by 10 feet. When you take the Dash action, opportunity attacks against you have disadvantage.",
            speed_bonus=10,
            special_abilities=["dash_opp_attack_disadvantage"],
        ),
    ),

    "spell_sniper": Feat(
        id="spell_sniper",
        name="Spell Sniper",
        category=FeatCategory.GENERAL,
        description="You have learned techniques to enhance your attacks with certain kinds of spells.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.SPELLCASTING, True),
        ],
        benefits=FeatBenefit(
            description="Spell attacks ignore half cover and three-quarters cover. The range of spell attacks is doubled. You learn one cantrip that requires an attack roll from a class of your choice.",
            special_abilities=["spell_ignore_cover", "spell_range_doubled", "spell_sniper_cantrip"],
        ),
    ),

    "tavern_brawler": Feat(
        id="tavern_brawler",
        name="Tavern Brawler",
        category=FeatCategory.GENERAL,
        description="Accustomed to rough-and-tumble fighting using whatever is at hand.",
        benefits=FeatBenefit(
            description="Increase STR or CON by 1. You are proficient with improvised weapons. Your unarmed strikes deal 1d4 + STR damage. When you hit with an unarmed strike or improvised weapon, you can use a bonus action to grapple.",
            ability_choice=["strength", "constitution"],
            ability_choice_amount=1,
            grants_proficiency=["improvised_weapons"],
            special_abilities=["unarmed_d4", "grapple_bonus_action_on_hit"],
        ),
    ),

    "tough": Feat(
        id="tough",
        name="Tough",
        category=FeatCategory.GENERAL,
        description="Your hit point maximum increases.",
        benefits=FeatBenefit(
            description="Your hit point maximum increases by 2 for every level you have.",
            hp_bonus_per_level=2,
        ),
    ),

    "war_caster": Feat(
        id="war_caster",
        name="War Caster",
        category=FeatCategory.GENERAL,
        description="You have practiced casting spells in the midst of combat.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.SPELLCASTING, True),
        ],
        benefits=FeatBenefit(
            description="Advantage on concentration saves. You can perform somatic components with hands full of weapons or shield. When a creature provokes an opportunity attack, you can cast a spell at it instead of making a melee attack.",
            special_abilities=["war_caster_concentration_advantage", "war_caster_somatic_full_hands", "war_caster_spell_opportunity"],
        ),
    ),
}


# =============================================================================
# EPIC BOONS (Level 19+)
# =============================================================================

EPIC_BOONS: Dict[str, Feat] = {
    "boon_of_combat_prowess": Feat(
        id="boon_of_combat_prowess",
        name="Boon of Combat Prowess",
        category=FeatCategory.EPIC_BOON,
        description="Your combat skills are legendary.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.LEVEL, 19),
        ],
        benefits=FeatBenefit(
            description="Increase one ability score by 1 (max 30). Once per turn, when you miss with an attack roll, you can treat the roll as a 20.",
            ability_choice=["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"],
            ability_choice_amount=1,
            special_abilities=["epic_miss_becomes_20"],
        ),
    ),

    "boon_of_dimensional_travel": Feat(
        id="boon_of_dimensional_travel",
        name="Boon of Dimensional Travel",
        category=FeatCategory.EPIC_BOON,
        description="You can slip through the fabric of space.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.LEVEL, 19),
        ],
        benefits=FeatBenefit(
            description="Increase one ability score by 1 (max 30). You can cast Misty Step without expending a spell slot. You can use this a number of times equal to your proficiency bonus per long rest.",
            ability_choice=["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"],
            ability_choice_amount=1,
            grants_spells=["misty_step"],
            special_abilities=["epic_free_misty_step"],
        ),
    ),

    "boon_of_fate": Feat(
        id="boon_of_fate",
        name="Boon of Fate",
        category=FeatCategory.EPIC_BOON,
        description="You can influence the cosmic forces of fate.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.LEVEL, 19),
        ],
        benefits=FeatBenefit(
            description="Increase one ability score by 1 (max 30). When you or a creature you can see within 60 feet makes an attack roll, ability check, or saving throw, you can roll a d10 and add or subtract it from the roll. Proficiency bonus uses per long rest.",
            ability_choice=["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"],
            ability_choice_amount=1,
            special_abilities=["epic_fate_d10"],
        ),
    ),

    "boon_of_fortitude": Feat(
        id="boon_of_fortitude",
        name="Boon of Fortitude",
        category=FeatCategory.EPIC_BOON,
        description="Your hit point maximum has no upper limit.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.LEVEL, 19),
        ],
        benefits=FeatBenefit(
            description="Increase one ability score by 1 (max 30). Your hit point maximum increases by 40.",
            ability_choice=["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"],
            ability_choice_amount=1,
            special_abilities=["epic_hp_bonus_40"],
        ),
    ),

    "boon_of_irresistible_offense": Feat(
        id="boon_of_irresistible_offense",
        name="Boon of Irresistible Offense",
        category=FeatCategory.EPIC_BOON,
        description="Your attacks pierce all defenses.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.LEVEL, 19),
        ],
        benefits=FeatBenefit(
            description="Increase one ability score by 1 (max 30). Your attacks ignore resistance to damage dealt. When you score a critical hit, you can roll one additional weapon damage die.",
            ability_choice=["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"],
            ability_choice_amount=1,
            special_abilities=["epic_ignore_resistance", "epic_crit_extra_die"],
        ),
    ),

    "boon_of_recovery": Feat(
        id="boon_of_recovery",
        name="Boon of Recovery",
        category=FeatCategory.EPIC_BOON,
        description="You can rapidly heal from wounds.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.LEVEL, 19),
        ],
        benefits=FeatBenefit(
            description="Increase one ability score by 1 (max 30). As a bonus action, you can regain hit points equal to half your hit point maximum. Once used, you can't use this again until you finish a long rest.",
            ability_choice=["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"],
            ability_choice_amount=1,
            special_abilities=["epic_recovery_half_hp"],
        ),
    ),

    "boon_of_speed": Feat(
        id="boon_of_speed",
        name="Boon of Speed",
        category=FeatCategory.EPIC_BOON,
        description="You move with supernatural swiftness.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.LEVEL, 19),
        ],
        benefits=FeatBenefit(
            description="Increase one ability score by 1 (max 30). Your speed increases by 30 feet.",
            ability_choice=["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"],
            ability_choice_amount=1,
            speed_bonus=30,
        ),
    ),

    "boon_of_spell_recall": Feat(
        id="boon_of_spell_recall",
        name="Boon of Spell Recall",
        category=FeatCategory.EPIC_BOON,
        description="You can cast spells more efficiently.",
        prerequisites=[
            FeatPrerequisite(FeatPrerequisiteType.LEVEL, 19),
            FeatPrerequisite(FeatPrerequisiteType.SPELLCASTING, True),
        ],
        benefits=FeatBenefit(
            description="Increase one ability score by 1 (max 30). Once per long rest, you can cast a spell of 4th level or lower without expending a spell slot.",
            ability_choice=["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"],
            ability_choice_amount=1,
            special_abilities=["epic_free_spell_4th"],
        ),
    ),
}


# =============================================================================
# FEAT REGISTRY
# =============================================================================

ALL_FEATS: Dict[str, Feat] = {**GENERAL_FEATS, **EPIC_BOONS}


def get_feat(feat_id: str) -> Optional[Feat]:
    """Get a feat by ID."""
    return ALL_FEATS.get(feat_id)


def get_all_feats() -> List[Feat]:
    """Get all feats."""
    return list(ALL_FEATS.values())


def get_feats_by_category(category: FeatCategory) -> List[Feat]:
    """Get all feats in a category."""
    return [f for f in ALL_FEATS.values() if f.category == category]


def get_general_feats() -> List[Feat]:
    """Get all general feats."""
    return list(GENERAL_FEATS.values())


def get_epic_boons() -> List[Feat]:
    """Get all epic boons."""
    return list(EPIC_BOONS.values())


# =============================================================================
# PREREQUISITES VALIDATION
# =============================================================================

def check_feat_prerequisites(
    feat: Feat,
    character_level: int,
    ability_scores: Dict[str, int],
    proficiencies: List[str],
    has_spellcasting: bool,
    character_class: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """
    Check if a character meets the prerequisites for a feat.

    Args:
        feat: The feat to check
        character_level: Character's total level
        ability_scores: Dict of ability scores {"strength": 15, ...}
        proficiencies: List of proficiency strings
        has_spellcasting: Whether the character can cast spells
        character_class: Optional character class for class-specific prereqs

    Returns:
        Tuple of (meets_prerequisites, list_of_unmet_requirements)
    """
    unmet = []

    for prereq in feat.prerequisites:
        if prereq.type == FeatPrerequisiteType.NONE:
            continue

        elif prereq.type == FeatPrerequisiteType.ABILITY_SCORE:
            ability = prereq.ability
            required = prereq.value
            current = ability_scores.get(ability, 0)
            if current < required:
                unmet.append(f"{ability.capitalize()} {required}+ (current: {current})")

        elif prereq.type == FeatPrerequisiteType.PROFICIENCY:
            if prereq.value not in proficiencies:
                unmet.append(f"Proficiency with {prereq.value}")

        elif prereq.type == FeatPrerequisiteType.LEVEL:
            if character_level < prereq.value:
                unmet.append(f"Level {prereq.value}+ (current: {character_level})")

        elif prereq.type == FeatPrerequisiteType.SPELLCASTING:
            if prereq.value and not has_spellcasting:
                unmet.append("Ability to cast at least one spell")

        elif prereq.type == FeatPrerequisiteType.CLASS:
            if character_class and character_class.lower() != prereq.value.lower():
                unmet.append(f"Must be a {prereq.value}")

    return len(unmet) == 0, unmet


def get_available_feats(
    character_level: int,
    ability_scores: Dict[str, int],
    proficiencies: List[str],
    has_spellcasting: bool,
    current_feats: List[str],
    character_class: Optional[str] = None,
    include_epic_boons: bool = True
) -> List[Feat]:
    """
    Get all feats available to a character.

    Args:
        character_level: Character's total level
        ability_scores: Dict of ability scores
        proficiencies: List of proficiency strings
        has_spellcasting: Whether the character can cast spells
        current_feats: List of feat IDs the character already has
        character_class: Optional character class
        include_epic_boons: Whether to include epic boons (level 19+)

    Returns:
        List of available Feat objects
    """
    available = []

    for feat in ALL_FEATS.values():
        # Skip if already has feat (unless repeatable)
        if feat.id in current_feats and not feat.repeatable:
            continue

        # Skip epic boons if not level 19+ or not requested
        if feat.category == FeatCategory.EPIC_BOON:
            if not include_epic_boons or character_level < 19:
                continue

        # Check prerequisites
        meets, unmet = check_feat_prerequisites(
            feat, character_level, ability_scores, proficiencies,
            has_spellcasting, character_class
        )

        if meets:
            available.append(feat)

    return available


def apply_feat_benefits(
    feat: Feat,
    character_data: Dict[str, Any],
    choices: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Apply a feat's benefits to a character.

    Args:
        feat: The feat being applied
        character_data: Character data dict (will be modified)
        choices: Any choices made for the feat (ability score, etc.)

    Returns:
        Updated character data
    """
    benefits = feat.benefits

    # Apply ability score increases
    if benefits.ability_increase:
        for ability, amount in benefits.ability_increase.items():
            current = character_data.get("ability_scores", {}).get(ability, 10)
            character_data.setdefault("ability_scores", {})[ability] = current + amount

    # Apply ability choice
    if benefits.ability_choice and choices and "ability_choice" in choices:
        chosen = choices["ability_choice"]
        if chosen in benefits.ability_choice:
            current = character_data.get("ability_scores", {}).get(chosen, 10)
            character_data.setdefault("ability_scores", {})[chosen] = current + benefits.ability_choice_amount

    # Apply combat bonuses
    if benefits.ac_bonus:
        character_data["feat_ac_bonus"] = character_data.get("feat_ac_bonus", 0) + benefits.ac_bonus

    if benefits.speed_bonus:
        character_data["feat_speed_bonus"] = character_data.get("feat_speed_bonus", 0) + benefits.speed_bonus

    if benefits.hp_bonus_per_level:
        level = character_data.get("level", 1)
        hp_bonus = benefits.hp_bonus_per_level * level
        character_data["feat_hp_bonus"] = character_data.get("feat_hp_bonus", 0) + hp_bonus

    # Apply proficiencies
    if benefits.grants_proficiency:
        current = set(character_data.get("proficiencies", []))
        current.update(benefits.grants_proficiency)
        character_data["proficiencies"] = list(current)

    # Apply resistances
    if benefits.grants_resistance:
        current = set(character_data.get("resistances", []))
        current.update(benefits.grants_resistance)
        character_data["resistances"] = list(current)

    # Apply immunities
    if benefits.grants_immunity:
        current = set(character_data.get("immunities", []))
        current.update(benefits.grants_immunity)
        character_data["immunities"] = list(current)

    # Apply spells
    if benefits.grants_spells:
        current = set(character_data.get("feat_spells", []))
        current.update(benefits.grants_spells)
        character_data["feat_spells"] = list(current)

    if benefits.grants_cantrips:
        current = set(character_data.get("feat_cantrips", []))
        current.update(benefits.grants_cantrips)
        character_data["feat_cantrips"] = list(current)

    # Track special abilities
    if benefits.special_abilities:
        current = set(character_data.get("feat_abilities", []))
        current.update(benefits.special_abilities)
        character_data["feat_abilities"] = list(current)

    # Track the feat itself
    current_feats = character_data.get("feats", [])
    if feat.id not in current_feats:
        current_feats.append(feat.id)
    character_data["feats"] = current_feats

    return character_data


def get_feat_choices(feat: Feat) -> Dict[str, Any]:
    """
    Get the choices that need to be made when taking a feat.

    Args:
        feat: The feat

    Returns:
        Dict describing required choices
    """
    choices = {}

    benefits = feat.benefits

    if benefits.ability_choice:
        choices["ability_choice"] = {
            "type": "select_one",
            "options": benefits.ability_choice,
            "amount": benefits.ability_choice_amount,
            "description": f"Choose {benefits.ability_choice_amount} ability score to increase",
        }

    # Check for skill/proficiency choices
    if "skilled_three_proficiencies" in benefits.special_abilities:
        choices["proficiency_choices"] = {
            "type": "select_multiple",
            "count": 3,
            "options": "skills_or_tools",
            "description": "Choose 3 skills or tools to gain proficiency",
        }

    if "choose_fighting_style" in benefits.special_abilities:
        choices["fighting_style"] = {
            "type": "select_one",
            "options": ["archery", "defense", "dueling", "great_weapon", "protection", "two_weapon"],
            "description": "Choose a Fighting Style",
        }

    if "resilient_save_proficiency" in benefits.special_abilities:
        choices["saving_throw"] = {
            "type": "linked_to_ability",
            "description": "Gain proficiency in saving throws for the chosen ability",
        }

    return choices
