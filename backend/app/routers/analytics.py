"""
Analytics router — cost insights from pre-aggregated rollup tables.

Phase 3.1: All endpoints require authentication and are scoped to the
authenticated project's data only.

Decimal precision is preserved end-to-end (DB NUMERIC → Python Decimal → JSON string).

Endpoints:
  GET /analytics/daily-cost      — total cost per calendar day
  GET /analytics/by-model        — cost breakdown per model
  GET /analytics/by-endpoint     — cost breakdown per application endpoint
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_project
from app.core.database import get_db_session
from app.models.project import Project
from app.models.rollups import (
    DailyCostRollup,
    EndpointCostRollup,
    ModelCostRollup,
)
from app.schemas.analytics import CostByEndpointOut, CostByModelOut, DailyCostOut

router = APIRouter(tags=["Analytics"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentProject = Annotated[Project, Depends(get_current_project)]


# ── 1. Daily Cost ───────────────────────────────────────────
@router.get(
    "/daily-cost",
    response_model=list[DailyCostOut],
    summary="Total cost per calendar day",
    description=(
        "Reads from daily_cost_rollups, scoped to the authenticated project. "
        "Returns results ordered by date ascending."
    ),
)
async def get_daily_cost(
    session: DbSession,
    project: CurrentProject,
) -> list[DailyCostOut]:
    """Reads pre-aggregated daily cost, filtered by project."""
    stmt = (
        select(DailyCostRollup)
        .where(DailyCostRollup.project_id == project.id)
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
        "Reads from model_cost_rollups, scoped to the authenticated project."
    ),
)
async def get_cost_by_model(
    session: DbSession,
    project: CurrentProject,
) -> list[CostByModelOut]:
    """Reads pre-aggregated model cost, filtered by project."""
    stmt = (
        select(ModelCostRollup)
        .where(ModelCostRollup.project_id == project.id)
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
        "Reads from endpoint_cost_rollups, scoped to the authenticated project."
    ),
)
async def get_cost_by_endpoint(
    session: DbSession,
    project: CurrentProject,
) -> list[CostByEndpointOut]:
    """Reads pre-aggregated endpoint cost, filtered by project."""
    stmt = (
        select(EndpointCostRollup)
        .where(EndpointCostRollup.project_id == project.id)
        .order_by(EndpointCostRollup.date.asc(), EndpointCostRollup.endpoint)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [CostByEndpointOut.model_validate(row, from_attributes=True) for row in rows]
