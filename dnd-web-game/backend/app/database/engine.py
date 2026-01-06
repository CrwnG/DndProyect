"""
Database engine configuration.

Supports both SQLite (development) and PostgreSQL (production).
Uses async SQLAlchemy for non-blocking database operations.
"""
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from sqlmodel import SQLModel

from app.config import get_settings


# Global engine instance
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_database_url() -> str:
    """
    Get the async database URL from settings.

    Converts standard URLs to async-compatible format:
    - postgresql:// -> postgresql+asyncpg://
    - sqlite:// -> sqlite+aiosqlite://
    """
    settings = get_settings()
    url = settings.DATABASE_URL

    # Convert to async driver
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    return url


def get_engine() -> AsyncEngine:
    """Get or create the async database engine."""
    global _engine

    if _engine is None:
        settings = get_settings()
        database_url = get_database_url()

        # Configure pool based on database type
        if "sqlite" in database_url:
            # SQLite doesn't support connection pooling
            _engine = create_async_engine(
                database_url,
                echo=settings.DEBUG,
                poolclass=NullPool,
                connect_args={"check_same_thread": False},
            )
        else:
            # PostgreSQL with connection pooling
            _engine = create_async_engine(
                database_url,
                echo=settings.DEBUG,
                poolclass=AsyncAdaptedQueuePool,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=1800,  # Recycle connections after 30 minutes
            )

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory."""
    global _session_factory

    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.

    Usage:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    try:
        session_factory = get_session_factory()
    except Exception as e:
        import traceback
        print(f"\n[DATABASE ERROR] Failed to get session factory: {e}", flush=True)
        traceback.print_exc()
        raise

    try:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                print(f"\n[DATABASE ERROR] Session error: {e}", flush=True)
                await session.rollback()
                raise
            finally:
                await session.close()
    except Exception as e:
        import traceback
        print(f"\n[DATABASE ERROR] Failed to create session: {e}", flush=True)
        traceback.print_exc()
        raise


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions.

    Usage:
        async with get_session_context() as session:
            ...
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize the database.

    Creates all tables defined in SQLModel metadata.
    Should be called on application startup.
    """
    engine = get_engine()

    # Import models to register them with SQLModel
    from app.database import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def close_db() -> None:
    """
    Close the database connection.

    Should be called on application shutdown.
    """
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def drop_all_tables() -> None:
    """
    Drop all database tables.

    WARNING: This deletes all data! Only use in testing.
    """
    engine = get_engine()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
