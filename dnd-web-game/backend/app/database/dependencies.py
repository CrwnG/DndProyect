"""
FastAPI dependencies for database access.

Provides dependency injection for database repositories,
enabling clean separation of concerns and easy testing.
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.engine import get_session
from app.database.repositories import (
    CharacterRepository,
    GameSessionRepository,
    CombatStateRepository,
    CombatLogRepository,
    CampaignProgressRepository,
    SaveGameRepository,
)


async def get_character_repo(
    session: AsyncSession = Depends(get_session)
) -> CharacterRepository:
    """Dependency for CharacterRepository."""
    print(f"[DEPS] get_character_repo called, session={session}", flush=True)
    return CharacterRepository(session)


async def get_session_repo(
    session: AsyncSession = Depends(get_session)
) -> GameSessionRepository:
    """Dependency for GameSessionRepository."""
    print(f"[DEPS] get_session_repo called, session={session}", flush=True)
    return GameSessionRepository(session)


async def get_combat_repo(
    session: AsyncSession = Depends(get_session)
) -> CombatStateRepository:
    """Dependency for CombatStateRepository."""
    return CombatStateRepository(session)


async def get_combat_log_repo(
    session: AsyncSession = Depends(get_session)
) -> CombatLogRepository:
    """Dependency for CombatLogRepository."""
    return CombatLogRepository(session)


async def get_progress_repo(
    session: AsyncSession = Depends(get_session)
) -> CampaignProgressRepository:
    """Dependency for CampaignProgressRepository."""
    print(f"[DEPS] get_progress_repo called, session={session}", flush=True)
    return CampaignProgressRepository(session)


async def get_db_session(
    session: AsyncSession = Depends(get_session)
) -> AsyncSession:
    """Dependency for raw database session (when repository pattern not needed)."""
    return session


async def get_savegame_repo(
    session: AsyncSession = Depends(get_session)
) -> SaveGameRepository:
    """Dependency for SaveGameRepository."""
    return SaveGameRepository(session)
