"""
Skill Checks API Routes.

Endpoints for D&D 5e skill checks, ability checks, and saving throws:
- Ability checks (raw)
- Skill checks (with proficiency)
- Saving throws
- Group checks (party stealth, etc.)
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from app.core.skill_checks import (
    perform_skill_check,
    perform_ability_check,
    perform_saving_throw,
    perform_group_check,
    get_skill_modifier,
    get_ability_modifier,
    get_proficiency_bonus,
    get_dc_difficulty_label,
    get_skill_display_name,
    Skill,
    SKILL_ABILITIES,
    DifficultyClass,
)

# Import session storage for character lookup
from app.api.routes.campaign import active_sessions

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class AbilityCheckRequest(BaseModel):
    """Request for a raw ability check."""
    ability: str = Field(..., description="Ability name: str, dex, con, int, wis, cha")
    dc: int = Field(..., ge=1, le=40, description="Difficulty class to beat")
    ability_score: int = Field(10, ge=1, le=30, description="Character's ability score")
    advantage: bool = False
    disadvantage: bool = False


class SkillCheckRequest(BaseModel):
    """Request for a skill check."""
    skill: str = Field(..., description="Skill name (e.g., 'stealth', 'persuasion')")
    dc: int = Field(..., ge=1, le=40, description="Difficulty class to beat")

    # Character stats - can be provided directly or looked up from session
    session_id: Optional[str] = None
    character_id: Optional[str] = None

    # Direct stats (used if no session/character provided)
    ability_score: int = Field(10, ge=1, le=30, description="Relevant ability score")
    level: int = Field(1, ge=1, le=20, description="Character level")
    proficient: Optional[bool] = None  # Override proficiency check
    expertise: bool = False
    skill_proficiencies: List[str] = Field(default_factory=list)

    advantage: bool = False
    disadvantage: bool = False


class SavingThrowRequest(BaseModel):
    """Request for a saving throw."""
    ability: str = Field(..., description="Ability for the save: str, dex, con, int, wis, cha")
    dc: int = Field(..., ge=1, le=40, description="Difficulty class to beat")

    # Character stats
    session_id: Optional[str] = None
    character_id: Optional[str] = None

    # Direct stats
    ability_score: int = Field(10, ge=1, le=30)
    level: int = Field(1, ge=1, le=20)
    proficient: Optional[bool] = None
    saving_throw_proficiencies: List[str] = Field(default_factory=list)

    advantage: bool = False
    disadvantage: bool = False


class GroupCheckRequest(BaseModel):
    """Request for a group skill check (e.g., party stealth)."""
    skill: str = Field(..., description="Skill name for the group check")
    dc: int = Field(..., ge=1, le=40, description="Difficulty class")
    session_id: str = Field(..., description="Session ID to get party members")
    advantage: bool = False
    disadvantage: bool = False


class CheckResultResponse(BaseModel):
    """Response for any check result."""
    success: bool
    skill: str
    ability: str
    roll: int
    rolls: List[int]
    modifier: int
    total: int
    dc: int
    dc_label: str
    critical_success: bool
    critical_failure: bool
    advantage: bool
    disadvantage: bool
    message: str


class GroupCheckResultResponse(BaseModel):
    """Response for a group check."""
    success: bool
    skill: str
    dc: int
    dc_label: str
    successes: int
    failures: int
    needed_successes: int
    individual_results: List[Dict[str, Any]]
    message: str


class CharacterModifiersResponse(BaseModel):
    """Response with all skill modifiers for a character."""
    character_id: str
    character_name: str
    level: int
    proficiency_bonus: int
    ability_modifiers: Dict[str, int]
    skill_modifiers: Dict[str, int]
    saving_throw_modifiers: Dict[str, int]


# =============================================================================
# Helper Functions
# =============================================================================

def get_character_from_session(session_id: str, character_id: str) -> Optional[Dict[str, Any]]:
    """Get character stats from session party."""
    if session_id not in active_sessions:
        return None

    engine = active_sessions[session_id]
    for member in engine.session.party:
        if member.id == character_id:
            return {
                "id": member.id,
                "name": member.name,
                "str": member.strength,
                "dex": member.dexterity,
                "con": member.constitution,
                "int": member.intelligence,
                "wis": member.wisdom,
                "cha": member.charisma,
                "level": member.level,
                "character_class": member.character_class,
                # These would need to be stored on character or derived from class
                "skill_proficiencies": [],
                "saving_throw_proficiencies": [],
            }
    return None


def build_check_message(result, dc_label: str) -> str:
    """Build a descriptive message for the check result."""
    skill_name = get_skill_display_name(result.skill)

    if result.critical_success:
        roll_desc = "Natural 20!"
    elif result.critical_failure:
        roll_desc = "Natural 1!"
    elif len(result.rolls) > 1:
        roll_desc = f"Rolled {result.rolls[0]} and {result.rolls[1]}, took {result.roll}"
    else:
        roll_desc = f"Rolled {result.roll}"

    outcome = "SUCCESS" if result.success else "FAILURE"
    sign = "+" if result.modifier >= 0 else ""

    return f"{skill_name} Check ({dc_label}): {roll_desc} {sign}{result.modifier} = {result.total} vs DC {result.dc} - {outcome}"


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/ability", response_model=CheckResultResponse)
async def ability_check(request: AbilityCheckRequest):
    """
    Perform a raw ability check (no skill proficiency).

    Used for tasks that don't map to a specific skill, like
    raw Strength checks for breaking down doors.
    """
    character_stats = {
        request.ability.lower()[:3]: request.ability_score,
        "level": 1,  # Not used for raw ability checks
    }

    result = perform_ability_check(
        ability=request.ability,
        dc=request.dc,
        character_stats=character_stats,
        advantage=request.advantage,
        disadvantage=request.disadvantage,
    )

    dc_label = get_dc_difficulty_label(request.dc)

    return CheckResultResponse(
        success=result.success,
        skill=result.skill,
        ability=result.ability,
        roll=result.roll,
        rolls=result.rolls,
        modifier=result.modifier,
        total=result.total,
        dc=result.dc,
        dc_label=dc_label,
        critical_success=result.critical_success,
        critical_failure=result.critical_failure,
        advantage=result.advantage,
        disadvantage=result.disadvantage,
        message=build_check_message(result, dc_label),
    )


@router.post("/skill", response_model=CheckResultResponse)
async def skill_check(request: SkillCheckRequest):
    """
    Perform a skill check with proficiency bonus if applicable.

    Can use session/character_id to look up stats, or provide
    stats directly for standalone testing.
    """
    # Build character stats
    if request.session_id and request.character_id:
        char_data = get_character_from_session(request.session_id, request.character_id)
        if not char_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Character not found in session"
            )
        character_stats = char_data
    else:
        # Use direct stats from request
        # Determine which ability this skill uses
        try:
            skill_enum = Skill(request.skill.lower())
            ability = SKILL_ABILITIES[skill_enum]
        except ValueError:
            ability = request.skill.lower()[:3]

        character_stats = {
            ability: request.ability_score,
            "level": request.level,
            "skill_proficiencies": request.skill_proficiencies,
        }

    result = perform_skill_check(
        skill=request.skill,
        dc=request.dc,
        character_stats=character_stats,
        advantage=request.advantage,
        disadvantage=request.disadvantage,
        proficient=request.proficient,
        expertise=request.expertise,
    )

    dc_label = get_dc_difficulty_label(request.dc)

    return CheckResultResponse(
        success=result.success,
        skill=result.skill,
        ability=result.ability,
        roll=result.roll,
        rolls=result.rolls,
        modifier=result.modifier,
        total=result.total,
        dc=result.dc,
        dc_label=dc_label,
        critical_success=result.critical_success,
        critical_failure=result.critical_failure,
        advantage=result.advantage,
        disadvantage=result.disadvantage,
        message=build_check_message(result, dc_label),
    )


@router.post("/save", response_model=CheckResultResponse)
async def saving_throw(request: SavingThrowRequest):
    """
    Perform a saving throw.

    Uses proficiency bonus if character is proficient in that save.
    """
    # Build character stats
    if request.session_id and request.character_id:
        char_data = get_character_from_session(request.session_id, request.character_id)
        if not char_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Character not found in session"
            )
        character_stats = char_data
    else:
        ability_key = request.ability.lower()[:3]
        character_stats = {
            ability_key: request.ability_score,
            "level": request.level,
            "saving_throw_proficiencies": request.saving_throw_proficiencies,
        }

    result = perform_saving_throw(
        ability=request.ability,
        dc=request.dc,
        character_stats=character_stats,
        advantage=request.advantage,
        disadvantage=request.disadvantage,
        proficient=request.proficient,
    )

    dc_label = get_dc_difficulty_label(request.dc)

    return CheckResultResponse(
        success=result.success,
        skill=result.skill,
        ability=result.ability,
        roll=result.roll,
        rolls=result.rolls,
        modifier=result.modifier,
        total=result.total,
        dc=result.dc,
        dc_label=dc_label,
        critical_success=result.critical_success,
        critical_failure=result.critical_failure,
        advantage=result.advantage,
        disadvantage=result.disadvantage,
        message=build_check_message(result, dc_label),
    )


@router.post("/group", response_model=GroupCheckResultResponse)
async def group_check(request: GroupCheckRequest):
    """
    Perform a group skill check (D&D 5e PHB p.175).

    Everyone in the party makes the check. If at least half succeed,
    the whole group succeeds. Used for party stealth, group climbing, etc.
    """
    if request.session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {request.session_id}"
        )

    engine = active_sessions[request.session_id]

    # Build party member data for the check
    party_members = []
    for member in engine.session.party:
        if not member.is_active or member.is_dead:
            continue
        party_members.append({
            "id": member.id,
            "name": member.name,
            "strength": member.strength,
            "dexterity": member.dexterity,
            "constitution": member.constitution,
            "intelligence": member.intelligence,
            "wisdom": member.wisdom,
            "charisma": member.charisma,
            "level": member.level,
            "skill_proficiencies": [],  # Would come from character data
        })

    if not party_members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active party members for group check"
        )

    result = perform_group_check(
        skill=request.skill,
        dc=request.dc,
        party_members=party_members,
        advantage=request.advantage,
        disadvantage=request.disadvantage,
    )

    dc_label = get_dc_difficulty_label(request.dc)
    skill_name = get_skill_display_name(request.skill)
    outcome = "SUCCESS" if result.success else "FAILURE"

    message = (
        f"Group {skill_name} Check ({dc_label}): "
        f"{result.successes}/{len(result.individual_results)} succeeded "
        f"(needed {result.needed_successes}) - {outcome}"
    )

    # Build individual results with character names
    individual_results = []
    for r in result.individual_results:
        individual_results.append({
            "character_name": getattr(r, "character_name", "Unknown"),
            "character_id": getattr(r, "character_id", ""),
            "roll": r.roll,
            "rolls": r.rolls,
            "modifier": r.modifier,
            "total": r.total,
            "success": r.success,
            "critical_success": r.critical_success,
            "critical_failure": r.critical_failure,
        })

    return GroupCheckResultResponse(
        success=result.success,
        skill=result.skill,
        dc=result.dc,
        dc_label=dc_label,
        successes=result.successes,
        failures=result.failures,
        needed_successes=result.needed_successes,
        individual_results=individual_results,
        message=message,
    )


@router.get("/modifiers/{session_id}/{character_id}", response_model=CharacterModifiersResponse)
async def get_character_modifiers(session_id: str, character_id: str):
    """
    Get all skill and saving throw modifiers for a character.

    Useful for displaying character sheets or for the UI to show
    what modifiers apply to different checks.
    """
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    engine = active_sessions[session_id]

    # Find character
    member = None
    for m in engine.session.party:
        if m.id == character_id:
            member = m
            break

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character not found: {character_id}"
        )

    # Calculate ability modifiers
    ability_modifiers = {
        "str": get_ability_modifier(member.strength),
        "dex": get_ability_modifier(member.dexterity),
        "con": get_ability_modifier(member.constitution),
        "int": get_ability_modifier(member.intelligence),
        "wis": get_ability_modifier(member.wisdom),
        "cha": get_ability_modifier(member.charisma),
    }

    proficiency_bonus = get_proficiency_bonus(member.level)

    # Build character stats for modifier calculation
    character_stats = {
        "str": member.strength,
        "dex": member.dexterity,
        "con": member.constitution,
        "int": member.intelligence,
        "wis": member.wisdom,
        "cha": member.charisma,
        "level": member.level,
        "skill_proficiencies": [],  # Would come from character data
        "saving_throw_proficiencies": [],  # Would come from class data
    }

    # Calculate all skill modifiers
    skill_modifiers = {}
    for skill in Skill:
        skill_modifiers[skill.value] = get_skill_modifier(character_stats, skill.value)

    # Calculate saving throw modifiers (ability mod only for now, proficiency needs class data)
    saving_throw_modifiers = {
        "str": ability_modifiers["str"],
        "dex": ability_modifiers["dex"],
        "con": ability_modifiers["con"],
        "int": ability_modifiers["int"],
        "wis": ability_modifiers["wis"],
        "cha": ability_modifiers["cha"],
    }

    return CharacterModifiersResponse(
        character_id=member.id,
        character_name=member.name,
        level=member.level,
        proficiency_bonus=proficiency_bonus,
        ability_modifiers=ability_modifiers,
        skill_modifiers=skill_modifiers,
        saving_throw_modifiers=saving_throw_modifiers,
    )


@router.get("/skills")
async def list_skills():
    """
    Get list of all D&D 5e skills with their associated abilities.

    Useful for building skill check UIs.
    """
    skills = []
    for skill in Skill:
        ability = SKILL_ABILITIES[skill]
        skills.append({
            "id": skill.value,
            "name": get_skill_display_name(skill.value),
            "ability": ability,
            "ability_name": {
                "str": "Strength",
                "dex": "Dexterity",
                "con": "Constitution",
                "int": "Intelligence",
                "wis": "Wisdom",
                "cha": "Charisma",
            }.get(ability, ability.title()),
        })

    return {"skills": skills}


@router.get("/difficulty-classes")
async def list_difficulty_classes():
    """
    Get standard D&D 5e difficulty classes for reference.
    """
    difficulties = []
    for dc in DifficultyClass:
        difficulties.append({
            "name": dc.name.replace("_", " ").title(),
            "dc": dc.value,
            "description": {
                DifficultyClass.TRIVIAL: "A task almost anyone can accomplish",
                DifficultyClass.EASY: "Requires minimal skill or luck",
                DifficultyClass.MEDIUM: "Moderately difficult, requires training or good ability",
                DifficultyClass.HARD: "Challenging even for skilled characters",
                DifficultyClass.VERY_HARD: "Requires exceptional skill or luck",
                DifficultyClass.NEARLY_IMPOSSIBLE: "Only the most exceptional can succeed",
            }.get(dc, ""),
        })

    return {"difficulty_classes": difficulties}


@router.post("/contested")
async def contested_check(
    skill1: str,
    stats1: Dict[str, Any],
    skill2: str,
    stats2: Dict[str, Any],
    advantage1: bool = False,
    disadvantage1: bool = False,
    advantage2: bool = False,
    disadvantage2: bool = False,
):
    """
    Perform a contested skill check between two characters.

    Used for things like Stealth vs Perception, Grapple contests,
    Deception vs Insight, etc.

    Returns both check results and declares a winner.
    """
    # Perform both checks (DC doesn't matter for contested, use 0)
    result1 = perform_skill_check(
        skill=skill1,
        dc=0,
        character_stats=stats1,
        advantage=advantage1,
        disadvantage=disadvantage1,
    )

    result2 = perform_skill_check(
        skill=skill2,
        dc=0,
        character_stats=stats2,
        advantage=advantage2,
        disadvantage=disadvantage2,
    )

    # Determine winner (ties go to reactor in D&D 5e, but we'll just say tie)
    if result1.total > result2.total:
        winner = "character1"
        margin = result1.total - result2.total
    elif result2.total > result1.total:
        winner = "character2"
        margin = result2.total - result1.total
    else:
        winner = "tie"
        margin = 0

    skill_name1 = get_skill_display_name(skill1)
    skill_name2 = get_skill_display_name(skill2)

    return {
        "character1": {
            "skill": skill1,
            "roll": result1.roll,
            "rolls": result1.rolls,
            "modifier": result1.modifier,
            "total": result1.total,
        },
        "character2": {
            "skill": skill2,
            "roll": result2.roll,
            "rolls": result2.rolls,
            "modifier": result2.modifier,
            "total": result2.total,
        },
        "winner": winner,
        "margin": margin,
        "message": (
            f"Contested Check: {skill_name1} ({result1.total}) vs {skill_name2} ({result2.total}) - "
            f"{'Tie!' if winner == 'tie' else f'{winner} wins by {margin}'}"
        ),
    }
