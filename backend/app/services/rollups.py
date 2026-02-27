"""
Idempotent rollup aggregation service.

Aggregates usage_events into pre-computed rollup tables for fast analytics.
usage_events is the source of truth — rollups are derived and reproducible.

Phase 3.1: project_id is now a GROUP BY dimension in all rollups.

IDEMPOTENCY:
  Uses INSERT … ON CONFLICT (pk) DO UPDATE for each rollup table.
  Running this twice for the same date produces identical results.
  ON CONFLICT is atomic per row — no gap between DELETE and INSERT
  where concurrent readers might see zero data.
"""

import datetime
import logging

from sqlalchemy import cast, Date, func, select
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

    Only processes events that have a project_id (pre-auth data is excluded).
    All 3 rollups are committed in a single transaction.
    """
    logger.info("Running rollups for %s", target_date)

    date_filter = cast(UsageEvent.timestamp, Date) == target_date
    # Only rollup events that belong to a project
    project_filter = UsageEvent.project_id.isnot(None)

    await _rollup_daily_cost(session, date_filter, project_filter)
    await _rollup_model_cost(session, date_filter, project_filter)
    await _rollup_endpoint_cost(session, date_filter, project_filter)

    await session.commit()
    logger.info("Rollups for %s committed ✓", target_date)


# ── Daily cost rollup ───────────────────────────────────────
async def _rollup_daily_cost(
    session: AsyncSession,
    date_filter,
    project_filter,
) -> None:
    """Aggregate into daily_cost_rollups, grouped by (date, env, project_id)."""
    stmt = select(
        cast(UsageEvent.timestamp, Date).label("date"),
        UsageEvent.environment,
        UsageEvent.project_id,
        func.sum(UsageEvent.cost_usd).label("total_cost_usd"),
        func.sum(UsageEvent.total_tokens).label("total_tokens"),
        func.count().label("request_count"),
    ).where(
        date_filter, project_filter,
    ).group_by(
        cast(UsageEvent.timestamp, Date),
        UsageEvent.environment,
        UsageEvent.project_id,
    )

    rows = (await session.execute(stmt)).all()

    for row in rows:
        upsert = pg_insert(DailyCostRollup).values(
            date=row.date,
            environment=row.environment,
            project_id=row.project_id,
            total_cost_usd=row.total_cost_usd,
            total_tokens=row.total_tokens,
            request_count=row.request_count,
        ).on_conflict_do_update(
            index_elements=["date", "environment", "project_id"],
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
    date_filter,
    project_filter,
) -> None:
    """Aggregate into model_cost_rollups, grouped by (date, model, env, project_id)."""
    stmt = select(
        cast(UsageEvent.timestamp, Date).label("date"),
        UsageEvent.model_name,
        UsageEvent.environment,
        UsageEvent.project_id,
        func.sum(UsageEvent.cost_usd).label("total_cost_usd"),
        func.sum(UsageEvent.total_tokens).label("total_tokens"),
        func.count().label("request_count"),
    ).where(
        date_filter, project_filter,
    ).group_by(
        cast(UsageEvent.timestamp, Date),
        UsageEvent.model_name,
        UsageEvent.environment,
        UsageEvent.project_id,
    )

    rows = (await session.execute(stmt)).all()

    for row in rows:
        upsert = pg_insert(ModelCostRollup).values(
            date=row.date,
            model_name=row.model_name,
            environment=row.environment,
            project_id=row.project_id,
            total_cost_usd=row.total_cost_usd,
            total_tokens=row.total_tokens,
            request_count=row.request_count,
        ).on_conflict_do_update(
            index_elements=["date", "model_name", "environment", "project_id"],
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
    date_filter,
    project_filter,
) -> None:
    """Aggregate into endpoint_cost_rollups, grouped by (date, endpoint, env, project_id)."""
    stmt = select(
        cast(UsageEvent.timestamp, Date).label("date"),
        UsageEvent.endpoint,
        UsageEvent.environment,
        UsageEvent.project_id,
        func.sum(UsageEvent.cost_usd).label("total_cost_usd"),
        func.count().label("request_count"),
    ).where(
        date_filter, project_filter,
    ).group_by(
        cast(UsageEvent.timestamp, Date),
        UsageEvent.endpoint,
        UsageEvent.environment,
        UsageEvent.project_id,
    )

    rows = (await session.execute(stmt)).all()

    for row in rows:
        upsert = pg_insert(EndpointCostRollup).values(
            date=row.date,
            endpoint=row.endpoint,
            environment=row.environment,
            project_id=row.project_id,
            total_cost_usd=row.total_cost_usd,
            request_count=row.request_count,
        ).on_conflict_do_update(
            index_elements=["date", "endpoint", "environment", "project_id"],
            set_={
                "total_cost_usd": row.total_cost_usd,
                "request_count": row.request_count,
                "updated_at": func.now(),
            },
        )
        await session.execute(upsert)
