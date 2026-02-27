"""
Analytics router — cost insights from pre-aggregated rollup tables.

Phase 3.2: All endpoints require authentication and are rate-limited
(RPM + RPD). Data is scoped to the authenticated project.

Endpoints:
  GET /analytics/daily-cost      — total cost per calendar day
  GET /analytics/by-model        — cost breakdown per model
  GET /analytics/by-endpoint     — cost breakdown per application endpoint
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AuthContext
from app.auth.rate_limit import enforce_rate_limit
from app.core.database import get_db_session
from app.models.rollups import (
    DailyCostRollup,
    EndpointCostRollup,
    ModelCostRollup,
)
from app.schemas.analytics import CostByEndpointOut, CostByModelOut, DailyCostOut

router = APIRouter(tags=["Analytics"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
Auth = Annotated[AuthContext, Depends(enforce_rate_limit)]


# ── 1. Daily Cost ───────────────────────────────────────────
@router.get(
    "/daily-cost",
    response_model=list[DailyCostOut],
    summary="Total cost per calendar day",
    description=(
        "Reads from daily_cost_rollups, scoped to the authenticated project. "
        "Rate limited."
    ),
)
async def get_daily_cost(
    session: DbSession,
    auth: Auth,
) -> list[DailyCostOut]:
    """Reads pre-aggregated daily cost, filtered by project."""
    stmt = (
        select(DailyCostRollup)
        .where(DailyCostRollup.project_id == auth.project.id)
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
        "Reads from model_cost_rollups, scoped to the authenticated project. "
        "Rate limited."
    ),
)
async def get_cost_by_model(
    session: DbSession,
    auth: Auth,
) -> list[CostByModelOut]:
    """Reads pre-aggregated model cost, filtered by project."""
    stmt = (
        select(ModelCostRollup)
        .where(ModelCostRollup.project_id == auth.project.id)
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
        "Reads from endpoint_cost_rollups, scoped to the authenticated project. "
        "Rate limited."
    ),
)
async def get_cost_by_endpoint(
    session: DbSession,
    auth: Auth,
) -> list[CostByEndpointOut]:
    """Reads pre-aggregated endpoint cost, filtered by project."""
    stmt = (
        select(EndpointCostRollup)
        .where(EndpointCostRollup.project_id == auth.project.id)
        .order_by(EndpointCostRollup.date.asc(), EndpointCostRollup.endpoint)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [CostByEndpointOut.model_validate(row, from_attributes=True) for row in rows]
