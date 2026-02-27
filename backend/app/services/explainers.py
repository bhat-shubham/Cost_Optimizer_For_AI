"""
Deterministic explanation context builder.

This service does ALL numerical computation — the LLM never touches math.
It reads from rollup tables and produces a structured dictionary of facts
that the LLM will narrate into human-readable text.

Phase 3.1: All queries are scoped by project_id.

CRITICAL DESIGN RULE:
  Zero AI logic lives here. Every number, comparison, and percentage
  is computed with exact Decimal arithmetic in Python.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rollups import (
    DailyCostRollup,
    EndpointCostRollup,
    ModelCostRollup,
)

logger = logging.getLogger(__name__)

# How many top drivers to include in the context
_TOP_N = 5


async def build_daily_cost_context(
    session: AsyncSession,
    target_date: datetime.date,
    environment: str,
    *,
    project_id: uuid.UUID,
) -> dict[str, Any] | None:
    """
    Build a structured facts dictionary for a given date, environment, and project.

    Returns None if no rollup data exists (caller should return 404).
    """

    # ── 1. Today's daily rollup ─────────────────────────────
    today_row = await _fetch_daily_rollup(session, target_date, environment, project_id)
    if today_row is None:
        return None

    # ── 2. Previous day's rollup (may not exist) ────────────
    prev_date = target_date - datetime.timedelta(days=1)
    prev_row = await _fetch_daily_rollup(session, prev_date, environment, project_id)

    # ── 3. Compute day-over-day change (deterministic) ──────
    direction: str
    percentage_change: str | None = None
    previous_day_cost: str | None = None

    if prev_row is None:
        direction = "new"
    else:
        previous_day_cost = str(prev_row.total_cost_usd)
        today_cost = Decimal(str(today_row.total_cost_usd))
        prev_cost = Decimal(str(prev_row.total_cost_usd))

        if prev_cost == 0:
            if today_cost > 0:
                direction = "increased"
                percentage_change = "∞ (from $0)"
            else:
                direction = "unchanged"
                percentage_change = "0%"
        else:
            change = ((today_cost - prev_cost) / prev_cost * 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if change > 0:
                direction = "increased"
                percentage_change = f"+{change}%"
            elif change < 0:
                direction = "decreased"
                percentage_change = f"{change}%"
            else:
                direction = "unchanged"
                percentage_change = "0%"

    # ── 4. Top models by cost ───────────────────────────────
    top_models = await _fetch_top_models(session, target_date, environment, project_id)

    # ── 5. Top endpoints by cost ────────────────────────────
    top_endpoints = await _fetch_top_endpoints(session, target_date, environment, project_id)

    # ── 6. Assemble the context ─────────────────────────────
    return {
        "date": target_date.isoformat(),
        "environment": environment,
        "total_cost_today": str(today_row.total_cost_usd),
        "total_tokens": today_row.total_tokens,
        "request_count": today_row.request_count,
        "previous_day_cost": previous_day_cost,
        "percentage_change": percentage_change,
        "direction": direction,
        "top_models": top_models,
        "top_endpoints": top_endpoints,
    }


# ── Internal helpers ────────────────────────────────────────

async def _fetch_daily_rollup(
    session: AsyncSession,
    date: datetime.date,
    environment: str,
    project_id: uuid.UUID,
) -> DailyCostRollup | None:
    """Fetch a single daily rollup row, scoped to project."""
    stmt = select(DailyCostRollup).where(
        DailyCostRollup.date == date,
        DailyCostRollup.environment == environment,
        DailyCostRollup.project_id == project_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _fetch_top_models(
    session: AsyncSession,
    date: datetime.date,
    environment: str,
    project_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Fetch top N models by cost, scoped to project."""
    stmt = (
        select(ModelCostRollup)
        .where(
            ModelCostRollup.date == date,
            ModelCostRollup.environment == environment,
            ModelCostRollup.project_id == project_id,
        )
        .order_by(ModelCostRollup.total_cost_usd.desc())
        .limit(_TOP_N)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "model_name": r.model_name,
            "cost_usd": str(r.total_cost_usd),
            "total_tokens": r.total_tokens,
            "request_count": r.request_count,
        }
        for r in rows
    ]


async def _fetch_top_endpoints(
    session: AsyncSession,
    date: datetime.date,
    environment: str,
    project_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Fetch top N endpoints by cost, scoped to project."""
    stmt = (
        select(EndpointCostRollup)
        .where(
            EndpointCostRollup.date == date,
            EndpointCostRollup.environment == environment,
            EndpointCostRollup.project_id == project_id,
        )
        .order_by(EndpointCostRollup.total_cost_usd.desc())
        .limit(_TOP_N)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "endpoint": r.endpoint,
            "cost_usd": str(r.total_cost_usd),
            "request_count": r.request_count,
        }
        for r in rows
    ]
