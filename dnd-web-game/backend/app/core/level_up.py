"""
Level-Up System for D&D 5e 2024

Handles the complete level-up process including:
- HP increase calculation
- Ability Score Improvements (ASI)
- Feat selection
- New feature unlocks
- Spell slot increases
- Subclass selection (at appropriate levels)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from enum import Enum
import random

from .hit_dice import get_hit_die_for_class, get_hit_die_average
from .progression import get_proficiency_bonus, can_level_up, get_new_level_from_xp

if TYPE_CHECKING:
    from app.models.game_session import PartyMember


class LevelUpChoiceType(str, Enum):
    """Types of choices a player must make during level-up."""
    HP_ROLL = "hp_roll"  # Roll or take average for HP
    ABILITY_SCORE = "ability_score"  # ASI distribution
    FEAT = "feat"  # Feat selection
    SPELL = "spell"  # New spells to learn
    SUBCLASS = "subclass"  # Subclass selection
    SKILL = "skill"  # New skill proficiency
    EXPERTISE = "expertise"  # Double proficiency
    FIGHTING_STYLE = "fighting_style"  # Fighter/Paladin/Ranger style
    METAMAGIC = "metamagic"  # Sorcerer metamagic
    INVOCATION = "invocation"  # Warlock invocations
    MANEUVER = "maneuver"  # Battle Master maneuvers
    CLASS_CHOICE = "class_choice"  # Multiclass: which class to take level in


# Levels where classes get Ability Score Improvements
ASI_LEVELS_BY_CLASS: Dict[str, List[int]] = {
    "fighter": [4, 6, 8, 12, 14, 16, 19],
    "rogue": [4, 8, 10, 12, 16, 19],
    # All other classes follow standard
    "default": [4, 8, 12, 16, 19],
}

# Levels where subclass is chosen
SUBCLASS_LEVELS: Dict[str, int] = {
    "barbarian": 3,
    "bard": 3,
    "cleric": 1,  # Domain at 1st level
    "druid": 2,
    "fighter": 3,
    "monk": 3,
    "paladin": 3,
    "ranger": 3,
    "rogue": 3,
    "sorcerer": 1,  # Origin at 1st level
    "warlock": 1,  # Patron at 1st level
    "wizard": 2,
}


# =============================================================================
# FEAT EFFECTS
# =============================================================================

# Feat definitions with their effects
# Each feat can have: ability_bonus, hp_bonus, features, proficiencies
FEAT_DATA: Dict[str, Dict[str, Any]] = {
    "alert": {
        "name": "Alert",
        "description": "+5 to initiative, can't be surprised while conscious",
        "effects": {
            "initiative_bonus": 5,
            "features": ["immune_to_surprise"],
        }
    },
    "athlete": {
        "name": "Athlete",
        "description": "+1 STR or DEX, climbing and jumping benefits",
        "effects": {
            "ability_choice": ["strength", "dexterity"],
            "ability_bonus": 1,
            "features": ["athletic_prowess"],
        }
    },
    "actor": {
        "name": "Actor",
        "description": "+1 CHA, advantage on Deception and Performance for disguises",
        "effects": {
            "ability_bonus": {"charisma": 1},
            "features": ["mimicry"],
        }
    },
    "charger": {
        "name": "Charger",
        "description": "After dashing, bonus action attack with +5 damage or shove",
        "effects": {
            "features": ["charge_attack"],
        }
    },
    "crossbow_expert": {
        "name": "Crossbow Expert",
        "description": "Ignore loading, no disadvantage at close range, bonus attack",
        "effects": {
            "features": ["crossbow_mastery"],
        }
    },
    "defensive_duelist": {
        "name": "Defensive Duelist",
        "description": "Reaction to add proficiency to AC against one attack",
        "effects": {
            "features": ["parry"],
        }
    },
    "dual_wielder": {
        "name": "Dual Wielder",
        "description": "+1 AC while dual wielding, draw two weapons, non-light weapons",
        "effects": {
            "ac_bonus_conditional": {"condition": "dual_wielding", "bonus": 1},
            "features": ["dual_wield_mastery"],
        }
    },
    "durable": {
        "name": "Durable",
        "description": "+1 CON, minimum HP from Hit Dice = 2x CON mod",
        "effects": {
            "ability_bonus": {"constitution": 1},
            "features": ["durable_recovery"],
        }
    },
    "great_weapon_master": {
        "name": "Great Weapon Master",
        "description": "-5 attack/+10 damage option, bonus action attack on crit/kill",
        "effects": {
            "features": ["heavy_weapon_mastery", "cleave"],
        }
    },
    "healer": {
        "name": "Healer",
        "description": "Stabilize and heal with healer's kit",
        "effects": {
            "features": ["expert_healer"],
        }
    },
    "heavily_armored": {
        "name": "Heavily Armored",
        "description": "+1 STR, heavy armor proficiency",
        "effects": {
            "ability_bonus": {"strength": 1},
            "proficiencies": {"armor": ["heavy"]},
        }
    },
    "inspiring_leader": {
        "name": "Inspiring Leader",
        "description": "Grant temp HP equal to level + CHA mod to allies",
        "effects": {
            "features": ["inspiring_speech"],
        }
    },
    "lucky": {
        "name": "Lucky",
        "description": "3 luck points per long rest to reroll d20s",
        "effects": {
            "resources": {"luck_points": 3},
            "features": ["lucky"],
        }
    },
    "mage_slayer": {
        "name": "Mage Slayer",
        "description": "Reaction attack vs casters, disadvantage on concentration",
        "effects": {
            "features": ["mage_slayer"],
        }
    },
    "magic_initiate": {
        "name": "Magic Initiate",
        "description": "Learn 2 cantrips and 1 1st-level spell",
        "effects": {
            "features": ["magic_initiate"],
        }
    },
    "mobile": {
        "name": "Mobile",
        "description": "+10 speed, Dash ignores difficult terrain, no OA after attack",
        "effects": {
            "speed_bonus": 10,
            "features": ["nimble_escape"],
        }
    },
    "observant": {
        "name": "Observant",
        "description": "+1 INT or WIS, +5 passive Perception and Investigation",
        "effects": {
            "ability_choice": ["intelligence", "wisdom"],
            "ability_bonus": 1,
            "passive_bonus": {"perception": 5, "investigation": 5},
        }
    },
    "polearm_master": {
        "name": "Polearm Master",
        "description": "Bonus action butt attack, OA when enemies enter reach",
        "effects": {
            "features": ["polearm_mastery"],
        }
    },
    "resilient": {
        "name": "Resilient",
        "description": "+1 to chosen ability, gain saving throw proficiency",
        "effects": {
            "ability_choice": ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"],
            "ability_bonus": 1,
            "saving_throw_proficiency": True,  # For chosen ability
        }
    },
    "ritual_caster": {
        "name": "Ritual Caster",
        "description": "Learn and cast ritual spells from chosen class",
        "effects": {
            "features": ["ritual_casting"],
        }
    },
    "savage_attacker": {
        "name": "Savage Attacker",
        "description": "Reroll melee weapon damage once per turn",
        "effects": {
            "features": ["savage_attacker"],
        }
    },
    "sentinel": {
        "name": "Sentinel",
        "description": "OA stops movement, attack creatures that attack allies, OA on Disengage",
        "effects": {
            "features": ["sentinel"],
        }
    },
    "sharpshooter": {
        "name": "Sharpshooter",
        "description": "No long range disadvantage, ignore cover, -5/+10 option",
        "effects": {
            "features": ["sharpshooter"],
        }
    },
    "shield_master": {
        "name": "Shield Master",
        "description": "Bonus action shove, add shield AC to DEX saves, Evasion for DEX saves",
        "effects": {
            "features": ["shield_mastery"],
        }
    },
    "skilled": {
        "name": "Skilled",
        "description": "Gain proficiency in 3 skills or tools",
        "effects": {
            "skill_proficiencies": 3,  # Player chooses 3
        }
    },
    "skulker": {
        "name": "Skulker",
        "description": "Hide when lightly obscured, ranged miss doesn't reveal, dim light doesn't impose disadvantage",
        "effects": {
            "features": ["skulker"],
        }
    },
    "spell_sniper": {
        "name": "Spell Sniper",
        "description": "Double spell range, ignore cover, learn attack cantrip",
        "effects": {
            "features": ["spell_sniper"],
        }
    },
    "tavern_brawler": {
        "name": "Tavern Brawler",
        "description": "+1 STR or CON, unarmed d4, bonus action grapple",
        "effects": {
            "ability_choice": ["strength", "constitution"],
            "ability_bonus": 1,
            "features": ["tavern_brawler"],
        }
    },
    "tough": {
        "name": "Tough",
        "description": "+2 HP per level",
        "effects": {
            "hp_per_level": 2,
        }
    },
    "war_caster": {
        "name": "War Caster",
        "description": "Advantage on concentration, somatic with hands full, spell as OA",
        "effects": {
            "features": ["war_caster"],
        }
    },
    "weapon_master": {
        "name": "Weapon Master",
        "description": "+1 STR or DEX, proficiency with 4 weapons",
        "effects": {
            "ability_choice": ["strength", "dexterity"],
            "ability_bonus": 1,
            "weapon_proficiencies": 4,  # Player chooses 4
        }
    },
}


def apply_feat_effects(
    member: "PartyMember",
    feat_name: str,
    ability_choice: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Apply the effects of a feat to a party member.

    Args:
        member: The party member gaining the feat
        feat_name: The ID/name of the feat
        ability_choice: For feats with ability choice (e.g., Resilient)

    Returns:
        Dict of effects applied
    """
    feat_key = feat_name.lower().replace(" ", "_").replace("-", "_")
    feat_data = FEAT_DATA.get(feat_key)

    if not feat_data:
        return {"error": f"Unknown feat: {feat_name}"}

    effects = feat_data.get("effects", {})
    applied = {"feat_name": feat_data["name"], "bonuses": []}

    # Apply ability score bonuses
    if "ability_bonus" in effects:
        bonus = effects["ability_bonus"]

        if isinstance(bonus, dict):
            # Fixed ability bonus (e.g., Actor: +1 CHA)
            for ability, value in bonus.items():
                if hasattr(member, ability.lower()):
                    current = getattr(member, ability.lower())
                    new_value = min(20, current + value)
                    setattr(member, ability.lower(), new_value)
                    applied["bonuses"].append(f"+{value} {ability.capitalize()}")

        elif "ability_choice" in effects and ability_choice:
            # Player-chosen ability (e.g., Resilient)
            ability = ability_choice.lower()
            if hasattr(member, ability):
                value = effects["ability_bonus"]
                current = getattr(member, ability)
                new_value = min(20, current + value)
                setattr(member, ability, new_value)
                applied["bonuses"].append(f"+{value} {ability.capitalize()}")

                # If feat grants saving throw proficiency for chosen ability
                if effects.get("saving_throw_proficiency"):
                    if not hasattr(member, "saving_throw_proficiencies"):
                        member.saving_throw_proficiencies = []
                    if ability not in member.saving_throw_proficiencies:
                        member.saving_throw_proficiencies.append(ability)
                        applied["bonuses"].append(f"{ability.capitalize()} saving throw proficiency")

    # Apply HP bonus (Tough feat)
    if "hp_per_level" in effects:
        hp_bonus = effects["hp_per_level"] * member.level
        member.max_hp += hp_bonus
        member.current_hp += hp_bonus
        applied["bonuses"].append(f"+{hp_bonus} HP (Tough)")

    # Apply speed bonus (Mobile feat)
    if "speed_bonus" in effects:
        if hasattr(member, "speed"):
            member.speed += effects["speed_bonus"]
            applied["bonuses"].append(f"+{effects['speed_bonus']} speed")

    # Apply features
    if "features" in effects:
        if not hasattr(member, "class_features"):
            member.class_features = []
        for feature in effects["features"]:
            if feature not in member.class_features:
                member.class_features.append(feature)
        applied["features"] = effects["features"]

    # Apply resources (e.g., Lucky points)
    if "resources" in effects:
        if not hasattr(member, "class_resources"):
            member.class_resources = {}
        for resource, amount in effects["resources"].items():
            member.class_resources[resource] = amount
        applied["resources"] = effects["resources"]

    # Store the feat itself
    if not hasattr(member, "feats"):
        member.feats = []
    if feat_key not in member.feats:
        member.feats.append(feat_key)

    return applied


