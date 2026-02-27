"""
Analytics router — aggregated cost insights from usage_events.

All aggregation happens in SQL via GROUP BY — no Python-side loops.
Decimal precision is preserved end-to-end (DB NUMERIC → Python Decimal → JSON string).

Endpoints:
  GET /analytics/daily-cost      — total cost per calendar day
  GET /analytics/by-model        — cost breakdown per model
  GET /analytics/by-endpoint     — cost breakdown per application endpoint
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.usage import UsageEvent
from app.schemas.analytics import CostByEndpointOut, CostByModelOut, DailyCostOut

router = APIRouter(tags=["Analytics"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


# ── 1. Daily Cost ───────────────────────────────────────────
@router.get(
    "/daily-cost",
    response_model=list[DailyCostOut],
    summary="Total cost per calendar day",
    description=(
        "Aggregates cost_usd by calendar day (UTC). "
        "Returns results ordered by date ascending. "
        "Empty dataset returns an empty list."
    ),
)
async def get_daily_cost(session: DbSession) -> list[DailyCostOut]:
    """
    SQL: SELECT DATE(timestamp) AS date, SUM(cost_usd) AS total_cost_usd
         FROM usage_events GROUP BY date ORDER BY date ASC

    Uses cast(timestamp, Date) which maps to DATE() in Postgres.
    The ix_usage_events_timestamp index supports this query.
    """
    date_col = cast(UsageEvent.timestamp, Date).label("date")

    stmt = (
        select(
            date_col,
            func.sum(UsageEvent.cost_usd).label("total_cost_usd"),
        )
        .group_by(date_col)
        .order_by(date_col.asc())
    )

    result = await session.execute(stmt)
    rows = result.all()
    return [DailyCostOut.model_validate(row, from_attributes=True) for row in rows]


# ── 2. Cost by Model ───────────────────────────────────────
@router.get(
    "/by-model",
    response_model=list[CostByModelOut],
    summary="Cost breakdown per AI model",
    description=(
        "Aggregates cost, tokens, and request count grouped by model_name. "
        "Useful for identifying which models drive spend."
    ),
)
async def get_cost_by_model(session: DbSession) -> list[CostByModelOut]:
    """
    SQL: SELECT model_name, SUM(cost_usd), SUM(total_tokens), COUNT(*)
         FROM usage_events GROUP BY model_name

    The ix_usage_events_model_name index supports this GROUP BY.
    """
    stmt = select(
        UsageEvent.model_name,
        func.sum(UsageEvent.cost_usd).label("total_cost_usd"),
        func.sum(UsageEvent.total_tokens).label("total_tokens"),
        func.count().label("request_count"),
    ).group_by(UsageEvent.model_name)

    result = await session.execute(stmt)
    rows = result.all()
    return [CostByModelOut.model_validate(row, from_attributes=True) for row in rows]


# ── 3. Cost by Endpoint ────────────────────────────────────
@router.get(
    "/by-endpoint",
    response_model=list[CostByEndpointOut],
    summary="Cost breakdown per application endpoint",
    description=(
        "Aggregates cost and request count grouped by the calling endpoint. "
        "Helps identify which features consume the most AI budget."
    ),
)
async def get_cost_by_endpoint(session: DbSession) -> list[CostByEndpointOut]:
    """
    SQL: SELECT endpoint, SUM(cost_usd), COUNT(*)
         FROM usage_events GROUP BY endpoint

    No dedicated index on endpoint yet — acceptable for Phase 2A volumes.
    Can add one later if this query becomes a bottleneck.
    """
    stmt = select(
        UsageEvent.endpoint,
        func.sum(UsageEvent.cost_usd).label("total_cost_usd"),
        func.count().label("request_count"),
    ).group_by(UsageEvent.endpoint)

    result = await session.execute(stmt)
    rows = result.all()
    return [CostByEndpointOut.model_validate(row, from_attributes=True) for row in rows]
