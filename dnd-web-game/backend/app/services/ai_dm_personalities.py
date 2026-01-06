"""
DM personality customization for narrative style.

Allows configuration of the AI DM's tone, verbosity, and style
to match different campaign moods and player preferences.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class DMTone(str, Enum):
    """Narrative tone presets."""
    DRAMATIC = "dramatic"      # Epic, high-stakes narration
    CASUAL = "casual"          # Lighthearted, conversational
    GRITTY = "gritty"          # Dark, realistic, harsh
    WHIMSICAL = "whimsical"    # Fairy-tale, fantastical
    NEUTRAL = "neutral"        # Balanced, standard D&D


class DMVerbosity(str, Enum):
    """How much detail in descriptions."""
    TERSE = "terse"            # 1-2 sentences, minimal
    STANDARD = "standard"       # 2-4 sentences, balanced
    VERBOSE = "verbose"         # 4-6 sentences, rich detail


@dataclass
class DMPersonality:
    """
    Complete DM personality configuration.

    Controls how the AI DM generates narrative text, including
    tone, length, and various stylistic preferences.
    """
    tone: DMTone = DMTone.NEUTRAL
    verbosity: DMVerbosity = DMVerbosity.STANDARD
    humor_level: float = 0.3        # 0-1, affects comedic moments
    gore_level: float = 0.3         # 0-1, affects combat descriptions
    formality: float = 0.5          # 0-1, formal vs casual language
    dramatic_flair: float = 0.5     # 0-1, use of dramatic language
    mystery_emphasis: float = 0.3   # 0-1, emphasis on mystery/suspense

    # Custom style hints (free-form text)
    custom_style_hints: str = ""

    # Name/description for this personality (for presets)
    name: str = "Custom"
    description: str = ""

    def to_system_prompt_addendum(self) -> str:
        """
        Generate system prompt additions for this personality.

        Returns a string to be appended to the base AI DM system prompt
        that modifies the narrative style.

        Returns:
            System prompt addendum text
        """
        parts: List[str] = []

        # Tone instructions
        tone_prompts = {
            DMTone.DRAMATIC: (
                "Use dramatic, epic language. Build tension and raise stakes. "
                "Emphasize heroic moments and the gravity of situations."
            ),
            DMTone.CASUAL: (
                "Keep things lighthearted and conversational. Don't take things "
                "too seriously. Allow for moments of levity and humor."
            ),
            DMTone.GRITTY: (
                "Be realistic and harsh. The world is dangerous and unforgiving. "
                "Actions have consequences. Don't shy from the darker aspects."
            ),
            DMTone.WHIMSICAL: (
                "Embrace the fantastical and magical. Wonder is around every corner. "
                "Describe magic as truly wondrous and creatures as colorful."
            ),
            DMTone.NEUTRAL: (
                "Balance drama with lightness. Use standard high-fantasy tone "
                "appropriate for classic D&D adventures."
            ),
        }
        parts.append(tone_prompts.get(self.tone, tone_prompts[DMTone.NEUTRAL]))

        # Verbosity instructions
        verbosity_prompts = {
            DMVerbosity.TERSE: (
                "Keep descriptions brief and punchy - 1-2 sentences maximum. "
                "Focus on the essential details only. Be concise."
            ),
            DMVerbosity.STANDARD: (
                "Use 2-4 sentences for descriptions. Balance detail with pacing."
            ),
            DMVerbosity.VERBOSE: (
                "Provide rich, detailed descriptions of 4-6 sentences. "
                "Paint vivid pictures with sensory details."
            ),
        }
        parts.append(verbosity_prompts.get(self.verbosity, verbosity_prompts[DMVerbosity.STANDARD]))

        # Humor level
        if self.humor_level < 0.2:
            parts.append("Maintain a serious tone. Avoid jokes and comedic moments.")
        elif self.humor_level > 0.7:
            parts.append("Include witty observations and occasional humor where appropriate.")

        # Gore level
        if self.gore_level < 0.2:
            parts.append(
                "Avoid graphic violence. Keep combat descriptions family-friendly "
                "and focus on action rather than injury details."
            )
        elif self.gore_level > 0.7:
            parts.append(
                "Don't shy from visceral combat descriptions when appropriate. "
                "Describe the reality of battle without excessive gratuitousness."
            )

        # Formality
        if self.formality < 0.3:
            parts.append("Use casual, conversational language. Avoid formal speech patterns.")
        elif self.formality > 0.7:
            parts.append("Employ more formal, eloquent language befitting high fantasy.")

        # Dramatic flair
        if self.dramatic_flair > 0.7:
            parts.append("Use dramatic pauses, foreshadowing, and theatrical descriptions.")

        # Mystery emphasis
        if self.mystery_emphasis > 0.7:
            parts.append(
                "Emphasize mystery and suspense. Leave some things unexplained. "
                "Create an atmosphere of secrets and hidden truths."
            )

        # Custom hints
        if self.custom_style_hints:
            parts.append(f"Additional style guidance: {self.custom_style_hints}")

        return "\n\n".join(filter(None, parts))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "tone": self.tone.value,
            "verbosity": self.verbosity.value,
            "humor_level": self.humor_level,
            "gore_level": self.gore_level,
            "formality": self.formality,
            "dramatic_flair": self.dramatic_flair,
            "mystery_emphasis": self.mystery_emphasis,
            "custom_style_hints": self.custom_style_hints,
            "name": self.name,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DMPersonality":
        """Deserialize from dictionary."""
        return cls(
            tone=DMTone(data.get("tone", "neutral")),
            verbosity=DMVerbosity(data.get("verbosity", "standard")),
            humor_level=float(data.get("humor_level", 0.3)),
            gore_level=float(data.get("gore_level", 0.3)),
            formality=float(data.get("formality", 0.5)),
            dramatic_flair=float(data.get("dramatic_flair", 0.5)),
            mystery_emphasis=float(data.get("mystery_emphasis", 0.3)),
            custom_style_hints=data.get("custom_style_hints", ""),
            name=data.get("name", "Custom"),
            description=data.get("description", ""),
        )

    def get_max_tokens(self, base_tokens: int = 300) -> int:
        """
        Get adjusted max tokens based on verbosity.

        Args:
            base_tokens: The base token limit

        Returns:
            Adjusted token limit
        """
        multipliers = {
            DMVerbosity.TERSE: 0.5,
            DMVerbosity.STANDARD: 1.0,
            DMVerbosity.VERBOSE: 1.5,
        }
        multiplier = multipliers.get(self.verbosity, 1.0)
        return int(base_tokens * multiplier)


# =============================================================================
# PRESET PERSONALITIES
# =============================================================================

PERSONALITY_PRESETS: Dict[str, DMPersonality] = {
    "classic": DMPersonality(
        tone=DMTone.NEUTRAL,
        verbosity=DMVerbosity.STANDARD,
        humor_level=0.3,
        gore_level=0.3,
        formality=0.5,
        dramatic_flair=0.5,
        mystery_emphasis=0.3,
        name="Classic",
        description="Balanced, traditional D&D narration style.",
    ),

    "epic": DMPersonality(
        tone=DMTone.DRAMATIC,
        verbosity=DMVerbosity.VERBOSE,
        humor_level=0.2,
        gore_level=0.5,
        formality=0.7,
        dramatic_flair=0.9,
        mystery_emphasis=0.4,
        name="Epic",
        description="Grand, heroic narration for legendary adventures.",
    ),

    "horror": DMPersonality(
        tone=DMTone.GRITTY,
        verbosity=DMVerbosity.VERBOSE,
        humor_level=0.1,
        gore_level=0.8,
        formality=0.6,
        dramatic_flair=0.7,
        mystery_emphasis=0.9,
        name="Horror",
        description="Dark, suspenseful tone for horror campaigns.",
    ),

    "comedy": DMPersonality(
        tone=DMTone.CASUAL,
        verbosity=DMVerbosity.STANDARD,
        humor_level=0.9,
        gore_level=0.1,
        formality=0.2,
        dramatic_flair=0.3,
        mystery_emphasis=0.1,
        name="Comedy",
        description="Lighthearted, humorous adventures.",
    ),

    "fairy_tale": DMPersonality(
        tone=DMTone.WHIMSICAL,
        verbosity=DMVerbosity.VERBOSE,
        humor_level=0.5,
        gore_level=0.1,
        formality=0.6,
        dramatic_flair=0.6,
        mystery_emphasis=0.5,
        name="Fairy Tale",
        description="Magical, wonder-filled storytelling.",
    ),

    "noir": DMPersonality(
        tone=DMTone.GRITTY,
        verbosity=DMVerbosity.STANDARD,
        humor_level=0.3,
        gore_level=0.4,
        formality=0.4,
        dramatic_flair=0.6,
        mystery_emphasis=0.8,
        custom_style_hints="Use noir-style narration with cynical observations and atmospheric descriptions.",
        name="Noir",
        description="Hardboiled detective-style narration.",
    ),

    "quick": DMPersonality(
        tone=DMTone.NEUTRAL,
        verbosity=DMVerbosity.TERSE,
        humor_level=0.2,
        gore_level=0.3,
        formality=0.4,
        dramatic_flair=0.2,
        mystery_emphasis=0.2,
        name="Quick",
        description="Minimal narration for fast-paced play.",
    ),

    "immersive": DMPersonality(
        tone=DMTone.DRAMATIC,
        verbosity=DMVerbosity.VERBOSE,
        humor_level=0.2,
        gore_level=0.4,
        formality=0.6,
        dramatic_flair=0.7,
        mystery_emphasis=0.6,
        custom_style_hints="Focus on sensory details - sounds, smells, textures. Help players feel present in the world.",
        name="Immersive",
        description="Rich, detailed narration for deep immersion.",
    ),
}


def get_preset(preset_name: str) -> Optional[DMPersonality]:
    """
    Get a preset personality by name.

    Args:
        preset_name: Name of the preset

    Returns:
        DMPersonality if found, None otherwise
    """
    return PERSONALITY_PRESETS.get(preset_name.lower())


def list_presets() -> List[Dict[str, str]]:
    """
    Get list of available presets.

    Returns:
        List of preset info dictionaries
    """
    return [
        {
            "id": preset_id,
            "name": preset.name,
            "description": preset.description,
        }
        for preset_id, preset in PERSONALITY_PRESETS.items()
    ]


def create_custom_personality(
    base_preset: Optional[str] = None,
    **overrides,
) -> DMPersonality:
    """
    Create a custom personality, optionally based on a preset.

    Args:
        base_preset: Optional preset to base on
        **overrides: Fields to override

    Returns:
        New DMPersonality instance
    """
    if base_preset:
        base = PERSONALITY_PRESETS.get(base_preset.lower())
        if base:
            # Start with preset values
            data = base.to_dict()
            data.update(overrides)
            data["name"] = overrides.get("name", f"Custom ({base.name})")
            data["description"] = overrides.get("description", f"Customized from {base.name}")
            return DMPersonality.from_dict(data)

    # Create from scratch with overrides
    return DMPersonality(**overrides)
