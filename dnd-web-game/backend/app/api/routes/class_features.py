"""
Class Features API Routes.

Endpoints for using class-specific abilities in combat:
- Monk Ki abilities (Flurry of Blows, Stunning Strike, etc.)
- Druid Wild Shape transformations
- Sorcerer Metamagic and Sorcery Points
- Warlock Eldritch Invocations
- Barbarian Rage and Reckless Attack
- Paladin Lay on Hands
- Rogue Cunning Action
- Bard Bardic Inspiration
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from app.core.combat_storage import active_combats, active_grids

# Import class feature systems
from app.core.ki_system import (
    KiState,
    KI_ABILITIES,
    initialize_ki_state,
    can_use_ability,
    use_ki_ability,
    get_available_ki_abilities,
    get_ki_ability_summary,
    resolve_stunning_strike,
    reset_turn_tracking,
)
from app.core.wild_shape import (
    WildShapeState,
    BEAST_FORMS,
    get_available_forms,
    transform as wild_shape_transform,
    revert as wild_shape_revert,
    take_damage_in_form,
    get_wild_shape_uses,
)
from app.core.sorcerer_features import (
    SorceryPointState,
    METAMAGIC_OPTIONS,
    MetamagicType,
    get_max_sorcery_points,
    initialize_sorcery_state,
    can_use_metamagic,
    apply_metamagic,
    convert_slot_to_points,
    convert_points_to_slot,
    SLOT_TO_POINTS,
    POINTS_TO_SLOT,
)
from app.core.warlock_features import (
    ELDRITCH_INVOCATIONS,
    PACT_BOONS,
    get_available_invocations,
    has_invocation,
    calculate_eldritch_blast_damage,
    get_warlock_pact_slots,
)
from app.core.class_features import (
    use_rage,
    use_reckless_attack,
    get_rage_damage_bonus,
    get_rage_uses,
    use_lay_on_hands,
    get_lay_on_hands_pool,
    use_bardic_inspiration,
    get_bardic_inspiration_die,
    calculate_sneak_attack_dice,
    get_channel_divinity_uses,
    use_turn_undead,
)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class KiAbilityRequest(BaseModel):
    """Request to use a Ki ability."""
    combatant_id: str
    target_id: Optional[str] = None
    ki_spent: Optional[int] = None  # For variable-cost abilities like Focused Aim


class KiStatusResponse(BaseModel):
    """Response with Ki status."""
    combatant_id: str
    current_ki: int
    max_ki: int
    ki_save_dc: int
    martial_arts_die: str
    available_abilities: List[Dict[str, Any]]


class WildShapeTransformRequest(BaseModel):
    """Request to transform via Wild Shape."""
    combatant_id: str
    form_id: str


class WildShapeResponse(BaseModel):
    """Response from Wild Shape action."""
    success: bool
    description: str
    form_data: Optional[Dict[str, Any]] = None
    combat_state: Dict[str, Any]


class MetamagicRequest(BaseModel):
    """Request to apply Metamagic to a spell."""
    combatant_id: str
    metamagic_type: str
    spell_id: str
    spell_level: int = 1
    extra_data: Dict[str, Any] = Field(default_factory=dict)


class SorceryPointRequest(BaseModel):
    """Request for sorcery point operations."""
    combatant_id: str
    operation: str  # "slot_to_points" or "points_to_slot"
    slot_level: Optional[int] = None


class RageRequest(BaseModel):
    """Request to enter Rage."""
    combatant_id: str


class RecklessAttackRequest(BaseModel):
    """Request to use Reckless Attack."""
    combatant_id: str


class LayOnHandsRequest(BaseModel):
    """Request to use Lay on Hands."""
    combatant_id: str
    target_id: str
    points_to_spend: int
    cure_disease: bool = False
    cure_poison: bool = False


class BardicInspirationRequest(BaseModel):
    """Request to grant Bardic Inspiration."""
    combatant_id: str
    target_id: str


class CunningActionRequest(BaseModel):
    """Request to use Cunning Action."""
    combatant_id: str
    action_type: str  # "dash", "disengage", "hide"


class ChannelDivinityRequest(BaseModel):
    """Request to use Channel Divinity."""
    combatant_id: str
    option: str = "turn_undead"  # "turn_undead", "destroy_undead", or subclass-specific


class ClassFeatureResponse(BaseModel):
    """Generic response from using a class feature."""
    success: bool
    description: str
    damage_dealt: int = 0
    healing_done: int = 0
    effects_applied: List[str] = Field(default_factory=list)
    extra_data: Dict[str, Any] = Field(default_factory=dict)
    combat_state: Dict[str, Any]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_combat_and_validate(combat_id: str, combatant_id: str):
    """Get combat engine and validate combatant exists."""
    engine = active_combats.get(combat_id)
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    combatant = engine.state.initiative_tracker.get_combatant(combatant_id)
    if not combatant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combatant not found"
        )

    return engine, combatant


def get_combatant_class(engine, combatant_id: str) -> str:
    """Get the class of a combatant."""
    stats = engine.state.combatant_stats.get(combatant_id, {})
    return stats.get("class", "").lower()


def get_combatant_level(engine, combatant_id: str) -> int:
    """Get the level of a combatant."""
    stats = engine.state.combatant_stats.get(combatant_id, {})
    return stats.get("level", 1)


def get_or_create_ki_state(engine, combatant_id: str) -> KiState:
    """Get or initialize Ki state for a monk."""
    stats = engine.state.combatant_stats.get(combatant_id, {})

    ki_data = stats.get("ki_state")
    if ki_data:
        return KiState.from_dict(ki_data)

    # Initialize new Ki state
    level = stats.get("level", 1)
    abilities = stats.get("abilities", {})
    wisdom = abilities.get("wisdom", 10)
    proficiency = 2 + ((level - 1) // 4)

    return initialize_ki_state(level, wisdom, proficiency)


def save_ki_state(engine, combatant_id: str, state: KiState):
    """Save Ki state back to combatant stats."""
    if combatant_id not in engine.state.combatant_stats:
        engine.state.combatant_stats[combatant_id] = {}
    engine.state.combatant_stats[combatant_id]["ki_state"] = state.to_dict()


def get_or_create_wild_shape_state(engine, combatant_id: str) -> WildShapeState:
    """Get or initialize Wild Shape state for a druid."""
    stats = engine.state.combatant_stats.get(combatant_id, {})

    ws_data = stats.get("wild_shape_state")
    if ws_data:
        return WildShapeState.from_dict(ws_data)

    # Initialize new Wild Shape state
    level = stats.get("level", 1)
    return WildShapeState(
        uses_remaining=get_wild_shape_uses(level),
        max_uses=get_wild_shape_uses(level),
    )


def save_wild_shape_state(engine, combatant_id: str, state: WildShapeState):
    """Save Wild Shape state back to combatant stats."""
    if combatant_id not in engine.state.combatant_stats:
        engine.state.combatant_stats[combatant_id] = {}
    engine.state.combatant_stats[combatant_id]["wild_shape_state"] = state.to_dict()


def get_or_create_sorcery_state(engine, combatant_id: str) -> SorceryPointState:
    """Get or initialize Sorcery Point state for a sorcerer."""
    stats = engine.state.combatant_stats.get(combatant_id, {})

    sp_data = stats.get("sorcery_state")
    if sp_data:
        return SorceryPointState.from_dict(sp_data)

    level = stats.get("level", 1)
    return initialize_sorcery_state(level)


def save_sorcery_state(engine, combatant_id: str, state: SorceryPointState):
    """Save Sorcery Point state back to combatant stats."""
    if combatant_id not in engine.state.combatant_stats:
        engine.state.combatant_stats[combatant_id] = {}
    engine.state.combatant_stats[combatant_id]["sorcery_state"] = state.to_dict()


# =============================================================================
# MONK KI ENDPOINTS
# =============================================================================

@router.get("/{combat_id}/ki/status/{combatant_id}", response_model=KiStatusResponse)
async def get_ki_status(combat_id: str, combatant_id: str):
    """Get current Ki status for a monk."""
    engine, combatant = get_combat_and_validate(combat_id, combatant_id)

    char_class = get_combatant_class(engine, combatant_id)
    if char_class != "monk":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only monks have Ki points"
        )

    level = get_combatant_level(engine, combatant_id)
    ki_state = get_or_create_ki_state(engine, combatant_id)

    return KiStatusResponse(
        combatant_id=combatant_id,
        current_ki=ki_state.current_ki,
        max_ki=ki_state.max_ki,
        ki_save_dc=ki_state.ki_save_dc,
        martial_arts_die=ki_state.martial_arts_die,
        available_abilities=get_ki_ability_summary(level)
    )


@router.post("/{combat_id}/ki/flurry-of-blows", response_model=ClassFeatureResponse)
async def use_flurry_of_blows(combat_id: str, request: KiAbilityRequest):
    """
    Use Flurry of Blows (1 Ki).

    Immediately after taking the Attack action, make two unarmed strikes
    as a bonus action.
    """
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    char_class = get_combatant_class(engine, request.combatant_id)
    if char_class != "monk":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only monks can use Flurry of Blows"
        )

    level = get_combatant_level(engine, request.combatant_id)
    ki_state = get_or_create_ki_state(engine, request.combatant_id)

    success, message, effect_data = use_ki_ability(ki_state, "flurry_of_blows", level)

    if success:
        save_ki_state(engine, request.combatant_id, ki_state)

        # Mark that this combatant can make 2 bonus action attacks
        stats = engine.state.combatant_stats.get(request.combatant_id, {})
        stats["flurry_attacks_remaining"] = 2
        engine.state.combatant_stats[request.combatant_id] = stats

        engine.state.add_event(
            "ki_ability",
            f"{combatant.name} uses Flurry of Blows!",
            combatant_id=request.combatant_id,
            data=effect_data
        )

    return ClassFeatureResponse(
        success=success,
        description=message,
        effects_applied=["flurry_of_blows"] if success else [],
        extra_data=effect_data,
        combat_state=engine.get_combat_state()
    )


@router.post("/{combat_id}/ki/patient-defense", response_model=ClassFeatureResponse)
async def use_patient_defense(combat_id: str, request: KiAbilityRequest):
    """
    Use Patient Defense (1 Ki).

    Take the Dodge action as a bonus action.
    """
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    char_class = get_combatant_class(engine, request.combatant_id)
    if char_class != "monk":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only monks can use Patient Defense"
        )

    level = get_combatant_level(engine, request.combatant_id)
    ki_state = get_or_create_ki_state(engine, request.combatant_id)

    success, message, effect_data = use_ki_ability(ki_state, "patient_defense", level)

    if success:
        save_ki_state(engine, request.combatant_id, ki_state)

        # Apply Dodge condition
        stats = engine.state.combatant_stats.get(request.combatant_id, {})
        conditions = stats.get("conditions", [])
        if "dodging" not in conditions:
            conditions.append("dodging")
        stats["conditions"] = conditions
        engine.state.combatant_stats[request.combatant_id] = stats

        engine.state.add_event(
            "ki_ability",
            f"{combatant.name} uses Patient Defense (Dodge)!",
            combatant_id=request.combatant_id,
            data=effect_data
        )

    return ClassFeatureResponse(
        success=success,
        description=message,
        effects_applied=["dodging"] if success else [],
        extra_data=effect_data,
        combat_state=engine.get_combat_state()
    )


@router.post("/{combat_id}/ki/step-of-the-wind", response_model=ClassFeatureResponse)
async def use_step_of_the_wind(combat_id: str, request: KiAbilityRequest):
    """
    Use Step of the Wind (1 Ki).

    Take Dash or Disengage as a bonus action, and double jump distance.
    """
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    char_class = get_combatant_class(engine, request.combatant_id)
    if char_class != "monk":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only monks can use Step of the Wind"
        )

    level = get_combatant_level(engine, request.combatant_id)
    ki_state = get_or_create_ki_state(engine, request.combatant_id)

    success, message, effect_data = use_ki_ability(ki_state, "step_of_the_wind", level)

    if success:
        save_ki_state(engine, request.combatant_id, ki_state)

        # Double movement for this turn
        stats = engine.state.combatant_stats.get(request.combatant_id, {})
        base_speed = stats.get("speed", 30)
        stats["movement_remaining"] = stats.get("movement_remaining", base_speed) + base_speed
        stats["step_of_wind_active"] = True
        engine.state.combatant_stats[request.combatant_id] = stats

        engine.state.add_event(
            "ki_ability",
            f"{combatant.name} uses Step of the Wind (Dash + Disengage)!",
            combatant_id=request.combatant_id,
            data=effect_data
        )

    return ClassFeatureResponse(
        success=success,
        description=message,
        effects_applied=["dash", "disengage"] if success else [],
        extra_data=effect_data,
        combat_state=engine.get_combat_state()
    )


@router.post("/{combat_id}/ki/stunning-strike", response_model=ClassFeatureResponse)
async def use_stunning_strike(combat_id: str, request: KiAbilityRequest):
    """
    Use Stunning Strike (1 Ki).

    When you hit with a melee attack, the target must make a CON save
    or be stunned until end of your next turn.
    """
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    if not request.target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_id is required for Stunning Strike"
        )

    target = engine.state.initiative_tracker.get_combatant(request.target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found"
        )

    char_class = get_combatant_class(engine, request.combatant_id)
    if char_class != "monk":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only monks can use Stunning Strike"
        )

    level = get_combatant_level(engine, request.combatant_id)
    ki_state = get_or_create_ki_state(engine, request.combatant_id)

    success, message, effect_data = use_ki_ability(ki_state, "stunning_strike", level)

    if not success:
        return ClassFeatureResponse(
            success=False,
            description=message,
            combat_state=engine.get_combat_state()
        )

    save_ki_state(engine, request.combatant_id, ki_state)

    # Resolve the saving throw
    target_stats = engine.state.combatant_stats.get(request.target_id, {})
    target_abilities = target_stats.get("abilities", {})
    target_con = target_abilities.get("constitution", 10)
    target_level = target_stats.get("level", 1)

    # Check if target is proficient in CON saves (monsters often are)
    target_proficient = target_stats.get("proficient_con_save", False)

    stunned, roll, description = resolve_stunning_strike(
        target_con_score=target_con,
        target_proficient_con_save=target_proficient,
        target_level=target_level,
        ki_save_dc=ki_state.ki_save_dc
    )

    effects_applied = []
    if stunned:
        # Apply stunned condition to target
        target_conditions = target_stats.get("conditions", [])
        if "stunned" not in target_conditions:
            target_conditions.append("stunned")
        target_stats["conditions"] = target_conditions
        target_stats["stunned_until"] = "end_of_next_turn"
        engine.state.combatant_stats[request.target_id] = target_stats
        effects_applied.append("stunned")

    effect_data["save_result"] = {
        "roll": roll,
        "stunned": stunned,
        "description": description
    }

    engine.state.add_event(
        "ki_ability",
        f"{combatant.name} uses Stunning Strike on {target.name}! {description}",
        combatant_id=request.combatant_id,
        data=effect_data
    )

    return ClassFeatureResponse(
        success=True,
        description=f"Stunning Strike: {description}",
        effects_applied=effects_applied,
        extra_data=effect_data,
        combat_state=engine.get_combat_state()
    )


# =============================================================================
# DRUID WILD SHAPE ENDPOINTS
# =============================================================================

@router.get("/{combat_id}/wild-shape/available-forms/{combatant_id}")
async def get_available_wild_shapes(combat_id: str, combatant_id: str):
    """Get available Wild Shape forms for a druid."""
    engine, combatant = get_combat_and_validate(combat_id, combatant_id)

    char_class = get_combatant_class(engine, combatant_id)
    if char_class != "druid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only druids can use Wild Shape"
        )

    level = get_combatant_level(engine, combatant_id)
    stats = engine.state.combatant_stats.get(combatant_id, {})
    circle = stats.get("subclass", "land")

    ws_state = get_or_create_wild_shape_state(engine, combatant_id)
    forms = get_available_forms(level, circle)

    return {
        "combatant_id": combatant_id,
        "uses_remaining": ws_state.uses_remaining,
        "max_uses": ws_state.max_uses,
        "is_transformed": ws_state.is_active,
        "current_form": ws_state.form_id,
        "available_forms": [f.to_dict() for f in forms]
    }


@router.post("/{combat_id}/wild-shape/transform", response_model=WildShapeResponse)
async def transform_wild_shape(combat_id: str, request: WildShapeTransformRequest):
    """Transform into a beast form using Wild Shape."""
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    char_class = get_combatant_class(engine, request.combatant_id)
    if char_class != "druid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only druids can use Wild Shape"
        )

    level = get_combatant_level(engine, request.combatant_id)
    stats = engine.state.combatant_stats.get(request.combatant_id, {})
    circle = stats.get("subclass", "land")

    # Check if form is available at this level
    available_forms = get_available_forms(level, circle)
    form_ids = [f.id for f in available_forms]
    if request.form_id not in form_ids:
        return WildShapeResponse(
            success=False,
            description=f"Form '{request.form_id}' not available at level {level}",
            combat_state=engine.get_combat_state()
        )

    ws_state = get_or_create_wild_shape_state(engine, request.combatant_id)

    # Get current HP to store for reversion
    current_hp = stats.get("current_hp", combatant.current_hp)
    current_temp_hp = stats.get("temp_hp", 0)

    success, message, form = wild_shape_transform(ws_state, request.form_id, current_hp, current_temp_hp)

    form_data = None
    if success and form:
        save_wild_shape_state(engine, request.combatant_id, ws_state)
        form_data = form.to_dict()

        # Update combatant stats with beast form stats
        stats["wild_shape_hp"] = form.hp
        stats["wild_shape_ac"] = form.ac
        stats["wild_shape_speed"] = form.speed
        stats["wild_shape_attacks"] = [a.to_dict() for a in form.attacks]
        engine.state.combatant_stats[request.combatant_id] = stats

        engine.state.add_event(
            "wild_shape",
            f"{combatant.name} transforms into a {form.name}!",
            combatant_id=request.combatant_id,
            data=form_data
        )

    return WildShapeResponse(
        success=success,
        description=message,
        form_data=form_data,
        combat_state=engine.get_combat_state()
    )


@router.post("/{combat_id}/wild-shape/revert", response_model=WildShapeResponse)
async def revert_wild_shape(combat_id: str, request: KiAbilityRequest):
    """Revert from Wild Shape to normal form."""
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    ws_state = get_or_create_wild_shape_state(engine, request.combatant_id)

    if not ws_state.is_active:
        return WildShapeResponse(
            success=False,
            description="Not currently in Wild Shape",
            combat_state=engine.get_combat_state()
        )

    # Revert returns (original_hp, original_temp_hp)
    original_hp, original_temp_hp = wild_shape_revert(ws_state)

    save_wild_shape_state(engine, request.combatant_id, ws_state)

    # Clear wild shape stats and restore original HP
    stats = engine.state.combatant_stats.get(request.combatant_id, {})
    for key in ["wild_shape_hp", "wild_shape_ac", "wild_shape_speed", "wild_shape_attacks"]:
        stats.pop(key, None)

    # Restore original HP
    if original_hp > 0:
        stats["current_hp"] = original_hp
        combatant.current_hp = original_hp
    if original_temp_hp > 0:
        stats["temp_hp"] = original_temp_hp

    engine.state.combatant_stats[request.combatant_id] = stats

    engine.state.add_event(
        "wild_shape",
        f"{combatant.name} reverts to their normal form!",
        combatant_id=request.combatant_id
    )

    return WildShapeResponse(
        success=True,
        description="Reverted to normal form",
        combat_state=engine.get_combat_state()
    )


# =============================================================================
# SORCERER METAMAGIC ENDPOINTS
# =============================================================================

@router.get("/{combat_id}/sorcery-points/{combatant_id}")
async def get_sorcery_points(combat_id: str, combatant_id: str):
    """Get current Sorcery Point status for a sorcerer."""
    engine, combatant = get_combat_and_validate(combat_id, combatant_id)

    char_class = get_combatant_class(engine, combatant_id)
    if char_class != "sorcerer":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only sorcerers have Sorcery Points"
        )

    level = get_combatant_level(engine, combatant_id)
    sp_state = get_or_create_sorcery_state(engine, combatant_id)

    # Get known metamagic options
    stats = engine.state.combatant_stats.get(combatant_id, {})
    known_metamagic = stats.get("known_metamagic", [])

    return {
        "combatant_id": combatant_id,
        "current_points": sp_state.current_points,
        "max_points": sp_state.max_points,
        "known_metamagic": known_metamagic,
        "all_metamagic": [opt.to_dict() for opt in METAMAGIC_OPTIONS.values()],
        "slot_to_points": SLOT_TO_POINTS,
        "points_to_slot": {str(k): v for k, v in POINTS_TO_SLOT.items()}
    }


@router.post("/{combat_id}/metamagic/apply", response_model=ClassFeatureResponse)
async def apply_metamagic_to_spell(combat_id: str, request: MetamagicRequest):
    """Apply a Metamagic option to a spell being cast."""
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    char_class = get_combatant_class(engine, request.combatant_id)
    if char_class != "sorcerer":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only sorcerers can use Metamagic"
        )

    # Validate metamagic type
    try:
        metamagic_type = MetamagicType(request.metamagic_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown metamagic type: {request.metamagic_type}"
        )

    sp_state = get_or_create_sorcery_state(engine, request.combatant_id)

    # Check if sorcerer knows this metamagic
    stats = engine.state.combatant_stats.get(request.combatant_id, {})
    known_metamagic = stats.get("known_metamagic", [])
    if request.metamagic_type not in known_metamagic and len(known_metamagic) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sorcerer doesn't know {metamagic_type.value}"
        )

    can_use, reason = can_use_metamagic(sp_state, metamagic_type, request.spell_level)
    if not can_use:
        return ClassFeatureResponse(
            success=False,
            description=reason,
            combat_state=engine.get_combat_state()
        )

    success, message, effect_data = apply_metamagic(
        sp_state, metamagic_type, request.spell_level
    )

    if success:
        save_sorcery_state(engine, request.combatant_id, sp_state)

        engine.state.add_event(
            "metamagic",
            f"{combatant.name} applies {METAMAGIC_OPTIONS[metamagic_type].name}!",
            combatant_id=request.combatant_id,
            data=effect_data
        )

    return ClassFeatureResponse(
        success=success,
        description=message,
        effects_applied=[request.metamagic_type] if success else [],
        extra_data=effect_data,
        combat_state=engine.get_combat_state()
    )


@router.post("/{combat_id}/sorcery-points/convert", response_model=ClassFeatureResponse)
async def convert_sorcery_points(combat_id: str, request: SorceryPointRequest):
    """Convert spell slots to/from Sorcery Points."""
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    char_class = get_combatant_class(engine, request.combatant_id)
    if char_class != "sorcerer":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only sorcerers can convert Sorcery Points"
        )

    sp_state = get_or_create_sorcery_state(engine, request.combatant_id)

    if request.operation == "slot_to_points":
        if not request.slot_level:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="slot_level required for conversion"
            )
        success, message = convert_slot_to_points(sp_state, request.slot_level)
    elif request.operation == "points_to_slot":
        if not request.slot_level:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="slot_level required for conversion"
            )
        success, message = convert_points_to_slot(sp_state, request.slot_level)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="operation must be 'slot_to_points' or 'points_to_slot'"
        )

    if success:
        save_sorcery_state(engine, request.combatant_id, sp_state)

    return ClassFeatureResponse(
        success=success,
        description=message,
        extra_data={
            "current_points": sp_state.current_points,
            "max_points": sp_state.max_points
        },
        combat_state=engine.get_combat_state()
    )


# =============================================================================
# WARLOCK ENDPOINTS
# =============================================================================

@router.get("/{combat_id}/warlock/invocations/{combatant_id}")
async def get_warlock_invocations(combat_id: str, combatant_id: str):
    """Get Eldritch Invocations for a warlock."""
    engine, combatant = get_combat_and_validate(combat_id, combatant_id)

    char_class = get_combatant_class(engine, combatant_id)
    if char_class != "warlock":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only warlocks have Eldritch Invocations"
        )

    level = get_combatant_level(engine, combatant_id)
    stats = engine.state.combatant_stats.get(combatant_id, {})
    pact_boon = stats.get("pact_boon")
    spells_known = stats.get("spells_known", [])
    known_invocations = stats.get("known_invocations", [])

    available = get_available_invocations(level, pact_boon, spells_known)

    return {
        "combatant_id": combatant_id,
        "level": level,
        "pact_boon": pact_boon,
        "known_invocations": known_invocations,
        "available_invocations": [inv.to_dict() for inv in available],
        "pact_slots": get_warlock_pact_slots(level)
    }


@router.post("/{combat_id}/warlock/eldritch-blast", response_model=ClassFeatureResponse)
async def cast_eldritch_blast(combat_id: str, request: KiAbilityRequest):
    """
    Cast Eldritch Blast with invocation modifiers.

    Applies Agonizing Blast (add CHA to damage) if known.
    """
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    if not request.target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_id is required"
        )

    char_class = get_combatant_class(engine, request.combatant_id)
    if char_class != "warlock":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only warlocks can use Eldritch Blast invocations"
        )

    level = get_combatant_level(engine, request.combatant_id)
    stats = engine.state.combatant_stats.get(request.combatant_id, {})
    abilities = stats.get("abilities", {})
    charisma = abilities.get("charisma", 10)
    known_invocations = stats.get("known_invocations", [])

    # Calculate damage with invocations
    damage_info = calculate_eldritch_blast_damage(level, charisma, known_invocations)

    return ClassFeatureResponse(
        success=True,
        description=f"Eldritch Blast: {damage_info['beams']} beam(s), {damage_info['damage_per_beam']} damage each",
        extra_data=damage_info,
        combat_state=engine.get_combat_state()
    )


# =============================================================================
# BARBARIAN ENDPOINTS
# =============================================================================

@router.post("/{combat_id}/barbarian/rage", response_model=ClassFeatureResponse)
async def enter_rage(combat_id: str, request: RageRequest):
    """Enter Barbarian Rage."""
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    char_class = get_combatant_class(engine, request.combatant_id)
    if char_class != "barbarian":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only barbarians can Rage"
        )

    level = get_combatant_level(engine, request.combatant_id)
    stats = engine.state.combatant_stats.get(request.combatant_id, {})

    # Check rage uses
    rage_uses = stats.get("rage_uses", get_rage_uses(level))
    if rage_uses <= 0 and level < 20:  # Level 20 = unlimited
        return ClassFeatureResponse(
            success=False,
            description="No rage uses remaining",
            combat_state=engine.get_combat_state()
        )

    # Activate rage
    result = use_rage(level)

    if result.success:
        stats["rage_uses"] = rage_uses - 1 if level < 20 else rage_uses
        stats["is_raging"] = True
        stats["rage_damage_bonus"] = result.value

        # Add resistances
        conditions = stats.get("conditions", [])
        if "raging" not in conditions:
            conditions.append("raging")
        stats["conditions"] = conditions

        engine.state.combatant_stats[request.combatant_id] = stats

        engine.state.add_event(
            "class_feature",
            f"{combatant.name} enters a RAGE!",
            combatant_id=request.combatant_id,
            data=result.extra_data
        )

    return ClassFeatureResponse(
        success=result.success,
        description=result.description,
        effects_applied=["raging", "resistance_physical"] if result.success else [],
        extra_data=result.extra_data,
        combat_state=engine.get_combat_state()
    )


@router.post("/{combat_id}/barbarian/reckless-attack", response_model=ClassFeatureResponse)
async def use_reckless(combat_id: str, request: RecklessAttackRequest):
    """Toggle Reckless Attack for this turn."""
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    char_class = get_combatant_class(engine, request.combatant_id)
    if char_class != "barbarian":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only barbarians can use Reckless Attack"
        )

    level = get_combatant_level(engine, request.combatant_id)
    if level < 2:
        return ClassFeatureResponse(
            success=False,
            description="Reckless Attack requires level 2",
            combat_state=engine.get_combat_state()
        )

    result = use_reckless_attack()

    stats = engine.state.combatant_stats.get(request.combatant_id, {})
    stats["reckless_attack_active"] = True
    engine.state.combatant_stats[request.combatant_id] = stats

    engine.state.add_event(
        "class_feature",
        f"{combatant.name} attacks recklessly!",
        combatant_id=request.combatant_id,
        data=result.extra_data
    )

    return ClassFeatureResponse(
        success=result.success,
        description=result.description,
        effects_applied=["reckless_attack"],
        extra_data=result.extra_data,
        combat_state=engine.get_combat_state()
    )


# =============================================================================
# PALADIN ENDPOINTS
# =============================================================================

@router.post("/{combat_id}/paladin/lay-on-hands", response_model=ClassFeatureResponse)
async def use_lay_on_hands_ability(combat_id: str, request: LayOnHandsRequest):
    """Use Paladin's Lay on Hands to heal or cure conditions."""
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    target = engine.state.initiative_tracker.get_combatant(request.target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found"
        )

    char_class = get_combatant_class(engine, request.combatant_id)
    if char_class != "paladin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only paladins can use Lay on Hands"
        )

    level = get_combatant_level(engine, request.combatant_id)
    stats = engine.state.combatant_stats.get(request.combatant_id, {})

    # Check pool
    max_pool = get_lay_on_hands_pool(level)
    current_pool = stats.get("lay_on_hands_pool", max_pool)

    total_cost = request.points_to_spend
    if request.cure_disease:
        total_cost = 5
    if request.cure_poison:
        total_cost = 5

    if current_pool < total_cost:
        return ClassFeatureResponse(
            success=False,
            description=f"Not enough Lay on Hands points (have {current_pool}, need {total_cost})",
            combat_state=engine.get_combat_state()
        )

    result = use_lay_on_hands(request.points_to_spend, request.cure_disease, request.cure_poison)

    if result.success:
        # Deduct from pool
        stats["lay_on_hands_pool"] = current_pool - total_cost
        engine.state.combatant_stats[request.combatant_id] = stats

        # Apply healing to target
        if result.value > 0:
            target_stats = engine.state.combatant_stats.get(request.target_id, {})
            current_hp = target_stats.get("current_hp", target.current_hp)
            max_hp = target_stats.get("max_hp", target.max_hp)
            new_hp = min(current_hp + result.value, max_hp)
            target_stats["current_hp"] = new_hp
            target.current_hp = new_hp
            engine.state.combatant_stats[request.target_id] = target_stats

        # Remove conditions if cured
        effects_applied = []
        if request.cure_disease:
            effects_applied.append("cured_disease")
        if request.cure_poison:
            target_stats = engine.state.combatant_stats.get(request.target_id, {})
            conditions = target_stats.get("conditions", [])
            if "poisoned" in conditions:
                conditions.remove("poisoned")
                target_stats["conditions"] = conditions
                engine.state.combatant_stats[request.target_id] = target_stats
            effects_applied.append("cured_poison")

        engine.state.add_event(
            "class_feature",
            f"{combatant.name} uses Lay on Hands on {target.name}!",
            combatant_id=request.combatant_id,
            data=result.extra_data
        )

    return ClassFeatureResponse(
        success=result.success,
        description=result.description,
        healing_done=result.value,
        effects_applied=effects_applied if result.success else [],
        extra_data={
            **result.extra_data,
            "pool_remaining": stats.get("lay_on_hands_pool", 0)
        },
        combat_state=engine.get_combat_state()
    )


