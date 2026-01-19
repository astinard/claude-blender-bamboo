"""Database module for Claude Fab Lab.

Production-grade database layer using SQLAlchemy with PostgreSQL support.
Falls back to SQLite for development and testing.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.utils import get_logger
from src.db.models import Base

logger = get_logger("db")

# Database URL from environment or default to SQLite
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./data/claude_fab_lab.db"
)

# For sync operations (migrations, etc.)
SYNC_DATABASE_URL = DATABASE_URL.replace("+aiosqlite", "").replace("+asyncpg", "")

# Global engine and session factory
_engine: Optional[create_async_engine] = None
_session_factory: Optional[async_sessionmaker] = None


def get_engine():
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        if "sqlite" in DATABASE_URL:
            # SQLite needs special handling for async
            _engine = create_async_engine(
                DATABASE_URL,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=os.getenv("DB_ECHO", "false").lower() == "true"
            )
        else:
            # PostgreSQL
            _engine = create_async_engine(
                DATABASE_URL,
                pool_size=20,
                max_overflow=10,
                pool_pre_ping=True,
                echo=os.getenv("DB_ECHO", "false").lower() == "true"
            )
    return _engine


def get_session_factory() -> async_sessionmaker:
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session with automatic cleanup."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db():
    """Initialize the database, creating all tables."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully")


async def close_db():
    """Close the database connection."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
    logger.info("Database connection closed")


def get_sync_engine():
    """Get synchronous engine for migrations."""
    return create_engine(SYNC_DATABASE_URL, echo=False)


# Dependency for FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with get_session() as session:
        yield session
