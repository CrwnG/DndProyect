"""
Pre-written fallback narratives for when AI is unavailable.

Provides template-based narrative generation as a backup when the
Claude API is unavailable, rate limited, or disabled.
"""
from typing import Dict, Any, List, Optional
import random
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# SCENE DESCRIPTION FALLBACKS
# =============================================================================

SCENE_FALLBACKS: Dict[str, List[str]] = {
    "combat": [
        "The air grows tense as your enemies ready their weapons. Steel glints in the dim light.",
        "A hostile presence fills the chamber. Combat is inevitable.",
        "Your foes block your path, weapons raised and eyes gleaming with malice.",
        "The sound of drawn blades echoes through the space. Battle is upon you.",
        "Enemies emerge from the shadows, their intent unmistakable. Prepare for combat.",
    ],
    "rest": [
        "You find a moment of peace in this dangerous place. Rest, while you can.",
        "A quiet sanctuary offers respite from your trials. The shadows hold no threat here.",
        "Weary from your journey, you find a place to recuperate. The silence is a welcome relief.",
        "This seems like a safe place to catch your breath. Take what rest you can.",
    ],
    "choice": [
        "A decision lies before you. Each path carries its own risks and rewards.",
        "Multiple options present themselves. Choose wisely - your choice may shape what follows.",
        "The way forward is not clear. You must decide which path to take.",
        "A crossroads of fate awaits your decision. Consider your options carefully.",
    ],
    "cutscene": [
        "The story unfolds before you, revealing new truths about your journey.",
        "Events transpire that will shape the path ahead.",
        "A moment of revelation changes everything you thought you knew.",
    ],
    "social": [
        "You find yourself in a delicate social situation. Words may be more powerful than swords here.",
        "An opportunity for negotiation presents itself. Tread carefully.",
        "The success of this encounter may depend on your diplomatic skills.",
    ],
    "exploration": [
        "The unknown stretches before you, full of mystery and potential danger.",
        "Your surroundings demand careful investigation. What secrets lie hidden here?",
        "Every shadow could hide treasure or peril. Explore with caution.",
    ],
}

# Generic fallback for unknown encounter types
DEFAULT_SCENE_FALLBACK = "You steel yourself for what lies ahead. Adventure awaits."


# =============================================================================
# COMBAT NARRATION FALLBACKS
# =============================================================================

COMBAT_NARRATION: Dict[str, List[str]] = {
    "hit_kill": [
        "{actor} delivers a devastating blow to {target}, ending the fight decisively!",
        "With deadly precision, {actor} strikes true. {target} falls!",
        "{actor}'s attack finds its mark with lethal force. {target} crumples to the ground.",
        "A masterful strike from {actor} brings {target} down permanently.",
        "{target} collapses under {actor}'s relentless assault.",
    ],
    "hit_critical": [
        "{actor} lands a critical strike on {target}! The blow is devastating!",
        "A perfect hit! {actor}'s attack deals tremendous damage to {target}!",
        "{actor} finds a weak point in {target}'s defenses - critical hit!",
        "Fortune favors {actor}! The attack strikes true for maximum damage!",
    ],
    "hit": [
        "{actor} lands a solid strike on {target}.",
        "{actor}'s attack connects, drawing blood from {target}.",
        "The blow finds its mark, and {target} staggers from the impact.",
        "{actor} strikes {target} with a well-aimed attack.",
        "A hit! {actor}'s weapon bites into {target}.",
    ],
    "miss": [
        "{actor}'s attack goes wide, missing {target}.",
        "{target} narrowly avoids {actor}'s strike.",
        "The attack fails to connect as {target} dodges aside.",
        "{actor} swings but finds only air.",
        "{target}'s defenses hold against {actor}'s assault.",
    ],
    "miss_critical": [
        "{actor}'s attack goes wildly astray - a critical miss!",
        "A fumble! {actor}'s strike completely misses the mark.",
        "{actor} overextends, leaving an opening after the failed attack.",
    ],
    "healing": [
        "{actor}'s healing magic washes over {target}, mending wounds.",
        "Divine energy flows from {actor}, restoring {target}'s vitality.",
        "{target} feels renewed as {actor}'s healing takes effect.",
    ],
    "spell_damage": [
        "Arcane energy erupts from {actor}, striking {target} with magical force!",
        "{actor}'s spell crashes into {target} with devastating effect.",
        "The spell finds its target, and {target} reels from the magical assault.",
    ],
    "spell_miss": [
        "{target} resists {actor}'s spell, shaking off the magical effect.",
        "The spell fizzles harmlessly against {target}'s defenses.",
        "{actor}'s magic fails to take hold on {target}.",
    ],
}


# =============================================================================
# SKILL CHECK NARRATION FALLBACKS
# =============================================================================