@dataclass
class LevelUpChoice:
    """A choice the player must make during level-up."""
    choice_type: LevelUpChoiceType
    description: str
    options: List[Dict[str, Any]]
    required: bool = True
    max_selections: int = 1  # For multi-select like ASI

    def to_dict(self) -> Dict[str, Any]:
        return {
            "choice_type": self.choice_type.value,
            "description": self.description,
            "options": self.options,
            "required": self.required,
            "max_selections": self.max_selections,
        }


@dataclass
class LevelUpBenefit:
    """A benefit gained from leveling up."""
    benefit_type: str
    name: str
    description: str
    value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benefit_type": self.benefit_type,
            "name": self.name,
            "description": self.description,
            "value": self.value,
        }


@dataclass
class LevelUpPreview:
    """Preview of what a character will gain from leveling up."""
    old_level: int
    new_level: int
    hp_increase_average: int
    hp_increase_max: int
    new_proficiency_bonus: Optional[int]
    new_features: List[LevelUpBenefit]
    choices_required: List[LevelUpChoice]
    spell_slots_gained: Dict[int, int]
    gets_asi: bool
    gets_subclass: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "old_level": self.old_level,
            "new_level": self.new_level,
            "hp_increase_average": self.hp_increase_average,
            "hp_increase_max": self.hp_increase_max,
            "new_proficiency_bonus": self.new_proficiency_bonus,
            "new_features": [f.to_dict() for f in self.new_features],
            "choices_required": [c.to_dict() for c in self.choices_required],
            "spell_slots_gained": self.spell_slots_gained,
            "gets_asi": self.gets_asi,
            "gets_subclass": self.gets_subclass,
        }


