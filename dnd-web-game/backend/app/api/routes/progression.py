"""
Character Progression API Routes.

Endpoints for XP management and leveling:
- Grant XP to characters
- Check level up eligibility
- Calculate encounter XP rewards
- Apply level ups
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from app.core.progression import (
    get_level_for_xp,
    get_xp_for_level,
    get_xp_for_next_level,
    xp_to_next_level,
    get_xp_progress,
    get_proficiency_bonus,
    can_level_up,
    get_new_level_from_xp,
    get_progression_info,
    get_xp_for_cr,
    calculate_encounter_xp,
    calculate_milestone_level,
    CR_TO_XP,
    XP_THRESHOLDS,
    MAX_LEVEL,
)

# Import session storage for character updates
from app.api.routes.campaign import active_sessions

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class GrantXPRequest(BaseModel):
    """Request to grant XP to one or more characters."""
    session_id: str = Field(..., description="Session ID")
    character_ids: List[str] = Field(..., description="Character IDs to grant XP")
    xp_amount: int = Field(..., ge=0, description="XP amount to grant each character")
    reason: Optional[str] = Field(None, description="Reason for XP grant (combat, quest, etc.)")


class EncounterXPRequest(BaseModel):
    """Request to calculate and grant encounter XP."""
    session_id: str = Field(..., description="Session ID")
    combat_id: Optional[str] = Field(None, description="Combat ID (if from combat)")
    defeated_crs: List[str] = Field(..., description="CRs of defeated creatures")
    character_ids: Optional[List[str]] = Field(None, description="Characters to reward (defaults to party)")
    divide_evenly: bool = Field(True, description="Divide XP among party members")


class MilestoneRequest(BaseModel):
    """Request to grant milestone XP/levels."""
    session_id: str = Field(..., description="Session ID")
    character_ids: Optional[List[str]] = Field(None, description="Characters to reward")
    milestone_type: str = Field(..., description="minor_milestone, moderate_milestone, major_milestone")
    xp_bonus: int = Field(0, ge=0, description="Additional XP to grant")


class LevelUpRequest(BaseModel):
    """Request to apply a level up."""
    session_id: str = Field(..., description="Session ID")
    character_id: str = Field(..., description="Character to level up")
    confirm: bool = Field(True, description="Confirm level up application")


class XPGrantResult(BaseModel):
    """Result of XP grant operation."""
    character_id: str
    character_name: str
    previous_xp: int
    xp_granted: int
    new_xp: int
    previous_level: int
    new_level: int
    leveled_up: bool
    can_level_up: bool
    xp_to_next_level: Optional[int]


class ProgressionInfoResponse(BaseModel):
    """Character progression information."""
    character_id: str
    character_name: str
    current_level: int
    current_xp: int
    xp_for_current_level: int
    xp_for_next_level: Optional[int]
    xp_needed: Optional[int]
    xp_progress: float
    proficiency_bonus: int
    can_level_up: bool
    potential_new_level: Optional[int]


# =============================================================================
# Helper Functions
# =============================================================================

def get_party_members(session_id: str, character_ids: Optional[List[str]] = None):
    """Get party members from session, optionally filtered by IDs."""
    if session_id not in active_sessions:
        return None

    engine = active_sessions[session_id]
    members = []

    for member in engine.session.party:
        if character_ids is None or member.id in character_ids:
            if member.is_active:
                members.append(member)

    return members


def apply_xp_to_character(member, xp_amount: int) -> XPGrantResult:
    """Apply XP to a character and check for level up."""
    previous_xp = getattr(member, 'experience', 0)
    previous_level = member.level

    new_xp = previous_xp + xp_amount

    # Update character XP
    member.experience = new_xp

    # Check for level up
    new_level = get_new_level_from_xp(new_xp, previous_level)
    if new_level:
        # Auto-apply level up
        member.level = new_level

    current_level = member.level
    leveled_up = current_level > previous_level

    return XPGrantResult(
        character_id=member.id,
        character_name=member.name,
        previous_xp=previous_xp,
        xp_granted=xp_amount,
        new_xp=new_xp,
        previous_level=previous_level,
        new_level=current_level,
        leveled_up=leveled_up,
        can_level_up=can_level_up(new_xp, current_level),
        xp_to_next_level=xp_to_next_level(new_xp),
    )


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/grant-xp", response_model=Dict[str, Any])
async def grant_xp(request: GrantXPRequest):
    """
    Grant XP to one or more characters.

    Automatically checks for and applies level ups.
    """
    members = get_party_members(request.session_id, request.character_ids)
    if members is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {request.session_id}"
        )

    if not members:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching characters found"
        )

    results = []
    level_ups = []

    for member in members:
        result = apply_xp_to_character(member, request.xp_amount)
        results.append(result.model_dump())

        if result.leveled_up:
            level_ups.append({
                "character_id": result.character_id,
                "character_name": result.character_name,
                "old_level": result.previous_level,
                "new_level": result.new_level,
            })

    return {
        "success": True,
        "xp_granted": request.xp_amount,
        "reason": request.reason,
        "results": results,
        "level_ups": level_ups,
        "message": f"Granted {request.xp_amount} XP to {len(members)} character(s). {len(level_ups)} level up(s)!",
    }


@router.post("/encounter-xp", response_model=Dict[str, Any])
async def grant_encounter_xp(request: EncounterXPRequest):
    """
    Calculate and grant XP from a combat encounter.

    Uses CR values to calculate total XP, optionally divided among party.
    """
    members = get_party_members(request.session_id, request.character_ids)
    if members is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {request.session_id}"
        )

    if not members:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No party members found"
        )

    # Calculate encounter XP
    party_size = len(members) if request.divide_evenly else 1
    xp_per_character = calculate_encounter_xp(
        request.defeated_crs,
        party_size=party_size,
        divide_among_party=request.divide_evenly,
    )

    total_xp = sum(get_xp_for_cr(cr) for cr in request.defeated_crs)

    results = []
    level_ups = []

    for member in members:
        result = apply_xp_to_character(member, xp_per_character)
        results.append(result.model_dump())

        if result.leveled_up:
            level_ups.append({
                "character_id": result.character_id,
                "character_name": result.character_name,
                "old_level": result.previous_level,
                "new_level": result.new_level,
            })

    # Build CR breakdown
    cr_breakdown = {}
    for cr in request.defeated_crs:
        if cr not in cr_breakdown:
            cr_breakdown[cr] = {"count": 0, "xp_each": get_xp_for_cr(cr)}
        cr_breakdown[cr]["count"] += 1

    return {
        "success": True,
        "combat_id": request.combat_id,
        "total_xp": total_xp,
        "xp_per_character": xp_per_character,
        "party_size": len(members),
        "divided_evenly": request.divide_evenly,
        "cr_breakdown": cr_breakdown,
        "results": results,
        "level_ups": level_ups,
        "message": f"Encounter complete! {total_xp} total XP, {xp_per_character} XP each. {len(level_ups)} level up(s)!",
    }


@router.post("/milestone", response_model=Dict[str, Any])
async def apply_milestone(request: MilestoneRequest):
    """
    Apply milestone leveling to characters.

    For narrative-based progression instead of XP grinding.
    """
    members = get_party_members(request.session_id, request.character_ids)
    if members is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {request.session_id}"
        )

    if not members:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No party members found"
        )

    valid_milestones = ["minor_milestone", "moderate_milestone", "major_milestone"]
    if request.milestone_type not in valid_milestones:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid milestone type. Must be one of: {valid_milestones}"
        )

    results = []
    level_ups = []

    for member in members:
        previous_level = member.level

        # Apply milestone level up
        new_level = calculate_milestone_level(previous_level, request.milestone_type)
        member.level = new_level

        # Apply bonus XP if any
        if request.xp_bonus > 0:
            previous_xp = getattr(member, 'experience', 0)
            member.experience = previous_xp + request.xp_bonus

        leveled_up = new_level > previous_level

        results.append({
            "character_id": member.id,
            "character_name": member.name,
            "previous_level": previous_level,
            "new_level": new_level,
            "leveled_up": leveled_up,
            "xp_bonus": request.xp_bonus,
        })

        if leveled_up:
            level_ups.append({
                "character_id": member.id,
                "character_name": member.name,
                "old_level": previous_level,
                "new_level": new_level,
            })

    milestone_desc = request.milestone_type.replace("_", " ").title()
    return {
        "success": True,
        "milestone_type": request.milestone_type,
        "xp_bonus": request.xp_bonus,
        "results": results,
        "level_ups": level_ups,
        "message": f"{milestone_desc} achieved! {len(level_ups)} character(s) leveled up!",
    }


@router.get("/info/{session_id}/{character_id}", response_model=ProgressionInfoResponse)
async def get_character_progression(session_id: str, character_id: str):
    """
    Get detailed progression information for a character.
    """
    members = get_party_members(session_id, [character_id])
    if members is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    if not members:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character not found: {character_id}"
        )

    member = members[0]
    current_xp = getattr(member, 'experience', 0)
    current_level = member.level

    info = get_progression_info(current_xp, current_level)

    return ProgressionInfoResponse(
        character_id=member.id,
        character_name=member.name,
        current_level=info.current_level,
        current_xp=info.current_xp,
        xp_for_current_level=info.xp_for_current_level,
        xp_for_next_level=info.xp_for_next_level,
        xp_needed=info.xp_needed,
        xp_progress=info.xp_progress,
        proficiency_bonus=info.proficiency_bonus,
        can_level_up=info.can_level_up,
        potential_new_level=info.potential_new_level,
    )


@router.get("/party/{session_id}", response_model=List[ProgressionInfoResponse])
async def get_party_progression(session_id: str):
    """
    Get progression information for all party members.
    """
    members = get_party_members(session_id)
    if members is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    results = []
    for member in members:
        current_xp = getattr(member, 'experience', 0)
        current_level = member.level
        info = get_progression_info(current_xp, current_level)

        results.append(ProgressionInfoResponse(
            character_id=member.id,
            character_name=member.name,
            current_level=info.current_level,
            current_xp=info.current_xp,
            xp_for_current_level=info.xp_for_current_level,
            xp_for_next_level=info.xp_for_next_level,
            xp_needed=info.xp_needed,
            xp_progress=info.xp_progress,
            proficiency_bonus=info.proficiency_bonus,
            can_level_up=info.can_level_up,
            potential_new_level=info.potential_new_level,
        ))

    return results


@router.get("/xp-table")
async def get_xp_table():
    """
    Get the XP threshold table for all levels.

    Useful for displaying level requirements in the UI.
    """
    table = []
    for level, xp in XP_THRESHOLDS.items():
        next_level = level + 1
        xp_for_next = XP_THRESHOLDS.get(next_level)

        table.append({
            "level": level,
            "xp_required": xp,
            "xp_to_next": xp_for_next - xp if xp_for_next else None,
            "proficiency_bonus": get_proficiency_bonus(level),
        })

    return {"levels": table, "max_level": MAX_LEVEL}


@router.get("/cr-table")
async def get_cr_xp_table():
    """
    Get the CR to XP conversion table.

    Useful for encounter building and XP calculations.
    """
    table = []
    for cr, xp in CR_TO_XP.items():
        table.append({
            "cr": cr,
            "xp": xp,
        })

    return {"challenge_ratings": table}


@router.post("/calculate-encounter")
async def calculate_encounter(defeated_crs: List[str], party_size: int = 4):
    """
    Calculate XP for an encounter without granting it.

    Preview tool for DMs planning encounters.
    """
    total_xp = sum(get_xp_for_cr(cr) for cr in defeated_crs)
    xp_per_character = total_xp // party_size if party_size > 0 else total_xp

    cr_breakdown = {}
    for cr in defeated_crs:
        if cr not in cr_breakdown:
            cr_breakdown[cr] = {"count": 0, "xp_each": get_xp_for_cr(cr)}
        cr_breakdown[cr]["count"] += 1

    return {
        "total_xp": total_xp,
        "party_size": party_size,
        "xp_per_character": xp_per_character,
        "cr_breakdown": cr_breakdown,
        "defeated_count": len(defeated_crs),
    }
