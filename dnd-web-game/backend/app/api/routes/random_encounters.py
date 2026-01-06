"""
Random encounter API routes.

Endpoints for:
- Generating random encounters by terrain and difficulty
- Wandering monster checks
- Reference data (terrains, difficulties)
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from app.core.random_encounters import (
    TerrainType,
    EncounterDifficulty,
    ActivityType,
    RandomEncounterGenerator,
    WanderingMonsterSystem,
    get_encounter_generator,
    get_wandering_system,
    XP_THRESHOLDS,
    CR_XP,
)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class GenerateEncounterRequest(BaseModel):
    """Request to generate a random encounter."""
    terrain: str = Field(..., description="Terrain type: dungeon, forest, mountain, swamp, underdark, urban, plains, coastal, desert, arctic")
    party_level: int = Field(1, ge=1, le=20, description="Average party level")
    party_size: int = Field(4, ge=1, le=10, description="Number of party members")
    difficulty: str = Field("medium", description="Difficulty: easy, medium, hard, deadly")


class WanderingCheckRequest(BaseModel):
    """Request to check for wandering monster encounter."""
    activity: str = Field(..., description="Activity: traveling, resting, exploring, camping, combat, stealth")
    hours_passed: float = Field(1.0, ge=0.1, le=24)
    stealth_modifier: int = Field(0, ge=-20, le=20)
    danger_level: int = Field(0, ge=-5, le=5)
    terrain: str = Field("dungeon")
    party_level: int = Field(1, ge=1, le=20)
    party_size: int = Field(4, ge=1, le=10)


class XPBudgetRequest(BaseModel):
    """Request to calculate XP budget."""
    party_level: int = Field(..., ge=1, le=20)
    party_size: int = Field(..., ge=1, le=10)
    difficulty: str = Field("medium")


# =============================================================================
# Encounter Generation Endpoints
# =============================================================================

@router.post("/generate")
async def generate_random_encounter(request: GenerateEncounterRequest):
    """
    Generate a random encounter for the given parameters.

    Uses D&D 5e encounter balancing based on party level and size.
    """
    # Validate terrain
    try:
        terrain = TerrainType(request.terrain.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid terrain: {request.terrain}. Valid: {[t.value for t in TerrainType]}"
        )

    # Validate difficulty
    try:
        difficulty = EncounterDifficulty(request.difficulty.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid difficulty: {request.difficulty}. Valid: easy, medium, hard, deadly"
        )

    generator = get_encounter_generator()
    encounter = generator.generate_encounter(
        terrain=terrain,
        party_level=request.party_level,
        party_size=request.party_size,
        difficulty=difficulty,
    )

    return {
        "encounter": encounter.to_dict(),
    }


@router.get("/generate")
async def generate_encounter_get(
    terrain: str = "dungeon",
    party_level: int = 1,
    party_size: int = 4,
    difficulty: str = "medium",
):
    """
    Generate a random encounter (GET version for easy testing).
    """
    request = GenerateEncounterRequest(
        terrain=terrain,
        party_level=party_level,
        party_size=party_size,
        difficulty=difficulty,
    )
    return await generate_random_encounter(request)


# =============================================================================
# Wandering Monster Endpoints
# =============================================================================

@router.post("/wandering-check")
async def check_wandering_encounter(request: WanderingCheckRequest):
    """
    Roll to check if a wandering encounter occurs.

    If triggered, also generates the encounter.
    """
    # Validate activity
    try:
        activity = ActivityType(request.activity.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid activity: {request.activity}. Valid: {[a.value for a in ActivityType]}"
        )

    # Validate terrain
    try:
        terrain = TerrainType(request.terrain.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid terrain: {request.terrain}"
        )

    system = get_wandering_system()
    triggered, roll = system.check_for_encounter(
        activity=activity,
        hours_passed=request.hours_passed,
        stealth_modifier=request.stealth_modifier,
        danger_level=request.danger_level,
    )

    response = {
        "encounter_triggered": triggered,
        "roll": roll,
        "activity": activity.value,
        "hours_passed": request.hours_passed,
    }

    if triggered:
        encounter = system.generate_wandering_encounter(
            terrain=terrain,
            party_level=request.party_level,
            party_size=request.party_size,
        )
        response["encounter"] = encounter.to_dict()

    return response


# =============================================================================
# XP Budget Endpoints
# =============================================================================

@router.post("/xp-budget")
async def calculate_xp_budget(request: XPBudgetRequest):
    """
    Calculate XP budget for an encounter.
    """
    try:
        difficulty = EncounterDifficulty(request.difficulty.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid difficulty: {request.difficulty}"
        )

    generator = get_encounter_generator()
    budget = generator.calculate_xp_budget(
        party_level=request.party_level,
        party_size=request.party_size,
        difficulty=difficulty,
    )

    # Get all thresholds for this level
    thresholds = XP_THRESHOLDS.get(request.party_level, XP_THRESHOLDS[1])

    return {
        "xp_budget": budget,
        "difficulty": difficulty.value,
        "party_level": request.party_level,
        "party_size": request.party_size,
        "thresholds_per_character": {
            "easy": thresholds[0],
            "medium": thresholds[1],
            "hard": thresholds[2],
            "deadly": thresholds[3],
        },
        "party_thresholds": {
            "easy": thresholds[0] * request.party_size,
            "medium": thresholds[1] * request.party_size,
            "hard": thresholds[2] * request.party_size,
            "deadly": thresholds[3] * request.party_size,
        },
    }


# =============================================================================
# Reference Endpoints
# =============================================================================

@router.get("/terrains")
async def list_terrains():
    """
    Get all available terrain types.
    """
    return {
        "terrains": [
            {
                "value": t.value,
                "name": t.value.replace("_", " ").title(),
            }
            for t in TerrainType
        ],
    }


@router.get("/difficulties")
async def list_difficulties():
    """
    Get all encounter difficulty levels.
    """
    return {
        "difficulties": [
            {
                "value": d.value,
                "name": d.value.title(),
            }
            for d in EncounterDifficulty
        ],
    }


@router.get("/activities")
async def list_activities():
    """
    Get all activity types for wandering checks.
    """
    from app.core.random_encounters import WanderingMonsterSystem

    return {
        "activities": [
            {
                "value": a.value,
                "name": a.value.replace("_", " ").title(),
                "base_encounter_chance": WanderingMonsterSystem.ENCOUNTER_CHANCES.get(a, 10),
            }
            for a in ActivityType
        ],
    }


@router.get("/cr-xp")
async def get_cr_xp_table():
    """
    Get the CR to XP mapping table.
    """
    return {
        "cr_xp": {str(k): v for k, v in CR_XP.items()},
    }


@router.get("/xp-thresholds")
async def get_xp_thresholds():
    """
    Get XP thresholds by character level.
    """
    return {
        "thresholds": {
            level: {
                "easy": thresholds[0],
                "medium": thresholds[1],
                "hard": thresholds[2],
                "deadly": thresholds[3],
            }
            for level, thresholds in XP_THRESHOLDS.items()
        },
    }
