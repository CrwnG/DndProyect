"""AI prompts for campaign generation."""

from .campaign_prompts import (
    CAMPAIGN_STRUCTURE_PROMPT,
    CHAPTER_GENERATION_PROMPT,
    ENCOUNTER_GENERATION_PROMPT,
    NPC_GENERATION_PROMPT,
    DIALOGUE_TREE_PROMPT,
    CONSEQUENCE_CHAIN_PROMPT,
    build_campaign_prompt,
    build_chapter_prompt,
    build_encounter_prompt,
    build_npc_prompt,
)

__all__ = [
    "CAMPAIGN_STRUCTURE_PROMPT",
    "CHAPTER_GENERATION_PROMPT",
    "ENCOUNTER_GENERATION_PROMPT",
    "NPC_GENERATION_PROMPT",
    "DIALOGUE_TREE_PROMPT",
    "CONSEQUENCE_CHAIN_PROMPT",
    "build_campaign_prompt",
    "build_chapter_prompt",
    "build_encounter_prompt",
    "build_npc_prompt",
]
