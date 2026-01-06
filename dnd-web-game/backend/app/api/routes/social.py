"""
Social encounter API routes.

Endpoints for:
- Social skill checks with relationship effects
- NPC relationship management
- Faction reputation tracking
- Skill challenges
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from app.models.social import (
    NPCRelationship,
    FactionReputation,
    SocialState,
    Disposition,
    InteractionType,
    FactionType,
    ReputationTier,
)
from app.core.social_engine import (
    SocialEngine,
    SocialCheckResult,
    SkillChallengeState,
    get_social_engine,
)

router = APIRouter()


# =============================================================================
# In-memory storage for session social states
# In production, this would be in the database
# =============================================================================

_social_states: Dict[str, SocialState] = {}


def get_or_create_social_state(session_id: str) -> SocialState:
    """Get or create social state for a session."""
    if session_id not in _social_states:
        _social_states[session_id] = SocialState(session_id=session_id)
    return _social_states[session_id]


# =============================================================================
# Request/Response Models
# =============================================================================

class SocialCheckRequest(BaseModel):
    """Request for a social skill check."""
    session_id: str
    skill: str = Field(..., description="Social skill: persuasion, deception, intimidation, insight")
    base_dc: int = Field(15, ge=1, le=30)
    character_modifier: int = Field(0, ge=-10, le=30)
    npc_id: Optional[str] = None
    npc_name: Optional[str] = None
    faction_id: Optional[str] = None
    advantage: bool = False
    disadvantage: bool = False


class CreateNPCRelationshipRequest(BaseModel):
    """Request to create/initialize NPC relationship."""
    session_id: str
    npc_id: str
    npc_name: str
    initial_disposition: int = Field(0, ge=-100, le=100)


class AdjustRelationshipRequest(BaseModel):
    """Request to adjust NPC relationship."""
    session_id: str
    npc_id: str
    disposition_change: int = Field(0, ge=-50, le=50)
    trust_change: int = Field(0, ge=-50, le=50)
    reason: str = ""


class CreateFactionRequest(BaseModel):
    """Request to create/initialize faction reputation."""
    session_id: str
    faction_id: str
    faction_name: str
    faction_type: str = "guild"


class AdjustFactionRequest(BaseModel):
    """Request to adjust faction reputation."""
    session_id: str
    faction_id: str
    reputation_change: int = Field(0, ge=-50, le=50)
    reason: str = ""


class CreateSkillChallengeRequest(BaseModel):
    """Request to create a skill challenge."""
    challenge_id: str
    name: str
    description: str = ""
    successes_needed: int = Field(3, ge=1, le=10)
    failures_allowed: int = Field(3, ge=1, le=10)
    skill_limits: Optional[Dict[str, int]] = None


class SkillChallengeAttemptRequest(BaseModel):
    """Request to attempt a skill in a skill challenge."""
    challenge_id: str
    skill: str
    character_modifier: int = 0
    base_dc: int = Field(15, ge=1, le=30)
    advantage: bool = False
    disadvantage: bool = False


# =============================================================================
# Social Check Endpoints
# =============================================================================

@router.post("/check")
async def perform_social_check(request: SocialCheckRequest):
    """
    Perform a social skill check with relationship effects.

    Applies disposition-based DC modifiers and tracks relationship changes.
    """
    engine = get_social_engine()
    state = get_or_create_social_state(request.session_id)

    # Get NPC relationship if specified
    npc_relationship = None
    if request.npc_id:
        npc_relationship = state.get_or_create_npc_relationship(
            npc_id=request.npc_id,
            npc_name=request.npc_name or request.npc_id,
        )

    # Get faction reputation if specified
    faction_reputation = None
    if request.faction_id:
        faction_reputation = state.get_faction_reputation(request.faction_id)

    # Perform the check
    result = engine.perform_social_check(
        skill=request.skill,
        base_dc=request.base_dc,
        character_modifier=request.character_modifier,
        npc_relationship=npc_relationship,
        advantage=request.advantage,
        disadvantage=request.disadvantage,
        faction_reputation=faction_reputation,
    )

    response = {
        "result": result.to_dict(),
    }

    # Include updated relationship if applicable
    if npc_relationship:
        response["relationship"] = npc_relationship.to_dict()

    return response


# =============================================================================
# NPC Relationship Endpoints
# =============================================================================

@router.get("/relationship/{session_id}/{npc_id}")
async def get_npc_relationship(session_id: str, npc_id: str):
    """
    Get relationship with a specific NPC.
    """
    state = get_or_create_social_state(session_id)
    relationship = state.get_npc_relationship(npc_id)

    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No relationship found with NPC: {npc_id}"
        )

    return {
        "relationship": relationship.to_dict(),
    }


@router.post("/relationship/create")
async def create_npc_relationship(request: CreateNPCRelationshipRequest):
    """
    Create or initialize relationship with an NPC.
    """
    state = get_or_create_social_state(request.session_id)
    relationship = state.get_or_create_npc_relationship(
        npc_id=request.npc_id,
        npc_name=request.npc_name,
        initial_disposition=request.initial_disposition,
    )

    return {
        "relationship": relationship.to_dict(),
    }


@router.post("/relationship/adjust")
async def adjust_npc_relationship(request: AdjustRelationshipRequest):
    """
    Adjust disposition and/or trust with an NPC.
    """
    state = get_or_create_social_state(request.session_id)
    relationship = state.get_npc_relationship(request.npc_id)

    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No relationship found with NPC: {request.npc_id}"
        )

    old_disposition = relationship.disposition
    if request.disposition_change:
        relationship.adjust_disposition(request.disposition_change)
    if request.trust_change:
        relationship.adjust_trust(request.trust_change)

    return {
        "relationship": relationship.to_dict(),
        "disposition_changed": old_disposition != relationship.disposition,
        "old_disposition": old_disposition.value,
        "new_disposition": relationship.disposition.value,
    }


@router.get("/relationships/{session_id}")
async def get_all_npc_relationships(session_id: str):
    """
    Get all NPC relationships for a session.
    """
    state = get_or_create_social_state(session_id)

    return {
        "relationships": {
            npc_id: rel.to_dict()
            for npc_id, rel in state.npc_relationships.items()
        },
        "count": len(state.npc_relationships),
    }


# =============================================================================
# Faction Reputation Endpoints
# =============================================================================

@router.get("/faction/{session_id}/{faction_id}")
async def get_faction_reputation(session_id: str, faction_id: str):
    """
    Get reputation with a specific faction.
    """
    state = get_or_create_social_state(session_id)
    reputation = state.get_faction_reputation(faction_id)

    if not reputation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No reputation found with faction: {faction_id}"
        )

    engine = get_social_engine()
    services = engine.get_faction_services(reputation)

    return {
        "reputation": reputation.to_dict(),
        "available_services": services,
    }


@router.post("/faction/create")
async def create_faction_reputation(request: CreateFactionRequest):
    """
    Create or initialize reputation with a faction.
    """
    state = get_or_create_social_state(request.session_id)

    try:
        faction_type = FactionType(request.faction_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid faction type: {request.faction_type}"
        )

    reputation = state.get_or_create_faction_reputation(
        faction_id=request.faction_id,
        faction_name=request.faction_name,
        faction_type=faction_type,
    )

    return {
        "reputation": reputation.to_dict(),
    }


@router.post("/faction/adjust")
async def adjust_faction_reputation(request: AdjustFactionRequest):
    """
    Adjust reputation with a faction.
    """
    state = get_or_create_social_state(request.session_id)
    reputation = state.get_faction_reputation(request.faction_id)

    if not reputation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No reputation found with faction: {request.faction_id}"
        )

    engine = get_social_engine()
    old_tier = reputation.tier
    new_value, new_tier = engine.adjust_faction_reputation(
        faction=reputation,
        amount=request.reputation_change,
        reason=request.reason,
    )

    return {
        "reputation": reputation.to_dict(),
        "tier_changed": new_tier is not None,
        "old_tier": old_tier.value,
        "new_tier": reputation.tier.value,
    }


@router.get("/factions/{session_id}")
async def get_all_faction_reputations(session_id: str):
    """
    Get all faction reputations for a session.
    """
    state = get_or_create_social_state(session_id)

    return {
        "factions": {
            faction_id: rep.to_dict()
            for faction_id, rep in state.faction_reputations.items()
        },
        "count": len(state.faction_reputations),
    }


# =============================================================================
# Skill Challenge Endpoints
# =============================================================================

@router.post("/skill-challenge/create")
async def create_skill_challenge(request: CreateSkillChallengeRequest):
    """
    Create a new skill challenge.

    Skill challenges are multi-stage social encounters where the party
    must accumulate successes before too many failures.
    """
    engine = get_social_engine()

    # Check if challenge already exists
    if engine.get_skill_challenge(request.challenge_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Skill challenge already exists: {request.challenge_id}"
        )

    challenge = engine.create_skill_challenge(
        challenge_id=request.challenge_id,
        name=request.name,
        description=request.description,
        successes_needed=request.successes_needed,
        failures_allowed=request.failures_allowed,
        skill_limits=request.skill_limits,
    )

    return {
        "challenge": challenge.to_dict(),
    }


@router.post("/skill-challenge/attempt")
async def attempt_skill_challenge(request: SkillChallengeAttemptRequest):
    """
    Make an attempt in a skill challenge.
    """
    engine = get_social_engine()

    try:
        result, challenge = engine.attempt_skill_challenge(
            challenge_id=request.challenge_id,
            skill=request.skill,
            character_modifier=request.character_modifier,
            base_dc=request.base_dc,
            advantage=request.advantage,
            disadvantage=request.disadvantage,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return {
        "result": result.to_dict(),
        "challenge": challenge.to_dict(),
    }


@router.get("/skill-challenge/{challenge_id}")
async def get_skill_challenge(challenge_id: str):
    """
    Get the current state of a skill challenge.
    """
    engine = get_social_engine()
    challenge = engine.get_skill_challenge(challenge_id)

    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill challenge not found: {challenge_id}"
        )

    return {
        "challenge": challenge.to_dict(),
    }


@router.delete("/skill-challenge/{challenge_id}")
async def end_skill_challenge(challenge_id: str):
    """
    End and remove a skill challenge.
    """
    engine = get_social_engine()
    challenge = engine.end_skill_challenge(challenge_id)

    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill challenge not found: {challenge_id}"
        )

    return {
        "success": True,
        "final_state": challenge.to_dict(),
    }


# =============================================================================
# Reference Endpoints
# =============================================================================

@router.get("/dispositions")
async def list_dispositions():
    """
    Get all disposition levels and their effects.
    """
    return {
        "dispositions": [
            {
                "value": d.value,
                "range": _get_disposition_range(d),
                "dc_modifier": _get_disposition_dc_mod(d),
            }
            for d in Disposition
        ],
    }


@router.get("/faction-types")
async def list_faction_types():
    """
    Get all faction types.
    """
    return {
        "faction_types": [ft.value for ft in FactionType],
    }


@router.get("/reputation-tiers")
async def list_reputation_tiers():
    """
    Get all reputation tiers and their effects.
    """
    return {
        "tiers": [
            {
                "value": t.value,
                "range": _get_tier_range(t),
            }
            for t in ReputationTier
        ],
    }


# Helper functions for reference endpoints
def _get_disposition_range(d: Disposition) -> str:
    ranges = {
        Disposition.HOSTILE: "-100 to -60",
        Disposition.UNFRIENDLY: "-59 to -20",
        Disposition.INDIFFERENT: "-19 to +19",
        Disposition.FRIENDLY: "+20 to +59",
        Disposition.ALLIED: "+60 to +100",
    }
    return ranges.get(d, "Unknown")


def _get_disposition_dc_mod(d: Disposition) -> int:
    mods = {
        Disposition.HOSTILE: 5,
        Disposition.UNFRIENDLY: 2,
        Disposition.INDIFFERENT: 0,
        Disposition.FRIENDLY: -2,
        Disposition.ALLIED: -5,
    }
    return mods.get(d, 0)


def _get_tier_range(t: ReputationTier) -> str:
    ranges = {
        ReputationTier.ENEMY: "-100 to -60",
        ReputationTier.HATED: "-59 to -30",
        ReputationTier.DISLIKED: "-29 to -10",
        ReputationTier.NEUTRAL: "-9 to +9",
        ReputationTier.LIKED: "+10 to +29",
        ReputationTier.HONORED: "+30 to +59",
        ReputationTier.REVERED: "+60 to +100",
    }
    return ranges.get(t, "Unknown")
