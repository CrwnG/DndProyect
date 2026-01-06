"""
D&D 5e 2024 Spell System - API Routes.

Provides endpoints for spell database queries, character spell management,
and combat spell casting.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query

from app.models.spells import (
    Spell, CastSpellRequest, SpellCastResult, PrepareSpellsRequest,
    SpellListResponse, CharacterSpellsResponse, SpellTargetInfo
)
from app.core.spell_system import (
    SpellRegistry, SpellCaster, cast_spell
)
from app.core.class_spellcasting import (
    get_spellcasting_summary, is_spellcasting_class
)
from app.core.combat_storage import active_combats

router = APIRouter()


# ==================== Spell Database Endpoints ====================

@router.get("/", response_model=SpellListResponse)
async def list_spells(
    level: Optional[int] = Query(None, ge=0, le=9, description="Filter by spell level (0 for cantrips)"),
    school: Optional[str] = Query(None, description="Filter by spell school"),
    class_name: Optional[str] = Query(None, description="Filter by class"),
    ritual: Optional[bool] = Query(None, description="Filter ritual spells"),
    concentration: Optional[bool] = Query(None, description="Filter concentration spells"),
    search: Optional[str] = Query(None, description="Search in spell name/description"),
    limit: int = Query(50, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> SpellListResponse:
    """
    List all spells with optional filtering.

    Supports filtering by level, school, class, ritual/concentration status,
    and text search. Returns paginated results.
    """
    registry = SpellRegistry.get_instance()

    spells = registry.search_spells(
        query=search,
        level=level,
        school=school,
        class_name=class_name,
        ritual=ritual,
        concentration=concentration,
    )

    total = len(spells)
    filtered_spells = spells[offset:offset + limit]

    return SpellListResponse(
        spells=filtered_spells,
        total=total,
        filtered=len(filtered_spells)
    )


@router.get("/level/{level}", response_model=SpellListResponse)
async def get_spells_by_level(
    level: int,
) -> SpellListResponse:
    """Get all spells of a specific level (0 = cantrips)."""
    if level < 0 or level > 9:
        raise HTTPException(status_code=400, detail="Spell level must be 0-9")

    registry = SpellRegistry.get_instance()
    spells = registry.get_spells_by_level(level)

    return SpellListResponse(
        spells=spells,
        total=len(spells),
        filtered=len(spells)
    )


@router.get("/class/{class_name}", response_model=SpellListResponse)
async def get_class_spells(
    class_name: str,
    max_level: Optional[int] = Query(9, ge=0, le=9, description="Maximum spell level"),
) -> SpellListResponse:
    """Get all spells available to a class."""
    registry = SpellRegistry.get_instance()
    spells = registry.get_spells_for_class(class_name, max_level)

    if not spells:
        raise HTTPException(
            status_code=404,
            detail=f"No spells found for class '{class_name}' or class doesn't exist"
        )

    return SpellListResponse(
        spells=spells,
        total=len(spells),
        filtered=len(spells)
    )


@router.get("/{spell_id}")
async def get_spell(spell_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific spell."""
    registry = SpellRegistry.get_instance()
    spell = registry.get_spell(spell_id)

    if not spell:
        raise HTTPException(status_code=404, detail=f"Spell '{spell_id}' not found")

    return {"spell": spell.model_dump()}


# ==================== Character Spell Management ====================

