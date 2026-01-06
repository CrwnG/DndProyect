"""
Combat API Routes.

Endpoints for managing combat encounters:
- Start/end combat
- Take actions and move
- Handle reactions
- Query combat state
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from app.core.combat_engine import (
    CombatEngine,
    CombatPhase,
    ActionType,
    BonusActionType,
    load_weapon_data,
)
from app.core.initiative import CombatantType
from app.core.movement import (
    CombatGrid,
    TerrainType,
    find_path,
    get_reachable_cells,
    check_opportunity_attack_triggers,
    get_threatened_squares,
)
from app.core.reactions import (
    ReactionsManager,
    ReactionType,
    ReactionTrigger,
    check_available_reactions,
    resolve_opportunity_attack,
    resolve_shield_spell,
    resolve_uncanny_dodge,
    resolve_riposte,
    resolve_sentinel_opportunity_attack,
)
from app.core.combat_storage import (
    active_combats,
    active_grids,
    reactions_managers,
    persist_combat_state,
    create_combat_state,
    end_combat_state,
)
from app.database.dependencies import get_combat_repo
from app.database.repositories import CombatStateRepository

# Import Advanced AI System
from app.core.ai import get_ai_for_combatant, coordinate_enemies

# Feature flag for advanced AI (can be toggled per encounter)
USE_ADVANCED_AI = True

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class CombatantData(BaseModel):
    """Data for a combatant."""
    id: Optional[str] = None
    name: str
    hp: int = 10
    max_hp: Optional[int] = None
    ac: int = 10
    dex_mod: int = 0
    str_mod: int = 0
    attack_bonus: int = 0
    damage_dice: str = "1d6"
    damage_type: str = "slashing"
    speed: int = 30
    resistances: List[str] = Field(default_factory=list)
    immunities: List[str] = Field(default_factory=list)
    vulnerabilities: List[str] = Field(default_factory=list)
    abilities: Dict[str, Any] = Field(default_factory=dict)


class StartCombatRequest(BaseModel):
    """Request to start combat."""
    players: List[CombatantData]
    enemies: List[CombatantData]
    grid_width: int = 8
    grid_height: int = 8
    obstacles: List[List[int]] = Field(default_factory=list)
    difficult_terrain: List[List[int]] = Field(default_factory=list)
    initial_positions: Optional[Dict[str, List[int]]] = None


class StartCombatResponse(BaseModel):
    """Response from starting combat."""
    combat_id: str
    initiative_order: List[Dict[str, Any]]
    current_combatant: Dict[str, Any]
    grid: Dict[str, Any]


class ActionRequest(BaseModel):
    """Request to take an action."""
    combat_id: str
    action_type: str
    target_id: Optional[str] = None
    weapon_name: Optional[str] = None
    spell_name: Optional[str] = None
    extra_data: Dict[str, Any] = Field(default_factory=dict)


class ActionResponse(BaseModel):
    """Response from taking an action."""
    success: bool
    description: str
    damage_dealt: int = 0
    effects_applied: List[str] = Field(default_factory=list)
    combat_state: Dict[str, Any]
    reaction_options: List[Dict[str, Any]] = Field(default_factory=list)
    # Attack roll details (populated for attack actions)
    hit: Optional[bool] = None
    critical: Optional[bool] = None
    attack_roll: Optional[int] = None  # Total attack roll
    natural_roll: Optional[int] = None  # Raw d20 value
    modifier: Optional[int] = None  # Attack modifier
    target_ac: Optional[int] = None  # Target's AC
    damage: Optional[int] = None  # Damage dealt (alias for damage_dealt)
    damage_type: Optional[str] = None
    damage_formula: Optional[str] = None
    advantage: Optional[bool] = None
    disadvantage: Optional[bool] = None
    second_roll: Optional[int] = None  # Second d20 for adv/disadv
    # Extra data for attack tracking (Extra Attack, Two-Weapon Fighting, etc.)
    extra_data: Dict[str, Any] = Field(default_factory=dict)


class MoveRequest(BaseModel):
    """Request to move a combatant."""
    combat_id: str
    target_x: int
    target_y: int
    combatant_id: Optional[str] = None  # Optional: validates it's this combatant's turn


class MoveResponse(BaseModel):
    """Response from movement."""
    success: bool
    path: List[List[int]]
    distance: int
    description: str
    opportunity_attacks: List[str] = Field(default_factory=list)
    combat_state: Dict[str, Any]


class ReactionRequest(BaseModel):
    """Request to use a reaction."""
    combat_id: str
    reaction_type: str
    trigger_source_id: str
    extra_data: Dict[str, Any] = Field(default_factory=dict)


class BonusActionRequest(BaseModel):
    """Request to take a bonus action."""
    combat_id: str
    bonus_action_type: str
    target_id: Optional[str] = None
    weapon_name: Optional[str] = None
    extra_data: Dict[str, Any] = Field(default_factory=dict)


class ReactionResponse(BaseModel):
    """Response from using a reaction."""
    success: bool
    description: str
    damage_dealt: int = 0
    damage_prevented: int = 0
    effects_applied: List[str] = Field(default_factory=list)
    combat_state: Dict[str, Any]


class EnemyAction(BaseModel):
    """Description of an enemy's action during their turn."""
    enemy_id: str
    enemy_name: str
    action_type: str  # "attack", "move", "none"
    description: str
    target_id: Optional[str] = None
    damage_dealt: int = 0
    hit: bool = False

    # Attack roll details (for dice animation)
    attack_roll: Optional[int] = None        # Total (d20 + modifier)
    natural_roll: Optional[int] = None       # Raw d20 value
    attack_modifier: Optional[int] = None    # +X from abilities
    target_ac: Optional[int] = None          # For comparison display
    critical: Optional[bool] = None          # Natural 20
    critical_miss: Optional[bool] = None     # Natural 1
    advantage: Optional[bool] = None
    disadvantage: Optional[bool] = None
    second_roll: Optional[int] = None        # For adv/disadv

    # Damage roll details
    damage_formula: Optional[str] = None     # "1d6+2"
    damage_rolls: Optional[List[int]] = None # [4] individual die results
    damage_modifier: Optional[int] = None    # +2 from STR/etc
    damage_type: Optional[str] = None        # "slashing"

    # Movement path (for animation)
    movement_path: Optional[List[List[int]]] = None  # [[x,y], [x,y], ...]
    old_position: Optional[List[int]] = None
    new_position: Optional[List[int]] = None


class EndTurnResponse(BaseModel):
    """Response from ending turn."""
    success: bool
    next_combatant: Optional[Dict[str, Any]]
    round_number: int
    current_turn_index: int = 0
    enemy_actions: List[EnemyAction] = Field(default_factory=list)
    combat_state: Optional[Dict[str, Any]] = None
    combat_over: bool = False
    combat_result: Optional[str] = None


class LegendaryCreatureInfo(BaseModel):
    """Info about a legendary creature and its available actions."""
    id: str
    name: str
    actions_remaining: int
    actions_per_round: int
    available_actions: List[Dict[str, Any]]  # [{name, cost, description}]


class CombatStateResponse(BaseModel):
    """Full combat state response."""
    combat_id: str
    phase: str
    round_number: int
    initiative_order: List[Dict[str, Any]]
    current_combatant: Optional[Dict[str, Any]]
    turn_state: Optional[Dict[str, Any]]
    positions: Dict[str, Any]  # {combatant_id: {x: int, y: int}}
    grid: Dict[str, Any]
    recent_events: List[Dict[str, Any]]
    legendary_creatures: List[LegendaryCreatureInfo] = Field(default_factory=list)
    is_combat_over: bool
    combat_result: Optional[str] = None


# =============================================================================
# Combat Lifecycle Endpoints
# =============================================================================

