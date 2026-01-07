"""
AI Prompt Templates for BG3-Quality Campaign Generation.

These prompts are designed to generate campaigns with:
- Multi-layered plots with meaningful choices
- Memorable NPCs with distinct personalities
- Varied encounter types with proper pacing
- Consequences that ripple through the story
- Mix of serious drama and comic relief
"""

from typing import Dict, Any, List, Optional


# =============================================================================
# CAMPAIGN STRUCTURE PROMPT
# =============================================================================

CAMPAIGN_STRUCTURE_PROMPT = """You are designing a D&D 5e campaign with the quality and depth of Baldur's Gate 3.

CONCEPT: {concept}

PARAMETERS:
- Party Level Range: {level_start} to {level_end}
- Campaign Length: {length} ({length_description})
- Tone: {tone}

Create a campaign structure following these BG3 principles:

1. THREE-ACT STRUCTURE with escalating stakes
   - Act 1: Setup, introduce conflict, gather allies (25% of campaign)
   - Act 2: Rising action, complications, revelations, darkest moment (50% of campaign)
   - Act 3: Climax, confrontation, resolution (25% of campaign)

2. COMPANION DYNAMICS - NPCs with distinct personalities who can:
   - Join the party as allies
   - Betray based on choices
   - Have their own arcs and secrets

3. MEANINGFUL CHOICES - Decisions that genuinely alter the story:
   - Faction allegiances
   - Moral dilemmas with no "right" answer
   - Consequences that manifest chapters later

4. TONAL VARIETY - Mix serious drama with:
   - Comic relief characters/moments
   - Tender character interactions
   - Moments of triumph and despair

5. MULTIPLE SOLUTIONS - Every major obstacle should have:
   - Combat approach
   - Stealth/cunning approach
   - Diplomacy/persuasion approach
   - Creative/unusual approach

6. ENVIRONMENTAL STORYTELLING - Locations that tell stories through:
   - Found notes and journals
   - Environmental details
   - Optional exploration rewards

Output a complete campaign structure as JSON with this exact format:
{{
  "title": "Campaign Title",
  "hook": "One-sentence compelling premise that makes players want to play",
  "central_conflict": "The core dramatic tension driving the story",
  "tone": "{tone}",
  "themes": ["theme1", "theme2", "theme3"],
  "acts": [
    {{
      "id": "act-1",
      "name": "Act 1: [Evocative Title]",
      "theme": "mystery|revelation|confrontation|exploration|despair|triumph|intrigue",
      "description": "2-3 sentence summary of this act",
      "emotional_arc": "Starting emotion -> midpoint -> ending emotion",
      "key_revelations": ["What players learn in this act"],
      "chapters": ["chapter-1-1", "chapter-1-2"]
    }}
  ],
  "chapters": [
    {{
      "id": "chapter-1-1",
      "title": "Chapter Title",
      "description": "What happens in this chapter",
      "encounter_count": 3
    }}
  ],
  "major_npcs": [
    {{
      "name": "NPC Name",
      "role": "companion|villain|quest_giver|ally",
      "personality_traits": ["trait1", "trait2", "trait3"],
      "motivation": "What drives them",
      "secret": "Hidden truth about them",
      "arc": "How they can change through the story",
      "humor_style": "dry|witty|dark|earnest|none"
    }}
  ],
  "branching_points": [
    {{
      "act": "act-1",
      "description": "Major decision point",
      "options": ["choice1", "choice2"],
      "consequences": {{
        "choice1": "What happens if players choose this",
        "choice2": "What happens if players choose this"
      }}
    }}
  ],
  "estimated_encounters": {{
    "combat": {combat_count},
    "social": {social_count},
    "exploration": {exploration_count},
    "choice": {choice_count},
    "rest": {rest_count}
  }}
}}"""


# =============================================================================
# CHAPTER GENERATION PROMPT
# =============================================================================

