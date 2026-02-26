"""
FastAPI application entrypoint.

Lifespan:
  • On startup: verify DB connectivity (log warning, don't crash).
  • On shutdown: dispose the engine cleanly.

Routers:
  • /ingest — telemetry ingestion (Phase 1)
  • /health — shallow liveness probe
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.routers.ingest import router as ingest_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle."""

    # Startup — verify DB is reachable
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified ✓")
    except Exception:
        logger.warning(
            "Could not reach the database on startup. "
            "The app will start, but requests will fail until the DB is available."
        )

    yield  # ← application runs here

    # Shutdown — clean up connection pool
    await engine.dispose()
    logger.info("Database engine disposed ✓")


# ── App ─────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description=(
        "AI Cost Management & Optimization Platform — "
        "Phase 1: Telemetry Ingestion & Cost Attribution."
    ),
    lifespan=lifespan,
)

# Mount routers
app.include_router(ingest_router, prefix="/ingest")


# ── Health check ────────────────────────────────────────────
@app.get(
    "/health",
    tags=["System"],
    summary="Liveness probe",
)
async def health_check() -> dict[str, str]:
    """Shallow health check — confirms the process is alive."""
    return {"status": "healthy"}