@router.post("/start", response_model=StartCombatResponse)
async def start_combat(
    request: StartCombatRequest,
    combat_repo: CombatStateRepository = Depends(get_combat_repo),
):
    """
    Start a new combat encounter.

    Sets up combatants, rolls initiative, and creates the combat grid.
    Persists combat state to database for resumability.
    """
    import uuid

    # Create combat engine
    engine = CombatEngine()

    # Convert player/enemy data to dicts
    players = [p.model_dump() for p in request.players]
    enemies = [e.model_dump() for e in request.enemies]

    # Assign IDs if not provided
    for i, p in enumerate(players):
        if not p.get("id"):
            p["id"] = f"player-{i+1}"

    for i, e in enumerate(enemies):
        if not e.get("id"):
            e["id"] = f"enemy-{i+1}"

    # Create grid
    grid = CombatGrid(width=request.grid_width, height=request.grid_height)

    # Set terrain
    for obs in request.obstacles:
        if len(obs) >= 2:
            grid.set_terrain(obs[0], obs[1], TerrainType.IMPASSABLE)

    for dt in request.difficult_terrain:
        if len(dt) >= 2:
            grid.set_terrain(dt[0], dt[1], TerrainType.DIFFICULT)

    # Helper function to find an unoccupied position
    def find_unoccupied_position(preferred_x: int, preferred_y: int, search_columns: list) -> tuple:
        """
        Find nearest unoccupied cell starting from preferred position.
        Searches through columns in order, trying each y position.
        """
        for x in search_columns:
            if x < 0 or x >= request.grid_width:
                continue
            # Start from preferred_y and spiral outward
            for offset in range(request.grid_height):
                for y_candidate in [preferred_y + offset, preferred_y - offset]:
                    if y_candidate < 0 or y_candidate >= request.grid_height:
                        continue
                    if grid.get_cell(x, y_candidate).occupied_by is None:
                        return (x, y_candidate)
        return None  # Grid is full in this area

    # Set initial positions
    positions = {}
    if request.initial_positions:
        for cid, pos in request.initial_positions.items():
            if len(pos) >= 2:
                positions[cid] = (pos[0], pos[1])
                grid.set_occupant(pos[0], pos[1], cid)
    else:
        # Default positions - players on left, enemies on right
        # Use collision detection to prevent stacking
        player_columns = [0, 1, 2]  # Players prefer leftmost columns
        enemy_columns = [request.grid_width - 1, request.grid_width - 2, request.grid_width - 3]

        for i, p in enumerate(players):
            preferred_y = i % request.grid_height
            pos = find_unoccupied_position(0, preferred_y, player_columns)
            if pos:
                positions[p["id"]] = pos
                grid.set_occupant(pos[0], pos[1], p["id"])
            else:
                # Fallback: place anywhere available
                for y in range(request.grid_height):
                    for x in range(request.grid_width):
                        if grid.get_cell(x, y).occupied_by is None:
                            positions[p["id"]] = (x, y)
                            grid.set_occupant(x, y, p["id"])
                            break
                    if p["id"] in positions:
                        break

        for i, e in enumerate(enemies):
            preferred_y = i % request.grid_height
            pos = find_unoccupied_position(request.grid_width - 1, preferred_y, enemy_columns)
            if pos:
                positions[e["id"]] = pos
                grid.set_occupant(pos[0], pos[1], e["id"])
            else:
                # Fallback: place anywhere available
                for y in range(request.grid_height):
                    for x in range(request.grid_width - 1, -1, -1):  # Start from right
                        if grid.get_cell(x, y).occupied_by is None:
                            positions[e["id"]] = (x, y)
                            grid.set_occupant(x, y, e["id"])
                            break
                    if e["id"] in positions:
                        break

    # Start combat
    initiative_results = engine.start_combat(players, enemies, positions)

    # Create reactions manager
    reactions_mgr = ReactionsManager()
    for p in players:
        reactions_mgr.register_combatant(p["id"])
    for e in enemies:
        reactions_mgr.register_combatant(e["id"])

    # Generate combat ID
    combat_id = str(uuid.uuid4())

    # Store in memory
    active_combats[combat_id] = engine
    active_grids[combat_id] = grid
    reactions_managers[combat_id] = reactions_mgr

    # Persist to database
    all_combatants = players + enemies
    await create_combat_state(
        combat_id=combat_id,
        session_id=None,  # Can be linked to game session if needed
        combatants=all_combatants,
        repo=combat_repo,
    )
    # Save initial state
    await persist_combat_state(combat_id, engine, combat_repo)

    current = engine.get_current_combatant()

    return StartCombatResponse(
        combat_id=combat_id,
        initiative_order=initiative_results,
        current_combatant=current.to_dict() if current else {},
        grid=grid.to_dict()
    )


@router.post("/{combat_id}/end")
async def end_combat(
    combat_id: str,
    reason: str = "manual",
    combat_repo: CombatStateRepository = Depends(get_combat_repo),
):
    """
    End a combat encounter.

    Args:
        combat_id: The combat session ID
        reason: Reason for ending (manual, victory, defeat, fled)
    """
    engine = active_combats.get(combat_id)
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    try:
        result = engine.end_combat(reason)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Persist end state to database
    xp_awarded = result.get("xp_awarded", 0)
    await end_combat_state(combat_id, result=reason, xp_awarded=xp_awarded, repo=combat_repo)

    # Clean up memory
    del active_combats[combat_id]
    if combat_id in active_grids:
        del active_grids[combat_id]
    if combat_id in reactions_managers:
        del reactions_managers[combat_id]

    return {
        "success": True,
        "result": result.get("result"),
        "reason": reason,
        "rounds": result.get("rounds", 0)
    }


@router.get("/{combat_id}/state", response_model=CombatStateResponse)
async def get_combat_state(combat_id: str):
    """Get the current state of a combat encounter."""
    engine = active_combats.get(combat_id)
    grid = active_grids.get(combat_id)

    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    state = engine.get_combat_state()
    current = engine.get_current_combatant()
    turn = engine.get_turn_state()

    # Positions are already in correct format from get_combat_state()
    # They're {combatant_id: {"x": x, "y": y}} dicts
    positions_dict = state["positions"]

    # Build legendary creatures info
    legendary_creatures = []
    for creature_id in engine.get_legendary_creatures():
        creature_stats = engine.state.combatant_stats.get(creature_id, {})
        legendary_creatures.append(LegendaryCreatureInfo(
            id=creature_id,
            name=creature_stats.get("name", "Unknown"),
            actions_remaining=engine.state.legendary_actions_remaining.get(creature_id, 0),
            actions_per_round=creature_stats.get("legendary_actions_per_round", 0),
            available_actions=engine.get_available_legendary_actions(creature_id)
        ))

    return CombatStateResponse(
        combat_id=combat_id,
        phase=state["phase"],
        round_number=state["round"],
        initiative_order=state["initiative_order"],
        current_combatant=current.to_dict() if current else None,
        turn_state={
            "combatant_id": turn.combatant_id,
            "movement_used": turn.movement_used,
            "action_taken": turn.action_taken,
            "bonus_action_taken": turn.bonus_action_taken,
            "phase": turn.current_phase.name
        } if turn else None,
        positions=positions_dict,
        grid=grid.to_dict() if grid else {},
        recent_events=engine.get_recent_events(10),
        legendary_creatures=legendary_creatures,
        is_combat_over=state["is_combat_over"],
        combat_result=state["combat_result"]
    )


# =============================================================================
# Action Endpoints
# =============================================================================

@router.post("/action", response_model=ActionResponse)
async def take_action(
    request: ActionRequest,
    combat_repo: CombatStateRepository = Depends(get_combat_repo),
):
    """
    Take an action in combat.

    Supports: attack, dash, disengage, dodge, help, hide, ready
    Persists state to database after action.
    """
    engine = active_combats.get(request.combat_id)
    reactions_mgr = reactions_managers.get(request.combat_id)

    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    # Map string to ActionType
    try:
        action_type = ActionType(request.action_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action type: {request.action_type}"
        )

    # Take the action
    result = engine.take_action(
        action_type=action_type,
        target_id=request.target_id,
        weapon_name=request.weapon_name,
        **request.extra_data
    )

    # Clear grid position if target was defeated (D&D rule: dead creatures don't block)
    if result.extra_data and result.extra_data.get("target_defeated"):
        target_id = request.target_id
        if target_id and target_id in engine.state.positions:
            target_pos = engine.state.positions[target_id]
            grid = active_grids.get(request.combat_id)
            if grid:
                grid.set_occupant(target_pos[0], target_pos[1], None)

    # Check for reaction opportunities
    reaction_options = []
    if result.success and request.target_id and reactions_mgr:
        # Check if target can react (e.g., Shield, Uncanny Dodge)
        if result.extra_data.get("hit"):
            target_abilities = engine.state.combatant_stats.get(
                request.target_id, {}
            ).get("abilities", {})

            options = check_available_reactions(
                combatant_id=request.target_id,
                trigger=ReactionTrigger.BEING_HIT,
                trigger_source_id=engine.get_current_combatant().id,
                reactions_manager=reactions_mgr,
                combatant_abilities=target_abilities,
                context={"damage_type": result.extra_data.get("damage_type", "slashing")}
            )

            reaction_options = [
                {
                    "reaction_type": opt.reaction_type.value,
                    "description": opt.description,
                    "can_use": opt.can_use
                }
                for opt in options
            ]

    # Build base response
    response_data = {
        "success": result.success,
        "description": result.description,
        "damage_dealt": result.damage_dealt,
        "effects_applied": result.effects_applied,
        "combat_state": engine.get_combat_state(),
        "reaction_options": reaction_options,
        # Include extra_data for attack tracking (Extra Attack, Two-Weapon Fighting)
        "extra_data": result.extra_data or {},
    }

    # Extract attack roll details if this was an attack action
    if action_type == ActionType.ATTACK and result.extra_data:
        extra = result.extra_data
        attack_roll_obj = extra.get("attack_roll")

        # Handle D20Result object or raw value
        if attack_roll_obj is not None:
            if hasattr(attack_roll_obj, "total"):
                # It's a D20Result object
                response_data["attack_roll"] = attack_roll_obj.total
                response_data["natural_roll"] = attack_roll_obj.base_roll
                response_data["modifier"] = attack_roll_obj.modifier
                response_data["advantage"] = attack_roll_obj.advantage
                response_data["disadvantage"] = attack_roll_obj.disadvantage
                # Second roll for advantage/disadvantage
                if len(attack_roll_obj.rolls) > 1:
                    # Get the roll that wasn't used
                    if attack_roll_obj.advantage:
                        response_data["second_roll"] = min(attack_roll_obj.rolls)
                    elif attack_roll_obj.disadvantage:
                        response_data["second_roll"] = max(attack_roll_obj.rolls)
            else:
                # It's already a number
                response_data["attack_roll"] = attack_roll_obj

        response_data["hit"] = extra.get("hit")
        response_data["critical"] = extra.get("critical_hit")
        response_data["target_ac"] = extra.get("target_ac")
        response_data["damage"] = result.damage_dealt
        response_data["damage_type"] = extra.get("damage_type", "slashing")

        # Get attacker stats for damage formula
        attacker = engine.get_current_combatant()
        if attacker:
            attacker_stats = engine.state.combatant_stats.get(attacker.id, {})
            response_data["damage_formula"] = attacker_stats.get("damage_dice", "1d6")

    # Persist state to database
    await persist_combat_state(request.combat_id, engine, combat_repo)

    return ActionResponse(**response_data)


