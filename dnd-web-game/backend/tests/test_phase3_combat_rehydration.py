"""Phase 3 — combat rehydration (see ROADMAP.md Phase 3).

Combat lived only in the in-memory active_combats cache, so a restart lost it.
Step 1: verify CombatEngine.to_dict()/from_dict() round-trips the core state.
Step 2: persist the engine snapshot to the DB and reload it on cache-miss.
"""
import json

import pytest
import pytest_asyncio
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


def test_combat_engine_round_trips_core_state_through_json():
    from app.core.combat_engine import CombatEngine, CombatState

    engine = CombatEngine(combat_state=CombatState())
    engine.start_combat([_mk("player-1", "player")],
                        [_mk("enemy-1", "enemy", hp=12, max_hp=12)])
    # Mutate some state so we know the round-trip preserves it (not just defaults).
    engine.state.combatant_stats["enemy-1"]["current_hp"] = 5

    # Simulate the DB round-trip: serialize -> JSON -> deserialize.
    snapshot = json.loads(json.dumps(engine.to_dict()))
    restored = CombatEngine.from_dict(snapshot)

    assert restored.state.phase == engine.state.phase
    assert restored.state.combatant_stats["enemy-1"]["current_hp"] == 5
    # Initiative order survives.
    assert [c.id for c in restored.state.initiative_tracker.combatants] == \
           [c.id for c in engine.state.initiative_tracker.combatants]


async def test_combat_rehydrates_from_db_snapshot(db_session):
    """A combat must reload + reconstruct from the DB on a cache miss (restart)."""
    from app.core.combat_engine import CombatEngine, CombatState
    from app.core.combat_storage import (
        create_combat_state, persist_combat_state, rehydrate_combat, active_combats,
    )
    from app.database.repositories import CombatStateRepository

    repo = CombatStateRepository(db_session)
    cid = "combat-rehy-1"
    engine = CombatEngine(combat_state=CombatState())
    engine.state.id = cid
    engine.start_combat([_mk("player-1", "player")],
                        [_mk("enemy-1", "enemy", hp=12, max_hp=12)])
    engine.state.combatant_stats["enemy-1"]["current_hp"] = 4

    await create_combat_state(cid, None, [], repo)
    await persist_combat_state(cid, engine, repo)

    active_combats.pop(cid, None)  # simulate a restart
    restored = await rehydrate_combat(cid, repo)
    assert restored is not None
    assert restored.state.combatant_stats["enemy-1"]["current_hp"] == 4
    assert restored.get_combat_state() is not None  # engine is usable after reload
    active_combats.pop(cid, None)