@dataclass
class LevelUpResult:
    """Result of applying a level-up."""
    success: bool
    old_level: int
    new_level: int
    hp_gained: int
    new_max_hp: int
    new_proficiency_bonus: int
    features_gained: List[str]
    choices_applied: Dict[str, Any]
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "old_level": self.old_level,
            "new_level": self.new_level,
            "hp_gained": self.hp_gained,
            "new_max_hp": self.new_max_hp,
            "new_proficiency_bonus": self.new_proficiency_bonus,
            "features_gained": self.features_gained,
            "choices_applied": self.choices_applied,
            "errors": self.errors,
        }


def check_level_up(member: "PartyMember") -> Optional[int]:
    """
    Check if a party member can level up.

    Args:
        member: The party member to check

    Returns:
        New level if level-up is available, None otherwise
    """
    return get_new_level_from_xp(member.xp, member.level)


def calculate_hp_increase(
    class_name: str,
    new_level: int,
    con_modifier: int,
    use_average: bool = True,
    roll_result: Optional[int] = None
) -> int:
    """
    Calculate HP gained when leveling up.

    Args:
        class_name: The character's class
        new_level: The level being gained
        con_modifier: Constitution modifier
        use_average: If True, use average die value; if False, roll
        roll_result: Specific roll result (for player-rolled dice)

    Returns:
        HP gained this level (minimum 1)
    """
    die_size = get_hit_die_for_class(class_name)

    if new_level == 1:
        # First level: max die + CON mod
        return max(1, die_size + con_modifier)

    if use_average:
        # Average rounded up + CON mod
        base_hp = get_hit_die_average(die_size)
    elif roll_result is not None:
        base_hp = roll_result
    else:
        # Roll if no average and no roll provided
        base_hp = random.randint(1, die_size)

    return max(1, base_hp + con_modifier)