@router.post("/bonus-action", response_model=ActionResponse)
async def take_bonus_action(
    request: BonusActionRequest,
    combat_repo: CombatStateRepository = Depends(get_combat_repo),
):
    """
    Take a bonus action in combat.

    Supports: offhand_attack, second_wind
    Persists state to database after action.
    """
    engine = active_combats.get(request.combat_id)

    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    # Map string to BonusActionType
    try:
        bonus_type = BonusActionType(request.bonus_action_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bonus action type: {request.bonus_action_type}"
        )

    # Take the bonus action
    result = engine.take_bonus_action(
        bonus_type=bonus_type,
        target_id=request.target_id,
        offhand_weapon=request.weapon_name or "dagger",
        **request.extra_data
    )

    # Clear grid position if target was defeated
    if result.extra_data and result.extra_data.get("target_defeated"):
        target_id = request.target_id
        if target_id and target_id in engine.state.positions:
            target_pos = engine.state.positions[target_id]
            grid = active_grids.get(request.combat_id)
            if grid:
                grid.set_occupant(target_pos[0], target_pos[1], None)

    # Build response
    response_data = {
        "success": result.success,
        "description": result.description,
        "damage_dealt": result.damage_dealt,
        "effects_applied": result.effects_applied,
        "combat_state": engine.get_combat_state(),
        "reaction_options": [],
    }

    # Extract attack roll details if this was an offhand attack
    if bonus_type == BonusActionType.OFFHAND_ATTACK and result.extra_data:
        extra = result.extra_data
        response_data["hit"] = extra.get("hit")
        response_data["critical"] = extra.get("critical_hit")
        response_data["target_ac"] = extra.get("target_ac")
        response_data["damage"] = result.damage_dealt

        attack_roll = extra.get("attack_roll")
        if attack_roll is not None:
            if hasattr(attack_roll, "total"):
                response_data["attack_roll"] = attack_roll.total
                response_data["natural_roll"] = attack_roll.base_roll
                response_data["modifier"] = attack_roll.modifier
            else:
                response_data["attack_roll"] = attack_roll

    # Persist state to database
    await persist_combat_state(request.combat_id, engine, combat_repo)

    return ActionResponse(**response_data)


@router.post("/move", response_model=MoveResponse)
async def move_combatant(
    request: MoveRequest,
    combat_repo: CombatStateRepository = Depends(get_combat_repo),
):
    """
    Move the current combatant to a new position.

    Uses A* pathfinding to find the best route.
    Checks for opportunity attacks if moving away from enemies.
    Persists state to database after movement.
    """
    engine = active_combats.get(request.combat_id)
    grid = active_grids.get(request.combat_id)
    reactions_mgr = reactions_managers.get(request.combat_id)

    if not engine or not grid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    current = engine.get_current_combatant()
    if not current:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No current combatant"
        )

    # Validate combatant_id if provided (prevents client/server desync bugs)
    if request.combatant_id and request.combatant_id != current.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not {request.combatant_id}'s turn. Current turn: {current.name} ({current.id})"
        )

    current_pos = engine.state.positions.get(current.id)
    if not current_pos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Combatant has no position"
        )

    # Get available movement
    stats = engine.state.combatant_stats.get(current.id, {})
    speed = stats.get("speed", 30)
    turn = engine.get_turn_state()
    remaining = speed - (turn.movement_used if turn else 0)

    # Determine ally IDs for the current combatant
    # Allies are combatants of the same type (player or enemy)
    tracker = engine.state.initiative_tracker
    ally_ids = set()
    for c in tracker.combatants:
        if c.id != current.id and c.is_active and c.combatant_type == current.combatant_type:
            ally_ids.add(c.id)

    # Find path
    path_result = find_path(
        grid=grid,
        start_x=current_pos[0],
        start_y=current_pos[1],
        end_x=request.target_x,
        end_y=request.target_y,
        max_movement=remaining,
        mover_id=current.id,
        ally_ids=ally_ids
    )

    if not path_result.success:
        return MoveResponse(
            success=False,
            path=[],
            distance=0,
            description=path_result.description,
            opportunity_attacks=[],
            combat_state=engine.get_combat_state()
        )

    # Check for opportunity attacks
    opportunity_attackers = []
    if len(path_result.path) > 1 and reactions_mgr:
        # Get enemy IDs
        enemy_ids = [
            c.id for c in engine.state.initiative_tracker.combatants
            if c.combatant_type != current.combatant_type and c.is_active
        ]

        # Get mover's conditions for Disengage check (D&D rule)
        mover_conditions = current.conditions or []

        # Check each step of the path
        for i in range(len(path_result.path) - 1):
            from_pos = path_result.path[i]
            to_pos = path_result.path[i + 1]

            attackers = check_opportunity_attack_triggers(
                grid=grid,
                mover_id=current.id,
                from_pos=from_pos,
                to_pos=to_pos,
                enemy_ids=enemy_ids,
                mover_conditions=mover_conditions
            )

            for attacker_id in attackers:
                if reactions_mgr.has_reaction_available(attacker_id):
                    opportunity_attackers.append(attacker_id)

    # Execute the move
    final_pos = path_result.path[-1] if path_result.path else current_pos

    # Update grid
    grid.set_occupant(current_pos[0], current_pos[1], None)
    grid.set_occupant(final_pos[0], final_pos[1], current.id)

    # Update engine position
    move_result = engine.move_combatant(current.id, final_pos[0], final_pos[1])

    # Persist state to database
    await persist_combat_state(request.combat_id, engine, combat_repo)

    return MoveResponse(
        success=move_result.success,
        path=[list(p) for p in path_result.path],
        distance=path_result.total_cost,
        description=move_result.description,
        opportunity_attacks=opportunity_attackers,
        combat_state=engine.get_combat_state()
    )


# =============================================================================
# Legendary Actions
# =============================================================================

class LegendaryActionRequest(BaseModel):
    """Request to use a legendary action."""
    combat_id: str
    monster_id: str
    action_id: str
    target_id: Optional[str] = None


class LegendaryActionResponse(BaseModel):
    """Response from using a legendary action."""
    success: bool
    description: str
    damage_dealt: int = 0
    actions_remaining: int = 0
    combat_state: Optional[Dict[str, Any]] = None


@router.post("/legendary-action", response_model=LegendaryActionResponse)
async def use_legendary_action(
    request: LegendaryActionRequest,
    combat_repo: CombatStateRepository = Depends(get_combat_repo),
):
    """
    Use a legendary action for a legendary creature.

    Can only be used at the end of another creature's turn.
    Persists state to database after use.
    """
    engine = active_combats.get(request.combat_id)

    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    # Execute the legendary action
    result = engine.execute_legendary_action(
        monster_id=request.monster_id,
        action_id=request.action_id,
        target_id=request.target_id
    )

    # Persist state after legendary action
    await persist_combat_state(
        request.combat_id,
        engine.state,
        combat_repo,
        reason="legendary_action"
    )

    return LegendaryActionResponse(
        success=result.success,
        description=result.description,
        damage_dealt=result.extra_data.get("damage", 0) if result.extra_data else 0,
        actions_remaining=engine.state.legendary_actions_remaining.get(request.monster_id, 0),
        combat_state=engine.get_combat_state()
    )


