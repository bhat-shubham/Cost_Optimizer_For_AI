"""
FastAPI application entrypoint.

Lifespan:
  • On startup: verify DB connectivity, run daily rollups.
  • On shutdown: dispose the engine cleanly.

Routers:
  • /ingest — telemetry ingestion (Phase 1)
  • /analytics — cost insights from rollups (Phase 2A/2B)
  • /health — shallow liveness probe
"""

import datetime
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import settings
from app.core.database import async_session_factory, engine
from app.routers.analytics import router as analytics_router
from app.routers.ingest import router as ingest_router
from app.services.rollups import run_daily_rollups

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
    db_available = False
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified ✓")
        db_available = True
    except Exception:
        logger.warning(
            "Could not reach the database on startup. "
            "The app will start, but requests will fail until the DB is available."
        )

    # Startup — run rollups for today (temporary, until background scheduler)
    if db_available:
        try:
            today = datetime.date.today()
            async with async_session_factory() as session:
                await run_daily_rollups(session, today)
            logger.info("Startup rollups for %s completed ✓", today)
        except Exception:
            logger.exception("Startup rollups failed (non-fatal)")

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
        "Phase 1: Ingestion | Phase 2A/2B: Analytics + Rollups."
    ),
    lifespan=lifespan,
)

# Mount routers
app.include_router(ingest_router, prefix="/ingest")
app.include_router(analytics_router, prefix="/analytics")


# ── Health check ────────────────────────────────────────────
@app.get(
    "/health",
    tags=["System"],
    summary="Liveness probe",
)
async def health_check() -> dict[str, str]:
    """Shallow health check — confirms the process is alive."""
    return {"status": "healthy"}