CHAPTER_GENERATION_PROMPT = """Generate detailed encounters for a D&D 5e campaign chapter.

CAMPAIGN CONTEXT:
- Campaign: {campaign_name}
- Central Conflict: {central_conflict}
- Current Act: {act_name} (Theme: {act_theme})
- Act Emotional Arc: {emotional_arc}

CHAPTER INFO:
- Chapter: {chapter_title}
- Description: {chapter_description}
- Position in Act: {position_in_act} (beginning/middle/end)

PARTY CONTEXT:
- Party Level: {party_level}
- Party Size: {party_size}
- Previous Chapter Summary: {previous_summary}

PACING REQUIREMENTS:
- Target encounter types: {encounter_targets}
- Pacing curve: {pacing_curve}
- Must include at least one: {required_types}

Generate {encounter_count} encounters that:
1. Progress the story naturally
2. Vary in type (combat, social, exploration, choice)
3. Include meaningful player choices
4. Reference previous events when appropriate
5. Build toward the chapter's climax

Output JSON array of encounters:
[
  {{
    "id": "enc-{chapter_id}-1",
    "type": "combat|social|exploration|choice|rest|cutscene",
    "name": "Encounter Name",
    "story": {{
      "intro_text": "Narrative description setting the scene (3-5 sentences)",
      "intro_prompts": ["AI hint for generating variations"],
      "outcome_victory": "What happens on success",
      "outcome_defeat": "What happens on failure"
    }},
    "combat": {{
      "enemies": [
        {{"template": "enemy_type", "count": 2}}
      ],
      "environment": {{
        "description": "Battlefield description",
        "features": ["cover positions", "hazards", "interactive elements"]
      }},
      "ai_tactics": "aggressive|defensive|mixed",
      "non_combat_resolution": "How players could avoid/end fight diplomatically"
    }},
    "choices": {{
      "choices": [
        {{
          "id": "choice-1",
          "text": "What player sees",
          "skill_check": {{"skill": "persuasion", "dc": 15}},
          "success_text": "Narrative on success",
          "failure_text": "Narrative on failure",
          "consequences": {{
            "immediate": ["flag:saved_prisoner"],
            "delayed": [
              {{
                "trigger": {{"type": "encounter", "id": "enc-x"}},
                "effect": "npc_disposition_change",
                "narrative": "Text shown when consequence triggers"
              }}
            ]
          }}
        }}
      ]
    }},
    "rewards": {{
      "xp": 100,
      "gold": 50,
      "items": ["item_id"],
      "story_flags": ["flag_name"]
    }},
    "transitions": {{
      "on_victory": "next-encounter-id",
      "on_defeat": "defeat-encounter-id",
      "on_flee": "flee-encounter-id"
    }},
    "pacing_notes": "Why this encounter is placed here"
  }}
]"""


# =============================================================================
# ENCOUNTER GENERATION PROMPT
# =============================================================================

ENCOUNTER_GENERATION_PROMPT = """Generate a single {encounter_type} encounter for a D&D 5e campaign.

CAMPAIGN CONTEXT:
- Campaign: {campaign_name}
- Current Act: {act_name} (Theme: {act_theme})
- Current Chapter: {chapter_name}
- Story So Far: {story_summary}

PARTY CONTEXT:
- Party Level: {party_level}
- Party Composition: {party_composition}
- Recent Events: {recent_events}
- Active Story Flags: {active_flags}

ENCOUNTER REQUIREMENTS:
- Type: {encounter_type}
- Desired Pacing: {pacing} (tension_rise|comic_relief|revelation|action|rest)
- Difficulty: {difficulty}
- Must Reference: {callbacks} previous choices/events

FOR COMBAT ENCOUNTERS, include:
- Enemy motivation (why are they fighting?)
- Environmental features for tactical play (cover, hazards, interactive objects)
- At least one non-combat resolution option
- Interesting terrain that affects tactics

FOR SOCIAL ENCOUNTERS, include:
- NPC with distinct personality and speech patterns
- Information the NPC can provide
- What the NPC wants from players
- Hidden agenda or secret (if any)
- Multiple dialogue paths based on approach

FOR EXPLORATION ENCOUNTERS, include:
- Environmental puzzles or investigation
- Skill check opportunities
- Optional secrets to discover
- Lore/world-building elements

FOR CHOICE ENCOUNTERS, include:
- Moral dilemma with no clear "right" answer
- Multiple valid approaches
- Consequences for each choice
- Stakes that matter to the characters

Output a single encounter as JSON matching the Encounter schema."""