@router.get("/character/{character_id}/spells")
async def get_character_spells(
    character_id: str,
    combat_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get character's spellcasting information.

    Returns spell slots, cantrips, prepared/known spells, and concentration status.
    """
    # Try to get character from active combat
    character_data = None

    if combat_id and combat_id in active_combats:
        combat_engine = active_combats[combat_id]
        character_data = combat_engine.state.combatant_stats.get(character_id)

    if not character_data:
        # Try looking in all active combats
        for cid, combat in active_combats.items():
            if character_id in combat.state.combatant_stats:
                character_data = combat.state.combatant_stats[character_id]
                break

    if not character_data:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")

    class_name = character_data.get("class", "")
    level = character_data.get("level", 1)

    if not is_spellcasting_class(class_name):
        return {
            "has_spellcasting": False,
            "message": f"{class_name} is not a spellcasting class"
        }

    # Get spellcasting ability modifier
    spellcasting_data = character_data.get("spellcasting", {})
    ability = spellcasting_data.get("ability", "intelligence")
    ability_score = character_data.get("stats", {}).get(ability, 10)
    ability_mod = (ability_score - 10) // 2

    # Create SpellCaster to get full spell info
    spell_caster = SpellCaster(character_data, spellcasting_data)
    registry = SpellRegistry.get_instance()

    # Helper to extract spell ID from string or object
    def get_spell_id(item):
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            # Try 'id', 'name', or 'spell_id' fields
            return item.get("id") or item.get("name") or item.get("spell_id")
        return None

    # Get actual spell objects
    cantrips = []
    for cantrip_item in spell_caster.spellcasting.cantrips_known:
        cantrip_id = get_spell_id(cantrip_item)
        if cantrip_id:
            spell = registry.get_spell(cantrip_id)
            if spell:
                cantrips.append(spell.model_dump())

    prepared = []
    for spell_item in spell_caster.spellcasting.prepared_spells:
        spell_id = get_spell_id(spell_item)
        if spell_id:
            spell = registry.get_spell(spell_id)
            if spell:
                prepared.append(spell.model_dump())

    available = []
    for spell in spell_caster.get_available_spells():
        available.append(spell.model_dump())

    # Get spellcasting summary
    summary = get_spellcasting_summary(class_name, level, ability_mod)

    return {
        "has_spellcasting": True,
        "ability": summary.get("ability"),
        "spell_save_dc": spell_caster.spellcasting.spell_save_dc,
        "spell_attack_bonus": spell_caster.spellcasting.spell_attack_bonus,
        "spell_slots": spell_caster.spellcasting.spell_slots_max,
        "spell_slots_used": spell_caster.spellcasting.spell_slots_used,
        "max_prepared": spell_caster.spellcasting.max_prepared,
        "cantrips": cantrips,
        "prepared_spells": prepared,
        "available_spells": available,
        "concentrating_on": spell_caster.spellcasting.concentrating_on,
        "type": summary.get("type"),
    }


@router.get("/character/{character_id}/available")
async def get_available_spells(
    character_id: str,
    combat_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get spells the character can currently cast.

    Filters by: prepared/known, has available slots, not blocked by concentration.
    """
    # Get character data
    character_data = None

    if combat_id and combat_id in active_combats:
        combat_engine = active_combats[combat_id]
        character_data = combat_engine.state.combatant_stats.get(character_id)

    if not character_data:
        for cid, combat in active_combats.items():
            if character_id in combat.state.combatant_stats:
                character_data = combat.state.combatant_stats[character_id]
                break

    if not character_data:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")

    spellcasting_data = character_data.get("spellcasting", {})
    spell_caster = SpellCaster(character_data, spellcasting_data)

    available = spell_caster.get_available_spells()

    # Separate cantrips from leveled spells
    cantrips = [s.model_dump() for s in available if s.level == 0]
    leveled = [s.model_dump() for s in available if s.level > 0]

    return {
        "cantrips": cantrips,
        "leveled_spells": leveled,
        "spell_slots": spell_caster.spellcasting.spell_slots_max,
        "spell_slots_used": spell_caster.spellcasting.spell_slots_used,
        "concentrating_on": spell_caster.spellcasting.concentrating_on,
    }


@router.post("/character/{character_id}/prepare")
async def prepare_spells(
    character_id: str,
    request: PrepareSpellsRequest,
    combat_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Set the character's prepared spells.

    Only for prepared casters (Wizard, Cleric, Druid, Paladin).
    Can only be done outside of combat (or before combat starts).
    """
    # Get character data
    character_data = None
    combat_engine = None

    if combat_id and combat_id in active_combats:
        combat_engine = active_combats[combat_id]
        character_data = combat_engine.state.combatant_stats.get(character_id)

    if not character_data:
        for cid, combat in active_combats.items():
            if character_id in combat.state.combatant_stats:
                character_data = combat.state.combatant_stats[character_id]
                combat_engine = combat
                break

    if not character_data:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")

    spellcasting_data = character_data.get("spellcasting", {})
    spell_caster = SpellCaster(character_data, spellcasting_data)

    success, message = spell_caster.prepare_spells(request.spell_ids)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Update character data in combat state
    if combat_engine:
        combat_engine.state.combatant_stats[character_id]["spellcasting"] = spell_caster.to_dict()

    return {
        "success": True,
        "message": message,
        "prepared_spells": request.spell_ids
    }


# ==================== Combat Spellcasting ====================

@router.post("/combat/{combat_id}/cast")
async def cast_spell_in_combat(
    combat_id: str,
    request: CastSpellRequest,
) -> Dict[str, Any]:
    """
    Cast a spell in combat.

    Validates spell preparation, slot availability, and resolves the spell effect.
    Returns full result including damage/healing, saves, and combat state updates.
    """
    if combat_id not in active_combats:
        raise HTTPException(status_code=404, detail=f"Combat '{combat_id}' not found")

    combat_engine = active_combats[combat_id]

    # Get caster data
    caster_data = combat_engine.state.combatant_stats.get(request.caster_id)
    if not caster_data:
        raise HTTPException(status_code=404, detail=f"Caster '{request.caster_id}' not found")

    # Verify it's the caster's turn
    current_combatant = combat_engine.get_current_combatant()
    if current_combatant and current_combatant.id != request.caster_id:
        raise HTTPException(status_code=400, detail="It's not your turn to act")

    # Get target data
    targets = []
    for target_id in request.target_ids:
        target_data = combat_engine.state.combatant_stats.get(target_id)
        if target_data:
            # Include position for range calculations
            pos = combat_engine.state.positions.get(target_id, {})
            target_data_with_pos = target_data.copy()
            target_data_with_pos["id"] = target_id
            target_data_with_pos["position"] = pos
            targets.append(target_data_with_pos)

    # Cast the spell
    result = cast_spell(
        caster_data=caster_data,
        spell_id=request.spell_id,
        slot_level=request.slot_level,
        targets=targets,
        combat_state={
            "round_number": combat_engine.state.initiative_tracker.current_round
        }
    )

    concentration_results = {}

    if result.success:
        # Apply damage to targets
        if result.damage_dealt:
            for target_id, damage in result.damage_dealt.items():
                if target_id in combat_engine.state.combatant_stats:
                    hp = combat_engine.state.combatant_stats[target_id].get("current_hp", 0)
                    new_hp = max(0, hp - damage)
                    combat_engine.state.combatant_stats[target_id]["current_hp"] = new_hp

                    # CRITICAL: Also update the Combatant object so get_combat_state() returns correct values
                    # Without this, end-turn would return old HP and enemy would "come back to life"
                    for combatant in combat_engine.state.initiative_tracker.combatants:
                        if combatant.id == target_id:
                            combatant.current_hp = new_hp
                            if new_hp <= 0:
                                combatant.is_active = False
                            break

                    # Check concentration for targets who take spell damage
                    if damage > 0:
                        conc_result = combat_engine._check_concentration_on_damage(
                            target_id=target_id,
                            damage_dealt=damage,
                            damage_source=f"{result.spell_name} spell"
                        )
                        if conc_result:
                            concentration_results[target_id] = conc_result

        # Apply healing to targets
        if result.healing_done:
            for target_id, healing in result.healing_done.items():
                if target_id in combat_engine.state.combatant_stats:
                    hp = combat_engine.state.combatant_stats[target_id].get("current_hp", 0)
                    max_hp = combat_engine.state.combatant_stats[target_id].get("max_hp", hp)
                    new_hp = min(max_hp, hp + healing)
                    combat_engine.state.combatant_stats[target_id]["current_hp"] = new_hp

                    # Also update the Combatant object for healing
                    for combatant in combat_engine.state.initiative_tracker.combatants:
                        if combatant.id == target_id:
                            combatant.current_hp = new_hp
                            break

        # Update caster's spell slots
        spell_caster = SpellCaster(caster_data)
        if result.slot_used:
            spell_caster.spellcasting.use_slot(result.slot_used)
            combat_engine.state.combatant_stats[request.caster_id]["spellcasting"] = spell_caster.to_dict()

        # Handle concentration
        if result.concentration_started:
            combat_engine.state.combatant_stats[request.caster_id]["spellcasting"]["concentrating_on"] = result.spell_id

        # Add combat event
        combat_engine.state.add_event(
            "spell_cast",
            result.description,
            combatant_id=request.caster_id,
            data={
                "spell_id": result.spell_id,
                "spell_name": result.spell_name,
                "damage": result.damage_dealt,
                "healing": result.healing_done,
                "hit": result.hit,
                "critical": result.critical,
            }
        )

        # Use action (if casting time is Action)
        registry = SpellRegistry.get_instance()
        spell = registry.get_spell(request.spell_id)
        if spell:
            casting_time = spell.casting_time.lower()
            if "action" in casting_time and "bonus" not in casting_time:
                combat_engine.state.current_turn.action_taken = True
            elif "bonus" in casting_time:
                combat_engine.state.current_turn.bonus_action_taken = True

    # Build combat_state for frontend to update HP
    # ALWAYS include targeted combatants so frontend can update HP display
    # Frontend expects combatants as an ARRAY with id and current_hp fields
    combatants_list = []
    included_ids = set()

    # Include ALL targets from the request (whether they took damage or not)
    # This ensures the frontend always gets updated HP values
    for target_id in request.target_ids:
        if target_id in combat_engine.state.combatant_stats:
            stats = combat_engine.state.combatant_stats[target_id]
            combatants_list.append({
                "id": target_id,
                "current_hp": stats.get("current_hp", 0),
                "is_active": stats.get("current_hp", 0) > 0
            })
            included_ids.add(target_id)

    # Also include any healed targets not already in the list
    if result.healing_done:
        for target_id in result.healing_done.keys():
            if target_id not in included_ids and target_id in combat_engine.state.combatant_stats:
                stats = combat_engine.state.combatant_stats[target_id]
                combatants_list.append({
                    "id": target_id,
                    "current_hp": stats.get("current_hp", 0),
                    "is_active": stats.get("current_hp", 0) > 0
                })
                included_ids.add(target_id)

    # Debug logging to trace the issue
    print(f"[SPELL DEBUG] result.damage_dealt = {result.damage_dealt}")
    print(f"[SPELL DEBUG] result.save_results = {result.save_results}")
    print(f"[SPELL DEBUG] combat_state.combatants = {combatants_list}")
    for target_id in request.target_ids:
        stats = combat_engine.state.combatant_stats.get(target_id, {})
        print(f"[SPELL DEBUG] Target {target_id}: current_hp={stats.get('current_hp', 'MISSING')}, is_active={stats.get('current_hp', 0) > 0}")

    combat_state = {
        "combatants": combatants_list
    }

    # Convert result to dict and add combat_state
    response = result.model_dump()
    response["combat_state"] = combat_state

    # Include concentration check results for any targets who had to make checks
    if concentration_results:
        response["concentration_checks"] = concentration_results

    return response


@router.get("/combat/{combat_id}/valid-targets/{spell_id}")
async def get_spell_targets(
    combat_id: str,
    spell_id: str,
    caster_id: str,
) -> Dict[str, Any]:
    """
    Get valid targets for a spell.

    Filters based on spell range, target type, and line of sight.
    """
    if combat_id not in active_combats:
        raise HTTPException(status_code=404, detail=f"Combat '{combat_id}' not found")

    combat_engine = active_combats[combat_id]
    registry = SpellRegistry.get_instance()

    spell = registry.get_spell(spell_id)
    if not spell:
        raise HTTPException(status_code=404, detail=f"Spell '{spell_id}' not found")

    caster_pos = combat_engine.state.positions.get(caster_id, {})
    if not caster_pos:
        raise HTTPException(status_code=404, detail=f"Caster '{caster_id}' not found in combat")

    caster_x = caster_pos.get("x", 0)
    caster_y = caster_pos.get("y", 0)

    # Parse spell range
    range_str = spell.range.lower()
    if "self" in range_str:
        max_range = 0
    elif "touch" in range_str:
        max_range = 5
    else:
        # Extract feet value
        import re
        match = re.search(r'(\d+)', range_str)
        max_range = int(match.group(1)) if match else 30

    # Get caster combatant to check friends/foes
    caster_combatant = combat_engine.state.initiative_tracker.get_combatant(caster_id)

    targets: List[SpellTargetInfo] = []

    for combatant_id, pos in combat_engine.state.positions.items():
        if combatant_id == caster_id:
            # Self is always a valid target for self spells
            if spell.target_type and "self" in spell.target_type.value:
                targets.append(SpellTargetInfo(
                    id=combatant_id,
                    name="Self",
                    distance=0,
                    is_ally=True,
                    is_self=True
                ))
            continue

        combatant = combat_engine.state.initiative_tracker.get_combatant(combatant_id)
        if not combatant or not combatant.is_active:
            continue

        # Calculate distance (5 ft per cell)
        target_x = pos.get("x", 0)
        target_y = pos.get("y", 0)
        dx = abs(target_x - caster_x)
        dy = abs(target_y - caster_y)
        distance_cells = max(dx, dy)
        distance_feet = distance_cells * 5

        if distance_feet <= max_range:
            # Determine if ally or enemy
            is_ally = (
                caster_combatant and combatant and
                caster_combatant.combatant_type == combatant.combatant_type
            )

            combatant_stats = combat_engine.state.combatant_stats.get(combatant_id, {})

            targets.append(SpellTargetInfo(
                id=combatant_id,
                name=combatant_stats.get("name", combatant.name),
                distance=distance_feet,
                is_ally=is_ally,
                is_self=False
            ))

    return {
        "spell": spell.model_dump(),
        "targets": [t.model_dump() for t in targets],
        "range_feet": max_range,
        "target_type": spell.target_type.value if spell.target_type else "single"
    }


@router.post("/combat/{combat_id}/concentration-check")
async def concentration_check(
    combat_id: str,
    caster_id: str,
    damage_taken: int,
) -> Dict[str, Any]:
    """
    Make a concentration check after taking damage.

    DC = max(10, damage/2). Returns whether concentration was maintained.
    """
    if combat_id not in active_combats:
        raise HTTPException(status_code=404, detail=f"Combat '{combat_id}' not found")

    combat_engine = active_combats[combat_id]

    caster_data = combat_engine.state.combatant_stats.get(caster_id)
    if not caster_data:
        raise HTTPException(status_code=404, detail=f"Caster '{caster_id}' not found")

    spellcasting_data = caster_data.get("spellcasting", {})
    if not spellcasting_data.get("concentrating_on"):
        return {
            "was_concentrating": False,
            "message": "Not concentrating on any spell"
        }

    spell_caster = SpellCaster(caster_data, spellcasting_data)

    # Get CON modifier and save proficiency
    con_score = caster_data.get("stats", {}).get("constitution", 10)
    con_mod = (con_score - 10) // 2
    level = caster_data.get("level", 1)
    prof_bonus = 2 + ((level - 1) // 4)
    is_proficient = "constitution" in caster_data.get("saving_throw_proficiencies", [])

    maintained, roll, dc = spell_caster.check_concentration(
        damage_taken, con_mod, prof_bonus, is_proficient
    )

    spell_name = spellcasting_data.get("concentrating_on", "unknown spell")

    if not maintained:
        # End concentration
        spell_caster.end_concentration()
        combat_engine.state.combatant_stats[caster_id]["spellcasting"] = spell_caster.to_dict()

        combat_engine.state.add_event(
            "concentration_broken",
            f"{caster_data.get('name', 'Caster')} loses concentration on {spell_name}!",
            combatant_id=caster_id,
            data={"spell": spell_name, "roll": roll, "dc": dc}
        )

    return {
        "was_concentrating": True,
        "spell": spell_name,
        "maintained": maintained,
        "roll": roll,
        "dc": dc,
        "total": roll + con_mod + (prof_bonus if is_proficient else 0),
        "message": f"Concentration {'maintained' if maintained else 'broken'}! (Rolled {roll} vs DC {dc})"
    }