SKILL_CHECK_FALLBACKS: Dict[str, Dict[str, str]] = {
    "success": {
        "athletics": "With impressive strength, {name} succeeds through sheer physical prowess.",
        "acrobatics": "{name} moves with fluid grace, executing the maneuver flawlessly.",
        "sleight_of_hand": "Quick fingers and steady nerves serve {name} well.",
        "stealth": "Moving like a shadow, {name} passes undetected.",
        "arcana": "{name}'s arcane knowledge proves invaluable.",
        "history": "Ancient lore springs to {name}'s mind at the crucial moment.",
        "investigation": "{name}'s keen eye catches what others miss.",
        "nature": "{name}'s understanding of the natural world provides insight.",
        "religion": "Divine wisdom guides {name} to the answer.",
        "animal_handling": "{name} connects with the creature, earning its trust.",
        "insight": "{name}'s keen perception pierces through the deception.",
        "medicine": "{name}'s medical knowledge proves effective.",
        "perception": "{name}'s sharp senses catch the crucial detail.",
        "survival": "{name}'s wilderness skills prove their worth.",
        "deception": "The lie slips past undetected, the target none the wiser.",
        "intimidation": "Fear flickers in their eyes as they back down before {name}.",
        "performance": "{name}'s display captivates the audience.",
        "persuasion": "{name}'s words find their mark, swaying the listener.",
        "default": "{name} succeeds with skill and determination.",
    },
    "failure": {
        "athletics": "Despite great effort, the physical challenge proves too great for {name}.",
        "acrobatics": "{name}'s balance fails at the crucial moment.",
        "sleight_of_hand": "Clumsy fingers betray {name}'s intentions.",
        "stealth": "Despite best efforts, {name} is spotted.",
        "arcana": "The arcane mysteries elude {name}'s understanding.",
        "history": "The relevant knowledge escapes {name}'s memory.",
        "investigation": "{name} fails to notice the crucial detail.",
        "nature": "Nature's secrets remain hidden from {name}.",
        "religion": "Divine wisdom does not favor {name} this time.",
        "animal_handling": "The creature remains wary of {name}'s approach.",
        "insight": "The truth remains hidden from {name}'s perception.",
        "medicine": "{name}'s medical treatment proves ineffective.",
        "perception": "{name} fails to notice what lies in plain sight.",
        "survival": "The wilderness proves more challenging than expected.",
        "deception": "Suspicion clouds their eyes - they don't believe {name}.",
        "intimidation": "They stand firm, unimpressed by {name}'s threats.",
        "performance": "The performance falls flat, failing to impress.",
        "persuasion": "{name}'s argument fails to convince the listener.",
        "default": "{name} falls short, despite their efforts.",
    },
    "critical_success": {
        "default": "Exceptional! {name} succeeds beyond all expectations with natural talent!",
    },
    "critical_failure": {
        "default": "{name}'s attempt goes terribly wrong - a catastrophic failure!",
    },
}


# =============================================================================
# NPC DIALOGUE FALLBACKS
# =============================================================================

NPC_DIALOGUE_FALLBACKS: Dict[str, List[str]] = {
    "friendly": [
        "\"Welcome, travelers. How may I assist you?\"",
        "\"Ah, adventurers! It's good to see friendly faces.\"",
        "\"Please, make yourselves comfortable. What brings you here?\"",
    ],
    "neutral": [
        "\"State your business.\"",
        "\"I don't know you, but I'll hear what you have to say.\"",
        "\"What do you want?\"",
    ],
    "hostile": [
        "\"You're not welcome here. Leave now.\"",
        "\"I have nothing to say to the likes of you.\"",
        "\"Tread carefully. My patience is thin.\"",
    ],
    "merchant": [
        "\"Browse my wares, friend. Fair prices for quality goods!\"",
        "\"Looking to buy? Or perhaps you have something to sell?\"",
        "\"Everything here is of the finest quality, I assure you.\"",
    ],
    "quest_giver": [
        "\"I have a task that requires capable adventurers. Interested?\"",
        "\"Your reputation precedes you. I have a proposition.\"",
        "\"There's work to be done, if you're willing.\"",
    ],
    "default": [
        "\"...\"",
        "\"Hmm.\"",
        "\"Is there something you need?\"",
    ],
}


# =============================================================================
# FALLBACK FUNCTIONS
# =============================================================================

def get_scene_fallback(encounter_type: str) -> str:
    """
    Get fallback scene description.

    Args:
        encounter_type: Type of encounter (combat, rest, choice, etc.)

    Returns:
        A pre-written scene description
    """
    templates = SCENE_FALLBACKS.get(encounter_type.lower(), [])
    if not templates:
        logger.debug(f"No fallback for encounter type: {encounter_type}, using default")
        return DEFAULT_SCENE_FALLBACK
    return random.choice(templates)