# =============================================================================
# NPC GENERATION PROMPT
# =============================================================================

NPC_GENERATION_PROMPT = """Generate a memorable D&D NPC with Baldur's Gate 3-quality depth.

CAMPAIGN CONTEXT:
- Campaign: {campaign_name}
- Setting/Tone: {tone}
- Current Story Point: {story_context}

NPC REQUIREMENTS:
- Role: {role} (companion/villain/quest_giver/merchant/ally/informant)
- Importance: {importance} (major/supporting/minor)
- First Appearance: {first_appearance}

Create an NPC following BG3 companion quality principles:

1. PERSONALITY (3 distinct traits that create interesting combinations)
   Examples from BG3:
   - Astarion: "vain + cunning + secretly vulnerable"
   - Shadowheart: "secretive + pragmatic + deeply loyal when trusted"
   - Gale: "scholarly + romantic + self-deprecating"

2. VOICE (How they speak - crucial for memorable characters)
   - Speech patterns (formal, casual, archaic, crude)
   - Verbal tics or catchphrases
   - Topics they gravitate toward
   - Sense of humor style

3. MOTIVATION (What drives them - layered)
   - Surface goal (what they claim to want)
   - True goal (what they actually need)
   - Fear (what they're running from)

4. SECRET (Something players can discover)
   - Hidden truth about their past
   - How discovering it changes the dynamic
   - When/how it should be revealed

5. ARC POTENTIAL (How they can grow)
   - Starting state (flaw or limitation)
   - What help/events could change them
   - Possible ending states (growth or tragedy)

6. RELATIONSHIP DYNAMICS
   - What actions increase their approval
   - What actions decrease their approval
   - Unique reactions to specific situations

Output NPC as JSON:
{{
  "id": "{npc_id}",
  "name": "Full Name",
  "role": "{role}",
  "description": "Physical appearance in 2-3 sentences",
  "appearance": "Key visual details",
  "voice_description": "How to write/voice this character",
  "personality": {{
    "traits": ["trait1", "trait2", "trait3"],
    "quirks": ["behavioral quirk 1", "quirk 2"],
    "surface_motivation": "What they say they want",
    "true_motivation": "What they actually need",
    "fear": "Their deepest fear",
    "secret": "Hidden truth about them",
    "tragic_flaw": "Character weakness",
    "humor_style": "dry|witty|dark|slapstick|earnest|none",
    "speech_pattern": "formal|casual|archaic|crude|scholarly|cryptic",
    "catchphrase": "Signature line (optional)",
    "likes": ["action types that increase approval"],
    "dislikes": ["action types that decrease approval"]
  }},
  "base_disposition": 0,
  "romance_available": false,
  "arc": {{
    "starting_state": "Where they begin emotionally/morally",
    "growth_triggers": ["events that could change them"],
    "ending_state": "Where they could end up"
  }},
  "bark_lines": {{
    "combat_start": ["Line 1", "Line 2"],
    "low_health": ["Line 1", "Line 2"],
    "victory": ["Line 1", "Line 2"],
    "rest": ["Line 1", "Line 2"],
    "exploration": ["Line 1", "Line 2"],
    "approval_high": ["Line when friendly"],
    "approval_low": ["Line when unfriendly"]
  }},
  "combat_disposition": "fights_alongside|flees|neutral|hostile",
  "available_encounters": ["encounter-ids where they appear"]
}}"""


# =============================================================================
# DIALOGUE TREE PROMPT
# =============================================================================