def gets_asi_at_level(class_name: str, level: int) -> bool:
    """
    Check if a class gets an ASI at a specific level.

    Args:
        class_name: The character's class
        level: The level to check

    Returns:
        True if ASI is available at this level
    """
    class_lower = class_name.lower()
    asi_levels = ASI_LEVELS_BY_CLASS.get(class_lower, ASI_LEVELS_BY_CLASS["default"])
    return level in asi_levels


def gets_subclass_at_level(class_name: str, level: int) -> bool:
    """
    Check if a class chooses their subclass at a specific level.

    Args:
        class_name: The character's class
        level: The level to check

    Returns:
        True if subclass selection happens at this level
    """
    class_lower = class_name.lower()
    subclass_level = SUBCLASS_LEVELS.get(class_lower, 3)
    return level == subclass_level


def get_level_up_preview(member: "PartyMember", new_level: int) -> LevelUpPreview:
    """
    Get a preview of what a character will gain from leveling up.

    Args:
        member: The party member
        new_level: The new level they will reach

    Returns:
        LevelUpPreview with all benefits and choices
    """
    class_name = member.character_class.lower()
    con_mod = (member.constitution - 10) // 2
    die_size = get_hit_die_for_class(class_name)

    # Calculate HP options
    hp_average = calculate_hp_increase(class_name, new_level, con_mod, use_average=True)
    hp_max = die_size + con_mod  # If they roll max

    # Check proficiency bonus change
    old_prof = get_proficiency_bonus(member.level)
    new_prof = get_proficiency_bonus(new_level)
    prof_change = new_prof if new_prof > old_prof else None

    # Build choices list
    choices: List[LevelUpChoice] = []

    # HP choice (roll or average)
    choices.append(LevelUpChoice(
        choice_type=LevelUpChoiceType.HP_ROLL,
        description=f"Choose how to determine HP: roll 1d{die_size} or take average ({get_hit_die_average(die_size)})",
        options=[
            {"id": "average", "name": f"Take Average ({get_hit_die_average(die_size)})", "value": get_hit_die_average(die_size)},
            {"id": "roll", "name": f"Roll 1d{die_size}", "value": "roll"},
        ],
        required=True,
    ))

    # ASI / Feat choice
    asi_available = gets_asi_at_level(class_name, new_level)
    if asi_available:
        choices.append(LevelUpChoice(
            choice_type=LevelUpChoiceType.ABILITY_SCORE,
            description="Ability Score Improvement: +2 to one ability, +1 to two abilities, or choose a feat",
            options=[
                {"id": "asi_2", "name": "+2 to One Ability", "type": "asi"},
                {"id": "asi_1_1", "name": "+1 to Two Abilities", "type": "asi"},
                {"id": "feat", "name": "Choose a Feat", "type": "feat"},
            ],
            required=True,
        ))

    # Subclass choice
    subclass_available = gets_subclass_at_level(class_name, new_level) and not member.subclass
    if subclass_available:
        choices.append(LevelUpChoice(
            choice_type=LevelUpChoiceType.SUBCLASS,
            description=f"Choose your {_get_subclass_name(class_name)}",
            options=_get_subclass_options(class_name),
            required=True,
        ))

    # Get new features
    new_features = _get_features_for_level(class_name, new_level)

    # Get spell slot changes
    spell_slots_gained = _get_spell_slot_changes(class_name, member.level, new_level)

    return LevelUpPreview(
        old_level=member.level,
        new_level=new_level,
        hp_increase_average=hp_average,
        hp_increase_max=hp_max,
        new_proficiency_bonus=prof_change,
        new_features=new_features,
        choices_required=choices,
        spell_slots_gained=spell_slots_gained,
        gets_asi=asi_available,
        gets_subclass=subclass_available,
    )


