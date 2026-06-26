"""Batch 43 (Durability P5): a builder-created character persists its combat-critical state.

`persist_created_character` only did `repo.create(...)` with the base fields (name/species/
class/subclass/level/abilities) — it dropped HP, spellcasting, gold, and experience. So a
character created in the builder and reloaded after a restart came back at default HP with no
spell slots: the `db_character_to_combatant` adapter reads current_hp/max_hp/spellcasting,
which were never persisted. It now follows the create with an update of those fields, mirroring
the PDF/JSON import path.
"""
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


_BUILDER_RESULT = {
    "id": "c-p5-cleric", "name": "Life Cleric",
    "species_id": "human", "class_id": "cleric", "subclass_id": "life_domain",
    "level": 3, "background_id": "acolyte",
    "ability_scores": {"strength": 14, "dexterity": 10, "constitution": 14,
                       "intelligence": 10, "wisdom": 16, "charisma": 12},
    "hit_points": 24, "max_hit_points": 24, "experience": 900, "gold": 15,
    "spellcasting": {"ability": "wisdom", "spell_save_dc": 13, "spell_attack_bonus": 5,
                     "spell_slots_max": {"1": 4, "2": 2}, "cantrips_known": ["sacred_flame"]},
}


async def test_created_character_persists_hp_spellcasting_gold_xp(db_session):
    from app.services.character_service import persist_created_character
    from app.database.repositories import CharacterRepository

    repo = CharacterRepository(db_session)
    await persist_created_character(_BUILDER_RESULT, repo)

    fetched = await repo.get_by_id("c-p5-cleric")
    assert fetched is not None
    assert fetched.max_hp == 24
    assert fetched.current_hp == 24
    assert fetched.experience == 900
    assert fetched.gold == 15
    assert fetched.spellcasting and fetched.spellcasting.get("spell_save_dc") == 13
    # subclass already round-tripped via create (regression guard)
    assert fetched.subclass == "life_domain"


async def test_downed_character_keeps_zero_hp_not_revived(db_session):
    """current_hp == 0 (a downed character) must persist as 0, not fall back to max_hp."""
    from app.services.character_service import persist_created_character
    from app.database.repositories import CharacterRepository

    repo = CharacterRepository(db_session)
    downed = dict(_BUILDER_RESULT, id="c-p5-downed", hit_points=0, max_hit_points=24)
    await persist_created_character(downed, repo)

    fetched = await repo.get_by_id("c-p5-downed")
    assert fetched.max_hp == 24
    assert fetched.current_hp == 0   # NOT revived to 24


async def test_reloaded_created_character_is_faithful_combatant(db_session):
    from app.services.character_service import persist_created_character, db_character_to_combatant
    from app.database.repositories import CharacterRepository

    repo = CharacterRepository(db_session)
    await persist_created_character(_BUILDER_RESULT, repo)
    fetched = await repo.get_by_id("c-p5-cleric")

    combatant = db_character_to_combatant(fetched)
    assert combatant["hp"] == 24          # not the 10-HP default
    assert combatant["max_hp"] == 24
    assert combatant["wis_mod"] == 3      # (16-10)//2
    assert combatant.get("spellcasting") is not None
