"""
Pacing Manager for Campaign Generation.

Ensures BG3-style variety in encounter sequencing:
- Never more than 2 combats in a row without relief
- Social encounters provide exposition and setup
- Comic relief breaks tension after serious beats
- Exploration rewards curiosity
- Boss fights have proper buildup
"""

from typing import List, Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass


class EncounterPacing(str, Enum):
    """Pacing role an encounter plays in the narrative."""
    TENSION_RISE = "tension_rise"      # Building toward climax
    TENSION_PEAK = "tension_peak"      # Climactic moment
    TENSION_RELEASE = "tension_release"  # After climax, wind down
    COMIC_RELIEF = "comic_relief"      # Lighten the mood
    REVELATION = "revelation"          # Plot twist/information dump
    CHARACTER_MOMENT = "character_moment"  # NPC development
    REST = "rest"                      # Mechanical rest, also narrative breather


@dataclass
class PacingTarget:
    """Target pacing for a position in a chapter."""
    position: float  # 0.0 to 1.0 through the chapter
    suggested_type: str  # encounter type
    pacing_role: EncounterPacing
    intensity: float  # 0.0 to 1.0


@dataclass
class PacingAnalysis:
    """Analysis of current chapter pacing."""
    combat_ratio: float
    social_ratio: float
    exploration_ratio: float
    consecutive_combats: int
    needs_relief: bool
    tension_curve: List[float]
    suggestions: List[str]