DIALOGUE_TREE_PROMPT = """Generate a branching dialogue tree for an NPC conversation.

NPC: {npc_name}
PERSONALITY: {personality_summary}
SPEECH PATTERN: {speech_pattern}
CURRENT DISPOSITION: {disposition} ({disposition_tier})

CONVERSATION CONTEXT:
- Encounter: {encounter_name}
- Topic: {topic}
- What NPC Knows: {npc_knowledge}
- What NPC Wants: {npc_wants}
- Player's Goal: {player_goal}

STORY FLAGS AVAILABLE:
{available_flags}

Generate a dialogue tree with:
1. Opening line that reflects NPC's personality and disposition
2. 3-4 player response options per node
3. Different paths based on:
   - Disposition (friendly vs unfriendly versions)
   - Previous choices (flag-gated options)
   - Skill checks (persuasion, insight, etc.)
4. Natural conversation flow
5. At least one humorous option (matching NPC's humor style)
6. Ways to gain/lose NPC approval
7. Information reveals based on relationship level

Output dialogue tree as JSON:
{{
  "id": "dialogue-{topic}",
  "topic": "{topic}",
  "entry_node": "node-1",
  "nodes": {{
    "node-1": {{
      "npc_text": "What the NPC says (in their voice)",
      "options": [
        {{
          "id": "opt-1",
          "text": "Player's dialogue choice",
          "npc_response": "NPC's reply to this choice",
          "requires_disposition": null,
          "requires_flags": [],
          "sets_flags": [],
          "disposition_change": 0,
          "leads_to": "node-2"
        }},
        {{
          "id": "opt-2",
          "text": "[Persuasion] Convince them...",
          "skill_check": {{"skill": "persuasion", "dc": 15}},
          "success_response": "NPC response on success",
          "failure_response": "NPC response on failure",
          "disposition_change": 5,
          "leads_to": "node-3"
        }}
      ],
      "is_exit": false
    }}
  }}
}}"""


# =============================================================================
# CONSEQUENCE CHAIN PROMPT
# =============================================================================