def apply_level_up(
    member: "PartyMember",
    new_level: int,
    hp_choice: str = "average",  # "average" or "roll"
    hp_roll_result: Optional[int] = None,
    asi_choice: Optional[Dict[str, int]] = None,  # {"strength": 2} or {"dexterity": 1, "wisdom": 1}
    feat_choice: Optional[str] = None,
    subclass_choice: Optional[str] = None,
) -> LevelUpResult:
    """
    Apply a level-up to a party member.

    Args:
        member: The party member to level up
        new_level: The new level
        hp_choice: How to determine HP ("average" or "roll")
        hp_roll_result: If rolling, the roll result
        asi_choice: Ability score improvements as dict
        feat_choice: Chosen feat ID
        subclass_choice: Chosen subclass ID

    Returns:
        LevelUpResult with the outcome
    """
    errors = []
    choices_applied = {}

    old_level = member.level
    class_name = member.character_class.lower()
    con_mod = (member.constitution - 10) // 2

    # Validate level-up
    expected_new_level = check_level_up(member)
    if expected_new_level is None:
        return LevelUpResult(
            success=False,
            old_level=old_level,
            new_level=old_level,
            hp_gained=0,
            new_max_hp=member.max_hp,
            new_proficiency_bonus=get_proficiency_bonus(old_level),
            features_gained=[],
            choices_applied={},
            errors=["Not enough XP to level up"],
        )

    # Calculate HP increase
    use_average = hp_choice == "average"
    hp_gained = calculate_hp_increase(
        class_name,
        new_level,
        con_mod,
        use_average=use_average,
        roll_result=hp_roll_result
    )

    # Apply HP increase
    member.max_hp += hp_gained
    member.current_hp += hp_gained  # Gain the HP immediately
    choices_applied["hp"] = {
        "method": hp_choice,
        "roll": hp_roll_result,
        "gained": hp_gained,
    }

    # Apply level increase
    member.level = new_level
    member.hit_dice_total = new_level
    member.hit_dice_remaining = min(member.hit_dice_remaining + 1, new_level)

    # Apply ASI or Feat
    if gets_asi_at_level(class_name, new_level):
        if feat_choice:
            # Apply feat effects
            feat_result = apply_feat_effects(member, feat_choice)
            choices_applied["feat"] = feat_choice
            choices_applied["feat_effects"] = feat_result

        elif asi_choice:
            # Apply ability score improvements
            for ability, increase in asi_choice.items():
                ability_lower = ability.lower()
                if hasattr(member, ability_lower):
                    current = getattr(member, ability_lower)
                    new_value = min(20, current + increase)  # Cap at 20
                    setattr(member, ability_lower, new_value)

            choices_applied["asi"] = asi_choice
        else:
            errors.append("ASI or feat choice required but not provided")

    # Apply subclass
    if gets_subclass_at_level(class_name, new_level) and not member.subclass:
        if subclass_choice:
            member.subclass = subclass_choice
            choices_applied["subclass"] = subclass_choice
        else:
            errors.append("Subclass choice required but not provided")

    # Update spell slots
    try:
        from app.core.class_spellcasting import get_spell_slots_for_level
        new_slots = get_spell_slots_for_level(class_name, new_level)
        if new_slots:
            for level, slots in new_slots.items():
                member.spell_slots[level] = slots
                member.spell_slots_max[level] = slots
    except ImportError as e:
        import logging
        logging.warning(f"Could not load spell slots module for {class_name}: {e}")
        # Spell slots will need to be set manually or remain unchanged

    # Get features gained
    features = _get_features_for_level(class_name, new_level)
    features_gained = [f.name for f in features]

    return LevelUpResult(
        success=len(errors) == 0,
        old_level=old_level,
        new_level=new_level,
        hp_gained=hp_gained,
        new_max_hp=member.max_hp,
        new_proficiency_bonus=get_proficiency_bonus(new_level),
        features_gained=features_gained,
        choices_applied=choices_applied,
        errors=errors,
    )


def _get_subclass_name(class_name: str) -> str:
    """Get the subclass type name for a class."""
    subclass_names = {
        "barbarian": "Primal Path",
        "bard": "Bard College",
        "cleric": "Divine Domain",
        "druid": "Druid Circle",
        "fighter": "Martial Archetype",
        "monk": "Monastic Tradition",
        "paladin": "Sacred Oath",
        "ranger": "Ranger Conclave",
        "rogue": "Roguish Archetype",
        "sorcerer": "Sorcerous Origin",
        "warlock": "Otherworldly Patron",
        "wizard": "Arcane Tradition",
    }
    return subclass_names.get(class_name.lower(), "Subclass")


