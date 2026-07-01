"""Batch 69 (F3): the gold economy is one ledger, not two.

Loot paid character.gold (DB) while shops charged combatant_stats['gold'] (combat
state); outside the campaign flow nothing bridged them: quick-combat shop purchases
never reached the character record (gold refunded, items gone next combat), and
looted gold was invisible to a shop visit in the same combat. Now combat end syncs
player combatants back to their matching DB characters (by id), and loot collection
credits the live combat's stats too.
"""
import pytest
import pytest_asyncio
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database.models  # noqa: F401 — register tables
from app.database.models import CharacterCreate, CharacterUpdate
from app.database.repositories import CharacterRepository
from app.core.combat_engine import CombatEngine, CombatState, CombatPhase


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


def _mk(cid, ctype, gold=0):
    return {"id": cid, "name": cid, "type": ctype, "hp": 30, "max_hp": 30, "ac": 15,
            "speed": 30, "gold": gold,
            "abilities": {"strength": 14, "dexterity": 12, "constitution": 14,
                          "intelligence": 10, "wisdom": 10, "charisma": 10},
            "class": "fighter", "level": 3, "conditions": []}


def _engine_with(player_id, gold):
    eng = CombatEngine(combat_state=CombatState())
    eng.start_combat([_mk(player_id, "player", gold=gold)], [_mk("gob", "enemy")],
                     positions={player_id: (0, 0), "gob": (5, 5)})
    eng.state.phase = CombatPhase.COMBAT_ACTIVE
    return eng


async def test_combat_end_syncs_gold_hp_inventory_to_character(db_session):
    from app.api.routes.combat import _sync_players_to_characters

    repo = CharacterRepository(db_session)
    await repo.create(CharacterCreate(id="char-1", name="Hero"))
    char = await repo.update("char-1", CharacterUpdate(gold=500))
    assert char.gold == 500

    eng = _engine_with("char-1", gold=500)
    stats = eng.state.combatant_stats["char-1"]
    stats["gold"] = 430                      # bought a potion mid-combat
    stats["current_hp"] = 17                 # took some hits
    stats["inventory"] = [{"id": "potion_of_healing_1", "name": "Potion of Healing"}]

    await _sync_players_to_characters(eng, repo)

    fetched = await repo.get_by_id("char-1")
    assert fetched.gold == 430
    assert fetched.current_hp == 17
    assert any("potion" in (i.get("id") or "") for i in fetched.inventory)


async def test_sync_skips_combatants_without_a_character_record(db_session):
    from app.api.routes.combat import _sync_players_to_characters

    repo = CharacterRepository(db_session)
    eng = _engine_with("demo-fighter", gold=100)   # demo party: no DB record
    await _sync_players_to_characters(eng, repo)   # must not raise


async def test_loot_collection_credits_the_live_combat_too(db_session):
    from app.api.routes.loot import collect_loot, CollectLootRequest, pending_loot
    from app.core.combat_storage import active_combats

    repo = CharacterRepository(db_session)
    await repo.create(CharacterCreate(id="char-2", name="Looter"))
    await repo.update("char-2", CharacterUpdate(gold=10))

    eng = _engine_with("char-2", gold=10)
    active_combats["combat-loot-1"] = eng
    pending_loot["combat-loot-1"] = {"coins": {"gp": 60}, "magic_items": [],
                                     "gems": [], "art_objects": [], "mundane_items": []}
    try:
        await collect_loot("combat-loot-1",
                           CollectLootRequest(character_id="char-2", take_coins=True),
                           char_repo=repo)
        fetched = await repo.get_by_id("char-2")
        assert fetched.gold == 70                                        # DB credited
        assert eng.state.combatant_stats["char-2"]["gold"] == 70         # live combat too
    finally:
        active_combats.pop("combat-loot-1", None)
        pending_loot.pop("combat-loot-1", None)
