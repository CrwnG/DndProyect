"""
Map Generation API Routes.

Handles procedural battlemap generation for D&D 5e encounters.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

from app.core.map_generation import (
    DungeonGenerator,
    DifficultyLevel,
    RoomType,
    generate_battlemap,
)

router = APIRouter(prefix="/maps", tags=["map_generation"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class GenerateMapRequest(BaseModel):
    """Request to generate a battlemap."""
    party_level: int = Field(default=1, ge=1, le=20, description="Average party level")
    party_size: int = Field(default=4, ge=1, le=8, description="Number of party members")
    difficulty: str = Field(default="medium", description="Encounter difficulty")
    room_type: Optional[str] = Field(default=None, description="Specific room type")
    num_rooms: int = Field(default=1, ge=1, le=5, description="Number of rooms")
    seed: Optional[int] = Field(default=None, description="Random seed")


class MapResponse(BaseModel):
    """Response containing generated map data."""
    success: bool
    map: Dict[str, Any]
    message: str = ""


class RoomTypesResponse(BaseModel):
    """Response listing available room types."""
    success: bool
    room_types: List[Dict[str, str]]


class DifficultyLevelsResponse(BaseModel):
    """Response listing available difficulty levels."""
    success: bool
    difficulty_levels: List[Dict[str, str]]


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/generate", response_model=MapResponse)
async def generate_map(request: GenerateMapRequest):
    """
    Generate a procedural battlemap.

    Creates a tactical battlemap using BSP algorithm with:
    - Terrain features (pillars, water, pits, etc.)
    - Spawn points for players and enemies
    - Difficulty-scaled sizing and hazards

    Returns grid data compatible with the combat system.
    """
    try:
        # Validate difficulty
        try:
            difficulty = request.difficulty.lower()
            if difficulty not in ["easy", "medium", "hard", "deadly"]:
                raise ValueError(f"Invalid difficulty: {difficulty}")
        except Exception:
            difficulty = "medium"

        # Validate room type
        room_type = None
        if request.room_type:
            try:
                room_type = request.room_type.lower()
                valid_types = [rt.value for rt in RoomType]
                if room_type not in valid_types:
                    raise ValueError(f"Invalid room type: {room_type}")
            except Exception:
                room_type = None

        # Generate the map
        generated_map = generate_battlemap(
            party_level=request.party_level,
            party_size=request.party_size,
            difficulty=difficulty,
            room_type=room_type,
            num_rooms=request.num_rooms,
            seed=request.seed,
        )

        return MapResponse(
            success=True,
            map=generated_map.to_dict(),
            message=f"Generated {generated_map.difficulty.value} battlemap for level {request.party_level} party"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Map generation failed: {str(e)}")


@router.get("/generate", response_model=MapResponse)
async def generate_map_get(
    party_level: int = Query(default=1, ge=1, le=20),
    party_size: int = Query(default=4, ge=1, le=8),
    difficulty: str = Query(default="medium"),
    room_type: Optional[str] = Query(default=None),
    num_rooms: int = Query(default=1, ge=1, le=5),
    seed: Optional[int] = Query(default=None),
):
    """
    Generate a procedural battlemap (GET version for convenience).
    """
    request = GenerateMapRequest(
        party_level=party_level,
        party_size=party_size,
        difficulty=difficulty,
        room_type=room_type,
        num_rooms=num_rooms,
        seed=seed,
    )
    return await generate_map(request)


@router.get("/room-types", response_model=RoomTypesResponse)
async def list_room_types():
    """
    List all available room types.

    Each room type has different terrain generation rules
    and spawn point configurations.
    """
    room_types = [
        {"id": rt.value, "name": rt.value.replace("_", " ").title()}
        for rt in RoomType
    ]

    return RoomTypesResponse(
        success=True,
        room_types=room_types
    )


@router.get("/difficulty-levels", response_model=DifficultyLevelsResponse)
async def list_difficulty_levels():
    """
    List all available difficulty levels.

    Difficulty affects map size, enemy count, hazard density,
    and cover availability.
    """
    difficulty_levels = [
        {"id": dl.value, "name": dl.value.title()}
        for dl in DifficultyLevel
    ]

    return DifficultyLevelsResponse(
        success=True,
        difficulty_levels=difficulty_levels
    )


@router.get("/{map_id}", response_model=MapResponse)
async def get_map(map_id: str):
    """
    Get a previously generated map by ID.

    Note: This is a placeholder. Full implementation would require
    map storage/caching system.
    """
    # For now, we don't store generated maps
    # This endpoint could be extended to retrieve cached maps
    raise HTTPException(
        status_code=404,
        detail=f"Map '{map_id}' not found. Maps are not currently persisted."
    )


@router.post("/preview", response_model=Dict[str, Any])
async def preview_encounter_params(request: GenerateMapRequest):
    """
    Preview encounter parameters without generating a full map.

    Useful for understanding what will be generated before
    committing to map generation.
    """
    try:
        difficulty = DifficultyLevel(request.difficulty.lower())
    except Exception:
        difficulty = DifficultyLevel.MEDIUM

    from app.core.map_generation.difficulty_scaler import DifficultyScaler

    scaler = DifficultyScaler(
        party_level=request.party_level,
        party_size=request.party_size,
        difficulty=difficulty
    )

    params = scaler.calculate_encounter()

    return {
        "success": True,
        "preview": {
            "map_width": params.map_width,
            "map_height": params.map_height,
            "num_enemies": params.num_enemies,
            "enemy_cr": round(params.enemy_cr, 2),
            "num_hazards": params.num_hazards,
            "trap_dc": params.trap_dc,
            "has_boss": params.has_boss,
            "difficulty": params.difficulty.value,
            "xp_budget": scaler.get_xp_budget(),
            "tier": scaler.tier,
        },
        "message": f"Preview for {request.difficulty} encounter (level {request.party_level}, {request.party_size} players)"
    }
