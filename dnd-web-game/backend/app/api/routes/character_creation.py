"""
Character Creation API Routes.

Provides endpoints for step-by-step character creation using D&D 2024 rules.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

from app.services.rules_loader import get_rules_loader
from app.core.character_builder import (
    CharacterBuilder,
    CharacterBuild,
    ValidationResult,
    CreationStep,
)

router = APIRouter()

# Singleton builder instance
_builder = CharacterBuilder()


# ==================== Request/Response Models ====================

class SetSpeciesRequest(BaseModel):
    """Request to set character species."""
    build_id: str
    species_id: str
    size: Optional[str] = None  # For species that allow size choice


class SetClassRequest(BaseModel):
    """Request to set character class."""
    build_id: str
    class_id: str
    skill_choices: Optional[List[str]] = None


class SetBackgroundRequest(BaseModel):
    """Request to set character background."""
    build_id: str
    background_id: str


class SetAbilityScoresRequest(BaseModel):
    """Request to set ability scores."""
    build_id: str
    scores: Dict[str, int]
    method: str = "point_buy"  # "point_buy" or "standard_array"
    bonuses: Dict[str, int]  # Background bonuses (+2/+1 or +1/+1/+1)


class SetFeatRequest(BaseModel):
    """Request to set origin feat."""
    build_id: str
    feat_id: str


class SetEquipmentRequest(BaseModel):
    """Request to set equipment choices."""
    build_id: str
    choices: List[Dict[str, Any]]


class SetDetailsRequest(BaseModel):
    """Request to set character details."""
    build_id: str
    name: str
    appearance: Optional[str] = None
    personality: Optional[str] = None
    backstory: Optional[str] = None


class SetFightingStyleRequest(BaseModel):
    """Request to set fighting style."""
    build_id: str
    style_id: str


class SetWeaponMasteriesRequest(BaseModel):
    """Request to set weapon masteries."""
    build_id: str
    weapons: List[str]


class SetLevelRequest(BaseModel):
    """Request to set character level."""
    build_id: str
    level: int = Field(ge=1, le=20, default=1)


class BuildResponse(BaseModel):
    """Response containing build state."""
    build_id: str
    current_step: str
    build: Dict[str, Any]


class ValidationResponse(BaseModel):
    """Response containing validation result."""
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    data: Dict[str, Any] = {}


# ==================== Data Endpoints ====================

@router.get("/species")
async def get_all_species():
    """Get all available species with summaries."""
    rules = get_rules_loader()
    return {
        "species": rules.get_species_summary(),
        "count": len(rules.get_all_species())
    }


@router.get("/species/{species_id}")
async def get_species(species_id: str):
    """Get full details for a specific species."""
    rules = get_rules_loader()
    species = rules.get_species(species_id)

    if not species:
        raise HTTPException(status_code=404, detail=f"Species not found: {species_id}")

    return species


@router.get("/classes")
async def get_all_classes():
    """Get all available classes with summaries."""
    rules = get_rules_loader()
    return {
        "classes": rules.get_class_summary(),
        "count": len(rules.get_all_classes())
    }


@router.get("/classes/{class_id}")
async def get_class(class_id: str):
    """Get full details for a specific class."""
    rules = get_rules_loader()
    class_data = rules.get_class(class_id)

    if not class_data:
        raise HTTPException(status_code=404, detail=f"Class not found: {class_id}")

    return class_data


@router.get("/classes/{class_id}/features")
async def get_class_features(class_id: str, level: int = Query(default=1, ge=1, le=20)):
    """Get class features available at a specific level."""
    rules = get_rules_loader()
    features = rules.get_class_features_at_level(class_id, level)

    if not features and not rules.get_class(class_id):
        raise HTTPException(status_code=404, detail=f"Class not found: {class_id}")

    return {"features": features, "level": level}


@router.get("/classes/{class_id}/equipment")
async def get_class_equipment(class_id: str):
    """Get starting equipment choices for a class."""
    rules = get_rules_loader()
    equipment = rules.get_class_equipment_choices(class_id)

    if not equipment.get("choices") and not rules.get_class(class_id):
        raise HTTPException(status_code=404, detail=f"Class not found: {class_id}")

    return equipment


@router.get("/backgrounds")
async def get_all_backgrounds():
    """Get all available backgrounds with summaries."""
    rules = get_rules_loader()
    return {
        "backgrounds": rules.get_background_summary(),
        "count": len(rules.get_all_backgrounds())
    }


@router.get("/backgrounds/{background_id}")
async def get_background(background_id: str):
    """Get full details for a specific background."""
    rules = get_rules_loader()
    background = rules.get_background(background_id)

    if not background:
        raise HTTPException(status_code=404, detail=f"Background not found: {background_id}")

    return background


@router.get("/feats/origin")
async def get_origin_feats():
    """Get all origin feats."""
    rules = get_rules_loader()
    return {
        "feats": rules.get_origin_feats(),
        "count": len(rules.get_origin_feats())
    }


@router.get("/feats/general")
async def get_general_feats():
    """Get all general feats."""
    rules = get_rules_loader()
    return {
        "feats": rules.get_general_feats(),
        "count": len(rules.get_general_feats())
    }


@router.get("/feats/{feat_id}")
async def get_feat(feat_id: str):
    """Get details for a specific feat."""
    rules = get_rules_loader()
    feat = rules.get_feat(feat_id)

    if not feat:
        raise HTTPException(status_code=404, detail=f"Feat not found: {feat_id}")

    return feat


@router.get("/ability-scores/point-buy")
async def get_point_buy_info():
    """Get point buy rules and costs."""
    return {
        "total_points": 27,
        "min_score": 8,
        "max_score": 15,
        "costs": {
            8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9
        },
        "abilities": ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
    }


@router.get("/ability-scores/standard-array")
async def get_standard_array():
    """Get the standard array values."""
    rules = get_rules_loader()
    return {
        "values": rules.get_standard_array(),
        "abilities": ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
    }


# ==================== Build Management ====================

@router.post("/build/new")
async def create_new_build():
    """Start a new character build."""
    build = _builder.create_new_build()

    return {
        "build_id": build.id,
        "current_step": build.get_current_step().value,
        "message": "New character build started"
    }


@router.get("/build/{build_id}")
async def get_build(build_id: str):
    """Get the current state of a build."""
    build = _builder.get_build(build_id)

    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {build_id}")

    return {
        "build_id": build.id,
        "current_step": build.get_current_step().value,
        "species_id": build.species_id,
        "class_id": build.class_id,
        "background_id": build.background_id,
        "level": build.level,
        "ability_scores": build.ability_scores,
        "ability_bonuses": build.ability_bonuses,
        "final_scores": build.get_final_ability_scores(),
        "modifiers": build.get_ability_modifiers(),
        "origin_feat_id": build.origin_feat_id,
        "skill_choices": build.skill_choices,
        "equipment_choices": build.equipment_choices,
        "fighting_style": build.fighting_style,
        "weapon_masteries": build.weapon_masteries,
        "name": build.name,
        "size": build.size,
        "ability_method": build.ability_method
    }


@router.delete("/build/{build_id}")
async def delete_build(build_id: str):
    """Delete a character build."""
    if _builder.delete_build(build_id):
        return {"success": True, "message": "Build deleted"}
    else:
        raise HTTPException(status_code=404, detail=f"Build not found: {build_id}")


# ==================== Build Steps ====================

@router.post("/build/species")
async def set_species(request: SetSpeciesRequest):
    """Set the species for a character build."""
    build = _builder.get_build(request.build_id)
    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {request.build_id}")

    result = _builder.set_species(build, request.species_id)

    if not result.valid:
        raise HTTPException(status_code=400, detail=result.errors)

    # Set size if provided and required
    if request.size and result.data.get("size_choice_required"):
        size_result = _builder.set_size_choice(build, request.size)
        if not size_result.valid:
            raise HTTPException(status_code=400, detail=size_result.errors)

    return {
        "success": True,
        "current_step": build.get_current_step().value,
        "data": result.data
    }


@router.post("/build/class")
async def set_class(request: SetClassRequest):
    """Set the class for a character build."""
    build = _builder.get_build(request.build_id)
    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {request.build_id}")

    result = _builder.set_class(build, request.class_id)

    if not result.valid:
        raise HTTPException(status_code=400, detail=result.errors)

    # Set skill choices if provided
    if request.skill_choices:
        skill_result = _builder.set_skill_choices(build, request.skill_choices)
        if not skill_result.valid:
            raise HTTPException(status_code=400, detail=skill_result.errors)

    return {
        "success": True,
        "current_step": build.get_current_step().value,
        "data": result.data
    }


@router.post("/build/skills")
async def set_skill_choices(build_id: str, skills: List[str]):
    """Set skill proficiency choices."""
    build = _builder.get_build(build_id)
    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {build_id}")

    result = _builder.set_skill_choices(build, skills)

    if not result.valid:
        raise HTTPException(status_code=400, detail=result.errors)

    return {"success": True}


@router.post("/build/background")
async def set_background(request: SetBackgroundRequest):
    """Set the background for a character build."""
    build = _builder.get_build(request.build_id)
    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {request.build_id}")

    result = _builder.set_background(build, request.background_id)

    if not result.valid:
        raise HTTPException(status_code=400, detail=result.errors)

    return {
        "success": True,
        "current_step": build.get_current_step().value,
        "data": result.data
    }


@router.post("/build/abilities")
async def set_ability_scores(request: SetAbilityScoresRequest):
    """Set ability scores and background bonuses."""
    build = _builder.get_build(request.build_id)
    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {request.build_id}")

    # Set base scores
    scores_result = _builder.set_ability_scores(build, request.scores, request.method)
    if not scores_result.valid:
        raise HTTPException(status_code=400, detail=scores_result.errors)

    # Set background bonuses
    bonuses_result = _builder.set_ability_bonuses(build, request.bonuses)
    if not bonuses_result.valid:
        raise HTTPException(status_code=400, detail=bonuses_result.errors)

    return {
        "success": True,
        "current_step": build.get_current_step().value,
        "final_scores": build.get_final_ability_scores(),
        "modifiers": build.get_ability_modifiers(),
        "data": {**scores_result.data, **bonuses_result.data}
    }


@router.post("/build/feat")
async def set_origin_feat(request: SetFeatRequest):
    """Set the origin feat for a character build."""
    build = _builder.get_build(request.build_id)
    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {request.build_id}")

    result = _builder.set_origin_feat(build, request.feat_id)

    if not result.valid:
        raise HTTPException(status_code=400, detail=result.errors)

    return {
        "success": True,
        "current_step": build.get_current_step().value,
        "data": result.data
    }


@router.post("/build/equipment")
async def set_equipment(request: SetEquipmentRequest):
    """Set equipment choices for a character build."""
    build = _builder.get_build(request.build_id)
    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {request.build_id}")

    result = _builder.set_equipment_choices(build, request.choices)

    if not result.valid:
        raise HTTPException(status_code=400, detail=result.errors)

    return {
        "success": True,
        "current_step": build.get_current_step().value
    }


@router.post("/build/fighting-style")
async def set_fighting_style(request: SetFightingStyleRequest):
    """Set fighting style for applicable classes."""
    build = _builder.get_build(request.build_id)
    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {request.build_id}")

    result = _builder.set_fighting_style(build, request.style_id)

    if not result.valid:
        raise HTTPException(status_code=400, detail=result.errors)

    return {"success": True}


@router.post("/build/weapon-masteries")
async def set_weapon_masteries(request: SetWeaponMasteriesRequest):
    """Set weapon mastery choices for applicable classes."""
    build = _builder.get_build(request.build_id)
    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {request.build_id}")

    result = _builder.set_weapon_masteries(build, request.weapons)

    if not result.valid:
        raise HTTPException(status_code=400, detail=result.errors)

    return {"success": True}


@router.post("/build/details")
async def set_details(request: SetDetailsRequest):
    """Set character details (name, appearance, etc.)."""
    build = _builder.get_build(request.build_id)
    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {request.build_id}")

    result = _builder.set_details(
        build,
        request.name,
        request.appearance,
        request.personality,
        request.backstory
    )

    if not result.valid:
        raise HTTPException(status_code=400, detail=result.errors)

    return {
        "success": True,
        "current_step": build.get_current_step().value
    }


@router.post("/build/level")
async def set_level(request: SetLevelRequest):
    """Set character level (1-20)."""
    build = _builder.get_build(request.build_id)
    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {request.build_id}")

    result = _builder.set_level(build, request.level)

    if not result.valid:
        raise HTTPException(status_code=400, detail=result.errors)

    return {
        "success": True,
        "level": build.level
    }


# ==================== Validation & Finalization ====================

@router.get("/build/{build_id}/validate")
async def validate_build(build_id: str):
    """Validate the current build state."""
    build = _builder.get_build(build_id)
    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {build_id}")

    result = _builder.validate_build(build)

    return {
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "current_step": build.get_current_step().value
    }


@router.post("/build/{build_id}/finalize")
async def finalize_build(build_id: str):
    """Finalize the build and create the character."""
    build = _builder.get_build(build_id)
    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {build_id}")

    success, result = _builder.finalize_character(build)

    if not success:
        raise HTTPException(status_code=400, detail=result.get("errors", ["Unknown error"]))

    # Store the created character (could be moved to character storage)
    from app.api.routes.character import imported_characters
    imported_characters[result["id"]] = {
        "raw": result,
        "combatant": result,
        "source": "character_builder",
        "build_id": build_id
    }

    return {
        "success": True,
        "character_id": result["id"],
        "character": result,
        "message": f"Successfully created {result['name']}"
    }


@router.get("/build/{build_id}/preview")
async def preview_build(build_id: str):
    """Preview what the finalized character would look like."""
    build = _builder.get_build(build_id)
    if not build:
        raise HTTPException(status_code=404, detail=f"Build not found: {build_id}")

    success, result = _builder.finalize_character(build)

    if not success:
        # Still return what we can preview
        return {
            "complete": False,
            "missing": result.get("errors", []),
            "preview": None
        }

    return {
        "complete": True,
        "missing": [],
        "preview": result
    }