# =============================================================================
# ROGUE ENDPOINTS
# =============================================================================

@router.post("/{combat_id}/rogue/cunning-action", response_model=ClassFeatureResponse)
async def use_cunning_action(combat_id: str, request: CunningActionRequest):
    """Use Rogue's Cunning Action (Dash, Disengage, or Hide as bonus action)."""
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    char_class = get_combatant_class(engine, request.combatant_id)
    if char_class != "rogue":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only rogues can use Cunning Action"
        )

    level = get_combatant_level(engine, request.combatant_id)
    if level < 2:
        return ClassFeatureResponse(
            success=False,
            description="Cunning Action requires level 2",
            combat_state=engine.get_combat_state()
        )

    valid_actions = ["dash", "disengage", "hide"]
    if request.action_type.lower() not in valid_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action type. Must be one of: {valid_actions}"
        )

    action = request.action_type.lower()
    stats = engine.state.combatant_stats.get(request.combatant_id, {})

    effects = []
    description = ""

    if action == "dash":
        base_speed = stats.get("speed", 30)
        stats["movement_remaining"] = stats.get("movement_remaining", base_speed) + base_speed
        description = "Cunning Action: Dash - doubled movement this turn"
        effects.append("dash")
    elif action == "disengage":
        stats["disengage_active"] = True
        description = "Cunning Action: Disengage - no opportunity attacks this turn"
        effects.append("disengage")
    elif action == "hide":
        stats["hidden"] = True
        description = "Cunning Action: Hide - attempting to hide"
        effects.append("hidden")

    stats["bonus_action_used"] = True
    engine.state.combatant_stats[request.combatant_id] = stats

    engine.state.add_event(
        "class_feature",
        f"{combatant.name} uses Cunning Action ({action.capitalize()})!",
        combatant_id=request.combatant_id
    )

    return ClassFeatureResponse(
        success=True,
        description=description,
        effects_applied=effects,
        combat_state=engine.get_combat_state()
    )


