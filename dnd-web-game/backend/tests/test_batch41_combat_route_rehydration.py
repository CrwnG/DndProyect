"""Batch 41 (Durability P3): combat mutation routes rehydrate on a cache miss.

`rehydrate_combat` reconstructed the engine into `active_combats` but left the route-level
`active_grids` and `reactions_managers` caches empty — so after a restart a rehydrated
combat had no grid (GET /state returned grid={}) and the action/move/reaction routes saw a
None reactions manager. And every mutation route read `active_combats` directly and 404'd on
a miss instead of rehydrating. Now `rehydrate_combat` restores all three caches (grid from
the P2 engine snapshot; a fresh ReactionsManager with every combatant registered), and the
shared `_resolve_engine` route helper rehydrates on a miss / 404s only when unrecoverable.
"""
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database.models  # noqa: F401 — register tables


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


def _mk(cid, ctype, **over):
    base = {
        "id": cid, "name": cid, "type": ctype,
        "hp": 30, "max_hp": 30, "ac": 12, "speed": 30,
        "str_mod": 2, "dex_mod": 1, "con_mod": 2,
        "attack_bonus": 4, "damage_dice": "1d8", "damage_type": "slashing",
        "abilities": {"strength": 14, "dexterity": 12, "constitution": 14,
                      "intelligence": 10, "wisdom": 10, "charisma": 10},
        "class": "fighter", "level": 3, "conditions": [],
    }
    base.update(over)
    return base


async def _persist_combat(cid, repo):
    """Start + persist a combat with a grid occupant/terrain set, then evict all caches."""
    from app.core.combat_engine import CombatEngine, CombatState
    from app.core.movement import TerrainType
    from app.core.combat_storage import (
        create_combat_state, persist_combat_state,
        active_combats, active_grids, reactions_managers,
    )
    engine = CombatEngine(combat_state=CombatState())
    engine.state.id = cid
    engine.start_combat([_mk("player-1", "player")],
                        [_mk("enemy-1", "enemy", hp=12, max_hp=12)])
    engine.state.grid.set_terrain(2, 2, TerrainType.DIFFICULT)
    engine.state.grid.set_occupant(1, 1, "player-1")

    await create_combat_state(cid, None, [], repo)
    await persist_combat_state(cid, engine, repo)

    active_combats.pop(cid, None)        # simulate a restart / cache eviction
    active_grids.pop(cid, None)
    reactions_managers.pop(cid, None)


async def test_rehydrate_restores_grid_and_reactions(db_session):
    from app.core.movement import TerrainType
    from app.core.combat_storage import (
        rehydrate_combat, active_combats, active_grids, reactions_managers,
    )
    from app.database.repositories import CombatStateRepository

    repo = CombatStateRepository(db_session)
    cid = "combat-p3-grid"
    await _persist_combat(cid, repo)

    engine = await rehydrate_combat(cid, repo)
    assert engine is not None
    # Grid cache restored, with terrain + occupancy from the snapshot.
    grid = active_grids.get(cid)
    assert grid is not None
    assert grid.get_cell(2, 2).terrain == TerrainType.DIFFICULT
    assert grid.get_cell(1, 1).occupied_by == "player-1"
    # Reactions manager rebuilt with every combatant registered.
    mgr = reactions_managers.get(cid)
    assert mgr is not None
    assert "player-1" in mgr.reaction_states
    assert "enemy-1" in mgr.reaction_states

    active_combats.pop(cid, None)
    active_grids.pop(cid, None)
    reactions_managers.pop(cid, None)


async def test_resolve_engine_rehydrates_on_cache_miss(db_session):
    from app.api.routes.combat import _resolve_engine
    from app.core.combat_storage import (
        active_combats, active_grids, reactions_managers,
    )
    from app.database.repositories import CombatStateRepository

    repo = CombatStateRepository(db_session)
    cid = "combat-p3-resolve"
    await _persist_combat(cid, repo)

    engine = await _resolve_engine(cid, repo)   # must NOT 404 — rehydrates instead
    assert engine is not None
    assert reactions_managers.get(cid) is not None
    assert active_grids.get(cid) is not None

    active_combats.pop(cid, None)
    active_grids.pop(cid, None)
    reactions_managers.pop(cid, None)


async def test_resolve_engine_404_when_unknown(db_session):
    from app.api.routes.combat import _resolve_engine
    from app.database.repositories import CombatStateRepository

    repo = CombatStateRepository(db_session)
    with pytest.raises(HTTPException) as exc:
        await _resolve_engine("does-not-exist", repo)
    assert exc.value.status_code == 404
