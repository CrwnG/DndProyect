"""
DM Control Routes - AI/Human hybrid DM management.

Endpoints for:
- Getting/setting DM mode (AI, Human, Hybrid)
- Requesting AI-generated content
- Human DM overrides
- Personality customization
- Usage statistics and rate limiting
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from app.services.ai_dm import get_ai_dm, DMMode
from app.services.ai_dm_personalities import DMPersonality, DMTone, DMVerbosity

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class DMControlRequest(BaseModel):
    """Request to set DM control mode."""
    mode: str = Field(..., description="DM mode: 'ai', 'human', or 'hybrid'")


class NarrativeRequest(BaseModel):
    """Request for AI-generated narrative content."""
    context_type: str = Field(..., description="Type: 'scene', 'npc', 'combat', 'skill_check'")
    context_data: Dict[str, Any] = Field(default_factory=dict)


class NPCDialogueRequest(BaseModel):
    """Request for NPC dialogue generation."""
    npc_name: str
    npc_personality: str
    context: str
    player_input: str


class CombatNarrationRequest(BaseModel):
    """Request for combat narration."""
    action_result: Dict[str, Any]
    combatant: Dict[str, Any]
    target: Optional[Dict[str, Any]] = None


class SkillCheckNarrationRequest(BaseModel):
    """Request for skill check narration."""
    character_name: str
    skill: str
    dc: int
    roll: int
    success: bool
    context: str


class EncounterSuggestionRequest(BaseModel):
    """Request for dynamic encounter suggestion."""
    avg_level: int = 1
    party_size: int = 4
    hp_percent: int = 100
    resources: str = "full"
    story_context: str = ""


class PersonalityPresetRequest(BaseModel):
    """Request to set DM personality from preset."""
    preset: str = Field(..., description="Preset name: classic, epic, horror, comedy, fairy_tale, noir, quick, immersive")


class CustomPersonalityRequest(BaseModel):
    """Request to set custom DM personality."""
    tone: Optional[str] = Field(None, description="Tone: dramatic, casual, gritty, whimsical, neutral")
    verbosity: Optional[str] = Field(None, description="Verbosity: terse, standard, verbose")
    humor_level: Optional[float] = Field(None, ge=0, le=1, description="Humor level 0-1")
    gore_level: Optional[float] = Field(None, ge=0, le=1, description="Gore/violence level 0-1")
    formality: Optional[float] = Field(None, ge=0, le=1, description="Formality level 0-1")
    dramatic_flair: Optional[float] = Field(None, ge=0, le=1, description="Dramatic flair 0-1")
    mystery_emphasis: Optional[float] = Field(None, ge=0, le=1, description="Mystery emphasis 0-1")
    custom_style_hints: Optional[str] = Field(None, description="Custom style hints text")
    base_preset: Optional[str] = Field(None, description="Preset to base on (optional)")


class RateLimitsRequest(BaseModel):
    """Request to update rate limits."""
    requests_per_minute: Optional[int] = Field(None, ge=1, le=100, description="Max requests per minute")
    requests_per_hour: Optional[int] = Field(None, ge=1, le=1000, description="Max requests per hour")
    daily_cost_cap_usd: Optional[float] = Field(None, ge=0.1, le=100, description="Daily cost cap in USD")


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/status")
async def get_dm_status():
    """
    Get current DM status and capabilities.

    Returns mode, whether AI is enabled, and available features.
    """
    dm = get_ai_dm()

    return {
        "mode": dm.mode.value,
        "ai_enabled": dm.is_ai_enabled,
        "human_override_active": dm.mode == DMMode.HUMAN,
        "capabilities": {
            "scene_description": dm.is_ai_enabled,
            "npc_dialogue": dm.is_ai_enabled,
            "combat_narration": dm.is_ai_enabled,
            "skill_check_narration": dm.is_ai_enabled,
            "encounter_suggestion": dm.is_ai_enabled,
        }
    }


@router.post("/control")
async def set_dm_control(request: DMControlRequest):
    """
    Set DM control mode.

    Modes:
    - 'ai': AI generates all content automatically
    - 'human': Human DM provides all content
    - 'hybrid': AI suggests, human approves
    """
    dm = get_ai_dm()

    mode_map = {
        "ai": DMMode.AI,
        "human": DMMode.HUMAN,
        "hybrid": DMMode.HYBRID,
    }

    if request.mode.lower() not in mode_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mode. Must be one of: {list(mode_map.keys())}"
        )

    new_mode = mode_map[request.mode.lower()]
    dm.set_mode(new_mode)

    return {
        "success": True,
        "mode": dm.mode.value,
        "message": f"DM control set to {dm.mode.value}",
    }


@router.post("/override")
async def set_human_override(active: bool = True):
    """
    Toggle human DM override.

    When active, all AI generation is paused and human provides content.
    """
    dm = get_ai_dm()
    dm.set_human_override(active)

    return {
        "success": True,
        "human_override_active": active,
        "mode": dm.mode.value,
        "message": f"Human override {'activated' if active else 'deactivated'}",
    }


@router.post("/generate/scene")
async def generate_scene_description(
    encounter: Dict[str, Any],
    party: List[Dict[str, Any]] = [],
    world_state: Dict[str, Any] = {},
):
    """
    Generate scene description for an encounter.

    AI creates immersive, atmospheric description of the current scene.
    """
    dm = get_ai_dm()

    if not dm.is_ai_enabled:
        return {
            "generated": False,
            "reason": "AI is disabled or human DM is in control",
            "content": None,
        }

    content = await dm.generate_scene_description(encounter, party, world_state)

    return {
        "generated": content is not None,
        "content": content,
    }


@router.post("/generate/npc")
async def generate_npc_dialogue(request: NPCDialogueRequest):
    """
    Generate NPC dialogue response.

    AI responds in character as the specified NPC.
    """
    dm = get_ai_dm()

    if not dm.is_ai_enabled:
        return {
            "generated": False,
            "reason": "AI is disabled or human DM is in control",
            "content": None,
        }

    content = await dm.generate_npc_dialogue(
        request.npc_name,
        request.npc_personality,
        request.context,
        request.player_input,
    )

    return {
        "generated": content is not None,
        "npc_name": request.npc_name,
        "content": content,
    }


@router.post("/generate/combat")
async def generate_combat_narration(request: CombatNarrationRequest):
    """
    Generate dramatic combat narration.

    AI describes combat actions with vivid, exciting language.
    """
    dm = get_ai_dm()

    if not dm.is_ai_enabled:
        return {
            "generated": False,
            "reason": "AI is disabled or human DM is in control",
            "content": None,
        }

    content = await dm.generate_combat_narration(
        request.action_result,
        request.combatant,
        request.target,
    )

    return {
        "generated": content is not None,
        "content": content,
    }


@router.post("/generate/skill-check")
async def generate_skill_check_narration(request: SkillCheckNarrationRequest):
    """
    Generate skill check result narration.

    AI describes the outcome of a skill check narratively.
    """
    dm = get_ai_dm()

    if not dm.is_ai_enabled:
        return {
            "generated": False,
            "reason": "AI is disabled or human DM is in control",
            "content": None,
        }

    content = await dm.generate_skill_check_result(
        request.character_name,
        request.skill,
        request.dc,
        request.roll,
        request.success,
        request.context,
    )

    return {
        "generated": content is not None,
        "success": request.success,
        "content": content,
    }


@router.post("/suggest/encounter")
async def suggest_encounter(request: EncounterSuggestionRequest):
    """
    Get AI-suggested dynamic encounter.

    AI suggests a balanced encounter based on party status and story context.
    """
    dm = get_ai_dm()

    if not dm.is_ai_enabled:
        return {
            "generated": False,
            "reason": "AI is disabled or human DM is in control",
            "suggestion": None,
        }

    party_status = {
        "avg_level": request.avg_level,
        "party_size": request.party_size,
        "hp_percent": request.hp_percent,
        "resources": request.resources,
    }

    suggestion = await dm.suggest_dynamic_encounter(party_status, request.story_context)

    return {
        "generated": suggestion is not None,
        "suggestion": suggestion,
    }


@router.post("/generate")
async def generate_narrative(request: NarrativeRequest):
    """
    Generic narrative generation endpoint.

    Handles multiple content types based on context_type.
    """
    dm = get_ai_dm()

    if not dm.is_ai_enabled:
        return {
            "generated": False,
            "reason": "AI is disabled or human DM is in control",
            "content": None,
        }

    context_type = request.context_type.lower()
    data = request.context_data

    if context_type == "scene":
        content = await dm.generate_scene_description(
            data.get("encounter", {}),
            data.get("party", []),
            data.get("world_state", {}),
        )
    elif context_type == "npc":
        content = await dm.generate_npc_dialogue(
            data.get("npc_name", "Unknown"),
            data.get("npc_personality", "neutral"),
            data.get("context", ""),
            data.get("player_input", ""),
        )
    elif context_type == "combat":
        content = await dm.generate_combat_narration(
            data.get("action_result", {}),
            data.get("combatant", {}),
            data.get("target"),
        )
    elif context_type == "skill_check":
        content = await dm.generate_skill_check_result(
            data.get("character_name", "Unknown"),
            data.get("skill", "Athletics"),
            data.get("dc", 10),
            data.get("roll", 10),
            data.get("success", True),
            data.get("context", ""),
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown context type: {context_type}"
        )

    return {
        "generated": content is not None,
        "context_type": context_type,
        "content": content,
    }


# =============================================================================
# Personality Endpoints
# =============================================================================

@router.get("/personality")
async def get_dm_personality():
    """
    Get current DM personality settings.

    Returns the full personality configuration including tone,
    verbosity, and all style settings.
    """
    dm = get_ai_dm()

    return {
        "personality": dm.get_personality(),
        "available_presets": dm.get_available_presets(),
    }


@router.post("/personality/preset")
async def set_dm_personality_preset(request: PersonalityPresetRequest):
    """
    Set DM personality from a preset.

    Available presets: classic, epic, horror, comedy, fairy_tale, noir, quick, immersive
    """
    dm = get_ai_dm()

    success = dm.set_personality_preset(request.preset)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown personality preset: {request.preset}. Available: classic, epic, horror, comedy, fairy_tale, noir, quick, immersive"
        )

    return {
        "success": True,
        "preset": request.preset,
        "personality": dm.get_personality(),
    }


@router.post("/personality/custom")
async def set_dm_personality_custom(request: CustomPersonalityRequest):
    """
    Set custom DM personality with specific settings.

    Can optionally base on an existing preset and override specific fields.
    """
    dm = get_ai_dm()

    # Build personality from request
    try:
        if request.base_preset:
            from app.services.ai_dm_personalities import create_custom_personality
            overrides = {}
            if request.tone:
                overrides["tone"] = DMTone(request.tone.lower())
            if request.verbosity:
                overrides["verbosity"] = DMVerbosity(request.verbosity.lower())
            if request.humor_level is not None:
                overrides["humor_level"] = request.humor_level
            if request.gore_level is not None:
                overrides["gore_level"] = request.gore_level
            if request.formality is not None:
                overrides["formality"] = request.formality
            if request.dramatic_flair is not None:
                overrides["dramatic_flair"] = request.dramatic_flair
            if request.mystery_emphasis is not None:
                overrides["mystery_emphasis"] = request.mystery_emphasis
            if request.custom_style_hints:
                overrides["custom_style_hints"] = request.custom_style_hints

            personality = create_custom_personality(request.base_preset, **overrides)
        else:
            # Create from scratch
            personality = DMPersonality(
                tone=DMTone(request.tone.lower()) if request.tone else DMTone.NEUTRAL,
                verbosity=DMVerbosity(request.verbosity.lower()) if request.verbosity else DMVerbosity.STANDARD,
                humor_level=request.humor_level if request.humor_level is not None else 0.3,
                gore_level=request.gore_level if request.gore_level is not None else 0.3,
                formality=request.formality if request.formality is not None else 0.5,
                dramatic_flair=request.dramatic_flair if request.dramatic_flair is not None else 0.5,
                mystery_emphasis=request.mystery_emphasis if request.mystery_emphasis is not None else 0.3,
                custom_style_hints=request.custom_style_hints or "",
                name="Custom",
                description="Custom personality configuration",
            )

        dm.set_personality(personality)

        return {
            "success": True,
            "personality": dm.get_personality(),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# =============================================================================
# Usage Statistics Endpoints
# =============================================================================

@router.get("/usage")
async def get_dm_usage_stats():
    """
    Get AI DM usage statistics.

    Returns request counts, token usage, estimated costs,
    and rate limit status.
    """
    dm = get_ai_dm()

    return {
        "usage": dm.get_usage_stats(),
        "ai_enabled": dm.is_ai_enabled,
    }


@router.get("/cache")
async def get_dm_cache_stats():
    """
    Get AI DM response cache statistics.

    Returns cache size, hit rate, and entries by scenario type.
    """
    dm = get_ai_dm()

    return {
        "cache": dm.get_cache_stats(),
    }


@router.post("/cache/clear")
async def clear_dm_cache():
    """
    Clear the AI DM response cache.

    Useful if you want to force fresh AI-generated content.
    """
    dm = get_ai_dm()
    entries_cleared = dm.clear_cache()

    return {
        "success": True,
        "entries_cleared": entries_cleared,
    }


@router.post("/limits")
async def set_dm_rate_limits(request: RateLimitsRequest):
    """
    Update AI DM rate limits.

    Adjust requests per minute, requests per hour, and daily cost cap.
    """
    dm = get_ai_dm()

    updated_limits = dm.set_rate_limits(
        requests_per_minute=request.requests_per_minute,
        requests_per_hour=request.requests_per_hour,
        daily_cost_cap_usd=request.daily_cost_cap_usd,
    )

    return {
        "success": True,
        "limits": updated_limits,
    }
