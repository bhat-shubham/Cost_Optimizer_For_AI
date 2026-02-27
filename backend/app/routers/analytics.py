"""
Analytics router — cost insights from pre-aggregated rollup tables.

Phase 2B: All endpoints now read from rollup tables instead of scanning
usage_events. This makes analytics O(days) instead of O(events).

Decimal precision is preserved end-to-end (DB NUMERIC → Python Decimal → JSON string).

Endpoints:
  GET /analytics/daily-cost      — total cost per calendar day
  GET /analytics/by-model        — cost breakdown per model
  GET /analytics/by-endpoint     — cost breakdown per application endpoint
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.rollups import (
    DailyCostRollup,
    EndpointCostRollup,
    ModelCostRollup,
)
from app.schemas.analytics import CostByEndpointOut, CostByModelOut, DailyCostOut

router = APIRouter(tags=["Analytics"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


# ── 1. Daily Cost ───────────────────────────────────────────
@router.get(
    "/daily-cost",
    response_model=list[DailyCostOut],
    summary="Total cost per calendar day",
    description=(
        "Reads from daily_cost_rollups. "
        "Returns results ordered by date ascending. "
        "Empty dataset returns an empty list."
    ),
)
async def get_daily_cost(session: DbSession) -> list[DailyCostOut]:
    """
    Reads pre-aggregated daily cost from rollup table.
    O(days × environments) instead of O(events).
    """
    stmt = (
        select(DailyCostRollup)
        .order_by(DailyCostRollup.date.asc())
    )

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [DailyCostOut.model_validate(row, from_attributes=True) for row in rows]


# ── 2. Cost by Model ───────────────────────────────────────
@router.get(
    "/by-model",
    response_model=list[CostByModelOut],
    summary="Cost breakdown per AI model",
    description=(
        "Reads from model_cost_rollups. "
        "Useful for identifying which models drive spend."
    ),
)
async def get_cost_by_model(session: DbSession) -> list[CostByModelOut]:
    """
    Reads pre-aggregated model cost from rollup table.
    O(days × models × environments) instead of O(events).
    """
    stmt = (
        select(ModelCostRollup)
        .order_by(ModelCostRollup.date.asc(), ModelCostRollup.model_name)
    )

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [CostByModelOut.model_validate(row, from_attributes=True) for row in rows]


# ── 3. Cost by Endpoint ────────────────────────────────────
@router.get(
    "/by-endpoint",
    response_model=list[CostByEndpointOut],
    summary="Cost breakdown per application endpoint",
    description=(
        "Reads from endpoint_cost_rollups. "
        "Helps identify which features consume the most AI budget."
    ),
)
async def get_cost_by_endpoint(session: DbSession) -> list[CostByEndpointOut]:
    """
    Reads pre-aggregated endpoint cost from rollup table.
    O(days × endpoints × environments) instead of O(events).
    """
    stmt = (
        select(EndpointCostRollup)
        .order_by(EndpointCostRollup.date.asc(), EndpointCostRollup.endpoint)
    )

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [CostByEndpointOut.model_validate(row, from_attributes=True) for row in rows]