CONSEQUENCE_CHAIN_PROMPT = """Design consequence chains for a player choice in a D&D campaign.

CHOICE CONTEXT:
- Encounter: {encounter_name}
- Choice Description: {choice_description}
- Options Available: {options}

CAMPAIGN CONTEXT:
- Current Act: {act_name}
- Remaining Chapters: {remaining_chapters}
- Active NPCs: {active_npcs}

For each choice option, design consequences that:
1. Have IMMEDIATE effects (happen right away)
2. Have SHORT-TERM effects (within 1-2 encounters)
3. Have LONG-TERM effects (manifest chapters/acts later)
4. Affect NPC relationships
5. Open or close future options
6. Feel meaningful and earned

BG3 Consequence Principles:
- Consequences should feel fair and logical
- Players should be able to anticipate some effects
- Some effects should be surprising but make sense in hindsight
- Major choices should have ripple effects throughout the campaign
- Even "good" choices can have negative side effects
- Even "bad" choices can have unexpected benefits

Output consequence chains as JSON:
{{
  "choice_id": "{choice_id}",
  "options": [
    {{
      "option_id": "opt-1",
      "option_text": "Choice text",
      "immediate_effects": [
        {{
          "type": "set_flag",
          "params": {{"flag": "saved_prisoner"}},
          "narrative": "Text shown to player"
        }},
        {{
          "type": "modify_npc",
          "params": {{"npc_id": "npc-1", "disposition_delta": 10}},
          "narrative": "Guard Theron nods approvingly."
        }}
      ],
      "short_term_effects": [
        {{
          "trigger": {{"type": "encounters_after", "count": 2}},
          "effect_type": "unlock_encounter",
          "params": {{"encounter_id": "enc-prisoner-help"}},
          "narrative": "The prisoner you saved has valuable information..."
        }}
      ],
      "long_term_effects": [
        {{
          "trigger": {{"type": "act", "act_id": "act-3"}},
          "effect_type": "modify_encounter",
          "params": {{"encounter_id": "enc-final", "modification": "ally_joins"}},
          "narrative": "An unexpected ally emerges from the crowd..."
        }}
      ],
      "npc_reactions": {{
        "npc-good": {{"disposition_delta": 15, "comment": "I knew you had a heart."}},
        "npc-evil": {{"disposition_delta": -10, "comment": "Soft-hearted fool."}}
      }},
      "doors_opened": ["Can recruit the prisoner later", "Prison faction favor"],
      "doors_closed": ["Guard captain becomes suspicious"]
    }}
  ]
}}"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def build_campaign_prompt(
    concept: str,
    level_start: int = 1,
    level_end: int = 10,
    length: str = "medium",
    tone: str = "mixed",
) -> str:
    """Build the campaign structure prompt with parameters."""

    length_map = {
        "short": ("5-8 encounters", 6, 2, 1, 1, 1),
        "medium": ("15-20 encounters", 10, 5, 3, 2, 2),
        "long": ("30-40 encounters", 18, 10, 6, 4, 4),
        "epic": ("50+ encounters", 25, 15, 8, 6, 5),
    }

    desc, combat, social, exploration, choice, rest = length_map.get(
        length, length_map["medium"]
    )

    return CAMPAIGN_STRUCTURE_PROMPT.format(
        concept=concept,
        level_start=level_start,
        level_end=level_end,
        length=length,
        length_description=desc,
        tone=tone,
        combat_count=combat,
        social_count=social,
        exploration_count=exploration,
        choice_count=choice,
        rest_count=rest,
    )


def build_chapter_prompt(
    campaign_name: str,
    central_conflict: str,
    act_name: str,
    act_theme: str,
    emotional_arc: str,
    chapter_id: str,
    chapter_title: str,
    chapter_description: str,
    position_in_act: str,
    party_level: int,
    party_size: int,
    previous_summary: str,
    encounter_count: int,
    encounter_targets: Dict[str, int],
    pacing_curve: str,
    required_types: List[str],
) -> str:
    """Build the chapter generation prompt with parameters."""

    targets_str = ", ".join(f"{k}: {v}" for k, v in encounter_targets.items())
    required_str = ", ".join(required_types)

    return CHAPTER_GENERATION_PROMPT.format(
        campaign_name=campaign_name,
        central_conflict=central_conflict,
        act_name=act_name,
        act_theme=act_theme,
        emotional_arc=emotional_arc,
        chapter_id=chapter_id,
        chapter_title=chapter_title,
        chapter_description=chapter_description,
        position_in_act=position_in_act,
        party_level=party_level,
        party_size=party_size,
        previous_summary=previous_summary,
        encounter_count=encounter_count,
        encounter_targets=targets_str,
        pacing_curve=pacing_curve,
        required_types=required_str,
    )


def build_encounter_prompt(
    campaign_name: str,
    act_name: str,
    act_theme: str,
    chapter_name: str,
    story_summary: str,
    party_level: int,
    party_composition: str,
    recent_events: str,
    active_flags: List[str],
    encounter_type: str,
    pacing: str,
    difficulty: str,
    callbacks: List[str],
) -> str:
    """Build the encounter generation prompt with parameters."""

    flags_str = ", ".join(active_flags) if active_flags else "None"
    callbacks_str = ", ".join(callbacks) if callbacks else "None"

    return ENCOUNTER_GENERATION_PROMPT.format(
        campaign_name=campaign_name,
        act_name=act_name,
        act_theme=act_theme,
        chapter_name=chapter_name,
        story_summary=story_summary,
        party_level=party_level,
        party_composition=party_composition,
        recent_events=recent_events,
        active_flags=flags_str,
        encounter_type=encounter_type,
        pacing=pacing,
        difficulty=difficulty,
        callbacks=callbacks_str,
    )


def build_npc_prompt(
    campaign_name: str,
    tone: str,
    story_context: str,
    role: str,
    importance: str,
    first_appearance: str,
    npc_id: str = None,
) -> str:
    """Build the NPC generation prompt with parameters."""
    import uuid

    return NPC_GENERATION_PROMPT.format(
        campaign_name=campaign_name,
        tone=tone,
        story_context=story_context,
        role=role,
        importance=importance,
        first_appearance=first_appearance,
        npc_id=npc_id or str(uuid.uuid4()),
    )