def _get_subclass_options(class_name: str) -> List[Dict[str, Any]]:
    """Get available subclass options for a class."""
    # Simplified - would load from JSON in production
    subclasses = {
        "fighter": [
            {"id": "champion", "name": "Champion", "description": "Improved critical hits and athletic prowess"},
            {"id": "battle_master", "name": "Battle Master", "description": "Combat maneuvers and tactical superiority"},
            {"id": "eldritch_knight", "name": "Eldritch Knight", "description": "Blend martial skill with arcane magic"},
        ],
        "rogue": [
            {"id": "thief", "name": "Thief", "description": "Master of stealth and second-story work"},
            {"id": "assassin", "name": "Assassin", "description": "Deadly strikes and infiltration"},
            {"id": "arcane_trickster", "name": "Arcane Trickster", "description": "Illusion and enchantment magic"},
        ],
        "wizard": [
            {"id": "evocation", "name": "School of Evocation", "description": "Master of damaging spells"},
            {"id": "abjuration", "name": "School of Abjuration", "description": "Protective magic specialist"},
            {"id": "divination", "name": "School of Divination", "description": "See the future, manipulate fate"},
        ],
        "cleric": [
            {"id": "life", "name": "Life Domain", "description": "Master healer"},
            {"id": "light", "name": "Light Domain", "description": "Radiant damage and fire"},
            {"id": "war", "name": "War Domain", "description": "Divine warrior"},
        ],
        "barbarian": [
            {"id": "berserker", "name": "Path of the Berserker", "description": "Unstoppable fury"},
            {"id": "totem_warrior", "name": "Path of the Totem Warrior", "description": "Spirit animal powers"},
            {"id": "zealot", "name": "Path of the Zealot", "description": "Divine fury"},
        ],
        "paladin": [
            {"id": "devotion", "name": "Oath of Devotion", "description": "Classic holy knight"},
            {"id": "vengeance", "name": "Oath of Vengeance", "description": "Punish the wicked"},
            {"id": "ancients", "name": "Oath of the Ancients", "description": "Protect light and life"},
        ],
    }
    return subclasses.get(class_name.lower(), [])


def _get_features_for_level(class_name: str, level: int) -> List[LevelUpBenefit]:
    """Get class features gained at a specific level."""
    # Simplified - would integrate with class_features.py in production
    features = []

    # Universal features
    if level == 5:
        if class_name.lower() in ["fighter", "paladin", "ranger", "barbarian", "monk"]:
            features.append(LevelUpBenefit(
                benefit_type="feature",
                name="Extra Attack",
                description="You can attack twice instead of once when you take the Attack action."
            ))

    # Proficiency bonus increase
    if level in [5, 9, 13, 17]:
        new_prof = get_proficiency_bonus(level)
        features.append(LevelUpBenefit(
            benefit_type="proficiency",
            name="Proficiency Bonus Increase",
            description=f"Your proficiency bonus increases to +{new_prof}",
            value=new_prof
        ))

    return features


def _get_spell_slot_changes(
    class_name: str,
    old_level: int,
    new_level: int
) -> Dict[int, int]:
    """Get new spell slots gained from leveling up."""
    try:
        from app.core.class_spellcasting import get_spell_slots_for_level

        old_slots = get_spell_slots_for_level(class_name, old_level) or {}
        new_slots = get_spell_slots_for_level(class_name, new_level) or {}

        gained = {}
        for slot_level, count in new_slots.items():
            old_count = old_slots.get(slot_level, 0)
            if count > old_count:
                gained[slot_level] = count - old_count

        return gained
    except ImportError:
        return {}


# =============================================================================
# MULTICLASS SUPPORT
# =============================================================================

def get_multiclass_level_up_options(member: "PartyMember") -> Dict[str, Dict]:
    """
    Get all eligible multiclass options for a character.

    Args:
        member: The party member to check

    Returns:
        Dict of class_name -> {eligible: bool, reasons: list, proficiencies: dict}
    """
    from app.core.multiclass import get_eligible_multiclass_options

    # Get current class levels
    class_levels = getattr(member, "class_levels", {})
    if not class_levels and hasattr(member, "character_class"):
        # Legacy single-class character
        class_levels = {member.character_class.lower(): member.level}

    # Get ability scores
    ability_scores = {
        "strength": getattr(member, "strength", 10),
        "dexterity": getattr(member, "dexterity", 10),
        "constitution": getattr(member, "constitution", 10),
        "intelligence": getattr(member, "intelligence", 10),
        "wisdom": getattr(member, "wisdom", 10),
        "charisma": getattr(member, "charisma", 10),
    }

    return get_eligible_multiclass_options(class_levels, ability_scores)