@router.post("/reaction", response_model=ReactionResponse)
async def use_reaction(
    request: ReactionRequest,
    combat_repo: CombatStateRepository = Depends(get_combat_repo),
):
    """
    Use a reaction in response to a trigger.

    Examples: opportunity attack, Shield spell, Uncanny Dodge
    Persists state to database after reaction.
    """
    print(f"[REACTION] Request received: combat_id={request.combat_id}, "
          f"reaction_type={request.reaction_type}, trigger_source_id={request.trigger_source_id}, "
          f"extra_data={request.extra_data}", flush=True)

    engine = active_combats.get(request.combat_id)
    reactions_mgr = reactions_managers.get(request.combat_id)

    if not engine or not reactions_mgr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    # Get the reacting combatant (current target of some action)
    # This would typically be passed in the request
    reactor_id = request.extra_data.get("reactor_id")
    if not reactor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reactor_id required in extra_data"
        )

    if not reactions_mgr.has_reaction_available(reactor_id):
        return ReactionResponse(
            success=False,
            description="No reaction available",
            combat_state=engine.get_combat_state()
        )

    reactor = engine.state.initiative_tracker.get_combatant(reactor_id)
    reactor_stats = engine.state.combatant_stats.get(reactor_id, {})

    trigger_source = engine.state.initiative_tracker.get_combatant(
        request.trigger_source_id
    )

    # Route to appropriate handler
    try:
        reaction_type = ReactionType(request.reaction_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid reaction type: {request.reaction_type}"
        )

    result = None

    if reaction_type == ReactionType.OPPORTUNITY_ATTACK:
        result = resolve_opportunity_attack(
            attacker_id=reactor_id,
            attacker_name=reactor.name if reactor else "Unknown",
            target_id=request.trigger_source_id,
            target_name=trigger_source.name if trigger_source else "Unknown",
            attack_bonus=reactor_stats.get("attack_bonus", 0),
            target_ac=engine.state.combatant_stats.get(
                request.trigger_source_id, {}
            ).get("ac", 10),
            damage_dice=reactor_stats.get("damage_dice", "1d6"),
            damage_modifier=reactor_stats.get("str_mod", 0)
        )

    elif reaction_type == ReactionType.SHIELD:
        attack_roll = request.extra_data.get("attack_roll", 0)
        result = resolve_shield_spell(
            caster_id=reactor_id,
            caster_name=reactor.name if reactor else "Unknown",
            attack_roll=attack_roll,
            current_ac=reactor_stats.get("ac", 10),
            has_spell_slot=reactor_stats.get("abilities", {}).get(
                "spell_slots_1st", 0
            ) > 0
        )

    elif reaction_type == ReactionType.UNCANNY_DODGE:
        damage = request.extra_data.get("damage", 0)
        result = resolve_uncanny_dodge(
            rogue_id=reactor_id,
            rogue_name=reactor.name if reactor else "Unknown",
            damage_amount=damage
        )

    elif reaction_type == ReactionType.RIPOSTE:
        # Battlemaster Riposte - counter-attack when missed
        superiority_die = request.extra_data.get("superiority_die", "1d8")
        trigger_source_stats = engine.state.combatant_stats.get(
            request.trigger_source_id, {}
        )
        result = resolve_riposte(
            attacker_id=reactor_id,
            attacker_name=reactor.name if reactor else "Unknown",
            target_id=request.trigger_source_id,
            target_name=trigger_source.name if trigger_source else "Unknown",
            attack_bonus=reactor_stats.get("attack_bonus", 0),
            target_ac=trigger_source_stats.get("ac", 10),
            damage_dice=reactor_stats.get("damage_dice", "1d6"),
            damage_modifier=reactor_stats.get("str_mod", 0),
            superiority_die=superiority_die
        )
        # Deduct superiority die
        if result and result.success:
            current_dice = reactor_stats.get("superiority_dice", 0)
            if current_dice > 0:
                engine.state.combatant_stats[reactor_id]["superiority_dice"] = current_dice - 1

    if result:
        # Mark reaction as used
        reactions_mgr.use_reaction(reactor_id)

        # Apply damage to target if opportunity attack or riposte hit
        damage_reactions = [ReactionType.OPPORTUNITY_ATTACK, ReactionType.RIPOSTE]
        if result.damage_dealt > 0 and reaction_type in damage_reactions:
            target_stats = engine.state.combatant_stats.get(request.trigger_source_id, {})
            current_hp = target_stats.get("current_hp", trigger_source.current_hp if trigger_source else 0)
            new_hp = max(0, current_hp - result.damage_dealt)

            # Update stats
            if request.trigger_source_id in engine.state.combatant_stats:
                engine.state.combatant_stats[request.trigger_source_id]["current_hp"] = new_hp

            # Update combatant object
            if trigger_source:
                trigger_source.current_hp = new_hp
                if new_hp <= 0:
                    trigger_source.is_active = False

            # Check for Sentinel speed reduction on OA hit
            is_sentinel_attack = result.extra_data.get("sentinel", False)
            if is_sentinel_attack and result.extra_data.get("speed_reduced_to_zero", False):
                # Apply speed_zero condition for rest of turn
                if "speed_zero" not in trigger_source.conditions:
                    trigger_source.conditions.append("speed_zero")

            # Log the damage
            event_type = reaction_type.value
            engine.state.add_event(
                event_type,
                result.description,
                combatant_id=reactor_id,
                data={
                    "damage": result.damage_dealt,
                    "target_id": request.trigger_source_id,
                    "sentinel": is_sentinel_attack if reaction_type == ReactionType.OPPORTUNITY_ATTACK else False,
                }
            )

        # Persist state to database
        await persist_combat_state(request.combat_id, engine, combat_repo)

        return ReactionResponse(
            success=result.success,
            description=result.description,
            damage_dealt=result.damage_dealt,
            damage_prevented=result.damage_prevented,
            effects_applied=result.effects_applied,
            combat_state=engine.get_combat_state()
        )

    return ReactionResponse(
        success=False,
        description="Reaction type not implemented",
        combat_state=engine.get_combat_state()
    )


