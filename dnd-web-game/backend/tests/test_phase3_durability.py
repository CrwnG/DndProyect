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
