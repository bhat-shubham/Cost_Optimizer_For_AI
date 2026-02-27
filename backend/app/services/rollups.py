"""
Idempotent rollup aggregation service.

Aggregates usage_events into pre-computed rollup tables for fast analytics.
usage_events is the source of truth — rollups are derived and reproducible.

IDEMPOTENCY:
  Uses INSERT … ON CONFLICT (pk) DO UPDATE for each rollup table.
  Running this twice for the same date produces identical results.
  ON CONFLICT is atomic per row — no gap between DELETE and INSERT
  where concurrent readers might see zero data.

PHASE 2B:
  Called at app startup for today's date. No background scheduler yet.
"""

import datetime
import logging

from sqlalchemy import cast, Date, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import UsageEvent
from app.models.rollups import (
    DailyCostRollup,
    EndpointCostRollup,
    ModelCostRollup,
)

logger = logging.getLogger(__name__)


async def run_daily_rollups(
    session: AsyncSession,
    target_date: datetime.date,
) -> None:
    """
    Aggregate usage_events for target_date into all 3 rollup tables.

    This function is idempotent — safe to call multiple times for the
    same date. Each rollup uses INSERT … ON CONFLICT DO UPDATE, so
    re-running overwrites with the latest aggregation.

    All 3 rollups are committed in a single transaction.

    Args:
        session:     Async DB session (caller manages lifecycle).
        target_date: The calendar day to aggregate.
    """
    logger.info("Running rollups for %s", target_date)

    date_filter = cast(UsageEvent.timestamp, Date) == target_date

    await _rollup_daily_cost(session, target_date, date_filter)
    await _rollup_model_cost(session, target_date, date_filter)
    await _rollup_endpoint_cost(session, target_date, date_filter)

    await session.commit()
    logger.info("Rollups for %s committed ✓", target_date)


# ── Daily cost rollup ───────────────────────────────────────
async def _rollup_daily_cost(
    session: AsyncSession,
    target_date: datetime.date,
    date_filter,  # type: ignore[no-untyped-def]
) -> None:
    """Aggregate into daily_cost_rollups."""
    stmt = select(
        cast(UsageEvent.timestamp, Date).label("date"),
        UsageEvent.environment,
        func.sum(UsageEvent.cost_usd).label("total_cost_usd"),
        func.sum(UsageEvent.total_tokens).label("total_tokens"),
        func.count().label("request_count"),
    ).where(
        date_filter
    ).group_by(
        cast(UsageEvent.timestamp, Date),
        UsageEvent.environment,
    )

    rows = (await session.execute(stmt)).all()

    for row in rows:
        upsert = pg_insert(DailyCostRollup).values(
            date=row.date,
            environment=row.environment,
            total_cost_usd=row.total_cost_usd,
            total_tokens=row.total_tokens,
            request_count=row.request_count,
        ).on_conflict_do_update(
            index_elements=["date", "environment"],
            set_={
                "total_cost_usd": row.total_cost_usd,
                "total_tokens": row.total_tokens,
                "request_count": row.request_count,
                "updated_at": func.now(),
            },
        )
        await session.execute(upsert)


# ── Model cost rollup ──────────────────────────────────────
async def _rollup_model_cost(
    session: AsyncSession,
    target_date: datetime.date,
    date_filter,  # type: ignore[no-untyped-def]
) -> None:
    """Aggregate into model_cost_rollups."""
    stmt = select(
        cast(UsageEvent.timestamp, Date).label("date"),
        UsageEvent.model_name,
        UsageEvent.environment,
        func.sum(UsageEvent.cost_usd).label("total_cost_usd"),
        func.sum(UsageEvent.total_tokens).label("total_tokens"),
        func.count().label("request_count"),
    ).where(
        date_filter
    ).group_by(
        cast(UsageEvent.timestamp, Date),
        UsageEvent.model_name,
        UsageEvent.environment,
    )

    rows = (await session.execute(stmt)).all()

    for row in rows:
        upsert = pg_insert(ModelCostRollup).values(
            date=row.date,
            model_name=row.model_name,
            environment=row.environment,
            total_cost_usd=row.total_cost_usd,
            total_tokens=row.total_tokens,
            request_count=row.request_count,
        ).on_conflict_do_update(
            index_elements=["date", "model_name", "environment"],
            set_={
                "total_cost_usd": row.total_cost_usd,
                "total_tokens": row.total_tokens,
                "request_count": row.request_count,
                "updated_at": func.now(),
            },
        )
        await session.execute(upsert)


# ── Endpoint cost rollup ────────────────────────────────────
async def _rollup_endpoint_cost(
    session: AsyncSession,
    target_date: datetime.date,
    date_filter,  # type: ignore[no-untyped-def]
) -> None:
    """Aggregate into endpoint_cost_rollups."""
    stmt = select(
        cast(UsageEvent.timestamp, Date).label("date"),
        UsageEvent.endpoint,
        UsageEvent.environment,
        func.sum(UsageEvent.cost_usd).label("total_cost_usd"),
        func.count().label("request_count"),
    ).where(
        date_filter
    ).group_by(
        cast(UsageEvent.timestamp, Date),
        UsageEvent.endpoint,
        UsageEvent.environment,
    )

    rows = (await session.execute(stmt)).all()

    for row in rows:
        upsert = pg_insert(EndpointCostRollup).values(
            date=row.date,
            endpoint=row.endpoint,
            environment=row.environment,
            total_cost_usd=row.total_cost_usd,
            request_count=row.request_count,
        ).on_conflict_do_update(
            index_elements=["date", "endpoint", "environment"],
            set_={
                "total_cost_usd": row.total_cost_usd,
                "request_count": row.request_count,
                "updated_at": func.now(),
            },
        )
        await session.execute(upsert)