def process_enemy_turn_advanced(
    engine: CombatEngine,
    grid: CombatGrid,
    enemy
) -> Optional[EnemyAction]:
    """
    Advanced enemy AI using tactical decision-making system.

    Uses role-based behaviors (Brute, Striker, Caster, etc.) and
    intelligent target prioritization.

    Returns an EnemyAction describing what the enemy did.
    """
    import re
    from app.core.initiative import CombatantType

    tracker = engine.state.initiative_tracker

    # Get the AI behavior for this enemy
    ai = get_ai_for_combatant(engine, enemy.id)

    # Get the AI's decision
    decision = ai.decide_action()

    if not decision:
        return EnemyAction(
            enemy_id=enemy.id,
            enemy_name=enemy.name,
            action_type="none",
            description=f"{enemy.name} considers their options."
        )

    # Convert AI decision to action
    action_type = decision.action_type

    # Handle different action types
    if action_type == "attack" or action_type == "ranged_attack":
        target_id = decision.target_id
        target = tracker.get_combatant(target_id) if target_id else None

        if not target:
            # No valid target, try to move
            return _execute_ai_movement(engine, grid, enemy, decision)

        # Check if we need to move to reach the target
        enemy_pos = engine.state.positions.get(enemy.id)
        target_pos = engine.state.positions.get(target_id)

        if enemy_pos and target_pos:
            dx = abs(target_pos[0] - enemy_pos[0])
            dy = abs(target_pos[1] - enemy_pos[1])
            is_adjacent = (dx <= 1 and dy <= 1 and (dx + dy) > 0)

            # Move if needed for melee
            if action_type == "attack" and not is_adjacent:
                move_result = _execute_ai_movement(engine, grid, enemy, decision)
                # After moving, check if now adjacent
                enemy_pos = engine.state.positions.get(enemy.id)
                if enemy_pos:
                    dx = abs(target_pos[0] - enemy_pos[0])
                    dy = abs(target_pos[1] - enemy_pos[1])
                    is_adjacent = (dx <= 1 and dy <= 1 and (dx + dy) > 0)

                if not is_adjacent:
                    # Couldn't reach, just return the move
                    return move_result

        # Execute the attack
        result = engine.take_action(
            action_type=ActionType.ATTACK,
            target_id=target_id
        )

        hit = result.extra_data.get("hit", False) if result.success else False
        damage = result.damage_dealt if hit else 0

        # Extract attack details
        attack_roll_obj = result.extra_data.get("attack_roll") if result.extra_data else None
        critical = result.extra_data.get("critical_hit", False) if result.extra_data else False
        critical_miss = result.extra_data.get("critical_miss", False) if result.extra_data else False
        target_ac = result.extra_data.get("target_ac") if result.extra_data else None

        natural_roll = None
        attack_modifier = None
        attack_total = None
        advantage = False
        disadvantage = False
        second_roll = None

        if attack_roll_obj and hasattr(attack_roll_obj, "total"):
            attack_total = attack_roll_obj.total
            natural_roll = attack_roll_obj.base_roll
            attack_modifier = attack_roll_obj.modifier
            advantage = attack_roll_obj.advantage
            disadvantage = attack_roll_obj.disadvantage
            if len(attack_roll_obj.rolls) > 1:
                if advantage:
                    second_roll = min(attack_roll_obj.rolls)
                elif disadvantage:
                    second_roll = max(attack_roll_obj.rolls)

        # Get damage details
        enemy_stats = engine.state.combatant_stats.get(enemy.id, {})
        damage_dice = enemy_stats.get("damage_dice", "1d6")
        damage_type = enemy_stats.get("damage_type", "slashing")

        # Parse damage formula
        damage_modifier = 0
        damage_rolls = []
        if hit and damage > 0:
            match = re.match(r"(\d+)d(\d+)(?:\+(\d+))?", damage_dice)
            if match:
                num_dice = int(match.group(1))
                die_size = int(match.group(2))
                damage_modifier = int(match.group(3)) if match.group(3) else 0
                dice_total = damage - damage_modifier
                if critical:
                    num_dice *= 2
                if num_dice > 0 and dice_total > 0:
                    avg_per_die = dice_total / num_dice
                    for i in range(num_dice):
                        roll = min(max(1, round(avg_per_die)), die_size)
                        damage_rolls.append(roll)
                    current_total = sum(damage_rolls)
                    if current_total != dice_total and damage_rolls:
                        diff = dice_total - current_total
                        damage_rolls[-1] = max(1, min(die_size, damage_rolls[-1] + diff))

        # Build description with AI reasoning
        hit_text = f"Hit for {damage} damage!" if hit else "Miss!"
        description = f"{enemy.name} {decision.reasoning} - {hit_text}"

        return EnemyAction(
            enemy_id=enemy.id,
            enemy_name=enemy.name,
            action_type="attack",
            description=description,
            target_id=target_id,
            damage_dealt=damage,
            hit=hit,
            attack_roll=attack_total,
            natural_roll=natural_roll,
            attack_modifier=attack_modifier,
            target_ac=target_ac,
            critical=critical,
            critical_miss=critical_miss,
            advantage=advantage,
            disadvantage=disadvantage,
            second_roll=second_roll,
            damage_formula=damage_dice,
            damage_rolls=damage_rolls if damage_rolls else None,
            damage_modifier=damage_modifier,
            damage_type=damage_type
        )

    elif action_type == "dash":
        return _execute_ai_movement(engine, grid, enemy, decision, is_dash=True)

    elif action_type == "move":
        return _execute_ai_movement(engine, grid, enemy, decision)

    elif action_type == "dodge":
        # Apply dodging condition - attackers have disadvantage until start of next turn
        enemy_stats = engine.state.combatant_stats.get(enemy.id, {})
        conditions = enemy_stats.get("conditions", [])

        if "dodging" not in conditions:
            conditions.append("dodging")
            enemy_stats["conditions"] = conditions

        return EnemyAction(
            enemy_id=enemy.id,
            enemy_name=enemy.name,
            action_type="dodge",
            description=f"{enemy.name} takes the Dodge action. Attacks against them have disadvantage. {decision.reasoning}",
            effects=["dodging"],
        )

    elif action_type == "disengage":
        # Mark as disengaged for this turn
        return EnemyAction(
            enemy_id=enemy.id,
            enemy_name=enemy.name,
            action_type="disengage",
            description=f"{enemy.name} disengages. {decision.reasoning}"
        )

    elif action_type == "hide":
        return EnemyAction(
            enemy_id=enemy.id,
            enemy_name=enemy.name,
            action_type="hide",
            description=f"{enemy.name} attempts to hide. {decision.reasoning}"
        )

    elif action_type in ("spell", "cantrip"):
        # Enemy spell casting implementation
        from app.core.spell_system import cast_spell, SpellRegistry

        spell_id = decision.spell_id
        if not spell_id:
            return EnemyAction(
                enemy_id=enemy.id,
                enemy_name=enemy.name,
                action_type="spell",
                description=f"{enemy.name} tries to cast a spell but fails to focus."
            )

        # Get spell info
        registry = SpellRegistry.get_instance()
        spell = registry.get_spell(spell_id)

        if not spell:
            return EnemyAction(
                enemy_id=enemy.id,
                enemy_name=enemy.name,
                action_type="spell",
                description=f"{enemy.name} attempts an unknown spell: {spell_id}"
            )

        # Build caster data from enemy stats
        enemy_stats = engine.state.combatant_stats.get(enemy.id, {})
        caster_data = {
            "id": enemy.id,
            "name": enemy.name,
            "level": enemy_stats.get("level", enemy_stats.get("cr", 1) * 2 or 1),
            "spellcasting": {
                "spell_attack_bonus": enemy_stats.get("spell_attack", 5),
                "spell_save_dc": enemy_stats.get("spell_dc", 13),
                "slots": enemy_stats.get("spell_slots", {}),
                "spells_known": enemy_stats.get("spells", []),
            },
        }

        # Build targets list
        targets = []
        if decision.target_id:
            target = engine.state.initiative_tracker.get_combatant(decision.target_id)
            target_stats = engine.state.combatant_stats.get(decision.target_id, {})
            if target:
                targets.append({
                    "id": target.id,
                    "name": target.name,
                    "ac": target_stats.get("ac", target.ac),
                    "current_hp": target_stats.get("current_hp", 0),
                    "saving_throws": target_stats.get("saving_throws", {}),
                })

        # Determine slot level (cantrips use None)
        slot_level = None if spell.level == 0 else spell.level

        # Cast the spell
        result = cast_spell(caster_data, spell_id, slot_level, targets)

        # Apply damage if any
        total_damage = 0
        if result.damage_dealt and result.success:
            total_damage = result.damage_dealt
            if decision.target_id and decision.target_id in engine.state.combatant_stats:
                target_stats = engine.state.combatant_stats[decision.target_id]
                current_hp = target_stats.get("current_hp", 0)
                target_stats["current_hp"] = max(0, current_hp - total_damage)

        return EnemyAction(
            enemy_id=enemy.id,
            enemy_name=enemy.name,
            action_type="spell",
            target_id=decision.target_id,
            description=f"{enemy.name} casts {spell.name}! {result.description}",
            damage_dealt=total_damage,
            hit=result.success,
            effects=result.effects_applied if hasattr(result, 'effects_applied') else [],
        )

    # Default fallback
    return EnemyAction(
        enemy_id=enemy.id,
        enemy_name=enemy.name,
        action_type="none",
        description=f"{enemy.name} waits."
    )


def _execute_ai_movement(
    engine: CombatEngine,
    grid: CombatGrid,
    enemy,
    decision,
    is_dash: bool = False
) -> Optional[EnemyAction]:
    """Execute movement based on AI decision."""
    from app.core.initiative import CombatantType

    enemy_pos = engine.state.positions.get(enemy.id)
    if not enemy_pos:
        return None

    # Determine target position
    target_pos = None
    target_name = "their objective"

    if decision.target_id:
        target_pos = engine.state.positions.get(decision.target_id)
        target = engine.state.initiative_tracker.get_combatant(decision.target_id)
        if target:
            target_name = target.name
    elif decision.position:
        target_pos = decision.position

    if not target_pos:
        return EnemyAction(
            enemy_id=enemy.id,
            enemy_name=enemy.name,
            action_type="none",
            description=f"{enemy.name} has nowhere to move."
        )

    # Get enemy speed
    enemy_stats = engine.state.combatant_stats.get(enemy.id, {})
    speed = enemy_stats.get("speed", 30)
    if is_dash:
        speed *= 2

    # Get reachable cells
    reachable = get_reachable_cells(
        grid,
        enemy_pos[0],
        enemy_pos[1],
        speed,
        include_occupied=False
    )

    if not reachable:
        return EnemyAction(
            enemy_id=enemy.id,
            enemy_name=enemy.name,
            action_type="none",
            description=f"{enemy.name} cannot move."
        )

    # Find closest cell to target
    best_cell = None
    best_dist = float('inf')

    for (rx, ry, cost) in reachable:
        dist = abs(target_pos[0] - rx) + abs(target_pos[1] - ry)
        if dist < best_dist:
            best_dist = dist
            best_cell = (rx, ry)

    if best_cell and best_cell != tuple(enemy_pos):
        old_pos = list(enemy_pos)

        # Get path for animation
        path_result = find_path(
            grid,
            enemy_pos[0],
            enemy_pos[1],
            best_cell[0],
            best_cell[1],
            max_movement=speed
        )

        # Update position
        engine.state.positions[enemy.id] = best_cell
        grid.set_occupant(enemy_pos[0], enemy_pos[1], None)
        grid.set_occupant(best_cell[0], best_cell[1], enemy.id)

        movement_path = [[x, y] for x, y in path_result.path] if path_result.success else None
        action_type = "dash" if is_dash else "move"

        return EnemyAction(
            enemy_id=enemy.id,
            enemy_name=enemy.name,
            action_type=action_type,
            description=f"{enemy.name} {'dashes' if is_dash else 'moves'} toward {target_name}. {decision.reasoning}",
            movement_path=movement_path,
            old_position=old_pos,
            new_position=list(best_cell)
        )

    return None