# =============================================================================
# BARD ENDPOINTS
# =============================================================================

@router.post("/{combat_id}/bard/bardic-inspiration", response_model=ClassFeatureResponse)
async def grant_bardic_inspiration(combat_id: str, request: BardicInspirationRequest):
    """Grant Bardic Inspiration to an ally."""
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    target = engine.state.initiative_tracker.get_combatant(request.target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found"
        )

    char_class = get_combatant_class(engine, request.combatant_id)
    if char_class != "bard":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only bards can grant Bardic Inspiration"
        )

    level = get_combatant_level(engine, request.combatant_id)
    stats = engine.state.combatant_stats.get(request.combatant_id, {})

    # Check uses (CHA modifier per long rest, or short rest at level 5+)
    abilities = stats.get("abilities", {})
    charisma = abilities.get("charisma", 10)
    cha_mod = max(1, (charisma - 10) // 2)
    max_uses = cha_mod
    current_uses = stats.get("bardic_inspiration_uses", max_uses)

    if current_uses <= 0:
        return ClassFeatureResponse(
            success=False,
            description="No Bardic Inspiration uses remaining",
            combat_state=engine.get_combat_state()
        )

    result = use_bardic_inspiration(level, target.name)

    if result.success:
        # Deduct use
        stats["bardic_inspiration_uses"] = current_uses - 1
        engine.state.combatant_stats[request.combatant_id] = stats

        # Grant inspiration to target
        target_stats = engine.state.combatant_stats.get(request.target_id, {})
        target_stats["bardic_inspiration_die"] = get_bardic_inspiration_die(level)
        target_stats["has_bardic_inspiration"] = True
        engine.state.combatant_stats[request.target_id] = target_stats

        engine.state.add_event(
            "class_feature",
            f"{combatant.name} grants Bardic Inspiration to {target.name}!",
            combatant_id=request.combatant_id,
            data=result.extra_data
        )

    return ClassFeatureResponse(
        success=result.success,
        description=result.description,
        effects_applied=["bardic_inspiration"] if result.success else [],
        extra_data={
            **result.extra_data,
            "uses_remaining": stats.get("bardic_inspiration_uses", 0)
        },
        combat_state=engine.get_combat_state()
    )


# =============================================================================
# CLERIC/PALADIN CHANNEL DIVINITY ENDPOINTS
# =============================================================================

@router.post("/{combat_id}/channel-divinity", response_model=ClassFeatureResponse)
async def use_channel_divinity(combat_id: str, request: ChannelDivinityRequest):
    """Use Channel Divinity (Cleric or Paladin feature)."""
    engine, combatant = get_combat_and_validate(combat_id, request.combatant_id)

    char_class = get_combatant_class(engine, request.combatant_id)
    if char_class not in ["cleric", "paladin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only clerics and paladins can use Channel Divinity"
        )

    level = get_combatant_level(engine, request.combatant_id)
    if level < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel Divinity requires at least level 2"
        )

    stats = engine.state.combatant_stats.get(request.combatant_id, {})

    # Check uses remaining
    max_uses = get_channel_divinity_uses(level)
    current_uses = stats.get("channel_divinity_uses", max_uses)

    if current_uses <= 0:
        return ClassFeatureResponse(
            success=False,
            description="No Channel Divinity uses remaining",
            combat_state=engine.get_combat_state()
        )

    # Handle different Channel Divinity options
    option = request.option.lower()
    effects = []
    description = ""
    extra_data = {}

    if option == "turn_undead":
        # Get all enemy undead in combat
        abilities = stats.get("abilities", {})
        wisdom = abilities.get("wisdom", 10)
        wis_mod = (wisdom - 10) // 2
        proficiency = stats.get("proficiency_bonus", 2)

        # Find undead enemies
        undead_targets = []
        for cid, c in engine.state.combatant_stats.items():
            combatant_obj = engine.state.initiative_tracker.get_combatant(cid)
            if combatant_obj and combatant_obj.type == "enemy":
                creature_type = c.get("creature_type", "").lower()
                if creature_type == "undead":
                    undead_targets.append({
                        "id": cid,
                        "name": combatant_obj.name,
                        "wis_save_mod": c.get("saving_throws", {}).get("wisdom", 0)
                    })

        if not undead_targets:
            return ClassFeatureResponse(
                success=True,
                description=f"{combatant.name} channels divine energy to turn undead, but no undead are present!",
                effects_applied=[],
                extra_data={"turned": [], "resisted": []},
                combat_state=engine.get_combat_state()
            )

        result = use_turn_undead(wis_mod, proficiency, undead_targets)

        # Apply turned condition to affected undead
        turned_list = result.extra_data.get("turned", [])
        for turned_id in [t.get("id") for t in turned_list if isinstance(t, dict)]:
            target_stats = engine.state.combatant_stats.get(turned_id, {})
            conditions = target_stats.get("conditions", [])
            if "turned" not in conditions:
                conditions.append("turned")
            target_stats["conditions"] = conditions
            engine.state.combatant_stats[turned_id] = target_stats

        description = result.description
        extra_data = result.extra_data
        effects = ["turn_undead"]

    elif option == "sacred_weapon":
        # Paladin Oath of Devotion: Add CHA to attack rolls for 1 minute
        abilities = stats.get("abilities", {})
        charisma = abilities.get("charisma", 10)
        cha_mod = max(1, (charisma - 10) // 2)

        stats["sacred_weapon_active"] = True
        stats["sacred_weapon_bonus"] = cha_mod
        engine.state.combatant_stats[request.combatant_id] = stats

        description = f"{combatant.name} imbues their weapon with divine energy! (+{cha_mod} to attack rolls for 1 minute)"
        effects = ["sacred_weapon"]
        extra_data = {"attack_bonus": cha_mod, "duration": "1 minute"}

    elif option == "vow_of_enmity":
        # Paladin Oath of Vengeance: Advantage vs one creature
        description = f"{combatant.name} swears a vow of enmity! (Select a target to gain advantage on attacks)"
        effects = ["vow_of_enmity"]
        extra_data = {"requires_target": True}

    else:
        # Generic divine energy burst
        description = f"{combatant.name} channels divine energy!"
        effects = ["channel_divinity"]

    # Deduct use
    stats["channel_divinity_uses"] = current_uses - 1
    engine.state.combatant_stats[request.combatant_id] = stats

    engine.state.add_event(
        "class_feature",
        description,
        combatant_id=request.combatant_id,
        data=extra_data
    )

    return ClassFeatureResponse(
        success=True,
        description=description,
        effects_applied=effects,
        extra_data={
            **extra_data,
            "uses_remaining": stats.get("channel_divinity_uses", 0)
        },
        combat_state=engine.get_combat_state()
    )