def get_combat_fallback(
    actor_name: str,
    target_name: str,
    hit: bool,
    is_kill: bool = False,
    is_critical: bool = False,
    is_healing: bool = False,
    is_spell: bool = False,
) -> str:
    """
    Get fallback combat narration.

    Args:
        actor_name: Name of the attacker/healer
        target_name: Name of the target
        hit: Whether the attack hit
        is_kill: Whether this was a killing blow
        is_critical: Whether this was a critical hit/miss
        is_healing: Whether this is healing
        is_spell: Whether this is a spell

    Returns:
        A formatted combat narration string
    """
    # Determine template category
    if is_healing:
        key = "healing"
    elif hit:
        if is_kill:
            key = "hit_kill"
        elif is_critical:
            key = "hit_critical"
        elif is_spell:
            key = "spell_damage"
        else:
            key = "hit"
    else:
        if is_critical:
            key = "miss_critical"
        elif is_spell:
            key = "spell_miss"
        else:
            key = "miss"

    templates = COMBAT_NARRATION.get(key, COMBAT_NARRATION["hit"])
    template = random.choice(templates)

    return template.format(actor=actor_name, target=target_name)


def get_skill_check_fallback(
    character_name: str,
    skill: str,
    success: bool,
    is_critical: bool = False,
) -> str:
    """
    Get fallback skill check narration.

    Args:
        character_name: Name of the character making the check
        skill: The skill being checked (e.g., "stealth", "persuasion")
        success: Whether the check succeeded
        is_critical: Whether this was a natural 20 or 1

    Returns:
        A formatted skill check narration string
    """
    if is_critical:
        result_type = "critical_success" if success else "critical_failure"
    else:
        result_type = "success" if success else "failure"

    templates = SKILL_CHECK_FALLBACKS[result_type]
    skill_lower = skill.lower().replace(" ", "_")

    # Get skill-specific template or default
    template = templates.get(skill_lower, templates.get("default", "{name} attempts the check."))

    return template.format(name=character_name)


def get_npc_dialogue_fallback(
    disposition: str = "neutral",
    npc_type: str = "",
) -> str:
    """
    Get fallback NPC dialogue.

    Args:
        disposition: NPC's attitude (friendly, neutral, hostile)
        npc_type: Type of NPC (merchant, quest_giver, etc.)

    Returns:
        A pre-written dialogue line
    """
    # First try NPC type-specific dialogue
    if npc_type.lower() in NPC_DIALOGUE_FALLBACKS:
        templates = NPC_DIALOGUE_FALLBACKS[npc_type.lower()]
        return random.choice(templates)

    # Fall back to disposition-based dialogue
    templates = NPC_DIALOGUE_FALLBACKS.get(disposition.lower(), NPC_DIALOGUE_FALLBACKS["default"])
    return random.choice(templates)


def get_encounter_suggestion_fallback(
    difficulty: str = "medium",
    terrain: str = "dungeon",
) -> Dict[str, Any]:
    """
    Get fallback encounter suggestion when AI is unavailable.

    Args:
        difficulty: Requested difficulty level
        terrain: Environment type

    Returns:
        Basic encounter suggestion data
    """
    suggestions = {
        "easy": {
            "name": "Minor Threat",
            "narrative_hook": "A small group of creatures blocks your path.",
            "enemies": [{"template": "goblin", "count": 2}],
        },
        "medium": {
            "name": "Standard Encounter",
            "narrative_hook": "Hostile creatures have made this place their territory.",
            "enemies": [{"template": "goblin", "count": 3}],
        },
        "hard": {
            "name": "Dangerous Foes",
            "narrative_hook": "A formidable group of enemies stands before you.",
            "enemies": [{"template": "orc", "count": 2}],
        },
        "deadly": {
            "name": "Deadly Encounter",
            "narrative_hook": "You face a truly dangerous threat.",
            "enemies": [{"template": "orc", "count": 2}, {"template": "goblin", "count": 3}],
        },
    }

    base = suggestions.get(difficulty.lower(), suggestions["medium"])

    return {
        "name": base["name"],
        "difficulty": difficulty,
        "terrain": terrain,
        "narrative_hook": base["narrative_hook"],
        "enemies": base["enemies"],
        "fallback": True,  # Indicates this is a fallback, not AI-generated
    }


def get_random_ambient_description() -> str:
    """
    Get a random ambient description for atmosphere.

    Returns:
        A short atmospheric description
    """
    descriptions = [
        "The air is thick with tension.",
        "Shadows dance at the edge of your vision.",
        "An eerie silence hangs over the area.",
        "The faint sound of dripping water echoes in the distance.",
        "A cold draft stirs the dust at your feet.",
        "The smell of old stone and damp earth fills your nostrils.",
        "Torchlight flickers, casting long shadows on the walls.",
        "Something about this place feels... wrong.",
        "You sense you are not alone.",
        "The weight of ancient history presses down upon you.",
    ]
    return random.choice(descriptions)