def process_enemy_turn(engine: CombatEngine, grid: CombatGrid, enemy) -> Optional[EnemyAction]:
    """
    Simple enemy AI: Find nearest player and attack if adjacent, otherwise move toward them.

    Returns an EnemyAction describing what the enemy did, or None if no action taken.
    """
    tracker = engine.state.initiative_tracker

    # Find all active players
    players = [c for c in tracker.combatants
               if c.is_active and c.combatant_type == CombatantType.PLAYER]

    if not players:
        return EnemyAction(
            enemy_id=enemy.id,
            enemy_name=enemy.name,
            action_type="none",
            description=f"{enemy.name} has no targets."
        )

    # Get enemy position
    enemy_pos = engine.state.positions.get(enemy.id)
    if not enemy_pos:
        return None

    # Find nearest player
    nearest_player = None
    nearest_distance = float('inf')

    for player in players:
        player_pos = engine.state.positions.get(player.id)
        if player_pos:
            # Manhattan distance
            dist = abs(player_pos[0] - enemy_pos[0]) + abs(player_pos[1] - enemy_pos[1])
            if dist < nearest_distance:
                nearest_distance = dist
                nearest_player = player

    if not nearest_player:
        return None

    player_pos = engine.state.positions.get(nearest_player.id)

    # Check if adjacent (distance 1 = adjacent for attack)
    dx = abs(player_pos[0] - enemy_pos[0])
    dy = abs(player_pos[1] - enemy_pos[1])
    is_adjacent = (dx <= 1 and dy <= 1 and (dx + dy) > 0)

    if is_adjacent:
        # Attack the player using take_action
        result = engine.take_action(
            action_type=ActionType.ATTACK,
            target_id=nearest_player.id
        )
        hit = result.extra_data.get("hit", False) if result.success else False
        damage = result.damage_dealt if hit else 0

        # Extract attack roll details for dice animation
        attack_roll_obj = result.extra_data.get("attack_roll") if result.extra_data else None
        critical = result.extra_data.get("critical_hit", False) if result.extra_data else False
        critical_miss = result.extra_data.get("critical_miss", False) if result.extra_data else False
        target_ac = result.extra_data.get("target_ac") if result.extra_data else None

        # Extract D20Result details
        natural_roll = None
        attack_modifier = None
        attack_total = None
        advantage = False
        disadvantage = False
        second_roll = None

        if attack_roll_obj and hasattr(attack_roll_obj, "total"):
            attack_total = attack_roll_obj.total
            natural_roll = attack_roll_obj.base_roll
            attack_modifier = attack_roll_obj.modifier
            advantage = attack_roll_obj.advantage
            disadvantage = attack_roll_obj.disadvantage
            if len(attack_roll_obj.rolls) > 1:
                # Get the roll that wasn't used
                if advantage:
                    second_roll = min(attack_roll_obj.rolls)
                elif disadvantage:
                    second_roll = max(attack_roll_obj.rolls)

        # Get damage details from enemy stats
        enemy_stats = engine.state.combatant_stats.get(enemy.id, {})
        damage_dice = enemy_stats.get("damage_dice", "1d6")
        damage_type = enemy_stats.get("damage_type", "slashing")

        # Parse damage formula to extract modifier and calculate individual rolls
        import re
        damage_modifier = 0
        damage_rolls = []
        if hit and damage > 0:
            # Parse formula like "1d6+2" or "2d6+3"
            match = re.match(r"(\d+)d(\d+)(?:\+(\d+))?", damage_dice)
            if match:
                num_dice = int(match.group(1))
                die_size = int(match.group(2))
                damage_modifier = int(match.group(3)) if match.group(3) else 0

                # Calculate total roll from dice (damage - modifier)
                dice_total = damage - damage_modifier
                if critical:
                    # Critical doubles dice, so we have twice as many
                    num_dice *= 2

                # Distribute dice_total across dice (approximate)
                if num_dice > 0 and dice_total > 0:
                    avg_per_die = dice_total / num_dice
                    for i in range(num_dice):
                        roll = min(max(1, round(avg_per_die)), die_size)
                        damage_rolls.append(roll)
                    # Adjust last roll to match total exactly
                    current_total = sum(damage_rolls)
                    if current_total != dice_total and damage_rolls:
                        diff = dice_total - current_total
                        damage_rolls[-1] = max(1, min(die_size, damage_rolls[-1] + diff))

        return EnemyAction(
            enemy_id=enemy.id,
            enemy_name=enemy.name,
            action_type="attack",
            description=f"{enemy.name} attacks {nearest_player.name}! {'Hit for ' + str(damage) + ' damage!' if hit else 'Miss!'}",
            target_id=nearest_player.id,
            damage_dealt=damage,
            hit=hit,
            attack_roll=attack_total,
            natural_roll=natural_roll,
            attack_modifier=attack_modifier,
            target_ac=target_ac,
            critical=critical,
            critical_miss=critical_miss,
            advantage=advantage,
            disadvantage=disadvantage,
            second_roll=second_roll,
            damage_formula=damage_dice,
            damage_rolls=damage_rolls if damage_rolls else None,
            damage_modifier=damage_modifier,
            damage_type=damage_type
        )
    else:
        # Try to move toward the player
        # Get reachable cells for enemy
        reachable = get_reachable_cells(
            grid,
            enemy_pos[0],
            enemy_pos[1],
            30,  # Assume 30ft speed
            include_occupied=False
        )

        if reachable:
            # Find the reachable cell closest to the player
            best_cell = None
            best_dist = float('inf')

            for (rx, ry, cost) in reachable:
                dist = abs(player_pos[0] - rx) + abs(player_pos[1] - ry)
                if dist < best_dist:
                    best_dist = dist
                    best_cell = (rx, ry)

            if best_cell and best_cell != enemy_pos:
                # Get the full path for animation
                old_pos = list(enemy_pos)
                path_result = find_path(
                    grid,
                    enemy_pos[0],
                    enemy_pos[1],
                    best_cell[0],
                    best_cell[1],
                    max_movement=30
                )

                # Move to that cell - update BOTH engine state AND grid occupancy
                # D&D rules: Must track occupancy to prevent stacking
                engine.state.positions[enemy.id] = best_cell
                grid.set_occupant(enemy_pos[0], enemy_pos[1], None)  # Clear old position
                grid.set_occupant(best_cell[0], best_cell[1], enemy.id)  # Set new position

                # Convert path to list of [x, y] pairs for frontend
                movement_path = [[x, y] for x, y in path_result.path] if path_result.success else None

                return EnemyAction(
                    enemy_id=enemy.id,
                    enemy_name=enemy.name,
                    action_type="move",
                    description=f"{enemy.name} moves toward {nearest_player.name}.",
                    movement_path=movement_path,
                    old_position=old_pos,
                    new_position=list(best_cell)
                )

        return EnemyAction(
            enemy_id=enemy.id,
            enemy_name=enemy.name,
            action_type="none",
            description=f"{enemy.name} cannot reach any targets."
        )


@router.post("/{combat_id}/end-turn", response_model=EndTurnResponse)
async def end_turn(
    combat_id: str,
    combat_repo: CombatStateRepository = Depends(get_combat_repo),
):
    """
    End the current combatant's turn and advance to the next.
    If the next combatant is an enemy, process all enemy turns automatically
    until it's a player's turn again.
    Persists state to database after turn changes.
    """
    engine = active_combats.get(combat_id)
    grid = active_grids.get(combat_id)
    reactions_mgr = reactions_managers.get(combat_id)

    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    enemy_actions: List[EnemyAction] = []
    tracker = engine.state.initiative_tracker

    # End current turn and advance
    try:
        next_combatant = engine.end_turn()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Reset reaction for the combatant whose turn just started
    if next_combatant and reactions_mgr:
        reactions_mgr.reset_combatant_reaction(next_combatant.id)

    # Process enemy turns automatically
    max_iterations = 20  # Safety limit to prevent infinite loops
    iterations = 0

    while next_combatant and iterations < max_iterations:
        # Check if combat is over
        if tracker.is_combat_over():
            break

        # If it's a player's turn, stop and wait for input
        if next_combatant.combatant_type == CombatantType.PLAYER:
            break

        # Enemy turn - process with AI
        if grid:
            # Use advanced AI if enabled, fallback to simple AI
            if USE_ADVANCED_AI:
                try:
                    action = process_enemy_turn_advanced(engine, grid, next_combatant)
                except Exception as e:
                    # Fallback to simple AI on error
                    print(f"[AI] Advanced AI error: {e}, falling back to simple AI")
                    action = process_enemy_turn(engine, grid, next_combatant)
            else:
                action = process_enemy_turn(engine, grid, next_combatant)

            if action:
                enemy_actions.append(action)

        # Advance to next combatant
        try:
            next_combatant = engine.end_turn()
            if next_combatant and reactions_mgr:
                reactions_mgr.reset_combatant_reaction(next_combatant.id)
        except ValueError:
            break

        iterations += 1

    # Get final state
    combat_over = tracker.is_combat_over()
    combat_result = tracker.get_combat_result()

    # Persist state to database
    await persist_combat_state(combat_id, engine, combat_repo)

    # If combat ended, update database record
    if combat_over and combat_result:
        await end_combat_state(combat_id, result=combat_result, xp_awarded=0, repo=combat_repo)

    return EndTurnResponse(
        success=True,
        next_combatant=next_combatant.to_dict() if next_combatant else None,
        round_number=tracker.current_round,
        current_turn_index=tracker.current_turn_index,
        enemy_actions=enemy_actions,
        combat_state=engine.get_combat_state(),
        combat_over=combat_over,
        combat_result=combat_result
    )


# =============================================================================
# Query Endpoints
# =============================================================================

@router.get("/{combat_id}/reachable")
async def get_reachable_positions(combat_id: str):
    """
    Get all positions the current combatant can reach with their remaining movement.
    """
    engine = active_combats.get(combat_id)
    grid = active_grids.get(combat_id)

    if not engine or not grid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    current = engine.get_current_combatant()
    if not current:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No current combatant"
        )

    pos = engine.state.positions.get(current.id)
    if not pos:
        return {"reachable": []}

    stats = engine.state.combatant_stats.get(current.id, {})
    speed = stats.get("speed", 30)
    turn = engine.get_turn_state()
    remaining = speed - (turn.movement_used if turn else 0)

    # Determine ally IDs for the current combatant
    tracker = engine.state.initiative_tracker
    ally_ids = set()
    for c in tracker.combatants:
        if c.id != current.id and c.is_active and c.combatant_type == current.combatant_type:
            ally_ids.add(c.id)

    reachable = get_reachable_cells(
        grid, pos[0], pos[1], remaining,
        mover_id=current.id,
        ally_ids=ally_ids
    )

    return {
        "current_position": list(pos),
        "movement_remaining": remaining,
        "reachable": [
            {"x": x, "y": y, "cost": cost}
            for x, y, cost in reachable
        ]
    }


