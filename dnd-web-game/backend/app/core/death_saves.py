"""
Death Saving Throws System for D&D 5e 2024

Implements the death saving throw mechanics:
- DC 10 Constitution saving throw at start of turn when at 0 HP
- Natural 20: Regain 1 HP and consciousness
- Natural 1: Counts as 2 failures
- 3 successes: Stabilize (unconscious but no longer dying)
- 3 failures: Death

Also handles:
- Taking damage while at 0 HP (auto-failure, crit = 2 failures)
- Stabilization via Spare the Dying, Medicine check, or healing
- Regaining consciousness when healed
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
from enum import Enum
import random


class DeathSaveOutcome(str, Enum):
    """Possible outcomes of a death save."""
    CONTINUE = "continue"  # Still dying, need more saves
    STABILIZED = "stabilized"  # 3 successes, unconscious but stable
    REVIVED = "revived"  # Natural 20, regain 1 HP
    DEAD = "dead"  # 3 failures, character dies


@dataclass
class DeathSaveState:
    """
    Tracks death saving throws for a character at 0 HP.
    """
    successes: int = 0
    failures: int = 0
    is_stable: bool = False
    is_dead: bool = False

    def reset(self):
        """Reset death save tracking (e.g., when healed)."""
        self.successes = 0
        self.failures = 0
        self.is_stable = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "successes": self.successes,
            "failures": self.failures,
            "is_stable": self.is_stable,
            "is_dead": self.is_dead,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DeathSaveState":
        return cls(
            successes=data.get("successes", 0),
            failures=data.get("failures", 0),
            is_stable=data.get("is_stable", False),
            is_dead=data.get("is_dead", False),
        )


@dataclass
class DeathSaveResult:
    """Result of a single death saving throw."""
    roll: int  # The d20 roll
    modified_roll: int  # Roll + any modifiers
    modifier: int  # Save bonus applied
    dc: int  # DC (always 10)
    success: bool  # Did the save succeed?
    critical_success: bool  # Natural 20
    critical_failure: bool  # Natural 1
    total_successes: int  # After this save
    total_failures: int  # After this save
    outcome: DeathSaveOutcome
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "roll": self.roll,
            "modified_roll": self.modified_roll,
            "modifier": self.modifier,
            "dc": self.dc,
            "success": self.success,
            "critical_success": self.critical_success,
            "critical_failure": self.critical_failure,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "outcome": self.outcome.value,
            "description": self.description,
        }


def roll_d20() -> int:
    """Roll a d20."""
    return random.randint(1, 20)


def roll_death_save(
    state: DeathSaveState,
    modifier: int = 0,
    advantage: bool = False,
    disadvantage: bool = False
) -> DeathSaveResult:
    """
    Make a death saving throw.

    D&D 5e Rules:
    - DC is 10
    - Natural 20: Immediately regain 1 HP and consciousness
    - Natural 1: Counts as 2 failures
    - 3 successes: Stable (unconscious but no longer dying)
    - 3 failures: Dead

    Args:
        state: Current death save state (will be modified)
        modifier: Bonus to the roll (rare, but some features grant this)
        advantage: Roll twice, take higher
        disadvantage: Roll twice, take lower

    Returns:
        DeathSaveResult with the outcome
    """
    DC = 10

    # Roll the die
    roll1 = roll_d20()
    roll2 = roll_d20() if advantage or disadvantage else roll1

    if advantage:
        roll = max(roll1, roll2)
    elif disadvantage:
        roll = min(roll1, roll2)
    else:
        roll = roll1

    modified_roll = roll + modifier

    # Check for critical success/failure (based on natural roll)
    critical_success = roll == 20
    critical_failure = roll == 1

    # Determine success
    if critical_success:
        # Natural 20: Regain 1 HP immediately
        state.reset()
        return DeathSaveResult(
            roll=roll,
            modified_roll=modified_roll,
            modifier=modifier,
            dc=DC,
            success=True,
            critical_success=True,
            critical_failure=False,
            total_successes=state.successes,
            total_failures=state.failures,
            outcome=DeathSaveOutcome.REVIVED,
            description=f"Natural 20! {_get_revive_message()}"
        )

    if critical_failure:
        # Natural 1: 2 failures
        state.failures += 2
        outcome = DeathSaveOutcome.DEAD if state.failures >= 3 else DeathSaveOutcome.CONTINUE

        if outcome == DeathSaveOutcome.DEAD:
            state.is_dead = True

        return DeathSaveResult(
            roll=roll,
            modified_roll=modified_roll,
            modifier=modifier,
            dc=DC,
            success=False,
            critical_success=False,
            critical_failure=True,
            total_successes=state.successes,
            total_failures=state.failures,
            outcome=outcome,
            description=f"Natural 1! Two death save failures ({state.failures}/3)"
            + (" - Character has died!" if outcome == DeathSaveOutcome.DEAD else "")
        )

    # Normal roll
    success = modified_roll >= DC

    if success:
        state.successes += 1
        if state.successes >= 3:
            state.is_stable = True
            outcome = DeathSaveOutcome.STABILIZED
            description = f"Success! ({state.successes}/3) - Character is now stable"
        else:
            outcome = DeathSaveOutcome.CONTINUE
            description = f"Success! ({state.successes}/3 successes, {state.failures}/3 failures)"
    else:
        state.failures += 1
        if state.failures >= 3:
            state.is_dead = True
            outcome = DeathSaveOutcome.DEAD
            description = f"Failure! ({state.failures}/3) - Character has died!"
        else:
            outcome = DeathSaveOutcome.CONTINUE
            description = f"Failure! ({state.successes}/3 successes, {state.failures}/3 failures)"

    return DeathSaveResult(
        roll=roll,
        modified_roll=modified_roll,
        modifier=modifier,
        dc=DC,
        success=success,
        critical_success=False,
        critical_failure=False,
        total_successes=state.successes,
        total_failures=state.failures,
        outcome=outcome,
        description=description,
    )


def _get_revive_message() -> str:
    """Get a flavor message for reviving on natural 20."""
    messages = [
        "Eyes snap open as life surges back!",
        "A gasp for air - consciousness returns!",
        "Refusing to die, they claw their way back!",
        "By sheer force of will, they return!",
        "Death's grip loosens as they awaken!",
    ]
    return random.choice(messages)


def take_damage_while_dying(
    state: DeathSaveState,
    damage: int,
    was_critical: bool = False
) -> Dict[str, Any]:
    """
    Handle taking damage while at 0 HP.

    D&D 5e Rules:
    - Any damage causes an automatic death save failure
    - Critical hit causes 2 failures
    - Massive damage (equal to max HP) causes instant death (handled elsewhere)

    Args:
        state: Current death save state
        damage: Damage amount (used for logging)
        was_critical: Whether the hit was a critical

    Returns:
        Dict with result information
    """
    failures_added = 2 if was_critical else 1
    state.failures += failures_added

    result = {
        "damage_taken": damage,
        "failures_added": failures_added,
        "was_critical": was_critical,
        "total_failures": state.failures,
        "died": False,
    }

    if state.failures >= 3:
        state.is_dead = True
        result["died"] = True
        result["description"] = "The blow proves fatal. Character has died."
    else:
        result["description"] = (
            f"Taking damage while dying! "
            f"{'Critical hit - 2 failures!' if was_critical else '1 failure.'} "
            f"({state.failures}/3 failures)"
        )

    return result


@dataclass
class StabilizationResult:
    """Result of an attempt to stabilize a dying creature."""
    success: bool
    method: str
    roll: Optional[int] = None
    dc: Optional[int] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "method": self.method,
            "roll": self.roll,
            "dc": self.dc,
            "description": self.description,
        }


def attempt_medicine_check(
    wisdom_modifier: int,
    proficiency_bonus: int = 0,
    is_proficient: bool = False,
    has_advantage: bool = False,
    has_disadvantage: bool = False
) -> Tuple[bool, int, int]:
    """
    Attempt a Wisdom (Medicine) check to stabilize a dying creature.

    Args:
        wisdom_modifier: Helper's Wisdom modifier
        proficiency_bonus: Helper's proficiency bonus
        is_proficient: Whether helper is proficient in Medicine
        has_advantage: Roll with advantage
        has_disadvantage: Roll with disadvantage

    Returns:
        Tuple of (success, roll, total)
    """
    DC = 10

    roll1 = roll_d20()
    roll2 = roll_d20() if has_advantage or has_disadvantage else roll1

    if has_advantage:
        roll = max(roll1, roll2)
    elif has_disadvantage:
        roll = min(roll1, roll2)
    else:
        roll = roll1

    bonus = wisdom_modifier
    if is_proficient:
        bonus += proficiency_bonus

    total = roll + bonus
    success = total >= DC

    return success, roll, total


def stabilize_creature(
    state: DeathSaveState,
    method: str = "medicine",
    medicine_check_result: Optional[Tuple[bool, int, int]] = None
) -> StabilizationResult:
    """
    Attempt to stabilize a dying creature.

    Methods:
    - "medicine": DC 10 Wisdom (Medicine) check
    - "spare_the_dying": Automatic (cantrip)
    - "healing": Any HP restoration (handled elsewhere)
    - "healer_kit": Automatic with Healer's Kit

    Args:
        state: Death save state to modify
        method: Stabilization method
        medicine_check_result: For medicine, tuple of (success, roll, total)

    Returns:
        StabilizationResult with outcome
    """
    if state.is_dead:
        return StabilizationResult(
            success=False,
            method=method,
            description="Cannot stabilize - creature is already dead"
        )

    if state.is_stable:
        return StabilizationResult(
            success=True,
            method=method,
            description="Creature is already stable"
        )

    if method == "spare_the_dying":
        state.is_stable = True
        state.successes = 0
        state.failures = 0
        return StabilizationResult(
            success=True,
            method=method,
            description="Spare the Dying cantrip stabilizes the creature"
        )

    if method == "healer_kit":
        state.is_stable = True
        state.successes = 0
        state.failures = 0
        return StabilizationResult(
            success=True,
            method=method,
            description="Healer's Kit stabilizes the creature"
        )

    if method == "medicine":
        if medicine_check_result is None:
            return StabilizationResult(
                success=False,
                method=method,
                description="Medicine check required but not provided"
            )

        success, roll, total = medicine_check_result

        if success:
            state.is_stable = True
            state.successes = 0
            state.failures = 0
            return StabilizationResult(
                success=True,
                method=method,
                roll=roll,
                dc=10,
                description=f"Medicine check succeeded ({total} vs DC 10)! Creature is stable"
            )
        else:
            return StabilizationResult(
                success=False,
                method=method,
                roll=roll,
                dc=10,
                description=f"Medicine check failed ({total} vs DC 10). Creature is still dying"
            )

    return StabilizationResult(
        success=False,
        method=method,
        description=f"Unknown stabilization method: {method}"
    )


def heal_dying_creature(state: DeathSaveState, hp_healed: int) -> Dict[str, Any]:
    """
    Handle healing a creature at 0 HP.

    Any healing brings the creature back to consciousness.

    Args:
        state: Death save state to modify
        hp_healed: Amount of HP healed

    Returns:
        Dict with result information
    """
    if state.is_dead:
        return {
            "success": False,
            "regained_consciousness": False,
            "description": "Cannot heal - creature is dead (requires resurrection magic)"
        }

    # Reset death saves
    state.reset()

    return {
        "success": True,
        "regained_consciousness": True,
        "hp_healed": hp_healed,
        "description": f"Healed for {hp_healed} HP! Creature regains consciousness"
    }


def get_death_save_status(state: DeathSaveState) -> Dict[str, Any]:
    """
    Get a formatted status of death saves for display.

    Args:
        state: Current death save state

    Returns:
        Dict with status information
    """
    if state.is_dead:
        status = "dead"
        description = "Character has died"
    elif state.is_stable:
        status = "stable"
        description = "Unconscious but stable"
    elif state.successes == 0 and state.failures == 0:
        status = "dying"
        description = "Dying - no death saves yet"
    else:
        status = "dying"
        description = f"Dying - {state.successes} successes, {state.failures} failures"

    return {
        "status": status,
        "successes": state.successes,
        "failures": state.failures,
        "is_stable": state.is_stable,
        "is_dead": state.is_dead,
        "description": description,
        "success_markers": "●" * state.successes + "○" * (3 - state.successes),
        "failure_markers": "●" * state.failures + "○" * (3 - state.failures),
    }
