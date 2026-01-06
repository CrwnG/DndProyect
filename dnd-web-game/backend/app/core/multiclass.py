"""
Multiclass Support for D&D 5e 2024.

Handles multiclass prerequisites, proficiency grants, and validation.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple, Set


class AbilityScore(str, Enum):
    """Ability score names."""
    STRENGTH = "strength"
    DEXTERITY = "dexterity"
    CONSTITUTION = "constitution"
    INTELLIGENCE = "intelligence"
    WISDOM = "wisdom"
    CHARISMA = "charisma"


@dataclass
class MulticlassPrerequisite:
    """Defines the ability score requirements for multiclassing into a class."""
    class_name: str
    requirements: List[Tuple[str, int]]  # List of (ability, min_score) pairs
    all_required: bool = True  # True = AND, False = OR


# D&D 5e 2024 Multiclass Prerequisites
MULTICLASS_PREREQUISITES: Dict[str, MulticlassPrerequisite] = {
    "barbarian": MulticlassPrerequisite(
        class_name="Barbarian",
        requirements=[("strength", 13)],
        all_required=True
    ),
    "bard": MulticlassPrerequisite(
        class_name="Bard",
        requirements=[("charisma", 13)],
        all_required=True
    ),
    "cleric": MulticlassPrerequisite(
        class_name="Cleric",
        requirements=[("wisdom", 13)],
        all_required=True
    ),
    "druid": MulticlassPrerequisite(
        class_name="Druid",
        requirements=[("wisdom", 13)],
        all_required=True
    ),
    "fighter": MulticlassPrerequisite(
        class_name="Fighter",
        requirements=[("strength", 13), ("dexterity", 13)],
        all_required=False  # STR 13 OR DEX 13
    ),
    "monk": MulticlassPrerequisite(
        class_name="Monk",
        requirements=[("dexterity", 13), ("wisdom", 13)],
        all_required=True  # DEX 13 AND WIS 13
    ),
    "paladin": MulticlassPrerequisite(
        class_name="Paladin",
        requirements=[("strength", 13), ("charisma", 13)],
        all_required=True  # STR 13 AND CHA 13
    ),
    "ranger": MulticlassPrerequisite(
        class_name="Ranger",
        requirements=[("dexterity", 13), ("wisdom", 13)],
        all_required=True  # DEX 13 AND WIS 13
    ),
    "rogue": MulticlassPrerequisite(
        class_name="Rogue",
        requirements=[("dexterity", 13)],
        all_required=True
    ),
    "sorcerer": MulticlassPrerequisite(
        class_name="Sorcerer",
        requirements=[("charisma", 13)],
        all_required=True
    ),
    "warlock": MulticlassPrerequisite(
        class_name="Warlock",
        requirements=[("charisma", 13)],
        all_required=True
    ),
    "wizard": MulticlassPrerequisite(
        class_name="Wizard",
        requirements=[("intelligence", 13)],
        all_required=True
    ),
}


# Proficiencies granted when multiclassing INTO a class (not starting as that class)
MULTICLASS_PROFICIENCIES: Dict[str, Dict[str, List[str]]] = {
    "barbarian": {
        "armor": [],  # No armor proficiencies
        "weapons": ["martial weapons"],
        "skills": [],
    },
    "bard": {
        "armor": ["light armor"],
        "weapons": [],
        "skills": ["any one skill"],  # Special: choose 1 skill
    },
    "cleric": {
        "armor": ["light armor", "medium armor", "shields"],
        "weapons": [],
        "skills": [],
    },
    "druid": {
        "armor": ["light armor", "medium armor", "shields"],  # Non-metal restriction
        "weapons": [],
        "skills": [],
    },
    "fighter": {
        "armor": ["light armor", "medium armor", "shields"],
        "weapons": ["simple weapons", "martial weapons"],
        "skills": [],
    },
    "monk": {
        "armor": [],
        "weapons": ["simple weapons", "shortswords"],
        "skills": [],
    },
    "paladin": {
        "armor": ["light armor", "medium armor", "shields"],
        "weapons": ["simple weapons", "martial weapons"],
        "skills": [],
    },
    "ranger": {
        "armor": ["light armor", "medium armor", "shields"],
        "weapons": ["simple weapons", "martial weapons"],
        "skills": ["one skill from ranger skill list"],  # Special: choose 1 skill
    },
    "rogue": {
        "armor": ["light armor"],
        "weapons": [],
        "skills": ["one skill from rogue skill list"],  # Special: choose 1 skill
    },
    "sorcerer": {
        "armor": [],
        "weapons": [],
        "skills": [],
    },
    "warlock": {
        "armor": ["light armor"],
        "weapons": ["simple weapons"],
        "skills": [],
    },
    "wizard": {
        "armor": [],
        "weapons": [],
        "skills": [],
    },
}


def check_prerequisite(
    prerequisite: MulticlassPrerequisite,
    ability_scores: Dict[str, int]
) -> Tuple[bool, List[str]]:
    """
    Check if ability scores meet a multiclass prerequisite.

    Args:
        prerequisite: The prerequisite to check
        ability_scores: Dict of ability name -> score

    Returns:
        Tuple of (meets_requirement, list of failure reasons)
    """
    failures = []
    met_requirements = []

    for ability, min_score in prerequisite.requirements:
        score = ability_scores.get(ability.lower(), 0)
        if score >= min_score:
            met_requirements.append(ability)
        else:
            failures.append(f"{ability.title()} must be at least {min_score} (currently {score})")

    if prerequisite.all_required:
        # All requirements must be met (AND)
        return len(failures) == 0, failures
    else:
        # At least one requirement must be met (OR)
        if met_requirements:
            return True, []
        return False, [f"Need at least one of: {', '.join(f'{a.title()} 13' for a, _ in prerequisite.requirements)}"]


def check_multiclass_prerequisites(
    current_classes: Dict[str, int],
    new_class: str,
    ability_scores: Dict[str, int]
) -> Tuple[bool, List[str]]:
    """
    Check if a character can multiclass into a new class.

    Per D&D 5e 2024 rules:
    - Must meet prerequisites of BOTH current class AND new class
    - For current classes, only need to check the classes you already have levels in

    Args:
        current_classes: Dict of class_name -> level (character's current classes)
        new_class: The class to multiclass into
        ability_scores: Dict of ability name -> score

    Returns:
        Tuple of (can_multiclass, list of failure reasons)
    """
    all_failures = []
    new_class_lower = new_class.lower()

    # Check prerequisites for the new class
    if new_class_lower in MULTICLASS_PREREQUISITES:
        prereq = MULTICLASS_PREREQUISITES[new_class_lower]
        meets, failures = check_prerequisite(prereq, ability_scores)
        if not meets:
            all_failures.extend([f"To multiclass into {new_class}: {f}" for f in failures])

    # Check prerequisites for all current classes
    for class_name in current_classes.keys():
        class_lower = class_name.lower()
        if class_lower in MULTICLASS_PREREQUISITES:
            prereq = MULTICLASS_PREREQUISITES[class_lower]
            meets, failures = check_prerequisite(prereq, ability_scores)
            if not meets:
                all_failures.extend([f"To multiclass from {class_name.title()}: {f}" for f in failures])

    return len(all_failures) == 0, all_failures


def get_multiclass_proficiencies(new_class: str) -> Dict[str, List[str]]:
    """
    Get proficiencies granted when multiclassing into a class.

    Note: These are DIFFERENT from starting proficiencies!
    Multiclassing grants a limited set of proficiencies.

    Args:
        new_class: The class being multiclassed into

    Returns:
        Dict with armor, weapons, and skills proficiency lists
    """
    return MULTICLASS_PROFICIENCIES.get(new_class.lower(), {
        "armor": [],
        "weapons": [],
        "skills": [],
    })


def get_eligible_multiclass_options(
    current_classes: Dict[str, int],
    ability_scores: Dict[str, int]
) -> Dict[str, Dict]:
    """
    Get all classes that a character is eligible to multiclass into.

    Args:
        current_classes: Dict of class_name -> level
        ability_scores: Dict of ability name -> score

    Returns:
        Dict of class_name -> {eligible: bool, reasons: list, proficiencies: dict}
    """
    options = {}

    for class_name, prereq in MULTICLASS_PREREQUISITES.items():
        can_multiclass, failures = check_multiclass_prerequisites(
            current_classes, class_name, ability_scores
        )

        options[class_name] = {
            "eligible": can_multiclass,
            "reasons": failures if not can_multiclass else [],
            "proficiencies": get_multiclass_proficiencies(class_name),
            "already_has": class_name in {c.lower() for c in current_classes.keys()},
        }

    return options


def format_prerequisites(class_name: str) -> str:
    """
    Get a human-readable description of multiclass prerequisites.

    Args:
        class_name: The class name

    Returns:
        Formatted prerequisite string
    """
    prereq = MULTICLASS_PREREQUISITES.get(class_name.lower())
    if not prereq:
        return "No prerequisites defined"

    if len(prereq.requirements) == 1:
        ability, score = prereq.requirements[0]
        return f"{ability.title()} {score}"

    connector = " and " if prereq.all_required else " or "
    parts = [f"{ability.title()} {score}" for ability, score in prereq.requirements]
    return connector.join(parts)