@router.get("/{combat_id}/threat-zones")
async def get_threat_zones(
    combat_id: str,
    combatant_id: Optional[str] = None
):
    """
    Get threat zones for all enemies or a specific combatant.

    Threat zones indicate cells where opportunity attacks could be triggered
    if the player moves out of them.

    Args:
        combat_id: The combat session ID
        combatant_id: Optional specific enemy ID to get threat zones for

    Returns:
        Dictionary mapping enemy IDs to their threat zone data:
        {
            "threat_zones": {
                "enemy_id": {
                    "name": "Goblin",
                    "reach": 5,
                    "cells": [{"x": 3, "y": 4}, ...]
                }
            }
        }
    """
    engine = active_combats.get(combat_id)
    grid = active_grids.get(combat_id)

    if not engine or not grid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    threat_zones = {}
    tracker = engine.state.initiative_tracker

    # Get threat zones for enemies (or specific combatant)
    for combatant in tracker.combatants:
        if not combatant.is_active:
            continue
        if combatant_id and combatant.id != combatant_id:
            continue
        # Only show enemy threats (players don't need to see their own)
        if combatant.combatant_type == CombatantType.PLAYER:
            continue

        # Get enemy's reach (default 5ft for melee)
        stats = engine.state.combatant_stats.get(combatant.id, {})
        reach = stats.get("reach", 5)

        # Get position
        pos = engine.state.positions.get(combatant.id)
        if not pos:
            continue

        # Calculate threatened squares
        threatened = get_threatened_squares(grid, combatant.id, reach)
        threat_zones[combatant.id] = {
            "name": combatant.name,
            "reach": reach,
            "cells": [{"x": x, "y": y} for x, y in threatened]
        }

    return {"threat_zones": threat_zones}


@router.get("/{combat_id}/targets")
async def get_valid_targets(
    combat_id: str,
    combatant_id: Optional[str] = None,
    range_ft: int = 5,
    weapon_id: Optional[str] = None
):
    """
    Get valid targets for a combatant.

    Args:
        combat_id: The combat session ID
        combatant_id: The attacking combatant's ID (uses current combatant if not provided)
        range_ft: Range in feet (default 5 for melee)
        weapon_id: Optional weapon ID to auto-determine range from weapon data
    """
    engine = active_combats.get(combat_id)

    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    # Use provided combatant_id if given, otherwise use current combatant
    if combatant_id:
        current = engine.state.initiative_tracker.get_combatant(combatant_id)
        if not current:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Combatant not found: {combatant_id}"
            )
    else:
        current = engine.get_current_combatant()
        if not current:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No current combatant"
            )

    # If weapon_id provided, use the weapon's range
    if weapon_id:
        weapon_data = load_weapon_data(weapon_id)
        if weapon_data:
            # Use long_range for maximum targeting, normal range for no-disadvantage
            range_ft = weapon_data.get("long_range") or weapon_data.get("range", 5)

    targets = engine.get_valid_targets(current.id, range_ft)

    # Get target info
    target_info = []
    for tid in targets:
        combatant = engine.state.initiative_tracker.get_combatant(tid)
        stats = engine.state.combatant_stats.get(tid, {})
        if combatant:
            target_info.append({
                "id": tid,
                "name": combatant.name,
                "current_hp": stats.get("current_hp", combatant.current_hp),
                "max_hp": stats.get("max_hp", combatant.max_hp),
                "ac": stats.get("ac", combatant.armor_class),
                "conditions": combatant.conditions
            })

    return {"targets": target_info}


@router.get("/{combat_id}/initiative")
async def get_initiative_order(combat_id: str):
    """
    Get the current initiative order.
    """
    engine = active_combats.get(combat_id)

    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    return {
        "round": engine.state.initiative_tracker.current_round,
        "order": engine.state.initiative_tracker.get_initiative_order()
    }


@router.get("/{combat_id}/events")
async def get_combat_events(combat_id: str, count: int = 20):
    """
    Get recent combat events.
    """
    engine = active_combats.get(combat_id)

    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    return {"events": engine.get_recent_events(count)}


# =============================================================================
# CLASS FEATURE ENDPOINTS
# =============================================================================

class ActionSurgeRequest(BaseModel):
    """Request to use Action Surge."""
    combat_id: str
    combatant_id: str


class DivineSmiteRequest(BaseModel):
    """Request to use Divine Smite."""
    combat_id: str
    slot_level: int = Field(ge=1, le=5, description="Spell slot level to expend")
    target_id: str


class ClassFeatureResponse(BaseModel):
    """Response for class feature usage."""
    success: bool
    description: str
    damage_dealt: int = 0
    extra_data: Dict[str, Any] = {}
    combat_state: Optional[Dict[str, Any]] = None


@router.post("/{combat_id}/action-surge", response_model=ClassFeatureResponse)
async def use_action_surge(
    combat_id: str,
    combatant_id: str,
    combat_repo: CombatStateRepository = Depends(get_combat_repo),
):
    """
    Use Fighter's Action Surge to gain an additional action.

    D&D 5e Rules:
    - Requires Fighter level 2+
    - Resets action availability for current turn
    - Can only be used once per turn
    - Limited uses per short/long rest
    """
    engine = active_combats.get(combat_id)

    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    # Verify it's the combatant's turn
    current = engine.get_current_combatant()
    if not current or current.id != combatant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only use Action Surge on your turn"
        )

    result = engine.use_action_surge()

    # Persist state to database
    await persist_combat_state(combat_id, engine, combat_repo)

    return ClassFeatureResponse(
        success=result.success,
        description=result.description,
        extra_data=result.extra_data,
        combat_state=engine.get_combat_state()
    )


@router.post("/{combat_id}/divine-smite", response_model=ClassFeatureResponse)
async def use_divine_smite(
    combat_id: str,
    slot_level: int = 1,
    target_id: str = "",
    combat_repo: CombatStateRepository = Depends(get_combat_repo),
):
    """
    Use Paladin's Divine Smite to deal extra radiant damage.

    D&D 5e Rules:
    - Requires Paladin level 2+
    - Expends a spell slot (1st-5th level)
    - Deals 2d8 + 1d8 per slot level above 1st (max 5d8)
    - +1d8 vs undead or fiends
    - Can be used after a successful hit
    """
    engine = active_combats.get(combat_id)

    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    if not target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target ID is required for Divine Smite"
        )

    result = engine.use_divine_smite(slot_level, target_id)

    # Persist state to database
    await persist_combat_state(combat_id, engine, combat_repo)

    return ClassFeatureResponse(
        success=result.success,
        description=result.description,
        damage_dealt=result.damage_dealt,
        extra_data=result.extra_data,
        combat_state=engine.get_combat_state()
    )


@router.get("/{combat_id}/class-features/{combatant_id}")
async def get_class_features(combat_id: str, combatant_id: str):
    """
    Get available class features and their resources for a combatant.

    Returns:
        - Available features based on class and level
        - Current resource counts (rage uses, action surge uses, spell slots, etc.)
        - Whether features are currently active (e.g., is_raging)
    """
    engine = active_combats.get(combat_id)

    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    stats = engine.state.combatant_stats.get(combatant_id, {})
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combatant not found"
        )

    class_id = stats.get("class", "").lower()
    level = stats.get("level", 1)

    features = {
        "class": class_id,
        "level": level,
        "available_features": [],
        "resources": {}
    }

    # Fighter features
    if class_id == "fighter":
        if level >= 1:
            features["available_features"].append({
                "id": "second_wind",
                "name": "Second Wind",
                "type": "bonus_action",
                "uses_remaining": 1 if not engine.state.current_turn.bonus_action_taken else 0,
                "description": "Regain 1d10 + level HP as bonus action"
            })
        if level >= 2:
            features["available_features"].append({
                "id": "action_surge",
                "name": "Action Surge",
                "type": "free",
                "uses_remaining": stats.get("action_surge_uses", 0),
                "description": "Gain an additional action this turn"
            })
            features["resources"]["action_surge_uses"] = stats.get("action_surge_uses", 0)

    # Rogue features
    elif class_id == "rogue":
        if level >= 2:
            features["available_features"].append({
                "id": "cunning_action",
                "name": "Cunning Action",
                "type": "bonus_action",
                "options": ["dash", "disengage", "hide"],
                "description": "Dash, Disengage, or Hide as bonus action"
            })
        features["resources"]["sneak_attack_used"] = engine.state.current_turn.sneak_attack_used

    # Barbarian features
    elif class_id == "barbarian":
        features["available_features"].append({
            "id": "rage",
            "name": "Rage",
            "type": "bonus_action",
            "uses_remaining": stats.get("rage_uses_remaining", 0),
            "is_active": stats.get("is_raging", False),
            "damage_bonus": stats.get("rage_damage_bonus", 0),
            "description": "Enter rage for damage bonus and resistance"
        })
        features["resources"]["rage_uses_remaining"] = stats.get("rage_uses_remaining", 0)
        features["resources"]["is_raging"] = stats.get("is_raging", False)
        features["resources"]["rage_damage_bonus"] = stats.get("rage_damage_bonus", 0)
        if level >= 2:
            features["available_features"].append({
                "id": "reckless_attack",
                "name": "Reckless Attack",
                "type": "special",
                "description": "Gain advantage on melee attacks, enemies gain advantage against you"
            })

    # Paladin features
    elif class_id == "paladin":
        if level >= 1:
            features["available_features"].append({
                "id": "lay_on_hands",
                "name": "Lay on Hands",
                "type": "action",
                "pool_remaining": stats.get("lay_on_hands_pool", 0),
                "description": "Heal HP from pool or cure disease/poison"
            })
            features["resources"]["lay_on_hands_pool"] = stats.get("lay_on_hands_pool", 0)
        if level >= 2:
            spell_slots = stats.get("spell_slots", {})
            features["available_features"].append({
                "id": "divine_smite",
                "name": "Divine Smite",
                "type": "on_hit",
                "spell_slots": spell_slots,
                "description": "Expend spell slot for extra radiant damage on hit"
            })
            features["resources"]["spell_slots"] = spell_slots

    return features


