"""
Shared storage for active combat sessions.

This module provides centralized storage dictionaries for combat state,
preventing circular imports between campaign_engine.py and combat.py routes.

Also provides persistence functions to save/load combat state from database.
"""
from typing import Dict, Any, Optional, List


# In-memory storage for active combat sessions
# Keys are combat_id (str), values are the corresponding objects
active_combats: Dict[str, Any] = {}  # combat_id -> CombatEngine
active_grids: Dict[str, Any] = {}     # combat_id -> CombatGrid
reactions_managers: Dict[str, Any] = {}  # combat_id -> ReactionsManager


async def persist_combat_state(
    combat_id: str,
    engine: Any,
    repo: Any,
) -> bool:
    """
    Persist current combat state to database.

    Args:
        combat_id: The combat session ID
        engine: The CombatEngine instance
        repo: CombatStateRepository instance

    Returns:
        True if persistence succeeded, False otherwise
    """
    try:
        state = engine.get_combat_state()

        await repo.update_full_state(
            combat_id,
            phase=state.get("phase", "combat_active"),
            round_number=state.get("round", 1),
            current_turn_index=state.get("current_turn_index", 0),
            combatant_stats=state.get("combatant_stats", {}),
            current_turn=state.get("current_turn"),
            positions=state.get("positions", {}),
            initiative_order=state.get("initiative_order", []),
            active_effects=state.get("active_effects", []),
        )
        return True
    except Exception as e:
        print(f"[CombatStorage] Failed to persist combat state: {e}")
        return False


async def create_combat_state(
    combat_id: str,
    session_id: Optional[str],
    combatants: List[Dict[str, Any]],
    repo: Any,
) -> Optional[Any]:
    """
    Create a new combat state record in database.

    Args:
        combat_id: The combat session ID (will be used as database ID)
        session_id: Optional game session ID
        combatants: List of combatant data
        repo: CombatStateRepository instance

    Returns:
        Created CombatState record or None on failure
    """
    try:
        from app.database.models import CombatStateCreate

        data = CombatStateCreate(
            session_id=session_id,
            combatants=combatants,
        )

        # Create with specific ID
        combat_state = await repo.create(data)
        return combat_state
    except Exception as e:
        print(f"[CombatStorage] Failed to create combat state: {e}")
        return None


async def end_combat_state(
    combat_id: str,
    result: str,
    xp_awarded: int,
    repo: Any,
) -> bool:
    """
    End a combat state in database.

    Args:
        combat_id: The combat session ID
        result: Combat result (victory, defeat, fled)
        xp_awarded: XP awarded from combat
        repo: CombatStateRepository instance

    Returns:
        True if update succeeded, False otherwise
    """
    try:
        await repo.end_combat(combat_id, result=result, xp_awarded=xp_awarded)
        return True
    except Exception as e:
        print(f"[CombatStorage] Failed to end combat state: {e}")
        return False


async def load_combat_from_db(
    combat_id: str,
    repo: Any,
) -> Optional[Dict[str, Any]]:
    """
    Load combat state from database.

    Args:
        combat_id: The combat session ID
        repo: CombatStateRepository instance

    Returns:
        Combat state dict or None if not found
    """
    try:
        combat_state = await repo.get_by_id(combat_id)
        if not combat_state:
            return None

        return {
            "id": combat_state.id,
            "session_id": combat_state.session_id,
            "phase": combat_state.phase,
            "round_number": combat_state.round_number,
            "current_turn_index": combat_state.current_turn_index,
            "combatants": combat_state.combatants,
            "initiative_order": combat_state.initiative_order,
            "positions": combat_state.positions,
            "combatant_stats": combat_state.combatant_stats,
            "current_turn": combat_state.current_turn,
            "active_effects": combat_state.active_effects,
            "is_active": combat_state.is_active,
            "result": combat_state.result,
            "xp_awarded": combat_state.xp_awarded,
        }
    except Exception as e:
        print(f"[CombatStorage] Failed to load combat state: {e}")
        return None