def get_multiclass_level_up_preview(
    member: "PartyMember",
    class_choice: str
) -> LevelUpPreview:
    """
    Get a preview of what a character will gain from a multiclass level-up.

    Args:
        member: The party member
        class_choice: The class to take the new level in

    Returns:
        LevelUpPreview with all benefits and choices
    """
    class_name = class_choice.lower()

    # Determine the new class level
    class_levels = getattr(member, "class_levels", {})
    if not class_levels and hasattr(member, "character_class"):
        class_levels = {member.character_class.lower(): member.level}

    current_class_level = class_levels.get(class_name, 0)
    new_class_level = current_class_level + 1
    new_total_level = member.level + 1

    con_mod = (member.constitution - 10) // 2
    die_size = get_hit_die_for_class(class_name)

    # Calculate HP options
    hp_average = calculate_hp_increase(class_name, new_class_level, con_mod, use_average=True)
    hp_max = die_size + con_mod

    # Check proficiency bonus change (based on total level)
    old_prof = get_proficiency_bonus(member.level)
    new_prof = get_proficiency_bonus(new_total_level)
    prof_change = new_prof if new_prof > old_prof else None

    # Build choices list
    choices: List[LevelUpChoice] = []

    # HP choice
    choices.append(LevelUpChoice(
        choice_type=LevelUpChoiceType.HP_ROLL,
        description=f"Choose how to determine HP: roll 1d{die_size} or take average ({get_hit_die_average(die_size)})",
        options=[
            {"id": "average", "name": f"Take Average ({get_hit_die_average(die_size)})", "value": get_hit_die_average(die_size)},
            {"id": "roll", "name": f"Roll 1d{die_size}", "value": "roll"},
        ],
        required=True,
    ))

    # ASI / Feat choice - check if this CLASS reaches an ASI level
    asi_available = gets_asi_at_level(class_name, new_class_level)
    if asi_available:
        choices.append(LevelUpChoice(
            choice_type=LevelUpChoiceType.ABILITY_SCORE,
            description="Ability Score Improvement: +2 to one ability, +1 to two abilities, or choose a feat",
            options=[
                {"id": "asi_2", "name": "+2 to One Ability", "type": "asi"},
                {"id": "asi_1_1", "name": "+1 to Two Abilities", "type": "asi"},
                {"id": "feat", "name": "Choose a Feat", "type": "feat"},
            ],
            required=True,
        ))

    # Subclass choice - check if this CLASS reaches subclass level
    subclass_available = gets_subclass_at_level(class_name, new_class_level)
    current_subclasses = getattr(member, "subclasses", {})
    has_subclass_for_class = class_name in current_subclasses
    if subclass_available and not has_subclass_for_class:
        choices.append(LevelUpChoice(
            choice_type=LevelUpChoiceType.SUBCLASS,
            description=f"Choose your {_get_subclass_name(class_name)}",
            options=_get_subclass_options(class_name),
            required=True,
        ))

    # Add multiclass proficiencies if first level in new class
    is_new_class = current_class_level == 0
    if is_new_class:
        from app.core.multiclass import get_multiclass_proficiencies
        mc_profs = get_multiclass_proficiencies(class_name)
        # Could add skill choices here if class grants them

    # Get new features for this class level
    new_features = _get_features_for_level(class_name, new_class_level)

    # Get spell slot changes (multiclass uses combined caster level)
    spell_slots_gained = {}  # Will be calculated by multiclass spellcasting

    return LevelUpPreview(
        old_level=member.level,
        new_level=new_total_level,
        hp_increase_average=hp_average,
        hp_increase_max=hp_max,
        new_proficiency_bonus=prof_change,
        new_features=new_features,
        choices_required=choices,
        spell_slots_gained=spell_slots_gained,
        gets_asi=asi_available,
        gets_subclass=subclass_available and not has_subclass_for_class,
    )


