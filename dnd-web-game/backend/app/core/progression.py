"""
Character Progression System for D&D 5e 2024

Handles experience points (XP) and level advancement:
- XP thresholds for each level
- Proficiency bonus by level
- Level calculations from XP
- Progress tracking to next level
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


# D&D 5e Experience Point Thresholds
# XP required to reach each level
XP_THRESHOLDS: Dict[int, int] = {
    1: 0,
    2: 300,
    3: 900,
    4: 2700,
    5: 6500,
    6: 14000,
    7: 23000,
    8: 34000,
    9: 48000,
    10: 64000,
    11: 85000,
    12: 100000,
    13: 120000,
    14: 140000,
    15: 165000,
    16: 195000,
    17: 225000,
    18: 265000,
    19: 305000,
    20: 355000,
}

# Maximum level in D&D 5e
MAX_LEVEL = 20

# Proficiency bonus by level
PROFICIENCY_BY_LEVEL: Dict[int, int] = {
    1: 2, 2: 2, 3: 2, 4: 2,
    5: 3, 6: 3, 7: 3, 8: 3,
    9: 4, 10: 4, 11: 4, 12: 4,
    13: 5, 14: 5, 15: 5, 16: 5,
    17: 6, 18: 6, 19: 6, 20: 6,
}


def get_level_for_xp(xp: int) -> int:
    """
    Calculate the level for a given XP total.

    Args:
        xp: Total experience points

    Returns:
        Character level (1-20)
    """
    level = 1
    for lvl, threshold in XP_THRESHOLDS.items():
        if xp >= threshold:
            level = lvl
        else:
            break
    return min(level, MAX_LEVEL)


def get_xp_for_level(level: int) -> int:
    """
    Get the XP threshold required to reach a specific level.

    Args:
        level: Target level (1-20)

    Returns:
        XP required to reach that level
    """
    level = max(1, min(level, MAX_LEVEL))
    return XP_THRESHOLDS.get(level, 0)


def get_xp_for_next_level(current_level: int) -> Optional[int]:
    """
    Get the XP threshold for the next level.

    Args:
        current_level: Current character level

    Returns:
        XP for next level, or None if at max level
    """
    if current_level >= MAX_LEVEL:
        return None
    return XP_THRESHOLDS.get(current_level + 1)


def xp_to_next_level(current_xp: int) -> Optional[int]:
    """
    Calculate XP needed to reach the next level.

    Args:
        current_xp: Current total XP

    Returns:
        XP needed, or None if at max level
    """
    current_level = get_level_for_xp(current_xp)
    if current_level >= MAX_LEVEL:
        return None

    next_threshold = XP_THRESHOLDS.get(current_level + 1, 0)
    return next_threshold - current_xp


def get_xp_progress(current_xp: int) -> Tuple[int, int, float]:
    """
    Get XP progress within current level.

    Args:
        current_xp: Current total XP

    Returns:
        Tuple of (current_level_xp, next_level_xp, progress_percent)
    """
    current_level = get_level_for_xp(current_xp)

    current_threshold = XP_THRESHOLDS.get(current_level, 0)

    if current_level >= MAX_LEVEL:
        return (current_xp, current_xp, 1.0)

    next_threshold = XP_THRESHOLDS.get(current_level + 1, current_xp)
    level_xp_range = next_threshold - current_threshold
    xp_in_level = current_xp - current_threshold

    if level_xp_range == 0:
        progress = 1.0
    else:
        progress = xp_in_level / level_xp_range

    return (current_xp - current_threshold, next_threshold - current_threshold, progress)


def get_proficiency_bonus(level: int) -> int:
    """
    Get the proficiency bonus for a level.

    Args:
        level: Character level (1-20)

    Returns:
        Proficiency bonus (+2 to +6)
    """
    level = max(1, min(level, MAX_LEVEL))
    return PROFICIENCY_BY_LEVEL.get(level, 2)


def can_level_up(current_xp: int, current_level: int) -> bool:
    """
    Check if a character can level up.

    Args:
        current_xp: Current total XP
        current_level: Current level

    Returns:
        True if character has enough XP for next level
    """
    if current_level >= MAX_LEVEL:
        return False

    next_threshold = XP_THRESHOLDS.get(current_level + 1)
    if next_threshold is None:
        return False

    return current_xp >= next_threshold


def get_new_level_from_xp(current_xp: int, current_level: int) -> Optional[int]:
    """
    Get the new level a character should be at based on XP.

    Handles multiple level-ups at once (e.g., from large XP rewards).

    Args:
        current_xp: Current total XP
        current_level: Current level

    Returns:
        New level if level up is possible, None if already at correct level
    """
    calculated_level = get_level_for_xp(current_xp)

    if calculated_level > current_level:
        return calculated_level

    return None


@dataclass
class ProgressionInfo:
    """Complete progression information for a character."""
    current_level: int
    current_xp: int
    xp_for_current_level: int
    xp_for_next_level: Optional[int]
    xp_needed: Optional[int]
    xp_progress: float  # 0.0 to 1.0
    proficiency_bonus: int
    can_level_up: bool
    potential_new_level: Optional[int]

    def to_dict(self) -> Dict:
        return {
            "current_level": self.current_level,
            "current_xp": self.current_xp,
            "xp_for_current_level": self.xp_for_current_level,
            "xp_for_next_level": self.xp_for_next_level,
            "xp_needed": self.xp_needed,
            "xp_progress": round(self.xp_progress, 3),
            "proficiency_bonus": self.proficiency_bonus,
            "can_level_up": self.can_level_up,
            "potential_new_level": self.potential_new_level,
        }


def get_progression_info(current_xp: int, current_level: int) -> ProgressionInfo:
    """
    Get complete progression information for a character.

    Args:
        current_xp: Current total XP
        current_level: Current level

    Returns:
        ProgressionInfo with all relevant data
    """
    xp_in_level, xp_range, progress = get_xp_progress(current_xp)

    return ProgressionInfo(
        current_level=current_level,
        current_xp=current_xp,
        xp_for_current_level=get_xp_for_level(current_level),
        xp_for_next_level=get_xp_for_next_level(current_level),
        xp_needed=xp_to_next_level(current_xp),
        xp_progress=progress,
        proficiency_bonus=get_proficiency_bonus(current_level),
        can_level_up=can_level_up(current_xp, current_level),
        potential_new_level=get_new_level_from_xp(current_xp, current_level),
    )


# Challenge Rating to XP conversion (for encounter rewards)
CR_TO_XP: Dict[str, int] = {
    "0": 10,
    "1/8": 25,
    "1/4": 50,
    "1/2": 100,
    "1": 200,
    "2": 450,
    "3": 700,
    "4": 1100,
    "5": 1800,
    "6": 2300,
    "7": 2900,
    "8": 3900,
    "9": 5000,
    "10": 5900,
    "11": 7200,
    "12": 8400,
    "13": 10000,
    "14": 11500,
    "15": 13000,
    "16": 15000,
    "17": 18000,
    "18": 20000,
    "19": 22000,
    "20": 25000,
    "21": 33000,
    "22": 41000,
    "23": 50000,
    "24": 62000,
    "25": 75000,
    "26": 90000,
    "27": 105000,
    "28": 120000,
    "29": 135000,
    "30": 155000,
}


def get_xp_for_cr(cr: str) -> int:
    """
    Get XP value for a creature's Challenge Rating.

    Args:
        cr: Challenge Rating as string (e.g., "1/4", "5", "21")

    Returns:
        XP value for that CR
    """
    return CR_TO_XP.get(str(cr), 0)


def calculate_encounter_xp(
    cr_list: list,
    party_size: int = 4,
    divide_among_party: bool = True
) -> int:
    """
    Calculate total XP from an encounter.

    Args:
        cr_list: List of CRs of defeated creatures
        party_size: Number of party members
        divide_among_party: Whether to divide XP among party

    Returns:
        XP per character (if divided) or total XP
    """
    total_xp = sum(get_xp_for_cr(cr) for cr in cr_list)

    if divide_among_party and party_size > 0:
        return total_xp // party_size

    return total_xp


# Milestone leveling alternative
MILESTONE_LEVELS: Dict[str, int] = {
    "minor_milestone": 0,  # Story progression, no level
    "moderate_milestone": 1,  # Significant achievement, +1 level
    "major_milestone": 2,  # Campaign milestone, +2 levels (rare)
}


def calculate_milestone_level(
    current_level: int,
    milestone_type: str
) -> int:
    """
    Calculate new level from milestone leveling.

    Args:
        current_level: Current character level
        milestone_type: Type of milestone achieved

    Returns:
        New level after milestone
    """
    levels_gained = MILESTONE_LEVELS.get(milestone_type, 0)
    new_level = current_level + levels_gained
    return min(new_level, MAX_LEVEL)
