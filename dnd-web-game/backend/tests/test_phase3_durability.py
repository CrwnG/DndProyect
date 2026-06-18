"""Phase 3 — durability regression tests (see ROADMAP.md Phase 3).

Combat/campaign/character state is held in memory and lost on restart. The
first gap: create_combat_state ignored the API combat_id and let the DB
generate its own UUID, so persist_combat_state/load_combat_from_db (which key
by combat_id) never matched the row.
"""
import pytest
import pytest_asyncio
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database.models  # noqa: F401 — register all tables


@pytest_asyncio.fixture
async def db_session():
    """A real in-memory async SQLite session sharing one connection (StaticPool)."""
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


def test_load_campaign_resolves_by_internal_id_and_filename():
    """Saved sessions store the internal campaign id (e.g. 'tutorial-campaign'),
    but load_campaign only resolved by filename stem ('tutorial') -> 404 on load.
    It must resolve by both."""
    from app.core.campaign_engine import load_campaign

    by_file = load_campaign("tutorial")          # filename stem
    assert by_file is not None
    # the internal id is what saved games persist; this 404'd before the fix
    by_id = load_campaign(by_file.id)
    assert by_id is not None
    assert by_id.id == by_file.id


async def test_created_character_persisted_to_db(db_session):
    """A finalized builder character must be saved to the DB (under its own id)
    so it survives a restart, not just live in the in-memory dict."""
    from app.services.character_service import persist_created_character
    from app.database.repositories import CharacterRepository

    repo = CharacterRepository(db_session)
    result = {
        "id": "char-xyz-1",
        "name": "Durable Wizard",
        "species_id": "elf", "class_id": "wizard", "subclass_id": "evoker",
        "level": 3, "background_id": "sage",
        "ability_scores": {"strength": 8, "dexterity": 14, "constitution": 13,
                           "intelligence": 16, "wisdom": 12, "charisma": 10},
    }
    created = await persist_created_character(result, repo)
    assert created.id == "char-xyz-1"

    fetched = await repo.get_by_id("char-xyz-1")
    assert fetched is not None
    assert fetched.name == "Durable Wizard"
    assert fetched.character_class == "wizard"
    assert fetched.subclass == "evoker"
    assert fetched.level == 3
    assert fetched.abilities["intelligence"] == 16


async def test_persisted_character_retrieves_as_valid_combatant(db_session):
    """A character loaded back from the DB must convert to a VALID combatant
    (real ability mods), not the 0-mod fallback. The DB stores flat scores and
    no modifiers, so the adapter must derive mods from scores."""
    from app.services.character_service import persist_created_character, db_character_to_combatant
    from app.database.repositories import CharacterRepository

    repo = CharacterRepository(db_session)
    result = {
        "id": "c1", "name": "Restored Wizard", "class_id": "wizard", "level": 1,
        "ability_scores": {"strength": 8, "dexterity": 14, "constitution": 13,
                           "intelligence": 16, "wisdom": 12, "charisma": 10},
    }
    await persist_created_character(result, repo)
    db_char = await repo.get_by_id("c1")
    assert db_char is not None

    combatant = db_character_to_combatant(db_char)
    assert combatant["int_mod"] == 3       # (16-10)//2, not 0
    assert combatant["dex_mod"] == 2
    assert combatant["abilities"]["int_score"] == 16


async def test_combat_state_persisted_under_api_combat_id(db_session):
    """create_combat_state must use the API combat_id as the DB primary key, so
    persist/load round-trip by that id."""
    from app.core.combat_storage import create_combat_state, load_combat_from_db
    from app.database.repositories import CombatStateRepository

    repo = CombatStateRepository(db_session)
    combat_id = "combat-abc-123"

    created = await create_combat_state(combat_id, None, [{"id": "p1"}], repo)
    assert created is not None
    assert created.id == combat_id

    loaded = await load_combat_from_db(combat_id, repo)
    assert loaded is not None
    assert loaded["id"] == combat_id