def apply_multiclass_level_up(
    member: "PartyMember",
    class_choice: str,
    hp_choice: str = "average",
    hp_roll_result: Optional[int] = None,
    asi_choice: Optional[Dict[str, int]] = None,
    feat_choice: Optional[str] = None,
    subclass_choice: Optional[str] = None,
) -> LevelUpResult:
    """
    Apply a multiclass level-up to a party member.

    Args:
        member: The party member to level up
        class_choice: The class to take the new level in
        hp_choice: How to determine HP ("average" or "roll")
        hp_roll_result: If rolling, the roll result
        asi_choice: Ability score improvements as dict
        feat_choice: Chosen feat ID
        subclass_choice: Chosen subclass ID

    Returns:
        LevelUpResult with the outcome
    """
    from app.core.multiclass import check_multiclass_prerequisites, get_multiclass_proficiencies

    errors = []
    choices_applied = {}
    class_name = class_choice.lower()

    old_level = member.level
    con_mod = (member.constitution - 10) // 2

    # Get or initialize class_levels
    if not hasattr(member, "class_levels") or not member.class_levels:
        member.class_levels = {}
        if hasattr(member, "character_class") and member.character_class:
            member.class_levels[member.character_class.lower()] = member.level
            if not member.primary_class:
                member.primary_class = member.character_class.lower()

    # Validate XP requirement
    expected_new_level = check_level_up(member)
    if expected_new_level is None:
        return LevelUpResult(
            success=False,
            old_level=old_level,
            new_level=old_level,
            hp_gained=0,
            new_max_hp=member.max_hp,
            new_proficiency_bonus=get_proficiency_bonus(old_level),
            features_gained=[],
            choices_applied={},
            errors=["Not enough XP to level up"],
        )

    # Validate multiclass prerequisites
    ability_scores = {
        "strength": getattr(member, "strength", 10),
        "dexterity": getattr(member, "dexterity", 10),
        "constitution": getattr(member, "constitution", 10),
        "intelligence": getattr(member, "intelligence", 10),
        "wisdom": getattr(member, "wisdom", 10),
        "charisma": getattr(member, "charisma", 10),
    }

    can_multiclass, prereq_failures = check_multiclass_prerequisites(
        member.class_levels, class_name, ability_scores
    )

    if not can_multiclass:
        return LevelUpResult(
            success=False,
            old_level=old_level,
            new_level=old_level,
            hp_gained=0,
            new_max_hp=member.max_hp,
            new_proficiency_bonus=get_proficiency_bonus(old_level),
            features_gained=[],
            choices_applied={},
            errors=prereq_failures,
        )

    # Determine if this is a new class
    is_new_class = class_name not in member.class_levels
    current_class_level = member.class_levels.get(class_name, 0)
    new_class_level = current_class_level + 1

    # Calculate HP increase (use the new class's hit die)
    use_average = hp_choice == "average"
    hp_gained = calculate_hp_increase(
        class_name,
        new_class_level,
        con_mod,
        use_average=use_average,
        roll_result=hp_roll_result
    )

    # Apply HP increase
    member.max_hp += hp_gained
    member.current_hp += hp_gained
    choices_applied["hp"] = {
        "method": hp_choice,
        "roll": hp_roll_result,
        "gained": hp_gained,
        "class": class_name,
    }

    # Add class level
    member.add_class_level(class_name)
    choices_applied["class_choice"] = class_name
    choices_applied["new_class_level"] = new_class_level

    # Update legacy level field
    member._level = member.total_level

    # Update hit dice pool
    die_size = get_hit_die_for_class(class_name)
    if not hasattr(member, "hit_dice_by_class") or not member.hit_dice_by_class:
        member.hit_dice_by_class = {}
    if class_name not in member.hit_dice_by_class:
        member.hit_dice_by_class[class_name] = {"total": 0, "remaining": 0}
    member.hit_dice_by_class[class_name]["total"] = new_class_level
    member.hit_dice_by_class[class_name]["remaining"] = min(
        member.hit_dice_by_class[class_name]["remaining"] + 1,
        new_class_level
    )

    # Grant multiclass proficiencies if new class
    if is_new_class:
        mc_profs = get_multiclass_proficiencies(class_name)
        if not hasattr(member, "proficiencies"):
            member.proficiencies = {"armor": [], "weapons": [], "tools": []}

        for armor in mc_profs.get("armor", []):
            if armor not in member.proficiencies.get("armor", []):
                if "armor" not in member.proficiencies:
                    member.proficiencies["armor"] = []
                member.proficiencies["armor"].append(armor)

        for weapon in mc_profs.get("weapons", []):
            if weapon not in member.proficiencies.get("weapons", []):
                if "weapons" not in member.proficiencies:
                    member.proficiencies["weapons"] = []
                member.proficiencies["weapons"].append(weapon)

        choices_applied["multiclass_proficiencies"] = mc_profs

    # Apply ASI or Feat (based on class level, not total level)
    if gets_asi_at_level(class_name, new_class_level):
        if feat_choice:
            feat_result = apply_feat_effects(member, feat_choice)
            choices_applied["feat"] = feat_choice
            choices_applied["feat_effects"] = feat_result
        elif asi_choice:
            for ability, increase in asi_choice.items():
                ability_lower = ability.lower()
                if hasattr(member, ability_lower):
                    current = getattr(member, ability_lower)
                    new_value = min(20, current + increase)
                    setattr(member, ability_lower, new_value)
            choices_applied["asi"] = asi_choice
        else:
            errors.append("ASI or feat choice required but not provided")

    # Apply subclass (based on class level)
    if gets_subclass_at_level(class_name, new_class_level):
        if not hasattr(member, "subclasses"):
            member.subclasses = {}
        if class_name not in member.subclasses:
            if subclass_choice:
                member.subclasses[class_name] = subclass_choice
                choices_applied["subclass"] = subclass_choice
            else:
                errors.append(f"Subclass choice required for {class_name} but not provided")

    # Get features gained for this class level
    features = _get_features_for_level(class_name, new_class_level)
    features_gained = [f.name for f in features]

    new_total_level = member.total_level

    return LevelUpResult(
        success=len(errors) == 0,
        old_level=old_level,
        new_level=new_total_level,
        hp_gained=hp_gained,
        new_max_hp=member.max_hp,
        new_proficiency_bonus=get_proficiency_bonus(new_total_level),
        features_gained=features_gained,
        choices_applied=choices_applied,
        errors=errors,
    )


def get_level_up_class_choices(member: "PartyMember") -> LevelUpChoice:
    """
    Get the class choice for level-up (for multiclass-eligible characters).

    Args:
        member: The party member

    Returns:
        LevelUpChoice with eligible class options
    """
    options = get_multiclass_level_up_options(member)

    class_options = []
    for class_name, info in options.items():
        option = {
            "id": class_name,
            "name": class_name.title(),
            "eligible": info["eligible"],
            "already_has": info["already_has"],
        }
        if not info["eligible"]:
            option["reasons"] = info["reasons"]
        if info["already_has"]:
            # Get current level in this class
            class_levels = getattr(member, "class_levels", {})
            option["current_level"] = class_levels.get(class_name, 0)
        class_options.append(option)

    # Sort: eligible first, then current classes, then ineligible
    class_options.sort(key=lambda x: (
        0 if x["eligible"] and x["already_has"] else
        1 if x["eligible"] else
        2
    ))

    return LevelUpChoice(
        choice_type=LevelUpChoiceType.CLASS_CHOICE,
        description="Choose which class to take your next level in",
        options=class_options,
        required=True,
    )