# =============================================================================
# DEATH SAVE ENDPOINTS
# =============================================================================

class DeathSaveRequest(BaseModel):
    """Request to manually roll a death save."""
    combat_id: str
    combatant_id: str


class StabilizeRequest(BaseModel):
    """Request to stabilize a dying combatant."""
    combat_id: str
    target_id: str
    method: str = "medicine"  # medicine, spare_the_dying, healer_kit
    helper_id: Optional[str] = None


class DeathSaveResponse(BaseModel):
    """Response from death save or stabilization."""
    success: bool
    roll: Optional[int] = None
    total: Optional[int] = None
    dc: int = 10
    outcome: str  # continue, stabilized, revived, dead
    successes: int = 0
    failures: int = 0
    description: str
    combat_state: Optional[Dict[str, Any]] = None


@router.post("/{combat_id}/death-save/{combatant_id}", response_model=DeathSaveResponse)
async def roll_death_save(
    combat_id: str,
    combatant_id: str,
    combat_repo: CombatStateRepository = Depends(get_combat_repo),
):
    """
    Roll a death saving throw for a dying combatant.

    D&D 5e Rules:
    - DC 10 Constitution saving throw
    - Natural 20: Regain 1 HP and consciousness
    - Natural 1: Counts as 2 failures
    - 3 successes: Stabilize (unconscious but not dying)
    - 3 failures: Death

    This is typically called automatically at turn start, but can be
    triggered manually for certain situations.
    """
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

    stats = engine.state.combatant_stats.get(combatant_id, {})

    # Validate combatant is at 0 HP and dying
    current_hp = stats.get("current_hp", combatant.current_hp)
    if current_hp > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Combatant is not at 0 HP - no death save needed"
        )

    is_dead = stats.get("is_dead", False)
    if is_dead:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Combatant is already dead"
        )

    is_stable = stats.get("is_stable", False)
    if is_stable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Combatant is already stable"
        )

    # Roll the death save
    try:
        from app.core.death_saves import (
            DeathSaveState,
            roll_death_save as roll_save,
            DeathSaveOutcome
        )

        state = DeathSaveState(
            successes=stats.get("death_save_successes", 0),
            failures=stats.get("death_save_failures", 0),
            is_stable=False,
            is_dead=False,
        )

        result = roll_save(state)

        # Update stats
        stats["death_save_successes"] = result.total_successes
        stats["death_save_failures"] = result.total_failures

        if result.outcome == DeathSaveOutcome.REVIVED:
            stats["current_hp"] = 1
            stats["death_save_successes"] = 0
            stats["death_save_failures"] = 0
            stats["is_stable"] = False
            combatant.current_hp = 1

        elif result.outcome == DeathSaveOutcome.STABILIZED:
            stats["is_stable"] = True
            stats["death_save_successes"] = 0
            stats["death_save_failures"] = 0

        elif result.outcome == DeathSaveOutcome.DEAD:
            stats["is_dead"] = True
            combatant.is_active = False

        # Log event
        engine.state.add_event(
            "death_save",
            result.description,
            combatant_id=combatant_id,
            data=result.to_dict()
        )

        # Persist state to database
        await persist_combat_state(combat_id, engine, combat_repo)

        return DeathSaveResponse(
            success=True,
            roll=result.roll,
            total=result.modified_roll,
            dc=result.dc,
            outcome=result.outcome.value,
            successes=result.total_successes,
            failures=result.total_failures,
            description=result.description,
            combat_state=engine.get_combat_state()
        )

    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Death save system not available: {e}"
        )


@router.post("/{combat_id}/stabilize", response_model=DeathSaveResponse)
async def stabilize_combatant(
    combat_id: str,
    request: StabilizeRequest,
    combat_repo: CombatStateRepository = Depends(get_combat_repo),
):
    """
    Attempt to stabilize a dying combatant.

    Methods:
    - medicine: DC 10 Wisdom (Medicine) check
    - spare_the_dying: Automatic (cantrip, no roll needed)
    - healer_kit: Automatic (requires item, no roll needed)

    Args:
        target_id: The dying combatant to stabilize
        method: How stabilization is being attempted
        helper_id: Who is doing the stabilization (for medicine check)
    """
    engine = active_combats.get(combat_id)

    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combat not found"
        )

    target = engine.state.initiative_tracker.get_combatant(request.target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found"
        )

    stats = engine.state.combatant_stats.get(request.target_id, {})

    # Validate target is dying
    current_hp = stats.get("current_hp", target.current_hp)
    if current_hp > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target is not at 0 HP"
        )

    is_dead = stats.get("is_dead", False)
    if is_dead:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot stabilize - target is dead"
        )

    is_stable = stats.get("is_stable", False)
    if is_stable:
        return DeathSaveResponse(
            success=True,
            outcome="stabilized",
            description="Target is already stable",
            combat_state=engine.get_combat_state()
        )

    try:
        from app.core.death_saves import (
            DeathSaveState,
            stabilize_creature,
            attempt_medicine_check
        )

        state = DeathSaveState(
            successes=stats.get("death_save_successes", 0),
            failures=stats.get("death_save_failures", 0),
            is_stable=False,
            is_dead=False,
        )

        medicine_result = None

        if request.method == "medicine":
            # Get helper stats for Medicine check
            if not request.helper_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="helper_id required for Medicine check"
                )

            helper_stats = engine.state.combatant_stats.get(request.helper_id, {})
            abilities = helper_stats.get("abilities", {})
            wis_mod = (abilities.get("wisdom", 10) - 10) // 2
            level = helper_stats.get("level", 1)
            prof_bonus = 2 + ((level - 1) // 4)

            # Check if proficient in Medicine
            # This would typically be in a skills list
            skills = helper_stats.get("skills", {})
            is_proficient = skills.get("medicine", False)

            success, roll, total = attempt_medicine_check(
                wisdom_modifier=wis_mod,
                proficiency_bonus=prof_bonus,
                is_proficient=is_proficient
            )
            medicine_result = (success, roll, total)

        result = stabilize_creature(
            state=state,
            method=request.method,
            medicine_check_result=medicine_result
        )

        if result.success:
            stats["is_stable"] = True
            stats["death_save_successes"] = 0
            stats["death_save_failures"] = 0

        # Log event
        engine.state.add_event(
            "stabilization",
            result.description,
            combatant_id=request.target_id,
            data=result.to_dict()
        )

        # Persist state to database
        await persist_combat_state(combat_id, engine, combat_repo)

        return DeathSaveResponse(
            success=result.success,
            roll=result.roll,
            dc=result.dc,
            outcome="stabilized" if result.success else "continue",
            description=result.description,
            combat_state=engine.get_combat_state()
        )

    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Death save system not available: {e}"
        )


@router.get("/{combat_id}/death-saves/{combatant_id}")
async def get_death_save_status(combat_id: str, combatant_id: str):
    """
    Get the current death save status for a combatant.

    Returns current successes, failures, and status (dying, stable, dead).
    """
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

    stats = engine.state.combatant_stats.get(combatant_id, {})

    current_hp = stats.get("current_hp", combatant.current_hp)
    is_dead = stats.get("is_dead", False)
    is_stable = stats.get("is_stable", False)
    successes = stats.get("death_save_successes", 0)
    failures = stats.get("death_save_failures", 0)

    if current_hp > 0:
        status_str = "conscious"
    elif is_dead:
        status_str = "dead"
    elif is_stable:
        status_str = "stable"
    else:
        status_str = "dying"

    return {
        "combatant_id": combatant_id,
        "combatant_name": combatant.name,
        "current_hp": current_hp,
        "status": status_str,
        "successes": successes,
        "failures": failures,
        "success_markers": "●" * successes + "○" * (3 - successes),
        "failure_markers": "●" * failures + "○" * (3 - failures),
    }
