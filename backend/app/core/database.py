"""
Async database engine, session factory, and ORM base.

Rules enforced:
  • Every DB call goes through AsyncSession (no sync, no raw SQL).
  • Sessions are request-scoped via FastAPI's Depends(get_db_session).
  • The declarative Base is shared across all models so Alembic can
    auto-detect schema changes from a single metadata object.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ── Engine ──────────────────────────────────────────────────
# pool_pre_ping: drop stale connections before reuse
# echo: SQL logging — only in debug mode
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

# ── Session factory ─────────────────────────────────────────
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # avoid lazy-load issues after commit
)


# ── ORM Base ────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy models."""


# ── Dependency ──────────────────────────────────────────────
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a scoped async session for one request.

    The session is committed by the caller (router/service);
    this generator only guarantees cleanup on exit.
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
