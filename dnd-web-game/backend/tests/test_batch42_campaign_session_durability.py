"""Batch 42 (Durability P4): campaign rest/level-up routes rehydrate + persist.

The session rest/level-up routes read the in-memory `active_sessions` cache directly
(404 on a miss) AND never called `_persist_session_state`, so (1) a rest/level-up after a
restart 404'd, and (2) even with a warm cache the mutation was never written to the DB — a
long rest's restored HP was lost on the next reload. These routes now resolve the engine
via `_get_or_load_session_engine` (rehydrating on a miss) and persist after mutating.
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


async def _seed_wounded_session(db_session):
    """Persist a campaign session whose only party member is at 5/30 HP, then evict
    the in-memory cache. Returns (session_id, repo)."""
    from app.core.campaign_engine import CampaignEngine, load_campaign
    from app.models.game_session import PartyMember
    from app.api.routes.campaign import active_sessions
    from app.database.repositories import GameSessionRepository
    from app.database.models import GameSession

    campaign = load_campaign("tutorial")
    assert campaign is not None
    member = PartyMember(id="p1", name="Hero", max_hp=30, current_hp=5)
    engine = CampaignEngine.create_new(campaign, [member])
    sid = engine.session.id

    repo = GameSessionRepository(db_session)
    row = GameSession(id=sid, campaign_id=campaign.id, state=engine.session.to_dict(),
                      party=[m.to_dict() for m in engine.session.party])
    db_session.add(row)
    await db_session.flush()

    active_sessions.pop(sid, None)  # simulate restart / eviction
    return sid, repo


async def test_long_rest_rehydrates_on_cache_miss_and_persists(db_session):
    from app.api.routes.campaign import take_long_rest, _get_or_load_session_engine, active_sessions

    sid, repo = await _seed_wounded_session(db_session)

    # Must NOT 404 — rehydrates from the DB — and the long rest restores HP.
    result = await take_long_rest(sid, session_repo=repo)
    assert result["success"] is True

    # The restored HP must be PERSISTED: drop the cache again and reload from the DB.
    active_sessions.pop(sid, None)
    reloaded = await _get_or_load_session_engine(sid, repo)
    assert reloaded is not None
    member = reloaded.session.party[0]
    assert member.current_hp == member.max_hp == 30   # was 5/30 before the rest
    active_sessions.pop(sid, None)


async def test_rest_route_404s_on_truly_unknown_session(db_session):
    from fastapi import HTTPException
    from app.api.routes.campaign import take_long_rest
    from app.database.repositories import GameSessionRepository

    repo = GameSessionRepository(db_session)
    with pytest.raises(HTTPException) as exc:
        await take_long_rest("no-such-session", session_repo=repo)
    assert exc.value.status_code == 404