class PacingManager:
    """
    Manages encounter pacing for BG3-quality campaigns.

    Key principles:
    1. Variety - Mix encounter types to prevent fatigue
    2. Tension curve - Build and release tension naturally
    3. Character moments - Give NPCs time to shine
    4. Breathing room - Players need time to process big events
    5. Earned climaxes - Build anticipation before boss fights
    """

    # Target percentages for encounter types in a well-paced campaign
    ENCOUNTER_MIX = {
        "combat": 0.35,       # ~35% combat
        "social": 0.25,       # ~25% NPC interactions
        "exploration": 0.15,  # ~15% puzzles/investigation
        "choice": 0.10,       # ~10% decision points
        "rest": 0.05,         # ~5% rest encounters
        "cutscene": 0.05,     # ~5% non-interactive story
        "comic_relief": 0.05, # ~5% lighter moments
    }

    # Maximum consecutive encounters of same type before forced variety
    MAX_CONSECUTIVE = {
        "combat": 2,
        "social": 3,
        "exploration": 2,
        "choice": 2,
        "rest": 1,
        "cutscene": 1,
    }

    # Encounter types that relieve tension after combat
    RELIEF_TYPES = {"social", "exploration", "rest", "cutscene"}

    # Pacing patterns for different chapter positions
    PACING_PATTERNS = {
        "opening": [
            EncounterPacing.TENSION_RISE,
            EncounterPacing.CHARACTER_MOMENT,
        ],
        "rising_action": [
            EncounterPacing.TENSION_RISE,
            EncounterPacing.REVELATION,
            EncounterPacing.TENSION_RISE,
        ],
        "midpoint": [
            EncounterPacing.TENSION_PEAK,
            EncounterPacing.TENSION_RELEASE,
            EncounterPacing.CHARACTER_MOMENT,
        ],
        "complications": [
            EncounterPacing.TENSION_RISE,
            EncounterPacing.COMIC_RELIEF,
            EncounterPacing.TENSION_RISE,
        ],
        "climax": [
            EncounterPacing.TENSION_RISE,
            EncounterPacing.TENSION_PEAK,
            EncounterPacing.TENSION_RELEASE,
        ],
    }

    def __init__(self):
        self._recent_encounters: List[str] = []
        self._tension_level: float = 0.3  # Start at moderate tension

    def suggest_next_type(
        self,
        recent_encounters: List[str],
        chapter_position: float,
        chapter_theme: str,
        story_beat: str = None,
    ) -> Tuple[str, EncounterPacing]:
        """
        Suggest what type of encounter should come next.

        Args:
            recent_encounters: List of recent encounter types
            chapter_position: 0.0 to 1.0 through the chapter
            chapter_theme: Theme of current chapter
            story_beat: Current story beat if known

        Returns:
            Tuple of (suggested_type, pacing_role)
        """
        # Count recent combats
        recent_combats = sum(1 for e in recent_encounters[-3:] if e == "combat")

        # Force relief if too many combats
        if recent_combats >= 2:
            relief_type = self._pick_relief_type(recent_encounters)
            return (relief_type, EncounterPacing.TENSION_RELEASE)

        # Check for consecutive same-type encounters
        if recent_encounters:
            last_type = recent_encounters[-1]
            consecutive = sum(1 for e in reversed(recent_encounters) if e == last_type)
            max_allowed = self.MAX_CONSECUTIVE.get(last_type, 2)

            if consecutive >= max_allowed:
                # Force different type
                return self._suggest_different_type(last_type, chapter_position)

        # Base suggestion on chapter position
        if chapter_position < 0.2:
            # Opening - establish stakes, introduce conflict
            return self._suggest_for_opening(recent_encounters)
        elif chapter_position < 0.4:
            # Rising action - build tension
            return self._suggest_for_rising_action(recent_encounters)
        elif chapter_position < 0.6:
            # Midpoint - revelation or twist
            return self._suggest_for_midpoint(recent_encounters)
        elif chapter_position < 0.8:
            # Complications - rising stakes, character moments
            return self._suggest_for_complications(recent_encounters)
        else:
            # Climax - major confrontation
            return self._suggest_for_climax(recent_encounters)

    def analyze_pacing(
        self,
        encounters: List[Dict],
    ) -> PacingAnalysis:
        """
        Analyze current pacing and suggest improvements.

        Args:
            encounters: List of encounter dictionaries with 'type' field

        Returns:
            PacingAnalysis with metrics and suggestions
        """
        if not encounters:
            return PacingAnalysis(
                combat_ratio=0,
                social_ratio=0,
                exploration_ratio=0,
                consecutive_combats=0,
                needs_relief=False,
                tension_curve=[],
                suggestions=["Add some encounters to analyze pacing."],
            )

        types = [e.get("type", "combat") for e in encounters]
        total = len(types)

        # Calculate ratios
        combat_count = types.count("combat")
        social_count = types.count("social")
        exploration_count = types.count("exploration")

        combat_ratio = combat_count / total
        social_ratio = social_count / total
        exploration_ratio = exploration_count / total

        # Find consecutive combats
        max_consecutive = 0
        current_consecutive = 0
        for t in types:
            if t == "combat":
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        # Calculate tension curve (simplified)
        tension_curve = self._calculate_tension_curve(types)

        # Generate suggestions
        suggestions = []

        if combat_ratio > 0.5:
            suggestions.append(
                "Too combat-heavy. Add more social or exploration encounters."
            )

        if max_consecutive > 2:
            suggestions.append(
                f"Found {max_consecutive} consecutive combats. Add relief encounters."
            )

        if social_ratio < 0.15:
            suggestions.append(
                "Not enough NPC interactions. Add social encounters for character development."
            )

        if exploration_ratio < 0.1:
            suggestions.append(
                "Consider adding exploration encounters for world-building."
            )

        # Check for pacing issues
        if len(tension_curve) > 5:
            avg_tension = sum(tension_curve) / len(tension_curve)
            if avg_tension > 0.7:
                suggestions.append(
                    "Tension is consistently high. Add moments of relief."
                )
            elif avg_tension < 0.3:
                suggestions.append(
                    "Tension is too low. Add more dramatic encounters."
                )

        needs_relief = current_consecutive >= 2

        return PacingAnalysis(
            combat_ratio=combat_ratio,
            social_ratio=social_ratio,
            exploration_ratio=exploration_ratio,
            consecutive_combats=max_consecutive,
            needs_relief=needs_relief,
            tension_curve=tension_curve,
            suggestions=suggestions,
        )

    def generate_pacing_curve(
        self,
        chapter_length: int,
        climax_position: float = 0.85,
        chapter_type: str = "standard",
    ) -> List[PacingTarget]:
        """
        Generate target pacing for a chapter.

        Args:
            chapter_length: Number of encounters in chapter
            climax_position: Where the climax should fall (0.0-1.0)
            chapter_type: "standard", "action_heavy", "intrigue", "exploration"

        Returns:
            List of PacingTarget for each position
        """
        targets = []

        for i in range(chapter_length):
            position = i / max(chapter_length - 1, 1)

            # Determine intensity based on position relative to climax
            if position < climax_position:
                # Rising action - gradually increase
                intensity = 0.3 + (position / climax_position) * 0.5
            else:
                # Falling action - decrease after climax
                post_climax = (position - climax_position) / (1 - climax_position)
                intensity = 0.8 - post_climax * 0.4

            # Determine encounter type and pacing role
            suggested_type, pacing_role = self._get_target_for_position(
                position, intensity, chapter_type
            )

            targets.append(PacingTarget(
                position=position,
                suggested_type=suggested_type,
                pacing_role=pacing_role,
                intensity=intensity,
            ))

        return targets

    def get_encounter_budget(
        self,
        total_encounters: int,
        chapter_type: str = "standard",
    ) -> Dict[str, int]:
        """
        Get target count for each encounter type.

        Args:
            total_encounters: Total encounters in chapter
            chapter_type: Type of chapter for weight adjustments

        Returns:
            Dictionary of encounter type -> target count
        """
        # Adjust weights based on chapter type
        weights = dict(self.ENCOUNTER_MIX)

        if chapter_type == "action_heavy":
            weights["combat"] = 0.50
            weights["social"] = 0.15
        elif chapter_type == "intrigue":
            weights["social"] = 0.40
            weights["combat"] = 0.20
            weights["choice"] = 0.20
        elif chapter_type == "exploration":
            weights["exploration"] = 0.35
            weights["combat"] = 0.25

        # Calculate counts
        budget = {}
        remaining = total_encounters

        for enc_type, weight in sorted(weights.items(), key=lambda x: -x[1]):
            count = max(1, round(total_encounters * weight))
            count = min(count, remaining)
            budget[enc_type] = count
            remaining -= count

        # Distribute any remaining
        if remaining > 0:
            budget["combat"] = budget.get("combat", 0) + remaining

        return budget

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    def _pick_relief_type(self, recent_encounters: List[str]) -> str:
        """Pick a relief encounter type that hasn't been used recently."""
        recent_set = set(recent_encounters[-2:]) if recent_encounters else set()

        for relief_type in ["social", "exploration", "rest"]:
            if relief_type not in recent_set:
                return relief_type

        return "social"  # Default

    def _suggest_different_type(
        self,
        current_type: str,
        chapter_position: float,
    ) -> Tuple[str, EncounterPacing]:
        """Suggest a different encounter type."""
        alternatives = {
            "combat": [("social", EncounterPacing.CHARACTER_MOMENT),
                       ("exploration", EncounterPacing.REVELATION)],
            "social": [("exploration", EncounterPacing.REVELATION),
                       ("choice", EncounterPacing.TENSION_RISE)],
            "exploration": [("social", EncounterPacing.CHARACTER_MOMENT),
                           ("combat", EncounterPacing.TENSION_RISE)],
            "choice": [("combat", EncounterPacing.TENSION_PEAK),
                       ("social", EncounterPacing.TENSION_RELEASE)],
            "rest": [("social", EncounterPacing.CHARACTER_MOMENT),
                     ("exploration", EncounterPacing.REVELATION)],
        }

        options = alternatives.get(current_type, [("social", EncounterPacing.TENSION_RELEASE)])
        return options[0]

    def _suggest_for_opening(
        self,
        recent: List[str],
    ) -> Tuple[str, EncounterPacing]:
        """Suggest encounter for chapter opening."""
        if not recent or recent[-1] != "social":
            return ("social", EncounterPacing.CHARACTER_MOMENT)
        return ("exploration", EncounterPacing.TENSION_RISE)

    def _suggest_for_rising_action(
        self,
        recent: List[str],
    ) -> Tuple[str, EncounterPacing]:
        """Suggest encounter for rising action."""
        if not recent:
            return ("combat", EncounterPacing.TENSION_RISE)

        if recent[-1] == "combat":
            return ("social", EncounterPacing.REVELATION)
        return ("combat", EncounterPacing.TENSION_RISE)

    def _suggest_for_midpoint(
        self,
        recent: List[str],
    ) -> Tuple[str, EncounterPacing]:
        """Suggest encounter for chapter midpoint."""
        # Midpoint should have a revelation or twist
        if recent and recent[-1] == "combat":
            return ("choice", EncounterPacing.REVELATION)
        return ("social", EncounterPacing.REVELATION)

    def _suggest_for_complications(
        self,
        recent: List[str],
    ) -> Tuple[str, EncounterPacing]:
        """Suggest encounter for complications section."""
        recent_combats = sum(1 for e in recent[-2:] if e == "combat")

        if recent_combats >= 2:
            return ("social", EncounterPacing.COMIC_RELIEF)

        return ("combat", EncounterPacing.TENSION_RISE)

    def _suggest_for_climax(
        self,
        recent: List[str],
    ) -> Tuple[str, EncounterPacing]:
        """Suggest encounter for chapter climax."""
        if recent and recent[-1] == "combat":
            return ("cutscene", EncounterPacing.TENSION_RELEASE)
        return ("combat", EncounterPacing.TENSION_PEAK)

    def _calculate_tension_curve(self, types: List[str]) -> List[float]:
        """Calculate tension levels for a sequence of encounters."""
        tension_values = {
            "combat": 0.8,
            "social": 0.4,
            "exploration": 0.3,
            "choice": 0.6,
            "rest": 0.2,
            "cutscene": 0.5,
        }

        return [tension_values.get(t, 0.5) for t in types]

    def _get_target_for_position(
        self,
        position: float,
        intensity: float,
        chapter_type: str,
    ) -> Tuple[str, EncounterPacing]:
        """Get target encounter type for a specific position."""
        if intensity > 0.7:
            return ("combat", EncounterPacing.TENSION_PEAK)
        elif intensity > 0.5:
            if chapter_type == "intrigue":
                return ("choice", EncounterPacing.TENSION_RISE)
            return ("combat", EncounterPacing.TENSION_RISE)
        elif intensity > 0.3:
            return ("social", EncounterPacing.CHARACTER_MOMENT)
        else:
            return ("exploration", EncounterPacing.TENSION_RELEASE)
