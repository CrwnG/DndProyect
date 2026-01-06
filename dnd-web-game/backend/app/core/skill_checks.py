"""
Skill Check System.

D&D 5e skill checks with dice rolling, modifiers, and DC comparison.
Supports proficiency bonuses, expertise, advantage/disadvantage.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
import random


class Skill(str, Enum):
    """D&D 5e skills mapped to ability scores."""
    # Strength
    ATHLETICS = "athletics"

    # Dexterity
    ACROBATICS = "acrobatics"
    SLEIGHT_OF_HAND = "sleight_of_hand"
    STEALTH = "stealth"

    # Intelligence
    ARCANA = "arcana"
    HISTORY = "history"
    INVESTIGATION = "investigation"
    NATURE = "nature"
    RELIGION = "religion"

    # Wisdom
    ANIMAL_HANDLING = "animal_handling"
    INSIGHT = "insight"
    MEDICINE = "medicine"
    PERCEPTION = "perception"
    SURVIVAL = "survival"

    # Charisma
    DECEPTION = "deception"
    INTIMIDATION = "intimidation"
    PERFORMANCE = "performance"
    PERSUASION = "persuasion"


# Skill to ability score mapping
SKILL_ABILITIES = {
    Skill.ATHLETICS: "str",
    Skill.ACROBATICS: "dex",
    Skill.SLEIGHT_OF_HAND: "dex",
    Skill.STEALTH: "dex",
    Skill.ARCANA: "int",
    Skill.HISTORY: "int",
    Skill.INVESTIGATION: "int",
    Skill.NATURE: "int",
    Skill.RELIGION: "int",
    Skill.ANIMAL_HANDLING: "wis",
    Skill.INSIGHT: "wis",
    Skill.MEDICINE: "wis",
    Skill.PERCEPTION: "wis",
    Skill.SURVIVAL: "wis",
    Skill.DECEPTION: "cha",
    Skill.INTIMIDATION: "cha",
    Skill.PERFORMANCE: "cha",
    Skill.PERSUASION: "cha",
}


class DifficultyClass(Enum):
    """Standard D&D 5e difficulty classes."""
    TRIVIAL = 5
    EASY = 10
    MEDIUM = 15
    HARD = 20
    VERY_HARD = 25
    NEARLY_IMPOSSIBLE = 30


@dataclass
class SkillCheckResult:
    """Result of a skill check."""
    skill: str
    ability: str
    roll: int
    modifier: int
    total: int
    dc: int
    success: bool
    critical_success: bool  # Natural 20
    critical_failure: bool  # Natural 1
    advantage: bool = False
    disadvantage: bool = False
    rolls: List[int] = None  # Both dice if advantage/disadvantage

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill": self.skill,
            "ability": self.ability,
            "roll": self.roll,
            "modifier": self.modifier,
            "total": self.total,
            "dc": self.dc,
            "success": self.success,
            "critical_success": self.critical_success,
            "critical_failure": self.critical_failure,
            "advantage": self.advantage,
            "disadvantage": self.disadvantage,
            "rolls": self.rolls or [self.roll],
        }


def get_ability_modifier(score: int) -> int:
    """Calculate ability modifier from score (D&D 5e formula)."""
    return (score - 10) // 2


def get_proficiency_bonus(level: int) -> int:
    """Get proficiency bonus based on character level."""
    if level < 5:
        return 2
    elif level < 9:
        return 3
    elif level < 13:
        return 4
    elif level < 17:
        return 5
    else:
        return 6


def roll_d20(
    advantage: bool = False,
    disadvantage: bool = False
) -> Tuple[int, List[int]]:
    """
    Roll a d20 with optional advantage/disadvantage.

    Returns:
        Tuple of (result, all_rolls)
    """
    roll1 = random.randint(1, 20)

    if advantage and not disadvantage:
        roll2 = random.randint(1, 20)
        return max(roll1, roll2), [roll1, roll2]
    elif disadvantage and not advantage:
        roll2 = random.randint(1, 20)
        return min(roll1, roll2), [roll1, roll2]
    else:
        return roll1, [roll1]


def perform_skill_check(
    skill: str,
    dc: int,
    character_stats: Dict[str, Any],
    advantage: bool = False,
    disadvantage: bool = False,
    proficient: bool = None,
    expertise: bool = False,
) -> SkillCheckResult:
    """
    Perform a skill check for a character.

    Args:
        skill: Skill name (e.g., "stealth", "persuasion")
        dc: Difficulty class to beat
        character_stats: Dict with ability scores, level, proficiencies
        advantage: Roll with advantage
        disadvantage: Roll with disadvantage
        proficient: Override proficiency (None = check character's proficiencies)
        expertise: Has expertise (double proficiency)

    Returns:
        SkillCheckResult with all roll details
    """
    # Get skill enum
    try:
        skill_enum = Skill(skill.lower())
    except ValueError:
        # Default to a straight ability check
        skill_enum = None

    # Determine ability score
    if skill_enum:
        ability = SKILL_ABILITIES[skill_enum]
    else:
        # If not a skill, assume it's an ability check (str, dex, etc.)
        ability = skill.lower()[:3]

    # Get ability score and modifier
    ability_score = character_stats.get(ability, 10)
    ability_mod = get_ability_modifier(ability_score)

    # Calculate proficiency
    level = character_stats.get("level", 1)
    prof_bonus = get_proficiency_bonus(level)

    # Check if character is proficient
    if proficient is None:
        proficiencies = character_stats.get("skill_proficiencies", [])
        proficient = skill.lower() in [p.lower() for p in proficiencies]

    # Calculate total modifier
    modifier = ability_mod
    if proficient:
        modifier += prof_bonus * (2 if expertise else 1)

    # Roll the dice
    roll, all_rolls = roll_d20(advantage, disadvantage)
    total = roll + modifier

    # Determine success
    critical_success = roll == 20
    critical_failure = roll == 1
    success = total >= dc

    return SkillCheckResult(
        skill=skill,
        ability=ability,
        roll=roll,
        modifier=modifier,
        total=total,
        dc=dc,
        success=success,
        critical_success=critical_success,
        critical_failure=critical_failure,
        advantage=advantage,
        disadvantage=disadvantage,
        rolls=all_rolls,
    )


def perform_ability_check(
    ability: str,
    dc: int,
    character_stats: Dict[str, Any],
    advantage: bool = False,
    disadvantage: bool = False,
) -> SkillCheckResult:
    """
    Perform a raw ability check (no skill).

    Args:
        ability: Ability name (str, dex, con, int, wis, cha)
        dc: Difficulty class
        character_stats: Character stats dict
        advantage/disadvantage: Roll modifiers

    Returns:
        SkillCheckResult
    """
    ability_score = character_stats.get(ability.lower()[:3], 10)
    modifier = get_ability_modifier(ability_score)

    roll, all_rolls = roll_d20(advantage, disadvantage)
    total = roll + modifier

    return SkillCheckResult(
        skill=ability,
        ability=ability,
        roll=roll,
        modifier=modifier,
        total=total,
        dc=dc,
        success=total >= dc,
        critical_success=roll == 20,
        critical_failure=roll == 1,
        advantage=advantage,
        disadvantage=disadvantage,
        rolls=all_rolls,
    )


def perform_saving_throw(
    ability: str,
    dc: int,
    character_stats: Dict[str, Any],
    advantage: bool = False,
    disadvantage: bool = False,
    proficient: bool = None,
) -> SkillCheckResult:
    """
    Perform a saving throw.

    Args:
        ability: Ability for the save (str, dex, con, int, wis, cha)
        dc: Difficulty class
        character_stats: Character stats dict
        advantage/disadvantage: Roll modifiers
        proficient: Override save proficiency

    Returns:
        SkillCheckResult
    """
    ability_key = ability.lower()[:3]
    ability_score = character_stats.get(ability_key, 10)
    modifier = get_ability_modifier(ability_score)

    # Check save proficiency
    level = character_stats.get("level", 1)
    if proficient is None:
        save_profs = character_stats.get("saving_throw_proficiencies", [])
        proficient = ability_key in [p.lower()[:3] for p in save_profs]

    if proficient:
        modifier += get_proficiency_bonus(level)

    roll, all_rolls = roll_d20(advantage, disadvantage)
    total = roll + modifier

    return SkillCheckResult(
        skill=f"{ability}_save",
        ability=ability_key,
        roll=roll,
        modifier=modifier,
        total=total,
        dc=dc,
        success=total >= dc,
        critical_success=roll == 20,
        critical_failure=roll == 1,
        advantage=advantage,
        disadvantage=disadvantage,
        rolls=all_rolls,
    )


def get_dc_difficulty_label(dc: int) -> str:
    """Get human-readable difficulty label for a DC."""
    if dc <= 5:
        return "Trivial"
    elif dc <= 10:
        return "Easy"
    elif dc <= 15:
        return "Medium"
    elif dc <= 20:
        return "Hard"
    elif dc <= 25:
        return "Very Hard"
    else:
        return "Nearly Impossible"


def get_skill_display_name(skill: str) -> str:
    """Get display-friendly skill name."""
    return skill.replace("_", " ").title()


def get_skill_modifier(character_stats: Dict[str, Any], skill: str) -> int:
    """
    Calculate the total modifier for a skill check.

    Args:
        character_stats: Character stats dict with abilities and proficiencies
        skill: Skill name (e.g., "stealth", "persuasion")

    Returns:
        Total modifier (ability + proficiency if applicable)
    """
    # Get skill enum
    try:
        skill_enum = Skill(skill.lower())
        ability = SKILL_ABILITIES[skill_enum]
    except ValueError:
        # If not a skill, assume it's an ability check
        ability = skill.lower()[:3]

    # Get ability modifier
    ability_score = character_stats.get(ability, 10)
    ability_mod = get_ability_modifier(ability_score)

    # Check proficiency
    level = character_stats.get("level", 1)
    proficiencies = character_stats.get("skill_proficiencies", [])
    proficient = skill.lower() in [p.lower() for p in proficiencies]

    modifier = ability_mod
    if proficient:
        modifier += get_proficiency_bonus(level)

    return modifier


@dataclass
class GroupCheckResult:
    """Result of a group skill check (D&D 5e PHB p.175)."""
    skill: str
    dc: int
    individual_results: List[SkillCheckResult]
    successes: int
    failures: int
    needed_successes: int
    success: bool  # True if at least half succeeded

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill": self.skill,
            "dc": self.dc,
            "individual_results": [r.to_dict() for r in self.individual_results],
            "successes": self.successes,
            "failures": self.failures,
            "needed_successes": self.needed_successes,
            "success": self.success,
        }


def perform_group_check(
    skill: str,
    dc: int,
    party_members: List[Dict[str, Any]],
    advantage: bool = False,
    disadvantage: bool = False,
) -> GroupCheckResult:
    """
    Perform a D&D 5e group skill check.

    From PHB p.175: "To make a group ability check, everyone in the group
    makes the ability check. If at least half the group succeeds, the
    whole group succeeds."

    Args:
        skill: Skill name (e.g., "stealth")
        dc: Difficulty class
        party_members: List of party member stat dicts
        advantage: All members have advantage
        disadvantage: All members have disadvantage

    Returns:
        GroupCheckResult with all individual rolls and overall success
    """
    results = []

    for member in party_members:
        # Get character stats from member data
        character_stats = {
            "str": member.get("strength", member.get("str", 10)),
            "dex": member.get("dexterity", member.get("dex", 10)),
            "con": member.get("constitution", member.get("con", 10)),
            "int": member.get("intelligence", member.get("int", 10)),
            "wis": member.get("wisdom", member.get("wis", 10)),
            "cha": member.get("charisma", member.get("cha", 10)),
            "level": member.get("level", 1),
            "skill_proficiencies": member.get("skill_proficiencies", []),
        }

        result = perform_skill_check(
            skill=skill,
            dc=dc,
            character_stats=character_stats,
            advantage=advantage,
            disadvantage=disadvantage,
        )
        # Add character name to result for display
        result.character_name = member.get("name", "Unknown")
        result.character_id = member.get("id", "")
        results.append(result)

    # Count successes
    successes = sum(1 for r in results if r.success)
    failures = len(results) - successes

    # D&D 5e rule: at least half must succeed
    # For odd numbers, round up (e.g., 3 members need 2 successes)
    needed = (len(party_members) + 1) // 2
    group_success = successes >= needed

    return GroupCheckResult(
        skill=skill,
        dc=dc,
        individual_results=results,
        successes=successes,
        failures=failures,
        needed_successes=needed,
        success=group_success,
    )
