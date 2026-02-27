"""
Alembic migration environment — async variant.

Key design:
  • DB URL comes from app.core.config (single source of truth),
    NOT from alembic.ini, so secrets aren't duplicated.
  • target_metadata points to Base.metadata so `alembic revision
    --autogenerate` can diff the ORM models against the live schema.
  • Uses asyncpg via run_async_migrations().
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.core.database import Base

# Import all models so Base.metadata is fully populated
import app.models.usage  # noqa: F401
import app.models.rollups  # noqa: F401
import app.models.project  # noqa: F401
import app.models.api_key  # noqa: F401

# ── Alembic Config object ──────────────────────────────────
config = context.config

# Set the sqlalchemy URL programmatically (overrides alembic.ini)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData for autogenerate support
target_metadata = Base.metadata


# ── Offline mode (generates SQL script, no DB connection) ──
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online (async) mode ────────────────────────────────────
def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    """Configure context with a live connection and run."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (async)."""
    asyncio.run(run_async_migrations())


# ── Entrypoint ──────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
