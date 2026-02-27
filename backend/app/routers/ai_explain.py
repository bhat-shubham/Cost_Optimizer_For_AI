"""
AI explanation router — human-readable cost insights powered by LLM.

Phase 3.2: Requires authentication AND AI-specific rate limit (RPM + RPD + AED).
Each AI explain call consumes from the general request pool AND the AI daily cap.

GET /ai/explain/daily-cost?date=YYYY-MM-DD&environment=dev
"""

import datetime
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AuthContext
from app.auth.rate_limit import enforce_ai_rate_limit
from app.core.database import get_db_session
from app.schemas.explain import DailyCostExplanation
from app.services.explainers import build_daily_cost_context
from app.services.llm_client import generate_explanation

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Explain"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
Auth = Annotated[AuthContext, Depends(enforce_ai_rate_limit)]


@router.get(
    "/daily-cost",
    response_model=DailyCostExplanation,
    summary="AI explanation of daily cost behavior",
    description=(
        "Fetches pre-computed cost facts (scoped to project), "
        "then uses an LLM to narrate. "
        "Rate limited: RPM + RPD + 20 AI explanations/day."
    ),
)
async def explain_daily_cost(
    session: DbSession,
    auth: Auth,
    date: datetime.date = Query(
        ...,
        description="Target date (YYYY-MM-DD)",
        examples=["2026-02-27"],
    ),
    environment: str = Query(
        default="dev",
        description="Deployment environment",
        examples=["dev", "prod"],
    ),
) -> DailyCostExplanation:
    """
    1. Build deterministic context (Python math, no AI) — scoped to project
    2. Send context to LLM for narration
    3. Return structured explanation
    """

    # ── 1. Deterministic context ────────────────────────────
    context = await build_daily_cost_context(
        session, date, environment, project_id=auth.project.id,
    )

    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No cost data found for {date} in '{environment}' environment.",
        )

    # ── 2. LLM narration ───────────────────────────────────
    try:
        explanation = await generate_explanation(context)
    except RuntimeError:
        logger.exception("LLM explanation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI explanation service is temporarily unavailable.",
        )

    # ── 3. Return structured response ──────────────────────
    return DailyCostExplanation(
        date=date,
        environment=environment,
        summary=explanation["summary"],
        key_drivers=explanation["key_drivers"],
        recommendations=explanation["recommendations"],
    )
